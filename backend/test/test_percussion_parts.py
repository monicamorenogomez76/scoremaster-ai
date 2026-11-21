"""Percussion parts that play several instruments (2026-11-02, «Arabian Dances»: «Percussion 1» is marimba, low tom,
finger cymbals and suspended cymbal; «Percussion 2», for two players, suspended cymbal, frame drum and bongos). The
catalog has a generic percussion, the MusicXML declares the instruments of each part and its players (a
<score-instrument> each, a <player> each, MusicXML 4.0), BandFit counts those players and the part sounds as
percussion, never on the piano the browser falls back to."""
from backend.analyzers.band_fit import compute_band_fit
from backend.domain.instrument_catalog import match_instrument_name
from backend.domain.instrument_resolver import RESOLVED, resolve_part
from backend.domain.models import PartMetadata, Score, ScoreMeasure, ScoreNote, ScorePart


def _part(name, players=None, instruments=(), pitches=("C5",)):
    notes = tuple(ScoreNote(pitch, 1.0, offset_quarters=float(index)) for index, pitch in enumerate(pitches))
    return ScorePart(name, (ScoreMeasure(1, notes),),
                     PartMetadata(part_id=name, part_name=name, instrument_names=tuple(instruments), players=players))


def test_a_percussion_part_is_known_in_any_language():
    for name in ("Percussion 1", "Perc. 2", "Percusión", "Percussió 3", "Percussioni", "Schlagwerk"):
        identity = match_instrument_name(name).identity
        assert identity is not None and identity.canonical_id == "percussion", name
        assert identity.section == "percussion" and identity.sound is None
    assert match_instrument_name("Percussion 2").part_numbers == (2,)


def test_the_instruments_it_declares_agree_with_a_percussion_part():
    part = _part("Percussion 2", instruments=("Suspended Cymbal", "Frame Drum", "Bongos"))
    resolution = resolve_part(part)
    assert (resolution.status, resolution.identity.canonical_id) == (RESOLVED, "percussion")
    assert resolve_part(_part("Trumpet 1", instruments=("Suspended Cymbal",))).status != RESOLVED, \
        "only a percussion part takes percussion instruments as agreement"


def test_bandfit_counts_the_players_a_percussion_part_declares():
    score = Score("Obra", (_part("Timpani", players=1), _part("Percussion 1", players=1), _part("Percussion 2", players=2),
                           _part("Percussion 3", players=2), _part("Percussion 4", players=2), _part("Caja")))
    [percussion] = [item for item in compute_band_fit(score, {"percussion": 4})["requirements"] if item["key"] == "percussion"]
    assert percussion["required"] == 9, "1 + 1 + 2 + 2 + 2, and one for the snare drum that says nothing"


def test_the_players_and_instruments_are_read_from_the_musicxml():
    from backend.parsers.musicxml_parser import read_part_metadata
    content = b"""<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0"><part-list>
      <score-part id="P1"><part-name>Percussion 2</part-name>
        <score-instrument id="P1-I1"><instrument-name>Suspended Cymbal</instrument-name></score-instrument>
        <score-instrument id="P1-I2"><instrument-name>Frame Drum</instrument-name></score-instrument>
        <player id="P1-M1"><player-name>Percussion 2 (1)</player-name></player>
        <player id="P1-M2"><player-name>Percussion 2 (2)</player-name></player>
      </score-part><score-part id="P2"><part-name>Flute</part-name></score-part></part-list>
      <part id="P1"/><part id="P2"/></score-partwise>"""
    metadata = read_part_metadata(content)
    assert (metadata["P1"].players, metadata["P1"].instrument_names) == (2, ("Suspended Cymbal", "Frame Drum"))
    assert metadata["P2"].players is None


def test_the_kept_model_keeps_the_players():
    from backend.parsers.score_codec import decode_score, encode_score
    score = Score("Obra", (_part("Percussion 2", players=2),))
    assert decode_score(encode_score(score)).parts[0].metadata.players == 2


def test_a_percussion_part_written_with_pitches_sounds_as_drums(tmp_path):
    from music21 import meter, note, stream
    from backend.parsers.playback import build_playback
    score = stream.Score()
    part = stream.Part()
    part.partName = "Percussion 1"
    measure = stream.Measure(number=1)
    measure.append(meter.TimeSignature("2/4"))
    for written in ("F4", "C5"):
        measure.append(note.Note(written, quarterLength=1))
    part.append(measure)
    score.insert(0, part)
    path = tmp_path / "percusion.musicxml"
    score.write("musicxml", fp=path)
    [track] = build_playback(path, "", 0, 999999)["tracks"]
    assert track["events"] == [] and [hit["note"] for hit in track["percussion"]] == [36, 38], \
        "bass drum low, snare drum in the middle, as in drum notation"


