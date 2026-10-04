// The signed-in user's works and band template.
import { apiFetch } from './api.js';

async function failure(response, fallback) {
  try { const body = await response.json(); return new Error(typeof body.detail === 'string' ? body.detail : fallback); }
  catch { return new Error(fallback); }
}

async function json(url, options, fallback) {
  const response = await apiFetch(url, options);
  if (!response.ok) throw await failure(response, fallback);
  return response.status === 204 ? null : response.json();
}

export const listWorks = async () => (await json('/works', {}, 'No se pudo cargar la biblioteca.')).works;

// The latest analysis and the original file, so the score opens without uploading it again.
export async function loadWork(id) {
  const data = await json('/works/' + encodeURIComponent(id), {}, 'No se pudo abrir la obra.');
  const response = await apiFetch('/works/' + encodeURIComponent(id) + '/file');
  if (!response.ok) throw await failure(response, 'No se pudo abrir la obra.');
  const name = /filename="([^"]+)"/.exec(response.headers.get('Content-Disposition') || '')?.[1] || 'obra.musicxml';
  return { data, file: new File([await response.blob()], name) };
}

export const deleteWork = id => json('/works/' + encodeURIComponent(id), { method: 'DELETE' }, 'No se pudo eliminar la obra.');

export const loadBand = async () => (await json('/band', {}, 'No se pudo cargar la plantilla.')).profile;

export async function saveBand(changes) {
  const body = JSON.stringify({ profile: changes });
  return (await json('/band', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body },
    'No se pudo guardar la plantilla.')).profile;
}

const plural = (count, one, many) => count + ' ' + (count === 1 ? one : many);

export function workSummaryText(work) {
  const summary = work?.summary || {};
  if (summary.grade == null) return 'Sin análisis';
  return 'Grado ' + summary.grade + ' · ' + plural(summary.critical_passages ?? 0, 'pasaje crítico', 'pasajes críticos')
    + ' · ' + (summary.compatibility_percent ?? 0) + ' % de la plantilla';
}

export function durationText(duration) {
  if (!duration) return '';
  const minutes = Math.floor(duration.seconds / 60), seconds = String(duration.seconds % 60).padStart(2, '0');
  return minutes + ':' + seconds + (duration.assumed_tempo ? ' (tempo supuesto)' : '');
}
