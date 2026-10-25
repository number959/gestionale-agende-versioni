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
deve essere dentro l'eseguibile), la pagina Controllo dei codici fiscali, i turni
del personale (pagine, i dieci tipi di turno di partenza, Excel, turni.js, icone e
loro licenze), la registrazione del numero WhatsApp, Dove si fa (pagine, dove.js, il
menu, la ricerca rapida con le prestazioni) e la pagina dell'email della 1.9.1 (tipo di
casella, gestionale.js, la guida vecchia che porta a quella nuova). L'invio delle email sul
programma installato si prova con strumenti/prova_email_installato.py."""
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
# 1.8: turni del personale (solo lettura)
for p in ('/personale/turni/mese/', '/personale/turni/settimana/', '/personale/turni/giorno/', '/personale/persone'):
    s, b, _ = get(p)
    t = b.decode('utf-8', 'replace')
    controlla('turni: %s' % p, s == 200 and ('id="griglia-turni"' in t or 'id="vista-giorno"' in t or
                                             'Per cominciare, il personale' in t or 'Aggiungi una persona' in t), s)
s, b, _ = get('/personale/tipi')
t = testo(b)
codici = re.findall(r'<span class="turno[^"]*"[^>]*><b>([A-Z0-9]{1,4})</b></span>', b.decode('utf-8', 'replace'))
controlla('turni: i dieci tipi di turno di partenza (database aggiornato allo schema 9)',
          s == 200 and {'M', 'P', 'N', 'G', 'RE', 'SN', 'R', 'F', 'MA', 'PE'} <= set(codici), codici)
s, b, h = get('/personale/turni/mese/2026-12.xlsx')
controlla('turni: il mese in Excel', s == 200 and b[:2] == b'PK' and 'spreadsheet' in h.get('Content-Type', ''),
          (s, h.get('Content-Type')))
for p, tipo, parola in (('/static/turni.js', 'text/javascript', b'griglia-turni'),
                        ('/static/icone/LICENZE.txt', 'text/plain', b'Lucide')):
    s, b, h = get(p)
    controlla('turni: %s' % p, s == 200 and h.get('Content-Type', '').startswith(tipo) and parola in b,
              (s, h.get('Content-Type')))
s, b, _ = get('/invii')
controlla('WhatsApp: «Registra il numero» nella pagina', s == 200 and 'Registra il numero' in testo(b), s)
# 1.9: Dove si fa (solo lettura: con o senza il database delle prestazioni caricato)
s, b, _ = get('/dove-si-fa/')
t = b.decode('utf-8', 'replace')
controlla('Dove si fa: la pagina (database aggiornato allo schema 10)',
          s == 200 and ('id="q-dove"' in t or 'Manca il database delle prestazioni' in t), s)
controlla('Dove si fa: nel menu, con il tasto D', re.search(r'<a data-tasto="d" href="/dove-si-fa/', t) is not None)
for p, parola in (('/dove-si-fa/strutture', 'Strutture del gruppo'), ('/dove-si-fa/registro', 'Pazienti indirizzati')):
    s, b, _ = get(p)
    controlla('Dove si fa: %s' % p, s == 200 and parola in testo(b), s)
s, b, h = get('/static/dove.js')
controlla('Dove si fa: dove.js', s == 200 and h.get('Content-Type', '').startswith('text/javascript') and
          b'pagina-dove' in b, (s, h.get('Content-Type')))
s, b, _ = get('/cerca-tutto.json?q=ecografia')
d = json.loads(b) if s == 200 else {}
controlla('ricerca rapida: anche le prestazioni', isinstance(d.get('prestazioni'), list), (s, list(d)))
# 1.9.1: l'email con qualsiasi casella (solo lettura)
s, b, _ = get('/invii')
h = b.decode('utf-8', 'replace')
controlla('Email: il tipo di casella, con i quattro tipi e i loro valori',
          s == 200 and all('<option value="%s"' % c in h for c in ('dominio', 'aruba', 'gmail', 'altro')) and
          'id="caselle-email"' in h and 'Server e accesso' in h, s)
s, b, _ = get('/static/gestionale.js')
controlla('Email: gestionale.js propone il server della casella', s == 200 and b'serverPerTipo' in b, s)
class _SenzaRimandi(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


try:
    r = urllib.request.build_opener(_SenzaRimandi).open(B + '/aiuto/email-gmail', timeout=90)
    s, posto = r.status, r.headers.get('Location')
except urllib.error.HTTPError as e:
    s, posto = e.code, e.headers.get('Location')
controlla('Email: la guida vecchia porta a quella nuova', s in (301, 302) and
          (posto or '').endswith('/aiuto/email-casella'), (s, posto))

for ok, nome, dettaglio in esiti:
    print(('OK ' if ok else 'KO ') + nome + ('' if ok else '  ' + str(dettaglio)[:300]))
print('%d controlli, %d a posto' % (len(esiti), sum(1 for e in esiti if e[0])))
sys.exit(0 if all(e[0] for e in esiti) else 1)
