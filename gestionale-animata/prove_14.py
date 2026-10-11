# -*- coding: utf-8 -*-
"""Prove delle funzioni della 1.4: aggiornamento dalla 1.3, importazione da
Excel e CSV, chiusura della giornata, lista d'attesa, spostamenti, serie,
cassa e listino, documenti, moduli, provenienza, note del giorno, cose da
fare e notifiche, ricerca rapida, agenda del medico, robustezza.

Dove si puo' il risultato si confronta con un calcolo fatto a parte (un
oracolo) e non con quello che il programma stesso ha prodotto."""
import io
import json
import os
import random
import re
import shutil
import sqlite3
import sys
import traceback
from types import SimpleNamespace
from datetime import date, datetime, time, timedelta
from urllib.parse import unquote

from sqlalchemy import select, func

import servizi
import segreteria
import cassa
import documenti
import importa
import pazienti as PZ
import backup
import viste
import app as A
from modelli import (crea_sessione, Struttura, Risorsa, Operatore, Turno, Appuntamento, Prestazione,
                     Paziente, Attesa, Attivita, NotaGiorno, Documento, ModuloStampa, Tariffa, Assenza, Appunto,
                     STATI_ATTIVI, VERSIONE_SCHEMA, scrivi_impostazione)

A.app.config['TESTING'] = True
CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = os.path.join(CARTELLA, 'prove_14_tmp')
shutil.rmtree(PROVVISORIA, ignore_errors=True)
os.makedirs(PROVVISORIA)
esiti = []
_area = ['']
_n = [0]
OGGI = date.today()
# un martedi nel futuro, lontano dai festivi, e il giovedi dopo
MAR = OGGI + timedelta(days=(1 - OGGI.weekday()) % 7 + 14)
while servizi.calendario.festivo(MAR) or servizi.calendario.festivo(MAR + timedelta(days=2)):
    MAR += timedelta(days=7)
GIO = MAR + timedelta(days=2)
IERI = OGGI - timedelta(days=1)


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
    viste._sessionmaker = lambda: S
    return A.app.test_client()


def mondo():
    """Primo avvio piu' tre medici con turni il martedi, uno anche il giovedi."""
    S = crea_sessione('sqlite:///' + percorso_nuovo())
    s = S()
    servizi.prepara_primo_avvio(s)
    lip = Operatore(cognome='Lippiello', nome='Anna', colore='#154381', email='lippiello@example.it')
    gal = Operatore(cognome='Galasso', colore='#5B7F3E')
    amo = Operatore(cognome='Amato', colore='#A8582B')
    s.add_all([lip, gal, amo])
    s.flush()
    stanze = {r.nome: r for r in s.scalars(select(Risorsa))}
    ogni_giorno = date(2020, 1, 1)
    for g in range(7):
        s.add(Turno(operatore=lip, risorsa=stanze['Ambulatorio 1'], giorno_settimana=g,
                    ora_inizio=time(8, 0), ora_fine=time(14, 0), valido_da=ogni_giorno))
    s.add(Turno(operatore=gal, risorsa=stanze['Sala endoscopia'], giorno_settimana=1,
                ora_inizio=time(8, 0), ora_fine=time(13, 0), valido_da=ogni_giorno))
    s.add(Turno(operatore=amo, risorsa=stanze['Ambulatorio 3'], giorno_settimana=1,
                ora_inizio=time(15, 0), ora_fine=time(19, 0), valido_da=ogni_giorno))
    st = s.get(Struttura, 1)
    st.telefono, st.indirizzo = '081 123 4567', 'Via Posillipo 1'
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


def nuovo_app(S, stanza, medico, g, h, m, minuti=30, stato='PRENOTATO', paziente=None, prest=None, **altro):
    s = S()
    i = datetime.combine(g, time(h, m))
    a = Appuntamento(risorsa_id=stanza, operatore_id=medico, inizio=i, fine=i + timedelta(minutes=minuti),
                     stato=stato, paziente_id=paziente, prestazione_id=prest, **altro)
    s.add(a)
    s.commit()
    aid = a.id
    s.close()
    return aid


def crea_paz(S, **campi):
    s = S()
    p = Paziente(**campi)
    s.add(p)
    s.commit()
    pid = p.id
    s.close()
    return pid


def html(r):
    return r.get_data(as_text=True)


def avvisi(C, r=None):
    from html import unescape
    with C.session_transaction() as sess:
        m = sess.get('_flashes', [])
        sess['_flashes'] = []
    testo = ' '.join(str(x[1]) for x in m)
    if r is not None and r.status_code == 200:
        testo += ' ' + ' '.join(unescape(x) for x in re.findall(r'class="avviso[^"]*">(.*?)</div>', html(r)))
    return unescape(re.sub(r'<[^>]+>', '', testo))


def leggi(S, modello, ident):
    s = S()
    x = s.get(modello, ident)
    d = None if x is None else {c.name: getattr(x, c.name) for c in modello.__table__.columns
                                if c.name not in ('dati', 'logo')}
    s.close()
    return d


def conta(S, modello, *condizioni):
    s = S()
    n = s.scalar(select(func.count()).select_from(modello).where(*condizioni)) if condizioni else \
        s.scalar(select(func.count()).select_from(modello))
    s.close()
    return n


def righe(p, sql, *arg):
    c = sqlite3.connect(p)
    try:
        return c.execute(sql, arg).fetchall()
    finally:
        c.close()


SCHEMA_V13 = [
    """CREATE TABLE strutture (
	id INTEGER NOT NULL, 
	nome VARCHAR(80) NOT NULL, 
	attiva BOOLEAN NOT NULL, 
	societa VARCHAR(120), 
	colore VARCHAR(7), 
	logo BLOB, 
	logo_aggiornato DATETIME, 
	indirizzo VARCHAR(160), 
	telefono VARCHAR(40), 
	email VARCHAR(120), 
	ora_apertura TIME, 
	ora_chiusura TIME, 
	passo INTEGER, 
	giorni_apertura VARCHAR(7), 
	chiusa_festivi BOOLEAN, 
	patrono VARCHAR(5), 
	PRIMARY KEY (id), 
	UNIQUE (nome)
)""",
    """CREATE TABLE operatori (
	id INTEGER NOT NULL, 
	cognome VARCHAR(60) NOT NULL, 
	nome VARCHAR(60), 
	specialita VARCHAR(60), 
	colore VARCHAR(7), 
	attivo BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
)""",
    """CREATE TABLE prestazioni (
	id INTEGER NOT NULL, 
	nome VARCHAR(80) NOT NULL, 
	durata_min INTEGER NOT NULL, 
	campi_extra VARCHAR(200), 
	preparazione TEXT, 
	PRIMARY KEY (id), 
	UNIQUE (nome)
)""",
    """CREATE TABLE pazienti (
	id INTEGER NOT NULL, 
	cognome VARCHAR(60) NOT NULL, 
	nome VARCHAR(60), 
	telefono VARCHAR(30), 
	note TEXT, 
	telefono2 VARCHAR(30), 
	email VARCHAR(120), 
	data_nascita DATE, 
	codice_fiscale VARCHAR(16), 
	promemoria BOOLEAN, 
	canale VARCHAR(10), 
	creato_il DATETIME, 
	PRIMARY KEY (id)
)""",
    """CREATE TABLE impostazioni (
	chiave VARCHAR(60) NOT NULL, 
	valore TEXT, 
	PRIMARY KEY (chiave)
)""",
    """CREATE TABLE modifiche (
	id INTEGER NOT NULL, 
	quando DATETIME NOT NULL, 
	entita VARCHAR(40) NOT NULL, 
	entita_id INTEGER, 
	azione VARCHAR(20) NOT NULL, 
	dettaglio TEXT, 
	PRIMARY KEY (id)
)""",
    """CREATE TABLE risorse (
	id INTEGER NOT NULL, 
	nome VARCHAR(60) NOT NULL, 
	tipo VARCHAR(30) NOT NULL, 
	struttura_id INTEGER NOT NULL, 
	ordine INTEGER NOT NULL, 
	attiva BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (struttura_id, nome), 
	FOREIGN KEY(struttura_id) REFERENCES strutture (id)
)""",
    """CREATE TABLE assenze (
	id INTEGER NOT NULL, 
	operatore_id INTEGER NOT NULL, 
	dal DATE NOT NULL, 
	al DATE NOT NULL, 
	motivo VARCHAR(60), 
	PRIMARY KEY (id), 
	FOREIGN KEY(operatore_id) REFERENCES operatori (id)
)""",
    """CREATE TABLE chiusure (
	id INTEGER NOT NULL, 
	struttura_id INTEGER NOT NULL, 
	dal DATE NOT NULL, 
	al DATE NOT NULL, 
	motivo VARCHAR(80), 
	PRIMARY KEY (id), 
	FOREIGN KEY(struttura_id) REFERENCES strutture (id)
)""",
    """CREATE TABLE turni (
	id INTEGER NOT NULL, 
	operatore_id INTEGER NOT NULL, 
	risorsa_id INTEGER NOT NULL, 
	giorno_settimana INTEGER NOT NULL, 
	ora_inizio TIME NOT NULL, 
	ora_fine TIME NOT NULL, 
	valido_da DATE NOT NULL, 
	valido_a DATE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(operatore_id) REFERENCES operatori (id), 
	FOREIGN KEY(risorsa_id) REFERENCES risorse (id)
)""",
    """CREATE TABLE appuntamenti (
	id INTEGER NOT NULL, 
	risorsa_id INTEGER NOT NULL, 
	operatore_id INTEGER NOT NULL, 
	paziente_id INTEGER, 
	prestazione_id INTEGER, 
	inizio DATETIME NOT NULL, 
	fine DATETIME NOT NULL, 
	stato VARCHAR(20) NOT NULL, 
	note TEXT, 
	creato_il DATETIME, 
	modificato_il DATETIME, 
	tipo VARCHAR(20), 
	convenzione VARCHAR(80), 
	importo_cent INTEGER, 
	extra TEXT, 
	arrivato_alle DATETIME, 
	stato_il DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(risorsa_id) REFERENCES risorse (id), 
	FOREIGN KEY(operatore_id) REFERENCES operatori (id), 
	FOREIGN KEY(paziente_id) REFERENCES pazienti (id), 
	FOREIGN KEY(prestazione_id) REFERENCES prestazioni (id)
)""",
    """CREATE UNIQUE INDEX appuntamento_attivo_unico ON appuntamenti (risorsa_id, inizio) WHERE stato IN ('PRENOTATO', 'CONFERMATO', 'ARRIVATO')""",
    """CREATE INDEX ix_appuntamenti_inizio ON appuntamenti (inizio)""",
]


# =====================================================================
area('aggiornamento dalla 1.3')


