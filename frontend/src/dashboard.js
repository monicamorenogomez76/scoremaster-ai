// Director's dashboard (2026-10-26): the plan of the band shows which sections need work, counted from the
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

export function planDescription(counts) {
  return 'Plano de la banda con las prioridades de cada sección: '
    + PLAN_FAMILIES.map(family => PLAN_LABELS[family] + ', ' + (counts[family] ? counts[family] : 'ninguna')).join('; ') + '.';
}
