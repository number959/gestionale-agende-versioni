# -*- coding: utf-8 -*-
"""Prove della 1.11: i difetti trovati dalla revisione del codice di novembre
2026, uno per uno. Ognuno era stato riprodotto da un controllo indipendente
prima di correggerlo; qui ogni prova lo rifa' e controlla la correzione (le
prove sono state verificate anche rimettendo il difetto: devono fallire).

- messaggi ai pazienti: il messaggio in attesa di riprovare che arrivava al
  paziente di prima, il promemoria di un altro giorno dato per inviato, il
  disdetto rimesso in agenda senza la sua email, la password con le lettere
  accentate, l'email di un appuntamento eliminato mandata di nuovo, la serie
  con piu' email, l'indirizzo accentato con la colpa data all'accesso.

L'autoriparazione ha le sue prove in prove_autoriparazione.py."""
import base64
import email as libemail
import logging
import os
import shutil
import socket
import socketserver
import sys
import tempfile
import threading
import traceback
from datetime import date, datetime, time, timedelta
from email import policy

CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = tempfile.mkdtemp(prefix='prove_111_')
os.environ['LOCALAPPDATA'] = os.path.join(PROVVISORIA, 'localappdata')
os.environ['NO_PROXY'] = os.environ['no_proxy'] = '127.0.0.1,localhost'
sys.path.insert(0, CARTELLA)
logging.getLogger().setLevel(logging.CRITICAL)

from sqlalchemy import select  # noqa: E402

import app as A  # noqa: E402
import invii  # noqa: E402
import servizi  # noqa: E402
from modelli import (crea_sessione, Struttura, Risorsa, Operatore, Prestazione, Appuntamento, Paziente,  # noqa: E402
                     RegolaEmail, Invio, scrivi_impostazione)

A.app.config['TESTING'] = True
esiti, _area, _n = [], [''], [0]
SOLO = [x for x in os.environ.get('PROVE_SOLO', '').split(',') if x]


def area(nome):
    _area[0] = nome


