// Real smplr and the real recorded clarinet: the hybrid player must produce sound.
// Needs network access to unpkg and jsDelivr; any page of the app serves as origin.
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const banks = readFileSync(new URL('../../../frontend/src/score/sample-banks.js', import.meta.url), 'utf8').replace(/export /g, '');
const browser = await chromium.launch();
try {
  // The sample check injects a script, which the application's CSP rightly forbids.
  const page = await browser.newPage({ locale: 'es-ES', bypassCSP: true });
  await page.goto(process.env.SCOREMASTER_URL || 'http://127.0.0.1:8006');
  await page.addScriptTag({ content: banks + '\nwindow.recordedPreset = recordedPreset;' });
  const level = await page.evaluate(async () => {
    const { Sampler } = await import('https://unpkg.com/smplr@1.1.0/dist/index.mjs');
    const context = new OfflineAudioContext(1, 44100 * 2, 44100);
    const sampler = Sampler(context, { preset: window.recordedPreset('clarinet', [62]), destination: context.destination });
    await sampler.ready;
    sampler.start({ note: 62, time: 0.1, duration: 1, ampRelease: 0.008, loop: false, velocity: 65 });
    const data = (await context.startRendering()).getChannelData(0);
    let sum = 0; for (const value of data) sum += value * value;
    return Math.sqrt(sum / data.length);
  });
  assert.ok(level > 0.01, 'recorded clarinet must not be silent, RMS ' + level);
  console.log('PASS: recorded clarinet sounds (RMS ' + level.toFixed(4) + ')');
} finally { await browser.close(); }
