# -*- coding: utf-8 -*-
"""Prove della 1.4.3: aggiornamento del database dalla 1.4.2, degenza,
checklist pre-operatoria, lista operatoria, posti letto, pagina Oggi,
riepilogo mensile per medico, giorni di sala dei chirurghi, robustezza.

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
from datetime import date, datetime, time, timedelta
from html import unescape
from urllib.parse import unquote

from sqlalchemy import select

import servizi
import segreteria
import sala
import cruscotto
import importa
import viste
import app as A
from modelli import (crea_sessione, Struttura, Risorsa, Operatore, Appuntamento, Prestazione, Paziente,
                     Assenza, Attivita, VERSIONE_SCHEMA, CHECKLIST_PREDEFINITA, leggi_degenza, scrivi_impostazione)

A.app.config['TESTING'] = True
CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = os.path.join(CARTELLA, 'prove_143_tmp')
shutil.rmtree(PROVVISORIA, ignore_errors=True)
os.makedirs(PROVVISORIA)
esiti, _area, _n = [], [''], [0]
OGGI = date.today()
DOMANI = OGGI + timedelta(days=1)
# un martedi nel futuro, lontano dai festivi
MAR = OGGI + timedelta(days=(1 - OGGI.weekday()) % 7 + 14)
while servizi.calendario.festivo(MAR) or servizi.calendario.festivo(MAR + timedelta(days=3)):
    MAR += timedelta(days=7)
VEN = MAR + timedelta(days=3)


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


def mondo(letti=None):
    """Primo avvio, due sale operatorie, tre chirurghi e un medico
    d'ambulatorio, una prestazione con l'anestesista fra i campi in piu'."""
    S = crea_sessione('sqlite:///' + percorso_nuovo())
    s = S()
    servizi.prepara_primo_avvio(s)
    st = s.get(Struttura, 1)
    st.posti_letto = letti
    s.add_all([Risorsa(nome='Sala A', tipo='SALA_OPERATORIA', struttura_id=1, ordine=10),
               Risorsa(nome='Sala B', tipo='SALA_OPERATORIA', struttura_id=1, ordine=11)])
    s.add_all([Operatore(cognome='Borrelli', nome='Ugo', email='borrelli@example.it'),
               Operatore(cognome='Mancini', nome='Rita'), Operatore(cognome='Ferri', nome='Aldo'),
               Operatore(cognome='Lippi', nome='Anna')])
    s.add(Prestazione(nome='Rinoplastica', durata_min=60, campi_extra='Medico anestesista'))
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


def nuovo_app(S, stanza, medico, g, h, m=0, minuti=60, stato='PRENOTATO', cognome=None, **altro):
    s = S()
    pid = None
    if cognome:
        p = Paziente(cognome=cognome, nome='', telefono='333000%04d' % random.randint(0, 9999))
        s.add(p)
        s.flush()
        pid = p.id
    i = datetime.combine(g, time(h, m))
    a = Appuntamento(risorsa_id=stanza, operatore_id=medico, inizio=i, fine=i + timedelta(minutes=minuti),
                     stato=stato, paziente_id=pid, **altro)
    s.add(a)
    s.commit()
    aid = a.id
    s.close()
    return aid


def html(r):
    return r.get_data(as_text=True)


def testo(r):
    return ' '.join(unescape(re.sub(r'<[^>]+>', ' ', html(r))).split())


def avvisi(C):
    with C.session_transaction() as sess:
        m = sess.get('_flashes', [])
        sess['_flashes'] = []
    return unescape(re.sub(r'<[^>]+>', '', ' '.join(str(x[1]) for x in m)))


def notifiche(s):
    with A.app.test_request_context('/'):
        return segreteria.notifiche_di(s, 1)


def leggi(S, aid):
    s = S()
    a = s.get(Appuntamento, aid)
    d = {c.name: getattr(a, c.name) for c in Appuntamento.__table__.columns}
    s.close()
    return d


def modulo_app(I, stanza, medico, g, ora='09:00', **altro):
    d = {'risorsa': str(I[stanza]), 'operatore': str(I[medico]), 'prestazione': str(I['Rinoplastica']),
         'data': g.isoformat(), 'ora': ora, 'durata': '60', 'struttura': '1', 'paziente': 'Rossi',
         'nome_paziente': 'Marta', 'telefono': '3331112222', 'tipo': '', 'convenzione': '', 'importo': '', 'note': ''}
    d.update(altro)
    return d


# ============================================================ aggiornamento
area('aggiornamento dalla 1.4.2')


