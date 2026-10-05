import { createRequire } from 'node:module';
import { credentials, login } from './login.mjs';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const url = process.env.SCOREMASTER_URL || 'http://127.0.0.1:8006';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const fixture = readFileSync(new URL('../../../test-scores/high_register.musicxml', import.meta.url));
const view = name => page.locator(`[data-view=${name}]`);
const waitIdle = () => page.waitForFunction(() => !document.querySelector('#upload-form button[type=submit]').disabled);
try {
  await page.goto(url);
  await page.locator('#login-email').fill(credentials.email);
  await page.locator('#login-password').fill('no-es-la-contraseña');
  await page.locator('#login-submit').click();
  assert.equal(await page.locator('#login-error').textContent(), 'Email o contraseña incorrectos.');
  assert.equal(await page.locator('#app-shell').isVisible(), false);
  await login(page);
  await page.reload();
  await page.locator('#app-shell').waitFor({ state: 'visible' });
  assert.equal(await page.locator('[data-view-target=summary]').getAttribute('aria-current'), 'page');
  assert.equal(await page.locator('#current-user').textContent(), 'Usuario demo');
  console.log('PASS: sign-in rejects a wrong password and the session survives a reload');

  // The rest of the walkthrough uses a new account, so saved works and band start empty.
  const director = { email: 'directora-' + Date.now() + '@banda.test', password: 'una contraseña larga' };
  await page.locator('#sign-out').click();
  await page.locator('#login-screen').waitFor({ state: 'visible' });
  await page.locator('#login-mode').click();
  await page.locator('#login-name').fill('Nueva directora');
  await page.locator('#login-email').fill(director.email);
  await page.locator('#login-password').fill(director.password);
  await page.locator('#login-submit').click();
  await page.locator('#app-shell').waitFor({ state: 'visible' });
  assert.equal(await page.locator('#current-user').textContent(), 'Nueva directora');
  console.log('PASS: a new account can be created from the access screen');

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
  const several = await page.evaluate(() => {
    const part = id => `<part id="${id}"><measure number="1"><attributes><divisions>1</divisions></attributes><note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration></note></measure></part>`;
    const xml = '<score-partwise><part-list>' + [['P1', 'Flute'], ['P2', 'Oboe'], ['P3', 'Tuba']].map(([id, name]) =>
      `<score-part id="${id}"><part-name>${name}</part-name></score-part>`).join('') + '</part-list>' + part('P1') + part('P2') + part('P3') + '</score-partwise>';
    const result = new DOMParser().parseFromString(window.scoremasterWorkspace.filterPassage(xml, ['Flute', 'Tuba'], '1'), 'application/xml');
    return [...result.querySelectorAll('part')].map(node => node.id);
  });
  assert.deepEqual(several, ['P1', 'P3'], 'a sectional passage keeps every instrument of the block');
  console.log('PASS: a passage can keep several instruments');

  await page.locator('[data-view-target=repertoire]').click();
  await page.locator('#add-work').click();
  await page.locator('#file').setInputFiles({ name: 'high_register.musicxml', mimeType: 'application/xml', buffer: fixture });
  await waitIdle();
  await page.locator('#upload-form button[type=submit]').click();
  await page.locator('#overview-result').waitFor({ state: 'attached' });
  await waitIdle();

  await page.locator('[data-view-target=band]').click();
  const players = page.getByLabel('Músicos de Clarinete en Si bemol');
  assert.equal(await players.inputValue(), '1');
  assert.equal(await page.locator('#instrument-confirmation').count(), 0, 'identified parts need no confirmation');
  assert.match(await page.locator('#band-content').textContent(), /100%.*Compatible/);
  await players.fill('0');
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/analyze', async route => { await gate; await route.continue(); });
  await page.locator('#update-analysis').click();
  assert.equal(await page.locator('#update-analysis').isDisabled(), true, 'recalculation shows progress');
  release();
  await page.locator('#band-content').getByText('Clarinete en Si bemol: falta en la plantilla; se necesita 1.').waitFor();
  await page.unroute('**/analyze');
  assert.equal(await view('band').isVisible(), true, 'recalculation keeps the band view');
  assert.equal(await players.inputValue(), '0');
  console.log('PASS: BandFit recalculates from the edited template without leaving the view');

  await page.locator('[data-view-target=rehearsal]').click();
  await page.locator('#total-minutes').fill('90');
  await page.locator('#recalculate-rehearsal').click();
  await page.locator('#rehearsal-content').getByText('Duración total: 90 minutos').waitFor();
  assert.equal(await view('rehearsal').isVisible(), true);
  assert.equal(await page.getByLabel('Músicos de Clarinete en Si bemol').inputValue(), '0', 'rehearsal keeps the band template');
  const blocks = await page.locator('#rehearsal-content .rehearsal-block-title').allTextContents();
  assert.match(blocks[0], /^Seccional · Clarinetes · c\. 1/);
  assert.match(blocks.at(-1), /^Tutti para juntar/);
  assert.match(await page.locator('#rehearsal-content').textContent(), /Planificado: \d+ de 90 minutos/);
  console.log('PASS: rehearsal duration recalculates the plan with sectional blocks and a final tutti');

  await page.locator('#rehearsal-start').fill('18:30');
  const calendar = page.locator('.rehearsal-calendar .calendar-block');
  assert.ok(await calendar.count() >= 2, 'one calendar block per rehearsal block');
  assert.match(await calendar.first().getAttribute('aria-label'), /^18:30–\d\d:\d\d · Seccional · Clarinetes · c\. 1/);
  await calendar.first().click();
  await page.waitForFunction(() => document.querySelector('#notation-score svg'));
  assert.deepEqual(await page.evaluate(() => window.scoremasterWorkspace.getPassage().instruments), ['Clarinet']);
  assert.match(await page.locator('#notation-title').textContent(), /^Clarinetes · compases 1/);
  await page.locator('#notation-close').click();
  console.log('PASS: the rehearsal calendar opens the score at the block with its instruments');

  await page.locator('[data-view-target=repertoire]').click();
  await page.locator('#work-tab-difficulty').click();
  assert.equal(await page.locator('#overview-priority-title').textContent(), 'Clarinete · compases 1');
  assert.equal(await page.locator('#overview-priority-detail').textContent(), 'Registro agudo · Alta densidad rítmica · Intervalos amplios');
  assert.equal(await page.locator('#difficulty-content').isVisible(), true, 'the analysis shows the dashboard and the difficulty together');
  await page.locator('#open-priority').click();
  assert.equal(await page.locator('#work-tab-difficulty').getAttribute('aria-selected'), 'true');
  await page.waitForFunction(() => { const box = document.querySelector('#difficulty-content').getBoundingClientRect(); return box.top >= 0 && box.top < window.innerHeight; });
  await page.locator('#difficulty-content .tree-node').first().click();
  await page.locator('#difficulty-content .tree-node').first().click();
  assert.match(await page.locator('.tree-nav').textContent(), /Todas las familias›Viento madera› Clarinete/);
  await page.getByRole('button', { name: 'Todas las familias' }).click();
  assert.equal(await page.locator('#difficulty-content .tree-node').count(), 1);
  console.log('PASS: overview priority opens the difficulty explorer and its breadcrumb');

  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('#mobile-menu-button').click();
  assert.equal(await page.locator('#mobile-menu-button').getAttribute('aria-expanded'), 'true');
  await page.locator('[data-view-target=band]').click();
  assert.equal(await page.locator('#mobile-menu-button').getAttribute('aria-expanded'), 'false');
  assert.equal(await view('band').isVisible(), true);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
  console.log('PASS: mobile menu opens, navigates and closes');

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.route('**/youtube/search?*', route => route.fulfill({ contentType: 'application/json',
    body: JSON.stringify({ videos: [], search_url: 'https://www.youtube.com/results?search_query=High+Density+Study' }) }));
  await page.locator('[data-view-target=repertoire]').click();
  await page.locator('#work-tab-recordings').click();
  const videos = page.locator('#videos-content');
  await videos.getByRole('button', { name: 'Buscar' }).click();
  await videos.getByRole("link", { name: /^Abrir búsqueda de “/ }).waitFor();
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

  // A part the catalog does not know waits for the user before counting in the band template.
  const unnamed = Buffer.from(fixture.toString().replace('<part-name>Clarinet</part-name>', '<part-name>Melodía</part-name>'));
  await page.locator('[data-view-target=repertoire]').click();
  await page.locator('#add-work').click();
  await page.locator('#file').setInputFiles({ name: 'melodia.musicxml', mimeType: 'application/xml', buffer: unnamed });
  await waitIdle();
  await page.locator('#upload-form button[type=submit]').click();
  await page.locator('#overview-result').waitFor({ state: 'attached' });
  await waitIdle();
  await page.locator('[data-view-target=band]').click();
  const confirmation = page.locator('#instrument-confirmation');
  await confirmation.waitFor();
  assert.match(await confirmation.textContent(), /Melodía · Sin identificar/);
  assert.equal(await page.locator('#band-profile-editor').isHidden(), true, 'nothing counts before confirming');
  await page.getByLabel('Instrumento de Melodía').selectOption({ label: 'Clarinete en Si bemol' });
  await page.locator('#confirm-instruments').click();
  await page.getByLabel('Músicos de Clarinete en Si bemol').waitFor();
  assert.equal(await confirmation.count(), 0, 'confirmed parts leave the list');
  assert.equal(await page.getByLabel('Músicos de Clarinete en Si bemol').inputValue(), '0', 'the saved band applies to the next work');
  await page.locator('#band-content').getByText('Clarinete en Si bemol: falta en la plantilla; se necesita 1.').waitFor();
  console.log('PASS: an unknown part is confirmed from the catalog and the saved band applies to it');

  await page.locator('#sign-out').click();
  await page.locator('#login-screen').waitFor({ state: 'visible' });
  await page.reload();
  assert.equal(await page.locator('#login-screen').isVisible(), true, 'signing out closes the session');
  assert.equal((await page.request.post(url + '/analyze')).status(), 401, 'the API refuses requests without a session');
  assert.deepEqual(errors, []);
  console.log('PASS: signing out returns to the access screen');

  // The library survives signing out: reopen a work without uploading it again, then delete one.
  await login(page, director);
  await page.locator('[data-view-target=repertoire]').click();
  const works = page.locator('#works-content .works-item');
  await works.nth(1).waitFor();
  assert.equal(await works.count(), 2);
  const original = works.filter({ hasText: 'high_register.musicxml' });
  assert.match(await original.locator('.works-summary').textContent(), /^Grado \d · /);
  await original.locator('.work-open').click();
  await page.waitForFunction(() => document.querySelector('#full-score-rendering svg'), { timeout: 45000 });
  await page.locator('[data-view-target=band]').click();
  assert.equal(await page.getByLabel('Músicos de Clarinete en Si bemol').inputValue(), '0');
  await page.locator('[data-view-target=repertoire]').click();
  await page.locator('#back-to-list').click();
  const copy = works.filter({ hasText: 'melodia.musicxml' });
  await copy.locator('.work-delete').click();
  await copy.locator('.work-delete-confirm').click();
  await page.waitForFunction(() => document.querySelectorAll('#works-content .works-item').length === 1);
  assert.deepEqual(errors, []);
  console.log('PASS: saved works reopen after signing in again and can be deleted');

  // The summary shows the works the band is preparing and, as priorities, their critical passages.
  await original.locator('.work-preparation').selectOption('preparing');
  await page.waitForResponse(response => response.url().includes('/works/') && response.request().method() === 'PATCH');
  await page.locator('[data-view-target=summary]').click();
  await page.locator('#summary-works').getByText('high_register.musicxml').waitFor();
  const priorities = page.locator('#summary-priorities');
  await priorities.getByText('Viento madera').waitFor();
  assert.match(await priorities.textContent(), /c\. 1.*Análisis/);
  await priorities.getByRole('button', { name: 'Untitled score' }).click();
  // The same work was open before, so its score may already be drawn: wait for the detail itself.
  await page.locator('#work-detail').waitFor({ state: 'visible', timeout: 45000 });
  assert.equal(await page.locator('[data-view-target=repertoire]').getAttribute('aria-current'), 'page', 'each priority opens its work');
  assert.deepEqual(errors, []);
  console.log('PASS: the summary lists the works in preparation and their passages as priorities');

  // A saved rehearsal: planned from the summary, with an agenda whose blocks name their work.
  await page.locator('[data-view-target=summary]').click();
  await page.locator('#plan-rehearsal').click();
  const editor = page.locator('#rehearsal-editor');
  await editor.waitFor({ state: 'visible' });
  const today = await page.evaluate(() => { const now = new Date(); return [now.getFullYear(), String(now.getMonth() + 1).padStart(2, '0'), String(now.getDate()).padStart(2, '0')].join('-'); });
  await editor.getByLabel('Fecha').fill(today);
  await editor.getByLabel('Hora').fill('19:00');
  await editor.getByLabel('Duración (minutos)').fill('60');
  await editor.getByLabel('Untitled score').check();
  await editor.getByRole('button', { name: 'Añadir bloque' }).click();
  const blocksOf = () => editor.locator('.agenda-block');
  await blocksOf().nth(0).getByLabel('Título').fill('Calentamiento');
  await blocksOf().nth(0).getByLabel('Minutos').fill('15');
  await editor.getByRole('button', { name: 'Añadir bloque' }).click();
  await blocksOf().nth(1).getByLabel('Título').fill('Pasajes prioritarios');
  await blocksOf().nth(1).getByLabel('Minutos').fill('25');
  await blocksOf().nth(1).getByLabel('Obra').selectOption({ label: 'Untitled score' });
  await blocksOf().nth(1).getByLabel('Compases').fill('1-4');
  assert.match(await editor.locator('#agenda-time').textContent(), /40 de 60 minutos.*quedan 20/);
  await blocksOf().nth(1).getByRole('button', { name: 'Subir' }).click();
  await editor.getByRole('button', { name: 'Guardar ensayo' }).click();
  await page.locator('#rehearsals-upcoming').getByText('Hoy · 19:00').waitFor();
  await page.locator('[data-view-target=summary]').click();
  const next = page.locator('#summary-rehearsal');
  await next.getByText('Ensayo de hoy').waitFor();
  assert.deepEqual(await next.locator('.agenda-title').allTextContents(), ['Pasajes prioritarios', 'Calentamiento']);
  assert.deepEqual(await next.locator('.agenda-work').allTextContents(), ['Untitled score · cc. 1–4', 'Toda la banda · sin obra concreta']);
  await next.getByRole('button', { name: 'Editar' }).click();
  await editor.waitFor({ state: 'visible' });
  assert.equal(await editor.getByLabel('Hora').inputValue(), '19:00');
  assert.deepEqual(errors, []);
  console.log('PASS: a rehearsal is planned with an agenda that names the work of each block');
} finally {
  await browser.close();
}
