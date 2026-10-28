// Concerts of the signed-in user: programme, weekly rehearsal pattern and the series of rehearsals
// that prepares each one (decided 2026-10-06).
import { apiJson } from './api.js';
import { proposalBlocks, rehearsalDateText } from './rehearsals.js';

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

// The next concert in the summary's heading: its day, the days left and the rehearsals still to do. On the day
// itself «Hoy» says it all (reported 2026-10-26: it read «Hoy · hoy · 0 ensayos»).
export function nextConcertText({ concert, remaining, days }, today) {
  const plural = (count, one, many) => count + ' ' + (count === 1 ? one : many);
  return [concert.title, rehearsalDateText(concert, today),
    ...(days === 0 ? [] : [(days === 1 ? 'falta ' : 'faltan ') + plural(days, 'día', 'días'), plural(remaining, 'ensayo', 'ensayos')]),
  ].join(' · ');
}

// Next step of the next concert for the summary assistant (decided 2026-10-06): review the
// rehearsal already held, replan after a review newer than the plan, plan a concert without series,
// or show its next rehearsal. Without concerts the assistant proposes a single rehearsal.
export function assistantStep(concerts, rehearsals, today) {
  const upcoming = nextConcert(concerts, today);
  if (!upcoming) return { step: 'free' };
  const { concert } = upcoming;
  const series = rehearsals.filter(item => item.concert_id === concert.id).sort((left, right) => left.date.localeCompare(right.date));
  if (!series.length) return { step: 'plan', concert };
  const unreviewed = series.filter(item => item.date <= today && !item.reviewed_at);
  if (unreviewed.length) return { step: 'review', concert, rehearsal: unreviewed[unreviewed.length - 1] };
  const coming = series.filter(item => item.date > today || (item.date === today && !item.reviewed_at));
  const lastReview = series.map(item => item.reviewed_at).filter(Boolean).sort().pop();
  const stale = coming.find(item => !item.fixed && !item.reviewed_at && lastReview && (item.updated_at || '') < lastReview);
  if (stale) return { step: 'replan', concert, rehearsal: stale };
  return coming.length ? { step: 'next', concert, rehearsal: coming[0] } : { step: 'plan', concert };
}
