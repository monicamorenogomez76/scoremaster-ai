import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';

function harness() {
  const starts = [], callbacks = new Set(), instruments = [];
  const audio = { currentTime: 0, sampleRate: 100, resume: async () => {},
    createGain: () => ({ gain: {}, connect() {}, disconnect() {} }),
    createDynamicsCompressor: () => ({ connect() {}, disconnect() {} }),
    createBuffer: () => ({ getChannelData: () => new Float32Array(200) }) };
  const data = { duration: 10, tracks: [
    { instrument: 'Flute', program: 73, events: [{ note: 72, time: 0, duration: 4 }] },
    { instrument: 'Clarinet', program: 71, events: [{ note: 60, time: 0, duration: 2 }, { note: 62, time: 4, duration: 2 }] }
  ] };
  const scope = { exports: {}, window: { AudioContext: function () { return audio; } },
    FormData: class { append() {} }, AbortController,
    fetch: async () => ({ ok: true, json: async () => data }),
    setTimeout: () => 1, clearTimeout() {},
    setInterval: (callback) => { callbacks.add(callback); return callback; },
    clearInterval: (callback) => callbacks.delete(callback),
    fakeSoundfont: (_, options) => {
      const result = { ready: Promise.resolve(), stopCount: 0, disposeCount: 0,
        start: (event) => starts.push({ instrument: options.instrument, ...event }),
        stop() { this.stopCount++; }, dispose() { this.disposeCount++; } };
      instruments.push(result); return result;
    }
  };
  const source = readFileSync(new URL('../../app/static/playback.js', import.meta.url), 'utf8')
    .replace(/export /g, '')
    .replace(/import\('https:\/\/unpkg[^']+'\)/, 'Promise.resolve({ Soundfont: fakeSoundfont })');
  vm.runInNewContext(source + '\nObject.assign(exports, { stopPlayback, preparePlayback, playPassage });', scope);
  return { api: scope.exports, starts, audio, callbacks, instruments,
    tick(time) { audio.currentTime = time; [...callbacks].forEach((callback) => callback()); } };
}

test('ensemble starts parts on same clock and schedules ahead in small windows', async () => {
  const h = harness(), t = await h.api.preparePlayback({}, null);
  await t.play();
  assert.equal(h.starts.length, 2);
  assert.equal(h.starts[0].time, h.starts[1].time);
  h.tick(3.8);
  assert.equal(h.starts.length, 3);
  t.stop(); assert.equal(h.callbacks.size, 0);
});

test('pause and seek restore held notes; speed adjusts remaining duration', async () => {
  const h = harness(), t = await h.api.preparePlayback({}, null);
  await t.play(); h.tick(1.05); t.pause();
  assert.equal(h.callbacks.size, 0);
  t.seek(3); t.setSpeed(.5); await t.play();
  const last = h.starts.at(-1);
  assert.equal(last.instrument, 'flute'); assert.equal(last.duration, 2);
  h.api.stopPlayback(); assert.equal(h.callbacks.size, 0);
  assert.ok(h.instruments.every((instrument) => instrument.disposeCount === 1));
});

test('natural completion clears scheduler and allows replay', async () => {
  const h = harness(), t = await h.api.preparePlayback({}, null);
  await t.play(); h.tick(10.1); assert.equal(h.callbacks.size, 0);
  await t.play(); assert.equal(h.callbacks.size, 1); t.dispose();
});
