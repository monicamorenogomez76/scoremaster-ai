// Concerts of the signed-in user: programme, weekly rehearsal pattern and the series of rehearsals
// that prepares each one (author's decisions, 2026-10-06).
import { apiJson } from './api.js';
import { proposalBlocks } from './rehearsals.js';

const send = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
const path = id => '/concerts/' + encodeURIComponent(id);

export const listConcerts = async () => (await apiJson('/concerts', {}, 'No se pudieron cargar los conciertos.')).concerts;
export const createConcert = concert => apiJson('/concerts', send('POST', concert), 'No se pudo guardar el concierto.');
export const updateConcert = (id, concert) => apiJson(path(id), send('PUT', concert), 'No se pudo guardar el concierto.');
export const deleteConcert = id => apiJson(path(id), { method: 'DELETE' }, 'No se pudo eliminar el concierto.');
// The series is proposed from the director's day; nothing is saved until it is reviewed.
export const proposeConcertPlan = (id, today) => apiJson(path(id) + '/plan', send('POST', { today }), 'No se pudo proponer la planificación.');
export const saveConcertPlan = (id, today, rehearsals) => apiJson(path(id) + '/rehearsals', send('PUT', { today, rehearsals }),
  'No se pudo guardar la planificación.');

const PHASES = { reading: 'Lectura y pasajes', passages: 'Pasajes e integración', integration: 'Integración', general: 'Ensayo general' };
export const phaseLabel = phase => PHASES[phase] || 'Ensayo';

// 0 = Monday … 6 = Sunday, as the API.
export const weekdayOptions = [[0, 'L', 'lunes'], [1, 'M', 'martes'], [2, 'X', 'miércoles'], [3, 'J', 'jueves'],
  [4, 'V', 'viernes'], [5, 'S', 'sábado'], [6, 'D', 'domingo']];

// Calendar days as UTC dates, so no time zone moves a day.
const toDate = iso => { const [year, month, day] = iso.split('-').map(Number); return new Date(Date.UTC(year, month - 1, day)); };
const toIso = value => value.toISOString().slice(0, 10);
const weekday = value => (value.getUTCDay() + 6) % 7;
const DAY = 24 * 60 * 60 * 1000;

export const daysUntil = (date, today) => Math.round((toDate(date) - toDate(today)) / DAY);

export function concertProgress(concert) {
  const rehearsals = concert.rehearsals || [];
  return { reviewed: rehearsals.filter(item => item.reviewed).length, total: rehearsals.length };
}

// Preview of the dates the pattern gives, from today on and before the concert day.
export function patternDates(schedule, concertDate, today) {
  if (!schedule?.weekdays?.length || !schedule.start_date || !concertDate) return [];
  const days = new Set(schedule.weekdays.map(Number));
  const dates = [];
  const start = schedule.start_date > today ? schedule.start_date : today;
  for (let day = toDate(start); day < toDate(concertDate); day = new Date(day.getTime() + DAY)) {
    if (days.has(weekday(day))) dates.push(toIso(day));
  }
  return dates;
}

// Weeks of a month from Monday; empty cells are null and each day carries its events.
export function monthGrid(year, month, events) {
  const first = new Date(Date.UTC(year, month - 1, 1));
  const length = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const cells = Array(weekday(first)).fill(null);
  for (let day = 1; day <= length; day++) {
    const iso = toIso(new Date(Date.UTC(year, month - 1, day)));
    cells.push({ day, date: iso, events: events.filter(event => event.date === iso) });
  }
  while (cells.length % 7) cells.push(null);
  return Array.from({ length: cells.length / 7 }, (_, index) => cells.slice(index * 7, index * 7 + 7));
}

// What PUT /concerts/{id}/rehearsals receives for every planned rehearsal of the series.
export function planItemsToSave(plan) {
  return plan.map(item => ({
    id: item.id, date: item.date, time: item.time, duration_minutes: item.duration_minutes, phase: item.phase,
    work_ids: item.work_ids,
    blocks: proposalBlocks(item).map(({ work_title, ...block }) => block),
  }));
}

// The next concert from today, with the days left and its rehearsals still to do.
export function nextConcert(concerts, today) {
  const concert = concerts.filter(item => item.date >= today).sort((left, right) => left.date.localeCompare(right.date))[0];
  if (!concert) return null;
  const remaining = (concert.rehearsals || []).filter(item => item.date >= today && !item.reviewed).length;
  return { concert, remaining, days: daysUntil(concert.date, today) };
}
