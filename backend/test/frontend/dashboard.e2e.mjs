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

  const sharedNames = await page.evaluate(() => {
    const part = (id, step) => `<part id="${id}"><measure number="1"><attributes><divisions>1</divisions></attributes><note><pitch><step>${step}</step><octave>4</octave></pitch><duration>4</duration></note></measure></part>`;
    const xml = '<score-partwise><part-list>' + ['P1', 'P2', 'P3'].map(id => `<score-part id="${id}"><part-name>Voice</part-name></score-part>`).join('') +
      '</part-list>' + part('P1', 'C') + part('P2', 'D') + part('P3', 'E') + '</score-partwise>';
    const result = new DOMParser().parseFromString(window.scoremasterWorkspace.filterPassage(xml, 'Voice 3', '1'), 'application/xml');
    return { declared: [...result.querySelectorAll('score-part')].map(node => node.id), parts: [...result.querySelectorAll('part')].map(node => node.id),
      step: result.querySelector('step').textContent };
  });
  assert.deepEqual(sharedNames, { declared: ['P3'], parts: ['P3'], step: 'E' }, 'a numbered part keeps only that part and its notes');
  const literalNames = await page.evaluate(() => {
    const part = (id, step) => `<part id="${id}"><measure number="1"><attributes><divisions>1</divisions></attributes><note><pitch><step>${step}</step><octave>4</octave></pitch><duration>4</duration></note></measure></part>`;
    const xml = '<score-partwise><part-list><score-part id="P1"><part-name>B♭ Cornet 1</part-name></score-part>' +
      '<score-part id="P2"><part-name>B♭ Cornet 2</part-name></score-part><score-part id="P3"><part-name>Trombone 3 &amp;\nBass Trombone</part-name></score-part>' +
      '</part-list>' + part('P1', 'C') + part('P2', 'D') + part('P3', 'E') + '</score-partwise>';
    const pick = name => new DOMParser().parseFromString(window.scoremasterWorkspace.filterPassage(xml, name, '1'), 'application/xml').querySelector('part').id;
    return [pick('B♭ Cornet 2'), pick('Trombone 3 & Bass Trombone')];
  });
  assert.deepEqual(literalNames, ['P2', 'P3'], 'numbers and line breaks inside part names still find the part');
  console.log('PASS: passages of parts sharing a name contain only the selected part');

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
  const blocks = await page.locator('#rehearsal-content .rehearsal-block-title').allTextContents();
  assert.match(blocks[0], /^Seccional · Viento madera · c\. 1/);
  assert.match(blocks.at(-1), /^Tutti para juntar/);
  assert.match(await page.locator('#rehearsal-content').textContent(), /Planificado: \d+ de 90 minutos/);
  console.log('PASS: rehearsal duration recalculates the plan with sectional blocks and a final tutti');

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
  await page.route('**/youtube/search?*', route => route.fulfill({ contentType: 'application/json',
    body: JSON.stringify({ videos: [], search_url: 'https://www.youtube.com/results?search_query=High+Density+Study' }) }));
  await page.locator('[data-view-target=analyze]').click();
  await page.locator('[data-view-target=videos]').click();
  const videos = page.locator('#videos-content');
  await videos.getByRole('button', { name: 'Buscar' }).click();
  await videos.getByRole('link', { name: /Abrir búsqueda de “High Density Study”/ }).waitFor();
  const manualLink = videos.getByLabel('Enlace de vídeo de YouTube');
  await manualLink.fill('https://example.com/watch?v=dQw4w9WgXcQ');
  await videos.getByRole('button', { name: 'Reproducir enlace' }).click();
  assert.equal(await manualLink.evaluate(input => input.validity.valid), false, 'non-YouTube links are rejected');
  assert.equal(await videos.locator('iframe').count(), 0);
  await manualLink.fill('https://youtu.be/dQw4w9WgXcQ');
  await videos.getByRole('button', { name: 'Reproducir enlace' }).click();
  assert.equal(await videos.locator('iframe').getAttribute('src'), 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ');
  await page.unroute('**/youtube/search?*');
  console.log('PASS: video search falls back to a YouTube link and plays only valid links');

  await page.locator('#sign-out').click();
  assert.equal(await page.locator('#login-screen').isVisible(), true);
  await page.reload();
  assert.equal(await page.locator('#login-screen').isVisible(), true, 'leaving the demo is remembered');
  assert.deepEqual(errors, []);
  console.log('PASS: leaving the demo returns to the access screen');
} finally {
  await browser.close();
}
