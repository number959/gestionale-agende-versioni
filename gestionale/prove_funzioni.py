# -*- coding: utf-8 -*-
"""Prove della versione 1.3: pazienti, stati, assenze e chiusure, festivita',
turni di un giorno, settimana e mese, prima disponibilita', statistiche,
stampa, backup, orari per struttura, aggiornamento dello schema.

Dove si puo', il risultato del programma si confronta con un oracolo scritto
qui in modo diverso (query dirette, cicli minuto per minuto), non con il
programma stesso.
"""
import io
import json
import os
import random
import re
import shutil
import sqlite3
from decimal import Decimal
import threading
import traceback
from datetime import datetime, date, time, timedelta
from urllib.parse import unquote

from sqlalchemy import select, func, create_engine, text
from sqlalchemy.exc import IntegrityError

import servizi
import calendario
import pazienti as PZ
import backup
import viste
import modelli
import app as A
from modelli import (Base, crea_sessione, Struttura, Risorsa, Operatore, Turno, Appuntamento,
                     Prestazione, Paziente, Assenza, Chiusura, Modifica, Impostazione,
                     STATI_ATTIVI, VERSIONE_SCHEMA)

A.app.config['TESTING'] = True
CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = os.path.join(CARTELLA, 'prove_funzioni_tmp')
shutil.rmtree(PROVVISORIA, ignore_errors=True)
os.makedirs(PROVVISORIA)
esiti = []
_area = ['']
_n = [0]
MAR = date(2027, 3, 2)          # martedi, nessuna festivita', nel futuro
GIO = MAR + timedelta(days=2)


def area(nome):
    _area[0] = nome


def prova(nome, f):
    try:
        esiti.append(('OK', _area[0], nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', _area[0], nome, str(e) or 'asserzione fallita'))
    except Exception:
        esiti.append(('ERRORE', _area[0], nome, traceback.format_exc().strip().splitlines()[-1]))


def percorso_nuovo(nome='db'):
    _n[0] += 1
    return os.path.join(PROVVISORIA, '%s_%d.db' % (nome, _n[0]))


def collega(S):
    A.Sessione = S
    A._registro = None
    return A.app.test_client()


def mondo(medici=True):
    """Database nuovo come al primo avvio, piu' tre medici con turni."""
    S = crea_sessione('sqlite:///' + percorso_nuovo())
    s = S()
    servizi.prepara_primo_avvio(s)
    if medici:
        lip = Operatore(cognome='Lippiello', colore='#154381')
        gal = Operatore(cognome='Galasso', colore='#5B7F3E')
        amo = Operatore(cognome='Amato', colore='#A8582B')
        s.add_all([lip, gal, amo])
        s.flush()
        stanze = {r.nome: r for r in s.scalars(select(Risorsa))}
        for g in (1, 3):          # martedi e giovedi
            s.add(Turno(operatore=lip, risorsa=stanze['Ambulatorio 1'], giorno_settimana=g,
                        ora_inizio=time(8, 0), ora_fine=time(14, 0), valido_da=date(2026, 1, 1)))
        s.add(Turno(operatore=gal, risorsa=stanze['Sala endoscopia'], giorno_settimana=1,
                    ora_inizio=time(8, 0), ora_fine=time(13, 0), valido_da=date(2026, 1, 1)))
        s.add(Turno(operatore=amo, risorsa=stanze['Ambulatorio 3'], giorno_settimana=1,
                    ora_inizio=time(15, 0), ora_fine=time(19, 0), valido_da=date(2026, 1, 1)))
        s.commit()
    s.close()
    return S, collega(S)


def ids(S):
    s = S()
    d = {r.nome: r.id for r in s.scalars(select(Risorsa))}
    d.update({o.cognome: o.id for o in s.scalars(select(Operatore))})
    d.update({p.nome: p.id for p in s.scalars(select(Prestazione))})
    s.close()
    return d


def nuovo_app(S, stanza, medico, g, h, m, minuti=30, stato='PRENOTATO', paziente=None, prest=None):
    s = S()
    i = datetime.combine(g, time(h, m))
    a = Appuntamento(risorsa_id=stanza, operatore_id=medico, inizio=i, fine=i + timedelta(minutes=minuti),
                     stato=stato, paziente_id=paziente, prestazione_id=prest)
    s.add(a)
    s.commit()
    aid = a.id
    s.close()
    return aid


def html(r):
    return r.get_data(as_text=True)


def avvisi(C, r=None):
    """I messaggi per l'utente: quelli ancora in coda nella sessione (dopo un
    rinvio) piu', se si passa la risposta, quelli gia' scritti nella pagina."""
    from html import unescape
    with C.session_transaction() as sess:
        m = sess.get('_flashes', [])
        sess['_flashes'] = []
    testo = ' '.join(x[1] for x in m)
    if r is not None and r.status_code == 200:
        testo += ' ' + ' '.join(unescape(x) for x in re.findall(r'class="avviso[^"]*">([^<]*)</div>', html(r)))
    return testo


def prenota(C, d, stanza, medico, prest, g, ora, **altro):
    dati = {'struttura': '1', 'risorsa': str(stanza), 'operatore': str(medico), 'prestazione': str(prest),
            'data': g.isoformat(), 'ora': ora, 'durata': altro.pop('durata', ''), 'note': ''}
    dati.update({k: str(v) for k, v in altro.items()})
    return C.post('/appuntamento', data=dati)


def leggi_app(S, aid):
    s = S()
    a = s.get(Appuntamento, aid)
    d = None if a is None else dict(stato=a.stato, arrivato=a.arrivato_alle, paziente=a.paziente_id,
                                    tipo=a.tipo, convenzione=a.convenzione, importo=a.importo_cent,
                                    extra=a.valori_extra, inizio=a.inizio, fine=a.fine, risorsa=a.risorsa_id)
    s.close()
    return d


# =====================================================================
area('aggiornamento dello schema')

SCHEMA_APP_V12 = """CREATE TABLE appuntamenti (
    id INTEGER NOT NULL, risorsa_id INTEGER NOT NULL, operatore_id INTEGER NOT NULL,
    paziente_id INTEGER, prestazione_id INTEGER, inizio DATETIME NOT NULL, fine DATETIME NOT NULL,
    stato VARCHAR(20) NOT NULL, note TEXT, creato_il DATETIME, modificato_il DATETIME,
    PRIMARY KEY (id), CONSTRAINT una_stanza_un_orario UNIQUE (risorsa_id, inizio),
    FOREIGN KEY(risorsa_id) REFERENCES risorse (id), FOREIGN KEY(operatore_id) REFERENCES operatori (id),
    FOREIGN KEY(paziente_id) REFERENCES pazienti (id), FOREIGN KEY(prestazione_id) REFERENCES prestazioni (id))"""
SCHEMA_V12 = [
    """CREATE TABLE strutture (id INTEGER NOT NULL, nome VARCHAR(80) NOT NULL, attiva BOOLEAN NOT NULL,
       societa VARCHAR(120) DEFAULT '', colore VARCHAR(7) DEFAULT '#154381', logo BLOB,
       logo_aggiornato DATETIME, PRIMARY KEY (id), UNIQUE (nome))""",
    """CREATE TABLE risorse (id INTEGER NOT NULL, nome VARCHAR(60) NOT NULL, tipo VARCHAR(30) NOT NULL,
       struttura_id INTEGER NOT NULL, ordine INTEGER NOT NULL, attiva BOOLEAN NOT NULL, PRIMARY KEY (id),
       UNIQUE (struttura_id, nome), FOREIGN KEY(struttura_id) REFERENCES strutture (id))""",
    """CREATE TABLE operatori (id INTEGER NOT NULL, cognome VARCHAR(60) NOT NULL, nome VARCHAR(60),
       specialita VARCHAR(60), colore VARCHAR(7), attivo BOOLEAN NOT NULL, PRIMARY KEY (id))""",
    """CREATE TABLE prestazioni (id INTEGER NOT NULL, nome VARCHAR(80) NOT NULL, durata_min INTEGER NOT NULL,
       campi_extra VARCHAR(200), PRIMARY KEY (id), UNIQUE (nome))""",
    """CREATE TABLE pazienti (id INTEGER NOT NULL, cognome VARCHAR(60) NOT NULL, nome VARCHAR(60),
       telefono VARCHAR(30), note TEXT, PRIMARY KEY (id))""",
    """CREATE TABLE turni (id INTEGER NOT NULL, operatore_id INTEGER NOT NULL, risorsa_id INTEGER NOT NULL,
       giorno_settimana INTEGER NOT NULL, ora_inizio TIME NOT NULL, ora_fine TIME NOT NULL,
       valido_da DATE NOT NULL, valido_a DATE, PRIMARY KEY (id))""",
    SCHEMA_APP_V12,
    "CREATE INDEX ix_appuntamenti_inizio ON appuntamenti (inizio)",
    """CREATE TABLE modifiche (id INTEGER NOT NULL, quando DATETIME NOT NULL, entita VARCHAR(40) NOT NULL,
       entita_id INTEGER, azione VARCHAR(20) NOT NULL, dettaglio TEXT, PRIMARY KEY (id))""",
]


def database_v12(con_vincolo=True, doppioni=False):
    p = percorso_nuovo('v12')
    c = sqlite3.connect(p)
    for ddl in SCHEMA_V12:
        if not con_vincolo and ddl is SCHEMA_APP_V12:
            ddl = ddl.replace('CONSTRAINT una_stanza_un_orario UNIQUE (risorsa_id, inizio),', '')
        c.execute(ddl)
    c.execute("INSERT INTO strutture (id, nome, attiva) VALUES (1, 'Clinica Posillipo', 1)")
    for k in range(1, 4):
        c.execute("INSERT INTO risorse (nome, tipo, struttura_id, ordine, attiva) VALUES (?, 'AMBULATORIO', 1, ?, 1)",
                  ('Ambulatorio %d' % k, k))
    c.execute("INSERT INTO operatori (cognome, nome, specialita, colore, attivo) VALUES ('Lippiello', '', '', '#154381', 1)")
    c.execute("INSERT INTO prestazioni (nome, durata_min, campi_extra) VALUES ('Controllo', 20, '')")
    c.execute("INSERT INTO pazienti (cognome, nome, telefono, note) VALUES ('Esposito', 'Anna', '3331234567', 'n')")
    # le date come le scrive SQLAlchemy, microsecondi compresi: e' cosi' che
    # le ha lasciate la 1.2, e l'indice unico confronta il testo
    fmt = lambda x: x.strftime('%Y-%m-%d %H:%M:%S.%f')
    for n, (h, m) in enumerate([(9, 0), (9, 30), (10, 0)]):
        i = datetime.combine(MAR, time(h, m))
        c.execute("INSERT INTO appuntamenti (risorsa_id, operatore_id, paziente_id, prestazione_id, inizio, fine, "
                  "stato, note) VALUES (1, 1, 1, 1, ?, ?, 'CONFERMATO', ?)",
                  (fmt(i), fmt(i + timedelta(minutes=20)), 'dalla 1.2 n.%d' % n))
    if doppioni:
        i = datetime.combine(MAR, time(9, 0))
        c.execute("INSERT INTO appuntamenti (risorsa_id, operatore_id, inizio, fine, stato, note) "
                  "VALUES (1, 1, ?, ?, 'CONFERMATO', 'doppione')", (fmt(i), fmt(i + timedelta(minutes=20))))
    c.commit()
    c.close()
    return p


def righe(p, sql):
    c = sqlite3.connect(p)
    r = c.execute(sql).fetchall()
    c.close()
    return r


def ag_da_12():
    p = database_v12()
    prima = righe(p, 'SELECT id, risorsa_id, operatore_id, paziente_id, inizio, fine, note FROM appuntamenti ORDER BY id')
    S = crea_sessione('sqlite:///' + p)
    assert S.versione_precedente == 2, 'versione trovata %s' % S.versione_precedente
    dopo = righe(p, 'SELECT id, risorsa_id, operatore_id, paziente_id, inizio, fine, note FROM appuntamenti ORDER BY id')
    assert prima == dopo, 'appuntamenti cambiati nella ricostruzione'
    stati = {r[0] for r in righe(p, 'SELECT stato FROM appuntamenti')}
    assert stati == {'PRENOTATO'}, 'stati dopo la migrazione: %s' % stati
    ddl = righe(p, "SELECT sql FROM sqlite_master WHERE name = 'appuntamenti'")[0][0]
    assert 'una_stanza_un_orario' not in ddl, 'il vecchio vincolo e rimasto'
    indici = {r[0] for r in righe(p, "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'appuntamenti'")}
    assert {'appuntamento_attivo_unico', 'ix_appuntamenti_inizio'} <= indici, 'indici: %s' % indici
    assert righe(p, "SELECT valore FROM impostazioni WHERE chiave = 'versione_schema'") == [(str(VERSIONE_SCHEMA),)], 'versione non scritta'
    assert righe(p, 'PRAGMA integrity_check') == [('ok',)], 'database non integro'
    copie = [m for m in S.migrazioni if m.startswith('copia di sicurezza:')]
    assert copie, 'nessuna copia di sicurezza prima di migrare: %s' % S.migrazioni
    copia = copie[0].split(': ', 1)[1]
    assert righe(copia, "SELECT DISTINCT stato FROM appuntamenti") == [('CONFERMATO',)], 'la copia non e quella di prima'
    S2 = crea_sessione('sqlite:///' + p)
    assert S2.versione_precedente == VERSIONE_SCHEMA and S2.colonne_aggiunte == [] and S2.migrazioni == [], \
        'al secondo avvio rifa qualcosa: %s %s' % (S2.colonne_aggiunte, S2.migrazioni)
    return '; '.join(m.split(':')[0] if m.startswith('copia') else m for m in S.migrazioni)


def ag_indice_parziale():
    p = database_v12()
    S = crea_sessione('sqlite:///' + p)
    s = S()
    i = datetime.combine(MAR, time(9, 0))
    s.add(Appuntamento(risorsa_id=1, operatore_id=1, inizio=i, fine=i + timedelta(minutes=20)))
    try:
        s.commit()
        doppio = True
    except IntegrityError:
        s.rollback()
        doppio = False
    assert not doppio, 'due appuntamenti attivi nella stessa stanza alla stessa ora'
    a = s.scalars(select(Appuntamento).where(Appuntamento.inizio == i)).first()
    a.stato = 'DISDETTO'
    s.commit()
    s.add(Appuntamento(risorsa_id=1, operatore_id=1, inizio=i, fine=i + timedelta(minutes=20)))
    s.commit()                       # con il primo disdetto si riprenota la stessa ora
    n = s.scalar(select(func.count()).select_from(Appuntamento).where(Appuntamento.inizio == i))
    s.close()
    assert n == 2, 'righe alle 9: %d' % n


def ag_senza_vincolo_con_doppioni():
    p = database_v12(con_vincolo=False, doppioni=True)
    S = crea_sessione('sqlite:///' + p)
    note = ' '.join(S.migrazioni)
    assert 'indice appuntamento_attivo_unico non creato' in note, 'doppioni: %s' % note
    assert righe(p, 'SELECT COUNT(*) FROM appuntamenti') == [(4,)], 'righe perse'
    C = collega(S)
    assert C.get('/giorno/%s' % MAR.isoformat()).status_code == 200, 'griglia non disponibile'
    return 'aggiornato lo stesso, indice saltato e segnalato'


def ag_transazione():
    """La migrazione si appoggia a in_transazione: o passa tutto o niente."""
    p = percorso_nuovo('tr')
    motore = create_engine('sqlite:///' + p)
    with motore.begin() as c:
        c.exec_driver_sql('CREATE TABLE t (x INTEGER)')

    def lavoro(cur):
        cur.execute('CREATE TABLE t2 (y INTEGER)')
        cur.execute('INSERT INTO t VALUES (1)')
        raise RuntimeError('guasto a meta')
    try:
        modelli.in_transazione(motore, lavoro)
    except RuntimeError:
        pass
    tabelle = {r[0] for r in righe(p, "SELECT name FROM sqlite_master WHERE type='table'")}
    assert tabelle == {'t'}, 'dopo il guasto restano tabelle a meta: %s' % tabelle
    assert righe(p, 'SELECT COUNT(*) FROM t') == [(0,)], 'riga rimasta dopo il guasto'
    motore.dispose()


def ag_pagine_dopo():
    p = database_v12()
    S = crea_sessione('sqlite:///' + p)
    C = collega(S)
    for u in ('/giorno/%s' % MAR.isoformat(), '/giorno/%s/elenco' % MAR.isoformat(), '/settimana/%s' % MAR.isoformat(),
              '/mese/2027-03', '/pazienti', '/pazienti/1', '/appuntamento/1', '/statistiche', '/conferme',
              '/stampa/%s' % MAR.isoformat(), '/esporta/%s' % MAR.isoformat()):
        r = C.get(u)
        assert r.status_code == 200, '%s -> %d' % (u, r.status_code)
    assert 'Esposito' in html(C.get('/giorno/%s' % MAR.isoformat())), 'appuntamenti spariti dalla griglia'


prova('dalla 1.2: dati intatti, stati, indice, copia, secondo avvio', ag_da_12)
prova('indice unico solo sugli appuntamenti attivi', ag_indice_parziale)
prova('database vecchissimo con doppioni: si aggiorna lo stesso', ag_senza_vincolo_con_doppioni)
prova('una migrazione interrotta non lascia tabelle a meta', ag_transazione)
prova('dopo l aggiornamento tutte le pagine rispondono', ag_pagine_dopo)


# =====================================================================
area('stati degli appuntamenti')
S, C = mondo()
I = ids(S)


def st_predefinito():
    r = prenota(C, I, I['Ambulatorio 1'], I['Lippiello'], I['Controllo'], MAR, '09:00', paziente='Rossi')
    assert r.status_code == 302, 'HTTP %d' % r.status_code
    s = S()
    a = s.scalars(select(Appuntamento).order_by(Appuntamento.id.desc())).first()
    stato = a.stato
    s.close()
    assert stato == 'PRENOTATO', 'stato di un nuovo appuntamento: %s' % stato


def cambia(aid, stato, torna=None):
    d = {'stato': stato}
    if torna is not None:
        d['torna'] = torna
    return C.post('/appuntamento/%d/stato' % aid, data=d)


def st_arrivato():
    aid = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], MAR, 10, 0)
    r = cambia(aid, 'ARRIVATO')
    assert r.status_code == 302, 'HTTP %d' % r.status_code
    a = leggi_app(S, aid)
    assert a['stato'] == 'ARRIVATO' and a['arrivato'] is not None, 'arrivo non registrato: %s' % a
    cambia(aid, 'CONFERMATO')
    a = leggi_app(S, aid)
    assert a['stato'] == 'CONFERMATO' and a['arrivato'] is None, 'ora di arrivo rimasta: %s' % a
    s = S()
    n = s.scalar(select(func.count()).select_from(Modifica).where(
        Modifica.entita_id == aid, Modifica.azione == 'STATO'))
    s.close()
    assert n == 2, 'cambi di stato registrati nello storico: %d' % n


