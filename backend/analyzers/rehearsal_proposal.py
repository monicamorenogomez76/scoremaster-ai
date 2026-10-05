"""Proposed agenda for a rehearsal of several works.

Initial rules (2026-10-05, editable by the director before saving): a warm-up for the whole band
takes 15 % of the time (at least 5 minutes); the rest is shared among the works in proportion to
their grade, at least MIN_WORK_MINUTES each and in the director's order; works that do not fit are
reported, not squeezed. Each work then gets the ensemble plan of its own passages
(`build_rehearsal_plan`: common lines, subsections and a final tutti), and every block names its work.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.analyzers.rehearsal_plan import build_rehearsal_plan
from backend.domain.models import Score

WARMUP_SHARE = 0.15
MIN_WARMUP_MINUTES = 5
MIN_WORK_MINUTES = 10


@dataclass(frozen=True)
class WorkToRehearse:
    work_id: str
    title: str
    score: Score
    difficulty: dict


def _shares(grades: list[int], minutes: int) -> list[int]:
    """Minutes proportional to the grade, at least MIN_WORK_MINUTES; leftovers to the hardest works."""
    shares = [MIN_WORK_MINUTES] * len(grades)
    free = [index for index in range(len(grades))]
    budget = minutes
    while free:
        total = sum(grades[index] for index in free)
        proposed = {index: budget * grades[index] / total for index in free}
        short = [index for index in free if proposed[index] < MIN_WORK_MINUTES]
        if not short:
            for index in free:
                shares[index] = int(proposed[index])
            break
        for index in short:
            free.remove(index)
            budget -= MIN_WORK_MINUTES
    leftover = minutes - sum(shares)
    for index in sorted(range(len(grades)), key=lambda at: -grades[at])[:leftover]:
        shares[index] += 1
    return shares


def propose_rehearsal(works: list[WorkToRehearse], total_minutes: int) -> dict:
    total = max(0, int(total_minutes))
    warmup = total if not works else min(total, max(MIN_WARMUP_MINUTES, round(total * WARMUP_SHARE)))
    remaining = total - warmup
    planned = works[:remaining // MIN_WORK_MINUTES]
    if works and not planned:
        warmup = total
    grades = [max(1, int(item.difficulty.get("grade") or 1)) for item in planned]
    shares = _shares(grades, remaining) if planned else []

    blocks = [{"type": "warmup", "group": None, "parts": [], "minutes": warmup, "findings": [],
               "work_id": None, "work_title": None}]
    omitted = []
    for item, minutes in zip(planned, shares):
        plan = build_rehearsal_plan(item.score, minutes, item.difficulty)
        blocks += [{**segment, "work_id": item.work_id, "work_title": item.title} for segment in plan["segments"]]
        omitted += [{**block, "work_id": item.work_id, "work_title": item.title} for block in plan["omitted"]]
    return {
        "total_minutes": total,
        "blocks": blocks,
        "works": [{"work_id": item.work_id, "title": item.title, "grade": grade, "minutes": minutes}
                  for item, grade, minutes in zip(planned, grades, shares)],
        "omitted_works": [{"work_id": item.work_id, "title": item.title, "reason": "time"} for item in works[len(planned):]],
        "omitted": omitted,
    }
