# -*- coding: utf-8 -*-
"""Le pagine come sono fatte dentro (tappa 1 della base, 21/11/2026).

Si parte da tutte le pagine GET senza parametri (indirizzi.txt) e si seguono i collegamenti interni, ogni tipo di
pagina al massimo due volte (il tipo: l'indirizzo con le cifre scritte N e i nomi dei parametri). In ogni pagina:
- nessun modulo dentro un altro modulo (il browser butta via quello interno: i suoi campi finiscono nel primo);
- nessun id ripetuto (un'etichetta, un aiuto della guida o uno script prenderebbero l'elemento sbagliato);
- niente caricato da internet: script, fogli di stile, immagini, caratteri e cornici vengono dal programma (in
  clinica internet può mancare, e una pagina non deve dire a nessuno fuori chi la sta guardando).
Lo stesso per i fogli di stile in static/. I gemelli: lo stesso controllo trova i tre difetti in una pagina fatta
apposta, e nelle pagine vere vede davvero moduli, id e risorse del programma (altrimenti passerebbe da solo).
Dal 22/11/2026 anche il menu: ogni pagina intera lo ha una volta sola, tranne i fogli da stampare e la dashboard nel
modo schermo (?schermo=1), che devono esserne senza; prove_senza_menu.py prova quelle una per una, con la gemella.

    python prove_pagine.py
"""
import collections
import os
import re
import shutil
import sys
import tempfile
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urljoin, urlsplit

from prove_dove import dove

CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = tempfile.mkdtemp(prefix='prove-pagine-')

import seed  # noqa: E402
import app as A  # noqa: E402

A.app.config['TESTING'] = True
A.Sessione = seed.popola('sqlite:///' + os.path.join(PROVVISORIA, 'prove.db'))
C = A.app.test_client()
esiti = []

ESTERNO = re.compile(r'^\s*(https?:)?//', re.I)
URL_ESTERNO = re.compile(r'(url\(\s*[\'"]?\s*(https?:)?//|@import\s+[\'"]\s*(https?:)?//)', re.I)


