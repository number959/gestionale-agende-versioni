// La griglia di oggi nella larghezza che le resta accanto al menu di 248 px (1366 - 248 - 2x36 di margine = 1046 px).
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const path = require('path');
(async () => {
  const br = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  for (const [nome, url] of [['17', '/giorno/2026-11-17?struttura=1'], ['23', '/giorno/2026-11-23?struttura=1'], ['sett', '/settimana/2026-11-17?struttura=1'], ['elenco', '/giorno/2026-11-17/elenco?struttura=1'], ['sala7', '/sala/2026-11-22?struttura=1&giorni=7'], ['mese', '/mese/2026-11?struttura=1']]) {
    const ctx = await br.newContext({ viewport: { width: 1046 + 36, height: 657 } });
    const pg = await ctx.newPage();
    await pg.goto('http://127.0.0.1:5144' + url);
    await pg.waitForTimeout(300);
    const m = await pg.evaluate(() => {
      const t = document.querySelector('table.griglia, table.settimana, table.elenco, table.mese');
      const out = { tabella_larga: Math.round(t.getBoundingClientRect().width), pagina_scorre: document.documentElement.scrollWidth > document.documentElement.clientWidth };
      const ths = [...document.querySelectorAll('table.griglia thead th')].slice(1).map(x => Math.round(x.getBoundingClientRect().width));
      if (ths.length) out.colonne = ths;
      // voci che escono dalla loro cella (contenuto più alto della cella)
      const voci = [...document.querySelectorAll('table.griglia a.voce')];
      out.voci = voci.length;
      out.voci_tagliate = voci.filter(v => v.scrollHeight > v.clientHeight + 1 || v.scrollWidth > v.clientWidth + 1).length;
      out.voci_tagliate_testi = voci.filter(v => v.scrollWidth > v.clientWidth + 1 || v.scrollHeight > v.clientHeight + 1).slice(0, 4).map(v => v.textContent.replace(/\s+/g, ' ').trim().slice(0, 50));
      return out;
    });
    await pg.screenshot({ path: path.join(__dirname, 'foto', 'stretta-' + nome + '.png') });
    console.log(nome.padEnd(7), JSON.stringify(m));
    await ctx.close();
  }
  await br.close();
})();
