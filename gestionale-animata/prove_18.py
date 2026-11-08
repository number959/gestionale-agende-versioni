# -*- coding: utf-8 -*-
"""Prove della 1.8: i turni del personale.

Le regole (sovrapposizioni anche a cavallo della mezzanotte, riposi brevi,
riposi e assenze che valgono tutto il giorno), i conti (ore, notti, festivi,
assenze, presenti ora per ora, coperture minime), lo schema a rotazione e la
copia della settimana, si confrontano con oracoli scritti qui, indipendenti dal
programma. Poi le pagine e le richieste: metti, aggiungi, togli, annulla e
rifai (lo stato di prima torna identico), errori e protezioni, Excel,
aggiornamento del database dalla versione 8, e un giro di modifiche a caso
con gli invarianti controllati dopo ogni passo. Tutti i nomi sono inventati."""
import json
import os
import random
import re
import shutil
import sqlite3
import sys
import traceback
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from html import unescape
from io import BytesIO

import logging
logging.getLogger().setLevel(logging.CRITICAL)

from sqlalchemy import select

import servizi
import viste
import personale as PE
import app as A
from modelli import (crea_sessione, VERSIONE_SCHEMA, TIPI_TURNO_INIZIALI, Struttura, Operatore, Persona, TipoTurno,
                     TurnoPersonale, CoperturaMinima, testo_su, leggi_impostazione)

A.app.config['TESTING'] = True
CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = os.path.join(CARTELLA, 'prove_18_tmp')
shutil.rmtree(PROVVISORIA, ignore_errors=True)
os.makedirs(PROVVISORIA)
esiti, _area, _n = [], [''], [0]
OGGI = date.today()
SOLO = [x for x in os.environ.get('PROVE_SOLO', '').split(',') if x]
CAMBIA = '/personale/turni/cambia'


def area(nome):
    _area[0] = nome


