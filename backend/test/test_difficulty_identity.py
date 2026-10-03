"""Instrument difficulty uses the resolved identity, not the visible part name (step 08, consumers)."""
import pytest

from backend.analyzers.instrument_difficulty import compute_instrument_difficulty
from backend.domain.models import PartMetadata, ScoreMeasure, ScoreNote, ScorePart

# Wide range, leaps and high register, so that the instrument profile changes the result.
PASSAGE = tuple(ScoreMeasure(number, tuple(ScoreNote(pitch, 0.5) for pitch in
                ("C4", "G5", "D4", "A5", "E4", "B5", "C6", "E6")))
                for number in range(1, 9))


def numbers(name, metadata=None):
    part = ScorePart(name, PASSAGE, metadata or PartMetadata())
    result = compute_instrument_difficulty(part, tempo_bpm=120)
    return result["family"], result["difficulty_score"], result["dimensions"]


@pytest.mark.parametrize("alias, reference", [
    ("Clarinete 2", "B♭ Clarinet 2"),
    ("Clarinete bajo", "Bass Clarinet"),
    ("Trompa", "Horn in F"),
    ("F Horn 1 & 2", "Horn in F"),
    ("Trompeta en Si bemol", "B♭ Trumpet"),
    ("Saxofón alto", "Alto Sax"),
    ("Bombardino", "Euphonium"),
    ("Contrabajo", "Double Bass"),
])
def test_aliases_get_the_profile_of_their_identity(alias, reference):
    assert numbers(alias) == numbers(reference)


def test_spanish_names_are_no_longer_classified_as_other():
    assert numbers("Trompa")[0] == "brass"
    assert numbers("Corno inglés")[0] == "woodwinds"


def test_english_horn_is_not_scored_with_the_horn_profile():
    assert numbers("English Horn")[0] == "woodwinds"
    assert numbers("English Horn")[1:] != numbers("Horn in F")[1:]


def test_metadata_proposed_identity_is_used_when_the_name_is_generic():
    metadata = PartMetadata(part_id="P1", part_name="Voice", instrument_names=("Clarinet",))
    assert numbers("Voice", metadata) == numbers("Clarinet")


def test_unresolved_parts_keep_the_previous_behaviour():
    family, _, _ = numbers("Voice", PartMetadata(part_id="P1", part_name="Voice", instrument_names=("Voice Oohs",)))
    assert family == "other"


def test_rhythm_section_uses_neutral_weights_until_calibrated():
    from backend.analyzers.instrument_difficulty import compute_instrument_difficulty as compute
    bass = compute(ScorePart("Electric Bass", PASSAGE), tempo_bpm=120)
    assert bass["family"] == "rhythm"
    assert bass["family_label_es"] == "Sección rítmica"
    assert numbers("Electric Bass")[1:] == numbers("Voice")[1:]
