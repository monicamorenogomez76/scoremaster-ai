"""Asking the repertoire (M6, 2026-11-20): a question about all the works of the signed-in director. The programme chooses
the works: find_works filters and sorts the stored analyses deterministically, and the AI only turns the question into the
arguments of read-only functions (function calling) and explains what they returned. Arguments it gets wrong are ignored,
never an error; the works keep the same id (W1… by title) in every function, and the database ids never reach the AI.
The answer is validated and checked like every explanation; the suggested questions, and every question without the AI,
are answered by rules (the demo), never presented as AI."""
import re
from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional

from pydantic import ValidationError

from backend.application.explanations import InvalidExplanation
from backend.application.library import PREPARATION_STATUSES
from backend.application.work_questions import WorkAnswer, _plain, _question, answer_with_tools
from backend.domain.text import evidence_text

PROMPT_VERSION = "repertoire-question-v1"
EVIDENCE_VERSION = "repertoire-question-evidence-v1"
TOOLS = ("find_works", "work_details", "schedule", "band")
MAX_CALLS = 4
MAX_FOUND = 12
MAX_DETAILS = 2
MAX_CONCERTS, MAX_REHEARSALS = 4, 6
ORDERS = ("title", "grade_asc", "grade_desc", "minutes_asc", "minutes_desc")
IDS_IN_TEXT = re.compile(r"\b[WKRPSCT]\d{1,3}\b")
# The suggested questions and the calls the rules make for each one; they never spend AI quota.
SUGGESTIONS = {
    "ready": [{"name": "find_works", "args": {"band_ready": True}}],
    "easiest": [{"name": "find_works", "args": {"order": "grade_asc"}}],
    "hardest": [{"name": "find_works", "args": {"order": "grade_desc"}}],
    "preparing": [{"name": "find_works", "args": {"status": "preparing"}}],
    "concerts": [{"name": "schedule", "args": {}}],
}

DESCRIPTIONS = {
    "es": {
        "find_works": "Busca obras del repertorio de la directora con los análisis guardados: filtra por grado (1 a 6), "
                      "duración en minutos, si su banda las cubre enteras, estado de preparación o texto del título o del "
                      "compositor, y las ordena. Devuelve cuántas cumplen y, de cada una, título, compositor, grado, "
                      "minutos, pasajes críticos, porcentaje cubierto por la banda, instrumentos que faltan y estado.",
        "work_details": "Detalle de una obra del repertorio por su título: grado y criterios que lo fijan, pasajes "
                        "críticos, instrumentos más exigentes y lo que le falta a la banda.",
        "schedule": "Próximos conciertos (fecha, lugar y obras del programa) y ensayos (fecha y minutos de cada obra).",
        "band": "Plantilla de la banda activa: cuántos músicos tiene de cada instrumento.",
        "grade_min": "Grado mínimo, de 1 a 6.", "grade_max": "Grado máximo, de 1 a 6.",
        "min_minutes": "Duración mínima en minutos.", "max_minutes": "Duración máxima en minutos.",
        "band_ready": "true para quedarse solo con las obras que la banda cubre enteras.",
        "status": "Estado de preparación: review (por revisar), preparing (en preparación), ready (lista) o archived "
                  "(archivada).",
        "text": "Texto que debe aparecer en el título o en el compositor.",
        "order": "Orden: title, grade_asc, grade_desc, minutes_asc o minutes_desc.",
        "title": "Título de la obra, o parte de él.",
    },
    "en": {
        "find_works": "Finds works of the director's repertoire from their stored analyses: filters by grade (1 to 6), "
                      "duration in minutes, whether her band covers every part, preparation status or text of the title or "
                      "composer, and sorts them. Returns how many match and, for each, title, composer, grade, minutes, "
                      "critical passages, share covered by the band, missing instruments and status.",
        "work_details": "Details of one work of the repertoire by its title: grade and the criteria that set it, critical "
                        "passages, most demanding instruments and what the band lacks.",
        "schedule": "Coming concerts (date, place and works of the programme) and rehearsals (date and minutes of each work).",
        "band": "Lineup of the active band: how many musicians it has of each instrument.",
        "grade_min": "Lowest grade, 1 to 6.", "grade_max": "Highest grade, 1 to 6.",
        "min_minutes": "Shortest duration in minutes.", "max_minutes": "Longest duration in minutes.",
        "band_ready": "true to keep only the works the band covers entirely.",
        "status": "Preparation status: review, preparing, ready or archived.",
        "text": "Text that must appear in the title or the composer.",
        "order": "Order: title, grade_asc, grade_desc, minutes_asc or minutes_desc.",
        "title": "Title of the work, or part of it.",
    },
}

