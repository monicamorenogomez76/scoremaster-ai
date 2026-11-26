import assert from 'node:assert/strict';
import test from 'node:test';
import { setLanguage } from '../../../frontend/src/i18n.js';
import { cadenceText, keyName, markText, relationText, sectionShares, textureText } from '../../../frontend/src/musicalAnalysis.js';

// The musical analysis of a work (2026-11-18) in a musician's words.
test('a key is named as a musician says it, in each language', () => {
  setLanguage('es');
  assert.equal(keyName({ tonic: 'Eb', mode: 'major' }), 'Mi♭ mayor');
  assert.equal(keyName({ tonic: 'F#', mode: 'minor' }), 'Fa♯ menor');
  setLanguage('en');
  assert.equal(keyName({ tonic: 'Bb', mode: 'major' }), 'B♭ major');
  setLanguage('es');
  assert.equal(keyName(null), '');
});

test('relations, textures, cadences and marks read as words', () => {
  setLanguage('es');
  assert.equal(relationText('dominant'), 'dominante');
  assert.equal(relationText('distant'), 'tono lejano');
  assert.equal(textureText('reduced'), 'plantilla reducida');
  assert.equal(cadenceText('authentic'), 'cadencia auténtica');
  assert.equal(markText('rehearsal B'), 'letra de ensayo B');
  assert.equal(markText('words D.C. al Fine'), '«D.C. al Fine»');
  assert.equal(markText('ending 1'), 'casilla 1');
  assert.equal(markText('double barline'), 'doble barra');
});

test('the timeline gives each section its share of the measures', () => {
  assert.deepEqual(sectionShares([{ first: 1, last: 8 }, { first: 9, last: 24 }]), [33.33, 66.67]);
  assert.deepEqual(sectionShares([]), []);
});

test('duration, tempos and meters read as a musician writes them', async () => {
  const { durationText, tempoText, listText } = await import('../../../frontend/src/musicalAnalysis.js');
  setLanguage('es');
  assert.equal(durationText(467), '7 min 47 s');
  assert.equal(durationText(45), '45 s');
  assert.equal(tempoText({ measure: 1, bpm: 120, words: ['Allegro'] }), 'c. 1: ♩ = 120 · Allegro');
  assert.equal(tempoText({ measure: 16, bpm: null, words: ['rit.'] }), 'c. 16: rit.');
  assert.equal(listText(['a', 'b', 'c', 'd'], 2), 'a, b y 2 más');
  assert.equal(listText(['a', 'b'], 3), 'a, b');
});

test('phrases and periods read as a musician says them', async () => {
  const { phrasesText, periodText } = await import('../../../frontend/src/musicalAnalysis.js');
  setLanguage('es');
  assert.equal(phrasesText({ structure: '4 + 4', phrases: [{ ending: 'suspensive' }, { ending: 'conclusive' }] }),
    '4 + 4 (suspensiva, conclusiva)');
  assert.equal(phrasesText({ structure: '', phrases: [] }), '—');
  assert.equal(periodText({ first: 1, last: 8, kind: 'period', symmetric: true }), 'periodo simétrico, cc. 1–8');
  assert.equal(periodText({ first: 9, last: 20, kind: 'repetition', symmetric: false }), 'frase repetida, cc. 9–20');
});

test('texture and rhythm read as a musician says them', async () => {
  const { textureKindText, rhythmText } = await import('../../../frontend/src/musicalAnalysis.js');
  setLanguage('es');
  assert.equal(textureKindText('melody_and_accompaniment'), 'melodía acompañada');
  assert.equal(textureKindText('polyphonic'), 'polifónica');
  assert.equal(textureKindText(null), '');
  assert.equal(rhythmText({ syncopation: 0.5, ostinatos: [{ part: 'Tuba', first: 1, last: 4 }],
    imitations: [{ part: 'Clarinet', imitates: 'Flute', measure: 2 }] }),
    'síncopas (50 %) · ostinato: Tuba (cc. 1–4) · imitación: Clarinet (c. 2)');
  assert.equal(rhythmText({ syncopation: 0.05, ostinatos: [], imitations: [] }), '—');
});

test('the theme of a section and the themes it develops read as words', async () => {
  const { themeText } = await import('../../../frontend/src/musicalAnalysis.js');
  setLanguage('es');
  assert.equal(themeText({ theme: { id: 'T1', statement: 'exposition' }, motifs: [] }), 'T1 (exposición)');
  assert.equal(themeText({ theme: { id: 'T1', statement: 'transposed' }, motifs: [] }), 'T1 (vuelve en otro tono)');
  assert.equal(themeText({ theme: { id: 'T2', statement: 'return' }, motifs: [{ theme: 'T1', part: 'Tuba', measure: 9 }] }),
    'T2 (vuelve) · cabeza de T1: Tuba (c. 9)');
  assert.equal(themeText({ theme: null, motifs: [] }), '—');
});

