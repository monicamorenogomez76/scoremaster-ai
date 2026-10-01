from __future__ import annotations

import io
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile, is_zipfile

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.analyzers.band_fit import compute_band_fit
from backend.analyzers.difficulty import compute_difficulty_score
from backend.analyzers.rehearsal_plan import build_rehearsal_plan
from backend.analyzers.tempo import compute_tempo_metrics
from backend.app.youtube import search_videos
from backend.parsers.musicxml_parser import parse_musicxml

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="ScoreMasterAI API")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def _extract_musicxml(content: bytes) -> bytes | None:
    try:
        if is_zipfile(io.BytesIO(content)):
            with ZipFile(io.BytesIO(content)) as archive:
                container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
                rootfile = next(
                    element for element in container.iter()
                    if element.tag.rsplit("}", 1)[-1] == "rootfile"
                )
                score_xml = archive.read(rootfile.attrib["full-path"])
        else:
            score_xml = content
        root = ElementTree.fromstring(score_xml)
    except (BadZipFile, ElementTree.ParseError, KeyError, StopIteration, OSError):
        return None

    if root.tag.rsplit("}", 1)[-1] not in {"score-partwise", "score-timewise"}:
        return None
    return score_xml


def _musicxml_suffix(content: bytes, extension: str):
    is_compressed = is_zipfile(io.BytesIO(content))
    if extension == ".mxl" and not is_compressed:
        return None
    if _extract_musicxml(content) is None:
        return None
    return ".mxl" if is_compressed else extension


@app.get("/health")
def health():
    return {"status": "ok", "service": "scoremaster-ai"}


@app.get("/")
def root():
    return FileResponse(BASE_DIR / "static" / "index.html")


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
    source = _extract_musicxml(file.file.read())
    if source is None:
        raise HTTPException(status_code=400, detail="Uploaded file is not valid MusicXML.")
    return Response(content=source, media_type="application/vnd.recordare.musicxml+xml")


@app.post("/analyze")
def analyze_score(
    file: UploadFile = File(...),
    band_profile: str = Form("{}"),
    total_minutes: int = Form(60),
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
        rehearsal_plan = build_rehearsal_plan(score, total_minutes)

        return {
            "title": score.title,
            "composer": score.composer,
            "parts": [part.name for part in score.parts],
            "difficulty": difficulty,
            "tempo": compute_tempo_metrics(score),
            "band_fit": band_fit,
            "rehearsal_plan": rehearsal_plan,
        }
    finally:
        temp_path.unlink(missing_ok=True)