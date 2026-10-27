from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, LargeBinary, String, UniqueConstraint, delete, func, select, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID, insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.application.analysis_repository import AnalysisRecord
from backend.application.library import ExternalGrade, Work, WorkUpload
from backend.infrastructure.analysis_repository import Base, StoredAnalysis, record_of
from backend.infrastructure.band_repository import active_band, update_active_profile


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
    preparation_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default='review')
    source_format: Mapped[str] = mapped_column(String(10), nullable=False, server_default='musicxml')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StoredExternalGrade(Base):
    __tablename__ = 'work_external_grades'
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    work_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('works.id', ondelete='CASCADE'), nullable=False,
                                          index=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    scale: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[str] = mapped_column(String(40), nullable=False)
    grade: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    consulted_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _external(row: StoredExternalGrade) -> ExternalGrade:
    return ExternalGrade(row.id, row.scale, row.label, row.grade, row.source, row.url, row.consulted_on)


def _work(row: StoredWork, summary: Optional[dict] = None) -> Work:
    return Work(row.id, row.title, row.composer, row.file_name, row.size, row.created_at, row.updated_at, summary or {},
                row.preparation_status, row.source_format)


# Summary of the latest analysis of each work, read from the stored JSON without loading it whole.
# Analyses without a declared scale were graded 1-5, before step 13.
_LIST = text("""
    select w.id, s.grade, s.grade_max, s.critical_passages, s.compatibility_percent
    from works w left join lateral (
        select (a.result -> 'difficulty' ->> 'grade')::int as grade,
               coalesce((a.result -> 'difficulty' -> 'scale' ->> 'grades')::int, 5) as grade_max,
               jsonb_array_length(coalesce(a.result -> 'difficulty' -> 'critical_passages', '[]'::jsonb)) as critical_passages,
               (a.result -> 'band_fit' ->> 'compatibility_percent')::int as compatibility_percent
        from analyses a where a.work_id = w.id order by a.created_at desc limit 1) s on true
    where w.user_id = :user_id and s.grade is not null
""")

# Critical passages of the latest analysis of each work in preparation, in the analysis order.
_PRIORITIES = text("""
    select w.id as work_id, w.title, p.passage
    from works w cross join lateral (
        select a.result from analyses a where a.work_id = w.id order by a.created_at desc limit 1) latest
    cross join lateral jsonb_array_elements(coalesce(latest.result -> 'difficulty' -> 'critical_passages', '[]'::jsonb))
        with ordinality as p(passage, position)
    where w.user_id = :user_id and w.preparation_status = 'preparing'
    order by w.updated_at desc, w.title, p.position
""")
_PASSAGE_FIELDS = ("instrument", "instrument_label_es", "family", "family_label_es", "measure_range", "findings")


class PostgresLibraryRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def store_work(self, user_id: UUID, upload: WorkUpload) -> Work:
        """A new work, or the same work updated when its owner uploads the same file again."""
        values = dict(id=uuid4(), user_id=user_id, title=upload.title[:300], composer=(upload.composer or None),
                      file_name=upload.file_name[:255], source=upload.source, source_sha256=upload.source_sha256,
                      size=len(upload.source), source_format=upload.source_format)
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
            summaries = {row.id: {"grade": row.grade, "grade_max": row.grade_max, "critical_passages": row.critical_passages,
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

    def update_preparation(self, user_id: UUID, work_id: UUID, status: str) -> Optional[Work]:
        with Session(self.engine) as session, session.begin():
            row = session.scalars(select(StoredWork).where(StoredWork.id == work_id, StoredWork.user_id == user_id)).first()
            if row is None:
                return None
            row.preparation_status = status
            session.flush()
            return _work(row)

    def preparation_priorities(self, user_id: UUID) -> list[dict]:
        with Session(self.engine) as session:
            return [{"work_id": str(row.work_id), "title": row.title,
                     **{key: row.passage.get(key) for key in _PASSAGE_FIELDS}, "origin": "analysis"}
                    for row in session.execute(_PRIORITIES, {"user_id": user_id})]

    def band_profile(self, user_id: UUID) -> dict:
        """Template of the active band (several bands per director since 2026-10-06)."""
        with Session(self.engine) as session:
            row = active_band(session, user_id)
            return dict(row.profile) if row else {}

    def update_band_profile(self, user_id: UUID, changes: dict) -> dict:
        """Merge the changes into the active band: instruments of other works keep their musicians."""
        with Session(self.engine) as session, session.begin():
            return update_active_profile(session, user_id, changes)

    def _owns(self, session: Session, user_id: UUID, work_id: UUID) -> bool:
        return session.scalar(select(StoredWork.id).where(StoredWork.id == work_id, StoredWork.user_id == user_id)) is not None

    def external_grades(self, user_id: UUID, work_id: UUID) -> Optional[list[ExternalGrade]]:
        with Session(self.engine) as session:
            if not self._owns(session, user_id, work_id):
                return None
            return [_external(row) for row in session.scalars(
                select(StoredExternalGrade).where(StoredExternalGrade.work_id == work_id)
                .order_by(StoredExternalGrade.created_at, StoredExternalGrade.id))]

    def add_external_grade(self, user_id: UUID, work_id: UUID, grade: ExternalGrade) -> Optional[ExternalGrade]:
        with Session(self.engine) as session, session.begin():
            if not self._owns(session, user_id, work_id):
                return None
            row = StoredExternalGrade(id=grade.id, work_id=work_id, user_id=user_id, scale=grade.scale, label=grade.label,
                                      grade=grade.grade, source=grade.source, url=grade.url, consulted_on=grade.consulted_on)
            session.add(row)
            session.flush()
            return _external(row)

    def delete_external_grade(self, user_id: UUID, work_id: UUID, grade_id: UUID) -> bool:
        with Session(self.engine) as session, session.begin():
            deleted = session.execute(delete(StoredExternalGrade).where(
                StoredExternalGrade.id == grade_id, StoredExternalGrade.work_id == work_id,
                StoredExternalGrade.user_id == user_id))
            return deleted.rowcount > 0
