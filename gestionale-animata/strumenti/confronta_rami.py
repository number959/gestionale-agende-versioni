# -*- coding: utf-8 -*-
"""Confronta il programma di oggi (il ramo principale) con quello di questa cartella, sugli stessi dati
(tappa 1 della base, 21/11/2026): la veste nuova può cambiare l'aspetto, non quello che il programma fa.

    python strumenti/confronta_rami.py                         # principale = origin/ccr-07f8e160-7j5lup
    python strumenti/confronta_rami.py --principale <ref> --per-forma 10 --senza-testo

Come: il gestionale di prova (strumenti/demo.py del principale) fa una volta il database, che si copia due
volte; due programmi partono insieme su porte libere, uno dal principale (preso con git archive, senza
toccare il repository) e uno da questa cartella, ognuno sulla sua copia. Dalle pagine GET senza parametri si
seguono i collegamenti interni (niente /static/): ogni tipo di pagina (l'indirizzo con le cifre scritte N e
i nomi dei parametri) al massimo --per-forma volte, in tutto al massimo --massimo pagine. Per ogni pagina si confrontano:
risposta e rimando; i moduli come li manda il browser (indirizzo, metodo, campi anche nascosti, scelte delle
tendine, bottoni con il loro valore); collegamenti, data-tasto e data-guida; le righe di testo (non con
--senza-testo); i JSON per intero; gli Excel cella per cella; gli altri file byte per byte. Una pagina diversa
si chiede di nuovo una volta (l'ora può scattare fra le due richieste). Nessuna richiesta che cambia i dati:
solo GET. Finisce con «N pagine confrontate, K diverse» e un resoconto in confronto_rami.txt (nella cartella
temporanea, il percorso lo scrive alla fine)."""
import argparse
import hashlib
import html
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urljoin, urlsplit

QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))           # la cartella del programma
RADICE = os.path.dirname(QUI)
NOME = os.path.basename(QUI)                                                 # gestionale o gestionale-animata

ESEGUI = r'''
import os, sys
codice, db, porta = sys.argv[1], sys.argv[2], int(sys.argv[3])
sys.path.insert(0, codice); os.chdir(codice)
import app as A
from modelli import crea_sessione
A.Sessione = crea_sessione('sqlite:///' + db); A._registro = None
from waitress import serve
serve(A.app, host='127.0.0.1', port=porta, threads=4)
'''


def porta_libera():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def aspetta(porta, secondi=120):
    fine = time.time() + secondi
    while time.time() < fine:
        try:
            with urllib.request.urlopen('http://127.0.0.1:%d/salute' % porta, timeout=3):
                return True
        except Exception:
            time.sleep(0.5)
    return False


