"""Analysing a work and keeping it in its owner's library: what POST /analyze does once the upload is
validated, shared with the demo account's seed (PR 4 of the closing plan, 2026-10-14)."""
import hashlib
from pathlib import Path
from uuid import UUID

from backend.analyzers.band_fit import compute_band_fit
import logging

from backend.analyzers.difficulty import DIFFICULTY_VERSION, compute_difficulty_score
from backend.analyzers.rehearsal_plan import build_rehearsal_plan
from backend.analyzers.tempo import compute_tempo_metrics, estimate_duration
from backend.app.stored_scores import confirm_instruments, parsed_work
from backend.application.library import WorkUpload
from backend.application.save_analysis import save_analysis
from backend.domain.instrument_catalog import catalog_version, instrument_name_key
from backend.domain.instrument_resolver import RESOLVED, RESOLVER_VERSION, resolve_part


logger = logging.getLogger(__name__)


def _result(score, profile: dict, total_minutes: int) -> dict:
    difficulty = compute_difficulty_score(score)
    return {
        "title": score.title,
        "composer": score.composer,
        "parts": [part.name for part in score.parts],
        "instruments": [resolve_part(part).as_dict() for part in score.parts],
        "difficulty": difficulty,
        "tempo": compute_tempo_metrics(score),
        "duration": estimate_duration(score),
        "band_fit": compute_band_fit(score, profile),
        "rehearsal_plan": build_rehearsal_plan(score, total_minutes, difficulty),
    }


def learned_overrides(score, learned: dict[str, str]) -> dict[str, str]:
    """The instruments the account confirmed before for parts the catalog does not recognise (2026-10-28): «Fiscornio 3»
    takes what «Fiscornio 1» was confirmed as. A part the catalog recognises keeps its instrument."""
    found = {}
    for part in score.parts:
        instrument = learned.get(instrument_name_key(part.metadata.part_name or part.name))
        if instrument and resolve_part(part).status != RESOLVED:
            found[part.name] = instrument
    return found


def analyze_and_store(content: bytes, file_name: str, user_id: UUID, profile: dict, total_minutes: int, overrides: dict,
                      repository, library, score_store=None, source_format: str = "musicxml",
                      learned: dict | None = None) -> dict:
    """The saved analysis with its work id. Raises SQLAlchemyError when the storage fails."""
    # Parsed once per file: updating the band or the rehearsal minutes reuses the kept model.
    parsed = parsed_work(content, score_store)
    overrides = {**learned_overrides(parsed, learned or {}), **overrides}
    score = confirm_instruments(parsed, overrides)
    # Template: what the work needs for instruments never configured, then the saved band,
    # then the musicians sent with this request.
    needed = {item["key"]: item["required"] for item in compute_band_fit(score, {})["requirements"]}
    profile = {**needed, **library.band_profile(user_id), **profile}
    result = _result(score, profile, total_minutes)
    title = (score.title or "").strip() or Path(file_name).stem
    work = library.store_work(user_id, WorkUpload(title, score.composer, Path(file_name).name, content,
                                                  hashlib.sha256(content).hexdigest(), source_format))
    saved = save_analysis(result, content, profile, total_minutes, repository,
                          {part.name: overrides[part.name] for part in score.parts if part.name in overrides},
                          user_id=user_id, work_id=work.id)
    return {**saved, "work_id": str(work.id)}



def refresh_outdated_analyses(repository, library, score_store=None) -> int:
    """Analyses every work whose latest analysis came from an earlier ScoreLint again (difficulty-v2,
    2026-10-14), with the band, minutes and confirmed instruments it was made with. The old analysis stays
    as history and the work itself is not touched. Returns how many works were analysed again."""
    refreshed = 0
    for outdated in repository.outdated_latest(DIFFICULTY_VERSION, {"resolver_version": RESOLVER_VERSION,
                                                                    "catalog_version": catalog_version()}):
        stored = library.work_file(outdated.user_id, outdated.work_id)
        if stored is None:
            continue
        content, _ = stored
        configuration = outdated.configuration
        overrides = configuration.get("instrument_overrides") or {}
        try:
            score = confirm_instruments(parsed_work(content, score_store), overrides)
            result = _result(score, configuration.get("band_profile") or {}, int(configuration.get("total_minutes") or 90))
            save_analysis(result, content, configuration.get("band_profile") or {}, int(configuration.get("total_minutes") or 90),
                          repository, overrides, user_id=outdated.user_id, work_id=outdated.work_id)
            refreshed += 1
        except Exception:
            logger.warning("No se pudo volver a analizar una obra con la versión actual de ScoreLint.", exc_info=True)
    return refreshed
