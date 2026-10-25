# -*- coding: utf-8 -*-
"""Prove dell'email sul programma INSTALLATO (l'eseguibile vero, per esempio nel
Windows finto di strumenti/wine), che risponde su http://127.0.0.1:5000, con
finti server di posta su 127.0.0.1: senza sicurezza, con SSL diretto, con
STARTTLS, con e senza accesso. CAMBIA le impostazioni email del programma e
manda messaggi di prova: solo su un programma di prova, mai su quello vero.

    python strumenti/prova_email_installato.py --certificato DIR [--database FILE]

Controlla: il modulo salvato con i suoi avvisi, la password cifrata con la
protezione di Windows (con --database, il file agende.db del programma), la prova che arriva
con il nome utente e il mittente giusti, la password sbagliata, il server senza
password, SSL sulla porta che non lo usa, un certificato che il PC non conosce.

Gli invii protetti RIUSCITI (SSL e STARTTLS) vogliono che il programma si fidi
del certificato dei finti server: il certificato si scrive in DIR (la prima
volta lo crea openssl, poi si riusa) e il programma va avviato con la variabile
SSL_CERT_FILE che punta a DIR/certificato.pem visto da Windows (nel Windows
finto: Z: seguito dal percorso, con le barre rovesciate). Se il programma non se
ne fida, quelle due prove lo dicono e le altre valgono lo stesso."""
import argparse
import base64
import email
import http.cookiejar
import json
import os
import re
import socketserver
import sqlite3
import ssl
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
from email import policy
from html import unescape

os.environ['NO_PROXY'] = os.environ['no_proxy'] = '127.0.0.1,localhost'
B = os.environ.get('INDIRIZZO', 'http://127.0.0.1:5000')
esiti = []


def controlla(nome, ok, dettaglio=''):
    esiti.append((bool(ok), nome, dettaglio))
    print(('OK ' if ok else 'KO ') + nome + ('' if ok else '   ' + str(dettaglio)[:300]), flush=True)


# ---------------------------------------------------------- finti server
def certificato(cartella, nome, san):
    os.makedirs(cartella, exist_ok=True)
    cert, chiave = os.path.join(cartella, nome + '.pem'), os.path.join(cartella, nome + '-chiave.pem')
    if not (os.path.exists(cert) and os.path.exists(chiave)):
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '30', '-subj', '/CN=127.0.0.1',
                        '-addext', 'subjectAltName=' + san, '-keyout', chiave, '-out', cert], check=True, capture_output=True)
    contesto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contesto.load_cert_chain(cert, chiave)
    return contesto


