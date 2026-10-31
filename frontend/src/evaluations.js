// Evaluation campaigns (steps 16-18, decided 2026-10-07): the director proposes passages of
// her works, invites musicians by the email of their account and exports their ratings.
import { apiFetch, apiJson } from './api.js';
import { t } from './i18n.js';

const send = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
const path = id => '/evaluations/' + encodeURIComponent(id);

export const listCampaigns = () => apiJson('/evaluations', {}, t('No se pudieron cargar las campañas.'));
export const getCampaign = id => apiJson(path(id), {}, t('No se pudo abrir la campaña.'));
export const createCampaign = campaign => apiJson('/evaluations', send('POST', campaign), t('No se pudo crear la campaña.'));
export const removePassage = (id, passageId) => apiJson(path(id) + '/passages/' + encodeURIComponent(passageId),
  { method: 'DELETE' }, t('No se pudo quitar el pasaje.'));
export const setInvitations = (id, emails) => apiJson(path(id) + '/invitations', send('PUT', { emails }),
  t('No se pudieron guardar las invitaciones.'));
export const setCampaignStatus = (id, status) => apiJson(path(id) + '/status', send('POST', { status }),
  t('No se pudo cambiar el estado de la campaña.'));

// The results with the prediction and anonymous evaluators, saved as a JSON file for step 19.
export async function exportCampaign(campaign) {
  const response = await apiFetch(path(campaign.id) + '/export');
  if (!response.ok) throw new Error(t('No se pudieron exportar los resultados.'));
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([JSON.stringify(await response.json(), null, 2)], { type: 'application/json' }));
  link.download = exportFileName(campaign);
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

export function exportFileName(campaign) {
  const slug = (campaign.title || 'campaña').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  return 'valoraciones-' + (slug || 'campana') + '.json';
}

// One per line, or separated by commas, semicolons or spaces; repeated ones count once.
export function parseEmails(text) {
  return [...new Set((text || '').split(/[\s,;]+/).map(item => item.trim().toLowerCase()).filter(Boolean))];
}

const STATUSES = { draft: 'Borrador', open: 'Abierta', closed: 'Cerrada' };
export const statusLabel = status => (STATUSES[status] ? t(STATUSES[status]) : status);

// What ScoreLint predicted for the passage: only the director sees it, never the musicians.
export const predictionText = snapshot => t('Grado {grade}', { grade: snapshot.grade }) + (snapshot.critical ? ' · ' + t('crítico') : '');

export function invitationProgress(invitation, total) {
  if (!invitation.rated && !invitation.profile_done) return t('Aún no ha empezado');
  if (invitation.rated >= total) return t('Ha valorado todos los pasajes');
  return t('{rated} de {total} pasajes', { rated: invitation.rated, total });
}

export function campaignSummary(campaign) {
  const passages = campaign.passages || [];
  const critical = passages.filter(item => item.snapshot?.critical).length, invited = (campaign.invitations || []).length;
  return [t(passages.length === 1 ? '{count} pasaje' : '{count} pasajes', { count: passages.length }),
    t(critical === 1 ? '{count} crítico según ScoreLint' : '{count} críticos según ScoreLint', { count: critical }),
    t(invited === 1 ? '{count} músico invitado' : '{count} músicos invitados', { count: invited })].join(' · ');
}

export function shortfallText(requested, proposed) {
  if (proposed >= requested) return '';
  return t('Se han propuesto {proposed} de los {requested} pasajes pedidos: las obras elegidas no dan para más. Añade obras si necesitas más.',
    { proposed, requested });
}

// The musician's side: the same rubric as ScoreLint (docs/DIFICULTAD.md), never its prediction.
// Aligned with the Grade 1-6 scale of band publishers (decided 2026-10-13).
export const GRADE_RUBRIC = [
  { grade: 1, label: 'Muy fácil', standard: 'Grade 1', description: 'Primer año de instrumento: negras, blancas y redondas en compases simples, con tesitura reducida.' },
  { grade: 2, label: 'Fácil', standard: 'Grade 2', description: 'Unos dos años de práctica: corcheas, puntillos, síncopas y tresillos sencillos, primeros compases compuestos.' },
  { grade: 3, label: 'Intermedio', standard: 'Grade 3', description: 'Tres o cuatro años de práctica: síncopas frecuentes, cambios de compás y tesitura media o amplia.' },
  { grade: 4, label: 'Intermedio avanzado', standard: 'Grade 4', description: 'Cuatro a seis años de práctica: ritmos exigentes, tonalidades y compases menos habituales, pasajes técnicos.' },
  { grade: 5, label: 'Avanzado', standard: 'Grade 5', description: 'Siete a nueve años de práctica: ritmos muy exigentes, compases cambiantes o asimétricos, toda la tesitura y escritura virtuosística.' },
  { grade: 6, label: 'Profesional', standard: 'Grade 6', description: 'Nivel profesional o superior: extremadamente difícil en todos los aspectos.' },
];
export const EXPERIENCE_OPTIONS = [['estudiante', 'Estudiante'], ['amateur', 'Músico amateur'], ['profesional', 'Profesional'],
  ['docente', 'Docente o director']];
