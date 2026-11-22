// A 1366x657: dove comincia il contenuto utile (prima riga della tabella o primo campo), quante righe si vedono senza
// scorrere, altezza delle righe, larghezza del contenuto; se la pagina scorre di lato.
//   node misura.js tavola NOME SELETTORE_RIGHE ...   |   node misura.js pagina NOME URL SELETTORE_RIGHE ...
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const path = require('path');
const R = __dirname;
(async () => {
  const br = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const tipo = process.argv[2];
  const a = process.argv.slice(3);
  const casi = [];
  if (tipo === 'tavola') { for (let i = 0; i < a.length; i += 2) casi.push([a[i], 'file://' + path.join(R, 'tavole', a[i] + '.dc.html'), a[i + 1]]); }
  else { for (let i = 0; i < a.length; i += 3) casi.push([a[i], a[i + 1], a[i + 2]]); }
  for (const [nome, url, sel] of casi) {
    const ctx = await br.newContext({ viewport: { width: 1366, height: 657 }, locale: 'it-IT' });
    const pg = await ctx.newPage();
    await pg.route(/fonts\.(googleapis|gstatic)\.com/, r => r.abort());
    await pg.goto(url, { waitUntil: 'load' });
    if (tipo === 'tavola') { try { await pg.waitForFunction(() => window.__pronto === true, null, { timeout: 15000 }); } catch (e) {} }
    await pg.waitForTimeout(300);
    const m = await pg.evaluate((sel) => {
      const righe = [...document.querySelectorAll(sel)].filter(e => e.getBoundingClientRect().height > 0);
      const r = righe.map(e => e.getBoundingClientRect());
      const visibili = r.filter(x => x.bottom <= innerHeight).length;
      const alt = r.map(x => Math.round(x.height));
      const media = alt.length ? Math.round(alt.reduce((s, x) => s + x, 0) / alt.length) : 0;
      return { righe: r.length, prima_y: r.length ? Math.round(r[0].top) : null, visibili, altezza_media: media,
               largo: document.documentElement.scrollWidth, alto: document.documentElement.scrollHeight };
    }, sel);
    console.log(nome.padEnd(22), JSON.stringify(m));
    await ctx.close();
  }
  await br.close();
})();
