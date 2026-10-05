"""Saved rehearsals of each user: records and repository port (no database code).

A rehearsal can work on several works; each block of its agenda may name one of them.
"""
from dataclasses import dataclass
from datetime import date
from typing import Optional, Protocol
from uuid import UUID


class UnknownWork(ValueError):
    """A work that does not exist or belongs to another user."""


@dataclass(frozen=True)
class RehearsalBlock:
    title: str
    minutes: int
    objective: str = ""
    work_id: Optional[UUID] = None
    measures: str = ""
    sections: tuple[str, ...] = ()


@dataclass(frozen=True)
class RehearsalDraft:
    date: date
    time: Optional[str]
    duration_minutes: int
    place: Optional[str]
    objectives: str
    work_ids: tuple[UUID, ...]
    blocks: tuple[RehearsalBlock, ...]


@dataclass(frozen=True)
class Rehearsal:
    id: UUID
    draft: RehearsalDraft
    # (id, title) of the works that still exist, in the rehearsal's order.
    works: tuple[tuple[UUID, str], ...]


class RehearsalRepository(Protocol):
    def list_rehearsals(self, user_id: UUID) -> list[Rehearsal]: ...
    def get_rehearsal(self, user_id: UUID, rehearsal_id: UUID) -> Optional[Rehearsal]: ...
    def create_rehearsal(self, user_id: UUID, draft: RehearsalDraft) -> Rehearsal: ...
    def update_rehearsal(self, user_id: UUID, rehearsal_id: UUID, draft: RehearsalDraft) -> Optional[Rehearsal]: ...
    def delete_rehearsal(self, user_id: UUID, rehearsal_id: UUID) -> bool: ...
