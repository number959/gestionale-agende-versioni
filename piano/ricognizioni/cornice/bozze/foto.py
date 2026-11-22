# Foto e misure della cornice: tavole (file://) e pagine di oggi (porta 5142).
# Uso: python -I foto.py
import json, os, sys
from playwright.sync_api import sync_playwright

V = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(V, 'tavole')
F = os.path.join(V, 'foto')
os.makedirs(F, exist_ok=True)
BASE = 'http://127.0.0.1:5142'

TAVOLE = ['Main', 'Nefro-Agenda1-Giorno', 'Nefro-Agenda2-Settimana', 'Nefro-Ambulatori1-Pianificazione',
          'Nefro-Dashboard1-Oggi', 'Seg1-Conferme', 'Conf1-Anagrafiche', 'Paz1-Elenco', 'Nefro-Colori']
PAGINE = [('oggi', '/oggi'), ('giorno', '/'), ('conferme', '/conferme'), ('anagrafiche', '/anagrafiche'),
          ('ambulatori', '/ambulatori/settimana'), ('pazienti', '/pazienti')]
MISURE = r'''() => {
  const r = (el) => { if (!el) return null; const b = el.getBoundingClientRect();
    return {x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height)}; };
  const aside = document.querySelector('aside') || document.querySelector('nav.menu');
  const header = document.querySelector('header');
  const main = document.querySelector('main');
  const voci = Array.from(document.querySelectorAll('aside a, nav.menu > a, nav.menu .apri-gruppo')).map(a => ({t: a.textContent.trim().slice(0, 30), ...r(a)}));
  return {larghezza: document.documentElement.clientWidth, scroll_x: document.documentElement.scrollWidth,
          alto_pagina: document.documentElement.scrollHeight, aside: r(aside), header: r(header), main: r(main),
          voci: voci.slice(0, 30)};
}'''


def main():
    out = {}
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or '/opt/pw-browsers/chromium')
        for (w, h) in [(1366, 657), (1024, 657), (683, 657), (1440, 1000)]:
            ctx = br.new_context(viewport={'width': w, 'height': h}, device_scale_factor=1)
            pg = ctx.new_page()
            # niente caratteri da internet nelle tavole: le richieste fuori dal file si fermano
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
        print(k, 'larg', v['larghezza'], 'scrollX', v['scroll_x'], 'aside', v['aside'], 'header', v['header'], 'main', v['main'])


main()
