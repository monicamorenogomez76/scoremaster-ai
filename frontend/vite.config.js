import { readFileSync } from 'node:fs';
import { defineConfig } from 'vite';
import { VENDOR } from './vendor.js';

const vendor = {
  name: 'vendor',
  generateBundle() {
    for (const { name, file, address } of VENDOR) {
      this.emitFile({ type: 'asset', fileName: address, source: readFileSync(new URL('node_modules/' + name + '/' + file, import.meta.url)) });
    }
  },
};

export default defineConfig({
  base: '/static/frontend/',
  plugins: [vendor],
  build: {
    outDir: '../backend/app/static/frontend',
    emptyOutDir: true,
  },
});
