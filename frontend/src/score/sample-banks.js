// Real instrument recordings for playback, from tonejs-instruments (pinned commit).
// Sources per tonejs-instruments/sample-source-info.txt; see README «Créditos de sonido».
// Instruments without recordings keep the General MIDI soundfont.
export const RECORDED_BASE_URL = 'https://cdn.jsdelivr.net/gh/nbrosowsky/tonejs-instruments@622c2f1c32c8cfce4158ddc3eb26e518ddef37e5/samples/';

const RECORDED = {
  bassoon: { folder: 'bassoon', source: 'VSCO2 CE, CC0',
    notes: 'A2 A3 A4 C3 C4 C5 E4 G2 G3 G4' },
  clarinet: { folder: 'clarinet', source: 'sin fuente declarada; mismas notas que el clarinete de VSCO2 CE (CC0)',
    notes: 'As3 As4 As5 D3 D4 D5 D6 F3 F4 F5 Fs6' },
  flute: { folder: 'flute', source: 'VSCO2 CE, CC0',
    notes: 'A4 A5 A6 C4 C5 C6 C7 E4 E5 E6' },
  french_horn: { folder: 'french-horn', source: 'VSCO2 CE, CC0',
    notes: 'A1 A3 C2 C4 D3 D5 Ds2 F3 F5 G2' },
  alto_sax: { folder: 'saxophone', source: 'Karoryfer, CC0',
    notes: 'A4 A5 As3 As4 B3 B4 C4 C5 Cs3 Cs4 Cs5 D3 D4 D5 Ds3 Ds4 Ds5 E3 E4 E5 F3 F4 F5 Fs3 Fs4 Fs5 G3 G4 G5 Gs3 Gs4 Gs5' },
  tenor_sax: { folder: 'saxophone', source: 'Karoryfer, CC0',
    notes: 'A4 A5 As3 As4 B3 B4 C4 C5 Cs3 Cs4 Cs5 D3 D4 D5 Ds3 Ds4 Ds5 E3 E4 E5 F3 F4 F5 Fs3 Fs4 Fs5 G3 G4 G5 Gs3 Gs4 Gs5' },
  trombone: { folder: 'trombone', source: 'VSCO2 CE, CC0',
    notes: 'As1 As2 As3 C3 C4 Cs2 Cs4 D3 D4 Ds2 Ds3 Ds4 F2 F3 F4 Gs2 Gs3' },
  trumpet: { folder: 'trumpet', source: 'VSCO2 CE, CC0',
    notes: 'A3 A5 As4 C4 C6 D5 Ds4 F3 F4 F5 G4' },
  tuba: { folder: 'tuba', source: 'VSCO2 CE, CC0',
    notes: 'As1 As2 As3 D3 D4 Ds2 F1 F2 F3' },
  contrabass: { folder: 'contrabass', source: 'VSCO2 CE, CC0',
    notes: 'A2 As1 B3 C2 Cs3 D2 E2 E3 Fs1 Fs2 G1 Gs2 Gs3' },
  electric_bass_finger: { folder: 'bass-electric', source: 'Karoryfer, CC0',
    notes: 'As1 As2 As3 As4 Cs1 Cs2 Cs3 Cs4 Cs5 E1 E2 E3 E4 G1 G2 G3 G4' },
  acoustic_guitar_nylon: { folder: 'guitar-acoustic', source: 'University of Iowa MIS, sin restricciones',
    notes: 'A2 A3 A4 As2 As3 As4 B2 B3 B4 C3 C4 C5 Cs3 Cs4 Cs5 D2 D3 D4 D5 Ds2 Ds3 Ds4 E2 E3 E4 F2 F3 F4 Fs2 Fs3 Fs4 G2 G3 G4 Gs2 Gs3 Gs4' },
  electric_guitar_clean: { folder: 'guitar-electric', source: 'Karoryfer, CC0',
    notes: 'A2 A3 A4 A5 C3 C4 C5 C6 Cs2 Ds3 Ds4 Ds5 E2 Fs2 Fs3 Fs4 Fs5' },
  orchestral_harp: { folder: 'harp', source: 'VSCO2 CE, CC0',
    notes: 'A2 A4 A6 B1 B3 B5 B6 C3 C5 D2 D4 D6 D7 E1 E3 E5 F2 F4 F6 F7 G1 G3 G5' },
  xylophone: { folder: 'xylophone', source: 'VSCO2 CE, CC0',
    notes: 'C5 C6 C7 C8 G4 G5 G6 G7' },
  acoustic_grand_piano: { folder: 'piano', source: 'VSCO2 CE, CC0',
    notes: 'A1 A2 A3 A4 A5 A6 A7 As1 As2 As3 As4 As5 As6 As7 B1 B2 B3 B4 B5 B6 B7 C1 C2 C3 C4 C5 C6 C7 C8 Cs1 Cs2 Cs3 Cs4 Cs5 Cs6 Cs7 D1 D2 D3 D4 D5 D6 D7 Ds1 Ds2 Ds3 Ds4 Ds5 Ds6 Ds7 E1 E2 E3 E4 E5 E6 E7 F1 F2 F3 F4 F5 F6 F7 Fs1 Fs2 Fs3 Fs4 Fs5 Fs6 Fs7 G1 G2 G3 G4 G5 G6 G7 Gs1 Gs2 Gs3 Gs4 Gs5 Gs6 Gs7' },
};

