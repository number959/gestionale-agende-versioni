# -*- coding: utf-8 -*-
"""Prove della 1.9.1: l'email con qualsiasi casella.

I tipi di casella (la casella del sito della clinica, Aruba, Gmail, un altro
server) con server, porta e sicurezza proposti; il salvataggio del modulo
(anche quello senza il tipo, come nella 1.9), con i suoi errori e i suoi
avvisi; la pagina (tipo scelto, valori proposti, istruzioni giuste); l'invio
con un nome utente diverso dall'indirizzo, senza password, con password che
hanno spazi; i messaggi d'errore che dicono cosa correggere (password secondo
il fornitore, SSL sulla porta sbagliata, certificato di un altro nome, server
che non si trova, che rifiuta, che non risponde, relay, mittente); le
impostazioni salvate con la 1.9 che continuano a funzionare; il vecchio
indirizzo della guida.

Niente rete vera: le email vanno a un finto server di posta su 127.0.0.1 (lo
stesso di prove_15.py, con STARTTLS, SSL e accesso con password), gli altri
errori si provano con un finto smtplib. Dati inventati."""
import base64
import email
import json
import os
import re
import shutil
import smtplib
import socket
import socketserver
import ssl
import subprocess
import sys
import threading
import traceback
from email import policy
from email.message import EmailMessage
from html import unescape

# i finti server stanno su 127.0.0.1: niente proxy di sistema in mezzo
os.environ['NO_PROXY'] = os.environ['no_proxy'] = '127.0.0.1,localhost'

import logging
logging.getLogger().setLevel(logging.CRITICAL)

from sqlalchemy import select

import comune
import guida
import novita
import servizi
import viste
import invii
import app as A
from modelli import crea_sessione, Struttura, Invio, VERSIONE_SCHEMA, leggi_impostazione, scrivi_impostazione

A.app.config['TESTING'] = True
CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = os.path.join(CARTELLA, 'prove_191_tmp')
shutil.rmtree(PROVVISORIA, ignore_errors=True)
os.makedirs(PROVVISORIA)
esiti, _area, _n = [], [''], [0]
SOLO = [x for x in os.environ.get('PROVE_SOLO', '').split(',') if x]


def area(nome):
    _area[0] = nome


def prova(nome, f):
    if SOLO and f.__name__ not in SOLO:
        return
    try:
        esiti.append(('OK', _area[0], nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', _area[0], nome, str(e)[:600] or 'asserzione fallita'))
    except Exception:
        esiti.append(('ERRORE', _area[0], nome, traceback.format_exc().strip().splitlines()[-1]))


# ====================================================== finto server di posta
def certificato(nome, san):
    """Un certificato autofirmato fatto adesso con openssl, solo per queste prove."""
    cert, chiave = os.path.join(PROVVISORIA, nome + '.pem'), os.path.join(PROVVISORIA, nome + '-chiave.pem')
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '2', '-subj',
                    '/CN=' + san.split(',')[0].split(':')[1], '-addext', 'subjectAltName=' + san,
                    '-keyout', chiave, '-out', cert], check=True, capture_output=True)
    return cert, chiave


def contesti(nome, san):
    cert, chiave = certificato(nome, san)
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.load_cert_chain(cert, chiave)
    return server, ssl.create_default_context(cafile=cert)


# il certificato giusto (per 127.0.0.1) e uno di un altro nome
SERVER_GIUSTO, CLIENT_GIUSTO = contesti('giusto', 'IP:127.0.0.1,DNS:localhost')
SERVER_ALTRO, CLIENT_ALTRO = contesti('altro', 'DNS:posta.altro.example')
invii.contesto_tls = lambda: CLIENT_GIUSTO


