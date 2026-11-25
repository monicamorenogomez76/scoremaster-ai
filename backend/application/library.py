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
    # "pdf" when the reader in GitHub Actions read it from a PDF (2026-10-27): its grade is provisional.
    source_format: str = "musicxml"


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
    source_format: str = "musicxml"
    # The director named it (2026-11-25): its title and composer prevail over those of its file.
    title_edited: bool = False


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


@dataclass(frozen=True)
class Correction:
    """A note the director corrected (note_corrections.py), with what the list shows of it."""
    id: UUID
    data: dict
    created_at: datetime


def named_result(result: dict, work: Work) -> dict:
    """An analysis with the title and composer of a work the director named; the same otherwise."""
    return {**result, "title": work.title, "composer": work.composer} if work.title_edited else result


class LibraryRepository(Protocol):
    def store_work(self, user_id: UUID, upload: WorkUpload) -> Work: ...
    def list_works(self, user_id: UUID) -> list[Work]: ...
    def get_work(self, user_id: UUID, work_id: UUID) -> Optional[Work]: ...
    def work_file(self, user_id: UUID, work_id: UUID) -> Optional[tuple[bytes, str]]: ...
    def replace_source(self, user_id: UUID, work_id: UUID, source: bytes) -> bool:
        """False when the work does not exist or its owner already has a work with that file."""
    def latest_analysis(self, user_id: UUID, work_id: UUID) -> Optional[AnalysisRecord]: ...
    def delete_work(self, user_id: UUID, work_id: UUID) -> bool: ...
    def update_preparation(self, user_id: UUID, work_id: UUID, status: str) -> Optional[Work]: ...
    def rename_work(self, user_id: UUID, work_id: UUID, title: str, composer: Optional[str]) -> Optional[Work]: ...
    def preparation_priorities(self, user_id: UUID) -> list[dict]: ...
    # The corrected notes, oldest first; None when the work is not the user's. Each change of the file goes with its
    # correction, or neither does.
    def corrections(self, user_id: UUID, work_id: UUID) -> Optional[list[Correction]]: ...
    def add_corrections(self, user_id: UUID, work_id: UUID, corrections: list[dict], source: bytes) -> bool: ...
    def remove_correction(self, user_id: UUID, work_id: UUID, correction_id: UUID, source: bytes) -> bool: ...
    # The doubts of the PDF reader (reading_doubts.py); None when the work has none or is not the user's.
    def reading_doubts(self, user_id: UUID, work_id: UUID) -> Optional[dict]: ...
    def save_reading_doubts(self, user_id: UUID, work_id: UUID, doubts: Optional[dict]) -> bool: ...
    def band_profile(self, user_id: UUID) -> dict: ...
    def update_band_profile(self, user_id: UUID, changes: dict) -> dict: ...
    # Publisher grades: None when the work is not the user's.
    def external_grades(self, user_id: UUID, work_id: UUID) -> Optional[list[ExternalGrade]]: ...
    def add_external_grade(self, user_id: UUID, work_id: UUID, grade: ExternalGrade) -> Optional[ExternalGrade]: ...
    def delete_external_grade(self, user_id: UUID, work_id: UUID, grade_id: UUID) -> bool: ...
