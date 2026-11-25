import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';

const root = new URL('../../../frontend/', import.meta.url);
const read = path => readFileSync(new URL(path, root), 'utf8');

// Opening the app asks nothing of other sites (2026-11-25, data protection): its libraries and fonts are its own.
test('the page loads nothing from other sites', () => {
  assert.doesNotMatch(read('index.html'), /https?:\/\//);
});

test('the libraries are the packages pinned in package.json, at the addresses the page uses', async () => {
  const { VENDOR } = await import('../../../frontend/vendor.js');
  const { dependencies } = JSON.parse(read('package.json'));
  for (const { name, file } of VENDOR) {
    assert.match(dependencies[name], /^\d+\.\d+\.\d+$/, name + ' is pinned');
    assert.ok(existsSync(new URL('node_modules/' + name + '/' + file, root)), file);
  }
  const addresses = VENDOR.map(({ address }) => address);
  assert.ok(addresses.some(address => read('index.html').includes('"/static/frontend/' + address + '"')));
  assert.ok(addresses.some(address => read('src/score/playback.js').includes("'/static/frontend/" + address + "'")));
});
