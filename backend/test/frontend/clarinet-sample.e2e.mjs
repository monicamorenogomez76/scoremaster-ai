// Regression against real smplr and the real FluidR3_GM clarinet MP3 sample.
// No score is used. Optional file paths cache the public modules/samples locally.
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ locale: 'es-ES' });
  const urls = {
    module: 'https://unpkg.com/smplr@1.1.0/dist/index.mjs',
    sample: 'https://gleitz.github.io/midi-js-soundfonts/FluidR3_GM/clarinet-mp3.js',
    loops: 'https://goldst.dev/midi-js-soundfonts/FluidR3_GM/clarinet-loop.json'
  };
  for (const [url, path, type] of [
    [urls.module, process.env.SMPLR_MODULE_FILE, 'text/javascript'],
    [urls.sample, process.env.CLARINET_SAMPLE_FILE, 'text/javascript'],
    [urls.loops, process.env.CLARINET_LOOPS_FILE, 'application/json']
  ]) if (path) await page.route(url, route => route.fulfill({ contentType: type, body: readFileSync(path, 'utf8') }));
  await page.goto(process.env.SCOREMASTER_URL || 'http://127.0.0.1:8006');
  const result = await page.evaluate(async urls => {
    const { Soundfont } = await import(urls.module);
    async function render(useLoops) {
      const ctx = new OfflineAudioContext(1, 44100, 44100);
      let attacks = 0;
      const player = Soundfont(ctx, {
        instrumentUrl: urls.sample, loopDataUrl: useLoops ? urls.loops : undefined,
        loadLoopData: useLoops, notesToLoad: { notes: [62] },
        scheduler: { schedule(event, callback) { callback(event); return () => {}; }, stop() {} },
        onStart() { attacks++; }
      });
      await player.ready;
      player.start({ note: 62, time: 0, duration: .492, ampRelease: .008, velocity: 65, ...(useLoops ? {} : { loop: false }) });
      const samples = (await ctx.startRendering()).getChannelData(0);
      function pitch(offset) {
        const start = Math.floor(offset * 44100), length = 2646;
        const correlation = lag => {
          let sum = 0;
          for (let i = 0; i < length - lag; i++) sum += samples[start + i] * samples[start + i + lag];
          return sum;
        };
        let best = 0, max = -Infinity;
        for (let lag = 111; lag < 440; lag++) {
          const value = correlation(lag);
          if (value > correlation(lag - 1) && value >= correlation(lag + 1) && value > max) { max = value; best = lag; }
        }
        return 44100 / best;
      }
      const data = { attacks, beforeLoop: pitch(.12), afterLoop: pitch(.35) };
      player.dispose();
      return data;
    }
    return { looped: await render(true), corrected: await render(false) };
  }, urls);
  console.log(JSON.stringify(result));
  assert.equal(result.corrected.attacks, 1);
  assert.ok(Math.abs(result.corrected.beforeLoop - 293.66) < 3);
  assert.ok(Math.abs(result.corrected.afterLoop - 293.66) < 3, 'D4 must remain D4 during the note');
  assert.ok(Math.abs(result.looped.afterLoop - 293.66) > 10, 'reproduce the old sample-loop defect');
} finally { await browser.close(); }
