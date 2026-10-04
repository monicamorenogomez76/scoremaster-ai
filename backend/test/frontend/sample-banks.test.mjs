import test from 'node:test';
import assert from 'node:assert/strict';
import { RECORDED_BASE_URL, recordedPreset, sampleMidi } from '../../../frontend/src/score/sample-banks.js';

const regions = preset => preset.groups.flatMap(group => group.regions);

test('sample file names map to MIDI numbers, sharps written as "s"', () => {
  assert.equal(sampleMidi('C4'), 60);
  assert.equal(sampleMidi('As3'), 58);
  assert.equal(sampleMidi('Fs6'), 90);
});

test('the preset maps the nearest recordings to the notes of the part, splitting the keyboard between them', () => {
  // Clarinet recordings include D4 (62), F4 (65) and A#4 (70).
  const preset = recordedPreset('clarinet', [61, 62, 66, 69]);
  assert.deepEqual(preset.samples, { baseUrl: RECORDED_BASE_URL + 'clarinet/', formats: ['mp3'] });
  assert.deepEqual(regions(preset), [
    { sample: 'D4', pitch: 62, keyRange: [0, 63] },
    { sample: 'F4', pitch: 65, keyRange: [64, 67] },
    { sample: 'As4', pitch: 70, keyRange: [68, 127] },
  ]);
});

test('every note of the part falls in the region of its nearest recording', () => {
  const notes = [52, 58, 61, 67, 74, 80];
  for (const note of notes) {
    const region = regions(recordedPreset('trumpet', notes)).find(r => r.keyRange[0] <= note && note <= r.keyRange[1]);
    assert.ok(region, String(note));
  }
});

test('recordings come from a pinned commit so the sound never changes silently', () => {
  assert.match(RECORDED_BASE_URL, /^https:\/\/cdn\.jsdelivr\.net\/gh\/nbrosowsky\/tonejs-instruments@[0-9a-f]{40}\/samples\/$/);
});

test('band instruments with real recordings, and General MIDI for the rest', () => {
  for (const sound of ['bassoon', 'clarinet', 'flute', 'french_horn', 'alto_sax', 'tenor_sax', 'trombone', 'trumpet', 'tuba', 'contrabass']) {
    assert.ok(recordedPreset(sound, [60]), sound);
  }
  for (const sound of ['piccolo', 'oboe', 'english_horn', 'soprano_sax', 'baritone_sax', 'glockenspiel', 'timpani']) {
    assert.equal(recordedPreset(sound, [60]), null, sound);
  }
});

test('a part without notes downloads nothing', () => {
  assert.deepEqual(regions(recordedPreset('flute', [])), []);
});