def st_disdetto_libera():
    aid = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], MAR, 11, 0)
    cambia(aid, 'DISDETTO')
    avvisi(C)
    s = S()
    motivi = servizi.conflitti(s, I['Ambulatorio 1'], I['Lippiello'], datetime.combine(MAR, time(11, 0)),
                               datetime.combine(MAR, time(11, 30)))
    s.close()
    assert motivi == [], 'il disdetto blocca ancora: %s' % motivi
    r = prenota(C, I, I['Ambulatorio 1'], I['Lippiello'], I['Controllo'], MAR, '11:00', durata='30', paziente='Bianchi')
    assert r.status_code == 302, 'la fascia disdetta non si riprenota: HTTP %d' % r.status_code
    assert 'Appuntamento salvato' in avvisi(C), 'nessuna conferma di salvataggio'
    # rimettere in agenda il disdetto ora e' impossibile: la fascia e' presa
    cambia(aid, 'PRENOTATO')
    assert leggi_app(S, aid)['stato'] == 'DISDETTO', 'riattivato sopra un altro appuntamento'
    assert 'non si può rimettere in agenda' in avvisi(C), 'rifiuto non spiegato'
    return 'riprenotata la fascia, riattivazione rifiutata'


def st_non_valido():
    aid = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], MAR, 12, 0)
    for v in ('ANNULLATO', '', "'; DROP TABLE appuntamenti; --", 'prenotato'):
        cambia(aid, v)
        assert leggi_app(S, aid)['stato'] == 'PRENOTATO', 'stato %r accettato' % v
    avvisi(C)
    assert C.post('/appuntamento/999999/stato', data={'stato': 'ARRIVATO'}).status_code == 404, 'nessun 404'


def st_redirect_esterno():
    aid = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], MAR, 12, 30)
    for cattivo in ('//sito.example/x', 'http://sito.example/', '/\\sito.example', 'javascript:alert(1)',
                    '/giorno\n/x'):
        r = cambia(aid, 'CONFERMATO' if leggi_app(S, aid)['stato'] != 'CONFERMATO' else 'PRENOTATO', cattivo)
        destinazione = r.headers.get('Location', '')
        assert destinazione.startswith('/giorno/'), '%r porta a %s' % (cattivo, destinazione)
    r = cambia(aid, 'ARRIVATO', '/giorno/%s/elenco?struttura=1' % MAR.isoformat())
    assert r.headers['Location'].endswith('/giorno/%s/elenco?struttura=1' % MAR.isoformat()), 'ritorno interno ignorato'
    avvisi(C)


def st_griglia():
    g = MAR + timedelta(days=7)
    a1 = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], g, 9, 0, stato='DISDETTO')
    a2 = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], g, 10, 0, stato='NON_PRESENTATO')
    a3 = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], g, 11, 0, stato='ARRIVATO')
    s = S()
    v = servizi.griglia(s, g, 1)
    in_celle = {a.id for c in v['colonne'] for x in c['celle'] if x['stato'] == 'occupata' for a in x['apps']}
    annullati = {a.id for a in v['annullati']}
    cella_9 = [x for x in v['colonne'][0]['celle'] if x['ora'] == time(9, 0)][0]
    s.close()
    assert in_celle == {a3}, 'in griglia: %s' % in_celle
    assert annullati == {a1, a2}, 'elencati a parte: %s' % annullati
    assert cella_9['stato'] == 'aperta', 'la fascia del disdetto non torna libera: %s' % cella_9['stato']
    t = html(C.get('/giorno/%s' % g.isoformat()))
    assert 'Disdetti e non presentati' in t and 'arrivato' in t, 'griglia senza stati'


def st_modifica_disdetto():
    g = MAR + timedelta(days=14)
    a1 = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], g, 9, 0, stato='DISDETTO')
    nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], g, 9, 0)
    r = C.post('/appuntamento/%d' % a1, data={
        'struttura': '1', 'risorsa': str(I['Ambulatorio 1']), 'operatore': str(I['Lippiello']),
        'prestazione': str(I['Controllo']), 'data': g.isoformat(), 'ora': '09:00', 'durata': '30',
        'note': 'ha chiamato per disdire'})
    assert r.status_code == 302, 'un disdetto non si puo nemmeno annotare: HTTP %d' % r.status_code
    avvisi(C)
    assert leggi_app(S, a1)['stato'] == 'DISDETTO', 'lo stato e cambiato salvando'


prova('nuovo appuntamento: prenotato', st_predefinito)
prova('arrivato: ora registrata, tolta tornando indietro, storico', st_arrivato)
prova('disdetto libera la fascia; non si riattiva sopra un altro', st_disdetto_libera)
prova('stati non validi e appuntamento inesistente', st_non_valido)
prova('ritorno solo verso pagine interne', st_redirect_esterno)
prova('griglia: disdetti e non presentati fuori dalle celle', st_griglia)
prova('un disdetto si modifica senza conflitti', st_modifica_disdetto)


# =====================================================================
area('pazienti: controlli')


def cf_oracolo(cf15):
    """Carattere di controllo scritto dalle tabelle ufficiali, in modo diverso
    da pazienti.py: posizioni dispari (1a, 3a...) e pari."""
    dispari = dict(zip('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                       [1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 1, 0, 5, 7, 9, 13, 15, 17, 19, 21,
                        2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23]))
    pari = {c: (int(c) if c.isdigit() else ord(c) - 65) for c in '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'}
    totale = 0
    for posizione, c in enumerate(cf15, start=1):
        totale += dispari[c] if posizione % 2 else pari[c]
    return 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'[totale % 26]


def pz_cf():
    caso = random.Random(7)
    lettere = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    mesi = 'ABCDEHLMPRST'
    buoni = 0
    for _ in range(400):
        # giorni che esistono in ogni mese (le donne piu' 40): dalla 1.7 una data inesistente rende il codice non valido
        base = (''.join(caso.choice(lettere) for _ in range(6)) + '%02d' % caso.randint(0, 99)
                + caso.choice(mesi) + '%02d' % (caso.randint(1, 28) + caso.choice((0, 40))) + caso.choice(lettere)
                + '%03d' % caso.randint(0, 999))
        if caso.random() < 0.3:                       # omocodia: una cifra diventa lettera
            pos = caso.choice([6, 7, 9, 10, 12, 13, 14])
            base = base[:pos] + 'LMNPQRSTUV'[int(base[pos])] + base[pos + 1:]
        giusto = base + cf_oracolo(base)
        assert PZ.codice_fiscale_valido(giusto), 'valido rifiutato: %s' % giusto
        assert PZ.codice_fiscale_valido(giusto.lower()), 'minuscolo rifiutato: %s' % giusto
        sbagliato = base + lettere[(lettere.index(cf_oracolo(base)) + 1) % 26]
        assert not PZ.codice_fiscale_valido(sbagliato), 'controllo sbagliato accettato: %s' % sbagliato
        buoni += 1
    for cattivo in ('', 'RSSMRA85T10A562', 'RSSMRA85T10A562SX', 'RSSMRA85Z10A562S', '1SSMRA85T10A562S',
                    'RSSMRA85T10A5 2S'):
        assert not PZ.codice_fiscale_valido(cattivo), 'forma sbagliata accettata: %r' % cattivo
    return '%d codici generati con l oracolo, 6 forme sbagliate' % buoni


def pz_telefoni():
    casi = [('333 1234567', '3331234567', True, '393331234567'),
            ('+39 333 12.34.567', '3331234567', True, '393331234567'),
            ('0039-3331234567', '3331234567', True, '393331234567'),
            ('393 1234567', '3931234567', True, '393931234567'),      # cellulare che inizia per 39
            ('393331234567', '3331234567', True, '393331234567'),
            ('081 5551234', '0815551234', False, '390815551234'),
            ('+44 20 7946 0958', '442079460958', False, '442079460958'),
            ('12345', '12345', False, None), ('', '', False, None)]
    for testo, confronto, cellulare, internazionale in casi:
        assert PZ.telefono_confronto(testo) == confronto, '%r -> %r' % (testo, PZ.telefono_confronto(testo))
        assert PZ.e_cellulare(testo) == cellulare, '%r cellulare %s' % (testo, PZ.e_cellulare(testo))
        assert PZ.numero_internazionale(testo) == internazionale, '%r -> %r' % (testo, PZ.numero_internazionale(testo))


