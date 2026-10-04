from __future__ import annotations

import io
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile, is_zipfile

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from backend.analyzers.band_fit import compute_band_fit
from backend.analyzers.difficulty import compute_difficulty_score
from backend.analyzers.rehearsal_plan import build_rehearsal_plan
from backend.analyzers.tempo import compute_tempo_metrics
from backend.app.youtube import search_videos
from backend.app.dependencies import STORAGE_UNAVAILABLE, close_analysis_engine, get_analysis_repository
from backend.application.analysis_repository import AnalysisRepository
from backend.application.save_analysis import save_analysis
from backend.domain.instrument_resolver import resolve_part
from backend.parsers.musicxml_parser import parse_musicxml
from backend.parsers.musicxml_source import extract_musicxml
from backend.parsers.playback import build_playback

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app):
    try:
        yield
    finally:
        close_analysis_engine()


app = FastAPI(title="ScoreMasterAI API", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


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


@app.get("/youtube/search")
def youtube_search(query: str = Query(..., min_length=2, max_length=200)):
    return search_videos(query, api_key=os.environ.get("YOUTUBE_API_KEY"))


@app.post("/notation-source")
def notation_source(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Expected a MusicXML file upload.")
    extension = Path(file.filename).suffix.lower()
    if extension not in {".musicxml", ".mxl", ".xml"}:
        raise HTTPException(status_code=400, detail="Expected a MusicXML file upload.")
    source = extract_musicxml(file.file.read())
    if source is None:
        raise HTTPException(status_code=400, detail="Uploaded file is not valid MusicXML.")
    return Response(content=source, media_type="application/vnd.recordare.musicxml+xml")


@app.post("/playback")
def playback(
    file: UploadFile = File(...),
    instrument: str = Form("", max_length=200),
    first_measure: int = Form(0, ge=0),
    last_measure: int = Form(999999, ge=0),
):
    if last_measure < first_measure:
        raise HTTPException(status_code=400, detail="El rango de compases no es válido.")
    content = file.file.read(8 * 1024 * 1024 + 1)
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="La partitura supera 8 MB.")
    if is_zipfile(io.BytesIO(content)):
        with ZipFile(io.BytesIO(content)) as archive:
            if sum(item.file_size for item in archive.infolist()) > 20 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="La partitura descomprimida supera 20 MB.")
    source = extract_musicxml(content)
    if source is None or b"<!ENTITY" in source:
        raise HTTPException(status_code=400, detail="La partitura no es MusicXML válido.")
    with NamedTemporaryFile(suffix=".musicxml") as temporary:
        temporary.write(source)
        temporary.flush()
        try:
            return build_playback(temporary.name, instrument, first_measure, last_measure)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="No se pudo preparar el audio del pasaje.") from exc


@app.post("/analyze")
def analyze_score(
    file: UploadFile = File(...),
    band_profile: str = Form("{}"),
    total_minutes: int = Form(60),
    repository: AnalysisRepository = Depends(get_analysis_repository),
):
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

    content = file.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    musicxml_suffix = _musicxml_suffix(content, extension)
    if not musicxml_suffix:
        raise HTTPException(status_code=400, detail="Uploaded file is not valid MusicXML.")

    with NamedTemporaryFile(suffix=musicxml_suffix, delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        temp_path.write_bytes(content)

    try:
        score = parse_musicxml(temp_path)
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
            "band_fit": band_fit,
            "rehearsal_plan": rehearsal_plan,
        }
        try:
            return save_analysis(result, content, profile, total_minutes, repository)
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail=STORAGE_UNAVAILABLE) from exc
    finally:
        temp_path.unlink(missing_ok=True)
