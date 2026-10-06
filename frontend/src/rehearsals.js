// Saved rehearsals of the signed-in user: several works per rehearsal and an agenda of blocks,
// each naming the work rehearsed in it (author's decisions, 2026-10-05).
import { apiJson } from './api.js';
import { blockScoreLabel, calendarLabel, findingLabel, rehearsalBlockDetail, rehearsalGroupName } from './labels.js';
import { rehearsalSchedule } from './schedule.js';

const send = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
const path = id => '/rehearsals/' + encodeURIComponent(id);

export const listRehearsals = async () => (await apiJson('/rehearsals', {}, 'No se pudieron cargar los ensayos.')).rehearsals;
export const createRehearsal = rehearsal => apiJson('/rehearsals', send('POST', rehearsal), 'No se pudo guardar el ensayo.');
export const updateRehearsal = (id, rehearsal) => apiJson(path(id), send('PUT', rehearsal), 'No se pudo guardar el ensayo.');
export const deleteRehearsal = id => apiJson(path(id), { method: 'DELETE' }, 'No se pudo eliminar el ensayo.');

// Local date as YYYY-MM-DD: "today" is the director's day, not the server's.
export function todayIso(now = new Date()) {
  return [now.getFullYear(), String(now.getMonth() + 1).padStart(2, '0'), String(now.getDate()).padStart(2, '0')].join('-');
}

const order = item => item.date + ' ' + (item.time || '');

// From today on a rehearsal is upcoming (soonest first); before today it was held (latest first).
export function splitRehearsals(rehearsals, today = todayIso()) {
  const sorted = rehearsals.slice().sort((left, right) => order(left).localeCompare(order(right)));
  return { upcoming: sorted.filter(item => item.date >= today), past: sorted.filter(item => item.date < today).reverse() };
}

export const nextRehearsal = (rehearsals, today = todayIso()) => splitRehearsals(rehearsals, today).upcoming[0] || null;

export function rehearsalDateText(rehearsal, today = todayIso()) {
  const time = rehearsal.time ? ' · ' + rehearsal.time : '';
  if (rehearsal.date === today) return 'Hoy' + time;
  const [year, month, day] = rehearsal.date.split('-').map(Number);
  return new Date(year, month - 1, day).toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }) + time;
}

export function agendaTime(blocks, duration) {
  const assigned = blocks.reduce((total, block) => total + (Number(block.minutes) || 0), 0);
  return { assigned, remaining: Math.max(0, duration - assigned), exceeded: Math.max(0, assigned - duration) };
}

export function moveBlock(blocks, index, step) {
  const target = index + step;
  if (target < 0 || target >= blocks.length) return blocks;
  const moved = blocks.slice();
  [moved[index], moved[target]] = [moved[target], moved[index]];
  return moved;
}

export const duplicateBlock = (blocks, index) => [...blocks.slice(0, index + 1), { ...blocks[index] }, ...blocks.slice(index + 1)];

export function blockWorkText(block) {
  if (!block.work_title) return 'Toda la banda · sin obra concreta';
  const several = /[-,]/.test(block.measures || '');
  const measures = block.measures ? (several ? 'cc. ' : 'c. ') + block.measures.replace(/-/g, '–') : '';
  return [block.work_title, measures].filter(Boolean).join(' · ');
}

// The app proposes the agenda of the chosen works (warm-up, then the ensemble plan of each work);
// nothing is saved until the director reviews it.
export const proposeRehearsal = (workIds, minutes) => apiJson('/rehearsals/proposal',
  send('POST', { work_ids: workIds, duration_minutes: minutes }), 'No se pudo proponer la agenda.');

const WARMUP_OBJECTIVE = 'Afinación, sonido y articulación de toda la banda.';

function proposalTitle(segment) {
  if (segment.type === 'warmup') return 'Calentamiento';
  if (segment.type === 'runthrough') return 'Pasada completa';
  if (segment.type === 'tutti') return 'Tutti para juntar';
  if (segment.type === 'common') return blockScoreLabel(segment);
  return 'Seccional · ' + blockScoreLabel(segment);
}

function proposalSections(segment) {
  if (['warmup', 'tutti', 'runthrough'].includes(segment.type)) return ['Toda la banda'];
  if (segment.type === 'common') return (segment.groups || []).map(rehearsalGroupName);
  return [rehearsalGroupName(segment.group)];
}

// A run-through of the general rehearsal has the colour of the tutti.
const proposalGroup = segment => (segment.type === 'sectional' ? segment.group || 'other'
  : segment.type === 'runthrough' ? 'tutti' : segment.type);
const RUNTHROUGH_OBJECTIVE = 'Obra completa en orden de concierto.';

// Blocks of the editor, each with its work and measures, within the API's limits.
export function proposalBlocks(proposal) {
  return proposal.blocks.map(segment => ({
    title: proposalTitle(segment), minutes: segment.minutes, group: proposalGroup(segment), parts: segment.parts || [], work_id: segment.work_id || null, work_title: segment.work_title || null,
    measures: (segment.type === 'tutti' ? (segment.measure_ranges || []).join(', ') : segment.measure_range || '').slice(0, 40),
    sections: [...new Set(proposalSections(segment))].slice(0, 20),
    objective: (segment.type === 'warmup' ? WARMUP_OBJECTIVE : segment.type === 'runthrough' ? RUNTHROUGH_OBJECTIVE
      : rehearsalBlockDetail(segment)).slice(0, 500),
  }));
}

