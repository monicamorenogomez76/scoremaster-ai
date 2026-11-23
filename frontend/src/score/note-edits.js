// Notes edited on the score (2026-11-23), as in a notation program: a note is selected and changed with the keyboard;
// the changes are seen at once and saved together. Pitches are [step, alter, octave], null for a rest.
const STEPS = ['C', 'D', 'E', 'F', 'G', 'A', 'B'];
const SEMITONES = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
const SHARPS = [['C', 0], ['C', 1], ['D', 0], ['D', 1], ['E', 0], ['F', 0], ['F', 1], ['G', 0], ['G', 1], ['A', 0], ['A', 1], ['B', 0]];
const FLATS = [['C', 0], ['D', -1], ['D', 0], ['E', -1], ['E', 0], ['F', 0], ['G', -1], ['G', 0], ['A', -1], ['A', 0], ['B', -1], ['B', 0]];

const FIGURE_KEYS = { 3: '16th', 4: 'eighth', 5: 'quarter', 6: 'half', 7: 'whole' };
const FIGURES = { whole: 4, half: 2, quarter: 1, eighth: 0.5, '16th': 0.25, '32nd': 0.125 };

// The figure of a length in quarters, with its dots; null for a length no figure has (a note of a tuplet).
export function figureOf(quarters) {
  for (const [type, length] of Object.entries(FIGURES)) {
    for (const dots of [0, 1, 2]) if (Math.abs(length * (2 - 1 / 2 ** dots) - quarters) < 1e-6) return { type, dots };
  }
  return null;
}

export const midiOf = ([step, alter, octave]) => 12 * (octave + 1) + SEMITONES[step] + alter;

function spelled(midi, names) {
  const [step, alter] = names[((midi % 12) + 12) % 12];
  // C flat and B sharp change octave: never written here, the tables spell them as B and C.
  return [step, alter, Math.floor(midi / 12) - 1];
}

function stepped([step, , octave], delta) {
  const index = STEPS.indexOf(step) + delta;
  return [STEPS[(index + 7) % 7], 0, octave + Math.floor(index / 7)];
}

function nearest(step, reference) {
  const options = [-1, 0, 1].map(change => [step, 0, reference[2] + change]);
  return options.reduce((best, option) => (Math.abs(midiOf(option) - midiOf(reference)) < Math.abs(midiOf(best) - midiOf(reference)) ? option : best));
}

// What a key does to the selected note: { pitch }, { rest: true }, { move } or null. reference: a pitch near a rest.
export function keyChange(pitch, event, reference = ['C', 0, 5]) {
  const { key, shiftKey, altKey, ctrlKey, metaKey } = event;
  const command = ctrlKey || metaKey;
  if (key === 'ArrowLeft') return { move: 'previous' };
  if (key === 'ArrowRight') return { move: 'next' };
  if ((key === 'ArrowUp' || key === 'ArrowDown') && altKey) return { move: key === 'ArrowUp' ? 'up' : 'down' };
  if (key === 'Delete' || key === 'Backspace') return pitch ? { rest: true } : null;
  // The figures by number, as notation programs give them (2026-11-23): 3 a sixteenth … 7 a whole note; the dot.
  if (FIGURE_KEYS[key] && !command) return { duration: FIGURE_KEYS[key] };
  if (key === '.' && !command) return { dot: true };
  const letter = key.length === 1 ? key.toUpperCase() : '';
  if (STEPS.includes(letter) && !command) return { pitch: nearest(letter, pitch || reference) };
  if (!pitch) return null;
  const up = key === 'ArrowUp';
  if (up || key === 'ArrowDown') {
    if (command) return { pitch: [pitch[0], pitch[1], pitch[2] + (up ? 1 : -1)] };
    if (shiftKey) return { pitch: spelled(midiOf(pitch) + (up ? 1 : -1), up ? SHARPS : FLATS) };
    return { pitch: stepped(pitch, up ? 1 : -1) };
  }
  const alter = { '+': pitch[1] + 1, '-': pitch[1] - 1, '=': 0 }[key];
  if (alter === undefined || alter === pitch[1] || Math.abs(alter) > 2) return null;
  return { pitch: [pitch[0], alter, pitch[2]] };
}

