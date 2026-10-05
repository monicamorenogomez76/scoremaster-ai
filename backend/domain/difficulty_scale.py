"""Visible difficulty grades 1-6 and the internal technical index 0-10 (step 13).

Author's decisions (2026-10-05): the index is twice the previous 0-5 score, an explicit transform
that keeps the order between parts, and six equal bands of the index give the grade until the
evaluation with musicians calibrates them. The rubric (docs/DIFFICULTY_CRITICALITY.md) describes
the band that can play each grade; it is not an official certification.
"""
from __future__ import annotations

SCALE = {"version": 2, "grades": 6, "technical_index_max": 10}


def technical_index(legacy_score: float) -> float:
    return round(max(0.0, min(10.0, legacy_score * 2)), 2)


def grade_from_index(index: float) -> int:
    return 1 + min(5, int(index * 6 / 10))
