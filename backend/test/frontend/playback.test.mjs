import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';

function harness() {
  const starts = [], callbacks = new Set(), instruments = [], optionsUsed = [], samplersUsed = [], failRecorded = { value: false }, withRecordings = { value: false }, formFields = [];
  const gains = [], compressors = [];
  const audio = { currentTime: 0, sampleRate: 100, resume: async () => {},
    createGain: () => { const node = { gain: {}, connect() {}, disconnect() {} }; gains.push(node); return node; },
    createDynamicsCompressor: () => { const node = { threshold: {}, knee: {}, ratio: {}, attack: {}, release: {}, connect() {}, disconnect() {} };
      compressors.push(node); return node; },
    createBuffer: () => ({ getChannelData: () => new Float32Array(200) }) };
  const data = { duration: 10, measures: [{ number: 70, time: 0 }, { number: 71, time: 4 }], tracks: [
    { instrument: 'Flute', program: 73, events: [{ note: 72, time: 0, duration: 4 }] },
    { instrument: 'Clarinet', program: 71, events: [{ note: 60, time: 0, duration: 2 }, { note: 62, time: 4, duration: 2 }] }
  ] };
  const current = { data, failNext: false, hold: null };
  const apiCalls = [], timers = [];
  const scope = { exports: {}, withRecordings, window: { AudioContext: function () { return audio; } },
    FormData: class { append(key, value) { formFields.push([key, value]); } }, AbortController,
    fetch: async () => ({ ok: true, json: async () => current.data }),
    // playback.js calls the API through api.js; the test answers directly.
    apiFetch: async (url, options) => { apiCalls.push(url);
      if (current.hold) { const hold = current.hold; current.hold = null; await hold; }
      if (current.failNext) { current.failNext = false; return { ok: false, json: async () => ({}) }; }
      return { ok: true, json: async () => current.data }; },
    setTimeout: (callback, ms) => { timers.push({ callback, ms, cleared: false }); return timers.length; },
    clearTimeout(id) { if (timers[id - 1]) timers[id - 1].cleared = true; },
    setInterval: (callback) => { callbacks.add(callback); return callback; },
    clearInterval: (callback) => callbacks.delete(callback),
    fakeSampler: (_, options) => {
      samplersUsed.push(options);
      const result = { ready: failRecorded.value ? Promise.reject(new Error('CDN down')) : Promise.resolve(), stopCount: 0, disposeCount: 0,
        start: (event) => starts.push({ instrument: 'recorded', ...event }),
        stop() { this.stopCount++; }, dispose() { this.disposeCount++; } };
      instruments.push(result); return result;
    },
    fakeSoundfont: (_, options) => {
      optionsUsed.push(options);
      const result = { ready: Promise.resolve(), stopCount: 0, disposeCount: 0,
        start: (event) => starts.push({ instrument: options.instrument, ...event }),
        stop() { this.stopCount++; }, dispose() { this.disposeCount++; } };
      instruments.push(result); return result;
    }
  };
  const banks = readFileSync(new URL('../../../frontend/src/score/sample-banks.js', import.meta.url), 'utf8');
  const source = (banks + readFileSync(new URL('../../../frontend/src/score/playback.js', import.meta.url), 'utf8'))
    .replace(/^import .*\n/gm, '')
    .replace(/export /g, '')
    .replace(/import\([^)]*SMPLR_URL\)/, 'Promise.resolve({ Soundfont: fakeSoundfont, get Sampler() { return withRecordings.value ? fakeSampler : undefined; } })');
  vm.runInNewContext(source + '\nObject.assign(exports, { stopPlayback, preparePlayback, playPassage, passageTimeline });', scope);
  return { api: scope.exports, apiCalls, timers, failNext: () => { current.failNext = true; },
    holdNext: () => { let release; current.hold = new Promise(resolve => { release = resolve; }); return release; }, starts, audio, callbacks, instruments, optionsUsed, setData: value => { current.data = value; }, samplersUsed, failRecorded, withRecordings, formFields, gains, compressors,
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
  assert.equal(last.instrument, 'flute'); assert.equal(last.duration + last.ampRelease, 2);
  h.api.stopPlayback(); assert.equal(h.callbacks.size, 0);
  assert.ok(h.instruments.every((instrument) => instrument.disposeCount === 1));
});

