import json
import inspect
from pathlib import Path

from fastapi.testclient import TestClient
from music21 import stream, note

from backend.app.main import analyze_score, app

client = TestClient(app)


def test_analyze_handler_is_sync_for_threadpool_execution():
    assert not inspect.iscoroutinefunction(analyze_score)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_serves_upload_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "ScoreMasterAI" in response.text
    assert "Subir" in response.text or "subir" in response.text
    assert "Analizando la partitura" in response.text
    assert "Dificultad" in response.text
    assert "Adaptación a la banda" in response.text
    assert "Plan de ensayo" in response.text
    assert "JSON.stringify(data, null, 2)" not in response.text


def test_analyze_score_endpoint_returns_summary():
    score_path = Path(__file__).resolve().parents[2] / "test-scores" / "high_density.musicxml"

    with score_path.open("rb") as musicxml_file:
        response = client.post(
            "/analyze",
            files={"file": ("high_density.musicxml", musicxml_file, "application/xml")},
            data={"band_profile": json.dumps({"Flute": 1, "Clarinet": 1})},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"]
    assert payload["difficulty"]["overall_score"] >= 0
    assert payload["band_fit"]["status"] in {"ok", "warning", "critical"}
    assert "segments" in payload["rehearsal_plan"]


def test_analyze_accepts_mxl_files(tmp_path):
    score = stream.Score()
    part = stream.Part()
    melody = stream.Measure(number=1)
    melody.append(note.Note("C4", quarterLength=1))
    melody.append(note.Note("D4", quarterLength=1))
    part.append(melody)
    score.append(part)

    score_path = tmp_path / "example.mxl"
    score.write("mxl", fp=score_path)

    response = client.post(
        "/analyze",
        files={"file": ("example.mxl", score_path.read_bytes(), "application/vnd.recordare.musicxml")},
        data={"band_profile": json.dumps({"Part": 1}), "total_minutes": 30},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] or payload["parts"]


def test_analyze_accepts_compressed_score_named_musicxml(tmp_path):
    score = stream.Score()
    part = stream.Part()
    measure = stream.Measure(number=1)
    measure.append(note.Note("C4", quarterLength=1))
    part.append(measure)
    score.append(part)
    score_path = tmp_path / "compressed.mxl"
    score.write("mxl", fp=score_path)
    mislabeled_path = tmp_path / "compressed.musicxml"
    score_path.rename(mislabeled_path)

    response = client.post(
        "/analyze",
        files={"file": (mislabeled_path.name, mislabeled_path.read_bytes(), "application/xml")},
        data={"band_profile": "{}", "total_minutes": 60},
    )

    assert response.status_code == 200
    assert response.json()["parts"]


def test_analyze_accepts_musicxml_with_xml_extension(tmp_path):
    score = stream.Score()
    part = stream.Part()
    melody = stream.Measure(number=1)
    melody.append(note.Note("C4", quarterLength=1))
    part.append(melody)
    score.append(part)

    score_path = tmp_path / "example.xml"
    score.write("musicxml", fp=score_path)

    response = client.post(
        "/analyze",
        files={"file": ("example.xml", score_path.read_bytes(), "application/xml")},
        data={"band_profile": json.dumps({"Part": 1})},
    )

    assert response.status_code == 200


def test_analyze_rejects_non_musicxml_xml_files():
    response = client.post(
        "/analyze",
        files={"file": ("notes.xml", b"<notes><note>C4</note></notes>", "application/xml")},
    )

    assert response.status_code == 400
    assert "MusicXML" in response.json()["detail"]