def ag_da_5_a_6():
    """Un database della 1.4.2 (schema 5): la degenza stava fra i campi in piu'."""
    percorso = percorso_nuovo('v5')
    S = crea_sessione('sqlite:///' + percorso)
    s = S()
    servizi.prepara_primo_avvio(s)
    s.add(Risorsa(nome='Sala A', tipo='SALA_OPERATORIA', struttura_id=1, ordine=9))
    s.add(Operatore(cognome='Borrelli'))
    s.add(Prestazione(nome='Rinoplastica', campi_extra='Medico anestesista, Degenza, Sedazione?'))
    s.commit()
    rid = s.scalars(select(Risorsa.id).where(Risorsa.nome == 'Sala A')).first()
    oid = s.scalars(select(Operatore.id)).first()
    pid = s.scalars(select(Prestazione.id).where(Prestazione.nome == 'Rinoplastica')).first()
    s.close()
    S.motore.dispose()
    casi = [('{"Medico anestesista": "ROMANO", "Degenza": "DH"}', 'DH', None, '{"Medico anestesista": "ROMANO"}', ''),
            ('{"Degenza": "NOTTE"}', 'NOTTE', None, '', ''),
            ('{"Degenza": "RO", "Sedazione": "Sì"}', 'RICOVERO', None, '{"Sedazione": "Sì"}', ''),
            ('{"Degenza": "3 notti"}', 'RICOVERO', 3, '', ''),
            ('{"Degenza": "?"}', '', None, '', 'Degenza: ?'),
            ('{"Medico anestesista": "IZZO"}', '', None, '{"Medico anestesista": "IZZO"}', ''),
            ('non json', '', None, 'non json', '')]
    c = sqlite3.connect(percorso)
    for col in ('degenza', 'notti', 'checklist'):
        c.execute('ALTER TABLE appuntamenti DROP COLUMN %s' % col)
    c.execute('ALTER TABLE strutture DROP COLUMN posti_letto')
    c.execute('ALTER TABLE operatori DROP COLUMN giorni_sala')
    for i, (extra, *_x) in enumerate(casi):
        inizio = datetime.combine(MAR, time(8 + i, 0))
        c.execute("INSERT INTO appuntamenti (risorsa_id, operatore_id, prestazione_id, inizio, fine, stato, note, extra) "
                  "VALUES (?, ?, ?, ?, ?, 'PRENOTATO', ?, ?)",
                  (rid, oid, pid, str(inizio), str(inizio + timedelta(hours=1)), 'nota' if i == 4 else '', extra))
    c.execute("UPDATE impostazioni SET valore = '5' WHERE chiave = 'versione_schema'")
    c.commit()
    c.close()
    S = crea_sessione('sqlite:///' + percorso)
    assert S.versione_precedente == 5, S.versione_precedente
    assert {'appuntamenti.degenza', 'appuntamenti.notti', 'appuntamenti.checklist', 'strutture.posti_letto',
            'operatori.giorni_sala'} <= set(S.colonne_aggiunte), S.colonne_aggiunte
    assert any('prima-della-versione-%d' % VERSIONE_SCHEMA in m for m in S.migrazioni), \
        'nessuna copia di sicurezza: %s' % S.migrazioni
    s = S()
    apps = s.scalars(select(Appuntamento).order_by(Appuntamento.inizio)).all()
    for a, (_, deg, notti, extra, nota) in zip(apps, casi):
        assert (a.degenza or '') == deg and a.notti == notti and (a.extra or '') == extra, \
            (a.extra, a.degenza, a.notti, deg, notti, extra)
        if nota:
            assert a.note == 'nota ' + nota, a.note
    p = s.scalars(select(Prestazione).where(Prestazione.nome == 'Rinoplastica')).first()
    assert [e for e, _ in p.elenco_campi_extra] == ['Medico anestesista', 'Sedazione'], p.campi_extra
    assert dict(p.elenco_campi_extra)['Sedazione'] is True, 'la casella si/no ha perso il "?"'
    versione = s.execute(select(A.Appuntamento.id)).first() and \
        sqlite3.connect(percorso).execute("SELECT valore FROM impostazioni WHERE chiave='versione_schema'").fetchone()[0]
    assert versione == str(VERSIONE_SCHEMA), versione
    s.close()
    # un secondo avvio non rifa' niente
    S2 = crea_sessione('sqlite:///' + percorso)
    assert S2.versione_precedente == VERSIONE_SCHEMA and not S2.migrazioni and not S2.colonne_aggiunte, S2.migrazioni
    return '%d appuntamenti controllati' % len(casi)


def ag_leggi_degenza():
    attesi = {'DH': ('DH', None), 'd.h.': ('DH', None), 'Day Hospital': ('DH', None), 'day surgery': ('DH', None),
              'NOTTE': ('NOTTE', None), '1 notte': ('NOTTE', None), 'una notte': ('NOTTE', None),
              'RO': ('RICOVERO', None), 'ricovero ordinario': ('RICOVERO', None), '2 notti': ('RICOVERO', 2),
              'ricovero 3 notti': ('RICOVERO', 3), '0 notti': ('DH', None), '99 notti': ('RICOVERO', 60),
              '?': None, '': None, None: None, 'boh': None, 'DH?': ('DH', None)}
    for t, atteso in attesi.items():
        assert leggi_degenza(t) == atteso, '%r -> %r invece di %r' % (t, leggi_degenza(t), atteso)


prova('database della 1.4.2: degenza spostata dai campi in più, prestazioni ripulite, copia di sicurezza', ag_da_5_a_6)
prova('degenza scritta a mano: DH, notte, RO, "3 notti", "?"', ag_leggi_degenza)


# =================================================================== degenza
area('degenza nel modulo')


def de_modulo():
    S, C = mondo()
    I = ids(S)
    r = C.get('/appuntamento?data=%s&ora=09:00&risorsa=%d' % (MAR, I['Sala A']))
    t = html(r)
    assert 'id="campi-degenza"' in t and 'data-tipo="SALA_OPERATORIA"' in t, 'campo degenza o tipo stanza mancanti'
    r = C.post('/appuntamento', data=modulo_app(I, 'Sala A', 'Borrelli', MAR, degenza='RICOVERO', notti='3'))
    assert r.status_code == 302, avvisi(C)
    a = S().scalars(select(Appuntamento)).first()
    assert a.degenza == 'RICOVERO' and a.notti == 3 and a.notti_letto == 3, (a.degenza, a.notti)
    assert a.etichetta_degenza == 'Ricovero, 3 notti', a.etichetta_degenza
    aid = a.id
    # da ricovero a una notte: le notti non restano appese
    r = C.post('/appuntamento/%d' % aid, data=modulo_app(I, 'Sala A', 'Borrelli', MAR, degenza='NOTTE', notti='3'))
    d = leggi(S, aid)
    assert d['degenza'] == 'NOTTE' and d['notti'] is None, d
    for sbagliato, msg in ((dict(degenza='SETTIMANA'), 'Degenza: scelta non valida'),
                           (dict(degenza='RICOVERO', notti='0'), 'Notti di ricovero'),
                           (dict(degenza='RICOVERO', notti='abc'), 'Notti di ricovero'),
                           (dict(degenza='RICOVERO', notti='61'), 'Notti di ricovero')):
        r = C.post('/appuntamento/%d' % aid, data=modulo_app(I, 'Sala A', 'Borrelli', MAR, **sbagliato))
        assert r.status_code == 200 and msg in testo(r), sbagliato
        assert leggi(S, aid)['degenza'] == 'NOTTE', 'salvato nonostante l\'errore'
    # un modulo senza il campo (vecchia pagina aperta) non rompe niente
    dati = modulo_app(I, 'Ambulatorio 1', 'Lippi', MAR, ora='10:00')
    r = C.post('/appuntamento', data=dati)
    assert r.status_code == 302, avvisi(C)