def database_v13():
    """Un database come lo crea la 1.3, con dati dentro."""
    p = percorso_nuovo('v13')
    c = sqlite3.connect(p)
    for ddl in SCHEMA_V13:
        c.execute(ddl)
    c.execute("INSERT INTO impostazioni VALUES ('versione_schema', '3')")
    c.execute("INSERT INTO strutture (id, nome, attiva, societa, colore, telefono) VALUES (1, 'Clinica Posillipo', 1, 'Srl', '#154381', '081 1')")
    for i, nome in enumerate(['Ambulatorio 1', 'Sala endoscopia'], start=1):
        c.execute("INSERT INTO risorse (id, nome, tipo, struttura_id, ordine, attiva) VALUES (?, ?, 'AMBULATORIO', 1, ?, 1)", (i, nome, i))
    c.execute("INSERT INTO operatori (id, cognome, nome, specialita, colore, attivo) VALUES (1, 'Lippiello', '', '', '#154381', 1)")
    c.execute("INSERT INTO prestazioni (id, nome, durata_min, campi_extra, preparazione) VALUES (1, 'Visita', 30, 'Sedazione?', 'digiuno')")
    c.execute("INSERT INTO pazienti (id, cognome, nome, telefono, email, promemoria, canale, creato_il) VALUES (1, 'Esposito', 'Anna', '3331234567', 'a@b.it', 1, 'WHATSAPP', '2026-09-01 10:00:00.000000')")
    for k, stato in enumerate(['PRENOTATO', 'CONFERMATO', 'DISDETTO', 'ARRIVATO']):
        inizio = datetime.combine(MAR, time(9 + k, 0))
        c.execute("INSERT INTO appuntamenti (risorsa_id, operatore_id, paziente_id, prestazione_id, inizio, fine, stato, note, "
                  "tipo, convenzione, importo_cent, extra) VALUES (1, 1, 1, 1, ?, ?, ?, ?, 'CONTROLLO', 'Privato', 8000, ?)",
                  (inizio.strftime('%Y-%m-%d %H:%M:%S.000000'), (inizio + timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S.000000'),
                   stato, 'nota %d' % k, json.dumps({'Sedazione': 'Sì'})))
    c.commit()
    c.close()
    return p


def ag_da_13():
    p = database_v13()
    prima = righe(p, 'SELECT * FROM appuntamenti ORDER BY id')
    prima_paz = righe(p, 'SELECT * FROM pazienti ORDER BY id')
    S = crea_sessione('sqlite:///' + p)
    assert S.versione_precedente == 3, 'versione trovata %s' % S.versione_precedente
    assert righe(p, "SELECT valore FROM impostazioni WHERE chiave = 'versione_schema'") == [(str(VERSIONE_SCHEMA),)]
    dopo = righe(p, 'SELECT %s FROM appuntamenti ORDER BY id' % ', '.join(
        r[1] for r in righe(p, 'PRAGMA table_info(appuntamenti)')[:17]))
    assert prima == dopo, 'appuntamenti cambiati dall\'aggiornamento'
    assert righe(p, 'SELECT %s FROM pazienti ORDER BY id' % ', '.join(
        r[1] for r in righe(p, 'PRAGMA table_info(pazienti)')[:12])) == prima_paz, 'pazienti cambiati'
    tabelle = {r[0] for r in righe(p, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {'tariffe', 'lista_attesa', 'attivita', 'note_giorno', 'documenti', 'moduli'} <= tabelle, tabelle
    colonne = {r[1] for r in righe(p, 'PRAGMA table_info(appuntamenti)')}
    assert {'pagato_cent', 'pagamento', 'pagato_il', 'serie'} <= colonne, colonne
    assert {'provenienza', 'inviato_da'} <= {r[1] for r in righe(p, 'PRAGMA table_info(pazienti)')}
    assert {'email', 'telefono'} <= {r[1] for r in righe(p, 'PRAGMA table_info(operatori)')}
    assert righe(p, 'PRAGMA integrity_check') == [('ok',)]
    indici = {r[0] for r in righe(p, "SELECT name FROM sqlite_master WHERE type = 'index'")}
    assert 'appuntamento_attivo_unico' in indici, 'indice parziale perso'
    copie = [m for m in S.migrazioni if m.startswith('copia di sicurezza:')]
    assert copie, 'nessuna copia prima di aggiornare: %s' % S.migrazioni
    copia = copie[0].split(': ', 1)[1]
    assert 'prima-della-versione-%d' % VERSIONE_SCHEMA in copia
    assert righe(copia, "SELECT valore FROM impostazioni WHERE chiave = 'versione_schema'") == [('3',)], 'la copia non e la 1.3'
    S2 = crea_sessione('sqlite:///' + p)
    assert S2.versione_precedente == VERSIONE_SCHEMA and S2.colonne_aggiunte == [] and S2.migrazioni == [], \
        'al secondo avvio rifa qualcosa: %s %s' % (S2.colonne_aggiunte, S2.migrazioni)
    return '%d colonne aggiunte' % len(S.colonne_aggiunte)


def ag_pagine_dopo():
    p = database_v13()
    S = crea_sessione('sqlite:///' + p)
    C = collega(S)
    mese = MAR.strftime('%Y-%m')
    for u in ['/giorno/%s' % MAR, '/giorno/%s/elenco' % MAR, '/chiusura/%s' % MAR, '/cassa/%s' % MAR,
              '/cassa/mese/%s' % mese, '/cassa/listino', '/attesa', '/attesa/nuova', '/cose-da-fare', '/moduli',
              '/moduli/nuovo', '/importa', '/sposta', '/agenda-medico/%s' % MAR, '/appuntamento/1',
              '/appuntamento/1/sposta', '/pazienti/1', '/statistiche', '/notifiche.json', '/cerca-tutto.json?q=esp',
              '/stampa/%s' % MAR, '/impostazioni', '/anagrafiche/medici/1']:
        r = C.get(u)
        assert r.status_code == 200, '%s -> %d' % (u, r.status_code)
    # i campi in piu' salvati dalla 1.3 si vedono ancora
    assert 'Sedazione' in html(C.get('/giorno/%s/elenco' % MAR)), 'campi in piu persi'
    r = C.post('/appuntamento/1/pagamento', data={'metodo': 'POS'})
    assert r.status_code == 302 and leggi(S, Appuntamento, 1)['pagato_cent'] == 8000, 'pagamento su dato 1.3'


prova('dalla 1.3: dati intatti, tabelle e colonne nuove, copia, secondo avvio', ag_da_13)
prova('dalla 1.3: tutte le pagine nuove rispondono', ag_pagine_dopo)


# =====================================================================
area('importazione: riconoscimento')


def cf_oracolo(cf15):
    """Carattere di controllo del codice fiscale, calcolato a parte."""
    dispari = [1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23]
    somma = 0
    for i, c in enumerate(cf15):
        v = int(c) if c.isdigit() else ord(c) - 65
        somma += dispari[v] if i % 2 == 0 else v
    return cf15 + chr(65 + somma % 26)


def xlsx(fogli):
    """fogli: [(nome, righe, celle_unite)] -> bytes di un .xlsx"""
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for nome, righe_, unite in fogli:
        ws = wb.create_sheet(nome)
        for r in righe_:
            ws.append(list(r))
        for u in unite:
            ws.merge_cells(u)
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


def agenda_a_blocchi():
    """Come l'agenda degli interventi dell'accettazione: due sale affiancate
    con le stesse colonne, giorno e data in celle unite, un'ora per riga, il
    telefono del chirurgo, errori di battitura e punti interrogativi."""
    righe_ = [[None, None, None, 'SALA A ', None, None, None, None, None, None, None, None, 'SALA B'] + [None] * 7,
              ['GIORNO', None, 'ORA', 'INTERVENTO', 'OPERATORE', 'TELEFONO', 'MEDICO ANESTESISTA', 'PAZIENTE',
               'DEGENZA', 'ASSICURAZIONE MEDICO', 'IMPORTO', None, 'INTERVENTO', 'OPERATORE', 'TELEFONO',
               'MEDICO ANESTESISTA', 'PAZIENTE', 'DEGENZA', 'ASSICURAZIONE MEDICO', 'IMPORTO']]
    unite = ['D1:K1', 'M1:T1', 'A2:B2']
    blocchi = [
        (IERI, {9: (['OTOPLASTICA', 'AMENTA', 3470009101, 'LANDOLFI', 'CAPASSO CIRO', None, None, None], None)}),
        (MAR, {9: (['RINOPLASTICA', 'COSTANZO ', 3470009102, 'LANDOLFI', 'DE FITTIZI TERESA', 'RO', None, None],
                   ['MASTOPALSTICA ADDITIVA', 'PALUMBO', 3470009103, 'IZZO', 'FERRARA LUCIA ', 'DH', None, None]),
               10: (['MASTOPLASTICA ADDITIVA', 'PALUMBO', 3470009103, 'IZZO', 'SERRA MARIA ELENA', None, None, None], None),
               12: (['RIMOZIONE PROTESI', 'AMENTA', 3470009101, 'IZZO', 'PROVETTI PAOLA', 'DH', None, None],
                    ['RINOSETTOPLASTICA', 'AMENTA', 3470009101, 'IZZO', "D'AMORE GIULIA", 'NOTTE', None, None]),
               13: (None, [None, None, None, 'NESSUNA SECONDA SALA DOPO LE 13', None, None, None, None]),
               15: (['RINOPLASTICA ?', 'SORRENTINO', 3470009104, 'IZZO', '?', 'DH', None, None], None)}),
        (GIO, {8.5: (None, ['MASTOPLASTICA ADDITIVA', 'MARINO', 3470009105, 'ORLANDO', 'SCOGNAMIGLIO RITA', 'DH', 'UNISALUTE', 1500]),
               9: (['MASTOPLASTICA ADDITIVA', 'CARUSO', 3470009106, 'LANDOLFI F.', 'ANNA VITALE', 'DH', None, None], None),
               10: (['MASTOPESSI', 'PALUMBO', 3470009103, 'IZZO', 'DE FITTIZI TERESA', None, None, None], None)})]
    for giorno, voci in blocchi:
        ore = [8, 8.5, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19] if 8.5 in voci else list(range(8, 20))
        primo = len(righe_) + 1
        for h in ore:
            a, b = voci.get(h, (None, None))
            ora = time(int(h), 30 if h != int(h) else 0)
            righe_.append([servizi.GIORNI[giorno.weekday()].upper(), datetime.combine(giorno, time(0, 0)), ora]
                          + (a or [None] * 8) + [None] + (b or [None] * 8))
        ultimo = len(righe_)
        unite += ['A%d:A%d' % (primo, ultimo), 'B%d:B%d' % (primo, ultimo)]
    righe_.append([None] * 20)
    return xlsx([('SETTEMBRE', righe_, unite)])


def im_riconoscimento_blocchi():
    fogli = importa.leggi_file(agenda_a_blocchi(), 'interventi.xlsx')
    a = importa.analizza(fogli[0])
    assert a['tipo'] == 'appuntamenti', a['tipo']
    assert a['riga_intestazioni'] == 1, 'riga delle intestazioni %d' % a['riga_intestazioni']
    assert [g['nome'].strip() for g in a['gruppi']] == ['SALA A', 'SALA B'], a['gruppi']
    atteso = {'c1': 'data', 'c2': 'ora', 'g0': 'prestazione', 'g1': 'medico', 'g2': 'telefono_medico',
              'g3': 'extra', 'g4': 'cognome_nome', 'g5': 'extra', 'g6': 'convenzione', 'g7': 'importo'}
    trovato = {k: v for k, v in a['campi'].items() if k in atteso}
    assert trovato == atteso, 'colonne: %s' % trovato
    assert a['campi']['c0'] == 'ignora', 'il giorno della settimana va ignorato'
    assert any('telefono del medico' in n for n in a['note']), 'nessuna spiegazione sul telefono del medico'
    assert importa.passo_orari(a) == 60, 'passo %s' % importa.passo_orari(a)


def im_riconoscimento_semplice():
    casi = [
        (['Paziente', 'Tel.', 'Data', 'Ora', 'Dottore', 'Esame'],
         [['Rossi Marta', '333 1234567', '24/09/2027', '9:30', 'Lippiello', 'Visita']],
         {'Paziente': 'cognome_nome', 'Tel.': 'telefono', 'Data': 'data', 'Ora': 'ora', 'Dottore': 'medico', 'Esame': 'prestazione'}),
        (['Cognome', 'Nome', 'Cellulare', 'Telefono fisso', 'E-mail', 'Cod. Fiscale', 'Nato il'],
         [['Rossi', 'Marta', 3331234567, '081 555 1234', 'm@r.it', cf_oracolo('RSSMRT78C52F839'), date(1978, 3, 12)]],
         {'Cognome': 'cognome', 'Nome': 'nome', 'Cellulare': 'telefono', 'Telefono fisso': 'telefono2',
          'E-mail': 'email', 'Cod. Fiscale': 'codice_fiscale', 'Nato il': 'data_nascita'}),
        # nomi di colonna inutili: decide il contenuto
        (['Colonna1', 'Colonna2', 'Colonna3'],
         [['Rossi Marta', 'marta@example.it', cf_oracolo('RSSMRT78C52F839')], ['Bianchi Luca', 'l@b.it', cf_oracolo('BNCLCU80A01F839')]],
         {'Colonna2': 'email', 'Colonna3': 'codice_fiscale'}),
    ]
    for intestazioni, dati, atteso in casi:
        righe_ = [['Rubrica 2026'], []] + [intestazioni] + dati * 5
        a = importa.analizza({'nome': 'Foglio1', 'righe': righe_})
        mappa = {a['intestazioni'][j]: a['campi'][pos] for pos, j in a['posizioni']}
        sbagliati = {k: (mappa.get(k), v) for k, v in atteso.items() if mappa.get(k) != v}
        assert not sbagliati, 'colonne sbagliate (trovato, atteso): %s' % sbagliati
    return '%d fogli' % len(casi)


def im_nomi():
    casi = {'DE LUCA CIRO': ('DE LUCA', 'CIRO', True), 'ROSSI MARTA': ('ROSSI', 'MARTA', True),
            'DE FITTIZI TERESA': ('DE FITTIZI', 'TERESA', True), 'ANNA VITALE': ('VITALE', 'ANNA', True),
            'SERRA MARIA ELENA': ('SERRA', 'MARIA ELENA', True), "D'ARCO SILVIA": ("D'ARCO", 'SILVIA', True),
            'DI MARIA ANNA': ('DI MARIA', 'ANNA', True), 'LUCA DELLA ROCCA': ('DELLA ROCCA', 'LUCA', True),
            'ESPOSITO': ('ESPOSITO', '', True), 'MARIA ROSA': ('MARIA', 'ROSA', False),
            'KOWALSKI JAN': ('KOWALSKI', 'JAN', False)}
    for testo, atteso in casi.items():
        assert importa.dividi_nome(testo) == atteso, '%s -> %s' % (testo, importa.dividi_nome(testo))
    for testo, atteso in {'DE FITTIZI': 'De Fittizi', "D'ARCO": "D'Arco", 'Rossi': 'Rossi', 'mcDONALD': 'mcDONALD'}.items():
        assert importa.iniziali_maiuscole(testo) == atteso, '%s -> %s' % (testo, importa.iniziali_maiuscole(testo))


def im_valori():
    assert importa.come_ora(0.375) == time(9, 0) and importa.come_ora('9.30') == time(9, 30)
    assert importa.come_ora('25:00') is None and importa.come_ora('9') == time(9, 0)
    assert importa.come_data('24/9/27') == date(2027, 9, 24) and importa.come_data('2027-09-24') == date(2027, 9, 24)
    assert importa.come_data('31/02/2027') is None and importa.come_data(45000) is None
    assert importa.come_telefono(3331234567) == '3331234567' and importa.come_telefono('dr. Rossi 333 123 4567') == '3331234567'
    assert importa.come_telefono('+39 333 1234567') == '+393331234567'
    assert importa.come_importo('1.250,50') == 125050 and importa.come_importo(80) == 8000
    for cattivo in ('1e3', 'nan', '-5', 'abc'):
        try:
            importa.come_importo(cattivo)
            assert False, 'importo %r accettato' % cattivo
        except ValueError:
            pass
    assert importa.simile('MASTOPALSTICA ADDITIVA', 'Mastoplastica additiva')
    assert not importa.simile('Rinoplastica', 'Otoplastica'), 'rinoplastica e otoplastica sono diverse'
    assert importa.grafia_migliore([('MASTOPALSTICA ADDITIVA', 10), ('MASTOPLASTICA ADDITIVA', 2)]) == 'MASTOPLASTICA ADDITIVA'


prova('agenda a blocchi: sale, colonne, telefono del medico, passo', im_riconoscimento_blocchi)
prova('fogli semplici: sinonimi e contenuto', im_riconoscimento_semplice)
prova('cognome e nome nella stessa colonna', im_nomi)
prova('date, orari, telefoni, importi, nomi quasi uguali', im_valori)


# =====================================================================
area('importazione: agenda')


def importa_web(C, dati, nome, **campi):
    r = C.post('/importa', data={'file': (io.BytesIO(dati), nome), 'tipo': campi.pop('tipo', '')},
               content_type='multipart/form-data')
    assert r.status_code == 302 and '/importa/' in r.headers['Location'], 'caricamento: HTTP %d %s' % (
        r.status_code, avvisi(C))
    indirizzo = r.headers['Location']
    anteprima = C.get(indirizzo)
    assert anteprima.status_code == 200, 'anteprima HTTP %d' % anteprima.status_code
    return indirizzo, anteprima


def im_agenda():
    S, C = mondo()
    indirizzo, anteprima = importa_web(C, agenda_a_blocchi(), 'interventi.xlsx')
    t = html(anteprima)
    assert 'telefono del medico' in t and 'Mastoplastica additiva' in t, 'anteprima incompleta'
    r = C.post(indirizzo, data={'azione': 'importa', 'struttura': '1'})
    assert r.status_code == 200 and 'Importazione completata' in html(r), 'importazione: %s' % avvisi(C, r)
    s = S()
    apps = s.scalars(select(Appuntamento).order_by(Appuntamento.inizio)).all()
    assert len(apps) == 10, 'appuntamenti importati: %d invece di 10' % len(apps)
    per_giorno = {}
    for a in apps:
        per_giorno[a.inizio.date()] = per_giorno.get(a.inizio.date(), 0) + 1
    assert per_giorno == {IERI: 1, MAR: 6, GIO: 3}, per_giorno
    stanze = {a.risorsa.nome for a in apps}
    assert stanze == {'Sala A', 'Sala B'}, stanze
    medici = sorted(o.cognome for o in s.scalars(select(Operatore)) if o.cognome not in ('Lippiello', 'Galasso', 'Amato'))
    assert medici == ['Amenta', 'Caruso', 'Costanzo', 'Marino', 'Palumbo', 'Sorrentino'], medici
    palumbo = s.scalars(select(Operatore).where(Operatore.cognome == 'Palumbo')).one()
    assert palumbo.telefono == '3470009103', 'telefono del medico non salvato sul medico'
    paz = s.scalars(select(Paziente)).all()
    assert sorted(p.etichetta for p in paz) == sorted(['De Fittizi Teresa', 'Ferrara Lucia', 'Serra Maria Elena',
                                                        'Provetti Paola', "D'Amore Giulia", 'Scognamiglio Rita',
                                                        'Vitale Anna', 'Capasso Ciro']), [p.etichetta for p in paz]
    assert all(not p.telefono for p in paz), 'il telefono del chirurgo è finito su un paziente'
    de_fittizi = next(p for p in paz if p.cognome == 'De Fittizi')
    assert sum(1 for a in apps if a.paziente_id == de_fittizi.id) == 2, 'De Fittizi in due schede'
    prest = {p.nome for p in s.scalars(select(Prestazione))}
    assert 'Mastoplastica additiva' in prest and not any('palstica' in p.lower() for p in prest), prest
    rino = [a for a in apps if a.prestazione and a.prestazione.nome == 'Rinoplastica']
    assert len(rino) == 2, 'Rinoplastica e "RINOPLASTICA ?" sono la stessa prestazione: %d' % len(rino)
    sorrentino = next(a for a in apps if a.operatore.cognome == 'Sorrentino')
    assert sorrentino.paziente_id is None and 'paziente da definire' in sorrentino.note, 'riga con "?" come paziente'
    passato = next(a for a in apps if a.inizio.date() == IERI)
    assert passato.stato == 'ARRIVATO' and all(a.stato == 'PRENOTATO' for a in apps if a.inizio.date() > OGGI)
    marino = next(a for a in apps if a.operatore.cognome == 'Marino')
    assert marino.inizio.time() == time(8, 30) and marino.importo_cent == 150000 and marino.convenzione == 'UNISALUTE'
    assert all(a.durata_min == 60 for a in apps), 'durate: %s' % {a.durata_min for a in apps}
    serra = next(a for a in apps if a.paziente and a.paziente.cognome == 'Serra')
    assert serra.valori_extra == {'Medico anestesista': 'IZZO'}, serra.valori_extra
    campi = {e for e, _ in serra.prestazione.elenco_campi_extra}
    assert 'Medico anestesista' in campi and 'Degenza' not in campi, 'campi in più della prestazione: %s' % campi
    # la degenza e' un campo dell'appuntamento (conta i letti), non un campo in piu'
    degenze = {a.paziente.cognome: a.degenza for a in apps if a.paziente and a.inizio.date() == MAR}
    assert degenze.get('De Fittizi') == 'RICOVERO' and degenze.get('Ferrara') == 'DH' \
        and degenze.get("D'Amore") == 'NOTTE' and degenze.get('Serra') == '', degenze
    nota = s.scalars(select(NotaGiorno).where(NotaGiorno.data == MAR)).first()
    assert nota is not None and 'NESSUNA SECONDA SALA' in nota.testo, 'nota del giorno non importata'
    s.close()
    cartella = backup.cartella_predefinita(S.motore.url.database)
    assert any('prima-dell-importazione' in f for f in os.listdir(cartella)), 'nessun backup prima di importare'
    # il file importato di nuovo non duplica niente
    indirizzo, anteprima = importa_web(C, agenda_a_blocchi(), 'interventi.xlsx')
    assert 'già in agenda' in html(anteprima)
    # anche quelli senza paziente sono "gia' in agenda", non in conflitto con se stessi
    assert '</b> in conflitto' not in html(anteprima), 'reimportando, righe in conflitto con se stesse'
    assert re.search(r'<li><b>10</b> già in agenda', html(anteprima)), 'non tutti riconosciuti come già in agenda'
    C.post(indirizzo, data={'azione': 'importa', 'struttura': '1'})
    assert conta(S, Appuntamento) == 10 and conta(S, Paziente) == 8, 'seconda importazione: %d appuntamenti, %d pazienti' % (
        conta(S, Appuntamento), conta(S, Paziente))
    # la griglia del giorno si apre e mostra la nota
    t = html(C.get('/giorno/%s?struttura=1' % MAR))
    assert 'NESSUNA SECONDA SALA' in t and 'De Fittizi Teresa' in t
    return '10 appuntamenti, 8 pazienti, 6 medici'


def im_conflitti():
    S, C = mondo()
    I = ids(S)
    s = S()
    s.add(Risorsa(nome='Sala A', tipo='SALA_OPERATORIA', struttura_id=1, ordine=10))
    s.commit()
    sala = s.scalars(select(Risorsa).where(Risorsa.nome == 'Sala A')).one().id
    s.close()
    nuovo_app(S, sala, I['Lippiello'], MAR, 9, 30, minuti=30)          # occupa la Sala A alle 9:30
    fogli = importa.leggi_file(agenda_a_blocchi(), 'x.xlsx')
    a = importa.analizza(fogli[0])
    s = S()
    piano = importa.prepara(s, a, importa.opzioni_da({'struttura': '1'}, a))
    s.close()
    conflitti = [r for r in piano['righe'] if r['esito'] == 'conflitto']
    assert len(conflitti) == 1 and conflitti[0]['inizio'] == datetime.combine(MAR, time(9, 0)), \
        'conflitti: %s' % [(r['inizio'], r['motivo']) for r in conflitti]
    # stesso chirurgo in due sale alla stessa ora: si importa ma si segnala
    assert piano['medici_doppi'] == 1, 'medici doppi: %d' % piano['medici_doppi']
    # senza creare i medici mancanti: le righe dei medici sconosciuti si scartano col motivo
    s = S()
    piano = importa.prepara(s, a, importa.opzioni_da({'struttura': '1', 'crea_medici': '0'}, a))
    s.close()
    assert all(r['esito'] != 'nuovo' for r in piano['righe']), 'importate righe con medici sconosciuti'
    assert any('medico non in anagrafica' in r['motivo'] for r in piano['righe'])


def im_esportazione_e_ritorno():
    """Il planning esportato dal gestionale, reimportato in un database
    vuoto con le stesse stanze e medici, ridà gli stessi appuntamenti."""
    S, C = mondo()
    I = ids(S)
    p1 = crea_paz(S, cognome='Esposito', nome='Anna', telefono='3331234567', email='anna@example.it')
    p2 = crea_paz(S, cognome='De Luca', nome='Ciro', telefono='3401234567')
    nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], MAR, 9, 0, paziente=p1, prest=I['Controllo'], importo_cent=8000,
              convenzione='Privato', tipo='CONTROLLO')
    nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], MAR, 9, 30, minuti=45, paziente=p2, prest=I['Colonscopia'])
    nuovo_app(S, I['Sala endoscopia'], I['Galasso'], MAR, 10, 0, paziente=p1, prest=I['EGDS'], stato='CONFERMATO')
    nuovo_app(S, I['Ambulatorio 3'], I['Amato'], MAR, 16, 0, paziente=p2, prest=I['Prima visita'], stato='DISDETTO')
    percorso = os.path.join(PROVVISORIA, 'planning.xlsx')
    s = S()
    servizi.esporta_giorno(s, MAR, 1, percorso)
    prima = sorted((a.inizio, a.fine, a.risorsa.nome, a.operatore.cognome, a.paziente.etichetta, a.stato,
                    a.prestazione.nome, a.importo_cent) for a in s.scalars(select(Appuntamento)))
    s.close()
    S2, C2 = mondo()
    dati = open(percorso, 'rb').read()
    fogli = importa.leggi_file(dati, 'planning.xlsx')
    indice = next(i for i, f in enumerate(fogli) if f['nome'] == 'Elenco')
    indirizzo, anteprima = importa_web(C2, dati, 'planning.xlsx')
    r = C2.post(indirizzo, data={'azione': 'importa', 'struttura': '1', 'foglio': str(indice),
                                 'foglio_precedente': str(indice), 'maiuscole': '0'})
    assert r.status_code == 200 and 'Importazione completata' in html(r), avvisi(C2, r)
    s = S2()
    dopo = sorted((a.inizio, a.fine, a.risorsa.nome, a.operatore.cognome, a.paziente.etichetta, a.stato,
                   a.prestazione.nome, a.importo_cent) for a in s.scalars(select(Appuntamento)))
    telefoni = {p.etichetta: p.telefono for p in s.scalars(select(Paziente))}
    s.close()
    assert dopo == prima, 'diverso dopo il ritorno:\n%s\n%s' % (prima, dopo)
    assert telefoni == {'Esposito Anna': '3331234567', 'De Luca Ciro': '3401234567'}, telefoni


