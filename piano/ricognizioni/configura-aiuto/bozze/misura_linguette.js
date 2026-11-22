// Le linguette di Configura nella tavola: larghezze, e con una settima «Aree e accessi» aggiunta (copia dell'ultima)
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const path = require('path'); const fs = require('fs');
(async () => {
  const br = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const out = {};
  for (const w of [1366, 1440, 1280, 1024, 683]) {
    const ctx = await br.newContext({ viewport: { width: w, height: 657 }, locale: 'it-IT' });
    const pg = await ctx.newPage();
    await pg.goto('file://' + path.join(__dirname, 'tavole', 'Conf1-Anagrafiche.dc.html'));
    await pg.waitForFunction(() => window.__pronto === true);
    const m = await pg.evaluate(() => {
      const nav = document.querySelector('nav[aria-label="Pagine di Configura"]');
      const main = document.querySelector('main');
      const r = e => { const b = e.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)]; };
      const sei = { nav: r(nav), main: r(main), tab: Array.from(nav.children).map(a => [a.textContent.trim(), Math.round(a.getBoundingClientRect().width)]) };
      const c = nav.lastElementChild.cloneNode(true); c.textContent = 'Aree e accessi'; c.removeAttribute('aria-current'); nav.appendChild(c);
      const righe = new Set(Array.from(nav.children).map(a => Math.round(a.getBoundingClientRect().top)));
      return { sei, sette: { nav: r(nav), righe: righe.size, settima: r(c) } };
    });
    out[w] = m;
    await pg.screenshot({ path: path.join(__dirname, 'foto', 'linguette-sette-' + w + '.png'), clip: { x: 0, y: 0, width: w, height: 300 } });
    await ctx.close();
  }
  fs.writeFileSync(path.join(__dirname, 'misure', 'linguette.json'), JSON.stringify(out, null, 1));
  console.log(JSON.stringify(out, null, 1));
  await br.close();
})();