test('natural completion clears scheduler and allows replay', async () => {
  const h = harness(), t = await h.api.preparePlayback({}, null);
  await t.play(); h.tick(10.1); assert.equal(h.callbacks.size, 0);
  await t.play(); assert.equal(h.callbacks.size, 1); t.dispose();
});

test('measure guide follows audio position including seek and speed changes', async () => {
  const h = harness(), t = await h.api.preparePlayback({}, null);
  let current;
  t.subscribe(state => current = state.currentMeasure);
  assert.equal(current, 70);
  await t.play(); h.tick(4.1);
  assert.equal(current, 71);
  t.pause(); t.seek(1); assert.equal(current, 70);
  t.setSpeed(2); await t.play(); h.tick(6.1); assert.equal(current, 71);
  t.stop(); assert.equal(current, 70);
});

test('sample release ends at the written note end without spilling into rests', async () => {
  const h = harness(), t = await h.api.preparePlayback({}, null);
  await t.play();
  const flute = h.starts.find(e => e.instrument === 'flute');
  const clarinet = h.starts.find(e => e.instrument === 'clarinet');
  assert.equal(flute.duration + flute.ampRelease, 4);
  assert.equal(clarinet.duration + clarinet.ampRelease, 2);
  assert.ok(clarinet.ampRelease <= .008);
  t.stop();
});

test('pitched samples never use the external loops that introduce extra tones', async () => {
  const h = harness(), t = await h.api.preparePlayback({}, null);
  assert.ok(h.optionsUsed.every(options => options.loadLoopData === false));
  await t.play();
  assert.ok(h.starts.every(event => event.loop === false));
  t.stop();
});

test('the resolved sound wins over the MIDI program and the part name', async () => {
  const h = harness();
  const fetchData = { duration: 4, measures: [{ number: 1, time: 0 }], tracks: [
    { instrument: 'Trompa', program: 0, sound: 'french_horn', events: [{ note: 60, time: 0, duration: 1 }] },
    { instrument: 'Clarinet', program: 71, events: [{ note: 62, time: 0, duration: 1 }] }
  ] };
  h.setData(fetchData);
  const t = await h.api.preparePlayback({}, null);
  assert.deepEqual(h.optionsUsed.map(options => options.instrument).sort(), ['clarinet', 'french_horn']);
  t.stop();
});

test('instruments load from the MusyngKite bank, the higher quality General MIDI soundfont', async () => {
  const h = harness(), t = await h.api.preparePlayback({}, null);
  assert.ok(h.optionsUsed.length > 0);
  assert.ok(h.optionsUsed.every(options => options.kit === 'MusyngKite'));
  t.stop();
});

test('recorded samples play the instruments that have them; the rest use General MIDI', async () => {
  const h = harness();
  h.withRecordings.value = true;
  h.setData({ duration: 4, measures: [{ number: 1, time: 0 }], tracks: [
    { instrument: 'Clarinet', sound: 'clarinet', events: [{ note: 62, time: 0, duration: 1 }] },
    { instrument: 'Oboe', sound: 'oboe', events: [{ note: 69, time: 0, duration: 1 }] }
  ] });
  const t = await h.api.preparePlayback({}, null);
  assert.equal(h.samplersUsed.length, 1);
  assert.deepEqual(Array.from(h.samplersUsed[0].preset.groups[0].regions, region => region.sample), ['D4']);
  assert.deepEqual(h.optionsUsed.map(options => options.instrument), ['oboe']);
  await t.play();
  assert.deepEqual(h.starts.map(event => event.instrument).sort(), ['oboe', 'recorded']);
  t.stop();
});

test('if recordings cannot be downloaded, the General MIDI sound is used instead', async () => {
  const h = harness();
  h.withRecordings.value = true;
  h.failRecorded.value = true;
  h.setData({ duration: 4, measures: [{ number: 1, time: 0 }], tracks: [
    { instrument: 'Clarinet', sound: 'clarinet', events: [{ note: 62, time: 0, duration: 1 }] }
  ] });
  const t = await h.api.preparePlayback({}, null);
  assert.deepEqual(h.optionsUsed.map(options => options.instrument), ['clarinet']);
  await t.play();
  assert.deepEqual(h.starts.map(event => event.instrument), ['clarinet']);
  t.stop();
});

