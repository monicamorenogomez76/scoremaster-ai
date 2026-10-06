from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, delete, false, func, select, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.application.rehearsals import (BlockReview, Rehearsal, RehearsalBlock, RehearsalDraft, UnknownConcert,
                                            UnknownWork)
from backend.infrastructure.analysis_repository import Base
from backend.infrastructure.concert_repository import StoredConcert, work_titles


class StoredRehearsal(Base):
    __tablename__ = 'rehearsals'
    __table_args__ = (Index('ix_rehearsals_user_id', 'user_id', 'scheduled_on'), Index('ix_rehearsals_concert_id', 'concert_id'))
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    scheduled_on: Mapped[date] = mapped_column(Date, nullable=False)
    starts_at: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    place: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    objectives: Mapped[str] = mapped_column(Text, nullable=False, server_default='')
    work_ids: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    blocks: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    concert_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey('concerts.id', ondelete='SET NULL'),
                                                       nullable=True)
    fixed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    phase: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str] = mapped_column(Text, nullable=False, server_default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _review(review: Optional[BlockReview]) -> Optional[dict]:
    return None if review is None else {"status": review.status, "note": review.note}


def _values(draft: RehearsalDraft) -> dict:
    return dict(scheduled_on=draft.date, starts_at=draft.time, duration_minutes=draft.duration_minutes,
                place=draft.place, objectives=draft.objectives, work_ids=[str(work) for work in draft.work_ids],
                concert_id=draft.concert_id, fixed=draft.fixed, phase=draft.phase,
                blocks=[{"title": block.title, "minutes": block.minutes, "objective": block.objective,
                         "work_id": str(block.work_id) if block.work_id else None, "measures": block.measures,
                         "sections": list(block.sections), "group": block.group, "review": _review(block.review)}
                        for block in draft.blocks])


class PostgresRehearsalRepository:
    """Every query is scoped to the owner. Works deleted after saving are dropped from the rehearsal
    and from its blocks when it is read; the blocks themselves are kept."""

    def __init__(self, engine: Engine):
        self.engine = engine

    _titles = staticmethod(work_titles)

    def _rehearsal(self, session: Session, row: StoredRehearsal) -> Rehearsal:
        titles = self._titles(session, row.user_id, [UUID(work) for work in row.work_ids])
        works = tuple((UUID(work), titles[UUID(work)]) for work in row.work_ids if UUID(work) in titles)
        blocks = tuple(RehearsalBlock(item["title"], item["minutes"], item.get("objective", ""),
                                      UUID(item["work_id"]) if item.get("work_id") and UUID(item["work_id"]) in titles else None,
                                      item.get("measures", ""), tuple(item.get("sections", ())), item.get("group", "other"),
                                      BlockReview(item["review"]["status"], item["review"].get("note", "")) if item.get("review") else None)
                       for item in row.blocks)
        draft = RehearsalDraft(row.scheduled_on, row.starts_at, row.duration_minutes, row.place, row.objectives,
                               tuple(work for work, _ in works), blocks, row.concert_id, row.fixed, row.phase)
        return Rehearsal(row.id, draft, works, row.reviewed_at, row.review_notes)

    def _check_works(self, session: Session, user_id: UUID, draft: RehearsalDraft) -> None:
        if len(self._titles(session, user_id, set(draft.work_ids))) != len(set(draft.work_ids)):
            raise UnknownWork("La obra no existe.")
        if draft.concert_id is not None:
            concert = session.get(StoredConcert, draft.concert_id)
            if concert is None or concert.user_id != user_id:
                raise UnknownConcert("El concierto no existe.")

    def list_rehearsals(self, user_id: UUID, concert_id: Optional[UUID] = None) -> list[Rehearsal]:
        with Session(self.engine) as session:
            query = select(StoredRehearsal).where(StoredRehearsal.user_id == user_id)
            if concert_id is not None:
                query = query.where(StoredRehearsal.concert_id == concert_id)
            rows = session.scalars(query.order_by(StoredRehearsal.scheduled_on, StoredRehearsal.starts_at.nulls_first(),
                                             StoredRehearsal.created_at)).all()
            return [self._rehearsal(session, row) for row in rows]

    def get_rehearsal(self, user_id: UUID, rehearsal_id: UUID) -> Optional[Rehearsal]:
        with Session(self.engine) as session:
            row = session.get(StoredRehearsal, rehearsal_id)
            return self._rehearsal(session, row) if row and row.user_id == user_id else None

    def create_rehearsal(self, user_id: UUID, draft: RehearsalDraft) -> Rehearsal:
        with Session(self.engine) as session, session.begin():
            self._check_works(session, user_id, draft)
            row = StoredRehearsal(id=uuid4(), user_id=user_id, **_values(draft))
            session.add(row)
            session.flush()
            return self._rehearsal(session, row)

    def update_rehearsal(self, user_id: UUID, rehearsal_id: UUID, draft: RehearsalDraft) -> Optional[Rehearsal]:
        with Session(self.engine) as session, session.begin():
            row = session.get(StoredRehearsal, rehearsal_id)
            if row is None or row.user_id != user_id:
                return None
            self._check_works(session, user_id, draft)
            for key, value in _values(draft).items():
                setattr(row, key, value)
            row.updated_at = func.now()
            session.flush()
            return self._rehearsal(session, row)

    def delete_rehearsal(self, user_id: UUID, rehearsal_id: UUID) -> bool:
        with Session(self.engine) as session, session.begin():
            deleted = session.execute(delete(StoredRehearsal).where(StoredRehearsal.id == rehearsal_id,
                                                                    StoredRehearsal.user_id == user_id))
            return deleted.rowcount > 0

    def review_rehearsal(self, user_id: UUID, rehearsal_id: UUID, notes: str,
                         reviews: tuple[BlockReview, ...]) -> Optional[Rehearsal]:
        """One review per block, in agenda order; the agenda itself does not change."""
        with Session(self.engine) as session, session.begin():
            row = session.get(StoredRehearsal, rehearsal_id)
            if row is None or row.user_id != user_id:
                return None
            if len(reviews) != len(row.blocks):
                raise ValueError("Una revisión por bloque.")
            row.blocks = [{**block, "review": _review(review)} for block, review in zip(row.blocks, reviews)]
            row.review_notes = notes
            row.reviewed_at = datetime.now(timezone.utc)
            session.flush()
            return self._rehearsal(session, row)
