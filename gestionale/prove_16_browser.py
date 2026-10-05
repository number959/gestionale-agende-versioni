"""Prove nel browser della 1.6, su un gestionale gia' avviato con i dati di
prova e un aggiornamento finto pronto (vedi LEGGIMI, «Prove»):
    python prove_16_browser.py http://127.0.0.1:5000
- «Guarda il video» apre il video grande e lo fa partire; Esc, Chiudi o un
  clic fuori lo chiudono e lo fermano; nell'indice ogni guida ha il segno
  "video"; anche le novita' aprono il loro video;
- la pagina Aggiornamenti: salvato un indirizzo il controllo parte, la pagina
  segue l'avanzamento e si ricarica da sola con «È pronta la versione …»;
- la pagina d'attesa di «Aggiorna adesso» (con le risposte del programma
  simulate): aspetta mentre il programma e' chiuso e, appena torna aggiornato,
  apre le novita'; se il Setup non parte lo dice;
- la notifica «Aggiornamento disponibile»;
- «Rimetti l'indirizzo predefinito» riporta l'indirizzo delle versioni su
  GitHub (alla fine: il controllo che parte va su internet);
- nessun errore JavaScript nelle pagine nuove.
Cambia l'indirizzo degli aggiornamenti del gestionale su cui gira: usarla su un
gestionale di prova, mai su quello vero."""
import hashlib
import json
import os
import random
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright

import guida
import novita
import aggiornamenti as AG

B = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5000'
esiti = []


def ok(n, c, d=''):
    esiti.append(bool(c))
    print(('OK ' if c else 'KO ') + n, '' if c else d)


def pagina_attesa(da, a, avviato):
    """La pagina d'attesa vera (il template del programma), senza avviare niente."""
    import app as A
    A.app.config['TESTING'] = True
    with A.app.test_request_context('/aggiornamenti/aggiorna', method='POST'):
        from flask import render_template
        import viste
        from modelli import crea_sessione
        S = crea_sessione('sqlite:///' + os.path.join(tempfile.mkdtemp(), 'attesa.db'))
        A.Sessione, A._registro = S, None
        viste._sessionmaker = lambda: S
        return render_template('aggiornamento_in_corso.html', da=da, a=a, avviato=avviato,
                               copia='agende-prova-prima-di-aggiornare.db', sezione='aggiornamenti')


