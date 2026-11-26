// Human-paced helpers: visible cursor, curved eased mouse paths, key-by-key typing, marks.
export const W = +(process.env.VW || 1600), H = +(process.env.VH || 900);

export const cursorScript = () => {
  const init = () => {
    if (document.getElementById('pw-cursor')) return;
    const s = document.createElement('style');
    s.textContent = `#pw-cursor{position:fixed;z-index:2147483647;pointer-events:none;width:24px;height:24px;margin:-2px 0 0 -4px;transition:transform .08s}
#pw-cursor svg{filter:drop-shadow(0 1px 2px rgba(0,0,0,.45))}#pw-cursor.down{transform:scale(.85)}
.pw-ripple{position:fixed;z-index:2147483646;pointer-events:none;width:38px;height:38px;margin:-19px 0 0 -19px;border-radius:50%;background:rgba(196,72,38,.32);animation:pwr .5s ease-out forwards}
@keyframes pwr{from{transform:scale(.3);opacity:1}to{transform:scale(1.4);opacity:0}}`;
    document.head.appendChild(s);
    const d = document.createElement('div'); d.id = 'pw-cursor';
    d.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24"><path d="M4 2l0 17 4.6-4.4 3.2 7 2.6-1.2-3.1-6.8 6.4-.2z" fill="#111" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/></svg>';
    const st = window.__pwPos || { x: -60, y: -60 };
    d.style.left = st.x + 'px'; d.style.top = st.y + 'px';
    document.documentElement.appendChild(d);
    addEventListener('mousemove', e => { d.style.left = e.clientX + 'px'; d.style.top = e.clientY + 'px'; window.__pwPos = { x: e.clientX, y: e.clientY }; }, true);
    addEventListener('mousedown', e => { d.classList.add('down'); const r = document.createElement('div'); r.className = 'pw-ripple'; r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px'; document.documentElement.appendChild(r); setTimeout(() => r.remove(), 600); }, true);
    addEventListener('mouseup', () => d.classList.remove('down'), true);
  };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', init); else init();
};

export function makeHuman(p, t0, marks, prefix = '') {
  const PACE = +(process.env.PACE || 1);
  const wait = (ms) => p.waitForTimeout(ms >= 600 ? ms * PACE : ms);
  const rnd = (a, b) => a + Math.random() * (b - a);
  let mx = W * 0.55, my = H * 0.6;
  const ease = (t) => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  async function moveTo(x, y, ms) {
    const dist = Math.hypot(x - mx, y - my);
    if (dist < 2) return;
    ms = ms ?? Math.min(1100, 280 + dist * 0.7);
    const steps = Math.max(8, Math.round(ms / 16));
    // control point offset perpendicular to path for a natural curve
    const cx = (mx + x) / 2 + rnd(-0.18, 0.18) * (y - my), cy = (my + y) / 2 + rnd(-0.18, 0.18) * (mx - x);
    const sx = mx, sy = my;
    for (let i = 1; i <= steps; i++) {
      const t = ease(i / steps), u = 1 - t;
      const px = u * u * sx + 2 * u * t * cx + t * t * x, py = u * u * sy + 2 * u * t * cy + t * t * y;
      await p.mouse.move(px, py); await wait(14);
    }
    mx = x; my = y;
  }
  const L = (loc) => typeof loc === 'string' ? p.locator(loc).first() : loc;
  async function box(loc) {
    const el = L(loc); await el.waitFor({ state: 'visible', timeout: +(process.env.VIS_TIMEOUT || 20000) });
    await el.scrollIntoViewIfNeeded(); await wait(250);
    let bb = await el.boundingBox();
    // Keep clear of the sticky header and the bottom edge.
    if (bb && (bb.y < 90 || bb.y + Math.min(bb.height, 60) > H - 20)) {
      await el.evaluate(e => e.scrollIntoView({ block: 'center', behavior: 'smooth' })); await wait(700); bb = await el.boundingBox();
    }
    return bb;
  }
  async function hover(loc, pause = 700) {
    const b = await box(loc);
    await moveTo(b.x + b.width * rnd(0.4, 0.6), b.y + b.height * rnd(0.4, 0.6)); await wait(pause);
  }
  async function click(loc, pause = 900) {
    await hover(loc, rnd(180, 380)); await p.mouse.down(); await wait(rnd(60, 110)); await p.mouse.up(); await wait(pause);
  }
  async function typeText(text) {
    for (const ch of text) {
      await p.keyboard.type(ch);
      let d = rnd(55, 140); if (ch === ' ') d += rnd(30, 90); if (/[.,?¿@]/.test(ch)) d += rnd(80, 200);
      await wait(d);
    }
  }
  async function type(loc, text) { await click(loc, 250); await typeText(text); await wait(350); }
  async function scroll(dy, ms = 900) {
    const steps = Math.max(6, Math.round(ms / 50));
    for (let i = 0; i < steps; i++) { await p.mouse.wheel(0, dy / steps); await wait(50); }
    await wait(500);
  }
  async function drift(pause = 1200) { // small idle movement, like a hand on the mouse
    await moveTo(Math.min(W - 30, Math.max(30, mx + rnd(-90, 90))), Math.min(H - 30, Math.max(60, my + rnd(-50, 50))), rnd(500, 900)); await wait(pause);
  }
  const mark = (title) => { const t = (Date.now() - t0()) / 1000; marks.push({ t, title: prefix + title }); console.log(t.toFixed(1), prefix + title); };
  return { wait, moveTo, hover, click, typeText, type, scroll, drift, mark, rnd, get pos() { return { mx, my }; } };
}
