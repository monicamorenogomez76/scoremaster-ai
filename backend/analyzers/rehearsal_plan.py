"""Ensemble rehearsal plan: sectional blocks per common passage and a final tutti to join them.

Author's decision (2026-10-04): rehearsals are ensemble rehearsals. Common passages come
from overlapping critical passages and from shared material; every passage is rehearsed by
section, and a final tutti joins the passages that involve several sections or share material
across sections. Blocks never exceed the available time.
"""
from __future__ import annotations

import json

from backend.analyzers.difficulty import compute_difficulty_score
from backend.analyzers.rehearsal_passages import find_shared_material, group_common_passages
from backend.domain.models import Score

MIN_BLOCK_MINUTES = 5
TUTTI_SHARE = 0.25


def _range(first: int, last: int) -> str:
    return str(first) if first == last else "{}-{}".format(first, last)


def _score_range(score: Score) -> str:
    numbers = [measure.number for part in score.parts for measure in part.measures]
    return _range(min(numbers), max(numbers)) if numbers else "1"


def _tutti(parts, measure_ranges, minutes, findings, shared) -> dict:
    return {"type": "tutti", "section": None, "parts": parts, "measure_ranges": measure_ranges,
            "minutes": minutes, "findings": findings, "shared": shared}


def _allocate(blocks: list[dict], minutes: int) -> None:
    """Minimum per block, the rest proportional to priority; leftovers to the highest priority."""
    extra = minutes - MIN_BLOCK_MINUTES * len(blocks)
    total_priority = sum(block["priority"] for block in blocks) or len(blocks)
    for block in blocks:
        block["minutes"] = MIN_BLOCK_MINUTES + extra * (block["priority"] or 1) // total_priority
    leftover = minutes - sum(block["minutes"] for block in blocks)
    for index in range(leftover):
        blocks[index % len(blocks)]["minutes"] += 1


def build_rehearsal_plan(score: Score, total_minutes: int, difficulty: dict | None = None) -> dict:
    difficulty = difficulty if difficulty is not None else compute_difficulty_score(score)
    total = max(0, int(total_minutes))
    sections = {name: details.get("family", "other") for name, details in difficulty.get("by_instrument", {}).items()}
    section_of = lambda part: sections.get(part, "other")
    all_parts = list(dict.fromkeys(part.name for part in score.parts))
    passages = group_common_passages(difficulty.get("critical_passages", []))
    if not passages:
        return {"total_minutes": total, "planned_minutes": total, "omitted": [],
                "segments": [_tutti(all_parts, [_score_range(score)], total, [], [])]}

    candidates, joins = [], {}
    for passage in passages:
        measure_range = _range(passage.first, passage.last)
        shared = find_shared_material(score, passage.parts, passage.first, passage.last)
        by_section: dict[str, list[str]] = {}
        for part in passage.parts:
            by_section.setdefault(section_of(part), []).append(part)
        for section, parts in sorted(by_section.items()):
            candidates.append({
                "type": "sectional", "section": section, "parts": sorted(parts), "measure_range": measure_range,
                "minutes": 0, "findings": list(passage.findings), "priority": passage.score,
                "shared": [{"parts": list(item.parts), "kind": item.kind} for item in shared
                           if section_of(item.parts[0]) == section_of(item.parts[1]) == section],
            })
        across = [{"parts": list(item.parts), "kind": item.kind, "measure_range": measure_range} for item in shared
                  if section_of(item.parts[0]) != section_of(item.parts[1])]
        if len(by_section) > 1 or across:
            joins[measure_range] = (passage, across)

    tutti_minutes = min(total, max(MIN_BLOCK_MINUTES, round(total * TUTTI_SHARE)))
    remaining = total - tutti_minutes
    capacity = remaining // MIN_BLOCK_MINUTES
    kept, dropped = candidates[:capacity], candidates[capacity:]
    if kept:
        _allocate(kept, remaining)
    else:
        tutti_minutes = total

    worked = list(dict.fromkeys(block["measure_range"] for block in kept))
    joined = [measure_range for measure_range in worked if measure_range in joins] or worked
    tutti = _tutti(all_parts, joined, tutti_minutes,
                   sorted({code for block in kept if block["measure_range"] in joined for code in block["findings"]}),
                   list({json.dumps(item, sort_keys=True): item for measure_range in joined if measure_range in joins
                         for item in joins[measure_range][1]}.values()))
    segments = [{key: value for key, value in block.items() if key != "priority"} for block in kept] + [tutti]
    return {
        "total_minutes": total,
        "planned_minutes": sum(block["minutes"] for block in segments),
        "segments": segments,
        "omitted": [{"section": block["section"], "parts": block["parts"], "measure_range": block["measure_range"],
                     "reason": "time"} for block in dropped],
    }
