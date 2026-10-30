// Accessibility audit (WCAG 2.1 A and AA, a legal requirement, 2026-10-26): axe-core checks every view of the
// app, signed out and signed in, in the light and the dark theme and with the phone menu open. Any violation fails
// the walkthrough, so no change can break accessibility unnoticed. axe-core is installed next to Playwright
// (AXE_MODULE, or found from PLAYWRIGHT_MODULE's folder), never as a dependency of the app.
// The test browser ignores the app's CSP only to inject axe; the app's CSP itself is checked elsewhere. It asks for
// reduced motion (WCAG 2.3.3), so no view is measured halfway through its entrance.
import { createRequire } from 'node:module';
import { dirname } from 'node:path';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { login } from './login.mjs';
const require = createRequire(import.meta.url);
const playwrightModule = process.env.PLAYWRIGHT_MODULE || 'playwright';
const { chromium } = require(playwrightModule);
const axePath = process.env.AXE_MODULE
  || require.resolve('axe-core/axe.min.js', { paths: [dirname(require.resolve(playwrightModule))] });
const url = process.env.SCOREMASTER_URL || 'http://127.0.0.1:8006';
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
const violations = [];

async function audit(page, where) {
  await page.addScriptTag({ path: axePath });
  const result = await page.evaluate(tags => window.axe.run(document, { runOnly: { type: 'tag', values: tags } }), TAGS);
  const found = result.violations.map(item => `${item.id} (${item.impact}): ${item.help} — `
    + item.nodes.slice(0, 3).map(node => node.target.join(' ')).join(' | '));
  violations.push(...found.map(text => `${where}: ${text}`));
  if (!found.length) console.log('PASS: no WCAG A/AA violations in ' + where);
}

