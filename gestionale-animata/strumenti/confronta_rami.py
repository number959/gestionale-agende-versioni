# -*- coding: utf-8 -*-
"""Confronta il programma di oggi (il ramo principale) con quello di questa cartella, sugli stessi dati
(tappa 1 della base, 21/11/2026; cornice, insiemi e pagine che si stampano dalla tappa 2): la veste nuova può
cambiare l'aspetto, non quello che il programma fa.

    python strumenti/confronta_rami.py                         # principale = origin/ccr-07f8e160-7j5lup
    python strumenti/confronta_rami.py --principale <ref> --per-forma 10 --senza-testo
    python strumenti/confronta_rami.py --con-ordine            # anche le cose spostate nella pagina

Come: il gestionale di prova (strumenti/demo.py del principale) fa una volta il database, che si copia due
volte; due programmi partono insieme su porte libere, uno dal principale (preso con git archive, senza
toccare il repository) e uno da questa cartella, ognuno sulla sua copia. Dalle pagine GET senza parametri si
seguono i collegamenti interni del principale (niente /static/), anche quelli del menu: ogni tipo di pagina
(l'indirizzo con le cifre scritte N e i nomi dei parametri) al massimo --per-forma volte, in tutto al massimo
--massimo pagine. Per ogni pagina si confrontano: risposta e rimando; i moduli come li manda il browser
(indirizzo, metodo, campi anche nascosti, scelte delle tendine, bottoni con il loro valore); collegamenti; i segni
(data-tasto, data-guida, data-prova, role, aria-label, aria-current: vedi SEGNI); le righe di testo (non con
--senza-testo); i JSON per intero; gli Excel cella per cella; gli altri file byte per byte. Collegamenti, segni,
righe di testo, moduli e campi di un modulo si confrontano come insiemi con le quantità, senza ordine (la veste
sposta le cose); --con-ordine guarda anche l'ordine, come fino alla tappa 1. Una pagina diversa si chiede di nuovo
una volta (l'ora può scattare fra le due richieste). Nessuna richiesta che cambia i dati: solo GET.

La cornice (menu, barra in alto, linguette, campanella, zona dei messaggi, tasti rapidi) sta fuori dal confronto di
ogni pagina e si confronta una volta a parte (confronta_cornice): le voci di ogni tipo (parola, forma
dell'indirizzo, data-tasto, data-guida), i segni e il testo, su ogni pagina quali tipi ci sono e quale voce è
accesa, e gli indirizzi interi delle voci (struttura e giorno della pagina). Nella veste nuova la cornice sta nei
contenitori con data-cornice="<tipo>"; nel programma di oggi, che data-cornice non lo ha, sono nav.menu,
#notifiche, #aiuto-tasti e .avvisi (CORNICE_DI_OGGI).

Poi i 9 fogli da stampare (stampa del giorno, agenda dei medici, lista operatoria, promemoria…) e le 8 pagine che si
stampano (mese, settimana, cassa, cassa del mese, settimana, mese e riepilogo degli ambulatori, mese dei turni): di
ognuno fino a --fogli-per-tipo pagine prese dal giro, stampate in PDF da Chromium come con Ctrl+P e confrontate
pixel per pixel (strumenti/fogli_pdf.py; senza pdftoppm, foto in modo stampa; --senza-pdf per saltarli). Finisce
con la riga della cornice e «N pagine confrontate, K diverse», e un resoconto in confronto_rami-<cartella>.txt
(nella cartella temporanea, il percorso lo scrive alla fine). I cambiamenti approvati
(strumenti/cambiamenti_approvati.txt) si contano a parte."""
import argparse
import difflib
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
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urljoin, urlsplit

QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))           # la cartella del programma
RADICE = os.path.dirname(QUI)
NOME = os.path.basename(QUI)                                                 # gestionale o gestionale-animata

from fogli_pdf import AGGANCIO_MODELLI, confronta_fogli      # nella stessa cartella strumenti/