# Without the AI, the first rule whose words the question uses chooses the calls; numbers in it fill the filters.
KEYWORDS = (
    ("concerts", ("concierto", "ensay", "programa", "concert", "rehears", "programme", "program")),
    ("band", ("musico", "plantilla", "musician", "lineup", "players")),
    ("preparing", ("preparando", "preparacion", "preparing")),
    ("ready", ("lista", "listas", "cubre", "cubr", "falta", "ready", "cover", "missing")),
    ("easiest", ("facil", "faciles", "sencill", "easy", "easiest", "easier")),
    ("hardest", ("dificil", "dificiles", "complicad", "hard", "hardest", "difficult")),
)


@dataclass(frozen=True)
class RepertoireTools:
    """The read-only data of the signed-in director, built by the route; each is read only if a call needs it.
    works() → one row per work (work_id, title, composer, grade, minutes, critical_passages, compatibility_percent,
    missing, status); details(work_id) → the difficulty and band of one work."""
    works: Callable[[], list[dict]]
    details: Callable[[str], dict]
    rehearsals: Callable[[], list]
    concerts: Callable[[], list]
    band: Callable[[], dict]
    today: date


def tool_specs(language: str = "es") -> list[dict]:
    say = DESCRIPTIONS["en" if language == "en" else "es"]
    number = lambda name: {"type": "number", "description": say[name]}
    return [
        {"name": "find_works", "description": say["find_works"], "parameters": {"type": "object", "properties": {
            "grade_min": {"type": "integer", "description": say["grade_min"]},
            "grade_max": {"type": "integer", "description": say["grade_max"]},
            "min_minutes": number("min_minutes"), "max_minutes": number("max_minutes"),
            "band_ready": {"type": "boolean", "description": say["band_ready"]},
            "status": {"type": "string", "enum": list(PREPARATION_STATUSES), "description": say["status"]},
            "text": {"type": "string", "description": say["text"]},
            "order": {"type": "string", "enum": list(ORDERS), "description": say["order"]}}}},
        {"name": "work_details", "description": say["work_details"], "parameters": {"type": "object", "properties": {
            "title": {"type": "string", "description": say["title"]}}, "required": ["title"]}},
        {"name": "schedule", "description": say["schedule"]},
        {"name": "band", "description": say["band"]},
    ]


def _numbered(rows: list[dict]) -> list[dict]:
    """Every work with its id, by title: the same in every function of the same question."""
    ordered = sorted(rows, key=lambda row: (_plain(row["title"] or ""), row["work_id"]))
    return [{**row, "id": "W{}".format(index)} for index, row in enumerate(ordered, start=1)]


def _number(value) -> Optional[float]:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _public(row: dict) -> dict:
    return {"id": row["id"], "title": evidence_text(row["title"]), "composer": evidence_text(row.get("composer")) or None,
            "grade": row.get("grade"), "minutes": round(row["minutes"], 1) if row.get("minutes") is not None else None,
            "critical_passages": row.get("critical_passages"), "compatibility_percent": row.get("compatibility_percent"),
            "missing": [evidence_text(label) for label in row.get("missing", [])[:6]], "status": row.get("status")}


