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
    # «Percussion» is a part of several instruments since 2026-11-02 (test_percussion_parts.py), no longer unknown.
    "Voice", "Voice 3", "Part 1", "Instrument", "Bajo",
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
    assert match.matched_alias == "clarinete kbb", "the key is read into one token (2026-10-28)"
    assert match.source == "ALIAS"
    assert match.part_numbers == (2,)


def test_normalization_unifies_flats_case_accents_and_spacing_without_dropping_tunings():
    # 2026-10-28: every spelling of the key becomes one token at the end of the name.
    assert normalize_instrument_name("B♭ Clarinet") == "clarinet kbb"
    assert normalize_instrument_name("B-flat  Clarinet") == "clarinet kbb"
    assert normalize_instrument_name("E flat Clarinet") == "clarinet keb"
    assert normalize_instrument_name("Saxofón Barítono") == "saxofon baritono"
    assert normalize_instrument_name("Clarinet in A") == "clarinet ka"
    assert normalize_instrument_name("Clarinete en Si bemol") == normalize_instrument_name("Klarinette in B") \
        .replace("klarinette", "clarinete")


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
            # Aliases are written as scores print them; what must never happen is one name for two instruments.
            key = normalize_instrument_name(alias)
            assert seen.get(key, entry.canonical_id) == entry.canonical_id, \
                "alias {} used by {} and {}".format(alias, seen.get(key), entry.canonical_id)
            seen[key] = entry.canonical_id


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


# «Arabian Dances» (2026-11-20): three of its parts had no instrument and played as a piano.
@pytest.mark.parametrize("name, canonical_id", [
    ("E♭ Contra Alto Clarinet", "clarinet.contra_alto"),
    ("Eb Contra-Alto Clarinet", "clarinet.contra_alto"),
    ("C.A. Cl.", "clarinet.contra_alto"),
    ("Clarinete contraalto", "clarinet.contra_alto"),
    ("Baritone/ Euphonium", "euphonium"),
    ("Baritone T.C.", "euphonium"),
    ("Baritone B.C.", "euphonium"),
    ("Baritone", "saxophone.baritone"),
])
def test_the_names_of_the_band_parts_of_arabian_dances(name, canonical_id):
    assert match_instrument_name(name).identity.canonical_id == canonical_id


def test_the_contra_alto_clarinet_sounds_an_octave_and_a_major_sixth_below():
    from backend.domain.instrument_transposition import instrument_shift
    assert instrument_shift("clarinet.contra_alto") == -21


# The basses of brass bands and European editions (2026-11-21): «T.C.» says the clef, not the instrument.
@pytest.mark.parametrize("name, canonical_id", [
    ("Tuba in Eb (T.C.)", "tuba"),
    ("Tuba in B♭ (T.C.)", "tuba"),
    ("Eb Bass", "tuba"),
    ("BBb Bass", "tuba"),
    ("Es-Bass", "tuba"),
    ("Euphonium T.C.", "euphonium"),
    ("Bass", None),
])
def test_the_basses_of_brass_bands_and_parts_marked_with_their_clef(name, canonical_id):
    found = match_instrument_name(name).identity
    assert (found.canonical_id if found else None) == canonical_id


def test_the_key_a_name_writes():
    from backend.domain.instrument_catalog import written_key
    assert [written_key(name) for name in ("Tuba in E♭ (T.C.)", "Bb Bass", "Tuba")] == ["eb", "bb", None]


# Spanish parts write the number between the instrument and its key (2026-11-21): «Trompa 1ª en Fa», «Clarinete 1 Sib».
@pytest.mark.parametrize("name, canonical_id, part_numbers", [
    ("Trompa 1ª en Fa", "horn.f", (1,)),
    ("Clarinete 1 Sib", "clarinet.bb", (1,)),
    ("Horn 1 in F", "horn.f", (1,)),
    ("Trumpet 2 in Bb", "trumpet.bb", (2,)),
    ("Saxo Alto 1 Mib", "saxophone.alto", (1,)),
    ("Bombardino 1 Sib", "euphonium", (1,)),
    ("Fliscorno 1º", "flugelhorn.bb", (1,)),
    ("Trompas 3 y 4 en Fa", "horn.f", (3, 4)),
    ("Trompa en Fa 1", "horn.f", (1,)),
])
def test_the_number_of_a_part_before_its_key(name, canonical_id, part_numbers):
    match = match_instrument_name(name)
    assert (match.identity.canonical_id if match.identity else None, match.part_numbers) == (canonical_id, part_numbers)


