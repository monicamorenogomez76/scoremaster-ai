// Sampled solo playback. The MusicXML remains on our server/browser only.
import { apiFetch } from '../api.js';
import { recordedPreset, voiceGain } from './sample-banks.js';

let context;
let activeTransport;
let pendingRequest;
const wholeScoreCache = new WeakMap();
let generation = 0;
let library;
const SMPLR_URL = 'https://unpkg.com/smplr@1.1.0/dist/index.mjs';
// MusyngKite (CC BY-SA 3.0) sounds less synthetic than FluidR3_GM for winds; samples load from its CDN.
const SOUNDFONT_KIT = 'MusyngKite';
// Output was measured 10-20 times too quiet (-40 dB RMS): at the default 50 % volume the master
// gain is 2/sqrt(voices) and a limiter keeps the summed band from clipping.
const MASTER_GAIN = 4;
const VELOCITY = 100;
const masterLevel = (volume, voices) => Math.max(0, Math.min(1, volume)) * MASTER_GAIN / Math.sqrt(Math.max(1, voices));

const programs = {
  0: 'acoustic_grand_piano', 9: 'glockenspiel', 11: 'vibraphone',
  12: 'marimba', 13: 'xylophone', 14: 'tubular_bells', 46: 'orchestral_harp',
  40: 'violin', 41: 'viola', 42: 'cello', 43: 'contrabass', 47: 'timpani',
  56: 'trumpet', 57: 'trombone', 58: 'tuba', 60: 'french_horn',
  64: 'soprano_sax', 65: 'alto_sax', 66: 'tenor_sax', 67: 'baritone_sax',
  68: 'oboe', 69: 'english_horn', 70: 'bassoon', 71: 'clarinet',
  72: 'piccolo', 73: 'flute'
};

function timbre(data) {
  // Sound of the resolved instrument identity, chosen by the server from the catalog.
  if (data.sound) return data.sound;
  if (programs[data.program]) return programs[data.program];
  const name = data.instrument.toLowerCase();
  const aliases = [
    ['piccolo', 'piccolo'], ['flute', 'flute'], ['english horn', 'english_horn'],
    ['oboe', 'oboe'], ['bassoon', 'bassoon'], ['clarinet', 'clarinet'],
    ['alto sax', 'alto_sax'], ['tenor sax', 'tenor_sax'], ['baritone sax', 'baritone_sax'],
    ['soprano sax', 'soprano_sax'], ['cornet', 'trumpet'], ['trumpet', 'trumpet'],
    ['trombone', 'trombone'], ['euphonium', 'tuba'], ['tuba', 'tuba'],
    ['horn', 'french_horn'], ['timpani', 'timpani'], ['glockenspiel', 'glockenspiel'],
    ['xylophone', 'xylophone'], ['marimba', 'marimba'], ['vibraphone', 'vibraphone'],
    ['chimes', 'tubular_bells'], ['double bass', 'contrabass'], ['piano', 'acoustic_grand_piano']
  ];
  return (aliases.find(([text]) => name.includes(text)) || [null, 'acoustic_grand_piano'])[1];
}

function audioContext() {
  context ||= new (window.AudioContext || window.webkitAudioContext)();
  return context;
}

function percussionPlayer(destination) {
  const sources = new Set();
  const buffer = context.createBuffer(1, context.sampleRate * 2, context.sampleRate);
  const noise = buffer.getChannelData(0);
  for (let i = 0; i < noise.length; i++) noise[i] = Math.random() * 2 - 1;
  return {
    start({ note, time }) {
      const gain = context.createGain();
      gain.connect(destination);
      const bass = note === 35 || note === 36;
      const length = bass ? .3 : note === 38 ? .15 : .7;
      const source = bass ? context.createOscillator() : context.createBufferSource();
      if (bass) {
        source.frequency.setValueAtTime(130, time);
        source.frequency.exponentialRampToValueAtTime(40, time + length);
      } else {
        source.buffer = buffer;
      }
      const filter = context.createBiquadFilter();
      filter.type = bass ? 'lowpass' : 'highpass';
      filter.frequency.value = bass ? 200 : note === 38 ? 1000 : 4500;
      source.connect(filter); filter.connect(gain);
      gain.gain.setValueAtTime(.18, time);
      gain.gain.exponentialRampToValueAtTime(.001, time + length);
      source.onended = () => { sources.delete(source); source.disconnect(); filter.disconnect(); gain.disconnect(); };
      sources.add(source);
      source.start(time); source.stop(time + length);
    },
    stop() { sources.forEach((source) => { try { source.stop(); } catch (_) {} }); sources.clear(); },
    dispose() { this.stop(); }
  };
}

