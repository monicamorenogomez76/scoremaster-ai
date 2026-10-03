import { defineConfig } from 'vite';

export default defineConfig({
  base: '/static/frontend/',
  build: {
    outDir: '../backend/app/static/frontend',
    emptyOutDir: true,
  },
});
