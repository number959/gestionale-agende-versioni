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
import traceback
from datetime import date
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urljoin, urlsplit

import jinja2

from prove_dove import dove

CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = tempfile.mkdtemp(prefix='prove-pagine-')

import seed  # noqa: E402
import app as A  # noqa: E402
import aggiornamenti as AG  # noqa: E402

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
        self.fonti = []               # src degli script e href dei <link>
        self.main = 0                 # quanti <main>
        self.menu_in_main = False     # un nav.menu dentro il <main>
        self._in_main = 0
        self.griglie = []             # data-giorno di ogni table.griglia (None se non c'e')
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
        if tag == 'main':
            self.main += 1
            self._in_main += 1
        if tag == 'nav' and 'menu' in a.get('class', '').split() and self._in_main:
            self.menu_in_main = True
        if (tag == 'script' and a.get('src')) or (tag == 'link' and a.get('href')):
            self.fonti.append(a.get('src') or a.get('href'))
        if tag == 'table' and 'griglia' in a.get('class', '').split():
            self.griglie.append(dict(attrs).get('data-giorno'))
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
        if tag == 'main' and self._in_main:
            self._in_main -= 1
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
        try:
            r = C.get(p)
        except Exception as e:                       # con le variabili rigide la pagina cade: si dice dove
            nel_modello = [f for f in traceback.extract_tb(e.__traceback__) if f.filename.endswith('.html')]
            CADUTE[p] = '%s · %s' % ('%s:%d' % (os.path.basename(nel_modello[-1].filename), nel_modello[-1].lineno)
                                     if nel_modello else dove(e), e)
            continue
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


CADUTE = {}
PAGINE = giro()


def p_nessuna_cade():
    assert not CADUTE, 'pagine che cadono: %s' % sorted(CADUTE.items())[:5]


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


def p_main():
    """Ogni pagina fatta con base.html ha un <main> solo (dove comincia il contenuto, per i lettori di schermo), con
    il menu fuori."""
    con_base = {p: g for p, g in PAGINE.items() if '/static/gestionale.js' in g.fonti}
    male = {p: (g.main, g.menu_in_main) for p, g in con_base.items() if g.main != 1 or g.menu_in_main}
    assert len(con_base) >= 200, len(con_base)
    assert not male, 'pagine con il <main> sbagliato (quanti, menu dentro): %s' % sorted(male.items())[:5]
    return '%d pagine' % len(con_base)


def g_main():
    """Il gemello: il controllo conta i <main> e vede un menu messo dentro."""
    assert guarda('<nav class="menu"></nav><main><p>x</p></main>').main == 1
    due = guarda('<main></main><main><nav class="barra menu"></nav></main>')
    assert due.main == 2 and due.menu_in_main, (due.main, due.menu_in_main)


def g_variabili_rigide():
    """Il gemello delle variabili rigide: nelle prove una variabile che manca, scritta, ferma la pagina; in un if no."""
    env = A.app.jinja_env
    assert env.undefined is A.VariabileMancante, 'le prove girano senza GESTIONALE_PROVE_RIGIDE=1'
    for t in ('{{ manca }}', '{{ x.manca }}', '{% for y in manca %}{% endfor %}', '{{ manca|length }}',
              '{{ manca ~ "a" }}'):
        try:
            env.from_string(t).render(x={})
        except jinja2.UndefinedError:
            continue
        raise AssertionError('una variabile che manca non ferma la pagina: %s' % t)
    # permessi: if, ==, in, |default, is defined, e l'if in linea senza else (Jinja usa il suo Undefined di base)
    t = ("{% if manca %}a{% elif manca == 1 or 'b' in manca %}b{% endif %}{{ manca|default('c') }}"
         "{{ 'd' if manca is defined else 'e' }}{{ 'f' if manca }}")
    assert env.from_string(t).render() == 'ce', env.from_string(t).render()


