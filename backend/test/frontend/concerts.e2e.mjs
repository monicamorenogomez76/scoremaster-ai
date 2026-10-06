// Concerts (author's plan, 2026-10-06): a concert with its programme and weekly pattern, the series of
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
  for (const day of ['lunes', 'miércoles', 'viernes']) await editor.getByLabel(day, { exact: true }).check();
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
  await planning.getByRole('button', { name: 'Proponer planificación' }).click();
  const proposed = planning.locator('.planned-rehearsal');
  await proposed.first().waitFor();
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

  const calendar = page.locator('.month-calendar');
  assert.ok(await calendar.locator('.event-rehearsal').count() >= 1, 'the month calendar shows the rehearsals');
  await page.locator('[data-view-target=rehearsal]').click();
  await page.waitForFunction(count => document.querySelectorAll('#rehearsals-upcoming .works-item').length >= count, preview);
  assert.deepEqual(errors, []);
  console.log('PASS: the month calendar and Ensayos show the planned series');
} finally {
  await browser.close();
}
