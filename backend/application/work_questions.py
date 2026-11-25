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

PROMPT_VERSION = "work-question-v2"   # v2 (2026-11-25): the instrument function
EVIDENCE_VERSION = "work-question-evidence-v2"
MAX_QUESTION = 300
MAX_CITES = 12
MAX_REHEARSALS, MAX_CONCERTS = 6, 4
MAX_PARTS, MAX_PART_PASSAGES, MAX_AVAILABLE, MAX_DEMANDS = 8, 8, 40, 3
MAX_ASKED = 4
TOOLS = ("difficulty", "instrument", "band", "analysis", "schedule")
# The suggested questions and the function each one reads; the rules answer them, so they never spend AI quota.
SUGGESTIONS = {"grade": ("difficulty",), "passages": ("difficulty",), "band": ("band",), "form": ("analysis",),
               "schedule": ("schedule",)}
IDS_IN_TEXT = re.compile(r"\b[PSCTRK]\d{1,3}\b")

DESCRIPTIONS = {
    "es": {
        "difficulty": "Dificultad de la obra calculada por ScoreLint: grado de 1 a 6 y los criterios que lo fijan, los "
                      "instrumentos más exigentes y los pasajes críticos (instrumento, compases y motivo).",
        "instrument": "Lo que tiene que preparar un instrumento o una sección concretos: grado y exigencias de cada una de sus partes "
                      "y todos sus pasajes críticos con sus compases. Úsala siempre que la pregunta nombre un instrumento.",
        "asked": "El instrumento como lo nombra la pregunta: clarinete, trompeta 2, saxos altos…",
        "band": "Si la banda de la directora puede tocar la obra: porcentaje de partes cubiertas, instrumentos que faltan "
                "y partes sin instrumento confirmado.",
        "analysis": "Análisis musical calculado: forma y secciones con sus compases y tonalidades, modulaciones, "
                    "cadencias, temas, textura, tempo, compás y clímax.",
        "schedule": "Próximos ensayos en los que está la obra (fecha y minutos dedicados) y conciertos de su programa.",
    },
    "en": {
        "difficulty": "Difficulty of the work calculated by ScoreLint: grade from 1 to 6 and the criteria that set it, the "
                      "most demanding instruments and the critical passages (instrument, measures and reason).",
        "instrument": "What a given instrument or section has to prepare: grade and demands of each of its parts and all its critical "
                      "passages with their measures. Use it whenever the question names an instrument.",
        "asked": "The instrument as the question names it: clarinet, trumpet 2, alto saxes…",
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
    # What each named instrument has to prepare (2026-11-25): the only function with an argument.
    instrument: Callable[[str], dict] = lambda asked: {"asked": asked, "parts": [], "passages": [], "available": []}


class WorkAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=1200)
    # False when the results of the functions do not answer the question: the interface says so.
    answered: bool
    cites: list[str] = Field(default_factory=list, max_length=MAX_CITES)


def tool_specs(language: str = "es") -> list[dict]:
    """The functions as the AI sees them: a name and what it returns. The work is fixed; only the instrument is asked."""
    descriptions = DESCRIPTIONS["en" if language == "en" else "es"]
    asked = {"parameters": {"type": "object", "properties": {"instrument": {"type": "string", "description": descriptions["asked"]}},
                            "required": ["instrument"]}}
    return [{"name": name, "description": descriptions[name], **(asked if name == "instrument" else {})} for name in TOOLS]


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


# Words that tell one part of an instrument from another, or its key; they do not name it.
_QUALIFIERS = {"bemol", "flat", "natural", "sostenido", "sharp", "alto", "tenor", "soprano", "bajo", "bass", "baritono", "baritone",
               "contralto", "contrabajo", "solo", "primer", "segundo", "tercer"}
_SHORT_NAMES = {"sax": "saxofon", "saxo": "saxofon"}
ASPECTS = {"es": {"range": "tesitura", "register": "registro", "intervals": "saltos", "density": "densidad rítmica",
                  "endurance": "resistencia", "tempo": "tempo"},
           "en": {"range": "range", "register": "register", "intervals": "leaps", "density": "rhythmic density",
                  "endurance": "endurance", "tempo": "tempo"}}


def _same_word(one: str, other: str) -> bool:
    """«clarinetes» and «clarinete», «saxos» and «saxofón»; never «trompa» and «trompeta»."""
    one, other = (_SHORT_NAMES.get(word.rstrip("s"), word.rstrip("s")) for word in (one, other))
    short, long = sorted((one, other), key=len)
    return short == long or (len(short) >= 4 and len(long) - len(short) <= 2 and long.startswith(short))


def _named_parts(by_instrument: dict, asked: str) -> list[str]:
    """The parts of the work that the text names, by label: their numbers and qualifiers choose among them when they are said."""
    said = _plain(asked)
    words = {name: set(_plain(" ".join((entry.get("instrument_label_es") or name, english_label(entry.get("instrument_label_es") or name, name), name))))
             for name, entry in by_instrument.items()}

    def named(name: str) -> bool:
        own = {word for word in words[name] if len(word) >= 3 and not word.isdigit()}
        return any(_same_word(word, mine) for word in said if len(word) >= 3 for mine in (own - _QUALIFIERS) or own)
    found = [name for name in by_instrument if named(name)]
    for word in said:
        if word.isdigit() or word.rstrip("s") in _QUALIFIERS:
            chosen = [name for name in found if any(word == mine or word.rstrip("s") == mine for mine in words[name])]
            found = chosen or found
    return sorted(found, key=lambda name: (by_instrument[name].get("instrument_label_es") or name, name))


def instrument_tool(result: dict, asked: str, language: str = "es") -> dict:
    """What the named instrument has to prepare, from the whole of ScoreLint's analysis: the difficulty function gives only the
    hardest of the work. Its passages keep the id they have there."""
    from backend.application.difficulty_explanation import FINDING_LABELS, FINDING_LABELS_EN
    difficulty = result.get("difficulty") or {}
    by_instrument = difficulty.get("by_instrument") or {}
    english = language == "en"
    findings = FINDING_LABELS_EN if english else FINDING_LABELS
    aspects = ASPECTS["en" if english else "es"]

    def label(name: str, spanish) -> str:
        return evidence_text(english_label(spanish or name, name) if english else spanish or name)
    told = lambda codes: [{"code": code, "label": findings.get(code, code)} for code in codes or []]
    chosen = _named_parts(by_instrument, asked)[:MAX_PARTS]
    parts = []
    for name in chosen:
        entry = by_instrument[name]
        dimensions = sorted(((aspects[key], round(float(value), 1)) for key, value in (entry.get("dimensions") or {}).items()
                             if key in aspects and value), key=lambda item: (-item[1], item[0]))
        parts.append({"name": evidence_text(name), "label": label(name, entry.get("instrument_label_es")), "grade": entry.get("grade"),
                      "technical_index": entry.get("difficulty_score"),
                      "demands": [{"aspect": aspect, "value": value} for aspect, value in dimensions[:MAX_DEMANDS]],
                      "findings": told(entry.get("findings"))})
    passages = [{"id": "P{}".format(index), "instrument": evidence_text(passage.get("instrument")),
                 "label": label(passage.get("instrument"), passage.get("instrument_label_es")),
                 "measures": passage.get("measure_range"), "findings": told(passage.get("findings"))}
                for index, passage in enumerate(difficulty.get("critical_passages") or [], start=1) if passage.get("instrument") in chosen]
    return {"asked": evidence_text(asked), "parts": parts, "passages": passages[:MAX_PART_PASSAGES],
            "available": [] if parts else sorted({label(name, entry.get("instrument_label_es")) for name, entry in by_instrument.items()})[:MAX_AVAILABLE]}


def _together(found: list[dict]) -> dict:
    """Several instruments asked in one question, each part and passage once."""
    once = lambda key, name: list({item[name]: item for result in found for item in result[key]}.values())
    return {"asked": ", ".join(result["asked"] for result in found), "parts": once("parts", "name"),
            "passages": once("passages", "id"), "available": sorted({label for result in found for label in result["available"]})}


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
    for passage in (results.get("difficulty") or {}).get("passages", []) + (results.get("instrument") or {}).get("passages", []):
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
        names = [name for name in dict.fromkeys(call["name"] for call in calls) if name in TOOLS]
        asked = list(dict.fromkeys(call["args"]["instrument"].strip() for call in calls if call["name"] == "instrument"
                                   and isinstance(call["args"].get("instrument"), str) and call["args"]["instrument"].strip()))[:MAX_ASKED]
        if not asked:
            names = [name for name in names if name != "instrument"]
        return {name: _together([tools.instrument(text[:MAX_QUESTION]) for text in asked]) if name == "instrument"
                else getattr(tools, name)() for name in names}, names

    def topic_of(text):
        """A question that names an instrument of the work is about it, unless it asks what the band lacks or about the rest."""
        topic = recognise(text)
        return "instrument" if topic in (None, "passages", "grade") and tools.instrument(text)["parts"] else topic

    def rules(topic):
        if topic == "instrument":
            return [{"name": "instrument", "args": {"instrument": question}}]
        return [{"name": name, "args": {}} for name in SUGGESTIONS.get(topic, ())]

    return answer_with_tools(
        question, suggestion, scope="work", specs=tool_specs(language),
        rules=rules, recognise_topic=topic_of, run=run, evidence={"version": EVIDENCE_VERSION, "title": evidence_text(tools.title)},
        answer=lambda who, data: who.answer_work_question(data), validate=validate_answer, cited_index=cited,
        provider=provider, demo=demo, cache=cache, language=language, prompt_version=PROMPT_VERSION, purpose="work_question")