class Lettore(HTMLParser):
    """Quello che conta di una pagina, senza l'aspetto."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.moduli, self.collegamenti, self.segni, self.testo = [], [], [], []
        self._modulo, self._tendina, self._salta = None, None, 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for k in ('data-tasto', 'data-guida'):
            if k in a:
                self.segni.append('%s=%s' % (k, a[k]))
        if tag in ('script', 'style'):
            self._salta += 1
        if tag == 'a' and a.get('href'):
            self.collegamenti.append(a['href'])
        if tag == 'form':
            self._modulo = {'action': a.get('action', ''), 'method': (a.get('method') or 'get').lower(), 'campi': []}
            self.moduli.append(self._modulo)
        campi = self._modulo['campi'] if self._modulo is not None else None
        if campi is None:
            return
        if tag == 'input':
            tipo = (a.get('type') or 'text').lower()
            valore = a.get('value', '') if tipo in ('hidden', 'submit', 'button', 'checkbox', 'radio') else ''
            campi.append(('input', tipo, a.get('name', ''), valore))
        elif tag == 'button':
            campi.append(('button', (a.get('type') or 'submit').lower(), a.get('name', ''), a.get('value', '')))
        elif tag == 'textarea':
            campi.append(('textarea', '', a.get('name', ''), ''))
        elif tag == 'select':
            self._tendina = ['select', '', a.get('name', ''), []]
            campi.append(self._tendina)
        elif tag == 'option' and self._tendina is not None:
            self._tendina[3].append(a.get('value', ''))

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self._salta:
            self._salta -= 1
        if tag == 'form':
            self._modulo = None
        if tag == 'select' and self._tendina is not None:
            self._tendina[3] = tuple(self._tendina[3])
            self._tendina = None

    def handle_data(self, data):
        if not self._salta:
            t = ' '.join(data.split())
            if t:
                self.testo.append(t)


def leggi(porta, percorso):
    req = urllib.request.Request('http://127.0.0.1:%d%s' % (porta, percorso))

    class SenzaRimandi(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    try:
        r = urllib.request.build_opener(SenzaRimandi).open(req, timeout=60)
        return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


PER_PROCESSO = ('pid', 'avviato')          # nei JSON: cambiano da un programma all'altro anche senza modifiche


def togli_per_processo(x):
    if isinstance(x, dict):
        return {k: ('·' if k in PER_PROCESSO else togli_per_processo(v)) for k, v in x.items()}
    if isinstance(x, list):
        return [togli_per_processo(v) for v in x]
    return x


def riassunto(stato, intestazioni, corpo, con_testo, dati=''):
    if dati:                                   # la cartella dei dati è diversa per i due: si scrive DATI
        for forma in (dati, json.dumps(dati)[1:-1]):
            corpo = corpo.replace(forma.encode('utf-8'), b'DATI')
    tipo = (intestazioni.get('Content-Type') or '').split(';')[0]
    r = {'stato': stato, 'tipo': tipo}
    if stato in (301, 302, 303, 307, 308):
        r['rimando'] = re.sub(r'^https?://[^/]+', '', intestazioni.get('Location', ''))
        return r, []
    if tipo == 'text/html':
        p = Lettore()
        p.feed(corpo.decode('utf-8', 'replace'))
        r['moduli'] = [(m['action'], m['method'], tuple(tuple(c) for c in m['campi'])) for m in p.moduli]
        r['collegamenti'] = p.collegamenti
        r['segni'] = p.segni
        if con_testo:
            r['testo'] = p.testo
        return r, p.collegamenti
    if tipo == 'application/json':
        try:
            r['json'] = togli_per_processo(json.loads(corpo.decode('utf-8')))
        except ValueError:
            r['corpo'] = hashlib.sha256(corpo).hexdigest()
        return r, []
    if 'spreadsheetml' in tipo:
        from openpyxl import load_workbook
        lib = load_workbook(io.BytesIO(corpo), data_only=False)
        r['excel'] = {f.title: [[c.value if not hasattr(c.value, 'isoformat') else c.value.isoformat() for c in riga]
                                for riga in f.iter_rows()] for f in lib.worksheets}
        return r, []
    r['corpo'] = hashlib.sha256(corpo).hexdigest()
    return r, []


def uguali(a, b):
    """Uguali anche nel tipo: per Python 1 e 1.0, o 1 e True, sono uguali, per chi legge il JSON no."""
    return json.dumps(a, sort_keys=True, default=repr) == json.dumps(b, sort_keys=True, default=repr)


def primo_punto_diverso(a, b, dove=''):
    """Dove due JSON o due fogli Excel cominciano a essere diversi: (posto, valore di qua, valore di là)."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in list(a) + [k for k in b if k not in a]:
            if not uguali(a.get(k, '(manca)'), b.get(k, '(manca)')):
                return primo_punto_diverso(a.get(k, '(manca)'), b.get(k, '(manca)'), '%s[%r]' % (dove, k))
    elif isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        for i in range(max(len(a), len(b))):
            x = a[i] if i < len(a) else '(manca)'
            y = b[i] if i < len(b) else '(manca)'
            if not uguali(x, y):
                return primo_punto_diverso(x, y, '%s[%d]' % (dove, i))
    return dove or '(tutto)', a, b


