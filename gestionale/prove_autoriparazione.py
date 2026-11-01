# -*- coding: utf-8 -*-
"""Prove dell'autoriparazione (1.11): ogni guasto si crea apposta e si
controlla che il programma lo ripari da solo, senza perdere dati.

- il controllo del database: integro, mancante, vuoto, rovinato in testa,
  in un indice, in una tabella, occupato da un altro programma;
- la riparazione all'avvio: copia di sicurezza rimessa, ricostruzione senza
  perdite, recupero parziale, giornale lasciato da un programma chiuso a
  meta' scrittura (che non e' un guasto), avanzi di lavori interrotti;
- la riparazione a programma aperto (il custode), con i salvataggi fermi, e
  i lavori in sottofondo che ripartono;
- un gestionale solo: il secondo clic apre la pagina, un gestionale bloccato
  si chiude e si riparte, uno che sta partendo si aspetta, un programma che
  non e' il nostro non si chiude mai, la porta occupata da un altro programma;
- le copie di sicurezza quando la cartella scelta non si raggiunge;
- il registro che non cresce per sempre, la pagina, le notifiche, il diario.

I processi «altro gestionale» delle prove sono piccoli programmi Python
lanciati qui: nessuna prova tocca il gestionale vero o la porta 5000."""
import json
import logging
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time as orologio
import traceback
from datetime import date, datetime, timedelta

CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = tempfile.mkdtemp(prefix='prove_autoripara_')
# il programma mette il suo database in LOCALAPPDATA: qui, mai quello vero
os.environ['LOCALAPPDATA'] = os.path.join(PROVVISORIA, 'localappdata')
sys.path.insert(0, CARTELLA)

from sqlalchemy import select, func  # noqa: E402
from werkzeug.exceptions import InternalServerError  # noqa: E402

import app as A  # noqa: E402
import autoripara  # noqa: E402
import backup  # noqa: E402
import servizi  # noqa: E402
from modelli import crea_sessione, Paziente, Operatore, Risorsa, Appuntamento  # noqa: E402

A.app.config['TESTING'] = True
esiti, _area, _n = [], [''], [0]
SOLO = [x for x in os.environ.get('PROVE_SOLO', '').split(',') if x]
FIGLI = []


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


def cartella_nuova(nome='c'):
    _n[0] += 1
    c = os.path.join(PROVVISORIA, '%s_%d' % (nome, _n[0]))
    os.makedirs(c)
    return c


# ================================================================ i dati
COGNOMI = ['Fintini', 'Esempietti', 'Provolo', 'Testabianca', 'Fittizi', 'Esempio']


