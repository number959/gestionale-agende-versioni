// la matrice di oggi (7 giorni nella settimana del 16/11 del gestionale di prova) larga 1044 px come nella tavola,
// con i caratteri della tavola: quante scritte escono dalla loro cella?
const { chromium } = require('/opt/node-tools/node_modules/playwright');
(async () => {
  const br = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const pg = await (await br.newContext({ viewport: { width: 1366, height: 657 } })).newPage();
  for (const [iso, larga] of [['2026-11-16', 1044], ['2026-11-23', 1044], ['2026-11-16', 1118]]) {
    await pg.goto('http://127.0.0.1:5147/ambulatori/settimana/' + iso);
    await pg.addStyleTag({ content: `#matrice-ambulatori{width:${larga}px!important;table-layout:fixed;font-family:Inter} #matrice-ambulatori th.stanza-sett{width:120px} #matrice-ambulatori td{padding:7px 6px 40px} #matrice-ambulatori .disponibile{font:600 12.5px Inter} #matrice-ambulatori th.meta{font:500 12.5px Inter;padding:5px 2px 7px;white-space:nowrap}` });
    const m = await pg.evaluate(() => {
      const t = document.getElementById('matrice-ambulatori');
      const mezze = t.querySelectorAll('thead tr:nth-child(2) th').length;
      const cella = t.querySelector('td[data-cella]').getBoundingClientRect().width;
      let esce = 0, n = 0, peggio = 0; const quali = {};
      t.querySelectorAll('td[data-cella], th.meta, td[data-sala]').forEach(c => {
        const cs = getComputedStyle(c), destra = c.getBoundingClientRect().right - parseFloat(cs.paddingRight);
        const w = document.createTreeWalker(c, NodeFilter.SHOW_TEXT); let x;
        while ((x = w.nextNode())) { if (!x.nodeValue.trim() || x.parentElement.closest('details form, option')) continue; const r = document.createRange(); r.selectNodeContents(x); const rr = r.getBoundingClientRect(); n++; if (rr.right > destra + 0.5) { esce++; const k = x.nodeValue.trim().replace(/[0-9:–]+/g,'#').slice(0,14); quali[k] = (quali[k]||0)+1; peggio = Math.max(peggio, rr.right - destra); } }
      });
      return { mezze, cella: Math.round(cella), testi: n, escono: esce, di_piu_px: Math.round(peggio), quali };
    });
    console.log(iso, 'tabella', larga, JSON.stringify(m));
  }
  await br.close();
})();