def prova(nome, f):
    if SOLO and f.__name__ not in SOLO:
        return
    try:
        esiti.append(('OK', _area[0], nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', _area[0], nome, str(e) or 'asserzione fallita'))
    except Exception:
        esiti.append(('ERRORE', _area[0], nome, traceback.format_exc().strip().splitlines()[-1]))


# ================================================================ il mondo
def percorso_nuovo(nome='db'):
    _n[0] += 1
    dove = os.path.join(PROVVISORIA, 'm%d' % _n[0])
    os.makedirs(dove)
    return os.path.join(dove, '%s.db' % nome)


def mondo(con_persone=True):
    """Un gestionale nuovo, con un medico dell'agenda e (se richiesto) un po'
    di personale: tre infermieri, due OSS, il medico collegato, una persona
    non piu' in servizio."""
    S = crea_sessione('sqlite:///' + percorso_nuovo())
    s = S()
    servizi.prepara_primo_avvio(s)
    s.add(Operatore(cognome='Provolo', nome='Ugo', specialita='prove'))
    s.flush()
    if con_persone:
        op = s.scalars(select(Operatore).where(Operatore.cognome == 'Provolo')).first()
        s.add_all([Persona(cognome='Fittizi', nome='Ada', ruolo='INFERMIERE', minuti_settimana=36 * 60),
                   Persona(cognome='Esempio', nome='Bruno', ruolo='INFERMIERE', minuti_settimana=36 * 60),
                   Persona(cognome='Fintoni', nome='Paolo', ruolo='INFERMIERE'),
                   Persona(cognome='Modellini', nome='Carla', ruolo='OSS', minuti_settimana=30 * 60),
                   Persona(cognome='Prototti', nome='Gino', ruolo='OSS'),
                   Persona(cognome='Provolo', nome='Ugo', ruolo='MEDICO', operatore_id=op.id),
                   Persona(cognome='Vecchietti', nome='Eva', ruolo='INFERMIERE', attiva=False)])
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


def avvisi(C):
    with C.session_transaction() as sess:
        m = sess.get('_flashes', [])
        sess['_flashes'] = []
    return ' '.join(unescape(t) for _, t in m)


def persone(S):
    s = S()
    try:
        return {p.cognome: p.id for p in s.scalars(select(Persona))}
    finally:
        s.close()


def tipi(S):
    s = S()
    try:
        return {t.codice: t.id for t in s.scalars(select(TipoTurno))}
    finally:
        s.close()


def k(pid, g):
    return '%d_%s' % (pid, g.isoformat())


def cambia(C, **dati):
    r = C.post(CAMBIA, json=dati)
    try:
        return r.status_code, json.loads(r.get_data(as_text=True))
    except ValueError:
        return r.status_code, None


def lunedi(g=None):
    g = g or OGGI
    return g - timedelta(days=g.weekday())


def stato(S, pids=None):
    """Lo stato di tutti i turni: {(persona, giorno): [(tipo, inizio, fine, area, note)]} in ordine."""
    s = S()
    try:
        fuori = defaultdict(list)
        for t in s.scalars(select(TurnoPersonale)):
            if pids is not None and t.persona_id not in pids:
                continue
            fuori[(t.persona_id, t.giorno)].append((t.tipo_id, t.inizio.isoformat() if t.inizio else None,
                                                    t.fine.isoformat() if t.fine else None, t.area or '', t.note or ''))
        return {x: sorted(v, key=lambda y: (y[1] or '', y[0] or 0)) for x, v in fuori.items()}
    finally:
        s.close()


def invarianti(S):
    """Quello che deve valere sempre, qualunque cosa si sia fatta."""
    s = S()
    try:
        per_persona = defaultdict(list)
        per_cella = defaultdict(list)
        for t in s.scalars(select(TurnoPersonale)):
            per_persona[t.persona_id].append(t)
            per_cella[(t.persona_id, t.giorno)].append(t)
            if t.tipo is None:
                assert t.inizio is not None and t.fine is not None, 'turno senza tipo e senza orario'
            if t.tipo is not None and not t.tipo.con_orario:
                assert t.inizio is None and t.fine is None, 'riposo o assenza con un orario'
            if t.inizio is not None:
                assert t.fine > t.inizio and t.fine - t.inizio <= timedelta(hours=24), 'orario rovesciato'
                assert t.inizio.date() == t.giorno, 'un turno comincia nel suo giorno'
                assert t.minuti >= 0
        for lista in per_persona.values():
            con = [t for t in lista if t.inizio is not None]
            for i, a in enumerate(con):
                for b in con[i + 1:]:
                    assert not (a.inizio < b.fine and b.inizio < a.fine), \
                        'sovrapposti: %s e %s (persona %d)' % (PE.descrivi(a), PE.descrivi(b), a.persona_id)
        for (pid, g), lista in per_cella.items():
            if any(t.inizio is None for t in lista):
                assert len(lista) == 1, 'un riposo o un\'assenza insieme ad altri turni il %s' % g
    finally:
        s.close()


# ---------------------------------------------------------------- oracoli
def pasqua(anno):
    """Pasqua (calendario gregoriano, algoritmo di Meeus): scritto qui, non quello del programma."""
    a, b, c = anno % 19, anno // 100, anno % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, kk = c // 4, c % 4
    ll = (32 + 2 * e + 2 * i - h - kk) % 7
    m = (a + 11 * h + 22 * ll) // 451
    mese = (h + ll - 7 * m + 114) // 31
    giorno = (h + ll - 7 * m + 114) % 31 + 1
    return date(anno, mese, giorno)


FESTE = {(1, 1), (1, 6), (4, 25), (5, 1), (6, 2), (8, 15), (11, 1), (12, 8), (12, 25), (12, 26)}


def festivo_atteso(g):
    # San Francesco (4 ottobre) e' di nuovo festa nazionale dal 2026
    return g.weekday() == 6 or (g.month, g.day) in FESTE or ((g.month, g.day) == (10, 4) and g.year >= 2026) or \
        g == pasqua(g.year) + timedelta(days=1)


def conti_attesi(S, pids, dal, al):
    """Ore, notti, festivi e assenze calcolati qui dai turni del database."""
    s = S()
    try:
        c = defaultdict(lambda: {'lavoro': 0, 'notti': 0, 'festivi': 0, 'assenze': 0, 'reperibilita': 0})
        for t in s.scalars(select(TurnoPersonale)):
            if t.persona_id not in pids or not (dal <= t.giorno <= al):
                continue
            cat = t.tipo.categoria if t.tipo is not None else 'LAVORO'
            if cat == 'LAVORO':
                pausa = t.tipo.pausa_min if t.tipo is not None else 0
                c[t.persona_id]['lavoro'] += max(int((t.fine - t.inizio).total_seconds() // 60) - (pausa or 0), 0)
                c[t.persona_id]['notti'] += t.fine.date() > t.inizio.date()
                c[t.persona_id]['festivi'] += festivo_atteso(t.giorno)
            elif cat == 'REPERIBILITA':
                c[t.persona_id]['reperibilita'] += int((t.fine - t.inizio).total_seconds() // 60)
            elif cat == 'ASSENZA':
                c[t.persona_id]['assenze'] += 1
        return c
    finally:
        s.close()


def mettere(S, pid, g, codice=None, inizio=None, fine=None, aggiungi=False, area='', note=''):
    """Un turno messo direttamente con assegna() (per preparare i casi)."""
    s = S()
    try:
        p = s.get(Persona, pid)
        tipo = s.scalars(select(TipoTurno).where(TipoTurno.codice == codice)).first() if codice else None
        t, avv = PE.assegna(s, p, g, tipo, inizio, fine, area, note, aggiungi=aggiungi)
        s.commit()
        return avv
    finally:
        s.close()


# ================================================================ regole
area('regole dei turni')


def r_orari():
    attesi = {'7': time(7), '7:30': time(7, 30), '07.30': time(7, 30), '0730': time(7, 30), '24': time(0),
              '24:00': time(0), ' 9 ': time(9), '23:59': time(23, 59)}
    for x, atteso in attesi.items():
        assert PE.leggi_ora(x) == atteso, (x, PE.leggi_ora(x))
    for x in ('25', '7:60', 'ab', '', None, '7:3', '24:30', '-1'):
        assert PE.leggi_ora(x) is None, x
    g = date(2026, 10, 12)
    assert PE.intervallo(g, time(21), time(7)) == (datetime(2026, 10, 12, 21), datetime(2026, 10, 13, 7))
    assert PE.intervallo(g, time(7), time(14)) == (datetime(2026, 10, 12, 7), datetime(2026, 10, 12, 14))
    assert PE.intervallo(g, time(8), time(8)) == (datetime(2026, 10, 12, 8), datetime(2026, 10, 13, 8)), \
        'stessa ora: 24 ore (le escludono assegna e i tipi)'
    assert [PE.testo_ore(x) for x in (420, 450, 0, -90, 61)] == ['7', '7:30', '0', '-1:30', '1:01']
    assert [PE.leggi_ore_settimana(x) for x in ('36', '37:30', '37,5', '37.25', '', '81', '7:60', 'x')] == \
        [2160, 2250, 2250, 2235, None, False, False, False]


def r_assegna():
    S, C = mondo()
    P = persone(S)
    g = lunedi() + timedelta(days=7)
    a = P['Fittizi']
    mettere(S, a, g, 'M')
    mettere(S, a, g, 'P')                                        # sostituisce
    assert [x[0] for x in stato(S)[(a, g)]] == [tipi(S)['P']]
    mettere(S, a, g, None, time(8), time(12), aggiungi=True)     # 8-12 e poi 14-21: spezzato
    assert len(stato(S)[(a, g)]) == 2
    try:
        mettere(S, a, g, None, time(11), time(15), aggiungi=True)
        raise AssertionError('accettato un terzo turno sovrapposto')
    except PE.ErroreTurno as e:
        assert 'non possono stare insieme' in str(e), e
    try:
        mettere(S, a, g, 'F', aggiungi=True)
        raise AssertionError('ferie aggiunte a un giorno con turni')
    except PE.ErroreTurno:
        pass
    mettere(S, a, g, 'F')                                        # ferie: prendono il posto dei turni del giorno
    assert stato(S)[(a, g)] == [(tipi(S)['F'], None, None, '', '')]
    try:
        mettere(S, a, g, None, time(8), time(9), aggiungi=True)
        raise AssertionError('turno aggiunto a un giorno di ferie')
    except PE.ErroreTurno:
        pass
    for caso, args in (('inattiva', (P['Vecchietti'], g, 'M')), ('stesso orario', (a, g + timedelta(days=1), None, time(9), time(9))),
                       ('senza orario', (a, g + timedelta(days=1), None))):
        try:
            mettere(S, *args)
            raise AssertionError('accettato: %s' % caso)
        except PE.ErroreTurno:
            pass
    invarianti(S)


def r_mezzanotte():
    S, C = mondo()
    P = persone(S)
    g = lunedi() + timedelta(days=14)
    a = P['Esempio']
    mettere(S, a, g, 'N')                                        # 21-07 del giorno dopo
    try:
        mettere(S, a, g + timedelta(days=1), None, time(6), time(13))
        raise AssertionError('accettato un turno che comincia prima della fine della notte')
    except PE.ErroreTurno as e:
        assert '«Notte»' in str(e), e
    mettere(S, a, g + timedelta(days=1), 'M')                    # 07-14: tocca la fine della notte, va bene
    avv = mettere(S, a, g + timedelta(days=1), 'N')              # e la notte dopo
    mettere(S, a, g + timedelta(days=2), 'SN')                   # smonto notte: tutto il giorno, non si scontra
    try:
        mettere(S, a, g - timedelta(days=1), None, time(22), time(23, 30))
        mettere(S, a, g - timedelta(days=1), None, time(20), time(22), aggiungi=True)
        mettere(S, a, g - timedelta(days=1), None, time(23), time(6), aggiungi=True)
        raise AssertionError('accettata una notte sovrapposta (prima o dopo mezzanotte)')
    except PE.ErroreTurno:
        pass
    invarianti(S)
    st = stato(S)
    assert len(st[(a, g - timedelta(days=1))]) == 2, st[(a, g - timedelta(days=1))]
    return 'avvisi della seconda notte: %s' % (avv or 'nessuno')


def r_riposi():
    S, C = mondo()
    P = persone(S)
    g = lunedi() + timedelta(days=21)
    a, b = P['Fittizi'], P['Esempio']
    mettere(S, a, g, 'P')                                        # 14-21
    avv = mettere(S, a, g + timedelta(days=1), 'M')              # 07-14: 10 ore
    assert any('solo 10 ore di riposo prima del turno' in x for x in avv), avv
    mettere(S, b, g, 'N')
    avv = mettere(S, b, g + timedelta(days=1), 'M')              # nessun riposo
    assert any('nessun riposo prima del turno' in x for x in avv), avv
    avv = mettere(S, b, g + timedelta(days=3), 'M')
    assert not avv, avv
    avv = mettere(S, b, g + timedelta(days=3), None, time(23), time(23, 59), aggiungi=True)   # 9 ore dopo la mattina
    assert any('solo 9 ore' in x for x in avv), avv
    s = S()
    turni = PE.turni_tra(s, g - timedelta(days=1), g + timedelta(days=6))
    flag = PE.avvisi_celle(turni)
    s.close()
    assert flag.get((a, g + timedelta(days=1))) == 'riposo di 10 ore prima', flag
    assert flag.get((b, g + timedelta(days=1))) == 'nessun riposo prima', flag
    assert flag.get((b, g + timedelta(days=3))) == 'riposo di 9 ore prima' and (b, g + timedelta(days=4)) not in flag, flag


def r_festivi():
    sbagliati = []
    g = date(2026, 1, 1)
    while g <= date(2028, 12, 31):
        if bool(PE.festivo(g, None)) != festivo_atteso(g):
            sbagliati.append(g.isoformat())
        g += timedelta(days=1)
    assert not sbagliati, sbagliati[:10]
    assert pasqua(2026) == date(2026, 4, 5) and pasqua(2027) == date(2027, 3, 28)


def r_totali():
    S, C = mondo()
    P = persone(S)
    T = tipi(S)
    rnd = random.Random(18)
    pids = [P['Fittizi'], P['Esempio'], P['Fintoni'], P['Modellini']]
    dal = date(2026, 12, 21)                                     # Natale, Santo Stefano, domeniche
    al = dal + timedelta(days=20)
    codici = ['M', 'P', 'N', 'G', 'RE', 'R', 'SN', 'F', 'MA', 'PE', None]
    for _ in range(160):
        pid = rnd.choice(pids)
        g = dal + timedelta(days=rnd.randrange(21))
        c = rnd.choice(codici)
        try:
            if c is None:
                h = rnd.randrange(0, 24)
                mettere(S, pid, g, None, time(h), time((h + rnd.choice([3, 5, 8, 12])) % 24, rnd.choice([0, 30])),
                        aggiungi=rnd.random() < .3)
            else:
                mettere(S, pid, g, c, aggiungi=rnd.random() < .2)
        except PE.ErroreTurno:
            pass
    invarianti(S)
    attesi = conti_attesi(S, set(pids), dal, al)
    s = S()
    calcolati = PE.totali([t for t in PE.turni_tra(s, dal, al) if t.persona_id in pids])
    s.close()
    for pid in pids:
        a, c = attesi[pid], calcolati.get(pid)
        if c is None:
            assert not any(a.values()), (pid, a)
            continue
        got = {'lavoro': c['lavoro'], 'notti': c['notti'], 'festivi': c['festivi'], 'assenze': sum(c['assenze'].values()),
               'reperibilita': c['reperibilita']}
        assert got == dict(a), (pid, got, dict(a))
    del T


def r_presenti_ora():
    S, C = mondo()
    P = persone(S)
    g = lunedi() + timedelta(days=28)
    mettere(S, P['Fittizi'], g - timedelta(days=1), 'N')         # 21-07: ore 0..6
    mettere(S, P['Esempio'], g, 'M')                             # 07-14
    mettere(S, P['Fintoni'], g, None, time(7, 30), time(14))     # mezz'ora alle 7: conta
    mettere(S, P['Modellini'], g, None, time(8, 45), time(12))   # 15 minuti alle 8: non conta
    mettere(S, P['Prototti'], g, 'N')                            # 21-07: ore 21..23
    mettere(S, P['Provolo'], g, 'RE')                            # reperibilita': non e' lavoro
    s = S()
    turni = [t for t in PE.turni_tra(s, g - timedelta(days=1), g)]
    ore = PE.presenti_per_ora(turni, g)
    quanti = [len(x) for x in ore]
    s.close()
    atteso = [1] * 7 + [2, 2, 3, 3, 3, 2, 2] + [0] * 7 + [1, 1, 1]
    assert quanti == atteso, (quanti, atteso)


def r_copertura():
    S, C = mondo()
    P = persone(S)
    T = tipi(S)
    g = lunedi() + timedelta(days=35)                            # un lunedi
    s = S()
    s.add_all([CoperturaMinima(ruolo='INFERMIERE', tipo_id=T['M'], minimo=2, giorni='1111100'),
               CoperturaMinima(ruolo='INFERMIERE', tipo_id=T['N'], minimo=1),
               CoperturaMinima(ruolo='OSS', tipo_id=T['M'], minimo=1, area='Degenza')])
    s.commit()
    s.close()
    mettere(S, P['Fittizi'], g, 'M', area='Degenza')
    mettere(S, P['Esempio'], g, 'P')
    mettere(S, P['Modellini'], g, 'M', area='Ambulatori')
    mettere(S, P['Fittizi'], g + timedelta(days=5), 'M')         # sabato: la regola delle mattine non vale
    s = S()
    regole = s.scalars(select(CoperturaMinima)).all()
    del_giorno = [t for t in PE.turni_tra(s, g, g)]
    conti, carenze = PE.copertura(del_giorno, 'INFERMIERE', regole, g)
    assert conti == {'M': 1, 'P': 1} and list(conti) == ['M', 'P'], conti
    assert len(carenze) == 2 and any('mattina: 1 su 2' in x for x in carenze) and any('notte: 0 su 1' in x for x in carenze), carenze
    conti, carenze = PE.copertura(del_giorno, 'OSS', regole, g)
    assert conti == {'M': 1} and carenze == ['OSS mattina in degenza: 0 su 1'], (conti, carenze)
    conti, carenze = PE.copertura(del_giorno, 'OSS', regole, g, 'Ambulatori')
    assert conti == {'M': 1} and carenze == [], (conti, carenze)
    sab = [t for t in PE.turni_tra(s, g + timedelta(days=5), g + timedelta(days=5))]
    conti, carenze = PE.copertura(sab, 'INFERMIERE', regole, g + timedelta(days=5))
    assert carenze == ['Infermieri notte: 0 su 1'], carenze
    s.close()
    assert PE.testo_copertura({'M': 2, 'P': 2, 'N': 1}) == 'M2 P2 N1'


def r_schema():
    S, C = mondo()
    P = persone(S)
    s = S()
    per_codice = {t.codice: t for t in PE.tipi(s)}
    for x, errore in (('', 'Scrivere la sequenza'), ('M Q', 'Codici sconosciuti: Q'), (' '.join(['M'] * 61), 'troppo lunga')):
        try:
            PE.leggi_sequenza(x, per_codice)
            raise AssertionError('sequenza accettata: %r' % x)
        except PE.ErroreTurno as e:
            assert errore in str(e), (x, e)
    seq = PE.leggi_sequenza('m, p n;SN - r', per_codice)
    assert [t.codice if t else None for t in seq] == ['M', 'P', 'N', 'SN', None, 'R']
    gente = [s.get(Persona, P[c]) for c in ('Fittizi', 'Esempio', 'Vecchietti', 'Fintoni')]
    dal = lunedi() + timedelta(days=42)
    al = dal + timedelta(days=13)
    PE.assegna(s, gente[1], dal + timedelta(days=3), per_codice['F'])      # gia' piena: resta
    s.commit()
    messi, saltati, motivi = PE.applica_schema(s, gente, dal, al, seq, sfasamento=2)
    s.commit()
    st = stato(S)
    attesi = 0
    for i, p in enumerate(gente):
        for d in range(14):
            g = dal + timedelta(days=d)
            atteso = seq[(d + i * 2) % len(seq)]
            if not p.attiva:
                assert (p.id, g) not in st, 'schema su una persona non in servizio'
                continue
            if p.id == gente[1].id and d == 3:
                assert st[(p.id, g)][0][0] == per_codice['F'].id, 'cella gia\' piena toccata'
                continue
            if atteso is None:
                assert (p.id, g) not in st, (p.etichetta, g)
            else:
                assert st[(p.id, g)][0][0] == atteso.id, (p.etichetta, g, st.get((p.id, g)))
                attesi += 1
    assert messi == attesi and saltati >= 1, (messi, attesi, saltati, motivi)
    messi2, _, _ = PE.applica_schema(s, gente[:1], dal, al, PE.leggi_sequenza('R', per_codice), sostituisci=True)
    s.commit()
    assert messi2 == 14 and all(stato(S)[(gente[0].id, dal + timedelta(days=d))][0][0] == per_codice['R'].id
                                for d in range(14))
    for a, b in ((al, dal), (dal, dal + timedelta(days=PE.MASSIMO_SCHEMA))):
        try:
            PE.applica_schema(s, gente, a, b, seq)
            raise AssertionError('periodo accettato: %s %s' % (a, b))
        except PE.ErroreTurno:
            pass
    s.close()
    invarianti(S)


def r_copia():
    S, C = mondo()
    P = persone(S)
    lun = lunedi() + timedelta(days=56)
    prima = lun - timedelta(days=7)
    a, b, v = P['Fittizi'], P['Esempio'], P['Vecchietti']
    mettere(S, a, prima, 'M', area='Degenza', note='nota')
    mettere(S, a, prima + timedelta(days=1), None, time(8), time(12))
    mettere(S, a, prima + timedelta(days=1), None, time(15), time(19), aggiungi=True)
    mettere(S, a, prima + timedelta(days=6), 'N')
    mettere(S, b, prima + timedelta(days=2), 'F')
    mettere(S, b, lun + timedelta(days=2), 'R')                  # la cella di arrivo e' piena: resta
    s = S()
    s.get(Persona, v).attiva = True
    s.commit()
    PE.assegna(s, s.get(Persona, v), prima, s.scalars(select(TipoTurno).where(TipoTurno.codice == 'P')).first())
    s.get(Persona, v).attiva = False
    s.commit()
    gente = PE.persone_della_vista(s, None, '', prima, prima + timedelta(days=6))
    copiati, saltati = PE.copia_settimana(s, prima, lun, gente)
    s.commit()
    s.close()
    st = stato(S)
    assert copiati == 4 and saltati == 2, (copiati, saltati)
    assert [x[3:] for x in st[(a, lun)]] == [('Degenza', 'nota')]
    assert len(st[(a, lun + timedelta(days=1))]) == 2, 'il giorno spezzato si copia intero'
    assert st[(a, lun + timedelta(days=6))][0][2].startswith((lun + timedelta(days=7)).isoformat()), 'la notte finisce il lunedi dopo'
    assert st[(b, lun + timedelta(days=2))][0][0] == tipi(S)['R'], 'cella piena sostituita'
    assert (v, lun) not in st, 'copiato a chi non e\' in servizio'
    s = S()
    gente = PE.persone_della_vista(s, None, '', prima, prima + timedelta(days=6))
    copiati, saltati = PE.copia_settimana(s, prima, lun, gente, sostituisci=True)
    s.commit()
    s.close()
    assert stato(S)[(b, lun + timedelta(days=2))][0][0] == tipi(S)['F']
    invarianti(S)


prova('orari scritti, notti a cavallo del giorno, ore del contratto', r_orari)
prova('mettere, sostituire, spezzare il giorno, assenze tutto il giorno', r_assegna)
prova('la notte del giorno prima: sovrapposizioni dopo mezzanotte', r_mezzanotte)
prova('riposi sotto le 11 ore: avviso nel salvataggio e nella cella', r_riposi)
prova('festivi: domeniche, feste fisse e Pasquetta (oracolo indipendente) 2026-2028', r_festivi)
prova('ore, notti, festivi, reperibilita\' e assenze contro i conti fatti a parte', r_totali)
prova('presenti ora per ora: mezz\'ora conta, la notte di ieri, la reperibilita\' no', r_presenti_ora)
prova('coperture minime: giorni della settimana, area, ordine dei codici', r_copertura)
prova('schema a rotazione: sequenza, sfasamento, celle piene, chi non e\' in servizio', r_schema)
prova('copia della settimana: spezzati, notti, celle piene, sostituisci', r_copia)


# ================================================================ richieste
area('modifiche dalla pagina')


def q_metti():
    S, C = mondo()
    P = persone(S)
    T = tipi(S)
    g = lunedi() + timedelta(days=7)
    dal, al = g, g + timedelta(days=6)
    a = P['Fittizi']
    st_code, d = cambia(C, azione='metti', celle=[k(a, g)], tipo=T['M'], dal=dal.isoformat(), al=al.isoformat())
    assert st_code == 200 and d['ok'] and d['fatti'] == 1, (st_code, d)
    assert d['prima'] == {k(a, g): []}, d['prima']
    c = d['celle'][k(a, g)]
    assert [v['codice'] for v in c['turni']] == ['M'] and c['turni'][0]['desc'] == 'Mattina 7–14', c
    assert k(a, g + timedelta(days=1)) in d['celle'], 'mancano le celle vicine (i riposi dipendono da loro)'
    assert d['totali'][str(a)]['ore'] == '7' and d['totali'][str(a)]['previste'] == '36', d['totali']
    assert d['copertura']['INFERMIERE_%s' % g.isoformat()]['testo'] == 'M1', d['copertura']
    # per codice, con orario diverso e area: il pallino «diverso»
    st_code, d = cambia(C, azione='metti', celle=[k(a, g)], tipo='p', inizio='13:30', fine='21', area='Degenza',
                        note='cambio', dal=dal.isoformat(), al=al.isoformat())
    v = d['celle'][k(a, g)]['turni'][0]
    assert (v['codice'], v['orario'], v['diverso'], v['area'], v['note']) == ('P', '13:30–21', True, 'Degenza', 'cambio'), v
    assert d['prima'][k(a, g)] == [{'tipo': T['M'], 'inizio': '07:00', 'fine': '14:00', 'area': '', 'note': ''}], d['prima']
    # aggiungi (spezzato) e togli un turno solo
    st_code, d = cambia(C, azione='aggiungi', celle=[k(a, g)], inizio='8', fine='12', dal=dal.isoformat(), al=al.isoformat())
    voci = d['celle'][k(a, g)]['turni']
    assert [x['orario'] for x in voci] == ['8–12', '13:30–21'] and voci[0]['codice'] == '', voci
    st_code, d = cambia(C, azione='togli', celle=[k(a, g)], turno=voci[0]['id'], dal=dal.isoformat(), al=al.isoformat())
    assert [x['codice'] for x in d['celle'][k(a, g)]['turni']] == ['P'] and d['fatti'] == 1
    st_code, d = cambia(C, azione='togli', celle=[k(a, g), k(a, g + timedelta(days=1))])
    assert d['fatti'] == 1 and list(d['prima']) == [k(a, g)], 'una cella gia\' vuota non conta come tolta'
    assert d['celle'][k(a, g)]['turni'] == []


def q_tieni_area():
    S, C = mondo()
    P = persone(S)
    T = tipi(S)
    g = lunedi() + timedelta(days=7)
    a, b = P['Fittizi'], P['Esempio']
    mettere(S, a, g, 'M', area='Degenza')
    mettere(S, b, g, 'M', area='Sala operatoria')
    st_code, d = cambia(C, azione='metti', celle=[k(a, g), k(b, g)], tipo=T['P'], tieni_area=True)
    assert [d['celle'][x]['turni'][0]['area'] for x in (k(a, g), k(b, g))] == ['Degenza', 'Sala operatoria'], d['celle']
    st_code, d = cambia(C, azione='metti', celle=[k(a, g)], tipo=T['P'], area='Ambulatori', tieni_area=True)
    assert d['celle'][k(a, g)]['turni'][0]['area'] == 'Ambulatori', 'l\'area scritta vince'
    st_code, d = cambia(C, azione='metti', celle=[k(b, g)], tipo=T['R'], tieni_area=True)
    assert d['celle'][k(b, g)]['turni'][0]['area'] == '', 'un riposo non ha area'
    st_code, d = cambia(C, azione='metti', celle=[k(a, g)], tipo=T['N'])
    assert d['celle'][k(a, g)]['turni'][0]['area'] == '', 'senza tieni_area l\'area non resta'


def q_annulla():
    """Annulla e rifai: lo stato torna identico, anche con notti, orari diversi, aree, note e giorni spezzati."""
    S, C = mondo()
    P = persone(S)
    T = tipi(S)
    g = lunedi() + timedelta(days=7)
    a, b, c = P['Fittizi'], P['Esempio'], P['Fintoni']
    mettere(S, a, g, 'N', area='Degenza', note='notte')
    mettere(S, b, g, None, time(8), time(12), note='mattina corta')
    mettere(S, b, g, None, time(15), time(18, 30), aggiungi=True)
    mettere(S, c, g + timedelta(days=1), 'F')
    mettere(S, a, g + timedelta(days=1), 'M', time(7, 30), time(13))
    prima = stato(S)
    celle = [k(a, g), k(b, g), k(c, g), k(c, g + timedelta(days=1)), k(a, g + timedelta(days=1))]
    st_code, d = cambia(C, azione='metti', celle=celle, tipo=T['R'])
    assert d['ok'] and d['fatti'] == 5, d
    dopo = stato(S)
    assert dopo != prima
    st_code, d2 = cambia(C, azione='ripristina', stato=d['prima'])
    assert st_code == 200 and d2['ok'] and d2['fatti'] == 5, d2
    assert stato(S) == prima, 'annulla: lo stato non e\' tornato quello di prima'
    st_code, d3 = cambia(C, azione='ripristina', stato=d2['prima'])
    assert stato(S) == dopo, 'rifai: lo stato non e\' quello dopo la modifica'
    st_code, d4 = cambia(C, azione='ripristina', stato=d3['prima'])
    assert stato(S) == prima
    # tutto o niente: un turno di prima che adesso non sta (una notte e, fuori dall'annulla, un turno la mattina dopo)
    st_code, d = cambia(C, azione='togli', celle=[k(a, g)])
    mettere(S, a, g + timedelta(days=1), None, time(6), time(13))
    adesso = stato(S)
    st_code, d5 = cambia(C, azione='ripristina', stato=d['prima'])
    assert not d5['ok'] and d5['fatti'] == 0 and 'Non si può annullare' in d5['errori'][0], d5
    assert stato(S) == adesso, 'un annulla non riuscito ha cambiato qualcosa'
    invarianti(S)


def q_errori():
    S, C = mondo()
    P = persone(S)
    T = tipi(S)
    g = lunedi() + timedelta(days=7)
    a = P['Fittizi']
    casi = [
        ({'azione': 'cancella', 'celle': [k(a, g)], 'tipo': T['M']}, 'Richiesta non valida'),
        ({'azione': 'metti', 'celle': [], 'tipo': T['M']}, 'Richiesta non valida'),
        ({'azione': 'metti', 'celle': {'x': 1}, 'tipo': T['M']}, 'Richiesta non valida'),
        ({'azione': 'metti', 'celle': ['%d_2026-02-30' % a], 'tipo': T['M']}, 'Cella non valida'),
        ({'azione': 'metti', 'celle': ['abc'], 'tipo': T['M']}, 'Cella non valida'),
        ({'azione': 'metti', 'celle': ['%d_1800-01-01' % a], 'tipo': T['M']}, 'Cella non valida'),
        ({'azione': 'metti', 'celle': [k(a, g)] * (PE.MASSIMO_CELLE + 1), 'tipo': T['M']}, 'Troppe celle'),
        ({'azione': 'metti', 'celle': [k(a, g)], 'tipo': 99999}, 'Tipo di turno sconosciuto'),
        ({'azione': 'metti', 'celle': [k(a, g)], 'tipo': 'ZZ'}, 'Tipo di turno sconosciuto'),
        ({'azione': 'metti', 'celle': [k(a, g)], 'inizio': '25:00', 'fine': '12'}, 'Orario non valido'),
        ({'azione': 'metti', 'celle': [k(a, g)], 'inizio': '8'}, 'Scegliere un turno'),
        ({'azione': 'metti', 'celle': [k(a, g)]}, 'Scegliere un turno'),
        ({'azione': 'ripristina', 'stato': [1, 2]}, 'Richiesta non valida'),
        ({'azione': 'ripristina', 'stato': {k(a, g): 'x'}}, 'Richiesta non valida'),
        ({'azione': 'ripristina', 'stato': {k(a, g): [{'tipo': 99999}]}}, 'non c\'è più'),
        ({'azione': 'ripristina', 'stato': {k(a, g): [{'tipo': T['M'], 'inizio': 'xx'}]}}, 'Richiesta non valida'),
    ]
    for dati, atteso in casi:
        st_code, d = cambia(C, **dati)
        assert st_code == 400 and d and not d['ok'] and atteso in d['errore'], (dati.get('azione'), st_code, d)
    assert not stato(S), 'una richiesta sbagliata ha lasciato turni'
    r = C.post(CAMBIA, data='non json', content_type='application/json')
    assert r.status_code == 400
    # errori per cella: chi non c'e', chi non e' in servizio; le altre celle si salvano
    st_code, d = cambia(C, azione='metti', celle=[k(a, g), k(99999, g), k(P['Vecchietti'], g)], tipo=T['M'])
    assert st_code == 200 and not d['ok'] and d['fatti'] == 1 and len(d['errori']) == 2, d
    assert any('Persona non trovata' in x for x in d['errori']) and any('non più in servizio' in x for x in d['errori'])
    # un tipo non piu' in uso non si mette
    s = S()
    s.get(TipoTurno, T['G']).attivo = False
    s.commit()
    s.close()
    st_code, d = cambia(C, azione='metti', celle=[k(a, g + timedelta(days=1))], tipo=T['G'])
    assert not d['ok'] and 'non è più in uso' in d['errori'][0], d
    # celle ripetute: una volta sola
    st_code, d = cambia(C, azione='metti', celle=[k(a, g + timedelta(days=2))] * 3, tipo=T['M'])
    assert d['fatti'] == 1 and len(stato(S)[(a, g + timedelta(days=2))]) == 1, d


def q_protezioni():
    S, C = mondo()
    P = persone(S)
    T = tipi(S)
    g = lunedi() + timedelta(days=7)
    r = C.post(CAMBIA, json={'azione': 'metti', 'celle': [k(P['Fittizi'], g)], 'tipo': T['M']},
               headers={'Origin': 'http://pagina-cattiva.example'})
    assert r.status_code == 403 and not stato(S), 'modifica da un\'altra pagina accettata'
    r = C.post(CAMBIA, json={'azione': 'metti', 'celle': [k(P['Fittizi'], g)], 'tipo': T['M']},
               headers={'Sec-Fetch-Site': 'cross-site'})
    assert r.status_code == 403
    for url in ('/personale/turni/copia-settimana', '/personale/turni/schema', '/personale/persone/nuova',
                '/personale/tipi', '/personale/persone/medici-dall-agenda'):
        r = C.post(url, data={}, headers={'Origin': 'http://pagina-cattiva.example'})
        assert r.status_code == 403, url
    # un nome con <script>: nelle pagine e' testo, nel JSON e' codificato
    s = S()
    p = s.get(Persona, P['Esempio'])
    p.cognome = '<script>alert(1)</script>'
    p.qualifica = '"><img src=x>'
    s.commit()
    s.close()
    mettere(S, P['Esempio'], g, 'M', note='<b>grassetto</b>')
    for url in ('/personale/turni/settimana/%s' % g.isoformat(), '/personale/turni/mese/%s' % g.strftime('%Y-%m'),
                '/personale/turni/giorno/%s' % g.isoformat(), '/personale/persone', '/personale/persone/%d' % P['Esempio'],
                '/oggi'):
        corpo = html(C.get(url))
        assert '<script>alert(1)' not in corpo and '<img src=x>' not in corpo and '<b>grassetto</b>' not in corpo, url
    r = C.post(CAMBIA, json={'azione': 'metti', 'celle': [k(P['Esempio'], g)], 'tipo': T['P'], 'note': '<i>x</i>'})
    corpo = r.get_data(as_text=True)
    assert '<' not in corpo and r.headers['Content-Type'].startswith('application/json'), corpo[:200]
    assert r.headers.get('Cache-Control') == 'no-store'


def q_caso():
    """Modifiche a caso dalla pagina (metti, aggiungi, togli, annulla, rifai): dopo ogni passo gli invarianti,
    le celle della risposta uguali al database, e annulla subito dopo riporta lo stato di prima."""
    S, C = mondo()
    P = persone(S)
    T = tipi(S)
    rnd = random.Random(1808)
    pids = [P['Fittizi'], P['Esempio'], P['Fintoni']]
    dal = lunedi() + timedelta(days=70)
    giorni = [dal + timedelta(days=i) for i in range(6)]
    codici = list(T)
    passi = annullati = 0
    for passo in range(260):
        celle = list({k(rnd.choice(pids), rnd.choice(giorni)) for _ in range(rnd.choice([1, 1, 1, 2, 3, 5]))})
        azione = rnd.choice(['metti'] * 5 + ['aggiungi'] * 2 + ['togli'])
        dati = {'azione': azione, 'celle': celle, 'dal': giorni[0].isoformat(), 'al': giorni[-1].isoformat()}
        if azione != 'togli':
            if rnd.random() < .7:
                dati['tipo'] = T[rnd.choice(codici)]
            if rnd.random() < .4 or 'tipo' not in dati:
                h = rnd.randrange(24)
                dati['inizio'] = '%02d:%s' % (h, rnd.choice(['00', '30']))
                dati['fine'] = '%02d:%s' % ((h + rnd.choice([2, 4, 6, 8, 10, 13])) % 24, rnd.choice(['00', '30']))
        prima = stato(S)
        st_code, d = cambia(C, **dati)
        assert st_code in (200, 400), st_code
        passi += 1
        invarianti(S)
        if st_code == 400:
            assert stato(S) == prima, 'richiesta rifiutata ma turni cambiati'
            continue
        # la risposta descrive il database
        s = S()
        for chiave, cel in d['celle'].items():
            pid, iso = chiave.split('_')
            g = date.fromisoformat(iso)
            veri = sorted(s.scalars(select(TurnoPersonale).where(TurnoPersonale.persona_id == int(pid),
                                                                  TurnoPersonale.giorno == g)).all(),
                          key=lambda t: (t.inizio or datetime.combine(g, time(0)), t.id))
            assert [v['id'] for v in cel['turni']] == [t.id for t in veri], (chiave, cel, veri)
        s.close()
        if not d['fatti']:
            assert stato(S) == prima
            continue
        if rnd.random() < .35:
            dopo = stato(S)
            st_code, d2 = cambia(C, azione='ripristina', stato=d['prima'], dal=dati['dal'], al=dati['al'])
            assert d2['ok'] and stato(S) == prima, ('annulla', passo, d2.get('errori'))
            st_code, d3 = cambia(C, azione='ripristina', stato=d2['prima'])
            assert d3['ok'] and stato(S) == dopo, ('rifai', passo, d3.get('errori'))
            annullati += 1
    assert passi == 260 and annullati > 30, (passi, annullati)
    return '%d passi, %d annulla e rifai' % (passi, annullati)


prova('metti, per codice, orario diverso, aggiungi, togli: risposta e conti', q_metti)
prova('cambiando turno si tiene l\'area (dalla tastiera e su piu\' celle)', q_tieni_area)
prova('annulla e rifai: stato identico; annulla impossibile non tocca niente', q_annulla)
prova('richieste sbagliate: 400 con il motivo, nessun turno lasciato', q_errori)
prova('protezioni: altre pagine rifiutate, nomi e note sempre come testo', q_protezioni)
prova('giro a caso di 260 modifiche con invarianti, annulla e rifai', q_caso)


# ================================================================ pagine
area('pagine, persone, tipi, Excel')


def p_pagine():
    S, C = mondo(con_persone=False)
    for url in ('/personale/turni/mese/', '/personale/turni/settimana/', '/personale/turni/giorno/'):
        t = testo(C.get(url))
        assert 'Per cominciare, il personale' in t, url
    S, C = mondo()
    P = persone(S)
    g = lunedi() + timedelta(days=7)
    mettere(S, P['Fittizi'], g, 'M', area='Degenza')
    mettere(S, P['Modellini'], g, 'N', area='Degenza')
    r = C.get('/personale/turni')
    assert r.status_code == 302 and '/personale/turni/mese/' in r.headers['Location']
    for url, attesi in (
            ('/personale/turni/mese/%s' % g.strftime('%Y-%m'), ['id="griglia-turni"', 'data-vista="mese"', 'Fittizi',
                                                               'Copertura', 'id="scelta-turno"', 'id="finestra-schema"']),
            ('/personale/turni/settimana/%s' % g.isoformat(), ['data-vista="settimana"', 'data-copia-settimana', '7–14']),
            ('/personale/turni/giorno/%s' % g.isoformat(), ['id="vista-giorno"', 'class="pista"', 'id="aggiungi-persona"']),
            ('/personale/persone', ['Aggiungi una persona', 'Fittizi']),
            ('/personale/tipi', ['Mattina', 'Coperture minime']),
            ('/personale/persone/nuova?ruolo=OSS', ['value="OSS" checked'])):
        corpo = html(C.get(url))
        for x in attesi:
            assert x in corpo, (url, x)
    # filtri: per ruolo (gli altri non ci sono), per area (riposi e assenze restano), valori sbagliati ignorati
    corpo = html(C.get('/personale/turni/settimana/%s?ruolo=OSS' % g.isoformat()))
    assert 'Modellini' in corpo and 'Fittizi' not in corpo
    corpo = html(C.get('/personale/turni/settimana/%s?ruolo=XYZ&area=%%3Cb%%3Exss' % g.isoformat()))
    assert 'Modellini' in corpo and 'Fittizi' in corpo and '<b>xss' not in corpo and '&lt;b&gt;xss' in corpo
    corpo = html(C.get('/personale/turni/settimana/%s?area=Ambulatori' % g.isoformat()))
    assert 'data-k="%d_%s"' % (P['Fittizi'], g.isoformat()) in corpo and '7–14' not in corpo, \
        'con un\'altra area il turno non si vede'
    for url in ('/personale/turni/mese/2026-13', '/personale/turni/mese/xx', '/personale/turni/settimana/2026-02-31',
                '/personale/turni/giorno/abc', '/personale/turni/mese/3000-01'):
        assert C.get(url).status_code == 200, url
    assert C.get('/personale/persone/99999').status_code == 404


def p_persone():
    S, C = mondo(con_persone=False)
    r = C.post('/personale/persone/nuova', data={'cognome': '  Fittizi  ', 'nome': 'Ada', 'ruolo': 'INFERMIERE',
                                                 'ore_settimana': '37,5', 'attiva': '1', 'telefono': '333 0000000'})
    assert r.status_code == 302 and 'salvata' in avvisi(C)
    s = S()
    p = s.scalars(select(Persona)).first()
    assert (p.cognome, p.minuti_settimana, p.attiva, p.ore_settimana) == ('Fittizi', 2250, True, '37:30')
    pid = p.id
    s.close()
    for dati, atteso in (({'cognome': '', 'ruolo': 'OSS'}, 'Il cognome serve'),
                         ({'cognome': 'X', 'ruolo': 'PILOTA'}, 'Scegliere il ruolo'),
                         ({'cognome': 'X', 'ruolo': 'OSS', 'ore_settimana': '99'}, 'Ore settimanali'),
                         ({'cognome': 'X', 'ruolo': 'OSS', 'email': 'non-una-email'}, 'Email non valida')):
        r = C.post('/personale/persone/nuova', data=dati)
        assert r.status_code == 200 and atteso in testo(r), (dati, atteso)
    # senza la spunta «In servizio»: non attiva (niente campo nascosto che la rimetta)
    r = C.post('/personale/persone/%d' % pid, data={'cognome': 'Fittizi', 'nome': 'Ada', 'ruolo': 'INFERMIERE'})
    s = S()
    assert s.get(Persona, pid).attiva is False
    s.close()
    # medici dall'agenda: una volta sola; collegamento unico
    s = S()
    s.add_all([Operatore(cognome='Esempietti', nome='Rita'), Operatore(cognome='Spento', attivo=False)])
    s.commit()
    attivi = len(s.scalars(select(Operatore).where(Operatore.attivo == True)).all())
    s.close()
    C.post('/personale/persone/medici-dall-agenda')
    msg = avvisi(C)
    assert attivi >= 2 and 'Aggiunti %d medici' % attivi in msg, (attivi, msg)
    C.post('/personale/persone/medici-dall-agenda')
    assert 'già nel personale' in avvisi(C)
    s = S()
    medici = s.scalars(select(Persona).where(Persona.ruolo == 'MEDICO')).all()
    op = medici[0].operatore_id
    s.close()
    r = C.post('/personale/persone/nuova', data={'cognome': 'Doppio', 'ruolo': 'MEDICO', 'operatore_id': str(op)})
    assert 'già collegato' in testo(r)
    # eliminare: solo senza turni
    mettere(S, medici[0].id, lunedi() + timedelta(days=7), 'G')
    C.post('/personale/persone/%d' % medici[0].id, data={'azione': 'elimina'})
    assert 'non si può eliminare' in avvisi(C)
    C.post('/personale/persone/%d' % medici[1].id, data={'azione': 'elimina'})
    assert 'Persona eliminata' in avvisi(C)


def p_tipi():
    S, C = mondo()
    T = tipi(S)
    for dati, atteso in (({'azione': 'nuovo_tipo', 'codice': '1X', 'nome': 'Prova', 'categoria': 'LAVORO'}, 'Codice'),
                         ({'azione': 'nuovo_tipo', 'codice': 'M', 'nome': 'Doppio', 'categoria': 'RIPOSO'}, 'è già di'),
                         ({'azione': 'nuovo_tipo', 'codice': 'L', 'nome': 'Lungo', 'categoria': 'LAVORO'}, 'servono inizio e fine'),
                         ({'azione': 'nuovo_tipo', 'codice': 'L', 'nome': '', 'categoria': 'RIPOSO'}, 'Il nome serve'),
                         ({'azione': 'nuovo_tipo', 'codice': 'L', 'nome': 'X', 'categoria': 'LAVORO', 'ora_inizio': '8',
                           'ora_fine': '8'}, 'uguali')):
        C.post('/personale/tipi', data=dati)
        assert atteso in avvisi(C), (dati, atteso)
    C.post('/personale/tipi', data={'azione': 'nuovo_tipo', 'codice': ' lu ', 'nome': 'Lungo', 'categoria': 'LAVORO',
                                    'ora_inizio': '8', 'ora_fine': '20', 'pausa_min': '60', 'colore': '#123456',
                                    'attivo': '1'})
    assert 'LU salvato' in avvisi(C)
    s = S()
    t = s.scalars(select(TipoTurno).where(TipoTurno.codice == 'LU')).first()
    assert (t.minuti, t.colore, t.attivo, t.colore_testo) == (660, '#123456', True, '#FFFFFF'), (t.minuti, t.colore)
    s.close()
    # un colore storto non finisce nella pagina
    C.post('/personale/tipi', data={'azione': 'salva_tipo', 'id': str(T['M']), 'codice': 'M', 'nome': 'Mattina',
                                    'categoria': 'LAVORO', 'ora_inizio': '7', 'ora_fine': '14',
                                    'colore': 'red;background:url(x)', 'attivo': '1'})
    s = S()
    assert s.get(TipoTurno, T['M']).colore == '#E8E8EC'
    s.close()
    # eliminare un tipo usato: resta, non in uso
    P = persone(S)
    mettere(S, P['Fittizi'], lunedi() + timedelta(days=7), 'G')
    C.post('/personale/tipi', data={'azione': 'elimina_tipo', 'id': str(T['G'])})
    assert 'non si elimina' in avvisi(C)
    s = S()
    assert s.get(TipoTurno, T['G']).attivo is False
    s.close()
    C.post('/personale/tipi', data={'azione': 'elimina_tipo', 'id': str(T['PE'])})
    assert 'eliminato' in avvisi(C)
    # coperture
    C.post('/personale/tipi', data={'azione': 'nuova_copertura', 'ruolo': 'INFERMIERE', 'tipo_id': str(T['M']),
                                    'minimo': '2', 'g0': '1', 'g1': '1', 'area': ' Degenza '})
    assert 'Copertura minima aggiunta' in avvisi(C)
    C.post('/personale/tipi', data={'azione': 'nuova_copertura', 'ruolo': 'INFERMIERE', 'tipo_id': str(T['R']),
                                    'minimo': '0'})
    msg = avvisi(C)
    assert 'turno con orario' in msg and 'da 1 a 50' in msg and 'almeno un giorno' in msg, msg
    s = S()
    r = s.scalars(select(CoperturaMinima)).one()
    assert (r.giorni, r.area, r.minimo) == ('1100000', 'Degenza', 2), (r.giorni, r.area)
    rid = r.id
    s.close()
    C.post('/personale/tipi', data={'azione': 'elimina_copertura', 'id': str(rid)})
    assert 'tolta' in avvisi(C)


def p_schema_copia():
    S, C = mondo()
    P = persone(S)
    g = lunedi() + timedelta(days=7)
    torna = '/personale/turni/settimana/%s?ruolo=INFERMIERE' % g.isoformat()
    r = C.post('/personale/turni/schema', data={'dal': g.isoformat(), 'al': (g + timedelta(days=6)).isoformat(),
                                                'persone': [str(P['Esempio']), str(P['Fittizi'])], 'sequenza': 'M P',
                                                'sfasamento': '1', 'torna': torna})
    assert r.status_code == 302 and r.headers['Location'].endswith(torna), r.headers.get('Location')
    assert 'Schema applicato: 14 turni messi' in avvisi(C)
    st = stato(S)
    T = tipi(S)
    assert st[(P['Esempio'], g)][0][0] == T['M'] and st[(P['Fittizi'], g)][0][0] == T['P'], \
        'l\'ordine delle persone e\' quello scelto'
    r = C.post('/personale/turni/schema', data={'dal': g.isoformat(), 'al': g.isoformat(), 'sequenza': 'M',
                                                'torna': 'https://altro.example/'})
    assert r.headers['Location'].endswith('/personale/turni'), 'torna verso un altro sito'
    assert 'almeno una persona' in avvisi(C)
    C.post('/personale/turni/schema', data={'dal': g.isoformat(), 'al': g.isoformat(), 'sequenza': 'M Q',
                                            'persone': [str(P['Esempio'])]})
    assert 'Codici sconosciuti: Q' in avvisi(C)
    r = C.post('/personale/turni/copia-settimana', data={'lunedi': (g + timedelta(days=9)).isoformat()})
    assert r.status_code == 302 and 'Copiati 14 turni' in avvisi(C), 'il lunedi si ricava dal giorno'
    C.post('/personale/turni/copia-settimana', data={'lunedi': (g + timedelta(days=28)).isoformat()})
    assert 'Niente da copiare' in avvisi(C)


def p_excel():
    from openpyxl import load_workbook
    S, C = mondo()
    P = persone(S)
    g = date(2026, 12, 7)
    mettere(S, P['Fittizi'], g, 'M', area='Degenza')
    mettere(S, P['Fittizi'], g + timedelta(days=1), 'N', area='Degenza')
    mettere(S, P['Modellini'], g, 'F')
    mettere(S, P['Modellini'], g + timedelta(days=2), None, time(8), time(12), area='Ambulatori')
    r = C.get('/personale/turni/mese/2026-12.xlsx')
    assert r.status_code == 200 and 'turni-2026-12.xlsx' in r.headers.get('Content-Disposition', '')
    wb = load_workbook(BytesIO(r.data))
    assert wb.sheetnames == ['Turni 12-2026', 'Elenco'], wb.sheetnames
    ws = wb['Turni 12-2026']
    assert 'dicembre 2026' in ws['A1'].value
    righe = {ws.cell(row=i, column=1).value: i for i in range(1, ws.max_row + 1)}
    i = righe['Fittizi Ada']
    assert ws.cell(row=i, column=2 + 7).value == 'M' and ws.cell(row=i, column=2 + 8).value == 'N'
    assert str(ws.cell(row=i, column=2 + 31 + 1).value).startswith('17'), ws.cell(row=i, column=34).value
    assert ws.cell(row=i, column=2 + 31 + 2).value == 1, 'una notte'
    j = righe['Modellini Carla']
    assert ws.cell(row=j, column=2 + 9).value == '8–12' and ws.cell(row=j, column=2 + 31 + 4).value == 1
    el = wb['Elenco']
    # 1.12: titolo, «esportato il», riga vuota, intestazione, le righe, la riga dei totali
    testa = next(i for i in range(1, 8) if el.cell(i, 1).value == 'Data')
    assert el.max_row == testa + 4 + 1 and el.cell(el.max_row, 1).value == 'Totale', (testa, el.max_row)
    r = C.get('/personale/turni/mese/2026-12.xlsx?area=Degenza')
    el = load_workbook(BytesIO(r.data))['Elenco']
    testa = next(i for i in range(1, 8) if el.cell(i, 1).value == 'Data')
    valori = [el.cell(row=x, column=10).value for x in range(testa + 1, el.max_row + 1)]
    assert 'Ambulatori' not in valori and el.max_row == testa + 3 + 1, valori


def p_oggi():
    S, C = mondo(con_persone=False)
    assert 'In servizio oggi' not in testo(C.get('/oggi')), 'scheda mostrata senza personale'
    S, C = mondo()
    P = persone(S)
    assert 'Nessun turno di lavoro del personale oggi' in testo(C.get('/oggi'))
    mettere(S, P['Fittizi'], OGGI - timedelta(days=1), 'N', area='Degenza')
    mettere(S, P['Esempio'], OGGI, 'M')
    mettere(S, P['Fintoni'], OGGI, 'R')
    t = testo(C.get('/oggi'))
    assert 'In servizio oggi' in t and 'Fittizi Ada 21:00–07:00 da ieri · Degenza' in t and 'Esempio Bruno 07:00–14:00' in t, t
    assert 'Fintoni' not in t, 'chi riposa non e\' in servizio'
    s = S()
    voci = PE.in_servizio(s, datetime.combine(OGGI, time(6)))
    s.close()
    stati = {v['turno'].persona.cognome: (v['adesso'], v['finito']) for gr in voci for v in gr['voci']}
    assert stati == {'Fittizi': (True, False), 'Esempio': (False, False)}, stati


def p_contrasti_icone():
    """I colori dei tipi iniziali si leggono (contrasto almeno 4,5:1) e ogni icona usata esiste."""
    def lum(h):
        def ch(c):
            c = c / 255
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
        return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)
    for codice, nome, cat, a, b, pausa, colore in TIPI_TURNO_INIZIALI:
        t = testo_su(colore)
        l1, l2 = sorted((lum(colore), lum(t)), reverse=True)
        assert (l1 + 0.05) / (l2 + 0.05) >= 4.5, (codice, colore, t)
    icone = open(os.path.join(CARTELLA, 'templates', '_icone.html'), encoding='utf-8').read()
    disponibili = set(re.findall(r"'([a-z0-9-]+)': '", icone)) or set(re.findall(r'"([a-z0-9-]+)"\s*:', icone))
    usate = set()
    for nome in os.listdir(os.path.join(CARTELLA, 'templates')):
        if nome.endswith('.html'):
            corpo = open(os.path.join(CARTELLA, 'templates', nome), encoding='utf-8').read()
            usate |= set(re.findall(r"icona\('([a-z0-9-]+)'", corpo))
    import modelli
    usate |= {r[3] for r in modelli.RUOLI}
    assert disponibili, 'elenco delle icone non trovato in _icone.html'
    mancanti = usate - disponibili
    assert not mancanti, mancanti
    lic = open(os.path.join(CARTELLA, 'static', 'icone', 'LICENZE.txt'), encoding='utf-8').read()
    assert 'Lucide' in lic and 'ISC' in lic and 'Radix' in lic and 'MIT' in lic


prova('pagine: primi passi, mese, settimana, giorno, filtri, indirizzi storti', p_pagine)
prova('persone: modulo, ore 37,5, «In servizio», medici dall\'agenda, eliminare', p_persone)
prova('tipi di turno e coperture: controlli, colore sicuro, eliminare un tipo usato', p_tipi)
prova('schema a rotazione e copia della settimana dalla pagina', p_schema_copia)
prova('Excel del mese: foglio, totali, elenco, filtro per area', p_excel)
prova('Oggi: «In servizio oggi», la notte da ieri, chi e\' al lavoro adesso', p_oggi)
prova('colori leggibili (WCAG 4,5:1) e icone tutte presenti con le licenze', p_contrasti_icone)


# ================================================================ database
area('database')


def d_nuovo():
    S = crea_sessione('sqlite:///' + percorso_nuovo())
    s = S()
    lista = s.scalars(select(TipoTurno).order_by(TipoTurno.ordine)).all()
    assert [t.codice for t in lista] == [x[0] for x in TIPI_TURNO_INIZIALI]
    m = {t.codice: t for t in lista}
    assert (m['N'].ora_inizio, m['N'].ora_fine, m['N'].minuti, m['G'].minuti, m['R'].con_orario) == \
        (time(21), time(7), 600, 480, False)
    assert leggi_impostazione(s, 'tipi_turno_iniziali') == '1'
    s.close()


def d_migrazione():
    percorso = percorso_nuovo('v8')
    S0 = crea_sessione('sqlite:///' + percorso)
    s = S0()
    servizi.prepara_primo_avvio(s)
    s.commit()
    s.close()
    S0.motore.dispose()
    c = sqlite3.connect(percorso)
    for tab in ('turni_personale', 'coperture_minime', 'personale', 'tipi_turno'):
        c.execute('DROP TABLE %s' % tab)
    c.execute("DELETE FROM impostazioni WHERE chiave = 'tipi_turno_iniziali'")
    c.execute("UPDATE impostazioni SET valore = '8' WHERE chiave = 'versione_schema'")
    c.commit()
    c.close()
    S = crea_sessione('sqlite:///' + percorso)
    note = ' | '.join(S.migrazioni)
    assert S.versione_precedente == 8, S.versione_precedente
    assert 'prima-della-versione-%d' % VERSIONE_SCHEMA in note and '10 tipi di turno iniziali' in note, note
    assert os.listdir(os.path.join(os.path.dirname(percorso), 'backup')), 'copia di sicurezza mancante'
    s = S()
    assert len(s.scalars(select(TipoTurno)).all()) == 10
    for t in s.scalars(select(TipoTurno)):          # gli orari scritti dalla migrazione si leggono come orari
        assert t.con_orario == (t.categoria in ('LAVORO', 'REPERIBILITA')), t.codice
    # tolti tutti i tipi, alla riapertura non tornano
    for t in s.scalars(select(TipoTurno)):
        s.delete(t)
    s.commit()
    s.close()
    S2 = crea_sessione('sqlite:///' + percorso)
    s = S2()
    assert S2.versione_precedente == VERSIONE_SCHEMA and not S2.migrazioni
    assert not s.scalars(select(TipoTurno)).all(), 'tipi ricreati dopo che erano stati tolti'
    s.close()


def d_struttura():
    """Una persona di un'altra struttura non compare; una di «tutte» si'."""
    S, C = mondo()
    s = S()
    s.add(Struttura(nome='Seconda sede'))
    s.commit()
    seconda = s.scalars(select(Struttura).where(Struttura.nome == 'Seconda sede')).first().id
    s.add(Persona(cognome='Altrove', nome='Lia', ruolo='OSS', struttura_id=seconda))
    s.commit()
    s.close()
    g = lunedi() + timedelta(days=7)
    corpo = html(C.get('/personale/turni/settimana/%s?struttura=1' % g.isoformat()))
    assert 'Altrove' not in corpo and 'Fittizi' in corpo
    corpo = html(C.get('/personale/turni/settimana/%s?struttura=%d' % (g.isoformat(), seconda)))
    assert 'Altrove' in corpo and 'Fittizi' in corpo and 'data-struttura="%d"' % seconda in corpo
    # la copertura ridisegnata dopo una modifica conta solo chi si vede nella struttura scelta
    P = persone(S)
    T = tipi(S)
    mettere(S, P['Altrove'], g, 'M')
    r = C.post(CAMBIA + '?struttura=1', json={'azione': 'metti', 'celle': [k(P['Modellini'], g)], 'tipo': T['M'],
                                               'dal': g.isoformat(), 'al': (g + timedelta(days=6)).isoformat()})
    d = json.loads(r.get_data(as_text=True))
    assert d['copertura']['OSS_%s' % g.isoformat()]['testo'] == 'M1', d['copertura']
    r = C.post(CAMBIA + '?struttura=%d' % seconda, json={'azione': 'metti', 'celle': [k(P['Prototti'], g)],
                                                         'tipo': T['P'], 'dal': g.isoformat(),
                                                         'al': (g + timedelta(days=6)).isoformat()})
    d = json.loads(r.get_data(as_text=True))
    assert d['copertura']['OSS_%s' % g.isoformat()]['testo'] == 'M2 P1', d['copertura']


prova('database nuovo: i dieci tipi di turno di partenza', d_nuovo)
prova('aggiornamento dalla versione 8: copia di sicurezza, tabelle e tipi, una volta sola', d_migrazione)
prova('piu\' strutture: chi e\' di un\'altra sede non compare', d_struttura)


# ================================================================ WhatsApp
area('WhatsApp: registrare il numero')
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import invii
from modelli import scrivi_impostazione, Impostazione, Invio

TOKEN = 'EAAprovaTOKENfinto123'


class GestoreMeta(BaseHTTPRequestHandler):
    def do_POST(self):
        srv = self.server
        corpo = self.rfile.read(int(self.headers.get('Content-Length') or 0))
        srv.richieste.append({'percorso': self.path, 'auth': self.headers.get('Authorization'),
                              'corpo': json.loads(corpo or b'{}')})
        stato, risposta = srv.risposta
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
        self.prepara()
        threading.Thread(target=self.serve_forever, daemon=True).start()

    def prepara(self, stato=200, risposta=None):
        self.richieste = []
        self.risposta = (stato, {'success': True} if risposta is None else risposta)


META = ServerMeta()


def con_whatsapp(S, **altro):
    s = S()
    for chiave, valore in dict({'wa_token': invii.proteggi(TOKEN), 'wa_numero_id': '123456789',
                                'wa_indirizzo': 'http://127.0.0.1:%d' % META.server_address[1]}, **altro).items():
        scrivi_impostazione(s, chiave, valore)
    s.commit()
    s.close()


def w_registra():
    S, C = mondo(con_persone=False)
    META.prepara()
    C.post('/invii', data={'azione': 'registra_whatsapp', 'pin': '123456'})
    assert 'Prima salvare il token' in avvisi(C) and not META.richieste
    con_whatsapp(S)
    for pin in ('12345', 'abcdef', '1234567', ''):
        C.post('/invii', data={'azione': 'registra_whatsapp', 'pin': pin})
        assert 'Il PIN sono 6 cifre' in avvisi(C), pin
    assert not META.richieste, 'un PIN sbagliato e\' arrivato a Meta'
    r = C.post('/invii', data={'azione': 'registra_whatsapp', 'pin': ' 123 456 '})
    assert r.status_code == 302 and 'Numero registrato' in avvisi(C)
    q = META.richieste[-1]
    assert q['percorso'] == '/%s/123456789/register' % invii.PREDEFINITI['wa_versione'] and \
        q['auth'] == 'Bearer ' + TOKEN and q['corpo'] == {'messaging_product': 'whatsapp', 'pin': '123456'}, q
    s = S()
    valori = [x.valore or '' for x in s.scalars(select(Impostazione))]
    registrato = invii.impostazioni(s)['wa_registrato']
    s.close()
    assert not any('123456' in v and v != '123456789' for v in valori), 'il PIN e\' rimasto salvato'
    assert re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', registrato), registrato
    assert 'Numero registrato il' in testo(C.get('/invii'))
    # un altro numero: la registrazione non vale piu'
    C.post('/invii', data={'azione': 'salva', 'sezione': 'whatsapp', 'wa_numero_id': '987654321',
                           'wa_modello': 'promemoria_appuntamento', 'wa_lingua': 'it',
                           'wa_parametri': 'paziente,giorno,ora,struttura,recapito', 'wa_versione': 'v25.0'})
    s = S()
    assert invii.impostazioni(s)['wa_registrato'] == ''
    s.close()


def w_errori():
    S, C = mondo(con_persone=False)
    con_whatsapp(S)
    casi = [((400, {'error': {'message': '(#133005) Two step verification PIN Mismatch', 'code': 133005}}), 'PIN sbagliato'),
            ((400, {'error': {'message': 'Rate limit', 'code': 133016}}), 'al massimo 10 in 72 ore'),
            ((401, {'error': {'message': 'Invalid OAuth access token', 'code': 190}}), 'token non vale'),
            ((400, {'error': {'message': 'x', 'code': 133006, 'error_user_msg': 'Verifica di nuovo il numero'}}),
             'Verifica di nuovo il numero'),
            ((500, '<html>errore</html>'), 'Meta non ha registrato il numero'),
            ((200, {}), 'risposta di Meta non prevista'),
            ((200, {'success': False}), 'risposta di Meta non prevista')]
    for risposta, atteso in casi:
        META.prepara(*risposta)
        C.post('/invii', data={'azione': 'registra_whatsapp', 'pin': '654321'})
        msg = avvisi(C)
        assert atteso in msg and 'Numero registrato' not in msg and '654321' not in msg, (risposta, msg)
    s = S()
    assert invii.impostazioni(s)['wa_registrato'] == ''
    s.close()
    # Meta spenta
    import socket
    libero = socket.socket()
    libero.bind(('127.0.0.1', 0))
    porta = libero.getsockname()[1]
    libero.close()
    con_whatsapp(S, wa_indirizzo='http://127.0.0.1:%d' % porta)
    C.post('/invii', data={'azione': 'registra_whatsapp', 'pin': '654321'})
    assert 'Meta non raggiungibile' in avvisi(C)
    # un messaggio rifiutato perche' il numero non e' registrato: il programma dice cosa fare
    con_whatsapp(S)
    META.prepara(400, {'error': {'message': '(#133010) Account not registered', 'code': 133010}})
    cfg = dict(invii.PREDEFINITI, wa_token=invii.proteggi(TOKEN), wa_numero_id='123456789',
               wa_indirizzo='http://127.0.0.1:%d' % META.server_address[1])
    try:
        invii.manda_whatsapp(cfg, '393330000001', ['a', 'b', 'c', 'd', 'e'])
        raise AssertionError('messaggio accettato')
    except invii.ErroreInvio as e:
        assert 'codice 133010' in str(e) and '«Registra il numero»' in str(e) and e.permanente, str(e)


def w_pagina():
    S, C = mondo(con_persone=False)
    t = testo(C.get('/invii'))
    for x in ('whatsapp_business_management', 'Registra il numero', 'Utenti di sistema', 'nome visualizzato',
              'codice 133010'):
        assert x in t, x
    corpo = html(C.get('/invii'))
    assert re.search(r'<button class="bottone" type="submit" disabled[^>]*>Registra il numero', corpo), 'pulsante acceso senza token'
    con_whatsapp(S)
    corpo = html(C.get('/invii'))
    assert re.search(r'<button class="bottone" type="submit">Registra il numero', corpo)
    assert 'name="pin"' in corpo and 'autocomplete="off"' in corpo and 'type="password" id="pin-wa"' in corpo


prova('registrare il numero: PIN controllato, richiesta a Meta, PIN mai salvato', w_registra)
prova('registrazione rifiutata: il motivo in parole semplici, nessun segno di riuscita', w_errori)
prova('pagina: i passi aggiornati e il pulsante solo con token e ID', w_pagina)


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
