// La pagina «non trovata» sotto /riepilogo-live: quali richieste fa (devono cominciare con /riepilogo-live, /static/, /logo/)
const { chromium } = require('/opt/node-tools/node_modules/playwright');
(async () => {
  const br = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  for (const u of ['/riepilogo-live/xyz', '/riepilogo-live/statistiche/xyz', '/nonesiste']) {
    const pg = await br.newPage();
    const richieste = [];
    pg.on('request', r => richieste.push(new URL(r.url()).pathname));
    await pg.clock.install();
    await pg.goto('http://127.0.0.1:5148' + u);
    await pg.clock.runFor(5 * 60 * 1000);
    await pg.waitForTimeout(500);
    const fuori = richieste.filter(p => !/^\/(riepilogo-live|static\/|logo\/)/.test(p));
    console.log(u, 'richieste', richieste.length, 'fuori dal portiere:', JSON.stringify(fuori), 'menu:', await pg.locator('nav.menu').count());
    await pg.close();
  }
  await br.close();
})();
