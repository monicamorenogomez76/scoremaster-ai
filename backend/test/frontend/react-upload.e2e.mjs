import { createRequire } from 'node:module';
import { csrfToken, login } from './login.mjs';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const url = process.env.SCOREMASTER_URL || 'http://127.0.0.1:8006';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const fixture = readFileSync(new URL('../../../test-scores/high_density.musicxml', import.meta.url));
const select = async () => {
  if (!(await page.locator('#upload-form').isVisible())) await page.locator('#add-work').click();
  await page.locator('#file').setInputFiles({ name: 'synthetic.musicxml', mimeType: 'application/xml', buffer: fixture });
  await page.waitForFunction(() => !document.querySelector('#upload-form button[type=submit]').disabled);
};
try {
  await page.goto(url);
  await login(page);
  await page.locator('[data-view-target=repertoire]').click();
  await select();
  await page.route('**/analyze', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'No se pudo guardar el análisis.' }) }));
  await page.locator('#upload-form button[type=submit]').click();
  await page.getByRole('alert').filter({ hasText: 'No se pudo guardar' }).waitFor();
  assert.equal(await page.locator('#embedded-score').isVisible(), false);
  assert.equal(await page.locator('#upload-form button[type=submit]').isEnabled(), true);
  await page.unroute('**/analyze');
  console.log('PASS: persistence error is accessible and permits retry without opening notation');

  await page.route('**/analyze', route => route.fulfill({ status: 502, contentType: 'text/html', body: '<h1>Bad gateway</h1>' }));
  await page.locator('#upload-form button[type=submit]').click();
  await page.getByRole('alert').filter({ hasText: 'respuesta no válida' }).waitFor();
  await page.unroute('**/analyze');
  console.log('PASS: non-JSON server error gives a readable message');

  const response = await page.request.post(url + '/analyze', { multipart: {
    file: { name: 'synthetic.musicxml', mimeType: 'application/xml', buffer: fixture },
    band_profile: '{}', total_minutes: '60',
  }, headers: { 'X-CSRF-Token': await csrfToken(page, url) } });
  assert.equal(response.status(), 200);
  const saved = await response.json();
  let release, started;
  const gate = new Promise(resolve => { release = resolve; });
  const received = new Promise(resolve => { started = resolve; });
  await page.route('**/analyze', async route => {
    started(); await gate;
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(saved) }).catch(() => {});
  });
  await page.locator('#upload-form button[type=submit]').click();
  await received;
  assert.equal(await page.locator('#upload-form').getAttribute('aria-busy'), 'true');
  assert.match(await page.locator('#result').textContent(), /Analizando la partitura/);
  await page.locator('[data-view-target=summary]').click();
  assert.equal(await page.locator('[data-view=summary]').isVisible(), true);
  await page.locator('[data-view-target=repertoire]').click();
  await page.locator('#new-score').click();
  release();
  await page.waitForFunction(() => !document.querySelector('#upload-form button[type=submit]').disabled);
  await page.unroute('**/analyze');
  assert.equal(await page.locator('#file').evaluate(input => input.files.length), 0);
  assert.equal(await page.locator('#overview-result').isVisible(), false);
  assert.equal(await page.locator('#embedded-score').isVisible(), false);
  assert.equal(await page.locator('#result').isVisible(), false);
  assert.equal(await page.locator('#file').evaluate(input => input === document.activeElement), true);
  console.log('PASS: loading leaves navigation usable; reset aborts and discards a late result');

  await select();
  await page.locator('#upload-form button[type=submit]').click();
  await page.waitForFunction(() => document.querySelector('#full-score-rendering svg') && document.querySelector('#full-score-status').getAttribute('aria-busy') === 'false', { timeout: 45000 });
  assert.equal(await page.locator('#embedded-score').isVisible(), true);
  assert.deepEqual(errors, []);
  await page.screenshot({ path: '/tmp/scoremaster-react-upload.png', fullPage: true });
  console.log('PASS: a new analysis succeeds after cancellation without page errors');
} finally {
  await browser.close();
}
