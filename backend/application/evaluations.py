"""Evaluation campaigns (steps 16-18, author's decisions, 2026-10-07): records and repository port.

The director proposes passages of her works and invites musicians by email; each invited musician,
with an account, rates the passages without seeing ScoreLint's prediction (the passage snapshot).
Ratings belong to the invitation, so the export identifies evaluators only as «Evaluador n».
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Protocol
from uuid import UUID

STATUSES = ("draft", "open", "closed")
EXPERIENCE_LEVELS = ("estudiante", "amateur", "profesional", "docente")


class CampaignLocked(ValueError):
    """The campaign is not in the state the change needs (passages change in draft, ratings while open)."""


@dataclass(frozen=True)
class Passage:
    id: UUID
    work_id: UUID
    work_title: str
    parts: tuple[str, ...]
    measure_range: str
    label: str
    snapshot: dict
    position: int


@dataclass(frozen=True)
class Rating:
    difficulty: int
    critical: bool
    priority: int
    comment: str = ""


@dataclass(frozen=True)
class Invitation:
    id: UUID
    email: str
    experience_level: Optional[str] = None
    main_instrument: Optional[str] = None
    rated: int = 0


@dataclass(frozen=True)
class Campaign:
    id: UUID
    owner_id: UUID
    title: str
    instructions: str
    status: str
    created_at: Optional[datetime]
    passages: tuple[Passage, ...] = ()
    invitations: tuple[Invitation, ...] = ()
    # For an evaluator: their own invitation and ratings by passage id.
    own: Optional[Invitation] = None
    ratings: dict = field(default_factory=dict)


class EvaluationRepository(Protocol):
    def create_campaign(self, owner_id: UUID, title: str, instructions: str, passages: list[dict]) -> Campaign: ...
    def owned(self, owner_id: UUID) -> list[Campaign]: ...
    def invited(self, email: str) -> list[Campaign]: ...
    def for_owner(self, owner_id: UUID, campaign_id: UUID) -> Optional[Campaign]: ...
    def for_evaluator(self, email: str, campaign_id: UUID) -> Optional[Campaign]: ...
    def delete_passage(self, owner_id: UUID, campaign_id: UUID, passage_id: UUID) -> bool: ...
    def set_invitations(self, owner_id: UUID, campaign_id: UUID, emails: list[str]) -> Optional[Campaign]: ...
    def set_status(self, owner_id: UUID, campaign_id: UUID, status: str) -> Optional[Campaign]: ...
    def set_profile(self, email: str, campaign_id: UUID, level: str, instrument: str) -> bool: ...
    def rate(self, email: str, campaign_id: UUID, passage_id: UUID, rating: Rating) -> bool: ...
    def evaluator_work_file(self, email: str, campaign_id: UUID, work_id: UUID) -> Optional[tuple[bytes, str]]: ...
    def export(self, owner_id: UUID, campaign_id: UUID) -> Optional[dict]: ...
