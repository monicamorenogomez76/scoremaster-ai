from __future__ import annotations

import io
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
from threading import Thread
from zipfile import ZipFile, is_zipfile

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Path as FastAPIPath, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from backend.app.auth_routes import router as auth_router
from backend.app.i18n import language, translate
from backend.app.library_routes import router as library_router, valid_band_profile
from backend.app.band_routes import router as band_router
from backend.app.concert_routes import router as concert_router
from backend.app.evaluation_routes import router as evaluation_router
from backend.app.instrument_routes import (confirmable_ids, learn_confirmations, load_instrument_catalog,
                                           router as instrument_router)
from backend.app.rehearsal_routes import router as rehearsal_router
from backend.app.pdf_routes import router as pdf_router
from backend.app.stored_scores import prepare_missing_works
from backend.app.work_analysis import analyze_and_store, refresh_outdated_analyses, repair_pdf_works
from backend.app.youtube import search_videos
from backend.app.dependencies import (
    SAFE_METHODS, STORAGE_UNAVAILABLE, analysis_engine, authenticated_user, close_analysis_engine, get_analysis_repository,
    get_instrument_store, get_library_repository, get_pdf_import_repository, get_playback_store, get_score_store,
)
from backend.application.accounts import User
from backend.application.analysis_repository import AnalysisRepository
from backend.application.library import LibraryRepository
from backend.domain.models import Score
from backend.infrastructure.instrument_repository import PostgresInstrumentRepository
from backend.parsers.musicxml_source import extract_musicxml
from backend.parsers.playback import (NotMusicXML, StillPreparing, build_playback, prepare_playback, preparation_enabled,
                                      preparation_status)

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app):
    # The instrument catalog of the database, before any analysis (2026-10-28).
    try:
        load_instrument_catalog(PostgresInstrumentRepository(analysis_engine()))
    except ValueError:
        pass   # no database: the seed catalog
    # Works uploaded before are read once in the background, so the first proposal or passage after
    # a deploy does not wait minutes for music21 (Render's free plan, 2026-10-07).
    score_store, playback_store = get_score_store(), get_playback_store()
    if preparation_enabled() and score_store is not None and playback_store is not None:
        Thread(target=_prepare_missing, args=(score_store, playback_store), daemon=True, name='prepare-works').start()
    try:
        yield
    finally:
        close_analysis_engine()


def _refresh_analyses(score_store):
    """Works analysed with an earlier ScoreLint are analysed again (difficulty-v2, 2026-10-14)."""
    refreshed = refresh_outdated_analyses(get_analysis_repository(), get_library_repository(), score_store)
    if refreshed:
        # uvicorn.error is the logger Render shows.
        logging.getLogger("uvicorn.error").info("Obras analizadas de nuevo con la versión actual de ScoreLint: %s.", refreshed)


def _prepare_missing(score_store, playback_store):
    try:
        # Before preparing: the works read from a PDF before the fixes of 2026-10-29 change their file.
        repaired = repair_pdf_works(get_pdf_import_repository(), get_library_repository(), get_instrument_store())
        if repaired:
            logging.getLogger("uvicorn.error").info("Obras de PDF reparadas (compases y transposición): %s.", repaired)
        prepare_missing_works(score_store, playback_store, after_models=lambda: _refresh_analyses(score_store))
    except Exception:
        logging.getLogger(__name__).warning("No se pudieron preparar las obras guardadas.", exc_info=True)


PRODUCTION = os.environ.get("APP_ENV") == "production"
# Interactive API docs only outside production.
app = FastAPI(title="ScoreMasterAI API", lifespan=lifespan, docs_url=None if PRODUCTION else "/docs",
              redoc_url=None if PRODUCTION else "/redoc", openapi_url=None if PRODUCTION else "/openapi.json")


# Errors answer in the language of the interface, which the app sends as Accept-Language (2026-10-30).
@app.exception_handler(HTTPException)
async def translated_http_error(request: Request, exc: HTTPException):
    exc.detail = translate(exc.detail, language(request.headers.get("accept-language")))
    return await http_exception_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def translated_validation_error(request: Request, exc: RequestValidationError):
    lang = language(request.headers.get("accept-language"))
    errors = jsonable_encoder(exc.errors())
    for error in errors:
        message = str(error.get("msg", ""))
        prefix = "Value error, " if message.startswith("Value error, ") else ""
        error["msg"] = prefix + translate(message[len(prefix):], lang)
    return JSONResponse(status_code=422, content={"detail": errors})


