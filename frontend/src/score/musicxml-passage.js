// MusicXML helpers for the viewers: measure ranges and single-part passage extraction.
export function parseMeasureRange(value) {
  const values = String(value).split('-').map((part) => Number.parseInt(part, 10));
  if (!values.length || values.some((number) => !Number.isFinite(number))) {
    throw new Error('El rango de compases del pasaje no es válido.');
  }
  return [values[0], values[1] || values[0]];
}

// Part names are compared as the analysis reports them: whitespace and line breaks collapsed.
const normalizeName = text => text.replace(/\s+/g, ' ').trim();

export function filterMusicXmlPassage(source, instrumentName, measureRange) {
  const [firstMeasure, lastMeasure] = parseMeasureRange(measureRange);
  const documentXml = new DOMParser().parseFromString(source, 'application/xml');
  if (documentXml.querySelector('parsererror')) {
    throw new Error('No se pudo interpretar el MusicXML original.');
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
  let matchingParts = scoreParts, selectedStaffNumber = null;
  if (instrumentName !== null) {
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
  const selectedIds = new Set(matchingParts.map((part) => part.getAttribute('id')));
  if (selectedIds.size === 0) {
    throw new Error('No se encontró el instrumento dentro del MusicXML.');
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
    if (nameElement && instrumentName !== null) nameElement.textContent = instrumentName;
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
      if (selectedStaffNumber) {
        const currentAttributes = directChild(measure, 'attributes');
        if (currentAttributes) {
          Array.from(currentAttributes.children).forEach((element) => {
            if (element.localName === 'staves') element.textContent = '1';
            if (['clef', 'staff-details', 'key', 'transpose'].includes(element.localName) && element.hasAttribute('number')) {
              if (Number(element.getAttribute('number')) !== selectedStaffNumber) {
                currentAttributes.removeChild(element);
              } else {
                element.setAttribute('number', '1');
              }
            }
          });
        }
        Array.from(measure.children).forEach((element) => {
          if (!['note', 'direction'].includes(element.localName)) return;
          const staff = directChild(element, 'staff');
          const eventStaff = Number(staff ? staff.textContent : '1');
          if (eventStaff !== selectedStaffNumber) {
            measure.removeChild(element);
          } else if (staff) {
            staff.textContent = '1';
          }
        });
      }
      firstRetained = false;
      retainedMeasures += 1;
    });
  });
  if (retainedMeasures === 0) {
    throw new Error('El rango solicitado no contiene compases renderizables.');
  }
  return new XMLSerializer().serializeToString(documentXml);
}

// First and last written measure numbers of a score.
export function measureBounds(source) {
  const xml = new DOMParser().parseFromString(source, 'application/xml');
  const numbers = Array.from(xml.getElementsByTagName('*')).filter(item => item.localName === 'measure')
    .map(item => Number.parseInt(item.getAttribute('number'), 10)).filter(Number.isFinite);
  if (!numbers.length) throw new Error('La partitura no contiene compases.');
  return { first: numbers.reduce((a, b) => Math.min(a, b)), last: numbers.reduce((a, b) => Math.max(a, b)) };
}
