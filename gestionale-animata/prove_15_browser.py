"""Prove nel browser della 1.5, su un gestionale gia' avviato con i dati di
prova:
    python prove_15_browser.py http://127.0.0.1:5000
- il codice fiscale riempie da solo la data di nascita (modulo di
  prenotazione e scheda del paziente), senza toccare una data gia' scritta;
- scegliendo un paziente dall'elenco si riempiono anche nascita, codice
  fiscale e indirizzo;
- i pulsanti che mandano un messaggio dicono "Invio in corso…";
- nessun errore JavaScript nelle pagine nuove.
Non usarla sul database vero."""
import os, re, sys, datetime as dt
from playwright.sync_api import sync_playwright
B = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5000'
esiti = []
def ok(n, c, d=''):
    esiti.append(bool(c)); print(('OK ' if c else 'KO ') + n, '' if c else d)
oggi = dt.date.today()
domani = oggi + dt.timedelta(days=1)

def aspetta_valore(pg, sel, valore, ms=4000):
    """Dalla 1.7 il codice si controlla nel programma, non nella pagina: la data arriva dopo un attimo."""
    try:
        pg.wait_for_function("(a) => document.querySelector(a[0]).value === a[1]", arg=[sel, valore], timeout=ms)
    except Exception:
        pass


