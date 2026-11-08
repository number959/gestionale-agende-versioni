# -*- coding: utf-8 -*-
"""Prove della 1.9: Dove si fa.

La lettura del database delle prestazioni (il file Excel del gruppo, anche
scritto in modi diversi, con i suoi errori), l'importazione e le versioni
nuove del file (le prestazioni tengono il loro id, i recapiti scritti nel
programma restano, il registro non si perde), la ricerca confrontata con un
oracolo scritto qui (ogni risultato contiene tutte le parole cercate, ogni
prestazione si trova con l'inizio delle sue parole), le pagine e le richieste
(scheda della struttura, messaggio e collegamenti per il paziente, registro,
Excel, statistiche, ricerca rapida, protezioni) e l'aggiornamento del database
dalla versione 9. Strutture, prestazioni e pazienti sono inventati."""
import json
import os
import random
import re
import shutil
import sqlite3
import sys
import time as orologio
import traceback
import unicodedata
from datetime import date, datetime, timedelta
from html import unescape
from io import BytesIO
from urllib.parse import unquote

import logging
logging.getLogger().setLevel(logging.CRITICAL)

from sqlalchemy import select

import servizi
import viste
import pazienti
import dovesifa as DS
import app as A
from modelli import (crea_sessione, VERSIONE_SCHEMA, Struttura, Prestazione, Paziente, StrutturaGruppo, VoceCatalogo,
                     SedeVoce, Indirizzato, Appuntamento, leggi_impostazione)

CARTELLA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(CARTELLA, 'strumenti'))
import catalogo_prova as CP  # noqa: E402

A.app.config['TESTING'] = True
PROVVISORIA = os.path.join(CARTELLA, 'prove_19_tmp')
shutil.rmtree(PROVVISORIA, ignore_errors=True)
os.makedirs(PROVVISORIA)
esiti, _area, _n = [], [''], [0]
SOLO = [x for x in os.environ.get('PROVE_SOLO', '').split(',') if x]
NOMI = {sigla: nome for sigla, nome, _ in CP.STRUTTURE}


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


# ================================================================ il mondo
def percorso_nuovo(nome='db'):
    _n[0] += 1
    dove = os.path.join(PROVVISORIA, 'm%d' % _n[0])
    os.makedirs(dove)
    return os.path.join(dove, '%s.db' % nome)


def mondo(catalogo=False, nome='Clinica Posillipo'):
    """Un gestionale nuovo (la struttura si chiama come una del database di
    prova, per il segno «qui»), con due pazienti inventati e, se richiesto, il
    database delle prestazioni di prova gia' importato."""
    S = crea_sessione('sqlite:///' + percorso_nuovo())
    s = S()
    servizi.prepara_primo_avvio(s, nome)
    s.add(Prestazione(nome='Visita cardiologica', durata_min=30))
    s.add_all([Paziente(cognome='Fittizi', nome='Ada', sesso='F', telefono='333 000 1111', email='ada.fittizi@example.com'),
               Paziente(cognome='Esempio', nome='Bruno', sesso='M', telefono='081 000 2222')])
    s.commit()
    s.close()
    A.Sessione = S
    A._registro = None
    viste._sessionmaker = lambda: S
    if catalogo:
        importa_file(S, CP.libro())
    return S, A.app.test_client()


def importa_file(S, dati, nome='prova.xlsx'):
    s = S()
    try:
        esito = DS.importa_catalogo(s, DS.leggi_database(dati, nome))
        s.commit()
        return esito
    finally:
        s.close()


def html(r):
    return r.get_data(as_text=True)


def testo(r):
    return ' '.join(unescape(re.sub(r'<[^>]+>', ' ', html(r))).split())


def avvisi(C):
    with C.session_transaction() as sess:
        m = sess.get('_flashes', [])
        sess['_flashes'] = []
    return ' '.join(unescape(t) for _, t in m)


def libro_fatto(fogli):
    """Un file .xlsx da {nome del foglio: [righe]}."""
    import openpyxl
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for nome, righe in fogli.items():
        ws = wb.create_sheet(nome)
        for r in righe:
            ws.append(r)
    b = BytesIO()
    wb.save(b)
    return b.getvalue()


def per_nome(letto):
    return {v['nome']: v for v in letto['voci']}


def gruppo(S):
    s = S()
    try:
        return {g.nome: g.id for g in s.scalars(select(StrutturaGruppo))}
    finally:
        s.close()


def voci(S):
    s = S()
    try:
        return {v.nome: v.id for v in s.scalars(select(VoceCatalogo))}
    finally:
        s.close()


def nomi_trovati(S, q, branca='', limite=10000):
    s = S()
    try:
        e = DS.cerca(s, q, branca, limite)
        return [v['nome'] for v in e['risultati']], e
    finally:
        s.close()


# ================================================================ lettura del file
area('lettura del database delle prestazioni')


def l_base():
    """Il file di prova: fogli giusti, strutture nell'ordine, ogni X al suo
    posto (oracolo: la tabella di catalogo_prova), recapiti del foglio Strutture."""
    letto = DS.leggi_database(CP.libro(), 'prova.xlsx')
    assert letto['foglio'] == 'DATABASE PRESTAZIONI', letto['foglio']
    assert letto['strutture'] == [n for _, n, _ in CP.STRUTTURE], letto['strutture']
    assert len(letto['voci']) == len(CP.VOCI), len(letto['voci'])
    v = per_nome(letto)
    for branca, nome, sinonimi, dove, nota in CP.VOCI:
        x = v[nome]
        assert x['branca'] == branca and x['sinonimi'] == sinonimi, (nome, x['branca'], x['sinonimi'])
        assert set(x['sedi']) == {NOMI[s] for s in dove.split()}, (nome, set(x['sedi']))
    assert sorted(letto['recapiti']) == sorted(n for _, n, r in CP.STRUTTURE if r), sorted(letto['recapiti'])
    assert letto['recapiti']['Centro Nord']['sito'] == 'https://www.example.it/centro-nord/prenota'
    assert letto['recapiti']['Centro Nord']['telefono2'] == '333 000 0011'
    assert letto['avvisi'] == ['Prestazioni senza nessuna X, che nella ricerca compaiono «in nessuna struttura»: 1 '
                               '(per esempio «Consulenza psicologica»).'], letto['avvisi']
    # senza titolo sopra le intestazioni e senza gli altri fogli: lo stesso
    altro = DS.leggi_database(CP.libro(titolo=False, altri_fogli=False, con_recapiti=False))
    assert [(x['nome'], sorted(x['sedi'])) for x in altro['voci']] == \
        [(x['nome'], sorted(x['sedi'])) for x in letto['voci']]
    assert altro['recapiti'] == {}


def l_note():
    """Le note: il pezzo «SIGLA: …» va alla sua struttura (se li' la prestazione
    si fa), «da confermare»/«da verificare» la segnano; il resto resta sulla
    prestazione."""
    letto = DS.leggi_database(CP.libro())
    v = per_nome(letto)
    assert v['Ecografia renale']['sedi']['Clinica Collina'] == {'da_confermare': True, 'nota': CP.DC}
    assert v['Ecografia renale']['sedi']['Centro Sud'] == {'da_confermare': False, 'nota': ''}
    assert v['Ecografia tiroide']['sedi']['Poliambulatorio Mare'] == \
        {'da_confermare': False, 'nota': 'nel suo listino «Ecografia del collo»'}
    assert v['Test da sforzo']['sedi']['Centro Nord']['da_confermare'] is True
    assert all(x['note'] == '' for x in letto['voci']), [x['note'] for x in letto['voci'] if x['note']]
    strutture = [('CN', 'Centro Nord', None), ('CVF', 'Casa Verde Fiume', None), ('PM', 'Poliambulatorio Mare', None)]
    righe = [('DIAGNOSTICA PER IMMAGINI', 'Isterosonografia', '', 'CVF PM',
              "CVF: chiamata 'sonoisterografia' nel listino, da verificare; PM: chiamata 'isterosonografia 3D'"),
             ('DIAGNOSTICA PER IMMAGINI', 'Ecografia anca', '', 'CN', 'PM: da confermare; nota per tutti'),
             ('DIAGNOSTICA PER IMMAGINI', 'Ecografia gomito', '', 'CN', 'Centro Nord: in sede da gennaio')]
    letto = DS.leggi_database(CP.libro(voci=righe, strutture=strutture, con_recapiti=False, altri_fogli=False))
    v = per_nome(letto)
    assert v['Isterosonografia']['sedi']['Casa Verde Fiume'] == \
        {'da_confermare': True, 'nota': "chiamata 'sonoisterografia' nel listino, da verificare"}, v['Isterosonografia']
    assert v['Isterosonografia']['sedi']['Poliambulatorio Mare']['da_confermare'] is False
    # la sigla di una struttura dove la prestazione non si fa, e il testo senza sigla, restano sulla prestazione
    assert v['Ecografia anca']['note'] == 'PM: da confermare; nota per tutti', v['Ecografia anca']['note']
    assert v['Ecografia anca']['sedi']['Centro Nord']['da_confermare'] is False
    # anche il nome intero vale come sigla
    assert v['Ecografia gomito']['sedi']['Centro Nord']['nota'] == 'in sede da gennaio'
    assert DS.sigle('Casa di cura Collina') >= {'cdcc', 'ccc', 'casa di cura collina'}


