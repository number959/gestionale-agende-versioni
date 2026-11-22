# Il menu a sole icone (72 px) nelle tavole a 1024 e 683: la pagina smette di scorrere di lato?
import os
from playwright.sync_api import sync_playwright
V = os.path.dirname(os.path.abspath(__file__))
CSS = '''x-dc > div{grid-template-columns:72px minmax(0,1fr)!important}
aside{padding:16px 8px!important;overflow:hidden}
aside > a:first-child img{width:52px!important;height:auto!important}
aside > a:first-child > span, aside > span, aside > div:last-child, aside nav a span{display:none!important}
aside nav a{justify-content:center;padding:0!important}'''
with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    for w in (1024, 683):
        pg = br.new_page(viewport={'width': w, 'height': 657})
        pg.route('**/*', lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())
        for nome in ('Nefro-Agenda1-Giorno', 'Seg1-Conferme', 'Conf1-Anagrafiche', 'Paz1-Elenco', 'Nefro-Dashboard1-Oggi', 'Nefro-Ambulatori1-Pianificazione'):
            pg.goto('file://' + os.path.join(V, 'tavole', nome + '.dc.html'))
            pg.wait_for_function('window.__pronto === true')
            prima = pg.evaluate('[document.documentElement.scrollWidth, document.querySelector("main").clientWidth, document.querySelector("header").offsetHeight]')
            pg.add_style_tag(content=CSS); pg.evaluate("document.querySelector('aside').parentElement.style.gridTemplateColumns = '72px minmax(0,1fr)'")
            pg.wait_for_timeout(150)
            dopo = pg.evaluate('[document.documentElement.scrollWidth, document.querySelector("main").clientWidth, document.querySelector("header").offsetHeight]')
            if nome == 'Seg1-Conferme':
                pg.screenshot(path=os.path.join(V, 'foto', 'prova-icone-%s-%d.png' % (nome, w)))
            print(w, '%-34s menu 248: largo %4d contenuto %4d barra %3d | menu 72: largo %4d contenuto %4d barra %3d' % ((nome,) + tuple(prima) + tuple(dopo)))
        pg.close()
    br.close()
