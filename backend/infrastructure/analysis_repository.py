from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from backend.application.analysis_repository import AnalysisRecord, OutdatedAnalysis


class Base(DeclarativeBase):
    pass


class StoredAnalysis(Base):
    __tablename__ = 'analyses'
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    result: Mapped[dict] = mapped_column(JSONB, nullable=False)
    configuration: Mapped[dict] = mapped_column(JSONB, nullable=False)
    features: Mapped[dict] = mapped_column(JSONB, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(100), nullable=False)
    features_version: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'),
                                                    nullable=True, index=True)
    work_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey('works.id', ondelete='CASCADE'),
                                                    nullable=True, index=True)


def record_of(row: StoredAnalysis) -> AnalysisRecord:
    return AnalysisRecord(source_sha256=row.source_sha256, result=row.result,
        configuration=row.configuration, features=row.features,
        algorithm_version=row.algorithm_version, features_version=row.features_version,
        analysis_id=row.id, created_at=row.created_at, user_id=row.user_id, work_id=row.work_id)


class PostgresAnalysisRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def save(self, record: AnalysisRecord) -> UUID:
        with Session(self.engine) as session, session.begin():
            session.add(StoredAnalysis(id=record.analysis_id, source_sha256=record.source_sha256,
                result=record.result, configuration=record.configuration, features=record.features,
                algorithm_version=record.algorithm_version, features_version=record.features_version,
                user_id=record.user_id, work_id=record.work_id))
        return record.analysis_id

    def get(self, analysis_id: UUID) -> Optional[AnalysisRecord]:
        with Session(self.engine) as session:
            row = session.get(StoredAnalysis, analysis_id)
            return None if row is None else record_of(row)

    def outdated_latest(self, algorithm_version: str, instruments: dict | None = None) -> list[OutdatedAnalysis]:
        """Works whose latest analysis was made by another version of the algorithm or, when given, of the instrument
        catalog and resolver (2026-10-28: a part unknown before may now have its instrument), or from another file of
        the work (2026-10-29: the works read from a PDF before took their transposition)."""
        statement = text("""
            select distinct on (a.work_id) a.work_id, a.user_id, a.configuration, a.algorithm_version, a.features,
                   a.source_sha256 <> w.source_sha256 as changed
            from analyses a join works w on w.id = a.work_id where a.user_id is not null
            order by a.work_id, a.created_at desc""")
        with Session(self.engine) as session:
            return [OutdatedAnalysis(row.user_id, row.work_id, row.configuration or {})
                    for row in session.execute(statement)
                    if row.changed or row.algorithm_version != algorithm_version
                    or (instruments and (row.features or {}).get("instrument_resolution") != instruments)]


# Analyses reference users and works: register those tables on the shared metadata.
from backend.infrastructure import account_repository, library_repository  # noqa: E402,F401