def l_segni():
    """Quello che vale come «si fa» (X, x, Sì, 1, ✓) e come «no» (vuoto, no, -, 0);
    una colonna con altro si salta con un avviso, Codice e Tariffa senza avviso."""
    righe = [['Branca', 'Prestazione', 'Codice', 'Struttura A', 'Struttura B', 'Struttura C', 'Tariffa', 'Strana', 'Note'],
             ['CARDIOLOGIA', 'Visita cardiologica', '89.7', 'X', 'x', None, 80, 'X', None],
             ['CARDIOLOGIA', 'Holter ECG', '89.50', 'Sì', 0, '✓', 120, 'forse', None],
             ['CARDIOLOGIA', 'Holter pressorio', '89.61', 1, 'no', '-', 90, None, None],
             [None, None, None, None, None, None, None, None, None],
             ['CARDIOLOGIA', None, None, 'X', None, None, None, None, None],
             ['CARDIOLOGIA', 'visita  CARDIOLOGICA', None, None, None, 'X', None, None, None]]
    letto = DS.leggi_database(libro_fatto({'Foglio1': righe}))
    assert letto['strutture'] == ['Struttura A', 'Struttura B', 'Struttura C'], letto['strutture']
    v = per_nome(letto)
    assert sorted(v) == ['Holter ECG', 'Holter pressorio', 'Visita cardiologica'], sorted(v)
    assert set(v['Visita cardiologica']['sedi']) == {'Struttura A', 'Struttura B', 'Struttura C'}   # le due righe unite
    assert set(v['Holter ECG']['sedi']) == {'Struttura A', 'Struttura C'}
    assert set(v['Holter pressorio']['sedi']) == {'Struttura A'}
    tutti = ' '.join(letto['avvisi'])
    assert 'Colonna «Strana» ignorata' in tutti and 'forse' in tutti, tutti
    assert 'Codice' not in tutti and 'Tariffa' not in tutti, tutti
    assert 'Righe senza il nome della prestazione, saltate: 1' in tutti, tutti
    assert 'scritte due volte, unite in una: 1' in tutti, tutti


def l_errori():
    """File sbagliati: il motivo in parole semplici, niente importato."""
    casi = [(b'non sono un file excel', 'non si apre come foglio Excel'),
            (libro_fatto({'Foglio1': [['Nome', 'Cognome'], ['Ada', 'Fittizi']]}), 'non c\'è un foglio con le colonne'),
            (libro_fatto({'Foglio1': [['Branca', 'Prestazione', 'Note'], ['CARDIOLOGIA', 'Holter', '']]}),
             'nessuna colonna di struttura'),
            (libro_fatto({'Foglio1': [['Branca', 'Prestazione', 'Struttura A']]}), 'non ci sono prestazioni')]
    for dati, parole in casi:
        try:
            DS.leggi_database(dati)
        except DS.ErroreDatabase as e:
            assert parole in str(e), (parole, str(e))
        else:
            raise AssertionError('accettato: %s' % parole)
    # nomi troppo lunghi: tagliati alle misure del database, non un errore
    lungo = 'Prestazione ' + 'molto ' * 60
    letto = DS.leggi_database(libro_fatto({'DB': [['Branca', 'Prestazione', 'S' * 120], ['B' * 100, lungo, 'X']]}))
    assert len(letto['strutture'][0]) == 80 and len(letto['voci'][0]['nome']) == 160 and len(letto['voci'][0]['branca']) == 80


def l_recapiti():
    """Il foglio Strutture: solo le strutture del database, email e prenotazione
    online controllate (un indirizzo javascript: non passa)."""
    strutture = [('CN', 'Centro Nord', {'telefono': '0823 000 011', 'email': 'non-una-email', 'sito': 'javascript:alert(1)'}),
                 ('CS', 'Centro Sud', {'indirizzo': 'Corso Prova 25', 'sito': 'https://www.example.it/cs'})]
    dati = CP.libro(voci=[('CARDIOLOGIA', 'Holter ECG', '', 'CN CS', '')], strutture=strutture)
    import openpyxl
    wb = openpyxl.load_workbook(BytesIO(dati))
    wb['Strutture'].append(['Struttura Inventata', 'Via Nessuna 1'])
    b = BytesIO()
    wb.save(b)
    letto = DS.leggi_database(b.getvalue())
    assert letto['recapiti'] == {'Centro Nord': {'telefono': '0823 000 011'},
                                 'Centro Sud': {'indirizzo': 'Corso Prova 25', 'sito': 'https://www.example.it/cs'}}, \
        letto['recapiti']
    tutti = ' '.join(letto['avvisi'])
    for x in ('email di «Centro Nord» non valida', 'prenotazione online di «Centro Nord» non valido',
              '«Struttura Inventata» non è fra le strutture'):
        assert x in tutti, (x, tutti)
    assert DS.sito_valido('https://www.example.it/x') and DS.sito_valido('http://example.it')
    for x in ('javascript:alert(1)', 'www.example.it', 'https://', 'https://exa mple.it', 'ftp://example.it',
              'https://example.it/' + 'x' * 300):
        assert not DS.sito_valido(x), x


prova('il file di prova: fogli, strutture, X, sinonimi e recapiti come nella tabella di partenza', l_base)
prova('note per struttura: sigle, «da confermare», «da verificare», il resto sulla prestazione', l_note)
prova('segni nelle celle, colonne da saltare, righe vuote, senza nome e doppie', l_segni)
prova('file sbagliati: il motivo in parole semplici; nomi lunghi tagliati', l_errori)
prova('foglio Strutture: solo strutture del database, email e siti controllati', l_recapiti)


# ================================================================ importazione
area('importazione e versioni nuove del file')


def i_prima():
    S, C = mondo()
    esito = importa_file(S, CP.libro())
    assert esito == {'aggiunte': len(CP.VOCI), 'tolte': 0, 'voci': len(CP.VOCI), 'strutture': len(CP.STRUTTURE)}, esito
    s = S()
    g = {x.nome: x for x in s.scalars(select(StrutturaGruppo))}
    assert list(g) == [n for _, n, _ in CP.STRUTTURE]
    assert len({x.colore for x in g.values()}) == len(g), 'due strutture con lo stesso colore'
    # la struttura con il nome di questo gestionale e' lei; le altre no
    assert g['Clinica Posillipo'].struttura_id == s.scalars(select(Struttura)).first().id
    assert all(x.struttura_id is None for n, x in g.items() if n != 'Clinica Posillipo')
    assert g['Centro Nord'].telefono == '0823 000 011' and g['Centro Nord'].citta == 'Caserta'
    assert g['Diagnostica Lago'].con_recapiti is False and g['Centro Sud'].con_recapiti is True
    n_sedi = s.query(SedeVoce).count()
    assert n_sedi == sum(len(v[3].split()) for v in CP.VOCI), n_sedi
    info = DS.info_catalogo(s)
    assert info['file'] == 'prova.xlsx' and info['voci'] == len(CP.VOCI) and info['strutture'] == 6, info
    assert leggi_impostazione(s, 'catalogo_versione'), 'versione del catalogo non scritta'
    s.close()