const browser = await chromium.launch();
try {
  for (const scheme of ['light', 'dark']) {
    const page = await browser.newPage({ locale: 'es-ES', viewport: { width: 1440, height: 900 }, colorScheme: scheme, reducedMotion: 'reduce', bypassCSP: true });
    await page.goto(url);
    await page.locator('#login-screen').waitFor({ state: 'visible' });
    await audit(page, `access screen (${scheme})`);
    // Password recovery: asking for the link, and the form a link opens (this one is not valid).
    await page.locator('#login-forgot').click();
    await page.locator('#login-email').fill('nadie@banda.test');
    await page.locator('#login-submit').click();
    await page.locator('#login-notice').waitFor();
    await audit(page, `password recovery (${scheme})`);
    await page.goto('about:blank');   // a new page, as when the link is opened from the email
    await page.goto(url + '/#reset=not-a-valid-link');
    await page.locator('#login-password').fill('una contraseña larga');
    await page.locator('#login-submit').click();
    await page.locator('#login-error').waitFor();
    if (new URL(page.url()).hash) throw new Error('the recovery token stays in the address bar');
    await audit(page, `new password (${scheme})`);
    await page.locator('#login-mode').click();
    await login(page);
    await page.waitForLoadState('networkidle');
    for (const [view, name] of [['summary', 'Resumen'], ['repertoire', 'Repertorio'], ['band', 'Mi banda'],
      ['concerts', 'Conciertos'], ['rehearsal', 'Ensayos'], ['evaluation', 'Valoraciones'], ['settings', 'Configuración']]) {
      await page.locator(`[data-view-target=${view}]`).click();
      await page.locator(`[data-view=${view}]`).waitFor({ state: 'visible' });
      await page.waitForLoadState('networkidle');
      await audit(page, `${name} (${scheme})`);
    }
    // «Añadir obra», with the PDF option when the server has a reader (CI sets one that is never called).
    await page.locator('[data-view-target=repertoire]').click();
    await page.locator('#add-work').click();
    await page.locator('#upload-root').waitFor({ state: 'visible' });
    await page.waitForLoadState('networkidle');
    await audit(page, `Añadir obra (${scheme})`);
    await page.close();
  }
  // Configuración › Instrumentos is shown only to the administration (ADMIN_EMAILS has this account in CI).
  const admin = await browser.newPage({ locale: 'es-ES', viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce', bypassCSP: true });
  await admin.goto(url);
  const adminEmail = process.env.E2E_A11Y_ADMIN_EMAIL || 'admin-a11y@banda.test';
  for (const mode of ['register', 'sign in']) {   // the account may exist from an earlier run
    await admin.locator('#login-mode').click();
    if (mode === 'register') await admin.locator('#login-name').fill('Administración');
    await admin.locator('#login-email').fill(adminEmail);
    await admin.locator('#login-password').fill('una contraseña larga');
    await admin.locator('#login-submit').click();
    await Promise.race([admin.locator('#app-shell').waitFor({ state: 'visible' }), admin.locator('#login-error').waitFor()]);
    if (await admin.locator('#app-shell').isVisible()) break;
  }
  await admin.locator('[data-view-target=settings]').click();
  await admin.locator('#settings-instruments-title').waitFor({ state: 'visible' });
  await admin.locator('.instrument-admin-list details').first().locator('summary').click();
  await admin.locator('.instrument-new summary').click();
  // dashboard.e2e.mjs, run before in CI, confirmed «Melodía» as a clarinet in the demo account (2026-10-29).
  await admin.locator('#instrument-learned-title').waitFor({ state: 'visible' });
  assert.match(await admin.locator('.instrument-learned').textContent(), /Melodía → Clarinete en Si bemol/);
  await audit(admin, 'Configuración › Instrumentos');
  // «Otro instrumento…» for a part the catalog does not know (never confirmed, so it stays unknown in every run).
  const unknownPart = readFileSync(new URL('../../../test-scores/high_register.musicxml', import.meta.url), 'utf8')
    .replace('<part-name>Clarinet</part-name>', '<part-name>Gaita de fole</part-name>');
  await admin.locator('[data-view-target=repertoire]').click();
  await admin.locator('#add-work').click();
  await admin.locator('#file').setInputFiles({ name: 'gaita.musicxml', mimeType: 'application/xml', buffer: Buffer.from(unknownPart) });
  const uploadIdle = () => admin.waitForFunction(() => !document.querySelector('#upload-form button[type=submit]').disabled);
  await uploadIdle();
  await admin.locator('#upload-form button[type=submit]').click();
  await admin.locator('#overview-result').waitFor({ state: 'attached' });
  await uploadIdle();
  await admin.locator('[data-view-target=band]').click();
  await admin.getByLabel('Instrumento de Gaita de fole').selectOption({ label: 'Otro instrumento…' });
  await admin.locator('.own-instrument-form').waitFor();
  await audit(admin, 'Mi banda › Otro instrumento');
  // A name another account confirmed comes proposed, and counts only once confirmed.
  await admin.locator('[data-view-target=repertoire]').click();
  await admin.locator('#add-work').click();
  await admin.locator('#file').setInputFiles({ name: 'melodia-3.musicxml', mimeType: 'application/xml',
    buffer: Buffer.from(unknownPart.replace('Gaita de fole', 'Melodía 3')) });
  await uploadIdle();
  await admin.locator('#upload-form button[type=submit]').click();
  await admin.locator('#overview-result').waitFor({ state: 'attached' });
  await uploadIdle();
  await admin.locator('[data-view-target=band]').click();
  await admin.locator('#instrument-confirmation').getByText('Propuesto: otras cuentas lo confirmaron').waitFor();
  assert.equal(await admin.getByLabel('Instrumento de Melodía 3').inputValue(), 'clarinet.bb');
  await audit(admin, 'Mi banda › nombre propuesto por otras cuentas');
  await admin.close();
  const phone = await browser.newPage({ locale: 'es-ES', viewport: { width: 390, height: 844 }, reducedMotion: 'reduce', bypassCSP: true });
  await phone.goto(url);
  await login(phone);
  await phone.locator('#mobile-menu-button').click();
  await audit(phone, 'phone with the menu open');
  await phone.close();
  // The interface in English (2026-10-30): the page declares its language, which stays on this device.
  const english = await browser.newPage({ locale: 'es-ES', viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce', bypassCSP: true });
  await english.goto(url);
  await login(english);
  await english.locator('[data-view-target=settings]').click();
  await english.getByLabel('English').check();
  await english.locator('[data-view-target=summary]').getByText('Overview').waitFor();
  assert.equal(await english.locator('html').getAttribute('lang'), 'en');
  await audit(english, 'Settings (English)');
  await english.locator('[data-view-target=summary]').click();
  await english.locator('#summary-priorities-title').getByText('Priorities by section').waitFor();
  await english.waitForLoadState('networkidle');
  await audit(english, 'Overview (English)');
  await english.locator('[data-view-target=repertoire]').click();
  await english.locator('#works-heading').getByText('Works').waitFor();
  await english.waitForLoadState('networkidle');
  await audit(english, 'Repertoire (English)');
  await english.locator('.work-open').first().click();
  await english.locator('#work-tab-difficulty').click();
  await english.locator('#work-panel-difficulty').getByText('Grade of the work').waitFor();
  await audit(english, 'Work › Difficulty (English)');
  await english.locator('#work-tab-score').click();
  await english.locator('#embedded-score').getByRole('heading', { name: 'Full score' }).waitFor();
  await english.locator('#full-score-status').getByText('All voices').waitFor({ timeout: 60000 });
  await audit(english, 'Work › Score (English)');
  await english.locator('#work-tab-recordings').click();
  await english.locator('#videos-content').getByText('Recordings of').waitFor();
  await audit(english, 'Work › Recordings (English)');
  await english.locator('[data-view-target=band]').click();
  await english.locator('#band-manager-title').getByText('Your bands').waitFor();
  await english.waitForLoadState('networkidle');
  await audit(english, 'My band (English)');
  await english.locator('#new-band').click();
  await english.locator('#band-editor-title').getByText('New band').waitFor();
  await audit(english, 'My band › New band (English)');
  await english.locator('#band-editor').getByRole('button', { name: 'Cancel' }).click();
  await english.locator('[data-view-target=repertoire]').click();
  await english.locator('#back-to-list').click();
  await english.locator('#add-work').click();
  await english.locator('#upload-root').getByText('Add work').first().waitFor();
  await english.waitForLoadState('networkidle');
  await audit(english, 'Add work (English)');
  await english.locator('#sign-out').click();
  await english.locator('#login-screen').getByText('Welcome').waitFor();
  await english.reload();
  await english.locator('#login-screen').getByText('Welcome').waitFor();
  await audit(english, 'access screen (English)');
  await english.close();
} finally {
  await browser.close();
}
assert.deepEqual(violations, [], 'WCAG A/AA violations');
