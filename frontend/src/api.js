// Requests to the API with the session cookie. State-changing requests carry the session's CSRF
// token; a 401 tells the app that the session ended.
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
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!response.ok) throw new Error(await detail(response, fallback));
  const data = await response.json();
  csrfToken = data.csrf_token || '';
  return data.user;
}

export const signIn = (email, password) => postJson('/auth/login', { email, password }, 'No se pudo iniciar sesión.');

export const register = (email, password, displayName) =>
  postJson('/auth/register', { email, password, display_name: displayName }, 'No se pudo crear la cuenta.');

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
