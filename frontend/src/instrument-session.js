import { t } from './i18n.js';
export const instrumentChoices = [['Flute',74],['Piccolo',73],['Oboe',69],['Clarinet',72],['Bass Clarinet',72],['Bassoon',71],['Alto Saxophone',66],['Tenor Saxophone',67],['Baritone Saxophone',68],['Trumpet',57],['Horn',61],['Trombone',58],['Euphonium',59],['Tuba',59],['Timpani',48],['Glockenspiel',10],['Xylophone',14],['Snare Drum',null],['Bass Drum',null],['Cymbals',null]];

export function inspectInstruments(source) {
  const xml = new DOMParser().parseFromString(source, 'application/xml');
  if (xml.querySelector('parsererror')) throw new Error(t('La partitura no es MusicXML válido.'));
  const parts = Array.from(xml.querySelectorAll('score-part'));
  const unidentified = parts.filter(part => /^(voice|part|instrument|voz)(\s+\d+)?$/i.test(part.querySelector('part-name')?.textContent.trim() || ''));
  return { xml, parts: unidentified.map(part => {
    const metadata = part.querySelector('instrument-name')?.textContent;
    return { id: part.id, number: parts.indexOf(part) + 1,
      initialChoice: instrumentChoices.some(([name]) => name === metadata) ? metadata : '' };
  }) };
}

export function applyInstrumentAssignments(originalFile, xml, assignments) {
  if (!xml || !Object.values(assignments).some(Boolean)) return { file: originalFile, source: null };
  const mappedSource = xml.cloneNode(true);
  for (const [id, name] of Object.entries(assignments)) {
    if (!name) continue;
    const part = Array.from(mappedSource.querySelectorAll('score-part')).find(part => part.id === id);
    part.querySelector('part-name').textContent = name;
    const abbreviation = part.querySelector('part-abbreviation'); if (abbreviation) abbreviation.textContent = name;
    const instrument = part.querySelector('instrument-name'); if (instrument) instrument.textContent = name;
    const program = instrumentChoices.find(([choice]) => choice === name)[1];
    const midi = part.querySelector('midi-program'); if (midi && program) midi.textContent = program;
    if (!program) {
      if (midi) midi.textContent = '1';
      const channel = part.querySelector('midi-channel'); if (channel) channel.textContent = '10';
      const midiInstrument = part.querySelector('midi-instrument');
      if (midiInstrument) {
        let unpitched = midiInstrument.querySelector('midi-unpitched');
        if (!unpitched) { unpitched = mappedSource.createElement('midi-unpitched'); midiInstrument.append(unpitched); }
        unpitched.textContent = { 'Snare Drum': 39, 'Bass Drum': 36, 'Cymbals': 50 }[name];
      }
    }
  }
  const source = new XMLSerializer().serializeToString(mappedSource);
  return { source, file: new File([source], originalFile.name.replace(/\.(mxl|xml)$/i, '.musicxml'), { type: 'application/xml' }) };
}
