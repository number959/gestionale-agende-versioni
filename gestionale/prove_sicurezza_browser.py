# -*- coding: utf-8 -*-
"""Nel browser vero: una pagina di un altro sito (qui su un'altra porta dello
stesso PC, il caso piu' vicino) prova a mandare moduli al gestionale in tre
modi, e il gestionale li deve rifiutare tutti; i moduli delle sue pagine
invece passano. Da lanciare sui dati di prova:

    python prove_sicurezza_browser.py http://127.0.0.1:5000

Non cambia niente nel database: le richieste rifiutate non scrivono e quella
buona rimette il testo che c'era."""
import functools
import http.server
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
      '<script>document.getElementById("g").submit()<\\/script>';
    document.body.appendChild(c);
    setTimeout(function () { document.title = 'fatto'; }, 1500);
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
    b = p.chromium.launch()
    pg = b.new_page()
    risposte = []
    pg.on('response', lambda r: risposte.append((r.request.method, r.url, r.status))
          if r.url.startswith(B) and r.request.method == 'POST' else None)
    for modo in ('modulo', 'fetch', 'cornice'):
        risposte.clear()
        pg.goto(ALTRO + '/attacco-%s.html#%s' % (modo, modo))      # pagina nuova, non solo l'ancora
        try:
            pg.wait_for_function("document.title === 'fatto' || location.href.indexOf('%s') === 0" % B,
                                 timeout=8000)
        except Exception:
            pass
        pg.wait_for_timeout(800)
        dopo = testo_promemoria()
        stati = sorted({s for _, _, s in risposte})
        controlla('%s da un altro sito: rifiutato' % modo, dopo == prima and stati == [403],
                  'testo ora %r, risposte %s' % (dopo, risposte))
    # le pagine del gestionale invece salvano
    pg.goto(B + '/impostazioni')
    campo = pg.locator('textarea[name="testo"]')
    originale = campo.input_value()
    campo.fill(originale + ' (prova)')
    with pg.expect_navigation():
        campo.locator('xpath=ancestor::form').locator('button[type="submit"]').first.click()
    salvato = testo_promemoria()
    controlla('modulo del gestionale: salvato', salvato == originale + ' (prova)', 'testo ora %r' % salvato)
    pg.goto(B + '/impostazioni')
    campo = pg.locator('textarea[name="testo"]')
    campo.fill(originale)
    with pg.expect_navigation():
        campo.locator('xpath=ancestor::form').locator('button[type="submit"]').first.click()
    controlla('testo rimesso com\'era', testo_promemoria() == prima)
    b.close()
server.shutdown()
print('%d / %d' % (sum(1 for e in esiti if e[0]), len(esiti)))
sys.exit(0 if all(e[0] for e in esiti) else 1)
