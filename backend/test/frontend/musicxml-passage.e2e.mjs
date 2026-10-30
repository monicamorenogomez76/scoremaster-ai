// MusicXML passage filter in a real browser (it needs DOMParser): no server involved.
// 2026-10-14: in Persis the three trumpets are one MusicXML part with three staves. A campaign passage
// of «B♭ Trumpet 1» showed the three staves while the audio played only the first, so the third
// trumpet was seen but not heard when it played alone.
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const source = readFileSync(new URL('../../../frontend/src/score/musicxml-passage.js', import.meta.url), 'utf8').replace(/^export /gm, '');
const note = (staff, step) => `<note><pitch><step>${step}</step><octave>5</octave></pitch><duration>4</duration><voice>${staff}</voice><type>whole</type><staff>${staff}</staff></note>`;
const backup = '<backup><duration>4</duration></backup>';
const score = `<?xml version="1.0"?><score-partwise version="4.0"><part-list>
  <score-part id="P1"><part-name>B♭ Trumpet</part-name></score-part>
  <score-part id="P2"><part-name>Voice</part-name></score-part>
  <score-part id="P3"><part-name>Voice</part-name></score-part>
</part-list>
<part id="P1">
  <measure number="1"><attributes><divisions>1</divisions><key number="1"><fifths>0</fifths></key><key number="2"><fifths>0</fifths></key><key number="3"><fifths>0</fifths></key>
    <time><beats>4</beats><beat-type>4</beat-type></time><staves>3</staves>
    <clef number="1"><sign>G</sign><line>2</line></clef><clef number="2"><sign>G</sign><line>2</line></clef><clef number="3"><sign>G</sign><line>2</line></clef></attributes>
    ${note(1, 'C')}${backup}${note(2, 'E')}${backup}${note(3, 'G')}</measure>
  <measure number="2">${note(1, 'D')}${backup}${note(2, 'F')}${backup}${note(3, 'A')}</measure>
</part>
<part id="P2"><measure number="1"><attributes><divisions>1</divisions></attributes>${note(1, 'C')}</measure><measure number="2">${note(1, 'C')}</measure></part>
<part id="P3"><measure number="1"><attributes><divisions>1</divisions></attributes>${note(1, 'B')}</measure><measure number="2">${note(1, 'B')}</measure></part>
</score-partwise>`;

const browser = await chromium.launch();
try {
  const page = await browser.newPage({ locale: 'es-ES' });
  await page.goto('about:blank');
  await page.addScriptTag({ content: source + '\nwindow.filterMusicXmlPassage = filterMusicXmlPassage;' });
  // Parts, staves and the pitches of each staff that the filtered passage keeps.
  const kept = selection => page.evaluate(([xml, wanted]) => {
    const out = new DOMParser().parseFromString(window.filterMusicXmlPassage(xml, wanted, '1-2'), 'application/xml');
    return [...out.getElementsByTagName('part')].map(part => ({
      id: part.getAttribute('id'),
      name: [...out.getElementsByTagName('score-part')].find(entry => entry.getAttribute('id') === part.getAttribute('id'))
        .getElementsByTagName('part-name')[0].textContent,
      staves: part.getElementsByTagName('staves')[0]?.textContent ?? null,
      clefs: [...part.getElementsByTagName('clef')].map(clef => clef.getAttribute('number')),
      notes: [...part.getElementsByTagName('note')].map(item => (item.getElementsByTagName('staff')[0]?.textContent ?? '1') + item.getElementsByTagName('step')[0].textContent),
    }));
  }, [score, selection]);

  assert.deepEqual(await kept(['B♭ Trumpet 1']), [{ id: 'P1', name: 'B♭ Trumpet 1', staves: '1', clefs: ['1'], notes: ['1C', '1D'] }],
    'a passage of one trumpet shows only its staff, the one the audio plays');
  assert.deepEqual(await kept(['B♭ Trumpet 1', 'B♭ Trumpet 3']), [{ id: 'P1', name: 'B♭ Trumpet', staves: '2', clefs: ['1', '2'],
    notes: ['1C', '2G', '1D', '2A'] }], 'two trumpets of the part keep their two staves, renumbered');
  // A removed staff leaves its time: the next staff after a <backup> still starts on the beat.
  const timing = await page.evaluate(xml => {
    const out = new DOMParser().parseFromString(window.filterMusicXmlPassage(xml, ['B♭ Trumpet 1', 'B♭ Trumpet 3'], '1-1'), 'application/xml');
    let time = 0; const starts = [];
    for (const element of out.getElementsByTagName('measure')[0].children) {
      const duration = Number(element.getElementsByTagName('duration')[0]?.textContent || 0);
      if (element.localName === 'note') { starts.push(time); time += duration; }
      if (element.localName === 'backup') time -= duration;
      if (element.localName === 'forward') time += duration;
    }
    return starts;
  }, score);
  assert.deepEqual(timing, [0, 0], 'both kept staves start at the beginning of the measure');
  assert.deepEqual((await kept(['B♭ Trumpet']))[0].notes, ['1C', '2E', '3G', '1D', '2F', '3A'], 'the whole part when it is named whole');
  assert.deepEqual((await kept('B♭ Trumpet 3'))[0].notes, ['1G', '1A'], 'a single instrument keeps its staff, as before');
  assert.deepEqual((await kept(['Voice 2'])).map(part => [part.id, part.notes]), [['P3', ['1B', '1B']]], 'parts sharing a name are told apart by number');
  console.log('PASS: a passage shows the staves it plays, also inside a multi-staff part');
} finally {
  await browser.close();
}