def im_agenda_di_un_medico():
    """Come le agende dell'accettazione: un file per medico, senza la colonna del
    medico ne' della stanza; li dice il titolo. E il planning delle stanze, con le
    etichette STANZA 1, STANZA 2 sopra i nomi delle colonne."""
    S, C = mondo()
    I = ids(S)
    giorno = datetime.combine(MAR, time(0, 0))
    righe_ = [[None, 'AGENDA ENDOSCOPIA - DR. GALASSO'], [None, 'Anno'], [],
              ['GIORNO', None, 'ORA', 'PAZIENTE', 'TELEFONO', 'TIPO ESAME', 'SEDAZIONE', 'IMPORTO', 'NOTE'],
              ['MARTEDÌ', giorno, time(8, 0), 'ESPOSITO CIRO', '3471112233', 'Colonscopia', 'Sì', 250, None],
              [None, giorno, time(9, 0), None, None, None, None, None, None],
              [None, giorno, time(10, 0), 'ROSSI ANNA', '3339990001', 'EGDS', 'No', None, 'digiuno']]
    dati = xlsx([('OTTOBRE', righe_, ['A4:B4'])])
    fogli = importa.leggi_file(dati, 'AGENDA ENDOSCOPIA DR. GALASSO.xlsx')
    a = importa.analizza(fogli[0])
    s = S()
    piano = importa.prepara(s, a, importa.opzioni_da({'struttura': '1'}, a))
    s.close()
    assert piano['medico_file'] is not None and piano['medico_file'].cognome == 'Galasso', piano['medico_file']
    assert piano['stanze_scelte'] == {0: I['Sala endoscopia']}, piano['stanze_scelte']
    esiti_ = [(r['inizio'].time(), r['esito'], r['stanza'].nome, r['medico'].cognome) for r in piano['righe']]
    assert esiti_ == [(time(8, 0), 'nuovo', 'Sala endoscopia', 'Galasso'), (time(10, 0), 'nuovo', 'Sala endoscopia', 'Galasso')], esiti_
    # scelto a mano un altro medico: vale quello
    s = S()
    piano = importa.prepara(s, a, importa.opzioni_da({'struttura': '1', 'medico_file': str(I['Lippiello'])}, a))
    s.close()
    assert {r['medico'].cognome for r in piano['righe']} == {'Lippiello'}
    # tolto a mano ("—"): le righe dicono cosa manca
    s = S()
    piano = importa.prepara(s, a, importa.opzioni_da({'struttura': '1', 'medico_file': ''}, a))
    s.close()
    assert all('manca il medico' in r['motivo'] for r in piano['righe']), [r['motivo'] for r in piano['righe']]
    # il planning: la riga STANZA 1, STANZA 2 non e' quella delle intestazioni
    righe_ = [[None, None, None, 'STANZA 1', None, None, 'STANZA 2', None],
              ['GIORNO', None, 'ORA', 'MEDICO', 'PRESTAZIONE / NOTE', None, 'MEDICO', 'PRESTAZIONE / NOTE'],
              ['MARTEDÌ', giorno, time(8, 0), 'Lippiello', 'visite', None, None, None],
              [None, giorno, time(9, 0), None, None, None, 'Galasso', 'ecografie']]
    a = importa.analizza({'nome': 'SETTEMBRE', 'righe': righe_})
    assert a['riga_intestazioni'] == 1 and [g['nome'] for g in a['gruppi']] == ['STANZA 1', 'STANZA 2'], (
        a['riga_intestazioni'], a['gruppi'])
    s = S()
    piano = importa.prepara(s, a, importa.opzioni_da({'struttura': '1'}, a))
    s.close()
    assert piano['senza_pazienti'], 'planning senza pazienti non segnalato'
    # un medico del titolo che non c'e' ancora (appena installato): si crea
    attesi = {'AGENDA ENDOSCOPIA DR. GALASSO OTT-NOV-DIC 2026.xlsx OTTOBRE AGENDA ENDOSCOPIA - DR. GALASSO': 'GALASSO',
              'AGENDA AMBULATORI DOTT.SSA LIPPIELLO SET-DIC 2026.xlsx': 'LIPPIELLO',
              'Agenda Dott. Mario Rossi.xlsx': 'Mario Rossi', 'AGENDA PROF. DE LUCA 2027': 'DE LUCA',
              "DOTT. D'ANDREA": "D'ANDREA", 'Dott.ssa Maria Rosa Esposito': 'Maria Rosa Esposito',
              'INTERVENTI 2027.xlsx GENNAIO': '', 'Dr Rossi e Dr Bianchi': '', 'DRAGO SALA 2': '',
              'PLANNING AMBULATORI SET-DIC 2026.xlsx': ''}
    for titolo, nome in attesi.items():
        assert importa.nome_medico_nel_titolo(titolo) == nome, (titolo, importa.nome_medico_nel_titolo(titolo))
    righe_ = [[None, 'AGENDA ENDOSCOPIA - DOTT. FERRANTE'], [],
              ['GIORNO', None, 'ORA', 'PAZIENTE', 'TELEFONO', 'TIPO ESAME'],
              ['MARTEDÌ', giorno, time(8, 0), 'ESPOSITO CIRO', '3471112233', 'Colonscopia']]
    a = importa.analizza({'nome': 'OTTOBRE', 'righe': righe_, 'file': 'agenda ferrante.xlsx'})
    s = S()
    piano = importa.prepara(s, a, importa.opzioni_da({'struttura': '1'}, a))
    assert piano['medico_file'] is None and piano['medico_titolo_nuovo'] == 'FERRANTE', piano['medico_titolo_nuovo']
    assert [m['cognome'] for m in piano['nuovi_medici']] == ['Ferrante'], piano['nuovi_medici']
    assert [r['esito'] for r in piano['righe']] == ['nuovo'], [(r['esito'], r['motivo']) for r in piano['righe']]
    # la colonna B senza intestazione (niente cella unita su GIORNO) e' la data
    assert piano['righe'][0]['inizio'] == datetime.combine(MAR, time(8, 0))
    # tolto a mano: niente medico
    piano = importa.prepara(s, a, importa.opzioni_da({'struttura': '1', 'medico_file': ''}, a))
    assert piano['righe'][0]['esito'] == 'scartato' and not piano['nuovi_medici']
    piano = importa.prepara(s, a, importa.opzioni_da({'struttura': '1', 'medico_file': 'titolo'}, a))
    assert piano['righe'][0]['esito'] == 'nuovo'
    s.close()


def im_un_foglio_per_mese():
    """I modelli dell'accettazione: ISTRUZIONI in testa (con una tabella d'esempio),
    poi un foglio per mese, poi RIEPILOGO. Si parte dal primo mese, e dopo
    l'importazione si passa al mese dopo con le stesse colonne."""
    S, C = mondo()
    g1 = datetime.combine(MAR, time(0, 0))
    g2 = datetime.combine(MAR + timedelta(days=35), time(0, 0))
    intestazione = ['GIORNO', None, 'ORA', 'PAZIENTE', 'TELEFONO', 'TIPO ESAME', 'IMPORTO']
    istruzioni = [['COME SI USA'], ['Una riga per appuntamento.'],
                  ['Esempio:', 'ORA', 'PAZIENTE', 'TELEFONO'], [None, '09:00', 'ROSSI MARTA', '3331234567'],
                  [None, '10:00', 'BIANCHI LUCA', '3331234568']] + [['Nota %d' % k, 'testo'] for k in range(40)]
    mese1 = [[None, 'AGENDA ENDOSCOPIA - DR. GALASSO'], [], intestazione,
             ['MARTEDÌ', g1, time(8, 0), 'ESPOSITO CIRO', '3471112233', 'Colonscopia', 250],
             [None, g1, time(9, 0), 'ROSSI ANNA', '3339990001', 'EGDS', None]]
    mese2 = [[None, 'AGENDA ENDOSCOPIA - DR. GALASSO'], [], intestazione,
             ['MARTEDÌ', g2, time(8, 0), 'VERDI PAOLO', '3471112299', 'Colonscopia', 250]]
    riepilogo = [['MESE', 'APPUNTAMENTI', 'INCASSO'], ['OTTOBRE', 2, 250], ['NOVEMBRE', 1, 250]]
    dati = xlsx([('ISTRUZIONI', istruzioni, []), ('OTTOBRE', mese1, []), ('NOVEMBRE', mese2, []),
                 ('RIEPILOGO', riepilogo, [])])
    fogli = importa.leggi_file(dati, 'Agenda Dr. Galasso.XLSX')
    assert fogli[1]['file'] == 'Agenda Dr. Galasso.XLSX', 'nome del file cambiato: %s' % fogli[1]['file']
    assert importa.foglio_di_dati(fogli) == 1, 'foglio proposto: %s' % fogli[importa.foglio_di_dati(fogli)]['nome']
    assert importa.foglio_successivo(fogli, 1) == 2 and importa.foglio_successivo(fogli, 2) is None
    indirizzo, anteprima = importa_web(C, dati, 'AGENDA ENDOSCOPIA DR. GALASSO.xlsx')
    t = html(anteprima)
    assert re.search(r'<option value="1" selected>OTTOBRE', t), 'anteprima non sul primo mese'
    assert '<b>2</b> appuntamenti da importare' in t, 'conteggio primo mese: %s' % re.findall(r'<li><b>\d+</b>[^<]*', t)
    r = C.post(indirizzo, data={'azione': 'importa', 'struttura': '1'})
    t = html(r)
    assert 'Importazione completata' in t and 'foglio OTTOBRE' in t, avvisi(C, r)
    m = re.search(r'href="([^"]*foglio=2[^"]*)">Anteprima del foglio NOVEMBRE', t)
    assert m, 'manca il passaggio al mese dopo'
    successivo = m.group(1).replace('&amp;', '&')
    anteprima = C.get(successivo)
    t = html(anteprima)
    assert re.search(r'<option value="2" selected>NOVEMBRE', t) and '<b>1</b> appuntament' in t, 'anteprima mese dopo: %s %s %s' % (successivo, re.findall(r'<option value="\d" selected>\w+', t), re.findall(r'<li><b>\d+</b>[^<]*', t))
    r = C.post(successivo, data={'azione': 'importa', 'struttura': '1', 'foglio': '2'})
    t = html(r)
    assert 'Importazione completata' in t and 'Anteprima del foglio' not in t, 'dopo l\'ultimo mese niente passaggio'
    s = S()
    apps = s.scalars(select(Appuntamento).order_by(Appuntamento.inizio)).all()
    assert [(a.inizio.date(), a.operatore.cognome, a.risorsa.nome) for a in apps] == [
        (MAR, 'Galasso', 'Sala endoscopia'), (MAR, 'Galasso', 'Sala endoscopia'),
        (g2.date(), 'Galasso', 'Sala endoscopia')], [(a.inizio, a.operatore.cognome, a.risorsa.nome) for a in apps]
    assert not any(p.cognome in ('Rossi', 'Bianchi') and p.nome in ('Marta', 'Luca') for p in s.scalars(select(Paziente))), \
        'importati i pazienti dell\'esempio nelle istruzioni'
    s.close()


