import { apiFetch } from '../api.js';
import { t } from '../i18n.js';

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
      if (!file) return Promise.reject(new Error(t('Vuelve a subir la partitura para abrir este pasaje.')));
      if (!source && typeof file.arrayBuffer === 'function') {
        // An uncompressed MusicXML is read here (2026-10-28): asking the server waited behind the audio preparation on
        // Render's free plan. A zip (.mxl, «PK») still goes to the server, which decompresses it.
        const pending = file.arrayBuffer().then(bytes => {
          const head = new Uint8Array(bytes, 0, Math.min(2, bytes.byteLength));
          return head[0] === 0x50 && head[1] === 0x4b ? fromServer() : new TextDecoder().decode(bytes);
        });
        pending.catch(() => { if (source === pending) source = null; });
        source = pending;
      }
      if (!source) source = fromServer();
      return source;
    },
  };

  // The server decompresses a .mxl; a failed download may be retried on the next request.
  function fromServer() {
    const payload = new FormData();
    payload.append('file', file);
    const pending = request('/notation-source', { method: 'POST', body: payload }).then(response => {
      if (!response.ok) throw new Error(t('No se pudo recuperar la partitura original.'));
      return response.text();
    });
    pending.catch(() => { if (source === pending) source = null; });
    return pending;
  }
}