class GestorePosta(socketserver.BaseRequestHandler):
    """Lo stesso finto server di prove_15.py: STARTTLS o SSL diretto, AUTH
    PLAIN e LOGIN, e i rifiuti voluti."""
    def handle(self):
        try:
            self._parla()
        except (OSError, ssl.SSLError, ValueError):
            pass

    def _parla(self):
        srv = self.server
        c = srv.comportamento
        sock = self.request
        if c['ssl']:
            sock = srv.contesto.wrap_socket(sock, server_side=True)
        r, uscita = sock.makefile('rb'), [sock]

        def manda(riga):
            # senza buffer: se il gestionale ha gia' chiuso, l'errore resta qui
            uscita[0].sendall((riga + '\r\n').encode('utf-8'))
        tls, utente, mittente, destinatari = c['ssl'], None, None, []
        manda('220 finto.example ESMTP pronto')
        while True:
            grezza = r.readline()
            if not grezza:
                return
            comando = grezza.decode('utf-8', 'replace').rstrip('\r\n')
            verbo = comando.split(' ', 1)[0].upper()
            if verbo in ('EHLO', 'HELO'):
                righe = ['finto.example']
                if c['starttls'] and not tls:
                    righe.append('STARTTLS')
                if c['auth']:
                    righe.append('AUTH PLAIN LOGIN')
                righe += ['SIZE 35882577', '8BITMIME']
                for i, x in enumerate(righe):
                    manda(('250 ' if i == len(righe) - 1 else '250-') + x)
            elif verbo == 'STARTTLS' and c['starttls'] and not tls:
                manda('220 2.0.0 via con il TLS')
                sock = srv.contesto.wrap_socket(sock, server_side=True)
                r, uscita[0] = sock.makefile('rb'), sock
                tls = True
            elif verbo == 'AUTH':
                parti = comando.split()
                metodo = parti[1].upper() if len(parti) > 1 else ''
                if metodo == 'PLAIN':
                    if len(parti) > 2:
                        dati = parti[2]
                    else:
                        manda('334 ')
                        dati = r.readline().decode().strip()
                    _, u, p = base64.b64decode(dati).decode('utf-8').split('\0')
                elif metodo == 'LOGIN':
                    manda('334 VXNlcm5hbWU6')
                    u = base64.b64decode(r.readline().strip()).decode('utf-8')
                    manda('334 UGFzc3dvcmQ6')
                    p = base64.b64decode(r.readline().strip()).decode('utf-8')
                else:
                    manda('504 5.5.4 metodo sconosciuto')
                    continue
                if (u, p) == (c['utente'], c['password']):
                    utente = u
                    manda('235 2.7.0 Accepted')
                else:
                    manda('535 5.7.8 Username and Password not accepted')
            elif verbo == 'MAIL':
                if c['auth'] and utente is None:
                    manda('530 5.7.0 Authentication Required')
                    continue
                mittente, destinatari = re.search(r'<([^>]*)>', comando).group(1), []
                manda('250 2.1.0 OK')
            elif verbo == 'RCPT':
                if c['rifiuta_rcpt']:
                    manda(c['rifiuta_rcpt'])
                    continue
                destinatari.append(re.search(r'<([^>]*)>', comando).group(1))
                manda('250 2.1.5 OK')
            elif verbo == 'DATA':
                manda('354 vai pure')
                righe = []
                while True:
                    x = r.readline()
                    if not x or x in (b'.\r\n', b'.\n'):
                        break
                    righe.append(x[1:] if x.startswith(b'..') else x)
                srv.messaggi.append({'da': mittente, 'a': list(destinatari), 'dati': b''.join(righe),
                                     'tls': tls, 'utente': utente})
                manda('250 2.0.0 OK accettato')
                mittente, destinatari = None, []
            elif verbo in ('RSET', 'NOOP'):
                manda('250 2.0.0 OK')
            elif verbo == 'QUIT':
                manda('221 2.0.0 ciao')
                return
            else:
                manda('502 5.5.2 comando sconosciuto')


class ServerPosta(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, ssl_diretto=False, contesto=SERVER_GIUSTO):
        super().__init__(('127.0.0.1', 0), GestorePosta)
        self.ssl_diretto, self.contesto = ssl_diretto, contesto
        self.ripristina()
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def porta(self):
        return self.server_address[1]

    def ripristina(self, **altro):
        self.messaggi = []
        self.comportamento = {'ssl': self.ssl_diretto, 'starttls': not self.ssl_diretto, 'auth': True,
                              'utente': 'segreteria@example.com', 'password': 'Una password lunga',
                              'rifiuta_rcpt': None}
        self.comportamento.update(altro)


POSTA = ServerPosta()                                   # STARTTLS, come la porta 587
POSTA_SSL = ServerPosta(ssl_diretto=True)               # SSL diretto, come la porta 465
POSTA_ALTRO = ServerPosta(ssl_diretto=True, contesto=SERVER_ALTRO)   # certificato di un altro nome


def cfg_di(server=POSTA, **altro):
    """Impostazioni per il finto server: la casella del sito, con la password giusta."""
    c = dict(invii.PREDEFINITI, email_tipo='dominio', email_utente='segreteria@example.com',
             email_password=invii.proteggi('Una password lunga'), email_server='127.0.0.1', email_porta=str(server.porta),
             email_sicurezza='ssl' if server.ssl_diretto else 'starttls')
    c.update(altro)
    return c


def messaggio_prova(da='segreteria@example.com'):
    m = EmailMessage()
    m['Subject'], m['From'], m['To'] = 'Prova', da, 'ada.fittizi@example.com'
    m.set_content('Prova del gestionale.\n')
    return m


def errore_di(cfg, messaggio=None):
    """L'ErroreInvio di manda_email (AssertionError se l'email parte)."""
    try:
        invii.manda_email(cfg, messaggio or messaggio_prova(cfg['email_utente']))
    except invii.ErroreInvio as e:
        return e
    raise AssertionError('l\'email e\' partita')


# ================================================================ il mondo
def percorso_nuovo():
    _n[0] += 1
    return os.path.join(PROVVISORIA, 'g%d.db' % _n[0])


def mondo(email_struttura='', **impostazioni):
    """Un gestionale nuovo; la struttura con l'email indicata e le impostazioni date gia' salvate."""
    S = crea_sessione('sqlite:///' + percorso_nuovo())
    s = S()
    servizi.prepara_primo_avvio(s, 'Clinica Posillipo')
    s.get(Struttura, 1).email = email_struttura
    for k, v in impostazioni.items():
        scrivi_impostazione(s, k, v)
    s.commit()
    s.close()
    A.Sessione = S
    A._registro = None
    viste._sessionmaker = lambda: S
    return S, A.app.test_client()


def html(r):
    return r.get_data(as_text=True)


def testo(r):
    return ' '.join(unescape(re.sub(r'<[^>]+>', ' ', html(r))).split())


