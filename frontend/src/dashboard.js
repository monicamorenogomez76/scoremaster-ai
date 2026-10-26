// Director's dashboard (2026-10-26): «Dónde trabajar» shows which sections need work, counted from the
// priorities. Plain functions so the Node tests can import them.

export const PLAN_FAMILIES = ['woodwinds', 'brass', 'percussion', 'strings'];
const PLAN_LABELS = { woodwinds: 'viento madera', brass: 'viento metal', percussion: 'percusión', strings: 'cuerda' };

// Section names of the rehearsal groups and of the analysis families, to the family they sit with in the band.
const SECTION_FAMILIES = {
  'flautas': 'woodwinds', 'dobles cañas': 'woodwinds', 'clarinetes': 'woodwinds', 'saxofones': 'woodwinds', 'viento madera': 'woodwinds',
  'metales agudos': 'brass', 'graves': 'brass', 'viento metal': 'brass',
  'percusión': 'percussion',
  'cuerda y rítmica': 'strings', 'cuerda': 'strings',
};

export function familyOfSection(label) {
  const first = String(label || '').split(',')[0].trim().toLowerCase();
  return SECTION_FAMILIES[first] || null;
}

export function planCounts(rows) {
  const counts = Object.fromEntries(PLAN_FAMILIES.map(family => [family, 0]));
  for (const row of rows || []) if (row.family in counts) counts[row.family] += 1;
  return counts;
}

// One sentence on top of the bars, so the director does not have to read the chart (2026-10-26).
export function workHeadline(counts) {
  const top = Math.max(...PLAN_FAMILIES.map(family => counts[family] || 0));
  if (!top) return 'Sin prioridades por ahora.';
  const leaders = PLAN_FAMILIES.filter(family => counts[family] === top).map(family => PLAN_LABELS[family]);
  const names = leaders.length === 1 ? leaders[0] : leaders.slice(0, -1).join(', ') + ' y ' + leaders[leaders.length - 1];
  const passages = top + (top === 1 ? ' pasaje' : ' pasajes');
  return 'Más trabajo en ' + names + ': ' + passages + (leaders.length > 1 ? ' cada una' : '') + '.';
}