export function stopPlayback() {
  generation += 1;
  pendingRequest?.abort();
  pendingRequest = null;
  activeTransport?.dispose();
  activeTransport = null;
}

// Timelines of the passages opened (reported 2026-10-07: with real band scores a passage took
// many seconds to sound). A passage starts being prepared when its dialog opens, so pressing play
// reuses the same request; a failed one is asked again next time.
const passageTimelines = new Map();
const PASSAGES_KEPT = 8;
// A long work answers 202 while the server prepares it: the browser asks how it goes every few seconds
// and then asks for the passage again, so no request stays open for minutes (2026-10-07: Persis took
// ~3 min on Render's free plan and went past the browser's wait). The server keeps it afterwards.
const MAX_PREPARATION_MS = 15 * 60000;
const POLL_MS = 3000;
const SLOW_NOTICE_MS = 10000;
export const SLOW_SERVER_NOTICE = 'El servidor está preparando la obra. La primera vez puede tardar un par de minutos…';
const elapsedText = seconds => (seconds < 60 ? seconds + ' s'
  : Math.floor(seconds / 60) + ' min' + (seconds % 60 ? ' ' + (seconds % 60) + ' s' : ''));
const waitingText = seconds => 'El servidor está preparando la obra (solo la primera vez)… ' + elapsedText(seconds);
// Who is waiting for a preparation now: the transport being prepared, to show how long it takes.
let onWaiting = null;

const pause = (ms, signal) => new Promise((resolve, reject) => {
  const id = setTimeout(resolve, ms);
  signal.addEventListener('abort', () => { clearTimeout(id); reject(new DOMException('Cancelado', 'AbortError')); }, { once: true });
});

async function fetchTimeline(body, signal) {
  const started = Date.now();
  for (;;) {
    const response = await apiFetch('/playback', { method: 'POST', body, signal });
    if (response.status !== 202) {
      if (!response.ok) throw new Error('No se pudo preparar la reproducción.');
      return response.json();
    }
    const { preparing } = await response.json();
    let status = 'preparing';
    while (status === 'preparing') {
      onWaiting?.(Math.round((Date.now() - started) / 1000));
      await pause(POLL_MS, signal);
      const progress = await apiFetch('/playback/preparations/' + encodeURIComponent(preparing), { signal });
      status = progress.ok ? (await progress.json()).status : 'failed';
    }
    if (status === 'failed') throw new Error('No se pudo preparar la reproducción.');
    // ready, or unknown after a restart: the work is sent again.
  }
}

function timelineRequest(body, onAbandon) {
  const controller = new AbortController();
  onAbandon?.(controller);
  const timeout = setTimeout(() => controller.abort(), MAX_PREPARATION_MS);
  return fetchTimeline(body, controller.signal).finally(() => clearTimeout(timeout));
}

const passageKey = (file, passage) => [file?.name, file?.size, file?.lastModified,
  passage.instrument || (passage.instruments || []).join('|'), passage.firstMeasure, passage.lastMeasure].join('·');

export function passageTimeline(file, passage) {
  const key = passageKey(file, passage);
  if (!passageTimelines.has(key)) {
    const body = new FormData();
    body.append('file', file);
    // A rehearsal block plays several instruments together; a passage, a single one.
    if (passage.instruments) passage.instruments.forEach(name => body.append('instruments', name));
    else body.append('instrument', passage.instrument);
    body.append('first_measure', passage.firstMeasure);
    body.append('last_measure', passage.lastMeasure);
    const request = timelineRequest(body);
    request.catch(() => passageTimelines.delete(key));
    passageTimelines.set(key, request);
    while (passageTimelines.size > PASSAGES_KEPT) passageTimelines.delete(passageTimelines.keys().next().value);
  }
  return passageTimelines.get(key);
}