def avvisi(C, categoria=None):
    with C.session_transaction() as sess:
        m = sess.get('_flashes', [])
        sess['_flashes'] = []
    return ' '.join(unescape(t) for c, t in m if categoria is None or c == categoria)


def salvate(S):
    s = S()
    try:
        return invii.impostazioni(s)
    finally:
        s.close()


def modulo(**campi):
    base = {'azione': 'salva', 'sezione': 'email', 'email_attiva': '1', 'email_mittente': ''}
    base.update(campi)
    return base


def selezionato(pagina, nome):
    """Il valore scelto della tendina 'nome' (o quello del campo di testo)."""
    m = re.search(r'<select[^>]*name="%s"[^>]*>(.*?)</select>' % nome, pagina, re.S)
    if m:
        scelta = re.search(r'<option value="([^"]*)" selected', m.group(1))
        return scelta.group(1) if scelta else None
    m = re.search(r'<input[^>]*name="%s"[^>]*>' % nome, pagina)
    v = re.search(r'value="([^"]*)"', m.group(0)) if m else None
    return unescape(v.group(1)) if v else ''


def visibili(pagina):
    """I tipi di casella con le istruzioni visibili (senza hidden)."""
    return {m.group(1) for m in re.finditer(r'data-casella="(\w+)"(?! hidden)', pagina)}


# ================================================================== tipi
area('tipi di casella')


def a_tipo():
    casi = [({'email_tipo': 'aruba', 'email_server': 'smtp.gmail.com'}, '', 'aruba'),
            ({'email_tipo': 'boh', 'email_server': 'smtp.gmail.com'}, '', 'gmail'),
            ({'email_server': 'smtp.gmail.com'}, 'nome@example.com', 'gmail'),
            ({'email_server': 'SMTP.GMAIL.COM.'}, '', 'gmail'),
            ({'email_server': 'smtp.googlemail.com'}, '', 'gmail'),
            ({'email_server': 'smtps.aruba.it'}, '', 'aruba'),
            ({'email_server': 'smtp.aruba.it'}, '', 'aruba'),
            ({'email_server': 'mail.clinica-esempio.it'}, 'segreteria@clinica-esempio.it', 'dominio'),
            ({'email_server': 'mail.clinica-esempio.it', 'email_utente': 'segreteria@clinica-esempio.it'}, '', 'dominio'),
            ({'email_server': 'server12.hosting.example'}, 'segreteria@clinica-esempio.it', 'altro'),
            ({'email_server': ''}, 'nome@gmail.com', 'gmail'),
            ({'email_server': ''}, 'nome@GoogleMail.com', 'gmail'),
            ({'email_server': ''}, 'segreteria@clinica-esempio.it', 'dominio'),
            ({}, '', 'dominio')]
    for cfg, indirizzo, atteso in casi:
        assert invii.tipo_casella(cfg, indirizzo) == atteso, (cfg, indirizzo, invii.tipo_casella(cfg, indirizzo), atteso)


def a_server_proposto():
    assert invii.server_proposto('dominio', 'segreteria@Clinica-Esempio.it') == 'mail.clinica-esempio.it'
    assert invii.server_proposto('dominio', ' info@studio.example.org ') == 'mail.studio.example.org'
    assert invii.server_proposto('dominio', 'senza-chiocciola') == ''
    assert invii.server_proposto('dominio', 'a@localhost') == ''
    assert invii.server_proposto('dominio', '') == ''
    assert invii.server_proposto('aruba') == 'smtps.aruba.it' and invii.server_proposto('gmail') == 'smtp.gmail.com'
    assert invii.server_proposto('altro', 'x@example.com') == '' and invii.server_proposto('boh') == ''
    assert [c['codice'] for c in invii.CASELLE] == ['dominio', 'aruba', 'gmail', 'altro']
    for c in invii.CASELLE:
        assert c['sicurezza'] in ('', 'ssl', 'starttls') and (not c['porta'] or c['porta'].isdigit()), c
    assert {c for c, _ in invii.SICUREZZE} == {'ssl', 'starttls', 'nessuna'}


def a_pronta():
    base = dict(invii.PREDEFINITI, email_utente='a@example.com', email_server='mail.example.com')
    assert not invii.email_pronta(base), 'pronta senza password'
    assert invii.email_pronta(dict(base, email_password='chiaro:eA=='))
    assert invii.email_pronta(dict(base, email_senza_password='1')), 'server senza password: deve bastare'
    assert not invii.email_pronta(dict(base, email_senza_password='1', email_attiva='0'))
    assert not invii.email_pronta(dict(base, email_password='chiaro:eA==', email_server=''))
    assert not invii.email_pronta(dict(invii.PREDEFINITI, email_password='chiaro:eA==', email_utente='a@example.com')), \
        'nessun server di partenza: senza server non e\' pronta'
    # un dizionario della 1.9, senza le chiavi nuove
    vecchio = {'email_attiva': '1', 'email_server': 'smtp.gmail.com', 'email_utente': 'a@gmail.com',
               'email_password': 'chiaro:eA=='}
    assert invii.email_pronta(vecchio)


prova('il tipo dal server, dall\'indirizzo o scelto', a_tipo)
prova('server proposto per tipo; tipi e sicurezze', a_server_proposto)
prova('pronta: password o server che non la chiede', a_pronta)


# ================================================================ salvare
area('salvare la casella')


