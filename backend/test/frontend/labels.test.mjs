import assert from 'node:assert/strict';
import test from 'node:test';
import {
  bandIssueText, byDifficulty, displayFamilyName, displayInstrumentName,
  gradeOf, gradeScaleOf, gradeText, initialBandDraft, readBandProfile, unconfirmedStatusText, confirmationOptions, rehearsalBlockDetail, rehearsalBlockTitle, omittedBlockText, calendarLabel, rehearsalGroupName, blockScoreLabel,
} from '../../../frontend/src/labels.js';

test('instrument names keep the part number', () => {
  assert.equal(displayInstrumentName('Horn in F 2'), 'Trompa en Fa 2');
  assert.equal(displayInstrumentName('Ondes Martenot'), 'Ondes Martenot');
  assert.equal(displayInstrumentName('Flute', { instrument_label_es: 'Flauta 1ª' }), 'Flauta 1ª');
  assert.equal(displayFamilyName('brass'), 'Viento metal');
  assert.equal(displayFamilyName('brass', { label_es: 'Metales' }), 'Metales');
});

const current = gradeScaleOf({ scale: { version: 2, grades: 6, technical_index_max: 10 } });
const legacy = gradeScaleOf({});

test('an analysis declares its scale; one without it was graded 1-5 before step 13', () => {
  assert.deepEqual(current, { grades: 6, indexMax: 10, legacy: false });
  assert.deepEqual(legacy, { grades: 5, indexMax: 5, legacy: true });
  assert.deepEqual(gradeScaleOf(undefined), legacy);
});

test('grades are bounded to the visible scale', () => {
  assert.equal(gradeOf({}), 1);
  assert.equal(gradeOf({ grade: 9 }), 6);
  assert.equal(gradeOf({ grade: 9 }, legacy), 5);
  assert.equal(gradeOf(undefined), 1);
});

test('a grade reads with its rubric, and an old analysis says it used the previous scale', () => {
  assert.deepEqual([1, 2, 3, 4, 5, 6].map(grade => gradeText({ grade }, current)), [
    'Grado 1 · Muy fácil', 'Grado 2 · Fácil', 'Grado 3 · Intermedio',
    'Grado 4 · Intermedio avanzado', 'Grado 5 · Avanzado', 'Grado 6 · Profesional']);
  assert.equal(gradeText({ grade: 3 }, legacy), 'Grado 3 de 5 (escala anterior)');
});

test('difficulty ordering uses grade first and the index to break ties', () => {
  const ordered = byDifficulty([
    ['a', { grade: 2, score: 9 }], ['b', { grade: 4, score: 1 }], ['c', { grade: 4, score: 3 }],
  ], 'score');
  assert.deepEqual(ordered.map(([name]) => name), ['c', 'b', 'a']);
});

const requirements = [
  { key: 'clarinet.bb', label_es: 'Clarinete en Si bemol', required: 3, available: 0, parts: ['Clarinet 1', 'Clarinet 2', 'Clarinet 3'] },
  { key: 'percussion', label_es: 'Percusionistas', required: 2, available: 0, parts: ['Bass Drum', 'Snare Drum'] },
];

test('band template is one row per instrument and starts with the musicians the score needs', () => {
  const draft = initialBandDraft(requirements, { percussion: 1 });
  assert.deepEqual(draft, { 'clarinet.bb': '3', percussion: '1' });
  assert.deepEqual(readBandProfile(requirements, { ...draft, 'clarinet.bb': '-3' }), { 'clarinet.bb': 0, percussion: 1 });
  assert.deepEqual(readBandProfile(requirements, { 'clarinet.bb': '', percussion: '11' }), { 'clarinet.bb': 0, percussion: 11 });
  assert.deepEqual(readBandProfile(undefined, {}), {});
});

test('band issues and rehearsal blocks read as musician-facing Spanish', () => {
  assert.equal(bandIssueText({ label_es: 'Oboe', available: 0, required: 1 }), 'Oboe: falta en la plantilla; se necesita 1.');
  assert.equal(bandIssueText({ label_es: 'Trompa en Fa', available: 2, required: 4 }), 'Trompa en Fa: hay 2 músicos y se necesitan 4.');
});

test('parts to confirm explain why and offer the proposal and candidates first', () => {
  assert.equal(unconfirmedStatusText({ status: 'unknown' }), 'Sin identificar');
  assert.equal(unconfirmedStatusText({ status: 'review' }), 'Propuesta por los datos del archivo');
  assert.equal(unconfirmedStatusText({ status: 'conflict' }), 'El nombre y los datos del archivo no coinciden');
  assert.equal(unconfirmedStatusText({ status: 'shared' }), 'Propuesto: otras cuentas lo confirmaron con este instrumento');
  const catalog = [{ canonical_id: 'flute', label_es: 'Flauta' }, { canonical_id: 'oboe', label_es: 'Oboe' },
    { canonical_id: 'trumpet.bb', label_es: 'Trompeta en Si bemol' }];
  const options = confirmationOptions({ status: 'conflict', proposal: null, candidates: ['trumpet.bb', 'flute'] }, catalog);
  assert.deepEqual(options.map(option => option.canonical_id), ['trumpet.bb', 'flute', 'oboe']);
});

