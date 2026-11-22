// i testi visibili (nodi di testo e title/aria-label) di una tavola, solo nel contenuto (non nel menu a sinistra)
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const path = require('path'); const fs = require('fs');
(async () => {
  const br = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  for (const nome of process.argv.slice(2)) {
    const ctx = await br.newContext({ viewport: { width: 1366, height: 657 }, locale: 'it-IT' });
    const pg = await ctx.newPage();
    await pg.goto('file://' + path.join(__dirname, 'tavole', nome + '.dc.html'));
    await pg.waitForFunction(() => window.__pronto === true);
    const t = await pg.evaluate(() => {
      const out = [];
      const radice = document.querySelector('main') || document.body;
      const w = document.createTreeWalker(radice, NodeFilter.SHOW_TEXT);
      let n; while ((n = w.nextNode())) { const s = n.nodeValue.replace(/\s+/g, ' ').trim(); if (s) out.push(s); }
      radice.querySelectorAll('[title],[aria-label]').forEach(e => { if (e.title) out.push('@title ' + e.title); if (e.getAttribute('aria-label')) out.push('@aria ' + e.getAttribute('aria-label')); });
      return out;
    });
    fs.writeFileSync(path.join(__dirname, 'testi-' + nome + '.txt'), t.join('\n'));
    console.log(nome, t.length);
    await ctx.close();
  }
  await br.close();
})();
