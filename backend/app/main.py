from __future__ import annotations

import hashlib
import io
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
from tempfile import NamedTemporaryFile
from zipfile import ZipFile, is_zipfile

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from backend.analyzers.band_fit import PERCUSSION, compute_band_fit
from backend.analyzers.difficulty import compute_difficulty_score
from backend.analyzers.rehearsal_plan import build_rehearsal_plan
from backend.analyzers.tempo import compute_tempo_metrics, estimate_duration
from backend.app.auth_routes import router as auth_router
from backend.app.library_routes import router as library_router, valid_band_profile
from backend.app.band_routes import router as band_router
from backend.app.concert_routes import router as concert_router
from backend.app.rehearsal_routes import router as rehearsal_router
from backend.app.stored_scores import confirm_instruments
from backend.app.youtube import search_videos
from backend.app.dependencies import (
    SAFE_METHODS, STORAGE_UNAVAILABLE, authenticated_user, close_analysis_engine, get_analysis_repository,
    get_library_repository,
)
from backend.application.accounts import User
from backend.application.analysis_repository import AnalysisRepository
from backend.application.library import LibraryRepository, WorkUpload
from backend.application.save_analysis import save_analysis
from backend.domain.instrument_catalog import catalog_entries, identity_by_id
from backend.domain.instrument_resolver import resolve_part
from backend.domain.models import Score
from backend.parsers.musicxml_parser import parse_musicxml
from backend.parsers.musicxml_source import extract_musicxml
from backend.parsers.playback import NotMusicXML, build_playback, prepare_playback, preparation_enabled

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app):
    try:
        yield
    finally:
        close_analysis_engine()


PRODUCTION = os.environ.get("APP_ENV") == "production"
# Interactive API docs only outside production.
app = FastAPI(title="ScoreMasterAI API", lifespan=lifespan, docs_url=None if PRODUCTION else "/docs",
              redoc_url=None if PRODUCTION else "/redoc", openapi_url=None if PRODUCTION else "/openapi.json")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.include_router(auth_router)
app.include_router(library_router)
app.include_router(rehearsal_router)
app.include_router(concert_router)
app.include_router(band_router)

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
    return FileResponse(frontend)


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
):
    if last_measure < first_measure:
        raise HTTPException(status_code=400, detail="El rango de compases no es válido.")
    selection = [name[:200] for name in instruments[:64]] if instruments else instrument
    try:
        return build_playback(_read_upload(file), selection, first_measure, last_measure)
    except NotMusicXML as exc:
        raise HTTPException(status_code=400, detail="La partitura no es MusicXML válido.") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="No se pudo preparar el audio del pasaje.") from exc


MAX_INSTRUMENT_OVERRIDES = 256


def _instrument_overrides(raw: str) -> dict[str, str]:
    """Part name → catalog identity confirmed by the user; anything else is rejected."""
    try:
        overrides = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="instrument_overrides must be valid JSON.") from exc
    if not isinstance(overrides, dict) or len(overrides) > MAX_INSTRUMENT_OVERRIDES or not all(
            isinstance(part, str) and len(part) <= 200 and isinstance(identity, str) and identity_by_id(identity)
            for part, identity in overrides.items()):
        raise HTTPException(status_code=400, detail="instrument_overrides must map part names to catalog instruments.")
    return overrides


@app.get("/instruments/catalog")
def instrument_catalog():
    return {"instruments": [{"canonical_id": identity.canonical_id, "label_es": identity.label_es, "section": identity.section}
                            for identity in catalog_entries()],
            "percussion_key": PERCUSSION}


@app.post("/analyze")
def analyze_score(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    band_profile: str = Form("{}", max_length=64 * 1024),
    total_minutes: int = Form(60, ge=5, le=600),
    instrument_overrides: str = Form("{}", max_length=64 * 1024),
    repository: AnalysisRepository = Depends(get_analysis_repository),
    library: LibraryRepository = Depends(get_library_repository),
    user: User = Depends(authenticated_user),
):
    """Analyse a score and keep it in the user's library; the saved band completes the template."""
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
    overrides = _instrument_overrides(instrument_overrides)

    content = _read_upload(file)
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    musicxml_suffix = _musicxml_suffix(content, extension)
    if not musicxml_suffix:
        raise HTTPException(status_code=400, detail="Uploaded file is not valid MusicXML.")

    with NamedTemporaryFile(suffix=musicxml_suffix, delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        temp_path.write_bytes(content)

    try:
        score = confirm_instruments(parse_musicxml(temp_path), overrides)
        # Template: what the work needs for instruments never configured, then the saved band,
        # then the musicians sent with this request.
        needed = {item["key"]: item["required"] for item in compute_band_fit(score, {})["requirements"]}
        try:
            profile = {**needed, **library.band_profile(user.id), **profile}
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail=STORAGE_UNAVAILABLE) from exc
        difficulty = compute_difficulty_score(score)
        band_fit = compute_band_fit(score, profile)
        rehearsal_plan = build_rehearsal_plan(score, total_minutes, difficulty)

        result = {
            "title": score.title,
            "composer": score.composer,
            "parts": [part.name for part in score.parts],
            "instruments": [resolve_part(part).as_dict() for part in score.parts],
            "difficulty": difficulty,
            "tempo": compute_tempo_metrics(score),
            "duration": estimate_duration(score),
            "band_fit": band_fit,
            "rehearsal_plan": rehearsal_plan,
        }
        title = (score.title or "").strip() or Path(file.filename).stem
        try:
            work = library.store_work(user.id, WorkUpload(title, score.composer, Path(file.filename).name, content,
                                                          hashlib.sha256(content).hexdigest()))
            saved = save_analysis(result, content, profile, total_minutes, repository,
                                  {part.name: overrides[part.name] for part in score.parts if part.name in overrides},
                                  user_id=user.id, work_id=work.id)
            # Its passages will sound sooner: the work is read for playback after answering.
            if preparation_enabled():
                background.add_task(prepare_playback, content)
            return {**saved, "work_id": str(work.id)}
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail=STORAGE_UNAVAILABLE) from exc
    finally:
        temp_path.unlink(missing_ok=True)