def pz_email():
    for buona in ('a@b.it', 'mario.rossi+prenotazioni@studio-medico.example.com'):
        assert PZ.email_valida(buona), buona
    for cattiva in ('', 'mario', 'mario@', '@x.it', 'a b@x.it', 'a@b', 'a@@b.it', 'a@b.i', '<a@b.it>'):
        assert not PZ.email_valida(cattiva), cattiva


def pz_collegamenti():
    p = Paziente(cognome="D'Angelo", nome='Rosa', telefono='333 1234567', email='rosa.dangelo@example.it')
    c = PZ.collegamenti_paziente(p, "Gentile Rosa, ciao & a presto?", 'Promemoria 3/3')
    assert c['tel'] == 'tel:+393331234567', c['tel']
    assert c['whatsapp'].startswith('https://wa.me/393331234567?text='), c['whatsapp']
    assert unquote(c['whatsapp'].split('text=', 1)[1]) == "Gentile Rosa, ciao & a presto?", 'testo WhatsApp alterato'
    assert '&' not in c['whatsapp'].split('text=', 1)[1], 'la & non codificata spezza il messaggio'
    assert c['email'].startswith('mailto:rosa.dangelo@example.it?subject=Promemoria%203/3&body='), c['email']
    fisso = PZ.collegamenti_paziente(Paziente(cognome='X', telefono='081 555 1234'), 'x')
    assert 'whatsapp' not in fisso and fisso['tel'] == 'tel:+390815551234', 'WhatsApp su un numero fisso'
    due = PZ.collegamenti_paziente(Paziente(cognome='X', telefono='081 555 1234', telefono2='+39 347 765 4321'), 'x')
    assert due['tel'] == 'tel:+390815551234', 'si chiama il primo numero'
    assert due['whatsapp'].startswith('https://wa.me/393477654321?'), 'WhatsApp al cellulare secondo: %s' % due.get('whatsapp')
    solo2 = PZ.collegamenti_paziente(Paziente(cognome='X', telefono='', telefono2='3331112222'), 'x')
    assert solo2['tel'] == 'tel:+393331112222' and solo2['tel_numero'] == '3331112222', solo2
    assert 'whatsapp' not in PZ.collegamenti_paziente(Paziente(cognome='X', telefono='081 1', telefono2='089 555 6666'), 'x'), 'due fissi'
    niente = PZ.collegamenti_paziente(Paziente(cognome='X', telefono='abc', email='non-valida'), 'x')
    assert niente == {}, 'collegamenti da dati non validi: %s' % niente


prova('codice fiscale: 400 generati con oracolo indipendente, omocodia', pz_cf)
prova('telefoni: forma confrontabile, cellulare, internazionale', pz_telefoni)
prova('email', pz_email)
prova('collegamenti chiamata, WhatsApp, email', pz_collegamenti)


# =====================================================================
area('pazienti: ricerca, scheda, doppioni')
S, C = mondo()
I = ids(S)


def crea_paz(**campi):
    s = S()
    p = Paziente(**campi)
    s.add(p)
    s.commit()
    pid = p.id
    s.close()
    return pid


P_DANGELO = crea_paz(cognome="D'Angelo", nome='Rosa', telefono='333 1234567', email='rosa@example.it')
P_DELUCA = crea_paz(cognome='DE LUCA', nome='CIRO', telefono='+39 340 1112223', codice_fiscale='DLCCRI80A01F839Q')
P_ALVAREZ = crea_paz(cognome='Álvarez', nome='Inés', telefono='081 5551234')
P_ROSSI1 = crea_paz(cognome='Rossi', nome='Mario', telefono='3331000001')
P_ROSSI2 = crea_paz(cognome='Rossi', nome='Marta', telefono='3331000002')


def trovati(q):
    s = S()
    r = [p.id for p in PZ.cerca(s, q)]
    s.close()
    return r


def pr_ricerca():
    casi = [('dangelo', [P_DANGELO]), ("d'angelo", [P_DANGELO]), ('D ANGELO', [P_DANGELO]),
            ('de luca', [P_DELUCA]), ('deluca ciro', [P_DELUCA]), ('ciro deluca', [P_DELUCA]),
            ('alvarez', [P_ALVAREZ]), ('ines', [P_ALVAREZ]), ('1234567', [P_DANGELO]),
            ('+39 333 1234567'.replace(' ', ''), [P_DANGELO]), ('5551234', [P_ALVAREZ]),
            ('rosa@example', [P_DANGELO]), ('DLCCRI', [P_DELUCA]), ('rossi mario', [P_ROSSI1]),
            ('xyz', []), ('', [])]
    for q, attesi in casi:
        assert trovati(q) == attesi, '%r -> %s invece di %s' % (q, trovati(q), attesi)
    assert set(trovati('rossi')) == {P_ROSSI1, P_ROSSI2}, 'omonimi non trovati entrambi'
    assert trovati('ros')[:2] in ([P_ROSSI2, P_ROSSI1], [P_ROSSI1, P_ROSSI2]) and len(trovati('ros')) == 3, \
        'chi inizia per il cognome cercato deve venire prima: %s' % trovati('ros')
    return '%d ricerche' % len(casi)


def pr_json():
    crea_paz(cognome='<script>alert(1)</script>', nome='x', telefono='3339990000')
    r = C.get('/pazienti/cerca?q=script')
    assert r.mimetype == 'application/json', r.mimetype
    assert b'<script>' not in r.data, 'il JSON contiene HTML non protetto'
    dati = r.get_json()
    assert dati and dati[0]['cognome'] == '<script>alert(1)</script>', 'dato alterato: %s' % dati
    assert C.get('/pazienti/cerca?q=a').get_json() == [], 'con una lettera sola risponde'
    for i in range(12):
        crea_paz(cognome='Serie%02d' % i, telefono='333%07d' % i)
    assert len(C.get('/pazienti/cerca?q=serie').get_json()) == 8, 'suggerimenti oltre 8'


def pr_scheda_controlli():
    base = {'cognome': 'Verdi', 'nome': 'Luca', 'telefono': '3335550000', 'email': '', 'codice_fiscale': '',
            'data_nascita': '', 'canale': 'WHATSAPP', 'promemoria': '1', 'note': ''}
    for campo, valore, frammento in [('cognome', '', 'Cognome: campo obbligatorio'),
                                     ('email', 'luca@', 'Email: indirizzo non valido'),
                                     ('codice_fiscale', 'VRDLCU80A01F839X', 'Codice fiscale: non valido'),
                                     ('data_nascita', (date.today() + timedelta(days=1)).isoformat(), 'fuori dall'),
                                     ('data_nascita', '1850-01-01', 'fuori dall'),
                                     ('telefono', '12-34', 'almeno 6 cifre'),
                                     ('canale', 'PICCIONE', 'Canale: scelta non valida')]:
        d = dict(base)
        d[campo] = valore
        r = C.post('/pazienti/nuovo', data=d)
        messaggi = avvisi(C, r)
        assert r.status_code == 200 and frammento in messaggi, '%s=%r: %s' % (campo, valore, messaggi)
    d = dict(base, codice_fiscale='rssmra85t10a562s', data_nascita='1985-12-10')
    r = C.post('/pazienti/nuovo', data=d)
    assert r.status_code == 302, 'scheda valida rifiutata: %s' % avvisi(C)
    avvisi(C)
    s = S()
    p = s.scalars(select(Paziente).where(Paziente.cognome == 'Verdi')).first()
    cf, nascita = p.codice_fiscale, p.data_nascita
    s.close()
    assert cf == 'RSSMRA85T10A562S' and nascita == date(1985, 12, 10), 'salvati %s %s' % (cf, nascita)


def pr_doppioni():
    base = {'cognome': 'Rossi', 'nome': 'Mario', 'telefono': '3339998887', 'canale': 'SMS'}
    r = C.post('/pazienti/nuovo', data=base)
    assert r.status_code == 200 and 'Potrebbe essere già in anagrafica' in html(r), 'omonimo non segnalato'
    r = C.post('/pazienti/nuovo', data=dict(base, cognome='Bianco', nome='', telefono='+39 333 100 0002'))
    assert 'Potrebbe essere già in anagrafica' in html(r), 'stesso telefono non segnalato'
    r = C.post('/pazienti/nuovo', data=dict(base, cognome='Neri', telefono='3330000000', email='ROSA@example.it'))
    assert 'Potrebbe essere già in anagrafica' in html(r), 'stessa email non segnalata'
    r = C.post('/pazienti/nuovo', data=dict(base, doppione_confermato='1'))
    assert r.status_code == 302, 'la conferma non basta a salvare'
    avvisi(C)
    s = S()
    n = s.scalar(select(func.count()).select_from(Paziente).where(Paziente.cognome == 'Rossi', Paziente.nome == 'Mario'))
    s.close()
    assert n == 2, 'Rossi Mario presenti: %d' % n


def pr_elimina():
    pid = crea_paz(cognome='Dasolo', telefono='3330001111')
    aid = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], MAR, 13, 0, paziente=pid)
    C.post('/pazienti/%d' % pid, data={'azione': 'elimina'})
    assert 'non si può eliminare' in avvisi(C), 'eliminato con un appuntamento'
    s = S()
    s.delete(s.get(Appuntamento, aid))
    s.commit()
    s.close()
    r = C.post('/pazienti/%d' % pid, data={'azione': 'elimina'})
    avvisi(C)
    s = S()
    rimasto = s.get(Paziente, pid)
    s.close()
    assert r.status_code == 302 and rimasto is None, 'scheda senza appuntamenti non eliminata'


def pr_unisci():
    a = crea_paz(cognome='Caputo', nome='Rita', telefono='3331110000')
    b = crea_paz(cognome='CAPUTO', nome='', telefono='3332220000', email='rita@example.it',
                 codice_fiscale='RSSMRA85T10A562S', note='allergica al lattice')
    x1 = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], MAR, 13, 30, paziente=b)
    x2 = nuovo_app(S, I['Sala endoscopia'], I['Galasso'], MAR, 8, 0, paziente=b)
    r = C.post('/pazienti/%d/unisci' % a, data={'altro': str(b)})
    assert r.status_code == 200, 'unione senza conferma eseguita'
    r = C.post('/pazienti/%d/unisci' % a, data={'altro': str(b), 'conferma': '1'})
    assert r.status_code == 302, 'HTTP %d' % r.status_code
    avvisi(C)
    s = S()
    tenuto = s.get(Paziente, a)
    assert s.get(Paziente, b) is None, 'la scheda assorbita esiste ancora'
    assert {s.get(Appuntamento, x1).paziente_id, s.get(Appuntamento, x2).paziente_id} == {a}, 'appuntamenti non spostati'
    assert tenuto.email == 'rita@example.it' and tenuto.codice_fiscale == 'RSSMRA85T10A562S', 'dati non completati'
    assert tenuto.telefono2 == '3332220000' and 'lattice' in tenuto.note, 'telefono o note persi'
    storico = s.scalar(select(func.count()).select_from(Modifica).where(Modifica.azione == 'UNITO'))
    s.close()
    assert storico == 1, 'unione non registrata'
    r = C.post('/pazienti/%d/unisci' % a, data={'altro': str(a), 'conferma': '1'})
    s = S()
    ancora = s.get(Paziente, a)
    s.close()
    assert ancora is not None, 'unito con se stesso ed eliminato'


def pr_pagine():
    for u in ('/pazienti', '/pazienti?q=rossi', '/pazienti?q=' + 'x' * 500, '/pazienti/%d' % P_DANGELO,
              '/pazienti/nuovo', '/pazienti/%d/unisci' % P_DANGELO, '/pazienti/%d/unisci?q=rossi' % P_DANGELO):
        assert C.get(u).status_code == 200, u
    assert C.get('/pazienti/999999').status_code == 404, 'scheda inesistente senza 404'


prova('ricerca senza maiuscole, accenti, apostrofi; telefoni; email; CF', pr_ricerca)
prova('suggerimenti in JSON: dati come testo, al massimo 8', pr_json)
prova('scheda: controlli su ogni campo', pr_scheda_controlli)
prova('doppioni: nome, telefono, email; conferma per salvare', pr_doppioni)
prova('eliminazione solo senza appuntamenti', pr_elimina)
prova('unione di due schede', pr_unisci)
prova('pagine dei pazienti', pr_pagine)


# =====================================================================
area('prenotazione con paziente e campi nuovi')
S, C = mondo()
I = ids(S)


def pp_sceglie_paziente():
    pid = crea_paz(cognome='Improta', nome='Rosa', telefono='3330000001')
    r = prenota(C, I, I['Ambulatorio 1'], I['Lippiello'], I['Controllo'], MAR, '09:00', paziente_id=pid,
                paziente='Improta', telefono='347 1234567', email_paziente='rosa@example.it')
    assert r.status_code == 302, avvisi(C)
    avvisi(C)
    s = S()
    p = s.get(Paziente, pid)
    a = s.scalars(select(Appuntamento).order_by(Appuntamento.id.desc())).first()
    esito = (a.paziente_id, p.telefono, p.telefono2, p.email)
    s.close()
    assert esito == (pid, '347 1234567', '3330000001', 'rosa@example.it'), 'scheda: %s' % (esito,)


