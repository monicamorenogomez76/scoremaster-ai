"""Asking the work (M6, 2026-11-20). The director asks in her own words; the AI only chooses among read-only functions of
ScoreMaster and writes the answer from what they return. Nothing is changed and nothing outside the signed-in user's work
is read: the functions are built by the route for that work, so the AI never chooses whose data it reads.

Two requests per free question: the provider chooses the functions (function calling) and then answers from their
results, validated like every explanation (backend/application/explanations.py): the ids it cites must be in the
results and every figure it writes too. The suggested questions, and every question without the AI, are answered by
rules (the demo provider), which are never presented as AI."""
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError

from backend.application.explanations import InvalidExplanation, failure_reason, run_explanation
from backend.domain.instrument_catalog import english_label
from backend.domain.text import evidence_text

PROMPT_VERSION = "work-question-v1"
EVIDENCE_VERSION = "work-question-evidence-v1"
MAX_QUESTION = 300
MAX_CITES = 12
MAX_REHEARSALS, MAX_CONCERTS = 6, 4
TOOLS = ("difficulty", "band", "analysis", "schedule")
# The suggested questions and the function each one reads; the rules answer them, so they never spend AI quota.
SUGGESTIONS = {"grade": ("difficulty",), "passages": ("difficulty",), "band": ("band",), "form": ("analysis",),
               "schedule": ("schedule",)}
IDS_IN_TEXT = re.compile(r"\b[PSCTRK]\d{1,3}\b")

DESCRIPTIONS = {
    "es": {
        "difficulty": "Dificultad de la obra calculada por ScoreLint: grado de 1 a 6 y los criterios que lo fijan, los "
                      "instrumentos más exigentes y los pasajes críticos (instrumento, compases y motivo).",
        "band": "Si la banda de la directora puede tocar la obra: porcentaje de partes cubiertas, instrumentos que faltan "
                "y partes sin instrumento confirmado.",
        "analysis": "Análisis musical calculado: forma y secciones con sus compases y tonalidades, modulaciones, "
                    "cadencias, temas, textura, tempo, compás y clímax.",
        "schedule": "Próximos ensayos en los que está la obra (fecha y minutos dedicados) y conciertos de su programa.",
    },
    "en": {
        "difficulty": "Difficulty of the work calculated by ScoreLint: grade from 1 to 6 and the criteria that set it, the "
                      "most demanding instruments and the critical passages (instrument, measures and reason).",
        "band": "Whether the director's band can play the work: share of parts covered, missing instruments and parts "
                "without a confirmed instrument.",
        "analysis": "Calculated musical analysis: form and sections with their measures and keys, modulations, cadences, "
                    "themes, texture, tempo, meter and climax.",
        "schedule": "Coming rehearsals that include the work (date and minutes given to it) and concerts with it in "
                    "their programme.",
    },
}

# Without the AI a free question is recognised by its words: the first topic whose words it uses. «grado» is checked
# before «difícil» so that «¿por qué tiene ese grado?» asks for the grade and «lo más difícil» for the passages.
KEYWORDS = (
    ("grade", ("grado", "grados", "nivel", "dificultad", "grade", "level", "difficulty")),
    ("passages", ("pasaje", "dificil", "passage", "hard", "difficult", "trickiest")),
    ("schedule", ("ensay", "concierto", "cuando", "fecha", "rehears", "concert", "when", "date")),
    ("band", ("banda", "musico", "falta", "cubr", "plantilla", "instrument", "band", "musician", "player", "missing",
              "lineup")),
    ("form", ("forma", "seccion", "estructura", "tonalidad", "cadencia", "tema", "analisis", "modula", "form", "section",
              "structure", "key", "theme", "cadence", "analysis")),
)
CADENCES = {"es": {"authentic": "cadencia auténtica", "half": "semicadencia", "plagal": "cadencia plagal",
                   "deceptive": "cadencia rota"},
            "en": {"authentic": "authentic cadence", "half": "half cadence", "plagal": "plagal cadence",
                   "deceptive": "deceptive cadence"}}


@dataclass(frozen=True)
class WorkTools:
    """The read-only functions over one work of the signed-in user, built by the route; each is read only if chosen."""
    title: str
    difficulty: Callable[[], dict]
    band: Callable[[], dict]
    analysis: Callable[[], dict]
    schedule: Callable[[], dict]


class WorkAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=1200)
    # False when the results of the functions do not answer the question: the interface says so.
    answered: bool
    cites: list[str] = Field(default_factory=list, max_length=MAX_CITES)