def i_versione_nuova():
    """Una versione nuova del file: tolte, aggiunte, cambiate di branca e di
    sedi; stessi id per gli stessi nomi; il registro resta leggibile."""
    S, C = mondo(catalogo=True)
    prima = voci(S)
    G = gruppo(S)
    s = S()
    v_tolta = s.get(VoceCatalogo, prima['Tecarterapia'])
    s.add(Indirizzato(gruppo_id=G['Clinica Collina'], gruppo_nome='Clinica Collina', voce_id=v_tolta.id,
                      prestazione=v_tolta.nome, branca=v_tolta.branca, canale='telefono'))
    # recapiti scritti nel programma: la versione nuova del file non li cambia
    x = s.get(StrutturaGruppo, G['Centro Nord'])
    x.telefono = '0823 999 999'
    x.note = 'chiedere di Ada'
    s.commit()
    s.close()
    nuove = [v for v in CP.VOCI if v[1] not in ('Tecarterapia', 'Igiene dentale')]
    nuove = [(('CARDIOLOGIA' if v[1] == 'Ecocardiogramma' else v[0]), v[1], v[2],
              ('CS' if v[1] == 'RM spalla' else v[3]), v[4]) for v in nuove]
    nuove.append(('DIAGNOSTICA PER IMMAGINI', 'RM caviglia', 'risonanza caviglia', 'DL', ''))
    dati = CP.libro(voci=nuove)
    s = S()
    diff = DS.confronto(s, DS.leggi_database(dati))
    s.close()
    assert diff['aggiunte'] == ['RM caviglia'] and diff['tolte'] == ['Igiene dentale', 'Tecarterapia'], diff
    assert diff['spostate'] == ['Ecocardiogramma'] and not diff['primo'] and not diff['sparite'], diff
    esito = importa_file(S, dati)
    assert esito['aggiunte'] == 1 and esito['tolte'] == 2, esito
    dopo = voci(S)
    assert all(dopo[n] == i for n, i in prima.items() if n in dopo), 'gli id delle prestazioni sono cambiati'
    assert 'Tecarterapia' not in dopo and 'RM caviglia' in dopo
    s = S()
    r = s.scalars(select(Indirizzato)).one()
    assert r.voce_id is None and r.prestazione == 'Tecarterapia', (r.voce_id, r.prestazione)
    spalla = s.get(VoceCatalogo, dopo['RM spalla'])
    assert [x.struttura.nome for x in spalla.sedi] == ['Centro Sud'], [x.struttura.nome for x in spalla.sedi]
    cn = s.get(StrutturaGruppo, G['Centro Nord'])
    assert (cn.telefono, cn.note, cn.citta) == ('0823 999 999', 'chiedere di Ada', 'Caserta')
    s.close()
    trovati, _ = nomi_trovati(S, 'caviglia')
    assert trovati == ['RM caviglia'], trovati


def i_strutture():
    """Una struttura che sparisce dal file resta (con i recapiti) ma senza
    prestazioni; quando torna e' la stessa. Una struttura spenta non si propone."""
    S, C = mondo(catalogo=True)
    G = gruppo(S)
    senza = [s for s in CP.STRUTTURE if s[0] != 'PM']
    importa_file(S, CP.libro(strutture=senza))
    s = S()
    pm = s.get(StrutturaGruppo, G['Poliambulatorio Mare'])
    assert pm.nel_database is False and pm.telefono == '081 000 0033'
    assert s.query(SedeVoce).filter_by(struttura_id=pm.id).count() == 0
    s.close()
    s = S()
    assert 'Poliambulatorio Mare' in DS.confronto(s, DS.leggi_database(CP.libro()))['strutture'][3]['nome']
    s.close()
    importa_file(S, CP.libro())
    s = S()
    pm = s.get(StrutturaGruppo, G['Poliambulatorio Mare'])
    assert pm.nel_database is True and s.query(SedeVoce).filter_by(struttura_id=pm.id).count() > 0
    assert gruppo(S) == G, 'strutture nuove al posto di quelle di prima'
    s.close()
    # spenta dai recapiti: sparisce dalle ricerche, riaccesa torna
    r = C.post('/dove-si-fa/strutture/%d' % G['Poliambulatorio Mare'], data={'telefono': '081 000 0033'})
    assert r.status_code == 302, r.status_code
    _, e = nomi_trovati(S, 'visita odontoiatrica')
    assert e['risultati'][0]['sedi'] == [], e['risultati'][0]['sedi']
    C.post('/dove-si-fa/strutture/%d' % G['Poliambulatorio Mare'], data={'telefono': '081 000 0033', 'attiva': '1'})
    _, e = nomi_trovati(S, 'visita odontoiatrica')
    assert [x[0] for x in e['risultati'][0]['sedi']] == [G['Poliambulatorio Mare']]


def i_pagina():
    """Dalla pagina: caricamento, anteprima, conferma con la copia di sicurezza."""
    S, C = mondo()
    t = testo(C.get('/dove-si-fa/'))
    assert 'Manca il database delle prestazioni' in t, t[:300]
    r = C.post('/dove-si-fa/strutture', data={'file': (BytesIO(CP.libro()), 'database.xlsx')},
               content_type='multipart/form-data')
    assert r.status_code == 302 and '/dove-si-fa/strutture/importa/' in r.headers['Location'], r.status_code
    anteprima = r.headers['Location']
    t = testo(C.get(anteprima))
    for x in ('Il database delle prestazioni', '%d prestazioni' % len(CP.VOCI), 'Centro Nord', 'nuova',
              'Importa il database', 'Prima si fa una copia di sicurezza'):
        assert x in t, (x, t[:600])
    assert not voci(S), 'importato prima della conferma'
    r = C.post(anteprima, data={'azione': 'importa'})
    assert r.status_code == 302 and r.headers['Location'].endswith('/dove-si-fa/strutture'), r.headers.get('Location')
    assert 'Database delle prestazioni importato: %d prestazioni in 6 strutture' % len(CP.VOCI) in avvisi(C)
    assert len(voci(S)) == len(CP.VOCI)
    cartella = os.path.join(os.path.dirname(S.motore.url.database), 'backup')
    assert any('prima-del-database-prestazioni' in f for f in os.listdir(cartella)), os.listdir(cartella)
    # il file caricato non resta: il token non vale piu'
    C.get(anteprima)
    assert 'non c\'è più' in avvisi(C)
    # file sbagliato, troppo grande, token finto o di un'altra importazione
    r = C.post('/dove-si-fa/strutture', data={'file': (BytesIO(b'ciao'), 'x.xlsx')}, content_type='multipart/form-data')
    assert r.status_code == 302 and 'non si apre come foglio Excel' in avvisi(C)
    r = C.post('/dove-si-fa/strutture', data={'file': (BytesIO(b'0' * (10 * 1024 * 1024 + 5)), 'x.xlsx')},
               content_type='multipart/form-data')
    assert r.status_code == 302 and 'supera 10 MB' in avvisi(C)
    r = C.post('/dove-si-fa/strutture', data={}, content_type='multipart/form-data')
    assert 'Scegliere il file Excel' in avvisi(C)
    assert C.get('/dove-si-fa/strutture/importa/../../x').status_code == 404
    assert C.get('/dove-si-fa/strutture/importa/nonesadecimale').status_code == 404
    C.get('/dove-si-fa/strutture/importa/' + 'a' * 32)
    assert 'non c\'è più' in avvisi(C)
    import importa as caricamenti
    token = 'b' * 32
    with open(caricamenti.percorso_caricato(token), 'wb') as f:
        f.write(CP.libro())
    with open(caricamenti.percorso_caricato(token, '.json'), 'w', encoding='utf-8') as f:
        json.dump({'nome': 'rubrica.xlsx', 'tipo': 'pazienti'}, f)
    r = C.post('/dove-si-fa/strutture/importa/' + token, data={'azione': 'importa'})
    assert r.status_code == 302 and 'non c\'è più' in avvisi(C), 'importato un file di un\'altra importazione'


def i_backup_rotto():
    """Se la copia di sicurezza non riesce, niente si importa."""
    import backup
    S, C = mondo()
    r = C.post('/dove-si-fa/strutture', data={'file': (BytesIO(CP.libro()), 'database.xlsx')},
               content_type='multipart/form-data')
    vero = backup.esegui
    backup.esegui = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('disco pieno'))
    try:
        C.post(r.headers['Location'], data={'azione': 'importa'})
    finally:
        backup.esegui = vero
    assert 'il backup di sicurezza non è riuscito (disco pieno)' in avvisi(C)
    assert not voci(S)


