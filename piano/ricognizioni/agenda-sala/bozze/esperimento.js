// Esperimento sulla tavola del Giorno a 1366x657: quanto sale la griglia togliendo o stringendo pezzi dell'intestazione.
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const path = require('path');
(async () => {
  const br = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const prove = {
    'tavola così com è': () => {},
    'senza striscia (il conto accanto al titolo, come oggi)': () => { document.querySelector('[aria-label="I conti del giorno"]').style.display = 'none'; },
    'striscia via + barra dei comandi su una riga (nowrap, scorre)': () => {
      document.querySelector('[aria-label="I conti del giorno"]').style.display = 'none';
      const b = [...document.querySelectorAll('main > div')].find(x => /Nuovo appuntamento/.test(x.textContent) && x.getBoundingClientRect().height < 200);
      b.style.flexWrap = 'nowrap'; b.style.overflowX = 'auto'; [...b.children].forEach(c => { c.style.flexWrap = 'nowrap'; });
    },
    'come sopra + nota chiusa e senza appunti': () => {
      document.querySelector('[aria-label="I conti del giorno"]').style.display = 'none';
      const b = [...document.querySelectorAll('main > div')].find(x => /Nuovo appuntamento/.test(x.textContent) && x.getBoundingClientRect().height < 200);
      b.style.flexWrap = 'nowrap'; b.style.overflowX = 'auto'; [...b.children].forEach(c => { c.style.flexWrap = 'nowrap'; });
      const ta = document.querySelector('textarea'); ta.closest('label').style.display = 'none'; ta.closest('label').nextElementSibling.style.display = 'none';
      const app = [...document.querySelectorAll('main div')].find(x => /^Da confermare per questo giorno/.test(x.textContent.trim())); app.style.display = 'none';
    }
  };
  for (const [nome, f] of Object.entries(prove)) {
    const ctx = await br.newContext({ viewport: { width: 1366, height: 657 } });
    const pg = await ctx.newPage();
    await pg.goto('file://' + path.join(__dirname, 'tavole', 'Nefro-Agenda1-Giorno.dc.html'));
    await pg.waitForFunction(() => window.__pronto === true);
    await pg.evaluate(f);
    await pg.waitForTimeout(200);
    const m = await pg.evaluate(() => {
      const g = document.querySelector('section[aria-label="Griglia del giorno"]');
      const top = g.getBoundingClientRect().top;
      const testa = g.firstElementChild.firstElementChild.nextElementSibling.getBoundingClientRect().height; // intestazione di una stanza
      const barra = [...document.querySelectorAll('main > div')].find(x => /Nuovo appuntamento/.test(x.textContent) && x.getBoundingClientRect().height < 200);
      return { griglia_cima: Math.round(top), testa: Math.round(testa), barra_alta: Math.round(barra.getBoundingClientRect().height), barra_scorre: barra.scrollWidth > barra.clientWidth,
               mezzore_visibili: Math.max(0, Math.floor((657 - top - testa) / 36)) };
    });
    await pg.screenshot({ path: path.join(__dirname, 'foto', 'esperimento-' + Object.keys(prove).indexOf(nome) + '.png') });
    console.log(nome.padEnd(62), JSON.stringify(m));
    await ctx.close();
  }
  await br.close();
})();
