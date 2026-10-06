"""Ensemble rehearsal plan.

Author's decisions (2026-10-04): rehearsals are ensemble rehearsals. In every passage, first
the parts that play the same thing rehearse together (common line or common rhythm, even across
families); then the remaining difficult parts rehearse by subsection (flutes, double reeds,
clarinets, saxophones, high brass, low voices, percussion, strings and rhythm); a final tutti
joins the passages. Blocks never exceed the available time.
"""
from __future__ import annotations


from backend.analyzers.difficulty import compute_difficulty_score
from backend.analyzers.rehearsal_passages import _bounds, find_common_lines, group_common_passages
from backend.domain.instrument_resolver import resolve_part
from backend.domain.models import Score

MIN_BLOCK_MINUTES = 5
TUTTI_SHARE = 0.25
# A block covers only the measures its instruments play; a silence of a whole 8-bar phrase splits it.
SPLIT_SILENCE = 8


def _range(first: int, last: int) -> str:
    return str(first) if first == last else "{}-{}".format(first, last)


def _score_range(score: Score) -> str:
    numbers = [measure.number for part in score.parts for measure in part.measures]
    return _range(min(numbers), max(numbers)) if numbers else "1"


def _tutti(parts, measure_ranges, minutes, findings) -> dict:
    return {"type": "tutti", "group": None, "parts": parts, "measure_ranges": measure_ranges,
            "minutes": minutes, "findings": findings}


def _allocate(blocks: list[dict], minutes: int) -> None:
    """Minimum per block, the rest proportional to priority; leftovers to the highest priority."""
    extra = minutes - MIN_BLOCK_MINUTES * len(blocks)
    total_priority = sum(block["priority"] for block in blocks) or len(blocks)
    for block in blocks:
        block["minutes"] = MIN_BLOCK_MINUTES + int(extra * (block["priority"] or 1) // total_priority)
    leftover = minutes - sum(block["minutes"] for block in blocks)
    for index in range(leftover):
        blocks[index % len(blocks)]["minutes"] += 1


def _phrases(score: Score, parts, first: int, last: int) -> list[tuple[int, int]]:
    """Measure spans where any of the parts plays, split by silences of SPLIT_SILENCE measures."""
    names = set(parts)
    playing = sorted({measure.number for part in score.parts if part.name in names for measure in part.measures
                      if first <= measure.number <= last and any(not note.is_rest for note in measure.notes)})
    spans: list[list[int]] = []
    for number in playing:
        if spans and number - spans[-1][1] - 1 < SPLIT_SILENCE:
            spans[-1][1] = number
        else:
            spans.append([number, number])
    return [(start, end) for start, end in spans]


def _merged(ranges: list[str]) -> list[str]:
    """Overlapping or adjacent measure ranges joined, in score order."""
    spans = sorted(_bounds(measure_range) for measure_range in ranges)
    merged: list[list[int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [_range(start, end) for start, end in merged]


def _rehearsal_groups(score: Score) -> dict[str, str]:
    groups = {}
    for part in score.parts:
        identity = resolve_part(part).identity
        groups[part.name] = (identity.rehearsal_group if identity and identity.rehearsal_group else "other")
    return groups


def build_rehearsal_plan(score: Score, total_minutes: int, difficulty: dict | None = None,
                         tutti_share: float = TUTTI_SHARE) -> dict:
    """tutti_share: part of the time for the final tutti (more as a concert comes closer)."""
    difficulty = difficulty if difficulty is not None else compute_difficulty_score(score)
    total = max(0, int(total_minutes))
    group_of = _rehearsal_groups(score)
    all_parts = list(dict.fromkeys(part.name for part in score.parts))
    passages = group_common_passages(difficulty.get("critical_passages", []))
    if not passages:
        return {"total_minutes": total, "planned_minutes": total, "omitted": [],
                "segments": [_tutti(all_parts, [_score_range(score)], total, [])]}

    candidates, joined_ranges = [], set()
    for passage in passages:
        common = {"findings": list(passage.findings), "priority": passage.score, "minutes": 0}
        lines = find_common_lines(score, passage.parts, passage.first, passage.last)
        in_lines = {part for line in lines for part in line.parts}
        by_group: dict[str, list[str]] = {}
        for part in passage.parts:
            if part not in in_lines:
                by_group.setdefault(group_of.get(part, "other"), []).append(part)
        blocks = [{"type": "common", "group": None, "parts": list(line.parts), "kind": line.kind,
                   "groups": sorted({group_of.get(part, "other") for part in line.parts})} for line in lines]
        blocks += [{"type": "sectional", "group": group, "parts": sorted(parts)} for group, parts in sorted(by_group.items())]
        for block in blocks:
            for start, end in _phrases(score, block["parts"], passage.first, passage.last):
                candidates.append({**block, "measure_range": _range(start, end), **common})
                if lines or len(by_group) > 1:
                    joined_ranges.add(_range(start, end))

    tutti_minutes = min(total, max(MIN_BLOCK_MINUTES, round(total * tutti_share)))
    remaining = total - tutti_minutes
    capacity = remaining // MIN_BLOCK_MINUTES
    kept, dropped = candidates[:capacity], candidates[capacity:]
    if kept:
        _allocate(kept, remaining)
    else:
        tutti_minutes = total

    worked = list(dict.fromkeys(block["measure_range"] for block in kept))
    joined = _merged([measure_range for measure_range in worked if measure_range in joined_ranges] or worked)
    tutti = _tutti(all_parts, joined, tutti_minutes,
                   sorted({code for block in kept for code in block["findings"]}))
    segments = [{key: value for key, value in block.items() if key != "priority"} for block in kept] + [tutti]
    return {
        "total_minutes": total,
        "planned_minutes": sum(block["minutes"] for block in segments),
        "segments": segments,
        "omitted": [{"type": block["type"], "group": block["group"], "parts": block["parts"],
                     "measure_range": block["measure_range"], "reason": "time"} for block in dropped],
    }