def database_con_dati(cartella, pazienti=1500, appuntamenti=300):
    """Un database del gestionale con dati inventati: tante righe, cosi' le
    tabelle occupano molte pagine. Restituisce il percorso."""
    percorso = os.path.join(cartella, 'agende.db')
    S = crea_sessione('sqlite:///' + percorso)
    s = S()
    servizi.prepara_primo_avvio(s)
    medico = Operatore(cognome='Provolo', nome='Anna')
    s.add(medico)
    s.flush()
    stanza = s.scalars(select(Risorsa)).first()
    for i in range(pazienti):
        s.add(Paziente(cognome='%s%d' % (COGNOMI[i % len(COGNOMI)], i), nome='Prova',
                       telefono='333%07d' % i, note='nota di prova numero %d ' % i * 3))
    s.flush()
    inizio = datetime(2026, 1, 5, 8, 0)
    for i in range(appuntamenti):
        g = inizio + timedelta(days=i // 20, minutes=30 * (i % 20))
        s.add(Appuntamento(risorsa_id=stanza.id, operatore_id=medico.id, paziente_id=i + 1, inizio=g,
                           fine=g + timedelta(minutes=30), note='appuntamento %d' % i))
    s.commit()
    s.close()
    S.motore.dispose()
    return percorso


def conta(percorso, tabella):
    c = sqlite3.connect(percorso)
    try:
        return c.execute('SELECT COUNT(*) FROM %s' % tabella).fetchone()[0]
    finally:
        c.close()


def aggiungi_pazienti(percorso, n, cognome='Dopolacopia'):
    c = sqlite3.connect(percorso)
    try:
        for i in range(n):
            c.execute("INSERT INTO pazienti (cognome, nome) VALUES (?, 'Prova')", ('%s%d' % (cognome, i),))
        c.commit()
    finally:
        c.close()


def pagine(percorso, nome):
    """Le pagine di una tabella o di un indice: con dbstat (se SQLite ce l'ha)
    tutte, foglie per prime; altrimenti solo la radice."""
    c = sqlite3.connect(percorso)
    try:
        try:
            righe = c.execute("SELECT pageno, pagetype FROM dbstat WHERE name = ? ORDER BY pagetype = 'leaf' DESC, "
                              "pageno", (nome,)).fetchall()
            if righe:
                return [r[0] for r in righe]
        except sqlite3.Error:
            pass
        return [c.execute('SELECT rootpage FROM sqlite_master WHERE name = ?', (nome,)).fetchone()[0]]
    finally:
        c.close()


def rovina_pagina(percorso, pagina):
    c = sqlite3.connect(percorso)
    misura = c.execute('PRAGMA page_size').fetchone()[0]
    c.close()
    with open(percorso, 'r+b') as f:
        f.seek((pagina - 1) * misura)
        f.write(b'\xA5' * misura)


def foglia_in_mezzo(percorso, nome):
    """Una pagina foglia nel mezzo della tabella (con dbstat), altrimenti la radice."""
    tutte = pagine(percorso, nome)
    return tutte[len(tutte) // 2] if len(tutte) > 2 else tutte[0]


def indice_di(percorso, tabella):
    c = sqlite3.connect(percorso)
    try:
        return c.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = ? "
                         "AND sql IS NOT NULL ORDER BY name", (tabella,)).fetchone()[0]
    finally:
        c.close()


def copia_fatta(percorso, giorni_fa=1, motivo=''):
    """Una copia di sicurezza vera (backup.esegui), con la data spostata
    indietro nel nome: come quella automatica di ieri."""
    cartella = backup.cartella_predefinita(percorso)
    finale = backup.esegui(percorso, cartella, motivo)
    quando = datetime.now() - timedelta(days=giorni_fa)
    nome = 'agende-%s%s.db' % (quando.strftime('%Y-%m-%d_%H%M%S'), ('-' + motivo) if motivo else '')
    os.replace(finale, os.path.join(cartella, nome))
    return os.path.join(cartella, nome)


def client_su(percorso):
    S = crea_sessione('sqlite:///' + percorso)
    A.Sessione = S
    A._registro = None
    import viste
    viste._sessionmaker = lambda: S
    return S, A.app.test_client()


def eventi_qui(cartella):
    return autoripara.eventi(cartella=cartella)


# ===================================================== controllo del database
area('controllo del database')


def c_integro():
    p = database_con_dati(cartella_nuova('integro'), 50, 10)
    assert autoripara.controlla_database(p) == ('ok', ''), autoripara.controlla_database(p)
    assert autoripara.controlla_database(p, completo=True)[0] == 'ok'


def c_mancante():
    p = os.path.join(cartella_nuova('mancante'), 'agende.db')
    assert autoripara.controlla_database(p)[0] == 'mancante'
    assert not os.path.exists(p), 'il controllo ha creato il file'


def c_vuoto():
    c = cartella_nuova('vuoto')
    p = os.path.join(c, 'agende.db')
    open(p, 'wb').close()
    assert autoripara.controlla_database(p)[0] == 'vuoto'
    q = os.path.join(c, 'senza_tabelle.db')
    sqlite3.connect(q).execute('PRAGMA user_version = 1').connection.commit()
    assert autoripara.controlla_database(q)[0] == 'vuoto', autoripara.controlla_database(q)


def c_testa():
    p = os.path.join(cartella_nuova('testa'), 'agende.db')
    with open(p, 'wb') as f:
        f.write(b'questo non e\' un database ' * 300)
    esito, dettaglio = autoripara.controlla_database(p)
    assert esito == 'danneggiato' and 'non è un database' in dettaglio, (esito, dettaglio)


def c_indice():
    p = database_con_dati(cartella_nuova('indice'), 400, 300)
    rovina_pagina(p, pagine(p, indice_di(p, 'appuntamenti'))[0])
    assert autoripara.controlla_database(p)[0] == 'danneggiato', autoripara.controlla_database(p)


def c_tabella():
    p = database_con_dati(cartella_nuova('tabella'))
    rovina_pagina(p, foglia_in_mezzo(p, 'pazienti'))
    assert autoripara.controlla_database(p)[0] == 'danneggiato', autoripara.controlla_database(p)


def c_occupato():
    """Un altro programma tiene il database bloccato (BACKUP.bat, un antivirus):
    non e' un guasto, non si ripara niente."""
    p = database_con_dati(cartella_nuova('occupato'), 20, 5)
    altro = sqlite3.connect(p, isolation_level=None)
    altro.execute('BEGIN EXCLUSIVE')
    try:
        esito, dettaglio = autoripara.controlla_database(p, attesa=0.3)
        assert esito == 'occupato', (esito, dettaglio)
        assert autoripara.ripara(p, esito=(esito, dettaglio)) is None, 'riparato un database solo occupato'
    finally:
        altro.execute('ROLLBACK')
        altro.close()
    assert not os.path.exists(os.path.join(os.path.dirname(p), 'backup', 'danneggiati')), 'messo da parte'


for nome, f in [('database integro', c_integro), ('database mancante: non si crea', c_mancante),
                ('file di zero byte o senza tabelle: vuoto', c_vuoto),
                ('testa rovinata: non è un database', c_testa), ('indice rovinato', c_indice),
                ('pagina dei dati rovinata', c_tabella), ('database occupato: non è un guasto', c_occupato)]:
    prova(nome, f)


# ===================================================== riparazione all'avvio
area('riparazione all\'avvio')


def r_vuoto():
    c = cartella_nuova('r_vuoto')
    p = database_con_dati(c, 200, 50)
    copia_fatta(p)
    with open(p, 'wb'):
        pass                                  # corrente saltata mentre scriveva: zero byte
    evento = autoripara.all_avvio(p)
    assert evento and 'era vuoto' in evento['testo'] and 'copia di sicurezza' in evento['testo'], evento
    assert conta(p, 'pazienti') == 200 and conta(p, 'appuntamenti') == 50, 'copia non rimessa'
    assert any('era vuoto' in e['testo'] for e in eventi_qui(c)), 'non scritto nel diario'
    S, C = client_su(p)
    assert C.get('/').status_code in (200, 302) and C.get('/pazienti?q=Fintini').status_code == 200
    S.motore.dispose()


def r_mancante():
    c = cartella_nuova('r_mancante')
    p = database_con_dati(c, 120, 30)
    copia_fatta(p)
    os.remove(p)
    evento = autoripara.all_avvio(p)
    assert evento and 'non c\'era' in evento['testo'], evento
    assert conta(p, 'pazienti') == 120, 'copia non rimessa'


def r_primo_avvio():
    c = cartella_nuova('r_primo')
    p = os.path.join(c, 'agende.db')
    assert autoripara.all_avvio(p) is None, 'al primo avvio non c\'e\' niente da riparare'
    assert not os.path.exists(p) and not eventi_qui(c), 'primo avvio toccato'
    S = crea_sessione('sqlite:///' + p)
    servizi.prepara_primo_avvio(S())
    S.motore.dispose()
    assert autoripara.controlla_database(p)[0] == 'ok'


def r_testa():
    c = cartella_nuova('r_testa')
    p = database_con_dati(c, 150, 40)
    copia_fatta(p)
    aggiungi_pazienti(p, 7)
    with open(p, 'r+b') as f:
        f.write(b'\x00' * 100)               # la testa del file cancellata
    rovinato = open(p, 'rb').read()
    evento = autoripara.all_avvio(p)
    assert evento and evento['livello'] == 'attenzione' and 'copia di sicurezza' in evento['testo'], evento
    assert conta(p, 'pazienti') == 150, 'non e\' la copia di sicurezza'
    parte = os.path.join(c, 'backup', 'danneggiati')
    messi = [x for x in os.listdir(parte) if x.startswith('danneggiato-') and x.endswith('.db')]
    assert len(messi) == 1 and open(os.path.join(parte, messi[0]), 'rb').read() == rovinato, \
        'il file danneggiato non e\' stato messo da parte identico'
    assert autoripara.controlla_database(p, completo=True)[0] == 'ok'


def r_indice():
    """Un indice rovinato si rifa' dai dati: niente si perde, nemmeno quello
    salvato dopo l'ultima copia."""
    c = cartella_nuova('r_indice')
    p = database_con_dati(c, 400, 300)
    copia_fatta(p)
    aggiungi_pazienti(p, 11)
    prima = (conta(p, 'pazienti'), conta(p, 'appuntamenti'))
    rovina_pagina(p, pagine(p, indice_di(p, 'appuntamenti'))[0])
    evento = autoripara.all_avvio(p)
    assert evento and evento['livello'] == 'ok' and 'senza perdere niente' in evento['testo'], evento
    assert (conta(p, 'pazienti'), conta(p, 'appuntamenti')) == prima, 'dati persi riparando un indice'
    assert autoripara.controlla_database(p, completo=True)[0] == 'ok'
    S, C = client_su(p)
    assert C.get('/pazienti?q=Dopolacopia').status_code == 200
    S.motore.dispose()


def r_tabella_con_copia():
    c = cartella_nuova('r_tabella')
    p = database_con_dati(c)
    copia_fatta(p)
    rovina_pagina(p, foglia_in_mezzo(p, 'pazienti'))
    evento = autoripara.all_avvio(p)
    assert evento and 'copia di sicurezza' in evento['testo'], evento
    assert conta(p, 'pazienti') == 1500 and autoripara.controlla_database(p, completo=True)[0] == 'ok'
    parte = os.path.join(c, 'backup', 'danneggiati')
    assert [x for x in os.listdir(parte) if x.startswith('recuperato-')], 'recupero parziale non messo da parte'


def r_tabella_senza_copia():
    """Senza copie si tiene quello che si legge: le altre tabelle intere."""
    c = cartella_nuova('r_senza')
    p = database_con_dati(c)
    rovina_pagina(p, foglia_in_mezzo(p, 'pazienti'))
    evento = autoripara.all_avvio(p)
    assert evento and evento['livello'] == 'errore' and 'recuperato' in evento['testo'], evento
    assert autoripara.controlla_database(p, completo=True)[0] == 'ok'
    assert conta(p, 'appuntamenti') == 300, 'perse righe di una tabella sana'
    n = conta(p, 'pazienti')
    assert n < 1500, 'nessuna riga persa? la pagina rovinata non era dei pazienti'
    S, C = client_su(p)
    assert C.get('/').status_code in (200, 302), 'il programma non riparte sul recupero'
    S.motore.dispose()
    return '%d pazienti su 1500 recuperati' % n


def r_giornale():
    """Il programma chiuso a meta' di un salvataggio lascia il giornale: SQLite
    rimette il database com'era. Non e' un guasto e non si tocca niente."""
    c = cartella_nuova('r_giornale')
    p = database_con_dati(c, 600, 50)
    codice = ('import sqlite3, os\n'
              'c = sqlite3.connect(%r)\n'
              'c.execute("PRAGMA cache_size = 5")\n'
              'c.execute("BEGIN")\n'
              'c.execute("UPDATE pazienti SET note = \'cambiata\' || note")\n'
              'c.execute("DELETE FROM appuntamenti")\n'
              'os._exit(0)\n' % p)
    subprocess.run([sys.executable, '-c', codice], check=False, timeout=60)
    assert os.path.exists(p + '-journal'), 'il giornale non e\' rimasto (la prova non prova niente)'
    assert autoripara.all_avvio(p) is None, 'un giornale normale trattato da guasto'
    assert conta(p, 'appuntamenti') == 50, 'il salvataggio a meta\' non e\' stato annullato'
    assert not os.path.exists(os.path.join(c, 'backup', 'danneggiati')), 'messo da parte un database sano'


def r_giornale_testa():
    """Corrente saltata mentre salvava: la testa del file scritta a meta', ma il
    giornale ha la copia buona. SQLite la rimette da solo: non e' un guasto."""
    c = cartella_nuova('r_testa_giornale')
    p = database_con_dati(c, 600, 50)
    copia_fatta(p)
    codice = ('import sqlite3, os\n'
              'c = sqlite3.connect(%r)\n'
              'c.execute("PRAGMA cache_size = 5")\n'
              'c.execute("BEGIN")\n'
              'c.execute("UPDATE pazienti SET note = \'cambiata\' || note")\n'
              'c.execute("DELETE FROM appuntamenti")\n'
              'os._exit(0)\n' % p)
    subprocess.run([sys.executable, '-c', codice], check=False, timeout=60)
    assert os.path.exists(p + '-journal'), 'il giornale non e\' rimasto'
    with open(p, 'r+b') as f:
        f.write(b'\x00' * 100)
    assert autoripara.all_avvio(p) is None, 'riparato (con una copia vecchia) quello che SQLite rimette da solo'
    assert conta(p, 'appuntamenti') == 50 and conta(p, 'pazienti') == 600
    assert not os.path.exists(os.path.join(c, 'backup', 'danneggiati'))


def r_scelta_copia():
    """Si rimette la copia piu' recente che passa il controllo; una «prima del
    ripristino» solo se non ce ne sono altre; una copia rovinata si salta."""
    c = cartella_nuova('r_scelta')
    p = database_con_dati(c, 30, 5)
    vecchia = copia_fatta(p, giorni_fa=3)
    aggiungi_pazienti(p, 1, 'Seconda')
    buona = copia_fatta(p, giorni_fa=2)
    aggiungi_pazienti(p, 1, 'Terza')
    rovinata = copia_fatta(p, giorni_fa=1)
    with open(rovinata, 'r+b') as f:
        f.write(b'\x00' * 100)
    copia_fatta(p, giorni_fa=0, motivo='prima-del-ripristino')
    scelta = autoripara.copia_buona([backup.cartella_predefinita(p)])
    assert scelta and scelta['percorso'] == buona, 'scelta %s invece di %s' % (scelta and scelta['nome'], buona)
    os.remove(buona)
    os.remove(vecchia)
    scelta = autoripara.copia_buona([backup.cartella_predefinita(p)])
    assert scelta and scelta['motivo'] == 'prima-del-ripristino', scelta


def r_cartella_ricordata():
    """Le copie solo nella cartella scelta (una chiavetta): se il database non
    si legge, la cartella si trova nel diario."""
    c = cartella_nuova('r_ricordata')
    p = database_con_dati(c, 40, 10)
    chiavetta = cartella_nuova('chiavetta')
    backup.esegui(p, chiavetta)
    autoripara.ricorda(c, cartella_backup=chiavetta)
    os.remove(p)
    evento = autoripara.all_avvio(p)
    assert evento and conta(p, 'pazienti') == 40, 'la copia della cartella scelta non e\' stata trovata'


def r_avanzi():
    c = cartella_nuova('r_avanzi')
    p = database_con_dati(c, 10, 2)
    copia = copia_fatta(p)
    cartella = backup.cartella_predefinita(p)
    open(os.path.join(cartella, 'agende-2026-01-01_120000.db.parziale'), 'w').close()
    os.makedirs(os.path.join(c, 'riparazione-2026-01-01_120000'))
    open(p + '.nuovo', 'w').close()
    assert autoripara.pulisci_avanzi(p) == 3
    assert os.path.exists(copia) and os.path.exists(p), 'cancellato quello che non andava toccato'
    assert not os.path.exists(p + '.nuovo')


def r_mai_ferma():
    """Un guasto nel controllo non ferma l'avvio: si scrive e si va avanti."""
    c = cartella_nuova('r_ferma')
    p = database_con_dati(c, 10, 2)
    vero = autoripara.controlla_database

    def rotto(*a, **k):
        raise RuntimeError('guasto inventato')
    autoripara.controlla_database = rotto
    try:
        autoripara.imposta_cartella(c)
        assert autoripara.all_avvio(p) is None
    finally:
        autoripara.controlla_database = vero
    assert any('non è riuscito' in e['testo'] for e in eventi_qui(c)), 'guasto non scritto nel diario'


for nome, f in [('file vuoto: rimessa l\'ultima copia', r_vuoto), ('file mancante: rimessa l\'ultima copia', r_mancante),
                ('primo avvio: niente da riparare', r_primo_avvio),
                ('testa rovinata: copia rimessa, file messo da parte identico', r_testa),
                ('indice rovinato: riparato senza perdere niente', r_indice),
                ('tabella rovinata con copia: copia rimessa e recupero da parte', r_tabella_con_copia),
                ('tabella rovinata senza copia: recupero di quello che si legge', r_tabella_senza_copia),
                ('giornale di un salvataggio interrotto: non è un guasto', r_giornale),
                ('testa scritta a metà con il giornale: la rimette SQLite', r_giornale_testa),
                ('scelta della copia da rimettere', r_scelta_copia),
                ('cartella dei backup ricordata nel diario', r_cartella_ricordata),
                ('avanzi di lavori interrotti', r_avanzi), ('un guasto nel controllo non ferma l\'avvio', r_mai_ferma)]:
    prova(nome, f)


# ===================================================== a programma aperto
area('a programma aperto (custode)')


def a_indice_dal_vivo():
    c = cartella_nuova('a_indice')
    p = database_con_dati(c, 400, 300)
    S, C = client_su(p)
    autoripara.imposta_cartella(c)
    assert C.get('/pazienti?q=Fintini').status_code == 200
    aggiungi_pazienti(p, 5)
    rovina_pagina(p, pagine(p, indice_di(p, 'appuntamenti'))[0])
    S.motore.dispose()
    note = autoripara.un_giro(p, S.motore, A.LUCCHETTO, dopo=A.dopo_riparazione, forza_db=True)
    assert any('senza perdere niente' in n['testo'] for n in note), note
    assert A.LUCCHETTO.acquire(blocking=False), 'il lucchetto dei salvataggi e\' rimasto preso'
    A.LUCCHETTO.release()
    assert conta(p, 'pazienti') == 405 and conta(p, 'appuntamenti') == 300, 'dati persi'
    assert C.get('/pazienti?q=Dopolacopia').status_code == 200, 'il programma non risponde dopo la riparazione'
    s = S()
    assert s.scalar(select(func.count()).select_from(Paziente)) == 405
    s.close()
    S.motore.dispose()


def a_testa_dal_vivo():
    """Il file non si legge piu' mentre il programma e' aperto: si rimette la
    copia sostituendo il file, e il programma continua con quella."""
    c = cartella_nuova('a_testa')
    p = database_con_dati(c, 80, 20)
    copia_fatta(p)
    S, C = client_su(p)
    autoripara.imposta_cartella(c)
    C.get('/')
    with open(p, 'r+b') as f:
        f.write(b'\x00' * 100)
    S.motore.dispose()
    esito, evento = autoripara.controlla_e_ripara(p, S.motore, A.LUCCHETTO, dopo=A.dopo_riparazione)
    assert esito == 'danneggiato' and evento and 'copia di sicurezza' in evento['testo'], (esito, evento)
    assert autoripara.stato['esito_db'] == 'ok'
    s = S()
    assert s.scalar(select(func.count()).select_from(Paziente)) == 80, 'il programma non legge la copia'
    s.close()
    assert C.get('/pazienti?q=Fintini').status_code == 200
    S.motore.dispose()


def a_riparazione_non_riuscita():
    """La riparazione a programma aperto non riesce (Windows non lascia
    sostituire un file aperto): lo dice, e all'avvio si ripara."""
    c = cartella_nuova('a_non_riesce')
    p = database_con_dati(c, 30, 5)
    copia_fatta(p)
    autoripara.imposta_cartella(c)
    with open(p, 'r+b') as f:
        f.write(b'\x00' * 100)
    vero = backup.metti_al_posto

    def rifiuta(*a, **k):
        raise PermissionError(32, 'Il file è utilizzato da un altro processo')
    backup.metti_al_posto = rifiuta
    try:
        esito, evento = autoripara.controlla_e_ripara(p, None, A.LUCCHETTO)
    finally:
        backup.metti_al_posto = vero
    assert evento and evento['livello'] == 'errore' and 'si ripara all\'avvio' in evento['testo'], evento
    assert any('chiudere e riaprire' in t for _, t in autoripara.problemi_attuali())
    assert A.LUCCHETTO.acquire(blocking=False), 'lucchetto rimasto preso'
    A.LUCCHETTO.release()
    assert autoripara.all_avvio(p) and conta(p, 'pazienti') == 30, 'all\'avvio non si e\' riparato'
    autoripara.stato.update(esito_db='ok')


def a_errore_malformed():
    """Un errore «malformed» in una pagina: pagina d'errore in parole semplici e
    controllo subito."""
    autoripara._sveglia.clear()
    with A.app.test_request_context('/'):
        r = A.errore_interno(InternalServerError(original_exception=sqlite3.DatabaseError(
            'database disk image is malformed')))
    assert r.status_code == 500 and 'Qualcosa non è andato' in r.get_data(as_text=True)
    assert autoripara._sveglia.is_set(), 'il controllo non e\' stato chiesto'
    autoripara._sveglia.clear()
    with A.app.test_request_context('/'):
        A.errore_interno(InternalServerError(original_exception=ValueError('altro')))
    assert not autoripara._sveglia.is_set(), 'controllo chiesto per un errore che non e\' del database'


def a_pagina_errore_vera():
    """Senza TESTING un errore dentro una pagina da' la spiegazione, non la
    pagina del server."""
    vera = A.app.view_functions['salute']

    def guasta():
        raise sqlite3.DatabaseError('file is not a database')
    A.app.view_functions['salute'] = guasta
    A.app.config.update(TESTING=False, PROPAGATE_EXCEPTIONS=False)
    vecchio = logging.getLogger().level
    logging.getLogger().setLevel(logging.CRITICAL)
    A.app.logger.disabled = True
    try:
        r = A.app.test_client().get('/salute')
        assert r.status_code == 500 and 'Controllo del programma' in r.get_data(as_text=True), r.status_code
        assert autoripara._sveglia.is_set()
    finally:
        A.app.logger.disabled = False
        logging.getLogger().setLevel(vecchio)
        A.app.view_functions['salute'] = vera
        A.app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=None)
        autoripara._sveglia.clear()


