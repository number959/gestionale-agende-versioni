// Foto di tavole e pagine: a 1366x657 (quello che si vede) e pagina intera; le tavole anche a 1440.
//   node foto.js tavola NOME...          (file in tavole/NOME.dc.html)
//   node foto.js pagina NOME URL [NOME URL ...]
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const path = require('path');
const R = __dirname;
(async () => {
  const br = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const tipo = process.argv[2];
  const args = process.argv.slice(3);
  const coppie = tipo === 'tavola' ? args.map(n => [n, 'file://' + path.join(R, 'tavole', n + '.dc.html')])
    : (() => { const c = []; for (let i = 0; i < args.length; i += 2) c.push([args[i], args[i + 1]]); return c; })();
  const larghezze = tipo === 'tavola' ? [1366, 1440] : [1366];
  for (const [nome, url] of coppie) {
    for (const w of larghezze) {
      const ctx = await br.newContext({ viewport: { width: w, height: 657 }, deviceScaleFactor: 1, locale: 'it-IT' });
      const pg = await ctx.newPage();
      const errori = [];
      pg.on('pageerror', e => errori.push(e.message));
      await pg.route(/fonts\.(googleapis|gstatic)\.com/, r => r.abort());
      await pg.goto(url, { waitUntil: 'load' });
      if (tipo === 'tavola') { try { await pg.waitForFunction(() => window.__pronto === true, null, { timeout: 15000 }); } catch (e) { errori.push('non pronta'); } }
      await pg.waitForTimeout(500);
      if (w === 1366) await pg.screenshot({ path: path.join(R, 'foto', nome + '-1366.png') });
      await pg.screenshot({ path: path.join(R, 'foto', nome + '-' + w + '-intera.png'), fullPage: true });
      const m = await pg.evaluate(() => ({ alto: document.documentElement.scrollHeight, largo: document.documentElement.scrollWidth }));
      console.log(nome, w, 'pagina', m.largo + 'x' + m.alto, errori.length ? 'ERRORI: ' + errori.join(' / ') : '');
      await ctx.close();
    }
  }
  await br.close();
})();
