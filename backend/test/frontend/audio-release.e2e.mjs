import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch();
try {
 const page = await browser.newPage();
 if (process.env.SMPLR_MODULE_FILE) await page.route('https://unpkg.com/smplr@1.1.0/dist/index.mjs', r => r.fulfill({ contentType: 'text/javascript', body: readFileSync(process.env.SMPLR_MODULE_FILE, 'utf8') }));
 await page.goto(process.env.SCOREMASTER_URL || 'http://127.0.0.1:8006');
 const result = await page.evaluate(async () => {
  const { Instrument } = await import('https://unpkg.com/smplr@1.1.0/dist/index.mjs');
  async function render(fixed) {
   const ctx = new OfflineAudioContext(1, 24000, 48000);
   const buffer = ctx.createBuffer(1, 48000, 48000);
   const values = buffer.getChannelData(0);
   for(let i=0;i<values.length;i++) values[i]=Math.sin(2*Math.PI*440*i/48000)*.2;
   const factory = Instrument((ctx, options, smplr) => smplr.loadInstrument({samples:{baseUrl:'',formats:['wav']},groups:[{regions:[{sample:'test',keyRange:[60,60],pitch:60}]}]},new Map([['test',buffer]])));
   const player = factory(ctx); await player.ready;
   player.start({note:60,time:.1,duration:fixed?.047:.055,...(fixed?{ampRelease:.008}:{}),velocity:80});
   const audio = (await ctx.startRendering()).getChannelData(0);
   function rms(a,b){let sum=0; for(let i=a*48000;i<b*48000;i++)sum+=audio[i]*audio[i];return Math.sqrt(sum/((b-a)*48000));}
   return {during:rms(.11,.14),after:rms(.16,.20)};
  }
  return {before:await render(false),after:await render(true)};
 });
 console.log(JSON.stringify(result));
 assert.ok(result.before.after>.001,'old renderer audibly overlaps the rest');
 assert.ok(result.after.during>.001,'corrected renderer still sounds the written note');
 assert.equal(result.after.after,0,'corrected renderer is silent after the written note');
} finally {await browser.close();}
