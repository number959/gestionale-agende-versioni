# Foto e misure dei turni: tavole Turni1-6 (file://) e pagine di oggi (gestionale di prova, porta 5146).
# Uso: python -I foto.py
import json, os
from datetime import date, timedelta
from playwright.sync_api import sync_playwright

V = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(V, 'tavole')
F = os.path.join(V, 'foto')
os.makedirs(F, exist_ok=True)
BASE = 'http://127.0.0.1:5146'
oggi = date.today()
lun = oggi - timedelta(days=oggi.weekday())

TAVOLE = ['Turni1-Mese', 'Turni2-Settimana', 'Turni3-Giorno', 'Turni4-Persone', 'Turni5-Persona', 'Turni6-Tipi']
PAGINE = [('mese', '/personale/turni/mese/%s' % oggi.strftime('%Y-%m')),
          ('settimana', '/personale/turni/settimana/%s' % lun.isoformat()),
          ('giorno', '/personale/turni/giorno/%s' % oggi.isoformat()),
          ('persone', '/personale/persone'),
          ('persona-nuova', '/personale/persone/nuova'),
          ('tipi', '/personale/tipi')]

MISURE = r'''() => {
  const r = (el) => { if (!el) return null; const b = el.getBoundingClientRect();
    return {x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height)}; };
  const g = document.querySelector('[role=grid]') || document.querySelector('table.turni');
  const cella = document.querySelector('td.cella, [role=gridcell]');
  const nome = document.querySelector('th.nome-col, [role=rowheader]');
  const tot = document.querySelector('td.tot');
  const scorri = g ? g.parentElement : null;
  return {larghezza: document.documentElement.clientWidth, scroll_x: document.documentElement.scrollWidth,
          alto_pagina: document.documentElement.scrollHeight,
          griglia: r(g), griglia_scroll_w: g ? g.scrollWidth : null, contenitore: r(scorri),
          contenitore_scroll_w: scorri ? scorri.scrollWidth : null,
          cella: r(cella), nome: r(nome), tot: r(tot)};
}'''


def main():
    out = {}
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or '/opt/pw-browsers/chromium')
        for (w, h) in [(1366, 657), (1440, 1000)]:
            ctx = br.new_context(viewport={'width': w, 'height': h}, device_scale_factor=1, locale='it-IT')
            pg = ctx.new_page()
            pg.route('**/*', lambda route: route.abort() if route.request.url.startswith('http') and
                     '127.0.0.1' not in route.request.url else route.continue_())
            for nome in TAVOLE:
                pg.goto('file://' + os.path.join(T, nome + '.dc.html'))
                try:
                    pg.wait_for_function('window.__pronto === true', timeout=15000)
                except Exception as e:
                    print('non pronta', nome, e)
                pg.wait_for_timeout(300)
                pg.screenshot(path=os.path.join(F, 'tavola-%s-%d.png' % (nome, w)))
                if w == 1440:
                    pg.screenshot(path=os.path.join(F, 'tavola-%s-%d-intera.png' % (nome, w)), full_page=True)
                out['tavola %s %d' % (nome, w)] = pg.evaluate(MISURE)
            for nome, url in PAGINE:
                pg.goto(BASE + url)
                pg.wait_for_timeout(400)
                pg.screenshot(path=os.path.join(F, 'oggi-%s-%d.png' % (nome, w)))
                out['pagina %s %d' % (nome, w)] = pg.evaluate(MISURE)
            ctx.close()
        br.close()
    with open(os.path.join(V, 'misure.json'), 'w') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    for k, v in out.items():
        print(k, json.dumps(v, ensure_ascii=False))


main()
