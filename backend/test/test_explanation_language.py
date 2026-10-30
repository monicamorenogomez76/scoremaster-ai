"""The explanations in the language of the interface (2026-10-30). In English the evidence carries English labels,
grades and reasons and says so; the demo writes in English; Gemini is told to write in English with its own prompt
version; the Spanish evidence and prompts do not change, so the answers kept in the cache still serve."""
import re

import pytest

from backend.application.difficulty_explanation import PROMPT_VERSION, difficulty_evidence, explain_difficulty
from backend.application.rehearsal_explanation import explain_rehearsal, rehearsal_evidence
from backend.infrastructure.ai.demo_provider import DemoExplanationProvider
from backend.infrastructure.ai.gemini_provider import GeminiExplanationProvider
from backend.infrastructure.ai.prompts import DIFFICULTY_PROMPT, REHEARSAL_PROMPT, in_language
from backend.test.test_difficulty_explanation import result  # noqa: F401 (fixture)
from backend.test.test_rehearsal_explanation import ANALYSES, CONCERT, PENDING, REHEARSAL

SPANISH = re.compile(r"\b(tiene|grado|pasajes|compases|ensayo|minutos|banda|sobre todo|antes del)\b|[áéíóúñ]", re.I)


def test_the_spanish_evidence_is_the_same_as_before(result):
    assert difficulty_evidence(result) == difficulty_evidence(result, "es")
    assert "language" not in difficulty_evidence(result), "the answers kept in the cache still serve"


def test_the_english_evidence_says_so_and_carries_english_texts(result):
    evidence = difficulty_evidence(result, "en")
    assert evidence["language"] == "en"
    assert evidence["grade_label"] == "Professional" and evidence["grade_description"].startswith("Professional level")
    assert evidence["grade_reasons"] == ["Range of Tuba up to C4 → grade 6, above the chart (Galician Band Federation)"]
    assert {item["label"] for item in evidence["instruments"]} == {"Flute", "Clarinet", "Tuba"}
    assert {item["family"] for item in evidence["instruments"]} <= {"Woodwinds", "Brass"}
    labels = [finding["label"] for passage in evidence["passages"] for finding in passage["findings"]]
    assert labels and not any(SPANISH.search(label) for label in labels)


def test_the_demo_explains_in_english(result):
    shown = explain_difficulty(result, DemoExplanationProvider(), DemoExplanationProvider(), language="en")
    texts = [shown["explanation"]["summary"], shown["explanation"]["study_tip"]] + [f["text"] for f in shown["explanation"]["factors"]]
    assert shown["explanation"]["summary"].startswith("«Estudio de evaluación» is grade 6")
    assert not [text for text in texts if SPANISH.search(text.replace("Estudio de evaluación", ""))]


def test_the_rehearsal_demo_explains_in_english():
    shown = explain_rehearsal(REHEARSAL, ANALYSES, CONCERT, PENDING, DemoExplanationProvider(), DemoExplanationProvider(), language="en")
    explanation = shown["explanation"]
    assert explanation["summary"].startswith("Rehearsal of 90 minutes")
    texts = [explanation["summary"], explanation["advice"]] + [reason["text"] for reason in explanation["reasons"]]
    titles = [block["title"] for block in REHEARSAL["blocks"]] + ["Persis", "Spania", "Santa Cecilia"]
    cleaned = [re.sub("|".join(map(re.escape, titles)), "", text) for text in texts]
    assert not [text for text in cleaned if SPANISH.search(text)]
    evidence = rehearsal_evidence(REHEARSAL, ANALYSES, CONCERT, PENDING, "en")
    assert evidence["language"] == "en" and "language" not in rehearsal_evidence(REHEARSAL, ANALYSES, CONCERT, PENDING)


def test_gemini_is_told_to_write_in_english_with_its_own_prompt_version(result):
    english = in_language(DIFFICULTY_PROMPT, "en")
    assert in_language(DIFFICULTY_PROMPT, "es") is DIFFICULTY_PROMPT
    assert english.version == DIFFICULTY_PROMPT.version + "-en"
    assert "Escribe en inglés" in english.system and "Escribe en castellano" not in english.system
    assert "Escribe en inglés" in in_language(REHEARSAL_PROMPT, "en").system
    sent = {}

    class Chat:
        def invoke(self, messages):
            sent["system"] = messages[0][1]
            passage = difficulty_evidence(result, "en")["passages"][0]
            return {"summary": "Grade 6.", "factors": [{"dimension": "general", "text": "Hard.", "passages": [passage["id"]],
                                                       "instruments": [passage["instrument"]]}], "study_tip": "Slowly."}

    shown = explain_difficulty(result, GeminiExplanationProvider("key", chat_factory=lambda schema: Chat()),
                               DemoExplanationProvider(), language="en")
    assert sent["system"] == english.system
    assert (shown["mode"], shown["prompt_version"]) == ("llm", PROMPT_VERSION + "-en")


@pytest.mark.parametrize("prompt", [DIFFICULTY_PROMPT, REHEARSAL_PROMPT])
def test_the_lines_the_english_prompt_replaces_are_in_the_spanish_one(prompt):
    assert in_language(prompt, "en").system != prompt.system
    assert "«label» (en castellano)" not in in_language(prompt, "en").system
