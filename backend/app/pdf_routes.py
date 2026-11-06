"""PDF scores (decided 2026-10-27). The director uploads one score or the parts of a work (one PDF per
instrument); ScoreMaster keeps the PDFs and starts the reader in its private GitHub repository (scoremaster-omr) with a
one-time token. The reader, with no session, downloads the PDFs with that token, tells its progress and sends back
the work's MusicXML or why it failed; ScoreMaster then analyses the work like any upload, marked as read from a PDF.
The token is kept only as its sha256 and is spent, with the PDFs, when the result arrives. The reader may also send the
work already prepared (2026-11-04), so that Render does not spend minutes reading it again with music21."""
import base64
import binascii
import hashlib
import json
import logging
from xml.etree import ElementTree as ET
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from backend.app.dependencies import (authenticated_user, get_analysis_repository, get_instrument_store, get_library_repository,
                                      get_omr_dispatcher, get_pdf_import_repository, get_playback_store, get_score_store)
from backend.app.library_routes import valid_band_profile
from backend.app.stored_scores import clear_parsed_works
from backend.app.work_analysis import analyze_and_store
from backend.application.accounts import User
from backend.domain.instrument_catalog import catalog_entries
from backend.parsers.playback import TIMELINE_VERSION
from backend.parsers.prepare import final_musicxml, opened_final, usable_score, usable_timeline
from backend.parsers.reader import ONE_READING, ask_for_turn, end_turn
from backend.parsers.score_codec import SCORE_VERSION
from backend.application.pdf_imports import OmrDispatcher, PdfImport, PdfImportRepository

router = APIRouter()
logger = logging.getLogger(__name__)
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_FILES = 40
MAX_MUSICXML_CHARACTERS = 20 * 1024 * 1024
MAX_PREPARED_CHARACTERS = 20 * 1024 * 1024
NOT_FOUND = "No se encontró la lectura del PDF."
# A reading that stopped telling its progress, or an analysis that never ended, is given up.
STALLED = {"queued": timedelta(minutes=30), "preparing": timedelta(minutes=30), "reading": timedelta(minutes=30),
           "analysing": timedelta(minutes=15)}
STALLED_ERROR = {"analysing": "No se pudo analizar la obra leída. Vuelve a subir el PDF.",
                 "queued": "El lector de PDF no respondió a tiempo. Vuelve a intentarlo.",
                 "preparing": "El lector de PDF no respondió a tiempo. Vuelve a intentarlo.",
                 "reading": "El lector de PDF no respondió a tiempo. Vuelve a intentarlo."}


