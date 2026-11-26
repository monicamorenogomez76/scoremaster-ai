// Records the live demo of the web app on Render with Mónica's account, human-paced.
import { chromium } from 'playwright';
import fs from 'node:fs';
const C = await import(process.env.CREDS || './creds.mjs');
const BASE = process.env.BASE || C.BASE, EMAIL = C.EMAIL, PASS = C.PASS;
import { W, H, cursorScript, makeHuman } from './human.mjs';
import { tapScript, exportAudio } from './audiotap.mjs';
const OUT = process.env.OUT || '/tmp/claude-0/out'; fs.mkdirSync(OUT, { recursive: true });
const PASODOBLE = process.env.PASODOBLE || '/home/user/scoremaster-ai/demo/para-subir/pasodoble-de-las-fiestas.mxl';
const WORK = /^1812/i;

const b = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'], ...(process.env.CHANNEL ? { channel: process.env.CHANNEL } : {}) });
const c = await b.newContext({ viewport: { width: W, height: H }, locale: 'es-ES', timezoneId: 'Europe/Madrid',
  recordVideo: { dir: `${OUT}/raw-web`, size: { width: W, height: H } } });
await c.addInitScript(cursorScript); await c.addInitScript(tapScript);
const p = await c.newPage(); const start = Date.now(); const marks = [];
p.on('console', m => m.type() === 'error' && console.log('CONSOLE', m.text().slice(0, 160)));
const h = makeHuman(p, () => start, marks);
const { wait, typeText, scroll, drift, moveTo } = h;
const soft = (fn, name) => async (...a) => { try { return await fn(...a); } catch (e) { console.log('  skip', name, String(a[0]).slice(0, 60), e.message.split('\n')[0].slice(0, 80)); } };
const hover = soft(h.hover, 'hover'), click = soft(h.click, 'click'), type = soft(h.type, 'type');
const fails = [];
const scene = async (title, fn) => { h.mark(title); try { await fn(); } catch (e) { fails.push(title); console.log('SCENE FAIL', title, e.message.split('\n')[0]); } await p.screenshot({ path: `${OUT}/web-${marks.length}.png` }); };
const nav = (v) => click(`[data-view-target="${v}"]`, 1800);
const top = () => p.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' })).then(() => wait(900));
const btn = (name, exact = true) => p.getByRole('button', { name, exact }).locator('visible=true').first();
const vis = (sel) => p.locator(sel).locator('visible=true').first();
const exists = async (loc) => (await loc.count()) > 0 && await loc.isVisible().catch(() => false);
// Wait for a condition while the hand idles on the mouse.
const cuts = []; let ytFrame = null;
const now = () => (Date.now() - start) / 1000;
async function idleUntil(fn, timeout = 90000, arg) {
  const t1 = now(); const end = Date.now() + timeout; let ok = false;
  while (Date.now() < end) { if (await p.evaluate(fn, arg).catch(() => false)) { ok = true; break; } await drift(700); }
  const t2 = now(); if (t2 - t1 > 9) cuts.push({ from: +(t1 + 3.5).toFixed(2), to: +(t2 - 2).toFixed(2) });
  return ok;
}
const closeDialog = async () => { const x = p.locator('#notation-close'); if (await exists(x)) await click(x, 1500); };
const textGone = (t) => idleUntil((s) => !document.body.innerText.includes(s), 120000, t);
// Waits until every AI answer on screen has arrived: no progress bar, no "…ing" button.
const aiDone = async (timeout = 150000) => { await p.waitForTimeout(1500); return idleUntil(() => {
  const main = document.querySelector('main'); if (!main) return false;
  if ([...main.querySelectorAll('.activity-status')].some(e => e.offsetParent)) return false;
  if (/Redactando el comentario…|Buscando sustitutos…/.test(main.innerText)) return false;
  return [...main.querySelectorAll('.work-question-item')].filter(e => e.offsetParent).every(i => i.querySelector('.work-question-answer, [role=alert]'));
}, timeout).then(async r => { await p.waitForTimeout(3000); return r; }); };

