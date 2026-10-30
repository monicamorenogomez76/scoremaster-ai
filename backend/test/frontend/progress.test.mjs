import assert from 'node:assert/strict';
import test from 'node:test';
import { activityText, proposalActivity, slowNotice } from '../../../frontend/src/progress.js';

const SLOW_NOTICE = slowNotice();

// 2026-10-07: on Render's free plan analysing or planning took minutes with a fixed message,
// and it looked as if nothing was happening.
test('a short wait only says what is being done', () => {
  assert.equal(activityText('Analizando la partitura', 0), 'Analizando la partitura…');
  assert.equal(activityText('Analizando la partitura', 4), 'Analizando la partitura…');
});

test('a longer wait counts the seconds, so the musician sees it is still working', () => {
  assert.equal(activityText('Analizando la partitura', 5), 'Analizando la partitura… 5 s');
  assert.equal(activityText('Analizando la partitura', 14), 'Analizando la partitura… 14 s');
});

test('a slow wait explains why and keeps counting in minutes', () => {
  assert.equal(activityText('Analizando la partitura', 15), 'Analizando la partitura… 15 s. ' + SLOW_NOTICE);
  assert.equal(activityText('Analizando la partitura', 75), 'Analizando la partitura… 1 min 15 s. ' + SLOW_NOTICE);
  assert.equal(activityText('Analizando la partitura', 120), 'Analizando la partitura… 2 min. ' + SLOW_NOTICE);
  assert.match(SLOW_NOTICE, /unos minutos/);
});

test('without an action there is nothing to show', () => {
  assert.equal(activityText('', 30), '');
});

test('a proposal says how many works it is reading', () => {
  assert.equal(proposalActivity('agenda', 1), 'Calculando la agenda con el análisis de 1 obra');
  assert.equal(proposalActivity('agenda', 3), 'Calculando la agenda con el análisis de 3 obras');
  assert.equal(proposalActivity('concert', 2), 'Calculando la planificación del concierto con el análisis de 2 obras');
});