prova('degenza e notti di ricovero: salvate, controllate, errori spiegati', de_modulo)


# ================================================================= checklist
area('checklist pre-operatoria')


def ck_spunte():
    S, C = mondo()
    I = ids(S)
    aid = nuovo_app(S, I['Sala A'], I['Borrelli'], MAR, 9, cognome='Rossi')
    amb = nuovo_app(S, I['Ambulatorio 1'], I['Lippi'], MAR, 9, cognome='Verdi')
    t = html(C.get('/appuntamento/%d' % aid))
    assert 'Checklist pre-operatoria' in t and t.count('name="spunte"') == 5, 'riquadro checklist'
    assert 'Checklist pre-operatoria' not in html(C.get('/appuntamento/%d' % amb)), 'checklist su una visita'
    intest = {'X-Richiesta': 'fetch'}
    fatte = set()
    rnd = random.Random(7)
    for _ in range(25):
        v = rnd.choice(CHECKLIST_PREDEFINITA)
        fatto = rnd.random() < 0.6
        r = C.post('/appuntamento/%d/checklist' % aid, data={'voce': v, 'fatto': '1' if fatto else '0'}, headers=intest)
        assert r.status_code == 200, r.status_code
        (fatte.add if fatto else fatte.discard)(v)
        j = r.get_json()
        assert j['fatte'] == len(fatte) and j['totale'] == 5 and j['completa'] == (len(fatte) == 5), (j, fatte)
    spunte = json.loads(leggi(S, aid)['checklist'] or '{}')
    assert set(spunte) == fatte, (spunte, fatte)
    assert all(re.fullmatch(r'\d{4}-\d\d-\d\d \d\d:\d\d', x) for x in spunte.values()), spunte
    # la data della spunta resta quella della prima volta
    C.post('/appuntamento/%d/checklist' % aid, data={'voce': 'Consenso firmato', 'fatto': '1'}, headers=intest)
    prima = json.loads(leggi(S, aid)['checklist'])['Consenso firmato']
    C.post('/appuntamento/%d/checklist' % aid, data={'voce': 'Consenso firmato', 'fatto': '1'}, headers=intest)
    assert json.loads(leggi(S, aid)['checklist'])['Consenso firmato'] == prima
    # senza JavaScript: tutte le caselle insieme
    r = C.post('/appuntamento/%d/checklist' % aid, data={'spunte': ['Esami pre-operatori', 'Acconto versato'],
                                                           'torna': '/sala/%s' % MAR})
    assert r.status_code == 302 and r.headers['Location'].endswith('/sala/%s' % MAR), r.headers.get('Location')
    assert set(json.loads(leggi(S, aid)['checklist'])) == {'Esami pre-operatori', 'Acconto versato'}
    # una voce che non c'e', un appuntamento che non c'e', un indirizzo esterno
    assert C.post('/appuntamento/%d/checklist' % aid, data={'voce': 'Inventata', 'fatto': '1'}).status_code == 400
    assert C.post('/appuntamento/999999/checklist', data={'voce': 'Consenso firmato'}).status_code == 404
    r = C.post('/appuntamento/%d/checklist' % aid, data={'spunte': [], 'torna': '//sito.example'})
    assert r.headers['Location'].endswith('/appuntamento/%d' % aid), r.headers['Location']
    assert leggi(S, aid)['checklist'] == '', 'tutte tolte: vuota'


def ck_voci():
    S, C = mondo()
    I = ids(S)
    aid = nuovo_app(S, I['Sala A'], I['Borrelli'], MAR, 9, cognome='Rossi')
    C.post('/appuntamento/%d/checklist' % aid, data={'voce': 'Consenso firmato', 'fatto': '1'})
    t = html(C.get('/impostazioni'))
    assert 'id="checklist"' in t and 'Acconto versato' in t
    r = C.post('/sala/checklist-voci', data={'voci': ' Consenso firmato \n\nconsenso FIRMATO\nECG\n  Esami   del sangue '})
    assert r.status_code == 302
    s = S()
    assert sala.voci_checklist(s) == ['Consenso firmato', 'ECG', 'Esami del sangue'], sala.voci_checklist(s)
    s.close()
    g = html(C.get('/giorno/%s?struttura=1' % MAR))
    assert 'checklist-voce incompleta' in g and '>1/3<' in g, 'contatore nella griglia'
    # troppe voci: errore, restano quelle di prima
    C.post('/sala/checklist-voci', data={'voci': '\n'.join('Voce %d' % i for i in range(11))})
    assert 'Al massimo 10' in avvisi(C)
    s = S()
    assert len(sala.voci_checklist(s)) == 3
    s.close()
    # nessuna voce: niente checklist, niente contatore
    C.post('/sala/checklist-voci', data={'voci': ''})
    g = html(C.get('/giorno/%s?struttura=1' % MAR))
    assert 'checklist-voce' not in g and 'Checklist pre-operatoria' not in html(C.get('/appuntamento/%d' % aid))
    # di nuovo quelle predefinite: salvate come "predefinite", non come copia
    C.post('/sala/checklist-voci', data={'voci': '\n'.join(CHECKLIST_PREDEFINITA)})
    s = S()
    assert sala.voci_checklist(s) == CHECKLIST_PREDEFINITA
    s.close()
    # un valore rovinato nel database torna alle predefinite
    s = S()
    scrivi_impostazione(s, 'checklist_voci', '{rotto')
    s.commit()
    assert sala.voci_checklist(s) == CHECKLIST_PREDEFINITA
    s.close()