export const PRIORITY_LABELS = { 1: 'Puede esperar', 2: 'Baja', 3: 'Media', 4: 'Alta', 5: 'Ensayarlo cuanto antes' };

export const saveProfile = (id, level, instrument) => apiJson(path(id) + '/profile',
  send('PUT', { experience_level: level, main_instrument: instrument.trim() }), t('No se pudo guardar tu perfil.'));
export const saveRating = (id, passageId, rating) => apiJson(path(id) + '/passages/' + encodeURIComponent(passageId) + '/rating',
  send('PUT', rating), t('No se pudo guardar la valoración.'));
// The whole work of a passage: musicians do not have it in their own repertoire.
export async function evaluationWorkFile(id, workId) {
  const response = await apiFetch(path(id) + '/works/' + encodeURIComponent(workId) + '/file');
  if (!response.ok) throw new Error(t('No se pudo abrir la obra del pasaje.'));
  const name = /filename="([^"]+)"/.exec(response.headers.get('Content-Disposition') || '')?.[1] || 'obra.musicxml';
  return new File([await response.blob()], name);
}

// The form keeps strings (radio buttons); the API receives numbers and a boolean.
export function ratingDraft(rating) {
  if (!rating) return { difficulty: '', critical: '', priority: '', comment: '' };
  return { difficulty: String(rating.difficulty), critical: rating.critical ? 'yes' : 'no', priority: String(rating.priority),
    comment: rating.comment || '' };
}

export function ratingToSend(draft) {
  if (!draft.difficulty || !draft.critical || !draft.priority) return null;
  return { difficulty: Number(draft.difficulty), critical: draft.critical === 'yes', priority: Number(draft.priority),
    comment: draft.comment.trim() };
}

export const ratedCount = campaign => (campaign.passages || []).filter(item => item.rating).length;

// The next passage without a rating after the current one (wrapping round); when all are rated, the next one.
export function nextToRate(passages, current) {
  for (let step = 1; step <= passages.length; step++) {
    const index = (current + step) % passages.length;
    if (!passages[index].rating) return index;
  }
  return Math.min(current + 1, passages.length - 1);
}

// Method B (step 22): the LLM rates every passage with the musicians' rubric, never seeing ScoreLint.
export const getLlmReview = id => apiJson(path(id) + '/llm-review', {}, t('No se pudo consultar la valoración con IA.'));
export const startLlmReview = id => apiJson(path(id) + '/llm-review', { method: 'POST' }, t('No se pudo iniciar la valoración con IA.'));

const reviewErrors = () => ({ timeout: t('la IA no respondió a tiempo'), rate_limit: t('la IA alcanzó su límite de uso'),
  invalid: t('la respuesta no seguía la rúbrica'), error: t('la IA no estaba disponible') });

export function llmReviewText(status) {
  if (!status.available) return t('Necesita configurar GEMINI_API_KEY en el servidor: sin IA real no hay método B (un sustituto con reglas sería otra heurística).');
  const who = status.provider + ' (' + status.model + ')';
  const values = { done: status.done, total: status.total, failed: status.failed, who };
  if (status.state === 'running') return t('Valorando con IA: {done} de {total} pasajes · {who}', values);
  if (status.state === 'paused') {
    return t('{done} de {total} pasajes valorados. La IA ha agotado su cupo gratuito: vuelve a pulsar más tarde (el cupo diario se renueva cada día) y seguirá donde se quedó.', values);
  }
  if (status.failed) {
    const errors = reviewErrors();
    return t('{done} de {total} pasajes valorados. {failed} no se pudieron valorar ({reason}): vuelve a pulsar para reintentarlos.',
      { ...values, reason: errors[status.last_error] || errors.error });
  }
  if (status.done >= status.total && status.total) return t('Los {total} pasajes están valorados por {who}.', values);
  if (!status.done) return t('Sin valorar todavía · {who}.', values);
  return t('{done} de {total} pasajes valorados por {who}.', values);
}

// Only an administrator creates and manages campaigns (decided 2026-10-14); any other account
// only rates the campaigns it is invited to and sees only its own ratings.
export const evaluationIntro = canManage => canManage
  ? t('Músicos de confianza valoran pasajes de tus obras para comparar su criterio con el de ScoreLint.')
  : t('Aquí aparecen las campañas a las que te invitan. Solo ves tus propias valoraciones.');
