// Grades publishers give a work (2026-10-14): typed in by the director with
// their source and compared with ScoreLint's grade. Equivalences in docs/DIFICULTAD.md.
import { apiFetch, apiJson } from './api.js';
import { dateLocale, t } from './i18n.js';

const PEPPER = [['VE', 'muy fácil'], ['E', 'fácil'], ['ME', 'medio fácil'], ['M', 'medio'], ['MA', 'medio avanzado'], ['A', 'avanzado']];
// Labels of the scales, translated where they are shown: t('Grade (0,5 a 6)'), t('J.W. Pepper (VE a A)').
export const scales = [['grade', 'Grade (0,5 a 6)'], ['pepper', 'J.W. Pepper (VE a A)']];

export function valueOptions(scale) {
  if (scale === 'pepper') return PEPPER.map(([letters, label]) => [letters, letters + ' · ' + t(label)]);
  return Array.from({ length: 12 }, (_, index) => String((index + 1) / 2)).map(value => [value, 'Grade ' + value]);
}

const number = value => (Math.round(value * 100) / 100).toLocaleString(dateLocale());

export function comparisonText(scorelint, grades) {
  if (!grades.length) return t('ScoreLint: grado {grade}. Añade el grado que publica una editorial para compararlo.', { grade: scorelint });
  const published = grades.reduce((sum, item) => sum + item.grade, 0) / grades.length;
  const difference = scorelint - published;
  const verdict = Math.abs(difference) < 0.05 ? t('coinciden')
    : t(difference > 0 ? 'ScoreLint puntúa {difference} más difícil' : 'ScoreLint puntúa {difference} más fácil', { difference: number(Math.abs(difference)) });
  return t('ScoreLint: grado {grade} · editoriales: {published}', { grade: scorelint, published: number(published) }) +
    (grades.length > 1 ? ' ' + t('(media de {count})', { count: grades.length }) : '') + ' · ' + verdict + '.';
}

const path = workId => '/works/' + encodeURIComponent(workId) + '/external-grades';

export const listExternalGrades = async workId =>
  (await apiJson(path(workId), {}, t('No se pudieron cargar los grados publicados.'))).grades;

export async function addExternalGrade(workId, grade) {
  const body = { scale: grade.scale, value: grade.value, source: (grade.source || '').trim(),
    url: (grade.url || '').trim() || null, consulted_on: grade.consulted_on || null };
  const response = await apiFetch(path(workId), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!response.ok) {
    // A failed validation comes as a list of errors: the first message, without Pydantic's prefix.
    const detail = await response.json().then(data => data.detail).catch(() => null);
    const message = Array.isArray(detail) ? detail[0]?.msg : detail;
    throw new Error(typeof message === 'string' ? message.replace(/^Value error, /, '') : t('No se pudo guardar el grado.'));
  }
  return response.json();
}

export const deleteExternalGrade = (workId, gradeId) =>
  apiJson(path(workId) + '/' + encodeURIComponent(gradeId), { method: 'DELETE' }, t('No se pudo borrar el grado.'));
