from __future__ import annotations

from backend.analyzers.endurance import uninterrupted_passages
from backend.domain.models import Finding, Score


def find_long_passages_without_rest(score: Score) -> list[Finding]:
    findings = []
    threshold = 8
    for part in score.parts:
        for passage in uninterrupted_passages(part):
            if passage["measure_count"] < threshold:
                continue
            start, end = passage["measure_start"], passage["measure_end"]
            findings.append(Finding(
                code="SL005",
                severity="warning",
                instrument=part.name,
                measure_range=str(start) if start == end else f"{start}-{end}",
                description="Long passage without rest",
                evidence={**passage, "threshold_measures": threshold},
            ))
    return findings
