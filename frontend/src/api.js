import { currentLanguage, t } from './i18n.js';

// Requests to the API with the session cookie. State-changing requests carry the session's CSRF
// token; a 401 tells the app that the session ended. Every request names the language of the interface, in which the
// server answers its messages (2026-10-30).
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);
let csrfToken = '';
const unauthorizedListeners = new Set();

export function onUnauthorized(listener) {
  unauthorizedListeners.add(listener);
  return () => unauthorizedListeners.delete(listener);
}

export async function apiFetch(url, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const headers = new Headers(options.headers || {});
  headers.set('Accept-Language', currentLanguage());
  if (!SAFE_METHODS.has(method) && csrfToken) headers.set('X-CSRF-Token', csrfToken);
  const response = await fetch(url, { ...options, headers, credentials: 'same-origin' });
  if (response.status === 401) unauthorizedListeners.forEach(listener => listener());
  return response;
}

async function detail(response, fallback) {
  try { const body = await response.json(); return typeof body.detail === 'string' ? body.detail : fallback; }
  catch { return fallback; }
}

// JSON request to the API; an error carries the server's message, or the fallback.
export async function apiJson(url, options, fallback) {
  const response = await apiFetch(url, options);
  if (!response.ok) throw new Error(await detail(response, fallback));
  return response.status === 204 ? null : response.json();
}

async function postJson(url, body, fallback) {
  const response = await fetch(url, { method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'Accept-Language': currentLanguage() }, body: JSON.stringify(body) });
  if (!response.ok) throw new Error(await detail(response, fallback));
  const data = await response.json();
  csrfToken = data.csrf_token || '';
  return data.user;
}

export const signIn = (email, password) => postJson('/auth/login', { email, password }, t('No se pudo iniciar sesión.'));

export const register = (email, password, displayName) =>
  postJson('/auth/register', { email, password, display_name: displayName }, t('No se pudo crear la cuenta.'));

// Password recovery: the link in the email is /#reset=<token>; the fragment never reaches a server.
export const resetTokenFrom = hash => (/^#reset=([\w-]+)$/.exec(hash || '') || [])[1] || '';

export async function requestPasswordReset(email) {
  const response = await fetch('/auth/password/forgot', { method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'Accept-Language': currentLanguage() }, body: JSON.stringify({ email }) });
  if (!response.ok) throw new Error(await detail(response, t('No se pudo pedir el enlace.')));
  return (await response.json()).detail;
}

// Email confirmation (2026-10-30): the link in the email is /#verify=<token>; it confirms with or without a session.
export const verifyTokenFrom = hash => (/^#verify=([\w-]+)$/.exec(hash || '') || [])[1] || '';

export async function verifyEmail(token) {
  const response = await fetch('/auth/email/verify', { method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'Accept-Language': currentLanguage() }, body: JSON.stringify({ token }) });
  if (!response.ok) throw new Error(await detail(response, t('No se pudo confirmar el email.')));
  return (await response.json()).email_verified;
}

export const resendVerification = async () => (await apiJson('/auth/email/resend', { method: 'POST' },
  t('No se pudo enviar otro enlace.'))).detail;

export const resetPassword = (token, password) =>
  postJson('/auth/password/reset', { token, password }, t('No se pudo cambiar la contraseña.'));

export async function currentUser() {
  const response = await fetch('/auth/me', { credentials: 'same-origin' });
  if (!response.ok) { csrfToken = ''; return null; }
  const data = await response.json();
  csrfToken = data.csrf_token || '';
  return data.user;
}

export async function signOut() {
  try { await apiFetch('/auth/logout', { method: 'POST' }); }
  finally { csrfToken = ''; }
}

export async function authConfig() {
  try { const response = await fetch('/auth/config'); return response.ok ? await response.json() : {}; }
  catch { return {}; }
}