prova('agenda degli interventi: sale, medici, pazienti, note, backup, seconda volta', im_agenda)
prova('un foglio per mese: si parte dal primo, poi il mese dopo', im_un_foglio_per_mese)
prova('agenda di un medico: medico e stanza dal titolo; planning delle stanze', im_agenda_di_un_medico)
prova('conflitti con l\'agenda e medici non creati', im_conflitti)
prova('planning esportato e reimportato: stessi appuntamenti', im_esportazione_e_ritorno)


# =====================================================================
area('importazione: rubrica pazienti')


def rubrica_csv():
    cf_rossi = cf_oracolo('RSSMRT78C52F839')
    righe_ = ['Rubrica pazienti 2026;;;;;;', ';;;;;;',
              'Nominativo;Tel.;Cell;E-mail;Cod. Fiscale;Nato il;Note',
              'ROSSI MARTA;081 5551234;333 111 2222;marta.rossi@example.it;%s;12/03/1978;preferisce la mattina' % cf_rossi,
              'DE LUCA CIRO;;3401234567;;;;',
              'Esposito Anna;;+39 347 765 4321;anna@example;;;',
              'ROSSI MARTA;;333 111 2222;;;;',
              'Bianchi;;;;BNCXXX00A00A000A;;',
              ';;3339998888;;;;',
              "D'ANGELO ROSA;;3281112233;rosa@example.it;;31/12/2090;"]
    return '\r\n'.join(righe_).encode('cp1252')


def im_rubrica():
    S, C = mondo()
    crea_paz(S, cognome='Esposito', nome='Anna', telefono='3477654321')
    indirizzo, anteprima = importa_web(C, rubrica_csv(), 'rubrica.csv')
    t = html(anteprima)
    assert 'rubrica di pazienti' in t and 'selected>rubrica' in t.replace('"pazienti" selected', 'selected'), 'tipo non riconosciuto'
    s = S()
    fogli = importa.leggi_file(rubrica_csv(), 'rubrica.csv')
    a = importa.analizza(fogli[0])
    mappa = {a['intestazioni'][j]: a['campi'][pos] for pos, j in a['posizioni']}
    assert mappa == {'Nominativo': 'cognome_nome', 'Tel.': 'telefono', 'Cell': 'telefono2', 'E-mail': 'email',
                     'Cod. Fiscale': 'codice_fiscale', 'Nato il': 'data_nascita', 'Note': 'note'}, mappa
    piano = importa.prepara(s, a, importa.opzioni_da({}, a))
    s.close()
    esiti_ = [(r['n'], r['esito']) for r in piano['righe']]
    assert esiti_ == [(4, 'nuovo'), (5, 'nuovo'), (6, 'esistente'), (7, 'doppio'), (8, 'nuovo'), (9, 'scartato'),
                      (10, 'nuovo')], esiti_
    r = C.post(indirizzo, data={'azione': 'importa'})
    assert 'Importazione completata' in html(r), avvisi(C, r)
    s = S()
    paz = {p.etichetta: p for p in s.scalars(select(Paziente))}
    s.close()
    assert set(paz) == {'Esposito Anna', 'Rossi Marta', 'De Luca Ciro', 'Bianchi', "D'Angelo Rosa"}, set(paz)
    rossi = paz['Rossi Marta']
    assert (rossi.telefono, rossi.telefono2, rossi.email, rossi.data_nascita, rossi.note) == (
        '0815551234', '3331112222', 'marta.rossi@example.it', date(1978, 3, 12), 'preferisce la mattina'), \
        (rossi.telefono, rossi.telefono2, rossi.email, rossi.data_nascita, rossi.note)
    assert PZ.codice_fiscale_valido(rossi.codice_fiscale)
    assert paz['Bianchi'].codice_fiscale == '', 'codice fiscale sbagliato importato'
    assert paz['Esposito Anna'].email == '', 'email non valida importata'
    assert paz["D'Angelo Rosa"].data_nascita is None, 'data di nascita nel futuro importata'
    return '4 nuovi, 1 completato, 1 doppio, 1 scartato'


def im_telefoni_pazienti_veri():
    """Il contrario del telefono del medico: numeri diversi per pazienti
    diversi, anche con lo stesso medico, e una famiglia che condivide il fisso."""
    righe_ = [['Data', 'Ora', 'Medico', 'Paziente', 'Telefono']]
    for k in range(8):
        righe_.append([MAR.strftime('%d/%m/%Y'), '%d:00' % (9 + k), 'Lippiello' if k % 2 else 'Galasso',
                       'Paziente%s Uno' % chr(65 + k), '33312345%02d' % k])
    righe_.append([GIO.strftime('%d/%m/%Y'), '9:00', 'Lippiello', 'Rossi Paolo', '0815551234'])
    righe_.append([GIO.strftime('%d/%m/%Y'), '10:00', 'Lippiello', 'Rossi Anna', '0815551234'])
    a = importa.analizza({'nome': 'agenda', 'righe': righe_})
    campo = {a['intestazioni'][j]: a['campi'][pos] for pos, j in a['posizioni']}['Telefono']
    assert campo == 'telefono', 'telefoni dei pazienti presi per quelli del medico: %s' % campo


prova('rubrica CSV (cp1252, titolo, due telefoni): nuovi, completati, doppi, scartati', im_rubrica)
prova('telefoni veri dei pazienti restano dei pazienti', im_telefoni_pazienti_veri)


# =====================================================================
area('chiusura della giornata')


def ch_chiusura():
    S, C = mondo()
    I = ids(S)
    ieri = IERI
    p = crea_paz(S, cognome='Rossi', telefono='3331234567')
    a1 = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], ieri, 9, 0, paziente=p)
    a2 = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], ieri, 9, 30, stato='CONFERMATO')
    a3 = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], ieri, 10, 0, stato='ARRIVATO')
    a4 = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], ieri, 10, 30, stato='DISDETTO')
    vecchio = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], OGGI - timedelta(days=40), 9, 0)
    s = S()
    s.add(Struttura(nome='Altra sede'))
    s.flush()
    s.add(Risorsa(nome='Studio', struttura_id=2, ordine=1))
    s.commit()
    studio = s.scalars(select(Risorsa).where(Risorsa.nome == 'Studio')).one().id
    s.close()
    altra = nuovo_app(S, studio, I['Galasso'], ieri, 9, 0)
    t = html(C.get('/chiusura/%s?struttura=1' % ieri))
    for aid in (a1, a2):
        assert 'value="%d"' % aid in t, 'manca %d fra quelli da chiudere' % aid
    for aid in (a3, a4, altra):
        assert 'name="scelti" value="%d"' % aid not in t, '%d non va chiuso qui' % aid
    s = S()
    arretrati = segreteria.giorni_da_chiudere(s, 1)
    s.close()
    assert arretrati == {ieri: 2}, 'arretrati %s (il vecchio di 40 giorni non conta)' % arretrati
    # si segnano: uno arrivato, e un id di un'altra struttura mandato apposta non cambia
    C.post('/chiusura/%s?struttura=1' % ieri, data={'azione': 'arrivati', 'scelti': [str(a1), str(altra)], 'struttura': '1'})
    assert leggi(S, Appuntamento, a1)['stato'] == 'ARRIVATO' and leggi(S, Appuntamento, a1)['arrivato_alle'] is None, \
        'giorno passato: stato arrivato senza inventare l\'ora'
    assert leggi(S, Appuntamento, altra)['stato'] == 'PRENOTATO', 'chiuso un appuntamento di un\'altra struttura'
    C.post('/chiusura/%s' % ieri, data={'azione': 'non_presentati', 'scelti': [str(a2)], 'struttura': '1'})
    assert leggi(S, Appuntamento, a2)['stato'] == 'NON_PRESENTATO'
    assert leggi(S, Appuntamento, vecchio)['stato'] == 'PRENOTATO'
    s = S()
    assert segreteria.giorni_da_chiudere(s, 1) == {}, 'dopo la chiusura restano arretrati'
    s.close()
    assert 'È un giorno futuro' in html(C.get('/chiusura/%s' % MAR))
    r = C.post('/chiusura/%s' % ieri, data={'azione': 'boh', 'scelti': [str(a1)], 'struttura': '1'})
    assert r.status_code == 302 and 'non valida' in avvisi(C)


prova('chiusura: solo gli aperti di quel giorno e struttura, arretrati, niente ora inventata', ch_chiusura)


# =====================================================================
area('lista d\'attesa')


def at_adatta_oracolo():
    """adatta_a contro una regola scritta a parte, su combinazioni casuali."""
    S, C = mondo()
    I = ids(S)
    rnd = random.Random(14)
    pazienti_ = [crea_paz(S, cognome='P%d' % k, telefono='33300000%02d' % k) for k in range(4)]
    s = S()
    prove_fatte = 0
    for giro in range(300):
        stanza = rnd.choice([I['Ambulatorio 1'], I['Sala endoscopia']])
        medico = rnd.choice([I['Lippiello'], I['Galasso']])
        prest = rnd.choice([I['Controllo'], I['EGDS'], None])
        g = MAR + timedelta(days=rnd.randint(-3, 10))
        h = rnd.choice([8, 10, 12, 13, 15])
        a = Appuntamento(risorsa_id=stanza, operatore_id=medico, prestazione_id=prest, paziente_id=rnd.choice(pazienti_),
                         inizio=datetime.combine(g, time(h, 0)), fine=datetime.combine(g, time(h, 30)))
        a.risorsa = s.get(Risorsa, stanza)
        x = Attesa(paziente_id=rnd.choice(pazienti_), operatore_id=rnd.choice([None, I['Lippiello'], I['Galasso']]),
                   prestazione_id=rnd.choice([None, I['Controllo'], I['EGDS']]), struttura_id=rnd.choice([None, 1, 2]),
                   dal=rnd.choice([None, MAR, MAR + timedelta(days=5)]), entro=rnd.choice([None, MAR + timedelta(days=3)]),
                   fascia=rnd.choice(['', 'MATTINA', 'POMERIGGIO']), chiusa_il=rnd.choice([None, None, datetime.now()]))
        atteso = (x.chiusa_il is None and x.paziente_id != a.paziente_id
                  and x.operatore_id in (None, medico) and x.prestazione_id in (None, prest)
                  and x.struttura_id in (None, 1) and (x.dal is None or g >= x.dal) and (x.entro is None or g <= x.entro)
                  and not (x.fascia == 'MATTINA' and h >= 13) and not (x.fascia == 'POMERIGGIO' and h < 13))
        assert x.adatta_a(a) == atteso, 'giro %d: %s invece di %s' % (giro, x.adatta_a(a), atteso)
        prove_fatte += 1
    s.close()
    return '%d combinazioni' % prove_fatte


def at_flusso():
    S, C = mondo()
    I = ids(S)
    p0 = crea_paz(S, cognome='Occupante', telefono='3330000000')
    aid = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], MAR, 9, 0, paziente=p0, prest=I['Controllo'])
    # tre in lista: il primo va bene, il secondo vuole il pomeriggio, il terzo va bene ma e' arrivato dopo
    r = C.post('/attesa/nuova', data={'paziente': 'Primo', 'telefono': '3331110001', 'operatore': str(I['Lippiello'])})
    assert r.status_code == 302, avvisi(C)
    C.post('/attesa/nuova', data={'paziente': 'Secondo', 'telefono': '3331110002', 'fascia': 'POMERIGGIO'})
    C.post('/attesa/nuova', data={'paziente': 'Terzo', 'telefono': '3331110003', 'prestazione': str(I['Controllo'])})
    r = C.post('/attesa/nuova', data={'paziente': 'X', 'dal': MAR.isoformat(), 'entro': (MAR - timedelta(days=1)).isoformat()})
    assert 'viene prima' in avvisi(C, r), 'date rovesciate accettate'
    assert conta(S, Attesa) == 3
    r = C.post('/appuntamento/%d/stato' % aid, data={'stato': 'DISDETTO'})
    messaggio = avvisi(C)
    assert '2 in lista d\'attesa' in messaggio, 'avviso alla disdetta: %s' % messaggio
    t = html(C.get('/attesa/per/%d' % aid))
    assert t.index('Primo') < t.index('Terzo') and 'Secondo' not in t, 'ordine o filtro sbagliati'
    assert 'wa.me/393331110001' in t and 'si%20%C3%A8%20liberato' in t, 'WhatsApp per il posto libero'
    s = S()
    primo = s.scalars(select(Attesa).join(Paziente).where(Paziente.cognome == 'Primo')).one()
    xid, pid = primo.id, primo.paziente_id
    s.close()
    r = C.post('/appuntamento', data={'struttura': '1', 'risorsa': str(I['Ambulatorio 1']), 'operatore': str(I['Lippiello']),
                                      'prestazione': str(I['Controllo']), 'data': MAR.isoformat(), 'ora': '09:00',
                                      'paziente_id': str(pid), 'paziente': 'Primo', 'attesa': str(xid)})
    assert r.status_code == 302 and 'Tolto dalla lista' in avvisi(C), 'prenotazione dalla lista'
    x = leggi(S, Attesa, xid)
    assert x['esito'] == 'PRENOTATO' and x['chiusa_il'] and x['appuntamento_id'], x
    assert conta(S, Attesa, Attesa.chiusa_il == None) == 2
    # la pagina della lista e le chiuse
    t = html(C.get('/attesa'))
    assert 'Terzo' in t and 'Primo' not in t
    assert 'Primo' in html(C.get('/attesa?chiuse=1'))


prova('adatta_a contro l\'oracolo, 300 combinazioni', at_adatta_oracolo)
prova('disdetta, chi chiamare in ordine, prenota dalla lista e chiudi', at_flusso)


# =====================================================================
area('spostamenti e serie')


def sp_uno():
    S, C = mondo()
    I = ids(S)
    aid = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], MAR, 9, 0, minuti=40, stato='CONFERMATO')
    nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], GIO, 10, 0)
    t = html(C.get('/appuntamento/%d/sposta' % aid))
    assert 'Sposta qui' in t
    r = C.post('/appuntamento/%d/sposta' % aid, data={'inizio': '%sT10:20' % GIO, 'risorsa': str(I['Ambulatorio 1'])})
    assert 'Non spostato' in avvisi(C), 'spostato sopra un altro appuntamento'
    assert leggi(S, Appuntamento, aid)['inizio'] == datetime.combine(MAR, time(9, 0))
    r = C.post('/appuntamento/%d/sposta' % aid, data={'inizio': '%sT11:00' % GIO, 'risorsa': str(I['Ambulatorio 1'])})
    a = leggi(S, Appuntamento, aid)
    assert a['inizio'] == datetime.combine(GIO, time(11, 0)) and a['fine'] == datetime.combine(GIO, time(11, 40)), a
    assert a['stato'] == 'PRENOTATO', 'un confermato spostato va riconfermato'
    s = S()
    storia = [m.dettaglio for m in s.scalars(select(servizi.Modifica).where(servizi.Modifica.azione == 'SPOSTATO'))]
    s.close()
    assert storia and MAR.strftime('%d/%m/%Y') in storia[0], storia
    for cattivo in ('', 'domani', '2027-13-01T10:00', '1800-01-01T10:00'):
        r = C.post('/appuntamento/%d/sposta' % aid, data={'inizio': cattivo})
        assert r.status_code == 302 and 'non valid' in avvisi(C), 'data %r' % cattivo


