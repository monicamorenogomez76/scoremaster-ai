"""Bands of each director (author's decisions, 2026-10-06): several fixed templates, one of them
active, each with its locality, rehearsal days, full instrumentation and a level per section.
Records and repository port only."""
from dataclasses import dataclass, field
from typing import Optional, Protocol
from uuid import UUID

# Sections that get a level: the subsections of the ensemble rehearsal.
SECTION_GROUPS = ("flutes", "double_reeds", "clarinets", "saxophones", "high_brass", "low_voices", "percussion",
                  "strings_rhythm")
DEFAULT_BAND_NAME = "Mi banda"


class UnknownBand(ValueError):
    """A band that does not exist or belongs to another user."""


@dataclass(frozen=True)
class BandDraft:
    name: str
    locality: Optional[str] = None
    place: Optional[str] = None
    # 0 = Monday … 6 = Sunday.
    rehearsal_weekdays: tuple[int, ...] = ()
    rehearsal_time: Optional[str] = None
    rehearsal_minutes: Optional[int] = None
    # Musicians per instrument (catalog id, or "percussion" for all the percussionists).
    profile: dict = field(default_factory=dict)
    # Level 1-6 per section, on the grade rubric.
    section_levels: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Band:
    id: UUID
    draft: BandDraft
    active: bool


class BandRepository(Protocol):
    def list_bands(self, user_id: UUID) -> list[Band]: ...
    def get_band(self, user_id: UUID, band_id: UUID) -> Optional[Band]: ...
    def create_band(self, user_id: UUID, draft: BandDraft) -> Band: ...
    def update_band(self, user_id: UUID, band_id: UUID, draft: BandDraft) -> Optional[Band]: ...
    def delete_band(self, user_id: UUID, band_id: UUID) -> bool: ...
    def activate_band(self, user_id: UUID, band_id: UUID) -> Optional[Band]: ...
