# La griglia del mese che scorre con la pagina (riga dei giorni ferma in cima): funziona con turni.js di oggi?
import os, re
from playwright.sync_api import sync_playwright
V = os.path.dirname(os.path.abspath(__file__))
css = open(os.path.join(V, 'sim_mese.py')).read()
CSS = re.search(r"CSS = '''(.*?)''' %", css, re.S).group(1) % {'G': 24, 'ORE': 58, 'TOT': 32}
CSS += '''
.legenda-turni { margin-top: 250px; }   /* al posto di intestazione, linguette e barra della tavola: la griglia a y~485 */
.scorri-turni, .telaio { overflow: visible !important; max-height: none !important; }
table.turni thead th { top: 0; }
table.turni td.cella { scroll-margin-top: 64px; scroll-margin-bottom: 8px; }
'''
with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = br.new_page(viewport={'width': 1366, 'height': 657}, locale='it-IT')
    err = []; pg.on('pageerror', lambda e: err.append(str(e)))
    pg.goto('http://127.0.0.1:5146/personale/turni/mese/2026-12')
    pg.add_style_tag(content=CSS); pg.wait_for_timeout(300)
    y0 = pg.evaluate("document.getElementById('griglia-turni').getBoundingClientRect().top")
    pg.mouse.wheel(0, 700); pg.wait_for_timeout(300)
    th = pg.evaluate("document.querySelector('#griglia-turni thead th.giorno-col').getBoundingClientRect().top")
    # tastiera: dalla prima cella giù di 12 righe; la cella col fuoco non deve stare sotto la riga dei giorni
    pg.evaluate("window.scrollTo(0, 0)")
    c = pg.locator('#griglia-turni td.cella').first
    c.click(); pg.keyboard.press('Escape')
    for _ in range(14): pg.keyboard.press('ArrowDown')
    for _ in range(10): pg.keyboard.press('ArrowUp')
    pg.wait_for_timeout(200)
    r = pg.evaluate("""() => { const f = document.activeElement.getBoundingClientRect();
      const h = document.querySelector('#griglia-turni thead th.giorno-col').getBoundingClientRect();
      return {fuoco_top: Math.round(f.top), fuoco_bottom: Math.round(f.bottom), testa_bottom: Math.round(h.bottom), alto: innerHeight}; }""")
    # la scelta del turno dopo lo scorrere: dentro lo schermo e non sopra la cella
    pg.mouse.wheel(0, 300); pg.wait_for_timeout(200)
    cella = pg.locator('#griglia-turni tr.riga-persona').nth(8).locator('td.cella').nth(20)
    cella.click(); pg.wait_for_timeout(200)
    pop = pg.locator('#scelta-turno').bounding_box(); cb = cella.bounding_box()
    print('griglia a y=%d prima di scorrere; dopo 700 px la riga dei giorni sta a y=%d' % (y0, th))
    print('tastiera:', r, 'coperta' if r['fuoco_top'] < r['testa_bottom'] else 'visibile')
    print('scelta:', {k: round(v) for k, v in pop.items()}, 'cella', {k: round(v) for k, v in cb.items()},
          'dentro' if pop['y'] >= 0 and pop['y'] + pop['height'] <= 657 else 'FUORI')
    pg.screenshot(path=os.path.join(V, 'foto', 'sim-mese-scorre.png'))
    print('errori JS:', err)
    br.close()
