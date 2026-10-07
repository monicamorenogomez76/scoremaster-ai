// The signed-in user's works and band template.
import { apiFetch, apiJson } from './api.js';
import { gradeScaleOf, gradeText } from './labels.js';

async function failure(response, fallback) {
  try { const body = await response.json(); return new Error(typeof body.detail === 'string' ? body.detail : fallback); }
  catch { return new Error(fallback); }
}

const json = apiJson;

export const listWorks = async () => (await json('/works', {}, 'No se pudo cargar la biblioteca.')).works;

// The latest analysis and the original file, so the score opens without uploading it again.
export async function loadWork(id, onDownloading = () => {}) {
  const data = await json('/works/' + encodeURIComponent(id), {}, 'No se pudo abrir la obra.');
  onDownloading();
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
  const scale = gradeScaleOf({ scale: { grades: summary.grade_max } });
  return gradeText(summary, scale) + ' · ' + plural(summary.critical_passages ?? 0, 'pasaje crítico', 'pasajes críticos')
    + ' · ' + (summary.compatibility_percent ?? 0) + ' % de la plantilla';
}

export function durationText(duration) {
  if (!duration) return '';
  const minutes = Math.floor(duration.seconds / 60), seconds = String(duration.seconds % 60).padStart(2, '0');
  return minutes + ':' + seconds + (duration.assumed_tempo ? ' (tempo supuesto)' : '');
}

// How far the band is with a work: set by the director, independent of the analysed difficulty.
export const preparationLabelsEs = { review: 'Por revisar', preparing: 'En preparación', ready: 'Lista para programa', archived: 'Archivada' };

export const updatePreparation = (id, status) => json('/works/' + encodeURIComponent(id), {
  method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ preparation_status: status }),
}, 'No se pudo cambiar el estado de la obra.');

export const analysisStatusText = work => (work?.summary?.grade == null ? 'Sin analizar' : 'Disponible');

// Critical passages of the works in preparation (origin "analysis"; the director's notes arrive later).
export const listPriorities = async () => (await json('/works/priorities', {}, 'No se pudieron cargar las prioridades.')).priorities;

export function groupPrioritiesBySection(priorities) {
  const sections = new Map();
  for (const item of priorities) {
    const section = item.family_label_es || item.family || 'Otras';
    sections.set(section, [...(sections.get(section) || []), item]);
  }
  return [...sections];
}
