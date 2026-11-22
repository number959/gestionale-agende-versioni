// Lo schema del contenuto (dentro <main>), in ordine: titoli, linguette, comandi, campi, tabelle, testi.
// node schema.js tavola NOME...  |  node schema.js pagina NOME URL ...   -> schema-<tipo>-NOME.txt e testi-<tipo>-NOME.txt
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const path = require('path'); const fs = require('fs');
const R = __dirname;
(async () => {
  const br = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const tipo = process.argv[2]; const args = process.argv.slice(3);
  const coppie = tipo === 'tavola' ? args.map(n => [n, 'file://' + path.join(R, 'tavole', n + '.dc.html')])
    : (() => { const c = []; for (let i = 0; i < args.length; i += 2) c.push([args[i], args[i + 1]]); return c; })();
  for (const [nome, url] of coppie) {
    const ctx = await br.newContext({ viewport: { width: 1366, height: 657 }, locale: 'it-IT' });
    const pg = await ctx.newPage();
    await pg.goto(url);
    if (tipo === 'tavola') await pg.waitForFunction(() => window.__pronto === true);
    const out = await pg.evaluate(() => {
      const radice = document.querySelector('main') || document.body;
      const righe = [], testi = [];
      const vis = e => { const s = getComputedStyle(e); return s.display !== 'none' && s.visibility !== 'hidden' && !e.closest('[hidden]'); };
      const t = e => (e.innerText || e.textContent || '').replace(/\s+/g, ' ').trim();
      radice.querySelectorAll('h1,h2,h3,h4,nav,[role=tab],a,button,input,select,textarea,table,form,details>summary,label,dialog,[role=dialog]').forEach(e => {
        const v = vis(e) ? '' : ' (nascosto)';
        const tag = e.tagName.toLowerCase();
        if (/^h\d$/.test(tag)) righe.push(tag.toUpperCase() + ' ' + t(e) + v);
        else if (tag === 'nav') righe.push('NAV[' + (e.getAttribute('aria-label') || '') + '] ' + t(e) + v);
        else if (tag === 'a') righe.push('  link «' + t(e) + '»' + (e.title ? ' title=«' + e.title + '»' : '') + v);
        else if (tag === 'button') righe.push('  bottone «' + t(e) + '»' + (e.name ? ' name=' + e.name + ' value=' + e.value : '') + v);
        else if (tag === 'input' || tag === 'select' || tag === 'textarea') righe.push('  campo ' + tag + (e.type ? ':' + e.type : '') + (e.name ? ' name=' + e.name : '') + (e.placeholder ? ' «' + e.placeholder + '»' : '') + v);
        else if (tag === 'table') righe.push('  TABELLA [' + Array.from(e.querySelectorAll('th')).map(t).join(' | ') + '] righe=' + e.querySelectorAll('tr').length + v);
        else if (tag === 'form') righe.push('  MODULO ' + (e.method || '') + ' ' + (e.getAttribute('action') || '') + v);
        else if (tag === 'summary') righe.push('  apri/chiudi «' + t(e) + '»' + v);
        else if (tag === 'label') { }
        else righe.push('  ' + tag + ' ' + t(e).slice(0, 80) + v);
      });
      const w = document.createTreeWalker(radice, NodeFilter.SHOW_TEXT);
      let n; while ((n = w.nextNode())) { const s = n.nodeValue.replace(/\s+/g, ' ').trim(); if (s && n.parentElement && vis(n.parentElement) && !['SCRIPT', 'STYLE'].includes(n.parentElement.tagName)) testi.push(s); }
      radice.querySelectorAll('[title],[aria-label],[placeholder]').forEach(e => { if (e.title) testi.push('@title ' + e.title); if (e.getAttribute('aria-label')) testi.push('@aria ' + e.getAttribute('aria-label')); if (e.placeholder) testi.push('@placeholder ' + e.placeholder); });
      return { righe, testi };
    });
    fs.writeFileSync(path.join(R, 'misure', 'schema-' + tipo + '-' + nome + '.txt'), out.righe.join('\n'));
    fs.writeFileSync(path.join(R, 'misure', 'testi-' + tipo + '-' + nome + '.txt'), out.testi.join('\n'));
    console.log(nome, out.righe.length, out.testi.length);
    await ctx.close();
  }
  await br.close();
})();
