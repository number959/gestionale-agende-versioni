const { chromium } = require('/opt/node-tools/node_modules/playwright');
const path = require('path');
(async () => {
  const br = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  for (const w of [1366, 1440]) {
    const ctx = await br.newContext({ viewport: { width: w, height: 657 } });
    const pg = await ctx.newPage();
    await pg.goto('file://' + path.join(__dirname, 'tavole', 'Nefro-Agenda4-Elenco.dc.html'));
    await pg.waitForFunction(() => window.__pronto === true);
    const t = await pg.evaluate(() => { const r = [...document.querySelectorAll('[role=row]')].slice(1).map(x => Math.round(x.getBoundingClientRect().height)); return { n: r.length, min: Math.min(...r), max: Math.max(...r), media: Math.round(r.reduce((a, b) => a + b, 0) / r.length) }; });
    const pg2 = await ctx.newPage();
    await pg2.goto('http://127.0.0.1:5144/giorno/2026-11-17/elenco?struttura=1');
    const v = await pg2.evaluate(() => { const r = [...document.querySelectorAll('table.lista-giorno tr')].slice(1).map(x => Math.round(x.getBoundingClientRect().height)); return { n: r.length, min: Math.min(...r), max: Math.max(...r), media: Math.round(r.reduce((a, b) => a + b, 0) / r.length) }; });
    console.log(w, 'tavola Elenco righe', JSON.stringify(t), '| oggi', JSON.stringify(v));
    await ctx.close();
  }
  await br.close();
})();
