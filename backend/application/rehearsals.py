"""Saved rehearsals of each user: records and repository port (no database code).

A rehearsal can work on several works; each block of its agenda may name one of them. It may belong
to a concert, and after it the director reviews each block (author's decisions, 2026-10-06).
"""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Protocol
from uuid import UUID


# Type of a block: it colours the agenda calendar like the rehearsal plan (warm-up, common line,
# sectional of each subsection, tutti or other).
BLOCK_GROUPS = ("warmup", "common", "tutti", "flutes", "double_reeds", "clarinets", "saxophones", "high_brass",
                "low_voices", "percussion", "strings_rhythm", "other")


# How a block went, according to the director: it changes the priority of its passage afterwards.
REVIEW_STATUSES = ("resolved", "improve", "pending", "not_done")
# Phase of a rehearsal in the series that prepares a concert.
PHASES = ("reading", "passages", "integration", "general")


class UnknownWork(ValueError):
    """A work that does not exist or belongs to another user."""


class UnknownConcert(ValueError):
    """A concert that does not exist or belongs to another user."""


@dataclass(frozen=True)
class BlockReview:
    status: str
    note: str = ""


@dataclass(frozen=True)
class RehearsalBlock:
    title: str
    minutes: int
    objective: str = ""
    work_id: Optional[UUID] = None
    measures: str = ""
    sections: tuple[str, ...] = ()
    group: str = "other"
    review: Optional[BlockReview] = None
    # Score parts the block rehearses; empty for the whole band.
    parts: tuple[str, ...] = ()


@dataclass(frozen=True)
class RehearsalDraft:
    date: date
    time: Optional[str]
    duration_minutes: int
    place: Optional[str]
    objectives: str
    work_ids: tuple[UUID, ...]
    blocks: tuple[RehearsalBlock, ...]
    concert_id: Optional[UUID] = None
    # A fixed rehearsal is never replanned.
    fixed: bool = False
    phase: Optional[str] = None


@dataclass(frozen=True)
class Rehearsal:
    id: UUID
    draft: RehearsalDraft
    # (id, title) of the works that still exist, in the rehearsal's order.
    works: tuple[tuple[UUID, str], ...]
    reviewed_at: Optional[datetime] = None
    review_notes: str = ""


class RehearsalRepository(Protocol):
    def list_rehearsals(self, user_id: UUID, concert_id: Optional[UUID] = None) -> list[Rehearsal]: ...
    def get_rehearsal(self, user_id: UUID, rehearsal_id: UUID) -> Optional[Rehearsal]: ...
    def create_rehearsal(self, user_id: UUID, draft: RehearsalDraft) -> Rehearsal: ...
    def update_rehearsal(self, user_id: UUID, rehearsal_id: UUID, draft: RehearsalDraft) -> Optional[Rehearsal]: ...
    def delete_rehearsal(self, user_id: UUID, rehearsal_id: UUID) -> bool: ...
    def review_rehearsal(self, user_id: UUID, rehearsal_id: UUID, notes: str,
                         reviews: tuple[BlockReview, ...]) -> Optional[Rehearsal]: ...
    def save_concert_plan(self, user_id: UUID, concert_id: UUID, items: list[tuple[Optional[UUID], RehearsalDraft]],
                          today: date) -> list[Rehearsal]: ...


def replannable(rehearsal: Rehearsal, today: date) -> bool:
    """Only rehearsals still to come, not reviewed and not fixed by the director are replanned."""
    return rehearsal.draft.date >= today and rehearsal.reviewed_at is None and not rehearsal.draft.fixed


class NotReplannable(ValueError):
    """A rehearsal already held, reviewed, fixed or of another concert cannot be replaced."""