def sp_blocco():
    S, C = mondo()
    I = ids(S)
    dal, al = MAR, MAR + timedelta(days=6)
    aids = [nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], dal + timedelta(days=k % 7), 9 + k % 4, 0, minuti=30,
                      paziente=crea_paz(S, cognome='P%d' % k, telefono='33322200%02d' % k)) for k in range(10)]
    # proposte: tutte dopo il periodo, nei turni, senza sovrapporsi fra loro ne' con l'agenda
    t = html(C.get('/sposta?medico=%d&dal=%s&al=%s&modo=dopo' % (I['Lippiello'], dal, al)))
    proposte = re.findall(r'name="p_(\d+)" value="([^"|]+)\|(\d+)\|(\d+)"', t)
    assert len(proposte) == 10, 'proposte %d' % len(proposte)
    intervalli = []
    for aid, quando, rid, oid in proposte:
        inizio = datetime.strptime(quando, '%Y-%m-%dT%H:%M')
        assert inizio.date() > al, 'proposta dentro il periodo: %s' % inizio
        assert time(8, 0) <= inizio.time() and (inizio + timedelta(minutes=30)).time() <= time(14, 0), 'fuori turno %s' % inizio
        intervalli.append((inizio, inizio + timedelta(minutes=30)))
    intervalli.sort()
    assert all(a[1] <= b[0] for a, b in zip(intervalli, intervalli[1:])), 'proposte sovrapposte'
    dati = {'medico': str(I['Lippiello']), 'dal': dal.isoformat(), 'al': al.isoformat(), 'modo': 'dopo',
            'scelti': [p[0] for p in proposte[:7]]}
    dati.update({'p_%s' % p[0]: '%s|%s|%s' % p[1:] for p in proposte})
    r = C.post('/sposta', data=dati)
    assert r.status_code == 302 and '/sposta/avvisi' in r.headers['Location'], 'dopo lo spostamento'
    assert '7 appuntamenti spostati' in avvisi(C)
    t = html(C.get(r.headers['Location']))
    assert t.count('wa.me/') == 7 and 'spostato' in unquote(t), 'avvisi ai pazienti'
    rimasti = conta(S, Appuntamento, Appuntamento.inizio < datetime.combine(al + timedelta(days=1), time(0, 0)))
    assert rimasti == 3, 'nel periodo restano %d invece di 3' % rimasti
    # con un sostituto: stesso giorno e ora, altro medico; dove il sostituto e' occupato, niente proposta
    s = S()
    primo_rimasto = s.scalars(select(Appuntamento).where(
        Appuntamento.inizio < datetime.combine(al + timedelta(days=1), time(0, 0))).order_by(Appuntamento.inizio)).first()
    quando = primo_rimasto.inizio
    s.close()
    nuovo_app(S, I['Ambulatorio 3'], I['Galasso'], quando.date(), quando.hour, quando.minute)
    t = html(C.get('/sposta?medico=%d&dal=%s&al=%s&modo=sostituto&sostituto=%d' % (I['Lippiello'], dal, al, I['Galasso'])))
    proposte = re.findall(r'name="p_(\d+)" value="([^"|]+)\|(\d+)\|(\d+)"', t)
    assert all(int(p[3]) == I['Galasso'] for p in proposte), 'sostituto sbagliato'
    s = S()
    per_id = {str(a.id): a for a in s.scalars(select(Appuntamento))}
    assert all(per_id[p[0]].inizio.strftime('%Y-%m-%dT%H:%M') == p[1] for p in proposte), 'il sostituto cambia l\'ora'
    s.close()
    assert 'nessuna proposta' in t, 'il sostituto occupato va segnalato'
    assert len(proposte) == 2, 'proposte col sostituto: %d invece di 2' % len(proposte)


def se_serie():
    S, C = mondo()
    I = ids(S)
    # alla terza settimana la stanza e' occupata: quella salta e si dice
    nuovo_app(S, I['Ambulatorio 1'], I['Galasso'], MAR + timedelta(weeks=2), 9, 0)
    r = C.post('/appuntamento', data={'struttura': '1', 'risorsa': str(I['Ambulatorio 1']), 'operatore': str(I['Lippiello']),
                                      'prestazione': str(I['Controllo']), 'data': MAR.isoformat(), 'ora': '09:00',
                                      'paziente': 'Serie', 'telefono': '3331119999', 'ripeti': '1', 'ripeti_ogni': '1',
                                      'ripeti_unita': 'settimane', 'ripeti_volte': '5', 'importo': '50'})
    messaggio = avvisi(C)
    assert r.status_code == 302 and '4 appuntamenti prenotati' in messaggio and 'Non prenotato il %s' % (
        MAR + timedelta(weeks=2)).strftime('%d/%m/%Y') in messaggio, messaggio
    s = S()
    serie = s.scalars(select(Appuntamento).where(Appuntamento.serie != '').order_by(Appuntamento.inizio)).all()
    date_ = [a.inizio.date() for a in serie]
    assert date_ == [MAR + timedelta(weeks=k) for k in (0, 1, 3, 4)], date_
    assert len({a.serie for a in serie}) == 1 and all(a.importo_cent == 5000 and a.paziente_id == serie[0].paziente_id for a in serie)
    codice, terzo = serie[0].serie, serie[2].id
    s.close()
    assert 'Serie di 4' in html(C.get('/appuntamento/%d' % terzo))
    C.post('/serie/%s' % codice, data={'azione': 'disdici', 'dal': str(terzo)})
    stati = [leggi(S, Appuntamento, a.id)['stato'] for a in serie]
    assert stati == ['PRENOTATO', 'PRENOTATO', 'DISDETTO', 'DISDETTO'], stati
    # le date di una serie mensile, calcolate a parte
    for inizio, attese in [(datetime(2027, 1, 31, 9), [date(2027, 1, 31), date(2027, 2, 28), date(2027, 3, 31), date(2027, 4, 30)]),
                           (datetime(2027, 11, 30, 9), [date(2027, 11, 30), date(2027, 12, 30), date(2028, 1, 30), date(2028, 2, 29)])]:
        assert [d.date() for d in servizi.date_serie(inizio, 1, 'mesi', 4)] == attese, inizio
    for cattivi in ({'ripeti_volte': '1'}, {'ripeti_volte': '53'}, {'ripeti_ogni': '0'}, {'ripeti_unita': 'anni'},
                    {'ripeti_volte': 'tre'}):
        dati = {'struttura': '1', 'risorsa': str(I['Ambulatorio 1']), 'operatore': str(I['Lippiello']),
                'prestazione': str(I['Controllo']), 'data': GIO.isoformat(), 'ora': '12:00', 'ripeti': '1',
                'ripeti_ogni': '1', 'ripeti_unita': 'settimane', 'ripeti_volte': '3'}
        dati.update(cattivi)
        prima = conta(S, Appuntamento)
        r = C.post('/appuntamento', data=dati)
        assert r.status_code == 200 and 'Ripetizione' in avvisi(C, r) and conta(S, Appuntamento) == prima, cattivi
    assert C.get('/serie/zzzz').status_code == 404 and C.get('/serie/00000000').status_code == 404


prova('sposta: conflitto rifiutato, durata tenuta, confermato torna prenotato, storico', sp_uno)
prova('sposta in blocco: proposte libere, fuori periodo, nei turni; sostituto', sp_blocco)
prova('serie: settimanale con conflitto, disdici da qui, mesi corti, valori sbagliati', se_serie)


# =====================================================================
area('cassa e listino')


def ca_listino():
    S, C = mondo()
    I = ids(S)
    C.post('/cassa/listino', data={'azione': 'listino', 'tariffa_%d' % I['Controllo']: '60', 'tariffa_%d' % I['EGDS']: '1.250,50'})
    assert leggi(S, Prestazione, I['Controllo'])['tariffa_cent'] == 6000
    assert leggi(S, Prestazione, I['EGDS'])['tariffa_cent'] == 125050
    r = C.post('/cassa/listino', data={'azione': 'listino', 'tariffa_%d' % I['Controllo']: '1e3'})
    assert 'non valido' in avvisi(C) and leggi(S, Prestazione, I['Controllo'])['tariffa_cent'] == 6000, 'importo 1e3'
    C.post('/cassa/listino', data={'azione': 'aggiungi', 'prestazione': str(I['Controllo']), 'convenzione': 'UniSalute', 'importo': '45'})
    C.post('/cassa/listino', data={'azione': 'aggiungi', 'prestazione': str(I['Controllo']), 'convenzione': ' unisalute ', 'importo': '40'})
    assert conta(S, Tariffa) == 1, 'la stessa convenzione scritta diversa ha fatto due tariffe'
    C.post('/cassa/listino', data={'azione': 'aggiungi', 'prestazione': str(I['Controllo']), 'convenzione': 'Privato', 'importo': '1'})
    assert 'listino' in avvisi(C) and conta(S, Tariffa) == 1, 'tariffa "Privato"'
    s = S()
    assert cassa.tariffa_per(s, I['Controllo'], 'UNISALUTE') == 4000
    assert cassa.tariffa_per(s, I['Controllo'], 'Privato') == 6000 and cassa.tariffa_per(s, I['Controllo'], '') == 6000
    assert cassa.tariffa_per(s, I['Controllo'], 'Altra') == 6000 and cassa.tariffa_per(s, I['Ecografia'], '') is None
    mappa = cassa.mappa_tariffe(s)
    s.close()
    assert mappa[str(I['Controllo'])] == {'': '60,00', 'unisalute': '40,00'}, mappa
    t = html(C.get('/appuntamento?data=%s&ora=09:00&risorsa=%d' % (MAR, I['Ambulatorio 1'])))
    valore = re.search(r'data-tariffe="([^"]*)"', t).group(1)
    from html import unescape
    assert json.loads(unescape(valore)) == mappa, 'listino nel modulo'


def ca_pagamenti():
    """Totali per metodo contro una somma fatta a parte, su pagamenti casuali."""
    S, C = mondo()
    I = ids(S)
    rnd = random.Random(7)
    attesi = {'CONTANTI': 0, 'POS': 0, 'BONIFICO': 0, 'ASSEGNO': 0}
    aids = []
    for k in range(12):
        aid = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], OGGI, 8 + k // 2, 30 * (k % 2), minuti=30,
                        importo_cent=rnd.randint(1, 400) * 500, stato='ARRIVATO')
        aids.append(aid)
    for aid in aids[:9]:
        metodo = rnd.choice(list(attesi))
        importo = rnd.choice(['', '%d,%02d' % (rnd.randint(10, 300), rnd.randint(0, 99))])
        r = C.post('/appuntamento/%d/pagamento' % aid, data={'metodo': metodo, 'importo': importo})
        assert r.status_code == 302, 'pagamento HTTP %d' % r.status_code
        a = leggi(S, Appuntamento, aid)
        valore = a['importo_cent'] if not importo else int(importo.replace(',', ''))
        assert a['pagato_cent'] == valore and a['pagamento'] == metodo, (a['pagato_cent'], valore)
        attesi[metodo] += valore
    # annullato uno: esce dal totale
    a = leggi(S, Appuntamento, aids[0])
    attesi[a['pagamento']] -= a['pagato_cent']
    C.post('/appuntamento/%d/pagamento' % aids[0], data={'azione': 'annulla'})
    s = S()
    per_metodo, totale = cassa.totali(cassa.incassi(s, OGGI, OGGI, 1))
    s.close()
    assert per_metodo == attesi and totale == sum(attesi.values()), '%s invece di %s' % (per_metodo, attesi)
    t = html(C.get('/cassa/%s' % OGGI))
    from modelli import importo_in_testo
    assert importo_in_testo(totale) in t, 'totale non mostrato'
    # 12 appuntamenti, 9 pagati, 1 pagamento annullato: 4 da incassare
    assert t.count('Altro…') == 4, 'da incassare: %d invece di 4' % t.count('Altro…')
    r = C.get('/cassa/mese/%s' % OGGI.strftime('%Y-%m'))
    assert r.status_code == 200 and importo_in_testo(totale) in html(r)
    r = C.get('/cassa/mese/%s/excel' % OGGI.strftime('%Y-%m'))
    assert r.status_code == 200 and r.data[:2] == b'PK'
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(r.data))
    ultima = [c.value for c in wb['Per giorno'][wb['Per giorno'].max_row]]
    assert abs(ultima[-1] - totale / 100.0) < 0.001, 'totale Excel %s invece di %s' % (ultima[-1], totale / 100.0)
    # errori: metodo sconosciuto, importo storto, niente importo
    senza = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], OGGI, 14, 0)
    for dati, frammento in [({'metodo': 'BITCOIN'}, 'Metodo'), ({'metodo': 'POS', 'importo': 'abc'}, 'non valido'),
                            ({'metodo': 'POS'}, 'Manca')]:
        C.post('/appuntamento/%d/pagamento' % senza, data=dati)
        assert frammento in avvisi(C) and leggi(S, Appuntamento, senza)['pagato_il'] is None, dati
    C.post('/appuntamento/%d/pagamento' % senza, data={'metodo': 'CONTANTI', 'importo': '30'})
    assert leggi(S, Appuntamento, senza)['importo_cent'] == 3000, 'pagato senza prezzo: il prezzo è quello pagato'
    return 'totale %s' % importo_in_testo(totale)


prova('listino e tariffe per convenzione, prezzo proposto nel modulo', ca_listino)
prova('pagamenti casuali: totali per metodo, annullo, mese, Excel', ca_pagamenti)


# =====================================================================
area('documenti e moduli')


def PDF():
    return b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'


def PNG():
    from PIL import Image
    b = io.BytesIO()
    Image.new('RGB', (4, 4), (200, 10, 10)).save(b, 'PNG')
    return b.getvalue()


def do_documenti():
    S, C = mondo()
    p = crea_paz(S, cognome='Rossi', telefono='3331234567')
    for dati, nome in [(PDF(), 'impegnativa.pdf'), (PNG(), 'foto referto.png'), (b'\xff\xd8\xff\xe0' + b'0' * 100, 'x.JPG')]:
        r = C.post('/pazienti/%d/documenti' % p, data={'file': (io.BytesIO(dati), nome), 'descrizione': 'prova'},
                   content_type='multipart/form-data')
        assert r.status_code == 302 and 'allegato' in avvisi(C), nome
    assert conta(S, Documento) == 3
    for dati, nome, frammento in [(b'MZ\x90\x00' + b'0' * 50, 'virus.pdf', 'Si possono allegare'),
                                  (b'', 'vuoto.pdf', 'vuoto'),
                                  (b'%PDF-' + b'0' * (10 * 1024 * 1024 + 1), 'grande.pdf', 'supera 10 MB'),
                                  (b'<svg onload=alert(1)>', 'x.png', 'Si possono allegare')]:
        C.post('/pazienti/%d/documenti' % p, data={'file': (io.BytesIO(dati), nome)}, content_type='multipart/form-data')
        assert frammento in avvisi(C), nome
    assert conta(S, Documento) == 3, 'file non validi accettati'
    s = S()
    docs = s.scalars(select(Documento).order_by(Documento.id)).all()
    ids_ = [d.id for d in docs]
    nomi = [d.nome for d in docs]
    s.close()
    assert nomi == ['impegnativa.pdf', 'foto referto.png', 'x.JPG'], nomi
    r = C.get('/documenti/%d' % ids_[0])
    assert r.status_code == 200 and r.data == PDF() and r.headers['Content-Type'] == 'application/pdf'
    assert r.headers['X-Content-Type-Options'] == 'nosniff'
    r = C.get('/documenti/%d' % ids_[1])
    assert "default-src 'none'" in r.headers.get('Content-Security-Policy', ''), 'immagine senza CSP'
    assert 'attachment' in C.get('/documenti/%d?scarica=1' % ids_[0]).headers['Content-Disposition']
    assert C.get('/documenti/999999').status_code == 404
    t = html(C.get('/pazienti/%d' % p))
    assert 'impegnativa.pdf' in t and 'foto referto.png' in t
    # con documenti la scheda non si elimina; unendo, i documenti passano all'altra scheda
    C.post('/pazienti/%d' % p, data={'azione': 'elimina'})
    assert 'document' in avvisi(C) and conta(S, Paziente) == 1, 'eliminata una scheda con documenti'
    altro = crea_paz(S, cognome='Rossi', nome='Mario')
    s = S()
    tenuto, eliminato = s.get(Paziente, altro), s.get(Paziente, p)
    PZ.unisci(s, tenuto, eliminato)
    s.commit()
    s.close()
    assert conta(S, Documento, Documento.paziente_id == altro) == 3, 'documenti persi nell\'unione'
    C.post('/documenti/%d/elimina' % ids_[0])
    assert conta(S, Documento) == 2
    assert documenti.nome_pulito('C:\\Users\\x\\"a<b>.pdf', 'application/pdf') == 'ab.pdf'