const STEPS = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };

// "As3" is A#3 in the file names: MIDI 58.
export function sampleMidi(name) {
  const match = /^([A-G])(s?)(-?\d)$/.exec(name);
  return match ? (Number(match[3]) + 1) * 12 + STEPS[match[1]] + (match[2] ? 1 : 0) : NaN;
}

// smplr preset with, for each note of the part, its nearest recording. Each region keeps the
// recorded pitch and covers the keys closest to it, so smplr pitch-shifts between recordings.
// (smplr 1.1.0 plays flat `buffers` maps silently or with a non-finite detune.)
export function recordedPreset(sound, notes) {
  const bank = RECORDED[sound];
  if (!bank) return null;
  const samples = bank.notes.split(' ').map(name => ({ name, midi: sampleMidi(name) }));
  const chosen = new Map();
  for (const note of new Set(notes)) {
    const nearest = samples.reduce((best, sample) =>
      Math.abs(sample.midi - note) < Math.abs(best.midi - note) ? sample : best);
    chosen.set(nearest.midi, nearest);
  }
  const ordered = [...chosen.values()].sort((left, right) => left.midi - right.midi);
  const regions = ordered.map((sample, index) => ({
    sample: sample.name,
    pitch: sample.midi,
    keyRange: [index === 0 ? 0 : Math.floor((ordered[index - 1].midi + sample.midi) / 2) + 1,
      index === ordered.length - 1 ? 127 : Math.floor((sample.midi + ordered[index + 1].midi) / 2)],
  }));
  return { samples: { baseUrl: RECORDED_BASE_URL + bank.folder + '/', formats: ['mp3'] }, groups: [{ regions }] };
}

// Level of each sound (2026-10-14): RMS in dB of the player's real output (smplr 1.1.0, velocity 100,
// three central notes), measured in the browser. In a block of several voices the piccolo and the oboe
// sat 4-6 dB under the rest and a single flute was covered by the five clarinet parts of the band.
export const LEVEL_TARGET_DB = -24;
const MAX_BOOST_DB = 12;
const SOUNDFONT_DEFAULT_DB = -28;
const RECORDED_LEVELS = {
  flute: -22.7, clarinet: -20.6, alto_sax: -25.8, tenor_sax: -25.0, trumpet: -26.0, french_horn: -22.7,
  trombone: -24.7, tuba: -23.9, bassoon: -26.3, xylophone: -31.7, contrabass: -24.4, electric_bass_finger: -26.7,
  acoustic_guitar_nylon: -28.6, electric_guitar_clean: -30.9, orchestral_harp: -26.8, acoustic_grand_piano: -26.9,
};
const SOUNDFONT_LEVELS = {
  piccolo: -27.6, oboe: -30.1, english_horn: -23.7, soprano_sax: -29.8, baritone_sax: -27.6, cello: -28.3,
  glockenspiel: -39.5, timpani: -27.9, tubular_bells: -30.7, marimba: -24.9, vibraphone: -30.4,
  clarinet: -25.3, trumpet: -31.1, tuba: -22.8,
};

// Gain that brings a sound to the common level; parts sharing it (three clarinets play through one
// player) weigh 1/sqrt(parts) each, so a section does not cover a single voice such as the flute.
export function voiceGain(sound, recorded, parts = 1) {
  const level = (recorded ? RECORDED_LEVELS : SOUNDFONT_LEVELS)[sound] ?? (recorded ? LEVEL_TARGET_DB : SOUNDFONT_DEFAULT_DB);
  return 10 ** (Math.min(MAX_BOOST_DB, LEVEL_TARGET_DB - level) / 20) / Math.sqrt(Math.max(1, parts));
}