def ck_notifica():
    S, C = mondo()
    I = ids(S)
    a1 = nuovo_app(S, I['Sala A'], I['Borrelli'], DOMANI, 9, cognome='Rossi')
    a2 = nuovo_app(S, I['Sala B'], I['Mancini'], DOMANI, 9, cognome='Bianchi')
    nuovo_app(S, I['Ambulatorio 1'], I['Lippi'], DOMANI, 9, cognome='Verdi')
    s = S()
    n = [x for x in notifiche(s) if x['titolo'] == 'Checklist pre-operatoria']
    s.close()
    assert len(n) == 1 and '2 interventi su 2' in n[0]['testo'] and n[0]['testo'].startswith('Domani'), n
    chiave = n[0]['chiave']
    for v in CHECKLIST_PREDEFINITA:
        C.post('/appuntamento/%d/checklist' % a1, data={'voce': v, 'fatto': '1'})
    s = S()
    n = [x for x in notifiche(s) if x['titolo'] == 'Checklist pre-operatoria']
    s.close()
    assert len(n) == 1 and '1 intervento su 2' in n[0]['testo'] and n[0]['chiave'] != chiave, n
    for v in CHECKLIST_PREDEFINITA:
        C.post('/appuntamento/%d/checklist' % a2, data={'voce': v, 'fatto': '1'})
    s = S()
    assert not [x for x in notifiche(s) if x['titolo'] == 'Checklist pre-operatoria']
    s.close()
    # un intervento disdetto non chiede la checklist
    nuovo_app(S, I['Sala A'], I['Ferri'], DOMANI, 14, stato='DISDETTO', cognome='Neri')
    s = S()
    assert not [x for x in notifiche(s) if x['titolo'] == 'Checklist pre-operatoria']
    s.close()
    j = C.get('/notifiche.json?struttura=1').get_json()
    assert isinstance(j, list)


prova('spunte una per una e tutte insieme, oracolo sulle voci fatte, voci e indirizzi estranei', ck_spunte)
prova('voci della checklist da Impostazioni: doppioni, troppe, nessuna, valore rovinato', ck_voci)
prova('notifica del giorno prima: conta gli incompleti, sparisce quando è tutto fatto', ck_notifica)


# ============================================================ lista operatoria
area('lista operatoria')


def lo_foglio():
    S, C = mondo()
    I = ids(S)
    a = nuovo_app(S, I['Sala A'], I['Borrelli'], MAR, 9, cognome='Rossi', prestazione_id=I['Rinoplastica'],
                  extra=json.dumps({'Medico anestesista': 'ROMANO', 'Protesi': '350cc'}), degenza='NOTTE')
    nuovo_app(S, I['Sala B'], I['Mancini'], MAR, 11, cognome='Bianchi', degenza='DH')
    nuovo_app(S, I['Sala B'], I['Mancini'], MAR, 13, cognome='Gialli', stato='DISDETTO')
    nuovo_app(S, I['Ambulatorio 1'], I['Lippi'], MAR, 9, cognome='Verdi')
    C.post('/appuntamento/%d/checklist' % a, data={'voce': 'Consenso firmato', 'fatto': '1'})
    r = C.get('/lista-operatoria/%s?struttura=1' % MAR)
    t = testo(r)
    assert r.status_code == 200 and '2 interventi' in t, t[:300]
    assert 'Rossi' in t and 'Bianchi' in t and 'Verdi' not in t and 'Gialli' not in t, 'pazienti sbagliati'
    assert 'ROMANO' in t and 'Protesi: 350cc' in t and 'Medico anestesista: ROMANO' not in t, 'anestesista'
    assert 'Notte' in t and 'DH' in t, 'degenza'
    riga_rossi = t.split('Rossi')[1].split('Sala B')[0]
    assert 'Esami pre-operatori, Anestesista confermato' in riga_rossi and 'Consenso firmato' not in riga_rossi, riga_rossi
    assert t.index('Sala A') < t.index('Sala B'), 'ordine delle sale'
    assert 'letti la notte 1' in t
    t = testo(C.get('/lista-operatoria/%s?struttura=1' % (MAR + timedelta(days=1))))
    assert 'Nessun intervento in questo giorno' in t
    # la pagina del giorno della sala
    t = testo(C.get('/sala/%s?struttura=1' % MAR))
    assert 'Rossi' in t and 'Verdi' not in t and '1/5' in t and 'In sala: Borrelli (1), Mancini (1)' in t, t[:800]
    t = testo(C.get('/sala/%s?struttura=1&giorni=7' % (MAR - timedelta(days=2))))
    assert 'Rossi' in t and '7 giorni' in t


prova('una tabella per sala, solo interventi attivi, anestesista, degenza, cosa manca', lo_foglio)


# ================================================================ posti letto
area('posti letto')


def pl_oracolo():
    S, C = mondo(letti=2)
    I = ids(S)
    rnd = random.Random(143)
    casi = []
    for i in range(40):
        g = MAR + timedelta(days=rnd.randint(-5, 12))
        degenza = rnd.choice(['', 'DH', 'NOTTE', 'RICOVERO', 'RICOVERO'])
        notti = rnd.choice([None, 1, 2, 4]) if degenza == 'RICOVERO' else None
        stato = rnd.choice(['PRENOTATO', 'CONFERMATO', 'ARRIVATO', 'DISDETTO'])
        stanza = rnd.choice(['Sala A', 'Sala B'])
        ora = 7 + i // 3
        nuovo_app(S, I[stanza], I['Borrelli'], g, ora % 24, 20 * (i % 3), minuti=15, stato=stato, degenza=degenza, notti=notti)
        casi.append((g, degenza, notti, stato))
    dal = MAR
    s = S()
    notti_calc = sala.notti_occupate(s, 1, dal, dal + timedelta(days=9))
    s.close()
    for k in range(10):
        n = dal + timedelta(days=k)
        atteso = 0
        for g, deg, nt, stato in casi:
            if stato == 'DISDETTO':
                continue
            quante = {'NOTTE': 1, 'RICOVERO': max(nt or 1, 1)}.get(deg, 0)
            if g <= n < g + timedelta(days=quante):
                atteso += 1
        assert len(notti_calc[n]) == atteso, 'notte %s: %d invece di %d' % (n, len(notti_calc[n]), atteso)
    oltre_attese = [dal + timedelta(days=k) for k in range(10) if len(notti_calc[dal + timedelta(days=k)]) > 2]
    t = testo(C.get('/posti-letto?dal=%s&struttura=1' % dal))
    assert t.count('non bastano') == 0  # la pagina non ha frasi, solo righe evidenziate
    assert html(C.get('/posti-letto?dal=%s&struttura=1' % dal)).count('<tr class="oltre') >= len(oltre_attese)
    return '%d notti oltre i letti' % len(oltre_attese)


