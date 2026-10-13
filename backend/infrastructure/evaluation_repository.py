from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
                        delete, func, select)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID, insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.application.evaluations import Campaign, CampaignLocked, Invitation, Passage, Rating
from backend.infrastructure.analysis_repository import Base
from backend.infrastructure.library_repository import StoredWork

ID = PGUUID(as_uuid=True)


class StoredCampaign(Base):
    __tablename__ = 'evaluation_campaigns'
    __table_args__ = (Index('ix_evaluation_campaigns_owner_id', 'owner_id'),
                      CheckConstraint("status in ('draft', 'open', 'closed')", name='ck_evaluation_campaigns_status'))
    id: Mapped[UUID] = mapped_column(ID, primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(ID, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False, server_default='')
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default='draft')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StoredPassage(Base):
    __tablename__ = 'evaluation_passages'
    __table_args__ = (Index('ix_evaluation_passages_campaign_id', 'campaign_id'),)
    id: Mapped[UUID] = mapped_column(ID, primary_key=True)
    campaign_id: Mapped[UUID] = mapped_column(ID, ForeignKey('evaluation_campaigns.id', ondelete='CASCADE'), nullable=False)
    work_id: Mapped[UUID] = mapped_column(ID, ForeignKey('works.id', ondelete='CASCADE'), nullable=False)
    work_title: Mapped[str] = mapped_column(String(300), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    parts: Mapped[list] = mapped_column(JSONB, nullable=False)
    measure_range: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)


class StoredInvitation(Base):
    __tablename__ = 'evaluation_invitations'
    __table_args__ = (UniqueConstraint('campaign_id', 'email', name='uq_evaluation_invitations_email'),
                      Index('ix_evaluation_invitations_email', 'email'))
    id: Mapped[UUID] = mapped_column(ID, primary_key=True)
    campaign_id: Mapped[UUID] = mapped_column(ID, ForeignKey('evaluation_campaigns.id', ondelete='CASCADE'), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    experience_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    main_instrument: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)