with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None, args=['--autoplay-policy=no-user-gesture-required'])
    ctx = br.new_context(viewport={'width': 1366, 'height': 900})
    ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); localStorage.setItem('guida-viste', '{\"*\":1}'); } catch (e) {}")
    pg = ctx.new_page()
    err = []
    pg.on('pageerror', lambda e: err.append(str(e)))
    pg.on('console', lambda m: err.append(m.text) if m.type == 'error' else None)

    # ------------------------------------------------------------ videoguide
    pg.goto(B + '/aiuto/prenotare')
    pg.wait_for_timeout(300)
    pg.click('a[data-guida="guarda-video"]')
    pg.wait_for_timeout(300)
    aperto = pg.evaluate("() => { const d = document.querySelector('dialog.finestra-video'); return d && d.open; }")
    src = pg.evaluate("() => document.querySelector('dialog.finestra-video video').getAttribute('src')")
    ok('Guarda il video: finestra aperta con il video della guida', aperto and src == '/static/video/prenotare.webm', (aperto, src))
    pg.wait_for_function("() => document.querySelector('dialog.finestra-video video').currentTime > 0.8", timeout=8000)
    dim = pg.evaluate("() => { const v = document.querySelector('dialog.finestra-video video'); return [v.videoWidth, v.videoHeight, v.duration]; }")
    ok('il video parte da solo e si legge (1366×768)', dim[0] == 1366 and dim[1] == 768 and dim[2] > 20, dim)
    titolo = pg.text_content('dialog.finestra-video .testa-video b')
    ok('nella finestra il titolo della guida', titolo == guida.PER_SLUG['prenotare']['titolo'], titolo)
    pg.keyboard.press('Escape')
    pg.wait_for_timeout(300)
    stato = pg.evaluate("() => { const d = document.querySelector('dialog.finestra-video'); return [d.open, d.querySelector('video').paused]; }")
    ok('Esc chiude la finestra e ferma il video', stato == [False, True], stato)
    pg.click('a[data-guida="guarda-video"]')
    pg.wait_for_timeout(400)
    t0 = pg.evaluate("() => document.querySelector('dialog.finestra-video video').currentTime")
    ok('riaperto, il video riparte dall\'inizio', t0 < 1.5, t0)
    pg.mouse.click(8, 450)                       # fuori dal video: sullo sfondo scuro
    pg.wait_for_timeout(300)
    ok('un clic fuori chiude', not pg.evaluate("() => document.querySelector('dialog.finestra-video').open"))
    pg.click('a[data-guida="guarda-video"]')
    pg.wait_for_timeout(300)
    pg.click('dialog.finestra-video .testa-video button')
    pg.wait_for_timeout(300)
    ok('Chiudi chiude', not pg.evaluate("() => document.querySelector('dialog.finestra-video').open"))
    pg.goto(B + '/aiuto')
    n = pg.locator('.scheda-guida .con-video').count()
    ok('nell\'indice ogni guida ha il segno "video"', n == len(guida.ARTICOLI), n)
    pg.goto(B + '/aiuto/novita')
    primo = [x for x in novita.NOVITA[0][1] if x['guida']][0]
    pg.click('a[data-video="%s"]' % primo['titolo'])
    pg.wait_for_timeout(300)
    src = pg.evaluate("() => document.querySelector('dialog.finestra-video video').getAttribute('src')")
    ok('novità: Guarda il video apre il video della sua guida', src == '/static/video/%s.webm' % primo['guida'], src)
    pg.keyboard.press('Escape')

    # ------------------------------------------------- notifica e pagina
    # le notifiche si mostrano quattro alla volta: le altre del giorno si segnano come chiuse
    pg.goto(B + '/oggi')
    lista = pg.evaluate("() => fetch(document.getElementById('notifiche').getAttribute('data-indirizzo')).then(r => r.json())")
    agg = [x for x in lista if x['titolo'] == 'Aggiornamento disponibile']
    ok('fra le notifiche c\'è «Aggiornamento disponibile», con il collegamento alla pagina',
       len(agg) == 1 and agg[0]['link'] == '/aggiornamenti', lista)
    altre = [x['chiave'] for x in lista if x['titolo'] != 'Aggiornamento disponibile']
    pg.evaluate("(c) => sessionStorage.setItem('notifiche-chiuse', JSON.stringify(c))", altre)
    pg.reload()
    try:
        pg.wait_for_selector('.notifica:has-text("Aggiornamento disponibile")', timeout=5000)
        pg.click('.notifica:has-text("Aggiornamento disponibile") a')
        pg.wait_for_url(re.compile(r'.*/aggiornamenti$'), timeout=5000)
        notifica = True
    except Exception:
        notifica = False
    ok('la notifica si vede e porta alla pagina Aggiornamenti', notifica, pg.url)
    dove = tempfile.mkdtemp(prefix='aggiornamenti-prova-')
    nuova = '.'.join(str(x) for x in novita.numeri(AG.VERSIONE) + [7])
    dati = b'MZ' + random.Random(7).randbytes(1500000)
    open(os.path.join(dove, AG.NOME_SETUP), 'wb').write(dati)
    json.dump({'programma': 'Gestionale Agende', 'variante': AG.VARIANTE, 'versione': nuova, 'file': AG.NOME_SETUP,
               'byte': len(dati), 'sha256': hashlib.sha256(dati).hexdigest(), 'pubblicata': '2026-10-04',
               'novita': [{'versione': nuova, 'voci': [{'titolo': 'Prova del browser', 'testo': 'Una versione finta per la prova.'}]}]},
              open(os.path.join(dove, AG.MANIFESTO), 'w'))
    pg.goto(B + '/aggiornamenti')
    pg.fill('#indirizzo-aggiornamenti', dove)
    with pg.expect_navigation():
        pg.click('form[data-guida="aggiornamenti-indirizzo"] button[type="submit"]')
    try:
        pg.wait_for_selector('h2.pronta:has-text("È pronta la versione %s")' % nuova, timeout=15000)
        pronta = True
    except Exception:
        pronta = False
    ok('indirizzo salvato: controllo, avanzamento e pagina che si ricarica da sola', pronta, pg.text_content('#stato-aggiornamento'))
    ok('le novità della versione nuova nella pagina', 'Prova del browser' in (pg.text_content('#stato-aggiornamento') or ''))

    # ------------------------------------------ la pagina d'attesa
    def prova_attesa(risposte):
        html = pagina_attesa(AG.VERSIONE, nuova, 'avvio-1')
        chiamate = []

        def stato_finto(route):
            k = min(len(chiamate), len(risposte) - 1)
            chiamate.append(1)
            r = risposte[k]
            if r is None:
                route.abort()
            else:
                route.fulfill(status=200, content_type='application/json', body=json.dumps(r))
        pg.route(B + '/attesa-prova', lambda route: route.fulfill(status=200, content_type='text/html; charset=utf-8', body=html))
        pg.route(re.compile(r'.*/aggiornamenti/stato\.json.*'), stato_finto)
        pg.goto(B + '/attesa-prova')
        return chiamate

    base = {'versione': AG.VERSIONE, 'avviato': 'avvio-1', 'in_corso': False, 'scaricati': 0, 'totale': 0,
            'disponibile': nuova, 'pronto': True, 'partito': True, 'errore': None}
    chiamate = prova_attesa([base, base, None, None, dict(base, versione=nuova, avviato='avvio-2', disponibile=None)])
    try:
        pg.wait_for_url(re.compile(r'.*/aiuto/novita$'), timeout=20000)
        arrivata = True
    except Exception:
        arrivata = False
    ok('attesa: programma chiuso, poi riaperto aggiornato → si aprono le novità', arrivata and len(chiamate) >= 5,
       (pg.url, len(chiamate)))
    pg.unroute_all()
    chiamate = prova_attesa([base, dict(base, partito=False, errore='accesso negato')])
    pg.wait_for_timeout(6000)
    messaggio = pg.text_content('#messaggio-attesa') or ''
    ok('attesa: se il Setup non parte lo dice e smette di aspettare', 'Il Setup non è partito: accesso negato' in messaggio
       and pg.locator('#messaggio-attesa .rotella').count() == 0, messaggio)
    pg.unroute_all()
    chiamate = prova_attesa([base, None, dict(base, avviato='avvio-2')])      # tornato, ma la versione e' quella di prima
    try:
        pg.wait_for_url(re.compile(r'.*/aggiornamenti$'), timeout=20000)
        tornata = True
    except Exception:
        tornata = False
    ok('attesa: riaperto ma non aggiornato → pagina Aggiornamenti (che dice com\'è andata)', tornata, pg.url)
    pg.unroute_all()
    err[:] = [e for e in err if 'ERR_FAILED' not in e and 'Failed to load resource' not in e]   # le chiamate interrotte apposta

    # ------------------------------------------------- pagine senza errori
    for u in ('/aggiornamenti', '/aiuto/novita', '/aiuto/aggiornare', '/aiuto', '/aiuto/come-e-fatto', '/oggi'):
        pg.goto(B + u)
        pg.wait_for_timeout(300)

    # -------------------------- Rimetti l'indirizzo predefinito (per ultima: il controllo va su GitHub)
    pg.goto(B + '/aggiornamenti')
    rimetti = pg.locator('button[data-guida="rimetti-predefinito"]')
    ok('con un altro indirizzo c\'è «Rimetti l\'indirizzo predefinito»', rimetti.count() == 1 and rimetti.is_visible())
    with pg.expect_navigation():
        rimetti.click()
    avviso = pg.text_content('body') or ''
    for _ in range(60):                  # la pagina segue il controllo (riesce o no secondo la rete) e si ricarica
        try:
            if pg.get_attribute('#stato-aggiornamento', 'data-in-corso', timeout=2000) == '0':
                break
        except Exception:
            pass
        pg.wait_for_timeout(1000)
    valore = pg.input_value('#indirizzo-aggiornamenti')
    t = pg.text_content('form[data-guida="aggiornamenti-indirizzo"]') or ''
    ok('Rimetti: avviso, nel campo l\'indirizzo delle versioni su GitHub, il pulsante sparisce',
       'Rimesso l\'indirizzo predefinito' in avviso and valore == AG.INDIRIZZO_PREDEFINITO
       and 'È l\'indirizzo predefinito' in t and pg.locator('button[data-guida="rimetti-predefinito"]').count() == 0,
       (valore, avviso[:200], t[:200]))
    ok('nessun errore JavaScript', not err, err[:3])
    br.close()
print('\n%d prove nel browser, %d superate' % (len(esiti), sum(esiti)))
sys.exit(0 if all(esiti) else 1)
