from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ScoreNote:
	pitch: Optional[str]
	duration_quarters: float
	is_rest: bool = False


@dataclass(frozen=True)
class ScoreMeasure:
	number: int
	notes: tuple[ScoreNote, ...]


@dataclass(frozen=True)
class ScorePart:
	name: str
	measures: tuple[ScoreMeasure, ...]


@dataclass(frozen=True)
class TempoMark:
	measure_number: int
	offset_quarters: float
	beats_per_minute: float
	beat_unit_quarters: float


@dataclass(frozen=True)
class Score:
	title: str
	parts: tuple[ScorePart, ...]
	tempo_marks: tuple[TempoMark, ...] = ()


@dataclass(frozen=True)
class Finding:
	code: str
	severity: str
	instrument: str
	measure_range: str
	description: str
	evidence: dict

