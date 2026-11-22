"""The doubts of the PDF reader (2026-11-22): the measures it took from a part because the score's staff read otherwise.
Stored with the work as {"measures": [{"part", "position", "measure"}], "reviewed": [part]}: the position counts the
measures from 1, as the reader does; the measure is the number the work keeps, the one the PDF prints."""
from __future__ import annotations

import xml.etree.ElementTree as ET

# The doubts kept for a work, at most: the reader sends 5000 at most.
MAX_DOUBTS = 5000


def printed(musicxml: bytes, doubts: list) -> dict:
    """The doubts the reader sent with the number the work gives each measure; those that are not a measure of the work
    are left out."""
    root = ET.fromstring(musicxml)
    first = root.find("part")
    numbers = [measure.get("number") or str(index) for index, measure in enumerate(first.iter("measure"), 1)] if first is not None else []
    measures = []
    for doubt in doubts[:MAX_DOUBTS]:
        if not isinstance(doubt, dict):
            continue
        part, position = doubt.get("part"), doubt.get("measure")
        if (isinstance(part, str) and part and isinstance(position, int) and not isinstance(position, bool)
                and 1 <= position <= len(numbers)):
            measures.append({"part": part[:200], "position": position, "measure": numbers[position - 1]})
    return {"measures": measures, "reviewed": []}


def grouped(stored: dict | None) -> list[dict]:
    """The doubts by part, in the order of the work, each part's consecutive measures in one passage («81-83»)."""
    if not stored:
        return []
    by_part: dict[str, list[dict]] = {}
    for doubt in stored.get("measures", []):
        by_part.setdefault(doubt["part"], []).append(doubt)
    done = set(stored.get("reviewed", []))
    found = []
    for part, doubts in by_part.items():
        passages: list[list[dict]] = []
        for doubt in sorted(doubts, key=lambda item: item["position"]):
            if passages and doubt["position"] == passages[-1][-1]["position"] + 1:
                passages[-1].append(doubt)
            else:
                passages.append([doubt])
        found.append({"part": part, "measures": len(doubts), "reviewed": part in done,
                      "passages": [run[0]["measure"] if len(run) == 1 else f"{run[0]['measure']}-{run[-1]['measure']}"
                                   for run in passages]})
    return found


def reviewed(stored: dict | None, part: str, value: bool) -> dict | None:
    """The doubts with the part marked reviewed or not; None when the part has no doubts."""
    if not stored or not any(doubt["part"] == part for doubt in stored.get("measures", [])):
        return None
    others = [name for name in stored.get("reviewed", []) if name != part]
    return {**stored, "reviewed": others + [part] if value else others}
