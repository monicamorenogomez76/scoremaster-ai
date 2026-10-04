import { apiFetch } from '../api.js';

// Score selected in this browser session and its MusicXML, fetched at most once per file.
// The server decompresses .mxl files; the original never leaves this origin.
export function createScoreSession(request = (...args) => apiFetch(...args)) {
  let file = null, source = null, version = 0;
  return {
    getFile: () => file,
    // Changes whenever the selected score changes, so late results can be discarded.
    getVersion: () => version,
    setFile(next, knownSource = null) {
      if (knownSource) source = Promise.resolve(knownSource);
      else if (next !== file) source = null;
      file = next; version++;
    },
    clear() { file = null; source = null; version++; },
    loadSource() {
      if (!file) return Promise.reject(new Error('Vuelve a subir la partitura para abrir este pasaje.'));
      if (!source) {
        const payload = new FormData();
        payload.append('file', file);
        const pending = request('/notation-source', { method: 'POST', body: payload }).then(response => {
          if (!response.ok) throw new Error('No se pudo recuperar la partitura original.');
          return response.text();
        });
        // A failed download may be retried on the next request.
        pending.catch(() => { if (source === pending) source = null; });
        source = pending;
      }
      return source;
    },
  };
}
