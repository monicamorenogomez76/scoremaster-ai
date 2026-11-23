"""The names of an American band edition of a century ago (2026-11-23, «The Ride of the Valkyries», Carl Fischer, arr.
Laurendeau): the parts the reader named, unknown to the catalog, sounded in the wrong key because they took no
transposition. The altos are E♭ alto horns, the tenors B♭ tenor horns (treble clef), the basses tubas."""
import pytest

from backend.domain.instrument_catalog import match_instrument_name
from backend.domain.instrument_transposition import written_to_sounding


@pytest.mark.parametrize("name, canonical_id, part_numbers", [
    ("D♭ Piccolo", "piccolo.db", ()),
    ("Solo B♭ Clarinet", "clarinet.bb", ()),
    ("2nd & 3rd B♭ Cornets", "cornet.bb", (2, 3)),
    ("1st & 2nd Trombones", "trombone.tenor", (1, 2)),
    ("3rd & 4th Altos", "alto_horn", (3, 4)),
    ("1st & 2nd Tenors", "baritone_horn", (1, 2)),
    ("Basses", "tuba", ()),
    ("Timpany in B♭ & F", "timpani", ()),
])
def test_the_names_of_an_old_american_band_edition_are_known(name, canonical_id, part_numbers):
    match = match_instrument_name(name)
    assert match.identity is not None and match.identity.canonical_id == canonical_id
    assert match.part_numbers == part_numbers


def test_the_d_flat_piccolo_sounds_a_minor_ninth_above():
    assert written_to_sounding("piccolo.db") == (1, 1, 1)
    assert match_instrument_name("Piccolo").identity.canonical_id == "piccolo", "a piccolo is in C unless it says D♭"


def test_an_alto_saxophone_is_still_a_saxophone():
    """«Alto 1» is the alto saxophone of a big band and the alto horn of an old band: the director confirms it."""
    assert match_instrument_name("1st Alto").identity is None
    assert match_instrument_name("Alto Saxophone").identity.canonical_id == "saxophone.alto"
    assert match_instrument_name("Alto Sax. 1").identity.canonical_id == "saxophone.alto"
