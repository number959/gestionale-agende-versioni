// misure delle tavole Conf a 1366x657: larghezza utile, colonne, tabelle, altezza della prima schermata
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const path = require('path'); const fs = require('fs');
(async () => {
  const br = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const out = {};
  for (const n of ['Conf1-Anagrafiche', 'Conf2-Medico', 'Conf3-Gruppo', 'Conf4-Invii', 'Conf5-Importa', 'Conf6-Impostazioni', 'Conf7-Aggiornamenti']) {
    const pg = await br.newPage({ viewport: { width: 1366, height: 657 } });
    await pg.goto('file://' + path.join(__dirname, 'tavole', n + '.dc.html'));
    await pg.waitForFunction(() => window.__pronto === true);
    out[n] = await pg.evaluate(() => {
      const r = e => { const b = e.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)]; };
      const main = document.querySelector('main');
      const figli = Array.from(main.children).map(e => [e.tagName.toLowerCase(), (e.getAttribute('aria-label') || e.getAttribute('aria-labelledby') || (e.querySelector('h2,h3') || {}).textContent || '').trim().slice(0, 40), r(e), getComputedStyle(e).display === 'grid' ? getComputedStyle(e).gridTemplateColumns : '']);
      const h2 = main.querySelector('h2'); const nav = main.querySelector('nav');
      const piega = Array.from(main.querySelectorAll('h2,h3,table,[role=table],form')).filter(e => e.getBoundingClientRect().top < 657).map(e => (e.textContent || '').trim().slice(0, 30));
      return { main: r(main), titoloLinguetta: h2 ? r(h2) : null, linguette: nav ? r(nav) : null, figli, primaSchermata: piega.slice(0, 8), alto: document.documentElement.scrollHeight };
    });
    await pg.close();
  }
  fs.writeFileSync(path.join(__dirname, 'misure', 'tavole-1366.json'), JSON.stringify(out, null, 1));
  for (const [n, m] of Object.entries(out)) {
    console.log('==', n, 'main', m.main.join('x'), 'h2 a y=' + (m.titoloLinguetta || [])[1], 'alto', m.alto);
    m.figli.forEach(f => console.log('   ', f[0], JSON.stringify(f[1]), f[2].join(','), f[3]));
  }
  await br.close();
})();
