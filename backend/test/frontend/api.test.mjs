import assert from 'node:assert/strict';
import test from 'node:test';
import { apiFetch, currentUser, onUnauthorized, signIn, signOut } from '../../../frontend/src/api.js';

function fakeServer(routes) {
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method || 'GET', headers: new Headers(options.headers), body: options.body });
    const [status, body] = routes[url] || [404, { detail: 'No encontrado' }];
    return new Response(status === 204 ? null : JSON.stringify(body), { status });
  };
  return calls;
}

test('signing in keeps the CSRF token and sends it only on state-changing requests', async () => {
  const calls = fakeServer({
    '/auth/login': [200, { user: { email: 'a@b.org', display_name: 'A' }, csrf_token: 'token-1' }],
    '/analyze': [200, {}], '/works': [200, []],
  });
  assert.deepEqual(await signIn('a@b.org', 'secreta-larga'), { email: 'a@b.org', display_name: 'A' });
  assert.equal(calls[0].headers.get('Content-Type'), 'application/json');
  assert.deepEqual(JSON.parse(calls[0].body), { email: 'a@b.org', password: 'secreta-larga' });

  await apiFetch('/analyze', { method: 'POST', body: new FormData() });
  await apiFetch('/works');
  assert.equal(calls[1].headers.get('X-CSRF-Token'), 'token-1');
  assert.equal(calls[2].headers.get('X-CSRF-Token'), null);
});

test('a failed sign in reports the server message', async () => {
  fakeServer({ '/auth/login': [401, { detail: 'Email o contraseña incorrectos.' }] });
  await assert.rejects(signIn('a@b.org', 'mala'), { message: 'Email o contraseña incorrectos.' });
});

test('the current user comes from the session cookie, or nobody', async () => {
  fakeServer({ '/auth/me': [200, { user: { email: 'a@b.org', display_name: 'A' }, csrf_token: 'token-2' }] });
  assert.equal((await currentUser()).email, 'a@b.org');
  fakeServer({ '/auth/me': [401, { detail: 'Inicia sesión para continuar.' }] });
  assert.equal(await currentUser(), null);
});

test('an expired session notifies the app, and signing out forgets the token', async () => {
  const calls = fakeServer({
    '/auth/me': [200, { user: { email: 'a@b.org', display_name: 'A' }, csrf_token: 'token-3' }],
    '/auth/logout': [204, null], '/analyze': [401, { detail: 'Inicia sesión para continuar.' }],
  });
  await currentUser();
  let expired = 0;
  const stop = onUnauthorized(() => { expired += 1; });
  await apiFetch('/analyze', { method: 'POST' });
  assert.equal(expired, 1);
  stop();

  await signOut();
  assert.equal(calls.at(-1).headers.get('X-CSRF-Token'), 'token-3');
  await apiFetch('/analyze', { method: 'POST' });
  assert.equal(calls.at(-1).headers.get('X-CSRF-Token'), null);
});
