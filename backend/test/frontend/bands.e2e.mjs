// Bands (decided 2026-10-06): several fixed templates such as «Unió Musical d'Albalat dels
// Sorells», one active; the active one is the template of BandFit, and a concert takes its rehearsal days.
import { createRequire } from 'node:module';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const url = process.env.SCOREMASTER_URL || 'http://127.0.0.1:8006';
const browser = await chromium.launch();
const page = await browser.newPage({ locale: 'es-ES', viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const unio = "Unió Musical d'Albalat dels Sorells";
const waitIdle = () => page.waitForFunction(() => !document.querySelector('#upload-form button[type=submit]').disabled);
try {
  await page.goto(url);
  await page.locator('#login-mode').click();
  await page.locator('#login-name').fill('Director de banda');
  await page.locator('#login-email').fill('bandas-' + Date.now() + '@banda.test');
  await page.locator('#login-password').fill('una contraseña larga');
  await page.locator('#login-submit').click();
  await page.locator('#app-shell').waitFor({ state: 'visible' });

  await page.locator('[data-view-target=band]').click();
  await page.locator('#new-band').click();
  const editor = page.locator('#band-editor');
  await editor.getByLabel('Nombre de la banda').fill(unio);
  await editor.getByLabel('Localidad').fill('Albalat dels Sorells');
  for (const day of ['martes', 'jueves']) await editor.getByLabel(day, { exact: true }).check();
  await editor.getByLabel('Hora de ensayo').fill('20:00');
  await editor.getByLabel('Duración del ensayo (minutos)').fill('120');
  await editor.getByLabel('Plantilla: Clarinete en Si bemol').fill('11');
  await editor.getByLabel('Plantilla: Percusionistas').fill('4');
  await editor.getByLabel('Nivel de Clarinetes').selectOption('4');
  await editor.getByRole('button', { name: 'Guardar banda' }).click();
  const select = page.locator('#band-select');
  await page.waitForFunction(name => [...document.querySelectorAll('#band-select option')].some(option => option.textContent.startsWith(name)), unio);
  assert.match(await select.locator('option:checked').textContent(), /Unió Musical d'Albalat dels Sorells · activa/);
  console.log('PASS: a fixed band is created with its locality, rehearsal days, full template and levels');

  await page.locator('#new-band').click();
  await editor.getByLabel('Nombre de la banda').fill('Banda juvenil');
  await editor.getByLabel('Plantilla: Clarinete en Si bemol').fill('0');
  await editor.getByRole('button', { name: 'Guardar banda' }).click();
  await page.waitForFunction(() => document.querySelectorAll('#band-select option').length === 2);
  assert.match(await select.locator('option:checked').textContent(), /Unió/, 'a new band does not replace the active one');

  await page.locator('[data-view-target=repertoire]').click();
  await page.locator('#add-work').click();
  await page.locator('#file').setInputFiles({ name: 'high_register.musicxml', mimeType: 'application/xml',
    buffer: readFileSync(new URL('../../../test-scores/high_register.musicxml', import.meta.url)) });
  await waitIdle();
  await page.locator('#upload-form button[type=submit]').click();
  await page.locator('#work-detail').waitFor({ state: 'visible' });
  await waitIdle();
  await page.locator('[data-view-target=band]').click();
  const players = page.getByLabel('Músicos de Clarinete en Si bemol');
  assert.equal(await players.inputValue(), '11', 'the active band is the template of the work');
  await select.selectOption({ label: 'Banda juvenil' });
  await page.waitForFunction(() => document.querySelector('[aria-label="Músicos de Clarinete en Si bemol"]').value === '0');
  await page.locator('#band-content').getByText('Clarinete en Si bemol: falta en la plantilla; se necesita 1.').waitFor();
  console.log('PASS: activating another band recalculates the work with its template');

  await page.locator('[data-view-target=concerts]').click();
  await page.locator('#create-concert').click();
  const concert = page.locator('#concert-editor');
  await concert.getByLabel('Banda').selectOption({ label: unio });
  assert.equal(await concert.getByLabel('martes', { exact: true }).isChecked(), true, 'the concert takes the rehearsal days of its band');
  assert.equal(await concert.getByLabel('jueves', { exact: true }).isChecked(), true);
  assert.equal(await concert.getByLabel('Duración de cada ensayo (minutos)').inputValue(), '120');
  assert.deepEqual(errors, []);
  console.log('PASS: a concert is played by one band and takes its rehearsal days');

  // Configuración: the visible name is saved in the account and the text size on this device.
  await page.locator('[data-view-target=settings]').click();
  const settings = page.locator('[data-view=settings]');
  await settings.getByLabel('Nombre visible').fill('Mónica');
  await settings.getByRole('button', { name: 'Guardar nombre' }).click();
  await page.locator('#current-user').getByText('Mónica').waitFor();
  await settings.getByLabel('Grande', { exact: true }).check();
  const rootSize = () => page.evaluate(() => getComputedStyle(document.documentElement).fontSize);
  assert.equal(await rootSize(), '18px');
  await page.reload();
  await page.locator('#app-shell').waitFor({ state: 'visible' });
  assert.equal(await page.locator('#current-user').textContent(), 'Mónica', 'the name is kept in the account');
  assert.equal(await rootSize(), '18px', 'the text size is kept on this device');
  assert.deepEqual(errors, []);
  console.log('PASS: the visible name and the text size are set in Configuración');
} finally {
  await browser.close();
}
