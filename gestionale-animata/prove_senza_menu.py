# -*- coding: utf-8 -*-
"""Le pagine senza menu (tappa 1 della base, 22/11/2026).

Undici pagine non mostrano il menu di sinistra: i nove fogli da stampare, sempre, e due pagine della dashboard,
solo con ?schermo=1 (il modo schermo, per lo schermo grande). Per ognuna:
- la pagina risponde 200 ed è fatta dalla funzione giusta (data-pagina del <body>): anche una pagina d'errore
  (500, 404) è senza menu, e non deve passare per buona;
- il menu non c'è;
- il gemello: c'è, una volta sola, nella pagina gemella da cui la si apre (per il modo schermo: la stessa pagina
  senza ?schermo=1), cercato con lo stesso selettore e lo stesso modo di leggere la pagina.
Il selettore è nav.menu, lo stesso di prove_112_browser.py, dei passi della guida (guida.py) e di guida.js. Se il
menu cambia classe o posto, cadono le gemelle: le pagine «senza menu» non passano da sole.
In più: i modelli che tolgono il menu sono proprio questi undici, e il selettore vede il menu in ogni forma e solo
il menu. Il giro di prove_pagine.py controlla il menu in tutte le altre pagine.

    python prove_senza_menu.py
"""
import os
import re
import shutil
import sys
import tempfile
from datetime import date
from html.parser import HTMLParser

from prove_dove import dove

CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = tempfile.mkdtemp(prefix='prove-senza-menu-')

import seed  # noqa: E402
import app as A  # noqa: E402
from modelli import Appuntamento, ModuloStampa, StrutturaGruppo, Tariffario, VoceTariffario  # noqa: E402

A.app.config['TESTING'] = True
A.Sessione = seed.popola('sqlite:///' + os.path.join(PROVVISORIA, 'prove.db'))
C = A.app.test_client()
esiti = []

SELETTORE = 'nav.menu'          # lo stesso di prove_112_browser.py, dei passi della guida (guida.py) e di guida.js


