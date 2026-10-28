"""Canonical instrument catalog: stable identities and exact multilingual aliases (step 06)."""
import pytest

from backend.domain.instrument_catalog import (
    UNKNOWN,
    catalog_entries,
    match_instrument_name,
    normalize_instrument_name,
)


@pytest.mark.parametrize("name, canonical_id", [
    # Clarinets: soprano in B♭ written in many ways, and the variants that must not collapse.
    ("Clarinet", "clarinet.bb"),
    ("Clarinet in Bb", "clarinet.bb"),
    ("Clarinet in B♭", "clarinet.bb"),
    ("Bb Clarinet", "clarinet.bb"),
    ("B♭ Clarinet", "clarinet.bb"),
    ("B-flat Clarinet", "clarinet.bb"),
    ("Clarinete", "clarinet.bb"),
    ("Clarinete Sib", "clarinet.bb"),
    ("Clarinete en Si bemol", "clarinet.bb"),
    ("Clarinetto", "clarinet.bb"),
    ("Clarinetto in Sib", "clarinet.bb"),
    ("E♭ Clarinet", "clarinet.eb"),
    ("Requinto", "clarinet.eb"),
    ("Clarinet in A", "clarinet.a"),
    ("Alto Clarinet", "clarinet.alto"),
    ("Bass Clarinet", "clarinet.bass"),
    ("B♭ Bass Clarinet", "clarinet.bass"),
    ("Clarinete bajo", "clarinet.bass"),
    # Double reeds.
    ("Oboe", "oboe"),
    ("English Horn", "english_horn"),
    ("Cor anglais", "english_horn"),
    ("Corno inglés", "english_horn"),
    ("Bassoon", "bassoon"),
    ("Fagot", "bassoon"),
    ("Contrabassoon", "contrabassoon"),
    # Flutes and saxophones.
    ("Piccolo", "piccolo"),
    ("Flautín", "piccolo"),
    ("Flute", "flute"),
    ("Flauta", "flute"),
    ("Alto Sax", "saxophone.alto"),
    ("Alto Saxophone", "saxophone.alto"),
    ("Alto Saxophone in Eb", "saxophone.alto"),
    ("Saxofón alto", "saxophone.alto"),
    ("Tenor Saxophone", "saxophone.tenor"),
    ("Saxofón tenor", "saxophone.tenor"),
    ("Baritone Saxophone", "saxophone.baritone"),
    ("Saxofón barítono", "saxophone.baritone"),
    # In a concert band "Baritone" alone means the baritone saxophone (decided).
    ("Baritone", "saxophone.baritone"),
    ("Barítono", "saxophone.baritone"),
    # Brass: horn, and trumpet-family instruments kept apart.
    ("Horn", "horn.f"),
    ("French Horn", "horn.f"),
    ("Horn in F", "horn.f"),
    ("F Horn", "horn.f"),
    ("Trompa", "horn.f"),
    ("Trompa en Fa", "horn.f"),
    ("Corno", "horn.f"),
    ("Trumpet", "trumpet.bb"),
    ("B♭ Trumpet", "trumpet.bb"),
    ("Trompeta", "trumpet.bb"),
    ("Trompeta en Si bemol", "trumpet.bb"),
    ("Cornet", "cornet.bb"),
    ("B♭ Cornet", "cornet.bb"),
    ("Flugelhorn", "flugelhorn.bb"),
    ("Fliscorno", "flugelhorn.bb"),
    ("Trombone", "trombone.tenor"),
    ("Trombón", "trombone.tenor"),
    ("Bass Trombone", "trombone.bass"),
    ("Euphonium", "euphonium"),
    ("Bombardino", "euphonium"),
    ("Baritone Horn", "baritone_horn"),
    ("Tuba", "tuba"),
    # Strings, keyboards and percussion found in concert band scores.
    ("Double Bass", "double_bass"),
    ("String Bass", "double_bass"),
    ("Contrabajo", "double_bass"),
    ("5-str. Electric Bass", "electric_bass"),
    ("Piano", "piano"),
    ("Timpani", "timpani"),
    ("Timbales", "timpani"),
    ("Concert Snare Drum", "snare_drum"),
    ("Caja", "snare_drum"),
    ("Concert Bass Drum", "bass_drum"),
    ("Bombo", "bass_drum"),
    ("Crash Cymbal", "crash_cymbals"),
    ("Platos", "crash_cymbals"),
    ("Suspended Cymbal", "suspended_cymbal"),
    ("Drumset", "drum_set"),
    ("Batería", "drum_set"),
    ("Tambourine", "tambourine"),
    ("Pandereta", "tambourine"),
    ("Triangle", "triangle"),
    ("Glockenspiel", "glockenspiel"),
    ("Xylophone", "xylophone"),
    ("Xilófono", "xylophone"),
    ("Marimba", "marimba"),
    ("Chimes", "chimes"),
    ("Campanas tubulares", "chimes"),
])
def test_aliases_resolve_to_one_canonical_identity(name, canonical_id):
    match = match_instrument_name(name)
    assert match.identity is not None, name
    assert match.identity.canonical_id == canonical_id


