"""Works read once (gzipped JSON), by content hash, kind and algorithm version."""
from datetime import datetime
from typing import Iterator, Optional

from sqlalchemy import CheckConstraint, DateTime, LargeBinary, String, and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, Session, aliased, mapped_column

from backend.infrastructure.analysis_repository import Base
from backend.infrastructure.library_repository import StoredWork


class PreparedWork(Base):
    __tablename__ = 'prepared_works'
    __table_args__ = (CheckConstraint("kind in ('score', 'playback')", name='ck_prepared_works_kind'),)
    source_sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PostgresPreparedStore:
    """One kind of prepared work: the parsed score or the playback timeline."""
    def __init__(self, engine: Engine, kind: str):
        self.engine, self.kind = engine, kind

    def load(self, key: str, version: str) -> Optional[bytes]:
        with Session(self.engine) as session:
            return session.scalar(select(PreparedWork.data).where(
                PreparedWork.source_sha256 == key, PreparedWork.kind == self.kind, PreparedWork.version == version))

    def save(self, key: str, version: str, data: bytes) -> None:
        statement = insert(PreparedWork).values(source_sha256=key, kind=self.kind, version=version, data=data)
        statement = statement.on_conflict_do_update(index_elements=[PreparedWork.source_sha256, PreparedWork.kind],
                                                    set_={'version': version, 'data': data, 'created_at': func.now()})
        with Session(self.engine) as session, session.begin():
            session.execute(statement)

    def missing_sources(self, version: str) -> Iterator[bytes]:
        """Uploaded works not prepared yet with this version, one at a time (a band score is a few MB)."""
        with Session(self.engine) as session:
            prepared = aliased(PreparedWork)
            keys = session.scalars(
                select(StoredWork.source_sha256).distinct()
                .outerjoin(prepared, and_(prepared.source_sha256 == StoredWork.source_sha256,
                                          prepared.kind == self.kind, prepared.version == version))
                .where(prepared.source_sha256.is_(None))).all()
        for key in keys:
            with Session(self.engine) as session:
                source = session.scalar(select(StoredWork.source).where(StoredWork.source_sha256 == key).limit(1))
            if source is not None:
                yield source
