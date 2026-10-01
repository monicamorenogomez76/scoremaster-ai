import pytest
from fastapi.testclient import TestClient
from music21 import chord, instrument, meter, note, stream, tempo, tie

from backend.app.main import app
from backend.parsers.playback import build_playback


def make_score(tmp_path):
    score = stream.Score()
    flute = stream.Part()
    flute.partName = 'Flute'
    flute.insert(0, instrument.Flute())
    a = stream.Measure(number=1)
    a.append(meter.TimeSignature('4/4'))
    a.append(tempo.MetronomeMark(number=60))
    a.append(note.Rest(quarterLength=4))
    b = stream.Measure(number=2)
    b.append(note.Note('C5', quarterLength=2))
    b.append(chord.Chord(['E5', 'G5'], quarterLength=2))
    flute.append([a, b])
    clarinet = stream.Part()
    clarinet.partName = 'Clarinet'
    clarinet.insert(0, instrument.Clarinet())
    for number in (1, 2):
        measure = stream.Measure(number=number)
        n = note.Note('C5', quarterLength=4)
        n.tie = tie.Tie('start' if number == 1 else 'stop')
        measure.append(n)
        clarinet.append(measure)
    score.insert(0, flute)
    score.insert(0, clarinet)
    path = tmp_path / 'score.musicxml'
    score.write('musicxml', fp=path)
    return path


def test_solo_range_chords_and_tempo_from_other_part(tmp_path):
    path = make_score(tmp_path)
    result = build_playback(path, 'Flute', 2, 2)
    assert result['program'] == 73
    assert result['duration'] == 4
    assert result['events'] == [
        {'note': 72, 'time': 0, 'duration': 2},
        {'note': 76, 'time': 2, 'duration': 2},
        {'note': 79, 'time': 2, 'duration': 2},
    ]
    assert not result['default_tempo']


def test_transposition_and_tie_crossing_passage_boundary(tmp_path):
    result = build_playback(make_score(tmp_path), 'Clarinet', 2, 2)
    assert result['program'] == 71
    assert result['events'] == [{'note': 70, 'time': 0, 'duration': 4}]


def test_ties_do_not_rearticulate(tmp_path):
    result = build_playback(make_score(tmp_path), 'Clarinet', 1, 2)
    assert len(result['events']) == 1
    assert result['events'][0]['duration'] == 8


def test_endpoint_validation_and_musicxml(tmp_path):
    path = make_score(tmp_path)
    client = TestClient(app)
    def request(first=2, last=2, name='Flute', content=None):
        return client.post('/playback', data={'instrument': name, 'first_measure': first,
            'last_measure': last}, files={'file': ('score.musicxml', content or path.read_bytes())})
    assert request().status_code == 200
    assert request(3, 2).status_code == 400
    assert request(name='Missing').status_code == 400
    assert request(99, 100).status_code == 400
    assert request(content=b'<invalid/>').status_code == 400
    assert request(-1, 2).status_code == 422


def test_tempo_change_splits_note_duration(tmp_path):
    score = stream.Score()
    part = stream.Part()
    part.partName = 'Flute'
    m = stream.Measure(number=1)
    m.insert(0, tempo.MetronomeMark(number=60))
    m.insert(2, tempo.MetronomeMark(number=120))
    m.insert(0, note.Note('C5', quarterLength=4))
    part.append(m)
    score.append(part)
    path = tmp_path / 'tempo.musicxml'
    score.write('musicxml', fp=path)
    result = build_playback(path, 'Flute', 1, 1)
    assert result['events'][0]['duration'] == 3


def test_rests_and_default_tempo(tmp_path):
    score = stream.Score()
    part = stream.Part()
    part.partName = 'Flute'
    m = stream.Measure(number=1)
    m.append(note.Rest(quarterLength=2))
    m.append(note.Note('C5', quarterLength=2))
    part.append(m)
    score.append(part)
    path = tmp_path / 'rests.musicxml'
    score.write('musicxml', fp=path)
    result = build_playback(path, 'Flute', 1, 1)
    assert result['events'][0]['time'] == 1
    assert result['default_tempo']