def find_works(rows: list[dict], args: dict) -> dict:
    """The works that match the filters, sorted; what the AI got wrong in them is left out."""
    works = rows if rows and "id" in rows[0] else _numbered(rows)
    low, high = _number(args.get("grade_min")), _number(args.get("grade_max"))
    shortest, longest = _number(args.get("min_minutes")), _number(args.get("max_minutes"))
    text = " ".join(_plain(args["text"])) if isinstance(args.get("text"), str) else ""
    status = args.get("status") if args.get("status") in PREPARATION_STATUSES else None
    kept = [row for row in works
            if (low is None or (row.get("grade") or 0) >= low) and (high is None or (row.get("grade") or 99) <= high)
            and (shortest is None or (row.get("minutes") or 0) >= shortest)
            and (longest is None or (row.get("minutes") if row.get("minutes") is not None else 1e9) <= longest)
            and (args.get("band_ready") is not True or row.get("compatibility_percent") == 100)
            and (status is None or row.get("status") == status)
            and (not text or text in " ".join(_plain((row.get("title") or "") + " " + (row.get("composer") or ""))))]
    order = args.get("order") if args.get("order") in ORDERS else "title"
    if order != "title":
        field, reverse = order.rsplit("_", 1)
        missing = float("-inf") if reverse == "desc" else float("inf")
        kept = sorted(kept, key=lambda row: row.get(field) if row.get(field) is not None else missing,
                      reverse=reverse == "desc")
    return {"total": len(kept), "works": [_public(row) for row in kept[:MAX_FOUND]]}


def _details(works: list[dict], details, args: dict) -> dict:
    wanted = " ".join(_plain(args["title"])) if isinstance(args.get("title"), str) else ""
    found = [row for row in works if wanted and wanted in " ".join(_plain(row["title"] or ""))][:MAX_DETAILS]
    return {"works": [{"id": row["id"], "title": evidence_text(row["title"]), **details(row["work_id"])} for row in found]}


def _schedule(works: list[dict], rehearsals: list, concerts: list, today: date) -> dict:
    ids = {row["work_id"]: row for row in works}
    named = lambda work_ids: [{"id": ids[str(work)]["id"], "title": evidence_text(ids[str(work)]["title"])}
                              for work in work_ids if str(work) in ids]
    titles = {concert.id: concert.draft.title for concert in concerts}
    coming = sorted((concert for concert in concerts if concert.draft.date >= today), key=lambda item: item.draft.date)
    sessions = sorted((item for item in rehearsals if item.draft.date >= today), key=lambda item: item.draft.date)
    return {
        "concerts": [{"id": "K{}".format(index), "title": evidence_text(concert.draft.title),
                      "date": concert.draft.date.isoformat(), "days_left": (concert.draft.date - today).days,
                      "place": evidence_text(concert.draft.place) or None, "works": named(concert.draft.work_ids)}
                     for index, concert in enumerate(coming[:MAX_CONCERTS], start=1)],
        "rehearsals": [{"id": "R{}".format(index), "date": item.draft.date.isoformat(), "time": item.draft.time,
                        "concert": evidence_text(titles.get(item.draft.concert_id)) or None,
                        "works": [{**entry, "minutes": sum(block.minutes for block in item.draft.blocks
                                                           if str(block.work_id) == entry_id)}
                                  for entry, entry_id in zip(named(item.draft.work_ids),
                                                             [str(work) for work in item.draft.work_ids if str(work) in ids])]}
                       for index, item in enumerate(sessions[:MAX_REHEARSALS], start=1)],
    }


def recognise(question: str) -> Optional[str]:
    words = _plain(question)
    if _grade_in(words) is not None or _minutes_in(words) is not None:
        return "filter"
    for topic, stems in KEYWORDS:
        if any(word.startswith(stem) for word in words for stem in stems):
            return topic
    return None


