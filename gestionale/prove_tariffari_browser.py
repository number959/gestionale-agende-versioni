"""Prove nel browser dei tariffari (1.12.6), su un gestionale gia' avviato con i dati di prova (strumenti/demo.py):
    python prove_tariffari_browser.py http://127.0.0.1:5001
- Cassa -> Tariffari: il controllo dei medici (il tariffario di prova del Dott. Gallo attivo, quello della Dott.ssa
  Monti spento), sul telefono senza scorrimento laterale;
- nel modulo di prenotazione il prezzo del tariffario si propone da solo scegliendo medico e prestazione, quello del
  listino con un medico senza tariffario, un importo scritto a mano resta;
- «Carica tariffario» con un Excel inventato: l'anteprima propone il medico e la prestazione, si salva, il prezzo si
  propone nella prenotazione; poi si elimina, e i dati di prova restano come prima;
- la stampa del tariffario; nessun errore JavaScript."""
import os
import sys
import tempfile

from openpyxl import Workbook
from playwright.sync_api import sync_playwright

B = (sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5000').rstrip('/')
esiti = []


def ok(n, c, d=''):
    esiti.append(bool(c))
    print(('OK ' if c else 'KO ') + n, '' if c else d)


def valore_di(pg, sel, inizio):
    opzioni = pg.locator(sel).evaluate('e => Array.from(e.options).map(o => [o.value, o.text])')
    return next((v for v, t in opzioni if t.startswith(inizio)), None)


cartella = tempfile.mkdtemp(prefix='prove_tariffari_browser_')
FILE = os.path.join(cartella, 'tariffario-prova-guarino.xlsx')
wb = Workbook()
ws = wb.active
ws.title = 'Tariffario'
for r in (('TARIFFARIO DOTT. GUARINO', None), ('Prestazione', 'Prezzo (€)'), ('Visita diabetologica', 95),
          ('Visita di controllo', 65), ('Piano alimentare', 40)):
    ws.append(list(r))
wb.save(FILE)

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
    pg = br.new_page(viewport={'width': 1366, 'height': 900})
    err = []
    pg.on('pageerror', lambda e: err.append(str(e)))
    pg.on('dialog', lambda d: d.accept())
    pg.goto(B + '/cassa/tariffari')
    righe = {pg.locator('tr[data-medico]').nth(i).locator('td').first.inner_text().strip():
             pg.locator('tr[data-medico]').nth(i).get_attribute('class') for i in range(pg.locator('tr[data-medico]').count())}
    # (nell'animata le righe hanno anche la classe dell'animazione d'entrata)
    def classi(nome):
        return (righe.get(nome) or '').split()
    ok('controllo dei medici: il tariffario di Gallo attivo, quello di Monti spento, gli altri senza',
       'stato-tariffario-attivo' in classi('Gallo') and 'stato-tariffario-spento' in classi('Monti')
       and 'stato-tariffario-nessuno' in classi('Galasso'), righe)
    # il prezzo nella prenotazione
    pg.goto(B + '/appuntamento?data=2030-01-08&ora=10:00&risorsa=3&struttura=1')
    gallo, galasso, guarino = (valore_di(pg, '#operatore', x) for x in ('Gallo', 'Galasso', 'Guarino'))
    card, ctrl, diab = (valore_di(pg, '#prestazione', x) for x in ('Visita cardiologica', 'Controllo', 'Visita diabetologica'))
    pg.select_option('#operatore', gallo)
    pg.select_option('#prestazione', card)
    ok('prenotazione: Gallo e visita cardiologica, il prezzo del suo tariffario', pg.input_value('#importo') == '110,00',
       pg.input_value('#importo'))
    pg.select_option('#prestazione', ctrl)
    ok('prenotazione: Gallo e controllo (voce «Visita di controllo»)', pg.input_value('#importo') == '70,00',
       pg.input_value('#importo'))
    pg.select_option('#operatore', galasso)
    ok('prenotazione: un medico senza tariffario torna al listino (qui vuoto)', pg.input_value('#importo') == '',
       pg.input_value('#importo'))
    pg.select_option('#operatore', gallo)
    pg.fill('#importo', '95,00')
    pg.select_option('#prestazione', card)
    ok('prenotazione: un importo scritto a mano non si tocca', pg.input_value('#importo') == '95,00', pg.input_value('#importo'))
    # Carica tariffario
    pg.goto(B + '/cassa/tariffari')
    pg.set_input_files('input[name="file"]', FILE)
    pg.click('button:has-text("Carica tariffario")')
    pg.wait_for_selector('.tariffario-proposto')
    spuntato = pg.locator('input[name="medici_0"][value="%s"]' % guarino).is_checked()
    scelta = pg.locator('select[name="prestazione_0_0"]').evaluate('e => e.options[e.selectedIndex].text')
    scelta_ctrl = pg.locator('select[name="prestazione_0_1"]').evaluate('e => e.options[e.selectedIndex].text')
    ok('anteprima: proposti Guarino e le prestazioni Visita diabetologica e Controllo',
       spuntato and scelta == 'Visita diabetologica' and scelta_ctrl == 'Controllo', (spuntato, scelta, scelta_ctrl))
    pg.click('button:has-text("Salva i tariffari")')
    pg.wait_for_load_state()
    ok('salvato: torna all\'elenco con il messaggio e il tariffario nuovo',
       pg.url.endswith('/cassa/tariffari') and 'Tariffari caricati: Dott. Guarino (3 voci, 1 medico)' in pg.inner_text('.avvisi')
       and pg.locator('a', has_text='Dott. Guarino').count() >= 1, pg.url)
    pg.goto(B + '/appuntamento?data=2030-01-08&ora=10:00&risorsa=3&struttura=1')
    pg.select_option('#operatore', guarino)
    pg.select_option('#prestazione', diab)
    ok('prenotazione: il prezzo del tariffario appena caricato', pg.input_value('#importo') == '95,00', pg.input_value('#importo'))
    # la stampa del tariffario di prova
    pg.goto(B + '/cassa/tariffari')
    pg.locator('a', has_text='Dott. Gallo').first.click()
    pg.wait_for_selector('.scheda-tariffario')
    pg.click('.pagina-tariffari p.sotto a[href$="/stampa"]')
    pg.wait_for_selector('.tariffario-stampa')
    stampa = pg.inner_text('.tariffario-stampa')
    ok('stampa: titolo, sezioni, prezzi e note', 'Tariffario · Dott. Gallo' in stampa and '€ 110,00' in stampa
       and 'Esami' in stampa and 'pacchetto intero' in stampa, stampa[:200])
    # si elimina il tariffario caricato: i dati di prova tornano come prima
    pg.goto(B + '/cassa/tariffari')
    pg.locator('a', has_text='Dott. Guarino').first.click()
    pg.wait_for_selector('.scheda-tariffario')
    pg.click('button:has-text("Elimina il tariffario")')
    pg.wait_for_load_state()
    ok('eliminato: non c\'è più', pg.locator('a', has_text='Dott. Guarino').count() == 0, pg.url)
    pg.set_viewport_size({'width': 390, 'height': 844})
    pg.goto(B + '/cassa/tariffari')
    ok('sul telefono la pagina dei tariffari non scorre di lato',
       pg.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), pg.evaluate('document.documentElement.scrollWidth'))
    ok('nessun errore JavaScript', not err, err[:3])
    br.close()

print('%d prove nel browser, %d superate' % (len(esiti), sum(esiti)))
sys.exit(0 if all(esiti) else 1)
