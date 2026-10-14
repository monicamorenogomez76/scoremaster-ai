"""Analysing a work and keeping it in its owner's library: what POST /analyze does once the upload is
validated, shared with the demo account's seed (PR 4 of the closing plan, 2026-10-14)."""
import hashlib
from pathlib import Path
from uuid import UUID

from backend.analyzers.band_fit import compute_band_fit
from backend.analyzers.difficulty import compute_difficulty_score
from backend.analyzers.rehearsal_plan import build_rehearsal_plan
from backend.analyzers.tempo import compute_tempo_metrics, estimate_duration
from backend.app.stored_scores import confirm_instruments, parsed_work
from backend.application.library import WorkUpload
from backend.application.save_analysis import save_analysis
from backend.domain.instrument_resolver import resolve_part


def analyze_and_store(content: bytes, file_name: str, user_id: UUID, profile: dict, total_minutes: int, overrides: dict,
                      repository, library, score_store=None) -> dict:
    """The saved analysis with its work id. Raises SQLAlchemyError when the storage fails."""
    # Parsed once per file: updating the band or the rehearsal minutes reuses the kept model.
    score = confirm_instruments(parsed_work(content, score_store), overrides)
    # Template: what the work needs for instruments never configured, then the saved band,
    # then the musicians sent with this request.
    needed = {item["key"]: item["required"] for item in compute_band_fit(score, {})["requirements"]}
    profile = {**needed, **library.band_profile(user_id), **profile}
    difficulty = compute_difficulty_score(score)
    result = {
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
    title = (score.title or "").strip() or Path(file_name).stem
    work = library.store_work(user_id, WorkUpload(title, score.composer, Path(file_name).name, content,
                                                  hashlib.sha256(content).hexdigest()))
    saved = save_analysis(result, content, profile, total_minutes, repository,
                          {part.name: overrides[part.name] for part in score.parts if part.name in overrides},
                          user_id=user_id, work_id=work.id)
    return {**saved, "work_id": str(work.id)}