class StoredRating(Base):
    __tablename__ = 'evaluation_ratings'
    __table_args__ = (UniqueConstraint('passage_id', 'invitation_id', name='uq_evaluation_ratings_once'),
                      CheckConstraint('difficulty between 1 and 6', name='ck_evaluation_ratings_difficulty'),
                      CheckConstraint('priority between 1 and 5', name='ck_evaluation_ratings_priority'))
    id: Mapped[UUID] = mapped_column(ID, primary_key=True)
    passage_id: Mapped[UUID] = mapped_column(ID, ForeignKey('evaluation_passages.id', ondelete='CASCADE'), nullable=False)
    invitation_id: Mapped[UUID] = mapped_column(ID, ForeignKey('evaluation_invitations.id', ondelete='CASCADE'), nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    critical: Mapped[bool] = mapped_column(Boolean, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False, server_default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StoredLlmReview(Base):
    __tablename__ = 'evaluation_llm_reviews'
    __table_args__ = (UniqueConstraint('passage_id', 'provider', 'model', 'prompt_version', 'features_version',
                                       name='uq_evaluation_llm_reviews_version'),
                      CheckConstraint('grade between 1 and 6', name='ck_evaluation_llm_reviews_grade'),
                      CheckConstraint('confidence between 0 and 1', name='ck_evaluation_llm_reviews_confidence'),
                      Index('ix_evaluation_llm_reviews_passage_id', 'passage_id'))
    id: Mapped[UUID] = mapped_column(ID, primary_key=True)
    passage_id: Mapped[UUID] = mapped_column(ID, ForeignKey('evaluation_passages.id', ondelete='CASCADE'), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(60), nullable=False)
    features_version: Mapped[str] = mapped_column(String(60), nullable=False)
    grade: Mapped[int] = mapped_column(Integer, nullable=False)
    critical: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    main_factors: Mapped[list] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    features: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _review(row: StoredLlmReview) -> dict:
    return {"passage_id": str(row.passage_id), "provider": row.provider, "model": row.model,
            "prompt_version": row.prompt_version, "features_version": row.features_version, "grade": row.grade,
            "critical": row.critical, "confidence": row.confidence, "main_factors": list(row.main_factors),
            "reason": row.reason, "created_at": row.created_at.isoformat() if row.created_at else None}


def _email(value: str) -> str:
    return value.strip().lower()


def _passage(row: StoredPassage) -> Passage:
    return Passage(row.id, row.work_id, row.work_title, tuple(row.parts), row.measure_range, row.label, dict(row.snapshot),
                   row.position)


class PostgresEvaluationRepository:
    """The owner sees everything; an evaluator only campaigns that invite their email and are not drafts."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def _campaign(self, session: Session, row: StoredCampaign, evaluator: Optional[StoredInvitation] = None) -> Campaign:
        passages = tuple(_passage(item) for item in session.scalars(
            select(StoredPassage).where(StoredPassage.campaign_id == row.id).order_by(StoredPassage.position)))
        counts = dict(session.execute(select(StoredRating.invitation_id, func.count()).join(StoredInvitation)
                                      .where(StoredInvitation.campaign_id == row.id).group_by(StoredRating.invitation_id)).all())
        invitations = tuple(Invitation(item.id, item.email, item.experience_level, item.main_instrument, counts.get(item.id, 0))
                            for item in session.scalars(select(StoredInvitation).where(StoredInvitation.campaign_id == row.id)
                                                        .order_by(StoredInvitation.email)))
        own, ratings = None, {}
        if evaluator is not None:
            own = next(item for item in invitations if item.id == evaluator.id)
            ratings = {item.passage_id: Rating(item.difficulty, item.critical, item.priority, item.comment)
                       for item in session.scalars(select(StoredRating).where(StoredRating.invitation_id == evaluator.id))}
        return Campaign(row.id, row.owner_id, row.title, row.instructions, row.status, row.created_at, passages,
                        invitations, own, ratings)

    def _owned(self, session: Session, owner_id: UUID, campaign_id: UUID) -> Optional[StoredCampaign]:
        row = session.get(StoredCampaign, campaign_id)
        return row if row is not None and row.owner_id == owner_id else None

    def _invitation(self, session: Session, email: str, campaign_id: UUID):
        """The campaign and the invitation of this email, never for a draft."""
        row = session.get(StoredCampaign, campaign_id)
        if row is None or row.status == 'draft':
            return None, None
        invitation = session.scalars(select(StoredInvitation).where(StoredInvitation.campaign_id == campaign_id,
                                                                    StoredInvitation.email == _email(email))).first()
        return (row, invitation) if invitation is not None else (None, None)

    def create_campaign(self, owner_id: UUID, title: str, instructions: str, passages: list[dict]) -> Campaign:
        with Session(self.engine) as session, session.begin():
            row = StoredCampaign(id=uuid4(), owner_id=owner_id, title=title, instructions=instructions, status='draft')
            session.add(row)
            session.flush()
            for position, item in enumerate(passages):
                session.add(StoredPassage(id=uuid4(), campaign_id=row.id, work_id=UUID(str(item["work_id"])),
                                          work_title=item["work_title"][:300], position=position, parts=list(item["parts"]),
                                          measure_range=item["measure_range"], label=item["label"][:300],
                                          snapshot=item["snapshot"]))
            session.flush()
            return self._campaign(session, row)

    def owned(self, owner_id: UUID) -> list[Campaign]:
        with Session(self.engine) as session:
            rows = session.scalars(select(StoredCampaign).where(StoredCampaign.owner_id == owner_id)
                                   .order_by(StoredCampaign.created_at.desc())).all()
            return [self._campaign(session, row) for row in rows]

    def invited(self, email: str) -> list[Campaign]:
        with Session(self.engine) as session:
            rows = session.execute(select(StoredCampaign, StoredInvitation).join(StoredInvitation)
                                   .where(StoredInvitation.email == _email(email), StoredCampaign.status != 'draft')
                                   .order_by(StoredCampaign.created_at.desc())).all()
            return [self._campaign(session, campaign, invitation) for campaign, invitation in rows]

    def for_owner(self, owner_id: UUID, campaign_id: UUID) -> Optional[Campaign]:
        with Session(self.engine) as session:
            row = self._owned(session, owner_id, campaign_id)
            return self._campaign(session, row) if row else None

    def for_evaluator(self, email: str, campaign_id: UUID) -> Optional[Campaign]:
        with Session(self.engine) as session:
            row, invitation = self._invitation(session, email, campaign_id)
            return self._campaign(session, row, invitation) if row else None

    def delete_passage(self, owner_id: UUID, campaign_id: UUID, passage_id: UUID) -> bool:
        with Session(self.engine) as session, session.begin():
            row = self._owned(session, owner_id, campaign_id)
            if row is None:
                return False
            if row.status != 'draft':
                raise CampaignLocked("Los pasajes solo se cambian en borrador.")
            deleted = session.execute(delete(StoredPassage).where(StoredPassage.id == passage_id,
                                                                  StoredPassage.campaign_id == campaign_id))
            return deleted.rowcount > 0

    def set_invitations(self, owner_id: UUID, campaign_id: UUID, emails: list[str]) -> Optional[Campaign]:
        """The invited emails; an email removed loses its ratings, the others keep them."""
        wanted = list(dict.fromkeys(_email(item) for item in emails if item.strip()))
        with Session(self.engine) as session, session.begin():
            row = self._owned(session, owner_id, campaign_id)
            if row is None:
                return None
            session.execute(delete(StoredInvitation).where(StoredInvitation.campaign_id == campaign_id,
                                                           StoredInvitation.email.notin_(wanted)))
            for email in wanted:
                session.execute(insert(StoredInvitation).values(id=uuid4(), campaign_id=campaign_id, email=email)
                                .on_conflict_do_nothing(constraint='uq_evaluation_invitations_email'))
            session.flush()
            return self._campaign(session, row)

    def set_status(self, owner_id: UUID, campaign_id: UUID, status: str) -> Optional[Campaign]:
        with Session(self.engine) as session, session.begin():
            row = self._owned(session, owner_id, campaign_id)
            if row is None:
                return None
            row.status = status
            row.updated_at = func.now()
            session.flush()
            return self._campaign(session, row)

    def set_profile(self, email: str, campaign_id: UUID, level: str, instrument: str) -> bool:
        with Session(self.engine) as session, session.begin():
            _, invitation = self._invitation(session, email, campaign_id)
            if invitation is None:
                return False
            invitation.experience_level, invitation.main_instrument = level, instrument
            return True

    def rate(self, email: str, campaign_id: UUID, passage_id: UUID, rating: Rating) -> bool:
        with Session(self.engine) as session, session.begin():
            row, invitation = self._invitation(session, email, campaign_id)
            passage = session.get(StoredPassage, passage_id)
            if row is None or passage is None or passage.campaign_id != campaign_id:
                return False
            if row.status != 'open':
                raise CampaignLocked("La campaña está cerrada.")
            values = dict(difficulty=rating.difficulty, critical=rating.critical, priority=rating.priority, comment=rating.comment)
            session.execute(insert(StoredRating).values(id=uuid4(), passage_id=passage_id, invitation_id=invitation.id, **values)
                            .on_conflict_do_update(constraint='uq_evaluation_ratings_once',
                                                   set_={**values, 'updated_at': func.now()}))
            return True

    def evaluator_work_file(self, email: str, campaign_id: UUID, work_id: UUID) -> Optional[tuple[bytes, str]]:
        """The whole work of a passage of the campaign (author's decision: the musician may open it)."""
        with Session(self.engine) as session:
            row, _ = self._invitation(session, email, campaign_id)
            if row is None or session.scalars(select(StoredPassage.id).where(
                    StoredPassage.campaign_id == campaign_id, StoredPassage.work_id == work_id).limit(1)).first() is None:
                return None
            work = session.get(StoredWork, work_id)
            return (bytes(work.source), work.file_name) if work else None

    def llm_reviews(self, owner_id: UUID, campaign_id: UUID) -> Optional[list[dict]]:
        """Every independent review of the campaign's passages, newest first; None if not the owner's."""
        with Session(self.engine) as session:
            if self._owned(session, owner_id, campaign_id) is None:
                return None
            rows = session.scalars(select(StoredLlmReview).join(StoredPassage)
                                   .where(StoredPassage.campaign_id == campaign_id)
                                   .order_by(StoredLlmReview.created_at.desc())).all()
            return [_review(row) for row in rows]

    def save_llm_review(self, owner_id: UUID, campaign_id: UUID, passage_id: UUID, review: dict, features: dict) -> bool:
        """Kept once per passage and versions (the same versions replace the previous answer)."""
        with Session(self.engine) as session, session.begin():
            passage = session.get(StoredPassage, passage_id)
            if self._owned(session, owner_id, campaign_id) is None or passage is None or passage.campaign_id != campaign_id:
                return False
            values = {key: review[key] for key in ("provider", "model", "prompt_version", "features_version", "grade",
                                                   "critical", "confidence", "main_factors", "reason")}
            statement = insert(StoredLlmReview).values(id=uuid4(), passage_id=passage_id, features=features, **values)
            session.execute(statement.on_conflict_do_update(
                constraint='uq_evaluation_llm_reviews_version',
                set_={**{key: values[key] for key in ("grade", "critical", "confidence", "main_factors", "reason")},
                      "features": features, "created_at": func.now()}))
            return True

    def export(self, owner_id: UUID, campaign_id: UUID) -> Optional[dict]:
        """Passages with ScoreLint's prediction and every rating; evaluators are «Evaluador n», no email."""
        with Session(self.engine) as session:
            row = self._owned(session, owner_id, campaign_id)
            if row is None:
                return None
            campaign = self._campaign(session, row)
            names = {item.id: "Evaluador {}".format(index) for index, item in enumerate(campaign.invitations, start=1)}
            profiles = {item.id: item for item in campaign.invitations}
            by_passage = {item.id: item for item in campaign.passages}
            ratings = session.scalars(select(StoredRating).join(StoredPassage)
                                      .where(StoredPassage.campaign_id == campaign_id)
                                      .order_by(StoredPassage.position, StoredRating.created_at)).all()
            return {
                "campaign": {"id": str(row.id), "title": row.title, "status": row.status},
                "passages": [{"passage_id": str(item.id), "work_id": str(item.work_id), "work_title": item.work_title,
                              "parts": list(item.parts), "measure_range": item.measure_range, "snapshot": item.snapshot}
                             for item in campaign.passages],
                "ratings": [{"passage_id": str(item.passage_id), "work_title": by_passage[item.passage_id].work_title,
                             "measure_range": by_passage[item.passage_id].measure_range,
                             "snapshot": by_passage[item.passage_id].snapshot, "evaluator": names[item.invitation_id],
                             "experience_level": profiles[item.invitation_id].experience_level,
                             "main_instrument": profiles[item.invitation_id].main_instrument,
                             "difficulty": item.difficulty, "critical": item.critical, "priority": item.priority,
                             "comment": item.comment} for item in ratings],
                # Method B (step 22): the LLM's independent reviews with their versions.
                "llm_reviews": [_review(item) for item in session.scalars(
                    select(StoredLlmReview).join(StoredPassage).where(StoredPassage.campaign_id == campaign_id)
                    .order_by(StoredPassage.position, StoredLlmReview.created_at))],
            }