// ---------- 1. Acceso
await scene('Web · Acceso con tu cuenta', async () => {
  await p.goto(BASE + '/'); await p.waitForSelector('#login-email', { timeout: 120000 }); await wait(2200);
  await type('#login-email', EMAIL); await click('#login-password', 250); await typeText(PASS); await wait(500);
  await click('#login-submit', 1500);
  await p.waitForSelector('[data-view-target="summary"]', { timeout: 60000 }); await wait(1500);
  const ok = btn('Entendido'); if (await exists(ok)) await click(ok, 1000);
});

// ---------- 2. Resumen
await scene('Web · Resumen', async () => {
  await hover('main h1, main h2', 1500);
  await hover(btn('Ver conciertos'), 1500);
  await hover('#summary-rehearsal-title', 1800);
  const blocks = p.locator('main .calendar-block').locator('visible=true');
  for (const i of [0, 2, 5]) if (await blocks.nth(i).count()) await hover(blocks.nth(i), 1400);
  if (await exists(btn('Revisar ensayo'))) await hover(btn('Revisar ensayo'), 1500);
  await hover('#summary-priorities-title', 2000);
  await scroll(420); await hover('#summary-plan-title', 2500);
  await hover('#summary-coverage-title', 2500);
  await scroll(380); await hover('#summary-works-title', 2500);
  await top();
});

// ---------- 3. Repertorio y preguntar al repertorio
await scene('Web · Repertorio', async () => {
  await nav('repertoire'); await wait(800);
  const titles = p.locator('main h3.works-title');
  for (let i = 0; i < Math.min(4, await titles.count()); i++) await hover(titles.nth(i), 1100);
  await hover(p.locator('main select').locator('visible=true').first(), 1500);
  await click('#works-search', 300); await typeText(process.env.SEARCH || '1812'); await wait(1800);
  await p.fill('#works-search', ''); await wait(800);
});
await scene('Web · Preguntar al repertorio', async () => {
  const sum = p.locator('summary', { hasText: 'Preguntar al repertorio' });
  const box = p.locator('details', { has: sum });
  if (!(await box.getAttribute('open').catch(() => null) !== null)) await click(sum, 1200);
  await click(btn('¿Cuáles son las obras más difíciles?'), 500);
  await aiDone();
  await wait(3500);
  await type(box.locator('textarea'), '¿Qué obras de grado 4 puede tocar ya mi banda?');
  await click(box.getByRole('button', { name: 'Preguntar', exact: true }), 500);
  await aiDone();
  await wait(1500); await scroll(250); await wait(4000);
  await click(sum, 1000); await top();
});