def pp_cognome_diverso():
    pid = crea_paz(cognome='Scelto', telefono='3330000002')
    prenota(C, I, I['Ambulatorio 1'], I['Lippiello'], I['Controllo'], MAR, '09:30', paziente_id=pid,
            paziente='Altro', telefono='3330000003')
    avvisi(C)
    s = S()
    p = s.get(Paziente, pid)
    a = s.scalars(select(Appuntamento).order_by(Appuntamento.id.desc())).first()
    esito = (p.cognome, a.paziente_id != pid, a.paziente.cognome)
    s.close()
    assert esito == ('Scelto', True, 'Altro'), 'il paziente scelto e stato rinominato: %s' % (esito,)


def pp_riusa_per_telefono():
    prenota(C, I, I['Ambulatorio 1'], I['Lippiello'], I['Controllo'], MAR, '10:00', paziente='Ferrara', telefono='333 777 8888')
    prenota(C, I, I['Ambulatorio 1'], I['Lippiello'], I['Controllo'], MAR, '10:30', paziente='ferrara', telefono='+39 3337778888')
    prenota(C, I, I['Ambulatorio 1'], I['Lippiello'], I['Controllo'], MAR, '11:00', paziente='Ferrara', telefono='3339999999')
    avvisi(C)
    s = S()
    n = s.scalar(select(func.count()).select_from(Paziente).where(func.lower(Paziente.cognome) == 'ferrara'))
    s.close()
    assert n == 2, 'schede Ferrara: %d (attese 2: stesso numero scritto in due modi, omonimo diverso)' % n


def pp_importi():
    casi = [('80', 8000), ('80,5', 8050), ('80,50', 8050), ('1.250,50', 125050), ('1.250', 125000),
            ('80.50', 8050), ('€ 80', 8000), ('0', 0), ('', None)]
    for testo, atteso in casi:
        assert A.leggi_importo(testo) == atteso, '%r -> %r' % (testo, A.leggi_importo(testo))
    for cattivo in ('-5', 'abc', '100001', '1e3', 'nan', 'inf', '80,5,5'):
        try:
            A.leggi_importo(cattivo)
            assert False, '%r accettato' % cattivo
        except ValueError:
            pass
    return '%d importi, 7 rifiutati' % len(casi)


def pp_campi_extra():
    s = S()
    colon = s.get(Prestazione, I['Colonscopia'])
    colon.campi_extra = 'Sedazione?, Anestesista, Preparazione consegnata?'
    s.commit()
    pid_colon, pid_ctrl = colon.id, I['Controllo']
    s.close()
    r = prenota(C, I, I['Sala endoscopia'], I['Galasso'], pid_colon, MAR, '08:00', paziente='Aiello',
                tipo='PRESTAZIONE', convenzione='Unisalute', importo='250,00',
                **{'extra_%d_0' % pid_colon: '1', 'extra_%d_1' % pid_colon: ' Izzo  ',
                   'extra_%d_0' % pid_ctrl: 'intruso'})
    assert r.status_code == 302, avvisi(C)
    avvisi(C)
    s = S()
    a = s.scalars(select(Appuntamento).order_by(Appuntamento.id.desc())).first()
    esito = (a.tipo, a.convenzione, a.importo_cent, a.valori_extra)
    s.close()
    assert esito == ('PRESTAZIONE', 'Unisalute', 25000,
                     {'Sedazione': 'Sì', 'Anestesista': 'Izzo', 'Preparazione consegnata': 'No'}), esito


def pp_errori_campi_nuovi():
    for campo, valore, frammento in [('importo', '12,3,4', 'Importo: non valido'),
                                     ('tipo', 'VIP', 'Tipo: scelta non valida'),
                                     ('email_paziente', 'x@', 'Email del paziente'),
                                     ('paziente', 'C' * 61, 'al massimo 60'),
                                     ('convenzione', 'K' * 81, 'Convenzione: al massimo 80')]:
        r = prenota(C, I, I['Ambulatorio 1'], I['Lippiello'], I['Controllo'], MAR, '12:00', **{campo: valore})
        t = avvisi(C, r)
        assert r.status_code == 200 and frammento in t, '%s=%r: %s' % (campo, valore[:20], t)
        assert valore[:20] in html(r) or campo == 'tipo', '%s: il modulo non ripropone il valore' % campo


def pp_avvisi_paziente():
    pid = crea_paz(cognome='Assente', telefono='3334445555')
    for k in range(2):
        nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], date.today() - timedelta(days=10 + k), 9, 0,
                  stato='NON_PRESENTATO', paziente=pid)
    nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], GIO, 9, 0, paziente=pid)
    prenota(C, I, I['Sala endoscopia'], I['Galasso'], I['Controllo'], GIO, '12:00', paziente_id=pid, paziente='Assente')
    t = avvisi(C)
    assert 'ha anche un appuntamento alle 09:00' in t, 'stesso giorno non segnalato: %s' % t
    assert 'non si è presentato 2 volte' in t, 'assenze non segnalate: %s' % t


def pp_modulo_proposte():
    pid = crea_paz(cognome='Proposto', nome='Tizio', telefono='3331231234')
    t = html(C.get('/appuntamento?data=%s&ora=10:00&risorsa=%d&struttura=1&medico=%d&prestazione=%d&durata=45&paziente_id=%d'
                   % (MAR, I['Ambulatorio 1'], I['Galasso'], I['Colonscopia'], pid)))
    assert re.search(r'<option value="%d" selected>Galasso' % I['Galasso'], t), 'medico cercato non proposto'
    assert re.search(r'<option value="%d" data-durata="45" selected>Colonscopia' % I['Colonscopia'], t), 'prestazione non proposta'
    assert 'value="Proposto"' in t and 'value="%d"' % pid in t, 'paziente non proposto'
    assert 'value="45"' in t, 'durata non proposta'


prova('paziente scelto dall elenco: telefono ed email aggiornati', pp_sceglie_paziente)
prova('scelto uno ma scritto un altro cognome: non lo rinomina', pp_cognome_diverso)
prova('riuso della scheda con lo stesso numero scritto diversamente', pp_riusa_per_telefono)
prova('importi all italiana', pp_importi)
prova('campi extra solo della prestazione scelta', pp_campi_extra)
prova('errori sui campi nuovi: rifiuto e modulo ricompilato', pp_errori_campi_nuovi)
prova('avvisi: altro appuntamento lo stesso giorno, assenze ripetute', pp_avvisi_paziente)
prova('modulo con medico, prestazione, durata e paziente proposti', pp_modulo_proposte)


# =====================================================================
area('festivita, assenze, chiusure, turni di un giorno')


def fe_pasqua():
    note = {2000: (4, 23), 2001: (4, 15), 2002: (3, 31), 2003: (4, 20), 2004: (4, 11), 2005: (3, 27),
            2006: (4, 16), 2007: (4, 8), 2008: (3, 23), 2009: (4, 12), 2010: (4, 4), 2011: (4, 24),
            2012: (4, 8), 2013: (3, 31), 2014: (4, 20), 2015: (4, 5), 2016: (3, 27), 2017: (4, 16),
            2018: (4, 1), 2019: (4, 21), 2020: (4, 12), 2021: (4, 4), 2022: (4, 17), 2023: (4, 9),
            2024: (3, 31), 2025: (4, 20), 2026: (4, 5), 2027: (3, 28), 2028: (4, 16), 2029: (4, 1),
            2030: (4, 21), 2038: (4, 25), 2285: (3, 22)}
    for anno, (m, g) in note.items():
        assert calendario.pasqua(anno) == date(anno, m, g), 'Pasqua %d: %s' % (anno, calendario.pasqua(anno))
    return '%d anni confrontati con le date note' % len(note)


def fe_elenco():
    f26 = calendario.festivita(2026)
    assert len(f26) == 13, 'festivita 2026: %d' % len(f26)
    assert f26[date(2026, 10, 4)] == "San Francesco d'Assisi", 'manca il 4 ottobre 2026'
    assert date(2025, 10, 4) not in calendario.festivita(2025), 'il 4 ottobre prima del 2026'
    assert calendario.festivo(date(2027, 3, 29)) == "Lunedì dell'Angelo", 'Pasquetta 2027'
    assert calendario.festivo(date(2027, 9, 19), (19, 9)) == 'Festa del patrono', 'patrono'
    assert calendario.festivo(date(2027, 9, 19)) is None, 'patrono senza averlo indicato'
    assert date(2027, 2, 28) not in calendario.festivita(2027, (29, 2)), '29/02 in un anno non bisestile'
    assert calendario.festivita(2028, (29, 2))[date(2028, 2, 29)] == 'Festa del patrono', '29/02 bisestile'


S, C = mondo()
I = ids(S)


def stato_fasce(g, stanza_nome, sid=1):
    s = S()
    v = servizi.griglia(s, g, sid)
    col = [c for c in v['colonne'] if c['risorsa'].nome == stanza_nome][0]
    uscita = {x['ora'].strftime('%H:%M'): x['stato'] for x in col['celle']}
    info, assenti = v['giorno'], col['assenti']
    s.close()
    return uscita, info, assenti


def fe_assenza():
    g = MAR + timedelta(days=21)
    s = S()
    s.add(Assenza(operatore_id=I['Lippiello'], dal=g, al=g, motivo='Congresso'))
    s.commit()
    s.close()
    fasce, info, assenti = stato_fasce(g, 'Ambulatorio 1')
    assert 'aperta' not in fasce.values(), 'medico assente con fasce aperte'
    assert assenti and assenti[0][1] == 'Congresso', 'intestazione senza assenza: %s' % assenti
    fasce_gal, _, _ = stato_fasce(g, 'Sala endoscopia')
    assert fasce_gal['09:00'] == 'aperta', 'l assenza di uno chiude anche gli altri'
    fasce_dopo, _, _ = stato_fasce(g + timedelta(days=2), 'Ambulatorio 1')
    assert fasce_dopo['09:00'] == 'aperta', 'l assenza vale anche fuori dal periodo'
    s = S()
    avviso = servizi.fuori_turno(s, I['Ambulatorio 1'], I['Lippiello'], datetime.combine(g, time(9, 0)),
                                 datetime.combine(g, time(9, 30)))
    s.close()
    assert avviso == 'Lippiello risulta assente il %s (Congresso).' % g.strftime('%d/%m'), avviso
    t = html(C.get('/appuntamento?data=%s&ora=09:00&risorsa=%d' % (g, I['Ambulatorio 1'])))
    assert not re.search(r'<option value="%d" selected>Lippiello' % I['Lippiello'], t), 'propone il medico assente'


def fe_chiusura():
    g = MAR + timedelta(days=28)
    s = S()
    s.add(Chiusura(struttura_id=1, dal=g, al=g, motivo='Lavori'))
    s.commit()
    s.close()
    for stanza in ('Ambulatorio 1', 'Sala endoscopia', 'Ambulatorio 3'):
        fasce, info, _ = stato_fasce(g, stanza)
        assert 'aperta' not in fasce.values(), '%s aperta in un giorno di chiusura' % stanza
    assert 'Struttura chiusa: Lavori' in html(C.get('/giorno/%s' % g.isoformat())), 'nessun avviso di chiusura'
    s = S()
    avviso = servizi.fuori_turno(s, I['Ambulatorio 1'], I['Lippiello'], datetime.combine(g, time(9, 0)),
                                 datetime.combine(g, time(9, 30)))
    s.close()
    assert avviso == 'La struttura risulta chiusa il %s (Lavori).' % g.strftime('%d/%m'), avviso


def fe_festivo():
    g = date(2027, 6, 2)                      # mercoledi, festa della Repubblica
    s = S()
    s.add(Turno(operatore_id=I['Lippiello'], risorsa_id=I['Ambulatorio 2'], giorno_settimana=2,
                ora_inizio=time(8, 0), ora_fine=time(12, 0), valido_da=date(2026, 1, 1)))
    s.commit()
    s.close()
    fasce, info, _ = stato_fasce(g, 'Ambulatorio 2')
    assert info['festivo'] == 'Festa della Repubblica' and fasce['09:00'] == 'aperta', \
        'festivo segnalato ma la struttura non ha scelto di chiudere: %s %s' % (info['festivo'], fasce['09:00'])
    assert 'Festivo: Festa della Repubblica' in html(C.get('/giorno/%s' % g.isoformat())), 'festivo non segnalato'
    s = S()
    s.get(Struttura, 1).chiusa_festivi = True
    s.commit()
    avviso = servizi.fuori_turno(s, I['Ambulatorio 2'], I['Lippiello'], datetime.combine(g, time(9, 0)),
                                 datetime.combine(g, time(9, 30)))
    s.close()
    fasce, info, _ = stato_fasce(g, 'Ambulatorio 2')
    assert fasce['09:00'] == 'chiusa', 'chiusa nei festivi ma fasce aperte'
    assert 'è festivo: Festa della Repubblica' in avviso, avviso
    s = S()
    s.add(Turno(operatore_id=I['Galasso'], risorsa_id=I['Ambulatorio 2'], giorno_settimana=g.weekday(),
                ora_inizio=time(14, 0), ora_fine=time(16, 0), valido_da=g, valido_a=g))
    s.commit()
    s.close()
    fasce, _, _ = stato_fasce(g, 'Ambulatorio 2')
    assert fasce['14:00'] == 'aperta' and fasce['09:00'] == 'chiusa', \
        'il turno di un giorno non riapre il festivo: %s %s' % (fasce['14:00'], fasce['09:00'])
    s = S()
    s.get(Struttura, 1).chiusa_festivi = False
    s.commit()
    s.close()