def prova(nome, f):
    try:
        esiti.append(('OK', nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', nome, '%s · %s' % (dove(e), str(e) or 'asserzione fallita')))
    except Exception as e:
        esiti.append(('ERRORE', nome, '%s · %r' % (dove(e), e)))


class Guarda(HTMLParser):
    """Moduli annidati, id ripetuti e risorse da fuori in una pagina; conta anche quello che vede."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.id = collections.Counter()
        self.aperti = 0
        self.moduli = 0
        self.annidati = []
        self.esterni = []
        self.risorse = 0              # script, fogli di stile e immagini del programma
        self.collegamenti = []
        self._stile = False
        self.menu = 0                 # quanti nav.menu: lo stesso selettore del browser, della guida e di prove_senza_menu
        self.funzione = None          # data-pagina del <body>: la funzione che ha fatto la pagina

    def handle_starttag(self, tag, attrs):
        a = {k: (v or '') for k, v in attrs}
        if a.get('id'):
            self.id[a['id']] += 1
        if tag == 'nav' and 'menu' in a.get('class', '').split():
            self.menu += 1
        if tag == 'body':
            self.funzione = a.get('data-pagina')
        if tag == 'form':
            self.moduli += 1
            if self.aperti:
                self.annidati.append(a.get('action', '') or '(senza action)')
            self.aperti += 1
        if tag == 'a' and a.get('href'):
            self.collegamenti.append(a['href'])
        if tag == 'style':
            self._stile = True
        # quello che il browser va a prendere da solo (un collegamento <a> invece si apre solo se si clicca)
        for k in ('src', 'srcset', 'poster', 'data', 'background'):
            if a.get(k) and ESTERNO.match(a[k]):
                self.esterni.append('<%s %s="%s">' % (tag, k, a[k]))
        if tag == 'link' and a.get('href') and ESTERNO.match(a['href']):
            self.esterni.append('<link href="%s">' % a['href'])
        if tag in ('form',) and a.get('action') and ESTERNO.match(a['action']):
            self.esterni.append('<form action="%s">' % a['action'])
        if a.get('style') and URL_ESTERNO.search(a['style']):
            self.esterni.append('<%s style="%s">' % (tag, a['style'][:80]))
        if (tag == 'script' and a.get('src')) or (tag == 'link' and a.get('href')) or (tag == 'img' and a.get('src')):
            if not ESTERNO.match(a.get('src') or a.get('href') or ''):
                self.risorse += 1

    def handle_endtag(self, tag):
        if tag == 'form' and self.aperti:
            self.aperti -= 1
        if tag == 'style':
            self._stile = False

    def handle_data(self, data):
        if self._stile and URL_ESTERNO.search(data):
            self.esterni.append('<style> %s' % URL_ESTERNO.search(data).group(0))

    def ripetuti(self):
        return sorted(k for k, v in self.id.items() if v > 1)


def guarda(testo):
    g = Guarda()
    g.feed(testo)
    return g


def forma(percorso):
    u = urlsplit(percorso)
    return re.sub(r'\d+', 'N', u.path) + '?' + '&'.join(sorted({k for k, _ in parse_qsl(u.query, keep_blank_values=True)}))


def interni(base, collegamenti):
    for h in collegamenti:
        if h.startswith(('mailto:', 'tel:', 'javascript:', '#', 'data:')):
            continue
        u = urlsplit(urljoin('http://localhost' + base, h))
        if u.hostname not in ('localhost', None) or u.path.startswith('/static/'):
            continue
        yield u.path + ('?' + u.query if u.query else '')


def giro():
    """Tutte le pagine HTML raggiungibili, ogni tipo al massimo due volte: {indirizzo: Guarda}."""
    with open(os.path.join(CARTELLA, 'indirizzi.txt'), encoding='utf-8') as f:
        coda = [r.split('\t')[1] for r in f.read().splitlines()
                if r.count('\t') == 3 and 'GET' in r.split('\t')[0].split(',')]
    assert len(coda) >= 60, 'indirizzi.txt ha solo %d pagine senza parametri' % len(coda)
    visti, per_forma, pagine = set(coda), collections.Counter(forma(x) for x in coda), {}
    while coda:
        p = coda.pop(0)
        r = C.get(p)
        if r.status_code != 200 or 'text/html' not in (r.content_type or ''):
            continue
        g = pagine[p] = guarda(r.get_data(as_text=True))
        for x in interni(p, g.collegamenti):
            if x in visti:
                continue
            visti.add(x)
            if per_forma[forma(x)] >= 2:
                continue
            per_forma[forma(x)] += 1
            coda.append(x)
    return pagine


PAGINE = giro()


def p_quante():
    assert len(PAGINE) >= 250, 'il giro ha visto solo %d pagine: i collegamenti non si seguono più?' % len(PAGINE)
    return '%d pagine' % len(PAGINE)


def p_annidati():
    male = {p: g.annidati for p, g in PAGINE.items() if g.annidati}
    assert not male, 'moduli dentro altri moduli: %s' % sorted(male.items())[:5]


def p_id():
    male = {p: g.ripetuti() for p, g in PAGINE.items() if g.ripetuti()}
    assert not male, 'id ripetuti: %s' % sorted(male.items())[:5]


def p_esterni():
    male = {p: g.esterni for p, g in PAGINE.items() if g.esterni}
    assert not male, 'risorse prese da internet: %s' % sorted(male.items())[:5]


def p_fogli_di_stile():
    cartella = os.path.join(CARTELLA, 'static')
    fogli = [n for n in os.listdir(cartella) if n.endswith('.css')]
    assert fogli, 'nessun foglio di stile in static/'
    male = []
    for n in fogli:
        with open(os.path.join(cartella, n), encoding='utf-8') as f:
            testo = re.sub(r'/\*.*?\*/', '', f.read(), flags=re.S)       # i commenti non si caricano
        male += ['%s: %s' % (n, m.group(0)) for m in URL_ESTERNO.finditer(testo)]
    assert not male, 'fogli di stile che prendono qualcosa da internet: %s' % male[:5]
    return '%d fogli' % len(fogli)


# le pagine senza menu: i fogli da stampare sempre, la dashboard solo con ?schermo=1 (prove_senza_menu.py le prova
# una per una, con la gemella; lì anche le tre che il giro non vede, perché seed.py non ha moduli da stampare,
# tariffari e strutture del gruppo)
SENZA_MENU = {'viste.stampa', 'segreteria.agenda_medico', 'sala.lista_operatoria', 'cruscotto.riepilogo',
              'viste.promemoria', 'documenti.stampa_modulo', 'guida.stampa', 'dovesifa.stampa', 'tariffari.stampa'}
SENZA_MENU_SCHERMO = {'live.pagina', 'live.statistiche'}


def p_menu():
    """Ogni pagina intera ha il menu una volta sola, tranne quelle che devono farne a meno."""
    sconosciute = sorted((SENZA_MENU | SENZA_MENU_SCHERMO) - set(A.app.view_functions))
    assert not sconosciute, 'nell\'elenco delle pagine senza menu ci sono funzioni che non esistono più: %s' % sconosciute
    male, senza, guardate = [], set(), 0
    for p, g in PAGINE.items():
        if g.funzione is None:                      # un pezzo di pagina, senza <body> (i risultati di Dove si fa)
            continue
        guardate += 1
        schermo = ('schermo', '1') in parse_qsl(urlsplit(p).query)
        atteso = 0 if g.funzione in SENZA_MENU or (schermo and g.funzione in SENZA_MENU_SCHERMO) else 1
        if g.menu != atteso:
            male.append('%s (%s): %d menu, attesi %d' % (p, g.funzione, g.menu, atteso))
        if not g.menu:
            senza.add(g.funzione)
    # il gemello dei «senza menu»: lo stesso selettore trova il menu nelle altre pagine, e le pagine si riconoscono
    con = sum(1 for g in PAGINE.values() if g.funzione is not None and g.menu)
    assert guardate >= len(PAGINE) * 0.9, 'solo %d pagine su %d hanno data-pagina nel <body>' % (guardate, len(PAGINE))
    assert con >= 200, 'il menu si vede solo in %d pagine: il selettore non lo trova più?' % con
    assert not male, male[:5]
    return '%d pagine con il menu, %d senza (%s)' % (con, guardate - con, ', '.join(sorted(senza)))


def g_trova_i_difetti():
    """Il gemello del controllo: in una pagina fatta apposta trova tutti e tre i difetti, in ogni forma."""
    g = guarda('<form action="/fuori"><input id="a"><form action="/dentro"></form></form><p id="a"></p>'
               '<script src="https://esempio.invalid/x.js"></script><link rel="stylesheet" href="//esempio.invalid/c.css">'
               '<img src="HTTP://esempio.invalid/i.png"><div style="background:url( \'https://esempio.invalid/f.png\')">'
               '</div><style>@import "https://esempio.invalid/font.css";</style>')
    assert g.annidati == ['/dentro'], g.annidati
    assert g.ripetuti() == ['a'], g.ripetuti()
    assert len(g.esterni) == 5, g.esterni
    pulita = guarda('<form action="/uno"></form><form action="/due"><input id="b"></form><a href="https://esempio.invalid">'
                    'fuori, ma solo se si clicca</a><script src="/static/x.js"></script><img src="/logo/1">')
    assert not (pulita.annidati or pulita.ripetuti() or pulita.esterni), (pulita.annidati, pulita.ripetuti(), pulita.esterni)


def g_vede_le_pagine():
    """Il gemello sulle pagine vere: i controlli sopra hanno guardato moduli, id e risorse veri."""
    moduli = sum(g.moduli for g in PAGINE.values())
    con_id = sum(1 for g in PAGINE.values() if g.id)
    risorse = sum(g.risorse for g in PAGINE.values())
    assert moduli >= 200, 'nelle pagine si vedono solo %d moduli' % moduli
    assert con_id >= len(PAGINE) * 0.8, 'solo %d pagine su %d hanno degli id' % (con_id, len(PAGINE))
    assert risorse >= len(PAGINE) * 2, 'solo %d risorse del programma in %d pagine' % (risorse, len(PAGINE))
    return '%d moduli, %d risorse del programma' % (moduli, risorse)


prova('il giro vede le pagine del programma', p_quante)
prova('nessun modulo dentro un altro modulo', p_annidati)
prova('nessun id ripetuto nella stessa pagina', p_id)
prova('niente caricato da internet nelle pagine', p_esterni)
prova('niente caricato da internet nei fogli di stile', p_fogli_di_stile)
prova('il menu c\'è, una volta sola, tranne nei fogli da stampare e nel modo schermo', p_menu)
prova('gemello: il controllo trova moduli annidati, id ripetuti e risorse da internet', g_trova_i_difetti)
prova('gemello: nelle pagine vere il controllo vede moduli, id e risorse', g_vede_le_pagine)

shutil.rmtree(PROVVISORIA, ignore_errors=True)
for esito, nome, dettaglio in esiti:
    print('%-6s %s %s' % (esito, nome, dettaglio))
rotte = [e for e in esiti if e[0] != 'OK']
print('%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(rotte), len(rotte)))
sys.exit(1 if rotte else 0)
