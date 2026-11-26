// Captures everything the page plays through Web Audio into one recording, with its start time.
export const tapScript = () => {
  // Inside the YouTube player frame: record the sound of the <video> element itself.
  if (/(^|\.)youtube(-nocookie)?\.com$/.test(location.hostname)) {
    window.__audio = { chunks: [], start: null };
    const hook = (v) => {
      if (window.__audio.rec || !(v instanceof HTMLMediaElement)) return;
      const s = v.captureStream ? v.captureStream() : null; const tr = s ? s.getAudioTracks() : [];
      if (!tr.length) { setTimeout(() => hook(v), 500); return; }
      const rec = new MediaRecorder(new MediaStream(tr), { mimeType: 'audio/webm;codecs=opus', audioBitsPerSecond: 160000 });
      rec.ondataavailable = (e) => { if (e.data.size) window.__audio.chunks.push(e.data); };
      rec.onstart = () => { window.__audio.start = Date.now(); };
      rec.start(1000); window.__audio.rec = rec;
    };
    document.addEventListener('playing', (e) => hook(e.target), true);
    return;
  }
  const orig = AudioNode.prototype.connect;
  window.__audio = { chunks: [], start: null };
  const ensure = (ctx) => {
    if (ctx.__tap) return ctx.__tap;
    ctx.__tap = ctx.createMediaStreamDestination();
    const rec = new MediaRecorder(ctx.__tap.stream, { mimeType: 'audio/webm;codecs=opus', audioBitsPerSecond: 160000 });
    rec.ondataavailable = (e) => { if (e.data.size) window.__audio.chunks.push(e.data); };
    rec.onstart = () => { window.__audio.start = Date.now(); };
    rec.start(1000); window.__audio.rec = rec;
    return ctx.__tap;
  };
  AudioNode.prototype.connect = function (target, ...rest) {
    const r = orig.call(this, target, ...rest);
    try { if (target && target === this.context.destination) orig.call(this, ensure(this.context)); } catch (e) {}
    return r;
  };
};
export async function exportAudio(p, file, fs) {
  const info = await p.evaluate(async () => {
    const a = window.__audio; if (!a || !a.rec) return null;
    await new Promise(r => { a.rec.onstop = r; a.rec.stop(); });
    a.blob = new Blob(a.chunks, { type: 'audio/webm' }); return { start: a.start, size: a.blob.size };
  });
  if (!info) return null;
  const parts = [];
  for (let off = 0; off < info.size; off += 4 * 1024 * 1024) {
    parts.push(Buffer.from(await p.evaluate(async ([o]) => {
      const b = await window.__audio.blob.slice(o, o + 4 * 1024 * 1024).arrayBuffer();
      let s = ''; const u = new Uint8Array(b); for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode(...u.subarray(i, i + 0x8000));
      return btoa(s);
    }, [off]), 'base64'));
  }
  fs.writeFileSync(file, Buffer.concat(parts));
  return info;
}