@pytest.mark.parametrize("name, canonical_id", [
    ("Fl.", "flute"),
    ("Picc.", "piccolo"),
    ("Cl.", "clarinet.bb"),
    ("B. Cl.", "clarinet.bass"),
    ("A. Sax.", "saxophone.alto"),
    ("Tpt.", "trumpet.bb"),
    ("Hn.", "horn.f"),
    ("Tbn.", "trombone.tenor"),
    ("Euph.", "euphonium"),
    ("Timp.", "timpani"),
])
def test_common_abbreviations(name, canonical_id):
    assert match_instrument_name(name).identity.canonical_id == canonical_id


@pytest.mark.parametrize("name, not_expected", [
    ("English Horn", "horn.f"),
    ("Corno inglés", "horn.f"),
    ("Bass Clarinet", "clarinet.bb"),
    ("Alto Clarinet", "clarinet.bb"),
    ("Contrabassoon", "bassoon"),
    ("Cornet", "trumpet.bb"),
    ("Flugelhorn", "trumpet.bb"),
    ("Baritone Horn", "saxophone.baritone"),
    ("Bass Trombone", "trombone.tenor"),
    ("Bass Drum", "double_bass"),
])
def test_specific_instruments_never_collapse_into_generic_ones(name, not_expected):
    assert match_instrument_name(name).identity.canonical_id != not_expected


@pytest.mark.parametrize("name, canonical_id, part_numbers", [
    ("B♭ Clarinet 2", "clarinet.bb", (2,)),
    ("Clarinete 3", "clarinet.bb", (3,)),
    ("Trumpet II", "trumpet.bb", (2,)),
    ("1st Trumpet", "trumpet.bb", (1,)),
    ("2nd B♭ Clarinet", "clarinet.bb", (2,)),
    ("F Horn 1 & 2", "horn.f", (1, 2)),
    ("F Horn 3 &amp; 4", "horn.f", (3, 4)),
    ("Flute 1/2", "flute", (1, 2)),
    ("Bassoon", "bassoon", ()),
    # A third trombone part is a tenor trombone unless the score says bass trombone.
    ("Trombone 3", "trombone.tenor", (3,)),
])
def test_part_numbers_are_kept_apart_from_the_identity(name, canonical_id, part_numbers):
    match = match_instrument_name(name)
    assert match.identity.canonical_id == canonical_id
    assert match.part_numbers == part_numbers


@pytest.mark.parametrize("name", [
    "Voice", "Voice 3", "Part 1", "Instrument", "Percussion", "Bajo",
    "Solo", "", "   ", "Trombone 3 & Bass Trombone", "Glass Harmonica",
])
def test_generic_ambiguous_or_unknown_names_stay_unknown(name):
    match = match_instrument_name(name)
    assert match.identity is None
    assert match.source == UNKNOWN
    assert match.original_name == name


def test_match_keeps_the_original_name_and_reports_the_alias_used():
    match = match_instrument_name("  Clarinete  en SI BEMOL 2 ")
    assert match.original_name == "  Clarinete  en SI BEMOL 2 "
    assert match.matched_alias == "clarinete en si bemol"
    assert match.source == "ALIAS"
    assert match.part_numbers == (2,)