def tool_specs(language: str = "es") -> list[dict]:
    """The functions as the AI sees them: a name and what it returns. They take no arguments: the work is fixed."""
    descriptions = DESCRIPTIONS["en" if language == "en" else "es"]
    return [{"name": name, "description": descriptions[name]} for name in TOOLS]


def _plain(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", text.lower())
    return re.findall(r"\w+", "".join(character for character in folded if not unicodedata.combining(character)))


def recognise(question: str) -> Optional[str]:
    """The suggestion a free question asks for, by its words; None when the rules cannot tell."""
    words = _plain(question)
    for topic, stems in KEYWORDS:
        if any(word.startswith(stem) for word in words for stem in stems):
            return topic
    return None


def band_tool(band_fit: dict, language: str = "es") -> dict:
    """What the band lacks for the work, from the band fit of its latest analysis."""
    label = (lambda item: english_label(item["label_es"], item["key"])) if language == "en" else (lambda item: item["label_es"])
    return {"compatibility_percent": band_fit.get("compatibility_percent"), "status": band_fit.get("status"),
            "missing": [{"label": evidence_text(label(item)), "required": item["required"], "available": item["available"]}
                        for item in band_fit.get("issues", [])],
            "unconfirmed": len(band_fit.get("unconfirmed", []))}


def schedule_tool(work_id: UUID, rehearsals: list, concerts: list, today: date) -> dict:
    """The coming rehearsals that include the work, with the minutes of their blocks on it, and the concerts with it."""
    titles = {concert.id: concert.draft.title for concert in concerts}
    mine = [rehearsal for rehearsal in rehearsals if work_id in rehearsal.draft.work_ids]
    coming = sorted((rehearsal for rehearsal in mine if rehearsal.draft.date >= today), key=lambda item: item.draft.date)
    programmes = sorted((concert for concert in concerts if work_id in concert.draft.work_ids and concert.draft.date >= today),
                        key=lambda item: item.draft.date)
    return {
        "rehearsals": [{"id": "R{}".format(index), "date": rehearsal.draft.date.isoformat(), "time": rehearsal.draft.time,
                        "minutes": sum(block.minutes for block in rehearsal.draft.blocks if block.work_id == work_id),
                        "concert": evidence_text(titles.get(rehearsal.draft.concert_id)) or None}
                       for index, rehearsal in enumerate(coming[:MAX_REHEARSALS], start=1)],
        "past_rehearsals": len(mine) - len(coming),
        "concerts": [{"id": "K{}".format(index), "title": evidence_text(concert.draft.title),
                      "date": concert.draft.date.isoformat(), "days_left": (concert.draft.date - today).days,
                      "place": evidence_text(concert.draft.place) or None}
                     for index, concert in enumerate(programmes[:MAX_CONCERTS], start=1)],
    }


def _date(text: str) -> str:
    year, month, day = text.split("-")
    return "{}/{}/{}".format(day, month, year)


def cited(results: dict, language: str = "es") -> dict:
    """Every id the results hold, with what the interface shows for it."""
    measures, measure = ("mm.", "m.") if language == "en" else ("cc.", "c.")
    found = {}
    for passage in (results.get("difficulty") or {}).get("passages", []):
        found[passage["id"]] = {"id": passage["id"], "kind": "passage",
                                "text": "{} ({} {})".format(passage["label"], measures if "-" in str(passage["measures"])
                                                            else measure, passage["measures"]),
                                "instrument": passage["instrument"], "measures": passage["measures"]}
    analysis = results.get("analysis") or {}
    for section in analysis.get("sections", []):
        found[section["id"]] = {"id": section["id"], "kind": "section",
                                "text": "{} ({} {}–{})".format(section["label"], measures, section["first"], section["last"])}
    for cadence in analysis.get("cadences", []):
        kind = CADENCES["en" if language == "en" else "es"].get(cadence["kind"], cadence["kind"])
        found[cadence["id"]] = {"id": cadence["id"], "kind": "cadence",
                                "text": "{} ({} {})".format(kind, measure, cadence["measure"])}
    for theme in analysis.get("themes", []):
        found[theme["id"]] = {"id": theme["id"], "kind": "theme",
                              "text": "{} ({} {}–{})".format(theme["id"], measures, theme["first"], theme["last"])}
    schedule = results.get("schedule") or {}
    for rehearsal in schedule.get("rehearsals", []):
        found[rehearsal["id"]] = {"id": rehearsal["id"], "kind": "rehearsal", "text": _date(rehearsal["date"])}
    for concert in schedule.get("concerts", []):
        found[concert["id"]] = {"id": concert["id"], "kind": "concert", "text": concert["title"]}
    return found


def validate_answer(answer, evidence: dict) -> WorkAnswer:
    try:
        found = WorkAnswer.model_validate(answer)
    except ValidationError as error:
        fields = sorted({".".join(str(part) for part in item["loc"]) + f" ({item['type']})"
                         for item in error.errors() if item.get("loc")})[:6]
        raise InvalidExplanation("Respuesta fuera del esquema: " + ", ".join(fields or ["?"])) from None
    unknown = sorted(set(found.cites) - set(cited(evidence["results"])))
    if unknown:
        raise InvalidExplanation("Cita que no está en las evidencias: " + ", ".join(unknown))
    if IDS_IN_TEXT.search(found.answer):
        raise InvalidExplanation("Los ids van solo en las citas, no en el texto.")
    return found


def _question(question: Optional[str], suggestion: Optional[str]) -> str:
    if suggestion is not None:
        if suggestion not in SUGGESTIONS:
            raise ValueError("Pregunta sugerida desconocida.")
        return ""
    text = " ".join((question or "").split())
    if not text or len(text) > MAX_QUESTION:
        raise ValueError("Escribe una pregunta de hasta {} caracteres.".format(MAX_QUESTION))
    return text


def _calls(chosen) -> list[dict]:
    """What the provider chose, as calls with their arguments; a bare name is a call without them."""
    found = []
    for call in chosen or []:
        if isinstance(call, str):
            call = {"name": call, "args": {}}
        if isinstance(call, dict) and isinstance(call.get("name"), str):
            found.append({"name": call["name"], "args": call.get("args") if isinstance(call.get("args"), dict) else {}})
    return found


def answer_with_tools(question: str, suggestion: Optional[str], *, scope: str, specs: list[dict], rules, recognise_topic,
                      run, evidence: dict, answer, validate, cited_index, provider, demo, cache, language: str,
                      prompt_version: str, purpose: str) -> dict:
    """What asking the work and asking the repertoire share. The provider chooses the calls (function calling) unless
    the question is a suggestion or there is no AI; then the rules choose them (rules(topic) → calls). run(calls) →
    results; answer(who, evidence) → raw answer, validated and checked like every explanation."""
    topic, fallback_reason, writer, calls = suggestion, None, demo, []
    if suggestion is None and provider.info.kind == "llm":
        try:
            calls, writer = _calls(provider.choose_tools(question, specs, language, scope)), provider
        except Exception as error:
            fallback_reason = failure_reason(error)
    if writer is demo:
        topic = topic or recognise_topic(question)
        calls = rules(topic) if topic else []
    results, read = run(calls)
    evidence = {**evidence, "question": question, "results": results}
    if writer is demo and topic:
        evidence["topic"] = topic
    if language == "en":
        evidence["language"] = "en"
    version = prompt_version + ("-en" if language == "en" else "")
    shown = run_explanation(evidence, answer, validate, writer, demo, version, cache=cache, purpose=purpose)
    if fallback_reason:
        shown["fallback_reason"] = fallback_reason
    written, index = shown.pop("explanation"), cited_index(results, language)
    return {**shown, "question": question or None, "suggestion": suggestion, "tools": read, "answer": written,
            "cites": [index[code] for code in written["cites"] if code in index]}


def ask_work(question: Optional[str], suggestion: Optional[str], tools: WorkTools, provider, demo, cache=None,
             language: str = "es") -> dict:
    """The answer shown to the director: who wrote it, which functions were read and what each cited id is."""
    question = _question(question, suggestion)

    def run(calls):
        names = list(dict.fromkeys(call["name"] for call in calls if call["name"] in TOOLS))
        return {name: getattr(tools, name)() for name in names}, names

    return answer_with_tools(
        question, suggestion, scope="work", specs=tool_specs(language),
        rules=lambda topic: [{"name": name, "args": {}} for name in SUGGESTIONS.get(topic, ())],
        recognise_topic=recognise, run=run, evidence={"version": EVIDENCE_VERSION, "title": evidence_text(tools.title)},
        answer=lambda who, data: who.answer_work_question(data), validate=validate_answer, cited_index=cited,
        provider=provider, demo=demo, cache=cache, language=language, prompt_version=PROMPT_VERSION, purpose="work_question")