test('solos, percussion and extreme registers read as words', async () => {
  const { orchestrationText } = await import('../../../frontend/src/musicalAnalysis.js');
  setLanguage('es');
  assert.equal(orchestrationText({ solos: [{ part: 'Flute', measure: 9, kind: 'solo' }],
    percussion: [{ part: 'Caja', role: 'continuous' }, { part: 'Platos', role: 'punctual' }],
    registers: [{ part: 'Oboe', register: 'high', measure: 22 }] }),
    'solo: Flute (c. 9) · percusión: Caja (continua), Platos (puntual) · agudo extremo: Oboe (c. 22)');
  assert.equal(orchestrationText({ solos: [], percussion: [], registers: [] }), '—');
});

test('plagal and deceptive cadences and modulations read as words', async () => {
  const { cadenceText, modulationText } = await import('../../../frontend/src/musicalAnalysis.js');
  setLanguage('es');
  assert.equal(cadenceText('plagal'), 'cadencia plagal');
  assert.equal(cadenceText('deceptive'), 'cadencia rota');
  assert.equal(modulationText({ measure: 7, key: { tonic: 'G', mode: 'major' }, relation: 'dominant' }),
    'modula a Sol mayor (dominante, c. 7)');
  setLanguage('en');
  assert.equal(cadenceText('deceptive'), 'deceptive cadence');
  setLanguage('es');
});

test('harmonic rhythm, secondary dominants and pedals read as words', async () => {
  const { harmonyDetailsText } = await import('../../../frontend/src/musicalAnalysis.js');
  setLanguage('es');
  assert.equal(harmonyDetailsText({ harmonic_rhythm: 1.5, secondary_dominants: [{ measure: 2, of: 'V' }],
    pedals: [{ first: 1, last: 4, note: 'Bb', degree: 'tonic' }] }),
    '1,5 acordes por compás · V/V (c. 2) · pedal de tónica en Si♭ (cc. 1–4)');
  assert.equal(harmonyDetailsText({ harmonic_rhythm: null, secondary_dominants: [], pedals: [] }), '');
  setLanguage('en');
  assert.equal(harmonyDetailsText({ harmonic_rhythm: 2, secondary_dominants: [],
    pedals: [{ first: 9, last: 12, note: 'G', degree: 'other' }] }), '2 chords per measure · pedal on G (mm. 9–12)');
  setLanguage('es');
});

test('hemiolas and displaced accents read as words', async () => {
  const { meterText } = await import('../../../frontend/src/musicalAnalysis.js');
  setLanguage('es');
  assert.equal(meterText({ hemiolas: [3, 11], displaced_accents: [17, 18, 22, 23, 32, 40] }),
    'hemiolia (cc. 3, 11) · acentos a contratiempo (cc. 17, 18, 22, 23, 32 y 1 más)');
  assert.equal(meterText({ hemiolas: [], displaced_accents: [] }), '');
});

test('the range and contour of a theme read as words', async () => {
  const { themeShapeText } = await import('../../../frontend/src/musicalAnalysis.js');
  setLanguage('es');
  assert.equal(themeShapeText({ lowest: 'Bb4', highest: 'A5', range: 11, contour: 'arch', motion: 'conjunct' }),
    'Si♭4–La5 (11 semitonos), en arco, por grados');
  setLanguage('en');
  assert.equal(themeShapeText({ lowest: 'C4', highest: 'G5', range: 19, contour: 'descending', motion: 'disjunct' }),
    'C4–G5 (19 semitones), descending, by leaps');
  setLanguage('es');
});

test('the articulation of a section reads as its shares', async () => {
  const { articulationText } = await import('../../../frontend/src/musicalAnalysis.js');
  setLanguage('es');
  assert.equal(articulationText({ articulation: { staccato: 0.83, accent: 0.12, tenuto: 0.02 } }), 'staccato 83 % · acentos 12 %');
  assert.equal(articulationText({ articulation: { staccato: 0.01, accent: 0, tenuto: 0 } }), '');
});

