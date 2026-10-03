"""Capture/check the original deterministic engine on an explicit synthetic allowlist."""
import argparse
import hashlib
import json
from pathlib import Path

from backend.analyzers.difficulty import compute_difficulty_score
from backend.analyzers.instrument_difficulty import canonical_instrument_name, classify_instrument_family
from backend.analyzers.rehearsal_plan import build_rehearsal_plan
from backend.domain.models import Score, ScoreMeasure, ScoreNote, ScorePart, TempoMark
from backend.parsers.musicxml_parser import parse_musicxml
from backend.parsers.playback import build_playback

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = Path(__file__).with_name('baseline-v1.json')
FIXTURES = ('minimal.musicxml', 'high_density.musicxml', 'high_register.musicxml',
            'large_intervals.musicxml', 'measure_with_rest.musicxml')


def synthetic_case(name, pitches, bars=1, bpm=60, instrument='Clarinet'):
    notes = tuple(ScoreNote(pitch, 4 / len(pitches)) for pitch in pitches)
    part = ScorePart(instrument, tuple(ScoreMeasure(i, notes) for i in range(1, bars + 1)))
    return Score(name, (part,), (TempoMark(1, 0, bpm, 1),))


def capture():
    cases = {}
    for filename in FIXTURES:
        path = ROOT / 'test-scores' / filename
        score = parse_musicxml(path)
        cases[filename] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                           'analysis': compute_difficulty_score(score),
                           'rehearsal': build_rehearsal_plan(score, 15)}
    for bpm in (60, 160):
        name = f'stepwise-sixteenths-{bpm}'
        score = synthetic_case(name, ['C4','D4','E4','F4'] * 4, bpm=bpm)
        cases[name] = {'analysis': compute_difficulty_score(score),
                       'rehearsal': build_rehearsal_plan(score, 15)}
    for bars in (1, 8, 16):
        for instrument, pitch in [('Trumpet','C4'), ('Clarinet','C6')]:
            name = f'{instrument}-{pitch}-{bars}-bars'
            score = synthetic_case(name, [pitch], bars=bars, instrument=instrument)
            cases[name] = {'analysis': compute_difficulty_score(score),
                           'rehearsal': build_rehearsal_plan(score, 15)}
    easy = synthetic_case('sustained-slow', ['C4'])
    fast_elsewhere = Score('fast-elsewhere', easy.parts, easy.tempo_marks + (TempoMark(100, 0, 200, 1),))
    for score in (easy, fast_elsewhere):
        cases[score.title] = {'analysis': compute_difficulty_score(score)}
    names = ['Clarinete', 'Clarinete bajo', 'Trompa', 'Corno inglés', 'Saxofón alto',
             'Clarinetto', 'Voice', 'English Horn', 'Horn in F', 'Bass Clarinet']
    instruments = {name: {'canonical': canonical_instrument_name(name),
                          'family': classify_instrument_family(name)} for name in names}
    audio = build_playback(ROOT / 'test-scores' / 'minimal.musicxml', '', 0, 999999)
    return {'baseline_version': 'baseline-v1', 'algorithm_version': 'legacy-v1',
            'grade_scale': '1-5', 'technical_index_scale': '0-5',
            'human_labels': None, 'cases': cases, 'instruments': instruments, 'audio': audio}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update', action='store_true', help='Explicitly regenerate the recorded baseline')
    args = parser.parse_args()
    current = capture()
    if args.update:
        SNAPSHOT.write_text(json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
        print(f'Recorded {len(current["cases"])} cases in {SNAPSHOT.name}')
    else:
        expected = json.loads(SNAPSHOT.read_text())
        if current != expected:
            raise SystemExit('Baseline differs. Investigate before explicitly regenerating the snapshot.')
        print(f'Baseline matches: {len(current["cases"])} cases, {len(current["instruments"])} names and audio events')


if __name__ == '__main__':
    main()