def prova(nome, f):
    if SOLO and not any(x in nome for x in SOLO):
        return
    try:
        esiti.append(('OK', _area[0], nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', _area[0], nome, str(e) or 'asserzione fallita'))
    except Exception:
        esiti.append(('ERRORE', _area[0], nome, traceback.format_exc().strip().splitlines()[-1]))


# ================================================================ il mondo
def mondo():
    """Un database nuovo con due medici, la sessione nel programma e la coda
    dei messaggi che usa quella sessione. (S, ids, client)."""
    _n[0] += 1
    S = crea_sessione('sqlite:///' + os.path.join(PROVVISORIA, 'db_%d.db' % _n[0]))
    s = S()
    servizi.prepara_primo_avvio(s)
    st = s.get(Struttura, 1)
    st.nome, st.telefono, st.indirizzo, st.giorni_apertura = 'Clinica Prova', '081 0000000', 'Via di Prova 1', '1111110'
    s.add_all([Operatore(cognome='Galasso', nome=''), Operatore(cognome='Lippiello', nome='Anna')])
    s.commit()
    I = {r.nome: r.id for r in s.scalars(select(Risorsa))}
    I.update({o.cognome: o.id for o in s.scalars(select(Operatore))})
    I.update({p.nome: p.id for p in s.scalars(select(Prestazione))})
    s.close()
    A.Sessione = S
    A._registro = None
    invii._fabbrica = lambda: S()
    return S, I, A.app.test_client()


def regola(S, I, nome='Preparazione', medico='Galasso', prestazioni=('Colonscopia',)):
    s = S()
    s.add(RegolaEmail(nome=nome, attiva=True, operatore_id=I[medico],
                      prestazioni=','.join(str(I[p]) for p in prestazioni), oggetto='Preparazione per {paziente}',
                      testo='Gentile {paziente}, la sua {prestazione} è il {giorno} alle {ora}.'))
    s.commit()
    s.close()


def configura(S, porta, password='segretissima', **altro):
    s = S()
    valori = dict(email_tipo='altro', email_server='127.0.0.1', email_porta=str(porta), email_sicurezza='nessuna',
                  email_utente='clinica.prova@example.com', email_password=invii.proteggi(password),
                  email_attiva='1', email_senza_password='0')
    valori.update(altro)
    for k, v in valori.items():
        scrivi_impostazione(s, k, v)
    s.commit()
    s.close()


def giorno(settimane=2, giorno_settimana=1):
    g = date.today() + timedelta(days=7 * settimane)
    g += timedelta(days=(giorno_settimana - g.weekday()) % 7)
    while any(servizi.calendario.festivo(g + timedelta(days=k)) for k in range(-3, 4)):
        g += timedelta(days=7)
    return g


def modulo(I, quando, medico='Galasso', prestazione='Colonscopia', stanza='Sala endoscopia', cognome='Fintini',
           nome='Mara', telefono='333 000 0001', email_paziente='mara.fintini@example.com', **altro):
    d = {'risorsa': I[stanza], 'operatore': I[medico], 'prestazione': I[prestazione], 'struttura': 1,
         'data': quando.date().isoformat(), 'ora': quando.strftime('%H:%M'), 'durata': '30',
         'paziente': cognome, 'nome_paziente': nome, 'telefono': telefono, 'email_paziente': email_paziente,
         'tipo': '', 'degenza': ''}
    d.update(altro)
    return d


def avvisi(c):
    with c.session_transaction() as sess:
        m = sess.get('_flashes', [])
        sess['_flashes'] = []
    return ' '.join(x[1] for x in m)


def ultimo(S, modello=Appuntamento):
    s = S()
    x = s.scalars(select(modello).order_by(modello.id.desc())).first()
    xid = x.id if x is not None else None
    s.close()
    return xid


def coda(S, **filtro):
    s = S()
    q = select(Invio).order_by(Invio.id)
    for k, v in filtro.items():
        q = q.where(getattr(Invio, k) == v)
    righe = [(x.id, x.motivo, x.stato, x.destinatario, x.errore) for x in s.scalars(q)]
    s.close()
    return righe


def porta_chiusa():
    x = socket.socket()
    x.bind(('127.0.0.1', 0))
    p = x.getsockname()[1]
    x.close()
    return p


# ================================================================ finto server di posta
class _Gestore(socketserver.StreamRequestHandler):
    def scrivi(self, riga):
        self.wfile.write((riga + '\r\n').encode('utf-8'))

    def handle(self):
        srv = self.server
        self.scrivi('220 finto ESMTP')
        dati = None
        while True:
            riga = self.rfile.readline()
            if not riga:
                return
            if dati is not None:
                if riga in (b'.\r\n', b'.\n'):
                    srv.messaggi.append(b''.join(dati))
                    dati = None
                    self.scrivi('250 ok')
                else:
                    dati.append(riga[1:] if riga.startswith(b'..') else riga)
                continue
            cmd = riga.decode('utf-8', 'replace').strip()
            u = cmd.upper()
            if u.startswith('EHLO'):
                righe = ['finto', 'AUTH ' + srv.metodi] + (['SMTPUTF8'] if srv.utf8 else []) + ['8BITMIME']
                for i, x in enumerate(righe):
                    self.scrivi(('250 ' if i == len(righe) - 1 else '250-') + x)
            elif u.startswith('AUTH PLAIN'):
                parti = cmd.split()
                srv.accessi.append(base64.b64decode(parti[2]) if len(parti) > 2 else b'')
                self.scrivi('235 ok')
            elif u.startswith('AUTH'):
                self.scrivi('504 metodo non previsto')
            elif u == 'DATA':
                dati = []
                self.scrivi('354 vai')
            elif u == 'QUIT':
                self.scrivi('221 ciao')
                return
            else:
                self.scrivi('250 ok')


class FintaPosta(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, utf8=False, metodi='PLAIN LOGIN'):
        super().__init__(('127.0.0.1', 0), _Gestore)
        self.utf8, self.metodi = utf8, metodi
        self.messaggi, self.accessi = [], []
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def porta(self):
        return self.server_address[1]

    def lette(self):
        """[(a chi, oggetto, prima riga)] dei messaggi arrivati."""
        uscita = []
        for g in self.messaggi:
            m = libemail.message_from_bytes(g, policy=policy.default)
            corpo = m.get_body(('plain',)).get_content().strip()
            uscita.append((str(m['To']), str(m['Subject']), corpo.splitlines()[0] if corpo else ''))
        return uscita


POSTA = FintaPosta()


def manda_tutto(adesso=None):
    """Due giri della coda (il secondo per quello che il primo rimette in coda)."""
    invii.elabora(invii._fabbrica, adesso=adesso)
    return invii.elabora(invii._fabbrica, adesso=adesso)


# ================================================================ messaggi ai pazienti
area('messaggi ai pazienti')
QUANDO = datetime.combine(giorno(), time(9, 0))


def m0_paziente_cambiato():
    """Il messaggio aspetta di riprovare (server spento); intanto sull'appuntamento
    si mette un altro paziente. Prima: all'indirizzo di Fintini arrivava la
    preparazione con il nome e la prestazione di Provolo."""
    S, I, c = mondo()
    regola(S, I)
    configura(S, porta_chiusa())
    d = modulo(I, QUANDO)
    assert c.post('/appuntamento', data=d).status_code == 302
    avvisi(c)
    aid = ultimo(S)
    invii.elabora(invii._fabbrica)                       # primo tentativo: server spento
    d2 = dict(d, paziente='Provolo', nome_paziente='Ugo', telefono='333 000 0002',
              email_paziente='ugo.provolo@example.com')
    assert c.post('/appuntamento/%d' % aid, data=d2).status_code == 302
    avvisi(c)
    POSTA.messaggi.clear()
    configura(S, POSTA.porta)                            # il server torna
    manda_tutto(datetime.now() + timedelta(minutes=5))
    arrivati = POSTA.lette()
    assert not [x for x in arrivati if x[0].startswith('mara')], 'a Fintini e\' arrivato: %s' % arrivati
    assert len([x for x in arrivati if x[0] == 'ugo.provolo@example.com' and 'Provolo' in x[1]]) == 1, arrivati
    assert any(e == invii.CAMBIATO_PAZIENTE for _, _, st, _, e in coda(S) if st == 'ANNULLATO'), coda(S)


def m0_indirizzo_corretto():
    """Indirizzo scritto male e corretto mentre il messaggio aspetta: prima
    partiva lo stesso all'indirizzo sbagliato, e a quello giusto niente."""
    S, I, c = mondo()
    regola(S, I)
    configura(S, porta_chiusa())
    d = modulo(I, QUANDO, email_paziente='mara.fintni@example.com')
    c.post('/appuntamento', data=d)
    avvisi(c)
    aid = ultimo(S)
    invii.elabora(invii._fabbrica)
    s = S()
    pid = s.get(Appuntamento, aid).paziente_id
    s.close()
    c.post('/appuntamento/%d' % aid, data=dict(d, email_paziente='mara.fintini@example.com', paziente_id=pid))
    avvisi(c)
    POSTA.messaggi.clear()
    configura(S, POSTA.porta)
    manda_tutto(datetime.now() + timedelta(minutes=5))
    destinatari = [x[0] for x in POSTA.lette()]
    assert destinatari == ['mara.fintini@example.com'], destinatari


def m0_promemoria():
    """Lo stesso per il promemoria: annullato per il paziente di prima, e
    rimesso in coda per quello nuovo (il giro del giorno non lo rifarebbe)."""
    S, I, c = mondo()
    configura(S, porta_chiusa(), promemoria_email='1')
    d = modulo(I, QUANDO, medico='Lippiello', prestazione='Prima visita', stanza='Ambulatorio 1')
    c.post('/appuntamento', data=d)
    avvisi(c)
    aid = ultimo(S)
    s = S()
    with invii._lucchetto:
        x = invii.accoda_promemoria(s, s.get(Appuntamento, aid), invii.impostazioni(s))
        s.commit()
    assert x is not None, 'promemoria non preparato (configurazione della prova)'
    s.close()
    invii.elabora(invii._fabbrica)
    c.post('/appuntamento/%d' % aid, data=dict(d, paziente='Provolo', nome_paziente='Ugo', telefono='333 000 0002',
                                               email_paziente='ugo.provolo@example.com'))
    avvisi(c)
    POSTA.messaggi.clear()
    configura(S, POSTA.porta, promemoria_email='1')
    manda_tutto(datetime.now() + timedelta(minutes=5))
    destinatari = [x[0] for x in POSTA.lette()]
    assert destinatari == ['ugo.provolo@example.com'], destinatari


def m1_promemoria_altro_giorno():
    """Promemoria mandato per martedi', appuntamento spostato a giovedi': la
    pagina Conferme di giovedi' diceva «inviato» e non lasciava mandarlo."""
    S, I, c = mondo()
    configura(S, POSTA.porta)
    mar = giorno(giorno_settimana=1)
    d = modulo(I, datetime.combine(mar, time(10, 0)), medico='Lippiello', prestazione='Prima visita',
               stanza='Ambulatorio 1')
    c.post('/appuntamento', data=d)
    avvisi(c)
    aid = ultimo(S)
    s = S()
    with invii._lucchetto:
        x = invii.accoda(s, 'EMAIL', 'PROMEMORIA', 'mara.fintini@example.com', s.get(Appuntamento, aid), a_mano=True)
        x.stato, x.inviato_il = 'INVIATO', datetime.now()
        s.commit()
    s.close()
    s = S()
    pid = s.get(Appuntamento, aid).paziente_id
    s.close()
    gio = mar + timedelta(days=2)
    c.post('/appuntamento/%d' % aid, data=dict(d, data=gio.isoformat(), paziente_id=pid))
    avvisi(c)
    s = S()
    a = s.get(Appuntamento, aid)
    assert a.inizio.date() == gio, 'appuntamento non spostato (prova)'
    assert aid not in invii.stato_promemoria(s, [a]), 'il promemoria di martedi\' vale per giovedi\''
    s.close()
    t = c.get('/conferme?data=%s&struttura=1' % gio.isoformat()).get_data(as_text=True)
    assert 'value="promemoria"' in t, 'manca il pulsante per mandare il promemoria'


def m2_disdetto_rimesso():
    """Disdetto (l'email in attesa si annulla), poi rimesso in agenda con un
    clic: prima l'email non ripartiva piu'."""
    S, I, c = mondo()
    regola(S, I)
    configura(S, porta_chiusa())
    c.post('/appuntamento', data=modulo(I, QUANDO))
    avvisi(c)
    aid = ultimo(S)
    invii.elabora(invii._fabbrica)
    c.post('/appuntamento/%d/stato' % aid, data={'stato': 'DISDETTO', 'torna': '/'})
    avvisi(c)
    invii.elabora(invii._fabbrica, adesso=datetime.now() + timedelta(minutes=5))
    assert [x for x in coda(S) if x[2] == 'ANNULLATO'], 'l\'email del disdetto non si e\' annullata (prova)'
    c.post('/appuntamento/%d/stato' % aid, data={'stato': 'PRENOTATO', 'torna': '/'})
    detto = avvisi(c)
    assert 'in partenza' in detto, detto
    POSTA.messaggi.clear()
    configura(S, POSTA.porta)
    manda_tutto(datetime.now() + timedelta(minutes=10))
    assert [x[0] for x in POSTA.lette()] == ['mara.fintini@example.com'], POSTA.lette()


def m2_gia_partita():
    """Se l'email era gia' partita prima del disdetto, rimettendolo in agenda
    non ne parte un'altra."""
    S, I, c = mondo()
    regola(S, I)
    configura(S, POSTA.porta)
    c.post('/appuntamento', data=modulo(I, QUANDO))
    avvisi(c)
    aid = ultimo(S)
    manda_tutto()
    for stato in ('DISDETTO', 'PRENOTATO'):
        c.post('/appuntamento/%d/stato' % aid, data={'stato': stato, 'torna': '/'})
        avvisi(c)
    assert len([x for x in coda(S) if x[2] in invii.VIVI]) == 1, coda(S)


def m3_password_accentata():
    """Una password con lettere accentate o € fermava ogni email con «errore
    inatteso: ascii codec». Ora l'accesso va in UTF-8 (AUTH PLAIN)."""
    S, I, c = mondo()
    regola(S, I)
    configura(S, POSTA.porta, password='Clinicà2026€')
    POSTA.messaggi.clear()
    del POSTA.accessi[:]
    c.post('/appuntamento', data=modulo(I, QUANDO))
    avvisi(c)
    manda_tutto()
    assert [x[0] for x in POSTA.lette()] == ['mara.fintini@example.com'], (POSTA.lette(), coda(S))
    assert POSTA.accessi and POSTA.accessi[-1].decode('utf-8') == '\0clinica.prova@example.com\0Clinicà2026€'


def m3_server_senza_plain():
    """Un server che non offre AUTH PLAIN: l'errore dice cosa correggere."""
    S, I, c = mondo()
    altra = FintaPosta(metodi='LOGIN')
    try:
        configura(S, altra.porta, password='Clinicà2026€')
        s = S()
        cfg = invii.impostazioni(s)
        s.close()
        messaggio = invii.EmailMessage()
        messaggio['From'], messaggio['To'], messaggio['Subject'] = 'clinica.prova@example.com', 'a@example.com', 'x'
        messaggio.set_content('prova')
        try:
            invii.manda_email(cfg, messaggio)
        except invii.ErroreInvio as e:
            assert e.permanente and 'lettere accentate' in str(e) and 'Configura' in str(e), str(e)
        else:
            raise AssertionError('nessun errore')
    finally:
        altra.shutdown()
        altra.server_close()


def m4_eliminato():
    """Gastroscopia e colonscopia lo stesso giorno: l'email parte per la prima;
    eliminata la prima e modificata la seconda, prima ne partiva un'altra."""
    S, I, c = mondo()
    regola(S, I, prestazioni=('EGDS', 'Colonscopia'))
    configura(S, POSTA.porta)
    POSTA.messaggi.clear()
    c.post('/appuntamento', data=modulo(I, QUANDO, prestazione='EGDS'))
    avvisi(c)
    egds = ultimo(S)
    manda_tutto()
    s = S()
    pid = s.get(Appuntamento, egds).paziente_id
    s.close()
    d2 = modulo(I, QUANDO + timedelta(minutes=30), paziente_id=pid)
    c.post('/appuntamento', data=d2)
    avvisi(c)
    colon = ultimo(S)
    c.post('/appuntamento/%d' % egds, data={'azione': 'elimina'})
    avvisi(c)
    c.post('/appuntamento/%d' % colon, data=dict(d2, note='porta gli esami'))
    avvisi(c)
    manda_tutto()
    assert len(POSTA.messaggi) == 1, 'email arrivate al paziente: %d' % len(POSTA.messaggi)


def m5_serie():
    """Una serie riceve l'email una volta sola: prima, modificando il terzo
    appuntamento della serie, ne partiva un'altra."""
    S, I, c = mondo()
    regola(S, I, nome='Benvenuto', medico='Lippiello', prestazioni=())
    configura(S, POSTA.porta)
    POSTA.messaggi.clear()
    d = modulo(I, datetime.combine(giorno(), time(11, 0)), medico='Lippiello', prestazione='Controllo',
               stanza='Ambulatorio 1')
    r = c.post('/appuntamento', data=dict(d, ripeti='1', ripeti_ogni='1', ripeti_unita='settimane', ripeti_volte='4'))
    assert r.status_code == 302
    avvisi(c)
    manda_tutto()
    s = S()
    apps = s.scalars(select(Appuntamento).order_by(Appuntamento.inizio)).all()
    serie = [(a.id, a.inizio, a.paziente_id) for a in apps]
    s.close()
    assert len(serie) == 4 and len(POSTA.messaggi) == 1, (len(serie), len(POSTA.messaggi))
    terzo = serie[2]
    c.post('/appuntamento/%d' % terzo[0], data=dict(d, data=terzo[1].date().isoformat(), paziente_id=terzo[2],
                                                     note='porta il referto'))
    detto = avvisi(c)
    manda_tutto()
    assert len(POSTA.messaggi) == 1, 'email per la serie: %d' % len(POSTA.messaggi)
    assert 'serie' in detto, detto


def m6_indirizzo_accentato():
    """Un indirizzo del paziente con una lettera accentata e un server senza
    SMTPUTF8: prima la colpa andava alle impostazioni dell'accesso."""
    S, I, c = mondo()
    regola(S, I)
    configura(S, POSTA.porta)
    c.post('/appuntamento', data=modulo(I, QUANDO, email_paziente='marà.fintini@example.com'))
    avvisi(c)
    manda_tutto()
    errori = [e for _, _, st, _, e in coda(S) if st == 'ERRORE']
    assert errori and 'lettere accentate' in errori[0] and 'scheda del paziente' in errori[0], coda(S)
    assert 'Il server non chiede la password' not in errori[0], errori[0]


for nome, f in [('paziente cambiato mentre il messaggio aspetta', m0_paziente_cambiato),
                ('indirizzo corretto mentre il messaggio aspetta', m0_indirizzo_corretto),
                ('promemoria: paziente cambiato mentre aspetta', m0_promemoria),
                ('promemoria di un altro giorno non vale', m1_promemoria_altro_giorno),
                ('disdetto rimesso in agenda: l\'email riparte', m2_disdetto_rimesso),
                ('disdetto rimesso in agenda: niente doppioni', m2_gia_partita),
                ('password con lettere accentate', m3_password_accentata),
                ('server senza AUTH PLAIN: errore spiegato', m3_server_senza_plain),
                ('email di un appuntamento eliminato non ripartita', m4_eliminato),
                ('una serie, un\'email', m5_serie),
                ('indirizzo accentato: errore spiegato', m6_indirizzo_accentato)]:
    prova(nome, f)


# =====================================================================
if __name__ == '__main__':
    POSTA.shutdown()
    aree = []
    for e in esiti:
        if e[1] not in aree:
            aree.append(e[1])
    for a in aree:
        mie = [e for e in esiti if e[1] == a]
        rotte = [e for e in mie if e[0] != 'OK']
        print('%-40s %2d prove  %s' % (a, len(mie), 'tutte a posto' if not rotte else '%d DA SISTEMARE' % len(rotte)))
    rotte = [e for e in esiti if e[0] != 'OK']
    if rotte or os.environ.get('DETTAGLIO'):
        print('\nDettaglio:')
        for e in esiti:
            if e[0] != 'OK' or os.environ.get('DETTAGLIO'):
                print('  %-6s [%s] %s\n         %s' % (e[0], e[1], e[2], e[3]))
    print('\n%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(rotte), len(rotte)))
    shutil.rmtree(PROVVISORIA, ignore_errors=True)
    sys.exit(1 if rotte else 0)
