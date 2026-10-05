# -*- coding: utf-8 -*-
"""Prove sul programma INSTALLATO (l'eseguibile vero, per esempio nel Windows
finto di strumenti/wine), che risponde su http://127.0.0.1:5000. Non scrive
niente nel programma.

    python strumenti/prove_installato.py [versione attesa] [normale|animata]

Senza argomenti: la versione di comune.py e la variante di questa cartella.
Controlla: versione in Aiuto e nelle Novità, ogni guida con il suo video
servito come video/webm (anche a pezzi, Range), pagina Aggiornamenti con la
sua variante e l'indirizzo degli aggiornamenti, stato.json, i tipi dei file
statici, il codice fiscale (controllo, calcolo e luoghi: il file dei luoghi
deve essere dentro l'eseguibile) e la pagina Controllo dei codici fiscali."""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from html import unescape

QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, QUI)
import comune  # noqa: E402
import guida  # noqa: E402
import aggiornamenti  # noqa: E402

B = os.environ.get('INDIRIZZO', 'http://127.0.0.1:5000')
ATTESA = sys.argv[1] if len(sys.argv) > 1 else comune.VERSIONE
VARIANTE = sys.argv[2] if len(sys.argv) > 2 else aggiornamenti.VARIANTE
esiti = []


def controlla(nome, ok, dettaglio=''):
    esiti.append((bool(ok), nome, dettaglio))


def get(p, intestazioni=None):
    req = urllib.request.Request(B + p, headers=intestazioni or {})
    try:
        r = urllib.request.urlopen(req, timeout=90)
        return r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers


def testo(b):
    return ' '.join(unescape(re.sub(r'<[^>]+>', ' ', b.decode('utf-8', 'replace'))).split())


s, b, _ = get('/aiuto')
controlla('Aiuto: versione %s' % ATTESA, 'Gestionale Agende, versione %s' % ATTESA in testo(b), testo(b)[-200:])
n_video = b.decode().count('class="con-video"')
controlla('Aiuto: ogni guida ha il suo video (%d)' % len(guida.ARTICOLI), n_video == len(guida.ARTICOLI), n_video)
s, b, _ = get('/aiuto/novita')
controlla('Novità della versione installata', s == 200 and 'Novità della versione %s' % ATTESA in testo(b), testo(b)[:300])
s, b, _ = get('/aggiornamenti')
t = testo(b)
controlla('Aggiornamenti: versione e variante', 'Versione installata: %s' % ATTESA in t and
          ('(con animazioni)' in t) == (VARIANTE == 'animata') and aggiornamenti.MANIFESTO in t, t[:300])
campo = re.search(r'id="indirizzo-aggiornamenti"[^>]*value="([^"]*)"', b.decode())
predefinito = aggiornamenti.INDIRIZZO_PREDEFINITO
controlla('Aggiornamenti: indirizzo predefinito in uso, oppure «Rimetti l\'indirizzo predefinito»',
          (campo and unescape(campo.group(1)) == predefinito and 'È l\'indirizzo predefinito' in t) or
          (not predefinito) or 'rimetti-predefinito' in b.decode(), campo.group(1) if campo else None)
s, b, _ = get('/aggiornamenti/stato.json')
d = json.loads(b)
controlla('stato.json', s == 200 and d['versione'] == ATTESA, d)
totale, rotti = 0, []
for a in guida.ARTICOLI:
    s, b, _ = get('/aiuto/' + a['slug'])
    ok = s == 200 and 'href="/static/video/%s.webm" data-video=' % a['slug'] in b.decode()
    s2, v, h = get('/static/video/%s.webm' % a['slug'])
    totale += len(v)
    if not (ok and s2 == 200 and h.get('Content-Type', '').startswith('video/webm') and v[:4] == b'\x1a\x45\xdf\xa3'):
        rotti.append(a['slug'])
controlla('i %d video si servono come video/webm (%.1f MB)' % (len(guida.ARTICOLI), totale / 1048576), not rotti, rotti)
s, b, h = get('/static/video/prenotare.webm', {'Range': 'bytes=1000-1999'})
controlla('video: scorrimento (Range → 206)', s == 206 and len(b) == 1000 and h.get('Content-Range', '').startswith('bytes 1000-1999/'),
          (s, len(b), h.get('Content-Range')))
for p, tipo in (('/static/guida.js', 'text/javascript'), ('/static/stile.css', 'text/css'),
                ('/static/fonts/inter-latin.woff2', 'font/woff2'), ('/static/guida/aggiornare.png', 'image/png')):
    s, b, h = get(p)
    controlla('tipo di %s: %s' % (p, tipo), s == 200 and h.get('Content-Type', '').startswith(tipo), h.get('Content-Type'))
s, b, _ = get('/pazienti/codice-fiscale?cf=FNTPRV80A01F839W&cognome=Fintini&nome=Prova')
d = json.loads(b) if s == 200 else {}
controlla('codice fiscale: controllo e lettura dentro l\'eseguibile', d.get('stato') == 'valido' and
          (d.get('da_cf') or {}).get('luogo_testo') == 'Napoli (NA)', (s, d))
s, b, _ = get('/pazienti/codice-fiscale?cognome=Fintini&nome=Prova&sesso=M&data_nascita=1980-01-01&luogo_testo=Napoli')
d = json.loads(b) if s == 200 else {}
controlla('codice fiscale: calcolo dai dati', d.get('calcolato') == 'FNTPRV80A01F839W', (s, d))
s, b, _ = get('/pazienti/luoghi?q=pozzuoli')
d = json.loads(b) if s == 200 else []
controlla('luoghi di nascita: il file dei luoghi è dentro l\'eseguibile', d and d[0].get('codice') == 'G964', (s, d[:1]))
s, b, _ = get('/pazienti/codici-fiscali')
controlla('pagina Controllo dei codici fiscali', s == 200 and 'Controllo dei codici fiscali' in testo(b), s)

for ok, nome, dettaglio in esiti:
    print(('OK ' if ok else 'KO ') + nome + ('' if ok else '  ' + str(dettaglio)[:300]))
print('%d controlli, %d a posto' % (len(esiti), sum(1 for e in esiti if e[0])))
sys.exit(0 if all(e[0] for e in esiti) else 1)