def b_dominio():
    S, C = mondo()
    r = C.post('/invii', data=modulo(email_tipo='dominio', email_utente='segreteria@clinica-esempio.it',
                                     email_password='  la mia password  ', email_server='', email_porta='',
                                     email_sicurezza=''))
    assert r.status_code == 302 and r.headers['Location'].endswith('/invii#email'), r.status_code
    a = avvisi(C)
    assert 'Impostazioni salvate' in a, a
    c = salvate(S)
    assert (c['email_tipo'], c['email_server'], c['email_porta'], c['email_sicurezza']) == \
        ('dominio', 'mail.clinica-esempio.it', '465', 'ssl'), c
    assert invii.svela(c['email_password']) == 'la mia password', 'spazi dentro la password tolti o spazi ai lati rimasti'
    assert c['email_accesso'] == '' and c['email_senza_password'] == '0'
    assert 'Email: pronte' in testo(C.get('/invii'))
    # il server scritto a mano resta
    C.post('/invii', data=modulo(email_tipo='dominio', email_utente='segreteria@clinica-esempio.it',
                                 email_server='server12.hosting.example', email_porta='465', email_sicurezza='ssl'))
    c = salvate(S)
    assert c['email_server'] == 'server12.hosting.example' and invii.svela(c['email_password']) == 'la mia password', c


def b_aruba_e_gmail():
    S, C = mondo()
    C.post('/invii', data=modulo(email_tipo='aruba', email_utente='info@studio-esempio.it', email_password='x1 y2'))
    c = salvate(S)
    assert (c['email_server'], c['email_porta'], c['email_sicurezza']) == ('smtps.aruba.it', '465', 'ssl'), c
    assert invii.svela(c['email_password']) == 'x1 y2'
    C.post('/invii', data=modulo(email_tipo='gmail', email_utente='clinica.prova@gmail.com',
                                 email_password='abcd efgh ijkl mnop'))
    a = avvisi(C, 'avviso')
    c = salvate(S)
    assert (c['email_tipo'], c['email_server'], c['email_porta'], c['email_sicurezza']) == \
        ('gmail', 'smtp.gmail.com', '587', 'starttls'), c
    assert invii.svela(c['email_password']) == 'abcdefghijklmnop' and a == '', (a, c)
    C.post('/invii', data=modulo(email_tipo='gmail', email_utente='clinica.prova@gmail.com',
                                 email_password='la password normale'))
    assert '16 lettere' in avvisi(C, 'avviso'), 'nessun avviso per una password di Gmail che non e\' per le app'
    assert invii.svela(salvate(S)['email_password']) == 'lapasswordnormale'
    # casella del sito scelta con un indirizzo @gmail.com: e' Gmail
    C.post('/invii', data=modulo(email_tipo='dominio', email_utente='altra.prova@gmail.com', email_server=''))
    c = salvate(S)
    assert (c['email_tipo'], c['email_server']) == ('gmail', 'smtp.gmail.com'), c


def b_errori():
    S, C = mondo()
    C.post('/invii', data=modulo(email_tipo='altro', email_utente='a@example.com', email_password='p', email_server=''))
    assert 'Manca il server' in avvisi(C, 'errore')
    assert salvate(S)['email_utente'] == '', 'salvato nonostante l\'errore'
    for campi, parola in ((dict(email_tipo='boh'), 'Tipo di casella'),
                          (dict(email_server='smtp://mail.example.com'), 'Server non valido'),
                          (dict(email_server='mail example com'), 'Server non valido'),
                          (dict(email_porta='0'), 'Porta non valida'),
                          (dict(email_porta='465a'), 'Porta non valida'),
                          (dict(email_sicurezza='tls'), 'Sicurezza'),
                          (dict(email_accesso='nome con spazi'), 'Nome utente non valido'),
                          (dict(email_accesso='x' * 121), 'Nome utente non valido'),
                          (dict(email_utente='non-email'), 'Indirizzo email non valido')):
        dati = modulo(email_tipo='dominio', email_utente='a@example.com', email_password='p')
        dati.update(campi)
        C.post('/invii', data=dati)
        a = avvisi(C, 'errore')
        assert parola in a, (campi, a)
    assert salvate(S)['email_utente'] == ''
    # niente indirizzo e niente server: si puo' salvare (per esempio per spegnere tutto)
    C.post('/invii', data=modulo(email_tipo='altro', email_utente='', email_server='', email_attiva=''))
    assert 'Impostazioni salvate' in avvisi(C)


def b_accesso_e_senza_password():
    S, C = mondo()
    C.post('/invii', data=modulo(email_tipo='altro', email_utente='segreteria@example.com', email_password='p',
                                 email_server='smtp-relay.example.net', email_porta='587', email_sicurezza='starttls',
                                 email_accesso='8a1b2c@smtp.example.net'))
    c = salvate(S)
    assert c['email_accesso'] == '8a1b2c@smtp.example.net' and c['email_tipo'] == 'altro', c
    C.post('/invii', data=modulo(email_tipo='altro', email_utente='segreteria@example.com',
                                 email_server='smtp-relay.example.net', email_porta='587', email_sicurezza='starttls',
                                 email_accesso='SEGRETERIA@example.com'))
    assert salvate(S)['email_accesso'] == '', 'nome utente uguale all\'indirizzo: va lasciato vuoto'
    # server della rete interna senza password
    S, C = mondo()
    C.post('/invii', data=modulo(email_tipo='altro', email_utente='segreteria@example.com',
                                 email_server='posta.rete.interna', email_porta='25', email_sicurezza='nessuna',
                                 email_senza_password='1'))
    c = salvate(S)
    assert c['email_senza_password'] == '1' and c['email_password'] == '' and invii.email_pronta(c), c
    assert avvisi(C, 'avviso') == '', 'senza password e senza sicurezza: niente avviso sulla password in chiaro'
    assert 'Email: pronte' in testo(C.get('/invii'))
    C.post('/invii', data=modulo(email_tipo='altro', email_utente='segreteria@example.com',
                                 email_server='posta.rete.interna', email_porta='25', email_sicurezza='nessuna'))
    assert not invii.email_pronta(salvate(S)) and 'Email: da configurare' in testo(C.get('/invii'))


