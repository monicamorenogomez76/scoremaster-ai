// Evaluation campaigns, the director's side (steps 16-18, author's decisions, 2026-10-07): passages
// proposed from her works with ScoreLint's prediction, trimmed in draft, musicians invited by email,
// the campaign opened and closed, and the results exported.
import { createRequire } from 'node:module';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const url = process.env.SCOREMASTER_URL || 'http://127.0.0.1:8006';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const score = name => readFileSync(new URL('../../../test-scores/' + name, import.meta.url));
const waitIdle = () => page.waitForFunction(() => !document.querySelector('#upload-form button[type=submit]').disabled);
try {
  await page.goto(url);
  await page.locator('#login-mode').click();
  await page.locator('#login-name').fill('Directora evaluadora');
  await page.locator('#login-email').fill('evaluacion-' + Date.now() + '@banda.test');
  await page.locator('#login-password').fill('una contraseña larga');
  await page.locator('#login-submit').click();
  await page.locator('#app-shell').waitFor({ state: 'visible' });
  for (const name of ['evaluation_study.musicxml', 'high_density.musicxml']) {
    await page.locator('[data-view-target=repertoire]').click();
    await page.locator('#add-work').click();
    await page.locator('#file').setInputFiles({ name, mimeType: 'application/xml', buffer: score(name) });
    await waitIdle();
    await page.locator('#upload-form button[type=submit]').click();
    await page.locator('#work-detail').waitFor({ state: 'visible' });
    await waitIdle();
  }

  await page.locator('[data-view-target=evaluation]').click();
  await page.locator('#create-campaign').click();
  const editor = page.locator('#campaign-editor');
  await editor.getByLabel('Título').fill('Dificultad de pasajes de otoño');
  await editor.getByLabel('Instrucciones para los músicos').fill('Valora cada pasaje para una banda amateur media.');
  await editor.getByLabel(/evaluation_study\.musicxml/).check();
  await editor.getByLabel(/high_density\.musicxml/).check();
  await editor.getByLabel('Número de pasajes (entre 10 y 80)').fill('20');
  await editor.getByRole('button', { name: 'Proponer pasajes' }).click();
  const detail = page.locator('#campaign-detail');
  await detail.waitFor();
  assert.match(await detail.locator('h2').textContent(), /Dificultad de pasajes de otoño\s*Borrador/);
  const rows = detail.locator('.campaign-passages tbody tr');
  const proposed = await rows.count();
  assert.ok(proposed >= 5, 'passages proposed: ' + proposed);
  // The synthetic works are short: they give fewer than the 20 passages asked, and the director is told.
  assert.match(await page.locator('#campaign-notice').textContent(), new RegExp('Se han propuesto ' + proposed + ' de los 20 pasajes pedidos'));
  assert.match(await page.locator('#campaign-summary').textContent(), new RegExp('^' + proposed + ' pasajes · \\d+ críticos según ScoreLint · 0 músicos invitados$'));
  assert.match(await rows.first().locator('td').nth(4).textContent(), /^Grado [1-6]( · crítico)?$/, 'the director sees the prediction');
  console.log('PASS: the app proposes the passages of the chosen works with ScoreLint\'s prediction');

  await rows.first().getByRole('button', { name: 'Quitar' }).click();
  await page.waitForFunction(expected => document.querySelectorAll('#campaign-detail .campaign-passages tbody tr').length === expected, proposed - 1);
  await rows.first().getByRole('button', { name: 'Ver y escuchar' }).click();
  await page.waitForFunction(() => document.querySelector('#notation-score svg'), null, { timeout: 60000 });
  await page.locator('#notation-close').click();
  await page.locator('[data-view-target=evaluation]').click();
  console.log('PASS: a passage is removed in draft and opens in the score to listen to it');

  await page.locator('#campaign-emails').fill('musico1@banda.test, Musico2@banda.test\nmusico1@banda.test');
  await detail.getByRole('button', { name: 'Guardar invitaciones' }).click();
  await page.waitForFunction(() => document.querySelectorAll('.invitation-list li').length === 2);
  assert.deepEqual(await page.locator('.invitation-list li').evaluateAll(items => items.map(item => item.textContent)),
    ['musico1@banda.testAún no ha empezado', 'musico2@banda.testAún no ha empezado']);
  console.log('PASS: musicians are invited by email, each once');

  await detail.getByRole('button', { name: 'Abrir campaña' }).click();
  await detail.getByRole('button', { name: 'Abrir ahora' }).click();
  await page.waitForFunction(() => /Abierta/.test(document.querySelector('#campaign-detail h2').textContent));
  assert.equal(await detail.getByRole('button', { name: 'Quitar' }).count(), 0, 'passages are fixed once open');
  const [download] = await Promise.all([page.waitForEvent('download'), detail.getByRole('button', { name: 'Exportar resultados' }).click()]);
  assert.equal(download.suggestedFilename(), 'valoraciones-dificultad-de-pasajes-de-otono.json');
  const exported = JSON.parse(readFileSync(await download.path(), 'utf8'));
  assert.equal(exported.passages.length, proposed - 1);
  await detail.getByRole('button', { name: 'Cerrar campaña' }).click();
  await page.waitForFunction(() => /Cerrada/.test(document.querySelector('#campaign-detail h2').textContent));
  await page.waitForFunction(() => /Dificultad de pasajes de otoño\s*Cerrada/.test(document.querySelector('.campaign-item')?.textContent || ''));
  console.log('PASS: the campaign is opened, exported and closed');

  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'no horizontal scroll at 1440');
  await page.setViewportSize({ width: 390, height: 844 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'no horizontal scroll on a phone');
  assert.deepEqual(errors, []);
  console.log('PASS: the view fits the desktop and the phone');
} finally {
  await browser.close();
}
