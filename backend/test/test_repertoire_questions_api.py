"""Asking the repertoire over HTTP (M6, 2026-11-20): with the session and the CSRF token, and only over the works, band,
rehearsals and concerts of the signed-in director."""
import pytest
from fastapi.testclient import TestClient

from backend.app.dependencies import get_explanation_provider
from backend.app.main import app
from backend.application.ai import ProviderInfo
from backend.test.test_library_api import analyze, clients  # noqa: F401 (pytest fixture)

pytestmark = pytest.mark.real_auth


class Llm:
    info = ProviderInfo("llm", "gemini", "gemini-test")

    def __init__(self, calls, reply):
        self.calls, self.reply, self.evidence = calls, reply, []

    def choose_tools(self, question, specs, language, scope="work"):
        return self.calls

    def answer_repertoire_question(self, evidence):
        self.evidence.append(evidence)
        return self.reply(evidence)


def test_a_suggested_question_answers_with_the_works_of_its_owner_only(clients):
    ana, berta = clients
    mine = analyze(ana, "evaluation_study.musicxml").json()["work_id"]
    analyze(berta, "high_register.musicxml")
    body = ana.post("/repertoire/questions", json={"suggestion": "easiest"}).json()
    assert body["mode"] == "demo" and body["tools"] == ["find_works"] and body["answer"]["answered"]
    assert [(cite["kind"], cite["work_id"]) for cite in body["cites"]] == [("work", mine)]
    assert TestClient(app).post("/repertoire/questions", json={"suggestion": "easiest"}).status_code in (401, 403)
    del ana.headers["X-CSRF-Token"]
    assert ana.post("/repertoire/questions", json={"suggestion": "easiest"}).status_code == 403


@pytest.mark.parametrize("body", [{"question": "x" * 301}, {"question": " "}, {"suggestion": "band"}, {},
                                  {"question": "¿Qué?", "suggestion": "ready"}])
def test_the_question_is_validated(clients, body):
    ana, _ = clients
    assert ana.post("/repertoire/questions", json=body).status_code == 422


def test_the_ai_fills_the_filters_and_reads_the_details_and_the_band(clients):
    ana, berta = clients
    analyze(ana, "evaluation_study.musicxml")
    assert ana.patch("/band", json={"profile": {"flute": 2}}).status_code == 200
    analyze(berta, "high_register.musicxml")
    llm = Llm([{"name": "find_works", "args": {"grade_max": 6}}, {"name": "work_details", "args": {"title": "evaluation"}},
               {"name": "band", "args": {}}],
              lambda evidence: {"answer": "Tienes una obra.", "answered": True, "cites": ["W1"]})
    app.dependency_overrides[get_explanation_provider] = lambda: llm
    body = ana.post("/repertoire/questions", json={"question": "¿Qué obras tengo?"}).json()
    [evidence] = llm.evidence
    found, details, band = (item["result"] for item in evidence["results"])
    assert found["total"] == 1 and found["works"][0]["id"] == "W1" and found["works"][0]["minutes"] is not None
    assert details["works"][0]["grade"] == found["works"][0]["grade"] and "band" in details["works"][0]
    assert band["musicians"] >= 2 and any(item["label"] == "Flauta" for item in band["instruments"])
    assert body["mode"] == "llm" and body["cites"][0]["kind"] == "work"