def b_avvisi():
    S, C = mondo()
    for porta, sicurezza, parola in (('465', 'starttls', 'porta 465'), ('587', 'ssl', 'porta 587'),
                                     ('25', 'nessuna', 'in chiaro'), ('465', 'ssl', ''), ('587', 'starttls', '')):
        C.post('/invii', data=modulo(email_tipo='altro', email_utente='a@example.com', email_password='p',
                                     email_server='mail.example.com', email_porta=porta, email_sicurezza=sicurezza))
        tutti = avvisi(C)
        assert 'Impostazioni salvate' in tutti, (porta, sicurezza, tutti)
        a = tutti.replace('Impostazioni salvate.', '').strip()
        assert (parola in a) if parola else a == '', (porta, sicurezza, a)
        assert salvate(S)['email_porta'] == porta, 'con un avviso le impostazioni si salvano lo stesso'


def b_modulo_19():
    """Il modulo senza il tipo (pagina della 1.9 ancora aperta durante l'aggiornamento): il tipo dal server."""
    S, C = mondo()
    for server, indirizzo, atteso in (('smtp.gmail.com', 'clinica.prova@gmail.com', 'gmail'),
                                      ('mail.clinica-esempio.it', 'segreteria@clinica-esempio.it', 'dominio'),
                                      ('smtps.aruba.it', 'info@studio-esempio.it', 'aruba'),
                                      ('smtp.example.net', 'segreteria@clinica-esempio.it', 'altro')):
        C.post('/invii', data={'azione': 'salva', 'sezione': 'email', 'email_utente': indirizzo,
                               'email_password': 'abcd efgh ijkl mnop', 'email_server': server, 'email_porta': '587',
                               'email_sicurezza': 'starttls', 'email_attiva': '1'})
        c = salvate(S)
        assert (c['email_tipo'], c['email_server']) == (atteso, server), (server, c['email_tipo'])


prova('casella del sito: server mail. + dominio, 465 SSL, password con gli spazi', b_dominio)
prova('Aruba e Gmail: valori pronti, password per le app, avviso se non lo sembra', b_aruba_e_gmail)
prova('errori del modulo: niente si salva', b_errori)
prova('nome utente diverso; server interno senza password', b_accesso_e_senza_password)
prova('avvisi su porta e sicurezza, che non fermano il salvataggio', b_avvisi)
prova('modulo senza il tipo, come quello della 1.9', b_modulo_19)


# ================================================================== pagina
area('la pagina')


def c_pagina_nuova():
    S, C = mondo(email_struttura='clinica.esempio.prova@gmail.com')
    p = html(C.get('/invii'))
    assert selezionato(p, 'email_tipo') == 'gmail', selezionato(p, 'email_tipo')
    assert (selezionato(p, 'email_server'), selezionato(p, 'email_porta'), selezionato(p, 'email_sicurezza')) == \
        ('smtp.gmail.com', '587', 'starttls')
    assert visibili(p) == {'gmail'}, visibili(p)
    assert 'Password per le app' in p and 'Email: da configurare' in testo(C.get('/invii'))
    assert re.search(r'<details class="riquadro" data-guida="email-istruzioni" open>', p), 'istruzioni chiuse'
    S, C = mondo(email_struttura='segreteria@clinica-esempio.it')
    p = html(C.get('/invii'))
    assert selezionato(p, 'email_tipo') == 'dominio' and visibili(p) == {'dominio'}, (selezionato(p, 'email_tipo'), visibili(p))
    assert (selezionato(p, 'email_server'), selezionato(p, 'email_porta'), selezionato(p, 'email_sicurezza')) == \
        ('mail.clinica-esempio.it', '465', 'ssl')
    assert selezionato(p, 'email_utente') == 'segreteria@clinica-esempio.it' and 'Password della casella' in p
    assert re.search(r'<details class="campo" id="email-server" data-guida="email-server" open>', p), \
        'server e accesso chiusi per una casella del sito ancora da collegare'
    # tutti i tipi, le istruzioni di ciascuno, i valori per la pagina
    caselle = json.loads(unescape(re.search(r'<script type="application/json" id="caselle-email">(.*?)</script>',
                                            p, re.S).group(1)))
    assert caselle == invii.CASELLE
    for c in invii.CASELLE:
        assert '<option value="%s"' % c['codice'] in p and p.count('data-casella="%s"' % c['codice']) == 3, c['codice']
    assert 'form="modulo-email"' in p and 'id="modulo-email"' in p, 'la tendina del tipo non va con il modulo'
    for guida_ in ('email-tipo', 'email-istruzioni', 'email-account', 'email-server', 'email-prova'):
        assert 'data-guida="%s"' % guida_ in p, guida_