def fe_turno_giorno():
    g = MAR + timedelta(days=3)               # venerdi: nessun turno ricorrente
    r = C.post('/anagrafiche/turni/nuovo', data={
        'ripetizione': 'giorno', 'operatore': str(I['Galasso']), 'risorsa': str(I['Sala endoscopia']),
        'data_singola': g.isoformat(), 'ora_inizio': '08:00', 'ora_fine': '13:00'})
    assert r.status_code == 302, 'turno di un giorno rifiutato: %s' % avvisi(C)
    assert 'il %s' % g.strftime('%d/%m/%Y') in avvisi(C), 'conferma senza la data'
    fasce, _, _ = stato_fasce(g, 'Sala endoscopia')
    assert fasce['09:00'] == 'aperta', 'il turno di un giorno non apre le fasce'
    fasce, _, _ = stato_fasce(g + timedelta(days=7), 'Sala endoscopia')
    assert fasce['09:00'] == 'chiusa', 'il turno di un giorno vale anche la settimana dopo'
    t = html(C.get('/anagrafiche'))
    assert 'Turni di un giorno' in t and g.strftime('%d/%m/%Y') in t, 'turno di un giorno non elencato'
    r = C.post('/anagrafiche/turni/nuovo', data={'ripetizione': 'giorno', 'operatore': str(I['Galasso']),
                                                 'risorsa': str(I['Sala endoscopia']), 'data_singola': '',
                                                 'ora_inizio': '08:00', 'ora_fine': '13:00'})
    assert r.status_code == 200 and 'Giorno: campo obbligatorio' in avvisi(C, r), 'turno senza giorno accettato'


def fe_sostituzione():
    """La stanza di Lippiello, un martedi in cui e' assente, va a Galasso."""
    g = MAR + timedelta(days=35)
    dati = {'ripetizione': 'giorno', 'operatore': str(I['Galasso']), 'risorsa': str(I['Ambulatorio 1']),
            'data_singola': g.isoformat(), 'ora_inizio': '09:00', 'ora_fine': '12:00'}
    r = C.post('/anagrafiche/turni/nuovo', data=dati)
    assert r.status_code == 200 and 'già assegnata a Lippiello' in avvisi(C, r), 'stanza occupata non segnalata'
    s = S()
    s.add(Assenza(operatore_id=I['Lippiello'], dal=g, al=g, motivo='Ferie'))
    s.commit()
    s.close()
    r = C.post('/anagrafiche/turni/nuovo', data=dati)
    assert r.status_code == 302, 'sostituzione di un assente rifiutata: %s' % avvisi(C)
    avvisi(C)
    fasce, _, assenti = stato_fasce(g, 'Ambulatorio 1')
    assert fasce['10:00'] == 'aperta' and fasce['08:30'] == 'chiusa', 'la sostituzione non apre le sue fasce'


def fe_assenza_da_spostare():
    g = MAR + timedelta(days=42)
    aid = nuovo_app(S, I['Sala endoscopia'], I['Galasso'], g, 9, 0)
    r = C.post('/anagrafiche/assenze/nuova', data={'operatore': str(I['Galasso']), 'dal': g.isoformat(),
                                                   'al': '', 'motivo': 'Malattia'})
    assert r.status_code == 302 and '/anagrafiche/assenze/' in r.headers['Location'], 'nessun rinvio alla lista'
    assert 'da spostare' in avvisi(C), 'avviso mancante'
    t = html(C.get(r.headers['Location']))
    assert 'Appuntamenti da spostare (1)' in t and '/appuntamento/%d' % aid in t, 'lista da spostare mancante'
    s = S()
    x = s.scalars(select(Assenza).where(Assenza.motivo == 'Malattia')).first()
    esito = (x.dal, x.al)
    s.close()
    assert esito == (g, g), 'al vuoto: %s' % (esito,)
    for dati, frammento in [({'dal': g.isoformat(), 'al': (g - timedelta(days=1)).isoformat()}, 'viene prima'),
                            ({'dal': g.isoformat(), 'al': (g + timedelta(days=400)).isoformat()}, 'un anno'),
                            ({'dal': 'ieri', 'al': ''}, 'Dal: data non valida')]:
        r = C.post('/anagrafiche/assenze/nuova', data=dict(dati, operatore=str(I['Galasso']), motivo='x'))
        assert r.status_code == 200 and frammento in avvisi(C, r), 'periodo sbagliato accettato: %s' % dati


prova('Pasqua: 33 anni contro le date note', fe_pasqua)
prova('elenco festivita, 4 ottobre dal 2026, patrono, 29 febbraio', fe_elenco)
prova('assenza: chiude solo il medico assente, avviso, non proposto', fe_assenza)
prova('chiusura della struttura: tutto chiuso, avviso', fe_chiusura)
prova('festivo: segnalato; chiuso se scelto; il turno di un giorno riapre', fe_festivo)
prova('turno di un giorno: solo quel giorno, elencato, giorno obbligatorio', fe_turno_giorno)
prova('sostituzione di un medico assente con un turno di un giorno', fe_sostituzione)
prova('assenza con appuntamenti: elenco da spostare; periodi sbagliati', fe_assenza_da_spostare)


# =====================================================================
area('settimana, mese e prima disponibilita con oracolo')


def mondo_casuale(semenza, giorni=14):
    """Turni, assenze, chiusure e appuntamenti a caso su due settimane."""
    caso = random.Random(semenza)
    S, C = mondo()
    I = ids(S)
    s = S()
    stanze = [r for r in s.scalars(select(Risorsa)) if r.struttura_id == 1]
    medici = s.scalars(select(Operatore)).all()
    lunedi = calendario.lunedi_di(MAR) + timedelta(days=7 * (semenza % 5))
    for t in s.scalars(select(Turno)):
        s.delete(t)
    for _ in range(caso.randint(4, 9)):
        h = caso.randint(7, 15)
        t = Turno(operatore_id=caso.choice(medici).id, risorsa_id=caso.choice(stanze).id,
                  giorno_settimana=caso.randint(0, 5), ora_inizio=time(h, caso.choice([0, 30])),
                  ora_fine=time(min(h + caso.randint(2, 6), 23), 0), valido_da=date(2026, 1, 1))
        s.add(t)
    if caso.random() < 0.6:
        g = lunedi + timedelta(days=caso.randint(0, 13))
        s.add(Assenza(operatore_id=caso.choice(medici).id, dal=g, al=g + timedelta(days=caso.randint(0, 3)), motivo='Ferie'))
    if caso.random() < 0.3:
        g = lunedi + timedelta(days=caso.randint(0, 13))
        s.add(Chiusura(struttura_id=1, dal=g, al=g, motivo='Lavori'))
    s.commit()
    for _ in range(caso.randint(5, 25)):
        g = lunedi + timedelta(days=caso.randint(0, giorni - 1))
        i = datetime.combine(g, time(caso.randint(7, 18), caso.choice([0, 10, 15, 30, 45])))
        f = i + timedelta(minutes=caso.choice([15, 20, 30, 45, 60, 90]))
        r, o = caso.choice(stanze).id, caso.choice(medici).id
        stato = caso.choice(['PRENOTATO', 'CONFERMATO', 'ARRIVATO', 'DISDETTO', 'NON_PRESENTATO'])
        attivi = s.scalars(select(Appuntamento).where(Appuntamento.inizio < f, Appuntamento.fine > i,
                                                      Appuntamento.stato.in_(STATI_ATTIVI))).all()
        if stato in STATI_ATTIVI and any(a.risorsa_id == r or a.operatore_id == o for a in attivi):
            continue
        s.add(Appuntamento(risorsa_id=r, operatore_id=o, inizio=i, fine=f, stato=stato))
        s.commit()
    s.close()
    return S, C, lunedi


def oracolo_turni(p, g):
    """Turni che aprono le fasce il giorno g, letti dalle tabelle con SQL."""
    c = sqlite3.connect(p)
    turni = c.execute("SELECT t.operatore_id, t.risorsa_id, t.ora_inizio, t.ora_fine, t.valido_da, t.valido_a "
                      "FROM turni t JOIN risorse r ON r.id = t.risorsa_id WHERE r.struttura_id = 1 "
                      "AND t.giorno_settimana = ?", (g.weekday(),)).fetchall()
    assenti = {r[0] for r in c.execute("SELECT operatore_id FROM assenze WHERE dal <= ? AND al >= ?",
                                        (g.isoformat(), g.isoformat()))}
    chiusa = c.execute("SELECT COUNT(*) FROM chiusure WHERE struttura_id = 1 AND dal <= ? AND al >= ?",
                       (g.isoformat(), g.isoformat())).fetchone()[0] > 0
    c.close()
    if chiusa:
        return []
    uscita = []
    for o, r, da, a, vd, va in turni:
        if vd > g.isoformat() or (va and va < g.isoformat()) or o in assenti:
            continue
        uscita.append((o, r, time.fromisoformat(da[:8]), time.fromisoformat(a[:8])))
    return uscita


def oracolo_attivi(p, g):
    c = sqlite3.connect(p)
    righe_ = c.execute("SELECT a.id, a.risorsa_id, a.operatore_id, a.inizio, a.fine FROM appuntamenti a "
                       "JOIN risorse r ON r.id = a.risorsa_id WHERE r.struttura_id = 1 AND a.stato IN "
                       "('PRENOTATO','CONFERMATO','ARRIVATO') AND a.inizio >= ? AND a.inizio < ?",
                       (g.isoformat() + ' 00:00:00', (g + timedelta(days=1)).isoformat() + ' 00:00:00')).fetchall()
    c.close()
    return [(i, r, o, datetime.fromisoformat(da), datetime.fromisoformat(a)) for i, r, o, da, a in righe_]


def oracolo_libere(p, g, stanza, fasce_):
    """Fasce libere: coperte da un turno all'inizio e non coperte da un
    appuntamento attivo (dalla sua fascia di inizio a quella della fine)."""
    turni = [t for t in oracolo_turni(p, g) if t[1] == stanza]
    apps = [a for a in oracolo_attivi(p, g) if a[1] == stanza]
    libere = 0
    for k, f in enumerate(fasce_):
        inizio_f = datetime.combine(g, f)
        fine_f = inizio_f + timedelta(minutes=30)
        coperta = any(a[3] < fine_f and a[4] > inizio_f for a in apps)      # si sovrappone alla fascia
        if not coperta and any(da <= f < a for _, _, da, a in turni):
            libere += 1
    return libere


def se_oracolo():
    confronti = 0
    for semenza in range(12):
        S_, C_, lunedi = mondo_casuale(semenza)
        p = S_.motore.url.database
        s = S_()
        v = servizi.settimana(s, lunedi, 1)
        for riga in v['righe']:
            for c in riga['celle']:
                g, stanza = c['data'], riga['risorsa'].id
                attivi = [a for a in oracolo_attivi(p, g) if a[1] == stanza]
                assert c['occupate'] == len(attivi), 'semenza %d %s %s: %d app. invece di %d' % (
                    semenza, g, riga['risorsa'].nome, c['occupate'], len(attivi))
                attesi = sorted({t[0] for t in oracolo_turni(p, g) if t[1] == stanza})
                visti = sorted({t.operatore_id for t in c['turni']})
                assert visti == attesi, 'semenza %d %s: turni %s invece di %s' % (semenza, g, visti, attesi)
                fasce_ = servizi.griglia(s, g, 1)['fasce']
                if all(servizi._minuti(f) % 30 == 0 for f in fasce_):
                    atteso = oracolo_libere(p, g, stanza, fasce_)
                    assert c['libere'] == atteso, 'semenza %d %s %s: %d libere invece di %d' % (
                        semenza, g, riga['risorsa'].nome, c['libere'], atteso)
                confronti += 1
        s.close()
    return '%d caselle di 12 settimane casuali contro l oracolo' % confronti


def se_mese():
    for semenza in range(4):
        S_, C_, lunedi = mondo_casuale(100 + semenza)
        p = S_.motore.url.database
        s = S_()
        v = servizi.mese(s, lunedi.year, lunedi.month, 1)
        for g, d in v['giorni'].items():
            assert d['appuntamenti'] == len(oracolo_attivi(p, g)), '%s: %d invece di %d' % (
                g, d['appuntamenti'], len(oracolo_attivi(p, g)))
            assert d['info']['festivo'] == calendario.festivo(g), 'festivo del %s' % g
        s.close()
        r = C_.get('/mese/%04d-%02d' % (lunedi.year, lunedi.month))
        assert r.status_code == 200, 'pagina del mese: %d' % r.status_code


def se_medico():
    S_, C_, lunedi = mondo_casuale(7)
    p = S_.motore.url.database
    s = S_()
    for o in s.scalars(select(Operatore)):
        v = servizi.settimana_medico(s, lunedi, o.id, 1)
        visti = [a.id for riga in v['righe'] for c in riga['celle'] for a in c['apps']]
        attesi = [a[0] for k in range(7) for a in oracolo_attivi(p, lunedi + timedelta(days=k)) if a[2] == o.id]
        assert sorted(visti) == sorted(attesi), '%s: %s invece di %s' % (o.cognome, sorted(visti), sorted(attesi))
        assert len(visti) == len(set(visti)), 'un appuntamento compare due volte'
    s.close()
    assert C_.get('/settimana/%s?medico=1' % lunedi.isoformat()).status_code == 200