test('ensemble rehearsal blocks: common lines, subsections and a tutti to join', () => {
  const common = { type: 'common', group: null, kind: 'line', parts: ['Euphonium', 'Trombone', 'Tenor Saxophone'],
    measure_range: '47-54', findings: ['SL003'] };
  assert.equal(rehearsalBlockTitle(common), 'Línea común · c. 47–54');
  assert.equal(rehearsalBlockDetail(common), 'Bombardino, Trombón, Saxofón tenor · Alta densidad rítmica');
  assert.equal(rehearsalBlockTitle({ ...common, kind: 'rhythm' }), 'Ritmo común · c. 47–54');
  const sectional = { type: 'sectional', group: 'low_voices', parts: ['Bassoon', 'Tuba'], measure_range: '1-5', findings: [] };
  assert.equal(rehearsalBlockTitle(sectional), 'Seccional · Graves · c. 1–5');
  assert.equal(rehearsalBlockDetail(sectional), 'Fagot, Tuba');
  const tutti = { type: 'tutti', group: null, parts: ['Clarinet 1', 'Trumpet'], measure_ranges: ['9-12', '30'], findings: [] };
  assert.equal(rehearsalBlockTitle(tutti), 'Tutti para juntar · c. 9–12, 30');
  assert.equal(rehearsalBlockDetail(tutti), 'Toda la banda');
  assert.equal(omittedBlockText({ type: 'sectional', group: 'high_brass', parts: ['Trumpet'], measure_range: '30-31', reason: 'time' }),
    'Metales agudos · c. 30–31 · Trompeta');
  assert.equal(omittedBlockText({ type: 'common', group: null, parts: ['Oboe', 'Flute'], measure_range: '2', reason: 'time' }),
    'Común · c. 2 · Oboe, Flauta');
});

test('rehearsal groups have names for titles, the score viewer and narrow calendar slots', () => {
  const groups = ['flutes', 'double_reeds', 'clarinets', 'saxophones', 'high_brass', 'low_voices', 'percussion', 'strings_rhythm'];
  assert.deepEqual(groups.map(rehearsalGroupName), ['Flautas', 'Dobles cañas', 'Clarinetes', 'Saxofones', 'Metales agudos', 'Graves',
    'Percusión', 'Cuerda y rítmica']);
  assert.deepEqual(groups.map(group => calendarLabel({ type: 'sectional', group })),
    ['Flautas', 'D. cañas', 'Clarinetes', 'Saxos', 'M. agudos', 'Graves', 'Perc.', 'Cuerda']);
  assert.equal(calendarLabel({ type: 'common', kind: 'line' }), 'Línea');
  assert.equal(calendarLabel({ type: 'common', kind: 'rhythm' }), 'Ritmo');
  assert.equal(calendarLabel({ type: 'tutti' }), 'Tutti');
  assert.equal(blockScoreLabel({ type: 'common', kind: 'line' }), 'Línea común');
  assert.equal(blockScoreLabel({ type: 'sectional', group: 'saxophones' }), 'Saxofones');
  assert.equal(blockScoreLabel({ type: 'tutti' }), 'Toda la banda');
});

test('the work grade says which families make it; the rest are shown apart (difficulty-v2, 2026-10-14)', async () => {
  const { familyCountsForWork, workGradeDetail } = await import('../../../frontend/src/labels.js');
  assert.equal(workGradeDetail({ algorithm_version: 'difficulty-v2' }),
    'Estimación provisional · viento y cuerda; la percusión y la sección rítmica se muestran aparte');
  assert.equal(workGradeDetail({}), 'Estimación provisional · percentil 80 por familia', 'an analysis made before');
  assert.equal(familyCountsForWork({ counts_for_work: false }), false);
  assert.equal(familyCountsForWork({ counts_for_work: true }), true);
  assert.equal(familyCountsForWork({}), true, 'an earlier analysis counted every family');
});

test('the work grade follows the publishers\' guides and says why (difficulty-v3, 2026-10-25)', async () => {
  const { gradeReasons, workGradeDetail } = await import('../../../frontend/src/labels.js');
  const reason = 'Tesitura de Tuba hasta Do4 → grado 6, por encima de la tabla (American Band College)';
  assert.deepEqual(gradeReasons({ rubric: { reasons_es: [reason] } }), [reason]);
  const { setLanguage } = await import('../../../frontend/src/i18n.js');
  setLanguage('en');
  assert.deepEqual(gradeReasons({ rubric: { reasons_es: [reason], reasons_en: ['In English'] } }), ['In English']);
  assert.deepEqual(gradeReasons({ rubric: { reasons_es: [reason] } }), [reason], 'an analysis without them keeps the Spanish ones');
  setLanguage('es');
  assert.equal(workGradeDetail({ algorithm_version: 'difficulty-v3', rubric: {} }),
    'Según las guías de grados de las editoriales · viento y cuerda; la percusión se muestra aparte');
  assert.deepEqual(gradeReasons({ algorithm_version: 'difficulty-v2' }), [], 'an earlier analysis has no reasons');
});
