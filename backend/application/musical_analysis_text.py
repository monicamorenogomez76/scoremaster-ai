"""The teacher's commentary of the musical analysis (2026-11-19). ScoreMaster calculates the facts
(backend/analyzers/musical_analysis.py); the AI writes about them topic by topic, as a commentary of the subject
«Análisis musical», citing the sections (S1…), cadences (C1…) and themes (T1…) it leans on. Only the interpretation is
opinion. The answer is validated against the evidence: every cited id exists and no id appears in the texts. On any
failure the demo writes it from the same evidence and the interface says why (backend/application/explanations.py)."""
import re

from pydantic import BaseModel, Field, ValidationError

from backend.application.explanations import InvalidExplanation, run_explanation
from backend.domain.text import evidence_text

PROMPT_VERSION = "musical-analysis-text-v7"   # v7 (2026-11-20): a commentary, not a list of data, and longer; v6: lengths in the prompt; v5 (2026-11-19): articulation; v4: themes; v3: meter; v2: harmony
EVIDENCE_VERSION = "musical-analysis-evidence-v5"   # v5 (2026-11-19): articulation; v4: themes; v3: meter…
# The topics of the commentary, in the order of a conservatory analysis; the interpretation, last, is the only opinion.
TOPICS = ("form", "themes", "harmony", "texture", "rhythm", "dynamics", "interpretation")
MAX_SECTIONS = 30
MAX_CADENCES = 60
MAX_LISTED = 4         # parts named in each list of a section (doublings, solos, registers…)
IDS_IN_TEXT = re.compile(r"\b[SC]\d{1,2}\b")

SOLFEGE = {"C": "Do", "D": "Re", "E": "Mi", "F": "Fa", "G": "Sol", "A": "La", "B": "Si"}
ACCIDENTALS = {"es": {"b": " bemol", "#": " sostenido"}, "en": {"b": "♭", "#": "♯"}}