const samePitch = (one, other) => JSON.stringify(one ?? null) === JSON.stringify(other ?? null);
const samePlace = (one, other) => one.partId === other.partId && one.number === other.number && Math.abs(one.offset - other.offset) < 1e-4;

// The pending changes with one more: a note changed again keeps what was read as its old pitch; back to it, no change.
export function mergeEdits(edits, edit) {
  const index = edits.findIndex(item => samePlace(item, edit) && samePitch(item.new, edit.old));
  if (index < 0) return [...edits, edit];
  const merged = { ...edits[index], new: edit.new };
  return samePitch(merged.old, merged.new) ? edits.filter((_, at) => at !== index) : edits.map((item, at) => (at === index ? merged : item));
}

// --- On the page drawn (browser only: DOMParser) --------------------------------------------------------------

const child = (element, name) => Array.from(element.children).find(item => item.localName === name);
const text = (element, name) => child(element, name)?.textContent?.trim();

function pitchOf(note) {
  const found = child(note, 'pitch');
  return found ? [text(found, 'step'), Number(text(found, 'alter') || 0), Number(text(found, 'octave'))] : null;
}

// The notes of a measure with where each starts, in quarters, as the server finds them (note_corrections.py).
function notesWithPlace(measure, divisions) {
  const found = [];
  let at = 0, last = 0;
  for (const item of Array.from(measure.children)) {
    if (item.localName === 'attributes' && text(item, 'divisions')) divisions = Number(text(item, 'divisions'));
    else if (item.localName === 'backup') at -= Number(text(item, 'duration') || 0) / divisions;
    else if (item.localName === 'forward') at += Number(text(item, 'duration') || 0) / divisions;
    else if (item.localName === 'note') {
      if (child(item, 'chord')) { found.push([item, last]); continue; }
      last = at;
      found.push([item, at]);
      if (!child(item, 'grace')) at += Number(text(item, 'duration') || 0) / divisions;
    }
  }
  return { found, divisions };
}

function change(note, edit) {
  const document = note.ownerDocument;
  const old = child(note, edit.old ? 'pitch' : 'rest');
  for (const name of ['accidental']) child(note, name)?.remove();
  if (!edit.new) {
    old.replaceWith(document.createElement('rest'));
    for (const name of ['tie', 'stem', 'notehead', 'beam']) Array.from(note.children).filter(item => item.localName === name).forEach(item => item.remove());
    return;
  }
  const pitch = document.createElement('pitch');
  const [step, alter, octave] = edit.new;
  const add = (name, value) => { const item = document.createElement(name); item.textContent = String(value); pitch.append(item); };
  add('step', step);
  if (alter) add('alter', alter);
  add('octave', octave);
  old.replaceWith(pitch);
}

// The MusicXML of a page with the pending changes, so a page drawn again shows them; a change that is not on the page
// is left for the others.
export function applyEdits(xml, edits) {
  if (!edits.length) return xml;
  const document = new DOMParser().parseFromString(xml, 'application/xml');
  for (const part of Array.from(document.getElementsByTagName('part'))) {
    const mine = edits.filter(edit => edit.partId === part.getAttribute('id'));
    if (!mine.length) continue;
    let divisions = 1;
    for (const measure of Array.from(part.children).filter(item => item.localName === 'measure')) {
      const placed = notesWithPlace(measure, divisions);
      divisions = placed.divisions;
      for (const edit of mine.filter(item => item.number === measure.getAttribute('number'))) {
        const note = placed.found.find(([item, at]) => Math.abs(at - edit.offset) < 1e-4 && !child(item, 'grace')
          && samePitch(pitchOf(item), edit.old) && (edit.old || child(item, 'rest')))?.[0];
        if (note) change(note, edit);
      }
    }
  }
  return new XMLSerializer().serializeToString(document);
}
