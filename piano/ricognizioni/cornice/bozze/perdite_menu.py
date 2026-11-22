# Se il menu nuovo tiene la classe «menu» (nav.menu serve alla guida e alle prove), quali regole vecchie di
# stile.css / tema-scuro.css lo toccano ancora, anche dentro @layer vecchio? Esperimento sulla tavola
# Nefro-Agenda1-Giorno: i suoi stili (in linea) fanno da veste.css; si aggiungono i fogli vecchi in un layer e la
# classe «menu» alle tre nav, poi si confrontano gli stili calcolati delle voci, in chiaro e in scuro.
import os, json
from playwright.sync_api import sync_playwright

V = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(V, 'tavole', 'Nefro-Agenda1-Giorno.dc.html')
R = '/home/user/gestionale-agende-versioni/gestionale/static/'
vecchio = open(R + 'stile.css').read() + '\n' + open(R + 'tema-scuro.css').read()
PROPRIETA = ['display', 'color', 'background-color', 'opacity', 'padding-top', 'padding-bottom', 'border-bottom-width',
             'border-bottom-color', 'font-size', 'font-weight', 'gap', 'flex-wrap']
MISURA = """(p) => [...document.querySelectorAll('aside nav, aside nav a')].map(e => {
   const c = getComputedStyle(e); const o = {t: e.tagName + ' ' + (e.textContent || '').trim().slice(0, 12)};
   p.forEach(k => o[k] = c.getPropertyValue(k)); return o; })"""

with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = br.new_page(viewport={'width': 1366, 'height': 657})
    pg.route('**/*', lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
    for scuro in (False, True):
        pg.goto('file://' + T)
        pg.wait_for_function('window.__pronto === true')
        if scuro:
            pg.evaluate("document.documentElement.classList.add('scuro')")
        prima = pg.evaluate(MISURA, PROPRIETA)
        pg.evaluate("""(css) => { const s = document.createElement('style'); s.textContent = '@layer vecchio {\\n' + css + '\\n}';
            document.head.prepend(s);
            document.querySelectorAll('aside nav').forEach(n => n.classList.add('menu'));
            const a = document.querySelector('aside nav a[aria-current]'); if (a) a.classList.add('attivo'); }""", vecchio)
        pg.wait_for_timeout(100)
        dopo = pg.evaluate(MISURA, PROPRIETA)
        diverse = {}
        for a, b in zip(prima, dopo):
            for k in PROPRIETA:
                if a[k] != b[k]:
                    diverse.setdefault(k, set()).add('%s: %s -> %s' % (a['t'][:16], a[k], b[k]))
        print('== tema', 'scuro' if scuro else 'chiaro', '- proprieta\' che cambiano:', sorted(diverse) or 'nessuna')
        for k, v in sorted(diverse.items()):
            for x in sorted(v)[:4]:
                print('   ', k, '|', x)
    br.close()