// Type of a block: it colours the agenda calendar with the colours of the rehearsal plan.
const SECTIONS = ['flutes', 'double_reeds', 'clarinets', 'saxophones', 'high_brass', 'low_voices', 'percussion', 'strings_rhythm'];

export const blockTypeOptions = () => [['warmup', 'Calentamiento · banda completa'], ['common', 'Línea o ritmo común'],
  ...SECTIONS.map(group => [group, 'Seccional · ' + rehearsalGroupName(group)]), ['tutti', 'Tutti'], ['other', 'Otro']];

// Words that reveal the type of a block written by hand (accents and case ignored). The warm-up is a
// whole-band category of its own (author's decision, 2026-10-05).
const GROUP_WORDS = [
  ['warmup', ['calentamiento', 'banda completa']], ['tutti', ['tutti']], ['common', ['comun']],
  ['flutes', ['flauta', 'flautin']], ['double_reeds', ['doble', 'oboe', 'fagot']], ['clarinets', ['clarinete']],
  ['saxophones', ['saxo']], ['high_brass', ['metales agudos', 'trompeta', 'trompa', 'fliscorno', 'corneta']],
  ['low_voices', ['grave', 'trombon', 'bombardino', 'tuba']], ['percussion', ['percusion']],
  ['strings_rhythm', ['cuerda', 'ritmica', 'contrabajo']],
];
const plain = text => String(text || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

// The chosen type, or the one the title and sections reveal, so the calendar is always coloured.
export function blockGroup(block) {
  if (block.group && block.group !== 'other') return block.group;
  const sections = Array.isArray(block.sections) ? block.sections.join(' ') : block.sections;
  const text = plain(block.title + ' ' + (sections || ''));
  return (GROUP_WORDS.find(([, words]) => words.some(word => text.includes(word))) || ['other'])[0];
}

export function agendaCalendarLabel(block) {
  const group = blockGroup(block);
  if (group === 'warmup') return 'Calentam.';
  if (group === 'common') return 'Común';
  if (group === 'tutti') return plain(block.title).startsWith('pasada') ? 'Pasada' : 'Tutti';
  return calendarLabel({ type: 'sectional', group: SECTIONS.includes(group) ? group : 'other' });
}

// Clock times of the agenda from the rehearsal's start; minutes typed in the editor are text.
export const agendaSchedule = (blocks, start) => rehearsalSchedule(
  blocks.map(block => ({ ...block, minutes: Number(block.minutes) || 0 })), start || undefined);

// The director's review after a rehearsal (author's decision, 2026-10-06): one status and note per block.
export const reviewStatusOptions = [['resolved', 'Resuelto'], ['improve', 'Mejorable'], ['pending', 'Pendiente'], ['not_done', 'No se hizo']];
const statusLabel = status => (reviewStatusOptions.find(([value]) => value === status) || [, status])[1];

// Only a rehearsal held today or before can be reviewed.
export const canReview = (rehearsal, today = todayIso()) => rehearsal.date <= today;

export const reviewRehearsal = (id, notes, blocks) => apiJson(path(id) + '/review', send('PUT', { notes, blocks }),
  'No se pudo guardar la revisión.');
export const listReviewPriorities = async () => (await apiJson('/rehearsals/priorities', {}, 'No se pudieron cargar las prioridades.')).priorities;

const measuresOf = range => (!range ? '—' : (/[-,]/.test(range) ? 'cc. ' : 'c. ') + range.replace(/-/g, '–'));

// Rows of «Prioridades por sección»: what the director left pending first, then the analysis.
export function summaryPriorityRows(reviewItems, analysisItems) {
  return [
    ...reviewItems.map(item => ({ work_id: item.work_id, title: item.title, section: item.sections.join(', ') || 'Toda la banda',
      parts: item.parts || [], range: item.measure_range || '',
      detail: item.block, measures: measuresOf(item.measure_range),
      reason: [statusLabel(item.status), item.note].filter(Boolean).join(' · '), origin: 'Revisión', originTitle: 'Revisión del director' })),
    ...analysisItems.map(item => ({ work_id: item.work_id, title: item.title, section: item.family_label_es || item.family || 'Otras',
      parts: item.instrument ? [item.instrument] : [], range: item.measure_range || '',
      detail: item.instrument_label_es || item.instrument, measures: measuresOf(item.measure_range),
      reason: (item.findings || []).map(findingLabel).join(' · '), origin: 'Análisis', originTitle: 'Análisis de ScoreLint' })),
  ];
}

// The passage a block opens in the score viewer: from its first to its last measure; null opens the work.
export function passageRange(measures) {
  const bounds = String(measures || '').split(/[,\-–]/).map(value => Number(value.trim())).filter(Number.isFinite).filter(Boolean);
  if (!bounds.length) return null;
  const first = Math.min(...bounds), last = Math.max(...bounds);
  return first === last ? String(first) : first + '-' + last;
}