def do_moduli():
    S, C = mondo()
    I = ids(S)
    p = crea_paz(S, cognome='Rossi', nome='Marta', telefono='3331234567', data_nascita=date(1978, 3, 12),
                 codice_fiscale=cf_oracolo('RSSMRT78C52F839'))
    aid = nuovo_app(S, I['Sala endoscopia'], I['Galasso'], MAR, 9, 30, paziente=p, prest=I['Colonscopia'])
    r = C.post('/moduli/nuovo', data={'nome': 'Preparazione colonscopia', 'prestazione': str(I['Colonscopia']), 'firma': '1',
                                      'testo': 'Gentile {paziente} ({codice_fiscale}, nata il {data_nascita}): {giorno} alle {ora}. '
                                               'Da {giorno-3} dieta; il {data-1} solo liquidi; controllo il {data+7}. '
                                               '{sconosciuto} {prestazione} con {medico} in {stanza}, {struttura}{indirizzo}.'})
    assert r.status_code == 302, avvisi(C)
    C.post('/moduli/nuovo', data={'nome': 'Per tutti', 'testo': 'Privacy {cognome}'})
    C.post('/moduli/nuovo', data={'nome': 'Solo EGDS', 'prestazione': str(I['EGDS']), 'testo': 'x'})
    r = C.post('/moduli/nuovo', data={'nome': 'preparazione COLONSCOPIA', 'testo': 'doppio'})
    assert 'Esiste già' in avvisi(C, r), 'nome doppio accettato'
    s = S()
    a = s.get(Appuntamento, aid)
    m = s.scalars(select(ModuloStampa).where(ModuloStampa.nome == 'Preparazione colonscopia')).one()
    testo = documenti.compila(m.testo, a, adesso=datetime(2027, 1, 1, 10, 0))
    applicabili = sorted(x.nome for x in documenti.moduli_per(s, a))
    mid = m.id
    s.close()
    giorno = lambda d: '%s %d %s' % (servizi.GIORNI[d.weekday()], d.day, servizi.MESI[d.month - 1])
    atteso = ('Gentile Rossi Marta (%s, nata il 12/03/1978): %s alle 09:30. Da %s dieta; il %s solo liquidi; '
              'controllo il %s. {sconosciuto} Colonscopia con Galasso in Sala endoscopia, La mia struttura, Via Posillipo 1.') % (
        cf_oracolo('RSSMRT78C52F839'), giorno(MAR), giorno(MAR - timedelta(days=3)),
        (MAR - timedelta(days=1)).strftime('%d/%m/%Y'), (MAR + timedelta(days=7)).strftime('%d/%m/%Y'))
    assert testo == atteso, '\n%s\n%s' % (testo, atteso)
    assert applicabili == ['Per tutti', 'Preparazione colonscopia'], applicabili
    t = html(C.get('/appuntamento/%d' % aid))
    assert 'Preparazione colonscopia' in t and 'Solo EGDS' not in t
    t = html(C.get('/appuntamento/%d/modulo/%d' % (aid, mid)))
    assert 'Firma del paziente' in t and 'Rossi Marta' in t
    # il testo del modulo non puo' iniettare HTML nella stampa
    C.post('/moduli/%d' % mid, data={'nome': 'Preparazione colonscopia', 'testo': '<script>alert(1)</script> {paziente}'})
    t = html(C.get('/appuntamento/%d/modulo/%d' % (aid, mid)))
    assert '<script>alert(1)' not in t and '&lt;script&gt;' in t
    r = C.post('/moduli/nuovo', data={'azione': 'esempio'})
    assert r.status_code == 302 and conta(S, ModuloStampa) == 4


prova('documenti: PDF, PNG, JPG sì; eseguibili, vuoti, enormi no; intestazioni; unione', do_documenti)
prova('moduli: segnaposto e date relative contro l\'oracolo, per prestazione, niente HTML', do_moduli)


# =====================================================================
area('provenienza, note del giorno, cose da fare, notifiche')


def pr_provenienza():
    S, C = mondo()
    I = ids(S)
    r = C.post('/pazienti/nuovo', data={'cognome': 'Nuovo', 'telefono': '3330001111', 'provenienza': 'INTERNET',
                                         'inviato_da': 'Dott. Bianchi', 'canale': 'WHATSAPP'})
    assert r.status_code == 302, avvisi(C)
    C.post('/pazienti/nuovo', data={'cognome': 'Altro', 'provenienza': 'MEDICO', 'inviato_da': 'Dott. Bianchi', 'canale': 'SMS'})
    C.post('/pazienti/nuovo', data={'cognome': 'Terzo', 'canale': 'SMS'})
    r = C.post('/pazienti/nuovo', data={'cognome': 'Cattivo', 'provenienza': 'MARTE', 'canale': 'SMS'})
    assert 'Provenienza' in avvisi(C, r)
    # dal modulo di prenotazione, per un paziente nuovo
    C.post('/appuntamento', data={'struttura': '1', 'risorsa': str(I['Ambulatorio 1']), 'operatore': str(I['Lippiello']),
                                  'prestazione': str(I['Controllo']), 'data': MAR.isoformat(), 'ora': '09:00',
                                  'paziente': 'Dalmodulo', 'telefono': '3339990000', 'provenienza': 'PASSAPAROLA'})
    s = S()
    assert s.scalars(select(Paziente).where(Paziente.cognome == 'Dalmodulo')).one().provenienza == 'PASSAPAROLA'
    d = servizi.statistiche(s, 1, OGGI - timedelta(days=1), OGGI + timedelta(days=1))
    s.close()
    assert dict(d['per_provenienza']) == {'Internet / Google': 1, 'Medico curante o specialista': 1, 'Non indicata': 1,
                                          'Passaparola': 1}, d['per_provenienza']
    assert d['inviati'] == [('Dott. Bianchi', 2)], d['inviati']
    assert 'Chi li manda' in html(C.get('/statistiche'))
    r = C.get('/statistiche/excel')
    from openpyxl import load_workbook
    assert 'Provenienza' in load_workbook(io.BytesIO(r.data)).sheetnames


def no_note_giorno():
    S, C = mondo()
    torna = '/giorno/%s?struttura=1' % MAR
    C.post('/note-giorno', data={'struttura': '1', 'data': MAR.isoformat(), 'testo': 'Lippiello <b>arriva</b> alle 10', 'torna': torna})
    for u in ('/giorno/%s?struttura=1' % MAR, '/giorno/%s/elenco?struttura=1' % MAR, '/stampa/%s?struttura=1' % MAR):
        t = html(C.get(u))
        assert 'Lippiello &lt;b&gt;arriva&lt;/b&gt; alle 10' in t, 'nota non mostrata o non protetta in %s' % u
    assert 'Lippiello &lt;b&gt;arriva' not in html(C.get('/giorno/%s?struttura=1' % GIO)), 'la nota vale per un giorno solo'
    C.post('/note-giorno', data={'struttura': '1', 'data': MAR.isoformat(), 'testo': 'seconda versione'})
    assert conta(S, NotaGiorno) == 1, 'nota duplicata'
    C.post('/note-giorno', data={'struttura': '1', 'data': MAR.isoformat(), 'testo': '   '})
    assert conta(S, NotaGiorno) == 0, 'nota vuota non tolta'
    for dati in ({'struttura': '99', 'data': MAR.isoformat(), 'testo': 'x'}, {'struttura': '1', 'data': 'ieri', 'testo': 'x'},
                 {'struttura': '1', 'data': MAR.isoformat(), 'testo': 'x' * 1001}):
        r = C.post('/note-giorno', data=dati)
        assert r.status_code == 302 and conta(S, NotaGiorno) == 0, dati
    r = C.post('/note-giorno', data={'struttura': '1', 'data': MAR.isoformat(), 'testo': 'x', 'torna': '//sito.esempio'})
    assert r.headers['Location'].startswith('/'), 'rinvio fuori dal programma'


def no_notifiche():
    S, C = mondo()
    I = ids(S)
    domani = servizi.prossimo_giorno_con_appuntamenti  # usata come oracolo sotto
    C.post('/cose-da-fare', data={'testo': 'Richiamare <script>x</script>', 'per_il': OGGI.isoformat()})
    C.post('/cose-da-fare', data={'testo': 'Scaduta', 'per_il': (OGGI - timedelta(days=2)).isoformat()})
    C.post('/cose-da-fare', data={'testo': 'Futura', 'per_il': (OGGI + timedelta(days=3)).isoformat()})
    r = C.post('/cose-da-fare', data={'testo': '', 'per_il': OGGI.isoformat()})
    assert 'serve un testo' in avvisi(C) and conta(S, Attivita) == 3
    g = OGGI + timedelta(days=1)
    for k, stato in enumerate(['PRENOTATO', 'PRENOTATO', 'CONFERMATO', 'DISDETTO']):
        nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], g, 9 + k, 0, stato=stato)
    nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], OGGI - timedelta(days=3), 9, 0)
    r = C.get('/notifiche.json?struttura=1')
    assert r.headers['Content-Type'].startswith('application/json') and r.headers['X-Content-Type-Options'] == 'nosniff'
    assert '<script>' not in html(r), 'JSON con HTML vivo'
    lista = json.loads(html(r))
    titoli = [n['titolo'] for n in lista]
    testi = ' | '.join(n['testo'] for n in lista)
    assert titoli.count('Da fare') == 1 and 'Da fare (dal' in ' '.join(titoli), titoli
    s = S()
    prossimo = domani(s, OGGI, 1)
    attesi = len(servizi.elenco_giorno(s, prossimo, 1, ('PRENOTATO',)))
    s.close()
    assert '%d appuntamenti da confermare' % attesi in testi and attesi == 2, testi
    assert '1 appuntamento dei giorni scorsi' in testi, testi
    chiavi = [n['chiave'] for n in lista]
    assert len(chiavi) == len(set(chiavi)), 'chiavi doppie'
    # "fatto" dalla notifica: sparisce
    fatto = next(n for n in lista if n['titolo'] == 'Da fare' and n['azioni'])
    r = C.post(fatto['azioni'][0]['url'], headers={'X-Richiesta': 'notifica'})
    assert json.loads(html(r)) == {'ok': True}
    lista2 = json.loads(html(C.get('/notifiche.json?struttura=1')))
    assert sum(1 for n in lista2 if n['titolo'].startswith('Da fare')) == 1, 'la cosa fatta è ancora notificata'
    # "domani": passa a domani
    rimanda = next(n for n in lista2 if n['titolo'].startswith('Da fare'))
    C.post(rimanda['azioni'][1]['url'], headers={'X-Richiesta': 'notifica'})
    lista3 = json.loads(html(C.get('/notifiche.json?struttura=1')))
    assert not any(n['titolo'].startswith('Da fare') for n in lista3), 'rimandata ma ancora notificata'
    assert C.get('/notifiche.json?struttura=abc').status_code == 200
    t = html(C.get('/cose-da-fare'))
    assert 'Futura' in t and '&lt;script&gt;' in t


def no_ricerca():
    S, C = mondo()
    crea_paz(S, cognome='De Rosa', nome='Anna', telefono='3331234567')
    casi = {'oggi': OGGI, 'domani': OGGI + timedelta(days=1), 'ieri': OGGI - timedelta(days=1),
            '24/9': date(OGGI.year, 9, 24), '24/09/27': date(2027, 9, 24), '24-09-2027': date(2027, 9, 24),
            '24 settembre': date(OGGI.year, 9, 24), '3 mar 2028': date(2028, 3, 3), '31/02': None, 'rossi': None, '': None}
    for testo, atteso in casi.items():
        assert segreteria.interpreta_data(testo) == atteso, '%r -> %s' % (testo, segreteria.interpreta_data(testo))
    for nome in ('lunedì', 'lunedi', 'lun', 'venerdì'):
        g = segreteria.interpreta_data(nome)
        assert g.weekday() == segreteria.GIORNI_NOMI[nome] and 0 <= (g - OGGI).days < 7, nome
    d = json.loads(html(C.get('/cerca-tutto.json?q=de+rosa')))
    assert [p['etichetta'] for p in d['pazienti']] == ['De Rosa Anna'] and d['giorno'] is None
    d = json.loads(html(C.get('/cerca-tutto.json?q=domani&struttura=1')))
    assert d['giorno'] and (OGGI + timedelta(days=1)).isoformat() in d['giorno']['url']
    d = json.loads(html(C.get('/cerca-tutto.json?q=lipp')))
    assert d['medici'] and 'medico=' in d['medici'][0]['url']
    assert '<' not in html(C.get('/cerca-tutto.json?q=%3Cscript%3E'))
    t = html(C.get('/giorno/%s' % MAR))
    assert 'id="ricerca-rapida"' in t and 'data-tasto="precedente"' in t and 'id="notifiche"' in t


def no_agenda_medico():
    S, C = mondo()
    I = ids(S)
    p = crea_paz(S, cognome='Rossi', telefono='3331234567', data_nascita=date(1980, 1, 1))
    nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], MAR, 9, 0, paziente=p, prest=I['Controllo'], note='porta esami')
    nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], MAR, 9, 30, stato='DISDETTO', paziente=p)
    nuovo_app(S, I['Sala endoscopia'], I['Galasso'], MAR, 10, 0, paziente=p)
    t = html(C.get('/agenda-medico/%s?medico=%d' % (MAR, I['Lippiello'])))
    assert t.count('<tr><td class="c-ora">') == 1, 'disdetti o altri medici nell\'agenda'
    assert 'porta esami' in t and 'mailto:lippiello@example.it' in t
    t = html(C.get('/agenda-medico/%s' % MAR))
    assert t.count('foglio-medico') == 2, 'un foglio per medico'
    assert 'scrivere l\'indirizzo del medico' in t, 'Galasso senza email: spiegazione'
    s = S()
    o = s.get(Operatore, I['Lippiello'])
    lunghe = [s.get(Appuntamento, nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], GIO, 8, 0 + k, minuti=1, note='x' * 300))
              for k in range(0, 50, 1)]
    s.close()
    t = html(C.get('/agenda-medico/%s?medico=%d' % (GIO, I['Lippiello'])))
    mail = re.search(r'href="(mailto:[^"]+)"', t).group(1)
    assert len(unquote(mail)) < 2200, 'mailto troppo lungo per Windows: %d' % len(unquote(mail))


prova('provenienza: scheda, prenotazione, statistiche, Excel', pr_provenienza)
prova('note del giorno: griglia, elenco, stampa, protette, una per giorno', no_note_giorno)
prova('cose da fare e notifiche: scadute, conferme, giornate da chiudere, fatto, domani', no_notifiche)
prova('ricerca rapida: date in italiano, pazienti, medici, protetta', no_ricerca)
prova('agenda del medico: solo i suoi attivi, un foglio per medico, email corta', no_agenda_medico)


# =====================================================================
area('importazione: file veri della clinica (ricostruiti con nomi inventati)')