def test_normalization_unifies_flats_case_accents_and_spacing_without_dropping_tunings():
    assert normalize_instrument_name("B♭ Clarinet") == "bb clarinet"
    assert normalize_instrument_name("B-flat  Clarinet") == "bb clarinet"
    assert normalize_instrument_name("E flat Clarinet") == "eb clarinet"
    assert normalize_instrument_name("Saxofón Barítono") == "saxofon baritono"
    assert normalize_instrument_name("Clarinet in A") == "clarinet in a"


def test_identity_keeps_variant_transposition_and_labels():
    bass_clarinet = match_instrument_name("Bass Clarinet").identity
    assert bass_clarinet.section == "woodwinds"
    assert bass_clarinet.family == "clarinet"
    assert bass_clarinet.variant == "bass"
    assert bass_clarinet.transposition == "Bb"
    assert bass_clarinet.label_es == "Clarinete bajo"
    assert bass_clarinet.label_en == "Bass Clarinet"
    assert match_instrument_name("Horn in F").identity.transposition == "F"
    assert match_instrument_name("Flute").identity.transposition is None


def test_catalog_integrity():
    entries = catalog_entries()
    assert len(entries) >= 40, "covers the usual concert band instrumentation"
    ids = [entry.canonical_id for entry in entries]
    assert len(ids) == len(set(ids)), "canonical ids are unique"
    sections = {"woodwinds", "brass", "strings", "percussion", "keyboard", "rhythm"}
    seen = {}
    for entry in entries:
        assert entry.section in sections, entry.canonical_id
        assert entry.label_es and entry.label_en, entry.canonical_id
        for alias in entry.aliases:
            assert alias == normalize_instrument_name(alias), "aliases are stored normalized: " + alias
            assert alias not in seen, "alias {} used by {} and {}".format(alias, seen.get(alias), entry.canonical_id)
            seen[alias] = entry.canonical_id


@pytest.mark.parametrize("name, canonical_id", [
    ("5-str. Electric Bass", "electric_bass"),
    ("Bajo eléctrico", "electric_bass"),
    ("Electric Guitar", "guitar.electric"),
    ("Guitarra eléctrica", "guitar.electric"),
    ("Acoustic Guitar", "guitar.acoustic"),
    ("Guitarra acústica", "guitar.acoustic"),
])
def test_rhythm_section_instruments(name, canonical_id):
    identity = match_instrument_name(name).identity
    assert identity.canonical_id == canonical_id
    assert identity.section == "rhythm"


def test_unqualified_guitar_stays_unknown_and_drum_set_stays_in_percussion():
    assert match_instrument_name("Guitar").identity is None
    assert match_instrument_name("Guitarra").identity is None
    assert match_instrument_name("Drumset").identity.section == "percussion"


@pytest.mark.parametrize("name, group", [
    ("Piccolo", "flutes"), ("Flute", "flutes"),
    ("Oboe", "double_reeds"), ("English Horn", "double_reeds"),
    ("E♭ Clarinet", "clarinets"), ("B♭ Clarinet", "clarinets"), ("Alto Clarinet", "clarinets"),
    ("Soprano Saxophone", "saxophones"), ("Alto Sax", "saxophones"), ("Tenor Saxophone", "saxophones"),
    ("Trumpet", "high_brass"), ("Cornet", "high_brass"), ("Flugelhorn", "high_brass"), ("Horn in F", "high_brass"),
    # Decided then: woodwind basses rehearse with the low brass.
    ("Trombone", "low_voices"), ("Bass Trombone", "low_voices"), ("Euphonium", "low_voices"), ("Tuba", "low_voices"),
    ("Bassoon", "low_voices"), ("Bass Clarinet", "low_voices"), ("Baritone Saxophone", "low_voices"),
    ("Timpani", "percussion"), ("Drumset", "percussion"), ("Xylophone", "percussion"),
    ("Double Bass", "strings_rhythm"), ("Electric Bass", "strings_rhythm"), ("Piano", "strings_rhythm"),
])
def test_every_instrument_belongs_to_a_rehearsal_group(name, group):
    assert match_instrument_name(name).identity.rehearsal_group == group


def test_all_catalog_entries_declare_a_rehearsal_group():
    groups = {"flutes", "double_reeds", "clarinets", "saxophones", "high_brass", "low_voices", "percussion", "strings_rhythm"}
    assert all(entry.rehearsal_group in groups for entry in catalog_entries())
