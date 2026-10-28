"""BandFit by instrument identity (step 09).

Decided on 2026-10-04: an instrument needs one musician per voice (Clarinet 1, 2 and 3
need three; a shared "Clarinet 1 & 2" part counts two; the staves of one wind part are its voices,
while the staves of a keyboard part are one musician),
and percussion is counted as percussionists in total, one per percussion part. Parts without a
confirmed identity (unknown, conflict or metadata-only review) wait for the user and do not count.
"""
from __future__ import annotations

from backend.domain.instrument_catalog import catalog_entries, match_instrument_name
from backend.domain.instrument_resolver import RESOLVED, resolve_part
from backend.domain.models import Score

PERCUSSION = "percussion"
PERCUSSION_LABEL_ES = "Percusionistas"


# Instruments whose player reads several staves at once.
SINGLE_PLAYER_SECTIONS = {"keyboard"}


def _voice_numbers(part, identity) -> tuple[int, ...]:
    """Voices named in the part ("Clarinet 1 & 2") or, for winds, the staves of a split part."""
    named = match_instrument_name(part.metadata.part_name or part.name).part_numbers
    staff = part.metadata.staff_number
    if named or not staff or identity.section in SINGLE_PLAYER_SECTIONS:
        return named
    return (staff,)


def compute_band_fit(score: Score, band_profile: dict[str, int]) -> dict:
    order = {identity.canonical_id: index for index, identity in enumerate(catalog_entries())}
    percussion_order = min((index for identity, index in zip(catalog_entries(), order.values())
                            if identity.section == "percussion"), default=len(order))
    groups: dict[str, dict] = {}
    unconfirmed = []
    for part in score.parts:
        resolution = resolve_part(part)
        identity = resolution.identity
        if resolution.status != RESOLVED or identity is None:
            unconfirmed.append({"part": part.name, "status": resolution.status,
                                "proposal": identity.canonical_id if identity else None,
                                "candidates": [candidate.canonical_id for candidate in resolution.candidates]})
            continue
        percussion = identity.section == "percussion"
        key = PERCUSSION if percussion else identity.canonical_id
        group = groups.setdefault(key, {
            "label_es": PERCUSSION_LABEL_ES if percussion else identity.label_es,
            "order": percussion_order if percussion else order.get(identity.canonical_id, len(order)),
            "voices": set(), "parts": set()})
        numbers = () if percussion else _voice_numbers(part, identity)
        part_key = part.metadata.part_id or part.name
        group["voices"] |= {("voice", number) for number in numbers} or {("part", part_key)}
        group["parts"].add(part.name)

    requirements, issues = [], []
    for key, group in sorted(groups.items(), key=lambda item: (item[1]["order"], item[0])):
        required = len(group["voices"])
        available = max(0, int(band_profile.get(key, 0) or 0))
        requirements.append({"key": key, "label_es": group["label_es"], "required": required,
                             "available": available, "parts": sorted(group["parts"])})
        if available < required:
            issues.append({"key": key, "label_es": group["label_es"],
                           "severity": "critical" if available == 0 else "warning",
                           "required": required, "available": available})

    total_required = sum(item["required"] for item in requirements)
    covered = sum(min(item["required"], item["available"]) for item in requirements)
    compatibility_percent = 100 if total_required == 0 else int(covered * 100 / total_required)
    status = "ok" if not issues else "critical" if compatibility_percent < 50 else "warning"
    return {"compatibility_percent": compatibility_percent, "status": status, "issues": issues,
            "requirements": requirements, "unconfirmed": sorted(unconfirmed, key=lambda item: item["part"])}