# Gemini gets the schema without bounds (LEAN_SCHEMAS in gemini_provider.py) and the lengths in the prompt (2026-11-20):
# the bounds here leave room for a model that counts characters badly, and a topic may cite every id of the evidence.
class Topic(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    sections: list[str] = Field(default_factory=list, max_length=MAX_SECTIONS)
    cadences: list[str] = Field(default_factory=list, max_length=MAX_CADENCES)
    themes: list[str] = Field(default_factory=list, max_length=MAX_SECTIONS)   # at most one theme per section


class SectionComment(BaseModel):
    section: str = Field(pattern=r"^S\d{1,2}$")
    text: str = Field(min_length=1, max_length=700)


class MusicalAnalysisText(BaseModel):
    summary: str = Field(min_length=1, max_length=800)
    form: Topic
    themes: Topic
    harmony: Topic
    texture: Topic
    rhythm: Topic
    dynamics: Topic
    by_section: list[SectionComment] = Field(max_length=MAX_SECTIONS)
    interpretation: Topic


def _note(note: str, language: str) -> str:
    """«Si bemol», «B♭»."""
    letter = note[0] if language == "en" else SOLFEGE[note[0]]
    return letter + ACCIDENTALS[language].get(note[1:], "")


def key_label(key: dict | None, language: str = "es") -> str:
    """«Mi bemol mayor», «E♭ major»."""
    if not key:
        return ""
    letter, accidental = key["tonic"][0], ACCIDENTALS[language].get(key["tonic"][1:], "")
    if language == "en":
        return letter + accidental + " " + key["mode"]
    return SOLFEGE[letter] + accidental + (" menor" if key["mode"] == "minor" else " mayor")


def _section(section: dict, language: str, name) -> dict:
    names = lambda items: [name(item) for item in items[:MAX_LISTED]]
    return {
        "id": section["id"], "label": section["label"], "first": section["first"], "last": section["last"],
        "like": section["like"], "key": key_label(section["key"], language), "relation": section["relation"],
        "modulations": [{"measure": item["measure"], "key": key_label(item["key"], language), "relation": item["relation"]}
                        for item in section["modulations"][:MAX_LISTED]],
        "melody": name(section["melody"]) if section["melody"] else None, "doubled_by": names(section["doubled_by"]),
        "parts_playing": len(section["playing"]), "texture": section["texture"], "texture_kind": section["texture_kind"],
        "tempo": section["tempo"], "meter": section["meter"], "dynamics": section["dynamics"][:8],
        "phrases": section["structure"], "phrase_endings": [phrase["ending"] for phrase in section["phrases"]][:8],
        "periods": [period["kind"] for period in section["periods"]][:4],
        "theme": section["theme"], "theme_heads": [{"theme": item["theme"], "part": name(item["part"]),
                                                    "measure": item["measure"]} for item in section["motifs"][:MAX_LISTED]],
        "syncopation": section["syncopation"],
        "ostinatos": [{**item, "part": name(item["part"])} for item in section["ostinatos"][:MAX_LISTED]],
        "imitations": [{"part": name(item["part"]), "measure": item["measure"]}
                       for item in section["imitations"][:MAX_LISTED]],
        "solos": [{**item, "part": name(item["part"])} for item in section["solos"][:MAX_LISTED]],
        "percussion": [{**item, "part": name(item["part"])} for item in section["percussion"][:MAX_LISTED]],
        "extreme_high_register": names([item["part"] for item in section["registers"]]),
        "harmonic_rhythm": section.get("harmonic_rhythm"),
        "articulation": section.get("articulation"), "hemiolas": section.get("hemiolas", [])[:8], "displaced_accents": section.get("displaced_accents", [])[:8],
        "secondary_dominants": section.get("secondary_dominants", [])[:MAX_LISTED],
        "pedals": [{**item, "note": _note(item["note"], language)} for item in section.get("pedals", [])[:MAX_LISTED]],
    }


def analysis_evidence(analysis: dict, title: str, language: str = "es", labels: dict | None = None) -> dict:
    """The calculated analysis, bounded and with its ids: what the AI may write about, and nothing else. Parts go by
    their catalog name in the language of the interface (labels), else by their own."""
    general = analysis["general"] or {}
    name = lambda part: evidence_text((labels or {}).get(part, part))
    evidence = {
        "version": EVIDENCE_VERSION, "title": evidence_text(title or ""), "form": analysis["form"],
        "main_key": key_label(analysis["main_key"], language),
        "general": {"measures": general.get("measures"), "parts": general.get("parts"), "seconds": general.get("seconds"),
                    "tempos": [{"measure": item["measure"], "bpm": item["bpm"], "words": item["words"][:3]}
                               for item in general.get("tempos", [])[:8]],
                    "meters": general.get("meters", [])[:8]},
        "climax": analysis["climax"],
        "sections": [_section(section, language, name) for section in analysis["sections"][:MAX_SECTIONS]],
        "themes": [{"id": theme["id"], "section": theme["section"],
                    "part": name(theme["part"]) if theme["part"] else None,
                    "first": theme["first"], "last": theme["last"],
                    **{key: theme[key] for key in ("lowest", "highest", "range", "contour", "motion") if key in theme}}
                   for theme in analysis.get("themes", [])],
        "cadences": [{"id": cadence["id"], "measure": cadence["measure"], "kind": cadence["kind"],
                      "section": cadence["section"]} for cadence in analysis["cadences"][:MAX_CADENCES]],
    }
    if language == "en":
        evidence["language"] = "en"
    return evidence


def validate_text(answer, evidence: dict) -> MusicalAnalysisText:
    try:
        text = MusicalAnalysisText.model_validate(answer)
    except ValidationError as error:
        # Where and why, never the text: «themes.text (string_too_long)».
        fields = sorted({".".join(str(part) for part in item["loc"]) + f" ({item['type']})"
                         for item in error.errors() if item.get("loc")})[:6]
        raise InvalidExplanation("Respuesta fuera del esquema: " + ", ".join(fields or ["?"])) from None
    known = {"sections": {item["id"] for item in evidence["sections"]},
             "cadences": {item["id"] for item in evidence["cadences"]},
             "themes": {item["id"] for item in evidence["themes"]}}
    for name in TOPICS:
        topic = getattr(text, name)
        for kind, ids in known.items():
            unknown = set(getattr(topic, kind)) - ids
            if unknown:
                raise InvalidExplanation("Cita que no está en las evidencias: " + ", ".join(sorted(unknown)))
    seen = set()
    for comment in text.by_section:
        if comment.section not in known["sections"] or comment.section in seen:
            raise InvalidExplanation("Comentario de una sección que no está en las evidencias: " + comment.section)
        seen.add(comment.section)
    texts = [text.summary] + [getattr(text, name).text for name in TOPICS] + [item.text for item in text.by_section]
    if any(IDS_IN_TEXT.search(item) for item in texts):
        raise InvalidExplanation("Los ids van solo en las citas, no en el texto.")
    return text


def explain_analysis(analysis: dict, title: str, provider, demo, cache=None, language: str = "es",
                     labels: dict | None = None) -> dict:
    if not analysis["sections"]:
        provider = demo    # nothing to comment on: no quota is spent
    evidence = analysis_evidence(analysis, title, language, labels)
    ask = lambda who, data: who.explain_musical_analysis(data)
    version = PROMPT_VERSION + ("-en" if language == "en" else "")
    result = run_explanation(evidence, ask, validate_text, provider, demo, version, cache=cache,
                             purpose="musical_analysis")
    return {**result, "commentary": result.pop("explanation")}
