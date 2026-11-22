// con il menu a sinistra alto quanto la finestra (come dalla tappa 2), dove comincia la scheda di Dove si fa?
const { chromium } = require('/opt/node-tools/node_modules/playwright');
(async () => {
  const br = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const pg = await (await br.newContext({ viewport: { width: 1366, height: 657 } })).newPage();
  await pg.goto('http://127.0.0.1:5147/dove-si-fa/?q=ecografia');
  await pg.addStyleTag({ content: '.menu{position:fixed!important;left:0;top:0;bottom:0;width:248px;height:auto!important;flex-direction:column!important;overflow:auto} body{padding-left:248px}' });
  await pg.evaluate(() => window.dispatchEvent(new Event('resize')));
  await pg.locator('#risultati-dove a.sede').first().click();
  await pg.waitForSelector('#scheda-dove:not([hidden]) .dentro-scheda');
  await pg.waitForTimeout(400);
  const m = await pg.evaluate(() => {
    const s = document.getElementById('scheda-dove').getBoundingClientRect();
    const menu = document.querySelector('.menu').getBoundingClientRect();
    return { scheda: [Math.round(s.top), Math.round(s.height), Math.round(s.left), Math.round(s.width)], menu_bottom: Math.round(menu.bottom), finestra: innerHeight, testo_h2: document.querySelector('#scheda-dove h2').innerText };
  });
  console.log(JSON.stringify(m));
  await pg.screenshot({ path: __dirname + '/foto/esperimento-scheda-menu-a-sinistra.png' });
  await br.close();
})();
