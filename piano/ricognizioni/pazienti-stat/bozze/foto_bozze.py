# Foto delle bozze (porta 5143, copia in prova/) e controlli nel browser: errori JS, codice fiscale dal vivo,
# suggerimenti del luogo non coperti, ul.numeri per l'animata, <td>X,Y</td> della prova delle statistiche.
import os, re, json
from playwright.sync_api import sync_playwright
V = os.path.dirname(os.path.abspath(__file__))
B = 'http://127.0.0.1:5143'
pagine = [('pazienti', '/pazienti'), ('paziente-1-documenti', '/pazienti/1'), ('paziente-3-cuomo', '/pazienti/3'),
          ('paziente-17-elimina', '/pazienti/17'), ('paziente-nuovo', '/pazienti/nuovo'), ('unisci-altro', '/pazienti/29/unisci?altro=30'),
          ('codici-fiscali', '/pazienti/codici-fiscali'), ('statistiche', '/statistiche'), ('pazienti-nessuno', '/pazienti?q=zzzz')]
esiti = {}
with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
    for tema in ('chiaro', 'scuro'):
        for nome, url in pagine:
            for (w, h, intera, suff) in ((1366, 657, False, '1366'), (1440, 900, True, '1440'), (683, 657, False, '683')):
                if tema == 'scuro' and suff != '1366':
                    continue
                if suff == '683' and nome not in ('paziente-3-cuomo', 'statistiche', 'pazienti'):
                    continue
                ctx = br.new_context(viewport={'width': w, 'height': h}, locale='it-IT')
                pg = ctx.new_page()
                pg.add_init_script("try{localStorage.setItem('guida-benvenuto','1');localStorage.setItem('guida-viste','{\"*\":1}');%s}catch(e){}"
                                   % ("localStorage.setItem('gestionale-tema','scuro');" if tema == 'scuro' else ''))
                err = []
                pg.on('pageerror', lambda e: err.append(str(e)))
                pg.on('console', lambda m: err.append(m.text) if m.type == 'error' else None)
                pg.goto(B + url)
                pg.wait_for_timeout(500)
                pg.screenshot(path=os.path.join(V, 'foto', 'bozza-%s-%s-%s.png' % (nome, suff, tema)), full_page=intera)
                largo = pg.evaluate('document.documentElement.scrollWidth')
                esiti['%s %s %s' % (nome, suff, tema)] = {'errori': err, 'scorre_di_lato': largo > w}
                ctx.close()
    # codice fiscale dal vivo e suggerimenti del luogo nella scheda nuova
    ctx = br.new_context(viewport={'width': 1366, 'height': 657}, locale='it-IT')
    pg = ctx.new_page()
    pg.add_init_script("try{localStorage.setItem('guida-benvenuto','1');localStorage.setItem('guida-viste','{\"*\":1}')}catch(e){}")
    pg.goto(B + '/pazienti/nuovo')
    pg.fill('#cognome', 'Fintini'); pg.fill('#nome', 'Prova')
    pg.click('#luogo_nascita_testo'); pg.keyboard.type('san gi', delay=40)
    pg.wait_for_selector('#suggerimenti-luogo button', timeout=5000)
    b = pg.locator('#suggerimenti-luogo button').first.bounding_box()
    sopra = pg.evaluate('([x, y]) => { const e = document.elementFromPoint(x, y); return e && !!e.closest("#suggerimenti-luogo"); }',
                        [b['x'] + b['width'] / 2, b['y'] + b['height'] / 2])
    pg.screenshot(path=os.path.join(V, 'foto', 'bozza-paziente-nuovo-luogo-1366-chiaro.png'))
    esiti['suggerimenti del luogo non coperti'] = sopra
    pg.keyboard.press('Escape')
    pg.fill('#codice_fiscale', 'FNTPRV80A01F839X'); pg.locator('#codice_fiscale').blur(); pg.wait_for_timeout(900)
    esiti['esito cf'] = pg.text_content('#esito-cf')
    esiti['classe esito cf'] = pg.get_attribute('#esito-cf', 'class')
    esiti['cf_calcolato dentro il modulo'] = pg.evaluate("!!document.querySelector('form.modulo-paziente input[name=cf_calcolato]')")
    ctx.close()
    # animata e prova delle statistiche, sull'HTML
    ctx = br.new_context(); pg = ctx.new_page(); pg.goto(B + '/statistiche')
    esiti['ul.numeri b in statistiche'] = pg.evaluate("[...document.querySelectorAll('ul.numeri b')].map(b => b.textContent)")
    esiti['barra-dato span'] = pg.evaluate("document.querySelectorAll('.barra-dato span').length")
    esiti['a.bottone Riepilogo del mese'] = pg.evaluate("[...document.querySelectorAll('a.bottone')].some(a => a.textContent.includes('Riepilogo del mese'))")
    pg.goto(B + '/pazienti/3')
    esiti['ul.numeri b in In breve'] = pg.evaluate("[...document.querySelectorAll('ul.numeri b')].map(b => b.textContent)")
    ctx.close()
    br.close()
import urllib.request
html = urllib.request.urlopen(B + '/statistiche').read().decode()
esiti['celle <td>X,Y</td> (prove_funzioni.py:1270)'] = len(re.findall(r'<td>\d+,\d</td>', html))
esiti['celle <td class="v-numero">X,Y</td>'] = len(re.findall(r'<td class="v-numero">\d+,\d</td>', html))
testo = ' '.join(re.sub(r'<[^>]+>', ' ', html).split())
i = testo.find('Indirizzati alle altre strutture')
esiti['testo dopo «Indirizzati alle altre strutture»'] = testo[i:i+90] if i >= 0 else '(niente indirizzati nei dati di prova)'
nuovo = urllib.request.urlopen(B + '/pazienti/nuovo').read().decode()
esiti['frammenti di prove_17.py:826-828'] = all(f in nuovo for f in ('id="sesso"', 'id="luogo_nascita_testo"', 'id="luogo_nascita"', 'id="esito-cf"',
    'data-controllo="/pazienti/codice-fiscale"', 'data-indirizzo="/pazienti/luoghi"', 'data-guida="codice-fiscale"', 'data-guida="luogo-nascita"'))
json.dump(esiti, open(os.path.join(V, 'controlli-bozze.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps(esiti, ensure_ascii=False, indent=1))