def im_sale_con_una_colonna_diversa():
    """INTERVENTI di ottobre: la sala A ha RECAPITO PZ dove la sala B ha
    ASSICURAZIONE MEDICO; TELEFONO accanto all'OPERATORE e' del chirurgo, anche
    con pochi numeri; "BIANCARDI X ROSSETTI"; "ROSSETTI" e "MARCO ROSSETTI"; le
    abbreviazioni delle prestazioni; "IL DOTTORE ANNULLA A D.D.D."."""
    S, C = mondo()
    righe_ = [[None, None, None, 'SALA A', None, None, None, None, None, None, None, None, 'SALA B'] + [None] * 7,
              ['GIORNO', None, 'ORA', 'INTERVENTO', 'OPERATORE', 'TELEFONO', 'MEDICO ANESTESISTA', 'PAZIENTE',
               'DEGENZA', 'RECAPITO PZ', 'IMPORTO', None, 'INTERVENTO', 'OPERATORE', 'TELEFONO',
               'MEDICO ANESTESISTA', 'PAZIENTE', 'DEGENZA', 'ASSICURAZIONE MEDICO', 'IMPORTO']]
    g = datetime.combine(MAR, time(0, 0))
    def riga(h, a=None, b=None):
        return ['MARTEDÌ', g, time(h, 0)] + (a or [None] * 8) + [None] + (b or [None] * 8)
    righe_ += [riga(8), riga(9, ['SOST. PROTESI CON  PESSI', 'COSTANZO', '3470009201', 'IZZO', 'CAPASSO LUIGIA', 'DH', 3470001001, None],
                        ['SOST, PROTESI +PESSI', 'AMENTA', None, 'IZZO', 'FERRARA LUCIA', None, 'UNISALUTE', 1200]),
               riga(10, ['ADDITIVA', 'BIANCARDI X ROSSETTI ', '3470009202', 'LANDOLFI', 'VALENTINA GRECO', 'DH', None, None]),
               riga(11, ['ADDITIVA', 'ROSSETTI', '3470009203', 'LANDOLFI', 'MARTINA SERRA', 'DH', 3470001002, None]),
               riga(12, ['ADDITIVA', 'MARCO ROSSETTI', '3470009203', 'LANDOLFI', 'IL.DOTTORE ANNULLA A D.D.D.', None, None, None]),
               riga(13)]
    a = importa.analizza(importa.leggi_file(xlsx([('OTTOBRE', righe_, ['D1:K1', 'M1:T1'])]), 'INTERVENTI.xlsx')[0])
    assert [x['nome'] for x in a['gruppi']] == ['SALA A', 'SALA B'], a['gruppi']
    per_nome = {a['intestazioni'][j]: a['campi'][p] for p, j in a['posizioni']}
    assert per_nome['TELEFONO'] == 'telefono_medico' and per_nome['RECAPITO PZ'] == 'telefono', per_nome
    assert per_nome['ASSICURAZIONE MEDICO'] == 'convenzione', per_nome
    s = S()
    piano = importa.prepara(s, a, importa.opzioni_da({'struttura': '1'}, a))
    medici = sorted((m['cognome'], m['nome']) for m in piano['nuovi_medici'])
    assert medici == [('Amenta', ''), ('Biancardi', ''), ('Costanzo', ''), ('Rossetti', 'Marco')], medici
    nomi = {p_['nome'] for p_ in piano['nuove_prestazioni']}
    assert nomi == {'Sost. protesi con pessi', 'Additiva'} or nomi == {'Sost, protesi +pessi', 'Additiva'}, nomi
    esito = importa.esegui(s, piano, 'INTERVENTI.xlsx')
    apps = s.scalars(select(Appuntamento).order_by(Appuntamento.inizio, Appuntamento.risorsa_id)).all()
    assert len(apps) == 5, len(apps)
    per_ora = {(x.inizio.hour, x.risorsa.nome): x for x in apps}
    capasso = per_ora[(9, 'Sala A')]
    assert capasso.paziente.telefono == '3470001001' and capasso.operatore.telefono == '3470009201'
    assert per_ora[(9, 'Sala B')].paziente.telefono in ('', None) and per_ora[(9, 'Sala B')].convenzione == 'UNISALUTE'
    assert capasso.prestazione_id == per_ora[(9, 'Sala B')].prestazione_id, 'due prestazioni per la stessa'
    sicc = per_ora[(10, 'Sala A')]
    assert sicc.operatore.cognome == 'Biancardi' and 'per conto di' in sicc.note and sicc.paziente.cognome == 'Greco'
    assert per_ora[(11, 'Sala A')].operatore_id == per_ora[(12, 'Sala A')].operatore_id, 'Rossetti due volte'
    annullato = per_ora[(12, 'Sala A')]
    assert annullato.stato == 'DISDETTO' and annullato.paziente_id is None and 'ANNULLA' in annullato.note
    assert esito['medici'] == 4
    s.close()


def im_agenda_di_una_giornata():
    """Il registro della dott.ssa: una giornata sola, la data scritta sopra la
    tabella, i posti vuoti gia' con il tipo di visita, una tabellina di
    riepilogo accanto, "Nome e Cognome" nell'intestazione, un posto bloccato."""
    S, C = mondo()
    iso = MAR.strftime('%d/%m/%Y')
    righe_ = [['REGISTRO APPUNTAMENTI AMBULATORIALI'], ['Dott.ssa Lippiello — %s' % iso], [],
              ['Medico:', 'Dott.ssa Lippiello', None, 'Data:', iso, None, 'Totale Slot:', 8, None, 'RIEPILOGO STATO', None],
              ['Orario Continuato:', '12:00 - 14:00', None, 'Durata visita:', '15 minuti', None, None, None, None, 'In attesa', 8],
              [None] * 9 + ['In corso', 0],
              ['Ora Inizio', 'Ora Fine', 'Paziente (Nome e Cognome)', 'Codice Fiscale / Tel.', 'Tipo Visita',
               'Stato Appuntamento', 'Note / Anamnesi Rapida', 'MAIL', None, 'Concluso', 0]]
    orari = ['12:00', '12:15', '12:30', '12:45', '13:00', '13:15', '13:30', '13:45', '14:00']
    pazienti_ = {2: ('ROBERTO PALUMBO', 3470002001, 'POST-OPERATORIO', 'R.PALUMBO@EXAMPLE.IT'),
                 3: ('?D.SSA LIPPIELLO BLOCCA ', None, 'INFILTRAZIONE', None),
                 4: ('AMARA DEI', '3470002002(FIGLIO)', 'CONTROLLO', 'AMARA _DEI@EXAMPLE.IT'),
                 5: ('ESPOSITO CARLA', 3470002003, 'DISDICE', None)}
    for k in range(8):
        paz, tel, nota, mail = pazienti_.get(k, (None, None, None, None))
        righe_.append([orari[k], orari[k + 1], paz, tel, ['Prima Visita', 'Controllo'][k % 2], 'In attesa', nota, mail,
                       None] + ([['Assente', 0], ['Annullato', 0]][k] if k < 2 else [None, None]))
    righe_.append([None, None, '4 PZ'])
    a = importa.analizza(importa.leggi_file(xlsx([('Ambulatorio', righe_, [])]), 'LIPPIELLO.xlsx')[0])
    assert a['data_foglio'] == MAR, a['data_foglio']
    assert set(a['campi'].values()) >= {'ora', 'ora_fine', 'cognome_nome', 'telefono', 'email', 'note'}
    assert 'extra' not in a['campi'].values() and 'durata' not in a['campi'].values(), a['campi']
    s = S()
    piano = importa.prepara(s, a, importa.opzioni_da({'struttura': '1', 'campo_g4': 'ignora'}, a))
    assert piano['medico_file'] is not None and piano['medico_file'].cognome == 'Lippiello'
    assert not piano['note_giorno'], 'i posti vuoti e il riepilogo non sono note del giorno: %s' % piano['note_giorno']
    righe = [r for r in piano['righe'] if r.get('inizio')]
    assert len(righe) == 4, [(r['n'], r['esito'], r['motivo']) for r in piano['righe']]
    # la stanza non si sa: righe scartate, che diventano appunti da confermare
    assert all(r['esito'] == 'scartato' and 'stanza' in r['motivo'] for r in righe)
    esito = importa.esegui(s, piano, 'LIPPIELLO.xlsx')
    assert esito['appuntamenti'] == 0 and esito['appunti'] == 4, esito
    ap = {x.ora.strftime('%H:%M'): x for x in s.scalars(select(Appunto))}
    assert ap['12:30'].paziente.cognome == 'Palumbo' and ap['12:30'].paziente.nome == 'Roberto'
    assert ap['12:30'].paziente.email == 'R.PALUMBO@EXAMPLE.IT' and ap['12:30'].durata_min == 15
    assert ap['12:45'].paziente_id is None and 'BLOCCA' in ap['12:45'].note
    assert ap['13:00'].paziente.cognome == 'Dei' and ap['13:00'].paziente.email == 'AMARA_DEI@EXAMPLE.IT'
    assert 'figlio' in ap['13:00'].note and ap['13:00'].paziente.telefono == '3470002002'
    assert all(x.operatore.cognome == 'Lippiello' and x.giorno == MAR and x.risorsa_id is None for x in ap.values())
    assert 'Manca la stanza' in ap['12:30'].testo and 'riga' in ap['12:30'].origine
    s.close()


def im_nomi_difficili():
    casi = {'DI NARDO': ('DI NARDO', ''), 'JENNYFER SERAFINI': ('SERAFINI', 'JENNYFER'),
            "ANTONYO D'ANDREA": ("D'ANDREA", 'ANTONYO'), 'DI NARDO M.ROSARIA': ('DI NARDO', 'M.ROSARIA'),
            'CAPUANO ANNARITA': ('CAPUANO', 'ANNARITA'), "MARIA D'AURIA": ("D'AURIA", 'MARIA'),
            "D'ANDREA ROBERTO": ("D'ANDREA", 'ROBERTO'), 'DE LUCA CIRO': ('DE LUCA', 'CIRO')}
    for testo, (c, n) in casi.items():
        trovato = importa.dividi_nome(testo)[:2]
        assert trovato == (c, n), (testo, trovato)
    # parentesi e note al posto del paziente
    avv = []
    p = importa._paziente_da({'cognome_nome': [('PAZIENTE', 'RUSSO LINA(ROSSI)', False)],
                              'telefono': [('TEL', '3470003001 (FIGLIA)', False)]}, {'maiuscole': True}, avv)
    assert (p['cognome'], p['nome']) == ('Russo', 'Lina') and '(ROSSI)' in p['annotazioni'], p
    assert 'telefono: figlia' in p['annotazioni'] and p['telefono'] == '3470003001', p
    for testo in ('?D.SSA LIPPIELLO BLOCCA', 'IL.DOTTORE ANNULLA A D.D.D.', 'RINVIATO'):
        p = importa._paziente_da({'cognome_nome': [('PAZIENTE', testo, False)]}, {}, [])
        assert not p['cognome'] and p['annotazioni'], (testo, p)
    # titolo con la barra, stanza con la "a" di "a partire"
    assert importa.nome_medico_nel_titolo('SALA ENDOSCOPIA - DR. GALASSO/VISITE OGNI ORA A PARTIRE DALLE 9') == 'GALASSO'
    assert importa.nome_medico_nel_titolo('x | Medico: Dott.ssa Lippiello | Data: 25/09/2026') == 'Lippiello'
    stanze = [SimpleNamespace(nome='Sala A'), SimpleNamespace(nome='Sala B'), SimpleNamespace(nome='Sala endoscopia')]
    assert importa.stanza_dal_titolo(stanze, 'SALA ENDOSCOPIA - DR. GALASSO/VISITE OGNI ORA A PARTIRE DALLE 9').nome == 'Sala endoscopia'
    assert importa.simile('Sost, protesi +pessi', 'SOSTITUZIONE PROTESI CON PESSI')
    assert not importa.simile('Rinoplastica', 'Rinosettoplastica')


prova('sale con una colonna diversa, telefono del chirurgo, medici e prestazioni riuniti', im_sale_con_una_colonna_diversa)
prova('registro di una giornata: data sopra, riepilogo accanto, stanza da confermare', im_agenda_di_una_giornata)
prova('nomi difficili, parentesi, note al posto del paziente, titoli', im_nomi_difficili)


# =====================================================================
area('appunti da confermare')


def ap_dal_file_alla_prenotazione():
    """Una riga in conflitto diventa un appunto; Prenota apre il modulo gia'
    compilato e, salvato, l'appunto si chiude con l'appuntamento."""
    S, C = mondo()
    I = ids(S)
    g = datetime.combine(MAR, time(0, 0))
    righe_ = [[None, 'SALA ENDOSCOPIA - DR. GALASSO/VISITE OGNI ORA'],
              ['GIORNO', None, 'ORA', 'PAZIENTE', 'TELEFONO', 'TIPO ESAME', 'NOTE', 'MAIL'],
              ['MARTEDÌ', g, time(9, 45), 'DI MARTINO ROSA', '3470004001', 'COLONSCOPIA', None, 'ROSA@EXAMPLE.IT'],
              [None, g, time(10, 0), 'DI MARTINO ROSA', '3470004001', 'EGDS', None, 'ROSA@EXAMPLE.IT'],
              [None, g, time(10, 0), 'CARUSO PAOLA', '3470004002', 'EGDS', 'PRIMA VOLTA', 'PAOLA@EXAMPLE.IT'],
              [None, g, time(10, 30), 'VITALE LUCA', '3470004003', 'COLONSCOPIA', 'DISDICE', None],
              [None, g, time(12, 0), 'SERAFINI?', None, None, None, None]]
    indirizzo, anteprima = importa_web(C, xlsx([('OTTOBRE', righe_, [])]), 'GALASSO.xlsx')
    t = html(anteprima)
    assert '</b> in conflitto (vanno fra i da confermare)' in t, re.findall(r'<li[^>]*><b>\d+</b>[^<]*', t)
    r = C.post(indirizzo, data={'azione': 'importa', 'struttura': '1'})
    t = html(r)
    assert 'Importazione completata' in t and 'da confermare</a>' in t, avvisi(C, r)
    s = S()
    forse = s.scalars(select(Appunto).where(Appunto.ora == time(12, 0))).one()
    assert 'da confermare' in forse.testo and forse.paziente.cognome == 'Serafini', forse.testo
    assert not s.scalars(select(Appuntamento).where(Appuntamento.inizio == datetime.combine(MAR, time(12, 0)))).all()
    s.delete(forse)
    s.commit()
    x = s.scalars(select(Appunto)).one()
    assert x.paziente.cognome == 'Caruso' and x.paziente.email == 'PAOLA@EXAMPLE.IT', x.paziente
    assert x.operatore.cognome == 'Galasso' and x.risorsa.nome == 'Sala endoscopia' and x.prestazione.nome == 'EGDS'
    assert x.ora == time(10, 0) and 'occupata' in x.testo and 'PRIMA VOLTA' in x.note, (x.testo, x.note)
    vitale = s.scalars(select(Appuntamento).join(Paziente).where(Paziente.cognome == 'Vitale')).one()
    assert vitale.stato == 'DISDETTO', 'DISDICE nelle note'
    xid, pid = x.id, x.paziente_id
    s.close()
    # la giornata lo mostra, il menu lo conta
    t = html(C.get('/giorno/%s?struttura=1' % MAR.isoformat()))
    assert 'Da confermare per questo giorno (1)' in t and 'appunto=%d' % xid in t
    assert re.search(r'Da confermare<span class="contatore">1</span>', t)
    # Prenota: il modulo gia' compilato
    t = html(C.get('/appuntamento?appunto=%d&data=%s&ora=10:00&risorsa=%d&struttura=1' % (xid, MAR.isoformat(), I['Sala endoscopia'])))
    assert 'value="Caruso"' in t and 'value="%d"' % pid in t and 'name="appunto" value="%d"' % xid in t
    assert re.search(r'<option value="%d"[^>]*selected' % I['Galasso'], t), 'medico non proposto'
    # alle 10:00 la sala e' occupata fino alle 10:30 (l'EGDS di Di Martino): si prenota alle 10:30,
    # libere perche' Vitale ha disdetto
    r = C.post('/appuntamento', data={'risorsa': I['Sala endoscopia'], 'operatore': I['Galasso'], 'prestazione': I['EGDS'],
                                      'data': MAR.isoformat(), 'ora': '10:30', 'durata': '15', 'paziente': 'Caruso',
                                      'nome_paziente': 'Paola', 'paziente_id': pid, 'telefono': '3470004002',
                                      'appunto': xid, 'struttura': '1'})
    assert r.status_code == 302, avvisi(C, r)
    assert 'Tolto dai da confermare' in avvisi(C)
    s = S()
    x = s.get(Appunto, xid)
    assert x.chiuso_il is not None and x.esito == 'PRENOTATO' and x.appuntamento_id is not None
    a = s.get(Appuntamento, x.appuntamento_id)
    assert a.paziente_id == pid and a.inizio.time() == time(10, 30)
    aid = a.id
    s.close()
    t = html(C.get('/giorno/%s?struttura=1' % MAR.isoformat()))
    assert 'Da confermare per questo giorno' not in t and 'class="contatore"' not in t
    # eliminato l'appuntamento, l'appunto resta chiuso ma senza legame
    C.post('/appuntamento/%d' % aid, data={'azione': 'elimina', 'struttura': '1'})
    s = S()
    assert s.get(Appunto, xid).appuntamento_id is None
    s.close()


