# -*- coding: utf-8 -*-
"""Il menu fatto da menu.py e la cornice che lo disegna (tappa 2 della base, 22/11/2026).

Dalla tappa 2 voci, linguette, tendina Aiuto e collegamenti nascosti stanno in un elenco in menu.py; la cornice nuova
li disegna: templates/_menu.html il menu a sinistra, _barra.html la barra in alto, _linguette.html le linguette della
voce accesa in cima al contenuto. Qui:
- ogni voce, linguetta, voce della tendina Aiuto e collegamento nascosto si costruisce con url_for: la funzione
  della pagina esiste e gli argomenti che porta bastano al suo indirizzo, e la sua icona c'è in _icone.html (e i
  moduli possono aggiungere voci con registra_voce, che rifiuta una sezione, una chiave o un tasto già presi);
- ogni pagina senza parametri (indirizzi.txt) accende una voce sola e, se la sua voce ha le linguette, una linguetta
  sola (mai nessuna), nell'elenco di menu.py e nella cornice disegnata (aria-current), le stesse;
- da una pagina della seconda struttura, in un giorno che non è oggi, ogni voce e ogni linguetta porta ancora
  struttura e giorno (un difetto così c'è stato: «Nuovo appuntamento» dalla seconda struttura proponeva la prima,
  LEGGIMI.md, storico dei difetti), e ogni collegamento disegnato è una voce di menu.py; nel disegno, anche senza
  menu.py, ogni collegamento della cornice porta la struttura, tranne quelli di SENZA_STRUTTURA (come nel menu di prima);
- i tasti G, E, C e D: il primo [data-tasto] della pagina (quello che gestionale.js clicca) porta dove deve;
- il percorso della barra in alto: il nome della struttura della pagina (non per Pazienti, Configura e Aiuto), la voce
  accesa e la linguetta della pagina, letti dal disegno e dal database, non da menu.percorso;
- ogni linguetta che nel menu di prima aveva una riga piccola la porta nel title;
- le linguette accese per pagina («pagine», come serviranno alla Cassa nella tappa 6) e le condizioni anche su
  linguette e collegamenti nascosti; registra_voce rifiuta una voce senza icona o con un'icona che non c'è;
- il lanciatore (strumenti/confronta_rami.py) vede gli indirizzi della cornice di ogni pagina anche per le voci che
  hanno cambiato nome, e una seconda voce accesa (le sue regole approvate non la coprono);
- le parole, gli indirizzi, i tasti e i data-guida delle voci sono quelli del menu di prima: l'oracolo è il menu del
  ramo principale, prove_menu_principale.html, una copia ferma del suo templates/_menu.html (byte per byte; se git e il
  ramo ci sono, la prova lo controlla), disegnato sulla stessa pagina e confrontato voce per voce. Le sole parole nuove
  sono in PAROLE_NUOVE, con il perché.
Ogni controllo ha il suo gemello: lo stesso controllo, su una copia guastata apposta, deve trovare il guasto.

    python prove_menu.py
"""
import copy
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlsplit

from prove_dove import dove

CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = tempfile.mkdtemp(prefix='prove-menu-')

import flask  # noqa: E402
import seed  # noqa: E402
import app as A  # noqa: E402
import menu as M  # noqa: E402
from modelli import Appunto, Risorsa, Struttura  # noqa: E402

sys.path.append(os.path.join(CARTELLA, 'strumenti'))
import confronta_rami as CR  # noqa: E402

A.app.config['TESTING'] = True
A.Sessione = seed.popola('sqlite:///' + os.path.join(PROVVISORIA, 'prove.db'))
C = A.app.test_client()
esiti = []

CON_MENU = re.compile(r'<nav class="menu[ "]')                  # il menu, nella cornice nuova (class="menu v-menu")
PRINCIPALE = os.path.join(CARTELLA, 'prove_menu_principale.html')
RAMO_PRINCIPALE = 'origin/ccr-07f8e160-7j5lup'
# le parole nuove della veste (che oggi nel menu non ci sono): (tipo, voce, parola)
PAROLE_NUOVE = {
    ('voce', 'agenda', 'Agenda'),       # Giorno, Settimana, Mese ed Elenco diventano le linguette della voce Agenda
                                        # (piano/piano/s4.md, tappa 2; tavole Nefro-*): oggi si chiama Giorno
    ('linguetta', 'agenda', 'Elenco'),  # la quarta linguetta dell'Agenda (s4.md: «Giorno · Settimana · Mese · Elenco»):
                                        # oggi è «Elenco del giorno» nella tendina Segreteria
}
# l'unica voce che si accende in un altro posto: l'Elenco del giorno oggi accende la tendina Segreteria, nella veste
# nuova la voce Agenda (tavola Nefro-Agenda4, «Agenda › Elenco»; ricognizione della cornice)
ACCESA_ALTROVE = {'elenco': ('Segreteria', 'agenda')}
# come il menu di prima (in alto, con le tendine) disegnava le voci di menu.py (scritto qui, non in menu.py: serve solo
# a questo confronto): le linguette dell'Agenda stavano in fila nel menu (Giorno, Settimana, Mese); una voce con
# linguette (Ambulatori, Segreteria, Configura) o con una tendina (Aiuto) era una tendina; le altre un collegamento.
# La linguetta Elenco dell'Agenda lì non c'era (stava nella tendina Segreteria come «Elenco del giorno»); la linguetta
# «Aree e accessi» di Configura (1.13, registrata da accessi.py) nemmeno: la sua pagina nel ramo principale non c'è
# (strumenti/cambiamenti_approvati.txt, regola «nuova»), e lì si accende lei sola, dove il menu di prima non accende niente
IN_FILA = {'agenda'}
NON_NEL_MENU_DI_PRIMA = {('agenda', 'Elenco'), ('configura', 'Aree e accessi')}


def come_era(v):
    """Come il menu di prima disegnava la voce v (fatta da menu.costruisci): 'in_fila', 'tendina' o 'voce'."""
    return 'in_fila' if v['chiave'] in IN_FILA else 'tendina' if v['linguette'] or v['tendina'] else 'voce'

OGGI = date.today()
ALTRO = OGGI + timedelta(days=9)                    # un giorno che non è oggi (e nemmeno di questa settimana)
D = ALTRO.isoformat()
PAGINE_SECONDA = ['/giorno/%s?struttura=2' % D, '/settimana/%s?struttura=2' % D, '/mese/%s?struttura=2' % D[:7],
                  '/giorno/%s/elenco?struttura=2' % D, '/chiusura/%s?struttura=2' % D, '/cassa/%s?struttura=2' % D,
                  '/sala/%s?struttura=2' % D, '/ambulatori/settimana/%s?struttura=2' % D,
                  '/esportazioni?data=%s&struttura=2' % D]


