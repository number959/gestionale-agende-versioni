# -*- coding: utf-8 -*-
"""Nel browser vero: una pagina di un altro sito (qui su un'altra porta dello
stesso PC, il caso piu' vicino) prova a mandare moduli al gestionale in tre
modi, e il gestionale li deve rifiutare tutti; i moduli delle sue pagine
invece passano. Da lanciare sui dati di prova:

    python prove_sicurezza_browser.py http://127.0.0.1:5000

Non cambia niente nel database: le richieste rifiutate non scrivono e quella
buona rimette il testo che c'era.

Già che c'è, la zona dei messaggi (tappa 1 della base, 22/11/2026): la conferma
del salvataggio (dopo il rinvio) e un errore (nella pagina ridisegnata, la scheda
con il telefono sbagliato non si crea) si vedono una volta sola, dentro la zona,
rossi solo se sono errori, e ricaricando la pagina non tornano. Le prove senza
browser prendono i messaggi da Flask (prove_messaggi.py); dove si vedono lo dice
questa."""
import functools
import http.server
import os
import re
import sys
import threading
import urllib.request
from html import unescape

from playwright.sync_api import sync_playwright

B = (sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5000').rstrip('/')
esiti = []


def controlla(nome, ok, dettaglio=''):
    esiti.append((ok, nome, dettaglio))
    print('%s %s %s' % ('OK' if ok else 'NO', nome, '' if ok else dettaglio))


ZONA = '.avvisi'          # la zona dei messaggi di base.html: se cambia l'aspetto, si cambia solo qui


def nella_zona(pg, testo, errore):
    """(va bene, dettaglio): il messaggio con quel testo c'è una volta sola, dentro la zona dei messaggi,
    visibile, e rosso solo se è un errore."""
    trovati = pg.get_by_text(testo)
    if trovati.count() != 1:
        return False, '%r trovato %d volte; zona: %d' % (testo, trovati.count(), pg.locator(ZONA).count())
    m = trovati.first
    dentro = m.evaluate('(e, z) => !!e.closest(z)', ZONA)
    rosso = 'errore' in (m.get_attribute('class') or '').split()
    return dentro and m.is_visible() and rosso == errore, {'dentro': dentro, 'visibile': m.is_visible(), 'errore': rosso}


def testo_promemoria():
    pagina = urllib.request.urlopen(B + '/impostazioni', timeout=30).read().decode('utf-8')
    m = re.search(r'<textarea[^>]*name="testo"[^>]*>(.*?)</textarea>', pagina, re.S)
    return unescape(m.group(1)).strip() if m else None


ATTACCO = """<!doctype html><meta charset="utf-8"><title>altro sito</title>
<form id="f" method="post" action="%(b)s/impostazioni">
  <input name="azione" value="testo"><input name="testo" value="SCRITTO DA UN ALTRO SITO %(n)s">
  <input name="oggetto" value="x"></form>
<script>
  var modo = location.hash.slice(1);
  if (modo === 'modulo') { document.getElementById('f').submit(); }
  if (modo === 'fetch') {
    fetch('%(b)s/impostazioni', {method: 'POST', mode: 'no-cors',
      body: new URLSearchParams('azione=testo&testo=SCRITTO+DA+FETCH&oggetto=x')})
      .then(function () { document.title = 'fatto'; }, function () { document.title = 'fatto'; });
  }
  if (modo === 'cornice') {
    var c = document.createElement('iframe');
    c.setAttribute('sandbox', 'allow-forms allow-scripts');
    c.srcdoc = '<form id=g method=post action="%(b)s/impostazioni"><input name=azione value=testo>' +
      '<input name=testo value="SCRITTO DA UNA CORNICE"><input name=oggetto value=x></form>' +
      '<script>setTimeout(function () { document.getElementById("g").submit(); }, 1000)<\\/script>';
    document.body.appendChild(c);
    setTimeout(function () { document.title = 'fatto'; }, 3000);
  }
</script>"""


class Pagine(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        corpo = (ATTACCO % {'b': B, 'n': self.path}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *a):
        pass


server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Pagine)
ALTRO = 'http://127.0.0.1:%d' % server.server_address[1]
threading.Thread(target=server.serve_forever, daemon=True).start()

prima = testo_promemoria()
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
    pg = b.new_page()
    risposte = []
    pg.on('response', lambda r: risposte.append((r.request.method, r.url, r.status))
          if r.url.startswith(B) and r.request.method == 'POST' else None)
    for modo in ('modulo', 'fetch', 'cornice'):
        # 21/11/2026: Chrome fa girare la cornice chiusa in una sandbox in un processo suo; se il modulo partiva
        # subito, a volte partiva prima che Playwright seguisse la cornice e la prova non vedeva né la richiesta né il
        # 403 (la cornice finisce comunque sulla pagina d'errore di Chrome: il gestionale non si lascia aprire in una
        # cornice). Ora il modulo della cornice parte dopo un secondo, e senza il 403 visto si riprova, fino a tre
        # volte. Se intanto il testo cambia, l'attacco è riuscito e la prova fallisce subito. Ogni tentativo apre un
        # indirizzo suo: con lo stesso indirizzo e la stessa ancora il browser resta nella stessa pagina e l'attacco
        # non riparte (lo ha trovato la revisione della 1.12.7); il server delle pagine d'attacco risponde a ogni percorso.
        for tentativo in range(3):
            risposte.clear()
            pg.goto(ALTRO + '/attacco-%s-%d.html#%s' % (modo, tentativo + 1, modo))      # pagina nuova, non solo l'ancora
            try:
                pg.wait_for_function("document.title === 'fatto' || location.href.indexOf('%s') === 0" % B,
                                     timeout=8000)
            except Exception:
                pass
            for _ in range(30):
                if risposte:
                    break
                pg.wait_for_timeout(100)
            pg.wait_for_timeout(800)
            dopo = testo_promemoria()
            if risposte or dopo != prima:
                break
        stati = sorted({s for _, _, s in risposte})
        controlla('%s da un altro sito: rifiutato' % modo, dopo == prima and stati == [403],
                  'testo ora %r, risposte %s, tentativi %d' % (dopo, risposte, tentativo + 1))
    # le pagine del gestionale invece salvano
    pg.goto(B + '/impostazioni')
    campo = pg.locator('textarea[name="testo"]')
    originale = campo.input_value()
    campo.fill(originale + ' (prova)')
    with pg.expect_navigation():
        campo.locator('xpath=ancestor::form').locator('button[type="submit"]').first.click()
    salvato = testo_promemoria()
    controlla('modulo del gestionale: salvato', salvato == originale + ' (prova)', 'testo ora %r' % salvato)
    controlla('salvato: «Testo dei messaggi salvato» nella zona dei messaggi', *nella_zona(pg, 'Testo dei messaggi salvato', False))
    pg.goto(B + '/impostazioni')
    campo = pg.locator('textarea[name="testo"]')
    campo.fill(originale)
    with pg.expect_navigation():
        campo.locator('xpath=ancestor::form').locator('button[type="submit"]').first.click()
    controlla('testo rimesso com\'era', testo_promemoria() == prima)
    controlla('rimesso: di nuovo il messaggio nella zona', *nella_zona(pg, 'Testo dei messaggi salvato', False))
    pg.reload()
    controlla('ricaricata la pagina il messaggio non torna', pg.locator(ZONA).count() == 0, pg.locator(ZONA).count())
    # un errore: la pagina ridisegnata (200) con il messaggio rosso; la scheda con il telefono sbagliato non si crea
    pg.goto(B + '/pazienti/nuovo')
    pg.fill('#cognome', 'Fittizi')
    pg.fill('#telefono', '12-34')                  # type="tel" senza pattern: il browser lo lascia passare
    with pg.expect_navigation():
        pg.locator('form.modulo-paziente button.primario[type="submit"]').click()
    controlla('errore: «almeno 6 cifre» nella zona dei messaggi, rosso', *nella_zona(pg, 'almeno 6 cifre', True))
    controlla('errore: il modulo ripropone quello scritto', pg.input_value('#telefono') == '12-34', pg.input_value('#telefono'))
    b.close()
server.shutdown()
print('%d / %d' % (sum(1 for e in esiti if e[0]), len(esiti)))
sys.exit(0 if all(e[0] for e in esiti) else 1)