class Gestore(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            self._parla()
        except (OSError, ssl.SSLError, ValueError):
            pass

    def _parla(self):
        srv, sock = self.server, self.request
        if srv.ssl_diretto:
            sock = srv.contesto.wrap_socket(sock, server_side=True)
        r, uscita = sock.makefile('rb'), [sock]

        def manda(riga):
            uscita[0].sendall((riga + '\r\n').encode('utf-8'))
        tls, utente, mittente, destinatari = srv.ssl_diretto, None, None, []
        manda('220 finto.example ESMTP pronto')
        while True:
            grezza = r.readline()
            if not grezza:
                return
            comando = grezza.decode('utf-8', 'replace').rstrip('\r\n')
            verbo = comando.split(' ', 1)[0].upper()
            if verbo in ('EHLO', 'HELO'):
                righe = ['finto.example'] + (['STARTTLS'] if srv.starttls and not tls else []) + \
                        (['AUTH PLAIN LOGIN'] if srv.accesso else []) + ['8BITMIME']
                for i, x in enumerate(righe):
                    manda(('250 ' if i == len(righe) - 1 else '250-') + x)
            elif verbo == 'STARTTLS' and srv.starttls and not tls:
                manda('220 2.0.0 via con il TLS')
                sock = srv.contesto.wrap_socket(sock, server_side=True)
                r, uscita[0], tls = sock.makefile('rb'), sock, True
            elif verbo == 'AUTH':
                parti = comando.split()
                if len(parti) > 1 and parti[1].upper() == 'PLAIN':
                    dati = parti[2] if len(parti) > 2 else (manda('334 ') or r.readline().decode().strip())
                    _, u, p = base64.b64decode(dati).decode('utf-8').split('\0')
                elif len(parti) > 1 and parti[1].upper() == 'LOGIN':
                    manda('334 VXNlcm5hbWU6')
                    u = base64.b64decode(r.readline().strip()).decode('utf-8')
                    manda('334 UGFzc3dvcmQ6')
                    p = base64.b64decode(r.readline().strip()).decode('utf-8')
                else:
                    manda('504 5.5.4 metodo sconosciuto')
                    continue
                if (u, p) == (srv.utente, srv.password):
                    utente = u
                    manda('235 2.7.0 Accepted')
                else:
                    manda('535 5.7.8 Username and Password not accepted')
            elif verbo == 'MAIL':
                if srv.accesso and utente is None:
                    manda('530 5.7.0 Authentication Required')
                    continue
                mittente, destinatari = re.search(r'<([^>]*)>', comando).group(1), []
                manda('250 2.1.0 OK')
            elif verbo == 'RCPT':
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
                srv.messaggi.append({'da': mittente, 'a': destinatari, 'dati': b''.join(righe), 'tls': tls,
                                     'utente': utente})
                manda('250 2.0.0 OK accettato')
            elif verbo == 'QUIT':
                manda('221 2.0.0 ciao')
                return
            else:
                manda('250 2.0.0 OK')


class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, contesto=None, ssl_diretto=False, starttls=False, accesso=True):
        super().__init__(('127.0.0.1', 0), Gestore)
        self.contesto, self.ssl_diretto, self.starttls, self.accesso = contesto, ssl_diretto, starttls, accesso
        self.utente, self.password, self.messaggi = 'segreteria@example.com', 'Una password lunga', []
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def porta(self):
        return self.server_address[1]


# ---------------------------------------------------------- il programma
cookie = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def chiedi(percorso, dati=None):
    corpo = urllib.parse.urlencode(dati).encode('utf-8') if dati is not None else None
    with cookie.open(urllib.request.Request(B + percorso, data=corpo), timeout=120) as r:
        return r.read().decode('utf-8', 'replace')


def testo(h):
    return ' '.join(unescape(re.sub(r'<[^>]+>', ' ', h)).split())


def avvisi(h):
    return ' '.join(testo(x) for x in re.findall(r'<div class="avviso[^"]*">(.*?)</div>', h, re.S))


def salva(**campi):
    dati = {'azione': 'salva', 'sezione': 'email', 'email_attiva': '1', 'email_mittente': 'Clinica di prova',
            'email_utente': 'segreteria@example.com', 'email_server': '127.0.0.1'}
    dati.update(campi)
    return avvisi(chiedi('/invii', dati))


def prova(srv):
    srv.messaggi = []
    return avvisi(chiedi('/invii', {'azione': 'prova_email', 'a': 'ada.fittizi@example.com'}))