def a_lavori():
    c = cartella_nuova('a_lavori')
    autoripara.imposta_cartella(c)
    vivo = [threading.Thread(target=lambda: None)]
    vivo[0].start()
    vivo[0].join()                              # un lavoro morto

    def riavvia():
        t = threading.Thread(target=orologio.sleep, args=(5,), daemon=True)
        t.start()
        vivo[0] = t
        return t
    salvati = dict(autoripara._sorvegliati)
    autoripara._sorvegliati.clear()
    try:
        autoripara.sorveglia('invii', lambda: vivo[0], riavvia)
        assert autoripara.lavori()[0][2] is False and autoripara.problemi_attuali(), 'lavoro fermo non visto'
        note = autoripara.un_giro(None, None, A.LUCCHETTO)
        assert note and 'ripartito' in note[0]['testo'] and vivo[0].is_alive(), note
        assert autoripara.lavori()[0][2] is True and not autoripara.problemi_attuali()
        assert autoripara.un_giro(None, None, A.LUCCHETTO) == [], 'riavviato un lavoro vivo'

        def non_riparte():
            raise RuntimeError('niente')
        autoripara.sorveglia('backup', lambda: None, non_riparte)
        note = autoripara.un_giro(None, None, A.LUCCHETTO)
        assert note and note[0]['livello'] == 'errore', note
        assert any('fermo' in t for _, t in autoripara.problemi_attuali())
    finally:
        autoripara._sorvegliati.clear()
        autoripara._sorvegliati.update(salvati)


