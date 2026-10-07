import assert from 'node:assert/strict';
import test from 'node:test';
import { loadTextSize, saveTextSize, textSizes, updateProfile } from '../../../frontend/src/settings.js';

function storage(values = {}) {
  return { getItem: key => (key in values ? values[key] : null), setItem: (key, value) => { values[key] = String(value); }, values };
}

test('the text size is a preference of this device, with three sizes', () => {
  assert.deepEqual(textSizes.map(([key, label]) => [key, label]), [['normal', 'Normal'], ['large', 'Grande'], ['xlarge', 'Muy grande']]);
  const local = storage();
  assert.equal(loadTextSize(local), 'normal');
  saveTextSize('large', local);
  assert.equal(local.values['scoremaster.text-size'], 'large');
  assert.equal(loadTextSize(local), 'large');
  assert.equal(loadTextSize(storage({ 'scoremaster.text-size': 'enorme' })), 'normal', 'an unknown value falls back');
});

test('a blocked storage never breaks the app', () => {
  const blocked = { getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); } };
  assert.equal(loadTextSize(blocked), 'normal');
  assert.doesNotThrow(() => saveTextSize('large', blocked));
});

test('the visible name is saved in the account', async () => {
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, method: options.method, body: options.body });
    return new Response(JSON.stringify({ user: { email: 'a@b.c', display_name: 'Mónica' } }), { status: 200 });
  };
  assert.deepEqual(await updateProfile('Mónica'), { email: 'a@b.c', display_name: 'Mónica' });
  assert.deepEqual([calls[0].url, calls[0].method, JSON.parse(calls[0].body)], ['/auth/me', 'PATCH', { display_name: 'Mónica' }]);
});