def main():
    a = argparse.ArgumentParser(description='Prove dell\'email sul programma installato.')
    a.add_argument('--certificato', required=True, help='cartella del certificato dei finti server')
    a.add_argument('--database', help='il database del programma (agende.db nella cartella dei dati)')
    arg = a.parse_args()
    fidato = certificato(arg.certificato, 'certificato', 'IP:127.0.0.1,DNS:localhost')
    sconosciuto = certificato(arg.certificato, 'sconosciuto', 'IP:127.0.0.1,DNS:localhost')
    chiaro, relay = Server(), Server(accesso=False)
    ssl_465, starttls = Server(fidato, ssl_diretto=True), Server(fidato, starttls=True)
    ignoto = Server(sconosciuto, starttls=True)

    stato = json.loads(chiedi('/aggiornamenti/stato.json'))
    print('Programma installato: versione %s' % stato.get('versione'))
    pagina = testo(chiedi('/invii'))
    controlla('pagina Email: il tipo di casella c\'è', 'Tipo di casella' in pagina and 'Server e accesso' in pagina)

    # senza sicurezza, con la password: avviso, password cifrata, prova arrivata
    a_ = salva(email_tipo='altro', email_porta=str(chiaro.porta), email_sicurezza='nessuna',
               email_password='Una password lunga')
    controlla('salvato, con l\'avviso della password in chiaro', 'Impostazioni salvate' in a_ and 'in chiaro' in a_, a_)
    if arg.database:
        with sqlite3.connect(arg.database) as db:
            riga = db.execute("select valore from impostazioni where chiave = 'email_password'").fetchone()
        controlla('password cifrata con la protezione di Windows (dpapi)', riga and riga[0].startswith('dpapi:'),
                  (riga[0][:12] if riga else None))
    a_ = prova(chiaro)
    m = chiaro.messaggi
    x = email.message_from_bytes(m[0]['dati'], policy=policy.default) if m else None
    controlla('prova arrivata, con l\'accesso giusto', 'Prova mandata' in a_ and len(m) == 1 and
              m[0]['utente'] == 'segreteria@example.com', (a_, m[:1]))
    controlla('mittente: il nome scelto e l\'indirizzo della casella',
              x is not None and x['From'] == 'Clinica di prova <segreteria@example.com>', x and x['From'])

    # password sbagliata
    salva(email_tipo='altro', email_porta=str(chiaro.porta), email_sicurezza='nessuna', email_password='sbagliata')
    a_ = prova(chiaro)
    controlla('password sbagliata: il messaggio dice cosa controllare',
              'Non partito' in a_ and 'non ha accettato nome utente e password' in a_ and 'risposta del server: 535' in a_, a_)

    # nome utente diverso dall'indirizzo
    chiaro.utente = '8a1b2c@smtp.example.net'
    salva(email_tipo='altro', email_porta=str(chiaro.porta), email_sicurezza='nessuna', email_password='Una password lunga',
          email_accesso='8a1b2c@smtp.example.net')
    a_ = prova(chiaro)
    controlla('nome utente diverso: si entra con quello', 'Prova mandata' in a_ and len(chiaro.messaggi) == 1 and
              chiaro.messaggi[0]['utente'] == '8a1b2c@smtp.example.net' and chiaro.messaggi[0]['da'] == 'segreteria@example.com',
              (a_, chiaro.messaggi[:1]))
    chiaro.utente = 'segreteria@example.com'

    # server della rete interna senza password
    a_ = salva(email_tipo='altro', email_porta=str(relay.porta), email_sicurezza='nessuna', email_senza_password='1',
               togli_password='1', email_accesso='')
    a_ = prova(relay)
    controlla('server senza password: arrivata, senza accesso', 'Prova mandata' in a_ and len(relay.messaggi) == 1 and
              relay.messaggi[0]['utente'] is None, (a_, relay.messaggi[:1]))

    # SSL su una porta che non lo usa
    salva(email_tipo='dominio', email_porta=str(chiaro.porta), email_sicurezza='ssl', email_password='Una password lunga')
    a_ = prova(chiaro)
    controlla('SSL sulla porta senza SSL: «scegliere STARTTLS»', 'non usa SSL' in a_ and 'STARTTLS' in a_, a_)

    # certificato che il PC non conosce
    salva(email_tipo='altro', email_porta=str(ignoto.porta), email_sicurezza='starttls')
    a_ = prova(ignoto)
    controlla('certificato sconosciuto: connessione protetta non riuscita, si riprova',
              'connessione protetta non riuscita' in a_ and 'certificato' in a_ and ignoto.messaggi == [], a_)

    # invii protetti riusciti (il programma deve fidarsi di DIR/certificato.pem)
    salva(email_tipo='dominio', email_porta=str(ssl_465.porta), email_sicurezza='ssl')
    a_ = prova(ssl_465)
    controlla('SSL diretto (come la porta 465): arrivata', 'Prova mandata' in a_ and len(ssl_465.messaggi) == 1 and
              ssl_465.messaggi[0]['tls'], a_ or 'il programma si fida del certificato? (SSL_CERT_FILE)')
    salva(email_tipo='altro', email_porta=str(starttls.porta), email_sicurezza='starttls')
    a_ = prova(starttls)
    controlla('STARTTLS (come la porta 587): arrivata', 'Prova mandata' in a_ and len(starttls.messaggi) == 1 and
              starttls.messaggi[0]['tls'], a_)

    rotte = [e for e in esiti if not e[0]]
    print('\n%d controlli, %d a posto' % (len(esiti), len(esiti) - len(rotte)))
    return 1 if rotte else 0


if __name__ == '__main__':
    sys.exit(main())
