# -*- coding: utf-8 -*-
"""Il menu fatto da menu.py (tappa 2 della base, 22/11/2026).

Dalla tappa 2 voci, linguette, tendina Aiuto e collegamenti nascosti stanno in un elenco in menu.py, e
templates/_menu.html li disegna. Qui:
- ogni voce, linguetta, voce della tendina Aiuto e collegamento nascosto si costruisce con url_for: la funzione
  della pagina esiste e gli argomenti che porta bastano al suo indirizzo (e i moduli possono aggiungere voci con
  registra_voce, che rifiuta una sezione, una chiave o un tasto già presi);
- ogni pagina senza parametri (indirizzi.txt) accende una voce sola e al più una linguetta, nell'elenco di menu.py e
  nel menu disegnato (la classe attivo e aria-current insieme);
- da una pagina della seconda struttura, in un giorno che non è oggi, ogni voce e ogni linguetta porta ancora
  struttura e giorno (un difetto così c'è stato: «Nuovo appuntamento» dalla seconda struttura proponeva la prima,
  LEGGIMI.md, storico dei difetti);
- le parole, gli indirizzi, i tasti e i data-guida delle voci sono quelli di oggi: l'oracolo è il menu del ramo
  principale, prove_menu_principale.html, una copia ferma del suo templates/_menu.html (byte per byte; se git e il
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
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlsplit

from prove_dove import dove

CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = tempfile.mkdtemp(prefix='prove-menu-')

import flask  # noqa: E402
import seed  # noqa: E402
import app as A  # noqa: E402
import menu as M  # noqa: E402
from modelli import Appunto, Risorsa  # noqa: E402

A.app.config['TESTING'] = True
A.Sessione = seed.popola('sqlite:///' + os.path.join(PROVVISORIA, 'prove.db'))
C = A.app.test_client()
esiti = []

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
    """Il menu (nav.menu) di una pagina: i collegamenti con parola, riga piccola, tasto, guida, accesa (classe attivo e
    aria-current) e la tendina in cui stanno; le tendine con parola, guida e accesa."""

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


# ---------------------------------------------------------------- le pagine
CONTESTO = {}


@flask.template_rendered.connect_via(A.app)
def _contesto(sender, template, context, **extra):
    CONTESTO['ultimo'] = context            # l'ultimo modello disegnato: quello della pagina intera


def apri(url):
    """(risposta, testo, menu di menu.py, menu del ramo principale disegnato sulla stessa pagina) di una pagina."""
    CONTESTO.clear()
    with C:
        r = C.get(url, follow_redirects=True)
        testo = r.get_data(as_text=True) if 'text/html' in (r.content_type or '') else ''
        menu = getattr(flask.g, 'menu_della_pagina', None)
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
            # e il modello la disegna da sé (come oggi: una tendina dopo Statistiche, prima della ricerca), accesa
            funzioni = dict(sezione='prova-modulo', sid=2, data_menu=D, oggi_iso=OGGI.isoformat(),
                            ci_sono_sale=lambda: True, n_da_confermare=lambda: 0)
            disegno = A.app.jinja_env.get_template('_menu.html').render(**funzioni)
            letto = leggi_menu(disegno)
            t = next(t for t in letto.tendine if t['parola'] == 'Modulo di prova')
            assert t['attivo'] and t['corrente'] == 'true' and t['guida'] == 'menu-prova', t
            assert [(a['parola'], a['href'], a['attivo']) for a in t['voci']] == [('Prima', '/statistiche?struttura=2', True)], t
            assert disegno.index('>Statistiche</a>') < disegno.index('Modulo di prova') < disegno.index('class="spinta"')
            assert accese_nel_disegno(disegno)[0] == ['Modulo di prova'], accese_nel_disegno(disegno)
        # e rifiuta quello che romperebbe il menu: una sezione, una chiave, un tasto già presi, un gruppo sconosciuto
        rifiutati = 0
        for argomenti in (dict(gruppo='aree', chiave='doppia', endpoint='viste.statistiche', parola='x', sezioni={'cassa'}),
                          dict(gruppo='aree', chiave='oggi', endpoint='viste.statistiche', parola='x'),
                          dict(gruppo='aree', chiave='col-tasto', endpoint='viste.statistiche', parola='x', tasto='g'),
                          dict(gruppo='altrove', chiave='fuori', endpoint='viste.statistiche', parola='x'),
                          dict(gruppo='aree', chiave='dopo', endpoint='viste.statistiche', parola='x', dopo='oggi')):
            try:
                M.registra_voce(**argomenti)
            except ValueError:
                rifiutati += 1
        try:
            M.registra_linguetta('prova-modulo', 'viste.statistiche', 'Altrove', sezioni={'cassa'})
        except ValueError:
            rifiutati += 1                  # una linguetta accesa dove la sua voce è spenta
        assert rifiutati == 6, rifiutati
    finally:
        M.VOCI[:] = prima[0]
        M.LINGUETTE.clear()
        M.LINGUETTE.update(prima[1])
    assert 'prova-modulo' not in [v['chiave'] for v in M.VOCI]


# ---------------------------------------------------------------- 2. una voce sola
def accese_nel_disegno(testo):
    """(voci accese in cima al menu, collegamenti accesi nelle tendine, disaccordi fra classe e aria-current)."""
    m = leggi_menu(testo)
    in_cima = [x['parola'] for x in m.collegamenti if x['tendina'] is None and x['attivo']]
    in_cima += [t['parola'] for t in m.tendine if t['attivo']]
    dentro = [x['parola'] for x in m.collegamenti if x['tendina'] is not None and x['attivo']]
    disaccordi = [x['parola'] for x in m.collegamenti if x['attivo'] != (x['corrente'] == 'page')]
    disaccordi += [t['parola'] for t in m.tendine if t['attivo'] != (t['corrente'] == 'true')]
    return in_cima, dentro, disaccordi


def accese_nell_elenco(menu):
    """(voci accese, linguette accese) del menu fatto da menu.py per una pagina."""
    voci = [v['chiave'] for v in menu['voci'] if v['accesa']]
    linguette = [(v['chiave'], x['parola']) for v in menu['voci'] for x in v['linguette'] if x['accesa']]
    return voci, linguette


def problemi_una_voce(url, testo, menu):
    problemi = []
    voci, linguette = accese_nell_elenco(menu)
    if len(voci) != 1:
        problemi.append('%s: voci accese in menu.py %s' % (url, voci))
    if len(linguette) > 1 or (linguette and linguette[0][0] not in voci):
        problemi.append('%s: linguette accese in menu.py %s' % (url, linguette))
    in_cima, dentro, disaccordi = accese_nel_disegno(testo)
    if len(in_cima) != 1 or len(dentro) > 1 or disaccordi:
        problemi.append('%s: nel menu disegnato accese %s, nelle tendine %s, classe e aria-current diverse %s'
                        % (url, in_cima, dentro, disaccordi))
    return problemi


VISTE = {}                                         # indirizzo -> (testo, menu, principale): le pagine già aperte


def m_una_voce_sola():
    problemi, con_menu, senza = [], 0, []
    for url in senza_parametri():
        r, testo, menu, principale = apri(url)
        if r.status_code != 200 or '<nav class="menu"' not in testo:
            senza.append(url)
            continue
        assert menu is not None, '%s: il menu c\'è ma non viene da menu.py' % url
        con_menu += 1
        VISTE[url] = (testo, menu, principale)
        problemi += problemi_una_voce(url, testo, menu)
    assert not problemi, problemi
    assert con_menu >= 45, 'solo %d pagine senza parametri con il menu' % con_menu
    # gemello: due voci accese (una sezione data a due voci) e due collegamenti accesi nel disegno si vedono
    testo, menu, _ = VISTE['/statistiche']
    guasto = copy.deepcopy(menu)
    next(v for v in guasto['voci'] if v['chiave'] == 'cassa')['accesa'] = True
    doppio = testo.replace('<a href="/cassa/', '<a class="attivo" aria-current="page" href="/cassa/', 1)
    assert doppio != testo and len(problemi_una_voce('gemello', doppio, guasto)) == 2
    solo_classe = testo.replace('<a href="/cassa/', '<a class="attivo" href="/cassa/', 1)
    assert problemi_una_voce('gemello', solo_classe, menu), 'una voce accesa senza aria-current non si vede'
    con_linguette = copy.deepcopy(VISTE['/conferme'][1])
    next(v for v in con_linguette['voci'] if v['chiave'] == 'segreteria')['linguette'][2]['accesa'] = True
    assert problemi_una_voce('gemello', VISTE['/conferme'][0], con_linguette), 'due linguette accese non si vedono'
    return '%d pagine con il menu, ognuna con una voce accesa (%d senza menu o non 200)' % (con_menu, len(senza))


# ---------------------------------------------------------------- 3. struttura e giorno
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
        # nel menu disegnato: ogni collegamento che nel principale porta struttura e giorno li porta anche qui
        oggi = {x['href'] for x in leggi_menu(testo).collegamenti}
        for x in leggi_menu(principale).collegamenti:
            if ('struttura=2' in x['href'] or D in x['href'] or D[:7] in x['href']) and x['href'] not in oggi:
                problemi.append('%s: %s del principale non c\'è nel menu disegnato' % (url, x['href']))
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
        dentro = [(x['url'], str(x['parola'])) for x in v['linguette'] if x['oggi']] + \
                 [(x['url'], str(x['parola'])) for x in v['tendina']]
        if [(a['href'], a['parola']) for a in t['voci']] != dentro:
            diff.append('tendina «%s»: %s, in menu.py %s' % (t['parola'], [a['parola'] for a in t['voci']], [p for _, p in dentro]))
    tendine = {t['parola']: t for t in vecchio.tendine}
    for tipo, chiave, x in cose:
        chi = x['url'] if x['url'] != '#' else '#' + (x.get('azione_guida') or '')
        if tipo == 'voce' and x['oggi'] == 'tendina':
            # oggi è una tendina (Ambulatori, Segreteria, Configura, Aiuto): la parola è quella del suo pulsante e la
            # voce porta a una delle sue pagine (la prima: ricognizione della cornice)
            t = tendine.get(str(x['parola']))
            if t is None:
                diff.append('voce %s: nel menu di oggi non c\'è la tendina «%s»' % (chiave, x['parola']))
            elif x['endpoint'] and x['url'] not in [a['href'] for a in t['voci']]:
                diff.append('voce %s: %s non è fra le pagine della tendina «%s»' % (chiave, x['url'], x['parola']))
            continue
        if chi not in parole_di_oggi:
            diff.append('%s %s/%s: %s non è nel menu di oggi' % (tipo, chiave, x['parola'], chi))
        elif str(x['parola']) != parole_di_oggi[chi] and (tipo, chiave, str(x['parola'])) not in PAROLE_NUOVE:
            diff.append('%s %s: «%s», oggi «%s» (%s)' % (tipo, chiave, x['parola'], parole_di_oggi[chi], chi))
    # la voce accesa: lo stesso indirizzo acceso, e la stessa tendina accesa
    accesi = [a['href'] for a in vecchio.collegamenti if a['attivo']]
    linguetta = [x for v in menu['voci'] for x in v['linguette'] if x['accesa']]
    voce = menu['accesa']
    nuovo = linguetta[0]['url'] if linguetta else (voce['url'] if voce and voce['url'] != '#' else None)
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


prova('ogni voce, linguetta e collegamento si costruisce con url_for', m_url_for)
prova('registra_voce: una voce di un modulo, con condizione e linguette; i doppioni rifiutati', m_registra_voce)
prova('ogni pagina senza parametri accende una voce sola e al più una linguetta', m_una_voce_sola)
prova('dalla seconda struttura, in un giorno che non è oggi, tutto porta struttura e giorno', m_struttura_e_giorno)
prova('parole, indirizzi, tasti e guide come nel menu del ramo principale, voce per voce', m_come_oggi)

shutil.rmtree(PROVVISORIA, ignore_errors=True)
for stato, nome, nota in esiti:
    print('%-6s %s%s' % (stato, nome, ('\n       ' + nota) if nota and stato != 'OK' else ('  (%s)' % nota if nota else '')))
rotte = [e for e in esiti if e[0] != 'OK']
print('\n%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(rotte), len(rotte)))
sys.exit(1 if rotte else 0)
