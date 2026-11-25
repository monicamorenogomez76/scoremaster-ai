import test from 'node:test';
import assert from 'node:assert/strict';
import { allowYouTube, noticeSeen, policy, seeNotice, youTubeAllowed } from '../../../frontend/src/privacy.js';
import { VIEW } from '../../../frontend/src/privacy.js';

const memory = () => { const kept = {}; return { getItem: key => kept[key] ?? null, setItem(key, value) { kept[key] = String(value); }, removeItem(key) { delete kept[key]; } }; };
const closed = { getItem() { throw new Error('closed'); }, setItem() { throw new Error('closed'); }, removeItem() { throw new Error('closed'); } };

test('the cookie notice is shown until it is read, and again when it changes', () => {
  const storage = memory();
  assert.equal(noticeSeen(storage), false);
  seeNotice(storage);
  assert.equal(noticeSeen(storage), true);
  storage.setItem('scoremaster.cookie-notice', '2020-01-01');
  assert.equal(noticeSeen(storage), false);
  assert.equal(noticeSeen(closed), false);
  seeNotice(closed);
});

test('YouTube is asked for nothing until it is allowed, and that can be taken back', () => {
  const storage = memory();
  assert.equal(youTubeAllowed(storage), false);
  allowYouTube(true, storage);
  assert.equal(youTubeAllowed(storage), true);
  allowYouTube(false, storage);
  assert.equal(youTubeAllowed(storage), false);
  assert.equal(youTubeAllowed(closed), false);
});

test('the policy names the controller and its contact, or says that they are missing', () => {
  const text = value => JSON.stringify(policy(value));
  assert.match(text({ controller: 'Banda de prueba', email: 'datos@banda.test' }), /Banda de prueba.*datos@banda\.test/);
  assert.match(text({}), /todavía no se han publicado/);
  assert.match(text(undefined), /todavía no se han publicado/);
});

test('the policy tells every cookie and the sites of the playback and the videos', () => {
  const text = JSON.stringify(policy({}));
  for (const said of ['scoremaster_session', 'scoremaster_oauth', 'jsDelivr', 'gleitz.github.io', 'YouTube', 'Render', 'Neon', 'Brevo', 'GitHub', 'Gemini', 'Agencia Española de Protección de Datos']) {
    assert.ok(text.includes(said), said);
  }
  assert.equal(VIEW, '#privacidad');
});