// The map of the work (2026-11-20): every lane on one axis of measures, in percent of the work.
test('the map places sections, keys, phrases, themes, cadences and the timeline on the measures', async () => {
  const { workMap } = await import('../../../frontend/src/musicalAnalysis.js');
  setLanguage('es');
  const timeline = Array.from({ length: 20 }, (_, at) => ({ measure: at + 1, dynamic: at < 10 ? 'p' : at === 15 ? 'ff' : null,
    playing: at < 10 ? 4 : 8 }));
  const map = workMap({
    sections: [
      { id: 'S1', first: 1, last: 5, label: 'A', like: null, key: { tonic: 'G', mode: 'major' }, modulations: [],
        phrases: [{ first: 1, last: 5 }] },
      { id: 'S2', first: 6, last: 15, label: 'B', like: null, key: { tonic: 'E', mode: 'minor' },
        modulations: [{ measure: 11, key: { tonic: 'B', mode: 'minor' } }], phrases: [{ first: 6, last: 10 }, { first: 11, last: 15 }] },
      { id: 'S3', first: 16, last: 20, label: 'A', like: 'S1', key: { tonic: 'G', mode: 'major' }, modulations: [], phrases: [] },
    ],
    themes: [{ id: 'T1', section: 'S1', first: 1, last: 4, part: 'Clarinete' }],
    cadences: [{ id: 'C1', measure: 5, kind: 'half' }, { id: 'C2', measure: 20, kind: 'authentic' }],
    climax: { measure: 16, dynamic: 'ff' },
    timeline,
  });
  assert.deepEqual(map.sections.map(item => [item.label, item.left, item.width, item.colour]),
    [['A', 0, 25, 0], ['B', 25, 50, 1], ['A', 75, 25, 0]], 'a section that comes back keeps the colour of its material');
  assert.deepEqual(map.keys.map(item => [item.name, item.left, item.width, item.colour]),
    [['Sol mayor', 0, 25, 0], ['Mi menor', 25, 25, 1], ['Si menor', 50, 25, 2], ['Sol mayor', 75, 25, 0]]);
  assert.deepEqual(map.phrases.map(item => [item.left, item.width]), [[0, 25], [25, 25], [50, 25]]);
  assert.deepEqual(map.themes, [{ id: 'T1', left: 0, label: 'T1 · Clarinete' }]);
  assert.deepEqual(map.cadences.map(item => [item.kind, item.left, item.symbol]), [['half', 22.5, '◐'], ['authentic', 97.5, '●']]);
  assert.equal(map.dynamics.length, 20);
  assert.equal(map.dynamics[0], 3 / 8, 'p on a scale of ppp to fff');
  assert.equal(map.dynamics[12], 3 / 8, 'an unmarked measure keeps the last dynamic');
  assert.equal(map.dynamics[15], 7 / 8);
  assert.deepEqual([map.playing[0], map.playing[19]], [0.5, 1]);
  assert.equal(map.climax.left, 77.5);
  assert.deepEqual(map.ticks.slice(0, 3), [{ measure: 1, left: 0 }, { measure: 5, left: 20 }, { measure: 9, left: 40 }]);
});

test('a work without a timeline still has its map, without the curves', async () => {
  const { workMap } = await import('../../../frontend/src/musicalAnalysis.js');
  const map = workMap({ sections: [{ id: 'S1', first: 1, last: 8, label: 'A', like: null, key: { tonic: 'C', mode: 'major' },
    modulations: [], phrases: [] }], themes: [], cadences: [], climax: null });
  assert.deepEqual(map.sections.map(item => [item.left, item.width]), [[0, 100]]);
  assert.deepEqual(map.dynamics, []);
  assert.equal(map.climax, null);
  const unmarked = workMap({ sections: [{ id: 'S1', first: 1, last: 2, label: 'A', like: null, key: { tonic: 'C', mode: 'major' },
    modulations: [], phrases: [] }], themes: [], cadences: [], climax: null,
    timeline: [{ measure: 1, dynamic: null, playing: 2 }, { measure: 2, dynamic: null, playing: 3 }] });
  assert.deepEqual(unmarked.dynamics, [], 'a work that writes no dynamic has no curve of dynamics');
  assert.equal(unmarked.playing.length, 2);
});