// ---------- 4. 1812: partitura
if (await p.locator('h3.works-title', { hasText: WORK }).count()) await scene('Web · Abrir 1812 · partitura leída de PDF', async () => {
  const row = p.locator('h3.works-title', { hasText: WORK }).first().locator('xpath=ancestor::*[.//button[normalize-space()="Abrir"]][1]');
  await click(row.getByRole('button', { name: 'Abrir' }), 1500);
  await idleUntil(() => /compases \d+–\d+$/.test(document.querySelector('#full-score-status')?.textContent?.trim() || ''), 120000);
  await hover('#work-detail-title', 1500);
  await hover(p.locator('main').getByText(/Leída de PDF/).first(), 3000);
  const corr = p.locator('summary', { hasText: 'Corregir notas' });
  await click(corr, 2500); await hover(corr, 800); await click(corr, 800);
  await hover(p.locator('label', { hasText: 'Comparar con un PDF' }), 2500);
});
if (process.env.MAIN2) await scene('Web · Abrir Persis Overture', async () => {
  await top(); await click('#back-to-list', 1500);
  const row = p.locator('h3.works-title', { hasText: /^Persis Overture$/ }).locator('xpath=ancestor::*[.//button[normalize-space()="Abrir"]][1]');
  await hover(row, 1500); await click(row.getByRole('button', { name: 'Abrir' }), 1500);
  await idleUntil(() => /compases \d+–\d+$/.test(document.querySelector('#full-score-status')?.textContent?.trim() || ''), 120000);
  await hover('#work-detail-title', 1500);
});
await scene('Web · Reproducir la partitura', async () => {
  await scroll(520); await wait(800);
  await click('#ensemble-play', 500);
  await idleUntil(() => /Reproduciendo/.test(document.querySelector('#ensemble-status')?.textContent || ''), 300000);
  const r = await p.locator('#full-score-rendering').boundingBox();
  await moveTo(r.x + r.width * 0.6, r.y + 220); await p.waitForTimeout(9000); await drift(3000); await p.waitForTimeout(3000);
  await click('#ensemble-stop', 1500);
});
await scene('Web · Navegar por la partitura', async () => {
  await click('#score-next', 2500); await click('#score-next', 2000); await click('#score-prev', 1800);
  await click('#score-zoom-in', 1800); await click('#score-zoom-in', 1800); await click('#score-fit', 2000);
  const sel = p.locator('#score-measures'); await click(sel, 400); await sel.selectOption('4'); await p.keyboard.press('Escape').catch(() => {}); await wait(3500);
  await sel.selectOption({ index: 0 }); await wait(2500);
  await type('#score-go-to', '120'); await click(btn('Ir'), 3500);
});
await scene('Web · El mapa de la obra sobre la partitura', async () => {
  await click('#score-analysis-toggle', 1000);
  await idleUntil(() => !!document.querySelector('#full-score-rendering .score-map-lane'), 300000);
  await p.locator('#full-score-rendering .score-map').first().evaluate(e => e.scrollIntoView({ block: 'start', behavior: 'smooth' })).catch(() => {}); await p.evaluate(() => window.scrollBy(0, -120));
  await p.waitForTimeout(1500); const r = await p.locator('#full-score-rendering .score-map').first().boundingBox();
  await moveTo(r.x + 300, r.y + 20); await p.waitForTimeout(2500); await moveTo(r.x + 800, r.y + 60); await p.waitForTimeout(2500); await moveTo(r.x + 500, r.y + r.height - 15); await p.waitForTimeout(2500);
  await click('#score-next', 1000); await p.waitForTimeout(3500);
  await click('#score-analysis-toggle', 1500);
  if (await p.locator('#score-analysis-toggle[aria-pressed="true"]').count()) await p.click('#score-analysis-toggle');
});
await scene('Web · Editar notas sobre la partitura', async () => {
  await click('#score-edit-toggle', 1500);
  await hover('#score-edit-help', 3500);
  await click('#score-zoom-in', 1200); await click('#score-zoom-in', 1500);
  await p.locator('#full-score-rendering').evaluate(e => { const y = e.getBoundingClientRect().top + window.scrollY - 80; window.scrollTo({ top: y, behavior: 'smooth' }); }); await wait(1200);
  const notes = p.locator('#full-score-rendering g.score-note');
  const n = await notes.count(); let target = null;
  for (let i = 0; i < n; i++) { const bb = await notes.nth(i).boundingBox(); if (bb && bb.height > 10 && bb.y > 200 && bb.y < 820 && bb.x > 300 && bb.x < 1450) { target = notes.nth(i); break; } }
  console.log('  edit target', !!target, n);
  if (target) {
    await click(target, 1500);
    await p.keyboard.press('ArrowUp'); await wait(1300); await p.keyboard.press('ArrowUp'); await wait(1500);
    await p.keyboard.press('ArrowRight'); await wait(1200); await p.keyboard.press('Shift+ArrowDown'); await wait(1500);
    await hover('.score-edit-count', 2500);
    await click(btn('Descartar'), 1800);
  }
  await click('#score-edit-toggle', 1500);
  if (await p.locator('#score-edit-toggle[aria-pressed="true"]').count()) await p.click('#score-edit-toggle');
  await click('#score-fit', 1500);
});
await top();