def righe_della_variante(g, animata):
    """Cosa non torna, in una pagina, con le righe della sola animata (lista vuota: tutto a posto)."""
    male = []
    if '/static/gestionale.js' in g.fonti:                                  # le pagine con base.html
        for f in ('/static/animazioni.css', '/static/animazioni.js'):
            if (f in g.fonti) != animata:
                male.append(f)
    if any((d is not None) != animata for d in g.griglie):
        male.append('data-giorno della griglia')
    if 'stato-tema' in g.id and ('aspetto' in g.id) != animata:              # Impostazioni
        male.append('riquadro Animazioni')
    return male


def p_variante():
    """base.html, griglia.html e impostazioni.html sono gli stessi nelle due cartelle: le righe della sola animata
    ci sono tutte nell'animata e nessuna nella normale."""
    animata = AG.VARIANTE == 'animata'
    male = {p: righe_della_variante(g, animata) for p, g in PAGINE.items() if righe_della_variante(g, animata)}
    assert not male, 'versione %s, righe sbagliate: %s' % (AG.VARIANTE, sorted(male.items())[:5])
    con_base = sum(1 for g in PAGINE.values() if '/static/gestionale.js' in g.fonti)
    griglie = sum(len(g.griglie) for g in PAGINE.values())
    impostazioni = sum(1 for g in PAGINE.values() if 'stato-tema' in g.id)
    assert con_base >= 200 and griglie and impostazioni, (con_base, griglie, impostazioni)
    return '%s: %d pagine con base.html, %d griglie, %d Impostazioni' % (AG.VARIANTE, con_base, griglie, impostazioni)


def g_variante():
    """Il gemello: con la variante dell'altra versione le stesse pagine cambiano tutte e tre le cose (i modelli
    leggono davvero la variante, e app.py la passa a ogni pagina)."""
    vera = AG.VARIANTE
    AG.VARIANTE = 'normale' if vera == 'animata' else 'animata'
    try:
        imp = guarda(C.get('/impostazioni').get_data(as_text=True))
        gri = guarda(C.get('/giorno/%s?struttura=1' % date.today().isoformat()).get_data(as_text=True))
    finally:
        AG.VARIANTE = vera
    altra = vera != 'animata'
    assert gri.griglie, 'nessuna griglia nella pagina del giorno'
    assert sorted(righe_della_variante(imp, altra) + righe_della_variante(gri, altra)) == [], 'non reagiscono'
    assert len(righe_della_variante(imp, not altra)) == 3 and righe_della_variante(gri, not altra) == \
        ['/static/animazioni.css', '/static/animazioni.js', 'data-giorno della griglia'], 'il controllo non vede'


prova('il giro vede le pagine del programma', p_quante)
prova('nessuna pagina cade (variabili che mancano comprese)', p_nessuna_cade)
prova('nessun modulo dentro un altro modulo', p_annidati)
prova('nessun id ripetuto nella stessa pagina', p_id)
prova('niente caricato da internet nelle pagine', p_esterni)
prova('niente caricato da internet nei fogli di stile', p_fogli_di_stile)
prova('il menu c\'è, una volta sola, tranne nei fogli da stampare e nel modo schermo', p_menu)
prova('gemello: il controllo trova moduli annidati, id ripetuti e risorse da internet', g_trova_i_difetti)
prova('gemello: nelle pagine vere il controllo vede moduli, id e risorse', g_vede_le_pagine)
prova('le righe della sola animata solo nell\'animata (modelli comuni)', p_variante)
prova('gemello: con l\'altra variante le pagine cambiano', g_variante)
prova('gemello: le variabili che mancano fermano la pagina, negli if no', g_variabili_rigide)
prova('un <main> solo in ogni pagina con base.html, con il menu fuori', p_main)
prova('gemello: il controllo del <main> conta e vede il menu dentro', g_main)

shutil.rmtree(PROVVISORIA, ignore_errors=True)
for esito, nome, dettaglio in esiti:
    print('%-6s %s %s' % (esito, nome, dettaglio))
rotte = [e for e in esiti if e[0] != 'OK']
print('%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(rotte), len(rotte)))
sys.exit(1 if rotte else 0)