def _sha256(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _uuid(value: str, status: int, detail: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise HTTPException(status_code=status, detail=detail) from None


def _public(found: PdfImport) -> dict:
    return {"status": found.status, "pages_done": found.pages_done, "pages_total": found.pages_total,
            "error": found.error, "work_id": str(found.work_id) if found.work_id else None}


@router.get("/pdf-imports/available")
def pdf_available(user: User = Depends(authenticated_user),
                  dispatcher: Optional[OmrDispatcher] = Depends(get_omr_dispatcher)):
    return {"available": dispatcher is not None}


@router.post("/pdf-imports", status_code=202)
def create_pdf_import(request: Request, files: list[UploadFile] = File(default=[]), kind: str = Form(...),
                      title: str = Form("", max_length=200), total_minutes: int = Form(60, ge=5, le=600),
                      band_profile: str = Form("{}", max_length=64 * 1024), user: User = Depends(authenticated_user),
                      imports: PdfImportRepository = Depends(get_pdf_import_repository),
                      dispatcher: Optional[OmrDispatcher] = Depends(get_omr_dispatcher)):
    if dispatcher is None:
        raise HTTPException(status_code=503, detail="La lectura de PDF no está configurada en este servidor.")
    if kind not in ("auto", "score", "parts"):
        raise HTTPException(status_code=422, detail="Elige qué tiene el PDF: detectar solo, partitura general o particellas.")
    if not files or len(files) > MAX_FILES:
        raise HTTPException(status_code=422, detail=f"Sube entre 1 y {MAX_FILES} PDF.")
    try:
        profile = json.loads(band_profile or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="band_profile must be valid JSON.") from exc
    if not valid_band_profile(profile):
        raise HTTPException(status_code=400, detail="band_profile must map instruments to musician counts.")
    saved = []
    for upload in files:
        name = Path(upload.filename or "").name
        content = upload.file.read(MAX_FILE_BYTES + 1)
        if not name.lower().endswith(".pdf") or not content.startswith(b"%PDF"):
            raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF.")
        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail=f"Cada PDF puede tener hasta {MAX_FILE_BYTES // (1024 * 1024)} MB.")
        saved.append((name, content))
    token = secrets.token_urlsafe(32)
    work_title = title.strip() or Path(saved[0][0]).stem
    created = imports.create(user.id, kind, work_title, saved, _sha256(token), profile, total_minutes)
    # The reader calls back on this server's public address (Render's, over https).
    base = (os.environ.get("PUBLIC_BASE_URL") or str(request.base_url)).rstrip("/")
    callback = f"{base}/omr/imports/{created.id}"
    try:
        dispatcher.dispatch({"kind": kind, "title": work_title, "token": token, "callback": callback,
                             "files": [{"name": name, "url": f"{callback}/files/{position}"}
                                       for position, (name, _) in enumerate(saved)]})
    except Exception:
        logger.warning("No se pudo poner en marcha el lector de PDF.", exc_info=True)
        imports.failed(created.id, "No se pudo poner en marcha el lector de PDF.")
        raise HTTPException(status_code=502, detail="No se pudo poner en marcha el lector de PDF. Inténtalo de nuevo.")
    return JSONResponse(status_code=202, content={"id": str(created.id)})


@router.get("/pdf-imports/{import_id}")
def pdf_import_status(import_id: str, user: User = Depends(authenticated_user),
                      imports: PdfImportRepository = Depends(get_pdf_import_repository)):
    found = imports.for_owner(user.id, _uuid(import_id, 404, NOT_FOUND))
    if found is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    limit = STALLED.get(found.status)
    if limit and found.updated_at and datetime.now(timezone.utc) - found.updated_at > limit:
        imports.failed(found.id, STALLED_ERROR[found.status])
        found = imports.for_owner(user.id, found.id)
    return _public(found)


# --- the reader in GitHub Actions: no session, only the one-time token of its job ------------------------------------

def _reader(import_id: str, authorization: Optional[str], imports: PdfImportRepository) -> PdfImport:
    token = (authorization or "").removeprefix("Bearer ").strip()
    found = imports.for_reader(_uuid(import_id, 401, "No autorizado."), _sha256(token)) if token else None
    if found is None:
        raise HTTPException(status_code=401, detail="No autorizado.")
    return found


class Progress(BaseModel):
    pages_done: int = Field(ge=0, le=10000)
    pages_total: int = Field(ge=0, le=10000)
    # "preparing" while the reader installs copista (2026-10-28); pages read mean "reading".
    stage: Optional[str] = Field(default=None, pattern="^(preparing|reading)$")


class Result(BaseModel):
    musicxml: Optional[str] = Field(default=None, max_length=MAX_MUSICXML_CHARACTERS)
    error: Optional[str] = Field(default=None, max_length=300)
    # Where the work came from and whether the score says it is in C (2026-10-29): parts are always transposed.
    source: Optional[str] = Field(default=None, pattern="^(parts|score)$")
    concert_pitch: bool = False
    # The work prepared by the reader (2026-11-04). A plain dict: what does not fit is ignored here, it never loses the
    # reading of a whole PDF to a refused request.
    prepared: Optional[dict] = None


@router.get("/omr/imports/{import_id}/files/{position}")
def reader_file(import_id: str, position: int, authorization: Optional[str] = Header(default=None),
                imports: PdfImportRepository = Depends(get_pdf_import_repository)):
    found = imports.file(_reader(import_id, authorization, imports).id, position)
    if found is None:
        raise HTTPException(status_code=404, detail="No existe ese PDF.")
    return Response(content=found[1], media_type="application/pdf")


@router.post("/omr/imports/{import_id}/progress", status_code=204)
def reader_progress(import_id: str, progress: Progress, authorization: Optional[str] = Header(default=None),
                    imports: PdfImportRepository = Depends(get_pdf_import_repository)):
    imports.progress(_reader(import_id, authorization, imports).id, progress.pages_done, progress.pages_total,
                     "preparing" if progress.stage == "preparing" else "reading")
    return Response(status_code=204)


@router.get("/omr/imports/{import_id}/instruments")
def reader_instruments(import_id: str, authorization: Optional[str] = Header(default=None),
                       imports: PdfImportRepository = Depends(get_pdf_import_repository),
                       instruments=Depends(get_instrument_store)):
    """The catalog the reader names the parts with (2026-10-28): the common instruments with their names and the part
    names the account confirmed before (normalized, without part numbers)."""
    found = _reader(import_id, authorization, imports)
    learned = instruments.learned(found.user_id) if instruments else {}
    return {"instruments": [{"id": identity.canonical_id, "section": identity.section, "family": identity.family,
                             "variant": identity.variant, "transposition": identity.transposition,
                             "label_es": identity.label_es, "label_en": identity.label_en, "aliases": list(identity.aliases),
                             "sound": identity.sound, "rehearsal_group": identity.rehearsal_group}
                            for identity in catalog_entries()],
            "learned": sorted(learned), "learned_instruments": learned}


# Render's 512 MB (2026-11-06): a reading of 34 staves is a MusicXML of 12 MB; its body and its XML tree take ~300 MB. Render
# ran out of memory receiving one while music21 read another work: the reader now finishes the work and sends it compressed,
# and one reading goes at a time, told before its body is read.
_READING_SENT = re.compile(r"^/omr/imports/[^/]+/(final|result)$")


class OneReadingAtATime:
    """Wraps the whole request, its analysis in the background included. Without a token, the route answers 401 as usual."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST" or not _READING_SENT.match(scope["path"]) \
                or not dict(scope["headers"]).get(b"authorization"):
            await self.app(scope, receive, send)
            return
        if not ask_for_turn():
            await JSONResponse(status_code=503, content={"detail": "ScoreMaster está procesando otra obra."})(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        finally:
            # Its model is in the store; the works of the startup need that room.
            clear_parsed_works()
            end_turn()


def _final_musicxml(found: PdfImport, result: Result, instruments) -> bytes:
    """The bytes kept for the work, for a reader that sends what it read. Raises ET.ParseError."""
    return final_musicxml((result.musicxml or "").encode("utf-8"), instruments.learned(found.user_id) if instruments else None,
                          result.concert_pitch, result.source or "parts")


def _keep_prepared(content: bytes, prepared: Optional[dict], score_store, playback_store) -> None:
    """What the reader prepared, only for the bytes ScoreMaster keeps and never over what is stored: prepared works are
    shared by content between accounts. Whatever does not fit is left out, and Render reads the work as any other."""
    if not prepared or prepared.get("sha256") != hashlib.sha256(content).hexdigest():
        return
    key = prepared["sha256"]
    for store, version, usable, name in ((score_store, SCORE_VERSION, usable_score, "score"),
                                         (playback_store, TIMELINE_VERSION, usable_timeline, "timeline")):
        encoded = prepared.get(name)
        if (store is None or prepared.get(name + "_version") != version or not isinstance(encoded, str)
                or len(encoded) > MAX_PREPARED_CHARACTERS):
            continue
        try:
            data = base64.b64decode(encoded, validate=True)
            if usable(data) and store.load(key, version) is None:
                store.save(key, version, data)
        except (binascii.Error, ValueError):
            continue
        except Exception:
            logger.warning("No se pudo guardar lo que preparó el lector de PDF.", exc_info=True)


def _analyse(found: PdfImport, imports, repository, library, score_store, instruments=None, prepared=None,
             playback_store=None) -> None:
    try:
        content = imports.musicxml(found.id)
        _keep_prepared(content, prepared, score_store, playback_store)
        # The instruments the account confirmed before name the parts the catalog does not know (2026-10-28).
        learned = instruments.learned(found.user_id) if instruments else None
        saved = analyze_and_store(content, found.title + ".musicxml", found.user_id, found.band_profile,
                                  found.total_minutes, {}, repository, library, score_store, source_format="pdf",
                                  learned=learned)
        imports.done(found.id, UUID(saved["work_id"]))
    except Exception:
        logger.warning("No se pudo analizar una obra leída de PDF.", exc_info=True)
        imports.failed(found.id, "No se pudo analizar la obra leída. Revisa el PDF y vuelve a subirlo.")


@router.post("/omr/imports/{import_id}/final")
def reader_final(import_id: str, result: Result, authorization: Optional[str] = Header(default=None),
                 imports: PdfImportRepository = Depends(get_pdf_import_repository),
                 instruments=Depends(get_instrument_store)):
    """The bytes that the same result would keep (2026-11-04), which the reader prepares. Changes nothing."""
    found = _reader(import_id, authorization, imports)
    if not result.musicxml or "<!ENTITY" in result.musicxml:
        raise HTTPException(status_code=422, detail="La lectura no es MusicXML válido.")
    try:
        return {"musicxml": _final_musicxml(found, result, instruments).decode("utf-8")}
    except ET.ParseError:
        raise HTTPException(status_code=422, detail="La lectura no es MusicXML válido.") from None


@router.post("/omr/imports/{import_id}/result", status_code=202)
def reader_result(import_id: str, result: Result, background: BackgroundTasks,
                  authorization: Optional[str] = Header(default=None),
                  imports: PdfImportRepository = Depends(get_pdf_import_repository),
                  repository=Depends(get_analysis_repository), library=Depends(get_library_repository),
                  score_store=Depends(get_score_store), instruments=Depends(get_instrument_store),
                  playback_store=Depends(get_playback_store)):
    found = _reader(import_id, authorization, imports)
    finished = None
    if result.prepared and "musicxml_gz" in result.prepared:
        finished = opened_final(result.prepared, MAX_MUSICXML_CHARACTERS)
        if finished is None:
            # The token lives on: the reader sends what it read, as an older one does.
            raise HTTPException(status_code=422, detail="La obra terminada no es lo que dice ser.")
    content = (result.musicxml or "").encode("utf-8")
    if finished:
        imports.received(found.id, finished)
        background.add_task(_analyse, found, imports, repository, library, score_store, instruments, result.prepared,
                            playback_store)
    elif result.error or not content:
        imports.failed(found.id, result.error or "El lector no devolvió ninguna obra.")
    elif b"<!ENTITY" in content:
        imports.failed(found.id, "La lectura no es MusicXML válido.")
    else:
        try:
            content = _final_musicxml(found, result, instruments)
        except ET.ParseError:
            imports.failed(found.id, "La lectura no es MusicXML válido.")
            return JSONResponse(status_code=202, content={})
        imports.received(found.id, content)
        # music21 is slow on Render: the reader is answered at once and the work is analysed afterwards.
        background.add_task(_analyse, found, imports, repository, library, score_store, instruments, result.prepared,
                            playback_store)
    return JSONResponse(status_code=202, content={})
