from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text, delete, func, select, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.application.concerts import Concert, ConcertDraft, RehearsalPattern
from backend.application.bands import UnknownBand
from backend.application.rehearsals import UnknownWork
from backend.infrastructure.analysis_repository import Base
from backend.infrastructure.band_repository import StoredEnsemble
from backend.infrastructure.library_repository import StoredWork


class StoredConcert(Base):
    __tablename__ = 'concerts'
    __table_args__ = (Index('ix_concerts_user_id', 'user_id', 'scheduled_on'),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    scheduled_on: Mapped[date] = mapped_column(Date, nullable=False)
    starts_at: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    place: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default='')
    work_ids: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    schedule: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    band_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey('ensembles.id', ondelete='SET NULL'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def work_titles(session: Session, user_id: UUID, work_ids) -> dict[UUID, str]:
    """Titles of the user's works among the given ids; another user's works are not found."""
    if not work_ids:
        return {}
    rows = session.execute(select(StoredWork.id, StoredWork.title)
                           .where(StoredWork.user_id == user_id, StoredWork.id.in_(list(work_ids))))
    return {row.id: row.title for row in rows}


def _values(draft: ConcertDraft) -> dict:
    pattern = draft.schedule
    return dict(title=draft.title, scheduled_on=draft.date, starts_at=draft.time, place=draft.place, notes=draft.notes,
                work_ids=[str(work) for work in draft.work_ids],
                schedule=None if pattern is None else {"weekdays": list(pattern.weekdays), "time": pattern.time,
                                                       "duration_minutes": pattern.duration_minutes,
                                                       "start_date": pattern.start_date.isoformat()},
                band_id=draft.band_id)


class PostgresConcertRepository:
    """Every query is scoped to the owner; works deleted later are dropped from the programme."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def _concert(self, session: Session, row: StoredConcert) -> Concert:
        titles = work_titles(session, row.user_id, [UUID(work) for work in row.work_ids])
        works = tuple((UUID(work), titles[UUID(work)]) for work in row.work_ids if UUID(work) in titles)
        pattern = row.schedule and RehearsalPattern(tuple(row.schedule["weekdays"]), row.schedule["time"],
                                                    row.schedule["duration_minutes"],
                                                    date.fromisoformat(row.schedule["start_date"]))
        draft = ConcertDraft(row.title, row.scheduled_on, row.starts_at, row.place, row.notes,
                             tuple(work for work, _ in works), pattern or None, row.band_id)
        band = session.get(StoredEnsemble, row.band_id) if row.band_id else None
        return Concert(row.id, draft, works, (band.id, band.name) if band else None)

    def _check_works(self, session: Session, user_id: UUID, draft: ConcertDraft) -> None:
        if len(work_titles(session, user_id, set(draft.work_ids))) != len(set(draft.work_ids)):
            raise UnknownWork("La obra no existe.")
        if draft.band_id is not None:
            band = session.get(StoredEnsemble, draft.band_id)
            if band is None or band.user_id != user_id:
                raise UnknownBand("La banda no existe.")

    def list_concerts(self, user_id: UUID) -> list[Concert]:
        with Session(self.engine) as session:
            rows = session.scalars(select(StoredConcert).where(StoredConcert.user_id == user_id)
                                   .order_by(StoredConcert.scheduled_on, StoredConcert.created_at)).all()
            return [self._concert(session, row) for row in rows]

    def get_concert(self, user_id: UUID, concert_id: UUID) -> Optional[Concert]:
        with Session(self.engine) as session:
            row = session.get(StoredConcert, concert_id)
            return self._concert(session, row) if row and row.user_id == user_id else None

    def create_concert(self, user_id: UUID, draft: ConcertDraft) -> Concert:
        with Session(self.engine) as session, session.begin():
            self._check_works(session, user_id, draft)
            row = StoredConcert(id=uuid4(), user_id=user_id, **_values(draft))
            session.add(row)
            session.flush()
            return self._concert(session, row)

    def update_concert(self, user_id: UUID, concert_id: UUID, draft: ConcertDraft) -> Optional[Concert]:
        with Session(self.engine) as session, session.begin():
            row = session.get(StoredConcert, concert_id)
            if row is None or row.user_id != user_id:
                return None
            self._check_works(session, user_id, draft)
            for key, value in _values(draft).items():
                setattr(row, key, value)
            row.updated_at = func.now()
            session.flush()
            return self._concert(session, row)

    def delete_concert(self, user_id: UUID, concert_id: UUID) -> bool:
        """Its rehearsals are kept without a concert (ON DELETE SET NULL)."""
        with Session(self.engine) as session, session.begin():
            deleted = session.execute(delete(StoredConcert).where(StoredConcert.id == concert_id,
                                                                  StoredConcert.user_id == user_id))
            return deleted.rowcount > 0
