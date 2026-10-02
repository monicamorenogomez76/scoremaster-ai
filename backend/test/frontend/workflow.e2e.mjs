import { createRequire } from 'node:module';
import assert from 'node:assert/strict';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const score = name => `<?xml version="1.0"?><score-partwise version="4.0"><work><work-title>Synthetic workflow test</work-title></work><part-list><score-part id="P1"><part-name>${name}</part-name><score-instrument id="I1"><instrument-name>${name === 'Voice' ? 'Voice Oohs' : name}</instrument-name></score-instrument><midi-instrument id="I1"><midi-channel>1</midi-channel><midi-program>${name === 'Voice' ? 54 : 74}</midi-program></midi-instrument></score-part></part-list><part id="P1"><measure number="1"><attributes><divisions>1</divisions><key><fifths>0</fifths></key><time><beats>4</beats><beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes><note><pitch><step>C</step><octave>5</octave></pitch><duration>4</duration><type>whole</type></note></measure></part></score-partwise>`;
const upload = async name => {
  await page.locator('#file').setInputFiles({ name: 'synthetic.musicxml', mimeType: 'application/xml', buffer: Buffer.from(score(name)) });
  await page.waitForFunction(() => !document.querySelector('#upload-form button[type=submit]').disabled);
};
try {
  await page.goto(process.env.SCOREMASTER_URL || 'http://127.0.0.1:8005');
  await page.locator('#enter-demo').click();
  await page.getByRole('button', { name: '02 Analizar partitura' }).click();
  assert.equal(await page.locator('#embedded-score').isVisible(), false);
  await upload('Flute');
  assert.equal(await page.locator('#embedded-score').isVisible(), false);
  await page.locator('#upload-form button[type=submit]').click();
  await page.waitForFunction(() => document.querySelector('#full-score-rendering svg') && document.querySelector('#full-score-status').getAttribute('aria-busy') === 'false', { timeout: 45000 });
  const fits = await page.locator('#full-score-rendering').evaluate(container => {
    const svg = container.querySelector('svg').getBoundingClientRect(), box = container.getBoundingClientRect();
    return svg.width <= box.width && svg.height <= box.height;
  });
  assert.equal(fits, true, 'page must fit viewport');
  await page.locator('#new-score').click();
  await page.waitForFunction(() => document.querySelector('#file').files.length === 0);
  assert.equal(await page.locator('#embedded-score').isVisible(), false);
  assert.equal(await page.locator('#full-score-rendering svg').count(), 0);
  console.log('PASS: analysis visibility, page fitting and reset');
  await upload('Voice');
  await page.locator('#instrument-assignment select').selectOption('Clarinet');
  await page.locator('#upload-form button[type=submit]').click();
  await page.waitForFunction(() => document.querySelector('#full-score-rendering svg') && document.querySelector('#full-score-status').getAttribute('aria-busy') === 'false', { timeout: 45000 });
  assert.match(await page.locator('#full-score-rendering').textContent(), /Clarinet/);
  const playback = await page.evaluate(async () => {
    const source = await loadNotationSource();
    const body = new FormData(); body.append('file', new File([source], 'assigned.musicxml')); body.append('instrument', 'Clarinet'); body.append('first_measure', '1'); body.append('last_measure', '1');
    return (await fetch('/playback', { method: 'POST', body })).json();
  });
  assert.equal(playback.instrument, 'Clarinet'); assert.equal(playback.program, 71);
  console.log('PASS: generic instrument assignment reaches notation, analysis and playback');
  await upload('Flute');
  assert.equal(await page.locator('#embedded-score').isVisible(), false);
  assert.equal(await page.locator('#instrument-assignment').isVisible(), false);
  assert.deepEqual(errors, []);
  await page.screenshot({ path: '/tmp/scoremaster-workflow.png', fullPage: true });
  console.log('PASS: replacing file clears previous score without page errors');
} finally { await browser.close(); }
