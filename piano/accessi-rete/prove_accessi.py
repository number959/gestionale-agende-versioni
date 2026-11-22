# -*- coding: utf-8 -*-
"""Prove dell'accesso dagli altri PC (BOZZA, M2-bis).

Le richieste «dalla rete» si fanno con il test_client di Flask cambiando l'ambiente: REMOTE_ADDR di un altro PC,
la presa della rete (environ['gestionale.presa_rete'], come la mette accessi.MarcaRete), X-Forwarded-For o
Forwarded (un portiere sullo stesso PC). In fondo il secondo ascolto vero, con le prese: acceso, spento, riacceso.

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
from datetime import date, datetime

from prove_dove import dove

PROVVISORIA = tempfile.mkdtemp(prefix='prove-accessi-')

import seed  # noqa: E402
import app as A  # noqa: E402
import accessi  # noqa: E402
from modelli import Attivita, NotaGiorno, Paziente, scrivi_impostazione, leggi_impostazione  # noqa: E402
from sqlalchemy import event, func, select  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

A.app.config['TESTING'] = True
A.Sessione = seed.popola('sqlite:///' + os.path.join(PROVVISORIA, 'prove.db'))
esiti = []
OGGI = date.today().isoformat()
RETE = 'http://192.168.1.10:5080'        # il PC della segreteria visto dagli altri (in rete_nomi)


def prova(nome, f):
    try:
        esiti.append(('OK', nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', nome, '%s · %s' % (dove(e), str(e) or 'asserzione fallita')))
    except Exception as e:
        esiti.append(('ERRORE', nome, '%s · %r' % (dove(e), e)))


def utente(nome, password, aree, attivo=True):
    return {'nome': nome, 'hash': generate_password_hash(password), 'attivo': attivo, 'versione': 1, 'aree': aree}


TUTTE = {a: 'modifica' for a, _, _ in accessi.AREE}
TUTTE_GUARDA = {a: 'guarda' for a, _, _ in accessi.AREE}


def imposta(**valori):
    s = A.Sessione()
    for k, v in valori.items():
        scrivi_impostazione(s, k, v)
    s.commit()
    s.close()


def configura_di_partenza():
    imposta(rete_accesa='1', rete_porta='5080', rete_schermo_libero='1', rete_nomi='192.168.1.10 pc-segreteria',
            rete_utenti=json.dumps([
                utente('Anna Esempietti', 'password-anna', {'agenda': 'modifica', 'pazienti': 'guarda', 'guida': 'guarda'}),
                # con tutto, e il Sistema scritto a mano nel JSON: non deve valere
                utente('Tutto Provolo', 'password-tutto', dict(TUTTE, sistema='modifica')),
                utente('Guarda Fittizi', 'password-guarda', TUTTE_GUARDA),
                utente('Spento Testabianca', 'password-spento', TUTTE, attivo=False)]))
    accessi._tentativi.clear()


configura_di_partenza()


def locale():
    return A.app.test_client()


def rete(come='indirizzo', ip='192.168.1.50'):
    """Un client «dalla rete», in tre modi diversi."""
    ambiente = {'REMOTE_ADDR': ip}
    base = RETE
    if come == 'presa':
        ambiente['gestionale.presa_rete'] = True
    elif come == 'inoltrata':                  # un portiere sullo stesso PC (Caddy): REMOTE_ADDR e' 127.0.0.1
        ambiente = {'REMOTE_ADDR': '127.0.0.1', 'HTTP_X_FORWARDED_FOR': ip}
        base = 'http://127.0.0.1:5000'
    elif come == 'forwarded':
        ambiente = {'REMOTE_ADDR': '127.0.0.1', 'HTTP_FORWARDED': 'for=%s;proto=http' % ip}
        base = 'http://127.0.0.1:5000'
    c = A.app.test_client()
    c.environ_base.update(ambiente)
    c.base = base
    return c


def chiedi(c, metodo, percorso, **kw):
    kw.setdefault('base_url', getattr(c, 'base', 'http://localhost'))
    if metodo == 'POST':
        kw.setdefault('headers', {}).setdefault('Origin', kw['base_url'])
    return c.open(percorso, method=metodo, **kw)


def entra(c, nome, password, dopo=''):
    return chiedi(c, 'POST', '/accesso', data={'nome': nome, 'password': password, 'dopo': dopo})


def conta(modello):
    s = A.Sessione()
    try:
        return s.scalar(select(func.count()).select_from(modello))
    finally:
        s.close()


def struttura_id():
    s = A.Sessione()
    try:
        from modelli import Struttura
        return s.scalars(select(Struttura.id).order_by(Struttura.id)).first()
    finally:
        s.close()


# ------------------------------------------------------------------ prove
def a_senza_accesso_pagina_di_accesso():
    for come in ('indirizzo', 'presa', 'inoltrata', 'forwarded'):
        c = rete(come)
        r = chiedi(c, 'GET', '/oggi')
        assert r.status_code == 302 and '/accesso' in r.headers['Location'], (come, r.status_code, r.headers.get('Location'))
        assert 'dopo=/oggi' in r.headers['Location'], r.headers['Location']
        r = chiedi(c, 'GET', '/notifiche.json')
        assert r.status_code == 401 and r.mimetype == 'application/json', (come, r.status_code)
        prima = conta(NotaGiorno)
        r = chiedi(c, 'POST', '/note-giorno', data={'struttura': struttura_id(), 'data': OGGI, 'testo': 'dalla rete'})
        assert r.status_code == 302 and '/accesso' in r.headers['Location'], (come, r.status_code)
        assert conta(NotaGiorno) == prima, 'una nota salvata senza accesso'
        r = chiedi(c, 'GET', '/accesso')
        assert r.status_code == 200 and 'Password' in r.get_data(as_text=True)
        assert 'in chiaro' in r.get_data(as_text=True), 'la pagina di accesso deve dire che il collegamento non è protetto'
    return 'quattro modi di arrivare dalla rete: tutti alla pagina di accesso'


def b_password_e_tentativi():
    accessi._tentativi.clear()
    c = rete(ip='192.168.1.61')
    r = entra(c, 'Anna Esempietti', 'sbagliata')
    assert r.status_code == 200 and 'non giusti' in r.get_data(as_text=True)
    r = entra(rete(ip='192.168.1.64'), 'Nessuno Inventato', 'qualcosa')
    assert r.status_code == 200 and 'non giusti' in r.get_data(as_text=True), 'nome sconosciuto: stesso messaggio'
    for _ in range(4):                                   # 5 sbagliate da questo PC e per il nome di Anna
        entra(c, 'Anna Esempietti', 'sbagliata')
    r = entra(c, 'Anna Esempietti', 'password-anna')     # quinta sbagliata prima: adesso anche la giusta aspetta
    assert r.status_code == 429 and 'Troppi tentativi' in r.get_data(as_text=True), r.status_code
    # da un altro PC lo stesso nome e' bloccato (si contano anche i nomi), un altro nome no
    c2 = rete(ip='192.168.1.62')
    assert entra(c2, 'Anna Esempietti', 'password-anna').status_code == 429
    assert entra(c2, 'Guarda Fittizi', 'password-guarda').status_code == 302
    r = entra(rete(ip='192.168.1.63'), 'Spento Testabianca', 'password-spento')
    assert r.status_code == 200 and 'disattivato' in r.get_data(as_text=True)
    accessi._tentativi.clear()
    return 'dopo 5 sbagliate si aspetta, per indirizzo e per nome'


def c_area_negata_403():
    c = rete()
    r = entra(c, 'Anna Esempietti', 'password-anna', dopo='/pazienti')
    assert r.status_code == 302 and r.headers['Location'].endswith('/pazienti'), r.headers.get('Location')
    assert chiedi(c, 'GET', '/oggi').status_code == 200
    for percorso in ('/cassa/%s' % OGGI, '/personale/turni/mese/', '/statistiche', '/dove-si-fa/', '/invii',
                     '/conferme', '/sala/%s' % OGGI, '/ambulatori/riepilogo', '/anagrafiche'):
        r = chiedi(c, 'GET', percorso)
        testo = r.get_data(as_text=True)
        assert r.status_code == 403, (percorso, r.status_code)
        assert 'non è fra le parti disponibili' in testo and 'Anna Esempietti' in testo, percorso
        assert '<html lang="it">' in testo
    r = chiedi(c, 'GET', '/ambulatori/riepilogo.json')
    assert r.status_code == 403 and r.mimetype == 'application/json'
    # il menu non ha le voci delle aree negate, ha il nome e «Esci»
    testo = chiedi(c, 'GET', '/oggi').get_data(as_text=True)
    assert '/cassa/' not in testo and '/statistiche' not in testo and '/personale/turni' not in testo
    assert '/impostazioni' not in testo and '/aggiornamenti' not in testo and '/aree-e-accessi' not in testo
    assert 'Anna Esempietti' in testo and '/esci' in testo
    assert '/pazienti' in testo and '/giorno/' in testo
    return '9 aree negate: 403 con la pagina italiana; il menu senza quelle voci'


def d_solo_guardare_post_403():
    c = rete()
    entra(c, 'Anna Esempietti', 'password-anna')
    assert chiedi(c, 'GET', '/pazienti').status_code == 200
    prima = conta(Paziente)
    r = chiedi(c, 'POST', '/pazienti/nuovo', data={'cognome': 'Inventatissimo', 'nome': 'Dalla Rete'})
    assert r.status_code == 403 and 'Solo guardare' in r.get_data(as_text=True), r.status_code
    assert conta(Paziente) == prima, 'un paziente creato con solo guardare'
    # con «guardare e modificare» (Agenda) il salvataggio passa
    prima = conta(NotaGiorno)
    r = chiedi(c, 'POST', '/note-giorno', data={'struttura': struttura_id(), 'data': OGGI, 'testo': 'Fintini arriva alle 10'})
    assert r.status_code == 302 and '/accesso' not in r.headers['Location'], r.status_code
    assert conta(NotaGiorno) == prima + 1
    # chi ha tutto in «solo guardare»: nessun POST in nessuna area
    g = rete(ip='192.168.1.70')
    entra(g, 'Guarda Fittizi', 'password-guarda')
    for percorso in ('/note-giorno', '/pazienti/nuovo', '/cassa/listino', '/personale/turni/cambia', '/ambulatori/metti',
                     '/da-confermare/prenota', '/dove-si-fa/indirizza', '/invii'):
        r = chiedi(g, 'POST', percorso, data={})
        assert r.status_code == 403, (percorso, r.status_code)
    return 'POST con solo guardare: 403 e niente salvato; con modificare passa'


def e_sistema_mai_dalla_rete():
    c = rete()
    entra(c, 'Tutto Provolo', 'password-tutto')
    assert chiedi(c, 'GET', '/cassa/%s' % OGGI).status_code == 200
    for metodo, percorso in (('GET', '/impostazioni'), ('GET', '/salute'), ('GET', '/autoriparazione'),
                             ('GET', '/aggiornamenti'), ('GET', '/aggiornamenti/stato.json'),
                             ('POST', '/aggiornamenti/aggiorna'), ('POST', '/aggiornamenti/piu-tardi'),
                             ('GET', '/impostazioni/backup/agende-20261122-1000.db'), ('POST', '/impostazioni/ripristina'),
                             ('GET', '/aree-e-accessi'), ('POST', '/aree-e-accessi')):
        r = chiedi(c, metodo, percorso)
        assert r.status_code == 403, (metodo, percorso, r.status_code)
    assert 'Solo dal PC della segreteria' in chiedi(c, 'GET', '/impostazioni').get_data(as_text=True)
    # «sistema» scritto nel JSON non mette nel menu le voci del Sistema, ne' le notifiche che ci portano (Backup)
    testo = chiedi(c, 'GET', '/oggi').get_data(as_text=True)
    assert '/impostazioni' not in testo and '/aree-e-accessi' not in testo and '/aggiornamenti' not in testo
    import backup
    prima = dict(backup.stato)
    backup.stato.update(ultimo_errore='disco pieno (prova)', ultimo_ok=None)      # la notifica «Backup»
    try:
        sul_pc = locale().get('/notifiche.json?struttura=%d' % struttura_id()).json
        assert any('/impostazioni' in n['link'] for n in sul_pc), 'gemello: sul PC la notifica del backup c\'è'
        dalla_rete = chiedi(c, 'GET', '/notifiche.json?struttura=%d' % struttura_id()).json
        for n in dalla_rete:
            assert '/impostazioni' not in n['link'] and '/autoriparazione' not in n['link'], n
        assert 'disco pieno' not in chiedi(c, 'GET', '/oggi').get_data(as_text=True), 'l\'allarme dei backup dalla rete'
    finally:
        backup.stato.clear()
        backup.stato.update(prima)
    # anche senza accesso il Sistema risponde 403 subito, senza aprire il database (come /salute)
    vero = A.ses
    A.ses = lambda: (_ for _ in ()).throw(RuntimeError('database fermo'))
    try:
        assert chiedi(rete(), 'GET', '/salute').status_code == 403
        assert chiedi(rete(), 'GET', '/impostazioni').status_code == 403
    finally:
        A.ses = vero
    return '11 pagine del Sistema: 403 anche per chi ha tutto (e «sistema» scritto nel JSON)'


def f_pc_principale_invariato():
    c = locale()
    for percorso in ('/oggi', '/impostazioni', '/autoriparazione', '/aggiornamenti', '/cassa/%s' % OGGI, '/aree-e-accessi',
                     '/riepilogo-live?schermo=1', '/notifiche.json'):
        r = c.get(percorso)
        assert r.status_code == 200, (percorso, r.status_code)
    assert c.get('/accesso').status_code == 302, 'sul PC principale la pagina di accesso non serve'
    prima = conta(NotaGiorno)
    r = c.post('/note-giorno', data={'struttura': struttura_id(), 'data': '2026-12-01', 'testo': 'dal PC'})
    assert r.status_code == 302 and conta(NotaGiorno) == prima + 1
    # /salute del PC principale non apre il database neanche con l'accesso installato
    vero = A.ses
    A.ses = lambda: (_ for _ in ()).throw(RuntimeError('database fermo'))
    try:
        r = c.get('/salute')
        assert r.status_code == 200 and r.json['programma'], r.status_code
    finally:
        A.ses = vero
    # il menu ha tutto, e la voce nuova «Aree e accessi»
    testo = c.get('/oggi').get_data(as_text=True)
    assert '/cassa/' in testo and '/impostazioni' in testo and '/aree-e-accessi' in testo and '/esci' not in testo
    # il cookie: sul PC il nome di sempre; dalla rete un nome suo, HttpOnly e SameSite=Strict
    c.post('/note-giorno', data={'struttura': struttura_id(), 'data': '2026-12-02', 'testo': 'x'})
    assert c.get_cookie('session') is not None and c.get_cookie(accessi.COOKIE_RETE) is None
    r = entra(rete(), 'Anna Esempietti', 'password-anna')
    intestazione = r.headers.get('Set-Cookie', '')
    assert intestazione.startswith(accessi.COOKIE_RETE + '=') and 'HttpOnly' in intestazione and \
        'SameSite=Strict' in intestazione, intestazione
    return 'senza accesso, tutte le pagine, /salute senza database, cookie di sempre'


def g_modo_schermo():
    anonimo = rete()
    r = chiedi(anonimo, 'GET', '/riepilogo-live?schermo=1')
    assert r.status_code == 200, r.status_code
    assert chiedi(anonimo, 'GET', '/riepilogo-live.json').status_code == 200
    imposta(rete_schermo_libero='')
    try:
        r = chiedi(anonimo, 'GET', '/riepilogo-live?schermo=1')
        assert r.status_code == 302 and '/accesso' in r.headers['Location']
        c = rete()
        entra(c, 'Anna Esempietti', 'password-anna')
        assert chiedi(c, 'GET', '/riepilogo-live?schermo=1').status_code == 403, 'senza Ambulatori e dashboard'
    finally:
        imposta(rete_schermo_libero='1')
    # accesso dalla rete spento: il portiere di oggi (Caddy) continua a mostrare il Modo schermo, il resto no
    imposta(rete_accesa='')
    try:
        p = rete('inoltrata')
        assert chiedi(p, 'GET', '/riepilogo-live?schermo=1').status_code == 200
        assert chiedi(p, 'GET', '/static/stile.css').status_code == 200
        r = chiedi(p, 'GET', '/oggi')
        assert r.status_code == 403 and 'spento' in r.get_data(as_text=True)
        assert chiedi(p, 'POST', '/accesso', data={'nome': 'Tutto Provolo', 'password': 'password-tutto'}).status_code == 403
    finally:
        imposta(rete_accesa='1')
    return 'Modo schermo libero o con accesso; con la rete spenta solo lui'


def h_host_e_origine():
    c = rete()
    r = c.get('/oggi', base_url='http://cattivo.example:5080')
    assert r.status_code == 400, r.status_code
    r = c.get('/oggi', base_url='http://192.168.1.10:8080')          # nome giusto, porta sbagliata
    assert r.status_code == 400, r.status_code
    entra(c, 'Anna Esempietti', 'password-anna')
    prima = conta(NotaGiorno)
    r = c.post('/note-giorno', base_url=RETE, headers={'Origin': 'http://cattivo.example'},
               data={'struttura': struttura_id(), 'data': OGGI, 'testo': 'da un altro sito'})
    assert r.status_code == 403 and conta(NotaGiorno) == prima, r.status_code
    return 'nome di un altro sito: 400; modulo da un altro sito: 403'


def i_notifiche_e_ricerca_filtrate():
    s = A.Sessione()
    p = Paziente(cognome='Esempietti', nome='Canarino', telefono='3331234567')
    s.add(p)
    s.flush()
    s.add(Attivita(testo='Richiamare per il referto', per_il=date.today(), paziente_id=p.id))
    s.commit()
    s.close()
    sid = struttura_id()
    tutto = locale().get('/notifiche.json?struttura=%d' % sid).json
    da_fare = [n for n in tutto if n['titolo'].startswith('Da fare')]
    assert da_fare and da_fare[0]['azioni'], 'la cosa da fare inventata non c\'è fra le notifiche'
    c = rete()
    entra(c, 'Anna Esempietti', 'password-anna')       # pazienti: guarda; segreteria: no
    lista = chiedi(c, 'GET', '/notifiche.json?struttura=%d' % sid).json
    for n in lista:
        with A.app.app_context():
            assert accessi.livello(utente_salvato('Anna Esempietti'), accessi.area_di_indirizzo(n['link'])) != 'no', n
        assert not n.get('azioni'), ('bottoni di un\'area senza modifica', n)
        assert n['titolo'] not in ('Backup',), n
    assert any(n['titolo'].startswith('Da fare') for n in lista), 'il paziente si può guardare: la notifica resta'
    # la ricerca rapida: senza Pazienti niente pazienti
    v = rete(ip='192.168.1.80')
    imposta(rete_utenti=json.dumps(json.loads(leggi(None, 'rete_utenti')) +
                                   [utente('Solo Agenda', 'password-solo', {'agenda': 'guarda'})]))
    entra(v, 'Solo Agenda', 'password-solo')
    r = chiedi(v, 'GET', '/cerca-tutto.json?q=Esempietti')
    assert r.status_code == 200 and r.json['pazienti'] == [], r.json
    assert locale().get('/cerca-tutto.json?q=Esempietti').json['pazienti'], 'sul PC il paziente si trova'
    return 'notifiche e ricerca rapida senza le voci delle aree negate'


def leggi(_, chiave):
    s = A.Sessione()
    try:
        return leggi_impostazione(s, chiave, '')
    finally:
        s.close()


def utente_salvato(nome):
    return accessi.trova(json.loads(leggi(None, 'rete_utenti')), nome)


def j_ogni_pagina_ha_un_area():
    senza = sorted({r.endpoint for r in A.app.url_map.iter_rules()} - set(accessi.AREA))
    assert not senza, 'pagine senza area: %s' % senza
    avanzate = sorted(set(accessi.AREA) - {r.endpoint for r in A.app.url_map.iter_rules()})
    assert not avanzate, 'aree di pagine che non ci sono più: %s' % avanzate
    return '%d pagine, tutte con la loro area' % len({r.endpoint for r in A.app.url_map.iter_rules()})


def k_solo_guardare_non_scrive_mai():
    """Chi ha tutto in «solo guardare» gira tutte le pagine GET senza parametri e i loro collegamenti: nessuna
    scrittura nel database (le GET non cambiano dati; la pagina delle novità dalla rete non segna «vista»)."""
    scritture = []
    motore = A.Sessione.motore

    def guarda(conn, cursor, statement, params, context, executemany):
        if statement.lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
            scritture.append((percorso_attuale[0], statement.split('\n')[0][:80]))
    event.listen(motore, 'before_cursor_execute', guarda)
    percorso_attuale = ['']
    try:
        g = rete(ip='192.168.1.90')
        entra(g, 'Guarda Fittizi', 'password-guarda')
        del scritture[:]
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
                coda += [h.replace('&amp;', '&') for h in re.findall(r'href="(/[^"#]*)"', r.get_data(as_text=True))
                         if not h.startswith(('/static/', '/esci'))]
    finally:
        event.remove(motore, 'before_cursor_execute', guarda)
    assert not scritture, scritture[:5]
    assert leggi(None, 'novita_vista') == '', 'la pagina delle novità dalla rete ha segnato «vista»'
    return '%d pagine guardate dalla rete: nessuna scrittura' % len(visti)


def l_utente_disattivato_o_password_cambiata_esce():
    c = rete(ip='192.168.1.100')
    entra(c, 'Tutto Provolo', 'password-tutto')
    assert chiedi(c, 'GET', '/cassa/%s' % OGGI).status_code == 200
    # dal PC principale, la pagina degli accessi: password nuova
    loc = locale()
    r = loc.post('/aree-e-accessi', data={'azione': 'password', 'utente': 'Tutto Provolo', 'password': 'nuova-password'})
    assert r.status_code == 302
    r = chiedi(c, 'GET', '/cassa/%s' % OGGI)
    assert r.status_code == 302 and '/accesso' in r.headers['Location'], 'con la password cambiata si rientra'
    assert entra(c, 'Tutto Provolo', 'nuova-password').status_code == 302
    # inattivo da piu' di 4 ore
    with c.session_transaction(base_url=RETE, environ_base=dict(c.environ_base)) as sess:
        sess['ultimo'] = time.time() - accessi.INATTIVITA - 5
    assert chiedi(c, 'GET', '/oggi').status_code == 302
    return 'password cambiata e inattività: si rientra'


def m_pagina_degli_accessi_dal_pc():
    loc = locale()
    r = loc.post('/aree-e-accessi', data={'azione': 'nuovo', 'nome': 'Nuovo Fintini', 'password': 'corta'})
    assert 'almeno 8' in loc.get('/aree-e-accessi').get_data(as_text=True) or r.status_code == 302
    loc.post('/aree-e-accessi', data={'azione': 'nuovo', 'nome': 'Nuovo Fintini', 'password': 'password-nuovo'})
    loc.post('/aree-e-accessi', data={'azione': 'salva', 'utente': 'Nuovo Fintini', 'attivo': '1',
                                       'area_cassa': 'guarda', 'area_sistema': 'modifica', 'area_agenda': 'altro'})
    u = utente_salvato('Nuovo Fintini')
    assert u['aree'] == {'cassa': 'guarda'}, u['aree']
    assert u['hash'].startswith(('scrypt:', 'pbkdf2:')) and 'password-nuovo' not in leggi(None, 'rete_utenti')
    c = rete(ip='192.168.1.110')
    r = entra(c, 'nuovo fintini', 'password-nuovo')            # il nome senza badare alle maiuscole
    assert r.status_code == 302 and '/cassa/listino' in r.headers['Location'], r.headers.get('Location')
    assert chiedi(c, 'GET', '/').headers['Location'].endswith('/cassa/listino'), 'la radice porta alla prima area'
    testo = loc.get('/aree-e-accessi').get_data(as_text=True)
    assert 'Nuovo Fintini' in testo and 'in chiaro' in testo and ':5080/' in testo
    assert 'entrato' in testo, 'gli ultimi accessi nella pagina'
    r = loc.post('/aree-e-accessi', data={'azione': 'rete', 'accesa': '1', 'porta': '5000'})
    assert leggi(None, 'rete_porta') == '5080', 'la porta del PC principale non si può usare per la rete'
    return 'utente creato, aree salvate (Sistema e valori strani ignorati), password con hash'


def n_secondo_ascolto_vero():
    """Il server principale su 127.0.0.1 e il secondo ascolto su 0.0.0.0, prese vere: acceso, spento, riacceso."""
    def libera():
        with socket.socket() as x:
            x.bind(('127.0.0.1', 0))
            return x.getsockname()[1]

    def get(porta, percorso):
        h = http.client.HTTPConnection('127.0.0.1', porta, timeout=5)
        try:
            h.request('GET', percorso, headers={'Host': '127.0.0.1:%d' % porta})
            r = h.getresponse()
            return r.status, r.getheader('Location') or '', r.read()
        finally:
            h.close()
    principale, porta_p = A.crea_server(libera())
    filo = threading.Thread(target=principale.run, daemon=True)
    filo.start()
    porta_r = libera()
    try:
        assert accessi.ascolto.accendi(A.app, porta_r), accessi.ascolto.errore
        assert accessi.ascolto.acceso()
        # dalla presa della rete, anche da 127.0.0.1: e' «dalla rete»
        stato, dove_va, _ = get(porta_r, '/oggi')
        assert stato == 302 and '/accesso' in dove_va, (stato, dove_va)
        assert get(porta_r, '/salute')[0] == 403
        stato, _, corpo = get(porta_p, '/salute')
        assert stato == 200 and json.loads(corpo)['programma'], stato
        assert get(porta_p, '/oggi')[0] == 200, 'il PC principale senza accesso'
        assert not [p for _, p in A._in_corso.values() if p], 'richieste rimaste segnate'
        accessi.ascolto.spegni()
        assert not accessi.ascolto.acceso()
        try:
            get(porta_r, '/oggi')
            raise AssertionError('la porta della rete risponde ancora dopo lo spegnimento')
        except ConnectionRefusedError:
            pass
        assert get(porta_p, '/salute')[0] == 200, 'spegnere la rete non tocca il PC principale'
        assert accessi.ascolto.accendi(A.app, porta_r), 'riacceso sulla stessa porta: ' + accessi.ascolto.errore
        assert get(porta_r, '/oggi')[0] == 302
        # una porta gia' presa: errore spiegato, niente eccezione
        with socket.socket() as occupata:
            occupata.bind(('0.0.0.0', 0))
            occupata.listen(1)
            assert not accessi.ascolto.accendi(A.app, occupata.getsockname()[1])
            assert 'già usata' in accessi.ascolto.errore, accessi.ascolto.errore
        # la porta nuova non si poteva usare: resta acceso l'ascolto di prima
        assert accessi.ascolto.acceso() and get(porta_r, '/oggi')[0] == 302, 'spento l\'ascolto di prima'
        # cambiata la porta a programma aperto: la vecchia si chiude, la nuova risponde
        porta_2 = libera()
        assert accessi.ascolto.accendi(A.app, porta_2), accessi.ascolto.errore
        assert get(porta_2, '/oggi')[0] == 302
        try:
            get(porta_r, '/oggi')
            raise AssertionError('la porta di prima risponde ancora')
        except ConnectionRefusedError:
            pass
    finally:
        accessi.ascolto.spegni()
        from waitress import wasyncore
        principale.trigger.pull_trigger(lambda: wasyncore.close_all(principale._map))
        filo.join(5)
    return 'acceso, risponde con l\'accesso, spento (porta chiusa), riacceso; il PC principale sempre su'


for nome, f in sorted((k, v) for k, v in dict(globals()).items() if re.match(r'[a-z]_', k) and callable(v)):
    if os.environ.get('PROVE_SOLO') and nome not in os.environ['PROVE_SOLO'].split(','):
        continue
    configura_di_partenza()
    prova(nome, f)

shutil.rmtree(PROVVISORIA, ignore_errors=True)
for stato, nome, nota in esiti:
    print('%-6s %-50s %s' % (stato, nome, nota))
male = sum(1 for e in esiti if e[0] != 'OK')
print('\n%d prove, %d da sistemare' % (len(esiti), male))
sys.exit(1 if male else 0)