def cf_valido(primi15):
    dispari = dict(zip('0123456789', [1, 0, 5, 7, 9, 13, 15, 17, 19, 21]))
    dispari.update(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ', [1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23]))
    pari = {**{str(i): i for i in range(10)}, **{c: i for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}}
    somma = sum((dispari if i % 2 == 0 else pari)[c] for i, c in enumerate(primi15))
    return primi15 + chr(65 + somma % 26)

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
    ctx = br.new_context(viewport={'width': 1366, 'height': 900})
    ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); localStorage.setItem('guida-viste', '{\"*\":1}'); } catch (e) {}")
    pg = ctx.new_page(); err = []
    pg.on('pageerror', lambda e: err.append(str(e))); pg.on('console', lambda m: err.append(m.text) if m.type == 'error' else None)
    nuovo = B + '/appuntamento?data=%s&ora=11:00&risorsa=1&struttura=1' % domani
    pg.goto(nuovo); pg.wait_for_timeout(300)
    for campo, nascita in ((cf_valido('FNTMRA85D61F839'), '1985-04-21'), (cf_valido('FNTMRCULA1RF839'), '1980-01-15'),
                           (cf_valido('FNTMRC30A15F839'), '1930-01-15')):
        pg.fill('#codice_fiscale', '')
        pg.fill('#data_nascita', '')
        pg.type('#codice_fiscale', campo.lower(), delay=5)
        aspetta_valore(pg, '#data_nascita', nascita)
        ok('codice fiscale %s → nascita %s' % (campo, nascita), pg.input_value('#data_nascita') == nascita, pg.input_value('#data_nascita'))
    pg.fill('#data_nascita', '1990-01-01'); pg.fill('#codice_fiscale', ''); pg.type('#codice_fiscale', cf_valido('FNTMRA85D61F839'), delay=5)
    pg.wait_for_timeout(1200)
    ok('una data già scritta non si tocca', pg.input_value('#data_nascita') == '1990-01-01', pg.input_value('#data_nascita'))
    giusto = cf_valido('FNTMRA85D61F839')
    sbagliato = giusto[:15] + ('A' if giusto[15] != 'A' else 'B')
    pg.fill('#codice_fiscale', ''); pg.fill('#data_nascita', ''); pg.type('#codice_fiscale', sbagliato, delay=5)
    pg.wait_for_timeout(1200)
    ok('codice sbagliato: nessuna data inventata', pg.input_value('#data_nascita') == '', pg.input_value('#data_nascita'))
    # scelta dall'elenco
    pg.goto(nuovo); pg.wait_for_timeout(300)
    pg.type('#cerca_paziente', 'sepe', delay=30); pg.wait_for_timeout(700)
    ok('suggerimenti', pg.locator('#suggerimenti button').count() >= 1)
    pg.locator('#suggerimenti button').first.dispatch_event('mousedown'); pg.wait_for_timeout(200)
    valori = {k: pg.input_value(k) for k in ('#paziente', '#data_nascita', '#codice_fiscale', '#indirizzo_paziente')}
    ok('scelto: nascita, codice fiscale e indirizzo riempiti', valori['#paziente'] == 'Sepe' and valori['#data_nascita'] == '1978-03-12'
       and valori['#codice_fiscale'] == 'SPSNNA78C52F839X' and valori['#indirizzo_paziente'] == 'Via Manzoni 12, 80123 Napoli', valori)
    # scheda del paziente
    pg.goto(B + '/pazienti/nuovo'); pg.wait_for_timeout(300)
    pg.type('#codice_fiscale', cf_valido('FNTMRA85D61F839'), delay=5)
    aspetta_valore(pg, '#data_nascita', '1985-04-21')
    ok('scheda del paziente: anche qui la data si riempie', pg.input_value('#data_nascita') == '1985-04-21', pg.input_value('#data_nascita'))
    ok('scheda del paziente: campo indirizzo', pg.locator('#indirizzo').count() == 1)
    # i pulsanti di invio dicono che lavorano: qui l'invio vero si ferma, conta il pulsante
    pg.goto(B + '/invii'); pg.wait_for_timeout(300)
    pg.evaluate("document.querySelector('[data-guida=\"email-prova\"]').addEventListener('submit', function (e) { e.preventDefault(); })")
    pulsante = pg.locator('[data-guida="email-prova"] button[type="submit"]')
    pulsante.click(); pg.wait_for_timeout(200)
    ok('il pulsante dice "Invio in corso…" e non si preme due volte', pulsante.text_content() == 'Invio in corso…' and pulsante.is_disabled(),
       pulsante.text_content())
    # una email per medico: dal gruppo del medico la nuova ha gia' il medico; Crea in fondo fa lo stesso
    pg.goto(B + '/invii'); pg.wait_for_timeout(300)
    with pg.expect_navigation():
        pg.locator('.gruppo-regole p.azioni-gruppo a').first.click()
    scelto = pg.evaluate("document.querySelector('#operatore').selectedOptions[0].textContent")
    ok('Nuova email per… dal gruppo: medico già scelto', pg.url.split('?')[1].startswith('medico=') and 'Nuova email per ' + scelto.strip()
       in pg.locator('h1').text_content(), (pg.url, scelto))
    pg.goto(B + '/invii'); pg.wait_for_timeout(300)
    form = pg.locator('form[data-guida="nuova-regola"]')
    form.locator('select[name="medico"]').select_option(index=1)
    voluto = form.locator('select[name="medico"]').evaluate("s => s.selectedOptions[0].textContent")
    with pg.expect_navigation():
        form.locator('button[type="submit"]').click()
    ok('Nuova email per [medico] Crea', pg.evaluate("document.querySelector('#operatore').selectedOptions[0].textContent").strip()
       == voluto.strip(), voluto)
    # i caratteri del sito, dal programma stesso (niente internet)
    pg.goto(B + '/giorno/%s?struttura=1' % domani); pg.wait_for_timeout(400)
    caratteri = pg.evaluate("""() => ({inter: document.fonts.check('14px Inter'), manrope: document.fonts.check('30px Manrope'),
        caricati: [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family.replace(/["']/g, '')),
        corpo: getComputedStyle(document.body).fontFamily, titolo: getComputedStyle(document.querySelector('h1.giorno')).fontFamily})""")
    ok('caratteri Inter e Manrope caricati dal programma', caratteri['inter'] and caratteri['manrope'] and
       {'Inter', 'Manrope'} <= set(caratteri['caricati']) and caratteri['corpo'].strip('"\'').startswith('Inter') and
       caratteri['titolo'].strip('"\'').startswith('Manrope'), caratteri)
    # pagine nuove senza errori
    for u in ('/invii', '/invii/regole/1', '/invii/regole/nuova', '/invii/regole/nuova?medico=1', '/anagrafiche/medici/1',
              '/conferme?data=%s' % domani, '/mese/%s' % oggi.strftime('%Y-%m'), '/aiuto/email-gmail', '/aiuto/email-automatiche',
              '/aiuto/email-per-medico', '/aiuto/promemoria', '/aiuto/mese', '/aiuto/aggiornare', '/aiuto'):
        pg.goto(B + u); pg.wait_for_timeout(250)
    ok('nessun errore JavaScript', not err, err[:3])
    br.close()
print('\n%d prove nel browser, %d superate' % (len(esiti), sum(esiti)))
sys.exit(0 if all(esiti) else 1)
