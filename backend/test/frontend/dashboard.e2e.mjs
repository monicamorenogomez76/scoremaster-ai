import { createRequire } from 'node:module';
import { credentials, login } from './login.mjs';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const url = process.env.SCOREMASTER_URL || 'http://127.0.0.1:8006';
const browser = await chromium.launch();
const page = await browser.newPage({ locale: 'es-ES', viewport: { width: 1440, height: 1000 } });
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

  // The sections sit in a bar across the top (chosen 2026-10-25): the content takes the whole width.
  const bar = await page.locator('.topbar').boundingBox();
  for (const name of ['summary', 'repertoire', 'band', 'concerts', 'rehearsal', 'evaluation', 'settings']) {
    const item = await page.locator(`[data-view-target=${name}]`).boundingBox();
    assert.ok(item && item.y >= bar.y && item.y + item.height <= bar.y + bar.height, name + ' is in the top bar');
  }
  assert.equal(await page.locator('#mobile-menu-button').isVisible(), false, 'no menu button on a wide screen');
  assert.ok((await page.locator('.workspace').boundingBox()).x < 40, 'no side column before the content');
  console.log('PASS: the sections are in the top bar and the content takes the whole width');

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
  const planWorks = await page.locator('#rehearsal-content .rehearsal-block-work').allTextContents();
  assert.ok(planWorks.length === blocks.length && planWorks.every(text => text === 'Obra: Untitled score'), 'each planned block names its work');
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

  // A part the catalog does not know waits for the user before counting in the band template; what is confirmed is
  // learnt for the account's next works (2026-10-28).
  const melody = 'Melodía';
  const upload = async (part, name) => {
    await page.locator('[data-view-target=repertoire]').click();
    await page.locator('#add-work').click();
    await page.locator('#file').setInputFiles({ name, mimeType: 'application/xml',
      buffer: Buffer.from(fixture.toString().replace('<part-name>Clarinet</part-name>', `<part-name>${part}</part-name>`)
        .replace('<score-partwise version="4.0">', `<score-partwise version="4.0"><!-- ${name} -->`)) });
    await waitIdle();
    await page.locator('#upload-form button[type=submit]').click();
    await page.locator('#overview-result').waitFor({ state: 'attached' });
    await waitIdle();
    await page.locator('[data-view-target=band]').click();
  };
  await upload(melody + ' 1', 'melodia.musicxml');
  const confirmation = page.locator('#instrument-confirmation');
  await confirmation.waitFor();
  assert.match(await confirmation.textContent(), new RegExp(melody + ' 1 · Sin identificar'));
  assert.equal(await page.locator('#band-profile-editor').isHidden(), true, 'nothing counts before confirming');
  // Without GEMINI_API_KEY (as in CI) the AI proposes nothing and the panel says why.
  await page.locator('#propose-instruments').click();
  await confirmation.getByRole('alert').getByText(/necesita la IA/).waitFor();
  console.log('PASS: without a real AI, «Proponer con IA» says why and nothing changes');
  await page.getByLabel('Instrumento de ' + melody + ' 1').selectOption({ label: 'Clarinete en Si bemol' });
  await page.locator('#confirm-instruments').click();
  await page.getByLabel('Músicos de Clarinete en Si bemol').waitFor();
  assert.equal(await confirmation.count(), 0, 'confirmed parts leave the list');
  assert.equal(await page.getByLabel('Músicos de Clarinete en Si bemol').inputValue(), '0', 'the saved band applies to the next work');
  await page.locator('#band-content').getByText('Clarinete en Si bemol: falta en la plantilla; se necesita 1.').waitFor();
  console.log('PASS: an unknown part is confirmed from the catalog and the saved band applies to it');

  await upload(melody + ' 2', 'melodia-2.musicxml');
  await page.getByLabel('Músicos de Clarinete en Si bemol').waitFor();
  assert.equal(await confirmation.count(), 0, 'the next work comes recognised');
  console.log('PASS: the confirmed name is learnt for the next works');

  // «Otro instrumento…»: an instrument the catalog does not have is created for the account with its name and key.
  const own = 'Dulzaina';
  await upload(own + ' 1', 'dulzaina.musicxml');
  await confirmation.waitFor();
  await page.getByLabel('Instrumento de ' + own + ' 1').selectOption({ label: 'Otro instrumento…' });
  const ownForm = confirmation.locator('.own-instrument-form');
  assert.equal(await ownForm.getByLabel('Nombre').inputValue(), own, 'the part name without its number');
  await ownForm.getByLabel('Tonalidad').selectOption({ label: 'Mi♭' });
  await ownForm.getByLabel('Suena como').selectOption('oboe');
  await ownForm.getByLabel('Grupo de ensayo').selectOption({ label: 'Dobles cañas' });
  await ownForm.getByRole('button', { name: 'Crear instrumento' }).click();
  await ownForm.waitFor({ state: 'detached' });
  assert.equal(await page.getByLabel('Instrumento de ' + own + ' 1').inputValue().then(value => value.startsWith('own.')), true);
  await page.locator('#confirm-instruments').click();
  await page.getByLabel('Músicos de ' + own).waitFor();
  console.log('PASS: an instrument the catalog does not have is created for the account and confirmed');

  await page.locator('#sign-out').click();
  await page.locator('#login-screen').waitFor({ state: 'visible' });
  await page.reload();
  // The app checks the session first; wait until it shows either the access screen or the workspace.
  await page.waitForFunction(() => [...document.querySelectorAll('#login-screen, #app-shell')].some(node => !node.hidden));
  assert.equal(await page.locator('#login-screen').isVisible(), true, 'signing out closes the session');
  assert.equal((await page.request.post(url + '/analyze')).status(), 401, 'the API refuses requests without a session');
  assert.deepEqual(errors, []);
  console.log('PASS: signing out returns to the access screen');

  // The library survives signing out: reopen a work without uploading it again, then delete one.
  await login(page, director);
  await page.locator('[data-view-target=repertoire]').click();
  const works = page.locator('#works-content .works-item');
  await works.nth(3).waitFor();
  assert.equal(await works.count(), 4);
  const original = works.filter({ hasText: 'high_register.musicxml' });
  assert.match(await original.locator('.works-summary').textContent(), /^Grado \d · /);
  await original.locator('.work-open').click();
  await page.waitForFunction(() => document.querySelector('#full-score-rendering svg'), { timeout: 45000 });
  await page.locator('[data-view-target=band]').click();
  assert.equal(await page.getByLabel('Músicos de Clarinete en Si bemol').inputValue(), '0');
  await page.locator('[data-view-target=repertoire]').click();
  await page.locator('#back-to-list').click();
  for (const [file, left] of [['melodia.musicxml', 3], ['melodia-2.musicxml', 2], ['dulzaina.musicxml', 1]]) {
    const copy = works.filter({ hasText: file });
    await copy.locator('.work-delete').click();
    await copy.locator('.work-delete-confirm').click();
    await page.waitForFunction(count => document.querySelectorAll('#works-content .works-item').length === count, left);
  }
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
  assert.equal(await page.locator('#rehearsals-upcoming .agenda-calendar .calendar-slot').count(), 2, 'each saved rehearsal shows its coloured calendar');
  // «¿Por qué este plan?» (step 20): explained in demo mode, citing its blocks, which open their passage.
  const why = page.locator('#rehearsals-upcoming .rehearsal-why');
  await why.getByRole('button', { name: '¿Por qué este plan?' }).click();
  await why.locator('.explanation-source').waitFor();
  assert.match(await why.locator('.explanation-source').textContent(), /^Modo demo · .* sin IA\.$/);
  assert.match(await why.locator('.explanation-summary').textContent(), /^Ensayo de 60 minutos\./);
  await why.getByRole('button', { name: /Pasajes prioritarios · Untitled score · compases 1-4/ }).first().click();
  await page.waitForFunction(() => document.querySelector('#notation-score svg'), null, { timeout: 60000 });
  await page.locator('#notation-close').click();
  await page.locator('[data-view-target=rehearsal]').click();
  await why.getByRole('button', { name: 'Ocultar la explicación' }).click();
  console.log('PASS: a saved rehearsal explains its plan in demo mode and its blocks open their passage');
  await page.locator('[data-view-target=summary]').click();
  const next = page.locator('#summary-rehearsal');
  await next.getByText('Ensayo de hoy').waitFor();
  await next.getByRole('button', { name: 'Ver detalle' }).click();
  assert.deepEqual(await next.locator('.agenda-title').allTextContents(), ['Pasajes prioritarios', 'Calentamiento']);
  assert.deepEqual(await next.locator('.agenda-work').allTextContents(), ['Untitled score · cc. 1–4', 'Toda la banda · sin obra concreta']);
  assert.equal(await next.locator('.agenda-calendar .calendar-slot').count(), 2, 'the rehearsal of today has its coloured calendar');
  assert.match(await next.locator('.agenda-calendar .calendar-slot').nth(1).getAttribute('class'), /calendar-slot--warmup/, 'a hand-written warm-up is coloured as a warm-up');
  await next.getByRole('button', { name: 'Editar' }).click();
  await editor.waitFor({ state: 'visible' });
  assert.equal(await editor.getByLabel('Hora').inputValue(), '19:00');
  assert.deepEqual(errors, []);
  console.log('PASS: a rehearsal is planned with an agenda that names the work of each block');

  // The app proposes the agenda itself from the analysis of the chosen works.
  await page.locator('#create-rehearsal').click();
  await editor.getByLabel('Duración (minutos)').fill('60');
  await editor.getByLabel('Untitled score').check();
  await editor.getByRole('button', { name: 'Proponer agenda' }).click();
  await editor.locator('.agenda-block').nth(1).waitFor();
  assert.equal(await blocksOf().nth(0).getByLabel('Título').inputValue(), 'Calentamiento');
  const proposedWorks = [];
  for (let index = 1; index < await blocksOf().count(); index++) {
    proposedWorks.push(await blocksOf().nth(index).getByLabel('Obra').evaluate(select => select.selectedOptions[0].textContent));
  }
  assert.ok(proposedWorks.length > 0 && proposedWorks.every(title => title === 'Untitled score'), 'every proposed block names its work');
  assert.match(await editor.locator('#agenda-time').textContent(), /60 de 60 minutos/);
  const slots = editor.locator('.agenda-calendar .calendar-slot');
  assert.equal(await slots.count(), await blocksOf().count(), 'the agenda calendar shows every block');
  assert.match(await slots.first().getAttribute('class'), /calendar-slot--warmup/);
  assert.match(await slots.nth(1).locator('.calendar-work').textContent(), /Untitled score/);
  assert.equal(await blocksOf().nth(0).getByLabel('Tipo').inputValue(), 'warmup');
  assert.deepEqual(errors, []);
  console.log('PASS: the app proposes the agenda of the chosen works, every block with its work');

  // The summary looks like its mock-up: everything at a glance on a computer.
  await page.locator('#rehearsal-editor').getByRole('button', { name: 'Cancelar' }).click();
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.locator('[data-view-target=summary]').click();
  const todayCard = page.locator('#summary-rehearsal');
  await todayCard.locator('.agenda-calendar').waitFor();
  assert.deepEqual(await todayCard.locator('.calendar-work').allTextContents(), ['Untitled score', 'Toda la banda'],
    'each coloured box names its work');
  assert.equal(await todayCard.locator('.agenda-list').count(), 0, 'the agenda list is a detail asked for');
  await todayCard.getByRole('button', { name: 'Ver detalle' }).click();
  await todayCard.locator('.agenda-list').waitFor();
  await todayCard.getByRole('button', { name: 'Ocultar detalle' }).click();
  // No panel repeats what the cards already say (decided 2026-10-06).
  assert.equal(await page.locator('#summary-assistant').count(), 0);
  const worksCard = page.locator('#summary-works'), worksBox = await worksCard.boundingBox(), rehearsalBox = await todayCard.boundingBox();
  assert.ok(worksBox.x > rehearsalBox.x + rehearsalBox.width - 1, 'the works in preparation are a column on the right');
  assert.equal(await page.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight + 2), true,
    'the summary fits on a computer screen');
  assert.equal(await todayCard.locator('.next-step').count(), 0, 'without a concert there is no step to suggest');
  assert.equal(await page.locator('#summary-coverage').count(), 0, 'without a concert there is no coverage to show');
  await page.setViewportSize({ width: 1440, height: 1000 });
  assert.deepEqual(errors, []);
  console.log('PASS: the summary shows everything at a glance without repeating information')
} finally {
  await browser.close();
}
