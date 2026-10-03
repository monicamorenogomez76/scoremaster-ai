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
const fixture = readFileSync(new URL('../../../test-scores/high_density.musicxml', import.meta.url));
const view = name => page.locator(`[data-view=${name}]`);
const waitIdle = () => page.waitForFunction(() => !document.querySelector('#upload-form button[type=submit]').disabled);
try {
  await page.goto(url);
  await page.locator('#enter-demo').click();
  await page.reload();
  assert.equal(await page.locator('#app-shell').isVisible(), true, 'demo session survives a reload');
  assert.equal(await page.locator('[data-view-target=overview]').getAttribute('aria-current'), 'page');
  console.log('PASS: demo session and navigation state');

  await page.locator('[data-view-target=analyze]').click();
  await page.locator('#file').setInputFiles({ name: 'high_density.musicxml', mimeType: 'application/xml', buffer: fixture });
  await waitIdle();
  await page.locator('#upload-form button[type=submit]').click();
  await page.locator('#overview-result').waitFor({ state: 'attached' });
  await waitIdle();

  await page.locator('[data-view-target=band]').click();
  const players = page.getByLabel('Músicos para Clarinete');
  assert.equal(await players.inputValue(), '1');
  assert.match(await page.locator('#band-content').textContent(), /100%.*Compatible/);
  await players.fill('0');
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/analyze', async route => { await gate; await route.continue(); });
  await page.locator('#update-analysis').click();
  assert.equal(await page.locator('#update-analysis').isDisabled(), true, 'recalculation shows progress');
  release();
  await page.locator('#band-content').getByText('Clarinete: falta en la plantilla; se necesita 1.').waitFor();
  await page.unroute('**/analyze');
  assert.equal(await view('band').isVisible(), true, 'recalculation keeps the band view');
  assert.equal(await players.inputValue(), '0');
  console.log('PASS: BandFit recalculates from the edited template without leaving the view');

  await page.locator('[data-view-target=rehearsal]').click();
  await page.locator('#total-minutes').fill('90');
  await page.locator('#recalculate-rehearsal').click();
  await page.locator('#rehearsal-content').getByText('Duración total: 90 minutos').waitFor();
  assert.equal(await view('rehearsal').isVisible(), true);
  assert.equal(await page.getByLabel('Músicos para Clarinete').inputValue(), '0', 'rehearsal keeps the band template');
  console.log('PASS: rehearsal duration recalculates the plan');

  await page.locator('[data-view-target=overview]').click();
  assert.equal(await page.locator('#overview-priority-title').textContent(), 'Clarinete · compases 1');
  assert.equal(await page.locator('#overview-priority-detail').textContent(), 'Alta densidad rítmica');
  await page.locator('#open-priority').click();
  assert.equal(await view('difficulty').isVisible(), true);
  await page.locator('#difficulty-content .tree-node').first().click();
  await page.locator('#difficulty-content .tree-node').first().click();
  assert.match(await page.locator('.tree-nav').textContent(), /Todas las familias›Viento madera› Clarinete/);
  await page.getByRole('button', { name: 'Todas las familias' }).click();
  assert.equal(await page.locator('#difficulty-content .tree-node').count(), 1);
  console.log('PASS: overview priority opens the difficulty explorer and its breadcrumb');

  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('#mobile-menu-button').click();
  assert.equal(await page.locator('#mobile-menu-button').getAttribute('aria-expanded'), 'true');
  await page.locator('[data-view-target=videos]').click();
  assert.equal(await page.locator('#mobile-menu-button').getAttribute('aria-expanded'), 'false');
  assert.equal(await view('videos').isVisible(), true);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
  console.log('PASS: mobile menu opens, navigates and closes');

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.locator('#sign-out').click();
  assert.equal(await page.locator('#login-screen').isVisible(), true);
  await page.reload();
  assert.equal(await page.locator('#login-screen').isVisible(), true, 'leaving the demo is remembered');
  assert.deepEqual(errors, []);
  console.log('PASS: leaving the demo returns to the access screen');
} finally {
  await browser.close();
}
