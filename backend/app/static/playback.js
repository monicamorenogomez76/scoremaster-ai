// Sampled solo playback. The MusicXML remains on our server/browser only.
let context;
let player;
let generation = 0;
let finished;
let library;

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

export function stopPlayback() {
  generation += 1;
  clearTimeout(finished);
  if (player) { player.dispose(); player = null; }
}

export async function playPassage(file, passage, onStatus) {
  stopPlayback();
  const token = generation;
  context ||= new (window.AudioContext || window.webkitAudioContext)();
  await context.resume();
  onStatus('Preparando audio del pasaje…');
  const body = new FormData();
  body.append('file', file);
  body.append('instrument', passage.instrument);
  body.append('first_measure', passage.firstMeasure);
  body.append('last_measure', passage.lastMeasure);
  const response = await fetch('/playback', { method: 'POST', body });
  if (!response.ok) throw new Error('No se pudo preparar el audio del pasaje.');
  const data = await response.json();
  if (token !== generation) return;
  if (!data.events.length) throw new Error('Este pasaje no contiene notas afinadas reproducibles. La percusión sin altura todavía no está disponible.');
  onStatus('Cargando sonido del instrumento…');
  library ||= import('https://unpkg.com/smplr@1.1.0/dist/index.mjs').catch((error) => { library = null; throw error; });
  const { Soundfont } = await library;
  if (token !== generation) return;
  const sound = timbre(data);
  const loaded = Soundfont(context, { instrument: sound, kit: 'FluidR3_GM',
    loadLoopData: true, notesToLoad: [...new Set(data.events.map((event) => event.note))] });
  player = loaded;
  await loaded.ready;
  if (token !== generation) return;
  const begin = context.currentTime + .1;
  data.events.forEach((event) => loaded.start({ ...event, time: begin + event.time, velocity: 70 }));
  const notices = [];
  if (data.default_tempo) notices.push('sin tempo indicado: negra = 120');
  if (data.skipped_unpitched) notices.push('notas de percusión sin altura omitidas');
  onStatus('Reproduciendo · sonido aproximado: ' + sound.replaceAll('_', ' ') +
    (notices.length ? ' · ' + notices.join(' · ') : ''));
  finished = setTimeout(() => {
    if (token !== generation) return;
    stopPlayback();
    onStatus('Reproducción finalizada.');
  }, (data.duration + .3) * 1000);
}
