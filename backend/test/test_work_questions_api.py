"""Asking the work over HTTP (M6, 2026-11-20): only its owner asks, with the session and the CSRF token, and the
functions the AI may choose read only that work and that director's rehearsals and concerts."""
import pytest
from fastapi.testclient import TestClient

from backend.app.dependencies import get_explanation_provider
from backend.app.main import app
from backend.application.ai import ProviderInfo
from backend.test.test_library_api import analyze, clients  # noqa: F401 (pytest fixture)
from backend.test.test_rehearsal_api import rehearsal

pytestmark = pytest.mark.real_auth


class Llm:
    info = ProviderInfo("llm", "gemini", "gemini-test")

    def __init__(self, chosen, reply):
        self.chosen, self.reply, self.evidence = chosen, reply, []

    def choose_tools(self, question, specs, language):
        return self.chosen

    def answer_work_question(self, evidence):
        self.evidence.append(evidence)
        return self.reply(evidence)


def test_a_suggested_question_is_answered_to_the_owner_only(clients):
    ana, berta = clients
    work_id = analyze(ana, "evaluation_study.musicxml").json()["work_id"]
    response = ana.post("/works/" + work_id + "/questions", json={"suggestion": "passages"})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "demo" and body["tools"] == ["difficulty"] and body["answer"]["answered"]
    assert [cite["kind"] for cite in body["cites"]] == ["passage"] * len(body["answer"]["cites"])
    assert berta.post("/works/" + work_id + "/questions", json={"suggestion": "passages"}).status_code == 404
    assert TestClient(app).post("/works/" + work_id + "/questions", json={"suggestion": "passages"}).status_code in (401, 403)
    del ana.headers["X-CSRF-Token"]
    assert ana.post("/works/" + work_id + "/questions", json={"suggestion": "passages"}).status_code == 403


@pytest.mark.parametrize("body", [{"question": "x" * 301}, {"question": "  "}, {"suggestion": "borrar"}, {},
                                  {"question": "¿Qué?", "suggestion": "band"}])
def test_the_question_is_validated(clients, body):
    ana, _ = clients
    work_id = analyze(ana).json()["work_id"]
    assert ana.post("/works/" + work_id + "/questions", json=body).status_code == 422


def test_the_ai_reads_the_analysis_and_the_rehearsals_of_the_work_it_chose(clients):
    ana, berta = clients
    work_id = analyze(ana, "evaluation_study.musicxml").json()["work_id"]
    assert ana.post("/rehearsals", json=rehearsal(work_id, date="2099-01-15")).status_code == 201
    others = analyze(berta, "evaluation_study.musicxml").json()["work_id"]
    berta.post("/rehearsals", json=rehearsal(others, date="2099-01-10"))
    llm = Llm(["analysis", "schedule"], lambda evidence: {
        "answer": "Se ensaya el 15 de enero.", "answered": True,
        "cites": ["R1", evidence["results"]["analysis"]["sections"][0]["id"]]})
    app.dependency_overrides[get_explanation_provider] = lambda: llm
    body = ana.post("/works/" + work_id + "/questions", json={"question": "¿Cuándo la ensayamos?"}).json()
    [evidence] = llm.evidence
    assert [item["date"] for item in evidence["results"]["schedule"]["rehearsals"]] == ["2099-01-15"]
    assert evidence["results"]["schedule"]["rehearsals"][0]["minutes"] == 25
    assert evidence["results"]["analysis"]["sections"], "the calculated analysis of the work"
    assert (body["mode"], body["fallback_reason"]) == ("llm", None)
    assert [cite["kind"] for cite in body["cites"]] == ["rehearsal", "section"]
    assert body["cites"][0]["text"] == "15/01/2099"
