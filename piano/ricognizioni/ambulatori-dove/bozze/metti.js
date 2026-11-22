// apre il «+» della prima riga e misura la finestrella rispetto alla tabella; poi la stessa dentro un contenitore che scorre di lato
const { chromium } = require('/opt/node-tools/node_modules/playwright');
(async () => {
  const br = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const pg = await (await br.newContext({ viewport: { width: 1366, height: 657 } })).newPage();
  await pg.goto('http://127.0.0.1:5147/ambulatori/settimana/2026-11-23');
  await pg.waitForSelector('#matrice-ambulatori details.metti');
  const prova = async (titolo) => {
    const m = await pg.evaluate(() => {
      const d = document.querySelector('#matrice-ambulatori tbody tr details.metti'); d.open = true;
      const f = d.querySelector('form').getBoundingClientRect(), t = document.getElementById('matrice-ambulatori').getBoundingClientRect();
      const c = document.getElementById('matrice-ambulatori').parentElement.getBoundingClientRect();
      const x = document.elementFromPoint(f.left + 20, f.top + 8);
      return { form: [Math.round(f.top), Math.round(f.height), Math.round(f.width)], tabella_top: Math.round(t.top), contenitore_top: Math.round(c.top), sopra_al_punto: x ? (x.closest('details.metti') ? 'la finestrella' : x.tagName + '.' + x.className) : null };
    });
    console.log(titolo, JSON.stringify(m));
  };
  await prova('oggi:');
  await pg.evaluate(() => { const t = document.getElementById('matrice-ambulatori'); const w = document.createElement('div'); w.style.overflowX = 'auto'; t.parentNode.insertBefore(w, t); w.appendChild(t); document.querySelector('#matrice-ambulatori details.metti').open = false; });
  await prova('dentro overflow-x:auto:');
  await br.close();
})();