class _BuiltStatic(StaticFiles):
    """Vite names each built file after its content hash: it never changes, so the browser may keep it."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200 and path.replace("\\", "/").startswith("frontend/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


app.mount("/static", _BuiltStatic(directory=str(BASE_DIR / "static")), name="static")
app.include_router(auth_router)
app.include_router(library_router)
app.include_router(rehearsal_router)
app.include_router(concert_router)
app.include_router(band_router)
app.include_router(evaluation_router)
app.include_router(pdf_router)
app.include_router(instrument_router)

# The score viewer, the samples and the video search load from these CDNs; nothing else runs scripts.
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self' https://cdn.jsdelivr.net https://unpkg.com",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: blob: https://i.ytimg.com",
    "media-src 'self' data: blob: https:",
    "connect-src 'self' https:",
    "worker-src 'self' blob:",
    "frame-src https://www.youtube-nocookie.com",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
])
SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
}
HSTS = "max-age=31536000; includeSubDomains"
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 20 * 1024 * 1024


@app.middleware("http")
async def security(request, call_next):
    """Refuse state-changing requests sent from another site and add the security headers."""
    origin = request.headers.get("origin")
    if request.method not in SAFE_METHODS and origin and urlparse(origin).netloc != request.headers.get("host"):
        response = JSONResponse({"detail": "Origen no permitido."}, status_code=403)
    else:
        response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    # Production is served over HTTPS (Render): never plain HTTP again for a year. Not locally, where
    # it would lock the browser out of http://localhost.
    if PRODUCTION:
        response.headers.setdefault("Strict-Transport-Security", HSTS)
    return response


def _read_upload(file: UploadFile) -> bytes:
    """Upload bytes within the size limits, with no XML entity declarations."""
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="La partitura supera 8 MB.")
    if is_zipfile(io.BytesIO(content)):
        with ZipFile(io.BytesIO(content)) as archive:
            if sum(item.file_size for item in archive.infolist()) > MAX_UNCOMPRESSED_BYTES:
                raise HTTPException(status_code=413, detail="La partitura descomprimida supera 20 MB.")
    source = extract_musicxml(content) if content else None
    if source is not None and b"<!ENTITY" in source:
        raise HTTPException(status_code=400, detail="La partitura no es MusicXML válido.")
    return content


def _musicxml_suffix(content: bytes, extension: str):
    is_compressed = is_zipfile(io.BytesIO(content))
    if extension == ".mxl" and not is_compressed:
        return None
    if extract_musicxml(content) is None:
        return None
    return ".mxl" if is_compressed else extension


@app.get("/health")
def health():
    return {"status": "ok", "service": "scoremaster-ai"}


@app.get("/")
def root():
    frontend = BASE_DIR / "static" / "frontend" / "index.html"
    if not frontend.is_file():
        raise HTTPException(status_code=503, detail="Compila el frontend: npm --prefix frontend ci y npm --prefix frontend run build.")
    # Always revalidated (2026-10-15): after a deploy the browser kept the previous page and its old script.
    return FileResponse(frontend, headers={"Cache-Control": "no-cache"})


@app.get("/youtube/search", dependencies=[Depends(authenticated_user)])
def youtube_search(query: str = Query(..., min_length=2, max_length=200)):
    return search_videos(query, api_key=os.environ.get("YOUTUBE_API_KEY"))


@app.post("/notation-source", dependencies=[Depends(authenticated_user)])
def notation_source(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Expected a MusicXML file upload.")
    extension = Path(file.filename).suffix.lower()
    if extension not in {".musicxml", ".mxl", ".xml"}:
        raise HTTPException(status_code=400, detail="Expected a MusicXML file upload.")
    source = extract_musicxml(_read_upload(file))
    if source is None:
        raise HTTPException(status_code=400, detail="Uploaded file is not valid MusicXML.")
    return Response(content=source, media_type="application/vnd.recordare.musicxml+xml")


@app.post("/playback", dependencies=[Depends(authenticated_user)])
def playback(
    file: UploadFile = File(...),
    instrument: str = Form("", max_length=200),
    instruments: list[str] = Form([]),
    first_measure: int = Form(0, ge=0),
    last_measure: int = Form(999999, ge=0),
    store=Depends(get_playback_store),
):
    if last_measure < first_measure:
        raise HTTPException(status_code=400, detail="El rango de compases no es válido.")
    selection = [name[:200] for name in instruments[:64]] if instruments else instrument
    try:
        return build_playback(_read_upload(file), selection, first_measure, last_measure, store, answer_quickly=True)
    except StillPreparing as preparing:
        # A long work: the browser follows /playback/preparations/{key} and asks again when it is ready.
        return JSONResponse(status_code=202, content={"preparing": preparing.key})
    except NotMusicXML as exc:
        raise HTTPException(status_code=400, detail="La partitura no es MusicXML válido.") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="No se pudo preparar el audio del pasaje.") from exc


@app.get("/playback/preparations/{key}", dependencies=[Depends(authenticated_user)])
def playback_preparation(key: str = FastAPIPath(..., pattern="^[0-9a-f]{64}$")):
    """ready, preparing, failed or unknown (a restarted server: the browser sends the work again)."""
    return {"status": preparation_status(key)}


MAX_INSTRUMENT_OVERRIDES = 256


def _instrument_overrides(raw: str, confirmable: set[str]) -> dict[str, str]:
    """Part name → catalog identity (common or the account's own) confirmed by the user; anything else is rejected."""
    try:
        overrides = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="instrument_overrides must be valid JSON.") from exc
    if not isinstance(overrides, dict) or len(overrides) > MAX_INSTRUMENT_OVERRIDES or not all(
            isinstance(part, str) and len(part) <= 200 and isinstance(identity, str) and identity in confirmable
            for part, identity in overrides.items()):
        raise HTTPException(status_code=400, detail="instrument_overrides must map part names to catalog instruments.")
    return overrides


