"""Rehearsal series that prepares a concert.

Decided on 2026-10-06; the percentages and factors are initial rules, editable by the
director before saving and to be calibrated:
- Dates follow a weekly pattern from a start date until the day before the concert.
- Phases: the first third of the series reads and works the passages (25 % tutti), the middle
  rehearsals work passages and integrate (40 %), the one before last integrates (60 %) and the last
  one is the general rehearsal: a warm-up and a run-through of every work in concert order.
- The director's review changes the plan: a passage left pending weighs ×2, one to improve ×1.5 and a
  resolved one ×0.25; a work with pending passages gets more time and a resolved one less.
- A work that does not fit in a rehearsal is rehearsed first in the next one.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from math import ceil

from backend.analyzers.rehearsal_plan import MIN_BLOCK_MINUTES
from backend.analyzers.rehearsal_proposal import MIN_WARMUP_MINUTES, WARMUP_SHARE, WorkToRehearse, propose_rehearsal
from backend.analyzers.tempo import estimate_duration

PHASE_TUTTI = {"reading": 0.25, "passages": 0.40, "integration": 0.60}
PASSAGE_FACTORS = {"pending": 2.0, "improve": 1.5, "resolved": 0.25, "not_done": 1.0}


@dataclass(frozen=True)
class Slot:
    date: date
    time: str | None
    duration_minutes: int
    phase: str


@dataclass(frozen=True)
class ReviewedBlock:
    """A block of a rehearsal already held, as the director reviewed it (oldest first)."""
    work_id: str
    measures: str
    status: str


def rehearsal_dates(start: date, concert_date: date, weekdays) -> list[date]:
    days = set(weekdays)
    return [start + timedelta(days=offset) for offset in range(max(0, (concert_date - start).days))
            if (start + timedelta(days=offset)).weekday() in days]


def phases(count: int) -> list[str]:
    if count <= 0:
        return []
    if count <= 2:
        return ["integration", "general"][-count:]
    reading = ceil((count - 2) / 3)
    return ["reading"] * reading + ["passages"] * (count - 2 - reading) + ["integration", "general"]


def _spans(measures: str) -> list[tuple[int, int]]:
    spans = []
    for piece in str(measures or "").replace("–", "-").split(","):
        bounds = [int(value) for value in piece.strip().split("-") if value.strip().isdigit()]
        if bounds:
            spans.append((bounds[0], bounds[-1]))
    return spans


def _overlaps(left: str, right: str) -> bool:
    return any(a <= d and c <= b for a, b in _spans(left) for c, d in _spans(right))


def _reviewed(item: WorkToRehearse, reviews: list[ReviewedBlock]) -> WorkToRehearse:
    """The work with its passages and its time weighted by the latest review of each passage."""
    own = [review for review in reviews if review.work_id == item.work_id]
    if not own:
        return item
    passages = []
    for passage in item.difficulty.get("critical_passages", []):
        latest = [review for review in own if _overlaps(review.measures, passage.get("measure_range", ""))]
        factor = PASSAGE_FACTORS.get(latest[-1].status, 1.0) if latest else 1.0
        passages.append({**passage, "score": passage.get("score", 0) * factor})
    statuses = {review.status for review in own}
    weight = 1.5 if "pending" in statuses else 1.25 if "improve" in statuses else 0.75 if statuses == {"resolved"} else 1.0
    return replace(item, difficulty={**item.difficulty, "critical_passages": passages}, weight=weight)


def _general(works: list[WorkToRehearse], total: int) -> dict:
    """Warm-up, then each work played through in concert order, with time in proportion to its length."""
    warmup = min(total, max(MIN_WARMUP_MINUTES, round(total * WARMUP_SHARE)))
    remaining = total - warmup
    played = works[:remaining // MIN_BLOCK_MINUTES] if works else []
    seconds = [max(1, estimate_duration(item.score)["seconds"]) for item in played]
    minutes = [MIN_BLOCK_MINUTES + int((remaining - MIN_BLOCK_MINUTES * len(played)) * share / sum(seconds))
               for share in seconds] if played else []
    if minutes:
        minutes[-1] += remaining - sum(minutes)
    else:
        warmup = total
    blocks = [{"type": "warmup", "group": None, "parts": [], "minutes": warmup, "findings": [], "work_id": None, "work_title": None}]
    blocks += [{"type": "runthrough", "group": None, "parts": [], "minutes": length, "findings": [],
                "work_id": item.work_id, "work_title": item.title} for item, length in zip(played, minutes)]
    return {"blocks": blocks, "omitted_works": [item.work_id for item in works[len(played):]]}


def plan_concert(programme: list[WorkToRehearse], slots: list[Slot], reviews: list[ReviewedBlock]) -> list[dict]:
    """Agenda of every slot; `programme` is in concert order. Nothing is saved: the director reviews it."""
    weighted = [_reviewed(item, reviews) for item in programme]
    order = list(weighted)
    plans = []
    for slot in slots:
        if slot.phase == "general":
            planned = _general(weighted, slot.duration_minutes)
        else:
            proposal = propose_rehearsal(order, slot.duration_minutes, PHASE_TUTTI.get(slot.phase, 0.25))
            planned = {"blocks": proposal["blocks"], "omitted_works": [item["work_id"] for item in proposal["omitted_works"]]}
            # Works left out go first next time.
            skipped = set(planned["omitted_works"])
            order = [item for item in order if item.work_id in skipped] + [item for item in order if item.work_id not in skipped]
        work_ids = list(dict.fromkeys(block["work_id"] for block in planned["blocks"] if block["work_id"]))
        plans.append({"date": slot.date.isoformat(), "time": slot.time, "duration_minutes": slot.duration_minutes,
                      "phase": slot.phase, "work_ids": work_ids, **planned})
    return plans