ESEGUI = r'''
import os, sys
codice, db, porta = sys.argv[1], sys.argv[2], int(sys.argv[3])
sys.path.insert(0, codice); os.chdir(codice)
import app as A
from modelli import crea_sessione
A.Sessione = crea_sessione('sqlite:///' + db); A._registro = None
'''.strip('\n') + '\n' + AGGANCIO_MODELLI + r'''from waitress import serve
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


# I segni di una pagina: gli attributi che non sono aspetto ma servono a qualcuno. data-tasto ai tasti rapidi,
# data-guida ai passi della guida; role, aria-label e aria-current a chi usa un lettore di schermo e alle prove nel
# browser, che cercano i pezzi per ruolo e nome (aiuti_browser.py); data-prova alle prove, per i pezzi che un nome
# non ce l'hanno. Una veste nuova che ne perde uno lo fa vedere qui come differenza da spiegare.
SEGNI = ('data-tasto', 'data-guida', 'data-prova', 'role', 'aria-label', 'aria-current')

# La cornice (tappa 2): menu, barra in alto, linguette, campanella, zona dei messaggi, tasti rapidi. È uguale in
# quasi ogni pagina e la veste nuova la cambia tutta: si toglie dal confronto di ogni pagina e si confronta una volta
# a parte (confronta_cornice). Nella veste nuova sta in contenitori con data-cornice="<tipo>" (menu, barra,
# linguette, campanella, messaggi, tasti). Il programma di oggi data-cornice non lo ha: i suoi pezzi sono questi
# (tag o None per tutti, attributo, valore, tipo), letti solo nelle pagine dove data-cornice non c'è:
CORNICE_DI_OGGI = (
    ('nav', 'class', 'menu', 'menu'),                 # nav.menu di _menu.html: voci, tendine, ricerca rapida
    (None, 'id', 'notifiche', 'campanella'),          # #notifiche di _menu.html: la campanella ne prende il posto
    (None, 'id', 'aiuto-tasti', 'tasti'),             # #aiuto-tasti di _menu.html: il riquadro dei tasti rapidi
    (None, 'class', 'avvisi', 'messaggi'),            # .avvisi di base.html: i messaggi dopo un'azione
)
# Una voce della cornice: collegamenti, bottoni, campi, moduli e ogni pezzo con un data-indirizzo (la ricerca rapida,
# le notifiche). Accesa: con data-cornice ha aria-current (page o true); nella cornice di oggi ha la classe attivo,
# o è il pulsante di un gruppo con la classe attivo (la tendina di _menu.html).
VOCI = ('a', 'button', 'input', 'select', 'textarea', 'form')
VUOTI = ('area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr')
CON_DATA_CORNICE = re.compile(r'<[a-zA-Z][^>]*\sdata-cornice(?=[\s=/>])')


def tipo_di_oggi(tag, a):
    for t, attributo, valore, tipo in CORNICE_DI_OGGI:
        if (t is None or t == tag) and valore in (a.get(attributo) or '').split():
            return tipo
    return None


class Lettore(HTMLParser):
    """Quello che conta di una pagina, senza l'aspetto. La cornice va a parte, in self.cornice: le voci
    («<tipo> «parola» → indirizzo [data-tasto] [data-guida]», con l'indirizzo nella sua forma), i segni e il
    testo fuori dalle voci, quali tipi ci sono e quali voci sono accese, e gli indirizzi interi delle voci."""

    def __init__(self, con_data_cornice=False):
        super().__init__(convert_charrefs=True)
        self.moduli, self.collegamenti, self.segni, self.testo = [], [], [], []
        self.da_seguire = []                 # tutti i collegamenti, anche della cornice: il giro li segue tutti
        self.cornice = {'voci': [], 'segni': [], 'testo': [], 'cornici': [], 'accese': [], 'indirizzi': {}, 'messaggi': []}
        self._modulo, self._tendina, self._salta = None, None, 0
        self._con_data_cornice = con_data_cornice
        self._cornici = []                   # i contenitori aperti: [tag, quanti aperti con quel tag, tipo, di oggi]
        self._aperti = []                    # gli elementi aperti dentro la cornice: (tag, classi)
        self._voci = []                      # le voci aperte: [tag, quanti aperti, attributi, parole, accesa, tipo]

    def _tipo(self, tag, a):
        if self._con_data_cornice:
            return (a.get('data-cornice') or 'cornice', False) if 'data-cornice' in a else (None, False)
        return tipo_di_oggi(tag, a), True

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        tipo, di_oggi = self._tipo(tag, a)
        if tipo is not None:
            self.cornice['cornici'].append(tipo)
            if tag not in VUOTI:
                self._cornici.append([tag, 0, tipo, di_oggi])
        if self._cornici or tipo is not None:
            self._nella_cornice(tag, a, tipo if tipo is not None else self._cornici[-1][2],
                                di_oggi if tipo is not None else self._cornici[-1][3])
            return
        for k in SEGNI:
            if k in a:
                self.segni.append('%s=%s' % (k, a[k]))
        if tag in ('script', 'style'):
            self._salta += 1
        if tag == 'a' and a.get('href'):
            self.collegamenti.append(a['href'])
            self.da_seguire.append(a['href'])
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

    def _nella_cornice(self, tag, a, tipo, di_oggi):
        for k in SEGNI:
            if k in a:
                self.cornice['segni'].append('%s=%s' % (k, a[k]))
        if tag in ('script', 'style'):
            self._salta += 1
        if tag == 'a' and a.get('href'):
            self.da_seguire.append(a['href'])
        if tag in VOCI or 'data-indirizzo' in a:
            if di_oggi:
                classi_padre = self._aperti[-1][1] if self._aperti else ()
                accesa = 'attivo' in (a.get('class') or '').split() or (tag == 'button' and 'attivo' in classi_padre)
            else:
                accesa = (a.get('aria-current') or 'false') != 'false'
            voce = [tag, 0, a, [], accesa, tipo]
            if tag in VUOTI:
                self._chiudi_voce(voce)
            else:
                self._voci.append(voce)
        if tag not in VUOTI:
            for f in self._cornici + self._voci:      # quanti aperti con lo stesso tag: il contenitore finisce a 0
                if f[0] == tag:
                    f[1] += 1
            self._aperti.append((tag, tuple((a.get('class') or '').split())))

    def _chiudi_voce(self, voce):
        tag, _, a, parole, accesa, tipo = voce
        # la parola: il testo di collegamenti e bottoni; per campi, moduli e pezzi con data-indirizzo prima nome e id,
        # che restano gli stessi (un aria-label nuovo non cambia la voce)
        if tag in ('a', 'button'):
            parola = ' '.join(parole) or a.get('aria-label') or a.get('title') or a.get('id') or ''
        else:
            parola = a.get('name') or a.get('id') or a.get('aria-label') or a.get('placeholder') or a.get('title') or ''
        parola = re.sub(r'\d+', 'N', parola)       # i contatori («Segreteria 3») cambiano da pagina a pagina
        indirizzo = a.get('href') or a.get('action') or a.get('formaction') or a.get('data-indirizzo') or ''
        if indirizzo[:1] in ('', '#') and a.get('data-azione-guida'):
            indirizzo = 'guida:' + a['data-azione-guida']
        if tag == 'form':
            indirizzo = (a.get('method') or 'get').lower() + ' ' + indirizzo
        f = forma(indirizzo) if indirizzo[:1] in ('/', '?') or indirizzo.startswith('http') else (indirizzo or '(niente)')
        chiave = '«%s» → %s' % (parola, f)
        segni = ''.join(' %s=%s' % (k, a[k]) for k in ('data-tasto', 'data-guida') if k in a)
        self.cornice['voci'].append('%s %s%s' % (tipo, chiave, segni))
        if accesa:
            self.cornice['accese'].append('%s «%s»' % (tipo, parola))
        if indirizzo:
            self.cornice['indirizzi'].setdefault(chiave, set()).add(indirizzo)

    def handle_endtag(self, tag):
        if self._cornici:
            if tag in ('script', 'style') and self._salta:
                self._salta -= 1
            for v in list(self._voci):
                if v[0] == tag:
                    v[1] -= 1
                    if v[1] <= 0:
                        self._voci.remove(v)
                        self._chiudi_voce(v)
            for i in range(len(self._aperti) - 1, -1, -1):
                if self._aperti[i][0] == tag:
                    del self._aperti[i:]
                    break
            for f in self._cornici:
                if f[0] == tag:
                    f[1] -= 1
            while self._cornici and self._cornici[-1][1] <= 0:
                self._cornici.pop()
            if not self._cornici:                       # fuori: le voci rimaste aperte (HTML rotto) si chiudono
                for v in self._voci:
                    self._chiudi_voce(v)
                self._voci, self._aperti = [], []
            return
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
            if not t:
                return
            if not self._cornici:
                self.testo.append(t)
                return
            if self._cornici[-1][2] == 'messaggi':     # quello che il programma ha detto su questa pagina
                self.cornice['messaggi'].append(t)
            if self._voci and self._voci[-1][0] in ('a', 'button'):
                self._voci[-1][3].append(t)
            else:
                self.cornice['testo'].append(t)


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


def in_ordine(x):
    """Gli elementi di un elenco in un ordine fisso, qualunque sia il loro tipo: un insieme con le quantità."""
    return sorted(x, key=lambda e: json.dumps(e, ensure_ascii=False, sort_keys=True, default=repr))


def riassunto(stato, intestazioni, corpo, con_testo, dati='', con_ordine=False):
    """(quello che conta della pagina, collegamenti da seguire, cornice o None). Senza con_ordine collegamenti, segni,
    righe di testo, moduli e campi di ogni modulo sono insiemi con le quantità (elenchi messi in un ordine fisso): la
    veste nuova sposta le cose nella pagina. Le scelte di una tendina restano nel loro ordine."""
    if dati:                                   # la cartella dei dati è diversa per i due: si scrive DATI
        for forma in (dati, json.dumps(dati)[1:-1]):
            corpo = corpo.replace(forma.encode('utf-8'), b'DATI')
    tipo = (intestazioni.get('Content-Type') or '').split(';')[0]
    r = {'stato': stato, 'tipo': tipo}
    if stato in (301, 302, 303, 307, 308):
        r['rimando'] = re.sub(r'^https?://[^/]+', '', intestazioni.get('Location', ''))
        return r, [], None
    if tipo == 'text/html':
        testo = corpo.decode('utf-8', 'replace')
        p = Lettore(con_data_cornice=bool(CON_DATA_CORNICE.search(testo)))
        p.feed(testo)
        p.close()
        ordina = (lambda x: x) if con_ordine else in_ordine
        r['moduli'] = ordina([(m['action'], m['method'], tuple(ordina([tuple(c) for c in m['campi']])))
                              for m in p.moduli])
        r['collegamenti'] = ordina(p.collegamenti)
        r['segni'] = ordina(p.segni)
        c = p.cornice
        cornice = {'voci': sorted(set(c['voci'])), 'segni': sorted(set(c['segni'])), 'cornici': sorted(set(c['cornici'])),
                   'accese': sorted(c['accese']), 'indirizzi': {k: sorted(v) for k, v in c['indirizzi'].items()},
                   'messaggi': ordina(c['messaggi'])}
        if con_testo:                          # la grandezza del database cambia di poco fra i due programmi
            r['testo'] = ordina([re.sub(r'\b\d+([.,]\d+)? (MB|KB|kB)\b', 'N \\2', x) for x in p.testo])
            cornice['testo'] = sorted(set(c['testo']))
        return r, p.da_seguire, cornice
    if tipo == 'application/json':
        try:
            r['json'] = togli_per_processo(json.loads(corpo.decode('utf-8')))
        except ValueError:
            r['corpo'] = hashlib.sha256(corpo).hexdigest()
        return r, [], None
    if 'spreadsheetml' in tipo:
        from openpyxl import load_workbook
        lib = load_workbook(io.BytesIO(corpo), data_only=False)
        r['excel'] = {f.title: [[c.value if not hasattr(c.value, 'isoformat') else c.value.isoformat() for c in riga]
                                for riga in f.iter_rows()] for f in lib.worksheets}
        return r, [], None
    r['corpo'] = hashlib.sha256(corpo).hexdigest()
    return r, [], None


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


def _chiave(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, default=repr)


def solo_da_una_parte(va, vb):
    """Gli elementi che una parte ha più volte dell'altra (insiemi con le quantità): (solo in va, solo in vb)."""
    ca, cb = Counter(_chiave(x) for x in va), Counter(_chiave(x) for x in vb)
    primo = {}
    for x in list(va) + list(vb):
        primo.setdefault(_chiave(x), x)
    return ([primo[k] for k in (ca - cb).elements()], [primo[k] for k in (cb - ca).elements()])


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
            solo_a, solo_b = solo_da_una_parte(va, vb)
            out.append('%s: solo nel principale (%d) %s; solo qui (%d) %s%s' % (
                k, len(solo_a), solo_a[:3], len(solo_b), solo_b[:3],
                '' if (solo_a or solo_b) else ' (stessi elementi, ordine diverso)'))
        else:
            out.append('%s: principale %.300r; qui %.300r' % (k, va, vb))
    return out


def leggi_approvati(percorso):
    """Le regole di strumenti/cambiamenti_approvati.txt: [(tipo, chiave, espressione compilata, al posto o None)]."""
    regole = []
    if not os.path.exists(percorso):
        return regole
    with open(percorso, encoding='utf-8') as f:
        for n, riga in enumerate(f, 1):
            if not riga.strip() or riga.startswith('#'):
                continue
            parti = riga.rstrip('\n').split('\t')
            if parti[0] == 'aggiunto' and len(parti) >= 4:
                regole.append(('aggiunto', parti[1], re.compile(parti[2]), None))
            elif parti[0] == 'sostituisci' and len(parti) >= 5:
                regole.append(('sostituisci', parti[1], re.compile(parti[2]), parti[3]))
            else:
                sys.exit('cambiamenti_approvati.txt, riga %d: non la capisco: %r' % (n, riga))
    return regole


def _sostituisci(x, rx, al_posto, in_cima=True):
    """re.sub in ogni testo, anche dentro i moduli. Un elemento dell'elenco che diventa vuoto è tolto (solo al primo
    livello: un campo vuoto di un modulo resta)."""
    if isinstance(x, str):
        return rx.sub(al_posto, x)
    if isinstance(x, (list, tuple)):
        fatti = [_sostituisci(y, rx, al_posto, False) for y in x]
        if in_cima:
            fatti = [y for y, prima in zip(fatti, x) if not (isinstance(prima, str) and y == '')]
        return type(x)(fatti)
    return x


def togli_aggiunti(principale, qui, rx, con_ordine=False):
    """«qui» senza gli elementi che ci sono in più rispetto al principale e corrispondono all'espressione. Senza
    ordine (insiemi con le quantità) in più vuol dire più volte che nel principale: un aria-current=page aggiunto al
    menu conta come aggiunto anche nelle pagine che ne avevano già uno (la barra dei turni), e uno che c'era e ora
    manca resta una differenza. Con l'ordine vuol dire non appaiati, nello stesso ordine, con un elemento uguale del
    principale (difflib)."""
    if principale == qui:
        return qui
    if not con_ordine:
        da_togliere = Counter(_chiave(x) for x in solo_da_una_parte(principale, qui)[1]
                              if isinstance(x, str) and rx.search(x))
        tieni = []
        for x in qui:
            if da_togliere[_chiave(x)]:
                da_togliere[_chiave(x)] -= 1
            else:
                tieni.append(x)
        return tieni
    tieni = []
    for op, _, _, j1, j2 in difflib.SequenceMatcher(None, principale, qui, autojunk=False).get_opcodes():
        tieni += [x for x in qui[j1:j2] if op == 'equal' or not (isinstance(x, str) and rx.search(x))]
    return tieni


def applica_approvati(ra, rb, regole, con_ordine=False):
    """Le due pagine (o le due cornici) con i cambiamenti approvati tolti (copie): (principale, qui). Senza ordine
    gli elenchi restano in un ordine fisso anche dopo una sostituzione."""
    if not regole:
        return ra, rb
    ra, rb = dict(ra), dict(rb)
    for tipo, chiave, rx, al_posto in regole:
        if tipo == 'sostituisci' and chiave in ra:
            ra[chiave] = _sostituisci(ra[chiave], rx, al_posto)
            if isinstance(ra[chiave], list) and not con_ordine:
                ra[chiave] = in_ordine(ra[chiave])
        elif tipo == 'aggiunto' and isinstance(rb.get(chiave), list):
            rb[chiave] = togli_aggiunti(ra.get(chiave) or [], rb[chiave], rx, con_ordine)
    return ra, rb


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


CATALOGO = ('voci', 'segni', 'testo')        # le parti della cornice confrontate una volta, su tutte le pagine
PER_PAGINA = ('cornici', 'accese', 'messaggi')  # e quelle confrontate pagina per pagina


def _senza_tipo(voce):
    return voce.split(' ', 1)[1] if ' ' in voce else voce


def confronta_cornice(catalogo, pagine, regole):
    """La cornice, una volta sola. catalogo: {lato: {voci, segni, testo: insiemi su tutte le pagine}}; pagine:
    [(percorso, cornice del principale, cornice di qui)]. Si confrontano (1) voci, segni e testo della cornice, per
    tipo (la voce comincia con il suo tipo); (2) su ogni pagina quali tipi di cornice ci sono, quali voci sono accese
    e i messaggi del programma (la zona dei messaggi: sono di quella pagina); (3) su ogni pagina gli indirizzi interi
    delle voci che ci sono da tutte e due le parti (stessa parola e stessa forma, anche in un tipo diverso): portano
    ancora struttura e giorno della pagina. Le regole approvate valgono anche qui: «segni» e «testo» come nelle
    pagine, «voci», «cornici», «accese» e «messaggi» solo per la cornice.
    Torna (righe del resoconto, differenze, parti diverse solo per i cambiamenti approvati, riga di testa)."""
    righe, n, approvate = [], 0, 0
    ra = {k: sorted(catalogo['principale'][k]) for k in CATALOGO}
    rb = {k: sorted(catalogo['qui'][k]) for k in CATALOGO}
    xa, xb = applica_approvati(ra, rb, regole)
    for k in CATALOGO:
        if uguali(ra[k], rb[k]):
            continue
        if uguali(xa[k], xb[k]):
            approvate += 1
            continue
        solo_a, solo_b = solo_da_una_parte(xa[k], xb[k])
        for di, solo, altra in (('principale', solo_a, xb[k]), ('qui', solo_b, xa[k])):
            for x in solo:
                altrove = ''
                if k == 'voci':                         # la stessa voce, in un altro tipo di cornice dall'altra parte
                    tipi = sorted({y.split(' ', 1)[0] for y in altra if _senza_tipo(y) == _senza_tipo(x)})
                    altrove = ' (dall\'altra parte in: %s)' % ', '.join(tipi) if tipi else ''
                n += 1
                righe.append('  %s solo nel %s: %s%s' % (k, di, x, altrove) if di == 'principale'
                             else '  %s solo qui: %s%s' % (k, x, altrove))
    gruppi = {}                                         # (tipo di pagina, differenza) → [pagine]
    for percorso, ca, cb in pagine:
        pa = {k: ca[k] for k in PER_PAGINA}
        pb = {k: cb[k] for k in PER_PAGINA}
        if not uguali(pa, pb):
            pa2, pb2 = applica_approvati(pa, pb, regole)
            if uguali(pa2, pb2):
                approvate += 1
            for k in PER_PAGINA:
                if not uguali(pa2[k], pb2[k]):
                    solo_a, solo_b = solo_da_una_parte(pa2[k], pb2[k])
                    gruppi.setdefault((forma(percorso), '%s: solo nel principale %s; solo qui %s' % (
                        k, solo_a, solo_b)), []).append(percorso)
        for chiave in sorted(set(ca['indirizzi']) & set(cb['indirizzi'])):
            if ca['indirizzi'][chiave] != cb['indirizzi'][chiave]:
                gruppi.setdefault((forma(percorso), 'indirizzo della voce %s: principale %s; qui %s' % (
                    chiave, ca['indirizzi'][chiave], cb['indirizzi'][chiave])), []).append(percorso)
    for (f, cosa), quali in sorted(gruppi.items()):
        n += 1
        righe.append('  su %d %s %s (per esempio %s): %s' % (len(quali), 'pagina' if len(quali) == 1 else 'pagine', f,
                                                             quali[0], cosa))
    conti = {}
    for i, lato in enumerate(('principale', 'qui')):
        per_tipo = Counter({t: 0 for _, *c in pagine for t in c[i]['cornici']})
        per_tipo.update(v.split(' ', 1)[0] for v in catalogo[lato]['voci'])
        conti[lato] = ', '.join('%s %d' % kv for kv in sorted(per_tipo.items())) or 'nessuna'
    testa = 'CORNICE (fuori dal confronto delle pagine, confrontata una volta su %d pagine; tipi e voci: principale %s; ' \
            'qui %s)' % (sum(1 for _, ca, cb in pagine if ca['cornici'] or cb['cornici']), conti['principale'], conti['qui'])
    return ([testa] + righe if righe else []), n, approvate, testa


def main():
    par = argparse.ArgumentParser(description='Confronta il programma di oggi con questa cartella.')
    par.add_argument('--principale', default='origin/ccr-07f8e160-7j5lup')
    par.add_argument('--massimo', type=int, default=3000)
    par.add_argument('--per-forma', type=int, default=4, help='quante pagine dello stesso tipo (0 = tutte)')
    par.add_argument('--senza-testo', action='store_true')
    par.add_argument('--qui', default=QUI, help='la cartella da confrontare (di solito questa)')
    par.add_argument('--senza-pdf', action='store_true', help='non confrontare in PDF i 17 fogli e pagine che si stampano')
    par.add_argument('--fogli-per-tipo', type=int, default=3, help='quante pagine di ogni foglio da stampare')
    par.add_argument('--senza-approvati', action='store_true', help='conta anche i cambiamenti approvati')
    par.add_argument('--con-ordine', action='store_true',
                     help='collegamenti, segni, testo, moduli e campi anche nel loro ordine (come fino alla tappa 1)')
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
        regole = [] if arg.senza_approvati else leggi_approvati(os.path.join(QUI, 'strumenti', 'cambiamenti_approvati.txt'))
        approvate = 0                       # pagine diverse solo per cambiamenti approvati
        n, viste = 0, []                    # viste: (percorso, modelli che l'hanno fatta, byte) delle pagine 200
        catalogo = {lato: {k: set() for k in CATALOGO} for lato in ('principale', 'qui')}
        cornici = []                        # (percorso, cornice del principale, cornice di qui) delle pagine HTML
        con_ordine = arg.con_ordine
        while coda and n < arg.massimo:
            percorso = coda.pop(0)
            n += 1
            def due():
                sa, ia, ca = leggi(porte['principale'], percorso)
                a = riassunto(sa, ia, ca, not arg.senza_testo, cartelle['principale'], con_ordine)
                b = riassunto(*leggi(porte['qui'], percorso), not arg.senza_testo, cartelle['qui'], con_ordine)
                return a[0], a[1], b[0], (sa, ia.get('X-Modelli'), len(ca)), (a[2], b[2])
            ra, la, rb, (sa, modelli, byte), cc = due()
            if sa == 200:
                viste.append((percorso, modelli, byte))
            if not uguali(*applica_approvati(ra, rb, regole, con_ordine)):  # l'ora può scattare fra le due richieste: una volta ancora
                ra, la, rb, _, cc = due()
            if not uguali(ra, rb) and uguali(*applica_approvati(ra, rb, regole, con_ordine)):
                approvate += 1
            elif not uguali(ra, rb):
                ra, rb = applica_approvati(ra, rb, regole, con_ordine)
                diverse.append(percorso)
                righe.append('DIVERSA %s\n  %s' % (percorso, '\n  '.join(differenze(ra, rb))))
            vuota = {'voci': [], 'segni': [], 'testo': [], 'cornici': [], 'accese': [], 'indirizzi': {}, 'messaggi': []}
            if cc[0] is not None or cc[1] is not None:     # la cornice delle due pagine, da confrontare alla fine
                cornici.append((percorso, cc[0] or vuota, cc[1] or vuota))
                for lato, c in zip(('principale', 'qui'), cc):
                    for k in CATALOGO:
                        catalogo[lato][k].update((c or vuota).get(k, ()))
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
        righe_c, d_c, approvate_c, testa_c = confronta_cornice(catalogo, cornici, regole)
        righe = righe_c + righe
        n_f = d_f = 0
        # una cartella nuova a ogni giro (due giri insieme non si pestano i piedi); resta solo con dei fogli diversi
        cartella_fogli = tempfile.mkdtemp(prefix='confronto_rami-%s-fogli-' % NOME)
        if not arg.senza_pdf:                # i fogli da stampare in PDF, con i due programmi ancora accesi
            r_f, n_f, d_f, mancanti = confronta_fogli(porte, viste, cartella_fogli, arg.fogli_per_tipo)
            righe += r_f
            d_f += len(mancanti)             # un foglio mai incontrato non deve passare in silenzio
        if not os.listdir(cartella_fogli):
            os.rmdir(cartella_fogli)
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
        print('confronto %s' % ('con l\'ordine (--con-ordine)' if con_ordine else
                                'senza ordine: collegamenti, segni, testo, moduli e campi come insiemi con le quantità'))
        if regole:
            print('pagine diverse solo per i cambiamenti approvati (strumenti/cambiamenti_approvati.txt, %d regole): %d'
                  % (len(regole), approvate))
        print('resoconto: %s' % resoconto)
        if not arg.senza_pdf:
            print('%d fogli e pagine che si stampano confrontati in PDF, %d diversi o mancanti%s' % (
                n_f, d_f, ' (immagini in %s)' % cartella_fogli if d_f else ''))
        print('%s: %d differenze%s' % (testa_c, d_c, ', %d parti diverse solo per i cambiamenti approvati' % approvate_c
                                       if regole else ''))
        print('%d pagine confrontate, %d diverse' % (n, len(diverse)))
        return 1 if diverse or d_f or d_c else 0
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