export async function preparePlayback(file, passage, onStatus = () => {}) {
  stopPlayback();
  const token = generation;
  const ctx = audioContext();
  await ctx.resume();
  onStatus(passage ? 'Preparando audio del pasaje…' : 'Preparando todas las voces…');
  let data;
  const notice = setTimeout(() => { if (token === generation) onStatus(SLOW_SERVER_NOTICE); }, SLOW_NOTICE_MS);
  const waiting = seconds => { clearTimeout(notice); if (token === generation) onStatus(waitingText(seconds)); };
  onWaiting = waiting;
  try {
    if (passage) data = await passageTimeline(file, passage);
    else data = wholeScoreCache.get(file);
    if (!data) {
      const body = new FormData();
      body.append('file', file);
      data = await timelineRequest(body, controller => { pendingRequest = controller; });
      wholeScoreCache.set(file, data);
    }
  } finally {
    clearTimeout(notice);
    if (onWaiting === waiting) onWaiting = null;
  }
  if (token !== generation) return null;
  const tracks = data.tracks || [data];
  if (!tracks.some((track) => track.events.length || track.percussion?.length)) {
    throw new Error('La partitura no contiene notas reproducibles.');
  }
  library ||= import(/* @vite-ignore */ SMPLR_URL).catch((error) => { library = null; throw error; });
  const { Soundfont, Sampler } = await library;
  if (token !== generation) return null;
  const master = ctx.createGain();
  const limiter = ctx.createDynamicsCompressor();
  limiter.threshold.value = -3; limiter.knee.value = 0; limiter.ratio.value = 20;
  limiter.attack.value = 0.003; limiter.release.value = 0.25;
  master.gain.value = masterLevel(.5, tracks.length);
  master.connect(limiter); limiter.connect(ctx.destination);
  const instruments = new Map();
  const drums = percussionPlayer(master);
  const timeline = [];
  tracks.forEach((track) => {
    if (track.events.length) {
      const sound = timbre(track);
      if (!instruments.has(sound)) instruments.set(sound, { notes: new Set(), events: [], parts: 0 });
      const group = instruments.get(sound);
      group.parts += 1;
      track.events.forEach((event) => { group.notes.add(event.note); group.events.push(event); });
    }
    (track.percussion || []).forEach((event) => timeline.push({ ...event, player: drums }));
  });
  const players = [drums], voices = [];
  let transport;
  function disposePlayers() { players.forEach((player) => player.dispose()); voices.forEach((voice) => voice.disconnect()); master.disconnect(); limiter.disconnect(); }
  // Publish disposal before awaiting samples, so Stop can cancel loading too.
  activeTransport = { dispose: disposePlayers };
  async function ready(player) {
    players.push(player);
    let timeoutId;
    const timeout = new Promise((_, reject) => { timeoutId = setTimeout(() => reject(new Error('La descarga de sonidos ha tardado demasiado. Comprueba tu conexión.')), 90000); });
    try { await Promise.race([player.ready, timeout]); }
    finally { clearTimeout(timeoutId); }
    return player;
  }
  // Real recordings where they exist; the General MIDI soundfont otherwise or if they fail to load.
  // Each sound plays through its own gain, calibrated to the source that finally loaded.
  async function loadPlayer(sound, group) {
    const voice = ctx.createGain();
    voice.connect(master);
    voices.push(voice);
    const preset = Sampler && recordedPreset(sound, [...group.notes]);
    if (preset) {
      try {
        const player = await ready(Sampler(ctx, { preset, destination: voice }));
        voice.gain.value = voiceGain(sound, true, group.parts);
        return player;
      } catch { /* recordings unavailable: fall back to the soundfont */ }
    }
    voice.gain.value = voiceGain(sound, false, group.parts);
    return ready(Soundfont(ctx, { instrument: sound, kit: SOUNDFONT_KIT,
      // External loop points change pitch in some MP3 samples (e.g. clarinet D4).
      destination: voice, loadLoopData: false, notesToLoad: { notes: [...group.notes] } }));
  }
  // A whole band means many instruments to download the first time: say how many are ready.
  let readyCount = 0;
  onStatus('Cargando sonidos: 0 de ' + instruments.size + ' instrumentos… La primera carga puede tardar.');
  try {
    await Promise.all([...instruments].map(async ([sound, group]) => {
      const loaded = await loadPlayer(sound, group);
      readyCount += 1;
      if (token === generation) onStatus('Cargando sonidos: ' + readyCount + ' de ' + instruments.size + ' instrumentos…');
      if (token === generation) group.events.forEach((event) => timeline.push({ ...event, player: loaded }));
    }));
  } catch (error) {
    if (token === generation) stopPlayback();
    throw error;
  }
  if (token !== generation) return null;
  timeline.sort((a, b) => a.time - b.time);
  let position = 0, speed = 1, began = 0, base = 0, playing = false, timer, pointer = 0, disposed = false;
  let queue = [];
  const duration = data.duration;
  const listeners = new Set();
  function tell() {
    const measure = (data.measures || []).findLast(item => item.time <= position);
    listeners.forEach(callback => callback({ position, duration, playing, currentMeasure: measure?.number, tempoMap: data.tempo_map }));
  }
  function silence() { clearInterval(timer); players.forEach((player) => player.stop()); }
  function tick() {
    position = Math.min(duration, base + Math.max(0, ctx.currentTime - began) * speed);
    const horizon = position + .3 * speed;
    while (pointer < queue.length && queue[pointer].time <= horizon) {
      const event = queue[pointer++];
      const time = began + (event.time - base) / speed;
      // smplr defaults to a 300 ms release AFTER duration, creating unintended
      // overlapping pitches. Place a short anti-click release INSIDE the note.
      const length = event.duration / speed;
      const release = Math.min(.008, length * .1);
      event.player.start({ note: event.note, time: Math.max(ctx.currentTime, time),
        duration: Math.max(0, length - release), ampRelease: release, loop: false, velocity: VELOCITY });
    }
    if (position >= duration) { playing = false; silence(); onStatus('Reproducción finalizada.'); }
    tell();
  }
  transport = {
    duration,
    subscribe(callback) { listeners.add(callback); tell(); return () => listeners.delete(callback); },
    async play() {
      if (disposed || playing) return;
      await ctx.resume();
      if (disposed) return;
      if (position >= duration) position = 0;
      base = position; began = ctx.currentTime + .05;
      // Restore a note held across a seek or pause, without losing its end.
      queue = timeline.filter((event) => event.time + event.duration > position).map((event) =>
        event.time < position ? { ...event, time: position, duration: event.time + event.duration - position } : event);
      pointer = 0; playing = true; tick();
      if (playing) timer = setInterval(tick, 50);
      onStatus('Reproduciendo ' + (passage?.instruments ? tracks.length + ' voces del bloque' : passage ? 'instrumento solista' : tracks.length + ' voces') + ' · timbres aproximados' +
        (data.default_tempo ? ' · negra = 120 por defecto' : '') +
        (tracks.some((track) => track.skipped_unpitched) ? ' · percusión no identificada omitida' : ''));
    },
    pause() { if (playing) tick(); playing = false; silence(); tell(); onStatus('En pausa.'); },
    stop() { playing = false; silence(); position = 0; tell(); onStatus('Detenido.'); },
    seek(value) { const resume = playing; this.pause(); position = Math.max(0, Math.min(duration, value)); tell(); if (resume) this.play(); },
    setSpeed(value) { const resume = playing; this.pause(); speed = Math.max(.25, Math.min(2, value)); if (resume) this.play(); },
    setVolume(value) { master.gain.value = masterLevel(value, tracks.length); },
    dispose() { if (disposed) return; disposed = true; silence(); disposePlayers(); listeners.clear(); }
  };
  activeTransport = transport;
  onStatus('Lista para reproducir · ' + tracks.length + ' voces.');
  return transport;
}

export async function playPassage(file, passage, onStatus) {
  const transport = await preparePlayback(file, passage, onStatus);
  if (transport) await transport.play();
}