@app.post("/analyze")
def analyze_score(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    band_profile: str = Form("{}", max_length=64 * 1024),
    total_minutes: int = Form(60, ge=5, le=600),
    instrument_overrides: str = Form("{}", max_length=64 * 1024),
    repository: AnalysisRepository = Depends(get_analysis_repository),
    library: LibraryRepository = Depends(get_library_repository),
    playback_store=Depends(get_playback_store),
    score_store=Depends(get_score_store),
    instruments=Depends(get_instrument_store),
    user: User = Depends(authenticated_user),
):
    """Analyse a score and keep it in the user's library; the saved band completes the template. The instruments
    confirmed are learnt for the account's next works (2026-10-28)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Expected a MusicXML file upload.")
    extension = Path(file.filename).suffix.lower()
    if extension not in {".musicxml", ".mxl", ".xml"}:
        raise HTTPException(
            status_code=400,
            detail="Expected a .musicxml, .mxl, or MusicXML .xml file upload.",
        )

    try:
        profile = json.loads(band_profile or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="band_profile must be valid JSON.") from exc
    if not valid_band_profile(profile):
        raise HTTPException(status_code=400, detail="band_profile must map instruments to musician counts.")
    overrides = _instrument_overrides(instrument_overrides, confirmable_ids(user, instruments))

    content = _read_upload(file)
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    musicxml_suffix = _musicxml_suffix(content, extension)
    if not musicxml_suffix:
        raise HTTPException(status_code=400, detail="Uploaded file is not valid MusicXML.")

    try:
        saved = analyze_and_store(content, file.filename, user.id, profile, total_minutes, overrides, repository, library,
                                  score_store, learned=instruments.learned(user.id) if instruments else None)
        learn_confirmations(user, instruments, overrides)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail=STORAGE_UNAVAILABLE) from exc
    # Its passages will sound sooner: the work is read for playback after answering.
    if preparation_enabled():
        background.add_task(prepare_playback, content, playback_store)
    return saved
