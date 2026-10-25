# -*- coding: utf-8 -*-
"""Prove della 1.5: data di nascita, codice fiscale e indirizzo in
prenotazione; email automatiche alla prenotazione (la preparazione agli esami
endoscopici del Dr. Galasso, con le informative allegate) e invio a comando;
promemoria del giorno prima per WhatsApp o email; sala operatoria nel mese;
email della struttura nelle stampe.

Niente rete vera: le email vanno a un finto server di posta su 127.0.0.1
(con STARTTLS e accesso con password, come Gmail) e i WhatsApp a un finto
server di Meta. I dati sono inventati."""
import base64
import email
import json
import os
import re
import shutil
import socket
import socketserver
import sqlite3
import ssl
import subprocess
import sys
import threading
import time as orologio
import traceback
from datetime import date, datetime, time, timedelta
from email import policy
from html import unescape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# i finti server stanno su 127.0.0.1: niente proxy di sistema in mezzo
os.environ['NO_PROXY'] = os.environ['no_proxy'] = '127.0.0.1,localhost'
import logging
logging.getLogger().setLevel(logging.CRITICAL)      # gli errori voluti delle prove non sporcano l'uscita

from sqlalchemy import select, func

import servizi
import importa
import pazienti
import documenti
import viste
import invii
import app as A
from modelli import (crea_sessione, Struttura, Risorsa, Operatore, Prestazione, Appuntamento, Paziente, Chiusura,
                     Appunto, RegolaEmail, AllegatoRegola, Invio, ModuloStampa, VERSIONE_SCHEMA,
                     leggi_impostazione, scrivi_impostazione)

A.app.config['TESTING'] = True
CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = os.path.join(CARTELLA, 'prove_15_tmp')
shutil.rmtree(PROVVISORIA, ignore_errors=True)
os.makedirs(PROVVISORIA)
esiti, _area, _n = [], [''], [0]
OGGI = date.today()


def giorno_libero(g, giorno_settimana):
    """Il primo giorno della settimana voluto, da g in poi, senza festivi
    vicini (le prove guardano anche i giorni intorno)."""
    g += timedelta(days=(giorno_settimana - g.weekday()) % 7)
    while any(servizi.calendario.festivo(g + timedelta(days=k)) for k in range(-3, 9)):
        g += timedelta(days=7)
    return g


MAR = giorno_libero(OGGI + timedelta(days=14), 1)          # un martedi' fra un paio di settimane
MER = MAR + timedelta(days=1)
VEN = MAR + timedelta(days=3)
ORA9 = datetime.combine(MAR, time(9, 0))
PASSWORD_APP = 'abcdefghijklmnop'
UTENTE = 'clinica.prova@example.com'
TOKEN = 'EAAprovaTOKEN123'


def area(nome):
    _area[0] = nome


SOLO = [x for x in os.environ.get('PROVE_SOLO', '').split(',') if x]    # per rifare solo alcune prove


def prova(nome, f):
    if SOLO and f.__name__ not in SOLO:
        return
    try:
        esiti.append(('OK', _area[0], nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', _area[0], nome, str(e) or 'asserzione fallita'))
    except Exception:
        esiti.append(('ERRORE', _area[0], nome, traceback.format_exc().strip().splitlines()[-1]))


def percorso_nuovo(nome='db'):
    _n[0] += 1
    return os.path.join(PROVVISORIA, '%s_%d.db' % (nome, _n[0]))


def cf_valido(primi15):
    """Il codice fiscale con il carattere di controllo giusto."""
    somma = sum((pazienti._DISPARI if i % 2 == 0 else pazienti._PARI)[c] for i, c in enumerate(primi15))
    return primi15 + chr(ord('A') + somma % 26)


# =========================================================== finto Gmail
def certificato():
    """Un certificato autofirmato per 127.0.0.1, fatto adesso con openssl:
    serve solo al finto server di posta di queste prove."""
    cert, chiave = os.path.join(PROVVISORIA, 'cert.pem'), os.path.join(PROVVISORIA, 'chiave.pem')
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '2', '-subj', '/CN=127.0.0.1',
                    '-addext', 'subjectAltName=IP:127.0.0.1,DNS:localhost', '-keyout', chiave, '-out', cert],
                   check=True, capture_output=True)
    return cert, chiave


CERT, CHIAVE = certificato()
CONTESTO_SERVER = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
CONTESTO_SERVER.load_cert_chain(CERT, CHIAVE)
# il gestionale controlla davvero il certificato: nelle prove si fida di questo
CONTESTO_CLIENT = ssl.create_default_context(cafile=CERT)
invii.contesto_tls = lambda: CONTESTO_CLIENT


class GestorePosta(socketserver.BaseRequestHandler):
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
            sock = CONTESTO_SERVER.wrap_socket(sock, server_side=True)
        r, w = sock.makefile('rb'), sock.makefile('wb')

        def manda(riga):
            w.write((riga + '\r\n').encode('utf-8'))
            w.flush()
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
                sock = CONTESTO_SERVER.wrap_socket(sock, server_side=True)
                r, w = sock.makefile('rb'), sock.makefile('wb')
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
                    manda('550 5.1.1 utente sconosciuto')
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
                if c['ritardo']:
                    orologio.sleep(c['ritardo'])
                if c['errore_data']:
                    manda(c['errore_data'])
                else:
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

    def __init__(self, ssl_diretto=False):
        super().__init__(('127.0.0.1', 0), GestorePosta)
        self.ssl_diretto = ssl_diretto
        self.ripristina()
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def porta(self):
        return self.server_address[1]

    def ripristina(self, **altro):
        self.messaggi = []
        self.comportamento = {'ssl': self.ssl_diretto, 'starttls': not self.ssl_diretto, 'auth': True,
                              'utente': UTENTE, 'password': PASSWORD_APP, 'rifiuta_rcpt': False,
                              'errore_data': None, 'ritardo': 0}
        self.comportamento.update(altro)


POSTA = ServerPosta()
POSTA_SSL = ServerPosta(ssl_diretto=True)


def porta_chiusa():
    with socket.socket() as x:
        x.bind(('127.0.0.1', 0))
        return x.getsockname()[1]


def messaggio(i=-1):
    return email.message_from_bytes(POSTA.messaggi[i]['dati'], policy=policy.default)


# ============================================================ finta Meta
class GestoreMeta(BaseHTTPRequestHandler):
    def do_POST(self):
        srv = self.server
        corpo = self.rfile.read(int(self.headers.get('Content-Length') or 0))
        srv.richieste.append({'percorso': self.path, 'auth': self.headers.get('Authorization'),
                              'corpo': json.loads(corpo or b'{}')})
        stato, risposta = srv.risposta
        if risposta is None:
            risposta = {'messaging_product': 'whatsapp', 'messages': [{'id': 'wamid.PROVA%d' % len(srv.richieste)}]}
        dati = risposta.encode('utf-8') if isinstance(risposta, str) else json.dumps(risposta).encode('utf-8')
        self.send_response(stato)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(dati)))
        self.end_headers()
        self.wfile.write(dati)

    def log_message(self, *argomenti):
        pass


