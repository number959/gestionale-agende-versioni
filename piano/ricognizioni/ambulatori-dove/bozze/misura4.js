// elementi che scorrono o escono in orizzontale (tavola o pagina) a una larghezza data
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const path = require('path');
(async () => {
  const larga = parseInt(process.env.LARGA || '1366');
  const br = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  for (const arg of process.argv.slice(2)) {
    const url = arg.startsWith('http') ? arg : 'file://' + path.join(__dirname, 'tavole', arg + '.dc.html');
    const ctx = await br.newContext({ viewport: { width: larga, height: 657 }, locale: 'it-IT' });
    const pg = await ctx.newPage();
    await pg.goto(url, { waitUntil: 'load' });
    if (!arg.startsWith('http')) { try { await pg.waitForFunction(() => window.__pronto === true, null, { timeout: 15000 }); } catch (e) {} }
    await pg.waitForTimeout(400);
    const m = await pg.evaluate(() => {
      const out = [];
      document.querySelectorAll('body *').forEach(el => {
        const cs = getComputedStyle(el);
        if (el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 300 && /(auto|scroll|hidden)/.test(cs.overflowX)) {
          out.push({ tag: el.tagName.toLowerCase(), cls: (el.className && el.className.baseVal === undefined ? el.className : '').toString().slice(0, 30), aria: el.getAttribute('aria-label') || '', overflow: cs.overflowX, scroll: el.scrollWidth, client: el.clientWidth, testo: el.textContent.trim().slice(0, 40) });
        }
      });
      return { doc: [document.documentElement.scrollWidth, document.documentElement.clientWidth], scorrono: out.slice(0, 8) };
    });
    console.log(arg.slice(0, 70), JSON.stringify(m));
    await ctx.close();
  }
  await br.close();
})();
