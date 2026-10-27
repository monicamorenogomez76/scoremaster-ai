"""PDF imports in PostgreSQL (author's decision, 2026-10-27). The one-time token is kept only as its sha256 and is
forgotten, with the PDFs, as soon as the reader sends its result."""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, delete, func, select, text, update
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.application.pdf_imports import FINISHED, PdfImport
from backend.infrastructure.analysis_repository import Base


class StoredPdfImport(Base):
    __tablename__ = 'pdf_imports'
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False,
                                          index=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default='queued')
    token_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    pages_done: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')
    pages_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0')
    error: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    musicxml: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    band_profile: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    total_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default='60')
    work_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey('works.id', ondelete='SET NULL'),
                                                    nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StoredPdfImportFile(Base):
    __tablename__ = 'pdf_import_files'
    import_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('pdf_imports.id', ondelete='CASCADE'),
                                            primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


def _import(row: StoredPdfImport) -> PdfImport:
    return PdfImport(row.id, row.user_id, row.kind, row.title, row.status, row.pages_done, row.pages_total, row.error,
                     row.work_id, dict(row.band_profile or {}), row.total_minutes, row.updated_at)


class PostgresPdfImportRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def create(self, user_id: UUID, kind: str, title: str, files: list[tuple[str, bytes]], token_sha256: str,
               band_profile: dict, total_minutes: int) -> PdfImport:
        row = StoredPdfImport(id=uuid4(), user_id=user_id, kind=kind, title=title[:200], status='queued',
                              token_sha256=token_sha256, band_profile=band_profile, total_minutes=total_minutes)
        with Session(self.engine, expire_on_commit=False) as session, session.begin():
            session.add(row)
            session.flush()
            session.add_all(StoredPdfImportFile(import_id=row.id, position=position, name=name[:255], content=content)
                            for position, (name, content) in enumerate(files))
        return self.for_owner(user_id, row.id)

    def for_owner(self, user_id: UUID, import_id: UUID) -> Optional[PdfImport]:
        with Session(self.engine) as session:
            row = session.scalars(select(StoredPdfImport).where(StoredPdfImport.id == import_id,
                                                                StoredPdfImport.user_id == user_id)).first()
            return _import(row) if row else None

    def for_reader(self, import_id: UUID, token_sha256: str) -> Optional[PdfImport]:
        with Session(self.engine) as session:
            row = session.scalars(select(StoredPdfImport).where(StoredPdfImport.id == import_id,
                                                                StoredPdfImport.token_sha256 == token_sha256,
                                                                StoredPdfImport.status.not_in(FINISHED))).first()
            return _import(row) if row else None

    def file(self, import_id: UUID, position: int) -> Optional[tuple[str, bytes]]:
        with Session(self.engine) as session:
            row = session.execute(select(StoredPdfImportFile.name, StoredPdfImportFile.content).where(
                StoredPdfImportFile.import_id == import_id, StoredPdfImportFile.position == position)).first()
            return (row.name, bytes(row.content)) if row else None

    def _update(self, import_id: UUID, **values) -> None:
        with Session(self.engine) as session, session.begin():
            session.execute(update(StoredPdfImport).where(StoredPdfImport.id == import_id)
                            .values(**values, updated_at=func.now()))

    def progress(self, import_id: UUID, pages_done: int, pages_total: int) -> None:
        self._update(import_id, status='reading', pages_done=pages_done, pages_total=pages_total)

    def received(self, import_id: UUID, musicxml: bytes) -> None:
        with Session(self.engine) as session, session.begin():
            session.execute(delete(StoredPdfImportFile).where(StoredPdfImportFile.import_id == import_id))
            session.execute(update(StoredPdfImport).where(StoredPdfImport.id == import_id).values(
                status='analysing', musicxml=musicxml, token_sha256=None, updated_at=func.now()))

    def musicxml(self, import_id: UUID) -> Optional[bytes]:
        with Session(self.engine) as session:
            content = session.scalar(select(StoredPdfImport.musicxml).where(StoredPdfImport.id == import_id))
            return bytes(content) if content is not None else None

    def done(self, import_id: UUID, work_id: UUID) -> None:
        self._update(import_id, status='done', work_id=work_id, musicxml=None)

    def failed(self, import_id: UUID, error: str) -> None:
        with Session(self.engine) as session, session.begin():
            session.execute(delete(StoredPdfImportFile).where(StoredPdfImportFile.import_id == import_id))
            session.execute(update(StoredPdfImport).where(StoredPdfImport.id == import_id).values(
                status='failed', error=error[:300], token_sha256=None, musicxml=None, updated_at=func.now()))
