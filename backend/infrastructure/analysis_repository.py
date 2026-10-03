from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from backend.application.analysis_repository import AnalysisRecord


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


class PostgresAnalysisRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def save(self, record: AnalysisRecord) -> UUID:
        with Session(self.engine) as session, session.begin():
            session.add(StoredAnalysis(id=record.analysis_id, source_sha256=record.source_sha256,
                result=record.result, configuration=record.configuration, features=record.features,
                algorithm_version=record.algorithm_version, features_version=record.features_version))
        return record.analysis_id

    def get(self, analysis_id: UUID) -> Optional[AnalysisRecord]:
        with Session(self.engine) as session:
            row = session.get(StoredAnalysis, analysis_id)
            if row is None:
                return None
            return AnalysisRecord(source_sha256=row.source_sha256, result=row.result,
                configuration=row.configuration, features=row.features,
                algorithm_version=row.algorithm_version, features_version=row.features_version,
                analysis_id=row.id, created_at=row.created_at)
