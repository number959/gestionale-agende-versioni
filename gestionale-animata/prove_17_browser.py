"""Prove nel browser della 1.7, su un gestionale gia' avviato con i dati di
prova (vedi LEGGIMI, «Prove»):
    python prove_17_browser.py http://127.0.0.1:5000
- scritto il codice fiscale si riempiono data, sesso e luogo di nascita, e
  sotto il campo compare «Codice fiscale corretto»;
- un codice sbagliato: niente mentre si scrivono i primi caratteri, il
  motivo al sedicesimo o uscendo dal campo;
- senza codice, con i dati, il codice si calcola; cambiati i dati si
  ricalcola; uno scritto a mano non si tocca piu';
- il luogo di nascita: suggerimenti, scelta con la tastiera, codice nel
  campo nascosto, cancellato se si riscrive il nome;
- nella prenotazione: scelto un paziente dall'elenco arrivano anche sesso e
  luogo, e il codice si controlla;
- la pagina Controllo dei codici fiscali;
- nessun errore JavaScript.
Salva pazienti nuovi nel gestionale su cui gira: usarla su un gestionale di
prova, mai su quello vero."""
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright

import codice_fiscale as CF
from datetime import date

B = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5000'
esiti = []
# un cognome nuovo a ogni giro: la prova si puo' rifare sullo stesso gestionale senza trovare doppioni
NUOVO = 'Testanuova' + ''.join(random.choice('BCDFGLMNPRSTVZ') + random.choice('AEIOU') for _ in range(2)).lower()
FINTINI = CF.calcola('Fintini', 'Prova', date(1980, 1, 1), 'M', 'F839')


def ok(n, c, d=''):
    esiti.append(bool(c))
    print(('OK ' if c else 'KO ') + n, '' if c else d)


