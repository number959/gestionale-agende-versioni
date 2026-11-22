// Lo scheletro di una tavola o di una pagina: i nodi di testo visibili del contenuto (senza menu e barra in alto),
// in ordine, con il contenitore più vicino che ha fondo/bordo/angoli (la «scheda»), più bottoni, campi, tabelle.
//   node schema.js tavola NOME...   |   node schema.js pagina NOME URL ...
// Scrive schema/NOME.json e schema/NOME.txt
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs = require('fs'), path = require('path');
const R = __dirname;
(async () => {
  const br = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const tipo = process.argv[2];
  const args = process.argv.slice(3);
  const coppie = tipo === 'tavola' ? args.map(n => [n, 'file://' + path.join(R, 'tavole', n + '.dc.html')])
    : (() => { const c = []; for (let i = 0; i < args.length; i += 2) c.push([args[i], args[i + 1]]); return c; })();
  fs.mkdirSync(path.join(R, 'schema'), { recursive: true });
  for (const [nome, url] of coppie) {
    const ctx = await br.newContext({ viewport: { width: 1440, height: 900 }, locale: 'it-IT' });
    const pg = await ctx.newPage();
    await pg.route(/fonts\.(googleapis|gstatic)\.com/, r => r.abort());
    await pg.goto(url, { waitUntil: 'load' });
    if (tipo === 'tavola') { try { await pg.waitForFunction(() => window.__pronto === true, null, { timeout: 15000 }); } catch (e) {} }
    await pg.waitForTimeout(300);
    const out = await pg.evaluate((tipo) => {
      // radice del contenuto
      let radice;
      if (tipo === 'tavola') {
        const main = document.querySelector('main') || [...document.querySelectorAll('div')].find(d => d.parentElement && getComputedStyle(d.parentElement).display === 'grid' && d.previousElementSibling && d.previousElementSibling.tagName === 'ASIDE');
        radice = main || document.body;
      } else {
        radice = document.querySelector('main') || document.body;
      }
      const escludi = el => el.closest('nav.menu, aside, header, .notifiche, #aiuto-tasti, .popup-aggiornamento, [role=banner]');
      const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
      const scheda = el => { let e = el; while (e && e !== radice) { const s = getComputedStyle(e); if ((s.backgroundColor === 'rgb(255, 255, 255)' && parseFloat(s.borderTopLeftRadius) >= 8) || (s.borderTopWidth !== '0px' && parseFloat(s.borderTopLeftRadius) >= 12)) return e; e = e.parentElement; } return null; };
      const schede = new Map(); let n = 0;
      const righe = [];
      const giro = document.createTreeWalker(radice, NodeFilter.SHOW_TEXT);
      for (let t = giro.nextNode(); t; t = giro.nextNode()) {
        const v = t.nodeValue.replace(/\s+/g, ' ').trim();
        if (!v) continue;
        const el = t.parentElement;
        if (!el || escludi(el) || !vis(el) || el.closest('script,style,option')) continue;
        const sc = scheda(el);
        let id = '';
        if (sc) { if (!schede.has(sc)) { const r = sc.getBoundingClientRect(); const s = getComputedStyle(sc); schede.set(sc, 'S' + (++n) + '[' + Math.round(r.width) + 'x' + Math.round(r.height) + ' r' + s.borderTopLeftRadius + ']'); } id = schede.get(sc); }
        const tag = el.closest('button') ? 'button' : el.closest('a') ? 'a' : el.closest('th') ? 'th' : el.closest('h1,h2,h3,h4') ? el.closest('h1,h2,h3,h4').tagName.toLowerCase() : el.closest('label') ? 'label' : el.closest('summary') ? 'summary' : el.tagName.toLowerCase();
        const s = getComputedStyle(el);
        righe.push({ id, tag, testo: v, px: s.fontSize, peso: s.fontWeight, colore: s.color });
      }
      const campi = [...radice.querySelectorAll('input,select,textarea')].filter(e => !escludi(e)).map(e => ({ tag: e.tagName.toLowerCase(), type: e.type, name: e.getAttribute('name'), placeholder: e.getAttribute('placeholder'), aria: e.getAttribute('aria-label'), vis: vis(e) }));
      const tabelle = [...radice.querySelectorAll('table')].filter(e => !escludi(e)).map(t => ({ w: Math.round(t.getBoundingClientRect().width), intest: [...t.querySelectorAll('th')].map(h => h.textContent.replace(/\s+/g, ' ').trim()), righe: t.rows.length }));
      const r = radice.getBoundingClientRect();
      return { radice: Math.round(r.width) + 'x' + Math.round(r.height), righe, campi, tabelle };
    }, tipo);
    fs.writeFileSync(path.join(R, 'schema', nome + '.json'), JSON.stringify(out, null, 1));
    let txt = 'radice ' + out.radice + '\n';
    let ultimo = null;
    for (const x of out.righe) { if (x.id !== ultimo) { txt += '\n== ' + (x.id || '(fuori scheda)') + '\n'; ultimo = x.id; } txt += '  ' + x.tag + ' ' + x.px + '/' + x.peso + ': ' + x.testo + '\n'; }
    txt += '\nCAMPI\n' + out.campi.map(c => '  ' + JSON.stringify(c)).join('\n') + '\nTABELLE\n' + out.tabelle.map(t => '  ' + JSON.stringify(t)).join('\n') + '\n';
    fs.writeFileSync(path.join(R, 'schema', nome + '.txt'), txt);
    console.log(nome, out.righe.length, 'testi', out.campi.length, 'campi', out.tabelle.length, 'tabelle');
    await ctx.close();
  }
  await br.close();
})();