def c_pagina_salvata_19():
    """Le impostazioni come le lascia la 1.9 (Gmail, senza tipo): restano Gmail e pronte."""
    S, C = mondo(email_struttura='clinica.esempio.prova@gmail.com', email_utente='clinica.esempio.prova@gmail.com',
                 email_password=invii.proteggi('abcdefghijklmnop'), email_server='smtp.gmail.com', email_porta='587',
                 email_sicurezza='starttls', email_attiva='1')
    p = html(C.get('/invii'))
    assert selezionato(p, 'email_tipo') == 'gmail' and visibili(p) == {'gmail'}
    assert 'Email: pronte' in testo(C.get('/invii')) and 'salvata: vuoto per lasciarla' in p
    assert not re.search(r'data-guida="email-istruzioni" open', p), 'istruzioni aperte con l\'email gia\' pronta'
    # un altro server scritto a mano con la 1.9: «Altro server», con il suo server
    S, C = mondo(email_utente='segreteria@clinica-esempio.it', email_password=invii.proteggi('p'),
                 email_server='smtp.example.net', email_porta='465', email_sicurezza='ssl')
    p = html(C.get('/invii'))
    assert selezionato(p, 'email_tipo') == 'altro' and selezionato(p, 'email_server') == 'smtp.example.net'
    assert selezionato(p, 'email_porta') == '465' and selezionato(p, 'email_sicurezza') == 'ssl'


def c_guida():
    S, C = mondo()
    r = C.get('/aiuto/email-gmail')
    assert r.status_code in (301, 302) and r.headers['Location'].endswith('/aiuto/email-casella'), r.status_code
    r = C.get('/aiuto/email-gmail/passi.json')
    assert r.status_code in (301, 302) and r.headers['Location'].endswith('/aiuto/email-casella/passi.json')
    a = guida.PER_SLUG['email-casella']
    assert 'email-gmail' not in guida.PER_SLUG
    t = testo(C.get('/aiuto/email-casella'))
    assert a['titolo'] in t and 'Aruba' in t and 'password per le app' in t
    assert C.get('/aiuto/non-esiste').status_code == 404
    assert [v for v, _ in novita.NOVITA][0] == comune.VERSIONE == '1.9.1', (novita.NOVITA[0][0], comune.VERSIONE)
    for v, voci in novita.NOVITA:
        for x in voci:
            assert not x.get('guida') or x['guida'] in guida.PER_SLUG, (v, x['guida'])
    assert all(x['guida'] == 'email-casella' for x in novita.NOVITA[0][1])


prova('casella mai salvata: tipo e valori dall\'indirizzo della struttura', c_pagina_nuova)
prova('impostazioni della 1.9: Gmail resta Gmail, un altro server resta suo', c_pagina_salvata_19)
prova('guida nuova, vecchio indirizzo, novità della 1.9.1', c_guida)


# ================================================================= spedire
area('spedire')


def d_casella_del_sito():
    """SSL diretto (porta 465) e STARTTLS (587), nome utente = indirizzo, password con gli spazi."""
    for srv in (POSTA_SSL, POSTA):
        srv.ripristina()
        invii.manda_email(cfg_di(srv), messaggio_prova())
        m = srv.messaggi
        assert len(m) == 1 and m[0]['tls'] and m[0]['utente'] == 'segreteria@example.com', m
        assert m[0]['da'] == 'segreteria@example.com' and m[0]['a'] == ['ada.fittizi@example.com'], m


def d_nome_utente_diverso():
    POSTA.ripristina(utente='8a1b2c@smtp.example.net', password='chiave-smtp')
    try:
        invii.manda_email(cfg_di(POSTA, email_accesso='8a1b2c@smtp.example.net',
                                 email_password=invii.proteggi('chiave-smtp')), messaggio_prova())
        m = POSTA.messaggi
        assert len(m) == 1 and m[0]['utente'] == '8a1b2c@smtp.example.net' and m[0]['da'] == 'segreteria@example.com', m
        # con il gestionale vero: il mittente e' l'indirizzo, non il nome utente
        S, C = mondo(email_struttura='segreteria@example.com', email_tipo='altro',
                     email_utente='segreteria@example.com', email_accesso='8a1b2c@smtp.example.net',
                     email_password=invii.proteggi('chiave-smtp'), email_server='127.0.0.1',
                     email_porta=str(POSTA.porta), email_sicurezza='starttls')
        POSTA.messaggi = []
        C.post('/invii', data={'azione': 'prova_email', 'a': 'ada.fittizi@example.com'})
        a = avvisi(C)
        assert 'Prova mandata' in a, a
        x = email.message_from_bytes(POSTA.messaggi[-1]['dati'], policy=policy.default)
        assert 'segreteria@example.com' in x['From'] and POSTA.messaggi[-1]['utente'] == '8a1b2c@smtp.example.net'
    finally:
        POSTA.ripristina()