def prova(nome, f):
    try:
        esiti.append(('OK', nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', nome, '%s · %s' % (dove(e), str(e) or 'asserzione fallita')))
    except Exception as e:
        esiti.append(('ERRORE', nome, '%s · %r' % (dove(e), e)))


# ---------------------------------------------------------------- leggere il menu disegnato
class LeggiMenu(HTMLParser):
    """Il menu di prima (nav.menu del ramo principale, l'oracolo): i collegamenti con parola, riga piccola, tasto,
    guida, accesa (classe attivo e aria-current) e la tendina in cui stanno; le tendine con parola, guida e accesa."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.dentro = 0                     # profondità dentro nav.menu
        self.pila = []                      # i tag aperti dentro il menu
        self.collegamenti, self.tendine = [], []
        self.a = self.tendina = None
        self.dove = None                    # dove va il testo: 'parola', 'sotto', 'bottone' o None
        self.salta = 0                      # dentro uno span (contatore, freccia): il testo non conta

    def handle_starttag(self, tag, attrs):
        a = {k: (v if v is not None else '') for k, v in attrs}
        classi = a.get('class', '').split()
        if tag == 'nav' and 'menu' in classi and not self.dentro:
            self.dentro = 1
            return
        if not self.dentro:
            return
        if tag not in ('input', 'br', 'img'):
            self.pila.append((tag, classi))
        if tag == 'div' and 'gruppo' in classi:
            self.tendina = dict(parola='', guida=a.get('data-guida'), attivo='attivo' in classi, corrente=None,
                                a_destra='a-destra' in classi, voci=[])
            self.tendine.append(self.tendina)
        elif tag == 'button' and self.tendina is not None:
            self.tendina['corrente'] = a.get('aria-current')
            self.dove = 'bottone'
        elif tag == 'a':
            self.a = dict(href=a.get('href'), parola='', sotto=None, tasto=a.get('data-tasto'), guida=a.get('data-guida'),
                          attivo='attivo' in classi, corrente=a.get('aria-current'), azione_guida=a.get('data-azione-guida'),
                          tendina=self.tendina['parola'] if self.tendina is not None else None)
            self.collegamenti.append(self.a)
            if self.tendina is not None:
                self.tendina['voci'].append(self.a)
            self.dove = 'parola'
        elif tag == 'small' and self.a is not None:
            self.a['sotto'] = ''
            self.dove = 'sotto'
        elif tag == 'span':
            self.salta += 1

    def handle_endtag(self, tag):
        if not self.dentro:
            return
        if tag == 'nav' and not any(t == 'nav' for t, _ in self.pila):
            self.dentro = 0
            return
        while self.pila:
            t, classi = self.pila.pop()
            if t == 'span':
                self.salta -= 1
            if t == 'div' and 'gruppo' in classi:
                self.tendina = None
            if t == 'a':
                self.a = None
                self.dove = None
            if t in ('button', 'small'):
                self.dove = 'parola' if t == 'small' and self.a is not None else None
            if t == tag:
                break

    def handle_data(self, data):
        if not self.dentro or self.salta or self.dove is None:
            return
        if self.dove == 'bottone':
            self.tendina['parola'] += data.strip()
        elif self.dove == 'sotto':
            self.a['sotto'] += data
        elif self.dove == 'parola' and self.a is not None:
            self.a['parola'] += data


def leggi_menu(testo):
    m = LeggiMenu()
    m.feed(testo)
    for x in m.collegamenti:
        x['parola'] = ' '.join(x['parola'].split())
    return m


class LeggiCornice(HTMLParser):
    """La cornice nuova di una pagina: le voci del menu (collegamenti dentro nav.menu, anche nascosti, e i pulsanti
    delle tendine), le voci della tendina Aiuto, le linguette (i collegamenti dentro data-cornice="linguette") e il
    primo elemento di ogni data-tasto della pagina intera (quello che clicca gestionale.js). Per ognuno: indirizzo,
    parola (solo il testo, senza i contatori), tasto, guida, aria-current."""
    SENZA_FINE = ('input', 'br', 'img', 'path', 'circle', 'rect', 'line', 'meta', 'link')

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pila = []                       # (tag, dove, nella tendina, contatore)
        self.voci, self.tendine, self.aiuto, self.linguette = [], [], [], []
        self.primi_tasti = {}                # tasto -> indirizzo del primo elemento con quel data-tasto
        self.cosa = None                     # il pezzo a cui va il testo

    def handle_starttag(self, tag, attrs):
        a = {k: (v if v is not None else '') for k, v in attrs}
        classi = a.get('class', '').split()
        if a.get('data-tasto') and a['data-tasto'] not in self.primi_tasti:
            self.primi_tasti[a['data-tasto']] = a.get('href')
        if tag in self.SENZA_FINE:
            return
        sopra = self.pila[-1] if self.pila else (None, None, False, False)
        dove = 'menu' if tag == 'nav' and 'menu' in classi else (
            'linguette' if a.get('data-cornice') == 'linguette' else sopra[1])
        tendina = sopra[2] or (dove == 'menu' and tag == 'div' and 'tendina' in classi)
        contatore = sopra[3] or 'v-conta' in classi
        self.pila.append((tag, dove, tendina, contatore))
        if dove is None:
            return
        if tag == 'a':
            x = dict(href=a.get('href'), parola='', tasto=a.get('data-tasto'), guida=a.get('data-guida'),
                     corrente=a.get('aria-current'), nascosto='hidden' in a, titolo=a.get('title'), attivo='attivo' in classi)
            (self.linguette if dove == 'linguette' else self.aiuto if tendina else self.voci).append(x)
            self.cosa = x
        elif tag == 'button' and dove == 'menu':
            x = dict(parola='', corrente=a.get('aria-current'), espansa=a.get('aria-expanded'))
            self.tendine.append(x)
            self.cosa = x

    def handle_endtag(self, tag):
        if tag in self.SENZA_FINE:
            return
        while self.pila:
            t = self.pila.pop()[0]
            if t in ('a', 'button'):
                self.cosa = None
            if t == tag:
                break

    def handle_data(self, data):
        if self.cosa is not None and not (self.pila and self.pila[-1][3]):
            self.cosa['parola'] += data


def leggi_cornice(testo):
    c = LeggiCornice()
    c.feed(testo)
    for x in c.voci + c.tendine + c.aiuto + c.linguette:
        x['parola'] = ' '.join(x['parola'].split())
    return c


# ---------------------------------------------------------------- le pagine
CONTESTO = {}
FINALI = {}                                 # indirizzo chiesto -> percorso della pagina dove si arriva


@flask.template_rendered.connect_via(A.app)
def _contesto(sender, template, context, **extra):
    CONTESTO['ultimo'] = context            # l'ultimo modello disegnato: quello della pagina intera


def apri(url):
    """(risposta, testo, menu di menu.py, menu del ramo principale disegnato sulla stessa pagina) di una pagina."""
    CONTESTO.clear()
    with C:
        r = C.get(url, follow_redirects=True)
        FINALI[url] = r.request.path        # dove si arriva, dopo i rimandi: per il percorso della barra
        testo = r.get_data(as_text=True) if 'text/html' in (r.content_type or '') else ''
        fatti = getattr(flask.g, 'menu_fatti', None) or {}     # i menu fatti da menu_della_pagina: l'ultimo è della pagina
        menu = list(fatti.values())[-1] if fatti else None
        principale = None
        if menu is not None and 'ultimo' in CONTESTO:
            with open(PRINCIPALE, encoding='utf-8') as f:
                principale = A.app.jinja_env.from_string(f.read()).render(CONTESTO['ultimo'])
    return r, testo, menu, principale


def senza_parametri():
    with open(os.path.join(CARTELLA, 'indirizzi.txt'), encoding='utf-8') as f:
        return [r.split('\t')[1] for r in f.read().splitlines()
                if r.count('\t') == 3 and 'GET' in r.split('\t')[0].split(',')]


def tutte_le_voci(menu):
    """Ogni cosa del menu di una pagina con il suo tipo: (tipo, voce, cosa)."""
    for v in menu['voci']:
        yield 'voce', v['chiave'], v
        for x in v['linguette']:
            yield 'linguetta', v['chiave'], x
        for x in v['tendina']:
            yield 'aiuto', v['chiave'], x
    for x in menu['nascosti']:
        yield 'nascosto', None, x


# ---------------------------------------------------------------- 1. url_for
REGOLE = {}
for _r in A.app.url_map.iter_rules():
    REGOLE.setdefault(_r.endpoint, []).append(_r)


def problemi_url_for(cose):
    """Per ogni (nome, voce) dell'elenco: la funzione della pagina esiste, gli argomenti bastano al suo indirizzo,
    url_for lo scrive e l'indirizzo torna alla stessa funzione."""
    problemi = []
    with A.app.test_request_context('/giorno/%s?struttura=2' % D):
        adattatore = A.app.url_map.bind('localhost')
        for nome, x in cose:
            if not x.get('endpoint'):
                continue
            if x['endpoint'] not in REGOLE:
                problemi.append('%s: la funzione %s non c\'è' % (nome, x['endpoint']))
                continue
            dati = M.argomenti_di(x, 2, D)
            if not any(r.arguments <= set(dati) for r in REGOLE[x['endpoint']]):
                problemi.append('%s: a %s mancano %s' % (nome, x['endpoint'],
                                                          sorted(min((r.arguments - set(dati) for r in REGOLE[x['endpoint']]), key=len))))
                continue
            try:
                u = flask.url_for(x['endpoint'], **dati)
            except Exception as e:
                problemi.append('%s: url_for non lo scrive (%r)' % (nome, e))
                continue
            if adattatore.match(urlsplit(u).path)[0] != x['endpoint']:
                problemi.append('%s: %s non torna a %s' % (nome, u, x['endpoint']))
    return problemi


def elenco_di_menu_py():
    cose = [('voce %s' % v['chiave'], v) for v in M.VOCI]
    cose += [('linguetta %s/%s' % (k, x['parola']), x) for k, g in M.LINGUETTE.items() for x in g['voci']]
    cose += [('Aiuto/%s' % x['parola'], x) for x in M.AIUTO] + [('nascosto %s' % x['parola'], x) for x in M.NASCOSTI]
    return cose


def m_url_for():
    cose = elenco_di_menu_py()
    problemi = problemi_url_for(cose)
    assert not problemi, problemi
    con_indirizzo = [n for n, x in cose if x.get('endpoint')]
    assert len(con_indirizzo) >= 30, con_indirizzo
    # le voci della pagina sono proprio quelle di url_for (indirizzo_di), anche nel menu fatto per una pagina
    r, _, menu, _ = apri(PAGINE_SECONDA[0])
    with A.app.test_request_context(PAGINE_SECONDA[0]):
        for tipo, chiave, x in tutte_le_voci(menu):
            atteso = flask.url_for(x['endpoint'], **M.argomenti_di(x, 2, D)) if x['endpoint'] else '#'
            assert x['url'] == atteso, (tipo, chiave, x['url'], atteso)
    # gemello: lo stesso controllo vede una funzione che non c'è, un argomento che manca e uno sconosciuto
    finte = [('finta 1', dict(endpoint='pagina.che_non_esiste', argomenti=())),
             ('finta 2', dict(endpoint='giorno', argomenti=('struttura',))),              # manca il giorno (iso)
             ('finta 3', dict(endpoint='viste.mese', argomenti=('giorno', 'struttura')))]   # iso al posto di aaaamm
    trovati = problemi_url_for(finte)
    assert len(trovati) == 3, trovati
    try:
        M._controlla_argomenti(('struttura', 'settimana'))
        raise AssertionError('un argomento sconosciuto passa')
    except ValueError:
        pass
    return '%d voci, linguette e collegamenti con un indirizzo' % len(con_indirizzo)


def m_registra_voce():
    """L'aggancio dei moduli: una voce nuova, con la sua condizione e le sue linguette, senza toccare i modelli."""
    prima = (list(M.VOCI), copy.deepcopy(M.LINGUETTE))
    acceso = {'si': False}
    try:
        M.registra_voce('aree', 'prova-modulo', 'viste.statistiche', 'Modulo di prova', ('struttura',),
                        icona='users', sezioni={'prova-modulo'}, condizione=lambda: acceso['si'], guida='menu-prova')
        M.registra_linguetta('prova-modulo', 'viste.statistiche', 'Prima', ('struttura',), sezioni={'prova-modulo'},
                             etichetta='Pagine di prova')
        assert [v['chiave'] for v in M.VOCI].index('prova-modulo') == [v['chiave'] for v in M.VOCI].index('statistiche') + 1
        with A.app.test_request_context('/'):
            spento = M.costruisci('prova-modulo', 2, D)
            assert 'prova-modulo' not in [v['chiave'] for v in spento['voci']] and not spento['accese'], spento['accese']
            acceso['si'] = True
            m = M.costruisci('prova-modulo', 2, D)
            v = next(v for v in m['voci'] if v['chiave'] == 'prova-modulo')
            assert m['accesa'] is v and v['url'] == '/statistiche?struttura=2' and m['linguette'][0]['accesa']
            # e la cornice la disegna da sé: la voce nel menu dopo Statistiche, prima di Aiuto, accesa; la sua
            # linguetta in cima al contenuto, accesa
            funzioni = dict(sezione='prova-modulo', sid=2, data_menu=D, oggi_iso=OGGI.isoformat(),
                            ci_sono_sale=lambda: True, n_da_confermare=lambda: 0, marchio_di=A.marchio_di)
            disegno = ''.join(A.app.jinja_env.get_template(n).render(**funzioni) for n in ('_menu.html', '_linguette.html'))
            letto = leggi_cornice(disegno)
            parole = [x['parola'] for x in letto.voci]
            assert parole.index('Statistiche') + 1 == parole.index('Modulo di prova'), parole
            v = letto.voci[parole.index('Modulo di prova')]
            assert v['corrente'] == 'page' and v['guida'] == 'menu-prova' and v['href'] == '/statistiche?struttura=2', v
            assert [(a['parola'], a['href'], a['corrente']) for a in letto.linguette] == [
                ('Prima', '/statistiche?struttura=2', 'page')], letto.linguette
            assert disegno.index('Modulo di prova') < disegno.index('data-guida="menu-aiuto"')
            assert accese_nel_disegno(disegno) == (['Modulo di prova'], ['Prima']), accese_nel_disegno(disegno)
        # e rifiuta quello che romperebbe il menu: una sezione, una chiave, un tasto già presi, un gruppo sconosciuto, un
        # «dopo» di un altro gruppo, una voce senza icona o con un'icona che non c'è (nel menu stretto resterebbe un
        # quadrato vuoto); ognuna per il suo motivo (l'icona c'è in tutte le altre)
        rifiutati = []
        for argomenti, motivo in (
                (dict(gruppo='aree', chiave='doppia', endpoint='viste.statistiche', parola='x', sezioni={'cassa'}), 'sezioni già'),
                (dict(gruppo='aree', chiave='oggi', endpoint='viste.statistiche', parola='x'), 'voce già'),
                (dict(gruppo='aree', chiave='col-tasto', endpoint='viste.statistiche', parola='x', tasto='g'), 'tasto già'),
                (dict(gruppo='altrove', chiave='fuori', endpoint='viste.statistiche', parola='x'), 'gruppo sconosciuto'),
                (dict(gruppo='aree', chiave='dopo', endpoint='viste.statistiche', parola='x', dopo='oggi'), '«dopo»'),
                (dict(gruppo='aree', chiave='senza-icona', endpoint='viste.statistiche', parola='x', icona=None), 'vuole la sua icona'),
                (dict(gruppo='aree', chiave='icona-finta', endpoint='viste.statistiche', parola='x', icona='calendario-finto'),
                 'non c\'è in templates/_icone.html')):
            argomenti.setdefault('icona', 'users')
            try:
                M.registra_voce(**argomenti)
            except ValueError as e:
                if motivo in str(e):
                    rifiutati.append(motivo)
        try:
            M.registra_linguetta('prova-modulo', 'viste.statistiche', 'Altrove', sezioni={'cassa'})
        except ValueError as e:
            if 'si accende solo nelle pagine della sua voce' in str(e):
                rifiutati.append('fuori dalla voce')        # una linguetta accesa dove la sua voce è spenta
        assert len(rifiutati) == 8, rifiutati
        assert M.ICONE and 'users' in M.ICONE, 'le icone di _icone.html non sono state lette (menu.collega)'
    finally:
        M.VOCI[:] = prima[0]
        M.LINGUETTE.clear()
        M.LINGUETTE.update(prima[1])
    assert 'prova-modulo' not in [v['chiave'] for v in M.VOCI]


# ---------------------------------------------------------------- 2. una voce sola
def accese_nel_disegno(testo):
    """(voci del menu accese, linguette accese) nella cornice disegnata: aria-current (page sulle voci e sulle
    linguette, true sul pulsante della tendina Aiuto)."""
    c = leggi_cornice(testo)
    voci = [x['parola'] for x in c.voci if x['corrente'] == 'page'] + [t['parola'] for t in c.tendine if t['corrente'] == 'true']
    voci += ['%s (%s)' % (x['parola'], x['corrente']) for x in c.voci + c.tendine
             if x['corrente'] not in (None, 'page', 'true')]          # un aria-current di un altro tipo non passa
    return voci, [x['parola'] for x in c.linguette if x['corrente'] == 'page']


def accese_nell_elenco(menu):
    """(voci accese, linguette accese) del menu fatto da menu.py per una pagina."""
    voci = [v['chiave'] for v in menu['voci'] if v['accesa']]
    linguette = [(v['chiave'], x['parola']) for v in menu['voci'] for x in v['linguette'] if x['accesa']]
    return voci, linguette


def problemi_una_voce(url, testo, menu):
    """Una voce sola accesa e, se la voce accesa ha le linguette, una linguetta sola (dalla tappa 2 le linguette sono
    vere: ogni pagina di Agenda, Segreteria, Ambulatori e Configura ne accende una), le stesse in menu.py e nel disegno."""
    problemi = []
    voci, linguette = accese_nell_elenco(menu)
    una = 1 if menu['linguette'] else 0             # le linguette della voce accesa: se ci sono, una accesa
    if len(voci) != 1:
        problemi.append('%s: voci accese in menu.py %s' % (url, voci))
    if len(linguette) != una or (linguette and linguette[0][0] not in voci):
        problemi.append('%s: linguette accese in menu.py %s' % (url, linguette))
    voci_d, linguette_d = accese_nel_disegno(testo)
    attese_v = [str(v['parola']) for v in menu['voci'] if v['accesa']]
    attese_l = [str(x['parola']) for v in menu['voci'] for x in v['linguette'] if x['accesa']]
    if voci_d != attese_v or linguette_d != attese_l or len(voci_d) != 1 or len(linguette_d) != una:
        problemi.append('%s: nella cornice disegnata accese le voci %s e le linguette %s, in menu.py %s e %s'
                        % (url, voci_d, linguette_d, attese_v, attese_l))
    return problemi


VISTE = {}                                         # indirizzo -> (testo, menu, principale): le pagine già aperte


def m_una_voce_sola():
    problemi, con_menu, senza = [], 0, []
    for url in senza_parametri():
        r, testo, menu, principale = apri(url)
        if r.status_code != 200 or not CON_MENU.search(testo):
            senza.append(url)
            continue
        assert menu is not None, '%s: il menu c\'è ma non viene da menu.py' % url
        con_menu += 1
        VISTE[url] = (testo, menu, principale)
        problemi += problemi_una_voce(url, testo, menu)
    assert not problemi, problemi
    assert con_menu >= 45, 'solo %d pagine senza parametri con il menu' % con_menu
    # gemello: due voci accese (una sezione data a due voci) e due voci accese nel disegno si vedono; una voce accesa
    # nel disegno ma non in menu.py, una linguetta in più accesa nell'elenco o nel disegno anche
    testo, menu, _ = VISTE['/statistiche']
    guasto = copy.deepcopy(menu)
    next(v for v in guasto['voci'] if v['chiave'] == 'cassa')['accesa'] = True
    doppio = testo.replace('href="/cassa/', 'aria-current="page" href="/cassa/', 1)
    assert doppio != testo and len(problemi_una_voce('gemello', doppio, guasto)) == 2
    assert problemi_una_voce('gemello', doppio, menu), 'una voce accesa solo nel disegno non si vede'
    spenta = testo.replace(' aria-current="page"', '', 1)
    assert spenta != testo and problemi_una_voce('gemello', spenta, menu), 'una voce spenta nel disegno non si vede'
    con_linguette = copy.deepcopy(VISTE['/conferme'][1])
    next(v for v in con_linguette['voci'] if v['chiave'] == 'segreteria')['linguette'][2]['accesa'] = True
    assert problemi_una_voce('gemello', VISTE['/conferme'][0], con_linguette), 'due linguette accese non si vedono'
    due = VISTE['/conferme'][0].replace('href="/da-confermare?', 'aria-current="page" href="/da-confermare?', 1)
    assert problemi_una_voce('gemello', due, VISTE['/conferme'][1]), 'due linguette accese nel disegno non si vedono'
    # e nessuna linguetta accesa in una pagina con le linguette (nell'elenco e nel disegno)
    spente = copy.deepcopy(VISTE['/conferme'][1])
    next(v for v in spente['voci'] if v['chiave'] == 'segreteria')['linguette'][0]['accesa'] = False
    assert problemi_una_voce('gemello', VISTE['/conferme'][0], spente), 'nessuna linguetta accesa nell\'elenco passa'
    nessuna = re.sub(r'(<a class="v-linguetta" href="/conferme[^"]*") aria-current="page"', r'\1', VISTE['/conferme'][0], count=1)
    assert nessuna != VISTE['/conferme'][0] and problemi_una_voce('gemello', nessuna, VISTE['/conferme'][1]), \
        'nessuna linguetta accesa nel disegno passa'
    con_linguette = sum(1 for _, m, _ in VISTE.values() if m['linguette'])
    assert con_linguette >= 25, con_linguette
    return '%d pagine con il menu, ognuna con una voce accesa, %d con le linguette e una accesa (%d senza menu o non 200)' % (
        con_menu, con_linguette, len(senza))


# ---------------------------------------------------------------- 3. struttura e giorno
# le voci e le linguette che non portano la struttura, come nel menu di prima: scritte qui, non prese da menu.py (se
# una voce perde la struttura in menu.py, il disegno lo dice da solo, senza passare dall'oracolo del principale)
SENZA_STRUTTURA = {'Pazienti', 'Configura', 'Anagrafiche', 'Strutture del gruppo', 'Email e WhatsApp',
                   'Importa da Excel', 'Impostazioni', 'Aggiornamenti'}


def senza_struttura_disegnati(testo, sid):
    """I collegamenti disegnati del menu (anche il nascosto del tasto E) e delle linguette che non portano la struttura
    sid, fuori da SENZA_STRUTTURA (la tendina Aiuto non la porta mai). Torna (problemi, quanti guardati)."""
    c = leggi_cornice(testo)
    cose = [x for x in c.voci + c.linguette if x['href'] and x['href'] != '#' and x['parola'] not in SENZA_STRUTTURA]
    return ['«%s» %s' % (x['parola'], x['href']) for x in cose
            if dict(parse_qsl(urlsplit(x['href']).query)).get('struttura') != str(sid)], len(cose)


def problemi_struttura_giorno(menu, sid, giorno):
    problemi = []
    for tipo, chiave, x in tutte_le_voci(menu):
        if not x['endpoint']:
            continue
        u = urlsplit(x['url'])
        q = dict(parse_qsl(u.query))
        nome = '%s %s/%s' % (tipo, chiave, x['parola'])
        if 'struttura' in x['argomenti'] and q.get('struttura') != str(sid):
            problemi.append('%s senza la struttura %s: %s' % (nome, sid, x['url']))
        if ('giorno' in x['argomenti'] or 'giorno_data' in x['argomenti']) and giorno not in x['url']:
            problemi.append('%s senza il giorno %s: %s' % (nome, giorno, x['url']))
        if 'mese' in x['argomenti'] and giorno[:7] not in x['url']:
            problemi.append('%s senza il mese %s: %s' % (nome, giorno[:7], x['url']))
        if OGGI.isoformat() in x['url'] or (giorno[:7] != OGGI.isoformat()[:7] and OGGI.isoformat()[:7] in x['url']):
            problemi.append('%s porta a oggi: %s' % (nome, x['url']))
    return problemi


def problemi_disegnati(testo, menu):
    """I collegamenti della cornice disegnata che non sono voci di menu.py (stesso indirizzo), e le voci di menu.py
    che la cornice di questa pagina non disegna: tutte le voci (con la loro condizione), la tendina Aiuto, i nascosti e
    le linguette della voce accesa."""
    c = leggi_cornice(testo)
    di_menu_py = {x['url'] for _, _, x in tutte_le_voci(menu)}
    problemi = ['«%s» %s non è una voce di menu.py' % (x['parola'], x['href'])
                for x in c.voci + c.aiuto + c.linguette if x['href'] not in di_menu_py]
    attese = [v['url'] for v in menu['voci'] if not v['tendina']] + [x['url'] for x in menu['nascosti']]
    if sorted(x['href'] for x in c.voci) != sorted(attese):
        problemi.append('voci del menu disegnate %s, in menu.py %s' % (sorted(x['href'] for x in c.voci), sorted(attese)))
    if [x['href'] for x in c.linguette] != [x['url'] for x in menu['linguette']]:
        problemi.append('linguette disegnate %s, in menu.py %s' % ([x['href'] for x in c.linguette],
                                                                    [x['url'] for x in menu['linguette']]))
    return problemi


def m_struttura_e_giorno():
    problemi, viste = [], 0
    for url in PAGINE_SECONDA:
        r, testo, menu, principale = apri(url)
        assert r.status_code == 200 and menu is not None, '%s: %s, menu %s' % (url, r.status_code, menu is not None)
        # la prova non passa da sola: la pagina è proprio della seconda struttura e del giorno scelto
        assert menu['sid'] in (2, '2') and menu['data'] == D, (url, menu['sid'], menu['data'])
        VISTE[url] = (testo, menu, principale)
        viste += 1
        problemi += ['%s: %s' % (url, p) for p in problemi_struttura_giorno(menu, 2, D)]
        problemi += problemi_una_voce(url, testo, menu)
        # nella cornice disegnata ogni collegamento (voci, voci nascoste, linguette) è una voce di menu.py, con lo
        # stesso indirizzo (quelle sono controllate qui sopra); ogni collegamento che nel principale porta struttura e
        # giorno è una voce di menu.py (nella cornice nuova le linguette di un'altra area non si disegnano: si arriva
        # dalla loro voce)
        problemi += ['%s: %s' % (url, p) for p in problemi_disegnati(testo, menu)]
        # e nel disegno, senza menu.py: ogni collegamento della cornice porta la struttura, fuori da SENZA_STRUTTURA
        manca, quanti = senza_struttura_disegnati(testo, 2)
        problemi += ['%s: senza la struttura 2: %s' % (url, x) for x in manca]
        if quanti < 10:
            problemi.append('%s: solo %d collegamenti della cornice con la struttura' % (url, quanti))
        di_menu_py = {x['url'] for _, _, x in tutte_le_voci(menu)}
        for x in leggi_menu(principale).collegamenti:
            if ('struttura=2' in x['href'] or D in x['href'] or D[:7] in x['href']) and x['href'] not in di_menu_py:
                problemi.append('%s: %s del principale non è una voce di menu.py' % (url, x['href']))
        # e gli indirizzi che la cornice chiede da sé (la ricerca rapida, le notifiche): uguali, con la struttura
        chiesti = re.findall(r'data-indirizzo="([^"]*)"', principale)
        if not chiesti or [c for c in chiesti if 'struttura=2' not in c or 'data-indirizzo="%s"' % c not in testo]:
            problemi.append('%s: indirizzi della ricerca e delle notifiche %s, nel principale %s'
                            % (url, re.findall(r'data-indirizzo="([^"]*struttura[^"]*)"', testo), chiesti))
    assert not problemi, problemi[:8]
    # quante voci portano la struttura, quante il giorno: il menu di oggi ne ha tante (se diventano zero, la prova
    # passerebbe da sola)
    _, menu, _ = VISTE[PAGINE_SECONDA[0]]
    con_struttura = [x['parola'] for _, _, x in tutte_le_voci(menu) if 'struttura' in x['argomenti']]
    con_giorno = [x['parola'] for _, _, x in tutte_le_voci(menu) if set(x['argomenti']) & {'giorno', 'giorno_data', 'mese'}]
    assert len(con_struttura) >= 25 and len(con_giorno) >= 10, (len(con_struttura), len(con_giorno))
    # gemello: una voce che perde la struttura, una che torna a oggi, una linguetta senza il mese si vedono
    guasto = copy.deepcopy(menu)
    v = next(v for v in guasto['voci'] if v['chiave'] == 'turni')
    v['url'] = v['url'].replace('struttura=2', 'struttura=1')
    x = next(v for v in guasto['voci'] if v['chiave'] == 'cassa')
    x['url'] = x['url'].replace(D, OGGI.isoformat())
    lg = next(v for v in guasto['voci'] if v['chiave'] == 'agenda')['linguette'][2]
    lg['url'] = lg['url'].replace(D[:7], '2000-01')
    trovati = problemi_struttura_giorno(guasto, 2, D)
    assert len(trovati) >= 3, trovati
    # gemello dei collegamenti disegnati: una voce disegnata senza la struttura e una linguetta che manca si vedono
    testo = VISTE[PAGINE_SECONDA[0]][0]
    guasto_t = testo.replace('href="/personale/turni?struttura=2"', 'href="/personale/turni"', 1)
    assert guasto_t != testo and problemi_disegnati(guasto_t, menu), 'una voce disegnata diversa da menu.py passa'
    assert senza_struttura_disegnati(guasto_t, 2)[0] == ['«Turni» /personale/turni'], senza_struttura_disegnati(guasto_t, 2)
    senza_mese = re.sub(r'<a class="v-linguetta" href="/mese/[^"]*"[^>]*>.*?</a>', '', testo, count=1, flags=re.S)
    assert senza_mese != testo and problemi_disegnati(senza_mese, menu), 'una linguetta che manca nel disegno passa'
    return '%d pagine della seconda struttura del %s: %d voci con la struttura, %d con il giorno' % (
        viste, D, len(con_struttura), len(con_giorno))


# ---------------------------------------------------------------- 4. come oggi (oracolo: il ramo principale)
def differenze(principale, menu):
    """Le differenze fra il menu del ramo principale (HTML) e quello di menu.py per la stessa pagina, voce per voce."""
    vecchio = leggi_menu(principale)
    diff = []
    cose = list(tutte_le_voci(menu))
    per_indirizzo = {}
    for tipo, chiave, x in cose:
        chi = x['url'] if x['url'] != '#' else '#' + (x.get('azione_guida') or '')
        per_indirizzo.setdefault(chi, []).append((tipo, chiave, x))
    parole_di_oggi = {}
    for a in vecchio.collegamenti:
        chi = a['href'] if a['href'] != '#' else '#' + (a['azione_guida'] or '')
        parole_di_oggi[chi] = a['parola']
        nuove = per_indirizzo.get(chi, [])
        if not nuove:
            diff.append('manca in menu.py: «%s» %s' % (a['parola'], chi))
            continue
        if a['parola'] not in [str(x['parola']) for _, _, x in nuove]:
            diff.append('«%s» %s: in menu.py %s' % (a['parola'], chi, [str(x['parola']) for _, _, x in nuove]))
        if a['sotto'] is not None and a['sotto'] not in [str(x['sotto']) for _, _, x in nuove]:
            diff.append('«%s»: riga piccola «%s», in menu.py %s' % (a['parola'], a['sotto'], [x['sotto'] for _, _, x in nuove]))
        if a['tasto'] and a['tasto'] not in [x.get('tasto') for _, _, x in nuove]:
            diff.append('«%s»: il tasto %s non è su nessuna voce di menu.py con lo stesso indirizzo' % (a['parola'], a['tasto']))
        if a['guida'] and a['guida'] not in [x.get('guida') for _, _, x in nuove]:
            diff.append('«%s»: data-guida %s non è su nessuna voce di menu.py con lo stesso indirizzo' % (a['parola'], a['guida']))
    for t in vecchio.tendine:
        v = next((v for v in menu['voci'] if str(v['parola']) == t['parola']), None)
        if v is None:
            diff.append('tendina «%s» senza voce in menu.py' % t['parola'])
            continue
        if t['guida'] != v['guida']:
            diff.append('tendina «%s»: data-guida %s, in menu.py %s' % (t['parola'], t['guida'], v['guida']))
        dentro = [(x['url'], str(x['parola'])) for x in v['linguette']
                  if (v['chiave'], str(x['parola'])) not in NON_NEL_MENU_DI_PRIMA] + \
                 [(x['url'], str(x['parola'])) for x in v['tendina']]
        if [(a['href'], a['parola']) for a in t['voci']] != dentro:
            diff.append('tendina «%s»: %s, in menu.py %s' % (t['parola'], [a['parola'] for a in t['voci']], [p for _, p in dentro]))
    tendine = {t['parola']: t for t in vecchio.tendine}
    for tipo, chiave, x in cose:
        chi = x['url'] if x['url'] != '#' else '#' + (x.get('azione_guida') or '')
        if tipo == 'voce' and come_era(x) == 'tendina':
            # oggi è una tendina (Ambulatori, Segreteria, Configura, Aiuto): la parola è quella del suo pulsante e la
            # voce porta a una delle sue pagine (la prima: ricognizione della cornice)
            t = tendine.get(str(x['parola']))
            if t is None:
                diff.append('voce %s: nel menu di oggi non c\'è la tendina «%s»' % (chiave, x['parola']))
            elif x['endpoint'] and x['url'] not in [a['href'] for a in t['voci']]:
                diff.append('voce %s: %s non è fra le pagine della tendina «%s»' % (chiave, x['url'], x['parola']))
            continue
        if chi not in parole_di_oggi:
            if tipo == 'linguetta' and (chiave, str(x['parola'])) in NON_NEL_MENU_DI_PRIMA:
                continue                # una pagina che il principale non ha (Aree e accessi)
            diff.append('%s %s/%s: %s non è nel menu di oggi' % (tipo, chiave, x['parola'], chi))
        elif str(x['parola']) != parole_di_oggi[chi] and (tipo, chiave, str(x['parola'])) not in PAROLE_NUOVE:
            diff.append('%s %s: «%s», oggi «%s» (%s)' % (tipo, chiave, x['parola'], parole_di_oggi[chi], chi))
    # la voce accesa: lo stesso indirizzo acceso, e la stessa tendina accesa
    accesi = [a['href'] for a in vecchio.collegamenti if a['attivo']]
    linguetta = [x for v in menu['voci'] for x in v['linguette'] if x['accesa']]
    voce = menu['accesa']
    nuovo = linguetta[0]['url'] if linguetta else (voce['url'] if voce and voce['url'] != '#' else None)
    if linguetta and linguetta[0]['url'] not in parole_di_oggi and \
            any((v['chiave'], str(linguetta[0]['parola'])) in NON_NEL_MENU_DI_PRIMA for v in menu['voci']
                if linguetta[0] in v['linguette']):
        nuovo = None                    # la pagina di una linguetta nuova (Aree e accessi): il menu di prima non accende niente
    if (accesi[0] if accesi else None) != nuovo:
        diff.append('accesa: oggi %s, in menu.py %s' % (accesi, nuovo))
    tendina = [t['parola'] for t in vecchio.tendine if t['attivo']]
    if tendina and voce is not None and str(voce['parola']) != tendina[0] and \
            ACCESA_ALTROVE.get(menu['sezione']) != (tendina[0], voce['chiave']):
        diff.append('tendina accesa: oggi %s, in menu.py la voce %s' % (tendina, voce['chiave']))
    return diff


def copia_ferma_controllata():
    """La copia ferma è il _menu.html del ramo principale, se git e il ramo ci sono."""
    try:
        vero = subprocess.run(['git', 'show', '%s:%s/templates/_menu.html' % (RAMO_PRINCIPALE, os.path.basename(CARTELLA))], cwd=CARTELLA,
                              capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return 'copia ferma non controllata (git non c\'è)'
    if vero.returncode != 0:
        return 'copia ferma non controllata (il ramo principale non c\'è)'
    with open(PRINCIPALE, 'rb') as f:
        assert f.read() == vero.stdout, ('prove_menu_principale.html non è più il _menu.html del ramo principale: '
                                         'se il principale ha cambiato il menu, va rifatta la copia (e guardato perché)')
    return 'copia ferma uguale al ramo principale'


def m_come_oggi():
    nota = copia_ferma_controllata()
    if not VISTE:
        m_una_voce_sola()
    problemi, voci_viste = [], 0
    for url, (testo, menu, principale) in sorted(VISTE.items()):
        assert principale and '<nav class="menu"' in principale, url
        problemi += ['%s: %s' % (url, d) for d in differenze(principale, menu)]
        voci_viste += len(leggi_menu(principale).collegamenti)
    assert not problemi, problemi[:8]
    # il numero accanto a Segreteria: con un appunto aperto c'è in tutti e due, con lo stesso title
    s = A.Sessione()
    s.add(Appunto(cognome='Fittizi', nome='Teresa', telefono='3331234567'))
    s.commit()
    _, testo, menu, principale = apri('/conferme')
    v = next(v for v in menu['voci'] if v['chiave'] == 'segreteria')
    assert v['contatore'] >= 1 and 'title="%d da confermare"' % v['contatore'] in principale, v['contatore']
    assert not differenze(principale, menu)
    # senza sala operatoria: niente Sala e le esportazioni «degli ambulatori», nel principale e in menu.py
    sale = s.query(Risorsa).filter(Risorsa.tipo == 'SALA_OPERATORIA').all()
    for r in sale:
        r.tipo = 'AMBULATORIO'
    s.commit()
    try:
        _, testo, menu, principale = apri('/giorno/%s?struttura=2' % D)
        assert 'sala' not in [v['chiave'] for v in menu['voci']] and '>Sala</a>' not in principale
        assert 'degli ambulatori' in principale and not differenze(principale, menu), differenze(principale, menu)
    finally:
        for r in sale:
            r.tipo = 'SALA_OPERATORIA'
        s.commit()
        s.close()
    # gemello: una parola cambiata, una riga piccola, un indirizzo senza la struttura, un tasto e una guida persi, una
    # voce accesa diversa: tutti visti
    testo, menu, principale = VISTE['/giorno/%s?struttura=2' % D]
    guasto = copy.deepcopy(menu)
    seg = next(v for v in guasto['voci'] if v['chiave'] == 'segreteria')
    seg['linguette'][1]['parola'] = 'Da richiamare'
    seg['linguette'][3]['sotto'] = 'altro testo'
    seg['tasto'] = seg['linguette'][0]['tasto'] = None
    turni = next(v for v in guasto['voci'] if v['chiave'] == 'turni')
    turni['url'] = turni['url'].replace('?struttura=2', '')
    next(v for v in guasto['voci'] if v['chiave'] == 'dove')['guida'] = None
    guasto['accesa'] = next(v for v in guasto['voci'] if v['chiave'] == 'cassa')
    next(v for v in guasto['voci'] if v['chiave'] == 'agenda')['linguette'][0]['accesa'] = False
    trovate = differenze(principale, guasto)
    for parola in ('Da richiamare', 'altro testo', 'tasto c', 'Turni', 'menu-dove', 'accesa'):
        assert any(parola in d for d in trovate), (parola, trovate)
    nuova = copy.deepcopy(menu)
    next(v for v in nuova['voci'] if v['chiave'] == 'pazienti')['parola'] = 'Archivio'
    assert differenze(principale, nuova), 'una parola nuova non approvata passa'
    return '%d pagine, %d collegamenti del principale confrontati; %s' % (len(VISTE), voci_viste, nota)


def icone_mancanti(voci, icone):
    return ['%s: %s' % (v['chiave'], v['icona']) for v in voci if not v['icona'] or v['icona'] not in icone]


def m_icone():
    """Ogni voce del menu ha la sua icona, e l'icona c'è in templates/_icone.html (scritto da strumenti/genera_icone.py:
    un nome che non c'è disegnerebbe un'icona vuota, e nel menu stretto resterebbe un quadrato vuoto)."""
    with open(os.path.join(CARTELLA, 'templates', '_icone.html'), encoding='utf-8') as f:
        icone = set(re.findall(r"^  '([a-z0-9-]+)':", f.read(), re.M))
    assert not icone_mancanti(M.VOCI, icone), icone_mancanti(M.VOCI, icone)
    altre = {'search', 'arrow-up-right'}                   # la ricerca della barra, la freccina dell'Elenco del giorno
    assert altre <= icone, altre - icone
    # gemello: un'icona sbagliata e una mancante si vedono
    finte = [dict(chiave='a', icona='calendario-che-non-esiste'), dict(chiave='b', icona=None)]
    assert len(icone_mancanti(finte, icone)) == 2
    return '%d voci con un\'icona di _icone.html' % len(M.VOCI)


def problemi_tasti(testo, menu):
    """I tasti G, E, C e D: gestionale.js clicca il primo elemento con quel data-tasto; deve portare alla voce di
    menu.py (G l'Agenda, E l'Elenco del giorno nascosto, C la Segreteria, D Dove si fa)."""
    attesi = {v['tasto']: v['url'] for v in menu['voci'] if v['tasto']}
    attesi.update({x['tasto']: x['url'] for x in menu['nascosti'] if x['tasto']})
    primi = leggi_cornice(testo).primi_tasti
    return ['tasto %s: %s, atteso %s' % (k, primi.get(k), u) for k, u in sorted(attesi.items()) if primi.get(k) != u] + \
        (['tasti %s' % sorted(attesi)] if sorted(attesi) != ['c', 'd', 'e', 'g'] else [])


def m_tasti():
    if not VISTE:
        m_una_voce_sola()
    problemi = []
    for url, (testo, menu, _) in sorted(VISTE.items()):
        problemi += ['%s: %s' % (url, p) for p in problemi_tasti(testo, menu)]
    assert not problemi, problemi[:6]
    # gemello: un collegamento della pagina con data-tasto="g" messo prima del menu prenderebbe il tasto
    testo, menu, _ = VISTE[PAGINE_SECONDA[1]]
    prima = testo.replace('<body', '<a data-tasto="g" href="/altrove"></a><body', 1)
    assert problemi_tasti(prima, menu) and not problemi_tasti(testo, menu)
    return '%d pagine: G, E, C e D portano dove devono' % len(VISTE)


# ---------------------------------------------------------------- 5. il percorso della barra in alto
# le voci che nel percorso non hanno la struttura, come nelle tavole (scritte qui, non prese da menu.py)
SENZA_STRUTTURA_NEL_PERCORSO = {'Pazienti', 'Configura', 'Aiuto'}


def percorso_disegnato(testo):
    """I pezzi del percorso della barra in alto (<p class="v-percorso"><span>…</span>…), None se non c'è."""
    m = re.search(r'<p class="v-percorso">(.*?)</p>', testo, re.S)
    if not m:
        return None
    return [' '.join(unescape(re.sub(r'<[^>]+>', '', x)).split()) for x in re.findall(r'<span>(.*?)</span>', m.group(1), re.S)]


def nome_della_struttura(url):
    """Il nome della struttura di una pagina, dal database: quella dell'indirizzo (?struttura=), se c'è ed è attiva,
    altrimenti la prima attiva (come comune.struttura_scelta)."""
    s = A.Sessione()
    try:
        attive = s.query(Struttura).filter(Struttura.attiva == True).order_by(Struttura.id).all()  # noqa: E712
        sid = dict(parse_qsl(urlsplit(url).query)).get('struttura')
        return next((x.nome for x in attive if str(x.id) == sid), attive[0].nome)
    finally:
        s.close()


def percorso_atteso(url, testo, finale):
    """Il percorso che la pagina deve avere, senza menu.percorso: [struttura della pagina (non per Pazienti, Configura,
    Aiuto), la voce accesa disegnata, la linguetta accesa disegnata se porta proprio a questa pagina]."""
    c = leggi_cornice(testo)
    voci = [x['parola'] for x in c.voci if x['corrente'] == 'page'] + [t['parola'] for t in c.tendine if t['corrente'] == 'true']
    if len(voci) != 1:
        return None
    pezzi = ([] if voci[0] in SENZA_STRUTTURA_NEL_PERCORSO else [nome_della_struttura(url)]) + voci
    return pezzi + [x['parola'] for x in c.linguette if x['corrente'] == 'page' and urlsplit(x['href']).path == finale]


def problemi_percorso(url, testo, finale):
    atteso, disegnato = percorso_atteso(url, testo, finale), percorso_disegnato(testo)
    return [] if atteso and disegnato == atteso else ['%s: percorso %s, atteso %s' % (url, disegnato, atteso)]


def m_percorso():
    if not VISTE:
        m_una_voce_sola()
    problemi, lunghi = [], 0
    for url, (testo, menu, _) in sorted(VISTE.items()):
        problemi += problemi_percorso(url, testo, FINALI[url])
        lunghi += len(percorso_disegnato(testo) or ()) == 3
    assert not problemi, problemi[:6]
    # la prova non passa da sola: ci sono pagine della seconda struttura con tre pezzi, e Pazienti senza la struttura
    seconda = nome_della_struttura('/?struttura=2')
    url = '/chiusura/%s?struttura=2' % D
    testo = VISTE[url][0]
    assert percorso_disegnato(testo) == [seconda, 'Segreteria', 'Chiusura della giornata'], percorso_disegnato(testo)
    assert percorso_disegnato(VISTE['/pazienti'][0]) == ['Pazienti'], percorso_disegnato(VISTE['/pazienti'][0])
    # gemelli: la struttura sbagliata (la prima al posto della seconda: il percorso diceva la struttura della prima
    # pagina, non quella della pagina), la linguetta che manca, la struttura su Pazienti si vedono
    prima = nome_della_struttura('/')
    assert prima != seconda
    sbagliata = testo.replace('<p class="v-percorso"><span>%s</span>' % seconda, '<p class="v-percorso"><span>%s</span>' % prima, 1)
    assert sbagliata != testo and problemi_percorso(url, sbagliata, FINALI[url]), 'la struttura sbagliata nel percorso passa'
    corto = re.sub(r'<span>Chiusura della giornata</span></p>', '</p>', testo, count=1)
    assert corto != testo and problemi_percorso(url, corto, FINALI[url]), 'il percorso senza la linguetta passa'
    p = VISTE['/pazienti'][0]
    con = p.replace('<p class="v-percorso"><span>Pazienti</span>', '<p class="v-percorso"><span>%s</span><span>Pazienti</span>' % prima, 1)
    assert con != p and problemi_percorso('/pazienti', con, FINALI['/pazienti']), 'la struttura su Pazienti passa'
    return '%d pagine, %d con struttura › voce › linguetta' % (len(VISTE), lunghi)


# ---------------------------------------------------------------- 6. il title delle linguette
def problemi_titoli(testo, principale):
    """Ogni linguetta disegnata che nel menu di prima aveva una riga piccola (stesso indirizzo) la porta nel title."""
    righe = {a['href']: ' '.join(a['sotto'].split()) for a in leggi_menu(principale).collegamenti if a['sotto']}
    return ['«%s» %s: title %r, nel menu di prima «%s»' % (x['parola'], x['href'], x['titolo'], righe[x['href']])
            for x in leggi_cornice(testo).linguette
            if x['href'] in righe and ' '.join((x['titolo'] or '').split()) != righe[x['href']]]


def m_titoli():
    if not VISTE:
        m_una_voce_sola()
    problemi, viste = [], 0
    for url, (testo, _, principale) in sorted(VISTE.items()):
        problemi += ['%s: %s' % (url, p) for p in problemi_titoli(testo, principale)]
        viste += len(leggi_cornice(testo).linguette)
    assert not problemi, problemi[:6]
    # gemello: la linguetta Elenco dell'Agenda senza il title (com'era) si vede
    testo, _, principale = VISTE['/giorno/%s?struttura=2' % D]
    senza = re.sub(r'(<a class="v-linguetta" href="/giorno/[^"]*/elenco[^"]*")[^>]*>', r'\1>', testo, count=1)
    assert senza != testo and problemi_titoli(senza, principale), 'una linguetta senza il title passa'
    return '%d linguette guardate' % viste


# ---------------------------------------------------------------- 7. linguette per pagina, condizioni
def m_linguette_e_condizioni():
    """Le linguette che si accendono per pagina (request.endpoint), dentro la stessa sezione, come serviranno alla
    Cassa (tappa 6); le condizioni anche su linguette e collegamenti nascosti (un modulo spento toglie anche loro)."""
    prima = (list(M.VOCI), copy.deepcopy(M.LINGUETTE), list(M.NASCOSTI))
    acceso = {'si': False}
    try:
        M.registra_voce('aree', 'prova-pagine', 'viste.statistiche', 'Pagine di prova', ('struttura',), icona='euro',
                        sezioni={'prova-pagine'})
        M.registra_linguetta('prova-pagine', 'viste.statistiche', 'Una', ('struttura',), sezioni={'prova-pagine'},
                             pagine={'viste.statistiche'}, etichetta='Pagine di prova')
        M.registra_linguetta('prova-pagine', 'viste.conferme', 'Due', ('struttura',), sezioni={'prova-pagine'},
                             pagine={'viste.conferme', 'segreteria.chiusura'})
        M.registra_linguetta('prova-pagine', 'viste.mese', 'Del modulo', ('mese', 'struttura'), sezioni={'prova-pagine'},
                             pagine={'viste.mese'}, condizione=lambda: acceso['si'])
        M.NASCOSTI.append(dict(endpoint='viste.statistiche', argomenti=('struttura',), parola='Nascosto di prova', tasto='x',
                               condizione=lambda: acceso['si']))
        # due linguette che si pestano: senza pagine sulla stessa sezione, o con una pagina in comune
        rifiutate = 0
        for pagine in ((), {'viste.conferme'}):
            try:
                M.registra_linguetta('prova-pagine', 'viste.settimana', 'Tre', sezioni={'prova-pagine'}, pagine=pagine)
            except ValueError as e:
                rifiutate += 'sezioni già' in str(e)
        assert rifiutate == 2, rifiutate
        accese = {}
        for endpoint, indirizzo in (('viste.statistiche', '/statistiche'), ('viste.conferme', '/conferme'),
                                    ('segreteria.chiusura', '/chiusura'), ('viste.mese', '/mese/2026-11')):
            with A.app.test_request_context(indirizzo + '?struttura=2'):
                m = M.costruisci('prova-pagine', 2, D, endpoint=endpoint)
                accese[endpoint] = [str(x['parola']) for x in m['linguette'] if x['accesa']]
                # e la cornice disegna la stessa linguetta accesa (l'endpoint arriva da request.endpoint)
                funzioni = dict(sezione='prova-pagine', sid=2, data_menu=D, oggi_iso=OGGI.isoformat(),
                                ci_sono_sale=lambda: True, n_da_confermare=lambda: 0, marchio_di=A.marchio_di)
                if flask.request.endpoint == endpoint:
                    disegno = A.app.jinja_env.get_template('_linguette.html').render(**funzioni)
                    assert accese_nel_disegno(disegno)[1] == accese[endpoint], (endpoint, accese_nel_disegno(disegno))
                pezzi = M.percorso(m, endpoint, 'Struttura')
                assert pezzi == ['Struttura', 'Pagine di prova'] + accese[endpoint], (endpoint, pezzi)
        assert accese == {'viste.statistiche': ['Una'], 'viste.conferme': ['Due'], 'segreteria.chiusura': ['Due'],
                          'viste.mese': []}, accese
        # le condizioni: spenta, la linguetta del modulo e il collegamento nascosto (con il suo tasto) non ci sono, né
        # nell'elenco né nel disegno; accesa, ci sono, e la linguetta si accende nella sua pagina
        funzioni = dict(sezione='prova-pagine', sid=2, data_menu=D, oggi_iso=OGGI.isoformat(),
                        ci_sono_sale=lambda: True, n_da_confermare=lambda: 0, marchio_di=A.marchio_di)
        with A.app.test_request_context('/mese/%s?struttura=2' % D[:7]):
            for si in (False, True):
                acceso['si'] = si
                flask.g.pop('menu_fatti', None)
                m = M.costruisci('prova-pagine', 2, D, endpoint='viste.mese')
                v = next(v for v in m['voci'] if v['chiave'] == 'prova-pagine')
                disegno = ''.join(A.app.jinja_env.get_template(n).render(**funzioni) for n in ('_menu.html', '_linguette.html'))
                c = leggi_cornice(disegno)
                ci_sono = ('Del modulo' in [str(x['parola']) for x in v['linguette']],
                           'Nascosto di prova' in [str(x['parola']) for x in m['nascosti']],
                           'Del modulo' in [x['parola'] for x in c.linguette], c.primi_tasti.get('x') is not None)
                assert ci_sono == (si,) * 4, (si, ci_sono)
                assert accese_nel_disegno(disegno)[1] == (['Del modulo'] if si else []), accese_nel_disegno(disegno)
    finally:
        M.VOCI[:] = prima[0]
        M.LINGUETTE.clear()
        M.LINGUETTE.update(prima[1])
        M.NASCOSTI[:] = prima[2]
    assert 'prova-pagine' not in [v['chiave'] for v in M.VOCI] and 'prova-pagine' not in M.LINGUETTE
    assert not [x for x in M.NASCOSTI if x['parola'] == 'Nascosto di prova']


# ---------------------------------------------------------------- 7-bis. la condizione per pagina e le sezioni dei moduli
def m_condizione_per_pagina():
    """La condizione per pagina (dalla 1.13, data da app.py: accessi.si_apre) toglie voci, linguette, voci della tendina e
    collegamenti nascosti la cui pagina non si apre; una voce la cui pagina non si apre porta alla prima delle sue
    linguette che si apre, senza il suo tasto, o non c'è. registra_sezioni dà a una voce una sezione per la linguetta di
    un modulo (Aree e accessi in Configura) e rifiuta una sezione di un'altra voce. Gemello: senza condizione tutto."""
    import accessi
    assert M.SI_APRE is accessi.si_apre, 'app.py non ha dato al menu la condizione per pagina'
    prima_si_apre = M.SI_APRE
    cassa = next(v for v in M.VOCI if v['chiave'] == 'cassa')
    sezioni_di_prima = cassa['sezioni']
    funzioni = dict(sezione='anagrafiche', sid=2, data_menu=D, oggi_iso=OGGI.isoformat(), ci_sono_sale=lambda: True,
                    n_da_confermare=lambda: 0, marchio_di=A.marchio_di)
    chiusi = {'anagrafiche.elenco', 'viste.elenco_giorno', 'guida.indice', 'pazienti.elenco'}
    try:
        # le sezioni di un modulo: la voce Cassa si accende anche sulla sezione nuova; una sezione di un'altra voce no
        M.registra_sezioni('cassa', {'prova-sezione'})
        with A.app.test_request_context('/'):
            assert M.costruisci('prova-sezione', 2, D)['accesa']['chiave'] == 'cassa'
        rifiuti = []
        for voce, sezioni in (('cassa', {'giorno'}), ('nessuna', {'altra'})):
            try:
                M.registra_sezioni(voce, sezioni)
            except ValueError as e:
                rifiuti.append(str(e).split(':')[0])
        assert rifiuti == ['sezioni già di un\'altra voce', 'voce sconosciuta'], rifiuti
        assert 'accessi' in next(v for v in M.VOCI if v['chiave'] == 'configura')['sezioni'], 'la sezione di Aree e accessi'
        for si_apre, atteso in ((None, 'tutto'), (lambda e: e not in chiusi, 'alcune'), (lambda e: False, 'nessuna')):
            M.SI_APRE = si_apre
            with A.app.test_request_context('/anagrafiche'):
                m = M.costruisci('anagrafiche', 2, D, funzioni, 'anagrafiche.elenco')
                disegno = ''.join(A.app.jinja_env.get_template(n).render(**funzioni) for n in ('_menu.html', '_linguette.html'))
            voci = {v['chiave']: v for v in m['voci']}
            cose = list(tutte_le_voci(m))
            c = leggi_cornice(disegno)
            if atteso == 'tutto':
                assert voci['configura']['url'] == '/anagrafiche' and 'pazienti' in voci and m['nascosti'] and \
                    c.primi_tasti.get('e'), 'gemello: senza condizione tutte le voci'
                tutte = len(cose)
            elif atteso == 'alcune':
                assert voci['configura']['url'] == '/dove-si-fa/strutture' and voci['configura']['tasto'] is None
                assert 'pazienti' not in voci and not m['nascosti'] and c.primi_tasti.get('e') is None
                assert [str(x['parola']) for x in voci['aiuto']['tendina']] == [
                    'Guida di questa pagina', 'Novità', 'Tasti rapidi'], voci['aiuto']['tendina']
                assert not [x for _, _, x in cose if x.get('endpoint') in chiusi], 'una cosa chiusa è rimasta'
                assert '/dove-si-fa/strutture' in [x['href'] for x in c.voci if x['parola'] == 'Configura'], \
                    'il disegno: Configura porta alle Strutture del gruppo'
                assert len(cose) < tutte
            else:
                assert list(voci) == ['aiuto'] and not m['nascosti'] and not m['linguette'], list(voci)
                assert [str(x['parola']) for x in voci['aiuto']['tendina']] == ['Guida di questa pagina', 'Tasti rapidi']
    finally:
        M.SI_APRE = prima_si_apre
        cassa['sezioni'] = sezioni_di_prima
    return 'senza condizione %d cose nel menu; con la condizione voci, linguette, Aiuto e tasto E tolti, Configura alle ' \
           'Strutture del gruppo senza tasto; sezioni dei moduli' % tutte

# ---------------------------------------------------------------- 8. il lanciatore vede la cornice di ogni pagina
def cornici_del_lanciatore(testo, principale):
    """(cornice del principale, cornice di qui) di una pagina come le legge strumenti/confronta_rami.py: qui la pagina
    disegnata, nel principale il suo menu (prove_menu_principale.html) disegnato sulla stessa pagina."""
    html_ = {'Content-Type': 'text/html; charset=utf-8'}
    prima = CR.riassunto(200, html_, ('<!doctype html><html><body>%s</body></html>' % principale).encode('utf-8'), True)[2]
    qui = CR.riassunto(200, html_, testo.encode('utf-8'), True)[2]
    return prima, qui


def problemi_del_lanciatore(pagine):
    """Le differenze che confronta_cornice trova pagina per pagina (gli indirizzi per forma, le voci accese con le
    regole approvate, la voce accesa sola), su [(indirizzo, testo, principale)]."""
    regole = CR.leggi_approvati(os.path.join(CARTELLA, 'strumenti', 'cambiamenti_approvati.txt'))
    vuoto = {k: set() for k in CR.CATALOGO}
    righe, n, _, _ = CR.confronta_cornice({'principale': vuoto, 'qui': vuoto},
                                          [(u,) + cornici_del_lanciatore(t, p) for u, t, p in pagine], regole)
    assert len(righe) == (n + 1 if n else 0), righe
    return righe[1:]


def m_lanciatore():
    if not VISTE:
        m_una_voce_sola()
    pagine = [(u, VISTE[u][0], VISTE[u][2]) for u in PAGINE_SECONDA + ['/conferme', '/pazienti', '/anagrafiche', '/statistiche']]
    problemi = problemi_del_lanciatore(pagine)
    assert not problemi, problemi[:4]
    # il gemello M1 della revisione: le linguette che venivano dalle tendine (qui quelle della Segreteria) portano alla
    # struttura 1 da una pagina della seconda. Per voce (parola → forma) non si vedeva: nel principale la parola ha la
    # riga piccola («Lista d'attesa chi vuole un posto prima»), qui no
    url = '/chiusura/%s?struttura=2' % D
    testo, _, principale = VISTE[url]
    i = testo.index('data-cornice="linguette"')
    guasto = testo[:i] + testo[i:].replace('?struttura=2', '?struttura=1', 3)
    trovati = problemi_del_lanciatore([(url, guasto, principale)])
    assert any('/attesa?struttura' in x or '/conferme?struttura' in x or '/da-confermare?struttura' in x for x in trovati), trovati
    # l'Agenda (era Giorno) che torna a oggi, vista da una pagina della Segreteria dove l'Agenda non ha linguette
    oggi = testo.replace('href="/giorno/%s?struttura=2" class="v-voce"' % D, 'href="/giorno/%s?struttura=2" class="v-voce"' % OGGI, 1)
    assert oggi != testo and any('/giorno/N-N-N?struttura' in x for x in problemi_del_lanciatore([(url, oggi, principale)]))
    # il gemello M3: una seconda voce accesa (Agenda anche su Pazienti) passerebbe con la regola «aggiunto accese@cornice
    # menu «Agenda»»: il controllo fisso la vede
    t, _, pr = VISTE['/pazienti']
    due = re.sub(r'(<a data-tasto="g" href="[^"]*" class="v-voce" title="Agenda")', r'\1 aria-current="page"', t, count=1)
    assert due != t and any('voci accese qui: 2' in x for x in problemi_del_lanciatore([('/pazienti', due, pr)]))
    return '%d pagine: indirizzi della cornice per forma e una voce accesa sola, come li vede il lanciatore' % len(pagine)


prova('ogni voce, linguetta e collegamento si costruisce con url_for', m_url_for)
prova('ogni voce del menu ha un\'icona che c\'è in _icone.html', m_icone)
prova('registra_voce: una voce di un modulo, con condizione e linguette; i doppioni rifiutati', m_registra_voce)
prova('ogni pagina senza parametri accende una voce sola e, se ha le linguette, una linguetta sola', m_una_voce_sola)
prova('dalla seconda struttura, in un giorno che non è oggi, tutto porta struttura e giorno', m_struttura_e_giorno)
prova('i tasti G, E, C e D portano alla pagina giusta', m_tasti)
prova('parole, indirizzi, tasti e guide come nel menu del ramo principale, voce per voce', m_come_oggi)
prova('il percorso della barra in alto: struttura della pagina, voce e linguetta', m_percorso)
prova('le linguette portano nel title la riga piccola del menu di prima', m_titoli)
prova('linguette accese per pagina; condizioni anche su linguette e collegamenti nascosti', m_linguette_e_condizioni)
prova('la condizione per pagina (dalla rete) e le sezioni dei moduli', m_condizione_per_pagina)
prova('il lanciatore vede gli indirizzi della cornice per forma e una seconda voce accesa', m_lanciatore)

shutil.rmtree(PROVVISORIA, ignore_errors=True)
for stato, nome, nota in esiti:
    print('%-6s %s%s' % (stato, nome, ('\n       ' + nota) if nota and stato != 'OK' else ('  (%s)' % nota if nota else '')))
rotte = [e for e in esiti if e[0] != 'OK']
print('\n%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(rotte), len(rotte)))
sys.exit(1 if rotte else 0)