def prova(nome, f):
    try:
        esiti.append(('OK', nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', nome, '%s · %s' % (dove(e), str(e) or 'asserzione fallita')))
    except Exception as e:
        esiti.append(('ERRORE', nome, '%s · %r' % (dove(e), e)))


class Guarda(HTMLParser):
    """Quanti elementi corrispondono al selettore «tag.classe» (come querySelectorAll nel browser) e la funzione
    che ha fatto la pagina (data-pagina del <body>)."""

    def __init__(self, selettore=SELETTORE):
        super().__init__(convert_charrefs=True)
        self.tag, _, self.classe = selettore.partition('.')
        self.menu = 0
        self.funzione = None

    def handle_starttag(self, tag, attrs):
        a = {k: (v or '') for k, v in attrs}
        if tag == self.tag and self.classe in a.get('class', '').split():
            self.menu += 1
        if tag == 'body':
            self.funzione = a.get('data-pagina')


def guarda(testo):
    g = Guarda()
    g.feed(testo)
    return g


def dati_di_prova():
    """Quello che seed.py non ha: un modulo da stampare, un tariffario con una voce, una struttura del gruppo.
    (In un database tutto suo: il giro di prove_pagine.py non li vede e resta com'è.)"""
    s = A.Sessione()
    a = s.query(Appuntamento).order_by(Appuntamento.id).first()
    m = ModuloStampa(nome='Consenso di prova', testo='Il paziente {paziente} ...', firma=True)
    t = Tariffario(nome='Tariffario di prova', voci=[VoceTariffario(sezione='Visite', nome='Visita', importo_cent=10000)])
    g = StrutturaGruppo(nome='Centro di prova', citta='Città di prova', telefono='081 000 0001')
    s.add_all([m, t, g])
    s.commit()
    uscita = {'aid': a.id, 'mid': m.id, 'tid': t.id, 'gid': g.id}
    s.close()
    return uscita


D = dati_di_prova()
OGGI = date.today().isoformat()
MESE = OGGI[:7]
GIORNO, SCHEDA = '/giorno/%s?struttura=1' % OGGI, '/appuntamento/%d' % D['aid']

# (cos'è, il modello, la pagina senza menu, la funzione che la fa, le gemelle con il menu). Le gemelle: la pagina
# da cui la si apre; per il modo schermo la stessa pagina senza ?schermo=1 e, per le statistiche, anche
# /ambulatori/riepilogo con ?schermo=1: stesso modello, ma fuori dalla dashboard il menu resta.
COPPIE = [
    ('la stampa del giorno', 'stampa.html', '/stampa/%s?struttura=1' % OGGI, 'viste.stampa', [GIORNO]),
    ('l\'agenda dei medici', 'agenda_medico.html', '/agenda-medico/%s?struttura=1' % OGGI,
     'segreteria.agenda_medico', [GIORNO]),
    ('la lista operatoria', 'lista_operatoria.html', '/lista-operatoria/%s?struttura=2' % OGGI,
     'sala.lista_operatoria', ['/sala/%s?struttura=2' % OGGI]),
    ('il riepilogo dei medici', 'riepilogo_medici.html', '/riepilogo-medici/%s' % MESE, 'cruscotto.riepilogo',
     ['/statistiche']),
    ('il promemoria per il paziente', 'promemoria.html', '/appuntamento/%d/promemoria' % D['aid'], 'viste.promemoria',
     [SCHEDA]),
    ('il modulo da stampare', 'stampa_modulo.html', '/appuntamento/%d/modulo/%d' % (D['aid'], D['mid']),
     'documenti.stampa_modulo', [SCHEDA]),
    ('la guida da stampare', 'aiuto_stampa.html', '/aiuto/stampa', 'guida.stampa', ['/aiuto']),
    ('«Dove si fa» da stampare', 'dove_stampa.html', '/dove-si-fa/stampa?gruppo=%d' % D['gid'], 'dovesifa.stampa',
     ['/dove-si-fa/?gruppo=%d' % D['gid']]),
    ('il tariffario da stampare', 'tariffario_stampa.html', '/cassa/tariffari/%d/stampa' % D['tid'],
     'tariffari.stampa', ['/cassa/tariffari/%d' % D['tid']]),
    ('il riepilogo live nel modo schermo', 'riepilogo_live.html', '/riepilogo-live?struttura=1&schermo=1',
     'live.pagina', ['/riepilogo-live?struttura=1']),
    ('le statistiche nel modo schermo', 'ambulatori_riepilogo.html',
     '/riepilogo-live/statistiche?struttura=1&schermo=1', 'live.statistiche',
     ['/riepilogo-live/statistiche?struttura=1', '/ambulatori/riepilogo?struttura=1&schermo=1']),
]


def pagina(url):
    """La pagina letta dal parser: 200 e HTML, altrimenti la prova cade (anche una pagina d'errore è senza menu)."""
    r = C.get(url)
    assert r.status_code == 200 and 'text/html' in (r.content_type or ''), \
        '%s risponde %s %s' % (url, r.status_code, r.content_type)
    return guarda(r.get_data(as_text=True))


def senza_menu(senza, funzione, gemelle):
    def p():
        g = pagina(senza)
        assert g.funzione == funzione, '%s è fatta da %s, non da %s' % (senza, g.funzione, funzione)
        # prima il gemello: se il selettore non vede più il menu, il messaggio lo dice
        male = []
        for con in gemelle:
            h = pagina(con)
            if h.menu != 1:
                male.append('%s: %d menu (fatta da %s)' % (con, h.menu, h.funzione))
        assert not male, ('gemello: %r non c\'è, una volta sola, nemmeno dove deve esserci (il controllo «senza '
                          'menu» non vedrebbe niente): %s' % (SELETTORE, '; '.join(male)))
        assert g.menu == 0, '%s: %d menu, la pagina deve esserne senza' % (senza, g.menu)
        return 'con il menu: %s' % ', '.join(gemelle)
    return p


# il blocco del menu scritto in ogni modo che Jinja accetta: {% block menu %}, {%- block menu -%}, {%block menu%}
BLOCCO_MENU = re.compile(r'\{%[-+]?\s*block\s+menu\s*[-+]?%\}')


def p_undici():
    """I modelli che cambiano il blocco del menu di base.html sono proprio quelli dell'elenco. (Legato a come sono
    fatti i modelli oggi: quando la veste nuova toglie il menu in un altro modo, si riscrive.)"""
    cartella = os.path.join(CARTELLA, 'templates')
    tolti = set()
    for n in os.listdir(cartella):
        if n.endswith('.html') and n != 'base.html':
            with open(os.path.join(cartella, n), encoding='utf-8') as f:
                if BLOCCO_MENU.search(f.read()):
                    tolti.add(n)
    attesi = {c[1] for c in COPPIE}
    assert tolti == attesi, 'modelli che tolgono il menu e non sono nell\'elenco: %s; nell\'elenco e non lo tolgono ' \
                            'più: %s' % (sorted(tolti - attesi), sorted(attesi - tolti))
    assert len(attesi) == len(COPPIE) == 11, (len(attesi), len(COPPIE))
    return '%d modelli' % len(tolti)


def g_selettore():
    """Il gemello del selettore e del blocco del menu: vedono il menu scritto in altri modi, e non vedono quello che
    menu non è."""
    assert guarda('<nav class="menu" aria-label="Pagine"></nav>').menu == 1
    assert guarda('<nav aria-label="Pagine" class="barra menu"></nav>').menu == 1
    assert guarda('<nav class="menu-secondario"></nav><div class="menu"></div><nav class="passi"></nav>'
                  '<p>Apri il menu a sinistra</p>').menu == 0
    assert guarda('<body class="x" data-pagina="viste.giorno">').funzione == 'viste.giorno'
    # e il blocco del menu nei modelli (p_undici): in ogni forma, e non un altro blocco che comincia con «menu»
    assert all(BLOCCO_MENU.search(m) for m in ('{% block menu %}{% endblock %}', '{%- block menu -%}{%- endblock -%}',
                                                 '{%block menu%}{%endblock%}', '{%+ block  menu %}'))
    assert not BLOCCO_MENU.search('{% block menu_extra %}{% endblock %}{% block menubar %}{% block corpo %}')


prova('i modelli che tolgono il menu sono gli undici dell\'elenco', p_undici)
for nome, _, senza, funzione, gemelle in COPPIE:
    prova('%s: senza menu, con il menu nella gemella' % nome, senza_menu(senza, funzione, gemelle))
prova('gemello: il selettore e il blocco del menu lo vedono in ogni forma, e solo il menu', g_selettore)

shutil.rmtree(PROVVISORIA, ignore_errors=True)
for esito, nome, dettaglio in esiti:
    print('%-6s %s %s' % (esito, nome, dettaglio))
rotte = [e for e in esiti if e[0] != 'OK']
print('%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(rotte), len(rotte)))
sys.exit(1 if rotte else 0)