prova('prima importazione: strutture, colori, «qui» per nome, recapiti, info', i_prima)
prova('versione nuova del file: cosa cambia, stessi id, recapiti scritti e registro restano', i_versione_nuova)
prova('strutture che spariscono e tornano, strutture spente', i_strutture)
prova('dalla pagina: caricamento, anteprima, conferma, copia di sicurezza, file sbagliati', i_pagina)
prova('copia di sicurezza non riuscita: niente importato', i_backup_rotto)


# ================================================================ ricerca
area('ricerca')
VOCALI = 'aeiou'


def norma(t):
    t = unicodedata.normalize('NFKD', t or '')
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in t if not unicodedata.combining(c)).lower()).split())


def parole_oracolo(t):
    unite = [norma(m).replace(' ', '') for m in re.findall(r'\w+(?:-\w+)+', t or '')]
    return norma(t).split() + unite


def corrisponde(parola, w):
    """La regola, scritta qui di nuovo: l'inizio della parola; senza la vocale
    finale per le parole lunghe; per quelle di quattro lettere anche il
    singolare o il plurale ('mani' e 'mano')."""
    if w.startswith(parola):
        return True
    if len(parola) > 4 and parola[-1] in VOCALI and w.startswith(parola[:-1]):
        return True
    return len(parola) == 4 and parola[3] in VOCALI and parola[:3].isalpha() and len(w) == 4 and \
        w[:3] == parola[:3] and w[3] in VOCALI


def contiene_tutte(v, q):
    piene = [p for p in norma(q).split() if (len(p) >= 2 or p.isdigit()) and p not in DS.PAROLE_VUOTE]
    if not piene:
        piene = [p for p in norma(q).split() if len(p) >= 2 and p not in ('fare', 'esame', 'esami')]
    tutte = parole_oracolo(v['nome']) + parole_oracolo(', '.join(v['sinonimi'])) + norma(v['branca']).split()
    return all(any(corrisponde(a, w) for a in DS.ESPANSIONI.get(p, [p]) for w in tutte) for p in piene)


ATTESI = [
    ('risonanza ginocchio', ['RM ginocchio', 'RM ginocchio con mezzo di contrasto']),
    ('RM GINOCCHIO', ['RM ginocchio', 'RM ginocchio con mezzo di contrasto']),
    ('tac torace', ['TC torace', 'TC torace con mezzo di contrasto']),
    ('eco addome', ['Ecografia addome completo']),
    ('holter', ['Holter ECG', 'Holter pressorio']),
    ('lastra mani', ['Radiografia mano']),
    ('eco reni', ['Ecografia renale']),
    ('rm lombare', ['RM rachide lombo-sacrale']),
    ('lombosacrale', ['RM rachide lombo-sacrale']),
    ('nei', ['Mappatura dei nei in epiluminescenza']),
    ('esami del sangue', ['Analisi di laboratorio']),
    ('prelievo', ['Analisi di laboratorio']),
    ('ÈCOGRAFIA   tiroide', ['Ecografia tiroide']),
    ('dentista', ['Visita odontoiatrica', 'Igiene dentale']),
    ('psicologo', ['Consulenza psicologica']),
    ('egds', ['Gastroscopia (EGDS)']),
    ('moc', ['Densitometria ossea (MOC)']),
]


def r_attesi():
    S, C = mondo(catalogo=True)
    for q, attesi in ATTESI:
        trovati, e = nomi_trovati(S, q)
        assert sorted(trovati) == sorted(attesi), (q, trovati)
        assert e['corretta'] is None, (q, e['corretta'])
    trovati, _ = nomi_trovati(S, 'tc torace mdc')
    assert trovati[0] == 'TC torace con mezzo di contrasto', trovati
    trovati, _ = nomi_trovati(S, 'cardiologo')
    assert trovati[0] == 'Visita cardiologica', trovati
    trovati, _ = nomi_trovati(S, 'oculista')
    assert trovati[0] == 'Visita oculistica', trovati
    trovati, _ = nomi_trovati(S, 'dentista')
    assert trovati[0] == 'Visita odontoiatrica', trovati
    for branca, nome, *_ in CP.VOCI:                 # il nome intero: quella prestazione per prima
        trovati, _ = nomi_trovati(S, nome)
        assert trovati[0] == nome, (nome, trovati[:3])


def r_correzione():
    S, C = mondo(catalogo=True)
    trovati, e = nomi_trovati(S, 'ecocardiogrma')
    assert trovati == ['Ecocardiogramma'] and e['corretta'] == 'ecocardiogramma', (trovati, e['corretta'])
    trovati, e = nomi_trovati(S, 'mammografai')
    assert trovati == ['Mammografia'] and e['corretta'] == 'mammografia', (trovati, e['corretta'])
    trovati, e = nomi_trovati(S, 'xyzqwk')
    assert trovati == [] and e['corretta'] is None
    trovati, e = nomi_trovati(S, '')
    assert trovati == [] and e['totale'] == 0
    trovati, e = nomi_trovati(S, 'di la con')     # solo parole vuote, e nessuna prestazione le contiene tutte
    assert e['totale'] == 0, trovati


def r_branche():
    S, C = mondo(catalogo=True)
    trovati, e = nomi_trovati(S, '', 'CARDIOLOGIA')
    attesi = sorted(n for b, n, *_ in CP.VOCI if b == 'CARDIOLOGIA')
    assert trovati == sorted(attesi, key=str.lower), trovati
    trovati, _ = nomi_trovati(S, 'holter', 'cardiologia')
    assert trovati == ['Holter ECG', 'Holter pressorio'], trovati
    trovati, _ = nomi_trovati(S, 'holter', 'OCULISTICA')
    assert trovati == [], trovati
    s = S()
    b = dict((x[0], x[1]) for x in DS.branche(s))
    s.close()
    assert b['DIAGNOSTICA PER IMMAGINI'] == sum(1 for v in CP.VOCI if v[0] == 'DIAGNOSTICA PER IMMAGINI'), b


def r_oracolo():
    """Su 1200 prestazioni inventate: ogni risultato contiene tutte le parole
    (oracolo scritto qui) e ogni prestazione si trova con l'inizio delle sue
    parole; il limite dei risultati non cambia il totale; mai piu' di 60 ms."""
    rnd = random.Random(19)
    esami = ['Ecografia', 'RM', 'TC', 'Radiografia', 'Ecocolordoppler', 'Scintigrafia', 'Biopsia', 'Visita',
             'Agoaspirato', 'Densitometria', 'Elastosonografia', 'Artro-RM', 'Angio-TC']
    parti = ['ginocchio', 'spalla', 'gomito', 'polso', 'mano', 'piede', 'caviglia', 'anca', 'bacino', 'torace', 'addome',
             'encefalo', 'collo', 'tiroide', 'rene', 'fegato', 'milza', 'cuore', 'prostata', 'vescica', 'mammella',
             'rachide cervicale', 'rachide dorsale', 'rachide lombo-sacrale', 'arti inferiori', 'arti superiori',
             'tronchi sovraaortici', 'testicoli', 'occhio', 'orecchio']
    code = ['', ' con mezzo di contrasto', ' senza mezzo di contrasto', ' bilaterale', ' destro', ' sinistro',
            ' sotto carico', ' dinamica', ' 3D']
    branche_ = ['DIAGNOSTICA PER IMMAGINI', 'CARDIOLOGIA', 'ORTOPEDIA', 'UROLOGIA', 'ENDOCRINOLOGIA']
    sigle_ = [s for s, _, _ in CP.STRUTTURE]
    nomi_visti, righe = set(), []
    while len(righe) < 1200:
        nome = '%s %s%s' % (rnd.choice(esami), rnd.choice(parti), rnd.choice(code))
        if nome.lower() in nomi_visti:
            continue
        nomi_visti.add(nome.lower())
        sin = ', '.join(rnd.sample(['controllo', 'esame', 'studio', 'valutazione', 'urgente', 'pediatrico'], 2))
        righe.append((rnd.choice(branche_), nome, sin, ' '.join(rnd.sample(sigle_, rnd.randint(0, 4))), ''))
    S, C = mondo()
    importa_file(S, CP.libro(voci=righe, con_recapiti=False))
    s = S()
    idx = DS.indice(s)
    tempi = []
    for _ in range(400):
        v = rnd.choice(idx['voci'])
        parole_v = [w for w in norma(v['nome']).split() if len(w) >= 3 and w not in DS.PAROLE_VUOTE]
        scelte = rnd.sample(parole_v, min(len(parole_v), rnd.randint(1, 2)))
        q = ' '.join(w[:rnd.randint(3, len(w))] for w in scelte)
        t0 = orologio.perf_counter()
        e = DS.cerca(s, q, limite=100000)
        tempi.append(orologio.perf_counter() - t0)
        assert v['id'] in [x['id'] for x in e['risultati']], ('non trovata', q, v['nome'])
        for x in e['risultati']:
            assert contiene_tutte(x, q), ('risultato senza tutte le parole', q, x['nome'])
        e60 = DS.cerca(s, q)
        assert e60['totale'] == e['totale'] and len(e60['risultati']) == min(60, e['totale']), (q, e60['totale'])
        assert [x['id'] for x in e60['risultati']] == [x['id'] for x in e['risultati'][:60]], q
    # parole a caso, anche inventate: i risultati contengono sempre tutte le parole
    lessico = list({w for v in idx['voci'] for w in norma(v['nome'] + ' ' + ', '.join(v['sinonimi'])).split()})
    for _ in range(300):
        q = ' '.join(rnd.choice(lessico)[:rnd.randint(2, 9)] for _ in range(rnd.randint(1, 3)))
        e = DS.cerca(s, q, limite=100000)
        if e['corretta']:
            q = e['corretta']
        for x in e['risultati']:
            assert contiene_tutte(x, q), ('risultato senza tutte le parole', q, x['nome'])
    s.close()
    media = sum(tempi) / len(tempi)
    assert media < 0.06, 'ricerca lenta: %.1f ms in media' % (media * 1000)
    return 'media %.1f ms su 1200 prestazioni' % (media * 1000)


