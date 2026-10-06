from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, delete, false, func, select, text, update
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.application.bands import DEFAULT_BAND_NAME, Band, BandDraft
from backend.infrastructure.analysis_repository import Base


class StoredEnsemble(Base):
    __tablename__ = 'ensembles'
    __table_args__ = (Index('ix_ensembles_user_id', 'user_id'),
                      Index('uq_ensembles_active', 'user_id', unique=True, postgresql_where=text('is_active')))
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    locality: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    place: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    rehearsal_weekdays: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    rehearsal_time: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    rehearsal_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    profile: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    section_levels: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _values(draft: BandDraft) -> dict:
    return dict(name=draft.name, locality=draft.locality, place=draft.place, rehearsal_weekdays=list(draft.rehearsal_weekdays),
                rehearsal_time=draft.rehearsal_time, rehearsal_minutes=draft.rehearsal_minutes, profile=dict(draft.profile),
                section_levels=dict(draft.section_levels))


def _band(row: StoredEnsemble) -> Band:
    return Band(row.id, BandDraft(row.name, row.locality, row.place, tuple(row.rehearsal_weekdays), row.rehearsal_time,
                                  row.rehearsal_minutes, dict(row.profile), dict(row.section_levels)), row.is_active)


def active_band(session: Session, user_id: UUID) -> Optional[StoredEnsemble]:
    return session.scalars(select(StoredEnsemble).where(StoredEnsemble.user_id == user_id, StoredEnsemble.is_active)).first()


def update_active_profile(session: Session, user_id: UUID, changes: dict) -> dict:
    """Merges the changes into the active band's template, creating «Mi banda» if there is none."""
    row = active_band(session, user_id)
    if row is None:
        row = StoredEnsemble(id=uuid4(), user_id=user_id, name=DEFAULT_BAND_NAME, profile=dict(changes), is_active=True)
        session.add(row)
    else:
        row.profile = {**row.profile, **changes}
        row.updated_at = func.now()
    session.flush()
    return dict(row.profile)


class PostgresBandRepository:
    """Every query is scoped to the owner; at most one band is active (partial unique index)."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def _owned(self, session: Session, user_id: UUID, band_id: UUID) -> Optional[StoredEnsemble]:
        row = session.get(StoredEnsemble, band_id)
        return row if row is not None and row.user_id == user_id else None

    def list_bands(self, user_id: UUID) -> list[Band]:
        with Session(self.engine) as session:
            rows = session.scalars(select(StoredEnsemble).where(StoredEnsemble.user_id == user_id)
                                   .order_by(StoredEnsemble.created_at, StoredEnsemble.name)).all()
            return [_band(row) for row in rows]

    def get_band(self, user_id: UUID, band_id: UUID) -> Optional[Band]:
        with Session(self.engine) as session:
            row = self._owned(session, user_id, band_id)
            return _band(row) if row else None

    def create_band(self, user_id: UUID, draft: BandDraft) -> Band:
        """The first band of a director is the active one."""
        with Session(self.engine) as session, session.begin():
            row = StoredEnsemble(id=uuid4(), user_id=user_id, is_active=active_band(session, user_id) is None, **_values(draft))
            session.add(row)
            session.flush()
            return _band(row)

    def update_band(self, user_id: UUID, band_id: UUID, draft: BandDraft) -> Optional[Band]:
        with Session(self.engine) as session, session.begin():
            row = self._owned(session, user_id, band_id)
            if row is None:
                return None
            for key, value in _values(draft).items():
                setattr(row, key, value)
            row.updated_at = func.now()
            session.flush()
            return _band(row)

    def delete_band(self, user_id: UUID, band_id: UUID) -> bool:
        """Deleting the active band activates the oldest remaining one."""
        with Session(self.engine) as session, session.begin():
            row = self._owned(session, user_id, band_id)
            if row is None:
                return False
            was_active = row.is_active
            session.execute(delete(StoredEnsemble).where(StoredEnsemble.id == band_id))
            if was_active:
                oldest = session.scalars(select(StoredEnsemble).where(StoredEnsemble.user_id == user_id)
                                         .order_by(StoredEnsemble.created_at).limit(1)).first()
                if oldest is not None:
                    oldest.is_active = True
            return True

    def activate_band(self, user_id: UUID, band_id: UUID) -> Optional[Band]:
        with Session(self.engine) as session, session.begin():
            row = self._owned(session, user_id, band_id)
            if row is None:
                return None
            session.execute(update(StoredEnsemble).where(StoredEnsemble.user_id == user_id, StoredEnsemble.id != band_id)
                            .values(is_active=False))
            session.flush()
            row.is_active = True
            session.flush()
            return _band(row)