def oracolo_disponibilita(p, medico, durata, dal, giorni=20):
    """Tutti gli inizi validi, giorno per giorno, dal turno a passi di 30'."""
    trovati = []
    for n in range(giorni + 1):
        g = dal + timedelta(days=n)
        attivi = oracolo_attivi(p, g)
        for o, r, da, a in oracolo_turni(p, g):
            if o != medico:
                continue
            m = da.hour * 60 + da.minute
            while m + durata <= a.hour * 60 + a.minute:
                i = datetime.combine(g, time(m // 60, m % 60))
                f = i + timedelta(minutes=durata)
                if i > datetime.now() and not any(x[3] < f and x[4] > i and (x[1] == r or x[2] == medico)
                                                  for x in attivi):
                    trovati.append((i, r))
                m += 30
    return sorted(set(trovati))


def se_disponibilita():
    confronti = 0
    for semenza in range(10):
        S_, C_, lunedi = mondo_casuale(200 + semenza)
        p = S_.motore.url.database
        s = S_()
        for o in s.scalars(select(Operatore)):
            for durata in (20, 45):
                atteso = oracolo_disponibilita(p, o.id, durata, lunedi, giorni=13)
                visto = [(x['inizio'], x['risorsa'].id) for x in
                         servizi.disponibilita(s, o.id, durata, lunedi, 1, giorni=13, massimo=500)]
                assert visto == atteso, 'semenza %d %s %d\': %d posti invece di %d, primo diverso %s' % (
                    semenza, o.cognome, durata, len(visto), len(atteso),
                    next(((a, b) for a, b in zip(visto, atteso) if a != b), None))
                corti = [(x['inizio'], x['risorsa'].id) for x in
                         servizi.disponibilita(s, o.id, durata, lunedi, 1, giorni=13, massimo=5)]
                assert corti == atteso[:5], 'i primi 5 non sono i primi'
                confronti += 1
        s.close()
    return '%d ricerche su 10 mondi casuali uguali all oracolo' % confronti


def se_disponibilita_pagina():
    S_, C_ = mondo()
    I_ = ids(S_)
    t = html(C_.get('/disponibilita?medico=%d&prestazione=%d&dal=%s&fascia=pomeriggio' % (
        I_['Amato'], I_['Controllo'], MAR.isoformat())))
    assert 'Prenota' in t and '15:00' in t, 'nessun posto nel pomeriggio di Amato'
    t = html(C_.get('/disponibilita?medico=%d&dal=%s&fascia=mattina' % (I_['Amato'], MAR.isoformat())))
    assert 'Nessun posto libero' in t, 'Amato di mattina non lavora'
    for u in ('/disponibilita?medico=abc', '/disponibilita?medico=1&durata=-5', '/disponibilita?medico=1&dal=2099-99-99',
              '/disponibilita?medico=1&durata=999999'):
        assert C_.get(u).status_code == 200, u


def se_due_turni_stesso_giorno():
    """Due turni lo stesso giorno: i primi posti vanno presi in ordine di ora
    su entrambi, non tutti dal turno che comincia prima."""
    S_, C_ = mondo()
    I_ = ids(S_)
    s = S_()
    for x in s.scalars(select(Turno)):
        s.delete(x)
    s.add(Turno(operatore_id=I_['Galasso'], risorsa_id=I_['Ambulatorio 2'], giorno_settimana=MAR.weekday(),
                ora_inizio=time(7, 0), ora_fine=time(12, 0), valido_da=date(2026, 1, 1)))
    s.add(Turno(operatore_id=I_['Galasso'], risorsa_id=I_['Ambulatorio 1'], giorno_settimana=MAR.weekday(),
                ora_inizio=time(8, 0), ora_fine=time(10, 0), valido_da=date(2026, 1, 1)))
    s.commit()
    primi = [(x['inizio'].strftime('%H:%M'), x['risorsa'].nome) for x in
             servizi.disponibilita(s, I_['Galasso'], 30, MAR, 1, giorni=0, massimo=5)]
    s.close()
    attesi = [('07:00', 'Ambulatorio 2'), ('07:30', 'Ambulatorio 2'), ('08:00', 'Ambulatorio 1'),
              ('08:00', 'Ambulatorio 2'), ('08:30', 'Ambulatorio 1')]
    assert primi == attesi, 'primi cinque: %s' % primi


prova('prima disponibilita con due turni lo stesso giorno', se_due_turni_stesso_giorno)
prova('settimana per stanza contro l oracolo: appuntamenti, turni, fasce libere', se_oracolo)
prova('mese: appuntamenti e festivita di ogni giorno', se_mese)
prova('settimana di un medico: ogni appuntamento una volta', se_medico)
prova('prima disponibilita contro l oracolo su 10 mondi casuali', se_disponibilita)
prova('pagina prima disponibilita: mattina, pomeriggio, parametri sporchi', se_disponibilita_pagina)


# =====================================================================
area('statistiche con oracolo')


def sa_oracolo():
    for semenza in range(6):
        S_, C_, lunedi = mondo_casuale(300 + semenza)
        p = S_.motore.url.database
        dal, al = lunedi, lunedi + timedelta(days=13)
        s = S_()
        d = servizi.statistiche(s, 1, dal, al)
        s.close()
        capacita, prenotati = {}, {}
        g = dal
        while g <= al:
            for o, r, da, a in oracolo_turni(p, g):
                capacita[r] = capacita.get(r, 0) + (a.hour * 60 + a.minute) - (da.hour * 60 + da.minute)
            for _, r, o, i, f in oracolo_attivi(p, g):
                prenotati[r] = prenotati.get(r, 0) + int((f - i).total_seconds() // 60)
            g += timedelta(days=1)
        for x in d['per_stanza']:
            rid = x['risorsa'].id
            assert x['capacita'] == capacita.get(rid, 0), 'semenza %d %s: capacita %d invece di %d' % (
                semenza, x['risorsa'].nome, x['capacita'], capacita.get(rid, 0))
            assert x['prenotati'] == prenotati.get(rid, 0), 'semenza %d %s: prenotati %d invece di %d' % (
                semenza, x['risorsa'].nome, x['prenotati'], prenotati.get(rid, 0))
        c = sqlite3.connect(p)
        disdetti = c.execute("SELECT COUNT(*) FROM appuntamenti WHERE stato = 'DISDETTO' AND inizio >= ? AND inizio < ?",
                             (dal.isoformat(), (al + timedelta(days=1)).isoformat())).fetchone()[0]
        c.close()
        assert d['disdetti'] == disdetti, 'disdetti %d invece di %d' % (d['disdetti'], disdetti)
        c = sqlite3.connect(p)
        assenti = c.execute("SELECT COUNT(*) FROM appuntamenti a JOIN risorse r ON r.id = a.risorsa_id "
                            "WHERE r.struttura_id = 1 AND stato = 'NON_PRESENTATO' AND inizio >= ? AND inizio < ?",
                            (dal.isoformat(), (al + timedelta(days=1)).isoformat())).fetchone()[0]
        c.close()
        assert d['non_presentati'] == assenti == sum(m['assenti'] for m in d['per_medico']), \
            'non presentati: riepilogo %d, medici %d, oracolo %d' % (
                d['non_presentati'], sum(m['assenti'] for m in d['per_medico']), assenti)
        r = C_.get('/statistiche?dal=%s&al=%s' % (dal, al))
        assert r.status_code == 200, 'pagina statistiche'
        pagina = r.get_data(as_text=True)
        for x in d['per_stanza']:
            # ore con un decimale arrotondate a meta' per eccesso, calcolate a parte
            decimi = int(Decimal(x['prenotati']) / 6 + Decimal('0.5'))
            atteso = '<td>%d,%d</td>' % divmod(decimi, 10)
            assert atteso in pagina, 'semenza %d %s: %d minuti non mostrati come %s' % (
                semenza, x['risorsa'].nome, x['prenotati'], atteso)
        r = C_.get('/statistiche/excel?dal=%s&al=%s' % (dal, al))
        assert r.status_code == 200 and r.data[:2] == b'PK', 'export statistiche'
    return '6 mondi casuali: capacita, prenotati e disdetti uguali'


def sa_periodi():
    S_, C_ = mondo()
    for u in ('/statistiche?dal=2030-01-01&al=2020-01-01', '/statistiche?dal=abc&al=def',
              '/statistiche?dal=2000-01-01&al=2100-12-31', '/statistiche?struttura=99999'):
        r = C_.get(u)
        assert r.status_code == 200, '%s -> %d' % (u, r.status_code)


prova('saturazione, prenotati e disdetti contro l oracolo', sa_oracolo)
prova('periodi rovesciati, enormi o sbagliati', sa_periodi)


# =====================================================================
area('elenco, conferme, messaggi, stampa')
S, C = mondo()
I = ids(S)
P1 = crea_paz(cognome='ESPOSITO', nome='ANNA', telefono='333 1234567', email='anna@example.it')
P2 = crea_paz(cognome='Sorrentino', nome='Teresa', telefono='081 555 1234')
domani = date.today() + timedelta(days=1)
A1 = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], domani, 9, 0, paziente=P1, prest=I['Colonscopia'])
A2 = nuovo_app(S, I['Ambulatorio 2'], I['Lippiello'], domani, 9, 30, paziente=P2, stato='CONFERMATO')
A3 = nuovo_app(S, I['Ambulatorio 2'], I['Lippiello'], domani, 11, 0, paziente=P2, stato='DISDETTO')


def ec_messaggio():
    s = S()
    st = s.get(Struttura, 1)
    st.nome, st.indirizzo, st.telefono = 'Studio Esempio', 'Via Roma 1', '081 000 0000'
    s.get(Prestazione, I['Colonscopia']).preparazione = 'Dieta senza scorie'
    s.commit()
    a = s.get(Appuntamento, A1)
    testo = viste.testo_messaggio(a)
    st.indirizzo, st.telefono = '', ''
    s.get(Prestazione, I['Colonscopia']).preparazione = ''
    s.commit()
    corto = viste.testo_messaggio(s.get(Appuntamento, A1))
    senza_prest = viste.testo_messaggio(s.get(Appuntamento, A2))
    s.close()
    assert testo.startswith('Gentile Anna Esposito, le ricordiamo'), 'maiuscole non sistemate: %s' % testo
    assert 'presso Studio Esempio, Via Roma 1 (Colonscopia, Lippiello). Dieta senza scorie.' in testo, testo
    assert testo.endswith('chiami il 081 000 0000. Grazie.'), testo
    assert 'ci contatti' in corto and ', )' not in corto and '  ' not in corto and ' .' not in corto, corto
    assert '(Lippiello)' in senza_prest and '(,' not in senza_prest, senza_prest
    s = S()
    st = s.get(Struttura, 1)
    st.indirizzo, st.telefono = 'Via Roma 1', '081 000 0000'
    s.commit()
    s.close()


def ec_conferme():
    t = html(C.get('/conferme'))
    assert servizi.etichetta_giorno(domani) in t, 'la pagina non propone il prossimo giorno con appuntamenti'
    assert '/appuntamento/%d' % A1 in t and '/appuntamento/%d' % A2 in t, 'appuntamenti mancanti'
    assert '/appuntamento/%d"' % A3 not in t, 'un disdetto fra le conferme'
    assert t.index('/appuntamento/%d' % A1) < t.index('/appuntamento/%d' % A2), 'i da confermare non vengono prima'
    wa = re.search(r'href="(https://wa\.me/393331234567\?text=[^"]+)"', t)
    assert wa and 'Anna Esposito' in unquote(wa.group(1).replace('&amp;', '&')), 'collegamento WhatsApp mancante'
    assert 'wa.me/39081' not in t, 'WhatsApp proposto per un fisso'
    r = C.post('/appuntamento/%d/stato' % A1, data={'stato': 'CONFERMATO', 'torna': '/conferme?data=%s' % domani})
    assert r.headers['Location'].endswith('/conferme?data=%s' % domani), 'non torna alle conferme'
    avvisi(C)
    assert leggi_app(S, A1)['stato'] == 'CONFERMATO'


def ec_testo_personalizzato():
    r = C.post('/impostazioni', data={'azione': 'testo', 'testo': 'Ciao {paziente}, ci vediamo il {data} alle {ora}. {sconosciuto}',
                                      'oggetto': 'Appuntamento {data}'})
    assert r.status_code == 302, 'testo non salvato'
    avvisi(C)
    t = html(C.get('/conferme?data=%s' % domani))
    testo = unquote(re.search(r'wa\.me/393331234567\?text=([^"]+)"', t).group(1))
    assert testo == 'Ciao Anna Esposito, ci vediamo il %s alle 09:00. {sconosciuto}' % domani.strftime('%d/%m/%Y'), testo
    C.post('/impostazioni', data={'azione': 'testo_predefinito'})
    avvisi(C)
    t = html(C.get('/conferme?data=%s' % domani))
    assert 'le%20ricordiamo' in t, 'testo predefinito non ripristinato'
    r = C.post('/impostazioni', data={'azione': 'testo', 'testo': 'x' * 1001, 'oggetto': ''})
    assert 'Testo troppo lungo' in avvisi(C, r), 'testo lunghissimo accettato'


def ec_elenco():
    t = html(C.get('/giorno/%s/elenco' % domani.isoformat()))
    for aid in (A1, A2, A3):
        assert '/appuntamento/%d' % aid in t, 'manca %d nell elenco' % aid
    assert 'Non presentato' in t and 'Arrivato' in t, 'pulsanti di stato mancanti'
    conteggio = re.search(r'<span class="conteggio">([^<]+)</span>', t).group(1)
    s = S()
    attivi = sum(1 for aid in (A1, A2, A3) if s.get(Appuntamento, aid).attivo)
    disdetti = sum(1 for aid in (A1, A2, A3) if s.get(Appuntamento, aid).stato == 'DISDETTO')
    s.close()
    assert conteggio.startswith('%d appuntament' % attivi), 'conteggio con i disdetti: %s' % conteggio
    assert disdetti == 0 or '%d disdett' % disdetti in conteggio, conteggio


def ec_stampa():
    t = html(C.get('/stampa/%s' % domani.isoformat()))
    assert 'Ambulatorio 1' in t and 'ESPOSITO ANNA' in t, 'stampa senza appuntamenti'
    assert t.count('Sorrentino Teresa') == 1, 'il disdetto e stampato'
    assert 'Via Roma 1' in t, 'recapiti della struttura mancanti'
    t = html(C.get('/stampa/%s?tutti=1&per=ora' % domani.isoformat()))
    assert t.count('Sorrentino Teresa') == 2 and 'Disdetto' in t, 'con tutti=1 manca il disdetto'
    t = html(C.get('/appuntamento/%d/promemoria' % A1))
    assert 'Promemoria appuntamento' in t and 'ESPOSITO ANNA' in t and '081 000 0000' in t, 'promemoria incompleto'
    assert C.get('/appuntamento/999999/promemoria').status_code == 404


def ec_export():
    import openpyxl
    r = C.get('/esporta/%s' % domani.isoformat())
    wb = openpyxl.load_workbook(io.BytesIO(r.data))
    assert wb.active.title == domani.strftime('%d-%m-%Y'), 'il foglio attivo non e piu il planning'
    ws = wb['Elenco']
    intest = [c.value for c in ws[1]]
    assert intest[:6] == ['ORA', 'FINE', 'STANZA', 'MEDICO', 'PAZIENTE', 'TELEFONO'], intest
    righe_ = list(ws.iter_rows(min_row=2, values_only=True))
    assert len(righe_) == 3, 'righe nell elenco: %d' % len(righe_)
    stati = sorted(r[11] for r in righe_)
    assert stati == ['Confermato', 'Confermato', 'Disdetto'], stati


prova('messaggio di promemoria: maiuscole, recapiti, parti vuote', ec_messaggio)
prova('conferme: prossimo giorno, ordine, WhatsApp solo ai cellulari', ec_conferme)
prova('testo dei messaggi personalizzato e ripristinato', ec_testo_personalizzato)
prova('elenco del giorno con tutti gli stati', ec_elenco)
prova('stampa del giorno e promemoria per il paziente', ec_stampa)
prova('Excel: planning come prima, piu il foglio Elenco', ec_export)


# =====================================================================
area('orari e dati della struttura')
S, C = mondo()
I = ids(S)


def or_passo_15():
    s = S()
    st = s.get(Struttura, 1)
    st.ora_apertura, st.ora_chiusura, st.passo = time(7, 30), time(13, 0), 15
    s.commit()
    v = servizi.griglia(s, MAR, 1)
    fasce_ = [f.strftime('%H:%M') for f in v['fasce']]
    s.close()
    assert fasce_[0] == '07:30' and fasce_[-1] == '12:45' and len(fasce_) == 22, fasce_[:3] + fasce_[-3:]
    nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], MAR, 6, 50, minuti=20)
    nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], MAR, 13, 10, minuti=50)
    s = S()
    v = servizi.griglia(s, MAR, 1)
    fasce_ = [f.strftime('%H:%M') for f in v['fasce']]
    visti = [a.id for c in v['colonne'] for x in c['celle'] if x['stato'] == 'occupata' for a in x['apps']]
    s.close()
    assert fasce_[0] == '06:45' and fasce_[-1] == '13:45', 'fasce allargate: %s ... %s' % (fasce_[0], fasce_[-1])
    assert len(visti) == 2, 'appuntamenti fuori orario non visibili'
    passi = {servizi._minuti(time.fromisoformat(b)) - servizi._minuti(time.fromisoformat(a))
             for a, b in zip(fasce_, fasce_[1:])}
    assert passi == {15}, 'passo non costante: %s' % passi


