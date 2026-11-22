# -*- coding: utf-8 -*-
"""Prove dell'accesso dagli altri PC della rete (accessi.py, dalla 1.13).

Le richieste «dalla rete» si fanno con il test_client di Flask cambiando l'ambiente: REMOTE_ADDR di un altro PC,
la presa della rete (environ['gestionale.presa_rete'], come la mette accessi.MarcaRete), X-Forwarded-For, Forwarded
o X-Real-Ip (un portiere sullo stesso PC). Le decisioni della guardia su TUTTE le pagine si leggono senza far girare
la pagina (app.preprocess_request in una richiesta finta, con il cookie vero dell'utente): così anche i moduli che
cancellano o mandano messaggi si provano senza effetti. In fondo le prese vere: il server principale con le
intestazioni del portiere, l'ascolto della rete acceso, spento, riacceso, rifiutato con una chiave fissa.

Ogni prova ha il suo gemello (la stessa cosa che deve riuscire, o il PC principale dove tutto resta come prima).

    python prove_accessi.py
"""
import http.client
import io
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import types
import urllib.parse
from datetime import date, datetime, timedelta
from html.parser import HTMLParser

from prove_dove import dove

PROVVISORIA = tempfile.mkdtemp(prefix='prove-accessi-')

import seed  # noqa: E402
import app as A  # noqa: E402
import prove_messaggi as PM  # noqa: E402
import accessi  # noqa: E402
import invii  # noqa: E402
import menu as MENU  # noqa: E402
import prove_cornice as PC_  # noqa: E402
from modelli import (Appuntamento, Appunto, Attesa, Attivita, Invio, NotaGiorno, Operatore, Paziente, Prestazione,  # noqa: E402
                     Risorsa, StrutturaGruppo, leggi_impostazione, scrivi_impostazione)
from sqlalchemy import event, func, select  # noqa: E402

A.app.config['TESTING'] = True
PM.segui(A.app)
A.Sessione = seed.popola('sqlite:///' + os.path.join(PROVVISORIA, 'prove.db'))
accessi.prepara_registro(PROVVISORIA)
accessi.sessioni.carica(PROVVISORIA)
esiti = []
OGGI = date.today().isoformat()
MESE = OGGI[:7]
RETE = 'http://192.168.1.10:5080'        # il PC della segreteria visto dagli altri (scritto in rete_nomi)
PC = 'http://127.0.0.1:5000'             # solo un indirizzo: nessuna presa vera su questa porta


