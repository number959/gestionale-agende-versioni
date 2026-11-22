const { chromium } = require('/opt/node-tools/node_modules/playwright');
(async () => {
  const br = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const ctx = await br.newContext({ viewport: { width: 1366, height: 657 } });
  const pg = await ctx.newPage();
  for (const u of ['/appuntamento?data=2026-11-23&struttura=1', '/appuntamento/39?struttura=1']) {
    await pg.goto('http://127.0.0.1:5144' + u);
    const m = await pg.evaluate(() => {
      const hs = [...document.querySelectorAll('#modulo-appuntamento input:not([type=hidden]):not([type=checkbox]), #modulo-appuntamento select')].map(x => Math.round(x.getBoundingClientRect().height));
      const pagina = document.querySelector('.pagina').getBoundingClientRect();
      const salva = document.querySelector('#modulo-appuntamento button.primario').getBoundingClientRect();
      return { campi: hs.length, alti: [...new Set(hs)], pagina_larga: Math.round(pagina.width), salva_cima: Math.round(salva.top + scrollY), alto: document.documentElement.scrollHeight,
               riquadri: [...document.querySelectorAll('.riquadro-modulo')].map(x => x.id || x.querySelector('h2')?.textContent.trim().slice(0, 20) || '(ripeti)') };
    });
    console.log(u, JSON.stringify(m));
  }
  await br.close();
})();
