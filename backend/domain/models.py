from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ScoreNote:
	pitch: Optional[str]
	duration_quarters: float
	is_rest: bool = False
	# Position inside the measure, in quarter notes (None when unknown, e.g. hand-built scores).
	offset_quarters: Optional[float] = None
	# Written breath mark, caesura or fermata: a hint of a phrase ending.
	phrase_mark: bool = False
	# MusicXML voice inside the staff (None for a single voice or hand-built scores).
	voice: Optional[str] = None
	# "start", "continue" or "stop": a continued or stopped tie is not a new attack.
	tie: Optional[str] = None
	# Grace notes take no time but are attacked (author's decision, 2026-10-05).
	is_grace: bool = False
	# Every written pitch of a chord, lowest first; `pitch` is then its top note.
	chord_pitches: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScoreMeasure:
	number: int
	notes: tuple[ScoreNote, ...]
	duration_quarters: Optional[float] = None


@dataclass(frozen=True)
class PartTransposition:
	"""MusicXML <transpose>: interval from written to sounding pitch."""
	chromatic: int
	diatonic: Optional[int] = None
	octave_change: int = 0


@dataclass(frozen=True)
class PartMetadata:
	"""What the MusicXML declares about a part, kept verbatim for later resolution."""
	part_id: Optional[str] = None
	part_name: Optional[str] = None
	part_abbreviation: Optional[str] = None
	instrument_names: tuple[str, ...] = ()
	instrument_sounds: tuple[str, ...] = ()
	midi_programs: tuple[int, ...] = ()
	midi_channels: tuple[int, ...] = ()
	transposition: Optional[PartTransposition] = None
	staff_number: Optional[int] = None
	# Catalog identity confirmed by the user (step 09); not read from the MusicXML.
	confirmed_id: Optional[str] = None


@dataclass(frozen=True)
class ScorePart:
	name: str
	measures: tuple[ScoreMeasure, ...]
	metadata: PartMetadata = PartMetadata()


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
	composer: Optional[str] = None


@dataclass(frozen=True)
class Finding:
	code: str
	severity: str
	instrument: str
	measure_range: str
	description: str
	evidence: dict

