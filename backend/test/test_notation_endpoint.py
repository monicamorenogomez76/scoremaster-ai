from xml.etree import ElementTree

from fastapi.testclient import TestClient
from music21 import note, stream

from backend.app.main import app


client = TestClient(app)


def _make_score(path, format_name):
    score = stream.Score()
    part = stream.Part()
    part.partName = "Flute"
    measure = stream.Measure(number=1)
    measure.append(note.Note("C5", quarterLength=1))
    part.append(measure)
    score.append(part)
    score.write(format_name, fp=path)
    return path


def test_notation_source_returns_plain_musicxml(tmp_path):
    score_path = _make_score(tmp_path / "score.musicxml", "musicxml")

    response = client.post(
        "/notation-source",
        files={"file": (score_path.name, score_path.read_bytes(), "application/xml")},
    )

    assert response.status_code == 200
    root = ElementTree.fromstring(response.content)
    assert root.tag.rsplit("}", 1)[-1] == "score-partwise"
    assert "Flute" in response.text


def test_notation_source_extracts_musicxml_from_mxl(tmp_path):
    score_path = _make_score(tmp_path / "score.mxl", "mxl")

    response = client.post(
        "/notation-source",
        files={"file": (score_path.name, score_path.read_bytes(), "application/vnd.recordare.musicxml")},
    )

    assert response.status_code == 200
    root = ElementTree.fromstring(response.content)
    assert root.tag.rsplit("}", 1)[-1] == "score-partwise"
    assert "Flute" in response.text