def d_senza_password():
    POSTA.ripristina(auth=False)
    try:
        invii.manda_email(cfg_di(POSTA, email_password='', email_senza_password='1'), messaggio_prova())
        assert len(POSTA.messaggi) == 1 and POSTA.messaggi[0]['utente'] is None, POSTA.messaggi
        # spunta messa ma password salvata: non si usa
        invii.manda_email(cfg_di(POSTA, email_senza_password='1'), messaggio_prova())
        assert len(POSTA.messaggi) == 2 and POSTA.messaggi[1]['utente'] is None
    finally:
        POSTA.ripristina()
    # il server invece la vuole
    e = errore_di(cfg_di(POSTA, email_password='', email_senza_password='1'))
    assert e.permanente and 'vuole nome utente e password' in str(e) and 'togliere la spunta' in str(e), str(e)
    assert POSTA.messaggi == []


def d_password_sbagliata():
    e = errore_di(cfg_di(POSTA, email_password=invii.proteggi('sbagliata')))
    assert e.permanente and 'non ha accettato nome utente e password' in str(e), str(e)
    assert 'risposta del server: 535 5.7.8 Username and Password not accepted' in str(e), str(e)
    assert 'password per le app' not in str(e), 'consiglio di Gmail per una casella che non e\' Gmail'
    x = smtplib.SMTPAuthenticationError(535, b'5.7.8 Username and Password not accepted. For more information, go to\n'
                                             b'5.7.8  https://support.google.com/mail/?p=BadCredentials')
    g = invii.spiega_accesso_rifiutato({'email_server': 'smtp.gmail.com'}, x)
    assert g.startswith('Gmail non ha accettato') and 'password per le app' in g and '\n' not in g, g
    m = invii.spiega_accesso_rifiutato({'email_server': 'smtp.office365.com'},
                                       smtplib.SMTPAuthenticationError(535, b'5.7.139 Authentication unsuccessful, '
                                                                            b'basic authentication is disabled.'))
    assert m.startswith('Microsoft') and 'SMTP AUTH' in m and 'basic authentication is disabled' in m, m
    assert 'risposta' not in invii.spiega_accesso_rifiutato({'email_server': 'mail.example.com'})


def d_ssl_sulla_porta_sbagliata():
    e = errore_di(cfg_di(POSTA, email_sicurezza='ssl'))
    assert e.permanente and 'non usa SSL' in str(e) and 'STARTTLS' in str(e), str(e)


def d_certificato():
    # certificato di un altro nome: va corretto il server
    invii.contesto_tls = lambda: CLIENT_ALTRO
    try:
        e = errore_di(cfg_di(POSTA_ALTRO))
    finally:
        invii.contesto_tls = lambda: CLIENT_GIUSTO
    assert e.permanente and 'non va bene' in str(e) and 'nome del server esatto' in str(e), str(e)
    assert POSTA_ALTRO.messaggi == []
    # certificato che il PC non conosce (autofirmato): si riprova
    invii.contesto_tls = ssl.create_default_context
    try:
        e = errore_di(cfg_di(POSTA_SSL))
    finally:
        invii.contesto_tls = lambda: CLIENT_GIUSTO
    assert not e.permanente and 'connessione protetta non riuscita' in str(e), str(e)
    assert 'nome del server esatto' not in str(e)


class FintoSMTP:
    """Al posto di smtplib.SMTP e SMTP_SSL: alza l'errore voluto nel momento voluto."""
    errore, quando = None, 'apri'

    def __init__(self, *a, **k):
        if FintoSMTP.quando == 'apri':
            raise FintoSMTP.errore

    def _forse(self, momento):
        if FintoSMTP.quando == momento:
            raise FintoSMTP.errore

    def starttls(self, **k):
        self._forse('starttls')

    def login(self, *a):
        self._forse('login')

    def send_message(self, m):
        self._forse('manda')

    def quit(self):
        pass


def d_errori_spiegati():
    casi = [
        (socket.gaierror(11001, 'getaddrinfo failed'), 'apri', {}, False, ['non raggiungibile', 'non si trova']),
        (ConnectionRefusedError(10061, 'rifiutata'), 'apri', {}, False, ['non raggiungibile', 'rifiuta il collegamento',
                                                                          'porta']),
        (TimeoutError('timed out'), 'apri', {'email_porta': '465', 'email_sicurezza': 'starttls'}, False,
         ['non risponde', 'con la porta 465 la sicurezza è SSL']),
        (TimeoutError('timed out'), 'apri', {'email_porta': '587', 'email_sicurezza': 'starttls'}, False,
         ['non risponde', 'controllare server e porta']),
        (smtplib.SMTPServerDisconnected('Connection unexpectedly closed'), 'apri',
         {'email_porta': '465', 'email_sicurezza': 'starttls'}, False, ['non raggiungibile', 'porta 465']),
        (smtplib.SMTPNotSupportedError('STARTTLS extension not supported by server.'), 'starttls', {}, True,
         ['non offre STARTTLS', '465']),
        (smtplib.SMTPNotSupportedError('SMTP AUTH extension not supported by server.'), 'login', {}, True,
         ['nome utente e password', 'Il server non chiede la password']),
        (smtplib.SMTPRecipientsRefused({'ada.fittizi@example.com': (554, b'5.7.1 <ada.fittizi@example.com>: Relay '
                                                                         b'access denied')}), 'manda', {}, True,
         ['destinatario rifiutato', 'Relay access denied', 'indirizzi di fuori']),
        (smtplib.SMTPRecipientsRefused({'ada.fittizi@example.com': (550, b'5.1.1 utente sconosciuto')}), 'manda', {}, True,
         ['destinatario rifiutato', 'utente sconosciuto']),
        (smtplib.SMTPSenderRefused(553, b'5.7.1 Sender address rejected: not owned by user', 'altro@example.com'),
         'manda', {}, True, ['mittente rifiutato', 'not owned by user', 'quello della casella']),
        (smtplib.SMTPSenderRefused(530, b'5.7.0 Authentication Required', 'segreteria@example.com'), 'manda',
         {'email_senza_password': '1'}, True, ['vuole nome utente e password', 'togliere la spunta']),
        (smtplib.SMTPDataError(451, b'4.3.0 riprovare piu tardi'), 'manda', {}, False, ['riprovare']),
        (smtplib.SMTPDataError(552, b'5.3.4 troppo grande'), 'manda', {}, True, ['troppo grande']),
    ]
    vecchi = smtplib.SMTP, smtplib.SMTP_SSL
    smtplib.SMTP = smtplib.SMTP_SSL = FintoSMTP
    try:
        for errore, quando, altro, permanente, parole in casi:
            FintoSMTP.errore, FintoSMTP.quando = errore, quando
            e = errore_di(cfg_di(POSTA, email_server='mail.example.com', **altro))
            assert e.permanente == permanente and all(p in str(e) for p in parole), (type(errore).__name__, str(e))
            assert '\n' not in str(e), str(e)
    finally:
        smtplib.SMTP, smtplib.SMTP_SSL = vecchi


