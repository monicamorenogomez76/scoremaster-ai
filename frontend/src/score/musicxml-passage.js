// MusicXML helpers for the viewers: measure ranges and single-part passage extraction.
import { t } from '../i18n.js';
export function parseMeasureRange(value) {
  const values = String(value).split('-').map((part) => Number.parseInt(part, 10));
  if (!values.length || values.some((number) => !Number.isFinite(number))) {
    throw new Error(t('El rango de compases del pasaje no es válido.'));
  }
  return [values[0], values[1] || values[0]];
}

// Part names are compared as the analysis reports them: whitespace and line breaks collapsed.
const normalizeName = text => text.replace(/\s+/g, ' ').trim();

export function filterMusicXmlPassage(source, instrumentName, measureRange) {
  const [firstMeasure, lastMeasure] = parseMeasureRange(measureRange);
  const documentXml = new DOMParser().parseFromString(source, 'application/xml');
  if (documentXml.querySelector('parsererror')) {
    throw new Error(t('No se pudo interpretar el MusicXML original.'));
  }
  const descendants = (parent, name) => Array.from(parent.getElementsByTagName('*'))
    .filter((element) => element.localName === name);
  const directChild = (parent, name) => Array.from(parent.children)
    .find((element) => element.localName === name);
  const scoreParts = descendants(documentXml, 'score-part');
  const named = (target) => scoreParts.filter((part) => {
    const name = directChild(part, 'part-name');
    return name && normalizeName(name.textContent) === target;
  });
  // Staves declared by each part: the analysis splits a multi-staff part into one instrument per staff.
  const stavesOf = new Map(descendants(documentXml, 'part').map(part =>
    [part.getAttribute('id'), Number(descendants(part, 'staves')[0]?.textContent || 1)]));
  // Part id → staves to keep (written numbers, in order); a part without an entry is kept whole.
  const staffSelection = new Map();
  let matchingParts = scoreParts, selectedStaffNumber = null;
  if (Array.isArray(instrumentName)) {
    // A rehearsal block or a campaign passage. The analysis numbers parts sharing a name ("Voice 3"
    // is the third "Voice") and staves of one part ("B♭ Trumpet 3" is the third staff of
    // «B♭ Trumpet»): a numbered staff keeps only that staff, the one the audio plays (2026-10-14).
    const wanted = new Set(instrumentName.map(normalizeName));
    const nameOf = part => normalizeName(directChild(part, 'part-name')?.textContent || '');
    matchingParts = scoreParts.filter(part => {
      const name = nameOf(part);
      const sameName = scoreParts.filter(other => nameOf(other) === name);
      if (wanted.has(name)) return true;
      if (sameName.length > 1) return wanted.has(name + ' ' + (sameName.indexOf(part) + 1));
      const numbers = [...wanted].filter(entry => entry.startsWith(name + ' ') && /^\d+$/.test(entry.slice(name.length + 1)))
        .map(entry => Number(entry.slice(name.length + 1)));
      const staves = stavesOf.get(part.getAttribute('id')) || 1;
      const inPart = numbers.filter(number => number <= staves).sort((a, b) => a - b);
      if (staves > 1 && inPart.length) staffSelection.set(part.getAttribute('id'), inPart);
      return numbers.length > 0;
    });
  } else if (instrumentName !== null) {
    // A part literally named "B♭ Cornet 2" wins; otherwise the trailing number selects
    // a staff of a multi-staff part, or one of several parts sharing a name.
    const exact = named(normalizeName(instrumentName));
    const partMatch = normalizeName(instrumentName).match(/^(.*)\s+(\d+)$/);
    if (exact.length === 1 || !partMatch) {
      matchingParts = exact;
    } else {
      matchingParts = named(partMatch[1]);
      selectedStaffNumber = Number(partMatch[2]);
    }
  }
  if (matchingParts.length > 1 && selectedStaffNumber) {
    const selectedPart = matchingParts[selectedStaffNumber - 1];
    matchingParts = selectedPart ? [selectedPart] : [];
    selectedStaffNumber = null;
  }
  if (selectedStaffNumber && matchingParts.length === 1) staffSelection.set(matchingParts[0].getAttribute('id'), [selectedStaffNumber]);
  const selectedIds = new Set(matchingParts.map((part) => part.getAttribute('id')));
  if (selectedIds.size === 0) {
    throw new Error(t('No se encontró el instrumento dentro del MusicXML.'));
  }

  scoreParts.forEach((part) => {
    if (!selectedIds.has(part.getAttribute('id'))) part.parentNode.removeChild(part);
  });
  const scorePartsData = descendants(documentXml, 'part');
  let retainedMeasures = 0;
  scorePartsData.forEach((part) => {
    if (!selectedIds.has(part.getAttribute('id'))) {
      part.parentNode.removeChild(part);
      return;
    }
    const scorePartName = scoreParts.find((entry) => entry.getAttribute('id') === part.getAttribute('id'));
    const nameElement = scorePartName && directChild(scorePartName, 'part-name');
    const staves = staffSelection.get(part.getAttribute('id'));
    if (nameElement && typeof instrumentName === 'string') nameElement.textContent = instrumentName;
    else if (nameElement && staves?.length === 1) nameElement.textContent = normalizeName(nameElement.textContent) + ' ' + staves[0];
    let previousAttributes = null;
    let firstRetained = true;
    Array.from(part.children).filter((element) => element.localName === 'measure').forEach((measure) => {
      const measureNumber = Number.parseInt(measure.getAttribute('number'), 10);
      const attributes = directChild(measure, 'attributes');
      if (attributes) {
        if (!previousAttributes) previousAttributes = attributes.cloneNode(true);
        else Array.from(attributes.children).forEach((element) => {
          const inherited = Array.from(previousAttributes.children).find((candidate) =>
            candidate.localName === element.localName &&
            candidate.getAttribute('number') === element.getAttribute('number'));
          if (inherited) previousAttributes.replaceChild(element.cloneNode(true), inherited);
          else previousAttributes.append(element.cloneNode(true));
        });
      }
      if (measureNumber < firstMeasure || measureNumber > lastMeasure) {
        part.removeChild(measure);
        return;
      }
      if (firstRetained && previousAttributes) {
        const print = directChild(measure, 'print');
        if (attributes) measure.replaceChild(previousAttributes.cloneNode(true), attributes);
        else measure.insertBefore(previousAttributes.cloneNode(true), print ? print.nextSibling : measure.firstChild);
      }
      if (staves) {
        // Kept staves are renumbered 1..n; a removed note leaves a <forward> of its duration so the
        // staves after a <backup> keep their place in the measure.
        const renumber = number => staves.indexOf(number) + 1;
        const currentAttributes = directChild(measure, 'attributes');
        if (currentAttributes) {
          Array.from(currentAttributes.children).forEach((element) => {
            if (element.localName === 'staves') element.textContent = String(staves.length);
            if (['clef', 'staff-details', 'key', 'transpose'].includes(element.localName) && element.hasAttribute('number')) {
              const kept = renumber(Number(element.getAttribute('number')));
              if (!kept) currentAttributes.removeChild(element);
              else element.setAttribute('number', String(kept));
            }
          });
        }
        Array.from(measure.children).forEach((element) => {
          if (!['note', 'direction'].includes(element.localName)) return;
          const staff = directChild(element, 'staff');
          const kept = renumber(Number(staff ? staff.textContent : '1'));
          if (kept) {
            if (staff) staff.textContent = String(kept);
            return;
          }
          const duration = directChild(element, 'duration');
          if (element.localName === 'note' && duration && !directChild(element, 'chord') && !directChild(element, 'grace')) {
            const forward = measure.ownerDocument.createElementNS(measure.namespaceURI, 'forward');
            forward.append(duration.cloneNode(true));
            measure.replaceChild(forward, element);
          } else {
            measure.removeChild(element);
          }
        });
      }
      firstRetained = false;
      retainedMeasures += 1;
    });
  });
  if (retainedMeasures === 0) {
    throw new Error(t('El rango solicitado no contiene compases renderizables.'));
  }
  return new XMLSerializer().serializeToString(documentXml);
}

// First and last written measure numbers of a score.
export function measureBounds(source) {
  const xml = new DOMParser().parseFromString(source, 'application/xml');
  const numbers = Array.from(xml.getElementsByTagName('*')).filter(item => item.localName === 'measure')
    .map(item => Number.parseInt(item.getAttribute('number'), 10)).filter(Number.isFinite);
  if (!numbers.length) throw new Error(t('La partitura no contiene compases.'));
  return { first: numbers.reduce((a, b) => Math.min(a, b)), last: numbers.reduce((a, b) => Math.max(a, b)) };
}
