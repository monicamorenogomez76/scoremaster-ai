"""Concerts of each user: date, programme of works in concert order and the weekly pattern of the
rehearsals that prepare it (author's decisions, 2026-10-06). Records and repository port only."""
from dataclasses import dataclass
from datetime import date
from typing import Optional, Protocol
from uuid import UUID


@dataclass(frozen=True)
class RehearsalPattern:
    # 0 = Monday … 6 = Sunday.
    weekdays: tuple[int, ...]
    time: str
    duration_minutes: int
    start_date: date


@dataclass(frozen=True)
class ConcertDraft:
    title: str
    date: date
    time: Optional[str]
    place: Optional[str]
    notes: str
    work_ids: tuple[UUID, ...]
    schedule: Optional[RehearsalPattern] = None
    # The band that plays it, one of the director's.
    band_id: Optional[UUID] = None


@dataclass(frozen=True)
class Concert:
    id: UUID
    draft: ConcertDraft
    # (id, title) of the programme's works that still exist, in concert order.
    works: tuple[tuple[UUID, str], ...]
    band: Optional[tuple[UUID, str]] = None


class ConcertRepository(Protocol):
    def list_concerts(self, user_id: UUID) -> list[Concert]: ...
    def get_concert(self, user_id: UUID, concert_id: UUID) -> Optional[Concert]: ...
    def create_concert(self, user_id: UUID, draft: ConcertDraft) -> Concert: ...
    def update_concert(self, user_id: UUID, concert_id: UUID, draft: ConcertDraft) -> Optional[Concert]: ...
    def delete_concert(self, user_id: UUID, concert_id: UUID) -> bool: ...