// ---------- 5. Dificultad
await scene('Web · Dificultad (ScoreLint)', async () => {
  await click('#work-tab-difficulty', 2500);
  await hover('#work-explanation-title', 1200);
  await hover('#grade-reasons-title', 1500); await scroll(350); await wait(3500);
  await hover(p.getByText('Dónde concentrar el ensayo'), 2500);
  await hover('#overview-priority-title', 2500);
  await scroll(-350); await wait(500);
});
await scene('Web · Explicar la dificultad (IA)', async () => {
  await click(btn(/Explicar la dificultad|Volver a explicar/, false), 800);
  await aiDone(); await idleUntil(() => !!document.querySelector('#explanation-source'), 60000);
  await wait(1200); await hover('#explanation-source', 3500);
  await scroll(250); await wait(5000);
  const cite = p.locator('#work-explanation .passage-open').first();
  if (await exists(cite)) { await click(cite, 3000); await idleUntil(() => !!document.querySelector('#notation-dialog[open] svg'), 60000); await wait(2500);
    const play = p.locator('#notation-dialog button[id$="-play"]').first(); if (await exists(play)) { await click(play, 500); await idleUntil(() => /Reproduciendo/.test(document.querySelector('#notation-dialog')?.innerText || ''), 30000); await p.waitForTimeout(8000); }
    await closeDialog(); }
});
await scene('Web · De la familia al instrumento y al pasaje', async () => {
  const fam = p.locator('#difficulty-content .tree-node').first();
  await fam.scrollIntoViewIfNeeded(); await wait(600); await hover(fam, 1500); await click(fam, 2500);
  const inst = p.locator('#difficulty-content .tree-node').nth(1); if (await exists(inst)) await click(inst, 2500);
  await scroll(300); await wait(2000);
  const open = p.locator('#difficulty-content .passage-open').first();
  if (await exists(open)) { await click(open, 3000); await wait(4000); await closeDialog(); }
});
await scene('Web · Grado publicado por la editorial', async () => {
  await hover('#published-grades-title', 2000);
  const form = p.locator('section, div', { has: p.locator('#published-grades-title') }).last();
  await hover(p.getByLabel('Escala').first(), 1200).catch(() => {});
  await hover(p.getByLabel('Editorial o catálogo').first(), 1500).catch(() => {});
  await hover(btn('Añadir grado'), 2000);
  await top();
});

// ---------- 6. Análisis musical
await scene('Web · Análisis musical', async () => {
  await click('#work-tab-analysis', 1500);
  await textGone('Analizando la obra');
  await wait(1200); await hover('#analysis-general', 2500);
  await scroll(380); await hover('#work-map-title', 2500);
  const secs = p.locator('.work-map-section');
  for (const i of [1, 3]) if (await secs.nth(i).count()) await click(secs.nth(i), 3000);
  await hover('#section-sheet-title', 2000); await scroll(400); await wait(3500);
  await click(btn('Siguiente →'), 3000);
  const tbl = p.locator('summary', { hasText: 'Ver los datos en tabla' }); if (await exists(tbl)) { await click(tbl, 2500); await scroll(500); await wait(3000); await click(tbl, 800); }
  await top();
  const red = btn('Redactar el comentario'); if (await exists(red)) { await click(red, 1000); await aiDone(240000); await wait(2500); await scroll(400); await wait(4000); }
  await top();
});

// ---------- 7. Preguntar a la obra
await scene('Web · Preguntar a la obra', async () => {
  await click('#work-tab-questions', 1800);
  await click(btn('¿Qué forma tiene?'), 800);
  await aiDone(); await wait(4000);
  await type(p.locator('main textarea').locator('visible=true').first(), '¿Qué tiene que preparar la trompeta?');
  await click(p.locator('main').getByRole('button', { name: 'Preguntar', exact: true }).locator('visible=true').first(), 800);
  await aiDone();
  await wait(1500); await scroll(350); await wait(5000); await top();
});

// ---------- 8. Grabaciones
await scene('Web · Grabaciones en YouTube', async () => {
  await click('#work-tab-recordings', 2000);
  const q = p.locator('.video-search-form input[type=search]');
  await click(q, 300); await p.keyboard.press('Control+A'); await typeText(process.env.MAIN2 ? 'Persis Hosay' : '1812 Overture Tchaikovsky concert band'); await wait(500);
  await click(btn('Buscar'), 500);
  await idleUntil(() => document.querySelectorAll('.video-result').length > 0 || /No se encontr|no está configurada/i.test(document.body.innerText), 30000); await wait(1500);
  const res = p.locator('.video-result'); const n = await res.count();
  for (let i = 0; i < Math.min(3, n); i++) await hover(res.nth(i), 1100);
  if (n) await click(res.nth(+(process.env.YT_PICK || 0)), 1500);
  const allow = btn('Permitir vídeos de YouTube'); if (await exists(allow)) await click(allow, 2500);
  const ifr = p.locator('.video-player iframe');
  if (await exists(ifr)) {
    await ifr.evaluate(e => e.scrollIntoView({ block: 'center', behavior: 'smooth' })); await wait(4000);
    const r = await ifr.boundingBox(); await moveTo(r.x + r.width / 2, r.y + r.height / 2); await p.mouse.click(r.x + r.width / 2, r.y + r.height / 2);
    await p.waitForTimeout(+(process.env.YT_SECS || 22) * 1000);
    await p.mouse.click(r.x + r.width / 2, r.y + r.height / 2); await wait(1500);
    ytFrame = p.frames().find(f => /youtube/.test(f.url())) || null;
  }
  await wait(1500); await top();
});

