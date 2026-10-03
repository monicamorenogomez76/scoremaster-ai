"""Part metadata kept by the parser exactly as the MusicXML declares it (step 07)."""
import pytest

from backend.domain.models import PartMetadata, PartTransposition, ScorePart
from backend.parsers.musicxml_parser import parse_musicxml

NOTE = "<note><pitch><step>C</step><octave>5</octave></pitch><duration>4</duration><type>whole</type></note>"


def write_score(tmp_path, part_list, parts, name="metadata.musicxml"):
    path = tmp_path / name
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<score-partwise version="4.0">'
                    "<part-list>" + part_list + "</part-list>" + parts + "</score-partwise>", encoding="utf-8")
    return path


def measure(attributes="", content=NOTE, number=1):
    return '<measure number="{}"><attributes><divisions>1</divisions>{}</attributes>{}</measure>'.format(
        number, attributes, content)


def test_keeps_declared_instrument_metadata_and_transposition(tmp_path):
    path = write_score(tmp_path,
        '<score-part id="P1"><part-name>B♭ Clarinet 1</part-name><part-abbreviation>Cl. 1</part-abbreviation>'
        '<score-instrument id="P1-I1"><instrument-name>B♭ Clarinet</instrument-name>'
        "<instrument-sound>wind.reed.clarinet.bflat</instrument-sound></score-instrument>"
        '<midi-instrument id="P1-I1"><midi-channel>2</midi-channel><midi-program>72</midi-program></midi-instrument></score-part>',
        '<part id="P1">' + measure("<transpose><diatonic>-1</diatonic><chromatic>-2</chromatic></transpose>") + "</part>")

    part = parse_musicxml(path).parts[0]

    assert part.name == "B♭ Clarinet 1"
    assert part.metadata == PartMetadata(
        part_id="P1",
        part_name="B♭ Clarinet 1",
        part_abbreviation="Cl. 1",
        instrument_names=("B♭ Clarinet",),
        instrument_sounds=("wind.reed.clarinet.bflat",),
        midi_programs=(72,),
        midi_channels=(2,),
        transposition=PartTransposition(chromatic=-2, diatonic=-1, octave_change=0),
        staff_number=None,
    )


def test_octave_change_is_part_of_the_transposition(tmp_path):
    path = write_score(tmp_path,
        '<score-part id="P1"><part-name>Tenor Saxophone</part-name></score-part>',
        '<part id="P1">' + measure("<transpose><diatonic>-1</diatonic><chromatic>-2</chromatic>"
                                   "<octave-change>-1</octave-change></transpose>") + "</part>")

    assert parse_musicxml(path).parts[0].metadata.transposition == PartTransposition(-2, -1, -1)


def test_part_without_metadata_has_empty_fields(tmp_path):
    path = write_score(tmp_path, '<score-part id="P1"><part-name>Flute</part-name></score-part>',
                       '<part id="P1">' + measure() + "</part>")

    metadata = parse_musicxml(path).parts[0].metadata

    assert metadata.part_id == "P1"
    assert metadata.part_name == "Flute"
    assert metadata.part_abbreviation is None
    assert metadata.instrument_names == ()
    assert metadata.midi_programs == ()
    assert metadata.transposition is None


def test_parts_sharing_a_name_keep_their_own_metadata(tmp_path):
    def voice(part_id, instrument, channel, program):
        return ('<score-part id="{0}"><part-name>Voice</part-name><score-instrument id="{0}-I1">'
                "<instrument-name>{1}</instrument-name></score-instrument>"
                '<midi-instrument id="{0}-I1"><midi-channel>{2}</midi-channel><midi-program>{3}</midi-program>'
                "</midi-instrument></score-part>").format(part_id, instrument, channel, program)
    path = write_score(tmp_path, voice("P1", "Voice Oohs", 1, 54) + voice("P2", "Acoustic_Bass_Drum", 10, 1),
                       '<part id="P1">' + measure() + '</part><part id="P2">' + measure() + "</part>")

    parts = parse_musicxml(path).parts

    assert [part.name for part in parts] == ["Voice 1", "Voice 2"]
    assert [part.metadata.part_name for part in parts] == ["Voice", "Voice"]
    assert [part.metadata.instrument_names for part in parts] == [("Voice Oohs",), ("Acoustic_Bass_Drum",)]
    assert [part.metadata.midi_channels for part in parts] == [(1,), (10,)]