def pl_avvisi():
    S, C = mondo(letti=1)
    I = ids(S)
    nuovo_app(S, I['Sala A'], I['Borrelli'], MAR, 9, degenza='RICOVERO', notti=3, cognome='Primo')
    # la seconda notte dopo il ricovero: il letto e' preso
    r = C.post('/appuntamento', data=modulo_app(I, 'Sala B', 'Mancini', MAR + timedelta(days=1), degenza='NOTTE'))
    m = avvisi(C)
    assert r.status_code == 302 and 'servono 2 letti e ce ne sono 1' in m, m
    # un DH non occupa letti: nessun avviso
    C.post('/appuntamento', data=modulo_app(I, 'Sala B', 'Mancini', MAR + timedelta(days=2), ora='12:00', degenza='DH'))
    assert 'Posti letto' not in avvisi(C)
    # dopo il ricovero il letto e' libero
    C.post('/appuntamento', data=modulo_app(I, 'Sala B', 'Ferri', MAR + timedelta(days=3), ora='12:00', degenza='NOTTE'))
    assert 'Posti letto' not in avvisi(C)
    # letti non indicati: nessun controllo
    s = S()
    s.get(Struttura, 1).posti_letto = None
    s.commit()
    s.close()
    C.post('/appuntamento', data=modulo_app(I, 'Sala A', 'Ferri', MAR + timedelta(days=1), ora='14:00', degenza='NOTTE'))
    assert 'Posti letto' not in avvisi(C)


def pl_notifica_e_struttura():
    S, C = mondo(letti=1)
    I = ids(S)
    nuovo_app(S, I['Sala A'], I['Borrelli'], DOMANI, 9, degenza='NOTTE')
    nuovo_app(S, I['Sala B'], I['Mancini'], DOMANI, 9, degenza='NOTTE')
    s = S()
    n = [x for x in notifiche(s) if x['titolo'] == 'Posti letto']
    s.close()
    assert len(n) == 1 and n[0]['livello'] == 'errore' and 'servono 2 letti' in n[0]['testo'], n
    # il numero di letti si scrive nella scheda della struttura
    t = html(C.get('/anagrafiche/strutture/1'))
    assert 'name="posti_letto"' in t and 'value="1"' in t
    base = {'nome': 'Clinica', 'sezione_orario': '1', 'ora_apertura': '08:00', 'ora_chiusura': '20:00',
            'passo': '30', 'giorno_0': '1', 'giorno_1': '1'}
    for valore, atteso, errore in (('4', 4, False), ('', None, False), ('0', None, False),
                                   ('-2', None, True), ('abc', None, True), ('501', None, True)):
        r = C.post('/anagrafiche/strutture/1', data=dict(base, posti_letto=valore))
        s = S()
        v = s.get(Struttura, 1).posti_letto
        s.close()
        if errore:
            assert r.status_code == 200 and 'Posti letto' in testo(r), valore
        else:
            assert r.status_code == 302 and v == atteso, (valore, v)
    s = S()
    assert not [x for x in notifiche(s) if x['titolo'] == 'Posti letto']
    s.close()
    # nella griglia: i letti della notte
    t = testo(C.get('/giorno/%s?struttura=1' % DOMANI))
    assert 'letti la notte 2' in t, 'riga sala operatoria nella griglia'


prova('notti occupate contro un conto fatto a parte (40 interventi a caso, disdetti esclusi)', pl_oracolo)
prova('avviso salvando: letti che non bastano, DH e dopo il ricovero no, letti non indicati no', pl_avvisi)
prova('notifica quando non bastano, numero di letti nella scheda della struttura', pl_notifica_e_struttura)


# ===================================================================== oggi
area('pagina Oggi')


def og_avvio():
    S, C = mondo()
    r = C.get('/')
    assert r.status_code == 302 and r.headers['Location'].endswith('/oggi'), r.headers.get('Location')
    r = C.get('/oggi')
    assert r.status_code == 200 and 'Adesso e nelle prossime due ore' in html(r)
    assert re.search(r'class="attivo"[^>]*>Oggi</a>', html(r)), 'Oggi non evidenziato nel menu'
    # senza strutture: la pagina che spiega cosa manca
    s = S()
    s.get(Struttura, 1).attiva = False
    s.commit()
    s.close()
    assert C.get('/oggi').status_code == 200