# The frequent band names the catalog did not know (2026-11-21, review of band instrumentation against the catalog).
@pytest.mark.parametrize("name, canonical_id", [
    # Brass: horn in E♭, the British tenor horn, the E♭ soprano cornet and the places of the brass band cornets.
    ("Horn in E♭", "horn.eb"), ("Trompa en Mib", "horn.eb"), ("1st Eb Horn", "horn.eb"),
    ("E♭ Tenor Horn", "alto_horn"), ("Solo Horn", "alto_horn"), ("Althorn", "alto_horn"), ("Alto Horn", "alto_horn"),
    ("Tenorhorn", "baritone_horn"),
    ("Soprano Cornet", "cornet.eb"), ("E♭ Soprano Cornet", "cornet.eb"),
    ("Solo Cornet", "cornet.bb"), ("Repiano Cornet", "cornet.bb"),
    # Woodwinds.
    ("B♭ Contra Bass Clarinet", "clarinet.contrabass"), ("Piccolo Clarinet (E♭)", "clarinet.eb"),
    ("Bass Saxophone", "saxophone.bass"), ("Saxofón bajo", "saxophone.bass"),
    # Abbreviations of the percussion, strings and keyboards the catalog has.
    ("Glsp.", "glockenspiel"), ("Xyl.", "xylophone"), ("Pk.", "timpani"), ("Kettledrums", "timpani"),
    ("S.D.", "snare_drum"), ("Field Drum", "snare_drum"), ("B.D.", "bass_drum"), ("Susp. Cym.", "suspended_cymbal"),
    ("Cym.", "crash_cymbals"), ("Tri.", "triangle"), ("Hp.", "harp"), ("D.B.", "double_bass"), ("Str. Bass", "double_bass"),
    ("Bass Gtr.", "electric_bass"),
    # Parts of mallets: they sound as a xylophone.
    ("Mallet Percussion", "xylophone"), ("Mallets", "xylophone"), ("Keyboard Percussion", "xylophone"),
    ("Auxiliary Percussion", "percussion"),
    # The usual percussion of a band.
    ("Wood Block", "wood_block"), ("Caja china", "wood_block"), ("Temple Blocks", "temple_blocks"),
    ("Tam-tam", "tam_tam"), ("Gong", "tam_tam"), ("Toms", "toms"), ("Tenor Drum", "tenor_drum"),
    ("Hi-Hat", "hi_hat"), ("Charles", "hi_hat"), ("Finger Cymbals", "finger_cymbals"), ("Castanets", "castanets"),
    ("Castañuelas", "castanets"), ("Claves", "claves"), ("Maracas", "maracas"), ("Guiro", "guiro"), ("Cowbell", "cowbell"),
    ("Cencerro", "cowbell"), ("Cabasa", "cabasa"), ("Shaker", "shaker"), ("Bongos", "bongos"), ("Congas", "congas"),
    ("Vibraslap", "vibraslap"), ("Whistle", "whistle"), ("Sleigh Bells", "sleigh_bells"), ("Mark Tree", "wind_chimes"),
    ("Wind Chimes", "wind_chimes"), ("Whip", "whip"), ("Slapstick", "whip"), ("Ratchet", "ratchet"), ("Carraca", "ratchet"),
    ("Crotales", "crotales"), ("Celesta", "celesta"),
])
def test_the_frequent_names_of_band_parts(name, canonical_id):
    found = match_instrument_name(name).identity
    assert (found.canonical_id if found else None) == canonical_id


def test_a_part_of_several_new_percussion_instruments_is_one_percussion_part():
    assert match_instrument_name("Percussion 2 (Wood Block, Tam-tam, Castanets)").identity.canonical_id == "percussion"


@pytest.mark.parametrize("canonical_id, semitones", [
    ("horn.eb", -9), ("alto_horn", -9), ("cornet.eb", 3), ("saxophone.bass", -26), ("crotales", 24), ("celesta", 12),
])
def test_the_new_instruments_sound_where_they_should(canonical_id, semitones):
    from backend.domain.instrument_transposition import instrument_shift
    assert instrument_shift(canonical_id) == semitones