def prova(nome, f):
    try:
        esiti.append(('OK', nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', nome, '%s · %s' % (dove(e), str(e) or 'asserzione fallita')))
    except Exception as e:
        esiti.append(('ERRORE', nome, '%s · %r' % (dove(e), e)))


# ============================================================== aiuti
PASSWORD = {'Anna Esempietti': 'mela verde sul tavolo', 'Tutto Provolo': 'nave lenta nel porto',
            'Guarda Fittizi': 'ombrello giallo di carta', 'Spento Testabianca': 'lampada blu in cucina'}
TUTTE = {a: 'modifica' for a in accessi.CODICI_AREE}
TUTTE_GUARDA = {a: 'guarda' for a in accessi.CODICI_AREE}


def utente(nome, password, aree, attivo=True, cambia=False):
    u = accessi.nuovo_utente(nome, password)
    u.update(aree=dict(aree), attivo=attivo, cambia=cambia)
    return u


def imposta(**valori):
    s = A.Sessione()
    for k, v in valori.items():
        scrivi_impostazione(s, k, v)
    s.commit()
    s.close()


def leggi(chiave):
    s = A.Sessione()
    try:
        return leggi_impostazione(s, chiave, '')
    finally:
        s.close()


def utenti_salvati():
    return json.loads(leggi('rete_utenti') or '[]')


def aggiungi_utenti(*nuovi):
    imposta(rete_utenti=json.dumps(utenti_salvati() + list(nuovi)))


def configura_di_partenza():
    imposta(rete_accesa='1', rete_porta='5080', rete_schermo_libero='', rete_nomi='192.168.1.10 pc-segreteria',
            rete_utenti=json.dumps([
                utente('Anna Esempietti', PASSWORD['Anna Esempietti'],
                       {'agenda': 'modifica', 'pazienti': 'guarda', 'guida': 'guarda'}),
                # tutto, e il Sistema scritto a mano nel JSON: non deve valere
                utente('Tutto Provolo', PASSWORD['Tutto Provolo'], dict(TUTTE, sistema='modifica')),
                utente('Guarda Fittizi', PASSWORD['Guarda Fittizi'], TUTTE_GUARDA),
                utente('Spento Testabianca', PASSWORD['Spento Testabianca'], TUTTE, attivo=False)]))
    accessi.tentativi.svuota()
    accessi.sessioni.svuota()


def locale():
    c = A.app.test_client()
    c.base = PC
    return c


def rete(come='indirizzo', ip='192.168.1.50'):
    """Un client «dalla rete», nei modi in cui una richiesta può arrivare da un altro PC."""
    ambiente, base = {'REMOTE_ADDR': ip}, RETE
    if come == 'presa':                        # dalla presa della rete, anche da questo PC
        ambiente = {'REMOTE_ADDR': '127.0.0.1', 'gestionale.presa_rete': True}
    elif come == 'inoltrata':                  # un portiere sullo stesso PC (Caddy): REMOTE_ADDR e' 127.0.0.1
        ambiente, base = {'REMOTE_ADDR': '127.0.0.1', 'HTTP_X_FORWARDED_FOR': ip}, PC
    elif come == 'forwarded':
        ambiente, base = {'REMOTE_ADDR': '127.0.0.1', 'HTTP_FORWARDED': 'for=%s;proto=http' % ip}, PC
    elif come == 'real-ip':
        ambiente, base = {'REMOTE_ADDR': '127.0.0.1', 'HTTP_X_REAL_IP': ip}, PC
    c = A.app.test_client()
    c.environ_base.update(ambiente)
    c.base = base
    return c


def chiedi(c, metodo, percorso, **kw):
    kw.setdefault('base_url', getattr(c, 'base', PC))
    if metodo == 'POST':
        kw.setdefault('headers', {}).setdefault('Origin', kw['base_url'])
    return c.open(percorso, method=metodo, **kw)


def entra(c, nome, password=None, dopo=''):
    return chiedi(c, 'POST', '/accesso', data={'nome': nome, 'password': PASSWORD.get(nome, '') if password is None
                                               else password, 'dopo': dopo})


def conta(modello):
    s = A.Sessione()
    try:
        return s.scalar(select(func.count()).select_from(modello))
    finally:
        s.close()


def primo(modello, *dove_):
    s = A.Sessione()
    try:
        return s.scalars(select(modello.id).where(*dove_).order_by(modello.id)).first()
    finally:
        s.close()


def testo(r):
    return r.get_data(as_text=True)


def entrato_come(t, nome):
    """La riga di chi è entrato da un altro PC, con il suo nome (_utente_rete.html: «Entrato da un altro PC come» per i
    lettori di schermo, il nome in grassetto)."""
    return bool(re.search(r'<span class="v-utente-come">Entrato da un altro PC come </span><b>%s</b>' % re.escape(nome), t))


def rifiutata(r):
    """La pagina italiana del rifiuto (o il JSON con l'errore)."""
    if r.status_code != 403:
        return False
    if r.mimetype == 'application/json':
        return 'errore' in (r.json or {})
    t = testo(r)
    return '<html lang="it">' in t and ('non è fra le parti disponibili' in t or 'Solo guardare' in t
                                        or 'Solo dal PC della segreteria' in t or 'spento' in t)


# ================================================ valori per gli indirizzi
VALORI = {'iso': OGGI, 'aaaamm': MESE, 'mese': MESE, 'token': '0' * 32, 'slug': 'prenotare', 'codice': 'serie-finta',
          'nome': 'agende-20260101-000000.db', 'azione': 'fatto', 'periodo': 'giorno', 'parte': 'ambulatori',
          'filename': 'stile.css'}


def indirizzo(regola, valori=None):
    """L'indirizzo della regola con i valori: i numeri 1 se non dati."""
    v = dict(VALORI, **(valori or {}))
    return re.sub(r'<(?:[a-z]+:)?([a-z_]+)>', lambda m: str(v.get(m.group(1), 1)), regola.rule)


def cookie_di(nome, da='192.168.1.77'):
    """Un cookie vero della rete per l'utente (sessione aperta sul server, come dopo l'accesso dal PC «da»: quello
    di decisione())."""
    u = accessi.trova(utenti_salvati(), nome)
    sid = accessi.sessioni.nuova(u['id'], da)
    return accessi.COOKIE_RETE + '=' + A.app.session_interface.get_signing_serializer(A.app).dumps({'sid': sid})


def decisione(metodo, url, cookie=None, da_rete=True):
    """Cosa fa la guardia (tutti i before_request) senza far girare la pagina: None se la pagina girerebbe,
    altrimenti (codice, Location, testo)."""
    base = RETE if da_rete else PC
    ambiente = {'REMOTE_ADDR': '192.168.1.77'} if da_rete else {'REMOTE_ADDR': '127.0.0.1'}
    intestazioni = {'Origin': base}
    if cookie:
        intestazioni['Cookie'] = cookie
    with A.app.test_request_context(url, method=metodo, base_url=base, environ_base=ambiente, headers=intestazioni):
        r = A.app.preprocess_request()
        if r is None:
            return None
        r = A.app.make_response(r)
        return r.status_code, r.headers.get('Location') or '', r.get_data(as_text=True)


# ================================================================= prove
def a_censimento():
    """Ogni pagina del programma ha la sua area, scritta una volta sola; il gemello: una pagina finta senza area
    la vede la prova e la rifiuta la guardia."""
    presenti = {r.endpoint for r in A.app.url_map.iter_rules()}
    assert not accessi.senza_area(presenti), 'pagine senza area: %s' % accessi.senza_area(presenti)
    avanzate = sorted(set(accessi.CENSIMENTO) - presenti)
    assert not avanzate, 'aree di pagine che non ci sono più: %s' % avanzate
    for endpoint, area in accessi.CENSIMENTO.items():
        aree = area if isinstance(area, tuple) else (area,)
        assert aree and all(a in accessi.CATEGORIE or a in accessi.CODICI_AREE for a in aree), (endpoint, area)
        assert not isinstance(area, tuple) or all(a in accessi.CODICI_AREE for a in area), (endpoint, area)
    assert set(accessi.PRIMA_PAGINA) == set(accessi.CODICI_AREE)
    for area, endpoint in accessi.PRIMA_PAGINA.items():
        assert accessi.CENSIMENTO[endpoint] == area, (area, endpoint)
    for servizio in ('pazienti.cerca_json', 'pazienti.luoghi_json', 'pazienti.codice_fiscale_json'):
        assert set(accessi.CENSIMENTO[servizio]) == {'pazienti', 'agenda', 'segreteria', 'dove'}, servizio
    assert len(accessi.AREE) == 12 and len(set(accessi.CODICI_AREE)) == 12
    # gemello: una pagina nuova senza area
    assert accessi.senza_area(presenti | {'finto.nuovo'}) == ['finto.nuovo']
    from werkzeug.routing import Rule
    with A.app.test_request_context('/finto', base_url=RETE, environ_base={'REMOTE_ADDR': '192.168.1.5'}) as ctx:
        ctx.request.url_rule = Rule('/finto', endpoint='finto.nuovo')
        r = accessi.controlla_accesso()
        assert r is not None and r.status_code == 403 and 'Solo dal PC della segreteria' in r.get_data(as_text=True)
    with A.app.test_request_context('/finto', base_url=PC) as ctx:
        ctx.request.url_rule = Rule('/finto', endpoint='finto.nuovo')
        assert accessi.controlla_accesso() is None, 'sul PC principale anche una pagina nuova si apre'
    return '%d pagine, ognuna con la sua area; una pagina finta senza area: rifiutata dalla rete' % len(presenti)


def atteso(area, livello_utente, metodo):
    """La regola scritta qui a parte: None (la pagina gira) o il codice."""
    if area == accessi.SISTEMA:
        return 403
    if area in (accessi.LIBERO, accessi.UTENTE, accessi.TRASVERSALE):
        return None
    if livello_utente == 'no':
        return 403
    if metodo == 'POST' and livello_utente != 'modifica':
        return 403
    return None


def b_matrice():
    """Area × livello × pagina × metodo, dal censimento: per ogni pagina e ogni metodo (GET e POST) un utente senza
    l'area (ma con tutte le altre in «modificare»), uno con «solo guardare», uno con «guardare e modificare»; dalla
    rete e dal PC. Il PC principale non è mai fermato."""
    imposta(rete_schermo_libero='')
    nuovi, per_area = [], {}
    for a in accessi.CODICI_AREE:
        per_area[a] = {'no': 'Senza %s' % a, 'guarda': 'Guarda %s' % a, 'modifica': 'Modifica %s' % a}
        nuovi += [utente('Senza %s' % a, 'x' * 12, {b: 'modifica' for b in accessi.CODICI_AREE if b != a}),
                  utente('Guarda %s' % a, 'x' * 12, {a: 'guarda'}),
                  utente('Modifica %s' % a, 'x' * 12, {a: 'modifica'})]
    nuovi.append(utente('Senza servizio', 'x' * 12, {b: 'modifica' for b in accessi.CODICI_AREE
                                                     if b not in accessi.SERVIZIO_PAZIENTI}))
    aggiungi_utenti(*nuovi)
    cookie = {}
    sbagliate, provate, per_pc = [], 0, 0
    for regola in sorted(A.app.url_map.iter_rules(), key=lambda r: r.rule):
        if regola.endpoint == 'static':
            continue
        area = accessi.CENSIMENTO[regola.endpoint]
        url = indirizzo(regola)
        for metodo in sorted({'GET', 'POST'} & set(regola.methods)):
            # dal PC principale: mai fermato (né rimandato all'accesso)
            assert decisione(metodo, url, da_rete=False) is None, ('PC', metodo, url)
            per_pc += 1
            if area == accessi.SCHERMO:
                area_vera = 'ambulatori'               # Modo schermo senza la casella: come Ambulatori e dashboard
            else:
                area_vera = area
            aree = area_vera if isinstance(area_vera, tuple) else (area_vera,)
            prima = aree[0]
            if prima in accessi.CODICI_AREE:
                casi = [(per_area[prima]['no'] if len(aree) == 1 else 'Senza servizio', 'no'),
                        (per_area[prima]['guarda'], 'guarda'), (per_area[prima]['modifica'], 'modifica')]
                # una qualsiasi delle aree di un servizio basta
                casi += [(per_area[b]['guarda'], 'guarda') for b in aree[1:]]
            else:
                casi = [(per_area['agenda']['modifica'], 'modifica')]
            if regola.endpoint == accessi.RICERCA_PAZIENTI:
                # la ricerca dei pazienti: con «solo guardare» delle altre aree no, con «modificare» sì (revisione)
                casi = [(n, 'no' if n.startswith('Guarda ') and n != 'Guarda pazienti' else lv) for n, lv in casi]
                casi += [(per_area[b]['modifica'], 'modifica') for b in aree[1:]]
            for nome, lv in casi:
                if nome not in cookie:
                    cookie[nome] = cookie_di(nome)
                d = decisione(metodo, url, cookie[nome])
                provate += 1
                voluto = atteso(area_vera, lv, metodo)
                if regola.endpoint == 'home' and d is not None and d[0] == 302:
                    d = None                           # la radice porta alla prima pagina dell'utente
                if voluto is None:
                    if d is not None:
                        sbagliate.append((metodo, url, nome, 'fermata: %s %s' % d[:2]))
                else:
                    if d is None or d[0] != voluto or 'lang="it"' not in d[2] and '"errore"' not in d[2]:
                        sbagliate.append((metodo, url, nome, 'voluto %s, avuto %s' % (voluto, d[:2] if d else 'passa')))
                    elif voluto == 403 and lv == 'guarda' and metodo == 'POST' and 'Solo guardare' not in d[2] \
                            and '"errore"' not in d[2]:
                        sbagliate.append((metodo, url, nome, 'il rifiuto non dice «solo guardare»'))
    assert not sbagliate, '%d decisioni sbagliate, per esempio %s' % (len(sbagliate), sbagliate[:5])
    # senza accesso: ogni pagina che non è libera porta all'accesso (o 401 per i JSON, 403 per il Sistema)
    for regola in A.app.url_map.iter_rules():
        area = accessi.CENSIMENTO[regola.endpoint]
        if area in (accessi.LIBERO,) or regola.endpoint == 'static':
            continue
        for metodo in sorted({'GET', 'POST'} & set(regola.methods)):
            d = decisione(metodo, indirizzo(regola))
            voluto = (403,) if area == accessi.SISTEMA else (302, 401)
            assert d is not None and d[0] in voluto, ('senza accesso', metodo, regola.rule, d and d[:2])
            if d[0] == 302:
                assert '/accesso' in d[1], (regola.rule, d[1])
    return '%d decisioni dalla rete giuste, %d dal PC principale tutte libere' % (provate, per_pc)


# attributi data-* con un indirizzo che gli script non chiedono: data-scheda della ricerca dei pazienti è il
# collegamento alla scheda (si apre cliccando, non la chiede lo script); data-aiuto è la base delle guide, da cui
# guida.js chiede <data-aiuto>/<guida>/passi.json per le guide di data-guide (chieste qui una per una)
SOLO_COLLEGAMENTI = {('data-scheda', 'pazienti.scheda'), ('data-aiuto', 'guida.indice')}


class Indirizzi(HTMLParser):
    """Gli indirizzi interni scritti negli attributi data-* (quelli che gli script chiedono)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.trovati = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'body' and a.get('data-aiuto'):
            for guida in json.loads(a.get('data-guide') or '[]'):
                self.trovati.add('%s/%s/passi.json' % (a['data-aiuto'], guida['slug']))
        for k, v in attrs:
            if k.startswith('data-') and v and v.startswith('/') and not v.startswith(('//', '/static/')):
                try:
                    endpoint, _ = A.app.url_map.bind('x').match(v.split('?')[0].replace('/0', '/1'), method='GET')
                except Exception:
                    endpoint = None
                if (k, endpoint) not in SOLO_COLLEGAMENTI:
                    self.trovati.add(v)


def dati_per_le_pagine():
    """Un paziente con un appuntamento, un documento, un appunto, una cosa da fare: le pagine con i numeri trovano
    qualcosa da mostrare."""
    s = A.Sessione()
    p = Paziente(cognome='Esempietti', nome='Canarino', telefono='3331112299', email='canarino@example.com')
    s.add(p)
    s.flush()
    stanza = s.scalars(select(Risorsa).where(Risorsa.tipo == 'AMBULATORIO').order_by(Risorsa.id)).first()
    medico = s.scalars(select(Operatore).order_by(Operatore.id)).first()
    prest = s.scalars(select(Prestazione).order_by(Prestazione.id)).first()
    giorni = 40 + conta(Paziente) % 50          # un giorno diverso a ogni chiamata
    inizio = datetime.combine(date.today() + timedelta(days=giorni), datetime.min.time()).replace(hour=7, minute=10)
    while s.scalars(select(Appuntamento.id).where(Appuntamento.risorsa_id == stanza.id, Appuntamento.inizio == inizio)).first():
        inizio += timedelta(days=1)                # già preso da una chiamata di prima
    a = Appuntamento(risorsa_id=stanza.id, operatore_id=medico.id, prestazione_id=prest.id, paziente_id=p.id,
                     inizio=inizio, fine=inizio + timedelta(minutes=20), stato='PRENOTATO', importo_cent=8000)
    s.add(a)
    s.add(Attivita(testo='Richiamare per il referto', per_il=date.today(), paziente_id=p.id))
    g = StrutturaGruppo(nome='Centro di prova %d' % p.id, citta='Città di prova', telefono='081 000 0001')
    s.add(g)
    s.commit()
    valori = {'aid': a.id, 'pid': p.id, 'oid': medico.id, 'rid': stanza.id, 'sid': stanza.struttura_id, 'gid': g.id}
    s.close()
    return valori


def c_pagine_e_servizi_di_ogni_area():
    """Per ogni area, chi ha solo quella in «solo guardare» apre tutte le sue pagine (GET) e ogni indirizzo che
    quelle pagine chiedono con gli script (data-*): nessun 401 o 403, nessun errore del server. Il gemello: lo
    stesso utente non apre la prima pagina di un'altra area."""
    valori = dati_per_le_pagine()
    nuovi = [utente('Solo %s' % a, 'x' * 12, {a: 'guarda'}) for a in accessi.CODICI_AREE]
    aggiungi_utenti(*nuovi)
    aperte, servizi, sbagliate = 0, 0, []
    for a in accessi.CODICI_AREE:
        c = rete(ip='192.168.1.%d' % (100 + accessi.CODICI_AREE.index(a)))
        r = entra(c, 'Solo %s' % a, 'x' * 12)
        assert r.status_code == 302, (a, r.status_code)
        da_chiedere = set()
        for regola in A.app.url_map.iter_rules():
            area = accessi.CENSIMENTO[regola.endpoint]
            if 'GET' not in regola.methods or not (area == a or isinstance(area, tuple) and a in area):
                continue
            if regola.endpoint == accessi.RICERCA_PAZIENTI and a != 'pazienti':
                continue                                  # con «solo guardare» delle altre aree non c'è (z_ricerca_pazienti)
            url = indirizzo(regola, valori)
            r = chiedi(c, 'GET', url)
            aperte += 1
            if r.status_code in (401, 403) or r.status_code >= 500 or \
                    r.status_code == 302 and '/accesso' in (r.headers.get('Location') or ''):
                sbagliate.append((a, url, r.status_code))
            elif r.mimetype == 'text/html' and r.status_code == 200:
                guarda = Indirizzi()
                guarda.feed(testo(r))
                da_chiedere |= guarda.trovati
        for url in sorted(da_chiedere):
            try:
                endpoint, argomenti = A.app.url_map.bind('192.168.1.10:5080').match(url.split('?')[0], method='GET')
            except Exception:
                continue                                  # un indirizzo solo per i moduli (POST) o un pezzo di indirizzo
            prova_url = url
            if url.endswith('/0'):                        # «/0» lo sostituisce lo script con il numero scelto
                nome_arg = next(k for k, v in argomenti.items() if v == 0)
                prova_url = url[:-2] + '/%d' % valori.get(nome_arg, 1)
            prova_url += ('&' if '?' in prova_url else '?') + 'q=es'
            r = chiedi(c, 'GET', prova_url)
            servizi += 1
            if r.status_code != 200:
                sbagliate.append((a, 'servizio ' + prova_url, r.status_code, endpoint))
        # gemello: un'altra area no
        altra = accessi.CODICI_AREE[(accessi.CODICI_AREE.index(a) + 1) % len(accessi.CODICI_AREE)]
        r = chiedi(c, 'GET', A.app.url_map.bind('x').build(accessi.PRIMA_PAGINA[altra]))
        assert rifiutata(r), (a, altra, r.status_code)
    assert not sbagliate, '%d pagine o servizi chiusi a chi ha l\'area: %s' % (len(sbagliate), sbagliate[:6])
    assert servizi >= 10, 'troppo pochi indirizzi trovati negli attributi data-*: %d' % servizi
    return '%d pagine e %d indirizzi chiesti dagli script, per 12 aree: tutti aperti a chi ha l\'area' % (aperte, servizi)


def d_dalla_rete_in_ogni_modo():
    """Dalla rete in cinque modi (un altro indirizzo, la presa della rete, X-Forwarded-For, Forwarded, X-Real-Ip):
    sempre la pagina di accesso; il gemello: dal PC principale la stessa pagina si apre."""
    for come in ('indirizzo', 'presa', 'inoltrata', 'forwarded', 'real-ip'):
        c = rete(come)
        r = chiedi(c, 'GET', '/oggi')
        assert r.status_code == 302 and '/accesso?dopo=/oggi' in r.headers['Location'], (come, r.status_code,
                                                                                       r.headers.get('Location'))
        r = chiedi(c, 'GET', '/notifiche.json')
        assert r.status_code == 401 and r.mimetype == 'application/json', (come, r.status_code)
        prima = conta(NotaGiorno)
        r = chiedi(c, 'POST', '/note-giorno', data={'struttura': 1, 'data': OGGI, 'testo': 'dalla rete'})
        assert r.status_code == 302 and '/accesso' in r.headers['Location'], (come, r.status_code)
        assert conta(NotaGiorno) == prima, 'una nota salvata senza accesso'
        t = testo(chiedi(c, 'GET', '/accesso'))
        assert 'Password' in t and 'in chiaro' in t, 'la pagina di accesso deve dire che il collegamento è in chiaro'
    assert locale().get('/oggi').status_code == 200
    with A.app.test_request_context('/oggi', base_url=PC):
        assert not accessi.dalla_rete()
    return 'cinque modi di arrivare dalla rete: tutti alla pagina di accesso; il PC principale no'


def e_sistema_mai_dalla_rete():
    c = rete()
    assert entra(c, 'Tutto Provolo').status_code == 302
    assert chiedi(c, 'GET', '/cassa/%s' % OGGI).status_code == 200
    sistema = [(m, indirizzo(r)) for r in A.app.url_map.iter_rules() if accessi.CENSIMENTO[r.endpoint] == accessi.SISTEMA
               for m in sorted({'GET', 'POST'} & set(r.methods))]
    assert len(sistema) >= 12, sistema
    for metodo, url in sistema:
        r = chiedi(c, metodo, url)
        assert r.status_code == 403 and ('Solo dal PC della segreteria' in testo(r) or r.mimetype == 'application/json'), \
            (metodo, url, r.status_code)
    # «sistema» scritto nel JSON non dà le notifiche del Sistema (Backup) né l'allarme dei backup
    import backup
    prima = dict(backup.stato)
    backup.stato.update(ultimo_errore='disco pieno (prova)', ultimo_ok=None)
    try:
        sul_pc = locale().get('/notifiche.json?struttura=1').json
        assert any(n['chiave'].startswith('backup-') for n in sul_pc), 'gemello: sul PC la notifica del backup c\'è'
        assert 'disco pieno' in locale().get('/oggi').get_data(as_text=True), 'gemello: sul PC l\'allarme c\'è'
        dalla_rete = chiedi(c, 'GET', '/notifiche.json?struttura=1').json
        assert dalla_rete and not [n for n in dalla_rete if n['chiave'].startswith(('backup-', 'autoripara-', 'aggiorn'))]
        assert 'disco pieno' not in testo(chiedi(c, 'GET', '/oggi')), 'l\'allarme dei backup dalla rete'
    finally:
        backup.stato.clear()
        backup.stato.update(prima)
    # anche senza accesso il Sistema risponde 403 subito, senza aprire il database (come /salute)
    vero = A.ses
    A.ses = lambda: (_ for _ in ()).throw(RuntimeError('database fermo'))
    try:
        assert chiedi(rete(), 'GET', '/salute').status_code == 403
        assert chiedi(rete(), 'GET', '/impostazioni').status_code == 403
        assert locale().get('/salute').status_code == 200, 'gemello: /salute del PC senza database'
    finally:
        A.ses = vero
    return '%d pagine del Sistema: 403 anche per chi ha tutto (e «sistema» scritto nel JSON)' % len(sistema)


def f_pc_principale_invariato():
    c = locale()
    for percorso in ('/oggi', '/impostazioni', '/autoriparazione', '/aggiornamenti', '/cassa/%s' % OGGI,
                     '/configura/accessi', '/riepilogo-live?schermo=1', '/notifiche.json', '/appuntamento/1'):
        r = c.get(percorso)
        assert r.status_code == 200, (percorso, r.status_code)
        assert 'Esci' not in testo(r) or percorso == '/configura/accessi', percorso
    assert c.get('/accesso').status_code == 302, 'sul PC principale la pagina di accesso non serve'
    assert c.get('/accesso/password').status_code == 302
    prima = conta(NotaGiorno)
    r = c.post('/note-giorno', data={'struttura': 1, 'data': '2026-12-01', 'testo': 'dal PC'})
    assert r.status_code == 302 and conta(NotaGiorno) == prima + 1
    # l'impostazione della rete spenta o accesa non cambia niente sul PC
    imposta(rete_accesa='')
    assert c.get('/oggi').status_code == 200 and c.get('/configura/accessi').status_code == 200
    configura_di_partenza()
    # il cookie: sul PC il nome di sempre; dalla rete un nome suo, HttpOnly e SameSite=Strict
    c.post('/note-giorno', data={'struttura': 1, 'data': '2026-12-02', 'testo': 'x'})
    assert c.get_cookie('session') is not None and c.get_cookie(accessi.COOKIE_RETE) is None
    r = entra(rete(), 'Anna Esempietti')
    intestazione = r.headers.get('Set-Cookie', '')
    assert intestazione.startswith(accessi.COOKIE_RETE + '=') and 'HttpOnly' in intestazione and \
        'SameSite=Strict' in intestazione, intestazione
    # nessuna riga nel registro per il PC principale
    assert not [e for e in accessi.eventi if e[2] == '127.0.0.1'], 'il registro degli accessi scrive anche il PC'
    return 'tutte le pagine, con la rete accesa o spenta; cookie di sempre; registro solo per la rete'


def g_modo_schermo():
    # di partenza (nessuna riga fra le impostazioni): rete spenta, schermo con l'accesso, porta 5080
    s = A.Sessione()
    from modelli import Impostazione
    for k in ('rete_accesa', 'rete_schermo_libero', 'rete_porta', 'rete_nomi', 'rete_utenti'):
        riga = s.get(Impostazione, k)
        if riga is not None:
            s.delete(riga)
    s.commit()
    cfg = accessi.configurazione(s)
    s.close()
    assert (cfg['accesa'], cfg['schermo_libero'], cfg['porta'], cfg['utenti']) == (False, False, 5080, []), cfg
    configura_di_partenza()
    s = A.Sessione()
    s.delete(s.get(Impostazione, 'rete_schermo_libero'))
    s.commit()
    s.close()
    anonimo = rete()
    # rete accesa, casella spenta (la partenza): anche il Modo schermo vuole l'accesso
    r = chiedi(anonimo, 'GET', '/riepilogo-live?schermo=1')
    assert r.status_code == 302 and '/accesso' in r.headers['Location'], r.status_code
    assert chiedi(anonimo, 'GET', '/riepilogo-live.json').status_code == 401
    imposta(rete_schermo_libero='1')
    for percorso in ('/riepilogo-live?schermo=1', '/riepilogo-live.json', '/riepilogo-live/statistiche?schermo=1',
                     '/riepilogo-live/statistiche.json', '/static/stile.css'):
        assert chiedi(anonimo, 'GET', percorso).status_code == 200, percorso
    # senza ?schermo=1 la pagina ha il menu: con l'accesso
    assert chiedi(anonimo, 'GET', '/riepilogo-live').status_code == 302
    # i collegamenti della dashboard in modo schermo restano dentro le pagine libere
    t = testo(chiedi(anonimo, 'GET', '/riepilogo-live?schermo=1'))
    collegamenti = {h.replace('&amp;', '&') for h in re.findall(r'href="(/[^"#]*)"', t)}
    assert collegamenti, 'nessun collegamento nella dashboard'
    for h in collegamenti:
        r = chiedi(anonimo, 'GET', h)
        if 'schermo=1' in h or not h.startswith('/riepilogo-live'):
            assert r.status_code == 200, ('collegamento della dashboard', h, r.status_code)
        else:                                  # uscire dal modo schermo (il menu) vuole l'accesso
            assert r.status_code == 302 and '/accesso' in r.headers['Location'], ('uscita dal modo schermo', h)
    # con l'accesso ma senza Ambulatori e dashboard: no
    c = rete(ip='192.168.1.71')
    entra(c, 'Anna Esempietti')
    imposta(rete_schermo_libero='')
    assert rifiutata(chiedi(c, 'GET', '/riepilogo-live?schermo=1')), 'senza Ambulatori e dashboard'
    # rete spenta: il portiere di oggi (Caddy) continua a mostrare il Modo schermo, il resto no
    imposta(rete_accesa='')
    p = rete('inoltrata')
    for percorso in ('/riepilogo-live?schermo=1', '/riepilogo-live', '/riepilogo-live.json', '/static/stile.css',
                     '/logo/1'):
        assert chiedi(p, 'GET', percorso).status_code == 200, percorso
    r = chiedi(p, 'GET', '/oggi')
    assert r.status_code == 403 and 'spento' in testo(r)
    assert chiedi(p, 'POST', '/accesso', data={'nome': 'Tutto Provolo', 'password': PASSWORD['Tutto Provolo']}).status_code == 403
    assert chiedi(c, 'GET', '/oggi').status_code == 403, 'rete spenta: chi era entrato non entra più'
    return 'Modo schermo con l\'accesso o libero con la casella; rete spenta: solo lui, come prima'


def h_nome_e_origine():
    c = rete()
    assert c.get('/oggi', base_url='http://cattivo.example:5080').status_code == 400
    assert c.get('/oggi', base_url='http://192.168.1.10:8080').status_code == 400, 'nome giusto, porta sbagliata'
    assert c.get('/accesso', base_url='http://pc-segreteria:5080').status_code == 200, 'gemello: un nome scritto'
    entra(c, 'Anna Esempietti')
    prima = conta(NotaGiorno)
    r = c.post('/note-giorno', base_url=RETE, headers={'Origin': 'http://cattivo.example'},
               data={'struttura': 1, 'data': OGGI, 'testo': 'da un altro sito'})
    assert r.status_code == 403 and conta(NotaGiorno) == prima, r.status_code
    r = c.post('/note-giorno', base_url=RETE, headers={'Origin': RETE},
               data={'struttura': 1, 'data': OGGI, 'testo': 'Fintini arriva alle 10'})
    assert r.status_code == 302 and conta(NotaGiorno) == prima + 1, 'gemello: dalla pagina giusta si salva'
    return 'nome di un altro sito: 400; modulo da un altro sito: 403; dalla pagina giusta passa'


def i_sessioni_sul_server():
    """Correzione 4: l'id nel cookie, la sessione sul server. «Esci» la chiude davvero (lo stesso cookie, rimandato,
    non vale più), «Fai uscire», password cambiata, utente spento o tolto: fuori."""
    def dentro(c):
        r = chiedi(c, 'GET', '/oggi')
        return r.status_code == 200
    c = rete(ip='192.168.1.80')
    assert entra(c, 'Tutto Provolo').status_code == 302 and dentro(c)
    biscotto = c.get_cookie(accessi.COOKIE_RETE, domain='192.168.1.10').value
    sid = A.app.session_interface.get_signing_serializer(A.app).loads(biscotto)['sid']
    assert len(sid) >= 40 and accessi.impronta_id(sid) in accessi.sessioni.dati and sid not in json.dumps(accessi.sessioni.dati)
    # lo stesso cookie da un altro client dello stesso PC: vale (gemello di quello che segue; da un altro PC no:
    # z_cookie_da_un_altro_pc)
    copia = rete(ip='192.168.1.80')
    copia.set_cookie(accessi.COOKIE_RETE, biscotto, domain='192.168.1.10')
    assert dentro(copia)
    assert chiedi(c, 'POST', '/esci').status_code == 302
    assert not dentro(c) and not dentro(copia), '«Esci»: il cookie rimandato vale ancora'
    # «Fai uscire» dal PC principale
    u = accessi.trova(utenti_salvati(), 'Tutto Provolo')
    d1, d2 = rete(ip='192.168.1.82'), rete(ip='192.168.1.83')
    entra(d1, 'Tutto Provolo')
    entra(d2, 'Tutto Provolo')
    a = rete(ip='192.168.1.84')
    entra(a, 'Anna Esempietti')
    assert dentro(d1) and dentro(d2) and dentro(a) and accessi.sessioni.quante(u['id']) == 2
    assert 'Fai uscire Tutto Provolo' in locale().get('/configura/accessi').get_data(as_text=True)
    locale().post('/configura/accessi', data={'azione': 'fai-uscire', 'utente': u['id']})
    assert not dentro(d1) and not dentro(d2), '«Fai uscire»'
    assert dentro(a), 'gemello: gli altri utenti restano dentro'
    # password data dal PC principale: chi era entrato esce (fuori del tutto: di nuovo alla pagina di accesso)
    entra(d1, 'Tutto Provolo')
    assert accessi.sessioni.quante(u['id']) == 1
    locale().post('/configura/accessi', data={'azione': 'password', 'utente': u['id'], 'password': 'tetto rosso di sera'})
    r = chiedi(d1, 'GET', '/oggi')
    assert r.status_code == 302 and '/accesso?' in r.headers['Location'] and accessi.sessioni.quante(u['id']) == 0, \
        ('password data dal PC: chi era entrato è ancora dentro', r.headers.get('Location'))
    # utente spento: esce
    entra(a, 'Anna Esempietti')
    ua = accessi.trova(utenti_salvati(), 'Anna Esempietti')
    locale().post('/configura/accessi', data={'azione': 'salva', 'utente': ua['id'], 'area_agenda': 'modifica'})
    assert not dentro(a), 'utente spento: è ancora dentro'
    # tolto e rifatto con lo stesso nome: la sessione di prima non vale (id casuale, non il nome)
    configura_di_partenza()
    v = rete(ip='192.168.1.85')
    entra(v, 'Anna Esempietti')
    assert dentro(v)
    vecchio = accessi.trova(utenti_salvati(), 'Anna Esempietti')
    nuovo = utente('Anna Esempietti', PASSWORD['Anna Esempietti'], {'agenda': 'modifica'})
    imposta(rete_utenti=json.dumps([x for x in utenti_salvati() if x['id'] != vecchio['id']] + [nuovo]))
    assert nuovo['id'] != vecchio['id'] and not dentro(v), 'rifatto con lo stesso nome: dentro con la sessione di prima'
    # le sessioni restano dopo un riavvio (il file accanto alla chiave), ma non quelle scadute
    w = rete(ip='192.168.1.86')
    entra(w, 'Anna Esempietti')
    biscotto = w.get_cookie(accessi.COOKIE_RETE, domain='192.168.1.10').value
    sid = A.app.session_interface.get_signing_serializer(A.app).loads(biscotto)['sid']
    def nel_file():
        with open(os.path.join(PROVVISORIA, 'sessioni-rete.json'), encoding='utf-8') as f:
            return accessi.impronta_id(sid) in json.load(f)
    # entrando il file si riscrive al più ogni SALVA_SESSIONI_OGNI secondi (z_sessioni_per_utente)
    assert aspetta(nel_file, accessi.SALVA_SESSIONI_OGNI + 3), 'la sessione non è nel file'
    accessi.sessioni.carica(PROVVISORIA)
    assert dentro(w), 'dopo il riavvio la sessione è sparita'
    accessi.sessioni.dati[accessi.impronta_id(sid)]['ultimo'] = time.time() - accessi.INATTIVITA - 5
    assert not dentro(w), 'inattivo da più di 4 ore: ancora dentro'
    entra(w, 'Anna Esempietti')
    accessi.sessioni.dati[accessi.impronta_id(
        A.app.session_interface.get_signing_serializer(A.app).loads(
            w.get_cookie(accessi.COOKIE_RETE, domain='192.168.1.10').value)['sid'])]['dal'] = \
        time.time() - accessi.DURATA_MASSIMA - 5
    assert not dentro(w), 'dentro da più di 12 ore: ancora dentro'
    # un cookie scritto a mano (senza la chiave) non vale
    falso = rete(ip='192.168.1.87')
    falso.set_cookie(accessi.COOKIE_RETE, 'eyJzaWQiOiJ4In0.falso.firma', domain='192.168.1.10')
    assert not dentro(falso)
    return 'Esci vero (cookie rimandato: fuori), Fai uscire, password data, utente spento o rifatto, inattività, riavvio'


def j_tentativi():
    """Correzione 9: per (PC, nome) 5 sbagliate in un quarto d'ora; per nome, da qualsiasi PC, dopo 20 l'attesa
    cresce; i nomi che non esistono contano uguale; «Sblocca» dalla pagina."""
    c = rete(ip='192.168.1.61')
    for _ in range(5):
        r = entra(c, 'Anna Esempietti', 'sbagliata del tutto')
        assert r.status_code == 200 and accessi.MESSAGGIO_SBAGLIATO in testo(r)
    r = entra(c, 'Anna Esempietti')
    assert r.status_code == 429 and 'Troppi tentativi' in testo(r), 'dopo 5 sbagliate la giusta passa subito'
    # gemelli: lo stesso PC con un altro nome, e lo stesso nome da un altro PC, entrano (sotto la soglia del nome)
    assert entra(c, 'Guarda Fittizi').status_code == 302
    assert entra(rete(ip='192.168.1.62'), 'Anna Esempietti').status_code == 302
    # dopo il quarto d'ora si riprova
    t0 = time.time()
    assert accessi.tentativi.attesa('192.168.1.61', 'anna esempietti', t0) > 0
    accessi.tentativi.svuota()
    for i in range(5):
        accessi.tentativi.sbagliata('192.168.1.61', 'Anna Esempietti', t0 + i)
    assert accessi.tentativi.attesa('192.168.1.61', 'Anna Esempietti', t0 + 5) > 800
    assert accessi.tentativi.attesa('192.168.1.61', 'Anna Esempietti', t0 + 4 + accessi.FINESTRA + 1) == 0
    # per nome: 20 sbagliate da 20 PC diversi, poi anche dal 21esimo con la password giusta si aspetta
    accessi.tentativi.svuota()
    for i in range(accessi.SOGLIA_NOME):
        assert entra(rete(ip='10.0.0.%d' % (i + 1)), 'Tutto Provolo', 'sbagliata %d' % i).status_code == 200
    r = entra(rete(ip='10.0.1.1'), 'Tutto Provolo')
    assert r.status_code == 429, 'dopo 20 sbagliate da PC diversi si entra lo stesso'
    # l'attesa cresce: 1, 2, 4 minuti... fino a un'ora
    accessi.tentativi.svuota()
    durate = []
    for n in range(accessi.SOGLIA_NOME + 8):
        accessi.tentativi.sbagliata('ip-%d' % n, 'Nome Prova', t0)
        durate.append(accessi.tentativi.attesa('altro', 'Nome Prova', t0))
    assert durate[accessi.SOGLIA_NOME - 2] == 0 and durate[accessi.SOGLIA_NOME - 1] == 61, durate
    assert durate[accessi.SOGLIA_NOME] == 121 and durate[accessi.SOGLIA_NOME + 2] == 481, durate
    assert durate[-1] == accessi.ATTESA_MASSIMA + 1, durate[-1]
    # un nome che non esiste si blocca come gli altri (dal blocco non si capisce se il nome c'è)
    accessi.tentativi.svuota()
    x = rete(ip='192.168.1.63')
    for _ in range(5):
        entra(x, 'Nessuno Inventato', 'qualcosa di lungo')
    assert entra(x, 'Nessuno Inventato', 'qualcosa di lungo').status_code == 429
    # «Sblocca» dal PC principale
    for _ in range(5):
        entra(x, 'Anna Esempietti', 'sbagliata ancora qui')
    assert entra(x, 'Anna Esempietti').status_code == 429
    pagina = locale().get('/configura/accessi').get_data(as_text=True)
    assert 'anna esempietti' in pagina and 'Sblocca' in pagina, 'il nome bloccato non è nella pagina'
    locale().post('/configura/accessi', data={'azione': 'sblocca', 'nome': 'anna esempietti'})
    assert entra(x, 'Anna Esempietti').status_code == 302, 'dopo «Sblocca» si entra'
    return 'per PC e nome 5, per nome 20 con attesa 1→2→4… minuti fino a un\'ora; nomi inesistenti uguali; Sblocca'


def k_messaggi_e_registro():
    """Correzione 10: sempre «Nome o password non giusti.» (password sbagliata, nome sconosciuto, utente spento);
    il registro: un file per giorno, senza caratteri di controllo, con salvataggi e letture di schede ed Excel."""
    pagine = []
    for ip, nome, password in (('192.168.1.91', 'Anna Esempietti', 'sbagliata ma lunga'),
                               ('192.168.1.92', 'Nessuno Inventato', 'qualcosa ma lungo'),
                               ('192.168.1.93', 'Spento Testabianca', PASSWORD['Spento Testabianca'])):
        r = entra(rete(ip=ip), nome, password)
        assert r.status_code == 200 and accessi.MESSAGGIO_SBAGLIATO in testo(r), (nome, r.status_code)
        pagine.append(testo(r).replace(nome, 'NOME'))
    assert pagine[0] == pagine[1] == pagine[2], 'le tre pagine di errore non sono uguali: si capisce se il nome c\'è'
    assert 'disattivato' not in pagine[2] and 'spento' not in pagine[2].lower()
    # il registro: una riga finta scritta nel nome non diventa una riga
    entra(rete(ip='192.168.1.94'), 'Anna\x1b[2J\x07finta\n2026 entrato', 'sbagliata ma lunga')
    c = rete(ip='192.168.1.95')
    entra(c, 'Tutto Provolo')
    pid = primo(Paziente)
    chiedi(c, 'GET', '/pazienti/%d' % pid)
    chiedi(c, 'GET', '/statistiche/excel')
    chiedi(c, 'POST', '/note-giorno', data={'struttura': 1, 'data': OGGI, 'testo': 'dal registro'})
    chiedi(c, 'GET', '/oggi')
    percorso = os.path.join(PROVVISORIA, 'accessi', 'accessi-%s.log' % OGGI)
    assert os.path.isfile(percorso), os.listdir(os.path.join(PROVVISORIA, 'accessi'))
    with open(percorso, encoding='utf-8') as f:
        righe = f.read().splitlines()
    assert all(re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+ (INFO|WARNING) ', r) for r in righe), \
        [r for r in righe if not re.match(r'\d{4}-', r)][:2]
    assert not any('\x1b' in r or '\r' in r for r in righe)
    assert any('Anna?[2J?finta 2026 entrato' in r for r in righe), 'il nome con i caratteri di controllo (puliti)'
    assert accessi.pulito('uno\ndue\rtre\u2028quattro\x00') == 'uno?due?tre?quattro?'
    for atteso_ in ('aperto /pazienti/%d' % pid, 'aperto /statistiche/excel', 'POST /note-giorno', 'entrato'):
        assert any(atteso_ in r for r in righe), 'manca nel registro: %s' % atteso_
    assert not any('/oggi' in r and 'Tutto Provolo' in r for r in righe), 'gemello: una pagina normale non si scrive'
    # ogni Excel e ogni documento scaricato dalla rete si scrive: le funzioni che danno un Excel sono in REGISTRA_LETTURE
    excel = {r.endpoint for r in A.app.url_map.iter_rules() if 'excel' in r.endpoint or r.rule.endswith(('.xlsx', '/excel'))}
    assert excel <= accessi.REGISTRA_LETTURE, 'Excel non scritti nel registro: %s' % sorted(excel - accessi.REGISTRA_LETTURE)
    # i file più vecchi di un anno e mezzo si cancellano all'avvio, gli altri no
    vecchio = os.path.join(PROVVISORIA, 'accessi', 'accessi-2020-01-01.log')
    recente = os.path.join(PROVVISORIA, 'accessi', 'accessi-%s.log' % (date.today() - timedelta(days=30)).isoformat())
    for p in (vecchio, recente):
        open(p, 'w').close()
    accessi.prepara_registro(PROVVISORIA)
    assert not os.path.exists(vecchio) and os.path.exists(recente)
    return 'un solo messaggio per i tre errori; registro per giorno, pulito, con salvataggi, schede ed Excel'


def l_password():
    """Correzione 11: password vietate, lunghezza, il nome dentro; la prima volta si cambia; consiglio della frase."""
    cattive = ['corta', 'Posillipo2026!', 'password1234', 'ciaociaociao', '1234567890', 'qwertyuiop', 'aaaaaaaaaaaa',
               '2026-11-22!!', 'Nefrocenter-1', 'annaesempietti!', 'Esempietti 2026',
               # revisione dell'attaccante: cifre in fila con poche lettere, parole vietate attaccate o con una lettera
               # in più, poche lettere ripetute
               '1234567890a', '1234512345ab', '12345678910x', 'clinicaposillipo1', 'Password1!a', 'amoremio123',
               'aa11bb22cc33', 'Gatto2026!']
    for p in cattive:
        assert accessi.problema_password(p, 'Anna Esempietti'), 'accettata: %r' % p
    buone = ['mela verde sul tavolo', 'Treno-Lento-Verso-Sud', 'cassetto pieno di bottoni 7', 'nave lenta nel porto',
             'ombrello giallo di carta', 'pentola blu sul fuoco', 'barca verde nel lago', 'scala a pioli nuova',
             'nuvola sopra il mare', 'tetto rosso di sera', 'Gatto123 sul divano rosso']
    for p in buone:
        assert accessi.problema_password(p, 'Anna Esempietti') is None, (p, accessi.problema_password(p, 'Anna Esempietti'))
    loc = locale()
    pagina = loc.get('/configura/accessi').get_data(as_text=True)
    assert 'tre o quattro parole' in pagina, 'il consiglio della frase lunga non c\'è'
    prima = len(utenti_salvati())
    loc.post('/configura/accessi', data={'azione': 'nuovo', 'nome': 'Nuovo Fintini', 'password': 'password1234'})
    assert len(utenti_salvati()) == prima, 'utente creato con una password vietata'
    loc.post('/configura/accessi', data={'azione': 'nuovo', 'nome': 'Nuovo Fintini', 'password': 'scala a pioli nuova'})
    u = accessi.trova(utenti_salvati(), 'Nuovo Fintini')
    assert u and u['cambia'] and u['aree'] == {} and len(u['id']) == 16, u
    assert u['hash'].startswith(('scrypt:', 'pbkdf2:')) and 'scala a pioli' not in leggi('rete_utenti')
    loc.post('/configura/accessi', data={'azione': 'salva', 'utente': u['id'], 'attivo': '1', 'area_cassa': 'guarda'})
    c = rete(ip='192.168.1.111')
    r = entra(c, 'nuovo fintini', 'scala a pioli nuova')         # il nome senza badare alle maiuscole
    assert r.status_code == 302 and r.headers['Location'].endswith('/accesso/password'), r.headers.get('Location')
    r = chiedi(c, 'GET', '/cassa/listino')
    assert r.status_code == 302 and r.headers['Location'].endswith('/accesso/password'), 'si va avanti senza cambiarla'
    assert chiedi(c, 'GET', '/notifiche.json').status_code == 401
    r = chiedi(c, 'POST', '/accesso/password', data={'attuale': 'scala a pioli nuova', 'nuova': 'password1234',
                                                     'ancora': 'password1234'})
    assert r.status_code == 200 and 'indovinano' in testo(r)
    r = chiedi(c, 'POST', '/accesso/password', data={'attuale': 'scala a pioli nuova', 'nuova': 'nuvola sopra il mare',
                                                     'ancora': 'nuvola sopra il marx'})
    assert r.status_code == 200 and 'non sono uguali' in testo(r)
    r = chiedi(c, 'POST', '/accesso/password', data={'attuale': 'altra cosa sbagliata', 'nuova': 'nuvola sopra il mare',
                                                     'ancora': 'nuvola sopra il mare'})
    assert r.status_code == 200 and 'attuale non è giusta' in testo(r)
    r = chiedi(c, 'POST', '/accesso/password', data={'attuale': 'scala a pioli nuova', 'nuova': 'nuvola sopra il mare',
                                                     'ancora': 'nuvola sopra il mare'})
    assert r.status_code == 302 and r.headers['Location'].endswith('/cassa/listino'), r.headers.get('Location')
    assert chiedi(c, 'GET', '/cassa/listino').status_code == 200, 'dopo il cambio la cassa si apre'
    assert not accessi.trova(utenti_salvati(), 'Nuovo Fintini')['cambia']
    assert entra(rete(ip='192.168.1.112'), 'Nuovo Fintini', 'scala a pioli nuova').status_code == 200, 'la vecchia vale'
    assert entra(rete(ip='192.168.1.113'), 'Nuovo Fintini', 'nuvola sopra il mare').status_code == 302
    return '%d password cattive rifiutate, %d buone accettate; cambio obbligato al primo accesso' % (len(cattive), len(buone))


def prenotazione(chi, **altro):
    s = A.Sessione()
    stanza = s.scalars(select(Risorsa).where(Risorsa.tipo == 'AMBULATORIO').order_by(Risorsa.id)).first()
    medico = s.scalars(select(Operatore).order_by(Operatore.id)).first()
    prest = s.scalars(select(Prestazione).order_by(Prestazione.id)).first()
    dati = {'struttura': stanza.struttura_id, 'risorsa': stanza.id, 'operatore': medico.id, 'prestazione': prest.id,
            'durata': '20', 'paziente_id': chi.id, 'paziente': chi.cognome, 'nome_paziente': chi.nome,
            'telefono': '3339990011', 'email_paziente': 'nuovo@example.com', 'tipo': '', 'degenza': '',
            'indirizzo_paziente': 'Via Inventata 3', 'convenzione': 'Assicurazione Finta', 'importo': '123,00'}
    dati.update(altro)
    s.close()
    return dati


def m_scritture_fra_aree():
    """Correzione 5: la prenotazione dalla rete aggiorna la scheda del paziente solo con «modificare» i Pazienti,
    importo e convenzione solo con la Cassa, lista d'attesa e appunti solo con la Segreteria. Il gemello: chi ha
    tutto (e il PC) li cambia."""
    def paziente_nuovo(cognome):
        s = A.Sessione()
        p = Paziente(cognome=cognome, nome='Prova', telefono='3330001122', email='vecchia@example.com')
        s.add(p)
        s.flush()
        x = Attesa(paziente_id=p.id, struttura_id=1, note='lista d\'attesa di prova')
        s.add(x)
        s.commit()
        uscita = (types.SimpleNamespace(id=p.id, cognome=p.cognome, nome=p.nome), x.id)
        s.close()
        return uscita

    def guarda(pid, xid):
        s = A.Sessione()
        try:
            p = s.get(Paziente, pid)
            a = s.scalars(select(Appuntamento).where(Appuntamento.paziente_id == pid).order_by(Appuntamento.id.desc())).first()
            x = s.get(Attesa, xid)
            return p.telefono, p.email, p.indirizzo, a and a.importo_cent, a and a.convenzione, x.esito
        finally:
            s.close()
    giorno = (date.today() + timedelta(days=60)).isoformat()
    # solo Agenda (modificare) e Pazienti (guardare): Anna
    p, xid = paziente_nuovo('Esempietti')
    c = rete(ip='192.168.1.120')
    entra(c, 'Anna Esempietti')
    prima_attesa = guarda(p.id, xid)[5]
    r = chiedi(c, 'POST', '/appuntamento', data=prenotazione(p, data=giorno, ora='07:00', attesa=xid))
    assert r.status_code == 302 and '/giorno/' in r.headers['Location'], (r.status_code, r.headers.get('Location'))
    tel, email, indirizzo_, importo, convenzione, attesa_ = guarda(p.id, xid)
    assert (tel, email) == ('3330001122', 'vecchia@example.com') and not indirizzo_, \
        'la scheda del paziente cambiata da chi può solo guardare i Pazienti: %s %s %s' % (tel, email, indirizzo_)
    assert importo is None and convenzione == '', 'importo o convenzione salvati senza la Cassa: %s %s' % (importo, convenzione)
    assert attesa_ == prima_attesa, 'la lista d\'attesa chiusa senza la Segreteria'
    # un paziente nuovo si crea lo stesso, con i suoi dati
    prima = conta(Paziente)
    nuovo = prenotazione(p, data=giorno, ora='07:40', paziente_id='', paziente='Fittizi', nome_paziente='Nuova',
                         telefono='3337776655')
    assert chiedi(c, 'POST', '/appuntamento', data=nuovo).status_code == 302
    assert conta(Paziente) == prima + 1
    # gemello: chi ha tutto in «modificare»
    p2, xid2 = paziente_nuovo('Provolo')
    t = rete(ip='192.168.1.121')
    entra(t, 'Tutto Provolo')
    r = chiedi(t, 'POST', '/appuntamento', data=prenotazione(p2, data=giorno, ora='08:20', attesa=xid2))
    assert r.status_code == 302
    tel, email, indirizzo_, importo, convenzione, attesa_ = guarda(p2.id, xid2)
    assert (tel, email, indirizzo_) == ('3339990011', 'nuovo@example.com', 'Via Inventata 3'), (tel, email, indirizzo_)
    assert importo == 12300 and convenzione == 'Assicurazione Finta', (importo, convenzione)
    assert attesa_ != prima_attesa, 'gemello: chi ha la Segreteria chiude la lista d\'attesa'
    # gemello: il PC principale come prima
    p3, xid3 = paziente_nuovo('Testabianca')
    r = locale().post('/appuntamento', data=prenotazione(p3, data=giorno, ora='09:00', attesa=xid3))
    assert r.status_code == 302 and guarda(p3.id, xid3)[3] == 12300
    return 'senza i permessi: scheda, importo, convenzione e lista d\'attesa intatti; con i permessi e dal PC cambiano'


def n_letture_fra_aree():
    """Correzione 6: nella prenotazione prezzi e incasso solo con la Cassa, messaggi solo con Email e WhatsApp,
    lista d'attesa e documenti solo con le loro aree; notifiche con la loro area; /sposta/avvisi solo gli
    appuntamenti spostati da chi chiede; la ricerca rapida senza pazienti a chi non ha Pazienti."""
    valori = dati_per_le_pagine()
    aid = valori['aid']
    s = A.Sessione()
    for p in s.scalars(select(Prestazione)):
        p.tariffa_cent = p.tariffa_cent or 7000          # un prezzo di listino: la mappa dei prezzi non è vuota
    s.commit()
    s.close()
    aggiungi_utenti(utente('Solo Agenda', 'x' * 12, {'agenda': 'modifica'}),
                    utente('Segreteria Guarda', 'x' * 12, {'segreteria': 'guarda'}),
                    utente('Segreteria Modifica', 'x' * 12, {'segreteria': 'modifica', 'pazienti': 'guarda'}))
    sa = rete(ip='192.168.1.130')
    entra(sa, 'Solo Agenda', 'x' * 12)
    from flask import template_rendered
    contesti = []

    def preso(_app, template, context, **_):
        if template.name == 'appuntamento.html':
            contesti.append(context)
    template_rendered.connect(preso, A.app)
    try:
        t_solo = testo(chiedi(sa, 'GET', '/appuntamento/%d' % aid))
        t_pc = locale().get('/appuntamento/%d' % aid).get_data(as_text=True)
    finally:
        template_rendered.disconnect(preso, A.app)
    # anche quello che arriva al modello, non solo quello che il modello scrive (due protezioni)
    solo, pc = contesti
    assert solo['tariffe'] == '{}' and solo['messaggi'] is None and solo['documenti'] == [] and solo['checklist'] is None, \
        'al modello arrivano prezzi, messaggi, documenti o checklist di aree che l\'utente non ha'
    assert pc['tariffe'] != '{}' and pc['messaggi'] is not None, 'gemello: sul PC arrivano'
    assert 'data-tariffe' in t_pc
    tutto = rete(ip='192.168.1.131')
    entra(tutto, 'Tutto Provolo')
    t_tutto = testo(chiedi(tutto, 'GET', '/appuntamento/%d' % aid))
    for pezzo in ('id="importo"', 'id="incasso"', 'id="convenzione"', 'id="messaggi"', 'nella scheda del paziente'):
        assert pezzo in t_tutto, 'gemello: con tutte le aree c\'è %s' % pezzo
        assert pezzo not in t_solo, 'solo Agenda: c\'è %s' % pezzo
    assert 'medico:' not in t_solo and 'data-tariffe' not in t_solo, 'i prezzi dei tariffari a chi non ha la Cassa'
    # Cassa in «solo guardare»: si vede l'importo, non si salva e non si incassa
    aggiungi_utenti(utente('Cassa Guarda', 'x' * 12, {'agenda': 'modifica', 'cassa': 'guarda'}))
    cg = rete(ip='192.168.1.132')
    entra(cg, 'Cassa Guarda', 'x' * 12)
    t = testo(chiedi(cg, 'GET', '/appuntamento/%d' % aid))
    assert 'id="importo"' in t and 'readonly' in t and 'Registra il pagamento' not in t, 'Cassa in solo guardare'
    # il numero dei «da confermare» nel menu: solo a chi ha la Segreteria
    s = A.Sessione()
    s.add(Appunto(testo='Richiamare Fintini per la visita', giorno=date.today() + timedelta(days=3)))
    s.commit()
    s.close()
    assert 'da confermare"' in locale().get('/oggi').get_data(as_text=True), 'gemello: sul PC il numero c\'è'
    assert 'da confermare"' in t_tutto or 'da confermare"' in testo(chiedi(tutto, 'GET', '/oggi'))
    assert 'da confermare"' not in testo(chiedi(sa, 'GET', '/oggi')), 'il numero dei da confermare a chi non ha la Segreteria'
    # le notifiche: ognuna con la sua area
    sid = 1
    sul_pc = locale().get('/notifiche.json?struttura=%d' % sid).json
    assert any(n['chiave'].startswith('cosa-') for n in sul_pc), 'gemello: sul PC la cosa da fare c\'è'
    assert not [n for n in chiedi(sa, 'GET', '/notifiche.json?struttura=%d' % sid).json
                if n['chiave'].startswith('cosa-')], 'la cosa da fare (Segreteria) a chi ha solo l\'Agenda'
    sg = rete(ip='192.168.1.133')
    entra(sg, 'Segreteria Guarda', 'x' * 12)
    lista = [n for n in chiedi(sg, 'GET', '/notifiche.json?struttura=%d' % sid).json if n['chiave'].startswith('cosa-')]
    assert lista and not lista[0]['azioni'], 'i bottoni «Fatto» a chi può solo guardare'
    assert lista[0]['link'].endswith('/cose-da-fare'), 'senza Pazienti il collegamento va alla pagina della Segreteria'
    sm = rete(ip='192.168.1.134')
    entra(sm, 'Segreteria Modifica', 'x' * 12)
    lista = [n for n in chiedi(sm, 'GET', '/notifiche.json?struttura=%d' % sid).json if n['chiave'].startswith('cosa-')]
    assert lista and lista[0]['azioni'] and '/pazienti/' in lista[0]['link'], 'gemello: con «modificare» i bottoni ci sono'
    # ogni chiave di notifica scritta nei sorgenti ha la sua area (una nuova senza area: non si mostrerebbe mai)
    cartella = os.path.dirname(os.path.abspath(__file__))
    chiavi = set()
    for n in os.listdir(cartella):
        if n.endswith('.py') and not n.startswith(('prove', 'campagna')):
            with open(os.path.join(cartella, n), encoding='utf-8') as f:
                chiavi |= set(re.findall(r"'chiave': '([a-z-]+?)(?:%|')", f.read()))
    senza = sorted(k for k in chiavi if accessi.area_notifica(k) == accessi.SISTEMA
                   and not k.startswith(('backup', 'autoripara', 'aggiornament')))
    assert len(chiavi) >= 12 and not senza, 'notifiche senza area: %s (trovate %s)' % (senza, sorted(chiavi))
    assert accessi.area_notifica('nuova-cosa-1') == accessi.SISTEMA, 'gemello: una chiave nuova non ha area'
    # la ricerca rapida
    assert locale().get('/cerca-tutto.json?q=Esempietti').json['pazienti'], 'gemello: sul PC il paziente si trova'
    assert chiedi(tutto, 'GET', '/cerca-tutto.json?q=Esempietti').json['pazienti'], 'gemello: con Pazienti si trova'
    r = chiedi(sa, 'GET', '/cerca-tutto.json?q=Esempietti')
    assert r.status_code == 200 and r.json['pazienti'] == [], r.json
    assert chiedi(sa, 'GET', '/pazienti/cerca?q=Esempietti').json, 'per prenotare la ricerca dei pazienti c\'è'
    # /sposta/avvisi: dalla rete solo gli appuntamenti spostati da chi chiede
    t = testo(chiedi(tutto, 'GET', '/sposta/avvisi?ids=%d' % aid))
    assert 'Canarino' not in t, 'nomi e telefoni di appuntamenti scelti a mano nell\'indirizzo'
    assert 'Canarino' in locale().get('/sposta/avvisi?ids=%d' % aid).get_data(as_text=True), 'gemello: sul PC sì'
    s = A.Sessione()
    a = s.get(Appuntamento, aid)
    medico, dopo = a.operatore_id, a.inizio + timedelta(days=1)
    stanza_id, oid = a.risorsa_id, a.operatore_id
    s.close()
    valore = '%s|%d|%d' % (dopo.strftime('%Y-%m-%dT%H:%M'), stanza_id, oid)
    r = chiedi(tutto, 'POST', '/sposta', data={'medico': medico, 'dal': a.inizio.date().isoformat(),
                                               'al': a.inizio.date().isoformat(), 'modo': 'dopo', 'scelti': str(aid),
                                               'p_%d' % aid: valore})
    assert r.status_code == 302 and 'ids=%d' % aid in r.headers['Location'], (r.status_code, r.headers.get('Location'))
    assert 'Canarino' in testo(chiedi(tutto, 'GET', r.headers['Location'])), 'chi ha spostato non vede chi avvisare'
    assert 'Canarino' not in testo(chiedi(sa, 'GET', r.headers['Location'])), 'un altro utente vede chi avvisare'
    return 'prezzi, incasso, messaggi, documenti, notifiche, chi avvisare e ricerca rapida: solo con le loro aree'


def o_solo_guardare_non_scrive_mai():
    """Chi ha tutto in «solo guardare» gira le pagine GET e i loro collegamenti: nessuna scrittura nel database
    (la pagina delle novità dalla rete non segna «vista»)."""
    scritture = []
    motore = A.Sessione.motore
    percorso_attuale = ['']

    def guarda(conn, cursor, statement, params, context, executemany):
        if statement.lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
            scritture.append((percorso_attuale[0], statement.split('\n')[0][:80]))
    imposta(novita_vista='')
    g = rete(ip='192.168.1.90')
    entra(g, 'Guarda Fittizi')
    event.listen(motore, 'before_cursor_execute', guarda)
    try:
        coda = [r.rule for r in A.app.url_map.iter_rules() if 'GET' in r.methods and not r.arguments
                and r.endpoint != 'static']
        visti, per_tipo = set(), {}
        while coda:
            u = coda.pop(0)
            tipo = re.sub(r'\d+', 'N', u.split('?')[0])
            if u in visti or per_tipo.get(tipo, 0) >= 2:
                continue
            visti.add(u)
            per_tipo[tipo] = per_tipo.get(tipo, 0) + 1
            percorso_attuale[0] = u
            r = chiedi(g, 'GET', u)
            if r.mimetype == 'text/html':
                coda += [h.replace('&amp;', '&') for h in re.findall(r'href="(/[^"#]*)"', testo(r))
                         if not h.startswith(('/static/', '/esci'))]
    finally:
        event.remove(motore, 'before_cursor_execute', guarda)
    assert not scritture, scritture[:5]
    assert leggi('novita_vista') == '', 'la pagina delle novità dalla rete ha segnato «vista»'
    locale().get('/aiuto/novita')
    assert leggi('novita_vista') != '', 'gemello: dal PC la pagina delle novità segna «vista»'
    return '%d pagine guardate dalla rete: nessuna scrittura' % len(visti)


def p_chiave():
    """Correzione 8: la chiave è casuale già all'avvio del modulo, quella della cartella dei dati si rifà se è corta
    o fissa, e la presa della rete non si accende con una chiave corta o fissa."""
    assert isinstance(A.app.secret_key, bytes) and len(A.app.secret_key) >= 32 and A.app.secret_key != b'gestionale-locale'
    cartella = os.path.join(PROVVISORIA, 'chiave')
    os.makedirs(cartella)
    k1 = accessi.chiave_sessione(cartella)
    assert len(k1) == 32 and accessi.chiave_sessione(cartella) == k1, 'la chiave non resta la stessa'
    for cattiva in (b'gestionale-locale', b'corta'):
        with open(os.path.join(cartella, 'chiave-sessione'), 'wb') as f:
            f.write(cattiva)
        k = accessi.chiave_sessione(cartella)
        assert len(k) == 32 and k != cattiva and k != k1
    vera = A.app.secret_key
    try:
        for cattiva in ('gestionale-locale', b'gestionale-locale', 'x' * 10):
            A.app.secret_key = cattiva
            assert not accessi.chiave_buona(cattiva)
            assert not accessi.ascolto.accendi(A.app, porta_libera()), 'acceso con la chiave %r' % cattiva
            assert 'chiave' in accessi.ascolto.errore and not accessi.ascolto.acceso()
    finally:
        A.app.secret_key = vera
    porta = porta_libera()
    assert accessi.ascolto.accendi(A.app, porta), 'gemello: con la chiave buona si accende: ' + accessi.ascolto.errore
    accessi.ascolto.spegni()
    return 'chiave casuale; corta o fissa rifatta; la presa della rete non parte con una chiave cattiva'


def porta_libera():
    """Una porta libera su tutte le schede (la presa della rete si lega a 0.0.0.0), fuori da quelle del programma vero
    e della prova (5000-5089)."""
    while True:
        with socket.socket() as x:
            x.bind(('0.0.0.0', 0))
            p = x.getsockname()[1]
        if not 5000 <= p < 5090:
            return p


def get_vero(porta, percorso, intestazioni=None):
    h = http.client.HTTPConnection('127.0.0.1', porta, timeout=10)
    try:
        h.request('GET', percorso, headers=dict({'Host': '127.0.0.1:%d' % porta}, **(intestazioni or {})))
        r = h.getresponse()
        return r.status, r.getheader('Location') or '', r.read()
    finally:
        h.close()


def q_prese_vere():
    """Il server principale vero (waitress) lascia arrivare X-Forwarded-For: un portiere sullo stesso PC è dalla
    rete (correzione 1); l'ascolto della rete acceso, spento, riacceso, su una porta occupata, cambiato di porta;
    applica() lo accende e lo spegne come dicono le impostazioni."""
    principale, porta_p = A.crea_server(porta_libera())
    filo = threading.Thread(target=principale.run, daemon=True)
    filo.start()
    porta_r = porta_libera()
    try:
        assert get_vero(porta_p, '/oggi')[0] == 200, 'gemello: dal PC la pagina si apre'
        for k, v in (('X-Forwarded-For', '192.168.1.40'), ('Forwarded', 'for=192.168.1.40'), ('X-Real-IP', '192.168.1.40')):
            stato, dove_va, _ = get_vero(porta_p, '/oggi', {k: v})
            assert stato == 302 and '/accesso' in dove_va, ('il portiere (%s) entra come il PC principale' % k, stato)
        assert accessi.ascolto.accendi(A.app, porta_r), accessi.ascolto.errore
        assert accessi.ascolto.acceso()
        stato, dove_va, _ = get_vero(porta_r, '/oggi')
        assert stato == 302 and '/accesso' in dove_va, (stato, dove_va)
        assert get_vero(porta_r, '/salute')[0] == 403
        stato, _, corpo = get_vero(porta_p, '/salute')
        assert stato == 200 and json.loads(corpo)['programma'], stato
        assert not [p for _, p in A._in_corso.values() if p], 'richieste rimaste segnate'
        accessi.ascolto.spegni()
        assert not accessi.ascolto.acceso()
        try:
            get_vero(porta_r, '/oggi')
            raise AssertionError('la porta della rete risponde ancora dopo lo spegnimento')
        except (ConnectionRefusedError, ConnectionResetError):
            pass
        assert get_vero(porta_p, '/salute')[0] == 200, 'spegnere la rete non tocca il PC principale'
        assert accessi.ascolto.accendi(A.app, porta_r), 'riacceso sulla stessa porta: ' + accessi.ascolto.errore
        assert get_vero(porta_r, '/oggi')[0] == 302
        with socket.socket() as occupata:
            occupata.bind(('0.0.0.0', 0))
            occupata.listen(1)
            assert not accessi.ascolto.accendi(A.app, occupata.getsockname()[1])
            # revisione del 22/11: resta in ascolto la porta di prima, quindi l'errore va solo nel messaggio della volta,
            # non nel riquadro rosso della pagina (che restava per sempre sotto «Acceso»). Il gemello è all'avvio, sotto
            assert 'già usata' in accessi.ascolto.errore_cambio and not accessi.ascolto.errore, \
                (accessi.ascolto.errore_cambio, accessi.ascolto.errore)
        assert accessi.ascolto.acceso() and get_vero(porta_r, '/oggi')[0] == 302, 'spento l\'ascolto di prima'
        porta_2 = porta_libera()
        assert accessi.ascolto.accendi(A.app, porta_2), accessi.ascolto.errore
        assert get_vero(porta_2, '/oggi')[0] == 302
        try:
            get_vero(porta_r, '/oggi')
            raise AssertionError('la porta di prima risponde ancora')
        except (ConnectionRefusedError, ConnectionResetError):
            pass
        # all'avvio con la porta ancora occupata (il programma di prima si sta chiudendo): riprova da solo
        accessi.ascolto.spegni()
        occupata = socket.socket()
        occupata.bind(('0.0.0.0', 0))
        occupata.listen(1)
        porta_3 = occupata.getsockname()[1]
        imposta(rete_accesa='1', rete_porta=str(porta_3))
        cartella = os.path.join(PROVVISORIA, 'avvio')
        os.makedirs(cartella)
        accessi.all_avvio(A.app, A.Sessione, cartella, prove=40, pausa=0.1)
        assert not accessi.ascolto.acceso() and 'già usata' in accessi.ascolto.errore
        occupata.close()
        for _ in range(60):
            if accessi.ascolto.acceso():
                break
            time.sleep(0.1)
        assert accessi.ascolto.acceso() and accessi.ascolto.porta == porta_3, 'all\'avvio non ha riprovato'
        assert get_vero(porta_3, '/oggi')[0] == 302
        accessi.prepara_registro(PROVVISORIA)
        accessi.sessioni.carica(PROVVISORIA)
        # applica: come le impostazioni (dopo un ripristino o una riparazione)
        imposta(rete_accesa='')
        assert accessi.applica(A.app, A.Sessione) and not accessi.ascolto.acceso()
        imposta(rete_accesa='1', rete_porta=str(porta_r))
        assert accessi.applica(A.app, A.Sessione) and accessi.ascolto.acceso() and accessi.ascolto.porta == porta_r
    finally:
        accessi.ascolto.spegni()
        from waitress import wasyncore
        principale.trigger.pull_trigger(lambda: wasyncore.close_all(principale._map))
        filo.join(5)
    return 'portiere vero = dalla rete; ascolto acceso, spento, riacceso, porta occupata, cambiata; applica'


def r_pagina_degli_accessi():
    """La pagina dal PC principale: aree salvate (Sistema e valori strani ignorati), porta controllata e salvata solo
    se l'ascolto parte, utente tolto."""
    loc = locale()
    u = accessi.trova(utenti_salvati(), 'Anna Esempietti')
    loc.post('/configura/accessi', data={'azione': 'salva', 'utente': u['id'], 'attivo': '1', 'area_cassa': 'guarda',
                                         'area_sistema': 'modifica', 'area_agenda': 'altro'})
    assert accessi.trova(utenti_salvati(), 'Anna Esempietti')['aree'] == {'cassa': 'guarda'}
    c = rete(ip='192.168.1.140')
    r = entra(c, 'Anna Esempietti')
    assert r.status_code == 302 and r.headers['Location'].endswith('/cassa/listino'), r.headers.get('Location')
    assert chiedi(c, 'GET', '/').headers['Location'].endswith('/cassa/listino'), 'la radice porta alla prima area'
    testo_ = loc.get('/configura/accessi').get_data(as_text=True)
    assert 'Anna Esempietti' in testo_ and 'in chiaro' in testo_ and ':5080/' in testo_ and 'entrato' in testo_
    for cattiva in ('5000', '5003', '80', 'abc', '99999'):
        loc.post('/configura/accessi', data={'azione': 'rete', 'accesa': '1', 'porta': cattiva})
        assert leggi('rete_porta') == '5080', 'porta accettata: %s' % cattiva
    # porta salvata solo se l'ascolto parte davvero
    A.app.config['TESTING'] = False
    try:
        with socket.socket() as occupata:
            occupata.bind(('0.0.0.0', 0))
            occupata.listen(1)
            p = occupata.getsockname()[1]
            loc.post('/configura/accessi', data={'azione': 'rete', 'accesa': '1', 'porta': str(p)})
            assert leggi('rete_porta') == '5080' and not accessi.ascolto.acceso(), 'porta occupata salvata'
        p = porta_libera()
        loc.post('/configura/accessi', data={'azione': 'rete', 'accesa': '1', 'porta': str(p), 'schermo_libero': '1'})
        assert leggi('rete_porta') == str(p) and accessi.ascolto.acceso() and leggi('rete_schermo_libero') == '1'
        loc.post('/configura/accessi', data={'azione': 'rete', 'porta': str(p)})
        assert leggi('rete_accesa') == '' and not accessi.ascolto.acceso()
    finally:
        A.app.config['TESTING'] = True
        accessi.ascolto.spegni()
    loc.post('/configura/accessi', data={'azione': 'elimina', 'utente': u['id']})
    assert accessi.trova(utenti_salvati(), 'Anna Esempietti') is None
    imposta(rete_accesa='1', rete_porta='5080', rete_nomi='192.168.1.10')
    r = entra(rete(ip='192.168.1.141'), 'Anna Esempietti')
    assert r.status_code == 200 and accessi.MESSAGGIO_SBAGLIATO in testo(r), ('l\'utente tolto entra ancora', r.status_code,
                                                                             r.headers.get('Location'))
    return 'aree (senza Sistema), porte cattive rifiutate, porta salvata solo con l\'ascolto partito, utente tolto'


def s_rifiuto_in_italiano():
    """Area negata: 403 con la pagina italiana, il nome dell'utente, «Torna alle pagine disponibili» ed «Esci»;
    «solo guardare»: 403 «Solo guardare» e niente salvato; JSON: 403 in JSON."""
    c = rete(ip='192.168.1.150')
    entra(c, 'Anna Esempietti')
    for percorso in ('/cassa/%s' % OGGI, '/personale/turni', '/statistiche', '/dove-si-fa/', '/invii', '/conferme',
                     '/sala/%s' % OGGI, '/ambulatori/riepilogo', '/anagrafiche'):
        r = chiedi(c, 'GET', percorso)
        t = testo(r)
        assert rifiutata(r) and 'Anna Esempietti' in t and 'Torna alle pagine disponibili' in t and '/esci' in t, percorso
    r = chiedi(c, 'GET', '/ambulatori/riepilogo.json')
    assert r.status_code == 403 and r.mimetype == 'application/json' and r.json['errore']
    prima = conta(Paziente)
    r = chiedi(c, 'POST', '/pazienti/nuovo', data={'cognome': 'Inventatissimo', 'nome': 'Dalla Rete'})
    assert r.status_code == 403 and 'Solo guardare' in testo(r) and conta(Paziente) == prima
    assert chiedi(c, 'GET', '/pazienti').status_code == 200, 'gemello: guardare sì'
    # la barra di chi è entrato da un altro PC: nome, la sua password, Esci
    t = testo(chiedi(c, 'GET', '/oggi'))
    assert entrato_come(t, 'Anna Esempietti') and '/accesso/password' in t
    assert 'Entrato da un altro PC' not in locale().get('/oggi').get_data(as_text=True), 'gemello: sul PC no'
    return '9 aree negate con la pagina italiana; solo guardare: 403 e niente salvato; la barra con Esci'


# ======================================================= la presa della rete, la pagina, il programma vero
def t_limiti_dei_server():
    """Correzione 2: il server del PC principale (app.crea_server) e quello della rete con i limiti di waitress: moduli
    fino a 13 MB (oltre: 413 da waitress, prima ancora di Flask); sul PC 20 collegamenti e 30 secondi di silenzio, sulla
    rete 100 collegamenti (al massimo 8 per PC: z_collegamenti_per_pc) e 10 secondi; le intestazioni dei portieri
    restano (correzione 1). Gemello: un modulo piccolo arriva al programma."""
    def manda(porta, lunghezza):
        with socket.create_connection(('127.0.0.1', porta), timeout=10) as x:
            x.sendall(('POST /note-giorno HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nContent-Type: application/x-www-form-'
                       'urlencoded\r\nContent-Length: %d\r\nConnection: close\r\n\r\n' % (porta, lunghezza)).encode())
            if lunghezza < 100:
                x.sendall(b'x' * lunghezza)
            return int(x.recv(200).split()[1])
    principale, porta_p = A.crea_server(porta_libera())
    filo = threading.Thread(target=principale.run, daemon=True)
    filo.start()
    try:
        assert accessi.ascolto.accendi(A.app, porta_libera()), accessi.ascolto.errore
        for nome, server, porta, voluti in (('PC principale', principale, porta_p, (13 * 1024 * 1024, 20, 30, False)),
                                            ('rete', accessi.ascolto.server, accessi.ascolto.porta,
                                             (13 * 1024 * 1024, 100, 10, False))):
            adj = server.adj
            valori = (adj.max_request_body_size, adj.connection_limit, adj.channel_timeout,
                      adj.clear_untrusted_proxy_headers)
            assert valori == voluti, (nome, valori)
            assert manda(porta, 14 * 1024 * 1024) == 413, '%s: un modulo di 14 MB non si ferma' % nome
            assert manda(porta, 10) != 413, 'gemello (%s): un modulo piccolo arriva al programma' % nome
    finally:
        accessi.ascolto.spegni()
        from waitress import wasyncore
        principale.trigger.pull_trigger(lambda: wasyncore.close_all(principale._map))
        filo.join(5)
    return 'limiti dei due server; 14 MB: 413 da waitress; un modulo piccolo passa'


def u_email_e_whatsapp_nel_sistema():
    """Correzione 3: la casella email e il token di WhatsApp di /invii sono Sistema. Dalla rete, anche con «Email e
    WhatsApp» da modificare, i loro moduli (salva, prova, registra il numero) rispondono 403 e niente cambia; la
    pagina non mostra le due parti. Gemelli: dalla rete i promemoria si salvano; dal PC le due parti ci sono e si
    salvano."""
    imposta(email_server='mail.example.it', email_utente='accettazione@example.it', email_porta='465',
            email_sicurezza='ssl', email_password=invii.proteggi('Password-di-prova'), wa_token=invii.proteggi('token-finto'),
            wa_numero_id='123456789', wa_modello='promemoria_appuntamento')
    chiavi = ('email_server', 'email_utente', 'email_porta', 'email_sicurezza', 'email_password', 'wa_token',
              'wa_numero_id', 'wa_registrato', 'wa_modello')
    prima, invii_prima = {k: leggi(k) for k in chiavi}, conta(Invio)
    c = rete(ip='192.168.1.160')
    entra(c, 'Tutto Provolo')
    for dati in ({'azione': 'salva', 'sezione': 'email', 'email_utente': 'altro@example.org', 'email_tipo': 'altro',
                  'email_server': 'smtp.cattivo.example', 'email_porta': '25', 'email_sicurezza': 'nessuna',
                  'email_attiva': '1'},
                 {'azione': 'salva', 'sezione': 'whatsapp', 'wa_numero_id': '999', 'wa_token': 'altro-token',
                  'wa_modello': 'altro', 'wa_lingua': 'it', 'wa_versione': 'v22.0'},
                 {'azione': 'prova_email', 'a': 'chiunque@example.org'},
                 {'azione': 'prova_whatsapp', 'a': '3330000000'},
                 {'azione': 'registra_whatsapp', 'pin': '123456'}):
        r = chiedi(c, 'POST', '/invii', data=dati)
        assert r.status_code == 403 and 'Solo dal PC della segreteria' in testo(r), (dati['azione'], r.status_code)
    assert {k: leggi(k) for k in chiavi} == prima and conta(Invio) == invii_prima, 'dalla rete la casella è cambiata'
    r = chiedi(c, 'GET', '/invii')
    t = testo(r)
    assert r.status_code == 200 and 'si configura solo dal PC della segreteria' in t, r.status_code
    for parte in ('id="modulo-email"', 'name="email_server"', 'name="wa_token"', 'name="pin"', 'mail.example.it',
                  'value="prova_email"', 'value="prova_whatsapp"'):
        assert parte not in t, 'dalla rete la pagina mostra %s' % parte
    r = chiedi(c, 'POST', '/invii', data={'azione': 'salva', 'sezione': 'promemoria', 'promemoria_attivo': '1',
                                         'promemoria_ora': '09:35'})
    assert r.status_code == 302 and leggi('promemoria_ora') == '09:35', 'gemello: dalla rete i promemoria si salvano'
    loc = locale()
    t = loc.get('/invii').get_data(as_text=True)
    assert all(parte in t for parte in ('id="modulo-email"', 'name="email_server"', 'name="wa_token"', 'name="pin"',
                                        'mail.example.it')) and 'si configura solo dal PC' not in t, \
        'gemello: dal PC le due parti ci sono'
    r = chiedi(loc, 'POST', '/invii', data={'azione': 'salva', 'sezione': 'whatsapp', 'wa_numero_id': '123456789',
                                            'wa_modello': 'modello_dal_pc', 'wa_lingua': 'it', 'wa_versione': 'v22.0'})
    assert r.status_code == 302 and leggi('wa_modello') == 'modello_dal_pc', 'gemello: dal PC WhatsApp si salva'
    assert leggi('wa_token') == prima['wa_token'], 'dal PC, senza token nuovo, quello salvato resta'
    return '5 moduli della casella e di WhatsApp: 403 dalla rete, niente cambiato, parti nascoste; promemoria sì'


def v_password_email_tolta():
    """Correzione 3, seconda parte: la password salvata della casella vale solo per server, porta, sicurezza e nome
    utente per cui è stata scritta. Cambiato uno di questi senza riscriverla, si toglie (e la pagina lo dice). Gemelli:
    la stessa casella salvata di nuovo (anche con il server in maiuscolo) la tiene; riscritta, vale quella nuova."""
    loc = locale()
    base = {'azione': 'salva', 'sezione': 'email', 'email_tipo': 'altro', 'email_utente': 'accettazione@example.it',
            'email_server': 'mail.example.it', 'email_porta': '465', 'email_sicurezza': 'ssl', 'email_accesso': '',
            'email_attiva': '1', 'email_mittente': ''}

    def salva(**cambi):
        r = chiedi(loc, 'POST', '/invii', data=dict(base, **cambi))
        assert r.status_code == 302, r.status_code
        with loc.session_transaction(base_url=PC) as sess:
            messaggi = ' '.join(m for _, m in sess.pop('_flashes', []))
        salvata = leggi('email_password')
        return (invii.svela(salvata) if salvata else ''), messaggi
    assert salva(email_password='Password-di-prova')[0] == 'Password-di-prova'
    password, messaggi = salva()
    assert password == 'Password-di-prova' and 'tolta' not in messaggi, 'gemello: la stessa casella la tiene'
    assert salva(email_server='MAIL.EXAMPLE.IT')[0] == 'Password-di-prova', 'gemello: le maiuscole non contano'
    cambiati = []
    for campo, valore in (('email_server', 'smtp.cattivo.example'), ('email_porta', '587'),
                          ('email_sicurezza', 'nessuna'), ('email_utente', 'altro@example.it'),
                          ('email_accesso', 'utente-diverso')):
        assert salva(email_password='Password-di-prova')[0] == 'Password-di-prova'
        password, messaggi = salva(**{campo: valore})
        assert password == '' and 'password salvata è stata tolta' in messaggi, (campo, password, messaggi)
        cambiati.append(campo)
    password, messaggi = salva(email_server='smtp.nuovo.example', email_password='Altra-password')
    assert password == 'Altra-password' and 'tolta' not in messaggi, 'gemello: riscritta, vale quella nuova'
    assert not invii.casella_cambiata({'email_server': 'Mail.Example.it.', 'email_porta': '465', 'email_sicurezza': 'ssl',
                                       'email_utente': 'A@example.it', 'email_accesso': ''},
                                      'mail.example.it', '465', 'ssl', 'a@example.it', '')
    return 'tolta cambiando %s; tenuta con la stessa casella; riscritta vale la nuova' % ', '.join(cambiati)


def w_indirizzi_in_numeri():
    """Dagli altri PC il programma si apre anche con l'indirizzo in numeri, qualsiasi (con il DHCP cambia, e una
    seconda scheda di rete ne ha un altro), ma solo sulla porta della rete; un nome che non è del PC no (DNS
    rebinding). I nomi del PC si rifanno ogni minuto."""
    c = rete(ip='192.168.1.170')
    for host in ('http://10.0.0.99:5080', 'http://192.168.77.77:5080', 'http://172.16.5.4:5080'):
        r = chiedi(c, 'GET', '/accesso', base_url=host)
        assert r.status_code == 200, (host, r.status_code)
    for host in ('http://192.168.77.77:8080', 'http://999.1.1.1:5080', 'http://192.168.1.10.cattivo.example:5080',
                 'http://cattivo.example:5080', 'http://1.2.3.4.nip.io:5080'):
        r = chiedi(c, 'GET', '/accesso', base_url=host)
        assert r.status_code == 400, (host, r.status_code)
    vero = accessi.socket.getaddrinfo
    vecchi = dict(accessi._nomi_del_pc)
    try:
        accessi.socket.getaddrinfo = lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.168.50.60', 0))]
        assert 'http://192.168.50.60:5080/' not in accessi.indirizzi_da_usare(5080) or vecchi['quando'] < 0, \
            'gemello: entro il minuto i nomi restano quelli di prima'
        accessi._nomi_del_pc['quando'] = time.monotonic() - 61
        assert 'http://192.168.50.60:5080/' in accessi.indirizzi_da_usare(5080), 'dopo un minuto i nomi non si rifanno'
    finally:
        accessi.socket.getaddrinfo = vero
        accessi._nomi_del_pc.update(vecchi)
    return 'indirizzi in numeri sulla porta della rete: sì; altra porta, numeri sbagliati o nomi altrui: 400'


def x_pagina_e_accesso():
    """La pagina «Aree e accessi» dal PC: il firewall (reti private sì, pubbliche no, il comando netsh con la porta),
    il collegamento in chiaro, gli indirizzi con i numeri del PC, Caddy puntato alla porta della rete, il registro
    degli ultimi 7 giorni letto dai file (non quello più vecchio), un utente nuovo con le aree scelte nello stesso
    modulo. La pagina di accesso: il nome della struttura, nessun dato dei pazienti. Il rifiuto del Sistema dice che
    si fa solo dal PC della segreteria."""
    loc = locale()
    vecchi = dict(accessi._nomi_del_pc)
    accessi._nomi_del_pc.update(quando=time.monotonic(), nomi=['192.168.1.10', 'pc-segreteria'])
    try:
        imposta(rete_porta='5091')
        t = loc.get('/configura/accessi').get_data(as_text=True)
    finally:
        accessi._nomi_del_pc.update(vecchi)
        imposta(rete_porta='5080')
    for parola in ('Reti private', 'Reti pubbliche', 'Consenti accesso', 'netsh advfirewall firewall add rule',
                   'localport=5091 profile=private', 'netsh advfirewall firewall delete rule', 'in chiaro', 'https',
                   'http://192.168.1.10:5091/', 'riepilogo-live?schermo=1', '127.0.0.1:5091', 'Privata'):
        assert parola in t, 'manca nella pagina: %s' % parola
    # il registro dai file: oggi, 3 giorni fa (si vedono, prima il più recente), 10 giorni fa (no); in una cartella
    # sua (quella delle altre prove ha già centinaia di righe di oggi, e la pagina ne mostra 150)
    cartella = accessi.prepara_registro(os.path.join(PROVVISORIA, 'registro-della-pagina'))
    os.makedirs(cartella, exist_ok=True)
    for giorni in (0, 3, 10):
        g = (date.today() - timedelta(days=giorni)).isoformat()
        with open(os.path.join(cartella, 'accessi-%s.log' % g), 'a', encoding='utf-8') as f:
            f.write('%s 10:11:12,345 WARNING riga di prova %d giorni | utente=Registro Fintini | da=192.168.1.%d\n'
                    % (g, giorni, 200 + giorni))
            if giorni == 0:
                f.write('%s 10:12:13,456 INFO riga dopo di oggi | utente=Registro Fintini | da=192.168.1.210\n' % g)
    t = loc.get('/configura/accessi').get_data(as_text=True)
    assert 'riga di prova 0 giorni' in t and 'riga di prova 3 giorni' in t and '192.168.1.203' in t, 'registro dai file'
    assert t.index('riga dopo di oggi') < t.index('riga di prova 0 giorni') < t.index('riga di prova 3 giorni'), \
        'prima i più recenti, anche nello stesso giorno'
    assert 'riga di prova 10 giorni' not in t, 'gemello: una riga di 10 giorni fa non si mostra'
    # un nome con « | » non sposta i campi della riga
    with A.app.test_request_context('/', environ_base={'REMOTE_ADDR': '192.168.1.99', 'gestionale.presa_rete': True}):
        accessi.annota('riga col nome strano', 'Finto | da=6.6.6.6 | utente=x')
    riga = next(r for r in accessi.ultimi_accessi() if 'riga col nome strano' in r[3])
    assert riga[1:4] == ('Finto / da=6.6.6.6 / utente=x', '192.168.1.99', 'riga col nome strano'), riga
    # un utente nuovo con le aree scelte nello stesso modulo (il Sistema scritto a mano non vale)
    loc.post('/configura/accessi', data={'azione': 'nuovo', 'nome': 'Nuovo Esempio', 'password': 'tavolo rosso in giardino',
                                         'area_agenda': 'modifica', 'area_cassa': 'guarda', 'area_sistema': 'modifica',
                                         'area_turni': 'no'})
    u = accessi.trova(utenti_salvati(), 'Nuovo Esempio')
    assert u and u['aree'] == {'agenda': 'modifica', 'cassa': 'guarda'} and u['cambia'], u
    accessi.prepara_registro(PROVVISORIA)
    # la pagina di accesso: il nome della struttura, nessun paziente
    s = A.Sessione()
    try:
        from modelli import Struttura
        struttura = s.scalars(select(Struttura.nome).order_by(Struttura.id)).first()
        pazienti_ = [p.etichetta for p in s.scalars(select(Paziente))]
    finally:
        s.close()
    t = testo(chiedi(rete(ip='192.168.1.180'), 'GET', '/accesso'))
    assert struttura and struttura.replace("'", '&#39;') in t, 'nome della struttura nella pagina di accesso'
    assert pazienti_ and not [n for n in pazienti_ if n in t], 'un paziente nella pagina di accesso'
    assert pazienti_[0] in loc.get('/pazienti').get_data(as_text=True), 'gemello: dal PC i pazienti si vedono'
    c = rete(ip='192.168.1.181')
    entra(c, 'Tutto Provolo')
    r = chiedi(c, 'GET', '/impostazioni')
    assert r.status_code == 403 and 'anche per chi dagli altri PC ha tutte le parti' in testo(r), r.status_code
    r = chiedi(c, 'GET', '/pazienti')
    assert r.status_code == 200, 'gemello: le parti date si aprono'
    return 'firewall, in chiaro, indirizzi, Caddy, registro di 7 giorni dai file, utente nuovo con le aree; accesso pulito'


# --------------------------------------------------------------- il programma vero, con le prese vere
AVVIO_VERO = r"""
import sys
sys.argv = ['app.py', '--avvio-automatico']            # niente browser
sys.path.insert(0, %(cartella)r)
import autoripara
autoripara.PORTE_DI_RISERVA = ()
import aggiornamenti
aggiornamenti.INDIRIZZO_PREDEFINITO = ''               # nessuna prova va su internet
import accessi
accessi.PAUSA_AVVIO = 0.3                              # all'avvio, con la porta della rete occupata, si riprova subito
# app.py gira come «__main__», come nell'eseguibile e con «python app.py» (revisione del 22/11, grave: con «import app»
# le prove non vedevano la seconda copia di app.py caricata dal primo «from app import» di accessi.py)
import os, runpy
runpy.run_path(os.path.join(%(cartella)r, 'app.py'), run_name='__main__')
"""


def indirizzo_di_un_altro_pc():
    """Un indirizzo IPv4 di questo PC fuori da 127.*: una richiesta che parte da lì arriva al programma come da un
    altro PC della rete (REMOTE_ADDR non di loopback). Prima quelli che il PC conosce per nome (su Windows ci sono
    tutti), poi la scheda che il sistema userebbe per uscire (UDP: nessun pacchetto parte)."""
    for n in accessi.nomi_del_pc():
        if accessi.IPV4.fullmatch(n):
            return n
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as u:
            u.connect(('192.0.2.1', 9))
            ip = u.getsockname()[0]
        return ip if ip and not ip.startswith(('127.', '0.')) else None
    except OSError:
        return None


class Navigatore:
    """Un browser minimo sulle prese vere: tiene i cookie, manda l'Origin con i moduli, parte dall'indirizzo dato
    (source_address) e chiama il PC con l'indirizzo dato (Host)."""

    def __init__(self, porta, host='127.0.0.1', da=None):
        self.porta, self.host, self.da, self.cookie = porta, host, da, {}

    def chiedi(self, metodo, percorso, campi=None):
        h = http.client.HTTPConnection(self.host, self.porta, timeout=30,
                                       source_address=(self.da, 0) if self.da else None)
        base = 'http://%s:%d' % (self.host, self.porta)
        intestazioni = {'Host': '%s:%d' % (self.host, self.porta)}
        if self.cookie:
            intestazioni['Cookie'] = '; '.join('%s=%s' % kv for kv in self.cookie.items())
        corpo = urllib.parse.urlencode(campi).encode() if campi is not None else None
        if corpo is not None:
            intestazioni.update({'Origin': base, 'Content-Type': 'application/x-www-form-urlencoded'})
        try:
            h.request(metodo, percorso, body=corpo, headers=intestazioni)
            r = h.getresponse()
            for v in r.headers.get_all('Set-Cookie') or []:
                nome, _, resto = v.partition('=')
                valore = resto.split(';')[0]
                if not valore or 'Expires=Thu, 01 Jan 1970' in v:
                    self.cookie.pop(nome, None)
                else:
                    self.cookie[nome] = valore
            return r.status, r.getheader('Location') or '', r.read().decode('utf-8', 'replace')
        finally:
            h.close()


def chiusa(host, porta, da=None):
    """La porta non accetta collegamenti (rifiutato)."""
    try:
        socket.create_connection((host, porta), timeout=5, source_address=(da, 0) if da else None).close()
        return False
    except OSError:
        return True


def aspetta(condizione, secondi):
    fine = time.monotonic() + secondi
    while time.monotonic() < fine:
        try:
            if condizione():
                return True
        except OSError:
            pass
        time.sleep(0.2)
    return False


def avvia_vero(base, porta):
    p = subprocess.Popen([sys.executable, '-c', AVVIO_VERO % {'cartella': os.path.dirname(os.path.abspath(__file__))}],
                         env=dict(os.environ, LOCALAPPDATA=base, GESTIONALE_PORTA=str(porta)),
                         stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if not aspetta(lambda: p.poll() is not None or Navigatore(porta).chiedi('GET', '/salute')[0] == 200, 120) \
            or p.poll() is not None:
        p.kill()
        raise AssertionError('il programma vero non parte: %s' % (p.stderr.read()[-800:] if p.poll() is not None else ''))
    return p


def ferma(p):
    if p is not None and p.poll() is None:
        p.terminate()
        try:
            p.wait(20)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(10)


def y_come_l_eseguibile():
    """Revisione del 22/11 (grave): nell'eseguibile app.py gira come «__main__», e il primo «from app import» di accessi.py
    caricava una seconda copia di app.py, che rifaceva i collega() con Sessione=None: da lì TUTTO rispondeva 500, anche
    sul PC della segreteria. Partiva in tre casi: la pagina Aree e accessi; con la rete spenta una richiesta del portiere
    (X-Forwarded-For, il Modo schermo di Caddy); con la rete accesa una richiesta da un altro PC. Qui il programma vero
    come «__main__» (come l'eseguibile e «python app.py»), i tre casi, e dopo ognuno Oggi, Pazienti, Cassa e Impostazioni
    dal PC: 200. Il gemello è il primo giro di Oggi, prima di tutto."""
    altro_pc = indirizzo_di_un_altro_pc()
    assert altro_pc, 'nessun indirizzo di questo PC fuori da 127.*: non si può provare l\'arrivo da un altro PC'
    base = os.path.join(PROVVISORIA, 'come-eseguibile')
    os.makedirs(base)
    porta_p, porta_r = porta_libera(), porta_libera()
    p = avvia_vero(base, porta_p)
    pc = Navigatore(porta_p)
    giri = []

    def tutto_risponde(dopo):
        for percorso in ('/oggi', '/pazienti', '/cassa/listino', '/impostazioni'):
            s = pc.chiedi('GET', percorso)[0]
            assert s == 200, 'dopo %s: %s dal PC risponde %s' % (dopo, percorso, s)
        giri.append(dopo)
    try:
        tutto_risponde('l\'avvio')                                   # il gemello: prima di tutto
        s, _, t = pc.chiedi('GET', '/configura/accessi')
        assert s == 200 and 'Accesso dagli altri PC' in t, ('la pagina Aree e accessi', s)
        tutto_risponde('la pagina Aree e accessi')
        s = get_vero(porta_p, '/riepilogo-live?schermo=1', {'X-Forwarded-For': '192.168.1.50'})[0]
        assert s == 200, ('con la rete spenta il Modo schermo dietro il portiere', s)
        tutto_risponde('una richiesta del portiere con la rete spenta')
        for _ in range(3):
            pc.chiedi('POST', '/configura/accessi', {'azione': 'rete', 'accesa': '1', 'porta': str(porta_r)})
            if 'Acceso</b>, sulla porta %d' % porta_r in pc.chiedi('GET', '/configura/accessi')[2]:
                break
            porta_r = porta_libera()
        # revisione del 22/11 (firewall): la pagina dice se dagli altri PC arriva qualcosa. Una richiesta da questo PC
        # sulla porta della rete non conta (gemello); una dall'indirizzo di un altro PC sì
        assert Navigatore(porta_r).chiedi('GET', '/oggi')[0] == 302
        t = pc.chiedi('GET', '/configura/accessi')[2]
        assert 'Ancora nessuna richiesta da un altro PC' in t, 'la pagina non dice che dagli altri PC non arriva niente'
        s, dove_va, _ = Navigatore(porta_r, host=altro_pc, da=altro_pc).chiedi('GET', '/oggi')
        assert s == 302 and '/accesso' in dove_va, ('dall\'altro PC si chiede l\'accesso', s, dove_va)
        t = pc.chiedi('GET', '/configura/accessi')[2]
        assert 'Ultima richiesta da un altro PC' in t and 'da %s.' % altro_pc in t and 'Ancora nessuna' not in t, \
            'la pagina non dice l\'ultima richiesta da un altro PC'
        s, _, t = Navigatore(porta_r, host=altro_pc, da=altro_pc).chiedi('GET', '/accesso')
        assert s == 200 and 'name="password"' in t, ('la pagina di accesso dall\'altro PC', s)
        tutto_risponde('le richieste da un altro PC')
    finally:
        ferma(p)
    return 'app.py come «__main__»: Oggi, Pazienti, Cassa e Impostazioni 200 dopo %s' % ', '.join(giri)


def a_nessun_modulo_importa_app():
    """Revisione del 22/11 (grave): un modulo del programma che fa «from app import» o «import app» (anche dentro una
    funzione) carica nell'eseguibile una seconda copia di app.py, che gira come «__main__». Qui i moduli raggiunti dagli
    import di app.py, e lo stesso per prova.py (il programma di prova): nessuno importa il suo programma. Gemello: lo
    stesso controllo trova gli «import app» di prova.py e di campagna.py, che sono programmi a sé."""
    import ast
    cartella = os.path.dirname(os.path.abspath(__file__))
    locali = {n[:-3] for n in os.listdir(cartella) if n.endswith('.py')}

    def importati(nome):
        with open(os.path.join(cartella, nome + '.py'), encoding='utf-8') as f:
            albero = ast.parse(f.read())
        uscita = set()
        for nodo in ast.walk(albero):
            if isinstance(nodo, ast.Import):
                uscita.update(a.name.split('.')[0] for a in nodo.names)
            elif isinstance(nodo, ast.ImportFrom) and nodo.module and not nodo.level:
                uscita.add(nodo.module.split('.')[0])
        return uscita & locali

    def raggiunti(inizio):
        visti, da_fare = set(), [inizio]
        while da_fare:
            n = da_fare.pop()
            for m in importati(n) - visti - {inizio}:
                visti.add(m)
                da_fare.append(m)
        return visti
    for principale in ('app', 'prova'):
        moduli = raggiunti(principale)
        assert 'accessi' in moduli and 'viste' in moduli and len(moduli) > 25, (principale, sorted(moduli))
        colpevoli = sorted(m for m in moduli if principale in importati(m))
        assert not colpevoli, 'importano %s (nell\'eseguibile ne caricano una seconda copia): %s' % (principale, colpevoli)
    assert 'app' in importati('prova') and 'app' in importati('campagna'), 'gemello: il controllo non vede gli import'
    return '%d moduli del programma e %d della prova: nessuno importa il suo programma' % (
        len(raggiunti('app')), len(raggiunti('prova')))


def y_programma_vero():
    """Il programma vero (app.principale) in un processo a parte, con le sue prese: dalla pagina un utente con Agenda
    da modificare e Cassa da guardare e la rete accesa; dall'indirizzo non di loopback di questo PC (come un altro PC)
    la porta principale non si raggiunge, quella della rete sì, con l'accesso; il PC principale non vede mai la pagina
    di accesso; entra, cambia la password, salva in Agenda, non salva in Cassa, Pazienti e Sistema no; il registro dice
    chi era; spenta, la porta si chiude davvero. Poi il programma chiuso e riaperto con la porta della rete occupata:
    il PC principale parte lo stesso, la rete appena la porta si libera, e chi era entrato è ancora dentro."""
    altro_pc = indirizzo_di_un_altro_pc()
    assert altro_pc, 'nessun indirizzo di questo PC fuori da 127.*: non si può provare l\'arrivo da un altro PC'
    base = os.path.join(PROVVISORIA, 'programma-vero')
    os.makedirs(base)
    porta_p, porta_r = porta_libera(), porta_libera()
    oggi = date.today().isoformat()
    p = avvia_vero(base, porta_p)
    occupata = None
    try:
        pc = Navigatore(porta_p)
        s, _, t = pc.chiedi('GET', '/oggi')
        assert s == 200 and 'Entrato da un altro PC' not in t and 'name="password"' not in t, s
        s, dove_va, _ = pc.chiedi('GET', '/accesso')
        assert s == 302 and '/accesso' not in dove_va, 'sul PC principale la pagina di accesso non serve'
        pc.chiedi('POST', '/configura/accessi', {'azione': 'nuovo', 'nome': 'Rete Esempietti',
                                                  'password': 'pentola blu sul fuoco', 'area_agenda': 'modifica',
                                                  'area_cassa': 'guarda'})
        for _ in range(3):                       # una porta libera adesso può prenderla un altro programma subito dopo
            pc.chiedi('POST', '/configura/accessi', {'azione': 'rete', 'accesa': '1', 'porta': str(porta_r)})
            _, _, t = pc.chiedi('GET', '/configura/accessi')
            if 'già usata' not in t:
                break
            porta_r = porta_libera()
        assert 'Acceso</b>, sulla porta %d' % porta_r in t and 'Rete Esempietti' in t, 'rete non accesa dalla pagina'
        # dall'altro PC: la porta principale no (è solo su 127.0.0.1), quella della rete sì, con l'accesso
        assert chiusa(altro_pc, porta_p, da=altro_pc), 'la porta del PC principale si raggiunge da un altro PC'
        rete_ = Navigatore(porta_r, host=altro_pc, da=altro_pc)
        s, dove_va, _ = rete_.chiedi('GET', '/oggi')
        assert s == 302 and '/accesso' in dove_va, ('gemello: dalla porta della rete si chiede l\'accesso', s, dove_va)
        s, dove_va, _ = Navigatore(porta_r).chiedi('GET', '/oggi')
        assert s == 302 and '/accesso' in dove_va, 'anche da questo PC, sulla porta della rete, si entra con l\'accesso'
        assert pc.chiedi('GET', '/oggi')[0] == 200, 'il PC principale resta senza accesso'
        s, dove_va, _ = rete_.chiedi('POST', '/accesso', {'nome': 'Rete Esempietti', 'password': 'pentola blu sul fuoco'})
        assert s == 302 and dove_va.endswith('/accesso/password'), ('primo accesso', s, dove_va)
        s, dove_va, _ = rete_.chiedi('POST', '/accesso/password', {'attuale': 'pentola blu sul fuoco',
                                                                   'nuova': 'barca verde nel lago',
                                                                   'ancora': 'barca verde nel lago'})
        assert s == 302 and dove_va.endswith('/oggi'), ('password cambiata', s, dove_va)
        s, _, t = rete_.chiedi('GET', '/oggi')
        assert s == 200 and entrato_come(t, 'Rete Esempietti'), s
        s, _, _ = rete_.chiedi('POST', '/note-giorno', {'struttura': '1', 'data': oggi, 'testo': 'Nota dalla rete Fintini'})
        assert s == 302, ('Agenda da modificare: la nota non si salva', s)
        s, _, _ = rete_.chiedi('GET', '/cassa/listino')
        assert s == 200, 'Cassa da guardare: la pagina non si apre'
        s, _, t = rete_.chiedi('POST', '/cassa/listino', {'azione': 'salva'})
        assert s == 403 and 'Solo guardare' in t, ('Cassa da guardare: il salvataggio passa', s)
        for percorso, parola in (('/pazienti', 'non è fra le parti disponibili'), ('/impostazioni', 'Solo dal PC'),
                                 ('/configura/accessi', 'Solo dal PC'), ('/salute', 'Solo dal PC')):
            s, _, t = rete_.chiedi('GET', percorso)
            assert s == 403 and parola in t, (percorso, s)
        db = sqlite3.connect(os.path.join(base, 'GestionaleAgende', 'agende.db'))
        try:
            note = [r[0] for r in db.execute('SELECT testo FROM note_giorno')]
        finally:
            db.close()
        assert 'Nota dalla rete Fintini' in note, note
        _, _, t = pc.chiedi('GET', '/configura/accessi')
        assert altro_pc in t and 'POST /note-giorno' in t and 'negato (solo guardare) POST /cassa/listino' in t, \
            'il registro non dice chi era'
        # spenta: la porta si chiude davvero, il PC principale continua
        pc.chiedi('POST', '/configura/accessi', {'azione': 'rete', 'porta': str(porta_r)})
        assert chiusa(altro_pc, porta_r, da=altro_pc) and chiusa('127.0.0.1', porta_r), 'spenta, la porta risponde'
        assert pc.chiedi('GET', '/oggi')[0] == 200
        # riaccesa: chi era entrato è uscito con lo spegnimento (revisione del 22/11) e rientra con nome e password; poi
        # il programma chiuso e riaperto con la porta della rete occupata da un altro programma
        pc.chiedi('POST', '/configura/accessi', {'azione': 'rete', 'accesa': '1', 'porta': str(porta_r)})
        s, dove_va, _ = rete_.chiedi('GET', '/oggi')
        assert s == 302 and '/accesso' in dove_va, ('spenta e riaccesa: chi era entrato è ancora dentro', s, dove_va)
        s, dove_va, _ = rete_.chiedi('POST', '/accesso', {'nome': 'Rete Esempietti', 'password': 'barca verde nel lago'})
        assert s == 302 and dove_va.endswith('/oggi'), ('di nuovo dentro', s, dove_va)
        assert rete_.chiedi('GET', '/oggi')[0] == 200
        time.sleep(accessi.SALVA_SESSIONI_OGNI + 1)  # le sessioni nuove si scrivono nel file al più qualche secondo dopo
        ferma(p)
        occupata = socket.socket()
        occupata.bind(('0.0.0.0', porta_r))
        occupata.listen(1)
        p = avvia_vero(base, porta_p)
        assert pc.chiedi('GET', '/oggi')[0] == 200, 'con la porta della rete occupata il PC principale non parte'
        _, _, t = pc.chiedi('GET', '/configura/accessi')
        assert 'non in ascolto' in t and 'già usata' in t, 'la pagina non dice che la rete non è partita'
        occupata.close()
        occupata = None
        assert aspetta(lambda: rete_.chiedi('GET', '/oggi')[0] == 200, 20), \
            'liberata la porta, la rete non riparte (o chi era entrato non è più dentro)'
    finally:
        if occupata is not None:
            occupata.close()
        ferma(p)
    return 'dall\'altro PC (%s): porta principale chiusa, rete con l\'accesso; Agenda sì, Cassa no; spenta = chiusa; ' \
        'avvio con la porta occupata' % altro_pc



# ======================================================= la revisione dei tre revisori (22/11, dopo la presa della rete)
def ospiti(*voci):
    """Utenti di prova con le aree date: [(nome, aree)]; la password è sempre 'x' * 12."""
    aggiungi_utenti(*[utente(nome, 'x' * 12, aree) for nome, aree in voci])


def dentro_come(nome, ip):
    c = rete(ip=ip)
    r = entra(c, nome, 'x' * 12)
    assert r.status_code == 302, (nome, r.status_code)
    return c


def appuntamento_di(aid, **campi):
    s = A.Sessione()
    try:
        a = s.get(Appuntamento, aid)
        for k, v in campi.items():
            setattr(a, k, v)
        s.commit()
        return types.SimpleNamespace(giorno=a.inizio.date(), oid=a.operatore_id, rid=a.risorsa_id,
                                     sid=a.risorsa.struttura_id, pid=a.paziente_id, prest=a.prestazione_id)
    finally:
        s.close()


def arrivato_ieri(da_copiare, importo_cent):
    """Un appuntamento di ieri, arrivato e non pagato, con l'importo dato (None: non indicato)."""
    s = A.Sessione()
    a = s.get(Appuntamento, da_copiare)
    inizio = datetime.combine(date.today() - timedelta(days=1), datetime.min.time()).replace(hour=6, minute=40 + conta(Appuntamento) % 15)
    b = Appuntamento(risorsa_id=a.risorsa_id, operatore_id=a.operatore_id, prestazione_id=a.prestazione_id,
                     paziente_id=a.paziente_id, inizio=inizio, fine=inizio + timedelta(minutes=5), stato='ARRIVATO',
                     importo_cent=importo_cent)
    s.add(b)
    s.commit()
    bid = b.id
    s.close()
    return bid


def z_assenze_e_chiusure_senza_agenda():
    """Revisione (grave): con le sole Anagrafiche, anche da guardare, un'assenza o una chiusura mostravano «Appuntamenti
    da spostare» con nomi e telefoni dei pazienti (con una chiusura di un anno creata e poi tolta: tutti). Ora senza
    l'Agenda solo il numero, senza nomi, telefoni, collegamenti e «Spostali tutti insieme». Gemelli: con l'Agenda,
    anche solo da guardare, e dal PC la lista c'è."""
    valori = dati_per_le_pagine()
    a = appuntamento_di(valori['aid'])
    ospiti(('Anagrafiche Guarda', {'configura': 'guarda'}), ('Anagrafiche Modifica', {'configura': 'modifica'}),
           ('Anagrafiche Agenda', {'configura': 'guarda', 'agenda': 'guarda'}))
    loc = locale()
    r = loc.post('/anagrafiche/assenze/nuova', data={'operatore': a.oid, 'dal': a.giorno.isoformat(),
                                                    'al': a.giorno.isoformat(), 'motivo': 'Ferie'})
    assert r.status_code == 302 and '/anagrafiche/assenze/' in r.headers['Location'], r.headers.get('Location')
    assenza = r.headers['Location']
    t = loc.get(assenza).get_data(as_text=True)
    assert 'Canarino' in t and '3331112299' in t and 'Spostali tutti insieme' in t and 'elencati qui sotto' in t, \
        'gemello: dal PC la lista con nomi e telefoni c\'è'
    cg = dentro_come('Anagrafiche Guarda', '192.168.1.160')
    t = testo(chiedi(cg, 'GET', assenza))
    assert 'Appuntamenti da spostare (' in t and 'li vede e li sposta chi ha' in t, 'il numero degli appuntamenti non c\'è'
    for pezzo in ('Canarino', '3331112299', 'Spostali tutti insieme', '/appuntamento/%d' % valori['aid']):
        assert pezzo not in t, 'assenza con le sole Anagrafiche da guardare: c\'è %s' % pezzo
    # una chiusura di un anno, con le Anagrafiche da modificare: il numero, mai i nomi (né nel messaggio)
    cm = dentro_come('Anagrafiche Modifica', '192.168.1.161')
    r = chiedi(cm, 'POST', '/anagrafiche/chiusure/nuova', data={
        'struttura': a.sid, 'dal': date.today().isoformat(), 'al': (date.today() + timedelta(days=365)).isoformat(),
        'motivo': 'Prova della revisione'})
    assert r.status_code == 302 and '/anagrafiche/chiusure/' in r.headers['Location'], r.status_code
    chiusura = r.headers['Location']
    t = testo(chiedi(cm, 'GET', chiusura))
    assert 'Appuntamenti da spostare (' in t and 'Canarino' not in t and '3331112299' not in t, \
        'chiusura con le sole Anagrafiche: nomi o telefoni'
    assert 'elencati qui sotto' not in t, 'il messaggio dice che sono elencati, e non lo sono'
    # gemello: con l'Agenda (anche solo da guardare) la lista c'è
    ca = dentro_come('Anagrafiche Agenda', '192.168.1.162')
    t = testo(chiedi(ca, 'GET', chiusura))
    assert 'Canarino' in t and '3331112299' in t, 'gemello: con l\'Agenda la lista con nomi e telefoni c\'è'
    for indirizzo_ in (chiusura, assenza):
        assert loc.post(indirizzo_, data={'azione': 'elimina'}).status_code == 302
    return 'assenza e chiusura di un anno con le sole Anagrafiche: solo il numero; con l\'Agenda e dal PC la lista'


def z_ricerca_pazienti():
    """Revisione: la ricerca dei pazienti (/pazienti/cerca: telefono, email, codice fiscale, indirizzo di tutto
    l'archivio) a chi aveva Agenda, Segreteria o Dove si fa anche solo da guardare. Ora senza i Pazienti solo a chi
    le ha da modificare (chi prenota), e le pagine di chi guarda non hanno il campo «Cerca in anagrafica». Lo stesso
    per il paziente scelto in Dove si fa (?paziente=: nome e telefono di chiunque cambiando il numero). Gemelli: con
    «modificare», con i Pazienti anche solo da guardare, e dal PC la ricerca c'è."""
    valori = dati_per_le_pagine()
    aid, pid = valori['aid'], valori['pid']
    ospiti(('Ricerca Agenda G', {'agenda': 'guarda'}), ('Ricerca Segreteria G', {'segreteria': 'guarda'}),
           ('Ricerca Dove G', {'dove': 'guarda'}), ('Ricerca Agenda M', {'agenda': 'modifica'}),
           ('Ricerca Dove M', {'dove': 'modifica'}), ('Ricerca Pazienti G', {'pazienti': 'guarda'}))
    pagine = {'Ricerca Agenda G': '/appuntamento/%d' % aid, 'Ricerca Segreteria G': '/attesa/nuova',
              'Ricerca Dove G': '/dove-si-fa/?paziente=%d' % pid}
    for n, nome in enumerate(('Ricerca Agenda G', 'Ricerca Segreteria G', 'Ricerca Dove G')):
        c = dentro_come(nome, '192.168.1.%d' % (165 + n))
        r = chiedi(c, 'GET', '/pazienti/cerca?q=Esempietti')
        assert rifiutata(r), (nome, r.status_code)
        t = testo(chiedi(c, 'GET', pagine[nome]))
        assert 'id="cerca_paziente"' not in t and 'id="paziente-dove"' not in t and '/pazienti/cerca"' not in t, \
            '%s: la pagina ha ancora la ricerca dei pazienti' % nome
        if 'paziente=' in pagine[nome]:
            assert 'Canarino' not in t and '3331112299' not in t and 'data-paziente="%d"' % pid not in t, \
                '%s: il paziente dell\'indirizzo si vede' % nome
    # gemelli
    for n, nome in enumerate(('Ricerca Agenda M', 'Ricerca Dove M', 'Ricerca Pazienti G')):
        c = dentro_come(nome, '192.168.1.%d' % (170 + n))
        r = chiedi(c, 'GET', '/pazienti/cerca?q=Esempietti')
        assert r.status_code == 200 and any(x['telefono'] == '3331112299' for x in r.json), (nome, r.status_code)
    am = dentro_come('Ricerca Agenda M', '192.168.1.173')
    assert 'id="cerca_paziente"' in testo(chiedi(am, 'GET', '/appuntamento/%d' % aid)), 'gemello: chi prenota ha il campo'
    dm = dentro_come('Ricerca Dove M', '192.168.1.174')
    t = testo(chiedi(dm, 'GET', '/dove-si-fa/?paziente=%d' % pid))
    assert 'data-paziente="%d"' % pid in t and '/pazienti/cerca"' in t, 'gemello: Dove si fa da modificare, il paziente c\'è'
    loc = locale()
    assert loc.get('/pazienti/cerca?q=Esempietti').json, 'gemello: dal PC la ricerca c\'è'
    assert 'id="cerca_paziente"' in loc.get('/appuntamento/%d' % aid).get_data(as_text=True)
    assert 'data-paziente="%d"' % pid in loc.get('/dove-si-fa/?paziente=%d' % pid).get_data(as_text=True)
    return 'ricerca dei pazienti: no con Agenda, Segreteria o Dove da guardare; sì da modificare, con i Pazienti e dal PC'


def z_cassa_solo_con_la_cassa():
    """Revisione: importi e convenzioni a chi non ha la Cassa. Con l'Agenda la stampa del giorno (colonna Importo,
    totali, «importi del giorno», convenzione), l'Excel del giorno (CONVENZIONE e IMPORTO nell'elenco) e l'elenco del
    giorno (convenzione); con Statistiche l'esportazione del giorno; con la Segreteria la chiusura («Arrivati con un
    importo e non ancora incassati», e i bottoni verso la cassa). Gemelli: con la Cassa (anche solo da guardare) e dal
    PC ci sono."""
    import openpyxl
    valori = dati_per_le_pagine()
    a = appuntamento_di(valori['aid'], convenzione='Assicurazione Finta', tipo='CONTROLLO')
    iso, ieri = a.giorno.isoformat(), (date.today() - timedelta(days=1)).isoformat()
    arrivato_ieri(valori['aid'], 10000)
    ospiti(('Cassa No Agenda', {'agenda': 'guarda'}), ('Cassa Si Agenda', {'agenda': 'guarda', 'cassa': 'guarda'}),
           ('Cassa No Segreteria', {'segreteria': 'guarda'}),
           ('Cassa Si Segreteria', {'segreteria': 'guarda', 'cassa': 'guarda'}),
           ('Cassa No Statistiche', {'statistiche': 'guarda'}),
           ('Cassa Si Statistiche', {'statistiche': 'guarda', 'cassa': 'guarda'}))

    def excel(c, percorso):
        r = chiedi(c, 'GET', percorso)
        assert r.status_code == 200, (percorso, r.status_code)
        libro = openpyxl.load_workbook(io.BytesIO(r.data))
        celle = [x.value for x in libro['Elenco'].iter_rows() for x in x if x.value is not None]
        return celle

    def guarda_agenda(c):
        t = testo(chiedi(c, 'GET', '/stampa/%s' % iso))
        e = testo(chiedi(c, 'GET', '/giorno/%s/elenco' % iso))
        x = excel(c, '/esporta/%s' % iso)
        return {'stampa importo': 'Importo' in t and '80,00' in t, 'stampa convenzione': 'Assicurazione Finta' in t,
                'stampa tipo': 'Controllo' in t, 'elenco convenzione': 'Assicurazione Finta' in e,
                'excel importo': 'IMPORTO' in x and 80 in x, 'excel convenzione': 'Assicurazione Finta' in x,
                'excel paziente': any('Canarino' in str(v) for v in x)}
    senza = guarda_agenda(dentro_come('Cassa No Agenda', '192.168.1.175'))
    assert senza['stampa tipo'] and senza['excel paziente'], 'senza Cassa il resto (tipo, paziente) deve restare'
    for k in ('stampa importo', 'stampa convenzione', 'elenco convenzione', 'excel importo', 'excel convenzione'):
        assert not senza[k], 'con l\'Agenda senza la Cassa: %s' % k
    for chi, c in (('con la Cassa', dentro_come('Cassa Si Agenda', '192.168.1.176')), ('dal PC', locale())):
        assert all(guarda_agenda(c).values()), 'gemello %s: %s' % (chi, guarda_agenda(c))
    # l'esportazione del giorno di Statistiche e report
    x = excel(dentro_come('Cassa No Statistiche', '192.168.1.177'), '/esportazioni/giorno/tutto/%s.xlsx' % iso)
    assert 'IMPORTO' not in x and 'Assicurazione Finta' not in x and 'STATO' in x, 'esportazione senza la Cassa'
    x = excel(dentro_come('Cassa Si Statistiche', '192.168.1.178'), '/esportazioni/giorno/tutto/%s.xlsx' % iso)
    assert 'IMPORTO' in x and 'Assicurazione Finta' in x, 'gemello: esportazione con la Cassa'
    # la chiusura della Segreteria
    for nome, ip, voluto in (('Cassa No Segreteria', '192.168.1.179', False), ('Cassa Si Segreteria', '192.168.1.180', True)):
        t = testo(chiedi(dentro_come(nome, ip), 'GET', '/chiusura/%s?struttura=%d' % (ieri, a.sid)))
        for pezzo in ('non ancora incassati', '100,00', 'Cassa del giorno'):
            assert (pezzo in t) == voluto, '%s: %s %s' % (nome, pezzo, 'manca' if voluto else 'c\'è')
    t = locale().get('/chiusura/%s?struttura=%d' % (ieri, a.sid)).get_data(as_text=True)
    assert 'non ancora incassati' in t and 'Cassa del giorno' in t, 'gemello: dal PC la chiusura ha la cassa'
    # in Statistiche e report (predefinito deciso dopo, z_nv_statistiche_e_report): la pagina degli accessi dice la regola
    pagina = locale().get('/configura/accessi').get_data(as_text=True)
    assert 'i nomi dei pazienti solo con Pazienti o Agenda, gli importi solo con la Cassa' in pagina, \
        'la pagina non dice cosa resta in Statistiche'
    return 'stampa, elenco, Excel ed esportazione del giorno, chiusura: importi e convenzioni solo con la Cassa'


def z_attesa_non_cambia_la_scheda():
    """Revisione: dalla lista d'attesa (e dagli appunti messi in agenda) la Segreteria cambiava telefono ed email di un
    paziente che c'è già, senza avere i Pazienti (la correzione 5 lo aveva chiuso solo per la prenotazione). Gemelli:
    con i Pazienti da modificare, e dal PC, la scheda si aggiorna."""
    ospiti(('Attesa Senza Pazienti', {'segreteria': 'modifica'}),
           ('Attesa Con Pazienti', {'segreteria': 'modifica', 'pazienti': 'modifica'}))
    s = A.Sessione()
    stanza = s.scalars(select(Risorsa).where(Risorsa.tipo == 'AMBULATORIO').order_by(Risorsa.id)).first()
    medico = s.scalars(select(Operatore).order_by(Operatore.id)).first()
    stanza = types.SimpleNamespace(id=stanza.id, struttura_id=stanza.struttura_id)
    medico = types.SimpleNamespace(id=medico.id)
    pazienti_ = [Paziente(cognome='Improvvisi', nome='Rosa%d' % i, telefono='36699887%02d' % i,
                          email='rosa%d@example.com' % i) for i in range(3)]
    s.add_all(pazienti_)
    s.flush()
    ids = [p.id for p in pazienti_]
    s.commit()
    s.close()

    def scheda(pid):
        s = A.Sessione()
        try:
            p = s.get(Paziente, pid)
            return p.telefono, p.email, p.nome
        finally:
            s.close()

    def in_attesa(c, pid, chi):
        r = chiedi(c, 'POST', '/attesa/nuova', data={'paziente_id': pid, 'paziente': 'Improvvisi', 'nome_paziente': chi,
                                                     'telefono': '3990001122', 'email_paziente': 'altra@example.com',
                                                     'struttura': stanza.struttura_id})
        assert r.status_code == 302 and r.headers['Location'].endswith('/attesa'), (r.status_code, r.headers.get('Location'))
    prima = scheda(ids[0])
    in_attesa(dentro_come('Attesa Senza Pazienti', '192.168.1.181'), ids[0], 'Rosa0')
    assert scheda(ids[0]) == prima, 'la Segreteria senza i Pazienti ha cambiato la scheda: %s' % (scheda(ids[0]),)
    assert primo(Attesa, Attesa.paziente_id == ids[0]), 'la richiesta in lista d\'attesa non c\'è'
    in_attesa(dentro_come('Attesa Con Pazienti', '192.168.1.182'), ids[1], 'Rosa1')
    assert scheda(ids[1])[:2] == ('3990001122', 'altra@example.com'), 'gemello: con i Pazienti la scheda cambia'
    in_attesa(locale(), ids[2], 'Rosa2')
    assert scheda(ids[2])[:2] == ('3990001122', 'altra@example.com'), 'gemello: dal PC la scheda cambia'
    # gli appunti messi in agenda: il paziente trovato per cognome e telefono non si completa (uno senza nome per ognuno)
    s = A.Sessione()
    senza_nome = [Paziente(cognome='Appuntati', nome='', telefono='33355544%02d' % i) for i in range(2)]
    s.add_all(senza_nome)
    s.flush()
    ids_appunti = [p.id for p in senza_nome]
    giorno = date.today() + timedelta(days=95 + conta(Appunto) % 20)
    appunti = [Appunto(testo='Richiamare Appuntati', giorno=giorno, ora=datetime.strptime('07:%02d' % (10 + 20 * i), '%H:%M').time(),
                       durata_min=10, risorsa_id=stanza.id, operatore_id=medico.id, cognome='Appuntati',
                       nome='Completato%d' % i, telefono='33355544%02d' % i) for i in range(2)]
    s.add_all(appunti)
    s.commit()
    aids = [x.id for x in appunti]
    s.close()
    for i, nome in enumerate(('Attesa Senza Pazienti', 'Attesa Con Pazienti')):
        c = dentro_come(nome, '192.168.1.%d' % (183 + i))
        r = chiedi(c, 'POST', '/da-confermare/prenota', data={'scelti': str(aids[i]), 'risorsa': stanza.id})
        assert r.status_code == 302, (nome, r.status_code)
    assert primo(Appuntamento, Appuntamento.paziente_id == ids_appunti[0]), 'l\'appunto non è diventato un appuntamento'
    assert scheda(ids_appunti[0])[2] == '', 'dagli appunti la Segreteria senza i Pazienti ha completato la scheda'
    assert scheda(ids_appunti[1])[2] == 'Completato1', 'gemello: con i Pazienti dagli appunti la scheda si completa'
    return 'lista d\'attesa e appunti: la scheda di un paziente che c\'è già cambia solo con i Pazienti (e dal PC)'


def z_conferme_della_segreteria():
    """Revisione: nelle Conferme, la prima pagina della Segreteria, i bottoni «Confermato», «Disdetto» e «Manda» (il
    promemoria) davano 403 a chi ha la Segreteria da modificare. Ora cambiare lo stato vale per Agenda o Segreteria, e
    il promemoria anche per la Segreteria (solo quello: le email delle regole restano di Email e WhatsApp). Gemelli: la
    Segreteria da guardare e chi non ha nessuna delle due: 403."""
    valori = dati_per_le_pagine()
    aid = valori['aid']
    ospiti(('Conferme Modifica', {'segreteria': 'modifica'}), ('Conferme Guarda', {'segreteria': 'guarda'}),
           ('Conferme Cassa', {'cassa': 'modifica'}))
    sm = dentro_come('Conferme Modifica', '192.168.1.186')
    a = appuntamento_di(aid)
    t = testo(chiedi(sm, 'GET', '/conferme?data=%s&struttura=%d' % (a.giorno.isoformat(), a.sid)))
    assert '/appuntamento/%d/stato' % aid in t, 'il bottone non è nella pagina delle Conferme'
    for stato in ('CONFERMATO', 'DISDETTO', 'PRENOTATO'):
        r = chiedi(sm, 'POST', '/appuntamento/%d/stato' % aid, data={'stato': stato, 'torna': '/conferme'})
        assert r.status_code == 302, (stato, r.status_code)
        s = A.Sessione()
        assert s.get(Appuntamento, aid).stato == stato, stato
        s.close()
    r = chiedi(sm, 'POST', '/invii/appuntamento/%d' % aid, data={'azione': 'promemoria', 'torna': '/conferme'})
    assert r.status_code == 302, ('«Manda» il promemoria dalla Segreteria', r.status_code)
    r = chiedi(sm, 'POST', '/invii/appuntamento/%d' % aid, data={'azione': 'regola', 'regola': 1})
    assert rifiutata(r), 'le email delle regole sono di Email e WhatsApp, non della Segreteria'
    # gemelli: la Segreteria da guardare, e la sola Cassa
    for nome, ip in (('Conferme Guarda', '192.168.1.187'), ('Conferme Cassa', '192.168.1.188')):
        c = dentro_come(nome, ip)
        for percorso, dati in (('/appuntamento/%d/stato' % aid, {'stato': 'CONFERMATO'}),
                               ('/invii/appuntamento/%d' % aid, {'azione': 'promemoria'})):
            assert rifiutata(chiedi(c, 'POST', percorso, data=dati)), (nome, percorso)
    return 'Confermato, Disdetto e Manda dalle Conferme con la Segreteria; le regole no; da guardare o senza: 403'


def z_incasso_con_la_sola_cassa():
    """Revisione: con la sola Cassa da modificare, nella cassa del giorno «Altro…» (bonifico, assegno, un importo
    diverso o non indicato) portava all'appuntamento, cioè all'Agenda: 403. Ora senza l'Agenda c'è lì il modulo, con
    importo e metodo. Gemelli: con l'Agenda e dal PC «Altro…» come prima."""
    valori = dati_per_le_pagine()
    bid = arrivato_ieri(valori['aid'], None)
    ieri = (date.today() - timedelta(days=1)).isoformat()
    ospiti(('Incasso Solo Cassa', {'cassa': 'modifica'}), ('Incasso Cassa Agenda', {'cassa': 'modifica', 'agenda': 'guarda'}))
    c = dentro_come('Incasso Solo Cassa', '192.168.1.189')
    t = testo(chiedi(c, 'GET', '/cassa/%s' % ieri))
    assert 'Altro…' not in t and 'value="BONIFICO"' in t and '/appuntamento/%d/pagamento' % bid in t, \
        'con la sola Cassa il modulo per incassare in altro modo non c\'è'
    r = chiedi(c, 'POST', '/appuntamento/%d/pagamento' % bid, data={'metodo': 'BONIFICO', 'importo': '55,00',
                                                                    'torna': '/cassa/%s' % ieri})
    assert r.status_code == 302 and r.headers['Location'].endswith('/cassa/%s' % ieri), r.status_code
    s = A.Sessione()
    b = s.get(Appuntamento, bid)
    assert (b.pagato_cent, b.pagamento, b.importo_cent) == (5500, 'BONIFICO', 5500), (b.pagato_cent, b.pagamento)
    s.close()
    bid2 = arrivato_ieri(valori['aid'], None)
    for chi, cliente in (('con l\'Agenda', dentro_come('Incasso Cassa Agenda', '192.168.1.190')), ('dal PC', locale())):
        t = testo(chiedi(cliente, 'GET', '/cassa/%s' % ieri))
        assert 'Altro…' in t and '/appuntamento/%d' % bid2 in t, 'gemello %s: «Altro…» come prima' % chi
    return 'con la sola Cassa si incassa con bonifico e importo scritto; con l\'Agenda e dal PC «Altro…»'


def z_tentativi_con_tanti_nomi():
    """Revisione: chiunque sulla rete, senza password, rendeva lenta per minuti la pagina «Aree e accessi» (quella
    che spegne la rete) provando nomi sempre nuovi: le voci crescevano senza fine e bloccati() confrontava ogni nome con
    ogni coppia; il registro cresceva di una riga per tentativo e la pagina rileggeva i file per intero. Ora: 30
    sbagliate dallo stesso PC con nomi qualsiasi e quel PC aspetta (gemello: un altro PC entra; «Sblocca» il PC); voci
    con un tetto; bloccati() con 20.000 nomi sotto mezzo secondo; nel registro al massimo una riga al minuto per PC,
    con quanti erano; la pagina legge solo la coda dei file."""
    t = accessi.Tentativi()
    t0 = time.time()
    inizio = time.perf_counter()
    for i in range(20000):
        t.sbagliata('192.0.2.9', 'nome finto %d' % i, t0 + i * 0.001)
    sbagliando = time.perf_counter() - inizio
    inizio = time.perf_counter()
    bloccati = t.bloccati(t0 + 25)
    in_pagina = time.perf_counter() - inizio
    assert sbagliando < 3 and in_pagina < 0.5, '20.000 nomi: sbagliata %.2f s, bloccati %.2f s' % (sbagliando, in_pagina)
    assert max(len(t.coppie), len(t.nomi)) < 10000, 'le voci non hanno un tetto: %d' % len(t.coppie)
    assert ('', ['192.0.2.9'], 15) in bloccati, 'il PC dei tanti nomi non è fra i bloccati: %s' % bloccati[:3]
    assert t.attesa('192.0.2.9', 'un nome mai provato', t0 + 25) > 0, 'il PC dei tanti nomi prova ancora un nome nuovo'
    assert t.attesa('192.0.2.99', 'un nome mai provato', t0 + 25) == 0, 'gemello: un altro PC prova'
    # gemello: un nome sbagliato 5 volte dallo stesso PC è fra i bloccati, con il suo PC
    for i in range(accessi.TENTATIVI_COPPIA):
        t.sbagliata('192.0.2.10', 'Anna Esempietti', t0 + 30 + i)
    assert ('anna esempietti', ['192.0.2.10'], 15) in t.bloccati(t0 + 40), t.bloccati(t0 + 40)[:3]
    # dalla pagina di accesso: 30 nomi qualsiasi, poi quel PC aspetta anche con il nome e la password giusti
    x = rete(ip='192.168.1.191')
    for i in range(accessi.TENTATIVI_PC):
        assert entra(x, 'Nome Inventato %d' % i, 'qualcosa di lungo').status_code == 200, i
    letture = []

    def conta_letture(*_a, **_k):
        letture.append(1)
    event.listen(A.Sessione.motore, 'before_cursor_execute', conta_letture)
    try:
        r = entra(x, 'Anna Esempietti')
    finally:
        event.remove(A.Sessione.motore, 'before_cursor_execute', conta_letture)
    assert r.status_code == 429, 'dopo 30 nomi sbagliati dallo stesso PC si entra ancora: %s' % r.status_code
    assert not letture, 'la risposta a un PC bloccato legge il database (%d volte): costa troppo' % len(letture)
    assert entra(rete(ip='192.168.1.192'), 'Anna Esempietti').status_code == 302, 'gemello: un altro PC entra'
    pagina = locale().get('/configura/accessi').get_data(as_text=True)
    assert '192.168.1.191' in pagina and 'Sblocca il PC' in pagina, 'il PC bloccato non è nella pagina'
    locale().post('/configura/accessi', data={'azione': 'sblocca', 'nome': '', 'pc': '192.168.1.191'})
    assert entra(x, 'Anna Esempietti').status_code == 302, 'dopo «Sblocca» il PC entra'
    # il registro: una riga al minuto per PC, poi quanti erano
    percorso = os.path.join(PROVVISORIA, 'accessi', 'accessi-%s.log' % OGGI)
    with open(percorso, encoding='utf-8') as f:
        righe = [r for r in f.read().splitlines() if 'da=192.168.1.191' in r and 'sbagliat' in r or 'da=192.168.1.191' in r
                 and 'non entrato' in r]
    assert 1 <= len(righe) <= 2, 'tentativi sbagliati dallo stesso PC nel registro: %d righe' % len(righe)
    accessi.tentativi.scrivi_rimasti(time.time() + 61)
    with open(percorso, encoding='utf-8') as f:
        resto = [int(n) for r in f.read().splitlines() if 'da=192.168.1.191' in r
                 for n in re.findall(r'altri (\d+) tentativi sbagliati', r)]
    assert resto and resto[-1] >= accessi.TENTATIVI_PC - 1, 'il numero dei tentativi non scritti uno per uno: %s' % resto
    # la pagina legge la coda dei file: un registro di 30 MB, letti meno di 2 MB
    cartella = os.path.join(PROVVISORIA, 'registro-grande')
    os.makedirs(cartella)
    grande = os.path.join(cartella, 'accessi-%s.log' % OGGI)
    riga = '%s 10:00:00,000 WARNING password sbagliata | utente=Riga Finta | da=192.0.2.50\n' % OGGI
    with open(grande, 'w', encoding='utf-8') as f:
        f.write(riga * (30 * 1024 * 1024 // len(riga)))
    letti = [0]
    vero_open = open

    def apri(*a, **k):
        f = vero_open(*a, **k)
        leggi_ = f.read

        def conta_letti(*b):
            dati = leggi_(*b)
            letti[0] += len(dati)
            return dati
        f.read = conta_letti
        return f
    accessi.open = apri
    prima_cartella = accessi._cartella_registro[0]
    accessi._cartella_registro[0] = cartella
    try:
        eventi_ = accessi.ultimi_accessi()
    finally:
        del accessi.open
        accessi._cartella_registro[0] = prima_cartella
        shutil.rmtree(cartella)
    assert len(eventi_) == 150 and eventi_[0][1] == eventi_[-1][1] == 'Riga Finta', (len(eventi_), eventi_[:1])
    assert letti[0] < 2 * 1024 * 1024, 'per la pagina letti %d byte del registro' % letti[0]
    return '20.000 nomi: bloccati in %.2f s; 30 nomi dallo stesso PC: bloccato, gli altri entrano; registro raggruppato ' \
        'e letto dal fondo' % in_pagina


def z_collegamenti_per_pc():
    """Revisione: un solo PC, senza password, apriva i 20 collegamenti della porta della rete e li teneva occupati
    mandando un carattere ogni tanto: nessun altro PC entrava più. Ora al massimo 12 collegamenti aperti dallo stesso
    indirizzo (il tredicesimo si chiude subito) e 100 in tutto; gli indirizzi del PC stesso (un portiere) no. Gemelli: un
    altro PC intanto entra; chiusi quelli lenti, lo stesso PC di nuovo; dal PC stesso più di 12 insieme passano."""
    lento = indirizzo_di_un_altro_pc()
    assert lento, 'nessun indirizzo di questo PC fuori da 127.*: non si può provare l\'arrivo da un altro PC'
    porta = porta_libera()
    assert accessi.ascolto.accendi(A.app, porta), accessi.ascolto.errore
    prese = []

    def richiesta(da, intera=True):
        x = socket.create_connection(('127.0.0.1' if da.startswith('127.') else da, porta), timeout=10,
                                     source_address=(da, 0))
        x.sendall(('GET /accesso HTTP/1.1\r\nHost: 127.0.0.1:%d\r\n' % porta).encode() + (b'Connection: close\r\n\r\n'
                                                                                          if intera else b''))
        return x
    try:
        for _ in range(accessi.COLLEGAMENTI_PER_PC):
            prese.append(richiesta(lento, intera=False))
        time.sleep(0.5)
        di_troppo = richiesta(lento)
        try:
            risposta = di_troppo.recv(100)
        except OSError:
            risposta = b''
        di_troppo.close()
        assert risposta == b'', 'un collegamento in più dallo stesso PC ha avuto risposta: %r' % risposta[:40]
        y = richiesta('127.0.0.1')
        assert y.recv(100).startswith(b'HTTP/1.1 '), 'gemello: un altro indirizzo intanto ha la risposta'
        y.close()
        dal_pc = [richiesta('127.0.0.1', intera=False) for _ in range(accessi.COLLEGAMENTI_PER_PC + 2)]
        y = richiesta('127.0.0.1')
        risposta = y.recv(100)
        for x in dal_pc + [y]:
            x.close()
        assert risposta.startswith(b'HTTP/1.1 '), 'gemello: dal PC stesso (un portiere) più collegamenti insieme passano'
        for x in prese:
            x.close()
        prese = []
        time.sleep(0.5)
        z = richiesta(lento)
        assert z.recv(100).startswith(b'HTTP/1.1 '), 'gemello: chiusi quelli lenti, lo stesso PC ha la risposta'
        z.close()
    finally:
        for x in prese:
            x.close()
        accessi.ascolto.spegni()
    return 'dallo stesso PC al massimo %d collegamenti aperti: quello in più chiuso subito, un altro PC entra' % \
        accessi.COLLEGAMENTI_PER_PC


def z_cookie_da_un_altro_pc():
    """Revisione: il cookie della sessione (in chiaro sulla rete) valeva da qualsiasi PC. Ora solo da quello da cui si
    è entrati: da un altro la sessione si chiude (nel registro «sessione usata da un altro PC») e si rientra. Gemelli:
    lo stesso cookie da un'altra finestra dello stesso PC vale, anche dietro il portiere (X-Forwarded-For)."""
    c = rete(ip='192.168.1.193')
    assert entra(c, 'Guarda Fittizi').status_code == 302
    biscotto = c.get_cookie(accessi.COOKIE_RETE, domain='192.168.1.10').value
    stesso = rete(ip='192.168.1.193')
    stesso.set_cookie(accessi.COOKIE_RETE, biscotto, domain='192.168.1.10')
    assert chiedi(stesso, 'GET', '/oggi').status_code == 200, 'gemello: dallo stesso PC il cookie vale'
    ladro = rete(ip='192.168.1.194')
    ladro.set_cookie(accessi.COOKIE_RETE, biscotto, domain='192.168.1.10')
    r = chiedi(ladro, 'GET', '/oggi')
    assert r.status_code == 302 and '/accesso' in r.headers['Location'], 'il cookie vale da un altro PC'
    assert chiedi(c, 'GET', '/oggi').status_code == 302, 'la sessione usata da un altro PC non si è chiusa'
    with open(os.path.join(PROVVISORIA, 'accessi', 'accessi-%s.log' % OGGI), encoding='utf-8') as f:
        assert any('sessione usata da un altro PC' in r and 'da=192.168.1.194' in r for r in f), 'non scritto nel registro'
    # dietro il portiere (Caddy sullo stesso PC): conta l'indirizzo che scrive lui
    p1 = rete('inoltrata', ip='192.168.1.195')
    assert entra(p1, 'Guarda Fittizi').status_code == 302
    biscotto = p1.get_cookie('session', domain='127.0.0.1') or p1.get_cookie(accessi.COOKIE_RETE, domain='127.0.0.1')
    p2 = rete('inoltrata', ip='192.168.1.195')
    p2.set_cookie(biscotto.key, biscotto.value, domain='127.0.0.1')
    assert chiedi(p2, 'GET', '/oggi').status_code == 200, 'gemello: dietro il portiere, lo stesso PC'
    p3 = rete('inoltrata', ip='192.168.1.196')
    p3.set_cookie(biscotto.key, biscotto.value, domain='127.0.0.1')
    assert chiedi(p3, 'GET', '/oggi').status_code == 302, 'dietro il portiere, da un altro PC il cookie vale'
    return 'il cookie vale solo dal PC da cui si è entrati (anche dietro il portiere); da un altro: fuori e nel registro'


def z_tentativi_mandati_insieme():
    """Revisione: 40 password sbagliate mandate tutte insieme dallo stesso PC sulla presa vera della rete: ne venivano
    provate 8 invece di 5, perché i fili leggevano il contatore prima che fosse aggiornato. Ora il tentativo si conta
    prima di provare la password: al massimo 5. Gemello: la password giusta dopo un'attesa sbloccata entra."""
    porta = porta_libera()
    assert accessi.ascolto.accendi(A.app, porta), accessi.ascolto.errore
    stati = []
    pronti = threading.Barrier(40)

    def prova_una(i):
        h = http.client.HTTPConnection('127.0.0.1', porta, timeout=60)
        corpo = urllib.parse.urlencode({'nome': 'Anna Esempietti', 'password': 'sbagliata numero %d' % i}).encode()
        pronti.wait()
        try:
            h.request('POST', '/accesso', body=corpo, headers={
                'Host': '127.0.0.1:%d' % porta, 'Origin': 'http://127.0.0.1:%d' % porta,
                'Content-Type': 'application/x-www-form-urlencoded'})
            stati.append(h.getresponse().status)
        finally:
            h.close()
    try:
        fili = [threading.Thread(target=prova_una, args=(i,)) for i in range(40)]
        for f in fili:
            f.start()
        for f in fili:
            f.join(120)
    finally:
        accessi.ascolto.spegni()
    provate = stati.count(200)
    assert len(stati) == 40 and provate <= accessi.TENTATIVI_COPPIA and stati.count(429) == 40 - provate, \
        '40 tentativi insieme: %d password provate (al massimo %d), risposte %s' % (
            provate, accessi.TENTATIVI_COPPIA, sorted(set(stati)))
    accessi.tentativi.sblocca('Anna Esempietti', pc='127.0.0.1')
    assert entra(rete(ip='127.0.0.1', come='presa'), 'Anna Esempietti').status_code == 302, 'gemello: sbloccato, si entra'
    return '40 tentativi insieme dallo stesso PC: %d password provate' % provate


def z_sessioni_per_utente():
    """Revisione: chi entrava di continuo senza uscire lasciava una sessione per ogni accesso (1.500 in un minuto), e
    ogni accesso riscriveva tutto il file. Ora al massimo 5 per utente (entrando la sesta, via quella usata meno di
    recente) e il file riscritto al più ogni pochi secondi. Gemelli: le ultime 5 valgono, e il file si scrive lo stesso
    poco dopo."""
    accessi.sessioni.svuota()
    u = accessi.trova(utenti_salvati(), 'Guarda Fittizi')
    scritture = [0]
    vero = accessi.os.replace

    def conta_scritture(a, b):
        if str(b).endswith('sessioni-rete.json'):
            scritture[0] += 1
        return vero(a, b)
    clienti = []
    accessi.os.replace = conta_scritture
    try:
        time.sleep(accessi.SALVA_SESSIONI_OGNI)          # l'ultima scrittura di svuota() abbastanza lontana
        for i in range(30):
            c = rete(ip='192.168.1.197')
            assert entra(c, 'Guarda Fittizi').status_code == 302, i
            clienti.append(c)
    finally:
        accessi.os.replace = vero
    assert accessi.sessioni.quante(u['id']) == accessi.MASSIMO_SESSIONI, accessi.sessioni.quante(u['id'])
    assert scritture[0] <= 2, '30 accessi: il file delle sessioni riscritto %d volte' % scritture[0]
    assert all(chiedi(c, 'GET', '/oggi').status_code == 200 for c in clienti[-5:]), 'gemello: le ultime 5 valgono'
    assert chiedi(clienti[0], 'GET', '/oggi').status_code == 302, 'la prima, la più vecchia, vale ancora'
    sid = A.app.session_interface.get_signing_serializer(A.app).loads(
        clienti[-1].get_cookie(accessi.COOKIE_RETE, domain='192.168.1.10').value)['sid']

    def nel_file():
        with open(os.path.join(PROVVISORIA, 'sessioni-rete.json'), encoding='utf-8') as f:
            return accessi.impronta_id(sid) in json.load(f)
    assert aspetta(nel_file, accessi.SALVA_SESSIONI_OGNI + 3), 'gemello: poco dopo la sessione è nel file'
    return '30 accessi di fila: %d sessioni, file riscritto %d volte' % (accessi.MASSIMO_SESSIONI, scritture[0])


def bomba_excel(righe, colonne=10):
    """Un .xlsx piccolo e molto compresso, con tante celle uguali e senza indirizzi (quello della revisione)."""
    import zipfile
    tipi = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/'
            'content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships'
            '+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override '
            'PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.'
            'spreadsheetml.worksheet+xml"/></Types>')
    rel = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
           'relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
           'relationships/%s" Target="%s"/></Relationships>')
    libro = ('<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/'
             '2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
             '<sheet name="Foglio1" sheetId="1" r:id="rId1"/></sheets></workbook>')
    uscita = io.BytesIO()
    with zipfile.ZipFile(uscita, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr('[Content_Types].xml', tipi)
        z.writestr('_rels/.rels', rel % ('officeDocument', 'xl/workbook.xml'))
        z.writestr('xl/workbook.xml', libro)
        z.writestr('xl/_rels/workbook.xml.rels', rel % ('worksheet', 'worksheets/sheet1.xml'))
        with z.open('xl/worksheets/sheet1.xml', 'w') as f:
            f.write(b'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/'
                    b'spreadsheetml/2006/main"><sheetData>')
            riga = b'<row>' + b'<c><v>1</v></c>' * colonne + b'</row>'
            for _ in range(righe):
                f.write(riga)
            f.write(b'</sheetData></worksheet>')
    return uscita.getvalue()


def leggi_come_prima(dati):
    """L'oracolo: importa.leggi_file per gli .xlsx com'era fino alla 1.13 (il foglio aperto per intero), copiato qui
    e da non toccare. La lettura nuova, in sola lettura, deve dare le stesse righe."""
    from openpyxl import load_workbook
    import importa
    wb = load_workbook(io.BytesIO(dati), data_only=True)
    fogli = []
    for ws in wb.worksheets:
        max_r = min(ws.max_row or 0, importa.MASSIMO_RIGHE + 30)
        max_c = min(ws.max_column or 0, importa.MASSIMO_COLONNE)
        righe = [[None] * max_c for _ in range(max_r)]
        for r_i, riga in enumerate(ws.iter_rows(min_row=1, max_row=max_r, max_col=max_c, values_only=True)):
            for c_i, v in enumerate(riga):
                righe[r_i][c_i] = v
        for m in ws.merged_cells.ranges:
            v = ws.cell(m.min_row, m.min_col).value
            for r in range(m.min_row, min(m.max_row, max_r) + 1):
                for c in range(m.min_col, min(m.max_col, max_c) + 1):
                    righe[r - 1][c - 1] = v
        while righe and all(v in (None, '') for v in righe[-1]):
            righe.pop()
        oltre = 0
        if (ws.max_row or 0) > max_r:
            for riga in ws.iter_rows(min_row=max_r + 1, max_col=max_c or None, values_only=True):
                if any(not importa.vuoto(v) for v in riga):
                    oltre += 1
        fogli.append((ws.title, righe, oltre))
    return fogli


def z_excel_troppo_compresso():
    """Revisione: un utente della rete con le Anagrafiche da modificare («Importa da Excel») caricava un .xlsx piccolo
    e molto compresso con milioni di celle, e il programma (uno solo, anche per il PC della segreteria) finiva la
    memoria: openpyxl caricava tutto prima di ogni controllo. Ora prima si guarda quanto diventa scompattato, poi si
    legge in sola lettura tenendo solo le righe che servono; lo stesso controllo per tariffari e strutture del gruppo.
    Gemelli: gli Excel veri (il planning del giorno con celle unite e logo, fogli inventati con celle unite e righe oltre
    il massimo) si leggono come prima, contro l'oracolo leggi_come_prima."""
    import importa
    import random
    import tariffari
    import dovesifa
    from openpyxl import Workbook
    bomba = bomba_excel(100000)
    assert len(bomba) < 100 * 1024, len(bomba)
    inizio = time.perf_counter()
    try:
        importa.leggi_file(bomba, 'agenda.xlsx')
        letta = True
    except ValueError as e:
        letta, motivo = False, str(e)
    durata = time.perf_counter() - inizio
    assert not letta and 'compresso troppo' in motivo and durata < 1, 'la bomba: letta %s in %.1f s' % (letta, durata)
    for leggi_, errore in ((tariffari.leggi_tariffari, tariffari.ErroreTariffario),
                           (dovesifa.leggi_database, dovesifa.ErroreDatabase)):
        try:
            leggi_(bomba, 'bomba.xlsx')
            assert False, '%s ha letto la bomba' % leggi_.__name__
        except errore as e:
            assert 'compresso troppo' in str(e), (leggi_.__name__, str(e))
    # sotto i controlli dello zip (foglio sotto i 10 MB): letto in sola lettura, con poca memoria e le righe in più contate
    import tracemalloc
    medio = bomba_excel(26000)
    tracemalloc.start()
    try:
        letto = importa.leggi_file(medio, 'agenda.xlsx')
        picco = tracemalloc.get_traced_memory()[1] / 2 ** 20
    finally:
        tracemalloc.stop()
    assert len(letto[0]['righe']) == importa.MASSIMO_RIGHE + 30 and letto[0]['oltre'] == 26000 - importa.MASSIMO_RIGHE - 30
    assert picco < 55, '260.000 celle lette con %.0f MB di memoria (aperto per intero ne servono più di 70)' % picco
    # troppo grande una volta aperto (il massimo abbassato apposta), e dalla pagina con le Anagrafiche
    normale = io.BytesIO()
    wb = Workbook()
    wb.active.append(['Cognome', 'Telefono'])
    wb.save(normale)
    import comune
    try:
        comune.controlla_excel_compresso(normale.getvalue(), massimo=1000)
        assert False, 'un file più grande del massimo passa'
    except ValueError as e:
        assert 'troppo grande' in str(e), str(e)
    ospiti(('Importa Modifica', {'configura': 'modifica'}))
    c = dentro_come('Importa Modifica', '192.168.1.198')
    r = chiedi(c, 'POST', '/importa', data={'tipo': '', 'file': (io.BytesIO(bomba), 'agenda.xlsx')},
               content_type='multipart/form-data')
    assert r.status_code == 302 and r.headers['Location'].endswith('/importa'), (r.status_code, r.headers.get('Location'))
    assert 'compresso troppo' in testo(chiedi(c, 'GET', '/importa')), 'dalla rete il motivo non si legge nella pagina'
    # gemelli: gli Excel veri si leggono come prima
    file = [('planning di oggi', locale().get('/esporta/%s' % OGGI).data),
            ('esportazione', locale().get('/esportazioni/giorno/tutto/%s.xlsx' % OGGI).data)]
    rnd = random.Random(13)
    for n in range(25):
        wb = Workbook()
        for f in range(rnd.randint(1, 2)):
            ws = wb.active if f == 0 else wb.create_sheet('Altro %d' % f)
            righe, colonne = rnd.choice([0, 3, 40]), rnd.choice([1, 6, 84])
            for r in range(1, righe + 1):
                for k in range(1, colonne + 1):
                    if rnd.random() < 0.5:
                        ws.cell(r, k, rnd.choice([None, '', ' ', 'testo %d' % r, r * k, 2.5, date(2026, 3, 1) + timedelta(days=r),
                                                  datetime(2026, 3, 2, 8, 15)]))
            for _ in range(rnd.randint(0, 6)):
                r1, k1 = rnd.randint(1, righe + 3), rnd.randint(1, colonne + 3)
                try:
                    ws.merge_cells(start_row=r1, start_column=k1, end_row=r1 + rnd.randint(0, 3), end_column=k1 + rnd.randint(0, 3))
                except ValueError:
                    pass
        b = io.BytesIO()
        wb.save(b)
        file.append(('inventato %d' % n, b.getvalue()))
    wb = Workbook()
    ws = wb.active
    massimo = importa.MASSIMO_RIGHE + 30
    for r in range(1, massimo + 41):
        ws.cell(r, 1, 'riga %d' % r if r % 7 else '')
    ws.merge_cells(start_row=massimo - 2, start_column=2, end_row=massimo + 4, end_column=3)
    ws.cell(massimo - 2, 2, 'unita oltre il massimo')
    b = io.BytesIO()
    wb.save(b)
    file.append(('righe oltre il massimo', b.getvalue()))
    diversi = []
    for nome, dati in file:
        assert dati[:2] == b'PK', nome
        nuovo = [(f['nome'], f['righe'], f['oltre']) for f in importa.leggi_file(dati, 'x.xlsx')]
        if nuovo != leggi_come_prima(dati):
            diversi.append(nome)
    assert not diversi, 'letti diversi da prima: %s' % diversi
    assert importa.leggi_file(file[-1][1], 'x.xlsx')[0]['oltre'] == sum(1 for r in range(massimo + 1, massimo + 41) if r % 7), \
        'le righe oltre il massimo non si contano'
    return 'la bomba (%d KB) rifiutata in %.2f s, anche da tariffari e strutture; %d Excel veri letti come prima' % (
        len(bomba) // 1024, durata, len(file))


# ======================================== la revisione dei tre revisori, i 14 problemi del secondo giro (22/11, sera)
def per(endpoint, **argomenti):
    with A.app.test_request_context():
        from flask import url_for
        return url_for(endpoint, **argomenti)


def moduli_post(t):
    """[(tag, azione)] dei <form method="post"> della pagina."""
    uscita = []
    for m in re.finditer(r'<form\b[^>]*>', t, re.I):
        tag = m.group(0)
        if (accessi._attributo(tag, 'method') or 'get').lower() == 'post':
            uscita.append((tag, accessi._attributo(tag, 'action')))
    return uscita


def z_nv_scheda_paziente_senza_segreteria():
    """Problema 1: chi ha solo i Pazienti leggeva nella scheda le cose da fare e la lista d'attesa (dati della
    Segreteria) e trovava «Ricordami di… Aggiungi» e «Metti in lista d'attesa», che rispondevano 403 perdendo il testo.
    Ora niente; gemelli: con la Segreteria da modificare ci sono, e sul PC pure."""
    valori = dati_per_le_pagine()
    s = A.Sessione()
    s.add(Attesa(paziente_id=valori['pid'], struttura_id=1, note='attesa di prova Fintini'))
    s.commit()
    s.close()
    ospiti(('Pazienti Guarda', {'pazienti': 'guarda'}), ('Pazienti Modifica', {'pazienti': 'modifica'}),
           ('Pazienti Segreteria', {'pazienti': 'modifica', 'segreteria': 'modifica'}))
    pezzi = ('Richiamare per il referto', 'In lista d\'attesa dal', 'Metti in lista d\'attesa',
             'action="%s"' % per('segreteria.cose_da_fare'))
    url = '/pazienti/%d' % valori['pid']
    for nome, ip in (('Pazienti Guarda', '192.168.1.201'), ('Pazienti Modifica', '192.168.1.202')):
        t = testo(chiedi(dentro_come(nome, ip), 'GET', url))
        assert 'Esempietti' in t, (nome, 'la scheda non si apre')
        dentro = [x for x in pezzi if x in t]
        assert not dentro, '%s legge o trova della Segreteria: %s' % (nome, dentro)
    t = testo(chiedi(dentro_come('Pazienti Segreteria', '192.168.1.203'), 'GET', url))
    assert all(x in t for x in pezzi), 'gemello: con la Segreteria ci sono'
    t = locale().get(url).get_data(as_text=True)
    assert all(x in t for x in pezzi), 'gemello: sul PC ci sono'
    return 'cose da fare, lista d\'attesa, «Ricordami di…» e «Metti in lista d\'attesa» solo con la Segreteria'


def z_nv_ricerca_dei_pazienti_ridotta():
    """Problema 2: chi cercava i pazienti da Dove si fa (o dalla Segreteria) senza Pazienti né Agenda riceveva
    l'anagrafica intera (codice fiscale, indirizzo, email, prossimo appuntamento). Ora solo nome, nascita e telefono.
    Per tutte le aree e i due livelli: la ricerca risponde 403, oppure dà l'anagrafica intera solo con Pazienti o Agenda.
    Gemelli: con l'Agenda e sul PC l'anagrafica intera."""
    valori = dati_per_le_pagine()
    s = A.Sessione()
    p = s.get(Paziente, valori['pid'])
    p.codice_fiscale, p.indirizzo = 'SMPCNR80A01F839X', 'Via Inventata 1, Napoli'
    s.commit()
    s.close()
    ridotte = {'id', 'cognome', 'nome', 'telefono', 'nascita', 'nascita_iso'}
    voci, n = [], 0
    for a in accessi.CODICI_AREE:
        for lv in accessi.LIVELLI_VALIDI:
            voci.append(('Cerca %s %s' % (a, lv), {a: lv}))
    voci.append(('Cerca dove e agenda', {'dove': 'modifica', 'agenda': 'modifica'}))
    ospiti(*voci)
    for nome, aree in voci:
        n += 1
        r = chiedi(dentro_come(nome, '192.168.2.%d' % n), 'GET', '/pazienti/cerca?q=Esempietti')
        intera = 'pazienti' in aree or 'agenda' in aree and aree['agenda'] == 'modifica'
        if r.status_code == 403:
            assert not ('pazienti' in aree or aree.get('agenda') == 'modifica'), (nome, 'ricerca negata a chi la deve avere')
            continue
        assert r.status_code == 200 and r.json, (nome, r.status_code)
        chiavi = set().union(*[set(x) for x in r.json])
        if intera:
            assert 'SMPCNR80A01F839X' in r.get_data(as_text=True), (nome, 'gemello: l\'anagrafica intera')
        else:
            assert chiavi == ridotte, '%s riceve dalla ricerca %s' % (nome, sorted(chiavi - ridotte))
            assert 'SMPCNR' not in r.get_data(as_text=True) and 'Inventata' not in r.get_data(as_text=True)
    r = locale().get('/pazienti/cerca?q=Esempietti')
    assert 'SMPCNR80A01F839X' in r.get_data(as_text=True) and 'Inventata' in r.get_data(as_text=True), \
        'gemello: sul PC l\'anagrafica intera'
    return '%d utenti, ogni area nei due livelli: anagrafica intera solo con Pazienti o Agenda' % len(voci)


def z_nv_listino_solo_con_la_cassa():
    """Problema 3: con le sole Anagrafiche da modificare si leggeva e cambiava il prezzo di listino della prestazione, e
    si vedeva il tariffario del medico (dati della Cassa). Ora il campo c'è solo a chi può cambiare la Cassa e il prezzo
    non cambia; il tariffario solo con la Cassa. Gemelli: con Anagrafiche e Cassa da modificare, e sul PC."""
    s = A.Sessione()
    prest = s.scalars(select(Prestazione).order_by(Prestazione.id)).first()
    prest.tariffa_cent = 8000
    pid, nome_p, durata = prest.id, prest.nome, prest.durata_min
    oid = s.scalars(select(Operatore).order_by(Operatore.id)).first().id
    s.commit()
    s.close()
    ospiti(('Anagrafiche Sole', {'configura': 'modifica'}),
           ('Anagrafiche Cassa Guarda', {'configura': 'modifica', 'cassa': 'guarda'}),
           ('Anagrafiche Cassa', {'configura': 'modifica', 'cassa': 'modifica'}))
    url = per('anagrafiche.prestazione', pid=pid)
    medico = per('anagrafiche.medico', oid=oid)
    tariffari = per('tariffari.elenco')

    def prezzo():
        s = A.Sessione()
        try:
            return s.get(Prestazione, pid).tariffa_cent
        finally:
            s.close()
    for nome, ip in (('Anagrafiche Sole', '192.168.1.211'), ('Anagrafiche Cassa Guarda', '192.168.1.212')):
        c = dentro_come(nome, ip)
        t = testo(chiedi(c, 'GET', url))
        assert nome_p in t and 'name="tariffa"' not in t and 'Prezzo di listino' not in t, (nome, 'il prezzo di listino')
        # il tariffario del medico: solo con la Cassa (da guardare basta: si legge anche in Cassa → Tariffari)
        assert (tariffari in testo(chiedi(c, 'GET', medico))) == (nome == 'Anagrafiche Cassa Guarda'), \
            (nome, 'il tariffario del medico')
        r = chiedi(c, 'POST', url, data={'nome': nome_p, 'durata': str(durata), 'tariffa': '1,00'})
        assert r.status_code == 302 and prezzo() == 8000, (nome, r.status_code, prezzo())
    c = dentro_come('Anagrafiche Cassa', '192.168.1.213')
    t = testo(chiedi(c, 'GET', url))
    assert 'name="tariffa"' in t and tariffari in testo(chiedi(c, 'GET', medico)), 'gemello: con la Cassa ci sono'
    r = chiedi(c, 'POST', url, data={'nome': nome_p, 'durata': str(durata), 'tariffa': '90,00'})
    assert r.status_code == 302 and prezzo() == 9000, ('gemello: con la Cassa il prezzo cambia', prezzo())
    t = locale().get(url).get_data(as_text=True)
    assert 'name="tariffa"' in t and tariffari in locale().get(medico).get_data(as_text=True), 'gemello: sul PC'
    return 'prezzo di listino e tariffario solo con la Cassa; con le sole Anagrafiche il prezzo resta 80,00'


def intervento_in_sala():
    s = A.Sessione()
    sala_ = s.scalars(select(Risorsa).where(Risorsa.tipo == 'SALA_OPERATORIA').order_by(Risorsa.id)).first()
    medico = s.scalars(select(Operatore).order_by(Operatore.id)).first()
    p = s.scalars(select(Paziente).order_by(Paziente.id)).first()
    giorno = date.today() + timedelta(days=200 + conta(Appuntamento) % 100)
    inizio = datetime.combine(giorno, datetime.min.time()).replace(hour=8)
    a = Appuntamento(risorsa_id=sala_.id, operatore_id=medico.id, paziente_id=p.id, inizio=inizio,
                     fine=inizio + timedelta(minutes=60), stato='PRENOTATO')
    s.add(a)
    s.commit()
    aid, sid = a.id, sala_.struttura_id
    s.close()
    return aid, giorno, sid


def z_nv_checklist_solo_guardare():
    """Problema 4: con la Sala in «solo guardare» le caselle della checklist si spuntavano, e la pagina diceva «il
    programma non risponde», che non è vero. Ora sono spente; e il 403 dice il suo motivo nel JSON (gestionale.js lo
    mostra: si prova nel browser in prove_accessi_browser.py). Gemelli: con la Sala da modificare e sul PC si spuntano."""
    aid, giorno, sid = intervento_in_sala()
    ospiti(('Sala Guarda', {'sala': 'guarda'}), ('Sala Modifica', {'sala': 'modifica'}))
    url = '/sala/%s?struttura=%d' % (giorno.isoformat(), sid)

    def caselle(t):
        return re.findall(r'<input type="checkbox" name="spunte"[^>]*>', t)
    g = dentro_come('Sala Guarda', '192.168.1.221')
    t = testo(chiedi(g, 'GET', url))
    assert caselle(t) and all(' disabled' in x for x in caselle(t)), ('caselle spuntabili in solo guardare', caselle(t)[:2])
    r = chiedi(g, 'POST', '/appuntamento/%d/checklist' % aid, data={'voce': 'x', 'fatto': '1'},
               headers={'X-Richiesta': 'fetch', 'Origin': RETE})
    assert r.status_code == 403 and 'solo guardare' in (r.json or {}).get('errore', ''), (r.status_code, r.data[:200])
    for t in (testo(chiedi(dentro_come('Sala Modifica', '192.168.1.222'), 'GET', url)), locale().get(url).get_data(as_text=True)):
        assert caselle(t) and not [x for x in caselle(t) if ' disabled' in x], 'gemello: le caselle si spuntano'
    return '%d caselle spente in solo guardare; il 403 dice «solo guardare» nel JSON' % len(caselle(testo(chiedi(g, 'GET', url))))


def z_nv_scarica_degli_ambulatori():
    """Problema 5: chi ha solo Ambulatori trovava nelle tendine «La sala operatoria in Excel», «Ambulatori e sala in
    Excel» e «Tutte le esportazioni», che rispondevano 403 (sono di Statistiche e report). Ora non ci sono; gemelli: con
    Statistiche e report e sul PC ci sono. Le voci degli Ambulatori restano. Dall'unione con la tappa 2 anche la
    linguetta «Esportazioni in Excel» della cornice sparisce a chi non ha Statistiche e report (la condizione per pagina
    del menu: z_menu_per_area); con Statistiche e report e sul PC c'è."""
    _, _, sid = intervento_in_sala()
    ospiti(('Ambulatori Soli', {'ambulatori': 'guarda'}), ('Ambulatori Statistiche', {'ambulatori': 'guarda', 'statistiche': 'guarda'}))
    lunedi = date.today() - timedelta(days=date.today().weekday())
    pagine = ('/ambulatori/settimana/%s?struttura=%d' % (lunedi.isoformat(), sid),
              '/ambulatori/mese/%s?struttura=%d' % (OGGI[:7], sid))

    def corpo(t):                           # la pagina, senza la cornice (le linguette si guardano a parte)
        return t[t.index('<main id="principale">'):]
    soli = dentro_come('Ambulatori Soli', '192.168.1.231')
    stat = dentro_come('Ambulatori Statistiche', '192.168.1.232')
    for url in pagine:
        t = corpo(testo(chiedi(soli, 'GET', url)))
        assert chiedi(soli, 'GET', url).status_code == 200 and '/esportazioni' not in t, (url, 'voci che portano al 403')
        assert '.xlsx' in t, (url, 'le voci degli Ambulatori sono sparite')
        assert '/esportazioni' not in PC_.linguette_html(testo(chiedi(soli, 'GET', url))), (url, 'la linguetta al 403')
        for t2 in (testo(chiedi(stat, 'GET', url)), locale().get(url).get_data(as_text=True)):
            assert '/esportazioni' in corpo(t2), (url, 'gemello: con Statistiche e report le voci ci sono')
            assert '/esportazioni' in PC_.linguette_html(t2), (url, 'gemello: con Statistiche e report la linguetta c\'è')
    for x in re.findall(r'href="(/[^"]+\.xlsx[^"]*)"', corpo(testo(chiedi(soli, 'GET', pagine[0])))):
        assert chiedi(soli, 'GET', x.replace('&amp;', '&')).status_code == 200, x
    return 'settimana e mese: niente esportazioni di Statistiche e report a chi ha solo Ambulatori; i suoi Excel si scaricano'


def z_nv_moduli_spenti_a_chi_guarda():
    """Problema 6: con «solo guardare» i bottoni per salvare restavano, e il clic portava al 403 perdendo quello che si
    era scritto. Ora ogni <form method="post"> che l'utente non può salvare porta data-solo-guardare (gestionale.js ne
    spegne campi e bottoni: nel browser in prove_accessi_browser.py). Oracolo: per ogni area, in «solo guardare» e in
    «modificare», ogni modulo di ogni sua pagina è segnato se e solo se la guardia rifiuterebbe il suo salvataggio
    (decisione(), senza far girare la pagina). Sul PC nessun modulo è mai segnato."""
    valori = dati_per_le_pagine()
    intervento_in_sala()
    voci = [('Moduli %s %s' % (a, lv), {a: lv}) for a in accessi.CODICI_AREE for lv in accessi.LIVELLI_VALIDI]
    ospiti(*voci)
    segnati, liberi, sbagliati, n = 0, 0, [], 0
    for nome, aree in voci:
        n += 1
        ip = '192.168.3.%d' % n
        c = dentro_come(nome, ip)
        cookie = cookie_di(nome)
        area = next(iter(aree))
        for regola in A.app.url_map.iter_rules():
            cens = accessi.CENSIMENTO[regola.endpoint]
            if 'GET' not in regola.methods or cens != area:
                continue
            url = indirizzo(regola, valori)
            r = chiedi(c, 'GET', url)
            if r.status_code != 200 or r.mimetype != 'text/html':
                continue
            for tag, azione in moduli_post(testo(r)):
                azione = azione or url
                try:
                    endpoint, _ = A.app.url_map.bind('x').match(azione.split('?')[0], method='POST')
                except Exception:
                    continue
                if endpoint in accessi.ANCHE_PER or endpoint in accessi.SISTEMA_DENTRO:
                    continue                            # la guardia guarda anche i campi
                d = decisione('POST', azione, cookie)
                negato = d is not None and d[0] == 403
                segnato = 'data-solo-guardare=' in tag
                segnati += segnato
                liberi += not segnato
                if segnato != negato:
                    sbagliati.append((nome, url, azione, segnato, d[0] if d else None))
    assert not sbagliati, '%d moduli segnati male: %s' % (len(sbagliati), sbagliati[:5])
    assert segnati >= 30 and liberi >= 30, (segnati, liberi)
    pc = 0
    for url in ('/appuntamento/%d' % valori['aid'], '/pazienti/%d' % valori['pid'], '/cassa/listino', '/conferme',
                '/giorno/%s' % OGGI, '/anagrafiche/prestazioni/1'):
        t = locale().get(url).get_data(as_text=True)
        pc += len(moduli_post(t))
        assert 'data-solo-guardare' not in t, ('sul PC un modulo segnato', url)
    assert pc >= 5, pc
    return '%d moduli segnati e %d liberi, tutti come la guardia; sul PC %d moduli, nessuno segnato' % (segnati, liberi, pc)


def z_nv_appunti_solo_con_la_segreteria():
    """Problema 7: chi ha solo l'Agenda vedeva nella griglia del giorno (e nell'elenco) gli appunti da confermare della
    Segreteria, con nome, telefono e nota. Ora no; gemelli: con la Segreteria e sul PC sì."""
    s = A.Sessione()
    s.add(Appunto(testo='Appunto di prova Fintini', giorno=date.today(), cognome='Appuntati', nome='Prova',
                  telefono='3331110099', struttura_id=1))
    s.commit()
    s.close()
    ospiti(('Agenda Sola', {'agenda': 'guarda'}), ('Agenda Segreteria', {'agenda': 'guarda', 'segreteria': 'guarda'}))
    sola = dentro_come('Agenda Sola', '192.168.1.241')
    con = dentro_come('Agenda Segreteria', '192.168.1.242')
    for url in ('/giorno/%s' % OGGI, '/giorno/%s/elenco' % OGGI):
        t = testo(chiedi(sola, 'GET', url))
        assert 'Agenda' and 'Da confermare per questo giorno' not in t and '3331110099' not in t, (url, 'appunti a chi ha solo l\'Agenda')
        for t2 in (testo(chiedi(con, 'GET', url)), locale().get(url).get_data(as_text=True)):
            assert 'Da confermare per questo giorno' in t2 and '3331110099' in t2, (url, 'gemello: gli appunti ci sono')
    return 'griglia ed elenco del giorno: appunti da confermare solo con la Segreteria'


def z_nv_copia_rimessa():
    """Problema 9 (medio): una copia di ieri rimessa riportava indietro utenti, password, aree e accensione della rete,
    senza dirlo (chi era stato spento rientrava con la password di ieri). Decisione (piano/ESECUZIONE.md): gli accessi
    non tornano indietro con la copia. Dalle Impostazioni (ripristino) e dopo una riparazione (app.dopo_riparazione,
    dal file accessi-rete.json) e all'avvio (copia_rimessa). Gemelli: i dati della clinica tornano indietro davvero (la
    nota del giorno scritta dopo la copia sparisce); senza il file la rete resta spenta."""
    import backup
    ospiti(('Copia Esempietti', {'agenda': 'modifica'}))
    imposta(rete_accesa='1')
    c = locale()
    s = A.Sessione()
    s.add(NotaGiorno(struttura_id=1, data=date.today() + timedelta(days=300), testo='nota dopo la copia Fintini'))
    s.commit()
    s.close()
    percorso_db = A.Sessione.motore.url.database
    copia = backup.esegui(percorso_db, os.path.join(PROVVISORIA, 'copie'))
    # dopo la copia: la nota (dato della clinica) e gli accessi cambiano
    s = A.Sessione()
    s.add(NotaGiorno(struttura_id=1, data=date.today() + timedelta(days=301), testo='nota scritta dopo Fintini'))
    s.commit()
    s.close()
    utenti = utenti_salvati()
    u = accessi.trova(utenti, 'Copia Esempietti')
    u['attivo'] = False
    u['hash'] = accessi.generate_password_hash('password di oggi lunga')
    imposta(rete_utenti=json.dumps(utenti), rete_accesa='')
    s = A.Sessione()
    accessi.ricorda(s)
    prima = accessi.istantanea(s)
    s.close()
    imposta(backup_cartella=os.path.join(PROVVISORIA, 'copie'))
    PM.segna(c)
    r = c.post('/impostazioni/ripristina', data={'nome': os.path.basename(copia), 'conferma': '1'},
               headers={'Origin': PC}, base_url=PC)
    assert r.status_code == 302, r.status_code
    s = A.Sessione()
    dopo = accessi.istantanea(s)
    note = [n.testo for n in s.scalars(select(NotaGiorno))]
    s.close()
    assert 'nota scritta dopo Fintini' not in note and 'nota dopo la copia Fintini' in note, 'gemello: la copia non è tornata'
    assert dopo == prima, 'il ripristino ha riportato indietro gli accessi: %s' % [k for k in prima if prima[k] != dopo[k]]
    testi = PM.avvisi(c)
    assert 'Ripristinata la copia' in testi and 'non tornano indietro con la copia' in testi, testi
    u = accessi.trova(utenti_salvati(), 'Copia Esempietti')
    assert u['attivo'] is False and leggi('rete_accesa') == '', 'spento oggi: con la copia di ieri rientrerebbe'
    # la riparazione (il custode): la copia rimessa sopra il database, poi dopo_riparazione, dal file
    backup.metti_al_posto(copia, percorso_db, A.Sessione.motore)
    assert leggi('rete_accesa') == '1', 'gemello: la copia aveva la rete accesa'
    A.dopo_riparazione()
    s = A.Sessione()
    assert accessi.istantanea(s) == prima, 'la riparazione ha riportato indietro gli accessi'
    s.close()
    # senza il file (non si sa com'erano): la rete resta spenta
    backup.metti_al_posto(copia, percorso_db, A.Sessione.motore)
    os.remove(os.path.join(PROVVISORIA, accessi.FILE_RETE))
    assert accessi.rimetti(A.Sessione, accessi.dal_file()) == 'spenta' and leggi('rete_accesa') == ''
    # all'avvio con una copia rimessa (autoripara.all_avvio): dal file, scritto con gli accessi di oggi
    imposta(**prima)
    s = A.Sessione()
    accessi.ricorda(s)
    s.close()
    backup.metti_al_posto(copia, percorso_db, A.Sessione.motore)
    accessi.all_avvio(A.app, A.Sessione, PROVVISORIA, prove=0, copia_rimessa=True)
    s = A.Sessione()
    try:
        assert accessi.istantanea(s)['rete_accesa'] == '' and accessi.trova(json.loads(
            accessi.istantanea(s)['rete_utenti']), 'Copia Esempietti')['attivo'] is False, 'all\'avvio la copia ha vinto'
    finally:
        s.close()
    accessi.ascolto.spegni()
    return 'ripristino, riparazione e avvio: gli accessi restano quelli di adesso; la nota torna indietro; senza file rete spenta'


def z_nv_file_accessi_rovinato():
    """Verifica del secondo giro (22/11, attacco nuovo): accessi-rete.json rovinato (scritto a metà, vuoto, con un'altra
    forma) quando si rimette una copia all'avvio. Non si sa com'erano gli accessi: la rete resta spenta (la copia l'aveva
    accesa), il programma va avanti e il file torna leggibile, riscritto dal database. Senza questa prova un dal_file()
    che non riconosce il file rovinato faceva vincere la copia (rete riaccesa con gli utenti di ieri) e nessuna prova
    cadeva. Gemello: con il file buono restano gli accessi del file, anche l'utente aggiunto dopo la copia."""
    import backup
    ospiti(('Rovinato Esempietti', {'agenda': 'modifica'}))
    imposta(rete_accesa='1', rete_porta=str(porta_libera()))       # mai la 5080, anche se la prova cade a metà
    percorso_db = A.Sessione.motore.url.database
    copia = backup.esegui(percorso_db, os.path.join(PROVVISORIA, 'copie-rovinato'))
    ospiti(('Dopo Esempietti', {'agenda': 'guarda'}))
    s = A.Sessione()
    accessi.ricorda(s)
    s.close()
    file_rete = os.path.join(PROVVISORIA, accessi.FILE_RETE)
    try:
        backup.metti_al_posto(copia, percorso_db, A.Sessione.motore)
        assert accessi.trova(utenti_salvati(), 'Dopo Esempietti') is None, 'gemello: la copia non ha l\'utente di dopo'
        assert accessi.rimetti(A.Sessione, accessi.dal_file()) == 'rimessi', 'gemello: il file buono non è servito'
        assert accessi.trova(utenti_salvati(), 'Dopo Esempietti') and leggi('rete_accesa') == '1', 'gemello'
        buono = open(file_rete, encoding='utf-8').read()
        for rovinato in (buono[:len(buono) // 2], '', '[1, 2]', json.dumps(dict(json.loads(buono), rete_utenti=[]))):
            with open(file_rete, 'w', encoding='utf-8') as f:
                f.write(rovinato)
            backup.metti_al_posto(copia, percorso_db, A.Sessione.motore)
            assert leggi('rete_accesa') == '1', 'gemello: la copia ha la rete accesa'
            accessi.all_avvio(A.app, A.Sessione, PROVVISORIA, prove=0, copia_rimessa=True)
            assert leggi('rete_accesa') == '' and not accessi.ascolto.acceso(), \
                'file rovinato (%r): la copia ha riacceso la rete' % rovinato[:30]
            s = A.Sessione()
            try:
                assert accessi.dal_file() == accessi.istantanea(s), 'il file non è stato riscritto dal database'
            finally:
                s.close()
    finally:
        accessi.ascolto.spegni()
    return 'file rovinato in 4 modi: rete spenta e file riscritto; gemello: il file buono rimette gli accessi'


def z_nv_firewall():
    """Problema 10 (medio): dopo «Annulla» o «No» Windows crea regole che BLOCCANO il programma, e una regola che blocca
    vince su quelle che permettono (documentazione di Microsoft): il comando «add rule ... action=allow» da solo non apriva
    niente. Ora la pagina spiega il blocco e, per l'assistenza, dà il comando che toglie tutte le regole del programma
    (con il suo percorso vero) e quello che lo lascia ricevere solo sulla porta della rete, reti private e di dominio.
    Gemello: senza Annulla non serve niente (punto 1 della pagina)."""
    cmd = accessi.comandi_firewall(5123, r'C:\Program Files\Gestionale Agende\Gestionale.exe')
    assert cmd['togli'] == r'netsh advfirewall firewall delete rule name=all program="C:\Program Files\Gestionale Agende\Gestionale.exe"'
    assert cmd['metti'] == (r'netsh advfirewall firewall add rule name="Gestionale Agende (rete della clinica)" dir=in '
                            r'action=allow program="C:\Program Files\Gestionale Agende\Gestionale.exe" protocol=TCP '
                            r'localport=5123 profile=private,domain'), cmd['metti']
    assert accessi.percorso_programma() == os.path.abspath(sys.executable)
    t = locale().get('/configura/accessi').get_data(as_text=True)
    assert 'bloccano</b> il programma' in t and '«Annulla» o «No»' in t, 'la pagina non spiega il blocco'
    assistenza = t[t.index('id="firewall-assistenza"'):]
    assistenza = assistenza[:assistenza.index('</details>')]
    assert 'delete rule name=all program=&#34;' in assistenza or 'delete rule name=all program=&quot;' in assistenza or \
        'delete rule name=all program="' in assistenza, assistenza[:300]
    assert 'profile=private,domain' in assistenza and 'Esegui come amministratore' in assistenza
    assert 'action=allow protocol=TCP localport' not in t, 'il comando di prima, che con le regole di blocco non basta'
    return 'il blocco spiegato; togli (name=all program=…) e metti (program, porta, private,domain) per l\'assistenza'


def z_nv_spegnere_fa_uscire():
    """Problema 11: spegnere l'accesso dalla pagina non faceva uscire chi era dentro; riacceso entro 4 ore, era di nuovo
    dentro senza password. Ora spegnere fa uscire tutti (e lo dice). Gemello: senza spegnere chi è dentro resta dentro;
    un riavvio del programma (sessioni.carica) non fa uscire nessuno."""
    ospiti(('Dentro Esempietti', {'agenda': 'guarda'}))
    c = dentro_come('Dentro Esempietti', '192.168.1.251')
    assert chiedi(c, 'GET', '/oggi').status_code == 200
    time.sleep(0.1)
    accessi.sessioni._salva(forza=True)
    accessi.sessioni.carica(PROVVISORIA)          # come un riavvio
    assert chiedi(c, 'GET', '/oggi').status_code == 200, 'gemello: dopo un riavvio chi era dentro resta dentro'
    pc = PM.segna(locale())
    pc.post('/configura/accessi', data={'azione': 'rete', 'porta': '5080'}, headers={'Origin': PC}, base_url=PC)
    testi = PM.avvisi(pc)
    assert 'Chi era entrato è uscito' in testi, testi
    imposta(rete_accesa='1')
    r = chiedi(c, 'GET', '/oggi')
    assert r.status_code == 302 and '/accesso' in r.headers['Location'], ('spenta e riaccesa: ancora dentro', r.status_code)
    return 'spenta: tutti fuori, e il messaggio lo dice; un riavvio no'


def z_nv_porta_occupata_e_riquadro():
    """Problema 12: con la rete accesa sulla porta A e la B occupata, il riquadro rosso «La porta B è già usata» restava
    per sempre sotto «Acceso». Ora il riquadro rosso solo se la rete deve essere accesa e non è in ascolto (gemello: lì
    c'è). L'errore della volta va nel messaggio (q_prese_vere: errore_cambio)."""
    ascolto = accessi.ascolto
    salvato = ascolto.errore
    try:
        ascolto.errore = 'La porta 5999 è già usata da un altro programma: sceglierne un\'altra.'
        imposta(rete_accesa='1')
        t = locale().get('/configura/accessi').get_data(as_text=True)
        assert 'non in ascolto' in t and 'La porta 5999 è già usata' in t, 'gemello: acceso nelle impostazioni, non in ascolto'
        imposta(rete_accesa='')
        t = locale().get('/configura/accessi').get_data(as_text=True)
        assert 'La porta 5999 è già usata' not in t, 'spenta: il riquadro rosso resta'
    finally:
        ascolto.errore = salvato
    return 'il riquadro rosso solo con la rete accesa e non in ascolto'


def z_nv_nuovo_utente_rifiutato():
    """Problema 13: un nuovo utente rifiutato (password con il nome, nome doppio o non valido) faceva tornare la pagina
    in cima con il modulo vuoto: nome e 12 scelte da rifare. Ora la pagina torna con quello che si era scritto (tranne la
    password) e il motivo accanto al modulo; la password del primo accesso si vede mentre la si scrive. Gemello: con una
    password buona l'utente c'è."""
    pc = locale()
    dati = {'azione': 'nuovo', 'nome': 'Ornella Fantasia', 'password': 'Fantasia del mare', 'area_agenda': 'modifica',
            'area_pazienti': 'modifica', 'area_segreteria': 'modifica', 'area_cassa': 'guarda'}
    r = pc.post('/configura/accessi', data=dati, headers={'Origin': PC}, base_url=PC)
    t = testo(r)
    assert r.status_code == 200 and 'id="errore-nuovo"' in t and 'nome dell&#39;utente' in t, r.status_code
    modulo = t[t.index('id="nuovo-utente"'):]
    assert 'value="Ornella Fantasia"' in modulo and 'Fantasia del mare' not in t, 'il nome perso, o la password ripetuta'
    for area, lv in (('agenda', 'modifica'), ('pazienti', 'modifica'), ('segreteria', 'modifica'), ('cassa', 'guarda')):
        assert re.search(r'name="area_%s" value="%s" checked' % (area, lv), modulo), (area, 'scelta persa')
    assert 'action="/configura/accessi#nuovo-utente"' in t and 'id="nuovo-password" type="text"' in t
    assert accessi.trova(utenti_salvati(), 'Ornella Fantasia') is None
    dati['password'] = 'conchiglia rossa sul molo'
    r = pc.post('/configura/accessi', data=dati, headers={'Origin': PC}, base_url=PC)
    u = accessi.trova(utenti_salvati(), 'Ornella Fantasia')
    assert r.status_code == 302 and u and u['aree'] == {'agenda': 'modifica', 'pazienti': 'modifica',
                                                       'segreteria': 'modifica', 'cassa': 'guarda'}, (r.status_code, u)
    assert ('aperto=%s' % u['id']) in r.headers['Location'], 'il riquadro dell\'utente nuovo non resta aperto'
    t = pc.get(r.headers['Location'], base_url=PC).get_data(as_text=True)
    assert re.search(r'<details class="riquadro utente-accessi" id="utente-%s"[^>]* open>' % u['id'], t)
    return 'rifiutato: nome e quattro parti rimasti, password no, motivo accanto al modulo; buono: aggiunto e aperto'


def z_nv_rifiuto_e_pagina_per_la_segreteria():
    """Problema 14: la pagina 403 mandava a «Configura → Aree e accessi», che nel menu di allora non c'era (dall'unione
    con la tappa 2 è la settima linguetta di Configura, e il percorso è di nuovo quello); nella pagina, in mezzo
    alle scelte di tutti i giorni, c'erano Caddy, Caddyfile, netsh e «Altri nomi»; ogni utente era una tabella aperta di 13
    righe; la barra «Entrato da un altro PC» non aveva stile. Ora: il percorso vero (gemello: in Impostazioni c'è il
    bottone «Aree e accessi»), le cose da tecnico in riquadri chiusi «Per l'assistenza», gli utenti chiusi con le parti in
    una riga, la barra con il suo stile in veste.css."""
    ospiti(('Rifiuto Esempietti', {'agenda': 'guarda'}))
    c = dentro_come('Rifiuto Esempietti', '192.168.1.252')
    assert re.search(r'<details class="per-assistenza" open', locale().get('/configura/accessi').get_data(as_text=True)), \
        'gemello: con altri nomi scritti il loro riquadro resta aperto'
    imposta(rete_nomi='')
    t = testo(chiedi(c, 'GET', '/pazienti'))
    assert 'Configura → Aree e accessi' in t, 'il percorso della pagina nel rifiuto'
    assert 'href="%s"' % per('accessi.pagina') in PC_.linguette_html(locale().get('/anagrafiche').get_data(as_text=True)), \
        'gemello: il percorso è vero (Aree e accessi è una linguetta di Configura)'
    assert 'href="%s"' % per('accessi.pagina') in locale().get('/impostazioni').get_data(as_text=True), \
        'e il bottone in Impostazioni resta'
    assert 'v-utente-rete' in testo(chiedi(c, 'GET', '/oggi'))
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'veste.css'), encoding='utf-8') as f:
        assert '.v-utente-rete {' in f.read()
    t = locale().get('/configura/accessi').get_data(as_text=True)
    chiusi = re.findall(r'<details class="per-assistenza"[^>]*>(.*?)</details>', t, re.S)
    for parola in ('Caddyfile', 'netsh', 'Altri nomi di questo PC'):
        fuori = t
        for x in chiusi:
            fuori = fuori.replace(x, '')
        assert parola in t and parola not in fuori, (parola, 'fuori da «Per l\'assistenza»')
    assert not re.search(r'<details class="per-assistenza" open', t), 'di partenza «Per l\'assistenza» è chiuso'
    u = accessi.trova(utenti_salvati(), 'Rifiuto Esempietti')
    m = re.search(r'<details class="riquadro utente-accessi" id="utente-%s"([^>]*)>\s*<summary>(.*?)</summary>' % u['id'], t, re.S)
    assert m and ' open' not in m.group(1) and 'Agenda (solo guardare)' in m.group(2), m.group(0)[:300] if m else None
    return 'il percorso vero nel rifiuto; Caddy, netsh e nomi in «Per l\'assistenza»; utenti chiusi; la barra con lo stile'


def z_nv_statistiche_e_report():
    """Decisione rimandata nel primo giro, ora il predefinito (piano/ESECUZIONE.md, Giovanni può cambiarlo): in
    «Statistiche e report» dagli altri PC nomi, telefoni ed email dei pazienti solo a chi ha anche Pazienti o Agenda,
    importi e incassi solo a chi ha anche la Cassa, nelle pagine e negli Excel, con le colonne tolte (non vuote). Gemelli:
    con le aree in più ci sono, sul PC tutto (il PC uguale al ramo principale lo dice confronta_rami)."""
    import io as _io
    from openpyxl import load_workbook
    s = A.Sessione()
    p = Paziente(cognome='Statistici', nome='Canarino', telefono='3337770011', email='statistici@example.com')
    s.add(p)
    s.flush()
    stanza = s.scalars(select(Risorsa).where(Risorsa.tipo == 'AMBULATORIO').order_by(Risorsa.id)).first()
    medico = s.scalars(select(Operatore).order_by(Operatore.id)).first()
    medico.email = medico.email or 'medico.prova@example.com'
    prest = s.scalars(select(Prestazione).order_by(Prestazione.id)).first()
    inizio = datetime.combine(date.today(), datetime.min.time()).replace(hour=6, minute=5)
    while s.scalars(select(Appuntamento.id).where(Appuntamento.risorsa_id == stanza.id, Appuntamento.inizio == inizio)).first():
        inizio += timedelta(minutes=5)
    s.add(Appuntamento(risorsa_id=stanza.id, operatore_id=medico.id, prestazione_id=prest.id, paziente_id=p.id,
                       inizio=inizio, fine=inizio + timedelta(minutes=5), stato='ARRIVATO', importo_cent=12345,
                       convenzione='Convenzione Inventata', note='richiamare Statistici'))
    sid = stanza.struttura_id
    s.commit()
    s.close()
    ospiti(('Statistiche Sole', {'statistiche': 'guarda'}),
           ('Statistiche Cassa', {'statistiche': 'guarda', 'cassa': 'guarda'}),
           ('Statistiche Pazienti', {'statistiche': 'guarda', 'pazienti': 'guarda'}),
           ('Statistiche Agenda', {'statistiche': 'guarda', 'agenda': 'guarda'}))
    def celle(dati):
        wb = load_workbook(_io.BytesIO(dati))
        return ' | '.join(str(c.value) for ws in wb.worksheets for r in ws.iter_rows() for c in r if c.value is not None)
    # per ogni pagina: (indirizzo, cosa dice che ci sono i pazienti, cosa dice che ci sono gli importi); le statistiche
    # non hanno pazienti (solo numeri)
    pagine = {
        'statistiche': ('/statistiche?struttura=%d&dal=%s&al=%s' % (sid, OGGI, OGGI), (),
                        ('euro indicati', '<th>Importi</th>')),
        'statistiche.xlsx': ('/statistiche/excel?struttura=%d&dal=%s&al=%s' % (sid, OGGI, OGGI), (),
                             ('Importi indicati (EUR)', 'Incassati (EUR)', 'Importi (EUR)')),
        'riepilogo': ('/riepilogo-medici/%s?struttura=%d' % (MESE, sid), ('Statistici',),
                      ('123,45', 'Convenzione Inventata', 'Importo</th>', 'importi previsti')),
        'riepilogo.xlsx': ('/riepilogo-medici/%s/excel?struttura=%d' % (MESE, sid),
                           ('Statistici', '3337770011', 'richiamare Statistici', 'Paziente | Telefono'),
                           ('123.45', 'Convenzione Inventata', 'Importi previsti', 'Convenzione | Importo')),
        'giorno.xlsx': ('/esportazioni/giorno/tutto/%s.xlsx?struttura=%d' % (OGGI, sid),
                        ('Statistici', '3337770011', 'statistici@example.com', 'richiamare Statistici', 'PAZIENTE | TELEFONO'),
                        ('123.45', 'Convenzione Inventata', 'IMPORTO')),
    }
    n = 0
    for nome, con_paz, con_soldi in (('Statistiche Sole', False, False), ('Statistiche Cassa', False, True),
                                     ('Statistiche Pazienti', True, False), ('Statistiche Agenda', True, False),
                                     (None, True, True)):
        c = locale() if nome is None else dentro_come(nome, '192.168.4.%d' % (n + 1))
        n += 1
        for chiave, (url, di_pazienti, di_soldi) in pagine.items():
            r = chiedi(c, 'GET', url)
            assert r.status_code == 200, (nome, url, r.status_code)
            testi = celle(r.data) if chiave.endswith('.xlsx') else testo(r)
            for x in di_pazienti:
                assert (x in testi) == con_paz, (nome or 'PC', chiave, x, 'gemello: ci sono' if con_paz else 'pazienti')
            for x in di_soldi:
                assert (x in testi) == con_soldi, (nome or 'PC', chiave, x, 'gemello: ci sono' if con_soldi else 'importi')
    return 'pagine ed Excel di Statistiche e report: pazienti con Pazienti o Agenda, importi con la Cassa, colonne tolte'


# ======================================================= il menu della tappa 2 e gli accessi insieme (unione, 22/11)

def collegamenti_della_cornice(t):
    """Gli indirizzi che la cornice di una pagina offre: il menu (con le voci della tendina Aiuto e i collegamenti
    nascosti dei tasti) e le linguette; non '#' (le voci della guida sullo schermo)."""
    pezzi = PC_.menu_html(t) + PC_.linguette_html(t)
    return {h.replace('&amp;', '&') for h in re.findall(r'href="(/[^"#]*)"', pezzi)}


def area_dell_indirizzo(url):
    """L'area che serve alla pagina di un indirizzo dalla rete (accessi.area_della_pagina, dal censimento)."""
    with A.app.test_request_context():
        endpoint, _ = A.app.url_map.bind('x').match(urllib.parse.urlsplit(url).path, method='GET')
    return accessi.area_della_pagina(endpoint)


def segui(c, url, volte=5):
    """GET con i rimandi interni seguiti (le pagine come /personale/turni rimandano alla loro vista): la risposta finale."""
    r = chiedi(c, 'GET', url)
    while r.status_code in (301, 302, 303) and volte:
        dove_ = urllib.parse.urlsplit(r.headers['Location'])
        r = chiedi(c, 'GET', dove_._replace(scheme='', netloc='').geturl())
        volte -= 1
    return r


def giro_della_cornice(c, inizio, massimo=300):
    """Dalla pagina «inizio», ogni indirizzo del menu e delle linguette, e così via dalle pagine che si aprono: (stato di
    ogni pagina vista, collegamenti della cornice di ogni pagina HTML)."""
    stati, cornici, coda = {}, {}, [inizio]
    while coda and len(stati) < massimo:
        url = coda.pop(0)
        if url in stati:
            continue
        r = segui(c, url)
        stati[url] = r.status_code
        if r.status_code == 200 and r.mimetype == 'text/html':
            cornici[url] = collegamenti_della_cornice(testo(r))
            coda += sorted(cornici[url] - set(stati))
    return stati, cornici


def problemi_del_menu_per_area(area, ip):
    """Un utente con la sola «area» (da guardare), dalla rete: ogni voce e linguetta della cornice di ogni pagina
    raggiunta apre una pagina 200 per lui; almeno una porta alla sua area; e niente di quello che sul PC c'è e che lui
    può aprire è tolto. Torna (problemi, pagine viste)."""
    nome = 'Menu %s' % area
    c = dentro_come(nome, ip)
    inizio = chiedi(c, 'GET', '/').headers['Location']
    inizio = urllib.parse.urlsplit(inizio)._replace(scheme='', netloc='').geturl()
    stati, cornici = giro_della_cornice(c, inizio)
    p = ['%s: %s risponde %d' % (area, u, s) for u, s in sorted(stati.items()) if s != 200]
    offerti = set().union(*cornici.values()) if cornici else set()
    if not offerti:
        p.append('%s: nessuna voce nel menu' % area)
    elif not [u for u in offerti if area_dell_indirizzo(u) == area]:
        p.append('%s: nessuna voce porta alla sua area: %s' % (area, sorted(offerti)[:6]))
    pc = locale()
    for url, suoi in sorted(cornici.items()):
        if url == inizio and not suoi:
            continue
        for h in sorted(collegamenti_della_cornice(segui(pc, url).get_data(as_text=True)) - suoi):
            if segui(c, h).status_code == 200:
                p.append('%s: su %s la cornice non offre %s, che per lui si apre' % (area, url, h))
    return p, len(stati)


def z_menu_per_area():
    """Unione della tappa 2 con gli accessi: dalla rete il menu, le linguette, la tendina Aiuto e i collegamenti nascosti
    dei tasti mostrano solo le pagine dell'utente (la condizione per pagina di menu.py, accessi.si_apre). Per ogni area,
    un utente che ha solo quella: partendo dalla sua prima pagina e seguendo ogni voce e linguetta della cornice, ogni
    pagina risponde 200; almeno una voce porta alla sua area; niente che sul PC c'è e che lui può aprire è tolto. Sul PC
    il menu è identico a quello senza la condizione (tutte le voci, anche «Aree e accessi» in Configura). Gemello: tolta la
    condizione per pagina, dalla rete le voci delle altre aree portano al 403."""
    intervento_in_sala()
    ospiti(*[('Menu %s' % a, {a: 'guarda'}) for a in accessi.CODICI_AREE])
    problemi, viste = [], 0
    for i, area in enumerate(accessi.CODICI_AREE):
        p, n = problemi_del_menu_per_area(area, '192.168.6.%d' % (i + 1))
        problemi += p
        viste += n
    assert not problemi, problemi[:6]
    # sul PC: tutte le voci, come senza la condizione per pagina (il menu della tappa 2)
    pc, pagine = locale(), ('/oggi', '/anagrafiche', '/configura/accessi', '/invii', '/conferme',
                            '/esportazioni?data=%s&struttura=1' % OGGI, '/aiuto')
    con = {u: pc.get(u).get_data(as_text=True) for u in pagine}
    prima, MENU.SI_APRE = MENU.SI_APRE, None
    try:
        senza = {u: pc.get(u).get_data(as_text=True) for u in pagine}
        gemello, _ = problemi_del_menu_per_area('agenda', '192.168.6.99')
    finally:
        MENU.SI_APRE = prima
    assert prima is accessi.si_apre, 'app.py non ha dato al menu la condizione per pagina (accessi.si_apre)'
    for u in pagine:
        assert con[u] == senza[u], ('sul PC il menu cambia con la condizione per pagina', u)
    linguette = [p_ for p_, _, _ in PC_.linguette(con['/anagrafiche'])]
    assert linguette == ['Anagrafiche', 'Strutture del gruppo', 'Email e WhatsApp', 'Importa da Excel', 'Impostazioni',
                         'Aggiornamenti', 'Aree e accessi'], linguette
    assert gemello and any('403' in x for x in gemello), ('gemello: senza la condizione le voci delle altre aree '
                                                         'dovrebbero portare al 403', gemello[:3])
    return '%d aree, %d pagine viste dalla rete: ogni voce e linguetta si apre, la sua c\'è; sul PC tutte (7 linguette ' \
           'in Configura); gemello: senza la condizione %d voci al 403' % (len(accessi.CODICI_AREE), viste, len(gemello))


def z_menu_voce_al_posto():
    """Una voce la cui pagina non si apre porta alla prima delle sue linguette che si apre, senza il suo tasto (Configura
    a chi ha solo Email e WhatsApp: alle Email e WhatsApp; Ambulatori a chi ha solo Statistiche e report: alle
    Esportazioni in Excel, che spariscono a chi non ha Statistiche); senza linguette che si aprono la voce non c'è. Sul PC
    le voci di sempre, con i loro tasti."""
    ospiti(('Voce Email', {'comunicazioni': 'guarda'}), ('Voce Statistiche', {'statistiche': 'guarda'}),
           ('Voce Agenda', {'agenda': 'modifica'}), ('Voce Ambulatori', {'ambulatori': 'guarda'}))
    def voce(t, guida):
        m = re.search(r'<a (?:data-tasto="(\w)" )?href="([^"]*)"[^>]*data-guida="%s"' % guida, PC_.menu_html(t))
        return (m.group(2).replace('&amp;', '&'), m.group(1)) if m else None
    t = testo(chiedi(dentro_come('Voce Email', '192.168.7.1'), 'GET', '/invii'))
    assert voce(t, 'menu-configura') == ('/invii', None), voce(t, 'menu-configura')
    assert PC_.voce_accesa(t, 'menu-configura') and PC_.linguetta_accesa(t) == 'Email e WhatsApp'
    assert [x for x, _, _ in PC_.linguette(t)] == ['Email e WhatsApp'], PC_.linguette(t)
    st = dentro_come('Voce Statistiche', '192.168.7.2')
    t = testo(chiedi(st, 'GET', '/statistiche'))
    assert voce(t, 'menu-ambulatori')[0].startswith('/esportazioni?'), voce(t, 'menu-ambulatori')
    am = testo(chiedi(dentro_come('Voce Ambulatori', '192.168.7.4'), 'GET', '/ambulatori/settimana/%s?struttura=1' % OGGI))
    assert '/esportazioni' not in am and [x for x, _, _ in PC_.linguette(am)] == [
        'Pianificazione della settimana', 'Programmazione del mese', 'Riepilogo live', 'Riepilogo del periodo'], \
        PC_.linguette(am)
    ag = testo(chiedi(dentro_come('Voce Agenda', '192.168.7.3'), 'GET', '/oggi'))
    assert voce(ag, 'menu-segreteria') == ('/disponibilita?struttura=1', None), voce(ag, 'menu-segreteria')
    assert voce(ag, 'menu-giorno')[1] == 'g' and 'data-tasto="e"' in PC_.menu_html(ag), 'Agenda: i tasti G ed E restano'
    for guida in ('menu-pazienti', 'menu-turni', 'menu-configura', 'menu-dove'):
        assert guida not in PC_.menu_html(ag), (guida, 'voce di un\'area che non ha')
    t = locale().get('/oggi').get_data(as_text=True)
    assert voce(t, 'menu-segreteria') == ('/conferme?struttura=1', 'c') and voce(t, 'menu-configura') == ('/anagrafiche', None), \
        ('gemello: sul PC le voci di sempre', voce(t, 'menu-segreteria'), voce(t, 'menu-configura'))
    return 'Configura → Email e WhatsApp, Ambulatori → Esportazioni, Segreteria → Prima disponibilità (senza il tasto C); ' \
           'le voci senza pagine non ci sono; sul PC come sempre'


def z_cornice_dalla_rete():
    """La cornice nuova dalla rete: nome, «La mia password» ed «Esci» nella barra in alto (data-cornice="barra"), non
    sopra la pagina; l'accesso, la propria password, il rifiuto e il Modo schermo senza cornice (e senza quella riga);
    il rifiuto dice dove si cambia: «Configura → Aree e accessi», la settima linguetta di Configura sul PC (gemello: il
    percorso è vero), che dalla rete non c'è nemmeno per chi ha tutte le parti."""
    ospiti(('Cornice Rete', {'agenda': 'modifica', 'ambulatori': 'guarda'}))
    c = dentro_come('Cornice Rete', '192.168.8.1')
    t = testo(chiedi(c, 'GET', '/oggi'))
    barra = re.search(r'<header class="v-barra" data-cornice="barra">(.*?)</header>', t, re.S)
    assert barra and entrato_come(barra.group(1), 'Cornice Rete') and \
        'action="/esci"' in barra.group(1) and '/accesso/password' in barra.group(1), 'la riga dell\'utente nella barra'
    assert t.count('class="utente-rete v-utente-rete"') == 1 and 'Entrato da un altro PC' not in t[t.index('<main'):]
    assert 'Entrato da un altro PC' not in locale().get('/oggi').get_data(as_text=True), 'gemello: sul PC no'
    senza = {'/accesso/password': chiedi(c, 'GET', '/accesso/password'), '/pazienti': chiedi(c, 'GET', '/pazienti'),
             '/riepilogo-live?schermo=1': chiedi(c, 'GET', '/riepilogo-live?schermo=1'),
             '/accesso': chiedi(rete(ip='192.168.8.2'), 'GET', '/accesso')}
    for url, r in senza.items():
        assert r.status_code in (200, 403), (url, r.status_code)
        assert 'data-cornice=' not in testo(r) and not PC_.CON_MENU.search(testo(r)) and \
            'Entrato da un altro PC' not in testo(r), (url, 'con la cornice')
    assert 'data-cornice="barra"' in testo(chiedi(c, 'GET', '/riepilogo-live')), 'gemello: senza schermo la cornice c\'è'
    r = senza['/pazienti']
    assert rifiutata(r) and 'Configura → Aree e accessi' in testo(r) and 'Impostazioni →' not in testo(r)
    assert accessi.PERCORSO_PAGINA in accessi.PAGINA_ATTESA % (1, 'o')
    pc = locale().get('/anagrafiche').get_data(as_text=True)
    assert ('Aree e accessi', '/configura/accessi', False) in PC_.linguette(pc), 'gemello: il percorso è vero'
    t = locale().get('/configura/accessi').get_data(as_text=True)
    assert PC_.voce_accesa(t, 'menu-configura') and PC_.linguetta_accesa(t) == 'Aree e accessi'
    assert 'Configura</span><span>Aree e accessi</span>' in t, 'il percorso nella barra in alto'
    c3 = rete(ip='192.168.8.3')
    entra(c3, 'Tutto Provolo')
    t = testo(chiedi(c3, 'GET', '/anagrafiche'))
    assert [x for x, _, _ in PC_.linguette(t)] == ['Anagrafiche', 'Strutture del gruppo', 'Email e WhatsApp',
                                                    'Importa da Excel'], PC_.linguette(t)
    # «Aree e accessi» ha anche la sua condizione (solo sul PC principale): vale anche senza la condizione per pagina
    prima, MENU.SI_APRE = MENU.SI_APRE, None
    try:
        nomi = [x for x, _, _ in PC_.linguette(testo(chiedi(c3, 'GET', '/anagrafiche')))]
    finally:
        MENU.SI_APRE = prima
    assert 'Aree e accessi' not in nomi and 'Impostazioni' in nomi, ('«Aree e accessi» senza la sua condizione', nomi)
    return 'barra con Esci al suo posto; accesso, password, rifiuto e Modo schermo senza cornice; percorso «%s»' % \
        accessi.PERCORSO_PAGINA


# ====================================================== revisione dell'unione con la tappa 2 (problemi A, B, C, D)
def z_rv_guida_con_le_immagini_solo_con_la_guida():
    """Problema A: il giro della guida sullo schermo (dalla cornice: Aiuto → Guida di questa pagina, l'invito in Oggi)
    finiva sempre con «La guida con le immagini», verso /aiuto/<guida>, che è di «Guida e aiuto»: chi non l'ha finiva su un
    403. Ora passi.json dà l'articolo vuoto, e guida.js mostra il collegamento solo se c'è. Per ogni guida: senza la Guida
    i passi ci sono e l'articolo no (e l'articolo, aperto a mano, è proprio un 403: il gemello del perché); con la Guida
    l'articolo c'è e si apre; sul PC c'è sempre."""
    import guida
    ospiti(('Giro Senza Guida', {'agenda': 'modifica'}), ('Giro Con Guida', {'agenda': 'modifica', 'guida': 'guarda'}))
    senza, con, pc = dentro_come('Giro Senza Guida', '192.168.9.1'), dentro_come('Giro Con Guida', '192.168.9.2'), locale()
    n = 0
    for a in guida.ARTICOLI:
        url, art = '/aiuto/%s/passi.json' % a['slug'], '/aiuto/%s' % a['slug']
        d = chiedi(senza, 'GET', url)
        assert d.status_code == 200 and d.json['passi'] and d.json['articolo'] == '', (a['slug'], d.status_code, d.json)
        assert chiedi(con, 'GET', url).json['articolo'] == art, ('gemello: con la Guida l\'articolo c\'è', a['slug'])
        assert pc.get(url).json['articolo'] == art, ('sul PC l\'articolo c\'è sempre', a['slug'])
        n += 1
    assert rifiutata(chiedi(senza, 'GET', '/aiuto/come-e-fatto')), 'gemello: senza la Guida l\'articolo è un 403'
    assert chiedi(con, 'GET', '/aiuto/come-e-fatto').status_code == 200, 'gemello: con la Guida l\'articolo si apre'
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'guida.js'), encoding='utf-8') as f:
        js = f.read()
    assert 'if (ultimo && giro.articolo) {' in js and "articolo: dati.articolo || ''" in js, \
        'guida.js deve mostrare «La guida con le immagini» solo se passi.json dà l\'articolo'
    return '%d guide: senza la Guida i passi senza l\'articolo, con la Guida e sul PC con l\'articolo' % n


def persone_dei_turni():
    """Due persone del personale (la griglia dei turni non è vuota), una volta sola."""
    from modelli import Persona
    s = A.Sessione()
    try:
        if not s.scalars(select(Persona.id)).first():
            s.add_all([Persona(cognome='Fittizi', nome='Ada', ruolo='INFERMIERE'),
                       Persona(cognome='Esempio', nome='Bruno', ruolo='OSS')])
            s.commit()
    finally:
        s.close()


def z_rv_turni_solo_guardare():
    """Problema B: con Turni in «solo guardare» la riga diceva «I campi e i bottoni per salvare sono spenti», ma la griglia
    restava attiva (clic, scelta, tasti, salvataggio rifiutato) e c'erano «Aggiungi» e gli Strumenti che cambiano. Ora la
    griglia della settimana e del mese e la vista del giorno hanno data-solo-guardare con il motivo (turni.js non apre
    niente: nel browser in prove_accessi_browser.py), e «Aggiungi», «Schema a rotazione…» e «Copia la settimana prima» non
    ci sono, e nemmeno la riga «Clic su una cella per scegliere il turno…»; Stampa e Scarica in Excel restano. Gemelli: con Turni in «modificare» e sul PC tutto come prima, e sul PC
    l'HTML è identico a quello senza le condizioni nuove."""
    persone_dei_turni()
    ospiti(('Turni Guarda', {'turni': 'guarda'}), ('Turni Modifica', {'turni': 'modifica'}))
    guarda, modifica = dentro_come('Turni Guarda', '192.168.9.3'), dentro_come('Turni Modifica', '192.168.9.4')
    lunedi = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    pagine = ('/personale/turni/settimana/%s' % lunedi, '/personale/turni/mese/%s' % MESE, '/personale/turni/giorno/%s' % OGGI)
    motivo = 'Solo guardare: per «Turni» questo utente non salva niente.'
    for url in pagine:
        tg, tm, tp = testo(chiedi(guarda, 'GET', url)), testo(chiedi(modifica, 'GET', url)), locale().get(url).get_data(as_text=True)
        contenitore = r'<(?:table|div)\b[^>]*id="(?:griglia-turni|vista-giorno)"[^>]*>'
        cg, cm, cp = (re.search(contenitore, x) for x in (tg, tm, tp))
        assert cg and cm and cp, (url, 'la griglia o la vista del giorno non c\'è')
        assert 'data-solo-guardare="%s"' % motivo.replace('«', '&laquo;').replace('»', '&raquo;') in cg.group(0) or \
            ('data-solo-guardare="%s"' % motivo) in cg.group(0), (url, 'solo guardare: la griglia non è segnata', cg.group(0)[:300])
        assert 'data-solo-guardare' not in cm.group(0) and 'data-solo-guardare' not in cp.group(0), (url, 'gemello: segnata')
        for parola in ('data-apri-schema', 'data-copia-settimana', 'class="aggiungi-ruolo"', 'Clic su una cella per scegliere'):
            assert parola not in tg, (url, parola, 'a chi può solo guardare')
        assert 'Scarica in Excel' in tg and 'window.print()' in tg, (url, 'Stampa e Excel restano')
        if '/settimana/' in url:
            for parola in ('data-apri-schema', 'data-copia-settimana', 'class="aggiungi-ruolo"', 'Clic su una cella per scegliere'):
                assert parola in tm and parola in tp, (url, parola, 'gemello: con «modificare» e sul PC c\'è')
    # sul PC l'HTML è proprio quello di prima: le condizioni nuove, rese sempre vere, non cambiano niente
    prima = {'solo_guardare': accessi.solo_guardare, 'puo_cambiare': accessi.puo_cambiare}
    url = pagine[0]
    con = locale().get(url).get_data(as_text=True)
    accessi.solo_guardare, accessi.puo_cambiare = (lambda area: ''), (lambda area: True)
    try:
        senza = locale().get(url).get_data(as_text=True)
    finally:
        accessi.solo_guardare, accessi.puo_cambiare = prima['solo_guardare'], prima['puo_cambiare']
    assert con == senza, 'sul PC i Turni cambiano'
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'turni.js'), encoding='utf-8') as f:
        js = f.read()
    assert js.count("hasAttribute('data-solo-guardare')") == 2, 'turni.js: la griglia e il giorno con «solo guardare»'
    return 'settimana, mese e giorno segnati, «Aggiungi» e gli Strumenti che cambiano tolti; con «modificare» e sul PC no'


def z_rv_nome_della_parte_doppia():
    """Problema C: il cambio di stato vale per Agenda o Segreteria, e la riga «solo guardare», il title dei bottoni e il
    rifiuto nominavano sempre la prima, Agenda: a chi ha solo la Segreteria da guardare si diceva «per Agenda». Ora la
    parte da cui viene il livello. Gemello: con la sola Agenda da guardare si dice ancora Agenda."""
    valori = dati_per_le_pagine()
    ospiti(('Doppia Segreteria', {'segreteria': 'guarda', 'pazienti': 'guarda'}), ('Doppia Agenda', {'agenda': 'guarda'}))
    azione = '/appuntamento/%d/stato' % valori['aid']
    s = A.Sessione()
    giorno = s.get(Appuntamento, valori['aid']).inizio.date().isoformat()
    s.close()
    for nome, ip, pagina, parte, altra in (
            ('Doppia Segreteria', '192.168.9.5', '/conferme?data=%s&struttura=%d' % (giorno, valori['sid']), 'Segreteria', 'Agenda'),
            ('Doppia Agenda', '192.168.9.6', '/appuntamento/%d' % valori['aid'], 'Agenda', 'Segreteria')):
        u = accessi.trova(utenti_salvati(), nome)
        with A.app.test_request_context('/', base_url=RETE, environ_base={'REMOTE_ADDR': '192.168.1.77'}):
            assert accessi.livello_modulo(u, azione) == ('guarda', parte), (nome, accessi.livello_modulo(u, azione))
        d = decisione('POST', azione, cookie_di(nome))
        assert d and d[0] == 403 and 'Per «%s» questo utente può solo guardare' % parte in d[2] and \
            '«%s»' % altra not in d[2], (nome, d[2][:300] if d else d)
        t = testo(chiedi(dentro_come(nome, ip), 'GET', pagina))
        segni = [accessi._attributo(tag, 'data-solo-guardare') for tag, a in moduli_post(t) if a and a.endswith('/stato')]
        assert segni and set(segni) == {accessi.SOLO_GUARDARE % parte}, (nome, pagina, set(segni))
    # la funzione da sola: la parte con il livello, o la prima se nessuna
    u = {'aree': {'segreteria': 'modifica', 'agenda': 'guarda'}}
    assert accessi.nome_della_parte(u, ('agenda', 'segreteria'), 'modifica') == 'Segreteria'
    assert accessi.nome_della_parte(u, ('agenda', 'segreteria'), 'guarda') == 'Agenda'
    assert accessi.nome_della_parte({'aree': {}}, ('agenda', 'segreteria'), 'no') == 'Agenda'
    assert accessi.nome_della_parte(u, 'cassa', 'no') == 'Cassa'
    return 'la Segreteria da guardare dice «Segreteria» (riga, title, rifiuto); la sola Agenda dice ancora «Agenda»'


def z_rv_ricerca_solo_se_serve():
    """Problema D: dalla rete la ricerca rapida della barra c'era sempre, ma a chi non ha Agenda, Pazienti né Dove si fa
    rispondeva sempre «Nessun risultato.», anche per un paziente che c'è. Ora c'è solo se almeno una delle pagine dei suoi
    risultati si apre (accessi.ricerca_utile). Oracolo delle pagine: gli url_for di segreteria.cerca_tutto e di
    dovesifa.per_ricerca_rapida, e le pagine dei risultati veri sul PC. Gemelli: con una sola di quelle aree la ricerca
    c'è; sul PC sempre, e l'HTML è quello di prima."""
    import inspect
    import dovesifa
    import segreteria
    sorgenti = inspect.getsource(segreteria.cerca_tutto) + inspect.getsource(dovesifa.per_ricerca_rapida)
    assert set(re.findall(r"url_for\('([\w.]+)'", sorgenti)) == set(accessi.PAGINE_RICERCA_RAPIDA), \
        (sorted(set(re.findall(r"url_for\('([\w.]+)'", sorgenti))), accessi.PAGINE_RICERCA_RAPIDA)
    dati_per_le_pagine()
    viste = set()
    for q in ('Esempietti', 'domani', 'Lippiello'):
        for gruppo in locale().get('/cerca-tutto.json?q=%s' % q).json.values():
            for voce in gruppo if isinstance(gruppo, list) else [gruppo] if gruppo else []:
                with A.app.test_request_context():
                    viste.add(A.app.url_map.bind('x').match(urllib.parse.urlsplit(voce['url']).path)[0])
    assert viste and viste <= set(accessi.PAGINE_RICERCA_RAPIDA) and len(viste) >= 3, viste
    senza = [('Cerca Cassa', {'cassa': 'guarda', 'sala': 'guarda', 'turni': 'modifica'}, '/cassa/listino'),
             ('Cerca Statistiche', {'statistiche': 'guarda'}, '/statistiche'),
             ('Cerca Guida', {'guida': 'guarda'}, '/aiuto')]
    con = [('Cerca Agenda', {'agenda': 'guarda'}, '/oggi'), ('Cerca Pazienti', {'pazienti': 'guarda'}, '/pazienti'),
           ('Cerca Dove', {'dove': 'guarda'}, '/dove-si-fa/')]
    ospiti(*[(n, a) for n, a, _ in senza + con])
    for i, (nome, _, url) in enumerate(senza + con):
        t = testo(chiedi(dentro_come(nome, '192.168.9.%d' % (20 + i)), 'GET', url))
        barra = re.search(r'<header class="v-barra" data-cornice="barra">(.*?)</header>', t, re.S)
        assert barra, (nome, url, 'senza la barra in alto')
        c = 'id="ricerca-rapida"' in barra.group(1) and 'role="search"' in barra.group(1)
        assert c == ((nome, _, url) in con), (nome, url, 'la ricerca c\'è' if c else 'la ricerca non c\'è')
        assert entrato_come(barra.group(1), nome), (nome, 'la riga dell\'utente resta nella barra')
    pc = locale().get('/oggi').get_data(as_text=True)
    assert 'id="ricerca-rapida"' in pc, 'gemello: sul PC la ricerca c\'è'
    prima = accessi.ricerca_utile
    accessi.ricerca_utile = lambda: True
    try:
        assert locale().get('/oggi').get_data(as_text=True) == pc, 'sul PC la barra cambia'
    finally:
        accessi.ricerca_utile = prima
    return 'pagine dei risultati %s; senza nessuna di quelle aree niente ricerca (3 utenti), con una sì (3); sul PC come ' \
           'prima' % ', '.join(sorted(viste))


if __name__ == '__main__':
    for nome, f in sorted((k, v) for k, v in dict(globals()).items() if re.match(r'[a-z]_', k) and callable(v)):
        if os.environ.get('PROVE_SOLO') and nome not in os.environ['PROVE_SOLO'].split(','):
            continue
        configura_di_partenza()
        prova(nome, f)
    accessi.ascolto.spegni()
    shutil.rmtree(PROVVISORIA, ignore_errors=True)
    for stato, nome, nota in esiti:
        print('%-6s %-36s %s' % (stato, nome, nota))
    male = sum(1 for e in esiti if e[0] != 'OK')
    print('\n%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - male, male))
    sys.exit(1 if male else 0)