def d_coda():
    """Un errore da correggere si ferma al primo tentativo e lo dice nel registro."""
    S, C = mondo(email_struttura='segreteria@example.com', email_tipo='dominio',
                 email_utente='segreteria@example.com', email_password=invii.proteggi('Una password lunga'),
                 email_server='127.0.0.1', email_porta=str(POSTA.porta), email_sicurezza='ssl')
    C.post('/invii', data={'azione': 'prova_email', 'a': 'ada.fittizi@example.com'})
    a = avvisi(C)
    assert 'Non partito' in a and 'non usa SSL' in a, a
    s = S()
    x = s.scalars(select(Invio)).one()
    assert x.stato == 'ERRORE' and x.tentativi == 1 and 'STARTTLS' in x.errore, (x.stato, x.tentativi, x.errore)
    s.close()
    assert 'non usa SSL' in testo(C.get('/invii'))


prova('casella del sito con SSL e con STARTTLS', d_casella_del_sito)
prova('nome utente diverso dall\'indirizzo: si entra con quello, scrive l\'indirizzo', d_nome_utente_diverso)
prova('server senza password; e se invece la vuole', d_senza_password)
prova('password sbagliata: il consiglio giusto per ogni fornitore', d_password_sbagliata)
prova('SSL su una porta senza SSL: si dice di scegliere STARTTLS', d_ssl_sulla_porta_sbagliata)
prova('certificato di un altro nome (da correggere) o sconosciuto (si riprova)', d_certificato)
prova('ogni errore con il suo consiglio, e se riprovare o no', d_errori_spiegati)
prova('dalla pagina: l\'errore da correggere nel registro, senza nuovi tentativi', d_coda)


# ============================================================ dalla 1.9
area('aggiornamento dalla 1.9')


def e_impostazioni_19():
    """Un database della 1.9 con Gmail collegato: nessun cambio di schema, stesse impostazioni, stesso invio."""
    assert VERSIONE_SCHEMA == 10, 'la 1.9.1 non cambia il database'
    S, C = mondo(email_utente='segreteria@example.com', email_password=invii.proteggi('Una password lunga'),
                 email_server='127.0.0.1', email_porta=str(POSTA.porta), email_sicurezza='starttls',
                 email_attiva='1')
    s = S()
    nomi = {k for k in invii.PREDEFINITI if leggi_impostazione(s, k, None) is not None}
    s.close()
    assert not nomi & {'email_tipo', 'email_accesso', 'email_senza_password'}, nomi
    c = salvate(S)
    assert c['email_accesso'] == '' and c['email_senza_password'] == '0' and invii.email_pronta(c)
    POSTA.ripristina()
    C.post('/invii', data={'azione': 'prova_email', 'a': 'ada.fittizi@example.com'})
    assert 'Prova mandata' in avvisi(C)
    assert POSTA.messaggi[-1]['utente'] == 'segreteria@example.com'


prova('impostazioni email della 1.9: nessuna migrazione, si manda come prima', e_impostazioni_19)


# =====================================================================
if __name__ == '__main__':
    aree = []
    for e in esiti:
        if e[1] not in aree:
            aree.append(e[1])
    for a in aree:
        mie = [e for e in esiti if e[1] == a]
        rotte = [e for e in mie if e[0] != 'OK']
        print('%-48s %2d prove  %s' % (a, len(mie), 'tutte a posto' if not rotte else '%d DA SISTEMARE' % len(rotte)))
    rotte = [e for e in esiti if e[0] != 'OK']
    if rotte or os.environ.get('DETTAGLIO'):
        print('\nDettaglio:')
        for e in esiti:
            if e[0] != 'OK' or os.environ.get('DETTAGLIO'):
                print('  %-6s [%s] %s\n         %s' % (e[0], e[1], e[2], e[3]))
    print('\n%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(rotte), len(rotte)))
    shutil.rmtree(PROVVISORIA, ignore_errors=True)
    sys.exit(1 if rotte else 0)