def _grade_in(words: list[str]) -> Optional[int]:
    for before, word in zip(words, words[1:]):
        if before in ("grado", "grade", "nivel", "level") and word.isdigit() and 1 <= int(word) <= 6:
            return int(word)
    return None


def _minutes_in(words: list[str]) -> Optional[int]:
    for number, unit in zip(words, words[1:]):
        if number.isdigit() and unit.startswith(("minuto", "minute", "min")):
            return int(number)
    return None


def _rules(question: str):
    """The calls the rules make for a topic; a question with a grade or minutes in it filters by them."""
    def calls(topic):
        if topic == "filter":
            words = _plain(question)
            grade, minutes = _grade_in(words), _minutes_in(words)
            args = {"grade_min": grade, "grade_max": grade} if grade is not None else {}
            return [{"name": "find_works", "args": {**args, **({"max_minutes": minutes} if minutes is not None else {})}}]
        if topic == "band":
            return [{"name": "band", "args": {}}]
        return SUGGESTIONS.get(topic, [])
    return calls


def cited(results: list, language: str = "es") -> dict:
    """Every id the results hold, with what the interface shows for it; a work keeps its database id to be opened."""
    found = {}
    for item in results:
        result = item["result"]
        for work in result.get("works", []) if item["function"] in ("find_works", "work_details") else []:
            found[work["id"]] = {"id": work["id"], "kind": "work", "text": work["title"]}
        for concert in result.get("concerts", []) if item["function"] == "schedule" else []:
            found[concert["id"]] = {"id": concert["id"], "kind": "concert", "text": concert["title"]}
            found.update({work["id"]: {"id": work["id"], "kind": "work", "text": work["title"]} for work in concert["works"]})
        for rehearsal in result.get("rehearsals", []) if item["function"] == "schedule" else []:
            year, month, day = rehearsal["date"].split("-")
            found[rehearsal["id"]] = {"id": rehearsal["id"], "kind": "rehearsal", "text": "/".join((day, month, year))}
            found.update({work["id"]: {"id": work["id"], "kind": "work", "text": work["title"]} for work in rehearsal["works"]})
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


def ask_repertoire(question: Optional[str], suggestion: Optional[str], tools: RepertoireTools, provider, demo, cache=None,
                   language: str = "es") -> dict:
    """The answer shown to the director, with the works it cites ready to be opened."""
    if suggestion is not None and suggestion not in SUGGESTIONS:
        raise ValueError("Pregunta sugerida desconocida.")
    question = "" if suggestion else _question(question, None)
    loaded = {}

    def works() -> list[dict]:
        if "works" not in loaded:
            loaded["works"] = _numbered(tools.works())
        return loaded["works"]

    def run(calls):
        results, read = [], []
        for call in [call for call in calls if call["name"] in TOOLS][:MAX_CALLS]:
            name, args = call["name"], call["args"]
            if name == "find_works":
                result = find_works(works(), args)
            elif name == "work_details":
                result = _details(works(), tools.details, args)
            elif name == "schedule":
                result = _schedule(works(), tools.rehearsals(), tools.concerts(), tools.today)
            else:
                result = tools.band()
            results.append({"function": name, "arguments": args, "result": result})
            read.append(name)
        return results, list(dict.fromkeys(read))

    shown = answer_with_tools(
        question, suggestion, scope="repertoire", specs=tool_specs(language), rules=_rules(question),
        recognise_topic=recognise, run=run, evidence={"version": EVIDENCE_VERSION},
        answer=lambda who, data: who.answer_repertoire_question(data), validate=validate_answer, cited_index=cited,
        provider=provider, demo=demo, cache=cache, language=language, prompt_version=PROMPT_VERSION,
        purpose="repertoire_question")
    database = {row["id"]: row["work_id"] for row in loaded.get("works", [])}
    return {**shown, "cites": [{**cite, "work_id": database[cite["id"]]} if cite["kind"] == "work" else cite
                               for cite in shown["cites"]]}