def ap_a_mano_e_insieme():
    S, C = mondo()
    I = ids(S)
    # a mano: testo obbligatorio, dati sbagliati rifiutati, id inesistenti ignorati
    for dati, attesa in [({'testo': ''}, 'Serve'), ({'testo': 'x', 'giorno': '2027-02-30'}, 'Giorno non valido'),
                         ({'testo': 'x', 'ora': '25:99'}, 'Ora non valida'), ({'testo': 'x' * 1001}, 'Serve')]:
        C.post('/da-confermare', data=dati)
        assert attesa in avvisi(C), dati
    C.post('/da-confermare', data={'testo': 'Richiama per l\'orario', 'giorno': MAR.isoformat(), 'ora': '09:00',
                                   'operatore': I['Lippiello'], 'risorsa': 999, 'cognome': 'Serra', 'nome': 'Maria',
                                   'telefono': '3470005001', 'prestazione': I['Controllo']})
    C.post('/da-confermare', data={'testo': 'Stessa giornata', 'giorno': MAR.isoformat(), 'ora': '09:30',
                                   'operatore': I['Lippiello'], 'cognome': 'Provetti', 'telefono': '3470005002'})
    C.post('/da-confermare', data={'testo': 'Manca tutto', 'cognome': 'Senzadata'})
    occupante = nuovo_app(S, I['Ambulatorio 2'], I['Amato'], MAR, 9, 30, 30)
    s = S()
    tutti = s.scalars(select(Appunto).order_by(Appunto.id)).all()
    assert len(tutti) == 3 and tutti[0].risorsa_id is None and tutti[0].origine == 'inserito a mano'
    ids_ = [x.id for x in tutti]
    s.close()
    t = html(C.get('/da-confermare'))
    assert 'Senza giorno' in t and 'stanza da assegnare' in t and 'Richiama per l&#39;orario' in t
    # insieme nell'Ambulatorio 2: il secondo trova la stanza occupata, il terzo non ha giorno
    r = C.post('/da-confermare/prenota', data={'scelti': ids_, 'risorsa': I['Ambulatorio 2']})
    m = avvisi(C)
    assert '1 appuntamento messi' in m or '1 appuntamento' in m, m
    assert 'Provetti' in m and 'Senzadata' in m and 'mancano' in m, m
    s = S()
    x0, x1, x2 = (s.get(Appunto, i) for i in ids_)
    assert x0.esito == 'PRENOTATO' and x1.aperto and x2.aperto
    a = s.get(Appuntamento, x0.appuntamento_id)
    assert a.risorsa_id == I['Ambulatorio 2'] and a.operatore_id == I['Lippiello'] and a.fine - a.inizio == timedelta(minutes=20)
    assert a.paziente.cognome == 'Serra' and a.paziente.telefono == '3470005001' and a.prestazione.nome == 'Controllo'
    s.close()
    # chiudi, riapri, elimina; azioni sconosciute e id inesistenti: 404
    assert C.post('/da-confermare/%d/chiudi' % ids_[1]).status_code == 302
    s = S(); assert s.get(Appunto, ids_[1]).esito == 'SCARTATO'; s.close()
    C.post('/da-confermare/%d/riapri' % ids_[1])
    s = S(); assert s.get(Appunto, ids_[1]).aperto; s.close()
    assert C.post('/da-confermare/%d/vola' % ids_[1]).status_code == 404
    assert C.post('/da-confermare/99999/chiudi').status_code == 404
    C.post('/da-confermare/%d/elimina' % ids_[2])
    s = S(); assert s.get(Appunto, ids_[2]) is None; s.close()
    # nessuno scelto
    C.post('/da-confermare/prenota', data={})
    assert 'Nessun appunto' in avvisi(C)


def ap_notifiche_e_anagrafiche():
    S, C = mondo()
    I = ids(S)
    pid = crea_paz(S, cognome='Ferrara', nome='Lucia', telefono='3470006001')
    doppio = crea_paz(S, cognome='Ferrara', nome='Lucia', telefono='3470006009')
    s = S()
    s.add(Appunto(testo='Da richiamare', giorno=OGGI, ora=time(9, 0), operatore_id=I['Amato'], paziente_id=doppio))
    s.add(Appunto(testo='Per il mese prossimo', giorno=OGGI + timedelta(days=40), operatore_id=I['Amato']))
    s.commit()
    s.close()
    with A.app.test_request_context():
        n = segreteria.notifiche_di(S(), 1)
    voce = [x for x in n if x['titolo'] == 'Da confermare']
    assert len(voce) == 1 and voce[0]['testo'].startswith('1 appunto'), n
    # unire le schede sposta l'appunto; eliminare la scheda lo lascia con il nome
    s = S()
    PZ.unisci(s, s.get(Paziente, pid), s.get(Paziente, doppio))
    s.commit()
    x = s.scalars(select(Appunto).where(Appunto.testo == 'Da richiamare')).one()
    assert x.paziente_id == pid
    s.close()
    r = C.post('/pazienti/%d' % pid, data={'azione': 'elimina'})
    s = S()
    x = s.scalars(select(Appunto).where(Appunto.testo == 'Da richiamare')).one()
    if s.get(Paziente, pid) is None:
        assert x.paziente_id is None and x.cognome == 'Ferrara' and x.telefono == '3470006001', (x.cognome, x.telefono)
    s.close()
    # un medico con appunti non si elimina
    r = C.post('/anagrafiche/medici/%d' % I['Amato'], data={'azione': 'elimina'})
    s = S()
    assert s.get(Operatore, I['Amato']) is not None, 'medico con appunti eliminato'
    s.close()


prova('dal file alla prenotazione: conflitto, giornata, modulo compilato, chiusura', ap_dal_file_alla_prenotazione)
prova('a mano, controlli, prenotazione di piu\' appunti insieme', ap_a_mano_e_insieme)
prova('notifiche, unione ed eliminazione delle schede, medici', ap_notifiche_e_anagrafiche)


area('foglio del giorno e tema scuro')


def st_colonne_e_orientamento():
    S, C = mondo()
    I = ids(S)
    pid = crea_paz(S, cognome='Serra', nome='Maria', telefono='3470007001')
    nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], MAR, 9, 0, paziente=pid, note='porta gli esami',
              importo_cent=8000, extra=json.dumps({'Sedazione': 'Sì'}))
    def intestazioni(r):
        return re.findall(r'<th[^>]*>([^<]*)</th>', html(r).split('<thead>')[1].split('</thead>')[0])
    # di serie: tutte le colonne, orizzontale, una tabella per stanza
    r = C.get('/stampa/%s?struttura=1' % MAR.isoformat())
    assert intestazioni(r) == ['Ora', 'Paziente', 'Telefono', 'Prestazione', 'Medico', 'Tipo · convenzione',
                               'Importo', 'Sedazione', 'Note'], intestazioni(r)
    assert 'size: A4 portrait' not in html(r) and 'foglio-orizzontale' in html(r) and '<h2>Ambulatorio 1</h2>' in html(r)
    # scelte in Impostazioni: telefono e note, verticale, in ordine di ora
    r = C.post('/impostazioni', data={'azione': 'stampa', 'colonne': ['note', 'telefono', 'inventata'],
                                      'orientamento': 'verticale', 'ordine': 'ora'})
    assert r.status_code == 302 and r.headers['Location'].endswith('#stampa')
    assert 'salvate' in avvisi(C)
    t = html(C.get('/impostazioni'))
    assert re.search(r'value="telefono" checked', t) and not re.search(r'value="medico" checked', t)
    assert re.search(r'value="verticale" checked', t) and re.search(r'name="ordine" value="ora" checked', t)
    r = C.get('/stampa/%s?struttura=1' % MAR.isoformat())
    assert intestazioni(r) == ['Ora', 'Stanza', 'Paziente', 'Telefono', 'Note'], intestazioni(r)
    assert '@page { size: A4 portrait' in html(r) and 'foglio-verticale' in html(r)
    assert '3470007001' in html(r) and 'porta gli esami' in html(r) and '80,00' not in html(r) and 'Sì' not in html(r)
    # dalla pagina di stampa si cambia al volo, senza toccare le impostazioni
    r = C.get('/stampa/%s?struttura=1&orientamento=orizzontale&per=stanza' % MAR.isoformat())
    assert 'size: A4 portrait' not in html(r) and '<h2>Ambulatorio 1</h2>' in html(r)
    assert 'orientamento=orizzontale' not in html(r) or 'Foglio verticale' in html(r)
    r = C.get('/stampa/%s?struttura=1&orientamento=storto&per=boh' % MAR.isoformat())
    assert r.status_code == 200 and 'size: A4 portrait' in html(r)
    # nessuna colonna scelta: restano ora e paziente
    C.post('/impostazioni', data={'azione': 'stampa', 'orientamento': 'x', 'ordine': 'y'})
    r = C.get('/stampa/%s?struttura=1' % MAR.isoformat())
    assert intestazioni(r) == ['Ora', 'Paziente'] and 'size: A4 portrait' not in html(r), intestazioni(r)
    # un valore rovinato nel database: si torna a quello di serie
    for rovinato in ('{rotto', '[1, 2]', '{"colonne": "telefono", "orientamento": 5}'):
        s = S()
        scrivi_impostazione(s, 'stampa_giorno', rovinato)
        s.commit()
        s.close()
        r = C.get('/stampa/%s?struttura=1' % MAR.isoformat())
        assert r.status_code == 200 and len(intestazioni(r)) == 9, (rovinato, intestazioni(r))
        assert C.get('/impostazioni').status_code == 200


def st_tema_scuro():
    S, C = mondo()
    t = html(C.get('/giorno/%s?struttura=1' % MAR.isoformat()))
    assert 'tema-scuro.css' in t and "localStorage.getItem('gestionale-tema')" in t and 'if (false)' in t
    # i fogli da stampare restano chiari anche con il tema scuro
    I = ids(S)
    aid = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], MAR, 9, 0)
    for u in ('/stampa/%s?struttura=1' % MAR.isoformat(), '/appuntamento/%d/promemoria' % aid,
              '/agenda-medico/%s' % MAR.isoformat()):
        r = C.get(u)
        assert r.status_code == 200 and 'if (true)' in html(r), u
    t = html(C.get('/impostazioni'))
    assert all('name="tema" value="%s"' % v in t for v in ('chiaro', 'scuro', 'sistema'))
    css = C.get('/static/tema-scuro.css').get_data(as_text=True)
    assert css.count('@media screen') >= 2 and '@media print' not in css
    # il file generato e' allineato a stile.css: rigenerandolo non cambia
    import subprocess
    prima = open(os.path.join(CARTELLA, 'static', 'tema-scuro.css'), encoding='utf-8').read()
    subprocess.run([sys.executable, os.path.join(CARTELLA, 'strumenti', 'genera_tema_scuro.py')], check=True,
                   capture_output=True)
    dopo = open(os.path.join(CARTELLA, 'static', 'tema-scuro.css'), encoding='utf-8').read()
    assert prima == dopo, 'tema-scuro.css non rigenerato dopo una modifica di stile.css'
    # nessun fondo chiaro e nessun testo scuro resta nella parte generata
    generata = dopo.split('correzioni a mano')[0]
    assert not re.search(r'background[^;{}]*#(FFFFFF|F4F5F3|FFFBEA)', generata, re.I), 'fondo chiaro rimasto'
    assert not re.search(r'(?<![-\w])color:\s*#(16263F|46596A|5B6B75)', generata, re.I), 'testo scuro rimasto'


prova('foglio del giorno: colonne, orientamento, ordine, valori rovinati', st_colonne_e_orientamento)
prova('tema scuro: caricato, fogli da stampare chiari, file generato allineato', st_tema_scuro)


# =====================================================================
area('robustezza')


def ro_indirizzi_sporchi():
    S, C = mondo()
    I = ids(S)
    aid = nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], MAR, 9, 0)
    rnd = random.Random(99)
    sporchi = ['0', '-1', '99999999999999999999999', 'abc', '%00', "1'--", '1.5', '../1', '%E2%80%AE']
    modelli_url = ['/chiusura/%s', '/cassa/%s', '/cassa/mese/%s', '/cassa/mese/%s/excel', '/agenda-medico/%s',
                   '/attesa/%s', '/attesa/per/%s', '/appuntamento/%s/sposta', '/serie/%s', '/documenti/%s',
                   '/appuntamento/%s/modulo/1', '/moduli/%s', '/importa/%s', '/importa/%s/scarti.xlsx',
                   '/sposta?medico=%s&dal=%s', '/cerca-tutto.json?q=%s', '/notifiche.json?struttura=%s',
                   '/attesa?medico=%s', '/sposta/avvisi?ids=%s', '/appuntamento?appunto=%s', '/da-confermare?struttura=%s']
    n = 0
    for u in modelli_url:
        for x in sporchi:
            indirizzo = u % ((x,) * u.count('%s'))
            r = C.get(indirizzo)
            assert r.status_code in (200, 302, 404), '%s -> %d' % (indirizzo, r.status_code)
            n += 1
    posts = ['/chiusura/%s' % MAR, '/note-giorno', '/cose-da-fare', '/attesa/nuova', '/sposta',
             '/appuntamento/%d/sposta' % aid, '/appuntamento/%d/pagamento' % aid, '/cassa/listino', '/moduli/nuovo',
             '/importa', '/cose-da-fare/1/fatto', '/serie/abcdef12', '/da-confermare', '/da-confermare/prenota',
             '/da-confermare/1/chiudi', '/da-confermare/1/riapri', '/impostazioni']
    campi = ['azione', 'scelti', 'struttura', 'data', 'testo', 'per_il', 'medico', 'dal', 'al', 'modo', 'inizio',
             'risorsa', 'metodo', 'importo', 'prestazione', 'convenzione', 'tariffa', 'nome', 'paziente_id', 'operatore',
             'fascia', 'entro', 'sostituto', 'torna', 'giorno', 'ora', 'cognome', 'telefono', 'appunto',
             'colonne', 'orientamento', 'ordine']
    valori = sporchi + ['', 'x' * 5000, '2027-02-30', '2027-01-01T25:00', 'CONTANTI', 'annulla', 'arrivati', 'esempio',
                        'elimina', 'sostituto', '<script>', 'stampa',
                        'verticale', 'orizzontale', 'telefono', 'note']
    for giro in range(400):
        dati = {rnd.choice(campi): rnd.choice(valori) for _ in range(rnd.randint(1, 8))}
        u = rnd.choice(posts)
        r = C.post(u, data=dati)
        assert r.status_code in (200, 302, 404), '%s %s -> %d' % (u, dati, r.status_code)
        n += 1
    return '%d richieste' % n


def ro_import_file_strani():
    S, C = mondo()
    for dati, nome in [(b'', 'vuoto.xlsx'), (b'PK\x03\x04rotto', 'rotto.xlsx'), (b'\xd0\xcf\x11\xe0', 'vecchio.xls'),
                       (b'solo una riga', 'uno.csv'), ('é;à\n'.encode('utf-16'), 'strano.csv'), (b'x' * 100, 'dati.bin')]:
        r = C.post('/importa', data={'file': (io.BytesIO(dati), nome)}, content_type='multipart/form-data')
        assert r.status_code in (302, 200), '%s -> %d' % (nome, r.status_code)
        if r.status_code == 302 and '/importa/' in r.headers['Location'] and r.headers['Location'] != '/importa':
            r2 = C.get(r.headers['Location'])
            assert r2.status_code in (200, 302), '%s anteprima -> %d' % (nome, r2.status_code)
        avvisi(C)
    # un'importazione vuota da confermare non rompe niente
    righe_ = [['Cognome', 'Telefono']] + [[None, None]] * 3
    dati = xlsx([('F', righe_, [])])
    r = C.post('/importa', data={'file': (io.BytesIO(dati), 'vuota.xlsx')}, content_type='multipart/form-data')
    if r.status_code == 302 and r.headers['Location'].startswith('/importa/'):
        r = C.post(r.headers['Location'], data={'azione': 'importa'})
        assert r.status_code in (200, 302)
    assert C.get('/importa/%s' % ('a' * 32)).status_code == 302, 'token sconosciuto'


prova('indirizzi sporchi e moduli a caso sulle pagine nuove: mai errore 500', ro_indirizzi_sporchi)
prova('file strani da importare', ro_import_file_strani)


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
    print('\n%d prove totali, %d superate, %d da sistemare' % (
        len(esiti), len(esiti) - len(rotte), len(rotte)))
    shutil.rmtree(PROVVISORIA, ignore_errors=True)
    sys.exit(1 if rotte else 0)