with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
    ctx = br.new_context(viewport={'width': 1366, 'height': 900})
    ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); localStorage.setItem('guida-viste', '{\"*\":1}'); } catch (e) {}")
    pg = ctx.new_page()
    err = []
    pg.on('pageerror', lambda e: err.append(str(e)))
    pg.on('console', lambda m: err.append(m.text) if m.type == 'error' else None)

    def esito():
        return (pg.text_content('#esito-cf') or '').strip()

    def aspetta_esito(testo, ms=4000):
        try:
            pg.wait_for_function("(t) => (document.getElementById('esito-cf').textContent || '').includes(t)", arg=testo,
                                 timeout=ms)
            return True
        except Exception:
            return False

    # ------------------------------------------------ dal codice fiscale
    pg.goto(B + '/pazienti/nuovo')
    pg.fill('#cognome', 'Fintini')
    pg.fill('#nome', 'Prova')
    pg.click('#codice_fiscale')
    pg.keyboard.type(FINTINI.lower(), delay=15)
    pronto = aspetta_esito('Codice fiscale corretto')
    ok('scritto il codice: «Codice fiscale corretto»', pronto, esito())
    ok('dal codice: data, sesso e luogo di nascita', (pg.input_value('#data_nascita'), pg.input_value('#sesso'),
       pg.input_value('#luogo_nascita'), pg.input_value('#luogo_nascita_testo')) == ('1980-01-01', 'M', 'F839', 'Napoli (NA)'),
       (pg.input_value('#data_nascita'), pg.input_value('#sesso'), pg.input_value('#luogo_nascita')))
    pg.fill('#nome', 'Pietro')
    ok('nome che non torna: avviso sotto il campo', aspetta_esito('Le lettere del nome non tornano'), esito())

    # ------------------------------------------------ codice sbagliato
    pg.goto(B + '/pazienti/nuovo')
    pg.click('#codice_fiscale')
    pg.keyboard.type('FNTPRV80', delay=15)
    pg.wait_for_timeout(700)
    ok('mentre si scrivono i primi caratteri nessun errore', 'non' not in esito().lower() or esito().startswith('Dal codice'),
       esito())
    pg.keyboard.type('A01F839X', delay=15)
    ok('al sedicesimo carattere: il motivo', aspetta_esito('sarebbe «W»'), esito())
    pg.fill('#codice_fiscale', 'FNTPRV80A01')
    pg.press('#codice_fiscale', 'Tab')
    ok('uscendo dal campo con un codice corto: il motivo', aspetta_esito('ne servono 16'), esito())

    # ------------------------------------------------ calcolo dai dati
    pg.goto(B + '/pazienti/nuovo')
    pg.fill('#cognome', 'Esempietti')
    pg.fill('#nome', 'Maria Rosa')
    pg.select_option('#sesso', 'F')
    pg.fill('#data_nascita', '1975-03-12')
    pg.click('#luogo_nascita_testo')
    pg.keyboard.type('s giorgio cre', delay=30)
    try:
        pg.wait_for_selector('#suggerimenti-luogo button', timeout=4000)
        voci = pg.locator('#suggerimenti-luogo button').all_text_contents()
    except Exception:
        voci = []
    ok('luogo: i suggerimenti', voci and voci[0].startswith('San Giorgio a Cremano (NA)'), voci)
    pg.keyboard.press('Enter')
    atteso = CF.calcola('Esempietti', 'Maria Rosa', date(1975, 3, 12), 'F', 'H892')
    calcolato = aspetta_esito('Calcolato dai dati')
    ok('scelto il luogo con la tastiera: codice nel campo nascosto e codice fiscale calcolato',
       calcolato and pg.input_value('#luogo_nascita') == 'H892' and pg.input_value('#codice_fiscale') == atteso,
       (pg.input_value('#luogo_nascita'), pg.input_value('#codice_fiscale'), esito()))
    pg.fill('#data_nascita', '1975-03-13')
    pg.dispatch_event('#data_nascita', 'change')
    atteso2 = CF.calcola('Esempietti', 'Maria Rosa', date(1975, 3, 13), 'F', 'H892')
    try:
        pg.wait_for_function("(v) => document.getElementById('codice_fiscale').value === v", arg=atteso2, timeout=4000)
        ricalcolato = True
    except Exception:
        ricalcolato = False
    ok('cambiata la data: ricalcolato', ricalcolato, pg.input_value('#codice_fiscale'))
    primi = atteso2[:14] + 'V'
    omocodico = primi + CF.carattere_controllo(primi)
    pg.fill('#codice_fiscale', omocodico)
    aspetta_esito('Codice fiscale corretto')
    pg.fill('#data_nascita', '1975-03-12')
    pg.dispatch_event('#data_nascita', 'change')
    pg.wait_for_timeout(1200)
    ok('il codice scritto a mano non si tocca più', pg.input_value('#codice_fiscale') == omocodico,
       pg.input_value('#codice_fiscale'))
    pg.click('#luogo_nascita_testo')
    pg.keyboard.press('End')
    pg.keyboard.type('x')
    ok('riscritto il nome del luogo: il codice nascosto si toglie', pg.input_value('#luogo_nascita') == '',
       pg.input_value('#luogo_nascita'))

    # ------------------------------------------------ salvataggio
    pg.goto(B + '/pazienti/nuovo')
    pg.fill('#cognome', NUOVO)
    pg.fill('#nome', 'Ugo')
    pg.fill('#telefono', '333%07d' % random.randint(0, 9999999))
    pg.select_option('#sesso', 'M')
    pg.fill('#data_nascita', '1969-07-04')
    pg.fill('#luogo_nascita_testo', 'Napoli')
    pg.press('#luogo_nascita_testo', 'Tab')
    calcolato = CF.calcola(NUOVO, 'Ugo', date(1969, 7, 4), 'M', 'F839')
    try:
        pg.wait_for_function("(v) => document.getElementById('codice_fiscale').value === v", arg=calcolato, timeout=5000)
        scritto = True
    except Exception:
        scritto = False
    ok('luogo scritto senza sceglierlo: riconosciuto, codice calcolato', scritto and pg.input_value('#luogo_nascita') == 'F839',
       (pg.input_value('#luogo_nascita'), pg.input_value('#codice_fiscale')))
    with pg.expect_navigation():
        pg.click('form.modulo-paziente button.primario[type="submit"]')
    messaggio = pg.text_content('body') or ''
    ok('salvato: «Codice fiscale calcolato dai dati»', 'Codice fiscale calcolato dai dati: %s' % calcolato in messaggio,
       messaggio[:300])

    # ------------------------------------------------ prenotazione
    pg.goto(B + '/appuntamento')
    pg.click('#cerca_paziente')
    pg.keyboard.type(NUOVO, delay=30)
    try:
        pg.wait_for_selector('#suggerimenti button', timeout=4000)
        pg.keyboard.press('Enter')
        scelto = True
    except Exception:
        scelto = False
    pronto = scelto and aspetta_esito('Codice fiscale corretto')
    ok('prenotazione: scelto dall\'elenco arrivano sesso e luogo, il codice si controlla',
       pronto and (pg.input_value('#sesso'), pg.input_value('#luogo_nascita'), pg.input_value('#luogo_nascita_testo')) ==
       ('M', 'F839', 'Napoli (NA)'), (pg.input_value('#sesso'), pg.input_value('#luogo_nascita'), esito()))

    # ------------------------------------------------ controllo dell'archivio
    pg.goto(B + '/pazienti')
    pg.click('a[data-guida="controllo-codici"]')
    pg.wait_for_url(re.compile(r'.*/pazienti/codici-fiscali$'), timeout=5000)
    t = pg.text_content('body') or ''
    ok('pagina Controllo dei codici fiscali dalla pagina Pazienti', 'Non validi' in t and 'Senza codice fiscale' in t, t[:200])

    for u in ('/pazienti/nuovo', '/appuntamento', '/pazienti/codici-fiscali', '/aiuto/codice-fiscale',
              '/aiuto/controllo-codici-fiscali', '/aiuto/novita'):
        pg.goto(B + u)
        pg.wait_for_timeout(400)
    ok('nessun errore JavaScript', not err, err[:3])
    br.close()
print('\n%d prove nel browser, %d superate' % (len(esiti), sum(esiti)))
sys.exit(0 if all(esiti) else 1)
