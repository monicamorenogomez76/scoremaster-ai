// Concerts (planned 2026-10-06): a concert with its programme and weekly pattern, the series of
// rehearsals the app proposes up to the general rehearsal, saved after the director reviews it.
import { createRequire } from 'node:module';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const url = process.env.SCOREMASTER_URL || 'http://127.0.0.1:8006';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const score = name => readFileSync(new URL('../../../test-scores/' + name, import.meta.url));
const iso = value => [value.getFullYear(), String(value.getMonth() + 1).padStart(2, '0'), String(value.getDate()).padStart(2, '0')].join('-');
// Minutes of one work in an agenda calendar ("20:52 · 28 min").
const minutesOf = (rehearsal, work) => rehearsal.locator('.calendar-slot').evaluateAll((slots, title) => slots
  .filter(slot => slot.querySelector('.calendar-work').textContent === title)
  .reduce((total, slot) => total + Number(/(\d+) min/.exec(slot.querySelector('.calendar-time').textContent)[1]), 0), work);
const waitIdle = () => page.waitForFunction(() => !document.querySelector('#upload-form button[type=submit]').disabled);
try {
  await page.goto(url);
  await page.locator('#login-mode').click();
  await page.locator('#login-name').fill('Directora de conciertos');
  await page.locator('#login-email').fill('conciertos-' + Date.now() + '@banda.test');
  await page.locator('#login-password').fill('una contraseña larga');
  await page.locator('#login-submit').click();
  await page.locator('#app-shell').waitFor({ state: 'visible' });
  for (const name of ['high_register.musicxml', 'high_density.musicxml']) {
    await page.locator('[data-view-target=repertoire]').click();
    await page.locator('#add-work').click();
    await page.locator('#file').setInputFiles({ name, mimeType: 'application/xml', buffer: score(name) });
    await waitIdle();
    await page.locator('#upload-form button[type=submit]').click();
    await page.locator('#work-detail').waitFor({ state: 'visible' });
    await waitIdle();
  }

  await page.locator('[data-view-target=concerts]').click();
  await page.locator('#create-concert').click();
  const editor = page.locator('#concert-editor');
  const concertDay = new Date(); concertDay.setDate(concertDay.getDate() + 16);
  await editor.getByLabel('Título').fill('Concierto de otoño');
  await editor.getByLabel('Fecha del concierto').fill(iso(concertDay));
  await editor.getByLabel('High Density Study').check();
  await editor.getByLabel('Untitled score').check();
  // Today is one of the rehearsal days, so the first rehearsal can be reviewed during the walkthrough.
  const names = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
  for (const offset of [0, 2, 4]) await editor.getByLabel(names[(new Date().getDay() + offset) % 7], { exact: true }).check();
  await editor.getByLabel('Hora de ensayo').fill('20:00');
  await editor.getByLabel('Duración de cada ensayo (minutos)').fill('90');
  const preview = await editor.locator('.pattern-preview li').count();
  assert.ok(preview >= 5 && preview <= 8, 'three days a week for about two weeks');
  await editor.getByRole('button', { name: 'Guardar concierto' }).click();
  const card = page.locator('.concert-item').filter({ hasText: 'Concierto de otoño' });
  await card.waitFor();
  assert.match(await card.textContent(), /Faltan 16 días/);
  assert.match(await card.textContent(), /High Density Study · Untitled score/, 'the programme keeps the concert order');
  console.log('PASS: a concert keeps its date, its programme in order and its weekly pattern');

  await card.getByRole('button', { name: 'Planificación' }).click();
  const planning = page.locator('#concert-planning');
  // On a slow server the proposal says what it is doing while it waits (2026-10-07).
  let releasePlan;
  const planGate = new Promise(resolve => { releasePlan = resolve; });
  await page.route('**/concerts/*/plan', async route => { await planGate; await route.continue(); });
  await planning.getByRole('button', { name: 'Proponer planificación' }).click();
  await page.locator('#concert-plan-activity').waitFor();
  assert.match(await page.locator('#concert-plan-activity').textContent(),
    /Calculando la planificación del concierto con el análisis de 2 obras/);
  releasePlan();
  const proposed = planning.locator('.planned-rehearsal');
  await proposed.first().waitFor();
  await page.unroute('**/concerts/*/plan');
  assert.equal(await page.locator('#concert-plan-activity').count(), 0, 'nothing in progress once proposed');
  assert.equal(await proposed.count(), preview, 'one rehearsal per date of the pattern');
  assert.match(await proposed.last().textContent(), /Ensayo general/);
  assert.deepEqual(await proposed.last().locator('.calendar-work').allTextContents(), ['Toda la banda', 'High Density Study', 'Untitled score'],
    'the general rehearsal runs through the programme in concert order');
  assert.match(await proposed.first().textContent(), /Lectura y pasajes/);
  await planning.getByRole('button', { name: 'Guardar planificación' }).click();
  await planning.locator('.series-rehearsal').first().waitFor();
  assert.equal(await planning.locator('.series-rehearsal').count(), preview);
  assert.match(await planning.textContent(), new RegExp('0 de ' + preview + ' ensayos revisados'));
  console.log('PASS: the app proposes the series up to the general rehearsal and saves it when reviewed');

  // The rehearsal card suggests the next step of the concert: review today's rehearsal.
  const nextStep = page.locator('#summary-rehearsal .next-step');
  await page.locator('[data-view-target=summary]').click();
  await nextStep.getByText(/El ensayo de hoy está sin revisar/).waitFor();
  assert.equal(await page.locator('#summary-assistant').count(), 0, 'no panel repeats the concert or the rehearsal');
  await nextStep.getByRole('button', { name: 'Revisar ensayo' }).click();
  await page.locator('#rehearsal-review').waitFor();
  assert.equal(await page.locator('[data-view-target=rehearsal]').getAttribute('aria-current'), 'page');
  await page.locator('#rehearsal-review').getByRole('button', { name: 'Cancelar' }).click();
  await page.locator('[data-view-target=concerts]').click();
  console.log('PASS: the rehearsal card suggests reviewing the rehearsal already held');

  // The director reviews today's rehearsal: what was left pending gains time in the next ones.
  const series = planning.locator('.series-rehearsal');
  const before = await minutesOf(series.nth(1), 'Untitled score');
  await series.first().getByRole('button', { name: 'Revisar' }).click();
  const review = page.locator('#rehearsal-review');
  await review.waitFor();
  const rows = review.locator('.review-block');
  let first = true;
  for (let index = 0; index < await rows.count(); index++) {
    const row = rows.nth(index), text = await row.textContent();
    if (text.includes('Untitled score')) {
      await row.getByLabel('Pendiente').check();
      if (first) { await row.getByLabel('Nota').fill('Entradas de clarinetes'); first = false; }
    } else {
      await row.getByLabel('Resuelto').check();
    }
  }
  await review.getByLabel('Notas del ensayo').fill('Buen ensayo; los clarinetes siguen justos.');
  await review.getByRole('button', { name: 'Guardar revisión' }).click();
  await series.first().getByText('Revisado').waitFor();
  await page.locator('[data-view-target=summary]').click();
  await nextStep.getByRole('button', { name: 'Replanificar los ensayos siguientes' }).waitFor();
  await page.locator('[data-view-target=concerts]').click();
  await planning.getByRole('button', { name: 'Replanificar los ensayos siguientes' }).click();
  const replanned = planning.locator('.planned-rehearsal');
  await replanned.first().waitFor();
  assert.equal(await replanned.count(), preview - 1, 'the reviewed rehearsal is kept');
  assert.match(await planning.textContent(), /Se mantienen 1 ensayos/);
  assert.ok(await minutesOf(replanned.first(), 'Untitled score') > before, 'what was left pending gains time');
  await planning.getByRole('button', { name: 'Guardar planificación' }).click();
  await planning.locator('.plan-preview').waitFor({ state: 'detached' });
  assert.match(await planning.textContent(), new RegExp('1 de ' + preview + ' ensayos revisados'));
  console.log('PASS: the director reviews a rehearsal and the next ones are replanned with it');

  const calendar = page.locator('.month-calendar');
  assert.ok(await calendar.locator('.event-rehearsal').count() >= 1, 'the month calendar shows the rehearsals');
  await page.locator('[data-view-target=rehearsal]').click();
  await page.waitForFunction(count => document.querySelectorAll('#rehearsals-upcoming .works-item').length >= count, preview);
  await page.locator('[data-view-target=summary]').click();
  await page.locator('#next-concert').getByText('Concierto de otoño').waitFor();
  assert.match(await page.locator('#next-concert').textContent(), new RegExp('faltan 16 días · ' + (preview - 1) + ' ensayos'));
  const priorities = page.locator('#summary-priorities');
  await priorities.getByText('Revisión', { exact: true }).first().waitFor();
  assert.match(await priorities.textContent(), /Pendiente · Entradas de clarinetes/);
  // «Cobertura hasta el concierto» (2026-10-26): the rehearsal held and reviewed out of the series, per work its
  // minutes rehearsed and its passages resolved, each with its percentage written out.
  const coverage = page.locator('#summary-coverage');
  await coverage.waitFor();
  assert.equal(await coverage.locator('.coverage-headline').textContent(), '1 de ' + preview + ' ensayos hechos (' + Math.round(100 / preview) + ' %)');
  assert.deepEqual(await coverage.locator('tbody th').allTextContents(), ['High Density Study', 'Untitled score'], 'one row per work of the programme');
  assert.match(await coverage.locator('tbody tr').nth(1).locator('td').nth(1).textContent(), /^0 %: 0 de \d+ resueltos, \d+ pendientes?$/,
    'Untitled score was left pending, and the percentage says what it counts');
  // With everything reviewed and replanned there is nothing to suggest (after the summary reloads).
  await nextStep.waitFor({ state: 'detached' });
  // Everything is navigable: a block and a priority open the score at their passage with their instruments.
  // Opening a passage of another work: the dialog answers at once while the work loads, and the
  // passage's audio starts being prepared before play is pressed (reported 2026-10-07).
  await page.route('**/works/*/file', async route => { await new Promise(resolve => setTimeout(resolve, 1500)); await route.continue(); });
  const prepared = page.waitForRequest(request => request.url().endsWith('/playback'), { timeout: 45000 });
  const sectional = page.locator('#summary-rehearsal .calendar-slot--clarinets').first().getByRole('button');
  await sectional.click();
  await page.locator('#notation-status').getByText('Cargando la obra…').waitFor({ timeout: 1000 });
  assert.equal(await page.locator('#notation-dialog').evaluate(dialog => dialog.open), true, 'the dialog opens while the work loads');
  await page.unroute('**/works/*/file');
  await page.waitForFunction(() => document.querySelector('#notation-score svg'), null, { timeout: 45000 });
  await prepared;
  assert.deepEqual(await page.evaluate(() => window.scoremasterWorkspace.getPassage().instruments), ['Clarinet']);
  await page.locator('#notation-close').click();
  await priorities.getByRole('button', { name: 'c. 1' }).first().click();
  await page.waitForFunction(() => document.querySelector('#notation-score svg'), null, { timeout: 45000 });
  await page.locator('#notation-close').click();
  assert.equal(await page.locator('[data-view-target=summary]').getAttribute('aria-current'), 'page', 'the passage opens without leaving the summary');
  console.log('PASS: a block and a priority open the score at their passage with their instruments');
  await page.setViewportSize({ width: 1440, height: 900 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight + 2), true,
    'with a concert and the review the summary still fits on a computer screen');
  assert.deepEqual(errors, []);
  console.log('PASS: the month calendar, Ensayos and the summary show the series and the review');
} finally {
  await browser.close();
}