def og_quadro():
    S, C = mondo(letti=3)
    I = ids(S)
    adesso = datetime.combine(OGGI, time(11, 0))
    def app(h, m, stato='PRENOTATO', stanza='Ambulatorio 1', medico='Lippi', **x):
        return nuovo_app(S, I[stanza], I[medico], OGGI, h, m, minuti=30, stato=stato, cognome='P%02d%02d' % (h, m), **x)
    ritardo = [app(8, 30), app(10, 45, 'CONFERMATO')]
    poco = [app(11, 30), app(12, 55, 'CONFERMATO')]
    app(7, 30)                                   # oltre tre ore: va nella chiusura giornata
    app(13, 30)                                  # oltre due ore
    app(10, 0, 'ARRIVATO')                       # arrivato: non si aspetta
    app(11, 15, 'DISDETTO')
    arr = app(10, 45, 'ARRIVATO', stanza='Ambulatorio 2')   # ancora in struttura alle 11
    s = S()
    st = s.get(Struttura, 1)
    s.add(Attivita(testo='Richiamare per il referto', per_il=OGGI - timedelta(days=2)))
    s.add(Attivita(testo='Domani non ancora', per_il=DOMANI))
    s.commit()
    q = cruscotto.quadro_di_oggi(s, st, adesso)
    assert [a.id for a in q['in_ritardo']] == ritardo, [a.inizio for a in q['in_ritardo']]
    assert [a.id for a in q['tra_poco']] == poco, [a.inizio for a in q['tra_poco']]
    assert [a.id for a in q['in_struttura']] == [arr]
    assert q['totale'] == 8 and q['arrivati'] == 2, (q['totale'], q['arrivati'])
    assert [x.testo for x in q['cose']] == ['Richiamare per il referto']
    s.close()
    # il pulsante Arrivato torna alla pagina Oggi
    r = C.post('/appuntamento/%d/stato' % ritardo[0], data={'stato': 'ARRIVATO', 'torna': '/oggi?struttura=1'})
    assert r.status_code == 302 and r.headers['Location'].endswith('/oggi?struttura=1')
    assert leggi(S, ritardo[0])['stato'] == 'ARRIVATO'
    t = testo(C.get('/oggi?struttura=1'))
    assert 'Richiamare per il referto' in t and 'Cassa di oggi' in t and 'Sala operatoria' in t


prova('all\'avvio si apre Oggi; senza strutture non cade', og_avvio)
prova('in ritardo, tra poco, in struttura, cose da fare: contro gli orari scelti apposta', og_quadro)


# ======================================================= riepilogo per medico
area('riepilogo mensile per medico')


def ri_oracolo():
    from openpyxl import load_workbook
    S, C = mondo()
    I = ids(S)
    primo = (MAR.replace(day=1) + timedelta(days=40)).replace(day=1)
    rnd = random.Random(5)
    atteso = {}
    for i in range(60):
        g = primo + timedelta(days=rnd.randint(0, 27))
        medico = rnd.choice(['Borrelli', 'Mancini', 'Lippi'])
        stanza = 'Sala A' if medico != 'Lippi' else 'Ambulatorio %d' % rnd.randint(1, 3)
        stato = rnd.choice(['PRENOTATO', 'CONFERMATO', 'ARRIVATO', 'NON_PRESENTATO', 'DISDETTO'])
        importo = rnd.choice([None, 8000, 150000])
        aid = nuovo_app(S, I[stanza], I[medico], g, 7 + i % 12, 0, minuti=30, stato=stato, importo_cent=importo)
        d = atteso.setdefault(medico, {'n': 0, 'stati': {}, 'previsto': 0})
        d['n'] += 1
        d['stati'][stato] = d['stati'].get(stato, 0) + 1
        if stato in ('PRENOTATO', 'CONFERMATO', 'ARRIVATO'):
            d['previsto'] += importo or 0
    # fuori mese: non conta
    nuovo_app(S, I['Sala A'], I['Borrelli'], primo - timedelta(days=1), 9, stato='ARRIVATO')
    s = S()
    fogli = cruscotto.riepilogo_medici(s, primo, (primo + timedelta(days=31)).replace(day=1) - timedelta(days=1))
    s.close()
    trovato = {f['operatore'].cognome: f for f in fogli}
    assert set(trovato) == set(atteso), (set(trovato), set(atteso))
    for m, d in atteso.items():
        f = trovato[m]
        assert len(f['apps']) == d['n'] and f['previsto'] == d['previsto'], (m, len(f['apps']), d)
        assert all(f['conteggio'].get(k, 0) == v for k, v in d['stati'].items()), (m, f['conteggio'], d['stati'])
    aaaamm = primo.strftime('%Y-%m')
    t = testo(C.get('/riepilogo-medici/%s' % aaaamm))
    assert all(m in t for m in atteso) and 'Manda per email a borrelli@example.it' in t
    r = C.get('/riepilogo-medici/%s?medico=%d' % (aaaamm, I['Mancini']))
    assert 'Mancini' in testo(r) and 'Borrelli' not in testo(r).split('Scarica in Excel')[1]
    corpo = unquote(re.search(r'href="(mailto:[^"]+)"', html(C.get('/riepilogo-medici/%s?medico=%d' % (aaaamm, I['Borrelli'])))).group(1))
    assert 'Appuntamenti: %d' % atteso['Borrelli']['n'] in corpo and len(corpo) < 2100, corpo[:200]
    r = C.get('/riepilogo-medici/%s/excel' % aaaamm)
    assert r.status_code == 200
    wb = load_workbook(io.BytesIO(r.data))
    assert wb.sheetnames[0] == 'Riepilogo' and len(wb.sheetnames) == 1 + len(atteso), wb.sheetnames
    righe = {x[0].value: x for x in wb['Riepilogo'].iter_rows(min_row=3)}
    for m, d in atteso.items():
        riga = next(v for k, v in righe.items() if k and k.startswith(m))
        assert riga[2].value == d['n'] and abs(riga[8].value - d['previsto'] / 100.0) < 0.001, (m, riga[2].value)
    assert righe['Totale'][2].value == sum(d['n'] for d in atteso.values())
    for m, d in atteso.items():
        foglio = next(w for w in wb.worksheets[1:] if w['A1'].value.startswith(m))
        assert foglio.max_row - 2 == d['n'], (m, foglio.max_row)
    return '%d medici, %d appuntamenti' % (len(atteso), sum(d['n'] for d in atteso.values()))


