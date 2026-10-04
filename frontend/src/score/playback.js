// Sampled solo playback. The MusicXML remains on our server/browser only.
import { recordedPreset } from './sample-banks.js';

let context;
let activeTransport;
let pendingRequest;
const wholeScoreCache = new WeakMap();
let generation = 0;
let library;
const SMPLR_URL = 'https://unpkg.com/smplr@1.1.0/dist/index.mjs';
// MusyngKite (CC BY-SA 3.0) sounds less synthetic than FluidR3_GM for winds; samples load from its CDN.
const SOUNDFONT_KIT = 'MusyngKite';

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

export async function preparePlayback(file, passage, onStatus = () => {}) {
  stopPlayback();
  const token = generation;
  const ctx = audioContext();
  await ctx.resume();
  onStatus(passage ? 'Preparando audio del pasaje…' : 'Preparando todas las voces…');
  const body = new FormData();
  body.append('file', file);
  if (passage) {
    // A rehearsal block plays several instruments together; a passage, a single one.
    if (passage.instruments) passage.instruments.forEach(name => body.append('instruments', name));
    else body.append('instrument', passage.instrument);
    body.append('first_measure', passage.firstMeasure);
    body.append('last_measure', passage.lastMeasure);
  }
  let data = !passage && wholeScoreCache.get(file);
  if (!data) {
    pendingRequest = new AbortController();
    const request = pendingRequest;
    const timeout = setTimeout(() => request.abort(), 60000);
    try {
      const response = await fetch('/playback', { method: 'POST', body, signal: request.signal });
      if (!response.ok) throw new Error('No se pudo preparar la reproducción.');
      data = await response.json();
      if (!passage) wholeScoreCache.set(file, data);
    } finally { clearTimeout(timeout); }
  }
  if (token !== generation) return null;
  const tracks = data.tracks || [data];
  if (!tracks.some((track) => track.events.length || track.percussion?.length)) {
    throw new Error('La partitura no contiene notas reproducibles.');
  }
  onStatus('Cargando sonidos de los instrumentos… La primera carga puede tardar.');
  library ||= import(/* @vite-ignore */ SMPLR_URL).catch((error) => { library = null; throw error; });
  const { Soundfont, Sampler } = await library;
  if (token !== generation) return null;
  const master = ctx.createGain();
  const limiter = ctx.createDynamicsCompressor();
  master.gain.value = .5 / Math.sqrt(Math.max(1, tracks.length));
  master.connect(limiter); limiter.connect(ctx.destination);
  const instruments = new Map();
  const drums = percussionPlayer(master);
  const timeline = [];
  tracks.forEach((track) => {
    if (track.events.length) {
      const sound = timbre(track);
      if (!instruments.has(sound)) instruments.set(sound, { notes: new Set(), events: [] });
      const group = instruments.get(sound);
      track.events.forEach((event) => { group.notes.add(event.note); group.events.push(event); });
    }
    (track.percussion || []).forEach((event) => timeline.push({ ...event, player: drums }));
  });
  const players = [drums];
  let transport;
  function disposePlayers() { players.forEach((player) => player.dispose()); master.disconnect(); limiter.disconnect(); }
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
  async function loadPlayer(sound, group) {
    const preset = Sampler && recordedPreset(sound, [...group.notes]);
    if (preset) {
      try { return await ready(Sampler(ctx, { preset, destination: master })); }
      catch { /* recordings unavailable: fall back to the soundfont */ }
    }
    return ready(Soundfont(ctx, { instrument: sound, kit: SOUNDFONT_KIT,
      // External loop points change pitch in some MP3 samples (e.g. clarinet D4).
      destination: master, loadLoopData: false, notesToLoad: { notes: [...group.notes] } }));
  }
  try {
    await Promise.all([...instruments].map(async ([sound, group]) => {
      const loaded = await loadPlayer(sound, group);
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
        duration: Math.max(0, length - release), ampRelease: release, loop: false, velocity: 65 });
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
    setVolume(value) { master.gain.value = Math.max(0, Math.min(1, value)) / Math.sqrt(Math.max(1, tracks.length)); },
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