def a_spazio():
    vero = shutil.disk_usage

    class Poco:
        free = 120 * 1024 * 1024
    shutil.disk_usage = lambda c: Poco()
    try:
        assert autoripara.controlla_spazio(PROVVISORIA) == Poco.free
        problemi = autoripara.problemi_attuali()
        assert problemi and '120 MB' in problemi[0][1], problemi
        n = autoripara.notifiche(datetime.now(), '/autoriparazione')
        assert any(x['livello'] == 'errore' and '120 MB' in x['testo'] for x in n), n
    finally:
        shutil.disk_usage = vero
        autoripara.controlla_spazio(PROVVISORIA)


def a_ogni_mezzora():
    """Il custode non controlla il database a ogni giro: ogni mezz'ora, o subito
    se una pagina lo chiede."""
    c = cartella_nuova('a_mezzora')
    p = database_con_dati(c, 10, 2)
    vero, chiamate = autoripara.controlla_database, []

    def conta_chiamate(*a, **k):
        chiamate.append(1)
        return vero(*a, **k)
    autoripara.controlla_database = conta_chiamate
    try:
        adesso = datetime.now()
        autoripara.stato['controllo_db'] = adesso
        autoripara.un_giro(p, None, A.LUCCHETTO, adesso=adesso + timedelta(minutes=10))
        assert not chiamate, 'controllato prima della mezz\'ora'
        autoripara.un_giro(p, None, A.LUCCHETTO, adesso=adesso + timedelta(minutes=31))
        assert chiamate, 'non controllato dopo la mezz\'ora'
    finally:
        autoripara.controlla_database = vero


for nome, f in [('indice rovinato a programma aperto: riparato, salvataggi fermi', a_indice_dal_vivo),
                ('file illeggibile a programma aperto: copia rimessa', a_testa_dal_vivo),
                ('riparazione a programma aperto non riuscita: lo dice', a_riparazione_non_riuscita),
                ('errore «malformed»: controllo subito', a_errore_malformed),
                ('pagina d\'errore in parole semplici', a_pagina_errore_vera),
                ('lavori in sottofondo fermi: ripartono', a_lavori), ('poco spazio sul disco', a_spazio),
                ('controllo del database ogni mezz\'ora', a_ogni_mezzora)]:
    prova(nome, f)


# ===================================================== un gestionale solo
area('un gestionale solo')

FIGLIO = r'''
import json, os, socket, sys, time
sys.path.insert(0, %(cartella_codice)r)
import autoripara
cartella, modo, porta = %(cartella)r, %(modo)r, %(porta)d
f = autoripara.prendi_lucchetto(cartella)
if f is None:
    sys.exit(3)
autoripara.scrivi_pid(cartella, porta, 'avvio' if modo == 'partendo' else 'in servizio')
if modo == 'altro_pid':
    autoripara.scrivi_pid(cartella, porta, 'in servizio')
    dati = autoripara.leggi_pid(cartella); dati['pid'] = %(altro_pid)d
    open(os.path.join(cartella, 'gestionale.pid'), 'w').write(json.dumps(dati))
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
if modo != 'partendo':
    s.bind(('127.0.0.1', porta)); s.listen(5)
print('pronto', flush=True)
while True:
    if modo in ('partendo',):
        time.sleep(1); continue
    conn, _ = s.accept()
    if modo in ('bloccato', 'altro_pid'):
        continue                      # accetta e non risponde mai
    conn.recv(4096)
    corpo = json.dumps({'programma': 'Gestionale Agende', 'versione': 'prova', 'pid': os.getpid(),
                        'bloccato': modo == 'fili_fermi'}).encode()
    conn.sendall(b'HTTP/1.0 200 OK\r\nContent-Type: application/json\r\nContent-Length: %%d\r\n\r\n' %% len(corpo) + corpo)
    conn.close()
'''