// ---------- 9. Mi banda
await scene('Web · Mi banda (BandFit)', async () => {
  await nav('band'); await wait(1000);
  await hover('#band-manager-title', 1500);
  await click(btn('Editar banda'), 2500); await scroll(400); await wait(2500);
  const cancel = btn('Cancelar'); if (await exists(cancel)) await click(cancel, 1500);
  await top();
  await hover(p.getByText('Adecuación de la obra abierta'), 2000);
  const rows = p.locator('.band-profile-row'); for (const i of [0, 4, 10, 16]) if (await rows.nth(i).count()) await hover(rows.nth(i), 1100);
  await hover('#update-analysis', 1500);
  await hover(p.locator('.result-metric').locator('visible=true').first(), 3000);
  const subs = btn('Proponer sustitutos'); if (await exists(subs)) { await click(subs, 1000); await aiDone(); await wait(1500); await scroll(400); await wait(5000); }
  await top();
});

// ---------- 10. Conciertos
await scene('Web · Conciertos y planificación', async () => {
  await nav('concerts'); await wait(1000);
  await hover('#concerts-upcoming-title', 2000);
  await click(btn('Planificación'), 3000);
  await hover('#concert-planning-title', 1500);
  const cb = p.locator('main .calendar-block').locator('visible=true'); for (const i of [0, 5, 10]) if (await cb.nth(i).count()) await hover(cb.nth(i), 1300);
  await hover(btn('Replanificar los ensayos siguientes'), 2500);
  await click(btn('Cerrar'), 1500);
  await hover('#concerts-past-title', 1500);
  await hover('#month-title', 1500); await click(p.locator('button', { hasText: '›' }).first(), 2500); await click(p.locator('button', { hasText: '‹' }).first(), 2000);
  await top();
});

// ---------- 11. Ensayos
await scene('Web · Ensayos', async () => {
  await nav('rehearsal'); await wait(1200);
  await hover('#saved-rehearsals-title', 1500);
  await click(btn('¿Por qué este plan?'), 800);
  await aiDone(); await idleUntil(() => !!document.querySelector('.rehearsal-why .explanation-body, .rehearsal-why [role=alert]'), 60000); await wait(2000); await scroll(300); await wait(5000);
  await hover(btn('Imprimir o PDF'), 2000);
  await hover('#rehearsals-past-title', 1500);
  const rev = btn('Ver revisión'); if (await exists(rev)) { await click(rev, 3000); await scroll(300); await wait(3500); const cancel = btn('Cancelar'); if (await exists(cancel)) await click(cancel, 1500); }
  await top();
});

// ---------- 12. Valoraciones
await scene('Web · Valoraciones (vista de directora)', async () => {
  await nav('evaluation'); await wait(1000);
  await click(btn('Abrir'), 2500);
  await hover('#campaign-summary', 2500);
  await hover(btn('Valorar con IA'), 2500);
  await hover(btn('Exportar resultados'), 1800);
  await hover('#campaign-passages-title', 1500);
  const see = p.locator('button.link-action', { hasText: 'Ver y escuchar' }).first();
  if (await exists(see)) { await click(see, 3000); await idleUntil(() => !!document.querySelector('#notation-dialog[open] svg'), 40000); await wait(3500); await closeDialog(); }
  await hover('#campaign-invitations-title', 2500);
  await click(btn('Cerrar'), 1500); await top();
});

