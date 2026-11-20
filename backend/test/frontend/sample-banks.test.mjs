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
  assert.deepEqual(regions(preset).map(({ sample, pitch, keyRange }) => ({ sample, pitch, keyRange })), [
    { sample: 'D4', pitch: 62, keyRange: [0, 63] },
    { sample: 'F4', pitch: 65, keyRange: [64, 67] },
    { sample: 'As4', pitch: 70, keyRange: [68, 127] },
  ]);
});

// A natural attack (2026-11-20): many recordings swell for a while before they sound full (the low D of the clarinet
// takes 0.43 s, some trombone notes 0.8 s), so a crotchet was only that soft start. Each note starts where its recording
// already sounds full, with a short fade in so it does not click; a recording that starts at once is left as it is.
test('a recording that swells slowly starts where it already sounds full', () => {
  const low = regions(recordedPreset('clarinet', [50])).find(region => region.sample === 'D3');
  assert.equal(low.offset, .43);
  assert.ok(low.ampAttack > 0 && low.ampAttack <= .02);
  const trombone = regions(recordedPreset('trombone', [48])).find(region => region.sample === 'C3');
  assert.ok(trombone.offset > .5);
});

test('a recording that sounds at once keeps its own start', () => {
  for (const [sound, note] of [['acoustic_grand_piano', 60], ['xylophone', 72], ['trumpet', 60]]) {
    const [region] = regions(recordedPreset(sound, [note]));
    assert.equal(region.offset, undefined, sound);
    assert.equal(region.ampAttack, undefined, sound);
  }
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

// Balance (2026-10-14): in a block of several voices the piccolo and the oboe were not heard. Measured
// on the player's real output, the General MIDI sounds sat 4-6 dB under the recordings, so each sound
// gets the gain that brings it to the common level.
const db = gain => 20 * Math.log10(gain);

test('every sound plays near the same level: the piccolo and the oboe sat 4-6 dB under the rest', async () => {
  const { LEVEL_TARGET_DB, voiceGain } = await import('../../../frontend/src/score/sample-banks.js');
  const measured = [['flute', true, -22.7], ['clarinet', true, -20.6], ['trumpet', true, -26.0], ['tuba', true, -23.9],
    ['piccolo', false, -27.6], ['oboe', false, -30.1], ['baritone_sax', false, -27.6], ['timpani', false, -27.9], ['clarinet', false, -25.3]];
  for (const [sound, recorded, level] of measured) {
    assert.ok(Math.abs(level + db(voiceGain(sound, recorded)) - LEVEL_TARGET_DB) < 0.05, sound);
  }
  assert.ok(db(voiceGain('oboe', false)) > 6 && db(voiceGain('piccolo', false)) > 3.5, 'the oboe and the piccolo rise');
  assert.ok(db(voiceGain('clarinet', true)) < 0, 'a loud recording is lowered');
});

test('a sound never rises more than 12 dB, and an unmeasured soundfont rises like the others', async () => {
  const { voiceGain } = await import('../../../frontend/src/score/sample-banks.js');
  assert.ok(Math.abs(db(voiceGain('glockenspiel', false)) - 12) < 1e-9, 'measured at -39.5 dB: limited');
  assert.ok(Math.abs(db(voiceGain('violin', false)) - 4) < 1e-9, 'not measured: the usual 4 dB of the soundfont');
  assert.equal(voiceGain('violin', true), 1, 'an unmeasured recording keeps its level');
});

test('parts that share a sound weigh less each, so a section does not cover a single voice', async () => {
  const { voiceGain } = await import('../../../frontend/src/score/sample-banks.js');
  assert.ok(Math.abs(voiceGain('clarinet', true, 3) - voiceGain('clarinet', true) / Math.sqrt(3)) < 1e-12);
  assert.equal(voiceGain('flute', true, 0), voiceGain('flute', true));
});
