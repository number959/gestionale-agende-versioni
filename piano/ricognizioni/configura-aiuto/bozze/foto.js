// Foto a 1366x657 (viewport) e pagina intera a 1440; tavole (file .dc.html) o pagine del gestionale di prova.
// node foto.js tavola NOME...   |   node foto.js pagina NOME URL ...
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const path = require('path');
const R = __dirname;
(async () => {
  const br = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const tipo = process.argv[2];
  const args = process.argv.slice(3);
  const coppie = tipo === 'tavola' ? args.map(n => [n, 'file://' + path.join(R, 'tavole', n + '.dc.html')])
                                  : (() => { const c = []; for (let i = 0; i < args.length; i += 2) c.push([args[i], args[i + 1]]); return c; })();
  for (const [nome, url] of coppie) {
    for (const [w, h, suff, intera] of [[1366, 657, '1366', false], [1440, 1000, '1440', true]]) {
      const ctx = await br.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'it-IT' });
      const pg = await ctx.newPage();
      const errori = [];
      pg.on('pageerror', e => errori.push(e.message));
      const r = await pg.goto(url, { waitUntil: 'load' });
      if (tipo === 'tavola') { try { await pg.waitForFunction(() => window.__pronto === true, null, { timeout: 15000 }); } catch (e) { errori.push('non pronta'); } }
      await pg.waitForTimeout(500);
      await pg.screenshot({ path: path.join(R, 'foto', (tipo === 'tavola' ? 'tavola-' : (process.env.PREFISSO || 'oggi-')) + nome + '-' + suff + '.png'), fullPage: intera });
      const m = await pg.evaluate(() => ({ alto: document.documentElement.scrollHeight, largo: document.documentElement.scrollWidth }));
      console.log(nome, suff, (r ? r.status() : ''), m.largo + 'x' + m.alto, errori.length ? 'ERRORI: ' + errori.join(' / ') : '');
      await ctx.close();
    }
  }
  await br.close();
})();
