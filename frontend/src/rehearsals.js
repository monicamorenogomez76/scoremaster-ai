// Saved rehearsals of the signed-in user: several works per rehearsal and an agenda of blocks,
// each naming the work rehearsed in it (author's decisions, 2026-10-05).
import { apiJson } from './api.js';

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
  const measures = block.measures ? (block.measures.includes('-') ? 'cc. ' + block.measures.replace('-', '–') : 'c. ' + block.measures) : '';
  return [block.work_title, measures].filter(Boolean).join(' · ');
}