def r_sede():
    """Le prestazioni di una struttura: solo quelle dove si fa (oracolo: la tabella
    di partenza), anche con una branca o con parole."""
    S, C = mondo(catalogo=True)
    G = gruppo(S)
    s = S()
    for sigla, nome, _ in CP.STRUTTURE:
        attese = sorted((n for b, n, _, dove, _ in CP.VOCI if sigla in dove.split()), key=str.lower)
        e = DS.cerca(s, '', sede=G[nome], limite=1000)
        assert [v['nome'] for v in e['risultati']] == attese, (nome, [v['nome'] for v in e['risultati']])
    e = DS.cerca(s, '', 'CARDIOLOGIA', sede=G['Centro Nord'], limite=1000)
    assert sorted(v['nome'] for v in e['risultati']) == sorted(n for b, n, _, dove, _ in CP.VOCI
                                                              if b == 'CARDIOLOGIA' and 'CN' in dove.split())
    e = DS.cerca(s, 'risonanza', sede=G['Centro Sud'], limite=1000)
    assert sorted(v['nome'] for v in e['risultati']) == ['RM encefalo', 'RM rachide lombo-sacrale'], e['risultati']
    e = DS.cerca(s, 'ecocardiogrma', sede=G['Diagnostica Lago'])
    assert e['totale'] == 0 and e['corretta'] is None, 'corretta con una prestazione che li\' non si fa'
    s.close()
    t = testo(C.get('/dove-si-fa/?sede=%d' % G['Centro Nord']))
    assert 'Solo le prestazioni di Centro Nord' in t and '29 prestazioni a Centro Nord' in t, t[:500]
    t = testo(C.get('/dove-si-fa/risultati?branca=CARDIOLOGIA&sede=%d' % G['Centro Nord']))
    assert '5 prestazioni in Cardiologia a Centro Nord' in t, t[:300]
    t = testo(C.get('/dove-si-fa/risultati?q=xyzk&sede=%d' % G['Centro Nord']))
    assert 'Nessuna prestazione con «xyzk» a Centro Nord' in t and 'Cercare in tutte le strutture' in t
    # una struttura che non c'e': come senza filtro
    assert 'Per branca' in testo(C.get('/dove-si-fa/risultati?sede=999'))
    d = json.loads(html(C.get('/dove-si-fa/cerca.json?sede=%d&branca=CARDIOLOGIA' % G['Centro Nord'])))
    assert d['sede'] == G['Centro Nord'] and d['totale'] == 5, d


def r_listino():
    S, C = mondo(catalogo=True)
    s = S()
    assert [p.nome for p in DS.nel_nostro_listino(s, 'visita cardiologica')] == ['Visita cardiologica']
    assert [p.nome for p in DS.nel_nostro_listino(s, 'colonscopia')] == ['Colonscopia']
    assert DS.nel_nostro_listino(s, 'risonanza') == [] and DS.nel_nostro_listino(s, '') == []
    s.close()


def r_indice():
    """L'indice si rifa' quando il catalogo cambia (importazione, recapiti), non
    a ogni ricerca."""
    S, C = mondo(catalogo=True)
    s = S()
    a = DS.indice(s)
    assert DS.indice(s) is a, 'indice rifatto senza cambi'
    s.close()
    G = gruppo(S)
    C.post('/dove-si-fa/strutture/%d' % G['Centro Sud'], data={'nome_breve': 'C. Sud', 'attiva': '1'})
    s = S()
    b = DS.indice(s)
    assert b is not a and b['strutture'][G['Centro Sud']]['etichetta'] == 'C. Sud'
    s.close()


prova('ricerche attese sul database di prova (sigle, sinonimi, plurali, accenti, trattini)', r_attesi)
prova('parole scritte male corrette, ricerche vuote o senza risultati', r_correzione)
prova('branche: filtro, elenco, conti', r_branche)
prova('oracolo su 1200 prestazioni inventate: tutte le parole, si trova ogni prestazione, limite, tempi', r_oracolo)
prova('le prestazioni di una struttura, anche con una branca o con parole', r_sede)
prova('«si fa anche qui»: il listino di questo gestionale', r_listino)
prova('indice rifatto solo quando il catalogo cambia', r_indice)


# ================================================================ pagine
area('pagine e richieste')


def p_pagina():
    S, C = mondo(catalogo=True)
    G, V = gruppo(S), voci(S)
    corpo = html(C.get('/dove-si-fa/'))
    for x in ('Per branca', 'Le strutture', 'Ultimi indirizzati', 'Centro Nord', 'recapiti da scrivere',
              'id="q-dove"', 'data-branca="CARDIOLOGIA"', 'id="scheda-dove"'):
        assert x in corpo, x
    assert re.search(r'<aside id="scheda-dove"[^>]*hidden', corpo), 'scheda aperta senza struttura'
    corpo = html(C.get('/dove-si-fa/?q=risonanza+ginocchio'))
    assert '2 prestazioni' in testo(C.get('/dove-si-fa/?q=risonanza+ginocchio'))
    assert 'href="/dove-si-fa/?q=risonanza+ginocchio&amp;voce=%d&amp;gruppo=%d"' % (V['RM ginocchio'], G['Centro Nord']) \
        in corpo, re.findall(r'href="(/dove-si-fa/\?q=[^"]+)"', corpo)[:3]
    # la struttura di questo gestionale porta il segno «qui»; «da confermare» dove il database non e' sicuro
    corpo = html(C.get('/dove-si-fa/?q=ecografia+addome'))
    assert re.search(r'class="sede qui"[^>]*>.*?Clinica Posillipo.*?segno-qui', corpo, re.S), 'manca «qui»'
    corpo = html(C.get('/dove-si-fa/?q=ecografia+renale'))
    assert re.search(r'class="sede da-confermare"[^>]*title="%s"' % re.escape(CP.DC), corpo), 'manca «da confermare»'
    # si fa anche qui: il collegamento per prenotare, con il paziente se scelto
    corpo = html(C.get('/dove-si-fa/?q=visita+cardiologica&paziente=1'))
    s = S()
    pid = s.scalars(select(Prestazione).where(Prestazione.nome == 'Visita cardiologica')).first().id
    s.close()
    assert 'Si fa anche qui' in corpo and \
        'href="/appuntamento?prestazione=%d&amp;struttura=1&amp;paziente_id=1"' % pid in corpo, 'prenota qui'
    corpo = html(C.get('/dove-si-fa/?q=ecocardiogrma'))
    assert 'Nessuna prestazione con «ecocardiogrma»: ecco quelle con «<b>ecocardiogramma</b>»' in corpo, \
        re.findall(r'corretta-dove.*', corpo)
    t = testo(C.get('/dove-si-fa/?q=qwzxk'))
    assert 'Nessuna prestazione con «qwzxk»' in t
    t = testo(C.get('/dove-si-fa/?branca=CARDIOLOGIA'))
    assert '5 prestazioni in Cardiologia' in t, t[:400]
    # pezzi della pagina chiesti mentre si scrive: stesso modello, niente cache
    r = C.get('/dove-si-fa/risultati?q=holter')
    assert r.status_code == 200 and '<html' not in html(r) and 'Holter ECG' in html(r)
    assert r.headers['Cache-Control'] == 'no-store' and r.headers['X-Content-Type-Options'] == 'nosniff'
    assert 'Per branca' in html(C.get('/dove-si-fa/risultati'))
    d = json.loads(html(C.get('/dove-si-fa/cerca.json?q=tac+torace')))
    assert d['totale'] == 2 and [x['nome'] for x in d['risultati']] == ['TC torace', 'TC torace con mezzo di contrasto']
    assert {x['nome'] for x in d['risultati'][0]['sedi']} == {'Centro Nord', 'Centro Sud'}
    assert C.get('/dove-si-fa/?q=' + 'x' * 5000).status_code == 200