class ServerMeta(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(('127.0.0.1', 0), GestoreMeta)
        self.ripristina()
        threading.Thread(target=self.serve_forever, daemon=True).start()

    def ripristina(self, stato=200, risposta=None):
        self.richieste = []
        self.risposta = (stato, risposta)


META = ServerMeta()


# ================================================================ il mondo
def collega(S):
    A.Sessione = S
    A._registro = None
    viste._sessionmaker = lambda: S
    return A.app.test_client()


def fabbrica():
    return A.Sessione()


def configura(S, email_ok=True, whatsapp=False, **altro):
    s = S()
    if email_ok:
        for k, v in (('email_utente', UTENTE), ('email_password', invii.proteggi(PASSWORD_APP)),
                     ('email_server', '127.0.0.1'), ('email_porta', str(POSTA.porta)),
                     ('email_sicurezza', 'starttls'), ('email_attiva', '1')):
            scrivi_impostazione(s, k, v)
    if whatsapp:
        for k, v in (('wa_token', invii.proteggi(TOKEN)), ('wa_numero_id', '123456789'),
                     ('wa_indirizzo', 'http://127.0.0.1:%d' % META.server_address[1])):
            scrivi_impostazione(s, k, v)
    for k, v in altro.items():
        scrivi_impostazione(s, k, v)
    s.commit()
    s.close()


def mondo(email_ok=True, whatsapp=False, struttura='Clinica Posillipo'):
    """Una clinica di prova: la struttura con i recapiti, la sala endoscopica,
    una sala operatoria, il Dr. Galasso e due colleghi, le prestazioni."""
    POSTA.ripristina()
    POSTA_SSL.ripristina()
    META.ripristina()
    S = crea_sessione('sqlite:///' + percorso_nuovo())
    s = S()
    servizi.prepara_primo_avvio(s)
    st = s.get(Struttura, 1)
    st.nome, st.societa = struttura, 'Societa di Prova S.r.l.'
    st.indirizzo, st.telefono, st.email = 'Via di Prova 1, Napoli', '081 0000000', 'segreteria@example.com'
    st.giorni_apertura = '1111110'
    s.add(Risorsa(nome='Sala A', tipo='SALA_OPERATORIA', struttura_id=1, ordine=10))
    s.add_all([Operatore(cognome='Galasso', nome=''), Operatore(cognome='Borrelli', nome='Ugo', giorni_sala='0010000'),
               Operatore(cognome='Lippi', nome='Anna')])
    s.add(Prestazione(nome='Visita gastroenterologica', durata_min=30))
    s.commit()
    s.close()
    configura(S, email_ok, whatsapp)
    return S, collega(S)


def ids(S):
    s = S()
    d = {r.nome: r.id for r in s.scalars(select(Risorsa))}
    d.update({o.cognome: o.id for o in s.scalars(select(Operatore))})
    d.update({p.nome: p.id for p in s.scalars(select(Prestazione))})
    s.close()
    return d


def html(r):
    return r.get_data(as_text=True)


def testo(r):
    return ' '.join(unescape(re.sub(r'<[^>]+>', ' ', html(r))).split())


def avvisi(C):
    with C.session_transaction() as sess:
        m = sess.get('_flashes', [])
        sess['_flashes'] = []
    return unescape(re.sub(r'<[^>]+>', '', ' '.join(str(x[1]) for x in m)))


def categorie(C):
    with C.session_transaction() as sess:
        m = sess.get('_flashes', [])
        sess['_flashes'] = []
    return [x[0] for x in m]


def prenota(C, I, medico='Galasso', prestazione='EGDS', quando=ORA9, cognome='Fintini', nome='Mara',
            telefono='333 000 0001', email_paziente='mara.fintini@example.com', stanza='Sala endoscopia', aid=None,
            **altro):
    dati = {'risorsa': I[stanza], 'operatore': I[medico], 'prestazione': I[prestazione], 'struttura': 1,
            'data': quando.date().isoformat(), 'ora': quando.strftime('%H:%M'), 'durata': '30',
            'paziente': cognome, 'nome_paziente': nome, 'telefono': telefono, 'email_paziente': email_paziente,
            'tipo': '', 'degenza': ''}
    dati.update(altro)
    return C.post('/appuntamento/%d' % aid if aid else '/appuntamento', data=dati)


def ultimo(S, modello=Appuntamento):
    s = S()
    x = s.scalars(select(modello).order_by(modello.id.desc())).first()
    xid = x.id if x is not None else None
    s.close()
    return xid


def invii_tutti(S):
    s = S()
    righe = [dict(id=x.id, canale=x.canale, motivo=x.motivo, stato=x.stato, destinatario=x.destinatario,
                  appuntamento_id=x.appuntamento_id, paziente_id=x.paziente_id, regola_id=x.regola_id,
                  errore=x.errore, tentativi=x.tentativi, prossimo=x.prossimo, a_mano=x.a_mano,
                  oggetto=x.oggetto, testo=x.testo, per_inizio=x.per_inizio)
             for x in s.scalars(select(Invio).order_by(Invio.id))]
    s.close()
    return righe


def regola_galasso(S, oggetto=invii.PRONTA_OGGETTO, testo=invii.PRONTA_TESTO, allegati=True, prestazioni=None):
    """La regola gia' pronta, creata come fa il pulsante."""
    s = S()
    medico = s.scalars(select(Operatore).where(Operatore.cognome == 'Galasso')).first()
    r = invii.crea_regola_pronta(s, medico)
    r.oggetto, r.testo = oggetto, testo
    if not allegati:
        r.allegati.clear()
    if prestazioni is not None:
        r.prestazioni = ','.join(str(x) for x in prestazioni)
    s.commit()
    rid = r.id
    s.close()
    return rid


def nuovo_paziente(S, **campi):
    s = S()
    p = Paziente(**campi)
    s.add(p)
    s.commit()
    pid = p.id
    s.close()
    return pid


def nuovo_app(S, stanza, medico, inizio, minuti=30, stato='PRENOTATO', **altro):
    s = S()
    a = Appuntamento(risorsa_id=stanza, operatore_id=medico, inizio=inizio, fine=inizio + timedelta(minutes=minuti),
                     stato=stato, **altro)
    s.add(a)
    s.commit()
    aid = a.id
    s.close()
    return aid


def imposta(S, **valori):
    s = S()
    for k, v in valori.items():
        scrivi_impostazione(s, k, v)
    s.commit()
    s.close()


PDF_FINTO = b'%PDF-1.4\n% documento di prova\n1 0 obj <<>> endobj\ntrailer <<>>\n%%EOF\n'


# ===================================================== schema e aggiornamento
area('schema e aggiornamento')


def a_nuovo_database():
    S = crea_sessione('sqlite:///' + percorso_nuovo())
    with S.motore.connect() as c:
        tabelle = {r[0] for r in c.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        colonne = {r[1] for r in c.exec_driver_sql('PRAGMA table_info(pazienti)')}
        indici = {r[1] for r in c.exec_driver_sql('PRAGMA index_list(invii)')}
        versione = c.exec_driver_sql("SELECT valore FROM impostazioni WHERE chiave='versione_schema'").scalar()
    assert {'regole_email', 'allegati_regole', 'invii'} <= tabelle, tabelle
    assert 'indirizzo' in colonne
    assert VERSIONE_SCHEMA >= 7 and versione == str(VERSIONE_SCHEMA), versione
    assert len(indici) >= 3, indici


def a_aggiornamento_dalla_146():
    """Un database della 1.4.6 (schema 6): colonna e tabelle nuove, copia di
    sicurezza, email della clinica nelle strutture Posillipo senza email."""
    import marchio
    percorso = percorso_nuovo('v6')
    S0 = crea_sessione('sqlite:///' + percorso)
    s = S0()
    servizi.prepara_primo_avvio(s)
    s.get(Struttura, 1).nome = 'Clinica Posillipo'
    precedente = open(os.path.join(CARTELLA, 'static', 'logo-posillipo-precedente.png'), 'rb').read()
    s.get(Struttura, 1).logo = marchio.normalizza_logo(precedente)
    s.get(Struttura, 1).logo_aggiornato = datetime.now() - timedelta(days=30)
    s.add(Struttura(nome='Altra sede'))
    s.add(Paziente(cognome='Fintini', nome='Mara', telefono='333 000 0001'))
    s.commit()
    s.close()
    S0.motore.dispose()
    c = sqlite3.connect(percorso)
    for t in ('invii', 'allegati_regole', 'regole_email'):
        c.execute('DROP TABLE %s' % t)
    c.execute('ALTER TABLE pazienti DROP COLUMN indirizzo')
    c.execute("UPDATE impostazioni SET valore = '6' WHERE chiave = 'versione_schema'")
    c.commit()
    c.close()
    S = crea_sessione('sqlite:///' + percorso)
    assert S.versione_precedente == 6, S.versione_precedente
    assert 'pazienti.indirizzo' in S.colonne_aggiunte, S.colonne_aggiunte
    assert any('prima-della-versione-%d' % VERSIONE_SCHEMA in m for m in S.migrazioni), S.migrazioni
    s = S()
    assert servizi.email_della_struttura(s, S.colonne_aggiunte) == ['Clinica Posillipo']
    st = {x.nome: x.email for x in s.scalars(select(Struttura))}
    assert st == {'Clinica Posillipo': servizi.EMAIL_POSILLIPO, 'Altra sede': ''}, st
    assert servizi.logo_nuovo(s, S.colonne_aggiunte) == ['Clinica Posillipo']
    assert s.get(Struttura, 1).logo == marchio.normalizza_logo(
        open(os.path.join(CARTELLA, 'static', 'logo-posillipo.png'), 'rb').read())
    p = s.scalars(select(Paziente)).one()
    assert (p.cognome, p.telefono, p.indirizzo) == ('Fintini', '333 000 0001', ''), (p.cognome, p.indirizzo)
    assert s.scalars(select(Invio)).all() == []
    # solo in quell'avvio: tolta a mano, non torna
    s.get(Struttura, 1).email = ''
    s.commit()
    assert servizi.email_della_struttura(s, []) == []
    s.close()
    S2 = crea_sessione('sqlite:///' + percorso)
    assert S2.versione_precedente == VERSIONE_SCHEMA and not S2.migrazioni and not S2.colonne_aggiunte
    s = S2()
    assert servizi.email_della_struttura(s, S2.colonne_aggiunte) == [] and s.get(Struttura, 1).email == ''
    s.close()


def a_logo_nuovo():
    """Aggiornando alla 1.5, dove c'e' il logo precedente della Clinica
    Posillipo arriva quello nuovo, con "Longevity Institute". Un logo diverso,
    caricato a mano, resta; una struttura senza logo resta senza."""
    import marchio
    from io import BytesIO
    from PIL import Image
    statica = os.path.join(CARTELLA, 'static')
    vecchio = open(os.path.join(statica, 'logo-posillipo-precedente.png'), 'rb').read()
    nuovo = marchio.normalizza_logo(open(os.path.join(statica, 'logo-posillipo.png'), 'rb').read())
    altro = marchio.normalizza_logo(open(os.path.join(statica, 'icona.png'), 'rb').read())
    S = crea_sessione('sqlite:///' + percorso_nuovo())
    s = S()
    servizi.prepara_primo_avvio(s)
    st = s.get(Struttura, 1)
    ieri = datetime.now() - timedelta(days=1)
    # come lo aveva copiato nel database la 1.2
    st.nome, st.logo, st.logo_aggiornato = 'Clinica Posillipo', marchio.normalizza_logo(vecchio), ieri
    s.add_all([Struttura(nome='Sede con il suo logo', logo=altro, logo_aggiornato=ieri),
               Struttura(nome='Sede senza logo')])
    s.commit()
    assert servizi.logo_nuovo(s, []) == [], 'cambiato fuori dall\'aggiornamento alla 1.5'
    assert servizi.logo_nuovo(s, ['pazienti.indirizzo']) == ['Clinica Posillipo']
    loghi = {x.nome: (x.logo, x.ha_logo) for x in s.scalars(select(Struttura))}
    assert loghi == {'Clinica Posillipo': (nuovo, True), 'Sede con il suo logo': (altro, True),
                     'Sede senza logo': (None, False)}, {k: (len(v[0] or b''), v[1]) for k, v in loghi.items()}
    assert s.get(Struttura, 1).logo_aggiornato > ieri, 'la data del logo fa ricaricare l\'immagine nel browser'
    assert Image.open(BytesIO(nuovo)).size == (800, 133)
    assert servizi.logo_nuovo(s, ['pazienti.indirizzo']) == [], 'il nuovo scambiato per il vecchio'
    s.close()
    # il riconoscimento regge a ricodifiche e ridimensionamenti, non scambia loghi diversi
    im = Image.open(BytesIO(vecchio)).convert('RGBA')
    fondo = Image.new('RGBA', im.size, (255, 255, 255, 255))
    fondo.alpha_composite(im)
    jpg, piccolo = BytesIO(), BytesIO()
    fondo.convert('RGB').save(jpg, 'JPEG', quality=60)
    im.resize((360, 50)).save(piccolo, 'PNG')
    assert marchio.stesso_logo(marchio.normalizza_logo(jpg.getvalue()), vecchio)
    assert marchio.stesso_logo(marchio.normalizza_logo(piccolo.getvalue()), vecchio)
    assert not marchio.stesso_logo(nuovo, vecchio) and not marchio.stesso_logo(altro, vecchio)
    assert not marchio.stesso_logo(None, vecchio) and not marchio.stesso_logo(b'non un PNG', vecchio)
    # stesse proporzioni, disegno diverso; stesso disegno, proporzioni diverse
    stirato, largo = BytesIO(), BytesIO()
    Image.open(BytesIO(nuovo)).resize((805, 100)).save(stirato, 'PNG')      # il vecchio, rifilato, e' 8,05 : 1
    im.resize((im.width * 2, im.height)).save(largo, 'PNG')
    assert not marchio.stesso_logo(stirato.getvalue(), vecchio) and not marchio.stesso_logo(largo.getvalue(), vecchio)


def a_email_esistente_non_toccata():
    S = crea_sessione('sqlite:///' + percorso_nuovo())
    s = S()
    servizi.prepara_primo_avvio(s)
    st = s.get(Struttura, 1)
    st.nome, st.email = 'Clinica Posillipo', 'altra@example.com'
    s.commit()
    assert servizi.email_della_struttura(s, ['pazienti.indirizzo']) == []
    assert s.get(Struttura, 1).email == 'altra@example.com'
    s.close()


prova('database nuovo: tabelle dei messaggi, indirizzo del paziente, versione dello schema', a_nuovo_database)
prova('aggiornamento dalla 1.4.6: colonne, copia di sicurezza, email della clinica una volta sola',
      a_aggiornamento_dalla_146)
def a_versione():
    """La versione mostrata in Aiuto e' quella dell'installatore: e' quella che
    il Setup confronta con la versione gia' installata."""
    import comune
    testo_iss = open(os.path.join(CARTELLA, 'installer.iss'), 'rb').read().decode('utf-8-sig')
    m = re.search(r'#define Versione "([^"]+)"', testo_iss)
    assert m and m.group(1) == comune.VERSIONE, (m.group(1) if m else None, comune.VERSIONE)
    assert 'DisableWelcomePage=no' in testo_iss and 'function ShouldSkipPage' in testo_iss
    # il preprocessore di Inno Setup prende per una sua direttiva ogni riga che comincia con #
    codice = testo_iss.replace('\r\n', '\n').split('[Code]', 1)[1].split('\n')
    assert not [r for r in codice if r.lstrip().startswith('#')], 'riga del [Code] che comincia con #'
    S, C = mondo()
    t = testo(C.get('/aiuto'))
    assert 'Gestionale Agende, versione %s' % comune.VERSIONE in t, t[-300:]
    assert 'Versione %s' % comune.VERSIONE in testo(C.get('/aiuto/stampa'))
    t = testo(C.get('/aiuto/aggiornare'))
    assert 'Non serve disinstallare' in t and 'GestionaleAgende-setup.exe' in t, t


prova('una struttura che ha già un\'email la tiene', a_email_esistente_non_toccata)
prova('versione in Aiuto uguale a quella dell\'installatore; guida all\'aggiornamento', a_versione)
prova('logo nuovo (Longevity Institute) al posto del precedente, solo dove c\'era quello', a_logo_nuovo)


# ================================================== campi nuovi del paziente
area('paziente: nascita, codice fiscale, indirizzo')


def b_nascita_dal_cf():
    oggi = date(2026, 10, 4)
    casi = [
        (cf_valido('FNTMRC80A15F839'), date(1980, 1, 15)),         # uomo
        (cf_valido('FNTMRA85D61F839'), date(1985, 4, 21)),         # donna: giorno + 40
        (cf_valido('FNTMRCULA1RF839'), date(1980, 1, 15)),         # omocodia: 8=U 0=L 5=R
        (cf_valido('FNTMRC10A15F839'), date(2010, 1, 15)),         # il 2010 e' passato
        (cf_valido('FNTMRC30A15F839'), date(1930, 1, 15)),         # il 2030 no
        (cf_valido('FNTMRC26T01F839'), date(1926, 12, 1)),         # quest'anno ma piu' avanti: secolo prima
        (cf_valido('FNTMRC26A01F839'), date(2026, 1, 1)),
        (cf_valido('FNTMRC80B30F839'), None),                      # 30 febbraio
        ('FNTMRC80A15F839Z' if cf_valido('FNTMRC80A15F839')[-1] != 'Z' else 'FNTMRC80A15F839Y', None),
        ('', None), ('NON UN CODICE', None),
    ]
    for cf, atteso in casi:
        trovato = pazienti.nascita_da_cf(cf, oggi)
        assert trovato == atteso, (cf, trovato, atteso)
    assert pazienti.nascita_da_cf(cf_valido('FNTMRC80A15F839').lower()) == date(1980, 1, 15)
    return '%d codici' % len(casi)


def b_leggi_campi():
    assert pazienti.leggi_nascita('') == (None, '')
    assert pazienti.leggi_nascita('1960-03-05') == (date(1960, 3, 5), '')
    assert pazienti.leggi_nascita('05/03/1960') == (date(1960, 3, 5), '')
    for brutta in ('2099-01-01', '1899-12-31', 'ieri', '1960-02-30'):
        d, e = pazienti.leggi_nascita(brutta)
        assert d is None and e.startswith('Data di nascita'), (brutta, d, e)
    cf = cf_valido('FNTMRC80A15F839')
    assert pazienti.leggi_codice_fiscale(' %s %s ' % (cf[:8].lower(), cf[8:])) == (cf, '')
    assert pazienti.leggi_codice_fiscale('') == ('', '')
    assert pazienti.leggi_codice_fiscale(cf[:15] + ('A' if cf[15] != 'A' else 'B'))[1].startswith('Codice fiscale')
    assert pazienti.leggi_indirizzo('  Via di Prova\n 3,\t Napoli ') == ('Via di Prova 3, Napoli', '')
    assert pazienti.leggi_indirizzo('x' * 201)[1].startswith('Indirizzo')
    assert pazienti.leggi_indirizzo('x' * 200) == ('x' * 200, '')


def b_avviso_nascita():
    cf = cf_valido('FNTMRC25A15F839')
    assert pazienti.avviso_nascita(cf, date(1925, 1, 15)) == ''      # il secolo nel codice non c'e'
    assert pazienti.avviso_nascita(cf, date(2025, 1, 15)) == ''
    assert pazienti.avviso_nascita(cf, None) == '' and pazienti.avviso_nascita('', date(1980, 1, 1)) == ''
    m = pazienti.avviso_nascita(cf, date(1925, 1, 16))
    assert 'non corrisponde' in m and '16/01/1925' in m and '15/01/' in m, m


def b_prenotazione_con_campi():
    S, C = mondo()
    I = ids(S)
    cf = cf_valido('FNTMRA85D61F839')
    r = prenota(C, I, prestazione='Visita gastroenterologica', data_nascita='1985-04-21', codice_fiscale=cf.lower(),
                indirizzo_paziente='  Via di Prova 3,   80100 Napoli ')
    assert r.status_code == 302, r.status_code
    s = S()
    p = s.scalars(select(Paziente)).one()
    assert (p.data_nascita, p.codice_fiscale, p.indirizzo) == (date(1985, 4, 21), cf, 'Via di Prova 3, 80100 Napoli'), \
        (p.data_nascita, p.codice_fiscale, p.indirizzo)
    assert s.get(Appuntamento, ultimo(S)).paziente_id == p.id
    s.close()
    assert 'non corrisponde' not in avvisi(C)


def b_prenotazione_errori():
    S, C = mondo()
    I = ids(S)
    cf = cf_valido('FNTMRA85D61F839')
    casi = [({'codice_fiscale': cf[:15] + ('A' if cf[15] != 'A' else 'B')}, 'Codice fiscale'),
            ({'data_nascita': (OGGI + timedelta(days=1)).isoformat()}, 'Data di nascita'),
            ({'indirizzo_paziente': 'Via ' + 'x' * 200}, 'Indirizzo')]
    for campi, parola in casi:
        r = prenota(C, I, **dict(campi, note='nota da non perdere'))
        assert r.status_code == 200, r.status_code
        assert parola in testo(r), parola          # il messaggio e' nella pagina rimandata indietro
        pagina = html(r)
        assert 'value="Fintini"' in pagina and 'nota da non perdere' in pagina, 'il modulo ha perso i dati'
        assert ultimo(S) is None and ultimo(S, Paziente) is None
    # la data sbagliata non e' un errore se c'e' il codice: e' un avviso, il resto si salva
    r = prenota(C, I, codice_fiscale=cf, data_nascita='1985-04-22')
    assert r.status_code == 302 and 'non corrisponde' in avvisi(C)


def b_paziente_scelto_aggiornato():
    S, C = mondo(email_ok=False)
    I = ids(S)
    pid = nuovo_paziente(S, cognome='Fintini', nome='Mara', telefono='333 000 0001')
    cf = cf_valido('FNTMRA85D61F839')
    prenota(C, I, prestazione='Visita gastroenterologica', paziente_id=pid, data_nascita='1985-04-21',
            codice_fiscale=cf, indirizzo_paziente='Via di Prova 3')
    s = S()
    p = s.get(Paziente, pid)
    assert (p.data_nascita, p.codice_fiscale, p.indirizzo) == (date(1985, 4, 21), cf, 'Via di Prova 3')
    s.close()
    # campi lasciati vuoti: la scheda non perde niente
    prenota(C, I, prestazione='Visita gastroenterologica', quando=ORA9 + timedelta(hours=2), paziente_id=pid,
            email_paziente='')
    s = S()
    p = s.get(Paziente, pid)
    assert (p.data_nascita, p.codice_fiscale, p.indirizzo) == (date(1985, 4, 21), cf, 'Via di Prova 3')
    assert s.scalar(select(func.count()).select_from(Paziente)) == 1
    s.close()


def b_stesso_cf_stesso_paziente():
    """Stesso cognome e codice fiscale, telefono diverso: e' lui; il numero
    nuovo va nel secondo telefono."""
    S, C = mondo(email_ok=False)
    I = ids(S)
    cf = cf_valido('FNTMRA85D61F839')
    pid = nuovo_paziente(S, cognome='Fintini', nome='Mara', telefono='333 000 0001', codice_fiscale=cf)
    prenota(C, I, prestazione='Visita gastroenterologica', telefono='347 000 0009', codice_fiscale=cf,
            indirizzo_paziente='Via di Prova 3')
    s = S()
    assert s.scalar(select(func.count()).select_from(Paziente)) == 1
    p = s.get(Paziente, pid)
    assert (p.telefono, p.telefono2, p.indirizzo) == ('333 000 0001', '347 000 0009', 'Via di Prova 3')
    assert s.get(Appuntamento, ultimo(S)).paziente_id == pid
    s.close()


def b_stesso_telefono_altro_cf():
    """Stesso cognome e telefono ma un altro codice fiscale: un familiare,
    non la stessa persona."""
    S, C = mondo(email_ok=False)
    I = ids(S)
    nuovo_paziente(S, cognome='Fintini', nome='', telefono='333 000 0001', codice_fiscale=cf_valido('FNTMRA85D61F839'))
    prenota(C, I, prestazione='Visita gastroenterologica', nome='', codice_fiscale=cf_valido('FNTLCU12C03F839'))
    s = S()
    assert s.scalar(select(func.count()).select_from(Paziente)) == 2
    s.close()
    # senza codice fiscale si riusa come prima
    S, C = mondo(email_ok=False)
    I = ids(S)
    pid = nuovo_paziente(S, cognome='Fintini', nome='', telefono='333 000 0001')
    prenota(C, I, prestazione='Visita gastroenterologica', nome='')
    s = S()
    assert s.scalar(select(func.count()).select_from(Paziente)) == 1 and s.get(Appuntamento, ultimo(S)).paziente_id == pid
    s.close()


def b_scheda_paziente():
    S, C = mondo(email_ok=False)
    cf = cf_valido('FNTMRA85D61F839')
    r = C.post('/pazienti/nuovo', data={'cognome': 'Fintini', 'nome': 'Mara', 'telefono': '333 000 0001',
                                        'codice_fiscale': cf, 'data_nascita': '1985-04-20', 'canale': 'WHATSAPP',
                                        'promemoria': '1', 'indirizzo': 'Via di Prova 3, Napoli', 'provenienza': ''})
    assert r.status_code == 302, r.status_code
    assert categorie(C) == ['avviso']
    s = S()
    p = s.scalars(select(Paziente)).one()
    assert p.indirizzo == 'Via di Prova 3, Napoli'
    pid = p.id
    s.close()
    pagina = html(C.get('/pazienti/%d' % pid))
    assert 'name="indirizzo"' in pagina and 'Via di Prova 3, Napoli' in pagina
    r = C.post('/pazienti/%d' % pid, data={'cognome': 'Fintini', 'nome': 'Mara', 'telefono': '333 000 0001',
                                           'canale': 'WHATSAPP', 'indirizzo': 'x' * 201, 'provenienza': ''})
    assert r.status_code == 200 and 'Indirizzo: al massimo 200 caratteri' in testo(r)


def b_ricerca_json():
    S, C = mondo(email_ok=False)
    cf = cf_valido('FNTMRA85D61F839')
    nuovo_paziente(S, cognome='Fintini', nome='Mara', telefono='333 000 0001', codice_fiscale=cf,
                   data_nascita=date(1985, 4, 21), indirizzo='Via di Prova 3')
    dati = json.loads(C.get('/pazienti/cerca?q=fintini').get_data(as_text=True))
    assert dati and dati[0]['nascita_iso'] == '1985-04-21' and dati[0]['codice_fiscale'] == cf \
        and dati[0]['indirizzo'] == 'Via di Prova 3', dati
    assert json.loads(C.get('/pazienti/cerca?q=' + cf.lower()).get_data(as_text=True)), 'il codice fiscale non si trova'


def b_unisci_e_elimina():
    S, C = mondo(email_ok=False)
    tenuto = nuovo_paziente(S, cognome='Fintini', nome='Mara', telefono='333 000 0001')
    doppio = nuovo_paziente(S, cognome='Fintini', nome='Mara', telefono='333 000 0002', indirizzo='Via di Prova 3')
    s = S()
    s.add(Invio(canale='EMAIL', motivo='PROVA', destinatario='x@example.com', paziente_id=doppio, stato='INVIATO'))
    s.commit()
    pazienti.unisci(s, s.get(Paziente, tenuto), s.get(Paziente, doppio))
    s.commit()
    assert s.scalars(select(Invio)).one().paziente_id == tenuto
    assert s.get(Paziente, tenuto).indirizzo == 'Via di Prova 3'
    s.close()
    r = C.post('/pazienti/%d' % tenuto, data={'azione': 'elimina'})
    assert r.status_code == 302
    s = S()
    assert s.get(Paziente, tenuto) is None
    x = s.scalars(select(Invio)).one()
    assert x.paziente_id is None, 'il registro dei messaggi deve restare, sciolto'
    s.close()


def b_modulo_protegge():
    S, C = mondo(email_ok=False)
    pid = nuovo_paziente(S, cognome='Fintini', nome='Mara', indirizzo='<b>Via</b> "di" Prova',
                         data_nascita=date(1985, 4, 21))
    pagina = html(C.get('/appuntamento?paziente_id=%d' % pid))
    for nome in ('data_nascita', 'codice_fiscale', 'indirizzo_paziente'):
        assert 'name="%s"' % nome in pagina, nome
    assert '<b>Via</b>' not in pagina and '&lt;b&gt;Via&lt;/b&gt; &#34;di&#34; Prova' in pagina, 'indirizzo non protetto'
    assert 'value="1985-04-21"' in pagina and 'max="%s"' % OGGI.isoformat() in pagina


def b_segnaposto():
    S, C = mondo(email_ok=False)
    I = ids(S)
    pid = nuovo_paziente(S, cognome='Fintini', nome='Mara', indirizzo='Via di Prova 3')
    aid = nuovo_app(S, I['Sala endoscopia'], I['Galasso'], ORA9, paziente_id=pid)
    s = S()
    a = s.get(Appuntamento, aid)
    assert documenti.compila('{indirizzo_paziente} / {Indirizzo_paziente}{indirizzo}', a) == \
        'Via di Prova 3 / Via di Prova 3, Via di Prova 1, Napoli'
    assert 'indirizzo_paziente' in documenti.SEGNAPOSTO_MODULI
    s.close()


def b_importa_indirizzo():
    S, C = mondo(email_ok=False)
    righe = [['Rubrica'], [], ['Cognome', 'Nome', 'Cellulare', 'Indirizzo', 'CAP', 'Città', 'Indirizzo e-mail']]
    righe += [['Fintini', 'Mara', '333 000 0001', 'Via di Prova 3', 80100, 'Napoli', 'mara.fintini@example.com'],
              ['Esempietti', 'Ugo', '333 000 0004', 'Piazza Finta 9', None, 'Pozzuoli', '']] * 3
    a = importa.analizza({'nome': 'Rubrica', 'righe': righe})
    mappa = {a['intestazioni'][j]: a['campi'][pos] for pos, j in a['posizioni']}
    assert mappa == {'Cognome': 'cognome', 'Nome': 'nome', 'Cellulare': 'telefono', 'Indirizzo': 'indirizzo',
                     'CAP': 'indirizzo', 'Città': 'indirizzo', 'Indirizzo e-mail': 'email'}, mappa
    s = S()
    piano = importa.prepara(s, a, importa.opzioni_da({'struttura': '1'}, a))
    esito = importa.esegui(s, piano, 'rubrica.xlsx')
    assert esito['pazienti_nuovi'] == 2, esito
    trovati = {p.cognome: p.indirizzo for p in s.scalars(select(Paziente))}
    assert trovati == {'Fintini': 'Via di Prova 3, 80100, Napoli', 'Esempietti': 'Piazza Finta 9, Pozzuoli'}, trovati
    s.close()


prova('data di nascita dal codice fiscale: donne, omocodia, secolo', b_nascita_dal_cf)
prova('lettura dei campi: date, codice fiscale, indirizzo', b_leggi_campi)
prova('avviso se data di nascita e codice fiscale non tornano', b_avviso_nascita)
prova('prenotazione di un paziente nuovo con nascita, codice fiscale e indirizzo', b_prenotazione_con_campi)
prova('prenotazione: campi sbagliati fermano il salvataggio senza perdere il modulo', b_prenotazione_errori)
prova('paziente scelto dall\'elenco: i campi aggiornano la scheda, i vuoti non cancellano', b_paziente_scelto_aggiornato)
prova('stesso codice fiscale e cognome: stessa scheda, il numero nuovo non si perde', b_stesso_cf_stesso_paziente)
prova('stesso telefono ma altro codice fiscale: un familiare, scheda nuova', b_stesso_telefono_altro_cf)
prova('scheda del paziente: indirizzo, avviso, limite di lunghezza', b_scheda_paziente)
prova('ricerca del modulo: nascita, codice fiscale e indirizzo per riempire i campi', b_ricerca_json)
prova('unione ed eliminazione: il registro dei messaggi segue la persona o resta sciolto', b_unisci_e_elimina)
prova('modulo di prenotazione: campi presenti e testo protetto', b_modulo_protegge)
prova('moduli da stampare: {indirizzo_paziente}', b_segnaposto)
prova('import da Excel: indirizzo anche in più colonne, "indirizzo e-mail" resta email', b_importa_indirizzo)



def parti(m):
    """(testo semplice, html, allegati [(nome, dati)], immagini in linea)."""
    semplice = m.get_body(('plain',)).get_content()
    pagina = m.get_body(('html',)).get_content()
    allegati = [(x.get_filename(), x.get_payload(decode=True)) for x in m.iter_attachments()]
    immagini = [x for x in m.walk() if x.get_content_maintype() == 'image']
    return semplice, pagina, allegati, immagini


# ===================================================== regole delle email
area('email automatiche: regole e coda')


def c_regola_pronta():
    S, C = mondo()
    I = ids(S)
    pagina = testo(C.get('/invii'))
    assert 'Crea la regola già pronta' in pagina and 'Dr. Galasso' in pagina, 'manca la regola già pronta'
    r = C.post('/invii', data={'azione': 'regola_pronta'})
    assert r.status_code == 302 and '/invii/regole/' in r.headers['Location'], r.headers.get('Location')
    s = S()
    regola = s.scalars(select(RegolaEmail)).one()
    assert regola.attiva and regola.operatore_id == I['Galasso'], (regola.attiva, regola.operatore_id)
    assert regola.id_prestazioni == {I['EGDS'], I['Colonscopia']}, regola.id_prestazioni   # non la visita
    assert (regola.nome, regola.oggetto, regola.testo) == (invii.PRONTA_NOME, invii.PRONTA_OGGETTO, invii.PRONTA_TESTO)
    assert 'Dr. Giovanni Galasso' in regola.testo and 'quattro ore prima' in regola.testo
    allegati = [(g.nome, g.tipo, g.dati) for g in regola.allegati]
    assert [g[0] for g in allegati] == ['INFORMATIVA_EGDS.pdf', 'INFORMATIVA_COLONSCOPIA.pdf'], allegati
    for nome, tipo, dati in allegati:
        assert tipo == 'application/pdf' and dati.startswith(b'%PDF-')
        assert dati == open(os.path.join(CARTELLA, 'modelli_email', nome), 'rb').read(), nome
    s.close()
    assert 'Crea la regola già pronta' not in testo(C.get('/invii')), 'il pulsante resta dopo la creazione'
    r = C.post('/invii', data={'azione': 'regola_pronta'})
    s = S()
    assert s.scalar(select(func.count()).select_from(RegolaEmail)) == 1, 'creata due volte'
    s.close()
    return '%d KB di allegati' % (sum(len(g[2]) for g in allegati) // 1024)


def c_regola_pronta_casi():
    # nessuna prestazione endoscopica: la regola nasce spenta
    S, C = mondo()
    s = S()
    for p in s.scalars(select(Prestazione)):
        if p.nome in ('EGDS', 'Colonscopia'):
            p.nome = 'Esame %d' % p.id
    s.commit()
    s.close()
    C.post('/invii', data={'azione': 'regola_pronta'})
    assert 'spenta' in avvisi(C)
    s = S()
    r = s.scalars(select(RegolaEmail)).one()
    assert not r.attiva and not r.id_prestazioni
    s.close()
    # senza il Dr. Galasso fra i medici attivi: niente regola
    S, C = mondo()
    s = S()
    s.scalars(select(Operatore).where(Operatore.cognome == 'Galasso')).one().attivo = False
    s.commit()
    s.close()
    assert 'Crea la regola già pronta' not in testo(C.get('/invii'))
    C.post('/invii', data={'azione': 'regola_pronta'})
    assert 'manca il medico Galasso' in avvisi(C)
    s = S()
    assert s.scalars(select(RegolaEmail)).first() is None
    s.close()


def c_regole_per():
    S, C = mondo()
    I = ids(S)
    rid = regola_galasso(S)
    s = S()
    s.add(RegolaEmail(nome='Colon per tutti', operatore_id=None, prestazioni=str(I['Colonscopia']), oggetto='o', testo='t'))
    s.add(RegolaEmail(nome='Spenta', attiva=False, operatore_id=I['Galasso'], prestazioni='', oggetto='o', testo='t'))
    s.add(RegolaEmail(nome='Per tutto', operatore_id=None, prestazioni='', oggetto='o', testo='t'))
    s.add(RegolaEmail(nome='Benvenuto Lippi', operatore_id=I['Lippi'], prestazioni='', oggetto='o', testo='t'))
    s.commit()

    def nomi(medico, prestazione):
        a = Appuntamento(operatore_id=I[medico], prestazione_id=I[prestazione], inizio=ORA9)
        return [r.nome for r in invii.regole_per(s, a)]
    assert nomi('Galasso', 'EGDS') == [invii.PRONTA_NOME]
    # la sua per la colonscopia prende il posto di quella per tutti i medici
    assert nomi('Galasso', 'Colonscopia') == [invii.PRONTA_NOME]
    assert nomi('Galasso', 'Visita gastroenterologica') == []
    assert nomi('Borrelli', 'EGDS') == []
    assert nomi('Borrelli', 'Colonscopia') == ['Colon per tutti']
    # una del medico senza prestazioni si aggiunge: non toglie la preparazione a nessuno
    assert nomi('Lippi', 'Colonscopia') == ['Colon per tutti', 'Benvenuto Lippi']
    assert nomi('Lippi', 'EGDS') == ['Benvenuto Lippi']
    assert invii.regole_per(s, Appuntamento(operatore_id=None, prestazione_id=I['Colonscopia'], inizio=ORA9)) == []
    s.close()


def regola(S, nome, medico=None, prestazioni=(), attiva=True, testo='Gentile {paziente},\n\nistruzioni.',
           allegati=()):
    """Una regola di prova; l'oggetto e' il nome."""
    s = S()
    r = RegolaEmail(nome=nome, attiva=attiva, operatore_id=medico, prestazioni=','.join(map(str, prestazioni)),
                    oggetto=nome, testo=testo)
    for nome_file, dati in allegati:
        r.allegati.append(AllegatoRegola(nome=nome_file, tipo='application/pdf', dimensione=len(dati), dati=dati))
    s.add(r)
    s.commit()
    rid = r.id
    s.close()
    return rid


def c_email_per_medico():
    """Ogni medico la sua informativa: per la colonscopia della Dr.ssa Lippi
    parte la sua, con il suo PDF; per quella degli altri quella per tutti."""
    S, C = mondo()
    I = ids(S)
    tutti = regola(S, 'Preparazione colonscopia', None, [I['Colonscopia']], allegati=[('generica.pdf', PDF_FINTO)])
    lippi = regola(S, 'Preparazione colonscopia Lippi', I['Lippi'], [I['Colonscopia']],
                   allegati=[('lippi.pdf', PDF_FINTO + b'% Lippi\n')])
    prenota(C, I, medico='Lippi', prestazione='Colonscopia')
    m = avvisi(C)
    assert '«Preparazione colonscopia Lippi» in partenza' in m and '«Preparazione colonscopia»' not in m, m
    prenota(C, I, medico='Borrelli', prestazione='Colonscopia', quando=ORA9 + timedelta(hours=2), cognome='Esempietti',
            nome='Ugo', telefono='333 000 0004', email_paziente='ugo.esempietti@example.com')
    m = avvisi(C)
    assert '«Preparazione colonscopia» in partenza' in m, m
    righe = invii_tutti(S)
    assert [(x['regola_id'], x['destinatario']) for x in righe] == [
        (lippi, 'mara.fintini@example.com'), (tutti, 'ugo.esempietti@example.com')], righe
    esiti_ = invii.elabora(fabbrica)
    assert [e[1] for e in esiti_] == ['INVIATO', 'INVIATO'], esiti_
    arrivati = sorted((m['To'], m['Subject'], [a[0] for a in parti(m)[2]]) for m in (messaggio(0), messaggio(1)))
    assert arrivati == [('mara.fintini@example.com', 'Preparazione colonscopia Lippi', ['lippi.pdf']),
                        ('ugo.esempietti@example.com', 'Preparazione colonscopia', ['generica.pdf'])], arrivati


def c_cambio_medico():
    """Un'email ancora in coda (manca la rete) per il medico di prima: cambiato
    il medico, quella non parte piu' e parte quella del medico nuovo."""
    S, C = mondo()
    I = ids(S)
    galasso = regola_galasso(S, allegati=False)
    lippi = regola(S, 'Colonscopia Lippi', I['Lippi'], [I['Colonscopia']])
    POSTA.ripristina(errore_data='451 4.3.0 riprovare piu tardi')
    prenota(C, I, prestazione='Colonscopia')
    avvisi(C)
    aid = ultimo(S)
    assert invii.elabora(fabbrica)[0][1] == 'DA_INVIARE'          # riprova fra due minuti
    pid = invii_tutti(S)[0]['paziente_id']
    prenota(C, I, aid=aid, medico='Lippi', prestazione='Colonscopia', paziente_id=pid)
    m = avvisi(C)
    assert '«Colonscopia Lippi» in partenza' in m, m
    POSTA.ripristina()
    invii.elabora(fabbrica, adesso=datetime.now() + timedelta(minutes=3))
    stati = {x['regola_id']: (x['stato'], x['errore']) for x in invii_tutti(S)}
    assert stati == {galasso: ('ANNULLATO', invii.NON_VALE_PIU), lippi: ('INVIATO', '')}, stati
    assert len(POSTA.messaggi) == 1 and messaggio()['Subject'] == 'Colonscopia Lippi'
    assert invii.elabora(fabbrica, adesso=datetime.now() + timedelta(minutes=10)) == [], 'rimessa in coda due volte'


def c_primo_dei_due_eliminato():
    """Gastroscopia e colonscopia lo stesso giorno: una email sola, legata alla
    prima. Se la prima viene eliminata o disdetta prima che l'email parta,
    l'email passa alla seconda invece di perdersi."""
    for come in ('elimina', 'disdici'):
        S, C = mondo()
        I = ids(S)
        regola_galasso(S, allegati=False)
        POSTA.ripristina(errore_data='451 4.3.0 riprovare piu tardi')
        prenota(C, I)
        avvisi(C)
        primo = ultimo(S)
        pid = invii_tutti(S)[0]['paziente_id']
        prenota(C, I, prestazione='Colonscopia', quando=ORA9 + timedelta(minutes=30), paziente_id=pid)
        assert 'già mandata' in avvisi(C)
        secondo = ultimo(S)
        assert invii.elabora(fabbrica)[0][1] == 'DA_INVIARE'
        if come == 'elimina':
            C.post('/appuntamento/%d' % primo, data={'azione': 'elimina'})
            m = avvisi(C)
            assert "parte per l'altro appuntamento" in m, m
            attese = [('ANNULLATO', None, 'appuntamento eliminato'), ('DA_INVIARE', secondo, '')]
        else:
            C.post('/appuntamento/%d/stato' % primo, data={'stato': 'DISDETTO'})
            avvisi(C)
            invii.elabora(fabbrica, adesso=datetime.now() + timedelta(minutes=3))   # se ne accorge il thread
            attese = [('ANNULLATO', primo, 'appuntamento disdetto'), ('DA_INVIARE', secondo, '')]
        righe = invii_tutti(S)
        assert [(x['stato'], x['appuntamento_id'], x['errore']) for x in righe] == attese, (come, righe)
        POSTA.ripristina()
        esiti_ = invii.elabora(fabbrica, adesso=datetime.now() + timedelta(minutes=3))
        assert [e[1] for e in esiti_] == ['INVIATO'] and len(POSTA.messaggi) == 1, (come, esiti_)


def c_sostituto():
    """Ferie del medico: i suoi appuntamenti passano a un sostituto che ha la
    sua informativa, e ai pazienti parte quella del sostituto."""
    S, C = mondo()
    I = ids(S)
    regola_galasso(S, allegati=False)
    lippi = regola(S, 'Preparazione EGDS Lippi', I['Lippi'], [I['EGDS']])
    prenota(C, I)
    avvisi(C)
    aid = ultimo(S)
    assert [e[1] for e in invii.elabora(fabbrica)] == ['INVIATO']
    valore = '%s|%d|%d' % (ORA9.strftime('%Y-%m-%dT%H:%M'), I['Sala endoscopia'], I['Lippi'])
    r = C.post('/sposta', data={'medico': str(I['Galasso']), 'dal': MAR.isoformat(), 'al': MAR.isoformat(),
                                'modo': 'sostituto', 'sostituto': str(I['Lippi']), 'scelti': str(aid),
                                'p_%d' % aid: valore})
    assert r.status_code == 302, r.status_code
    m = avvisi(C)
    assert '1 appuntamento spostato' in m and '«Preparazione EGDS Lippi» in partenza' in m, m
    s = S()
    assert s.get(Appuntamento, aid).operatore_id == I['Lippi']
    s.close()
    x = invii_tutti(S)[-1]
    assert (x['regola_id'], x['stato'], x['appuntamento_id']) == (lippi, 'DA_INVIARE', aid), x


def c_duplica():
    S, C = mondo()
    I = ids(S)
    rid = regola_galasso(S)
    r = C.post('/invii/regole/%d' % rid, data={'azione': 'duplica', 'medico': str(I['Lippi'])})
    assert r.status_code == 302
    m = avvisi(C)
    assert 'Copia creata per Lippi Anna, spenta' in m, m
    s = S()
    orig = s.get(RegolaEmail, rid)
    copia = s.scalars(select(RegolaEmail).order_by(RegolaEmail.id.desc())).first()
    assert r.headers['Location'].endswith('/invii/regole/%d' % copia.id), r.headers['Location']
    assert (copia.nome, copia.attiva, copia.operatore_id, copia.id_prestazioni, copia.oggetto, copia.testo) == \
        (invii.PRONTA_NOME + ' · Lippi Anna', False, I['Lippi'], orig.id_prestazioni, orig.oggetto, orig.testo)
    assert [(g.nome, g.dati) for g in copia.allegati] == [(g.nome, g.dati) for g in orig.allegati]
    assert {g.id for g in copia.allegati}.isdisjoint({g.id for g in orig.allegati}), 'allegati in comune'
    copia_id, primo_allegato = copia.id, copia.allegati[0].id
    s.close()
    # spenta: non parte da sola
    prenota(C, I, medico='Lippi')
    avvisi(C)
    assert invii_tutti(S) == []
    # togliere un PDF dalla copia non lo toglie all'originale
    C.post('/invii/regole/%d' % copia_id, data={'azione': 'togli_allegato', 'allegato': str(primo_allegato)})
    s = S()
    assert len(s.get(RegolaEmail, copia_id).allegati) == 1 and len(s.get(RegolaEmail, rid).allegati) == 2
    s.close()
    # la copia di una copia non mette i nomi in fila
    C.post('/invii/regole/%d' % copia_id, data={'azione': 'duplica', 'medico': ''})
    avvisi(C)
    s = S()
    ultima = s.scalars(select(RegolaEmail).order_by(RegolaEmail.id.desc())).first()
    assert (ultima.nome, ultima.operatore_id, ultima.attiva) == (invii.PRONTA_NOME + ' · tutti i medici', None, False)
    s.close()
    senza = regola(S, 'Benvenuto', I['Borrelli'], [])
    C.post('/invii/regole/%d' % senza, data={'azione': 'duplica', 'medico': ''})
    assert 'serve almeno una prestazione' in avvisi(C)
    C.post('/invii/regole/%d' % rid, data={'azione': 'duplica', 'medico': '999'})
    assert 'Medico non valido' in avvisi(C)
    s = S()
    assert s.scalar(select(func.count()).select_from(RegolaEmail)) == 4
    s.close()


def c_pagine_per_medico():
    S, C = mondo()
    I = ids(S)
    rid = regola_galasso(S)                                  # Galasso: EGDS e colonscopia
    tutti = regola(S, 'Colon per tutti', None, [I['Colonscopia']])
    benvenuto = regola(S, 'Benvenuto Galasso', I['Galasso'], [])
    regola(S, 'Visita Lippi', I['Lippi'], [I['Visita gastroenterologica']])
    r = C.get('/invii')
    h, t = html(r), testo(r)
    # raggruppate per medico, in ordine di cognome; per ultime quelle per tutti
    posti = [t.index(x) for x in ('Galasso Email Prestazioni', 'Lippi Anna Email Prestazioni',
                                  'Per tutti i medici Partono')]
    assert posti == sorted(posti), posti
    for medico in ('Galasso', 'Lippi'):
        assert 'href="/invii/regole/nuova?medico=%d"' % I[medico] in h, medico
    assert 'href="/invii/regole/nuova?medico=0"' in h and 'name="medico"' in h
    assert "Non parte per Galasso (Colonscopia): lì c'è «%s»" % invii.PRONTA_NOME in t, t
    assert 'Al posto di «Colon per tutti» (per tutti i medici): Galasso (Colonscopia).' in t
    assert 'Parte insieme a «Benvenuto Galasso» per Galasso (Colonscopia, EGDS)' in t
    # una nuova "per" un medico: gia' scelto
    t = testo(C.get('/invii/regole/nuova?medico=%d' % I['Lippi']))
    h = html(C.get('/invii/regole/nuova?medico=%d' % I['Lippi']))
    assert 'Nuova email per Lippi Anna' in t and 'value="%d" selected' % I['Lippi'] in h
    assert 'selected' not in html(C.get('/invii/regole/nuova?medico=0')).split('id="operatore"')[1].split('</select>')[0]
    assert C.get('/invii/regole/nuova?medico=abc').status_code == 200
    # la pagina della regola dice con chi convive
    t = testo(C.get('/invii/regole/%d' % rid))
    assert 'Con le altre email' in t and 'Per Galasso (Colonscopia) parte questa, al posto di «Colon per tutti»' in t, t
    assert 'Parte insieme a «Benvenuto Galasso» per Galasso (Colonscopia, EGDS)' in t
    assert 'Duplica per un altro medico' in t
    t = testo(C.get('/invii/regole/%d' % tutti))
    assert 'Non parte per Galasso (Colonscopia): lì parte «%s»' % invii.PRONTA_NOME in t, t
    # salvandola, l'avviso delle due email
    dati = {'nome': 'Benvenuto Galasso', 'operatore': str(I['Galasso']), 'oggetto': 'Benvenuto', 'testo': 'Gentile paziente',
            'attiva': '1'}
    C.post('/invii/regole/%d' % benvenuto, data=dati, content_type='multipart/form-data')
    m = avvisi(C)
    assert 'Attenzione: insieme a questa parte anche «%s» per Galasso (Colonscopia, EGDS)' % invii.PRONTA_NOME in m, m
    # spenta: dice cosa succederebbe accendendola
    del dati['attiva']
    C.post('/invii/regole/%d' % benvenuto, data=dati, content_type='multipart/form-data')
    m = avvisi(C)
    assert 'Attenzione' not in m and 'spenta' in m, m
    assert '(quando sarà attiva)' in testo(C.get('/invii/regole/%d' % benvenuto))


def c_scheda_medico_e_appuntamento():
    S, C = mondo()
    I = ids(S)
    rid = regola_galasso(S)
    regola(S, 'Colon per tutti', None, [I['Colonscopia']])
    regola(S, 'Visita Lippi', I['Lippi'], [I['Visita gastroenterologica']], attiva=False)
    regola(S, 'EGDS Lippi', I['Lippi'], [I['EGDS']])
    h = html(C.get('/anagrafiche/medici/%d' % I['Galasso']))
    t = testo(C.get('/anagrafiche/medici/%d' % I['Galasso']))
    assert 'Email automatiche ai suoi pazienti' in t and invii.PRONTA_NOME in t, t
    assert 'href="/invii/regole/%d"' % rid in h and 'href="/invii/regole/nuova?medico=%d"' % I['Galasso'] in h
    t = testo(C.get('/anagrafiche/medici/%d' % I['Lippi']))
    assert 'Visita Lippi (spenta)' in t and 'EGDS Lippi' in t
    assert 'Nessuna email sua' in testo(C.get('/anagrafiche/medici/%d' % I['Borrelli']))
    assert 'Email automatiche ai suoi pazienti' not in testo(C.get('/anagrafiche/medici/nuovo'))
    # nell'appuntamento, perche' le altre email non partono da sole
    prenota(C, I, prestazione='Colonscopia')
    avvisi(C)
    t = testo(C.get('/appuntamento/%d' % ultimo(S)))
    assert "Colon per tutti (per questo medico c'è la sua)" in t and 'EGDS Lippi (è di Lippi Anna)' in t, t
    assert '%s (' % invii.PRONTA_NOME not in t, 'la sua email segnata come se non partisse'
    prenota(C, I, prestazione='Visita gastroenterologica', quando=ORA9 + timedelta(hours=3), cognome='Esempietti',
            nome='Ugo', telefono='333 000 0004', email_paziente='ugo.esempietti@example.com')
    avvisi(C)
    t = testo(C.get('/appuntamento/%d' % ultimo(S)))
    assert 'Colon per tutti (non è per questa prestazione)' in t and '%s (non è per questa prestazione)' % \
        invii.PRONTA_NOME in t, t


def c_prenotazione_in_coda():
    S, C = mondo()
    I = ids(S)
    rid = regola_galasso(S)
    r = prenota(C, I)
    assert r.status_code == 302
    m = avvisi(C)
    assert 'in partenza per mara.fintini@example.com' in m and invii.PRONTA_NOME in m, m
    x = invii_tutti(S)
    assert len(x) == 1, x
    x = x[0]
    aid = ultimo(S)
    assert (x['canale'], x['motivo'], x['stato'], x['destinatario'], x['appuntamento_id'], x['regola_id'], x['a_mano']) \
        == ('EMAIL', 'PREPARAZIONE', 'DA_INVIARE', 'mara.fintini@example.com', aid, rid, False), x
    assert x['per_inizio'] == ORA9 and x['paziente_id'] is not None
    # modificare l'appuntamento non la rimanda
    prenota(C, I, aid=aid, note='spostata la nota', paziente_id=x['paziente_id'])
    assert len(invii_tutti(S)) == 1, 'rimandata a ogni modifica'
    # un altro paziente sullo stesso appuntamento: a lui si'
    prenota(C, I, aid=aid, cognome='Esempietti', nome='Ugo', telefono='333 000 0004',
            email_paziente='ugo.esempietti@example.com')
    x = invii_tutti(S)
    assert len(x) == 2 and x[1]['destinatario'] == 'ugo.esempietti@example.com', x


def c_prenotazione_senza():
    S, C = mondo(email_ok=False)
    I = ids(S)
    regola_galasso(S)
    prenota(C, I)
    m = avvisi(C)
    assert 'non è ancora configurato' in m and categorie(C) == [], m
    assert invii_tutti(S) == []
    S, C = mondo()
    I = ids(S)
    regola_galasso(S)
    prenota(C, I, email_paziente='')
    assert 'non ha un indirizzo email' in avvisi(C)
    assert invii_tutti(S) == []
    # nessuna regola per la visita: nessun messaggio, nessun avviso
    prenota(C, I, prestazione='Visita gastroenterologica', quando=ORA9 + timedelta(hours=3))
    assert 'Email' not in avvisi(C) and invii_tutti(S) == []


def c_stesso_giorno():
    """Gastroscopia e colonscopia prenotate separatamente lo stesso giorno:
    una email sola (il testo parla gia' di tutte e due)."""
    S, C = mondo()
    I = ids(S)
    regola_galasso(S)
    prenota(C, I)
    avvisi(C)
    pid = invii_tutti(S)[0]['paziente_id']
    prenota(C, I, prestazione='Colonscopia', quando=ORA9 + timedelta(minutes=30), paziente_id=pid)
    m = avvisi(C)
    assert 'già mandata al paziente per l\'appuntamento delle 09:00' in m, m
    assert len(invii_tutti(S)) == 1
    # un altro giorno invece si'
    prenota(C, I, prestazione='Colonscopia', quando=ORA9 + timedelta(days=7), paziente_id=pid)
    assert len(invii_tutti(S)) == 2


def c_passato_e_serie():
    S, C = mondo()
    I = ids(S)
    regola_galasso(S)
    ieri = datetime.combine(OGGI - timedelta(days=1), time(9, 0))
    prenota(C, I, quando=ieri)
    assert invii_tutti(S) == [], 'email per un appuntamento già passato'
    prenota(C, I, quando=ORA9, ripeti='1', ripeti_ogni='1', ripeti_unita='settimane', ripeti_volte='3')
    s = S()
    assert s.scalar(select(func.count()).select_from(Appuntamento).where(Appuntamento.inizio >= ORA9)) == 3
    s.close()
    assert len(invii_tutti(S)) == 1, 'una serie deve mandare la preparazione una volta'


def c_da_confermare():
    S, C = mondo()
    I = ids(S)
    regola_galasso(S)
    pid = nuovo_paziente(S, cognome='Fintini', nome='Mara', telefono='333 000 0001', email='mara.fintini@example.com')
    s = S()
    x = Appunto(testo='EGDS Fintini', paziente_id=pid, operatore_id=I['Galasso'], prestazione_id=I['EGDS'],
                giorno=MAR, ora=time(9, 0), durata_min=30)
    s.add(x)
    s.commit()
    xid = x.id
    s.close()
    r = C.post('/da-confermare/prenota', data={'scelti': str(xid), 'risorsa': str(I['Sala endoscopia'])})
    assert r.status_code == 302
    m = avvisi(C)
    assert 'messi in agenda' in m and 'in partenza' in m, m
    righe = invii_tutti(S)
    assert len(righe) == 1 and righe[0]['appuntamento_id'] == ultimo(S), righe


def c_elimina_appuntamento():
    S, C = mondo()
    I = ids(S)
    regola_galasso(S)
    prenota(C, I)
    aid = ultimo(S)
    r = C.post('/appuntamento/%d' % aid, data={'azione': 'elimina'})
    assert r.status_code == 302
    x = invii_tutti(S)[0]
    assert (x['stato'], x['appuntamento_id'], x['errore']) == ('ANNULLATO', None, 'appuntamento eliminato'), x


def c_pagina_regola():
    S, C = mondo()
    I = ids(S)
    from io import BytesIO
    base = {'nome': 'Preparazione colonscopia', 'operatore': str(I['Lippi']), 'prestazioni': [str(I['Colonscopia'])],
            'oggetto': 'Preparazione per {giorno}', 'testo': 'Gentile {paziente},\n\nistruzioni.', 'attiva': '1'}
    r = C.post('/invii/regole/nuova', data=dict(base, allegati=(BytesIO(PDF_FINTO), 'istruzioni.pdf')),
               content_type='multipart/form-data')
    assert r.status_code == 302, r.status_code
    s = S()
    regola = s.scalars(select(RegolaEmail)).one()
    assert (regola.nome, regola.operatore_id, regola.id_prestazioni, regola.attiva) == \
        ('Preparazione colonscopia', I['Lippi'], {I['Colonscopia']}, True)
    assert [(g.nome, g.dati) for g in regola.allegati] == [('istruzioni.pdf', PDF_FINTO)]
    rid = regola.id
    s.close()
    casi = [(dict(base, allegati=(BytesIO(b'GIF89a finto'), 'foto.pdf')), 'non è un PDF'),
            (dict(base, allegati=(BytesIO(b'%PDF-' + b'0' * (10 * 1024 * 1024)), 'grande.pdf')), 'oltre 10 MB'),
            (dict(base, operatore='', prestazioni=[]), 'almeno un medico o una prestazione'),
            (dict(base, oggetto=''), 'Servono oggetto e testo'),
            (dict(base, nome='  '), 'Serve un nome')]
    for dati, parola in casi:
        r = C.post('/invii/regole/%d' % rid, data=dati, content_type='multipart/form-data')
        assert r.status_code in (200, 302) and (parola in testo(r) or parola in avvisi(C)), parola
    s = S()
    assert len(s.get(RegolaEmail, rid).allegati) == 1 and s.get(RegolaEmail, rid).oggetto == 'Preparazione per {giorno}'
    s.close()
    pagina = testo(C.get('/invii/regole/%d' % rid))
    assert 'istruzioni.pdf' in pagina and '{indirizzo_paziente}' in pagina


def c_togli_elimina_scarica():
    S, C = mondo()
    I = ids(S)
    rid = regola_galasso(S)
    s = S()
    g = s.get(RegolaEmail, rid).allegati[0]
    gid, dati = g.id, g.dati
    s.close()
    r = C.get('/invii/allegati/%d' % gid)
    assert r.mimetype == 'application/pdf' and r.headers['X-Content-Type-Options'] == 'nosniff' and r.data == dati
    assert C.get('/invii/allegati/999').status_code == 404
    C.post('/invii/regole/%d' % rid, data={'azione': 'togli_allegato', 'allegato': str(gid)})
    s = S()
    assert [x.nome for x in s.get(RegolaEmail, rid).allegati] == ['INFORMATIVA_COLONSCOPIA.pdf']
    assert s.get(AllegatoRegola, gid) is None
    s.close()
    prenota(C, I)
    C.post('/invii/regole/%d' % rid, data={'azione': 'elimina'})
    s = S()
    assert s.get(RegolaEmail, rid) is None and s.scalars(select(AllegatoRegola)).all() == []
    s.close()
    x = invii_tutti(S)[0]
    assert (x['stato'], x['regola_id'], x['errore']) == ('ANNULLATO', None, 'regola eliminata'), x


def c_anagrafiche_protette():
    S, C = mondo()
    I = ids(S)
    regola_galasso(S)
    r = C.post('/anagrafiche/medici/%d' % I['Galasso'], data={'azione': 'elimina'})
    m = avvisi(C)
    assert 'non si può eliminare' in m and 'email automatiche' in m, m
    r = C.post('/anagrafiche/prestazioni/%d' % I['EGDS'], data={'azione': 'elimina'})
    m = avvisi(C)
    assert 'non si può eliminare' in m and invii.PRONTA_NOME in m, m
    s = S()
    assert s.get(Operatore, I['Galasso']) is not None and s.get(Prestazione, I['EGDS']) is not None
    s.close()
    # una prestazione che nessuna regola usa si elimina come prima
    C.post('/anagrafiche/prestazioni/%d' % I['Ecografia'], data={'azione': 'elimina'})
    s = S()
    assert s.get(Prestazione, I['Ecografia']) is None
    s.close()


def c_difetto_non_blocca():
    """Un difetto nella parte dei messaggi non deve mai far perdere una
    prenotazione: l'appuntamento si salva e l'avviso lo dice."""
    S, C = mondo()
    I = ids(S)
    regola_galasso(S)
    originale = invii.dopo_salvataggio

    def rotta(*argomenti, **chiavi):
        raise RuntimeError('difetto finto')
    invii.dopo_salvataggio = rotta
    try:
        r = prenota(C, I)
        m = avvisi(C)
        s = S()
        x = Appunto(testo='EGDS', operatore_id=I['Galasso'], prestazione_id=I['EGDS'], giorno=MAR, ora=time(11, 0),
                    durata_min=30, cognome='Esempietti', telefono='333 000 0004')
        s.add(x)
        s.commit()
        xid = x.id
        s.close()
        r2 = C.post('/da-confermare/prenota', data={'scelti': str(xid), 'risorsa': str(I['Sala endoscopia'])})
        m2 = avvisi(C)
    finally:
        invii.dopo_salvataggio = originale
    assert r.status_code == 302 and 'Email automatica non preparata (difetto finto)' in m, m
    assert r2.status_code == 302 and '1 appuntamento messi in agenda' in m2 and 'difetto finto' in m2, m2
    s = S()
    assert s.scalar(select(func.count()).select_from(Appuntamento)) == 2
    s.close()


prova('regola già pronta: Galasso, EGDS e colonscopia (non la visita), testo e informative', c_regola_pronta)
prova('un difetto nei messaggi non fa perdere la prenotazione', c_difetto_non_blocca)
prova('regola già pronta: spenta senza prestazioni adatte, niente senza Galasso', c_regola_pronta_casi)
prova('quali regole valgono per un appuntamento', c_regole_per)
prova('prenotazione: email in coda una volta, di nuovo solo per un altro paziente', c_prenotazione_in_coda)
prova('prenotazione senza invio configurato o senza email del paziente: avviso, niente coda',
      c_prenotazione_senza)
prova('due esami lo stesso giorno: una email sola', c_stesso_giorno)
prova('appuntamento passato: niente email; serie: una email', c_passato_e_serie)
prova('da confermare messi in agenda: anche loro mandano l\'email', c_da_confermare)
prova('appuntamento eliminato: l\'email in coda si annulla', c_elimina_appuntamento)
prova('pagina della regola: salvataggio, PDF, controlli', c_pagina_regola)
prova('allegati: scaricare, togliere; regola eliminata annulla la coda', c_togli_elimina_scarica)
prova('anagrafiche: medico e prestazione usati da una regola non si eliminano', c_anagrafiche_protette)
prova('per medico: la sua email, con il suo PDF, al posto di quella per tutti', c_email_per_medico)
prova('cambiato il medico con l\'email ancora in coda: parte quella del medico nuovo', c_cambio_medico)
prova('due esami lo stesso giorno, il primo eliminato o disdetto: l\'email passa al secondo',
      c_primo_dei_due_eliminato)
prova('appuntamenti passati a un sostituto: parte l\'email del sostituto', c_sostituto)
prova('duplica per un altro medico: copia spenta, allegati suoi', c_duplica)
prova('pagine: email raggruppate per medico, nuova per un medico, sovrapposizioni', c_pagine_per_medico)
prova('scheda del medico con le sue email; nell\'appuntamento perché le altre non partono',
      c_scheda_medico_e_appuntamento)



# ================================================ spedire le email (finto Gmail)
area('invio delle email')


def d_invio_riuscito():
    S, C = mondo()
    I = ids(S)
    regola_galasso(S)
    prenota(C, I)
    esiti_ = invii.elabora(fabbrica)
    assert [e[1] for e in esiti_] == ['INVIATO'], esiti_
    assert len(POSTA.messaggi) == 1
    arrivato = POSTA.messaggi[0]
    assert arrivato['tls'] and arrivato['utente'] == UTENTE, 'senza TLS o senza accesso'
    assert arrivato['da'] == UTENTE and arrivato['a'] == ['mara.fintini@example.com'], arrivato
    m = messaggio()
    assert m['Subject'] == invii.PRONTA_OGGETTO
    assert m['To'] == 'mara.fintini@example.com' and UTENTE in m['From'] and 'Clinica Posillipo' in m['From'], m['From']
    assert m['Reply-To'] == 'segreteria@example.com', m['Reply-To']
    semplice, pagina, allegati, immagini = parti(m)
    assert semplice.startswith('Gentile Paziente,') and 'quattro ore prima' in semplice
    for riga in ('Societa di Prova S.r.l.', 'Via di Prova 1, Napoli', 'Tel: 081 0000000', 'Mail: segreteria@example.com'):
        assert riga in semplice and riga in pagina, riga
    assert '⚠️ ATTENZIONE:' in semplice and "all&#x27;esame" in pagina and '<p' in pagina
    assert [a[0] for a in allegati] == ['INFORMATIVA_EGDS.pdf', 'INFORMATIVA_COLONSCOPIA.pdf'], allegati
    for nome, dati in allegati:
        assert dati == open(os.path.join(CARTELLA, 'modelli_email', nome), 'rb').read(), nome
    assert immagini == [], 'logo senza che la struttura lo abbia'
    x = invii_tutti(S)[0]
    assert x['stato'] == 'INVIATO' and x['tentativi'] == 1 and x['oggetto'] == invii.PRONTA_OGGETTO
    assert x['testo'].startswith('Gentile Paziente') and '[allegati: INFORMATIVA_EGDS.pdf, INFORMATIVA_COLONSCOPIA.pdf]' in x['testo']
    assert invii.elabora(fabbrica) == [] and len(POSTA.messaggi) == 1, 'partita due volte'
    return '%d KB' % (len(arrivato['dati']) // 1024)


def d_logo():
    S, C = mondo()
    I = ids(S)
    import marchio
    logo = marchio.normalizza_logo(open(os.path.join(CARTELLA, 'static', 'icona.png'), 'rb').read())
    s = S()
    st = s.get(Struttura, 1)
    st.logo, st.logo_aggiornato = logo, datetime.now()
    s.commit()
    s.close()
    regola_galasso(S, allegati=False)
    prenota(C, I)
    invii.elabora(fabbrica)
    semplice, pagina, allegati, immagini = parti(messaggio())
    assert len(immagini) == 1 and allegati == []
    cid = immagini[0]['Content-ID'].strip('<>')
    assert 'cid:%s' % cid in pagina and immagini[0].get_payload(decode=True) == logo


def d_errori_permanenti():
    S, C = mondo()
    I = ids(S)
    regola_galasso(S, allegati=False)
    POSTA.ripristina(password='un-altra-password')
    prenota(C, I)
    esito = invii.elabora(fabbrica)[0]
    # 1.9.1: il messaggio dipende dal fornitore; qui il server e' 127.0.0.1, uno qualsiasi
    assert esito[1] == 'ERRORE' and 'non ha accettato nome utente e password' in esito[2], esito
    x = invii_tutti(S)[0]
    assert x['tentativi'] == 1 and invii.elabora(fabbrica, adesso=datetime.now() + timedelta(days=1)) == []
    POSTA.ripristina(rifiuta_rcpt=True)
    prenota(C, I, quando=ORA9 + timedelta(days=7))
    esito = invii.elabora(fabbrica)[0]
    assert esito[1] == 'ERRORE' and 'destinatario rifiutato' in esito[2], esito
    POSTA.ripristina(errore_data='552 5.3.4 messaggio troppo grande')
    prenota(C, I, quando=ORA9 + timedelta(days=14))
    esito = invii.elabora(fabbrica)[0]
    assert esito[1] == 'ERRORE' and 'troppo grande' in esito[2], esito
    POSTA.ripristina(starttls=False)
    prenota(C, I, quando=ORA9 + timedelta(days=21))
    esito = invii.elabora(fabbrica)[0]
    assert esito[1] == 'ERRORE' and 'sicurezza' in esito[2], esito
    imposta(S, email_password='dpapi:QUJDRA==')         # cifrata su un altro PC
    prenota(C, I, quando=ORA9 + timedelta(days=28))
    esito = invii.elabora(fabbrica)[0]
    assert esito[1] == 'ERRORE' and 'va riscritta' in esito[2], esito
    assert POSTA.messaggi == []


def d_errori_temporanei():
    S, C = mondo()
    I = ids(S)
    regola_galasso(S, allegati=False)
    POSTA.ripristina(errore_data='451 4.3.0 riprovare piu tardi')
    prenota(C, I)
    prima = datetime.now()
    esito = invii.elabora(fabbrica)[0]
    assert esito[1] == 'DA_INVIARE' and 'riprovare' in esito[2], esito
    x = invii_tutti(S)[0]
    assert x['tentativi'] == 1 and timedelta(minutes=1.9) < x['prossimo'] - prima < timedelta(minutes=2.5), x['prossimo']
    assert invii.elabora(fabbrica) == [], 'riprovato subito'
    POSTA.ripristina()
    esito = invii.elabora(fabbrica, adesso=datetime.now() + timedelta(minutes=3))[0]
    assert esito[1] == 'INVIATO' and len(POSTA.messaggi) == 1, esito
    # server spento: cinque nuovi tentativi (2, 10, 30 minuti, 2 e 6 ore), poi ci si ferma
    imposta(S, email_porta=str(porta_chiusa()))
    prenota(C, I, quando=ORA9 + timedelta(days=7))
    attese, quando = [], datetime.now()
    for _ in range(10):
        e = invii.elabora(fabbrica, adesso=quando)
        if not e:
            break
        x = invii_tutti(S)[-1]
        if x['stato'] != 'DA_INVIARE':
            break
        attese.append(round((x['prossimo'] - datetime.now()).total_seconds() / 60))
        quando = x['prossimo'] + timedelta(seconds=1)
    x = invii_tutti(S)[-1]
    assert attese == invii.ATTESE, attese
    assert x['stato'] == 'ERRORE' and x['tentativi'] == len(invii.ATTESE) + 1 and 'non raggiungibile' in x['errore'], x


def d_certificati():
    S, C = mondo()
    I = ids(S)
    regola_galasso(S, allegati=False)
    invii.contesto_tls = ssl.create_default_context            # i certificati veri di sistema
    try:
        prenota(C, I)
        esito = invii.elabora(fabbrica)[0]
    finally:
        invii.contesto_tls = lambda: CONTESTO_CLIENT
    assert esito[1] == 'DA_INVIARE' and 'connessione protetta' in esito[2], esito
    assert POSTA.messaggi == [], 'mandata senza controllare il certificato'
    # SSL diretto, porta 465
    imposta(S, email_porta=str(POSTA_SSL.porta), email_sicurezza='ssl')
    esito = invii.elabora(fabbrica, adesso=datetime.now() + timedelta(minutes=3))[0]
    assert esito[1] == 'INVIATO' and len(POSTA_SSL.messaggi) == 1 and POSTA_SSL.messaggi[0]['tls'], esito


def d_controlli_prima_di_spedire():
    S, C = mondo()
    I = ids(S)
    regola_galasso(S, allegati=False)
    prenota(C, I)
    aid = ultimo(S)
    C.post('/appuntamento/%d/stato' % aid, data={'stato': 'DISDETTO'})
    esito = invii.elabora(fabbrica)[0]
    assert esito[1:] == ('ANNULLATO', 'appuntamento disdetto'), esito
    # passato: quella automatica non parte piu'; a comando si'
    prenota(C, I, quando=ORA9 + timedelta(days=7))
    esito = invii.elabora(fabbrica, adesso=ORA9 + timedelta(days=8))[0]
    assert esito[1:] == ('ANNULLATO', 'appuntamento già passato'), esito
    s = S()
    pid = s.scalars(select(Paziente)).first().id
    s.close()
    vecchio = nuovo_app(S, I['Sala endoscopia'], I['Galasso'], datetime.combine(OGGI - timedelta(days=2), time(9, 0)),
                        paziente_id=pid, prestazione_id=I['EGDS'])
    rid = ultimo(S, RegolaEmail)
    pagina = testo(C.get('/appuntamento/%d' % vecchio))
    assert "Manda l'email" in pagina and 'Manda il promemoria adesso' not in pagina, 'promemoria per un appuntamento passato'
    pagina = testo(C.get('/appuntamento/%d' % aid))
    assert "Manda l'email" not in pagina and 'Manda il promemoria' not in pagina, 'pulsanti per un appuntamento disdetto'
    r = C.post('/invii/appuntamento/%d' % vecchio, data={'azione': 'regola', 'regola': str(rid)})
    assert r.status_code == 302 and 'Mandato a mara.fintini@example.com' in avvisi(C)
    assert len(POSTA.messaggi) == 1 and invii.elabora(fabbrica) == []


def d_testo_compilato_all_invio():
    S, C = mondo()
    I = ids(S)
    regola_galasso(S, oggetto='Appuntamento del {data} alle {ora}', allegati=False,
                   testo='Gentile {paziente},\nci vediamo {giorno} alle {ora}.\n\nIndirizzo: {indirizzo_paziente}')
    prenota(C, I, cognome='FINTINI', nome='MARA', indirizzo_paziente='Via di Prova 3')
    aid = ultimo(S)
    s = S()
    a = s.get(Appuntamento, aid)
    a.inizio, a.fine = ORA9 + timedelta(hours=2), ORA9 + timedelta(hours=2, minutes=30)
    s.commit()
    s.close()
    invii.elabora(fabbrica)
    m = messaggio()
    assert m['Subject'] == 'Appuntamento del %s alle 11:00' % MAR.strftime('%d/%m/%Y'), m['Subject']
    semplice = m.get_body(('plain',)).get_content().replace('\r\n', '\n')
    from comune import giorno_breve
    atteso = 'Gentile Mara Fintini,\nci vediamo %s alle 11:00.\n\nIndirizzo: Via di Prova 3\n\n--\n' % giorno_breve(MAR)
    assert semplice.startswith(atteso), (semplice[:120], atteso)


def d_a_mano_e_prove():
    S, C = mondo()
    I = ids(S)
    rid = regola_galasso(S)
    prenota(C, I)
    avvisi(C)
    aid = ultimo(S)
    invii.elabora(fabbrica)
    for _ in range(2):                         # a comando si puo' rimandare
        r = C.post('/invii/appuntamento/%d' % aid, data={'azione': 'regola', 'regola': str(rid)})
        assert r.status_code == 302 and r.headers['Location'].endswith('/appuntamento/%d#messaggi' % aid)
        assert 'Mandato a mara.fintini@example.com.' in avvisi(C)
    assert len(POSTA.messaggi) == 3
    x = invii_tutti(S)
    assert [y['a_mano'] for y in x] == [False, True, True] and all(y['stato'] == 'INVIATO' for y in x)
    pagina = testo(C.get('/appuntamento/%d' % aid))
    assert 'Email e WhatsApp al paziente' in pagina and pagina.count('(a mano)') == 2 and 'inviato' in pagina
    # server spento: a comando non si riprova da solo, si dice subito
    imposta(S, email_porta=str(porta_chiusa()))
    C.post('/invii/appuntamento/%d' % aid, data={'azione': 'regola', 'regola': str(rid)})
    assert 'Non partito: server email non raggiungibile' in avvisi(C)
    assert invii_tutti(S)[-1]['stato'] == 'ERRORE'
    imposta(S, email_porta=str(POSTA.porta))
    # la prova dalle impostazioni e la prova della regola (dati finti, allegati veri)
    C.post('/invii', data={'azione': 'prova_email', 'a': 'io@example.com'})
    assert 'Prova mandata' in avvisi(C) and messaggio()['Subject'] == 'Prova del gestionale'
    C.post('/invii', data={'azione': 'prova_email', 'a': 'non-un-indirizzo'})
    assert 'indirizzo email valido' in avvisi(C)
    regola_galasso(S, testo='Gentile {paziente}, prova del {giorno}.', allegati=True)
    rid2 = ultimo(S, RegolaEmail)
    C.post('/invii/regole/%d' % rid2, data={'azione': 'prova', 'a': 'io@example.com'})
    assert 'Prova mandata, con gli allegati' in avvisi(C)
    m = messaggio()
    semplice, pagina_, allegati, _ = parti(m)
    assert m['Subject'] == '[PROVA] ' + invii.PRONTA_OGGETTO and len(allegati) == 2
    assert semplice.startswith('Gentile Paziente Prova, prova del'), semplice[:60]
    assert 'Fintini' not in semplice, 'nella prova un paziente vero'


def d_ripresa_e_concorrenza():
    S, C = mondo()
    I = ids(S)
    s = S()
    adesso = datetime.now()
    for minuti in (1, 60):
        s.add(Invio(canale='EMAIL', motivo='PROVA', destinatario='io@example.com', stato='IN_CORSO',
                    prossimo=adesso - timedelta(minutes=minuti), oggetto='o', testo='t'))
    s.add(Invio(canale='EMAIL', motivo='PROVA', destinatario='io@example.com', stato='DA_INVIARE',
                prossimo=adesso + timedelta(hours=1), oggetto='o', testo='t'))
    s.commit()
    s.close()
    assert invii.riprendi_interrotti(fabbrica, adesso - timedelta(minutes=invii.MINUTI_BLOCCATO)) == 1
    assert [x['stato'] for x in invii_tutti(S)] == ['IN_CORSO', 'DA_INVIARE', 'DA_INVIARE']
    assert invii.riprendi_interrotti(fabbrica) == 1                  # all'avvio: tutti
    # manda_subito tocca solo i messaggi "in partenza"
    esito = invii.manda_subito(fabbrica, invii_tutti(S)[2]['id'])
    assert esito[1] == 'DA_INVIARE' and POSTA.messaggi == [], esito
    esiti_ = invii.elabora(fabbrica)
    assert [e[1] for e in esiti_] == ['INVIATO', 'INVIATO'] and len(POSTA.messaggi) == 2, esiti_


def d_niente_attese_durante_invio():
    """Mentre il server di posta risponde piano, le prenotazioni non
    aspettano: il lucchetto e il database restano liberi."""
    S, C = mondo()
    I = ids(S)
    regola_galasso(S, allegati=False)
    prenota(C, I)
    POSTA.ripristina(ritardo=2.0)
    risultato = []
    filo = threading.Thread(target=lambda: risultato.extend(invii.elabora(fabbrica)))
    filo.start()
    orologio.sleep(0.5)
    inizio = orologio.monotonic()
    r = prenota(C, I, prestazione='Visita gastroenterologica', quando=ORA9 + timedelta(hours=3), cognome='Esempietti',
                nome='Ugo', telefono='333 000 0004', email_paziente='')
    durata_prenotazione = orologio.monotonic() - inizio
    c = sqlite3.connect(S.motore.url.database, timeout=0.5)
    inizio = orologio.monotonic()
    c.execute('BEGIN IMMEDIATE')
    c.execute("UPDATE impostazioni SET valore = valore WHERE chiave = 'versione_schema'")
    c.commit()
    c.close()
    durata_scrittura = orologio.monotonic() - inizio
    ancora_in_corso = filo.is_alive()
    filo.join(10)
    assert r.status_code == 302 and durata_prenotazione < 1.0, durata_prenotazione
    assert durata_scrittura < 0.3 and ancora_in_corso, (durata_scrittura, ancora_in_corso)
    assert [e[1] for e in risultato] == ['INVIATO'], risultato
    return 'prenotazione in %.2f s durante un invio di 2 s' % durata_prenotazione


def d_registro_e_notifiche():
    S, C = mondo()
    I = ids(S)
    regola_galasso(S, allegati=False)
    POSTA.ripristina(password='sbagliata')
    prenota(C, I)
    invii.elabora(fabbrica)
    x = invii_tutti(S)[0]
    assert x['stato'] == 'ERRORE'
    s = S()
    with A.app.test_request_context('/'):
        n = invii.notifiche(s)
    s.close()
    assert len(n) == 1 and n[0]['titolo'] == 'Messaggi non partiti' and 'non ha accettato' in n[0]['testo'], n
    dati = json.loads(C.get('/notifiche.json').get_data(as_text=True))
    assert any(y['titolo'] == 'Messaggi non partiti' for y in dati), dati
    pagina = testo(C.get('/invii'))
    assert 'non partito' in pagina and 'non ha accettato nome utente e password' in pagina and 'Riprova' in pagina
    POSTA.ripristina()
    C.post('/invii', data={'azione': 'riprova', 'invio': str(x['id'])})
    y = invii_tutti(S)[0]
    assert (y['stato'], y['tentativi'], y['errore']) == ('DA_INVIARE', 0, ''), y
    assert invii.elabora(fabbrica)[0][1] == 'INVIATO'
    s = S()
    with A.app.test_request_context('/'):
        assert invii.notifiche(s) == []
    s.close()
    # annullare un messaggio in coda
    prenota(C, I, quando=ORA9 + timedelta(days=7))
    z = invii_tutti(S)[-1]
    C.post('/invii', data={'azione': 'annulla', 'invio': str(z['id'])})
    assert invii_tutti(S)[-1]['stato'] == 'ANNULLATO' and invii.elabora(fabbrica) == []
    # le prove non partite non fanno notifica
    imposta(S, email_porta=str(porta_chiusa()))
    C.post('/invii', data={'azione': 'prova_email', 'a': 'io@example.com'})
    s = S()
    with A.app.test_request_context('/'):
        assert invii.notifiche(s) == []
    s.close()


prova('email partita: STARTTLS, accesso, firma, risposte alla struttura, le due informative', d_invio_riuscito)
prova('logo della struttura nella firma, come immagine in linea', d_logo)
prova('errori da correggere: password, destinatario, messaggio, sicurezza, password di un altro PC',
      d_errori_permanenti)
prova('errori di rete: si riprova dopo 2, 10, 30 minuti, 2 e 6 ore, poi ci si ferma', d_errori_temporanei)
prova('certificato controllato davvero; SSL sulla porta 465', d_certificati)
prova('prima di spedire: disdetto o passato annulla, a comando parte lo stesso', d_controlli_prima_di_spedire)
prova('testo compilato all\'invio: ora spostata, nome scritto per bene, indirizzo', d_testo_compilato_all_invio)
prova('a comando dalla pagina dell\'appuntamento; prove dalle impostazioni e della regola', d_a_mano_e_prove)
prova('messaggi rimasti a metà rimessi in coda; il pulsante non manda quelli in coda', d_ripresa_e_concorrenza)
prova('durante un invio lento prenotazioni e database non aspettano', d_niente_attese_durante_invio)
prova('registro: riprova, annulla; notifica dei messaggi non partiti', d_registro_e_notifiche)



# =================================================== WhatsApp (finta Meta)
area('WhatsApp automatico')


def con_paziente(S, I, quando=ORA9, stato='PRENOTATO', prestazione='EGDS', stanza='Sala endoscopia', medico='Galasso',
                 **campi):
    dati = dict(cognome='Fintini', nome='Mara', telefono='333 000 0001')
    dati.update(campi)
    pid = nuovo_paziente(S, **dati)
    return nuovo_app(S, I[stanza], I[medico], quando, stato=stato, paziente_id=pid, prestazione_id=I[prestazione])


def promemoria_in_coda(S, aid, a_mano=False):
    s = S()
    a = s.get(Appuntamento, aid)
    x = invii.accoda_promemoria(s, a, invii.impostazioni(s), a_mano=a_mano)
    s.commit()
    xid = x.id if x is not None else None
    s.close()
    return xid


def e_whatsapp_riuscito():
    from comune import giorno_breve
    S, C = mondo(email_ok=False, whatsapp=True)
    I = ids(S)
    aid = con_paziente(S, I, cognome='FINTINI', nome='MARA')
    assert promemoria_in_coda(S, aid) is not None
    esito = invii.elabora(fabbrica)
    assert [e[1] for e in esito] == ['INVIATO'], esito
    assert len(META.richieste) == 1
    q = META.richieste[0]
    assert q['percorso'] == '/%s/123456789/messages' % invii.PREDEFINITI['wa_versione'] and q['auth'] == 'Bearer ' + TOKEN, q
    c = q['corpo']
    assert (c['messaging_product'], c['to'], c['type']) == ('whatsapp', '393330000001', 'template'), c
    assert c['template']['name'] == 'promemoria_appuntamento' and c['template']['language'] == {'code': 'it'}
    valori = [p['text'] for p in c['template']['components'][0]['parameters']]
    assert valori == ['Mara Fintini', giorno_breve(MAR), '09:00', 'Clinica Posillipo', 'chiami il 081 0000000'], valori
    x = invii_tutti(S)[0]
    assert (x['canale'], x['motivo'], x['destinatario']) == ('WHATSAPP', 'PROMEMORIA', '393330000001')
    assert 'wamid.PROVA1' in x['oggetto'] and x['testo'].startswith('Mara Fintini | '), x
    assert promemoria_in_coda(S, aid) is None, 'promemoria messo in coda due volte'


def e_whatsapp_errori():
    S, C = mondo(email_ok=False, whatsapp=True)
    I = ids(S)
    casi = [((400, {'error': {'message': 'Template name does not exist in the translation', 'code': 132001}}),
             'ERRORE', 'Template name does not exist'),
            ((429, {'error': {'message': 'Rate limit hit', 'code': 130429}}), 'DA_INVIARE', 'Rate limit'),
            ((503, 'servizio non disponibile'), 'DA_INVIARE', 'WhatsApp ha rifiutato'),
            ((200, {}), 'DA_INVIARE', 'risposta di WhatsApp non prevista')]
    for k, (risposta, stato, parola) in enumerate(casi):
        META.ripristina(*risposta)
        aid = con_paziente(S, I, quando=ORA9 + timedelta(days=7 * k), telefono='333 000 00%02d' % (10 + k))
        promemoria_in_coda(S, aid)
        esito = invii.elabora(fabbrica)[0]
        assert esito[1] == stato and parola in esito[2], (risposta, esito)
    assert '132001' in invii_tutti(S)[0]['errore']
    imposta(S, wa_indirizzo='http://127.0.0.1:%d' % porta_chiusa())
    aid = con_paziente(S, I, quando=ORA9 + timedelta(days=35), telefono='333 000 0020')
    promemoria_in_coda(S, aid)
    esito = invii.elabora(fabbrica)[0]
    assert esito[1] == 'DA_INVIARE' and 'non raggiungibile' in esito[2], esito
    imposta(S, wa_indirizzo='http://127.0.0.1:%d' % META.server_address[1], wa_token='dpapi:QUJD')
    aid = con_paziente(S, I, quando=ORA9 + timedelta(days=42), telefono='333 000 0021')
    promemoria_in_coda(S, aid)
    esito = invii.elabora(fabbrica)[0]
    assert esito[1] == 'ERRORE' and 'va riscritta' in esito[2], esito


def e_numeri():
    def p(t1, t2=''):
        return Paziente(cognome='Fintini', telefono=t1, telefono2=t2)
    casi = [(p('333 000 0001'), '393330000001'), (p('081 1234567', '333 000 0002'), '393330000002'),
            (p('+39 333 000 0003'), '393330000003'), (p('0039 333 000 0004'), '393330000004'),
            (p('+44 7700 900123'), '447700900123'), (p('081 1234567'), None), (p(''), None)]
    for paziente, atteso in casi:
        assert pazienti.cellulare_whatsapp(paziente) == atteso, (paziente.telefono, paziente.telefono2)
        link = pazienti.collegamenti_paziente(paziente).get('whatsapp')
        assert (link == 'https://wa.me/%s' % atteso) if atteso else link is None, link


def e_variabili():
    S, C = mondo(email_ok=False, whatsapp=True)
    I = ids(S)
    aid = con_paziente(S, I)
    s = S()
    st = s.get(Struttura, 1)
    st.telefono, st.indirizzo = '', 'Via di Prova\n1,\tNapoli'
    s.commit()
    a = s.get(Appuntamento, aid)
    cfg = dict(invii.impostazioni(s), wa_parametri='paziente,indirizzo,recapito,stanza,data')
    assert invii.parametri_whatsapp(cfg, a) == ['Mara Fintini', 'Via di Prova 1, Napoli', 'ci contatti',
                                                'Sala endoscopia', MAR.strftime('%d/%m/%Y')]
    st.indirizzo = ''
    s.commit()
    assert invii.parametri_whatsapp(dict(cfg, wa_parametri='indirizzo'), s.get(Appuntamento, aid)) == ['-']
    s.close()


def e_prova_dalle_impostazioni():
    S, C = mondo(email_ok=False, whatsapp=True)
    C.post('/invii', data={'azione': 'prova_whatsapp', 'a': '333 000 0003'})
    assert 'Prova mandata' in avvisi(C)
    c = META.richieste[-1]['corpo']
    assert c['to'] == '393330000003'
    assert [p['text'] for p in c['template']['components'][0]['parameters']] == \
        ['Paziente di prova', 'lunedì 1 marzo', '09:00', 'Clinica Posillipo', 'ci contatti']
    C.post('/invii', data={'azione': 'prova_whatsapp', 'a': '12'})
    assert 'numero di cellulare valido' in avvisi(C)
    S, C = mondo(email_ok=False)
    C.post('/invii', data={'azione': 'prova_whatsapp', 'a': '333 000 0003'})
    assert 'Prima salvare token' in avvisi(C) and META.richieste == []


prova('promemoria su WhatsApp: indirizzo di Meta, token, modello, variabili, id del messaggio', e_whatsapp_riuscito)
prova('errori di Meta: modello sbagliato si ferma, occupata o irraggiungibile si riprova', e_whatsapp_errori)
prova('numero per WhatsApp: il primo cellulare fra i due telefoni, anche estero', e_numeri)
prova('variabili del modello pulite: niente a capo, mai vuote', e_variabili)
prova('prova di WhatsApp dalle impostazioni', e_prova_dalle_impostazioni)


# ============================================== promemoria del giorno prima
area('promemoria del giorno prima')


def f_canale():
    cfg = dict(invii.PREDEFINITI, email_utente=UTENTE, email_password='chiaro:eA==', wa_token='chiaro:eA==',
               wa_numero_id='1', email_server='smtp.example.com')    # dalla 1.9.1 nessun server di partenza
    assert invii.email_pronta(cfg) and invii.whatsapp_pronto(cfg)

    def p(telefono='333 000 0001', email_='mara@example.com', canale='WHATSAPP', promemoria=True):
        return Paziente(cognome='Fintini', telefono=telefono, email=email_, canale=canale, promemoria=promemoria)
    casi = [(cfg, p(), ('WHATSAPP', '393330000001')),
            (cfg, p(canale='EMAIL'), ('EMAIL', 'mara@example.com')),
            (cfg, p(canale='EMAIL', email_='non-valida'), ('WHATSAPP', '393330000001')),
            (cfg, p(canale='SMS'), ('WHATSAPP', '393330000001')),
            (dict(cfg, wa_token=''), p(), ('EMAIL', 'mara@example.com')),
            (dict(cfg, promemoria_whatsapp='0'), p(), ('EMAIL', 'mara@example.com')),
            (dict(cfg, wa_token='', promemoria_email='0'), p(), (None, '')),
            (dict(cfg, email_attiva='0'), p(telefono='081 1234567'), (None, '')),
            (cfg, p(promemoria=False), (None, '')),
            (cfg, p(telefono='081 1234567', email_=''), (None, '')),
            (cfg, None, (None, ''))]
    for c, paziente, atteso in casi:
        assert invii.canale_promemoria(c, paziente) == atteso, (paziente and (paziente.telefono, paziente.canale), atteso)


def f_giorni_del_giro():
    S, C = mondo()
    s = S()
    st = s.get(Struttura, 1)
    sab, dom, lun = VEN + timedelta(days=1), VEN + timedelta(days=2), VEN + timedelta(days=3)
    assert invii.giorni_del_giro(s, st, VEN) == [sab]                      # aperta il sabato
    assert invii.giorni_del_giro(s, st, sab) == [dom, lun]
    st.giorni_apertura = '1111100'
    s.commit()
    assert invii.giorni_del_giro(s, st, VEN) == [sab, dom, lun]          # sabato chiuso
    s.add(Chiusura(struttura_id=1, dal=lun, al=lun, motivo='ponte'))
    s.commit()
    assert invii.giorni_del_giro(s, st, VEN) == [sab, dom, lun, lun + timedelta(days=1)]
    # festivo: la struttura che chiude nei festivi lo salta (8 dicembre 2027 e' un mercoledi')
    st.giorni_apertura = '1111110'
    st.chiusa_festivi = False
    s.commit()
    assert invii.giorni_del_giro(s, st, date(2027, 12, 7)) == [date(2027, 12, 8)]
    st.chiusa_festivi = True
    s.commit()
    assert invii.giorni_del_giro(s, st, date(2027, 12, 7)) == [date(2027, 12, 8), date(2027, 12, 9)]
    st.giorni_apertura = '0000000'
    s.commit()
    assert invii.giorni_del_giro(s, st, VEN) == []
    s.close()


def scenario_giro(S, I):
    """Mercoledi': chi riceve il promemoria e chi no."""
    q = lambda h, m=0: datetime.combine(MER, time(h, m))
    a = {
        'whatsapp': con_paziente(S, I, q(9), telefono='333 000 0001'),
        'email': con_paziente(S, I, q(9, 30), stato='CONFERMATO', cognome='Esempietti', nome='Ugo', telefono='081 1234567',
                              email='ugo.esempietti@example.com', canale='EMAIL'),
        'disdetto': con_paziente(S, I, q(10), stato='DISDETTO', cognome='Provolo', telefono='333 000 0005'),
        'non_vuole': con_paziente(S, I, q(10, 30), cognome='Testabianca', telefono='333 000 0006', promemoria=False),
        'fisso': con_paziente(S, I, q(11), cognome='Fittizi', telefono='081 7654321'),
        'senza_paziente': nuovo_app(S, I['Sala endoscopia'], I['Galasso'], q(11, 30)),
        'giovedi': con_paziente(S, I, q(9) + timedelta(days=1), cognome='Esempio', telefono='333 000 0007'),
    }
    return a


def f_giro():
    S, C = mondo(whatsapp=True)
    I = ids(S)
    a = scenario_giro(S, I)
    imposta(S, promemoria_attivo='1', promemoria_ora='10:00')
    s = S()
    assert invii.giro_promemoria(s, datetime.combine(MAR, time(9, 59))) == 0, 'prima dell\'ora'
    assert invii.giro_promemoria(s, datetime.combine(MAR, time(10, 30))) == 2
    s.commit()
    assert leggi_impostazione(s, 'promemoria_ultimo_giro') == MAR.isoformat()
    assert invii.giro_promemoria(s, datetime.combine(MAR, time(16, 0))) == 0, 'due giri nello stesso giorno'
    s.close()
    righe = invii_tutti(S)
    assert [(x['appuntamento_id'], x['canale'], x['destinatario']) for x in righe] == [
        (a['whatsapp'], 'WHATSAPP', '393330000001'), (a['email'], 'EMAIL', 'ugo.esempietti@example.com')], righe
    assert all(x['motivo'] == 'PROMEMORIA' and not x['a_mano'] for x in righe)
    # il giorno dopo: giovedi', e quelli di mercoledi' non ripartono
    s = S()
    assert invii.giro_promemoria(s, datetime.combine(MER, time(10, 1))) == 1
    s.commit()
    s.close()
    assert invii_tutti(S)[-1]['appuntamento_id'] == a['giovedi']
    s = S()
    assert invii.accoda_promemoria(s, s.get(Appuntamento, a['whatsapp']), invii.impostazioni(s)) is None
    s.close()
    # spenti: niente
    S2, C2 = mondo(whatsapp=True)
    scenario_giro(S2, ids(S2))
    s = S2()
    assert invii.giro_promemoria(s, datetime.combine(MAR, time(10, 30))) == 0
    s.close()


def f_spostato_e_testo():
    S, C = mondo(whatsapp=True)
    I = ids(S)
    a = scenario_giro(S, I)
    imposta(S, promemoria_attivo='1', testo_promemoria='Promemoria per {paziente}: {giorno} ore {ora} con {medico}.',
            oggetto_promemoria='Appuntamento delle {ora}')
    s = S()
    invii.giro_promemoria(s, datetime.combine(MAR, time(10, 30)))
    s.commit()
    x = s.get(Appuntamento, a['whatsapp'])
    x.inizio, x.fine = x.inizio + timedelta(days=1, hours=3), x.fine + timedelta(days=1, hours=3)   # a giovedi'
    y = s.get(Appuntamento, a['email'])
    y.inizio, y.fine = y.inizio + timedelta(hours=4), y.fine + timedelta(hours=4)     # stesso giorno, altra ora
    s.commit()
    s.close()
    esito = dict((e[0], e[1:]) for e in invii.elabora(fabbrica, adesso=datetime.combine(MAR, time(10, 31))))
    righe = {x['appuntamento_id']: x for x in invii_tutti(S)}
    assert esito[righe[a['whatsapp']]['id']] == ('ANNULLATO', 'appuntamento spostato a un altro giorno'), esito
    assert esito[righe[a['email']]['id']][0] == 'INVIATO' and META.richieste == []
    from comune import giorno_breve
    m = messaggio()
    assert m['Subject'] == 'Appuntamento delle 13:30', m['Subject']
    assert m.get_body(('plain',)).get_content().startswith(
        'Promemoria per Ugo Esempietti: %s ore 13:30 con Galasso.' % giorno_breve(MER)), m.get_body(('plain',)).get_content()


def f_conferme():
    S, C = mondo(whatsapp=True)
    I = ids(S)
    a = scenario_giro(S, I)
    imposta(S, promemoria_attivo='1')
    s = S()
    invii.giro_promemoria(s, datetime.combine(MAR, time(10, 30)))
    s.commit()
    s.close()
    invii.elabora(fabbrica, adesso=datetime.combine(MAR, time(10, 31)))
    r = C.get('/conferme?data=%s&struttura=1' % MER.isoformat())
    pagina = testo(r)
    assert 'WhatsApp: inviato' in pagina and 'Email: inviato' in pagina, pagina[:400]
    assert 'partono ogni giorno alle 10:00' in pagina
    assert pagina.count('da chiamare') == 2, 'il fisso e chi non vuole promemoria restano da chiamare'
    # un promemoria fallito si rimanda dalla pagina, e si torna li'
    s = S()
    pid = s.get(Appuntamento, a['fisso']).paziente_id
    s.get(Paziente, pid).telefono2 = '333 000 0008'
    s.commit()
    s.close()
    pagina = html(C.get('/conferme?data=%s&struttura=1' % MER.isoformat()))
    assert pagina.count('value="promemoria"') == 1, 'un solo pulsante Manda: per chi ora ha un cellulare'
    torna = '/conferme?data=%s&struttura=1' % MER.isoformat()
    r = C.post('/invii/appuntamento/%d' % a['fisso'], data={'azione': 'promemoria', 'torna': torna})
    assert r.status_code == 302 and r.headers['Location'].endswith(torna), r.headers['Location']
    assert 'Mandato a +393330000008' in avvisi(C) and META.richieste[-1]['corpo']['to'] == '393330000008'
    r = C.post('/invii/appuntamento/%d' % a['non_vuole'], data={'azione': 'promemoria', 'torna': torna})
    assert 'Promemoria non mandato' in avvisi(C)
    r = C.post('/invii/appuntamento/%d' % a['senza_paziente'], data={'azione': 'promemoria'})
    assert r.status_code == 400


def f_un_giro():
    S, C = mondo(whatsapp=True)
    I = ids(S)
    scenario_giro(S, I)
    imposta(S, promemoria_attivo='1')
    esiti_ = invii.un_giro(fabbrica, datetime.combine(MAR, time(10, 30)))
    assert sorted(e[1] for e in esiti_) == ['INVIATO', 'INVIATO'], esiti_
    assert len(META.richieste) == 1 and len(POSTA.messaggi) == 1
    assert invii.un_giro(fabbrica, datetime.combine(MAR, time(10, 45))) == []


prova('canale del promemoria: WhatsApp, email, preferenze del paziente, interruttori', f_canale)
prova('giorni del giro: fino al prossimo giorno di lavoro, chiusure e festivi', f_giorni_del_giro)
prova('giro dei promemoria: dall\'ora scelta, una volta al giorno, solo chi deve', f_giro)
prova('promemoria: spostato ad altro giorno si annulla, ora cambiata parte giusta, testo di Impostazioni',
      f_spostato_e_testo)
prova('pagina Conferme: cosa è partito, chi è da chiamare, Manda', f_conferme)
prova('un giro del thread: promemoria e coda insieme', f_un_giro)



# ======================================================= pagina delle impostazioni
area('pagina Email e WhatsApp')


def g_pagina_iniziale():
    S, C = mondo(email_ok=False)
    pagina = html(C.get('/invii'))
    assert 'value="segreteria@example.com"' in pagina, 'non propone l\'email della struttura'
    t_ = testo(C.get('/invii'))
    for parola in ('Email: da configurare', 'Promemoria: spenti', 'WhatsApp automatico: da configurare',
                   'myaccount.google.com/apppasswords', 'promemoria_appuntamento', 'Nessun messaggio ancora'):
        assert parola in t_, parola
    assert 'Email e WhatsApp' in testo(C.get('/mese/%s' % MAR.strftime('%Y-%m'))), 'manca la voce nel menu'
    assert 'Email e WhatsApp' in testo(C.get('/impostazioni'))


def g_salva_email():
    S, C = mondo(email_ok=False)
    base = {'azione': 'salva', 'sezione': 'email', 'email_utente': UTENTE, 'email_password': 'abcd efgh ijkl mnop',
            'email_mittente': 'Clinica Posillipo', 'email_attiva': '1', 'email_server': 'smtp.gmail.com',
            'email_porta': '587', 'email_sicurezza': 'starttls'}
    r = C.post('/invii', data=base)
    assert r.status_code == 302 and r.headers['Location'].endswith('/invii#email')
    s = S()
    salvata = leggi_impostazione(s, 'email_password')
    s.close()
    assert salvata.startswith('chiaro:') and 'abcdefghijklmnop' not in salvata, salvata
    assert invii.svela(salvata) == 'abcdefghijklmnop'
    pagina = html(C.get('/invii'))
    assert 'abcdefghijklmnop' not in pagina and salvata not in pagina and 'salvata: vuoto per lasciarla' in pagina
    assert 'Email: pronte' in testo(C.get('/invii'))
    C.post('/invii', data=dict(base, email_password=''))
    s = S()
    assert leggi_impostazione(s, 'email_password') == salvata, 'la password vuota l\'ha cancellata'
    s.close()
    for campo, valore, parola in (('email_utente', 'non-email', 'Indirizzo email non valido'),
                                  ('email_porta', '99999', 'Porta non valida'),
                                  ('email_server', 'smtp gmail', 'Server non valido'),
                                  ('email_sicurezza', 'boh', 'Sicurezza')):
        C.post('/invii', data=dict(base, **{campo: valore}))
        assert parola in avvisi(C), parola
    s = S()
    assert leggi_impostazione(s, 'email_utente') == UTENTE and leggi_impostazione(s, 'email_porta') == '587'
    s.close()
    C.post('/invii', data=dict(base, email_password='', togli_password='1'))
    s = S()
    assert leggi_impostazione(s, 'email_password') == ''
    s.close()
    assert 'Email: da configurare' in testo(C.get('/invii'))


def g_salva_whatsapp_e_promemoria():
    S, C = mondo(email_ok=False)
    base = {'azione': 'salva', 'sezione': 'whatsapp', 'wa_numero_id': '123456789', 'wa_token': TOKEN,
            'wa_modello': 'promemoria_appuntamento', 'wa_lingua': 'it', 'wa_parametri': 'paziente, giorno,ora',
            'wa_versione': 'v22.0'}
    C.post('/invii', data=base)
    s = S()
    assert invii.svela(leggi_impostazione(s, 'wa_token')) == TOKEN and leggi_impostazione(s, 'wa_parametri') == 'paziente,giorno,ora'
    s.close()
    assert TOKEN not in html(C.get('/invii'))
    for campo, valore, parola in (('wa_numero_id', 'abc', 'ID del numero'), ('wa_modello', 'Promemoria-1', 'Nome del modello'),
                                  ('wa_parametri', 'paziente,pippo', 'Variabili sconosciute: pippo'),
                                  ('wa_lingua', 'italiano', 'Lingua'), ('wa_versione', 'v22', 'Versione'),
                                  ('wa_token', 'token con <spazi>', 'Token non valido')):
        C.post('/invii', data=dict(base, **{campo: valore}))
        assert parola in avvisi(C), parola
    C.post('/invii', data={'azione': 'salva', 'sezione': 'promemoria', 'promemoria_ora': '25:00', 'promemoria_attivo': '1'})
    assert 'Ora del promemoria non valida' in avvisi(C)
    C.post('/invii', data={'azione': 'salva', 'sezione': 'promemoria', 'promemoria_ora': '09:15', 'promemoria_attivo': '1',
                           'promemoria_whatsapp': '1'})
    s = S()
    assert (leggi_impostazione(s, 'promemoria_attivo'), leggi_impostazione(s, 'promemoria_ora'),
            leggi_impostazione(s, 'promemoria_whatsapp'), leggi_impostazione(s, 'promemoria_email')) == ('1', '09:15', '1', '0')
    s.close()
    assert 'Promemoria: ogni giorno alle 09:15' in testo(C.get('/invii'))
    assert C.post('/invii', data={'azione': 'salva', 'sezione': 'altro'}).status_code == 302 and 'Sezione' in avvisi(C)
    assert C.post('/invii', data={'azione': 'boh'}).status_code == 400


def g_richieste_esterne():
    S, C = mondo()
    for indirizzo, dati in (('/invii', {'azione': 'prova_email', 'a': 'io@example.com'}),
                            ('/invii/appuntamento/1', {'azione': 'promemoria'}),
                            ('/invii/regole/nuova', {'nome': 'x'})):
        r = C.post(indirizzo, data=dati, headers={'Origin': 'http://sito-esterno.example'})
        assert r.status_code == 403, (indirizzo, r.status_code)
    assert POSTA.messaggi == []
    assert C.get('/invii/regole/999').status_code == 404 and C.post('/invii/appuntamento/999', data={}).status_code == 404


prova('pagina: email della struttura proposta, istruzioni, menu', g_pagina_iniziale)
prova('account email: password cifrata, mai nella pagina, controlli dei campi', g_salva_email)
prova('WhatsApp e promemoria: token cifrato, controlli dei campi', g_salva_whatsapp_e_promemoria)
prova('richieste da altri siti respinte', g_richieste_esterne)


# ============================================================ mese e stampe
area('sala operatoria nel mese, email nelle stampe')


def h_mese():
    S, C = mondo(email_ok=False)
    I = ids(S)
    sala_a = I['Sala A']
    for ora_, medico, stato in ((8, 'Borrelli', 'PRENOTATO'), (10, 'Borrelli', 'CONFERMATO'), (12, 'Lippi', 'PRENOTATO'),
                                (14, 'Lippi', 'DISDETTO')):
        nuovo_app(S, sala_a, I[medico], datetime.combine(MAR, time(ora_, 0)), stato=stato)
    s = S()
    s.add(Chiusura(struttura_id=1, dal=MER + timedelta(days=7), al=MER + timedelta(days=7), motivo='ponte'))
    s.commit()
    vista = servizi.mese(s, MAR.year, MAR.month, 1)
    d = vista['giorni'][MAR]['sala']
    assert d['interventi'] == 3 and [(o.cognome, n) for o, n in d['chirurghi']] == [('Borrelli', 2), ('Lippi', 1)], d
    assert d['liberi'] == []
    assert [o.cognome for o in vista['giorni'][MER]['sala']['liberi']] == ['Borrelli'], 'il mercoledi\' di sala libero'
    regole = servizi.Regole(s, MER, MER + timedelta(days=7))
    sale = servizi.sala_del_mese(s, s.get(Struttura, 1), MER, MER + timedelta(days=7), regole)
    assert sale[MER + timedelta(days=7)]['liberi'] == [], 'chiusa: nessuno è libero'
    passato = servizi.sala_del_mese(s, s.get(Struttura, 1), MER - timedelta(days=28), MER - timedelta(days=28), regole,
                                    oggi=MER)
    assert passato[MER - timedelta(days=28)]['liberi'] == [], 'i giorni passati non hanno posti liberi'
    # un chirurgo che "opera di domenica" con la struttura chiusa la domenica: niente sala libera
    s.get(Operatore, I['Lippi']).giorni_sala = '0000001'
    s.commit()
    dom = MAR + timedelta(days=5)
    sale = servizi.sala_del_mese(s, s.get(Struttura, 1), dom, dom, servizi.Regole(s, dom, dom))
    assert sale[dom]['liberi'] == [], 'sala libera in un giorno di chiusura'
    s.get(Struttura, 1).giorni_apertura = '1111111'
    s.commit()
    sale = servizi.sala_del_mese(s, s.get(Struttura, 1), dom, dom, servizi.Regole(s, dom, dom))
    assert [o.cognome for o in sale[dom]['liberi']] == ['Lippi']
    s.get(Operatore, I['Lippi']).giorni_sala = ''
    s.get(Struttura, 1).giorni_apertura = '1111110'
    s.commit()
    assert vista['ci_sono_sale'] and vista['interventi'] >= 3
    lippi = servizi.mese(s, MAR.year, MAR.month, 1, I['Lippi'])
    assert lippi['giorni'][MAR]['sala']['interventi'] == 1 and lippi['giorni'][MER]['sala']['liberi'] == []
    s.close()
    pagina = testo(C.get('/mese/%s?struttura=1' % MAR.strftime('%Y-%m')))
    assert 'Sala 3: Borrelli (2), Lippi' in pagina and 'sala libera: Borrelli' in pagina, pagina[:300]
    assert 'in sala operatoria' in pagina
    pagina = testo(C.get('/mese/%s?struttura=1&medico=%d' % (MAR.strftime('%Y-%m'), I['Lippi'])))
    assert 'Sala 1: Lippi' in pagina and 'sala libera' not in pagina


def h_senza_sale():
    S, C = mondo(email_ok=False)
    I = ids(S)
    s = S()
    s.delete(s.get(Risorsa, I['Sala A']))
    s.commit()
    vista = servizi.mese(s, MAR.year, MAR.month, 1)
    assert not vista['ci_sono_sale'] and all(g['sala'] is None for g in vista['giorni'].values())
    s.close()
    pagina = testo(C.get('/mese/%s?struttura=1' % MAR.strftime('%Y-%m')))
    assert 'sala operatoria' not in pagina and 'Sala ' not in pagina.replace('Sala endoscopia', '')


def h_stampe():
    S, C = mondo(email_ok=False)
    I = ids(S)
    aid = con_paziente(S, I)
    nuovo_app(S, I['Sala A'], I['Borrelli'], datetime.combine(MAR, time(8, 0)))
    s = S()
    m = ModuloStampa(nome='Consenso', testo='Il paziente {paziente} abita in {indirizzo_paziente}.')
    s.add(m)
    s.commit()
    mid = m.id
    s.close()
    for indirizzo in ('/stampa/%s?struttura=1' % MAR.isoformat(), '/lista-operatoria/%s?struttura=1' % MAR.isoformat(),
                      '/appuntamento/%d/modulo/%d' % (aid, mid)):
        pagina = testo(C.get(indirizzo))
        assert 'segreteria@example.com' in pagina, indirizzo
    assert 'Via di Prova 1, Napoli · tel. 081 0000000 · segreteria@example.com' in testo(C.get('/stampa/%s?struttura=1' % MAR.isoformat()))


prova('mese: interventi e chirurghi di ogni giorno, sala libera nei giorni dei chirurghi', h_mese)
prova('mese senza sale operatorie: niente righe di sala', h_senza_sale)
prova('email della struttura nel foglio del giorno, nella lista operatoria, nei moduli', h_stampe)


# ================================================================ il thread
area('thread della coda')


def i_thread():
    """Ultima prova: il thread resta acceso fino alla fine del programma."""
    S, C = mondo()
    I = ids(S)
    regola_galasso(S, allegati=False)
    filo = invii.avvia(fabbrica, intervallo=30)
    assert filo.is_alive() and invii.avvia(fabbrica) is filo, 'un thread solo'
    prenota(C, I)                       # la prenotazione sveglia il thread
    for _ in range(50):
        if POSTA.messaggi:
            break
        orologio.sleep(0.1)
    assert len(POSTA.messaggi) == 1 and invii_tutti(S)[0]['stato'] == 'INVIATO', invii_tutti(S)
    return 'partita in meno di 5 secondi'


prova('la prenotazione sveglia il thread e l\'email parte da sola', i_thread)


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