def ri_nomi_fogli():
    from openpyxl import load_workbook
    S, C = mondo()
    s = S()
    lungo = 'De Santis Castellammare di Stabia'
    for nome in ('Anna', 'Maria', 'Rosa'):
        s.add(Operatore(cognome=lungo, nome=nome))
    s.add(Operatore(cognome='Rossi [chirurgia]/*?', nome=''))
    s.commit()
    medici = s.scalars(select(Operatore).where(Operatore.cognome.in_([lungo, 'Rossi [chirurgia]/*?']))).all()
    rid = s.scalars(select(Risorsa.id)).first()
    s.close()
    for o in medici:
        nuovo_app(S, rid, o.id, MAR, 8 + o.id % 10, 0, minuti=15)
    r = C.get('/riepilogo-medici/%s/excel' % MAR.strftime('%Y-%m'))
    wb = load_workbook(io.BytesIO(r.data))
    nomi = wb.sheetnames
    assert len(nomi) == 5 and len({n.lower() for n in nomi}) == 5 and all(len(n) <= 31 for n in nomi), nomi
    # mese sbagliato nell'indirizzo: il mese corrente, non un errore
    for x in ('abc', '2026-13', '0000-01', '99999-01', '2026-00'):
        assert C.get('/riepilogo-medici/%s' % x).status_code == 200, x
        assert C.get('/riepilogo-medici/%s/excel' % x).status_code == 200, x


prova('conteggi per stato e importi contro un oracolo, email, Excel con un foglio per medico', ri_oracolo)
prova('nomi dei fogli Excel: lunghi, uguali, caratteri vietati; mesi sbagliati', ri_nomi_fogli)


# ============================================================ giorni di sala
area('giorni di sala dei chirurghi')


def gs_proposta_e_griglia():
    S, C = mondo()
    I = ids(S)
    # Borrelli: tre martedi e un venerdi; Mancini: due venerdi; Ferri: un lunedi
    for k in range(3):
        nuovo_app(S, I['Sala A'], I['Borrelli'], MAR - timedelta(weeks=k + 1), 9)
    nuovo_app(S, I['Sala A'], I['Borrelli'], VEN - timedelta(weeks=1), 9)
    for k in range(2):
        nuovo_app(S, I['Sala B'], I['Mancini'], VEN - timedelta(weeks=k + 1), 9)
    nuovo_app(S, I['Sala B'], I['Ferri'], MAR - timedelta(days=1), 9)
    # due interventi lo stesso giorno contano una volta
    nuovo_app(S, I['Sala A'], I['Ferri'], MAR - timedelta(days=1), 11)
    t = html(C.get('/sala/chirurghi?proponi=1'))
    spuntati = set(re.findall(r'name="sala_(\d+)_(\d)" value="1" checked', t))
    atteso = {(str(I['Borrelli']), '1'), (str(I['Mancini']), '4')}
    assert spuntati == atteso, (spuntati, atteso)
    assert 'Lippi' in t.split('Altri medici')[1], 'chi non opera sta fra gli altri'
    dati = {'presente_%d' % I[m]: '1' for m in ('Borrelli', 'Mancini', 'Ferri', 'Lippi')}
    dati.update({'sala_%s_%s' % x: '1' for x in atteso})
    r = C.post('/sala/chirurghi', data=dati)
    assert r.status_code == 302 and '2 medici cambiati' in avvisi(C)
    s = S()
    assert s.get(Operatore, I['Borrelli']).giorni_sala == '0100000' and s.get(Operatore, I['Ferri']).giorni_sala == ''
    s.close()
    # una riga non inviata resta com'era
    C.post('/sala/chirurghi', data={'presente_%d' % I['Mancini']: '1'})
    s = S()
    assert s.get(Operatore, I['Borrelli']).giorni_sala == '0100000' and s.get(Operatore, I['Mancini']).giorni_sala == ''
    s.close()
    # nella griglia del martedi: Borrelli libero; se ha un intervento e' "in sala"
    t = testo(C.get('/giorno/%s?struttura=1' % MAR))
    assert 'liberi Borrelli' in t, 'chirurgo libero non indicato'
    nuovo_app(S, I['Sala A'], I['Borrelli'], MAR, 8)
    t = testo(C.get('/giorno/%s?struttura=1' % MAR))
    assert 'in sala Borrelli' in t and 'liberi Borrelli' not in t
    # assente: non e' libero
    s = S()
    s.add(Assenza(operatore_id=I['Borrelli'], dal=MAR + timedelta(days=7), al=MAR + timedelta(days=7), motivo='Ferie'))
    s.commit()
    s.close()
    t = testo(C.get('/sala/%s?struttura=1' % (MAR + timedelta(days=7))))
    assert 'Assenti: Borrelli' in t and 'liberi: Borrelli' not in t, t[:600]


def gs_avviso():
    S, C = mondo()
    I = ids(S)
    s = S()
    s.get(Operatore, I['Borrelli']).giorni_sala = '0100000'
    s.commit()
    s.close()
    C.post('/appuntamento', data=modulo_app(I, 'Sala A', 'Borrelli', VEN))
    assert 'Borrelli Ugo di solito opera: martedì.' in avvisi(C)
    C.post('/appuntamento', data=modulo_app(I, 'Sala A', 'Borrelli', MAR))
    assert 'di solito opera' not in avvisi(C)
    # in ambulatorio nessun avviso, e chi non ha giorni indicati nemmeno
    C.post('/appuntamento', data=modulo_app(I, 'Ambulatorio 1', 'Borrelli', VEN, ora='12:00'))
    assert 'di solito opera' not in avvisi(C)
    C.post('/appuntamento', data=modulo_app(I, 'Sala B', 'Mancini', VEN))
    assert 'di solito opera' not in avvisi(C)
    # un valore storto nel database vale "nessun giorno"
    s = S()
    s.get(Operatore, I['Borrelli']).giorni_sala = '01x'
    s.commit()
    assert s.get(Operatore, I['Borrelli']).giorni_di_sala == set()
    s.close()


prova('proposta dagli interventi (almeno due giorni diversi), salvataggio, griglia: in sala, liberi, assenti', gs_proposta_e_griglia)
prova('avviso quando un chirurgo opera in un giorno che non è il suo', gs_avviso)