def p_scheda():
    S, C = mondo(catalogo=True)
    G, V = gruppo(S), voci(S)
    assert C.get('/dove-si-fa/scheda/999').status_code == 404
    r = C.get('/dove-si-fa/scheda/%d?voce=%d' % (G['Centro Nord'], V['RM ginocchio']))
    corpo, t = html(r), testo(r)
    assert r.headers['Cache-Control'] == 'no-store' and '<html' not in corpo
    for x in ('Centro Nord', 'Caserta', 'Via Esempio 10, Caserta', '0823 000 011', '333 000 0011', 'Prenotazione online',
              'dal lunedì al sabato 7.30-19.30', 'Segna come indirizzato', 'RM ginocchio'):
        assert x in t, x
    area_ = unescape(re.search(r'<textarea[^>]*>(.*?)</textarea>', corpo, re.S).group(1))
    assert area_.startswith('Buongiorno,\nla prestazione «RM ginocchio» si può fare presso Centro Nord (Caserta).'), area_
    for x in ('Indirizzo: Via Esempio 10, Caserta', 'Per prenotare: 0823 000 011 oppure 333 000 0011',
              'Prenotazione online: https://www.example.it/centro-nord/prenota', 'Cordiali saluti\nClinica Posillipo'):
        assert x in area_, (x, area_)
    wa = unescape(re.search(r'data-azione="whatsapp" href="([^"]+)" data-base="([^"]+)"', corpo).group(1))
    assert wa.startswith('https://wa.me/?text=') and unquote(wa.split('text=', 1)[1]) == area_, wa[:80]
    # con il paziente: il suo nome, il suo cellulare e la sua email
    r = C.get('/dove-si-fa/scheda/%d?voce=%d&paziente=1' % (G['Centro Nord'], V['RM ginocchio']))
    corpo = html(r)
    area_ = unescape(re.search(r'<textarea[^>]*>(.*?)</textarea>', corpo, re.S).group(1))
    assert area_.startswith('Gentile Ada Fittizi,'), area_[:40]
    m = re.search(r'data-azione="whatsapp" href="([^"]+)" data-base="([^"]+)"', corpo)
    assert unescape(m.group(2)) == 'https://wa.me/393330001111?text=', m.group(2)
    m = re.search(r'data-azione="email" href="([^"]+)" data-base="([^"]+)"', corpo)
    assert unescape(m.group(2)).startswith('mailto:ada.fittizi@example.com?subject=Dove%20fare%3A%20RM%20ginocchio&body='), \
        m.group(2)
    # un paziente con il fisso: WhatsApp senza numero (si sceglie a chi mandarlo)
    corpo = html(C.get('/dove-si-fa/scheda/%d?voce=%d&paziente=2' % (G['Centro Nord'], V['RM ginocchio'])))
    assert 'data-base="https://wa.me/?text="' in corpo
    # una struttura senza recapiti: il collegamento per scriverli; una prestazione da confermare
    t = testo(C.get('/dove-si-fa/scheda/%d?voce=%d' % (G['Diagnostica Lago'], V['RM ginocchio'])))
    assert 'Indirizzo e telefono non sono ancora scritti' in t
    t = testo(C.get('/dove-si-fa/scheda/%d?voce=%d' % (G['Clinica Collina'], V['Ecografia renale'])))
    assert 'Da confermare: %s.' % CP.DC in t, t[:500]
    t = testo(C.get('/dove-si-fa/scheda/%d?voce=%d' % (G['Centro Sud'], V['RM spalla'])))
    assert 'Per il database questa prestazione qui non si fa' in t
    t = testo(C.get('/dove-si-fa/scheda/%d' % G['Clinica Posillipo']))
    assert 'È questa struttura' in t and 'la prestazione richiesta si può fare presso Clinica Posillipo' in t
    # senza una prestazione: cosa si fa in quella struttura, branca per branca (oracolo: la tabella di partenza)
    corpo = html(C.get('/dove-si-fa/scheda/%d' % G['Centro Nord']))
    attese = {}
    for b, n, _, dove, _ in CP.VOCI:
        if 'CN' in dove.split():
            attese[b] = attese.get(b, 0) + 1
    trovate = {unescape(b).upper(): int(n) for b, n in
               re.findall(r'data-branca-scheda="([^"]+)" data-sede="%d">[^<]+</a> <small>(\d+)</small>' % G['Centro Nord'],
                          corpo)}
    assert trovate == attese, (trovate, attese)
    assert 'Cosa si fa qui <small>%d prestazioni ·' % sum(attese.values()) in corpo
    assert 'href="/dove-si-fa/?sede=%d" data-branca-scheda="" data-sede="%d">vedile tutte' % ((G['Centro Nord'],) * 2) \
        in corpo
    assert 'Cosa si fa qui' not in html(C.get('/dove-si-fa/scheda/%d?voce=%d' % (G['Centro Nord'], V['RM ginocchio'])))
    # la pagina intera con la scheda aperta (dopo un ricaricamento)
    corpo = html(C.get('/dove-si-fa/?q=rm+ginocchio&voce=%d&gruppo=%d' % (V['RM ginocchio'], G['Centro Nord'])))
    assert 'class="scheda-dove-aperta"' in corpo and 'Messaggio per il paziente' in corpo
    assert not re.search(r'<aside id="scheda-dove"[^>]*hidden', corpo)


def p_stampa():
    S, C = mondo(catalogo=True)
    G, V = gruppo(S), voci(S)
    assert C.get('/dove-si-fa/stampa').status_code == 404
    t = testo(C.get('/dove-si-fa/stampa?gruppo=%d&voce=%d&paziente=1' % (G['Centro Nord'], V['Mammografia'])))
    for x in ('Dove fare «Mammografia»', 'Per: Fittizi Ada', 'Centro Nord', 'Via Esempio 10, Caserta',
              '0823 000 011 oppure 333 000 0011', 'Indicazioni date dalla segreteria di Clinica Posillipo',
              date.today().strftime('%d/%m/%Y')):
        assert x in t, (x, t[:600])
    t = testo(C.get('/dove-si-fa/stampa?gruppo=%d' % G['Diagnostica Lago']))
    assert 'Indirizzo e telefono della struttura non sono scritti' in t


