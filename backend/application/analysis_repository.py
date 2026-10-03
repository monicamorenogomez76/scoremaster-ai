from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Protocol
from uuid import UUID, uuid4


@dataclass(frozen=True)
class AnalysisRecord:
    source_sha256: str
    result: dict
    configuration: dict = field(default_factory=dict)
    features: dict = field(default_factory=dict)
    algorithm_version: str = 'legacy-v1'
    features_version: str = 'legacy-features-v1'
    analysis_id: UUID = field(default_factory=uuid4)
    created_at: Optional[datetime] = None


class AnalysisRepository(Protocol):
    def save(self, record: AnalysisRecord) -> UUID: ...
    def get(self, analysis_id: UUID) -> Optional[AnalysisRecord]: ...
