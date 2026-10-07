// Evaluation campaigns (steps 16-18, author's decisions, 2026-10-07): the director proposes passages of
// her works, invites musicians by the email of their account and exports their ratings.
import { apiFetch, apiJson } from './api.js';

const send = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
const path = id => '/evaluations/' + encodeURIComponent(id);

export const listCampaigns = () => apiJson('/evaluations', {}, 'No se pudieron cargar las campañas.');
export const getCampaign = id => apiJson(path(id), {}, 'No se pudo abrir la campaña.');
export const createCampaign = campaign => apiJson('/evaluations', send('POST', campaign), 'No se pudo crear la campaña.');
export const removePassage = (id, passageId) => apiJson(path(id) + '/passages/' + encodeURIComponent(passageId),
  { method: 'DELETE' }, 'No se pudo quitar el pasaje.');
export const setInvitations = (id, emails) => apiJson(path(id) + '/invitations', send('PUT', { emails }),
  'No se pudieron guardar las invitaciones.');
export const setCampaignStatus = (id, status) => apiJson(path(id) + '/status', send('POST', { status }),
  'No se pudo cambiar el estado de la campaña.');

// The results with the prediction and anonymous evaluators, saved as a JSON file for step 19.
export async function exportCampaign(campaign) {
  const response = await apiFetch(path(campaign.id) + '/export');
  if (!response.ok) throw new Error('No se pudieron exportar los resultados.');
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
export const statusLabel = status => STATUSES[status] || status;

// What ScoreLint predicted for the passage: only the director sees it, never the musicians.
export const predictionText = snapshot => 'Grado ' + snapshot.grade + (snapshot.critical ? ' · crítico' : '');

export function invitationProgress(invitation, total) {
  if (!invitation.rated && !invitation.profile_done) return 'Aún no ha empezado';
  if (invitation.rated >= total) return 'Ha valorado todos los pasajes';
  return invitation.rated + ' de ' + total + ' pasajes';
}

const count = (value, one, many) => value + ' ' + (value === 1 ? one : many);

export function campaignSummary(campaign) {
  const passages = campaign.passages || [];
  return [count(passages.length, 'pasaje', 'pasajes'),
    count(passages.filter(item => item.snapshot?.critical).length, 'crítico', 'críticos') + ' según ScoreLint',
    count((campaign.invitations || []).length, 'músico invitado', 'músicos invitados')].join(' · ');
}

export function shortfallText(requested, proposed) {
  if (proposed >= requested) return '';
  return 'Se han propuesto ' + proposed + ' de los ' + requested + ' pasajes pedidos: las obras elegidas no dan para más. '
    + 'Añade obras si necesitas más.';
}