def cella(dove):
    """['Foglio'][3][1] → foglio Foglio, cella B4."""
    m = re.match(r"\['(.*)'\]\[(\d+)\]\[(\d+)\]$", dove)
    if not m:
        return dove
    from openpyxl.utils import get_column_letter
    return 'foglio %s, cella %s%d' % (m.group(1), get_column_letter(int(m.group(3)) + 1), int(m.group(2)) + 1)


def differenze(a, b):
    out = []
    for k in sorted(set(a) | set(b)):
        if uguali(a.get(k), b.get(k)):
            continue
        va, vb = a.get(k), b.get(k)
        if k in ('json', 'excel'):
            dove, x, y = primo_punto_diverso(va, vb)
            out.append('%s, %s: principale %.200r; qui %.200r' % (k, cella(dove) if k == 'excel' else dove, x, y))
        elif isinstance(va, list) and isinstance(vb, list):
            solo_a = [x for x in va if x not in vb][:3]
            solo_b = [x for x in vb if x not in va][:3]
            out.append('%s: solo nel principale %s; solo qui %s%s' % (
                k, solo_a, solo_b, '' if (solo_a or solo_b) else ' (stessi elementi, ordine diverso)'))
        else:
            out.append('%s: principale %.300r; qui %.300r' % (k, va, vb))
    return out


def forma(percorso):
    """Il tipo di pagina: l'indirizzo con le cifre scritte N e i soli nomi dei parametri (/giorno/N-N-N?struttura)."""
    u = urlsplit(percorso)
    return re.sub(r'\d+', 'N', u.path) + '?' + '&'.join(sorted({k for k, _ in parse_qsl(u.query, keep_blank_values=True)}))


def interni(base, collegamenti):
    for h in collegamenti:
        if h.startswith(('mailto:', 'tel:', 'javascript:', '#', 'data:')):
            continue
        u = urlsplit(urljoin('http://127.0.0.1' + base, html.unescape(h)))
        if u.hostname not in ('127.0.0.1', None) or u.path.startswith('/static/'):
            continue
        yield u.path + ('?' + u.query if u.query else '')


