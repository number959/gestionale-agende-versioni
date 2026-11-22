// Misure a 1366x657 (e 1440) di tavole e pagine: dove comincia la griglia, quante righe si vedono, altezze.
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const path = require('path');
const R = __dirname;
const B = 'http://127.0.0.1:5144';
(async () => {
  const br = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const casi = [
    ['tavola', 'Nefro-Agenda1-Giorno'], ['tavola', 'Nefro-Agenda2-Settimana'], ['tavola', 'Nefro-Agenda3-Mese'], ['tavola', 'Nefro-Agenda4-Elenco'], ['tavola', 'Sala1-Giorno'],
    ['pagina', B + '/giorno/2026-11-17?struttura=1'], ['pagina', B + '/giorno/2026-11-23?struttura=1'], ['pagina', B + '/settimana/2026-11-17?struttura=1'],
    ['pagina', B + '/mese/2026-11?struttura=1'], ['pagina', B + '/giorno/2026-11-17/elenco?struttura=1'], ['pagina', B + '/sala/2026-11-23?struttura=1'],
    ['pagina', B + '/appuntamento?data=2026-11-23&struttura=1'], ['pagina', B + '/oggi']
  ];
  for (const larghezza of [1366, 1440]) {
    for (const [tipo, cosa] of casi) {
      const ctx = await br.newContext({ viewport: { width: larghezza, height: 657 }, locale: 'it-IT' });
      const pg = await ctx.newPage();
      await pg.goto(tipo === 'tavola' ? 'file://' + path.join(R, 'tavole', cosa + '.dc.html') : cosa);
      if (tipo === 'tavola') await pg.waitForFunction(() => window.__pronto === true, null, { timeout: 15000 }).catch(() => {});
      await pg.waitForTimeout(400);
      const m = await pg.evaluate(() => {
        const r = (el) => el ? Math.round(el.getBoundingClientRect().top) : null;
        const h = (el) => el ? Math.round(el.getBoundingClientRect().height) : null;
        const out = {};
        const t = document.querySelector('table.griglia, table.settimana, table.mese, table.elenco, section[aria-label^="Griglia"], section[aria-label^="Elenco"], [role=table]');
        // tavole: la griglia è una section con aria-label; il calendario del mese e la settimana sono altri contenitori
        let g = t;
        if (!g) { g = [...document.querySelectorAll('section, div')].find(x => /grid-template-columns: 48px|grid-template-columns: 150px|repeat\(7/.test(x.getAttribute('style') || '')); }
        out.griglia_cima = r(g);
        const h1 = document.querySelector('h1'); out.h1_cima = r(h1); out.h1 = h1 ? h1.textContent.trim().slice(0, 40) : '';
        // barra dei comandi (tavola: il div con «Nuovo appuntamento»; pagina: .barra)
        const barra = document.querySelector('.barra') || [...document.querySelectorAll('main > div')].find(x => /Stampa e scarica/.test(x.textContent) && x.getBoundingClientRect().height < 200);
        out.barra_alta = h(barra); out.barra_cima = r(barra);
        // righe della griglia visibili sopra i 657 px
        const tr = document.querySelectorAll('table.griglia tbody tr');
        if (tr.length) { out.riga_alta = h(tr[0]); out.righe_visibili = [...tr].filter(x => x.getBoundingClientRect().bottom <= 657).length; out.righe = tr.length;
          out.colonna_stanza = Math.round(document.querySelector('table.griglia thead th:nth-child(2)').getBoundingClientRect().width);
          out.thead_alta = h(document.querySelector('table.griglia thead')); }
        out.alto_pagina = document.documentElement.scrollHeight;
        out.largo_pagina = document.documentElement.scrollWidth;
        return out;
      });
      console.log(larghezza, (tipo === 'tavola' ? cosa : cosa.replace(B, '')).padEnd(42), JSON.stringify(m));
      await ctx.close();
    }
  }
  await br.close();
})();
