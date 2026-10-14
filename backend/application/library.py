"""Library of works and band template per user: records and repository port (no database code)."""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, Protocol
from uuid import UUID

from backend.application.analysis_repository import AnalysisRecord

# How far the band is with a work, set by the director; independent of the analysed difficulty.
PREPARATION_STATUSES = ("review", "preparing", "ready", "archived")


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
    preparation_status: str = "review"


@dataclass(frozen=True)
class ExternalGrade:
    """A grade published for the work (by a publisher or catalogue), typed in by its owner."""
    id: UUID
    scale: str
    label: str
    grade: float
    source: str
    url: Optional[str] = None
    consulted_on: Optional[date] = None


class LibraryRepository(Protocol):
    def store_work(self, user_id: UUID, upload: WorkUpload) -> Work: ...
    def list_works(self, user_id: UUID) -> list[Work]: ...
    def get_work(self, user_id: UUID, work_id: UUID) -> Optional[Work]: ...
    def work_file(self, user_id: UUID, work_id: UUID) -> Optional[tuple[bytes, str]]: ...
    def latest_analysis(self, user_id: UUID, work_id: UUID) -> Optional[AnalysisRecord]: ...
    def delete_work(self, user_id: UUID, work_id: UUID) -> bool: ...
    def update_preparation(self, user_id: UUID, work_id: UUID, status: str) -> Optional[Work]: ...
    def preparation_priorities(self, user_id: UUID) -> list[dict]: ...
    def band_profile(self, user_id: UUID) -> dict: ...
    def update_band_profile(self, user_id: UUID, changes: dict) -> dict: ...
    # Publisher grades: None when the work is not the user's.
    def external_grades(self, user_id: UUID, work_id: UUID) -> Optional[list[ExternalGrade]]: ...
    def add_external_grade(self, user_id: UUID, work_id: UUID, grade: ExternalGrade) -> Optional[ExternalGrade]: ...
    def delete_external_grade(self, user_id: UUID, work_id: UUID, grade_id: UUID) -> bool: ...