// The map over the full score (2026-11-20): the lanes of the map cut to the measures of the page, placed on the cells the
// engraving gives each measure (percent of the page).
test('the map over a page keeps the lanes of its measures, cut at the edges of the page', async () => {
  const { pageLanes } = await import('../../../frontend/src/musicalAnalysis.js');
  setLanguage('es');
  const analysis = {
    sections: [
      { id: 'S1', first: 1, last: 5, label: 'A', like: null, key: { tonic: 'G', mode: 'major' }, modulations: [],
        phrases: [{ first: 1, last: 5 }] },
      { id: 'S2', first: 6, last: 15, label: 'B', like: null, key: { tonic: 'E', mode: 'minor' },
        modulations: [{ measure: 11, key: { tonic: 'B', mode: 'minor' } }], phrases: [{ first: 6, last: 10 }, { first: 11, last: 15 }] },
    ],
    themes: [{ id: 'T1', section: 'S1', first: 1, last: 4, part: 'Clarinete' }, { id: 'T2', section: 'S2', first: 11, last: 15, part: 'Tuba' }],
    cadences: [{ id: 'C1', measure: 5, kind: 'half' }, { id: 'C2', measure: 10, kind: 'authentic' }],
    climax: null,
    timeline: Array.from({ length: 15 }, (_, at) => ({ measure: at + 1, dynamic: at === 8 ? 'p' : at === 11 ? 'f' : null, playing: 4 })),
  };
  const cells = [9, 10, 11, 12].map((measure, at) => ({ measure, left: 10 + at * 20, width: 20 }));
  const page = pageLanes(analysis, cells);
  assert.equal(page.labelWidth, 10, 'the part names keep their room');
  const lane = name => page.lanes.find(item => item.name === name)?.items;
  assert.deepEqual(lane('section'), [{ className: 'work-map-colour--1', left: 10, width: 80, text: 'B · cc. 6–15' }]);
  assert.deepEqual(lane('key'), [{ className: 'work-map-key work-map-tint--1', left: 10, width: 40, text: 'Mi menor' },
    { className: 'work-map-key work-map-tint--2', left: 50, width: 40, text: 'Si menor' }]);
  assert.deepEqual(lane('phrase').map(item => [item.className, item.left, item.width]),
    [['work-map-phrase work-map-phrase--open-start', 10, 40], ['work-map-phrase work-map-phrase--open-end', 50, 40]]);
  assert.deepEqual(lane('theme'), [{ className: 'work-map-theme', left: 50, text: 'T2 · Tuba' }]);
  assert.deepEqual(lane('cadence'), [{ className: 'work-map-cadence', left: 40, text: '●', title: 'cadencia auténtica (c. 10)' }]);
  assert.deepEqual(lane('dynamics').map(item => [item.left, item.width, item.height]),
    [[10, 20, 3 / 8], [30, 20, 3 / 8], [50, 20, 3 / 8], [70, 20, 6 / 8]]);
  assert.deepEqual(page.lanes.map(item => item.label), ['Sección', 'Tonalidad', 'Frase', 'Tema', 'Cadencia', 'Dinámica']);
  assert.equal(pageLanes(analysis, []), null, 'nothing to place without measures');
});

// The cards of the map (2026-11-20): the map widens, with a scroll, until its shortest section has room for its text.
test('the map is wide enough for the text of its shortest section', async () => {
  const { workMap } = await import('../../../frontend/src/musicalAnalysis.js');
  const sections = lengths => {
    let first = 1;
    return lengths.map((length, at) => { const section = { id: 'S' + (at + 1), first, last: first + length - 1, label: 'A', like: null,
      key: { tonic: 'C', mode: 'major' }, modulations: [], phrases: [] }; first += length; return section; });
  };
  const width = lengths => workMap({ sections: sections(lengths), themes: [], cadences: [], climax: null }).minWidth;
  assert.equal(width([8, 8]), 640, 'short works keep the usual width');
  assert.equal(width([28, 4, 28]), 96 + 60 * 22, 'a section of 4 measures gets 88 px');
  assert.equal(width([196, 2, 2]), 4000, 'never wider than this');
});

// The analysis is asked for when the work opens (2026-11-26): the map over the score and the analysis tab share that one request.
test('the analysis of a work is asked for once and shared, again after a failure or a change', async () => {
  const { musicalAnalysisOf, forgetMusicalAnalysis } = await import('../../../frontend/src/musicalAnalysis.js');
  setLanguage('es');
  let asked = 0;
  const load = async workId => { asked += 1; if (workId === 'falla' && asked === 1) throw new Error('caído'); return { workId }; };
  const first = musicalAnalysisOf('obra-1', load);
  assert.equal(musicalAnalysisOf('obra-1', load), first, 'one request for the map and the tab');
  assert.deepEqual(await first, { workId: 'obra-1' });
  assert.equal(asked, 1);
  setLanguage('en');
  await musicalAnalysisOf('obra-1', load);
  assert.equal(asked, 2, 'the parts are named in the new language');
  setLanguage('es');
  forgetMusicalAnalysis('obra-1');
  await musicalAnalysisOf('obra-1', load);
  assert.equal(asked, 3, 'asked again once its notes change');
  asked = 0;
  await assert.rejects(musicalAnalysisOf('falla', load));
  assert.deepEqual(await musicalAnalysisOf('falla', load), { workId: 'falla' }, 'a failure is asked again');
});
