from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, UniqueConstraint, delete, func, select, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID, insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.application.analysis_repository import AnalysisRecord
from backend.application.library import Work, WorkUpload
from backend.infrastructure.analysis_repository import Base, StoredAnalysis, record_of


class StoredWork(Base):
    __tablename__ = 'works'
    __table_args__ = (UniqueConstraint('user_id', 'source_sha256', name='uq_works_user_source'),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'),
                                          nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    composer: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StoredBand(Base):
    __tablename__ = 'bands'
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'),
                                          primary_key=True)
    profile: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    section_levels: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _work(row: StoredWork, summary: Optional[dict] = None) -> Work:
    return Work(row.id, row.title, row.composer, row.file_name, row.size, row.created_at, row.updated_at, summary or {})


# Summary of the latest analysis of each work, read from the stored JSON without loading it whole.
_LIST = text("""
    select w.id, s.grade, s.critical_passages, s.compatibility_percent
    from works w left join lateral (
        select (a.result -> 'difficulty' ->> 'grade')::int as grade,
               jsonb_array_length(coalesce(a.result -> 'difficulty' -> 'critical_passages', '[]'::jsonb)) as critical_passages,
               (a.result -> 'band_fit' ->> 'compatibility_percent')::int as compatibility_percent
        from analyses a where a.work_id = w.id order by a.created_at desc limit 1) s on true
    where w.user_id = :user_id and s.grade is not null
""")


class PostgresLibraryRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def store_work(self, user_id: UUID, upload: WorkUpload) -> Work:
        """A new work, or the same work updated when its owner uploads the same file again."""
        values = dict(id=uuid4(), user_id=user_id, title=upload.title[:300], composer=(upload.composer or None),
                      file_name=upload.file_name[:255], source=upload.source, source_sha256=upload.source_sha256,
                      size=len(upload.source))
        statement = insert(StoredWork).values(**values).on_conflict_do_update(
            constraint='uq_works_user_source',
            set_={'title': values['title'], 'composer': values['composer'], 'file_name': values['file_name'],
                  'updated_at': func.now()}).returning(StoredWork.id)
        with Session(self.engine) as session, session.begin():
            work_id = session.execute(statement).scalar_one()
        return self.get_work(user_id, work_id)

    def list_works(self, user_id: UUID) -> list[Work]:
        with Session(self.engine) as session:
            rows = session.scalars(select(StoredWork).where(StoredWork.user_id == user_id)
                                   .order_by(StoredWork.updated_at.desc(), StoredWork.title)).all()
            summaries = {row.id: {"grade": row.grade, "critical_passages": row.critical_passages,
                                  "compatibility_percent": row.compatibility_percent}
                         for row in session.execute(_LIST, {"user_id": user_id})}
            return [_work(row, summaries.get(row.id)) for row in rows]

    def get_work(self, user_id: UUID, work_id: UUID) -> Optional[Work]:
        with Session(self.engine) as session:
            row = session.scalars(select(StoredWork).where(StoredWork.id == work_id, StoredWork.user_id == user_id)).first()
            return _work(row) if row else None

    def work_file(self, user_id: UUID, work_id: UUID) -> Optional[tuple[bytes, str]]:
        with Session(self.engine) as session:
            row = session.execute(select(StoredWork.source, StoredWork.file_name)
                                  .where(StoredWork.id == work_id, StoredWork.user_id == user_id)).first()
            return (bytes(row.source), row.file_name) if row else None

    def latest_analysis(self, user_id: UUID, work_id: UUID) -> Optional[AnalysisRecord]:
        with Session(self.engine) as session:
            row = session.scalars(select(StoredAnalysis)
                                  .where(StoredAnalysis.work_id == work_id, StoredAnalysis.user_id == user_id)
                                  .order_by(StoredAnalysis.created_at.desc()).limit(1)).first()
            return record_of(row) if row else None

    def delete_work(self, user_id: UUID, work_id: UUID) -> bool:
        with Session(self.engine) as session, session.begin():
            deleted = session.execute(delete(StoredWork).where(StoredWork.id == work_id, StoredWork.user_id == user_id))
            return deleted.rowcount > 0

    def band_profile(self, user_id: UUID) -> dict:
        with Session(self.engine) as session:
            return session.scalar(select(StoredBand.profile).where(StoredBand.user_id == user_id)) or {}

    def update_band_profile(self, user_id: UUID, changes: dict) -> dict:
        """Merge the changes into the stored template: instruments of other works keep their musicians."""
        statement = insert(StoredBand).values(user_id=user_id, profile=changes).on_conflict_do_update(
            index_elements=['user_id'],
            set_={'profile': StoredBand.profile.concat(changes), 'updated_at': func.now()}).returning(StoredBand.profile)
        with Session(self.engine) as session, session.begin():
            return session.execute(statement).scalar_one()
