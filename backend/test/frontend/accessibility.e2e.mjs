// Accessibility audit (WCAG 2.1 A and AA, author's requirement, 2026-10-26): axe-core checks every view of the
// app, signed out and signed in, in the light and the dark theme and with the phone menu open. Any violation fails
// the walkthrough, so no change can break accessibility unnoticed. axe-core is installed next to Playwright
// (AXE_MODULE, or found from PLAYWRIGHT_MODULE's folder), never as a dependency of the app.
// The test browser ignores the app's CSP only to inject axe; the app's CSP itself is checked elsewhere. It asks for
// reduced motion (WCAG 2.3.3), so no view is measured halfway through its entrance.
import { createRequire } from 'node:module';
import { dirname } from 'node:path';
import assert from 'node:assert/strict';
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
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: scheme, reducedMotion: 'reduce', bypassCSP: true });
    await page.goto(url);
    await page.locator('#login-screen').waitFor({ state: 'visible' });
    await audit(page, `access screen (${scheme})`);
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
  const phone = await browser.newPage({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce', bypassCSP: true });
  await phone.goto(url);
  await login(phone);
  await phone.locator('#mobile-menu-button').click();
  await audit(phone, 'phone with the menu open');
  await phone.close();
} finally {
  await browser.close();
}
assert.deepEqual(violations, [], 'WCAG A/AA violations');
