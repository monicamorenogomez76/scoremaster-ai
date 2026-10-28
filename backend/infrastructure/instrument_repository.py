"""The instrument catalog in PostgreSQL (2026-10-28). Common rows have no owner; the names are kept as written and
normalized, and a normalized name is unique among the common ones."""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Identity, Index, Integer, String, delete, func, select, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID, insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.application.instruments import DuplicateName
from backend.infrastructure.analysis_repository import Base

FIELDS = ('section', 'family', 'variant', 'transposition', 'label_es', 'label_en', 'sound', 'rehearsal_group')


class StoredInstrument(Base):
    __tablename__ = 'instruments'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(String(20), nullable=False)
    family: Mapped[str] = mapped_column(String(40), nullable=False)
    variant: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    transposition: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    label_es: Mapped[str] = mapped_column(String(80), nullable=False)
    label_en: Mapped[str] = mapped_column(String(80), nullable=False)
    sound: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    rehearsal_group: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    owner_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'),
                                                     nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StoredInstrumentName(Base):
    __tablename__ = 'instrument_names'
    __table_args__ = (
        Index('uq_instrument_names_common', 'name_key', unique=True, postgresql_where=text('owner_id IS NULL')),
        Index('uq_instrument_names_owner', 'owner_id', 'name_key', unique=True, postgresql_where=text('owner_id IS NOT NULL')),
    )
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(String(80), ForeignKey('instruments.id', ondelete='CASCADE'), nullable=False,
                                               index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_key: Mapped[str] = mapped_column(String(160), nullable=False)
    owner_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'),
                                                     nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _fields(row: StoredInstrument) -> dict:
    return dict({'id': row.id}, **{field: getattr(row, field) for field in FIELDS})


class PostgresInstrumentRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def _common(self, session: Session):
        instruments = session.scalars(select(StoredInstrument).where(StoredInstrument.owner_id.is_(None))
                                      .order_by(StoredInstrument.position)).all()
        names = session.scalars(select(StoredInstrumentName).where(StoredInstrumentName.owner_id.is_(None))
                                .order_by(StoredInstrumentName.id)).all()
        by_instrument: dict[str, list[StoredInstrumentName]] = {}
        for name in names:
            by_instrument.setdefault(name.instrument_id, []).append(name)
        return [(row, by_instrument.get(row.id, [])) for row in instruments]

    def common(self) -> list[dict]:
        with Session(self.engine) as session:
            return [dict(_fields(row), aliases=[name.name for name in names]) for row, names in self._common(session)]

    def listing(self) -> list[dict]:
        with Session(self.engine) as session:
            return [dict(_fields(row), names=[{'id': name.id, 'name': name.name} for name in names])
                    for row, names in self._common(session)]

    def add_name(self, instrument_id: str, name: str, name_key: str) -> Optional[dict]:
        try:
            with Session(self.engine, expire_on_commit=False) as session, session.begin():
                instrument = session.get(StoredInstrument, instrument_id)
                if instrument is None or instrument.owner_id is not None:
                    return None
                row = StoredInstrumentName(instrument_id=instrument_id, name=name, name_key=name_key)
                session.add(row)
        except IntegrityError as exc:
            raise DuplicateName(name) from exc
        return {'id': row.id, 'name': row.name}

    def delete_name(self, name_id: int) -> bool:
        with Session(self.engine) as session, session.begin():
            return session.execute(delete(StoredInstrumentName).where(StoredInstrumentName.id == name_id,
                                                                      StoredInstrumentName.owner_id.is_(None))).rowcount > 0

    def create_instrument(self, fields: dict, names: list[tuple[str, str]]) -> dict:
        try:
            with Session(self.engine, expire_on_commit=False) as session, session.begin():
                position = session.scalar(select(func.coalesce(func.max(StoredInstrument.position), -1))) + 1
                row = StoredInstrument(position=position, **fields)
                session.add(row)
                session.flush()
                session.add_all(StoredInstrumentName(instrument_id=row.id, name=name, name_key=key) for name, key in names)
        except IntegrityError as exc:
            raise DuplicateName(fields['id']) from exc
        return _fields(row)

    def update_instrument(self, instrument_id: str, fields: dict) -> Optional[dict]:
        with Session(self.engine, expire_on_commit=False) as session, session.begin():
            row = session.get(StoredInstrument, instrument_id)
            if row is None or row.owner_id is not None:
                return None
            for field, value in fields.items():
                setattr(row, field, value)
            row.updated_at = func.now()
        with Session(self.engine) as session:
            return _fields(session.get(StoredInstrument, instrument_id))

    def private(self) -> list[dict]:
        with Session(self.engine) as session:
            return [_fields(row) for row in session.scalars(select(StoredInstrument)
                                                            .where(StoredInstrument.owner_id.is_not(None)))]

    def for_account(self, user_id: UUID) -> list[dict]:
        with Session(self.engine) as session:
            return [_fields(row) for row in session.scalars(select(StoredInstrument).where(StoredInstrument.owner_id == user_id)
                                                            .order_by(StoredInstrument.created_at))]

    def learned(self, user_id: UUID) -> dict[str, str]:
        with Session(self.engine) as session:
            rows = session.execute(select(StoredInstrumentName.name_key, StoredInstrumentName.instrument_id)
                                   .where(StoredInstrumentName.owner_id == user_id)).all()
        return {key: instrument_id for key, instrument_id in rows}

    def learn(self, user_id: UUID, names: list[tuple[str, str, str]]) -> None:
        if not names:
            return
        rows = {key: {'name': name[:120], 'name_key': key, 'instrument_id': instrument_id, 'owner_id': user_id}
                for name, key, instrument_id in names}
        statement = insert(StoredInstrumentName).values(list(rows.values()))
        statement = statement.on_conflict_do_update(
            index_elements=['owner_id', 'name_key'], index_where=text('owner_id IS NOT NULL'),
            set_={'instrument_id': statement.excluded.instrument_id, 'name': statement.excluded.name})
        with Session(self.engine) as session, session.begin():
            session.execute(statement)

    def create_own(self, user_id: UUID, fields: dict) -> dict:
        with Session(self.engine, expire_on_commit=False) as session, session.begin():
            row = StoredInstrument(id='own.' + uuid4().hex[:12], position=0, owner_id=user_id, **fields)
            session.add(row)
        return _fields(row)
