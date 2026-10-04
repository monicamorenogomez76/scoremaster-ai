"""Library of works and band template per user: records and repository port (no database code)."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Protocol
from uuid import UUID

from backend.application.analysis_repository import AnalysisRecord


@dataclass(frozen=True)
class WorkUpload:
    title: str
    composer: Optional[str]
    file_name: str
    source: bytes
    source_sha256: str


@dataclass(frozen=True)
class Work:
    id: UUID
    title: str
    composer: Optional[str]
    file_name: str
    size: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Latest analysis in brief: grade, number of critical passages and band compatibility.
    summary: dict = field(default_factory=dict)


class LibraryRepository(Protocol):
    def store_work(self, user_id: UUID, upload: WorkUpload) -> Work: ...
    def list_works(self, user_id: UUID) -> list[Work]: ...
    def get_work(self, user_id: UUID, work_id: UUID) -> Optional[Work]: ...
    def work_file(self, user_id: UUID, work_id: UUID) -> Optional[tuple[bytes, str]]: ...
    def latest_analysis(self, user_id: UUID, work_id: UUID) -> Optional[AnalysisRecord]: ...
    def delete_work(self, user_id: UUID, work_id: UUID) -> bool: ...
    def band_profile(self, user_id: UUID) -> dict: ...
    def update_band_profile(self, user_id: UUID, changes: dict) -> dict: ...
