"""PDF scores (decided 2026-10-27). The director uploads one score or the parts of a work (one PDF per
instrument); ScoreMaster keeps the PDFs and starts the reader in its private GitHub repository (scoremaster-omr) with a
one-time token. The reader, with no session, downloads the PDFs with that token, tells its progress and sends back
the work's MusicXML or why it failed; ScoreMaster then analyses the work like any upload, marked as read from a PDF.
The token is kept only as its sha256 and is spent, with the PDFs, when the result arrives."""
import hashlib
import json
import logging
from xml.etree import ElementTree as ET
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from backend.app.dependencies import (authenticated_user, get_analysis_repository, get_instrument_store, get_library_repository,
                                      get_omr_dispatcher, get_pdf_import_repository, get_score_store)
from backend.app.library_routes import valid_band_profile
from backend.app.work_analysis import analyze_and_store
from backend.application.accounts import User
from backend.domain.instrument_catalog import catalog_entries
from backend.parsers.pdf_measures import fit_measures
from backend.parsers.pdf_transpositions import add_transpositions
from backend.application.pdf_imports import OmrDispatcher, PdfImport, PdfImportRepository

router = APIRouter()
logger = logging.getLogger(__name__)
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_FILES = 40
MAX_MUSICXML_CHARACTERS = 20 * 1024 * 1024
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
    return {"instruments": [{"id": identity.canonical_id, "section": identity.section, "family": identity.family,
                             "variant": identity.variant, "transposition": identity.transposition,
                             "label_es": identity.label_es, "label_en": identity.label_en, "aliases": list(identity.aliases),
                             "sound": identity.sound, "rehearsal_group": identity.rehearsal_group}
                            for identity in catalog_entries()],
            "learned": sorted(instruments.learned(found.user_id)) if instruments else []}


def _analyse(found: PdfImport, imports, repository, library, score_store, instruments=None) -> None:
    try:
        # The instruments the account confirmed before name the parts the catalog does not know (2026-10-28).
        learned = instruments.learned(found.user_id) if instruments else None
        saved = analyze_and_store(imports.musicxml(found.id), found.title + ".musicxml", found.user_id, found.band_profile,
                                  found.total_minutes, {}, repository, library, score_store, source_format="pdf",
                                  learned=learned)
        imports.done(found.id, UUID(saved["work_id"]))
    except Exception:
        logger.warning("No se pudo analizar una obra leída de PDF.", exc_info=True)
        imports.failed(found.id, "No se pudo analizar la obra leída. Revisa el PDF y vuelve a subirlo.")


@router.post("/omr/imports/{import_id}/result", status_code=202)
def reader_result(import_id: str, result: Result, background: BackgroundTasks,
                  authorization: Optional[str] = Header(default=None),
                  imports: PdfImportRepository = Depends(get_pdf_import_repository),
                  repository=Depends(get_analysis_repository), library=Depends(get_library_repository),
                  score_store=Depends(get_score_store), instruments=Depends(get_instrument_store)):
    found = _reader(import_id, authorization, imports)
    content = (result.musicxml or "").encode("utf-8")
    if result.error or not content:
        imports.failed(found.id, result.error or "El lector no devolvió ninguna obra.")
    elif b"<!ENTITY" in content:
        imports.failed(found.id, "La lectura no es MusicXML válido.")
    else:
        # copista writes the notes in the key of each instrument but no <transpose> (2026-10-29).
        try:
            # Each measure keeps the length of its time signature: one read too long made its part sound late.
            content = add_transpositions(fit_measures(content), instruments.learned(found.user_id) if instruments else None,
                                         result.concert_pitch, result.source or "parts")
        except ET.ParseError:
            imports.failed(found.id, "La lectura no es MusicXML válido.")
            return JSONResponse(status_code=202, content={})
        imports.received(found.id, content)
        # music21 is slow on Render: the reader is answered at once and the work is analysed afterwards.
        background.add_task(_analyse, found, imports, repository, library, score_store, instruments)
    return JSONResponse(status_code=202, content={})