def or_passo_20_allineato():
    # database a parte, senza collegarlo all'applicazione: le prove seguenti
    # usano ancora quello dell'area
    S = crea_sessione('sqlite:///' + percorso_nuovo())
    s0 = S()
    servizi.prepara_primo_avvio(s0)
    s0.close()
    s = S()
    st = s.get(Struttura, 1)
    st.ora_apertura, st.ora_chiusura, st.passo = time(8, 10), time(12, 0), 20
    s.commit()
    v = servizi.griglia(s, MAR, 1)
    fasce_ = [f.strftime('%H:%M') for f in v['fasce']]
    s.close()
    assert fasce_[0] == '08:10' and fasce_[-1] == '11:50', fasce_
    assert all((servizi._minuti(time.fromisoformat(f)) - 490) % 20 == 0 for f in fasce_), 'fasce non allineate all apertura'


def or_modulo():
    base = {'nome': 'La mia struttura', 'societa': '', 'colore': '#154381', 'sezione_orario': '1',
            'indirizzo': 'Via Toledo 1', 'telefono': '081 1', 'email': 'a@b.it', 'ora_apertura': '07:00',
            'ora_chiusura': '15:00', 'passo': '20', 'patrono': '19/09', 'giorno_0': '1', 'giorno_2': '1',
            'chiusa_festivi': '1'}
    r = C.post('/anagrafiche/strutture/1', data=base)
    assert r.status_code == 302, avvisi(C)
    avvisi(C)
    s = S()
    st = s.get(Struttura, 1)
    esito = (st.indirizzo, st.apertura, st.chiusura, st.passo, st.giorni_apertura, st.chiusa_festivi, st.patrono)
    s.close()
    assert esito == ('Via Toledo 1', time(7, 0), time(15, 0), 20, '1010000', True, '19/09'), esito
    # modulo parziale (senza la sezione): nulla si azzera, nemmeno le caselle
    C.post('/anagrafiche/strutture/1', data={'nome': 'Rinominata'})
    avvisi(C)
    s = S()
    st = s.get(Struttura, 1)
    esito2 = (st.nome, st.indirizzo, st.giorni_apertura, st.chiusa_festivi, st.passo)
    s.close()
    assert esito2 == ('Rinominata', 'Via Toledo 1', '1010000', True, 20), esito2
    for campo, valore, frammento in [('ora_chiusura', '06:00', 'dopo l\'apertura'),
                                     ('passo', '7', 'Durata di una fascia: scelta non valida'),
                                     ('patrono', '31/02', 'Festa del patrono'),
                                     ('email', 'no', 'Email: indirizzo non valido')]:
        r = C.post('/anagrafiche/strutture/1', data=dict(base, **{campo: valore}))
        assert r.status_code == 200 and frammento in avvisi(C, r), '%s=%s accettato' % (campo, valore)
    d = {k: v for k, v in base.items() if not k.startswith('giorno_')}
    r = C.post('/anagrafiche/strutture/1', data=d)
    assert r.status_code == 200 and 'almeno uno' in avvisi(C, r), 'nessun giorno di apertura accettato'


def or_settimana_giorni():
    s = S()
    st = s.get(Struttura, 1)
    st.giorni_apertura = '1111100'
    st.ora_apertura, st.ora_chiusura, st.passo = time(8, 0), time(20, 0), 30
    s.commit()
    v = servizi.settimana(s, calendario.lunedi_di(MAR), 1)
    giorni = [g.weekday() for g in v['giorni']]
    s.close()
    assert giorni == [0, 1, 2, 3, 4], 'giorni mostrati: %s' % giorni
    nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], calendario.lunedi_di(MAR) + timedelta(days=6), 10, 0)
    s = S()
    v = servizi.settimana(s, calendario.lunedi_di(MAR), 1)
    giorni = [g.weekday() for g in v['giorni']]
    s.close()
    assert 6 in giorni, 'la domenica con un appuntamento non compare'


prova('fasce da 15 minuti dalle 7:30, allargate per gli appuntamenti fuori orario', or_passo_15)
prova('fasce da 20 minuti allineate a un apertura alle 8:10', or_passo_20_allineato)
prova('modulo: salvataggio, modulo parziale che non azzera, errori', or_modulo)
prova('settimana: giorni di apertura piu quelli con appuntamenti', or_settimana_giorni)


# =====================================================================
area('backup e ripristino')


def bk_copia():
    S_, C_ = mondo()
    p = S_.motore.url.database
    cartella = os.path.join(PROVVISORIA, 'bk_copia')
    f = backup.esegui(p, cartella)
    assert backup.NOME.match(os.path.basename(f)), 'nome inatteso: %s' % f
    assert righe(f, 'PRAGMA integrity_check') == [('ok',)], 'copia non integra'
    assert righe(f, 'SELECT COUNT(*) FROM risorse') == righe(p, 'SELECT COUNT(*) FROM risorse'), 'copia diversa'
    assert backup.fatto_oggi(cartella), 'la copia di oggi non risulta'
    assert not [x for x in os.listdir(cartella) if x.endswith('.parziale')], 'file parziale rimasto'
    open(os.path.join(cartella, 'appunti.txt'), 'w').write('x')
    assert [c['nome'] for c in backup.elenco(cartella)] == [os.path.basename(f)], 'elenco con file estranei'


def bk_rotazione():
    oggi = datetime(2027, 6, 15, 10, 0)
    copie = []
    for k in range(400):
        q = oggi - timedelta(days=k)
        copie.append({'nome': 'agende-%s.db' % q.strftime('%Y-%m-%d_%H%M%S'), 'quando': q, 'motivo': ''})
    copie.append({'nome': 'agende-2020-01-01_000000-prima-del-ripristino.db', 'quando': datetime(2020, 1, 1),
                  'motivo': 'prima-del-ripristino'})
    tenute = backup.da_tenere(copie)
    giornaliere = {c['nome'] for c in copie[:30]}
    assert giornaliere <= tenute, 'perse copie degli ultimi 30 giorni'
    mensili = {}
    for c in copie[:400]:
        mensili[(c['quando'].year, c['quando'].month)] = c['nome']     # l'ultima vista e' la piu' vecchia
    attese = {mensili[k] for k in sorted(mensili, reverse=True)[:12]}
    assert attese <= tenute, 'manca la prima copia di qualche mese'
    assert 'agende-2020-01-01_000000-prima-del-ripristino.db' in tenute, 'copia di sicurezza eliminata'
    assert len(tenute) <= 30 + 12 + 1, 'tenute troppe copie: %d' % len(tenute)
    cartella = os.path.join(PROVVISORIA, 'bk_rot')
    os.makedirs(cartella)
    for c in copie[:60]:
        open(os.path.join(cartella, c['nome']), 'w').write('x')
    attese_disco = backup.da_tenere(backup.elenco(cartella))
    backup.ruota(cartella)
    rimasti = set(os.listdir(cartella))
    assert rimasti == attese_disco and len(rimasti) < 60, 'la rotazione su disco non segue da_tenere: %d' % len(rimasti)
    return '%d tenute su %d' % (len(tenute), len(copie))


def bk_ripristino():
    S_, C_ = mondo()
    I_ = ids(S_)
    p = S_.motore.url.database
    prima = nuovo_app(S_, I_['Ambulatorio 1'], I_['Lippiello'], MAR, 9, 0)
    C_.post('/impostazioni', data={'azione': 'backup_ora'})
    assert 'Backup fatto' in avvisi(C_), 'backup dalla pagina non riuscito'
    dopo = nuovo_app(S_, I_['Ambulatorio 1'], I_['Lippiello'], MAR, 10, 0)
    cartella = backup.cartella_predefinita(p)
    copia = [c for c in backup.elenco(cartella) if not c['motivo']][0]
    r = C_.post('/impostazioni/ripristina', data={'nome': copia['nome']})
    assert 'va spuntata la conferma' in avvisi(C_), 'ripristino senza conferma'
    r = C_.post('/impostazioni/ripristina', data={'nome': copia['nome'], 'conferma': '1'})
    assert 'Ripristinata la copia' in avvisi(C_), 'ripristino non riuscito'
    assert leggi_app(S_, prima) is not None and leggi_app(S_, dopo) is None, 'il ripristino non riporta indietro'
    sicurezza = [c for c in backup.elenco(cartella) if c['motivo'] == 'prima-del-ripristino']
    assert sicurezza and righe(sicurezza[0]['percorso'], 'SELECT COUNT(*) FROM appuntamenti WHERE id = %d' % dopo) == [(1,)], \
        'la copia di sicurezza non contiene il database di prima'
    assert C_.get('/giorno/%s' % MAR.isoformat()).status_code == 200, 'griglia dopo il ripristino'
    for cattivo in ('../agende.db', 'agende-2027-01-01_000000.db', '/etc/passwd'):
        C_.post('/impostazioni/ripristina', data={'nome': cattivo, 'conferma': '1'})
        assert 'non' in avvisi(C_), 'nome %r accettato' % cattivo
        assert C_.get('/impostazioni/backup/' + cattivo.replace('/', '%2F')).status_code == 404, 'scaricato %r' % cattivo


def bk_ripristino_vecchio():
    """Una copia della 1.2 rimessa al suo posto viene aggiornata subito."""
    S_, C_ = mondo()
    p = S_.motore.url.database
    cartella = backup.cartella_predefinita(p)
    os.makedirs(cartella, exist_ok=True)
    vecchio = database_v12()
    nome = 'agende-2026-01-01_120000.db'
    shutil.copy(vecchio, os.path.join(cartella, nome))
    r = C_.post('/impostazioni/ripristina', data={'nome': nome, 'conferma': '1'})
    assert 'Ripristinata' in avvisi(C_), 'ripristino della copia vecchia non riuscito'
    colonne = {r_[1] for r_ in righe(p, 'PRAGMA table_info(pazienti)')}
    assert {'email', 'codice_fiscale'} <= colonne, 'schema non aggiornato dopo il ripristino'
    assert righe(p, "SELECT valore FROM impostazioni WHERE chiave = 'versione_schema'") == [(str(VERSIONE_SCHEMA),)]
    assert C_.get('/giorno/%s' % MAR.isoformat()).status_code == 200