def test_a_database_created_before_gets_the_generic_percussion(postgres_engine):
    """Render's and Neon's catalog was created on 2026-10-28: the migration adds the instrument where it is missing."""
    import sqlalchemy as sa
    from backend.domain.instrument_catalog import normalize_instrument_name, seed_instruments
    [item] = [entry for entry in seed_instruments() if entry["id"] == "percussion"]
    names = len({normalize_instrument_name(alias) for alias in item["aliases"]})
    from alembic import command
    from alembic.config import Config
    with postgres_engine.begin() as connection:
        assert connection.execute(sa.text("SELECT count(*) FROM instruments WHERE id = 'percussion'")).scalar() == 1
        assert connection.execute(sa.text("SELECT count(*) FROM instrument_names WHERE instrument_id = 'percussion'")).scalar() == names
        connection.execute(sa.text("DELETE FROM instruments WHERE id = 'percussion'"))
        connection.execute(sa.text("UPDATE alembic_version SET version_num = '0018_email_verification'"))
    with postgres_engine.begin() as connection:
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.upgrade(config, "0019_generic_percussion")
        assert connection.execute(sa.text("SELECT count(*) FROM instrument_names WHERE instrument_id = 'percussion'")).scalar() == names
        command.upgrade(config, "0019_generic_percussion")   # nothing twice
        assert connection.execute(sa.text("SELECT count(*) FROM instruments WHERE id = 'percussion'")).scalar() == 1


def test_a_database_created_before_gets_the_contra_alto_clarinet_and_the_names_of_the_euphonium(postgres_engine):
    """«Arabian Dances» (2026-11-20): its contra-alto clarinet and baritone parts played as a piano."""
    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config
    from backend.domain.instrument_catalog import normalize_instrument_name
    key = normalize_instrument_name("Baritone T.C.")
    with postgres_engine.begin() as connection:
        connection.execute(sa.text("DELETE FROM instruments WHERE id = 'clarinet.contra_alto'"))
        connection.execute(sa.text("DELETE FROM instrument_names WHERE name_key = :key"), {"key": key})
        connection.execute(sa.text("UPDATE alembic_version SET version_num = '0020_pdf_imports_repaired'"))
    with postgres_engine.begin() as connection:
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        for _ in range(2):   # nothing twice
            command.upgrade(config, "0021_contra_alto_and_euphonium")
            assert connection.execute(sa.text("SELECT count(*) FROM instruments WHERE id = 'clarinet.contra_alto'")).scalar() == 1
            assert connection.execute(sa.text("SELECT instrument_id FROM instrument_names WHERE name_key = :key"),
                                      {"key": key}).scalars().all() == ["euphonium"]


def test_a_database_created_before_gets_the_names_of_the_brass_band_basses(postgres_engine):
    """«Eb Bass» and «Bb Bass» (2026-11-21) are the tubas of brass bands."""
    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config
    from backend.domain.instrument_catalog import normalize_instrument_name
    key = normalize_instrument_name("Eb Bass")
    with postgres_engine.begin() as connection:
        connection.execute(sa.text("DELETE FROM instrument_names WHERE name_key = :key"), {"key": key})
        connection.execute(sa.text("UPDATE alembic_version SET version_num = '0021_contra_alto_and_euphonium'"))
    with postgres_engine.begin() as connection:
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        for _ in range(2):   # nothing twice
            command.upgrade(config, "0022_brass_band_basses")
            assert connection.execute(sa.text("SELECT instrument_id FROM instrument_names WHERE name_key = :key"),
                                      {"key": key}).scalars().all() == ["tuba"]


def test_a_database_created_before_gets_the_frequent_band_instruments_and_names(postgres_engine):
    """2026-11-21: the tenor horn, the wood block, and abbreviations such as «Glsp.»."""
    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config
    from backend.domain.instrument_catalog import normalize_instrument_name
    keys = {name: normalize_instrument_name(name) for name in ("Glsp.", "Tenor Horn", "Wood Block")}
    with postgres_engine.begin() as connection:
        connection.execute(sa.text("DELETE FROM instruments WHERE id IN ('alto_horn', 'wood_block')"))
        connection.execute(sa.text("DELETE FROM instrument_names WHERE name_key = :key"), {"key": keys["Glsp."]})
        connection.execute(sa.text("UPDATE alembic_version SET version_num = '0022_brass_band_basses'"))
    with postgres_engine.begin() as connection:
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        for _ in range(2):   # nothing twice
            command.upgrade(config, "0023_frequent_band_names")
            found = {name: connection.execute(sa.text("SELECT instrument_id FROM instrument_names WHERE name_key = :key"),
                                              {"key": key}).scalars().all() for name, key in keys.items()}
            assert found == {"Glsp.": ["glockenspiel"], "Tenor Horn": ["alto_horn"], "Wood Block": ["wood_block"]}


def test_a_database_created_before_gets_the_names_beside_the_staves_of_a_score(postgres_engine):
    """«Fls.», «Tpts.» (2026-11-21): the abbreviations under a brace in the margin of a score."""
    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config
    from backend.domain.instrument_catalog import normalize_instrument_name
    key = normalize_instrument_name("Tpts.")
    with postgres_engine.begin() as connection:
        connection.execute(sa.text("DELETE FROM instrument_names WHERE name_key = :key"), {"key": key})
        connection.execute(sa.text("UPDATE alembic_version SET version_num = '0023_frequent_band_names'"))
    with postgres_engine.begin() as connection:
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        for _ in range(2):   # nothing twice
            command.upgrade(config, "0024_score_margin_names")
            assert connection.execute(sa.text("SELECT instrument_id FROM instrument_names WHERE name_key = :key"),
                                      {"key": key}).scalars().all() == ["trumpet.bb"]