def p_registro():
    S, C = mondo(catalogo=True)
    G, V = gruppo(S), voci(S)
    r = C.post('/dove-si-fa/indirizza', json={'gruppo': G['Centro Nord'], 'voce': V['Mammografia'], 'paziente': 1,
                                              'canale': 'whatsapp'})
    d = json.loads(html(r))
    assert r.status_code == 200 and d['testo'] == 'Fittizi Ada indirizzata a Centro Nord per «Mammografia» (WhatsApp).', d
    r = C.post('/dove-si-fa/indirizza', json={'gruppo': G['Centro Sud'], 'canale': 'boh', 'note': '  da  richiamare '})
    d2 = json.loads(html(r))
    assert d2['testo'] == 'Paziente indirizzato a Centro Sud (al telefono).', d2
    assert C.post('/dove-si-fa/indirizza', json={'gruppo': 999}).status_code == 400
    s = S()
    righe = s.scalars(select(Indirizzato).order_by(Indirizzato.id)).all()
    assert [(x.gruppo_nome, x.prestazione, x.branca, x.paziente, x.canale, x.paziente_id) for x in righe] == \
        [('Centro Nord', 'Mammografia', 'DIAGNOSTICA PER IMMAGINI', 'Fittizi Ada', 'whatsapp', 1),
         ('Centro Sud', '', '', '', 'telefono', None)], righe
    assert righe[1].note == 'da richiamare' and righe[0].struttura_id == 1
    # un mese fa: non nel mese in corso, si' in quello prima
    vecchio = Indirizzato(quando=datetime.now().replace(day=1) - timedelta(days=3), gruppo_id=G['Centro Sud'],
                          gruppo_nome='Centro Sud', prestazione='Holter ECG', canale='voce')
    s.add(vecchio)
    s.commit()
    vid = vecchio.id
    mese_prima = vecchio.quando.strftime('%Y-%m')
    s.close()
    t = testo(C.get('/dove-si-fa/registro'))
    assert '2 in tutto' in t and 'Fittizi Ada' in t and 'Holter ECG' not in t, t[:600]
    t = testo(C.get('/dove-si-fa/registro?mese=' + mese_prima))
    assert '1 in tutto' in t and 'Holter ECG' in t and 'a voce' in t
    r = C.get('/dove-si-fa/registro/%s.xlsx' % date.today().strftime('%Y-%m'))
    import openpyxl
    ws = openpyxl.load_workbook(BytesIO(r.data)).active
    righe = list(ws.iter_rows(values_only=True))
    # 1.12: sopra la tabella il titolo e il mese, sotto i totali e i conteggi per struttura
    testa = next(i for i, r_ in enumerate(righe) if r_[0] == 'Data')
    assert 'Pazienti indirizzati' in str(righe[0][0]) and testa > 1, righe[0]
    assert righe[testa] == ('Data', 'Ora', 'Paziente', 'Prestazione', 'Branca', 'Struttura', 'Come', 'Note'), righe[testa]
    assert [r_[2:7] for r_ in righe[testa + 1:testa + 3]] == [('Fittizi Ada', 'Mammografia', 'DIAGNOSTICA PER IMMAGINI', 'Centro Nord',
                                             'WhatsApp'), (None, None, None, 'Centro Sud', 'al telefono')], righe[testa + 1:testa + 3]
    assert righe[testa + 3][0] == 'Totale' and righe[testa + 3][2] == '2 indirizzati', righe[testa + 3]
    assert ('Centro Nord', 1) in [r_[:2] for r_ in righe[testa + 4:]] and ('Centro Sud', 1) in [r_[:2] for r_ in righe[testa + 4:]], righe[testa + 4:]
    # togli: dall'avviso (JSON) e dal registro (modulo, si torna solo a pagine del programma)
    r = C.post(d['togli'], json={})
    assert json.loads(html(r)) == {'tolto': d['id']}
    r = C.post('/dove-si-fa/indirizzati/%d/togli' % vid, data={'torna': '/dove-si-fa/registro?mese=' + mese_prima})
    assert r.headers['Location'].endswith('/dove-si-fa/registro?mese=' + mese_prima) and 'Tolto dal registro' in avvisi(C)
    r = C.post('/dove-si-fa/indirizzati/%d/togli' % d2['id'], data={'torna': '//sito-cattivo.example.com'})
    assert r.headers['Location'].endswith('/dove-si-fa/registro'), r.headers['Location']
    r = C.post('/dove-si-fa/indirizzati/%d/togli' % d2['id'], data={})
    assert 'Era già stato tolto' in avvisi(C)
    s = S()
    assert s.query(Indirizzato).count() == 0
    s.close()


def p_strutture():
    S, C = mondo(catalogo=True)
    G = gruppo(S)
    t = testo(C.get('/dove-si-fa/strutture'))
    for x in ('Database caricato: prova.xlsx', '%d prestazioni in 6 strutture' % len(CP.VOCI), 'Carica la versione nuova',
              'Centro Nord', 'Caserta', 'da scrivere'):
        assert x in t, (x, t[:600])
    gid = G['Diagnostica Lago']
    for dati, parole in (({'email': 'non-email'}, 'L\'email non è scritta bene'),
                         ({'sito': 'javascript:alert(1)'}, 'indirizzo web completo'),
                         ({'telefono': '1' * 41}, '«Telefono» è troppo lungo'),
                         ({'prenotazione': 'x' * 401}, '«Come si prenota» è troppo lungo')):
        t = testo(C.post('/dove-si-fa/strutture/%d' % gid, data=dict(dati, attiva='1')))
        assert parole in t, (parole, t[:400])
    s = S()
    assert not s.get(StrutturaGruppo, gid).telefono, 'salvato nonostante gli errori'
    s.close()
    r = C.post('/dove-si-fa/strutture/%d' % gid, data={
        'indirizzo': '  Via   Lago 2 ', 'citta': 'Benevento', 'telefono': '0824 000 055', 'email': 'lago@example.it',
        'sito': 'https://www.example.it/lago', 'orari': 'sempre', 'prenotazione': 'per telefono\nal mattino',
        'note': 'parlare con l\'accettazione', 'nome_breve': 'Lago', 'struttura_id': '1', 'attiva': '1'})
    assert r.status_code == 302 and 'Recapiti di Diagnostica Lago salvati' in avvisi(C)
    s = S()
    g = s.get(StrutturaGruppo, gid)
    assert (g.indirizzo, g.citta, g.telefono, g.prenotazione, g.etichetta, g.struttura_id, g.attiva) == \
        ('Via Lago 2', 'Benevento', '0824 000 055', 'per telefono\nal mattino', 'Lago', 1, True)
    s.close()
    # una struttura del gestionale che non esiste non si collega
    C.post('/dove-si-fa/strutture/%d' % gid, data={'struttura_id': '987', 'attiva': '1'})
    s = S()
    assert s.get(StrutturaGruppo, gid).struttura_id is None
    s.close()
    assert C.get('/dove-si-fa/strutture/999').status_code == 404


def p_sicurezza():
    """Nomi con HTML nel file Excel: scritti come testo ovunque; richieste da
    altri siti rifiutate."""
    strutture = [('XS', '<script>alert(1)</script>', {'telefono': '<b>081</b>', 'orari': '"><img src=x onerror=alert(2)>'}),
                 ('CN', 'Centro Nord', None)]
    righe = [('CARDIOLOGIA', '<img src=x onerror=alert(3)> holter', '<i>sin</i>', 'XS CN',
              'XS: "><svg onload=alert(4)>, da confermare')]
    S, C = mondo()
    importa_file(S, CP.libro(voci=righe, strutture=strutture))
    G, V = gruppo(S), voci(S)
    for url in ('/dove-si-fa/?q=holter', '/dove-si-fa/risultati?q=holter', '/dove-si-fa/',
                '/dove-si-fa/scheda/%d?voce=%d' % (G['<script>alert(1)</script>'], V['<img src=x onerror=alert(3)> holter']),
                '/dove-si-fa/stampa?gruppo=%d' % G['<script>alert(1)</script>'], '/dove-si-fa/strutture'):
        corpo = html(C.get(url))
        for x in ('<script>alert', '<img src=x', '<svg onload', '<b>081', '<i>sin'):
            assert x not in corpo, (url, x)
    corpo = html(C.get('/dove-si-fa/?q=holter'))
    assert '&lt;img src=x onerror=alert(3)&gt; holter' in corpo and '&lt;script&gt;alert(1)&lt;/script&gt;' in corpo
    d = html(C.get('/dove-si-fa/cerca.json?q=holter'))
    assert '<' not in d and '\\u003cimg' in d
    # da un altro sito: rifiutato prima di arrivare alla pagina
    r = C.post('/dove-si-fa/indirizza', json={'gruppo': G['Centro Nord']}, headers={'Origin': 'https://sito-cattivo.example.com'})
    assert r.status_code == 403
    r = C.post('/dove-si-fa/strutture/%d' % G['Centro Nord'], data={'telefono': '1'},
               headers={'Sec-Fetch-Site': 'cross-site'})
    assert r.status_code == 403
    s = S()
    assert s.query(Indirizzato).count() == 0 and s.get(StrutturaGruppo, G['Centro Nord']).telefono == ''
    s.close()


