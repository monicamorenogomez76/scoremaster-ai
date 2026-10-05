// Saved rehearsals of the signed-in user: several works per rehearsal and an agenda of blocks,
// each naming the work rehearsed in it (author's decisions, 2026-10-05).
import { apiJson } from './api.js';
import { blockScoreLabel, calendarLabel, rehearsalBlockDetail, rehearsalGroupName } from './labels.js';
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
  if (segment.type === 'tutti') return 'Tutti para juntar';
  if (segment.type === 'common') return blockScoreLabel(segment);
  return 'Seccional · ' + blockScoreLabel(segment);
}

function proposalSections(segment) {
  if (segment.type === 'warmup' || segment.type === 'tutti') return ['Toda la banda'];
  if (segment.type === 'common') return (segment.groups || []).map(rehearsalGroupName);
  return [rehearsalGroupName(segment.group)];
}

const proposalGroup = segment => (segment.type === 'sectional' ? segment.group || 'other' : segment.type);

// Blocks of the editor, each with its work and measures, within the API's limits.
export function proposalBlocks(proposal) {
  return proposal.blocks.map(segment => ({
    title: proposalTitle(segment), minutes: segment.minutes, group: proposalGroup(segment), work_id: segment.work_id || null, work_title: segment.work_title || null,
    measures: (segment.type === 'tutti' ? (segment.measure_ranges || []).join(', ') : segment.measure_range || '').slice(0, 40),
    sections: [...new Set(proposalSections(segment))].slice(0, 20),
    objective: (segment.type === 'warmup' ? WARMUP_OBJECTIVE : rehearsalBlockDetail(segment)).slice(0, 500),
  }));
}

// Type of a block: it colours the agenda calendar with the colours of the rehearsal plan.
const SECTIONS = ['flutes', 'double_reeds', 'clarinets', 'saxophones', 'high_brass', 'low_voices', 'percussion', 'strings_rhythm'];

export const blockTypeOptions = () => [['warmup', 'Calentamiento'], ['common', 'Línea o ritmo común'],
  ...SECTIONS.map(group => [group, 'Seccional · ' + rehearsalGroupName(group)]), ['tutti', 'Tutti'], ['other', 'Otro']];

export function agendaCalendarLabel(block) {
  if (block.group === 'warmup') return 'Calentam.';
  if (block.group === 'common') return 'Común';
  if (block.group === 'tutti') return 'Tutti';
  return calendarLabel({ type: 'sectional', group: SECTIONS.includes(block.group) ? block.group : 'other' });
}

// Clock times of the agenda from the rehearsal's start; minutes typed in the editor are text.
export const agendaSchedule = (blocks, start) => rehearsalSchedule(
  blocks.map(block => ({ ...block, minutes: Number(block.minutes) || 0 })), start || undefined);