# ============================================================== importazione
area('importazione')


def im_degenza():
    from openpyxl import Workbook
    S, C = mondo()
    wb = Workbook()
    ws = wb.active
    ws.append(['DATA', 'ORA', 'SALA', 'OPERATORE', 'PAZIENTE', 'INTERVENTO', 'DEGENZA', 'ANESTESISTA'])
    for i, deg in enumerate(['DH', 'NOTTE', 'RO', '2 NOTTI', '?', None]):
        ws.append([datetime.combine(MAR, time(0, 0)), time(8 + i, 0), 'SALA A', 'BORRELLI',
                   'PAZIENTE%s MARIA' % 'ABCDEF'[i], 'RINOPLASTICA', deg, 'ROMANO'])
    f = io.BytesIO()
    wb.save(f)
    r = C.post('/importa', data={'file': (io.BytesIO(f.getvalue()), 'interventi.xlsx')}, content_type='multipart/form-data')
    assert r.status_code == 302, r.status_code
    indirizzo = r.headers['Location']
    anteprima = C.get(indirizzo)
    assert 'Degenza: notte' in testo(anteprima), 'degenza nell\'anteprima'
    r = C.post(indirizzo, data={'azione': 'importa', 'struttura': '1'})
    assert 'Importazione completata' in html(r), avvisi(C)
    s = S()
    apps = {a.paziente.cognome: a for a in s.scalars(select(Appuntamento)) if a.paziente}
    esito = {k[-1]: (v.degenza, v.notti) for k, v in apps.items()}
    assert esito == {'a': ('DH', None), 'b': ('NOTTE', None), 'c': ('RICOVERO', None), 'd': ('RICOVERO', 2),
                     'e': ('', None), 'f': ('', None)}, esito
    e = next(v for k, v in apps.items() if k.endswith('e'))
    assert 'Degenza: ?' in e.note and 'Degenza' not in (e.extra or ''), (e.note, e.extra)
    p = s.scalars(select(Prestazione).where(Prestazione.nome.ilike('rinoplastica'))).first()
    assert 'Degenza' not in (p.campi_extra or ''), p.campi_extra
    s.close()


prova('la colonna DEGENZA diventa il campo degenza; "?" nelle note', im_degenza)


# ================================================================ robustezza
area('robustezza')


def ro_indirizzi():
    S, C = mondo(letti=2)
    I = ids(S)
    aid = nuovo_app(S, I['Sala A'], I['Borrelli'], MAR, 9, cognome='Rossi')
    sporchi = ['0', '-1', '99999999999999999999999', 'abc', '%00', "1'--", '2026-02-30', '../1', '%E2%80%AE']
    modelli_url = ['/sala/%s', '/sala/%s?giorni=%s', '/lista-operatoria/%s', '/posti-letto?dal=%s',
                   '/posti-letto?struttura=%s', '/sala/chirurghi?struttura=%s', '/riepilogo-medici/%s',
                   '/riepilogo-medici/2026-10?medico=%s', '/riepilogo-medici/2026-10/excel?struttura=%s',
                   '/oggi?struttura=%s', '/sala/%s?struttura=%s', '/appuntamento/%s/checklist']
    n = 0
    for u in modelli_url:
        for x in sporchi:
            indirizzo = u % ((x,) * u.count('%s'))
            r = C.get(indirizzo)
            assert r.status_code in (200, 302, 404, 405), '%s -> %d' % (indirizzo, r.status_code)
            n += 1
    rnd = random.Random(3)
    campi = ['voce', 'fatto', 'spunte', 'torna', 'voci', 'presente_1', 'sala_1_1', 'degenza', 'notti', 'posti_letto']
    for indirizzo in ['/appuntamento/%d/checklist' % aid, '/sala/checklist-voci', '/sala/chirurghi',
                      '/appuntamento/%d' % aid, '/anagrafiche/strutture/1']:
        for _ in range(12):
            dati = {k: rnd.choice(sporchi + ['', 'x' * 5000, 'Consenso firmato']) for k in rnd.sample(campi, 4)}
            r = C.post(indirizzo, data=dati)
            assert r.status_code in (200, 302, 400, 404), '%s %s -> %d' % (indirizzo, dati, r.status_code)
            n += 1
    # un checklist rovinato nel database non rompe griglia, sala, Oggi, lista
    s = S()
    s.get(Appuntamento, aid).checklist = '[1, 2'
    s.get(Appuntamento, aid).degenza = 'STRANO'
    s.commit()
    s.close()
    for u in ('/giorno/%s?struttura=1' % MAR, '/sala/%s' % MAR, '/lista-operatoria/%s' % MAR, '/oggi',
              '/appuntamento/%d' % aid, '/posti-letto', '/riepilogo-medici/%s' % MAR.strftime('%Y-%m')):
        r = C.get(u)
        assert r.status_code == 200, '%s -> %d' % (u, r.status_code)
        n += 1
    return '%d richieste' % n


def ro_senza_sale():
    """Una struttura senza sale operatorie: niente voce Sala nel menu, niente riga nella griglia."""
    S = crea_sessione('sqlite:///' + percorso_nuovo())
    s = S()
    servizi.prepara_primo_avvio(s)
    s.add(Operatore(cognome='Lippi'))
    s.commit()
    s.close()
    C = collega(S)
    t = html(C.get('/giorno/%s?struttura=1' % MAR))
    assert '>Sala</a>' not in t and 'sala-giorno' not in t
    assert 'non ha stanze di tipo' in html(C.get('/sala/%s' % MAR))
    assert C.get('/oggi').status_code == 200 and 'Sala operatoria' not in testo(C.get('/oggi'))


prova('indirizzi sporchi e moduli a caso sulle pagine nuove: mai errore 500', ro_indirizzi)
prova('senza sale operatorie: le parti nuove non compaiono', ro_senza_sale)


# =====================================================================
if __name__ == '__main__':
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
