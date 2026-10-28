"""PDF scores (decided 2026-10-27): an import keeps its PDFs until the reader in GitHub Actions sends the
work back, and says how far the reading got. Ports only: PostgreSQL (backend/infrastructure/pdf_import_repository.py)
and GitHub (backend/infrastructure/omr_dispatcher.py) live in the infrastructure."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol
from uuid import UUID

# queued → reading → analysing → done, or failed at any step.
FINISHED = ("done", "failed")


@dataclass(frozen=True)
class PdfImport:
    id: UUID
    user_id: UUID
    kind: str
    title: str
    status: str
    pages_done: int
    pages_total: int
    error: Optional[str]
    work_id: Optional[UUID]
    band_profile: dict
    total_minutes: int
    updated_at: Optional[datetime] = None


class PdfImportRepository(Protocol):
    def create(self, user_id: UUID, kind: str, title: str, files: list[tuple[str, bytes]], token_sha256: str,
               band_profile: dict, total_minutes: int) -> PdfImport: ...
    # The owner's import; another user's is None, as a missing one.
    def for_owner(self, user_id: UUID, import_id: UUID) -> Optional[PdfImport]: ...
    # The reader's view: the import whose token matches while it is still being read.
    def for_reader(self, import_id: UUID, token_sha256: str) -> Optional[PdfImport]: ...
    def file(self, import_id: UUID, position: int) -> Optional[tuple[str, bytes]]: ...
    def progress(self, import_id: UUID, pages_done: int, pages_total: int) -> None: ...
    # The reader's MusicXML: the PDFs and the token go; the work is analysed next.
    def received(self, import_id: UUID, musicxml: bytes) -> None: ...
    def musicxml(self, import_id: UUID) -> Optional[bytes]: ...
    def done(self, import_id: UUID, work_id: UUID) -> None: ...
    def failed(self, import_id: UUID, error: str) -> None: ...


class OmrDispatcher(Protocol):
    """Starts the reader with a job: kind, title, the PDFs' addresses, the callback and the one-time token."""
    def dispatch(self, payload: dict) -> None: ...
