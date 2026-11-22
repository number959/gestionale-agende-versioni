# La settimana dei turni in 1046 px: colonne dei giorni elastiche, nome 150, Ore 92, gli altri tre 40.
import json, os
from datetime import date, timedelta
from playwright.sync_api import sync_playwright
V = os.path.dirname(os.path.abspath(__file__))
lun = date.today() - timedelta(days=date.today().weekday())
CSS = '''
nav.menu { display: none !important; }
body { margin-left: 248px !important; background: #F3F6FA; }
.barra-turni, .legenda-turni { padding-left: 36px !important; padding-right: 36px !important; }
.telaio-turni { padding: 10px 36px 40px !important; }
table.turni-settimana col.col-nome { width: 150px !important; }
table.turni-settimana col.col-giorno { width: auto !important; }
table.turni-settimana col.col-tot { width: 40px !important; }
table.turni-settimana col.col-tot:nth-last-child(4) { width: 92px !important; }
'''
MISURA = r'''() => {
  const tab = document.getElementById('griglia-turni'); const sc = tab.parentElement;
  const out = {contenitore: Math.round(sc.getBoundingClientRect().width), tabella: tab.scrollWidth,
    cella: Math.round(tab.querySelector('td.cella').getBoundingClientRect().width), tagliati: [], ore: []};
  for (const x of tab.querySelectorAll('td.cella .turno b, td.cella .ore-turno')) if (x.scrollWidth > x.clientWidth + 1 || x.getBoundingClientRect().width > x.closest('.turno').clientWidth) out.tagliati.push(x.textContent);
  out.aree_con_puntini = Array.from(tab.querySelectorAll('td.cella .area-turno')).filter(x => x.scrollWidth > x.clientWidth + 1).map(x => x.textContent);
  out.ore = Array.from(tab.querySelectorAll('td.tot[data-tot="ore"]')).filter(td => td.scrollWidth > td.clientWidth + 1).map(td => td.textContent);
  return out; }'''
with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = br.new_page(viewport={'width': 1366, 'height': 657}, locale='it-IT')
    pg.goto('http://127.0.0.1:5146/personale/turni/settimana/' + lun.isoformat())
    pg.add_style_tag(content=CSS); pg.wait_for_timeout(300)
    m = pg.evaluate(MISURA)
    pg.screenshot(path=os.path.join(V, 'foto', 'sim-settimana-1046.png'))
    br.close()
print(json.dumps(m, ensure_ascii=False))
