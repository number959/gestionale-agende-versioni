# Quanto e' alto il menu della tavola se resta fermo (sticky) in una finestra alta 657: ci sta o scorre?
import os
from playwright.sync_api import sync_playwright
T = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tavole', 'Nefro-Agenda1-Giorno.dc.html')
CASI = {
  'come la tavola (con logo del gruppo)': '',
  'senza logo del gruppo (arriva con M3)': 'aside > div:last-child{display:none!important}',
  'senza logo del gruppo, voci alte 38': 'aside > div:last-child{display:none!important} aside a{height:38px!important}',
  'senza logo del gruppo, voci 38, testata 64': 'aside > div:last-child{display:none!important} aside a{height:38px!important} aside > a:first-child{padding-bottom:6px!important;gap:4px!important}',
}
with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    for h in (657, 768):
        pg = br.new_page(viewport={'width': 1366, 'height': h})
        pg.route('**/*', lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
        for nome, css in CASI.items():
            pg.goto('file://' + T)
            pg.wait_for_function('window.__pronto === true')
            pg.add_style_tag(content='aside{position:sticky;top:0;height:100vh;overflow-y:auto;box-sizing:border-box} ' + css)
            pg.wait_for_timeout(200)
            m = pg.evaluate("""() => { const a = document.querySelector('aside');
                const ult = [...a.querySelectorAll('a')].pop(); const r = ult.getBoundingClientRect();
                return {serve: a.scrollHeight, c_e: a.clientHeight, configura_fondo: Math.round(r.bottom)}; }""")
            print(h, '%-48s' % nome, m)
        pg.close()
    br.close()