test('a sectional passage asks the server for all its instruments', async () => {
  const h = harness();
  await h.api.preparePlayback({}, { instruments: ['Flute', 'Clarinet'], firstMeasure: 1, lastMeasure: 4 });
  assert.deepEqual(h.formFields.filter(([key]) => key === 'instruments').map(([, value]) => value), ['Flute', 'Clarinet']);
  assert.deepEqual(h.formFields.find(([key]) => key === 'first_measure'), ['first_measure', 1]);
  assert.equal(h.formFields.some(([key]) => key === 'instrument'), false);
});

test('a rehearsal block announces how many voices it plays', async () => {
  const h = harness(), statuses = [];
  const t = await h.api.preparePlayback({}, { instruments: ['Flute', 'Clarinet'], firstMeasure: 1, lastMeasure: 4 }, message => statuses.push(message));
  await t.play();
  assert.match(statuses.at(-1), /^Reproduciendo 2 voces del bloque/);
  t.stop();
});

test('playback is loud enough: measured output was 10-20 times too quiet', async () => {
  const h = harness(), t = await h.api.preparePlayback({}, null);   // two tracks
  // Master gain at the default 50 % volume: 2 / sqrt(voices), protected by a real limiter.
  assert.ok(Math.abs(h.gains[0].gain.value - 2 / Math.sqrt(2)) < 1e-9);
  t.setVolume(1);
  assert.ok(Math.abs(h.gains[0].gain.value - 4 / Math.sqrt(2)) < 1e-9);
  const limiter = h.compressors[0];
  assert.deepEqual([limiter.threshold.value, limiter.ratio.value, limiter.knee.value], [-3, 20, 0]);
  await t.play();
  assert.ok(h.starts.every(event => event.velocity === 100));
  t.stop();
});

test('a passage is requested once: prepared when it opens, reused when it plays', async () => {
  const { api, apiCalls } = harness();
  const file = { name: 'persis.musicxml', size: 10, lastModified: 1 };
  const passage = { instruments: ['Flute', 'Clarinet'], firstMeasure: 70, lastMeasure: 71 };
  const [first, again] = await Promise.all([api.passageTimeline(file, passage), api.passageTimeline(file, passage)]);
  assert.equal(first, again);
  assert.equal(apiCalls.length, 1);
  await api.preparePlayback(file, passage);
  assert.equal(apiCalls.length, 1, 'playing reuses the timeline prepared when the passage opened');
  await api.passageTimeline(file, { ...passage, lastMeasure: 72 });
  assert.equal(apiCalls.length, 2, 'another range is another request');
});

test('a failed preparation is asked again the next time', async () => {
  const { api, apiCalls, failNext } = harness();
  const file = { name: 'unity.mxl', size: 20, lastModified: 2 };
  const passage = { instrument: 'Flute', firstMeasure: 1, lastMeasure: 8 };
  failNext();
  await assert.rejects(api.passageTimeline(file, passage));
  await api.passageTimeline(file, passage);
  assert.equal(apiCalls.length, 2);
});

test('loading the sounds tells how many instruments are ready', async () => {
  const { api } = harness();
  const messages = [];
  await api.preparePlayback({ name: 'a.musicxml', size: 1, lastModified: 1 }, null, message => messages.push(message));
  assert.ok(messages.includes('Cargando sonidos: 0 de 2 instrumentos… La primera carga puede tardar.'));
  assert.ok(messages.includes('Cargando sonidos: 2 de 2 instrumentos…'));
});

test('a slow server has three minutes and the musician is told it is preparing the work', async () => {
  // Render's free plan took more than the 60 s the browser waited to read Persis (2026-10-07).
  for (const passage of [{ instrument: 'Flute', firstMeasure: 1, lastMeasure: 8 }, null]) {
    const { api, timers, holdNext } = harness();
    const release = holdNext();
    const messages = [];
    const ready = api.preparePlayback({ name: 'persis.musicxml', size: 9, lastModified: 3 }, passage, message => messages.push(message));
    await new Promise(resolve => setImmediate(resolve));
    assert.ok(timers.some(timer => timer.ms === 180000), 'the request is abandoned only after three minutes');
    const notice = timers.find(timer => timer.ms === 10000);
    notice.callback();
    assert.ok(messages.includes('El servidor está preparando la obra. La primera vez puede tardar un par de minutos…'));
    release();
    await ready;
    assert.ok(notice.cleared, 'no notice once the timeline has arrived');
  }
});