def test_multi_staff_parts_share_metadata_and_keep_their_staff_number(tmp_path):
    two_staves = ("<staves>2</staves><clef number=\"1\"><sign>G</sign><line>2</line></clef>"
                  "<clef number=\"2\"><sign>F</sign><line>4</line></clef>")
    notes = NOTE.replace("</note>", "<staff>1</staff></note>") + "<backup><duration>4</duration></backup>" + \
        NOTE.replace("<octave>5</octave>", "<octave>3</octave>").replace("</note>", "<staff>2</staff></note>")
    path = write_score(tmp_path,
        '<score-part id="P1"><part-name>Piano</part-name><score-instrument id="P1-I1">'
        "<instrument-name>Acoustic Grand Piano</instrument-name></score-instrument></score-part>",
        '<part id="P1">' + measure(two_staves, notes) + "</part>")

    parts = parse_musicxml(path).parts

    assert len(parts) == 2
    assert [part.metadata.part_id for part in parts] == ["P1", "P1"]
    assert [part.metadata.staff_number for part in parts] == [1, 2]
    assert all(part.metadata.instrument_names == ("Acoustic Grand Piano",) for part in parts)


def test_part_names_collapse_whitespace_but_keep_their_text(tmp_path):
    path = write_score(tmp_path,
        '<score-part id="P1"><part-name>Trombone 3 &amp;\n  Bass Trombone</part-name></score-part>',
        '<part id="P1">' + measure() + "</part>")

    assert parse_musicxml(path).parts[0].metadata.part_name == "Trombone 3 & Bass Trombone"


def test_score_parts_built_without_metadata_remain_valid():
    part = ScorePart("Clarinet", ())

    assert part.metadata == PartMetadata()


def test_rejects_entity_declarations(tmp_path):
    path = tmp_path / "entities.musicxml"
    path.write_text('<?xml version="1.0"?><!DOCTYPE score-partwise [<!ENTITY a "aaaa">]>'
                    '<score-partwise version="4.0"><part-list><score-part id="P1"><part-name>&a;</part-name>'
                    '</score-part></part-list><part id="P1">' + measure() + "</part></score-partwise>", encoding="utf-8")

    with pytest.raises(ValueError):
        parse_musicxml(path)


def test_reads_metadata_and_rejects_entities_inside_compressed_mxl(tmp_path):
    import zipfile

    def mxl(name, score_xml):
        path = tmp_path / name
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("META-INF/container.xml", '<?xml version="1.0"?><container><rootfiles>'
                             '<rootfile full-path="score.musicxml"/></rootfiles></container>')
            archive.writestr("score.musicxml", score_xml)
        return path

    body = ('<score-partwise version="4.0"><part-list><score-part id="P1"><part-name>Oboe</part-name>'
            '</score-part></part-list><part id="P1">' + measure() + "</part></score-partwise>")
    assert parse_musicxml(mxl("oboe.mxl", '<?xml version="1.0"?>' + body)).parts[0].metadata.part_id == "P1"
    with pytest.raises(ValueError):
        parse_musicxml(mxl("entity.mxl", '<?xml version="1.0"?><!DOCTYPE score-partwise [<!ENTITY a "a">]>' + body))


def test_compressed_score_is_parsed_whatever_its_file_extension(tmp_path):
    import shutil
    compressed = tmp_path / "compressed.mxl"
    import zipfile
    with zipfile.ZipFile(compressed, "w") as archive:
        archive.writestr("META-INF/container.xml", '<?xml version="1.0"?><container><rootfiles>'
                         '<rootfile full-path="score.musicxml"/></rootfiles></container>')
        archive.writestr("score.musicxml", '<?xml version="1.0"?><score-partwise version="4.0"><part-list>'
                         '<score-part id="P1"><part-name>Oboe</part-name></score-part></part-list><part id="P1">'
                         + measure() + "</part></score-partwise>")
    misnamed = tmp_path / "compressed-but-named.musicxml"
    shutil.copy(compressed, misnamed)

    assert [part.name for part in parse_musicxml(misnamed).parts] == ["Oboe"]
