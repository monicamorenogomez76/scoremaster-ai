// The signed-in user's works and band template.
import { apiFetch, apiJson } from './api.js';
import { gradeScaleOf, gradeText } from './labels.js';
import { t } from './i18n.js';

async function failure(response, fallback) {
  try { const body = await response.json(); return new Error(typeof body.detail === 'string' ? body.detail : fallback); }
  catch { return new Error(fallback); }
}

const json = apiJson;

export const listWorks = async () => (await json('/works', {}, t('No se pudo cargar la biblioteca.'))).works;

// The latest analysis and the original file, so the score opens without uploading it again.
export async function loadWork(id, onDownloading = () => {}) {
  const data = await json('/works/' + encodeURIComponent(id), {}, t('No se pudo abrir la obra.'));
  onDownloading();
  const response = await apiFetch('/works/' + encodeURIComponent(id) + '/file');
  if (!response.ok) throw await failure(response, t('No se pudo abrir la obra.'));
  const name = /filename="([^"]+)"/.exec(response.headers.get('Content-Disposition') || '')?.[1] || 'obra.musicxml';
  return { data, file: new File([await response.blob()], name) };
}

export const deleteWork = id => json('/works/' + encodeURIComponent(id), { method: 'DELETE' }, t('No se pudo eliminar la obra.'));

export const loadBand = async () => (await json('/band', {}, t('No se pudo cargar la plantilla.'))).profile;

export async function saveBand(changes) {
  const body = JSON.stringify({ profile: changes });
  return (await json('/band', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body },
    t('No se pudo guardar la plantilla.'))).profile;
}

export function workSummaryText(work) {
  const summary = work?.summary || {};
  if (summary.grade == null) return t('Sin análisis');
  const scale = gradeScaleOf({ scale: { grades: summary.grade_max } });
  const count = summary.critical_passages ?? 0;
  return gradeText(summary, scale) + ' · ' + t(count === 1 ? '{count} pasaje crítico' : '{count} pasajes críticos', { count })
    + ' · ' + t('{percent} % de la plantilla', { percent: summary.compatibility_percent ?? 0 });
}

export function durationText(duration) {
  if (!duration) return '';
  const minutes = Math.floor(duration.seconds / 60), seconds = String(duration.seconds % 60).padStart(2, '0');
  return minutes + ':' + seconds + (duration.assumed_tempo ? ' ' + t('(tempo supuesto)') : '');
}

// How far the band is with a work: set by the director, independent of the analysed difficulty.
export const preparationLabelsEs = { review: 'Por revisar', preparing: 'En preparación', ready: 'Lista para programa', archived: 'Archivada' };
export const preparationLabels = () => Object.fromEntries(Object.entries(preparationLabelsEs).map(([status, label]) => [status, t(label)]));

export const updatePreparation = (id, status) => json('/works/' + encodeURIComponent(id), {
  method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ preparation_status: status }),
}, t('No se pudo cambiar el estado de la obra.'));

// A work read from a PDF says so: its grade is provisional (2026-10-27).
export const analysisStatusText = work => (work?.summary?.grade == null ? t('Sin analizar')
  : work.source_format === 'pdf' ? t('Disponible · leída de PDF') : t('Disponible'));

// Critical passages of the works in preparation (origin "analysis"; the director's notes arrive later).
export const listPriorities = async () => (await json('/works/priorities', {}, t('No se pudieron cargar las prioridades.'))).priorities;

export function groupPrioritiesBySection(priorities) {
  const sections = new Map();
  for (const item of priorities) {
    const section = item.family_label_es || item.family || 'Otras';
    sections.set(section, [...(sections.get(section) || []), item]);
  }
  return [...sections];
}