def main():
    par = argparse.ArgumentParser(description='Confronta il programma di oggi con questa cartella.')
    par.add_argument('--principale', default='origin/ccr-07f8e160-7j5lup')
    par.add_argument('--massimo', type=int, default=3000)
    par.add_argument('--per-forma', type=int, default=4, help='quante pagine dello stesso tipo (0 = tutte)')
    par.add_argument('--senza-testo', action='store_true')
    par.add_argument('--qui', default=QUI, help='la cartella da confrontare (di solito questa)')
    arg = par.parse_args()
    tmp = tempfile.mkdtemp(prefix='confronta-rami-')
    processi, registri = [], []
    try:
        principale = os.path.join(tmp, 'principale')
        os.makedirs(principale)
        archivio = subprocess.run(['git', '-C', RADICE, 'archive', '--format=tar', arg.principale, NOME],
                                  capture_output=True, check=True)
        with tarfile.open(fileobj=io.BytesIO(archivio.stdout)) as tf:      # senza il comando tar: va anche su Windows
            if hasattr(tarfile, 'data_filter'):
                tf.extractall(principale, filter='data')
            else:
                tf.extractall(principale)
        codice_a = os.path.join(principale, NOME)
        # il database, una volta sola, con il gestionale di prova del principale
        base = os.path.join(tmp, 'dati-base')
        porta = porta_libera()
        demo = subprocess.Popen([sys.executable, os.path.join(codice_a, 'strumenti', 'demo.py'), '--dati', base,
                                 '--porta', str(porta)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not aspetta(porta):
            demo.kill()
            sys.exit('il gestionale di prova del principale non parte')
        demo.terminate()
        demo.wait(timeout=30)
        porte, cartelle = {}, {}
        for lato, codice in (('principale', codice_a), ('qui', os.path.abspath(arg.qui))):
            dati = cartelle[lato] = os.path.join(tmp, 'dati-' + lato)
            os.makedirs(dati)
            for est in ('', '-wal', '-shm'):
                if os.path.exists(os.path.join(base, 'demo.db' + est)):
                    shutil.copy2(os.path.join(base, 'demo.db' + est), os.path.join(dati, 'demo.db' + est))
            porte[lato] = porta_libera()
            registri.append(open(os.path.join(tmp, lato + '.log'), 'w'))
            processi.append(subprocess.Popen([sys.executable, '-c', ESEGUI, codice, os.path.join(dati, 'demo.db'),
                                              str(porte[lato])], stdout=subprocess.DEVNULL, stderr=registri[-1]))
        for lato in porte:
            if not aspetta(porte[lato]):
                sys.exit('il programma «%s» non parte: %s' % (lato, os.path.join(tmp, lato + '.log')))
        # da dove si parte: le pagine GET senza parametri dell'elenco degli indirizzi
        coda = []
        with open(os.path.join(QUI, 'indirizzi.txt'), encoding='utf-8') as f:
            for riga in f:
                parti = riga.rstrip('\n').split('\t')
                if len(parti) == 4 and 'GET' in parti[0].split(','):
                    coda.append(parti[1])
        visti, diverse, righe = set(coda), [], []
        per_forma, saltati = {}, 0
        for x in coda:
            per_forma[forma(x)] = per_forma.get(forma(x), 0) + 1
        n = 0
        while coda and n < arg.massimo:
            percorso = coda.pop(0)
            n += 1
            def due():
                a = riassunto(*leggi(porte['principale'], percorso), not arg.senza_testo, cartelle['principale'])
                b = riassunto(*leggi(porte['qui'], percorso), not arg.senza_testo, cartelle['qui'])
                return a[0], a[1], b[0]
            ra, la, rb = due()
            if not uguali(ra, rb):                                   # l'ora può scattare fra le due richieste: una volta ancora
                ra, la, rb = due()
            if not uguali(ra, rb):
                diverse.append(percorso)
                righe.append('DIVERSA %s\n  %s' % (percorso, '\n  '.join(differenze(ra, rb))))
            for nuovo in interni(percorso, la):
                if nuovo in visti:
                    continue
                visti.add(nuovo)
                f = forma(nuovo)
                if arg.per_forma and per_forma.get(f, 0) >= arg.per_forma:
                    saltati += 1                           # stesso tipo di pagina, già visto abbastanza volte
                    continue
                per_forma[f] = per_forma.get(f, 0) + 1
                coda.append(nuovo)
        resoconto = os.path.join(tempfile.gettempdir(), 'confronto_rami-%s.txt' % NOME)
        with open(resoconto, 'w', encoding='utf-8') as f:
            f.write('\n'.join(righe) + '\n')
        for r in righe[:20]:
            print(r[:1500])
        if coda:
            print('(fermato a %d pagine: ne restavano %d da vedere; --massimo per andare oltre)' % (n, len(coda)))
        if saltati:
            print('(%d collegamenti non seguiti: dello stesso tipo di pagine già viste %d volte; --per-forma 0 per '
                  'seguirli tutti)' % (saltati, arg.per_forma))
        print('tipi di pagina: %d' % len(per_forma))
        print('resoconto: %s' % resoconto)
        print('%d pagine confrontate, %d diverse' % (n, len(diverse)))
        return 1 if diverse else 0
    finally:
        for p in processi:
            p.terminate()
        for p in processi:
            try:
                p.wait(timeout=20)
            except Exception:
                p.kill()
        for r in registri:
            r.close()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