// ---------- 13. Añadir obra
await scene('Web · Añadir una obra (MusicXML o PDF)', async () => {
  await nav('repertoire'); await wait(800);
  await click('#add-work', 2000);
  await hover(p.getByText('Desde un PDF'), 1500);
  const radios = p.locator('label', { hasText: /Detectar solo|Solo partitura general|Solo particellas/ });
  for (let i = 0; i < await radios.count(); i++) await hover(radios.nth(i), 1000);
  await hover(btn('Leer PDF'), 1500);
  await hover('#new-score', 1500);
  const file = p.locator('#file'); await hover(p.locator('label.file-field').first(), 1000);
  if (!process.env.UPLOAD) { await click(p.locator('#add-work'), 1500); return; }
  await file.setInputFiles(PASODOBLE); await wait(1500);
  await click(btn('Subir y analizar'), 800);
  await idleUntil(() => !!document.querySelector('#work-tab-difficulty')?.offsetParent && /Pasodoble/i.test(document.querySelector('#work-detail-title')?.textContent || ''), 300000);
  await wait(2000); await click('#work-tab-difficulty', 3000); await hover('#overview-priority-title', 3000);
  await top();
});

// ---------- 14. Configuración
let initial = null;
await scene('Web · Configuración: idioma, texto, tema e instrumentos', async () => {
  await nav('settings'); await wait(1000);
  initial = await p.evaluate(() => [...document.querySelectorAll('input[type=radio]:checked')].map(i => i.closest('label')?.textContent.trim()));
  const opt = (name, value) => p.locator(`label:has(input[name="${name}"][value="${value}"])`).first();
  const vals = await p.evaluate(() => Object.fromEntries(['language', 'text-size', 'theme'].map(n => [n, [...document.querySelectorAll(`input[name="${n}"]`)].map(i => i.value + (i.checked ? '*' : ''))])));
  console.log('settings values', JSON.stringify(vals));
  const cur = (n) => (vals[n].find(v => v.endsWith('*')) || vals[n][0]).replace('*', '');
  const other = (n, pref) => vals[n].map(v => v.replace('*', '')).find(v => v === pref) || vals[n].map(v => v.replace('*', '')).find(v => v !== cur(n));
  await click(opt('language', other('language', 'en')), 3000); await hover(p.locator('#settings-display-title'), 1500);
  await click(opt('language', cur('language')), 2500);
  await click(opt('text-size', other('text-size', 'large')), 2500); await click(opt('text-size', cur('text-size')), 2000);
  await click(opt('theme', other('theme', 'dark')), 3500); await drift(1500);
  await click(opt('theme', cur('theme')), 2500);
  await scroll(600); await hover('#settings-instruments-title', 1500);
  const s = p.getByLabel('Buscar instrumento o nombre'); await type(s, 'Requinto'); await wait(1500);
  const sum = p.locator('summary', { hasText: 'Requinto' }).first(); if (await exists(sum)) { await click(sum, 3500); await click(sum, 1000); }
  await top(); await drift(1500);
});
h.mark('Web · Fin');
await wait(1500);
if (ytFrame) { const yi = await exportAudio(ytFrame, `${OUT}/web.yt.webm`, fs).catch(e => { console.log('YT AUDIO FAIL', e.message); return null; });
  if (yi) fs.writeFileSync(`${OUT}/web.yt.json`, JSON.stringify({ offset: (yi.start - start) / 1000, size: yi.size })); console.log('yt audio', JSON.stringify(yi)); }
const ainfo = await exportAudio(p, `${OUT}/web.audio.webm`, fs).catch(e => { console.log('AUDIO FAIL', e.message); return null; });
if (ainfo) fs.writeFileSync(`${OUT}/web.audio.json`, JSON.stringify({ offset: (ainfo.start - start) / 1000, size: ainfo.size }));
console.log('audio', JSON.stringify(ainfo));
const v = p.video(); await c.close(); await b.close();
fs.copyFileSync(await v.path(), `${OUT}/web.webm`);
fs.writeFileSync(`${OUT}/web.marks.json`, JSON.stringify(marks, null, 1));
fs.writeFileSync(`${OUT}/web.cuts.json`, JSON.stringify(cuts, null, 1));
console.log('FAILS', JSON.stringify(fails), 'initial settings', JSON.stringify(initial));