def p_menu_e_altre():
    """Il menu, la ricerca rapida, la scheda del paziente, le statistiche."""
    S, C = mondo()
    corpo = html(C.get('/oggi'))
    assert re.search(r'<a data-tasto="d" href="/dove-si-fa/[^"]*"[^>]*>Dove si fa</a>', corpo), 'menu'
    assert 'Strutture del gruppo' in corpo and '<th>D</th>' in corpo
    d = json.loads(html(C.get('/cerca-tutto.json?q=holter')))
    assert d['prestazioni'] == [], d                    # senza database: niente, e nessun errore
    importa_file(S, CP.libro())
    d = json.loads(html(C.get('/cerca-tutto.json?q=holter')))
    assert [x['etichetta'] for x in d['prestazioni']] == ['Holter ECG', 'Holter pressorio'], d['prestazioni']
    assert d['prestazioni'][0]['dettaglio'] == 'si fa a: Clinica Posillipo, Centro Nord, Centro Sud'
    assert d['prestazioni'][0]['url'].startswith('/dove-si-fa/?q=holter&voce=')
    d = json.loads(html(C.get('/cerca-tutto.json?q=Fittizi')))
    assert d['pazienti'] and d['prestazioni'] == []
    assert json.loads(html(C.get('/cerca-tutto.json?q=ho')))['prestazioni'] == []
    corto = DS.per_ricerca_rapida
    DS.per_ricerca_rapida = lambda *a, **k: 1 / 0
    try:
        d = json.loads(html(C.get('/cerca-tutto.json?q=Fittizi')))
    finally:
        DS.per_ricerca_rapida = corto
    assert d['pazienti'] and d['prestazioni'] == [], 'un guasto delle prestazioni ferma la ricerca rapida'
    assert 'Dove si fa una prestazione' in html(C.get('/pazienti/1'))
    t = testo(C.get('/dove-si-fa/?paziente=1'))
    assert 'Per Fittizi Ada' in t and 'Togli' in t
    G = gruppo(S)
    C.post('/dove-si-fa/indirizza', json={'gruppo': G['Centro Sud'], 'paziente': 1})
    C.post('/dove-si-fa/indirizza', json={'gruppo': G['Centro Sud']})
    C.post('/dove-si-fa/indirizza', json={'gruppo': G['Centro Nord']})
    t = testo(C.get('/statistiche?struttura=1'))
    assert 'Indirizzati alle altre strutture Centro Sud 2 Centro Nord 1' in t, t[t.find('Indirizzati'):][:200]
    import openpyxl
    wb = openpyxl.load_workbook(BytesIO(C.get('/statistiche/excel?struttura=1').data))
    assert list(wb['Indirizzati'].iter_rows(values_only=True)) == \
        [('Struttura del gruppo', 'Pazienti indirizzati'), ('Centro Sud', 2), ('Centro Nord', 1)]


def p_pazienti():
    """Il registro segue il paziente: unito a un altro, passa all'altro;
    eliminato, la riga resta con il nome."""
    S, C = mondo(catalogo=True)
    G = gruppo(S)
    s = S()
    doppio = Paziente(cognome='Fittizi', nome='Ada', telefono='333 000 1111')
    s.add(doppio)
    s.commit()
    did = doppio.id
    s.close()
    C.post('/dove-si-fa/indirizza', json={'gruppo': G['Centro Sud'], 'paziente': did})
    s = S()
    pazienti.unisci(s, s.get(Paziente, 1), s.get(Paziente, did))
    s.commit()
    assert s.scalars(select(Indirizzato)).one().paziente_id == 1
    s.close()
    C.post('/dove-si-fa/indirizza', json={'gruppo': G['Centro Nord'], 'paziente': 2})
    r = C.post('/pazienti/2', data={'azione': 'elimina'})
    assert r.status_code == 302, r.status_code
    s = S()
    x = s.scalars(select(Indirizzato).where(Indirizzato.gruppo_nome == 'Centro Nord')).one()
    assert x.paziente_id is None and x.paziente == 'Esempio Bruno', (x.paziente_id, x.paziente)
    assert s.get(Paziente, 2) is None
    s.close()
    assert 'Esempio Bruno' in testo(C.get('/dove-si-fa/registro'))


def p_struttura_eliminata():
    """Eliminando una struttura del gestionale, la struttura del gruppo collegata e il
    registro perdono il collegamento, non i dati."""
    S, C = mondo(catalogo=True)
    G = gruppo(S)
    s = S()
    seconda = Struttura(nome='Seconda sede')
    s.add(seconda)
    s.commit()
    sid = seconda.id
    s.get(StrutturaGruppo, G['Centro Sud']).struttura_id = sid
    s.add(Indirizzato(struttura_id=sid, gruppo_id=G['Centro Sud'], gruppo_nome='Centro Sud', canale='voce'))
    s.commit()
    s.close()
    assert 'segno-qui' in html(C.get('/dove-si-fa/?q=visita+urologica&struttura=%d' % sid))
    r = C.post('/anagrafiche/strutture/%d' % sid, data={'azione': 'elimina'})
    assert r.status_code == 302 and 'Struttura eliminata: Seconda sede' in avvisi(C)
    s = S()
    assert s.get(Struttura, sid) is None
    assert s.get(StrutturaGruppo, G['Centro Sud']).struttura_id is None
    x = s.scalars(select(Indirizzato)).one()
    assert x.struttura_id is None and x.gruppo_nome == 'Centro Sud'
    s.close()
    assert 'Centro Sud' in testo(C.get('/dove-si-fa/registro'))


prova('pagina: inizio, risultati, «qui», «da confermare», prenota qui, correzioni, pezzi e JSON', p_pagina)
prova('una struttura del gestionale eliminata: collegamenti tolti, dati tenuti', p_struttura_eliminata)
prova('scheda della struttura: recapiti, messaggio, WhatsApp ed email al paziente, avvisi', p_scheda)
prova('foglio da stampare per il paziente', p_stampa)
prova('registro: segnare, mesi, Excel, togliere (anche con un indirizzo di ritorno cattivo)', p_registro)
prova('strutture del gruppo: elenco e recapiti con i controlli', p_strutture)
prova('sicurezza: HTML dal file scritto come testo, richieste da altri siti rifiutate', p_sicurezza)
prova('menu, ricerca rapida (anche con un guasto), scheda del paziente, statistiche', p_menu_e_altre)
prova('il registro segue il paziente unito o eliminato', p_pazienti)


# ================================================================ database
area('database')


def d_migrazione():
    percorso = percorso_nuovo('v9')
    S0 = crea_sessione('sqlite:///' + percorso)
    s = S0()
    servizi.prepara_primo_avvio(s, 'Sede di prova')
    s.add(Paziente(cognome='Testabianca', nome='Ugo'))
    s.commit()
    s.close()
    S0.motore.dispose()
    c = sqlite3.connect(percorso)
    for tab in ('indirizzati', 'catalogo_sedi', 'catalogo', 'strutture_gruppo'):
        c.execute('DROP TABLE %s' % tab)
    c.execute("UPDATE impostazioni SET valore = '9' WHERE chiave = 'versione_schema'")
    c.commit()
    c.close()
    S = crea_sessione('sqlite:///' + percorso)
    note = ' | '.join(S.migrazioni)
    assert S.versione_precedente == 9 and VERSIONE_SCHEMA >= 10, (S.versione_precedente, VERSIONE_SCHEMA)
    assert 'prima-della-versione-%d' % VERSIONE_SCHEMA in note and 'da 9 a %d' % VERSIONE_SCHEMA in note, note
    assert os.listdir(os.path.join(os.path.dirname(percorso), 'backup')), 'copia di sicurezza mancante'
    s = S()
    assert s.scalars(select(Paziente)).one().cognome == 'Testabianca'
    assert s.query(StrutturaGruppo).count() == 0
    s.close()
    A.Sessione = S
    A._registro = None
    viste._sessionmaker = lambda: S
    C = A.app.test_client()
    assert 'Manca il database delle prestazioni' in testo(C.get('/dove-si-fa/'))
    importa_file(S, CP.libro())
    assert 'Centro Nord' in testo(C.get('/dove-si-fa/?q=holter'))
    S2 = crea_sessione('sqlite:///' + percorso)
    assert S2.versione_precedente == VERSIONE_SCHEMA and not S2.migrazioni


prova('aggiornamento dalla versione 9: copia di sicurezza, tabelle nuove, dati intatti', d_migrazione)


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
