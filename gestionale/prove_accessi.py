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
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import threading
import time
import types
from datetime import date, datetime, timedelta
from html.parser import HTMLParser

from prove_dove import dove

PROVVISORIA = tempfile.mkdtemp(prefix='prove-accessi-')

import seed  # noqa: E402
import app as A  # noqa: E402
import accessi  # noqa: E402
from modelli import (Appuntamento, Appunto, Attesa, Attivita, NotaGiorno, Operatore, Paziente, Prestazione,  # noqa: E402
                     Risorsa, StrutturaGruppo, leggi_impostazione, scrivi_impostazione)
from sqlalchemy import event, func, select  # noqa: E402

A.app.config['TESTING'] = True
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


def cookie_di(nome):
    """Un cookie vero della rete per l'utente (sessione aperta sul server, come dopo l'accesso)."""
    u = accessi.trova(utenti_salvati(), nome)
    sid = accessi.sessioni.nuova(u['id'], 'prova')
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
    # lo stesso cookie da un altro client: vale (gemello di quello che segue)
    copia = rete(ip='192.168.1.81')
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
    with open(os.path.join(PROVVISORIA, 'sessioni-rete.json'), encoding='utf-8') as f:
        assert accessi.impronta_id(sid) in json.load(f), 'la sessione non è nel file'
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
               '2026-11-22!!', 'Nefrocenter-1', 'annaesempietti!', 'Esempietti 2026']
    for p in cattive:
        assert accessi.problema_password(p, 'Anna Esempietti'), 'accettata: %r' % p
    buone = ['mela verde sul tavolo', 'Treno-Lento-Verso-Sud', 'cassetto pieno di bottoni 7']
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
    with socket.socket() as x:
        x.bind(('127.0.0.1', 0))
        return x.getsockname()[1]


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
            assert 'già usata' in accessi.ascolto.errore, accessi.ascolto.errore
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
    assert 'Entrato da un altro PC come <b>Anna Esempietti</b>' in t and '/accesso/password' in t
    assert 'Entrato da un altro PC' not in locale().get('/oggi').get_data(as_text=True), 'gemello: sul PC no'
    return '9 aree negate con la pagina italiana; solo guardare: 403 e niente salvato; la barra con Esci'


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