def bk_non_valido():
    cartella = os.path.join(PROVVISORIA, 'bk_rotto')
    os.makedirs(cartella)
    finto = os.path.join(cartella, 'agende-2027-01-01_000000.db')
    open(finto, 'wb').write(b'SQLite format 3\x00' + b'\x00' * 200)
    S_, C_ = mondo()
    try:
        backup.ripristina(S_.motore.url.database, finto, S_.motore, cartella)
        assert False, 'ripristinato un file rovinato'
    except Exception as e:
        assert 'ripristinato' not in str(e), str(e)
    assert righe(S_.motore.url.database, 'SELECT COUNT(*) FROM risorse') == [(6,)], 'database toccato'


def bk_allarme():
    salvato = dict(backup.stato)
    try:
        backup.stato.update(ultimo_ok=None, ultimo_errore=None, errore_il=None)
        assert backup.allarme() is None, 'allarme prima del primo giro'
        backup.stato.update(ultimo_ok=datetime.now() - timedelta(days=4))
        assert 'giorni fa' in backup.allarme(), 'copia vecchia non segnalata'
        backup.stato.update(ultimo_errore='cartella irraggiungibile', errore_il=datetime.now())
        assert 'Backup non riuscito' in backup.allarme(), 'errore non segnalato'
        S_, C_ = mondo()
        assert 'Backup non riuscito' in html(C_.get('/giorno/%s' % MAR.isoformat())), 'allarme non in griglia'
        backup.stato.update(ultimo_ok=datetime.now(), ultimo_errore=None, errore_il=None)
        assert backup.allarme() is None, 'allarme dopo una copia riuscita'
    finally:
        backup.stato.update(salvato)


def bk_cartella():
    S_, C_ = mondo()
    # una cartella che non si puo' creare, su Linux e su Windows: sotto un file che esiste
    # (su Windows /proc diventerebbe C:\proc, che si puo' creare, e resterebbe sul disco)
    file_non_cartella = os.path.join(PROVVISORIA, 'bk_file')
    open(file_non_cartella, 'w').close()
    C_.post('/impostazioni', data={'azione': 'cartella', 'cartella': os.path.join(file_non_cartella, 'sotto')})
    assert 'non si riesce a scrivere' in avvisi(C_), 'cartella non scrivibile accettata'
    nuova = os.path.join(PROVVISORIA, 'bk_scelta')
    C_.post('/impostazioni', data={'azione': 'cartella', 'cartella': nuova})
    assert 'salvata' in avvisi(C_)
    C_.post('/impostazioni', data={'azione': 'backup_ora'})
    avvisi(C_)
    assert backup.elenco(nuova), 'il backup non va nella cartella scelta'
    assert viste.cartella_backup() == nuova, 'la cartella per il thread non e quella scelta'
    t = html(C_.get('/impostazioni'))
    assert nuova in t, 'pagina senza la cartella scelta'


prova('copia verificata, nome, elenco senza file estranei', bk_copia)
prova('rotazione: 30 giornaliere, 12 mensili, copie di sicurezza tenute', bk_rotazione)
prova('ripristino dalla pagina, con conferma e copia di sicurezza', bk_ripristino)
prova('ripristino di una copia della 1.2: schema aggiornato', bk_ripristino_vecchio)
prova('file rovinato: ripristino rifiutato, database intatto', bk_non_valido)
prova('allarme in griglia: errore o copia vecchia', bk_allarme)
prova('cartella scelta: verifica di scrittura e uso', bk_cartella)


# =====================================================================
area('robustezza')


def ro_rotte():
    S_, C_ = mondo()
    caso = random.Random(13)
    veleni = ['', '0', '-1', 'abc', '9' * 25, '2027-13-40', '../../x', '<script>', '%00', 'A' * 300, '1e5']
    modelli_url = ['/settimana/%s', '/mese/%s', '/giorno/%s/elenco', '/conferme?data=%s', '/stampa/%s',
                   '/stampa/%s?per=%s&tutti=%s', '/disponibilita?medico=%s&durata=%s&dal=%s&fascia=%s',
                   '/statistiche?dal=%s&al=%s&struttura=%s', '/pazienti?q=%s', '/pazienti/cerca?q=%s',
                   '/pazienti/%s', '/pazienti/%s/unisci?altro=%s', '/appuntamento/%s/promemoria',
                   '/settimana/2027-03-02?medico=%s&struttura=%s', '/mese/2027-03?medico=%s',
                   '/anagrafiche/assenze/%s', '/anagrafiche/chiusure/%s', '/impostazioni/backup/%s',
                   '/appuntamento?paziente_id=%s&medico=%s&prestazione=%s&durata=%s']
    guasti = []
    for n in range(400):
        m = caso.choice(modelli_url)
        u = m % tuple(caso.choice(veleni) for _ in range(m.count('%s')))
        r = C_.get(u)
        if r.status_code >= 500:
            guasti.append('%s -> %d' % (u[:80], r.status_code))
    assert not guasti, guasti[:3]
    return '400 indirizzi con parametri sporchi, nessun errore interno'


def ro_moduli():
    S_, C_ = mondo()
    I_ = ids(S_)
    caso = random.Random(17)
    veleni = ['', ' ', '0', '-1', 'abc', '9' * 25, '<script>x</script>', "'; DROP TABLE pazienti; --",
              'A' * 500, '\x00', '2027-02-30', '25:61', '1.2.3', '€', 'àèìòù']
    guasti = []
    for n in range(300):
        tipo = caso.random()
        if tipo < 0.4:
            campi = ['cognome', 'nome', 'telefono', 'telefono2', 'email', 'codice_fiscale', 'data_nascita',
                     'canale', 'promemoria', 'note', 'doppione_confermato']
            dati = {k: caso.choice(veleni + ['Rossi', '3331234567', 'a@b.it', '1980-01-01', 'SMS'])
                    for k in campi if caso.random() < 0.8}
            r = C_.post('/pazienti/nuovo', data=dati)
        elif tipo < 0.7:
            campi = ['operatore', 'dal', 'al', 'motivo']
            dati = {k: caso.choice(veleni + [str(I_['Lippiello']), '2027-03-02', 'Ferie']) for k in campi}
            r = C_.post('/anagrafiche/assenze/nuova', data=dati)
        else:
            dati = {k: caso.choice(veleni + [str(I_['Ambulatorio 1']), str(I_['Lippiello']), str(I_['Controllo']),
                                             '2027-03-02', '09:00', '30', 'PRENOTATO', '80,00'])
                    for k in ['risorsa', 'operatore', 'prestazione', 'data', 'ora', 'durata', 'paziente',
                              'telefono', 'email_paziente', 'tipo', 'convenzione', 'importo', 'paziente_id']}
            dati['struttura'] = '1'
            r = C_.post('/appuntamento', data=dati)
        if r.status_code >= 500:
            guasti.append('modulo %d -> %d' % (n, r.status_code))
    s = S_()
    for p in s.scalars(select(Paziente)):
        if not (p.cognome or '').strip():
            guasti.append('paziente senza cognome')
        if p.codice_fiscale and not PZ.codice_fiscale_valido(p.codice_fiscale):
            guasti.append('codice fiscale non valido salvato: %r' % p.codice_fiscale)
        if p.email and not PZ.email_valida(p.email):
            guasti.append('email non valida salvata: %r' % p.email)
    for x in s.scalars(select(Assenza)):
        if x.al < x.dal:
            guasti.append('assenza al rovescio')
    attivi = s.scalars(select(Appuntamento).where(Appuntamento.stato.in_(STATI_ATTIVI))).all()
    for a in attivi:
        for b in attivi:
            if a.id < b.id and a.risorsa_id == b.risorsa_id and a.inizio < b.fine and b.inizio < a.fine:
                guasti.append('sovrapposti %d e %d' % (a.id, b.id))
    s.close()
    assert not guasti, sorted(set(guasti))[:4]
    return '300 moduli sporchi: pazienti, assenze e appuntamenti sempre coerenti'


def ro_stati_casuali():
    """Cambi di stato e prenotazioni a caso: mai due appuntamenti attivi
    sovrapposti nella stessa stanza, ora di arrivo solo per gli arrivati."""
    S_, C_ = mondo()
    I_ = ids(S_)
    caso = random.Random(23)
    stanze = [I_['Ambulatorio 1'], I_['Ambulatorio 2']]
    medici = [I_['Lippiello'], I_['Galasso'], I_['Amato']]
    guasti = []
    for n in range(250):
        s = S_()
        tutti = [a.id for a in s.scalars(select(Appuntamento))]
        s.close()
        if tutti and caso.random() < 0.55:
            aid = caso.choice(tutti)
            r = C_.post('/appuntamento/%d/stato' % aid, data={
                'stato': caso.choice(['PRENOTATO', 'CONFERMATO', 'ARRIVATO', 'NON_PRESENTATO', 'DISDETTO'])})
        else:
            ora = '%02d:%02d' % (caso.randint(8, 12), caso.choice([0, 15, 30, 45]))
            r = prenota(C_, I_, caso.choice(stanze), caso.choice(medici), I_['Controllo'], MAR, ora,
                        durata=str(caso.choice([15, 30, 45])), paziente='P%d' % n)
        if r.status_code >= 500:
            guasti.append('HTTP %d' % r.status_code)
        avvisi(C_)
    s = S_()
    attivi = s.scalars(select(Appuntamento).where(Appuntamento.stato.in_(STATI_ATTIVI))).all()
    for a in attivi:
        for b in attivi:
            if a.id < b.id and (a.risorsa_id == b.risorsa_id or a.operatore_id == b.operatore_id) \
                    and a.inizio < b.fine and b.inizio < a.fine:
                guasti.append('sovrapposti %d e %d' % (a.id, b.id))
    for a in s.scalars(select(Appuntamento)):
        if (a.arrivato_alle is not None) != (a.stato == 'ARRIVATO'):
            guasti.append('ora di arrivo incoerente per %d (%s)' % (a.id, a.stato))
    n_stati = s.scalar(select(func.count()).select_from(Modifica).where(Modifica.azione == 'STATO'))
    s.close()
    assert not guasti, guasti[:4]
    return '250 azioni, %d cambi di stato registrati, nessuna sovrapposizione' % n_stati


def ro_parallelo():
    """Quattro persone disdicono e riprenotano la stessa fascia insieme."""
    S_, C_ = mondo()
    I_ = ids(S_)
    aid = nuovo_app(S_, I_['Ambulatorio 1'], I_['Lippiello'], MAR, 9, 0, stato='DISDETTO')
    barriera = threading.Barrier(4)
    errori = []

    def lavora(k):
        c = A.app.test_client()
        barriera.wait()
        try:
            if k % 2:
                r = c.post('/appuntamento/%d/stato' % aid, data={'stato': 'PRENOTATO'})
            else:
                r = prenota(c, I_, I_['Ambulatorio 1'], I_['Lippiello'], I_['Controllo'], MAR, '09:00',
                            durata='30', paziente='Parallelo%d' % k)
            if r.status_code >= 500:
                errori.append(r.status_code)
        except Exception as e:
            errori.append(repr(e)[:80])
    fili = [threading.Thread(target=lavora, args=(k,)) for k in range(4)]
    for f in fili:
        f.start()
    for f in fili:
        f.join()
    s = S_()
    attivi = s.scalar(select(func.count()).select_from(Appuntamento).where(
        Appuntamento.risorsa_id == I_['Ambulatorio 1'], Appuntamento.inizio == datetime.combine(MAR, time(9, 0)),
        Appuntamento.stato.in_(STATI_ATTIVI)))
    s.close()
    assert not errori, errori
    assert attivi == 1, 'dopo le corse la fascia ha %d appuntamenti attivi' % attivi


prova('400 indirizzi nuovi con parametri sporchi', ro_rotte)
prova('300 moduli sporchi con invarianti sui dati', ro_moduli)
prova('250 cambi di stato e prenotazioni a caso', ro_stati_casuali)
prova('corsa fra riattivazione e nuova prenotazione', ro_parallelo)


# =====================================================================
ordine = []
for e in esiti:
    if e[1] not in ordine:
        ordine.append(e[1])
print()
for ar in ordine:
    gruppo = [e for e in esiti if e[1] == ar]
    rotti = [e for e in gruppo if e[0] != 'OK']
    print('%-46s %3d prove  %s' % (ar, len(gruppo), 'tutte a posto' if not rotti else '%d DA SISTEMARE' % len(rotti)))
guasti = [e for e in esiti if e[0] != 'OK']
if guasti:
    print('\nDettaglio:')
    for stato, ar, nome, msg in guasti:
        print('  %-6s [%s] %s\n         %s' % (stato, ar, nome, msg))
if os.environ.get('DETTAGLIO'):
    print('\nNote delle prove superate:')
    for stato, ar, nome, msg in esiti:
        if stato == 'OK' and msg:
            print('  [%s] %s: %s' % (ar, nome, msg))
print('\n%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(guasti), len(guasti)))
A._registro = None
shutil.rmtree(PROVVISORIA, ignore_errors=True)