def porta_libera():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def figlio(cartella, modo, porta, altro_pid=0):
    codice = FIGLIO % dict(cartella_codice=CARTELLA, cartella=cartella, modo=modo, porta=porta, altro_pid=altro_pid)
    p = subprocess.Popen([sys.executable, '-c', codice], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    FIGLI.append(p)
    riga = p.stdout.readline()
    assert riga.strip() == 'pronto', 'il finto gestionale non parte: %s %s' % (riga, p.stderr.read()[:300])
    return p


def chiudi_figli():
    for p in FIGLI:
        if p.poll() is None:
            p.kill()
        try:
            p.wait(10)
        except subprocess.TimeoutExpired:
            pass
        for flusso in (p.stdout, p.stderr):
            if flusso:
                flusso.close()
    del FIGLI[:]


def lascia(ingresso):
    if ingresso.get('lucchetto'):
        ingresso['lucchetto'].close()


def u_primo():
    c = cartella_nuova('u_primo')
    porta = porta_libera()
    e = autoripara.entra(c, porta=porta, riserva=())
    try:
        assert e['principale'] and e['porta'] == porta and e['lucchetto'], e
        info = autoripara.leggi_pid(c)
        assert info['pid'] == os.getpid() and info['fase'] == 'avvio' and info['porta'] == porta, info
        altro = subprocess.run([sys.executable, '-c', 'import sys; sys.path.insert(0, %r); import autoripara; '
                                'sys.exit(0 if autoripara.prendi_lucchetto(%r) is None else 1)' % (CARTELLA, c)],
                               timeout=60)
        assert altro.returncode == 0, 'un altro processo ha preso il lucchetto del gestionale aperto'
    finally:
        lascia(e)
    f = autoripara.prendi_lucchetto(c)
    assert f is not None, 'lucchetto non rilasciato alla chiusura'
    f.close()


def u_gia_aperto():
    c, porta = cartella_nuova('u_aperto'), porta_libera()
    p = figlio(c, 'sano', porta)
    e = autoripara.entra(c, porta=5, riserva=(), attesa=3)
    assert not e['principale'] and e['porta'] == porta and e['nota'] == 'già aperto', e
    assert p.poll() is None, 'chiuso un gestionale che rispondeva'
    chiudi_figli()


def u_bloccato():
    c, porta = cartella_nuova('u_bloccato'), porta_libera()
    p = figlio(c, 'bloccato', porta)
    inizio = orologio.monotonic()
    e = autoripara.entra(c, porta=porta, riserva=(), attesa=1, tentativi=1)
    try:
        assert e['principale'] and e['nota'] == 'chiuso il gestionale bloccato', e
        assert p.wait(10) is not None, 'il gestionale bloccato e\' ancora vivo'
        assert e['porta'] == porta, 'la porta del gestionale chiuso non si e\' liberata'
        assert any('non rispondeva' in x['testo'] for x in eventi_qui(c)), 'non scritto nel diario'
        assert orologio.monotonic() - inizio < 30, 'troppo lento'
    finally:
        lascia(e)
        chiudi_figli()


def u_fili_fermi():
    """Risponde a /salute ma tutti i suoi fili sono fermi su una pagina: e'
    bloccato lo stesso."""
    c, porta = cartella_nuova('u_fili'), porta_libera()
    p = figlio(c, 'fili_fermi', porta)
    e = autoripara.entra(c, porta=porta, riserva=(), attesa=2, tentativi=1)
    try:
        assert e['principale'] and p.wait(10) is not None, e
    finally:
        lascia(e)
        chiudi_figli()


def u_partendo():
    c, porta = cartella_nuova('u_partendo'), porta_libera()
    p = figlio(c, 'partendo', porta)
    e = autoripara.entra(c, porta=porta, riserva=(), attesa=0.5, tentativi=1)
    assert not e['principale'] and e['nota'] == 'sta partendo' and p.poll() is None, e
    chiudi_figli()


def u_mai_un_altro():
    """Il lucchetto e' preso, il gestionale non risponde, ma il processo scritto
    nel file non e' il gestionale: non si chiude niente."""
    c, porta = cartella_nuova('u_altro'), porta_libera()
    estraneo = subprocess.Popen(['sleep', '120'] if os.name != 'nt' else ['ping', '-n', '120', '127.0.0.1'],
                                stdout=subprocess.DEVNULL)
    FIGLI.append(estraneo)
    p = figlio(c, 'altro_pid', porta, altro_pid=estraneo.pid)
    e = autoripara.entra(c, porta=porta, riserva=(), attesa=0.5, tentativi=1)
    try:
        assert not e['principale'] and e['nota'] == 'non risponde', e
        assert estraneo.poll() is None, 'chiuso un programma che non e\' il gestionale!'
        assert p.poll() is None
    finally:
        chiudi_figli()


def u_porta_occupata():
    c, porta, riserva = cartella_nuova('u_porta'), porta_libera(), porta_libera()
    altro = socket.socket()
    altro.bind(('127.0.0.1', porta))
    altro.listen(1)
    try:
        e = autoripara.entra(c, porta=porta, riserva=(riserva,))
        assert e['principale'] and e['porta'] == riserva, e
        assert any('occupata da un altro programma' in x['testo'] for x in eventi_qui(c))
        assert autoripara.leggi_pid(c)['porta'] == riserva
        lascia(e)
    finally:
        altro.close()


def u_salute():
    C = A.app.test_client()
    d = C.get('/salute').get_json()
    assert d['programma'] == autoripara.PROGRAMMA and d['pid'] == os.getpid() and d['bloccato'] is False, d
    vecchio = orologio.monotonic() - A.LENTA - 5
    for i in range(A.FILI - 1):
        A._in_corso[-1000 - i] = (vecchio, '/pagina-ferma')
    try:
        d = C.get('/salute').get_json()
        assert d['bloccato'] is True and d['lente'] == A.FILI - 1, d
    finally:
        for i in range(A.FILI - 1):
            A._in_corso.pop(-1000 - i, None)
    assert not [k for k in A._in_corso if k > 0], 'richieste finite rimaste fra quelle in corso'
    assert autoripara.salute(porta_libera(), 0.5) is None


for nome, f in [('nessun gestionale aperto: si parte', u_primo),
                ('gestionale già aperto che risponde: solo la pagina', u_gia_aperto),
                ('gestionale bloccato: chiuso e si riparte', u_bloccato),
                ('fili tutti fermi su una pagina: bloccato', u_fili_fermi),
                ('gestionale che sta partendo: si aspetta', u_partendo),
                ('un programma che non è il gestionale non si chiude mai', u_mai_un_altro),
                ('porta occupata da un altro programma: porta di riserva', u_porta_occupata),
                ('/salute', u_salute)]:
    prova(nome, f)
chiudi_figli()


# ===================================================== copie di sicurezza
area('copie di sicurezza')


def b_cartella_irraggiungibile():
    c = cartella_nuova('b_riserva')
    p = database_con_dati(c, 20, 5)
    salvato = dict(backup.stato)
    file_non_cartella = os.path.join(c, 'chiavetta-tolta')
    open(file_non_cartella, 'w').close()
    scelta = os.path.join(file_non_cartella, 'backup')     # non si puo' creare
    try:
        backup.stato.update(ultimo_ok=None, ultimo_errore=None, errore_il=None, riserva=None)
        dove = backup.copia_del_giorno(p, scelta)
        predefinita = backup.cartella_predefinita(p)
        assert dove == predefinita and len(backup.elenco(predefinita)) == 1, 'copia di riserva non fatta'
        assert backup.stato['riserva'] and 'non si raggiunge' in (backup.allarme() or ''), backup.allarme()
        orologio.sleep(1.1)                  # nomi diversi: le copie hanno l'ora al secondo
        backup.copia_del_giorno(p, scelta)
        assert len(backup.elenco(predefinita)) == 1, 'una copia in piu\' a ogni giro'
        tornata = cartella_nuova('b_tornata')
        assert backup.copia_del_giorno(p, tornata) == tornata and len(backup.elenco(tornata)) == 1
        assert backup.stato['riserva'] is None and backup.allarme() is None, backup.allarme()
    finally:
        backup.stato.clear()
        backup.stato.update(salvato)


def b_predefinita_non_va():
    c = cartella_nuova('b_predefinita')
    p = database_con_dati(c, 5, 1)
    salvato = dict(backup.stato)
    open(os.path.join(c, 'backup'), 'w').close()          # al posto della cartella c'e' un file
    try:
        try:
            backup.copia_del_giorno(p, backup.cartella_predefinita(p))
        except Exception:
            pass
        else:
            raise AssertionError('nessun errore con la cartella predefinita inservibile')
    finally:
        backup.stato.clear()
        backup.stato.update(salvato)


for nome, f in [('cartella scelta irraggiungibile: copia accanto al database', b_cartella_irraggiungibile),
                ('cartella predefinita inservibile: errore detto', b_predefinita_non_va)]:
    prova(nome, f)


# ===================================================== registro, pagina, diario
area('registro, pagina, notifiche, diario')


def g_registro():
    from logging.handlers import RotatingFileHandler
    percorso = A.prepara_registro()
    gestori = [h for h in logging.getLogger().handlers if isinstance(h, RotatingFileHandler)]
    assert gestori and gestori[0].maxBytes == 5 * 1024 * 1024 and gestori[0].backupCount == 3, gestori
    h = gestori[0]
    h.maxBytes = 2000
    try:
        for i in range(10):
            logging.warning('riga lunga %d %s', i, 'x' * 400)
        assert os.path.exists(percorso + '.1'), 'il registro non ha cambiato file'
        assert os.path.getsize(percorso) <= 2000 + 600
    finally:
        h.maxBytes = 5 * 1024 * 1024


def g_pagina():
    c = cartella_nuova('g_pagina')
    p = database_con_dati(c, 10, 2)
    S, C = client_su(p)
    autoripara.imposta_cartella(c)
    salvati = dict(autoripara._sorvegliati)
    autoripara._sorvegliati.clear()
    try:
        t = C.get('/autoriparazione').get_data(as_text=True)
        assert 'Tutto a posto' in t and 'finora non c\'è stato niente da riparare' in t, t[:300]
        autoripara.annota('Prova <script>alert(1)</script> riparata', 'ok')
        t = C.get('/autoriparazione').get_data(as_text=True)
        assert '&lt;script&gt;' in t and '<script>alert' not in t, 'testo del diario non protetto'
        r = C.post('/autoriparazione')
        assert r.status_code == 302
        t = C.get('/autoriparazione').get_data(as_text=True)
        assert 'il database è integro' in t and 'integro' in t, t[:500]
        assert 'Controllo del programma' in C.get('/impostazioni').get_data(as_text=True), 'manca il collegamento'
    finally:
        autoripara._sorvegliati.update(salvati)
        S.motore.dispose()


def g_notifiche():
    c = cartella_nuova('g_notifiche')
    p = database_con_dati(c, 10, 2)
    S, C = client_su(p)
    autoripara.imposta_cartella(c)
    autoripara.annota('Il database era danneggiato ed è stato riparato senza perdere niente (prova).', 'ok')
    prima = [x for x in C.get('/notifiche.json').get_json() if x['chiave'].startswith('autoripara-')]
    dopo = [x for x in C.get('/notifiche.json').get_json() if x['chiave'].startswith('autoripara-')]
    assert prima and prima == dopo and prima[0]['titolo'] == 'Riparato da solo', prima
    assert prima[0]['link'] == '/autoriparazione'
    vecchio = autoripara.leggi_diario(c)
    vecchio['eventi'][-1]['quando'] = (datetime.now() - timedelta(days=5)).isoformat(timespec='seconds')
    autoripara._scrivi_json(autoripara.percorso_diario(c), vecchio)
    assert not [x for x in C.get('/notifiche.json').get_json() if x['chiave'].startswith('autoripara-2')], \
        'notifica di una riparazione di cinque giorni fa'
    S.motore.dispose()


def g_diario():
    c = cartella_nuova('g_diario')
    with open(os.path.join(c, autoripara.FILE_DIARIO), 'w', encoding='utf-8') as f:
        f.write('{"eventi": [ scritto a meta')
    assert autoripara.leggi_diario(c)['eventi'] == []
    fili = [threading.Thread(target=lambda i=i: [autoripara.annota('evento %d-%d' % (i, k), cartella=c)
                                                for k in range(10)]) for i in range(8)]
    for t in fili:
        t.start()
    for t in fili:
        t.join()
    assert len(autoripara.leggi_diario(c)['eventi']) == 80, 'eventi persi scrivendo insieme'
    for k in range(150):
        autoripara.annota('altro %d' % k, cartella=c)
    d = autoripara.leggi_diario(c)
    assert len(d['eventi']) == autoripara.MASSIMO_EVENTI and d['eventi'][-1]['testo'] == 'altro 149'
    autoripara.ricorda(c, cartella_backup='X:\\copie')
    assert autoripara.leggi_diario(c)['cartella_backup'] == 'X:\\copie' and len(autoripara.leggi_diario(c)['eventi']) == 100
    assert not [x for x in os.listdir(c) if x.endswith('.tmp')], 'file provvisori rimasti'


for nome, f in [('registro che non cresce per sempre', g_registro), ('pagina Controllo del programma', g_pagina),
                ('notifiche delle riparazioni', g_notifiche), ('diario: rovinato, scritto insieme, limitato', g_diario)]:
    prova(nome, f)


# ===================================================== il programma intero
area('il programma intero (app.principale)')

AVVIO = r'''
import os, sys
sys.argv = ['app.py', '--avvio-automatico']        # niente browser
sys.path.insert(0, %(cartella_codice)r)
import autoripara
autoripara.PORTA = %(porta)d
autoripara.PORTE_DI_RISERVA = ()
import app
app.principale()
'''


def programma(localappdata, porta):
    """Il gestionale vero, come lo avvia l'icona, in un processo a parte."""
    ambiente = dict(os.environ, LOCALAPPDATA=localappdata)
    p = subprocess.Popen([sys.executable, '-c', AVVIO % dict(cartella_codice=CARTELLA, porta=porta)],
                         env=ambiente, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    FIGLI.append(p)
    return p


def risponde(porta, entro=60.0):
    fine = orologio.monotonic() + entro
    while orologio.monotonic() < fine:
        d = autoripara.salute(porta, 2)
        if d:
            return d
        orologio.sleep(0.3)
    return None


def e2e():
    """Come al PC della segreteria: l'icona cliccata due volte, il programma che
    si blocca e si riapre, il database rovinato fra una chiusura e l'altra."""
    base = cartella_nuova('e2e')
    dati = os.path.join(base, 'GestionaleAgende')
    porta = porta_libera()
    a = programma(base, porta)
    d = risponde(porta)
    assert d and d['pid'] == a.pid, 'il programma non parte: %s' % (a.poll() is not None and a.stderr.read()[-800:])
    info = autoripara.leggi_pid(dati)
    assert info['fase'] == 'in servizio' and info['pid'] == a.pid, info
    assert autoripara.leggi_diario(dati).get('ultimo_avvio'), 'avvio non ricordato nel diario'
    # secondo clic: apre solo la pagina e finisce subito
    b = programma(base, porta)
    assert b.wait(60) == 0 and a.poll() is None, 'il secondo clic ha fatto danni'
    passi = ['avvio, secondo clic']
    if os.name != 'nt':
        # il programma si blocca (fermato dal sistema): il clic dopo lo chiude e riparte
        import signal
        os.kill(a.pid, signal.SIGSTOP)
        c = programma(base, porta)
        # aspetta: 2 tentativi da 15 secondi prima di chiudere quello fermo
        d = risponde(porta, entro=120)
        assert d and d['pid'] == c.pid, 'il programma bloccato non e\' stato sostituito'
        assert a.wait(10) is not None, 'il programma bloccato e\' ancora vivo'
        assert any('non rispondeva' in x['testo'] for x in autoripara.eventi(cartella=dati))
        passi.append('programma bloccato sostituito')
        vivo = c
    else:
        vivo = a
    # si chiude il programma e si rovina un indice del database: alla riapertura si ripara
    vivo.kill()
    vivo.wait(10)
    pdb = os.path.join(dati, 'agende.db')
    aggiungi_pazienti(pdb, 300, 'Esempietti')
    n = conta(pdb, 'pazienti')
    rovina_pagina(pdb, pagine(pdb, 'ix_appuntamenti_inizio')[0])
    e = programma(base, porta)
    d = risponde(porta)
    assert d and d['pid'] == e.pid, 'non riparte sul database rovinato: %s' % (e.poll() is not None and e.stderr.read()[-800:])
    assert autoripara.controlla_database(pdb, completo=True)[0] == 'ok'
    eventi_ = [x['testo'] for x in autoripara.eventi(cartella=dati)]
    assert any('danneggiato' in t and 'senza perdere niente' in t for t in eventi_), eventi_
    assert conta(pdb, 'pazienti') == n, 'dati persi'
    passi.append('database rovinato riparato alla riapertura')
    # la pagina del programma vero mostra la riparazione
    import urllib.request
    pagina = urllib.request.urlopen('http://127.0.0.1:%d/autoriparazione' % porta, timeout=30).read().decode('utf-8')
    assert 'danneggiato' in pagina and 'Cosa ha fatto da solo' in pagina, pagina[:300]
    passi.append('pagina Controllo del programma')
    chiudi_figli()
    return ', '.join(passi)


prova('avvio, secondo clic, programma bloccato, database rovinato', e2e)
chiudi_figli()


# ===================================================== difetti trovati studiando i guasti
area('ripristino, copie, schema, avvio')


def d_schema_senza_riga():
    """Senza la riga 'versione_schema' (un recupero che l'ha persa) le
    migrazioni vecchie non si rifanno: i «Confermato» restano."""
    c = cartella_nuova('d_schema')
    p = database_con_dati(c, 20, 10)
    q = sqlite3.connect(p)
    q.execute("UPDATE appuntamenti SET stato = 'CONFERMATO'")
    q.execute("DELETE FROM impostazioni WHERE chiave = 'versione_schema'")
    q.commit()
    q.close()
    S = crea_sessione('sqlite:///' + p)
    S.motore.dispose()
    q = sqlite3.connect(p)
    confermati = q.execute("SELECT COUNT(*) FROM appuntamenti WHERE stato = 'CONFERMATO'").fetchone()[0]
    riga = q.execute("SELECT valore FROM impostazioni WHERE chiave = 'versione_schema'").fetchone()
    q.close()
    assert confermati == 10, 'migrazione vecchia rifatta: %d confermati su 10' % confermati
    assert S.versione_precedente == 11 and riga == ('11',), (S.versione_precedente, riga)


def d_ripristino_su_rovinato():
    """Il ripristino dalle impostazioni funziona anche quando il database
    attuale e' rovinato (prima si fermava: la sua copia non passava il controllo)."""
    c = cartella_nuova('d_ripristino')
    p = database_con_dati(c)
    copia = copia_fatta(p)
    S, C = client_su(p)
    rovina_pagina(p, foglia_in_mezzo(p, 'pazienti'))
    S.motore.dispose()
    r = C.post('/impostazioni/ripristina', data={'nome': os.path.basename(copia), 'conferma': '1'})
    t = C.get(r.headers['Location']).get_data(as_text=True)
    assert 'Ripristinata la copia' in t, t[t.find('avviso'):][:400]
    assert autoripara.controlla_database(p, completo=True)[0] == 'ok' and conta(p, 'pazienti') == 1500
    parte = os.path.join(c, 'backup', 'danneggiati')
    assert [x for x in os.listdir(parte) if x.startswith('danneggiato-')], 'il database rovinato non e\' da parte'
    S.motore.dispose()


def d_orologio_indietro():
    """Con l'orologio del PC indietro la copia appena fatta era la piu' vecchia
    e la rotazione la cancellava subito, ogni ora, senza dire niente."""
    c = cartella_nuova('d_orologio')
    p = database_con_dati(c, 5, 1)
    cartella = backup.cartella_predefinita(p)
    os.makedirs(cartella, exist_ok=True)
    # un anno e piu' di copie «del futuro» (l'orologio era avanti, o ora e' indietro):
    # la copia di oggi non e' fra le 30 piu' recenti ne' fra i 12 mesi piu' recenti
    futuro = datetime.now() + timedelta(days=430)
    modello = copia_fatta(p, 0)
    for i in range(43):
        g = futuro - timedelta(days=10 * i)
        shutil.copyfile(modello, os.path.join(cartella, 'agende-%s.db' % g.strftime('%Y-%m-%d_%H%M%S')))
    for x in backup.elenco(cartella):
        if x['quando'].date() <= date.today():
            os.remove(x['percorso'])
    salvato = dict(backup.stato)
    try:
        nuova = backup.esegui(p, cartella)
        assert os.path.exists(nuova), 'la copia appena fatta e\' stata cancellata dalla rotazione'
        assert 'orologio' in (backup.allarme() or ''), backup.allarme()
    finally:
        backup.stato.clear()
        backup.stato.update(salvato)


def d_parziale():
    """Una copia che non si scrive (disco pieno) non lascia il .parziale."""
    c = cartella_nuova('d_parziale')
    p = database_con_dati(c, 5, 1)
    vero = backup.sqlite3

    class Pieno:
        Error = sqlite3.Error
        DatabaseError = sqlite3.DatabaseError

        @staticmethod
        def connect(percorso, *a, **k):
            conn = sqlite3.connect(percorso, *a, **k)
            if not str(percorso).endswith('.parziale'):
                class Sorgente:
                    def backup(self, altra):
                        altra.execute('CREATE TABLE mezza (x)')
                        raise sqlite3.OperationalError('database or disk is full')

                    def close(self):
                        conn.close()
                return Sorgente()
            return conn
    backup.sqlite3 = Pieno
    salvato = dict(backup.stato)
    try:
        try:
            backup.esegui(p, os.path.join(c, 'copie'))
        except sqlite3.OperationalError:
            pass
        else:
            raise AssertionError('nessun errore col disco pieno')
    finally:
        backup.sqlite3 = vero
        backup.stato.clear()
        backup.stato.update(salvato)
    rimasti = [x for x in os.listdir(os.path.join(c, 'copie')) if x.endswith('.parziale')]
    assert not rimasti, 'rimasto %s' % rimasti


def d_copie_recenti():
    c = cartella_nuova('d_recenti')
    p = database_con_dati(c, 5, 1)
    cartella = backup.cartella_predefinita(p)
    copia_fatta(p, giorni_fa=0)
    vecchia = backup.elenco(cartella)[0]
    adesso = vecchia['quando'] + timedelta(hours=1)
    os.utime(p, (adesso.timestamp(), adesso.timestamp()))
    assert backup.copia_recente(p, cartella, adesso=adesso) is None, 'copia recente dopo un\'ora sola'
    adesso = vecchia['quando'] + timedelta(hours=3)
    assert backup.copia_recente(p, cartella, adesso=adesso), 'nessuna copia recente dopo tre ore di lavoro'
    # senza modifiche dopo l'ultima copia non se ne fa un'altra
    passato = datetime.now() - timedelta(hours=5)
    os.utime(p, (passato.timestamp(), passato.timestamp()))
    assert backup.copia_recente(p, cartella, adesso=datetime.now() + timedelta(hours=3)) is None
    for i in range(6):
        backup.esegui(p, cartella, backup.MOTIVO_RECENTE)
        orologio.sleep(1.05)
    recenti = [x for x in backup.elenco(cartella) if x['motivo'] == backup.MOTIVO_RECENTE]
    assert len(recenti) == backup.COPIE_RECENTI, 'copie recenti tenute: %d' % len(recenti)
    assert [x for x in backup.elenco(cartella) if not x['motivo']], 'la copia del giorno e\' sparita'
    assert autoripara.copia_buona([cartella])['motivo'] == backup.MOTIVO_RECENTE, 'non si rimette la piu\' recente'


def d_copie_due_cartelle():
    """Le copie della cartella accanto al database si vedono e si rimettono
    anche quando nelle impostazioni c'e' un'altra cartella."""
    c = cartella_nuova('d_due')
    p = database_con_dati(c, 15, 3)
    copia = copia_fatta(p)
    S, C = client_su(p)
    altrove = cartella_nuova('d_altrove')
    C.post('/impostazioni', data={'azione': 'cartella', 'cartella': altrove})
    t = C.get('/impostazioni').get_data(as_text=True)
    assert os.path.basename(copia) in t and 'nella cartella accanto al database' in t, 'copia nascosta'
    assert C.get('/impostazioni/backup/%s' % os.path.basename(copia)).status_code == 200
    r = C.post('/impostazioni/ripristina', data={'nome': os.path.basename(copia), 'conferma': '1'})
    assert 'Ripristinata la copia' in C.get(r.headers['Location']).get_data(as_text=True)
    assert autoripara.leggi_diario(c).get('cartella_backup') == altrove, 'cartella scelta non ricordata nel diario'
    S.motore.dispose()


def d_porta_non_utilizzabile():
    occupata, libera = socket.socket(), porta_libera()
    # come un altro server (waitress compreso): su Windows con SO_REUSEADDR un secondo
    # server poteva legarsi alla stessa porta invece di dare errore
    occupata.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    occupata.bind(('127.0.0.1', 0))
    occupata.listen(1)
    try:
        server, porta = A.crea_server(occupata.getsockname()[1], riserva=(libera,))
        server.close()
        assert porta == libera, porta
        try:
            A.crea_server(occupata.getsockname()[1], riserva=())
        except OSError:
            pass
        else:
            raise AssertionError('nessun errore senza porte di riserva')
    finally:
        occupata.close()


def d_pagine_errore():
    for errore, atteso in (('database or disk is full', 'disco del computer è pieno'),
                           ('database is locked', 'occupato da un altro programma'),
                           ('altro', 'Quello che era già salvato è al sicuro')):
        with A.app.test_request_context('/'):
            r = A.errore_interno(InternalServerError(original_exception=sqlite3.OperationalError(errore)))
        assert atteso in r.get_data(as_text=True), errore
    c = cartella_nuova('d_avvio')
    aperte = []
    vero = A.webbrowser.open
    A.webbrowser.open = lambda u, *a, **k: aperte.append(u)
    try:
        A.avvio_non_riuscito(os.path.join(c, 'gestionale.log'), RuntimeError('<guasto> inventato'))
    finally:
        A.webbrowser.open = vero
    pagina = open(os.path.join(c, 'avvio-non-riuscito.html'), encoding='utf-8').read()
    assert aperte and aperte[0].startswith('file:///') and '&lt;guasto&gt;' in pagina and 'non è partito' in pagina


def d_schema_piu_nuovo():
    autoripara.stato['schema_nuovo'] = 12
    try:
        assert any('versione più nuova' in t for _, t in autoripara.problemi_attuali())
    finally:
        autoripara.stato['schema_nuovo'] = None


for nome, f in [('database senza versione dello schema: niente migrazioni rifatte', d_schema_senza_riga),
                ('ripristino sopra un database rovinato', d_ripristino_su_rovinato),
                ('orologio del PC indietro: la copia nuova resta', d_orologio_indietro),
                ('copia non scritta: niente .parziale', d_parziale),
                ('copie recenti ogni due ore se il database cambia', d_copie_recenti),
                ('copie della cartella accanto al database visibili', d_copie_due_cartelle),
                ('porta non utilizzabile: la prossima', d_porta_non_utilizzabile),
                ('pagine d\'errore e avvio non riuscito', d_pagine_errore),
                ('database di una versione più nuova', d_schema_piu_nuovo)]:
    prova(nome, f)


# ===================================================== il riavvio da solo
area('il riavvio da solo')


def v_motivi():
    salvato = dict(autoripara._riavvio)
    try:
        autoripara.imposta_riavvio(['x'], risorse=lambda: True, ferme=lambda: [], fili=4)
        assert autoripara.motivo_per_riavviare() is None
        autoripara._riavvio['risorse'] = lambda: False
        assert 'file' in autoripara.motivo_per_riavviare()
        autoripara._riavvio['risorse'] = lambda: True
        autoripara._riavvio['ferme'] = lambda: [400, 400, 10]
        assert autoripara.motivo_per_riavviare() is None, 'riavvio con due pagine lente soltanto'
        autoripara._riavvio['ferme'] = lambda: [400, 400, 400]
        assert 'bloccato' in autoripara.motivo_per_riavviare()
        autoripara._riavvio['ferme'] = lambda: [31 * 60]
        assert 'bloccato' in autoripara.motivo_per_riavviare()
    finally:
        autoripara._riavvio.clear()
        autoripara._riavvio.update(salvato)


def v_riavvio():
    c = cartella_nuova('v_riavvio')
    autoripara.imposta_cartella(c)
    salvato = dict(autoripara._riavvio)
    lanciati, uscite = [], []
    f = autoripara.prendi_lucchetto(c)
    autoripara._istanza[0] = f
    try:
        assert autoripara.riavvia_programma('prova', lancia=lanciati.append, esci=uscite.append) is False, \
            'riavvio senza comando (le prove, il programma di prova)'
        autoripara.imposta_riavvio(['programma', '--avvio-automatico'], occupato=lambda: True)
        assert autoripara.riavvia_programma('prova', lancia=lanciati.append, esci=uscite.append) is False, \
            'riavvio durante un aggiornamento'
        autoripara._riavvio['occupato'] = lambda: False
        assert autoripara.riavvia_programma('era bloccato', lancia=lanciati.append, esci=uscite.append)
        assert lanciati == [['programma', '--avvio-automatico']] and uscite == [0], (lanciati, uscite)
        g = autoripara.prendi_lucchetto(c)
        assert g is not None, 'il lucchetto non e\' stato lasciato al programma che riparte'
        g.close()
        for _ in range(2):
            autoripara.riavvia_programma('era bloccato', lancia=lanciati.append, esci=uscite.append)
        assert len(lanciati) == 3
        assert autoripara.riavvia_programma('era bloccato', lancia=lanciati.append, esci=uscite.append) is False
        assert autoripara.riavvia_programma('era bloccato', lancia=lanciati.append, esci=uscite.append) is False
        troppi = [e for e in eventi_qui(c) if e.get('tipo') == 'troppi-riavvii']
        assert len(lanciati) == 3 and len(troppi) == 1, (len(lanciati), troppi)
    finally:
        autoripara._riavvio.clear()
        autoripara._riavvio.update(salvato)
        autoripara._istanza[0] = None
        if f:
            f.close()


RIAVVIO = r'''
import os, shutil, sys
sys.argv = ['app.py', '--avvio-automatico']
sys.path.insert(0, %(cartella_codice)r)
import autoripara
autoripara.OGNI_GIRO = 1
import app
copia = %(copia)r
shutil.copytree(app.app.template_folder, copia)
app.app.template_folder = copia
app.principale()
'''


def v_riavvio_vero():
    """Il programma vero perde i suoi file mentre e' aperto (la pulizia di
    Windows): si riavvia da solo e torna a rispondere sulla stessa porta."""
    if os.name == 'nt':
        return 'solo su Linux: su Windows lo prova strumenti/prove_installato.py'
    base = cartella_nuova('v_vero')
    dati = os.path.join(base, 'GestionaleAgende')
    porta = porta_libera()
    copia = os.path.join(base, 'modelli-temporanei')
    ambiente = dict(os.environ, LOCALAPPDATA=base, GESTIONALE_PORTA=str(porta))
    p = subprocess.Popen([sys.executable, '-c', RIAVVIO % dict(cartella_codice=CARTELLA, copia=copia)],
                         env=ambiente, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    FIGLI.append(p)
    nuovo = None
    try:
        d = risponde(porta)
        assert d and d['pid'] == p.pid, 'non parte: %s' % (p.poll() is not None and p.stderr.read()[-600:])
        shutil.rmtree(copia)                     # la pulizia di Windows
        assert p.wait(30) == 0, 'il programma senza file non si e\' chiuso'
        fine = orologio.monotonic() + 60
        while orologio.monotonic() < fine:
            d = autoripara.salute(porta, 2)
            if d and d['pid'] != p.pid:
                nuovo = d['pid']
                break
            orologio.sleep(0.3)
        assert nuovo, 'il programma non e\' ripartito'
        assert any(e.get('tipo') == 'riavvio' and 'file' in e['testo'] for e in autoripara.eventi(cartella=dati))
        import urllib.request
        assert urllib.request.urlopen('http://127.0.0.1:%d/oggi' % porta, timeout=30).status == 200
    finally:
        if nuovo:
            try:
                os.kill(nuovo, 9)
            except OSError:
                pass
        chiudi_figli()
    return 'ripartito con il processo %d' % nuovo


for nome, f in [('quando riavviarsi', v_motivi), ('riavvio: lucchetto lasciato, mai più di tre in un\'ora', v_riavvio),
                ('programma vero senza i suoi file: si riavvia da solo', v_riavvio_vero)]:
    prova(nome, f)
chiudi_figli()


# =====================================================================
if __name__ == '__main__':
    chiudi_figli()
    logging.shutdown()
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
