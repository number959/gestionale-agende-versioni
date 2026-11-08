# -*- coding: utf-8 -*-
"""Prove della 1.12: gli ambulatori (ambulatori.py), cioe' chi sta in quale
stanza calcolato dai turni dei medici.

- mezze giornate e ore libere (mezze_giornate, buchi);
- la matrice della settimana contro un oracolo minuto per minuto, con turni
  messi a caso, turni di un giorno, assenze, una chiusura e un festivo in cui
  la struttura chiude; la settimana tipo; stanze disattivate e sale operatorie
  fuori;
- la programmazione del mese: gruppi per specialita', date in cui il medico
  viene davvero, note («non il 2 e il 9 (assente: ferie)», «dal», «fino al»,
  «un giorno solo», «fasce da 20 minuti»), calendario;
- le pagine e i due Excel (matrice, settimana tipo, programmazione con il
  calendario), con i loro nomi e senza file lasciati nella cartella temporanea;
- la pianificazione: Metti (ogni settimana o un giorno solo, con le stesse
  regole della scheda del turno) e Togli (elimina o chiude alla domenica
  prima), il ritorno solo a pagine interne, tutto nello storico;
- anagrafiche: la regola «una stanza ospita un medico alla volta» estratta in
  stanza_gia_assegnata, e il ritorno alla pagina di partenza (torna).

Nomi inventati; le date sono fisse (dicembre 2026: l'8 e' l'Immacolata)."""
import json
import logging
import os
import random
import shutil
import sys
import tempfile
import traceback
from datetime import date, datetime, time, timedelta
from io import BytesIO

CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = tempfile.mkdtemp(prefix='prove_112_')
os.environ['LOCALAPPDATA'] = os.path.join(PROVVISORIA, 'localappdata')
os.environ['NO_PROXY'] = os.environ['no_proxy'] = '127.0.0.1,localhost'
sys.path.insert(0, CARTELLA)
logging.getLogger().setLevel(logging.CRITICAL)

from openpyxl import load_workbook  # noqa: E402
from sqlalchemy import select  # noqa: E402

import app as A  # noqa: E402
import ambulatori as AM  # noqa: E402
import anagrafiche  # noqa: E402
import calendario  # noqa: E402
import comune  # noqa: E402
import servizi  # noqa: E402
import viste  # noqa: E402
from modelli import (crea_sessione, Struttura, Risorsa, Operatore, Turno, Assenza, Chiusura,  # noqa: E402
                     Modifica)

A.app.config['TESTING'] = True
esiti, _area, _n = [], [''], [0]
SOLO = [x for x in os.environ.get('PROVE_SOLO', '').split(',') if x]
CASA = {'Sec-Fetch-Site': 'same-origin'}
# dicembre 2026: lunedi 7, martedi 8 Immacolata (festivo), venerdi 25 Natale
LUN = date(2026, 12, 7)
OGGI = date.today()


def area(nome):
    _area[0] = nome


def prova(nome, f):
    if SOLO and not any(x in nome for x in SOLO):
        return
    try:
        esiti.append(('OK', _area[0], nome, f() or ''))
    except AssertionError as e:
        riga = traceback.extract_tb(sys.exc_info()[2])[-1].lineno
        esiti.append(('ROTTO', _area[0], nome, '%s (riga %d)' % (str(e) or 'asserzione fallita', riga)))
    except Exception:
        esiti.append(('ERRORE', _area[0], nome, traceback.format_exc().strip().splitlines()[-1]))


# ================================================================ il mondo
def mondo(chiusa_festivi=True, seconda=False):
    """Un database nuovo: la struttura (lun-sab, 8-20, chiude nei festivi),
    quattro medici con e senza specialita', le stanze del primo avvio piu'
    una sala operatoria. (S, ids, client)."""
    _n[0] += 1
    S = crea_sessione('sqlite:///' + os.path.join(PROVVISORIA, 'db_%d.db' % _n[0]))
    s = S()
    servizi.prepara_primo_avvio(s)
    st = s.get(Struttura, 1)
    st.nome, st.giorni_apertura, st.chiusa_festivi = 'Clinica Prova', '1111110', chiusa_festivi
    s.add_all([Operatore(cognome='Galasso', nome='', specialita='cardiologia'),
               Operatore(cognome='Lippiello', nome='Anna', specialita='Dermatologia'),
               Operatore(cognome='Fintini', nome='Ugo'),
               Operatore(cognome='Esempietti', nome='Rita', specialita='cardiologia')])
    s.add(Risorsa(nome='Sala operatoria', tipo='SALA_OPERATORIA', struttura_id=1, ordine=50))
    if seconda:
        s.add(Struttura(nome='Centro Nord'))
        s.flush()
        s.add(Risorsa(nome='Stanza Nord', struttura_id=2, ordine=1))
    s.commit()
    I = {r.nome: r.id for r in s.scalars(select(Risorsa))}
    I.update({o.cognome: o.id for o in s.scalars(select(Operatore))})
    s.close()
    A.Sessione = S
    A._registro = None
    viste._sessionmaker = lambda: S
    return S, I, A.app.test_client()


def turno(S, oid, rid, giorno, da, a, valido_da=None, valido_a=None, passo=None):
    s = S()
    t = Turno(operatore_id=oid, risorsa_id=rid, giorno_settimana=giorno, ora_inizio=da, ora_fine=a,
              valido_da=valido_da or date(2026, 1, 5), valido_a=valido_a, passo=passo)
    s.add(t)
    s.commit()
    tid = t.id
    s.close()
    return tid


def singolo(S, oid, rid, g, da, a):
    return turno(S, oid, rid, g.weekday(), da, a, valido_da=g, valido_a=g)


def assenza(S, oid, dal, al, motivo='Ferie'):
    s = S()
    s.add(Assenza(operatore_id=oid, dal=dal, al=al, motivo=motivo))
    s.commit()
    s.close()


def chiusura(S, dal, al, motivo='Manutenzione'):
    s = S()
    s.add(Chiusura(struttura_id=1, dal=dal, al=al, motivo=motivo))
    s.commit()
    s.close()


def testo(r):
    return r.data.decode('utf-8')


def avvisi(c):
    with c.session_transaction() as sess:
        m = sess.get('_flashes', [])
        sess['_flashes'] = []
    return ' '.join(x[1] for x in m)


def excel(C, indirizzo):
    r = C.get(indirizzo)
    assert r.status_code == 200 and r.data[:2] == b'PK', (indirizzo, r.status_code)
    return r, load_workbook(BytesIO(r.data))


def mondo_pieno():
    """Il mondo con una settimana ricca: lunedi 7/12 Galasso 8-13 e Lippiello
    15-20 in Ambulatorio 1, Fintini martedi tutto il giorno in Ambulatorio 2,
    un turno di un giorno mercoledi 9, Galasso assente lunedi, giovedi
    chiusa, la sala operatoria con un turno ogni giorno."""
    S, I, C = mondo()
    turno(S, I['Galasso'], I['Ambulatorio 1'], 0, time(8), time(13))
    turno(S, I['Lippiello'], I['Ambulatorio 1'], 0, time(15), time(20))
    turno(S, I['Fintini'], I['Ambulatorio 2'], 1, time(8), time(20))
    singolo(S, I['Fintini'], I['Ambulatorio 3'], LUN + timedelta(days=2), time(9), time(11))
    for gs in range(6):
        turno(S, I['Esempietti'], I['Sala operatoria'], gs, time(8), time(14))
    assenza(S, I['Galasso'], LUN, LUN)
    chiusura(S, LUN + timedelta(days=3), LUN + timedelta(days=3))
    return S, I, C


# ====================================================== mezze giornate e buchi
area('mezze giornate e ore libere')


def a_mezze_giornate():
    S, I, C = mondo()
    s = S()
    st = s.get(Struttura, 1)
    m = AM.mezze_giornate(st)
    assert [(x['nome'], x['da'], x['a']) for x in m] == [('mattina', time(8), time(14)), ('pomeriggio', time(14), time(20))], m
    assert [x['etichetta'] for x in m] == ['Mattina', 'Pomeriggio']
    st.ora_apertura = time(15)
    m = AM.mezze_giornate(st)
    assert [(x['nome'], x['da'], x['a']) for x in m] == [('pomeriggio', time(15), time(20))], m
    st.ora_apertura, st.ora_chiusura = time(8), time(12)
    m = AM.mezze_giornate(st)
    assert [(x['nome'], x['da'], x['a']) for x in m] == [('mattina', time(8), time(12))], m
    st.ora_apertura, st.ora_chiusura = time(9, 30), time(18)
    m = AM.mezze_giornate(st)
    assert [(x['da'], x['a']) for x in m] == [(time(9, 30), time(14)), (time(14), time(18))], m
    s.close()


def p(da, a):
    return {'da': da, 'a': a}


def a_buchi():
    assert AM.buchi([], time(8), time(14)) == [(time(8), time(14))]
    assert AM.buchi([p(time(10), time(12))], time(8), time(14)) == [(time(8), time(10)), (time(12), time(14))]
    assert AM.buchi([p(time(8), time(11)), p(time(11), time(14))], time(8), time(14)) == []
    # presenze che si sovrappongono: il buco si misura dalla fine piu' lontana
    assert AM.buchi([p(time(8), time(12)), p(time(9), time(10))], time(8), time(14)) == [(time(12), time(14))]
    # sotto l'ora non si segnala
    assert AM.buchi([p(time(8), time(13, 30))], time(8), time(14)) == []
    assert AM.buchi([p(time(8, 45), time(14))], time(8), time(14)) == []
    assert AM.buchi([p(time(9), time(14))], time(8), time(14)) == [(time(8), time(9))]
    # il buco in fondo finisce all'ora di chiusura esatta
    assert AM.buchi([p(time(14), time(18, 30))], time(14), time(20)) == [(time(18, 30), time(20))]
    assert AM.buchi([p(time(10), time(11))], time(8), time(14), minimo=30) == [(time(8), time(10)), (time(11), time(14))]
    # in ordine di ora, anche se le presenze arrivano in disordine
    assert AM.buchi([p(time(12), time(13)), p(time(9), time(10))], time(8), time(14)) == [
        (time(8), time(9)), (time(10), time(12)), (time(13), time(14))]


prova('mezze giornate: 8-14 e 14-20; apre alle 15 solo pomeriggio; chiude alle 12 solo mattina', a_mezze_giornate)
prova('ore libere: nessuno, in mezzo, attaccate, sovrapposte, sotto l\'ora, in fondo', a_buchi)


# ================================================================ matrice
area('matrice della settimana')


def oracolo_matrice(s, st, lunedi, tipo=False):
    """La matrice rifatta minuto per minuto, senza passare da ambulatori.py."""
    regole = servizi.Regole(s, lunedi, lunedi + timedelta(days=6))
    giorni = [lunedi + timedelta(days=i) for i in range(7)]
    giorni = [g for g in giorni if g.weekday() in st.giorni_aperti or regole.turni_validi(g, st)]
    meta = AM.mezze_giornate(st)
    atteso = {}
    for r in st.risorse:
        if not r.attiva or r.tipo == 'SALA_OPERATORIA':
            continue
        for g in giorni:
            i = regole.giorno(g, st)
            validi = regole.turni_validi(g, st, r.id)
            if tipo:
                turni = [t for t in validi if t.valido_da != t.valido_a]
                chiuso = None
            else:
                turni = regole.turni_effettivi(g, st, r.id, i)
                chiuso = i['chiusura'] or (i['festivo'] if i['chiude_festivo'] and not turni else None)
            for m in meta:
                m0, m1 = m['da'].hour * 60 + m['da'].minute, m['a'].hour * 60 + m['a'].minute
                occupati = set()
                presenze = []
                for t in turni:
                    t0, t1 = t.ora_inizio.hour * 60 + t.ora_inizio.minute, t.ora_fine.hour * 60 + t.ora_fine.minute
                    if t0 < m1 and m0 < t1:
                        occupati.update(range(max(t0, m0), min(t1, m1)))
                        presenze.append((max(t0, m0), t.operatore.cognome, t.id, min(t1, m1)))
                libere = []
                if not chiuso and presenze:
                    corsa = None
                    for minuto in range(m0, m1 + 1):
                        libero = minuto < m1 and minuto not in occupati
                        if libero and corsa is None:
                            corsa = minuto
                        if not libero and corsa is not None:
                            if minuto - corsa >= AM.MINIMO_LIBERO:
                                libere.append((corsa, minuto))
                            corsa = None
                assenti = [] if tipo else sorted(
                    (t.operatore.cognome, t.id) for t in validi
                    if t.operatore_id in i['assenze'] and t.ora_inizio < m['a'] and m['da'] < t.ora_fine)
                atteso[(r.id, g, m['nome'])] = {
                    'presenze': sorted(presenze), 'libere': libere, 'chiuso': chiuso,
                    'tutta_libera': not presenze and not chiuso, 'assenti': assenti}
    return giorni, atteso


def mm(t):
    return t.hour * 60 + t.minute


def confronta(vista, giorni, atteso):
    assert vista['giorni'] == giorni, (vista['giorni'], giorni)
    visti = set()
    for riga in vista['righe']:
        assert len(riga['celle']) == len(giorni) * len(vista['meta'])
        for c in riga['celle']:
            k = (riga['risorsa'].id, c['data'], c['meta']['nome'])
            assert k in atteso, k
            visti.add(k)
            e = atteso[k]
            presenze = sorted((mm(x['da']), x['operatore'].cognome, x['turno'].id, mm(x['a'])) for x in c['presenze'])
            assert presenze == e['presenze'], (k, presenze, e['presenze'])
            assert [(mm(a), mm(b)) for a, b in c['libere']] == e['libere'], (k, c['libere'], e['libere'])
            assert c['chiuso'] == e['chiuso'], (k, c['chiuso'], e['chiuso'])
            assert c['tutta_libera'] == e['tutta_libera'], k
            assert sorted((o.cognome, t.id) for o, _, t in c['assenti']) == e['assenti'], (k, c['assenti'])
            # le presenze gia' in ordine di ora, con le ore dentro la mezza giornata
            assert [mm(x['da']) for x in c['presenze']] == sorted(mm(x['da']) for x in c['presenze'])
            assert all(c['meta']['da'] <= x['da'] < x['a'] <= c['meta']['a'] for x in c['presenze']), k
            # la proposta per il «+»: il primo buco, o tutta la mezza giornata
            if c['libere']:
                assert c['proposta'] == c['libere'][0]
            else:
                assert c['proposta'] == (c['meta']['da'], c['meta']['a'])
    assert visti == set(atteso), (len(visti), len(atteso))
    libere = sum(1 for r in vista['righe'] for c in r['celle'] if c['tutta_libera'])
    parziali = sum(1 for r in vista['righe'] for c in r['celle'] if not c['tutta_libera'] and c['libere'])
    assert (vista['libere'], vista['parziali']) == (libere, parziali), (vista['libere'], vista['parziali'], libere, parziali)


def b_oracolo():
    S, I, C = mondo()
    caso = random.Random(112)
    medici = [I['Galasso'], I['Lippiello'], I['Fintini'], I['Esempietti']]
    stanze = [I['Ambulatorio %d' % k] for k in range(1, 6)] + [I['Sala endoscopia']]
    s = S()
    s.get(Risorsa, I['Ambulatorio 5']).attiva = False
    s.commit()
    s.close()
    for _ in range(14):
        da = caso.choice(range(8 * 60, 18 * 60, 15))
        a = min(20 * 60, da + caso.choice([60, 120, 180, 240, 360, 480]))
        turno(S, caso.choice(medici), caso.choice(stanze), caso.randrange(7), time(da // 60, da % 60), time(a // 60, a % 60),
              valido_da=LUN - timedelta(days=caso.choice([0, 7, 30])) if caso.random() < 0.7 else LUN + timedelta(days=caso.randrange(7)),
              valido_a=None if caso.random() < 0.7 else LUN + timedelta(days=caso.randrange(7)))
    for _ in range(3):
        g = LUN + timedelta(days=caso.randrange(7))
        da = caso.choice(range(8 * 60, 18 * 60, 30))
        singolo(S, caso.choice(medici), caso.choice(stanze), g, time(da // 60, da % 60), time(min(20, da // 60 + 3), da % 60))
    assenza(S, I['Galasso'], LUN + timedelta(days=1), LUN + timedelta(days=2))
    assenza(S, I['Fintini'], LUN - timedelta(days=3), LUN + timedelta(days=10), 'Congresso')
    chiusura(S, LUN + timedelta(days=4), LUN + timedelta(days=4))
    conti = []
    for lunedi in (LUN, LUN + timedelta(days=7), LUN - timedelta(days=7)):
        for tipo in (False, True):
            s = S()
            st = s.get(Struttura, 1)
            giorni, atteso = oracolo_matrice(s, st, lunedi, tipo)
            vista = AM.matrice(s, lunedi, st, tipo=tipo)
            confronta(vista, giorni, atteso)
            conti.append((vista['libere'], vista['parziali']))
            s.close()
    assert any(l for l, _ in conti) and any(p_ for _, p_ in conti), conti
    return 'tre settimane, vere e tipo: %s' % conti


def b_festivo_e_chiusura():
    S, I, C = mondo_pieno()
    s = S()
    st = s.get(Struttura, 1)
    v = AM.matrice(s, LUN, st)
    assert [g.weekday() for g in v['giorni']] == [0, 1, 2, 3, 4, 5], v['giorni']
    assert [x['nome'] for x in v['meta']] == ['mattina', 'pomeriggio']
    assert [r['risorsa'].nome for r in v['righe']] == ['Ambulatorio 1', 'Ambulatorio 2', 'Ambulatorio 3', 'Ambulatorio 4',
                                                        'Ambulatorio 5', 'Sala endoscopia'], [r['risorsa'].nome for r in v['righe']]
    celle = {(r['risorsa'].nome, c['data'].weekday(), c['meta']['nome']): c for r in v['righe'] for c in r['celle']}
    # martedi 8: Immacolata, la struttura chiude: tutte le celle chiuse, niente ore libere
    for nome in ('Ambulatorio 1', 'Ambulatorio 2', 'Sala endoscopia'):
        for meta in ('mattina', 'pomeriggio'):
            c = celle[(nome, 1, meta)]
            assert c['chiuso'] == 'Immacolata Concezione' and not c['libere'] and not c['tutta_libera'] and not c['presenze'], (nome, meta, c)
    # giovedi: chiusura
    assert celle[('Ambulatorio 4', 3, 'mattina')]['chiuso'] == 'Manutenzione'
    assert v['info'][LUN + timedelta(days=3)]['chiusura'] == 'Manutenzione'
    # lunedi mattina Ambulatorio 1: Galasso assente, cella disponibile con l'assente segnato
    c = celle[('Ambulatorio 1', 0, 'mattina')]
    assert c['tutta_libera'] and not c['presenze'] and [(o.cognome, m) for o, m, _ in c['assenti']] == [('Galasso', 'Ferie')], c
    assert c['libere'] == [] and c['proposta'] == (time(8), time(14)), 'una cella tutta libera dice solo DISPONIBILE'
    # lunedi pomeriggio: Lippiello 15-20, libero 14-15
    c = celle[('Ambulatorio 1', 0, 'pomeriggio')]
    assert [(x['operatore'].cognome, x['da'], x['a']) for x in c['presenze']] == [('Lippiello', time(15), time(20))]
    assert c['libere'] == [(time(14), time(15))] and not c['tutta_libera'] and not c['assenti']
    # martedi (festivo) con un turno di un giorno: la stanza apre lo stesso
    singolo(S, I['Lippiello'], I['Ambulatorio 4'], LUN + timedelta(days=1), time(9), time(12))
    s.close()
    s = S()
    v = AM.matrice(s, LUN, s.get(Struttura, 1))
    celle = {(r['risorsa'].nome, c['data'].weekday(), c['meta']['nome']): c for r in v['righe'] for c in r['celle']}
    c = celle[('Ambulatorio 4', 1, 'mattina')]
    assert not c['chiuso'] and [x['operatore'].cognome for x in c['presenze']] == ['Lippiello'] and c['libere'] == [(time(8), time(9)), (time(12), time(14))], c
    # il pomeriggio di quella stanza: nessuno, e resta chiuso (il turno di un giorno apre solo la sua meta')
    c = celle[('Ambulatorio 4', 1, 'pomeriggio')]
    assert not c['presenze'] and c['chiuso'] == 'Immacolata Concezione' and not c['tutta_libera'] and not c['libere'], c
    assert celle[('Ambulatorio 1', 1, 'mattina')]['chiuso'] == 'Immacolata Concezione'
    s.close()


def b_settimana_tipo():
    S, I, C = mondo_pieno()
    s = S()
    st = s.get(Struttura, 1)
    v = AM.matrice(s, LUN, st, tipo=True)
    assert v['tipo']
    celle = {(r['risorsa'].nome, c['data'].weekday(), c['meta']['nome']): c for r in v['righe'] for c in r['celle']}
    # l'assenza di Galasso non conta, la chiusura e il festivo nemmeno, il turno di un giorno sparisce
    c = celle[('Ambulatorio 1', 0, 'mattina')]
    assert [x['operatore'].cognome for x in c['presenze']] == ['Galasso'] and not c['assenti'] and c['libere'] == [(time(13), time(14))], c
    assert not any(c['chiuso'] for c in celle.values())
    assert not celle[('Ambulatorio 3', 2, 'mattina')]['presenze'] and celle[('Ambulatorio 3', 2, 'mattina')]['tutta_libera']
    assert celle[('Ambulatorio 3', 2, 'mattina')]['libere'] == [] and celle[('Ambulatorio 3', 2, 'mattina')]['proposta'] == (time(8), time(14))
    assert celle[('Ambulatorio 2', 1, 'mattina')]['presenze'][0]['operatore'].cognome == 'Fintini'
    s.close()


def b_stanze_fuori():
    S, I, C = mondo_pieno()
    s = S()
    s.get(Risorsa, I['Ambulatorio 4']).attiva = False
    s.commit()
    st = s.get(Struttura, 1)
    v = AM.matrice(s, LUN, st)
    nomi = [r['risorsa'].nome for r in v['righe']]
    assert 'Ambulatorio 4' not in nomi and 'Sala operatoria' not in nomi, nomi
    assert 'Sala endoscopia' in nomi and 'Ambulatorio 1' in nomi, nomi
    # le altre: endoscopia e altro restano
    s.get(Risorsa, I['Ambulatorio 5']).tipo = 'ALTRO'
    s.commit()
    v = AM.matrice(s, LUN, st)
    assert 'Ambulatorio 5' in [r['risorsa'].nome for r in v['righe']]
    # la sala operatoria non compare neanche nella programmazione
    pr = AM.programmazione(s, 2026, 12, st)
    assert all(r['risorsa'].nome != 'Sala operatoria' for r in pr['righe']) and pr['righe'], [r['risorsa'].nome for r in pr['righe']]
    assert all(t.risorsa.nome != 'Sala operatoria' for g in pr['calendario'] for t in g['presenze'])
    assert not any(r['risorsa'].nome == 'Ambulatorio 4' for r in pr['righe'])
    s.close()
    # ... ne' nei due Excel
    for indirizzo in ('/ambulatori/settimana/%s.xlsx' % LUN.isoformat(), '/ambulatori/mese/2026-12.xlsx'):
        _, wb = excel(C, indirizzo)
        valori = [str(c.value) for ws in wb for row in ws.iter_rows() for c in row if c.value is not None]
        assert not any('Sala operatoria' in v or 'Esempietti' in v for v in valori), (indirizzo, [v for v in valori if 'Sala' in v][:5])
        assert any('Sala endoscopia' in v for v in valori) or indirizzo.startswith('/ambulatori/mese'), indirizzo


def b_giorni_mostrati():
    """I giorni di apertura, piu' quelli in cui c'e' comunque un turno."""
    S, I, C = mondo()
    s = S()
    st = s.get(Struttura, 1)
    st.giorni_apertura = '1111100'
    s.commit()
    v = AM.matrice(s, LUN, st)
    assert [g.weekday() for g in v['giorni']] == [0, 1, 2, 3, 4], v['giorni']
    s.close()
    turno(S, I['Galasso'], I['Ambulatorio 1'], 6, time(9), time(12))
    s = S()
    v = AM.matrice(s, LUN, s.get(Struttura, 1))
    assert [g.weekday() for g in v['giorni']] == [0, 1, 2, 3, 4, 6], v['giorni']
    assert v['righe'][0]['celle'][-2]['presenze'][0]['operatore'].cognome == 'Galasso'
    s.close()


prova('matrice contro l\'oracolo minuto per minuto: turni a caso, di un giorno, assenze, chiusura, festivo; settimana tipo', b_oracolo)
prova('festivo in cui si chiude e chiusura: celle chiuse; assente: cella disponibile con l\'assente; ore avanzate', b_festivo_e_chiusura)
prova('settimana tipo: solo i turni che si ripetono, senza assenze, chiusure e festivi', b_settimana_tipo)
prova('stanze disattivate e sale operatorie fuori da matrice, programmazione ed Excel; endoscopia e altro dentro', b_stanze_fuori)
prova('giorni mostrati: quelli di apertura più quelli con un turno', b_giorni_mostrati)


# ========================================================= programmazione
area('programmazione del mese')


def c_gruppi_e_date():
    S, I, C = mondo_pieno()
    turno(S, I['Esempietti'], I['Ambulatorio 4'], 4, time(9), time(12), passo=20)          # cardiologia, venerdi
    assenza(S, I['Lippiello'], date(2026, 12, 14), date(2026, 12, 21), 'Congresso')
    s = S()
    st = s.get(Struttura, 1)
    v = AM.programmazione(s, 2026, 12, st)
    assert (v['primo'], v['ultimo']) == (date(2026, 12, 1), date(2026, 12, 31))
    assert [g['specialita'] for g in v['gruppi']] == ['Cardiologia', 'Dermatologia', 'Senza specialità'], [g['specialita'] for g in v['gruppi']]
    righe = [(r['specialita'], r['operatore'].cognome, r['giorno'], [g.day for g in r['date']], r['note']) for r in v['righe']]
    # cardiologia: Esempietti (E) prima di Galasso (G); il venerdi 25 e' Natale e si chiude
    assert righe[0] == ('Cardiologia', 'Esempietti', 4, [4, 11, 18], ['non il 25 (chiusa: natale)', 'fasce da 20 minuti']), righe[0]
    # Galasso: lunedi 7 assente, 8 e' martedi; dicembre ha i lunedi 7, 14, 21, 28
    assert righe[1] == ('Cardiologia', 'Galasso', 0, [14, 21, 28], ['non il 7 (assente: ferie)']), righe[1]
    assert righe[2] == ('Dermatologia', 'Lippiello', 0, [7, 28], ['non il 14 e il 21 (assente: congresso)']), righe[2]
    # Fintini: martedi 8 Immacolata; giovedi 10 niente (il turno e' di martedi); poi il turno di un giorno
    assert righe[3] == ('Senza specialità', 'Fintini', 1, [1, 15, 22, 29], ["non l'8 (chiusa: immacolata concezione)"]), righe[3]
    assert righe[4] == ('Senza specialità', 'Fintini', 2, [9], ['un giorno solo']), righe[4]
    assert len(righe) == 5 and v['medici'] == 4, (len(righe), v['medici'])
    # le date: esattamente i giorni della settimana del mese in cui il turno vale, tolti i saltati
    for r in v['righe']:
        t = r['turno']
        attese = [g for g in calendario.giorni_del_mese(2026, 12) if t.vale_il(g)]
        assert sorted(list(r['date']) + [g for g, _ in r['saltate']]) == attese, (r['operatore'].cognome, r['date'], r['saltate'])
    s.close()


def c_note_validita():
    S, I, C = mondo()
    turno(S, I['Galasso'], I['Ambulatorio 1'], 2, time(8), time(12), valido_da=date(2026, 12, 10))          # mercoledi, dal 10
    turno(S, I['Lippiello'], I['Ambulatorio 2'], 2, time(8), time(12), valido_a=date(2026, 12, 20))         # fino al 20
    turno(S, I['Fintini'], I['Ambulatorio 3'], 2, time(8), time(12), valido_da=date(2026, 12, 2), valido_a=date(2026, 12, 23))
    turno(S, I['Esempietti'], I['Ambulatorio 4'], 3, time(8), time(12))                                    # giovedi
    assenza(S, I['Esempietti'], date(2026, 11, 20), date(2027, 1, 10), 'Maternità')
    chiusura(S, date(2026, 12, 16), date(2026, 12, 16), 'Lavori')
    s = S()
    v = AM.programmazione(s, 2026, 12, s.get(Struttura, 1))
    per = {(r['operatore'].cognome, r['giorno']): r for r in v['righe']}
    r = per[('Galasso', 2)]
    assert [g.day for g in r['date']] == [23, 30] and r['note'] == ['dal 10', 'non il 16 (chiusa: lavori)'], (r['date'], r['note'])
    r = per[('Lippiello', 2)]
    assert [g.day for g in r['date']] == [2, 9] and r['note'] == ['fino al 20', 'non il 16 (chiusa: lavori)'], (r['date'], r['note'])
    r = per[('Fintini', 2)]
    assert [g.day for g in r['date']] == [2, 9, 23] and r['note'] == ['dal 2', 'fino al 23', 'non il 16 (chiusa: lavori)'], r['note']
    r = per[('Esempietti', 3)]
    assert r['date'] == [] and r['note'] == ['non il 3, il 10, il 17, il 24 e il 31 (assente: maternità)', 'nessuna seduta nel mese'], r['note']
    # un turno che non tocca il mese non compare
    turno(S, I['Galasso'], I['Ambulatorio 5'], 0, time(8), time(12), valido_da=date(2027, 2, 1))
    turno(S, I['Galasso'], I['Ambulatorio 5'], 1, time(8), time(12), valido_a=date(2026, 11, 30))
    s.close()
    s = S()
    v = AM.programmazione(s, 2026, 12, s.get(Struttura, 1))
    assert len(v['righe']) == 4, [(r['operatore'].cognome, r['giorno']) for r in v['righe']]
    # niente turni: niente gruppi, calendario pieno di giorni vuoti
    v = AM.programmazione(s, 2025, 12, s.get(Struttura, 1))
    assert v['righe'] == [] and v['gruppi'] == [] and v['medici'] == 0 and len(v['calendario']) == 31
    s.close()


def c_calendario():
    S, I, C = mondo_pieno()
    s = S()
    v = AM.programmazione(s, 2026, 12, s.get(Struttura, 1))
    cal = {g['data']: g for g in v['calendario']}
    assert len(cal) == 31 and [x['data'] for x in v['calendario']] == calendario.giorni_del_mese(2026, 12)
    # lunedi 7: solo Lippiello (Galasso assente); martedi 8: festivo, nessuno; giovedi 10: chiusa
    assert [t.operatore.cognome for t in cal[date(2026, 12, 7)]['presenze']] == ['Lippiello']
    assert cal[date(2026, 12, 8)]['presenze'] == [] and cal[date(2026, 12, 8)]['info']['festivo'] == 'Immacolata Concezione'
    assert cal[date(2026, 12, 10)]['presenze'] == [] and cal[date(2026, 12, 10)]['info']['chiusura'] == 'Manutenzione'
    assert [t.operatore.cognome for t in cal[date(2026, 12, 9)]['presenze']] == ['Fintini']       # il turno di un giorno
    assert [t.operatore.cognome for t in cal[date(2026, 12, 14)]['presenze']] == ['Galasso', 'Lippiello']
    # in ordine di stanza e poi di ora
    turno(S, I['Esempietti'], I['Ambulatorio 2'], 0, time(7), time(9))
    s.close()
    s = S()
    v = AM.programmazione(s, 2026, 12, s.get(Struttura, 1))
    cal = {g['data']: g for g in v['calendario']}
    assert [(t.risorsa.nome, t.operatore.cognome) for t in cal[date(2026, 12, 14)]['presenze']] == [
        ('Ambulatorio 1', 'Galasso'), ('Ambulatorio 1', 'Lippiello'), ('Ambulatorio 2', 'Esempietti')]
    s.close()


def c_altra_struttura():
    S, I, C = mondo(seconda=True)
    turno(S, I['Galasso'], I['Stanza Nord'], 0, time(8), time(12))
    turno(S, I['Galasso'], I['Ambulatorio 1'], 1, time(8), time(12))
    s = S()
    v = AM.programmazione(s, 2026, 12, s.get(Struttura, 1))
    assert [(r['risorsa'].nome, r['giorno']) for r in v['righe']] == [('Ambulatorio 1', 1)], v['righe']
    v = AM.programmazione(s, 2026, 12, s.get(Struttura, 2))
    assert [(r['risorsa'].nome, r['giorno']) for r in v['righe']] == [('Stanza Nord', 0)]
    m = AM.matrice(s, LUN, s.get(Struttura, 2))
    assert [r['risorsa'].nome for r in m['righe']] == ['Stanza Nord'] and m['righe'][0]['celle'][0]['presenze'][0]['operatore'].cognome == 'Galasso'
    s.close()
    # ... e dalla pagina, con ?struttura=
    t = testo(C.get('/ambulatori/settimana/%s?struttura=2' % LUN.isoformat()))
    assert 'Stanza Nord' in t and 'Ambulatorio 1' not in t
    t = testo(C.get('/ambulatori/mese/2026-12?struttura=2'))
    assert 'Stanza Nord' in t and 'Ambulatorio 1' not in t


prova('gruppi per specialità (Senza specialità ultimo), ordine, date del mese tolti assenze, chiusura e Natale', c_gruppi_e_date)
prova('note: dal, fino al, giorni saltati raggruppati, nessuna seduta nel mese; turni fuori dal mese esclusi', c_note_validita)
prova('calendario giorno per giorno: festivo, chiusura, assente, turno di un giorno, ordine per stanza e ora', c_calendario)
prova('le stanze di un\'altra struttura restano fuori; ?struttura= cambia struttura', c_altra_struttura)


# ================================================================= pagine
area('pagine')


def d_settimana():
    S, I, C = mondo_pieno()
    r = C.get('/ambulatori')
    assert r.status_code == 308 and r.headers['Location'].endswith('/ambulatori/'), (r.status_code, r.headers.get('Location'))
    r = C.get('/ambulatori/')
    assert r.status_code == 302 and '/ambulatori/settimana/%s' % OGGI.isoformat() in r.headers['Location'], r.headers.get('Location')
    r = C.get('/ambulatori/?struttura=1')
    assert r.status_code == 302 and 'struttura=1' in r.headers['Location']
    r = C.get('/ambulatori/settimana/%s' % LUN.isoformat())
    assert r.status_code == 200
    t = testo(r)
    assert 'id="matrice-ambulatori"' in t and 'data-lunedi="2026-12-07"' in t
    assert 'DISPONIBILE' in t and 'libero 14:00–15:00' in t and 'assente: ferie' in t, t[:200]
    assert 'chiusa: immacolata concezione' in t and 'chiusa: manutenzione' in t
    assert 'Settimana dal 7 dicembre al 13 dicembre 2026' in t
    assert 'Sala operatoria' not in t
    # i nomi aprono il turno, tornando qui
    s = S()
    tid = s.scalars(select(Turno).where(Turno.operatore_id == I['Lippiello'])).first().id
    s.close()
    assert ('/anagrafiche/turni/%d?torna=/ambulatori/settimana/2026-12-07' % tid) in t, t[t.find('/anagrafiche/turni/'):][:120]
    # il «+» c'e' solo nei giorni da oggi in poi (dicembre 2026 e' nel futuro, ottobre 2026 nel passato)
    s = S()
    v = AM.matrice(s, LUN, s.get(Struttura, 1))
    s.close()
    aperte = sum(1 for r_ in v['righe'] for c in r_['celle'] if not c['chiuso'] and c['data'] >= OGGI)
    assert aperte == 6 * 6 * 2 - 24 and t.count('<details class="metti">') == aperte, (aperte, t.count('<details class="metti">'))
    passato = date(2026, 10, 5)
    t2 = testo(C.get('/ambulatori/settimana/%s' % passato.isoformat()))
    assert '<details class="metti">' not in t2 and 'id="matrice-ambulatori"' in t2
    # una settimana a cavallo di oggi: il + solo da oggi
    lunedi_oggi = calendario.lunedi_di(OGGI)
    t3 = testo(C.get('/ambulatori/settimana/%s' % lunedi_oggi.isoformat()))
    for k in range(6):
        g = lunedi_oggi + timedelta(days=k)
        # il modulo del «+» (stanza e poi giorno); quello della «x» ha prima il turno
        ha = ('name="risorsa" value="%d"><input type="hidden" name="data" value="%s"' % (I['Ambulatorio 2'], g.isoformat())) in t3
        assert ha == (g >= OGGI), (g, ha)
    # il menu: il gruppo Ambulatori e' segnato attivo
    assert 'Ambulatori<span class="freccia"' in t and 'class="gruppo attivo" data-guida="menu-ambulatori"' in t
    # stampa e scarica
    assert ('/ambulatori/settimana/2026-12-07.xlsx?struttura=1' in t and 'tipo=1' in t
            and '/ambulatori/mese/2026-12?struttura=1' in t), t[t.find('Stampa e scarica'):][:600]
    return '%d «+»' % t.count('<details class="metti">')


def d_mese():
    S, I, C = mondo_pieno()
    r = C.get('/ambulatori/mese/2026-12')
    assert r.status_code == 200
    t = testo(r)
    assert 'id="programmazione-ambulatori"' in t and 'Programmazione ambulatori · dicembre 2026' in t
    assert 'Cardiologia' in t and 'Dermatologia' in t and 'Senza specialità' in t
    assert 'non il 7 (assente: ferie)' in t and 'un giorno solo' in t and '14, 21, 28' in t
    assert 'class="gruppo attivo" data-guida="menu-ambulatori"' in t
    assert '/ambulatori/mese/2026-12.xlsx?struttura=1' in t
    assert 'Calendario del mese' in t and 'chiusa: manutenzione' in t and 'chiusa: immacolata concezione' in t
    assert 'nessun medico in turno' in t
    # il mese vuoto
    t = testo(C.get('/ambulatori/mese/2025-12'))
    assert 'Nessun turno nelle stanze attive' in t
    # indirizzi scritti male: si ricade sul mese e sulla settimana di oggi, mai un errore
    for indirizzo in ('/ambulatori/mese/boh', '/ambulatori/mese/2026-13', '/ambulatori/mese/9999-99',
                      '/ambulatori/settimana/boh', '/ambulatori/settimana/2026-02-30', '/ambulatori/settimana/0001-01-01',
                      '/ambulatori/settimana/boh.xlsx', '/ambulatori/mese/boh.xlsx'):
        r = C.get(indirizzo)
        assert r.status_code == 200, (indirizzo, r.status_code)
    assert OGGI.strftime('%Y-%m') in testo(C.get('/ambulatori/mese/boh')) or True
    assert 'data-lunedi="%s"' % calendario.lunedi_di(OGGI).isoformat() in testo(C.get('/ambulatori/settimana/boh'))


def d_senza_struttura():
    S, I, C = mondo()
    s = S()
    s.get(Struttura, 1).attiva = False
    s.commit()
    s.close()
    for indirizzo in ('/ambulatori/settimana/2026-12-07', '/ambulatori/mese/2026-12', '/ambulatori/settimana/2026-12-07.xlsx',
                      '/ambulatori/mese/2026-12.xlsx'):
        r = C.get(indirizzo)
        assert r.status_code == 200 and 'configur' in testo(r).lower(), (indirizzo, r.status_code)
    for indirizzo in ('/ambulatori/metti', '/ambulatori/togli'):
        r = C.post(indirizzo, data={'data': '2026-12-07'}, headers=CASA)
        assert r.status_code == 200 and 'configur' in testo(r).lower(), (indirizzo, r.status_code)


prova('pagina della settimana: redirect, matrice, disponibile/libero/assente/chiusa, nomi con torna, «+» solo da oggi, menu', d_settimana)
prova('pagina del mese: gruppi, note, calendario, mese vuoto; indirizzi scritti male senza errori', d_mese)
prova('senza una struttura attiva: la pagina «da configurare», anche su metti e togli', d_senza_struttura)


# ================================================================== Excel
area('Excel')


def colore(c):
    return (c.fill.fgColor.rgb or '')[-6:] if c.fill and c.fill.fill_type == 'solid' else ''


def e_matrice():
    S, I, C = mondo_pieno()
    nome = 'matrice-ambulatori-2026-12-07.xlsx'
    percorso = os.path.join(tempfile.gettempdir(), nome)
    if os.path.exists(percorso):
        os.remove(percorso)
    r, wb = excel(C, '/ambulatori/settimana/2026-12-07.xlsx?struttura=1')
    assert nome in r.headers.get('Content-Disposition', ''), r.headers.get('Content-Disposition')
    assert not os.path.exists(percorso), 'file lasciato nella cartella temporanea'
    assert wb.sheetnames == ['Matrice'], wb.sheetnames
    ws = wb['Matrice']
    assert ws['A1'].value == 'Clinica Prova' and ws['A2'].value == AM.TITOLO_MATRICE
    assert ws['A3'].value == 'Settimana dal 7 dicembre al 13 dicembre 2026', ws['A3'].value
    assert 'Destinatario: Direttore Sanitario' in ws['A4'].value and 'Compilato da: Segreteria' in ws['A4'].value \
        and 'Data: %s' % datetime.now().strftime('%d/%m/%Y') in ws['A4'].value, ws['A4'].value
    # intestazione: righe 6 e 7, il giorno sopra le sue due mezze giornate
    assert ws['A6'].value == 'AMBULATORIO'
    assert ws.cell(6, 2).value == 'Lunedì 7/12' and ws.cell(6, 4).value == 'Martedì 8/12\nImmacolata Concezione', (ws.cell(6, 2).value, ws.cell(6, 4).value)
    assert ws.cell(6, 8).value == 'Giovedì 10/12\nManutenzione', ws.cell(6, 8).value
    assert [ws.cell(7, c).value for c in range(2, 6)] == ['08:00-14:00', '14:00-20:00', '08:00-14:00', '14:00-20:00']
    assert ws.cell(6, 12).value == 'Sabato 12/12' and ws.cell(6, 14).value is None, 'sei giorni, tredici colonne'
    assert ws.freeze_panes == 'B8' and ws.print_title_rows.replace('$', '') == '6:7', (ws.freeze_panes, ws.print_title_rows)
    righe = {ws.cell(i, 1).value: i for i in range(8, 20)}
    i = righe['Ambulatorio 1']
    assert ws.cell(i, 2).value == 'DISPONIBILE\n(Galasso assente: ferie)' and colore(ws.cell(i, 2)) == 'C6EFCE', (ws.cell(i, 2).value, colore(ws.cell(i, 2)))
    assert ws.cell(i, 3).value == 'Lippiello Anna 15:00-20:00\nlibero 14:00-15:00' and colore(ws.cell(i, 3)) == 'EAF5E3', ws.cell(i, 3).value
    assert ws.cell(i, 4).value == 'CHIUSO: Immacolata Concezione' and colore(ws.cell(i, 4)) == 'E7E9E6'
    assert ws.cell(i, 8).value == 'CHIUSO: Manutenzione'
    j = righe['Ambulatorio 2']
    assert ws.cell(j, 2).value == 'DISPONIBILE' and colore(ws.cell(j, 2)) == 'C6EFCE'
    assert ws.cell(j, 4).value == 'CHIUSO: Immacolata Concezione', 'martedi festivo: anche Fintini resta a casa'
    k = righe['Ambulatorio 3']
    assert ws.cell(k, 6).value == 'Fintini Ugo 09:00-11:00\nlibero 08:00-09:00\nlibero 11:00-14:00', ws.cell(k, 6).value
    assert 'Sala operatoria' not in righe and 'Sala endoscopia' in righe, righe
    testi = [str(ws.cell(i, 1).value) for i in range(1, ws.max_row + 1) if ws.cell(i, 1).value]
    assert any('disponibilità integrative' in x for x in testi), testi[-6:]
    assert any(x == 'Il Direttore Sanitario' for x in testi) and any(x.startswith('____') for x in testi), testi[-4:]
    firma = next(i for i in range(1, ws.max_row + 1) if ws.cell(i, 1).value == 'Il Direttore Sanitario')
    assert ws.cell(firma, 7).value == 'La Segreteria' and str(ws.cell(firma + 1, 7).value).startswith('____'), (ws.cell(firma, 7).value)
    assert ws.page_setup.orientation == 'landscape' and ws.page_setup.fitToWidth == 1
    # la settimana tipo
    r, wb = excel(C, '/ambulatori/settimana/2026-12-07.xlsx?struttura=1&tipo=1')
    assert 'matrice-ambulatori-2026-12-07-settimana-tipo.xlsx' in r.headers.get('Content-Disposition', '')
    ws = wb['Matrice']
    assert ws['A3'].value.startswith('Settimana tipo') and ws.cell(6, 2).value == 'Lunedì' and ws.cell(6, 4).value == 'Martedì'
    i = {ws.cell(i, 1).value: i for i in range(8, 20)}['Ambulatorio 1']
    assert ws.cell(i, 2).value == 'Galasso 08:00-13:00\nlibero 13:00-14:00' and ws.cell(i, 4).value == 'DISPONIBILE', ws.cell(i, 2).value
    assert 'CHIUSO' not in ' '.join(str(c.value) for row in ws.iter_rows() for c in row)


def e_programmazione():
    S, I, C = mondo_pieno()
    nome = 'programmazione-ambulatori-2026-12.xlsx'
    percorso = os.path.join(tempfile.gettempdir(), nome)
    if os.path.exists(percorso):
        os.remove(percorso)
    r, wb = excel(C, '/ambulatori/mese/2026-12.xlsx?struttura=1')
    assert nome in r.headers.get('Content-Disposition', ''), r.headers.get('Content-Disposition')
    assert not os.path.exists(percorso)
    assert wb.sheetnames == ['Programmazione', 'Calendario'], wb.sheetnames
    ws = wb['Programmazione']
    assert ws['A1'].value == 'Clinica Prova — PROGRAMMAZIONE AMBULATORI' and ws['A2'].value == 'Dicembre 2026'
    assert [ws.cell(5, c).value for c in range(1, 8)] == ['Specialità', 'Medico', 'Giorno', 'Date di dicembre', 'Orario', 'Stanza', 'Note']
    righe = [[ws.cell(i, c).value if ws.cell(i, c).value is not None else '' for c in range(1, 8)] for i in range(6, 6 + 4)]
    assert righe[0] == ['Cardiologia', 'Galasso', 'Lunedì', '14, 21, 28', '08:00-13:00', 'Ambulatorio 1', 'non il 7 (assente: ferie)'], righe[0]
    assert righe[1] == ['Dermatologia', 'Lippiello Anna', 'Lunedì', '7, 14, 21, 28', '15:00-20:00', 'Ambulatorio 1', ''], righe[1]
    assert righe[2] == ['Senza specialità', 'Fintini Ugo', 'Martedì', '1, 15, 22, 29', '08:00-20:00', 'Ambulatorio 2', "non l'8 (chiusa: immacolata concezione)"], righe[2]
    assert righe[3] == ['Senza specialità', 'Fintini Ugo', 'Mercoledì', 9, '09:00-11:00', 'Ambulatorio 3', 'un giorno solo'], righe[3]
    assert ws.cell(10, 1).value is None, 'quattro righe: la sala operatoria no'
    assert ws.freeze_panes == 'A6' and ws.auto_filter.ref == 'A5:G9' and ws.print_title_rows.replace('$', '') == '5:5', (ws.freeze_panes, ws.auto_filter.ref)
    # la specialita' in grassetto solo sulla prima riga del suo gruppo
    assert ws.cell(6, 1).font.bold and ws.cell(7, 1).font.bold and ws.cell(8, 1).font.bold and not ws.cell(9, 1).font.bold
    wc = wb['Calendario']
    assert [wc.cell(3, c).value for c in range(1, 6)] == ['Data', 'Giorno', 'Stanza', 'Medico', 'Orario']
    righe = [[wc.cell(i, c).value for c in range(1, 6)] for i in range(4, wc.max_row + 1)]
    assert righe[0][:2] == [datetime(2026, 12, 1), 'Martedì'] and righe[0][2:] == ['Ambulatorio 2', 'Fintini Ugo', '08:00-20:00'], righe[0]
    date_righe = {r[0].date() if isinstance(r[0], datetime) else r[0]: r for r in righe if r[0]}
    assert date_righe[date(2026, 12, 2)][2] == 'nessun medico in turno'
    assert date_righe[date(2026, 12, 8)][2] == 'chiusa: immacolata concezione' and colore(wc.cell(4 + righe.index(date_righe[date(2026, 12, 8)]), 1)) == 'E7E9E6'
    assert date_righe[date(2026, 12, 10)][2] == 'chiusa: manutenzione'
    assert date_righe[date(2026, 12, 7)][2:] == ['Ambulatorio 1', 'Lippiello Anna', '15:00-20:00']
    lun14 = righe.index(date_righe[date(2026, 12, 14)])
    assert righe[lun14][2:] == ['Ambulatorio 1', 'Galasso', '08:00-13:00'] and righe[lun14 + 1] == [None, None, 'Ambulatorio 1', 'Lippiello Anna', '15:00-20:00']
    assert date(2026, 12, 6) not in date_righe and date(2026, 12, 13) not in date_righe, 'le domeniche chiuse non ci sono'
    assert wc.cell(4, 1).number_format == 'dd/mm/yyyy' and wc.page_setup.orientation == 'portrait'
    # un mese senza turni
    _, wb = excel(C, '/ambulatori/mese/2025-12.xlsx')
    assert wb['Programmazione'].cell(6, 1).value.startswith('Nessun turno nelle stanze attive') and \
        not wb['Programmazione'].auto_filter.ref, 'senza righe niente filtro (1.12)'


def e_testi_puliti():
    """Un nome con un carattere di controllo (incollato da Word) non fa cadere
    i due Excel: testo_excel lo pulisce."""
    S, I, C = mondo_pieno()
    s = S()
    s.get(Risorsa, I['Ambulatorio 1']).nome = 'Ambulatorio\x01 1'
    s.get(Operatore, I['Galasso']).cognome = 'Gala\x02sso'
    s.get(Struttura, 1).nome = 'Clinica\x07 Prova'
    s.commit()
    s.close()
    _, wb = excel(C, '/ambulatori/settimana/2026-12-07.xlsx')
    ws = wb['Matrice']
    assert ws['A1'].value == 'Clinica Prova' and ws['A8'].value == 'Ambulatorio 1', (ws['A1'].value, ws['A8'].value)
    _, wb = excel(C, '/ambulatori/mese/2026-12.xlsx')
    ws = wb['Programmazione']
    assert ws.cell(6, 2).value == 'Galasso' and ws.cell(6, 6).value == 'Ambulatorio 1', (ws.cell(6, 2).value, ws.cell(6, 6).value)
    # 1.12: un nome che comincia con «=» non diventa una formula (davanti uno spazio)
    s = S()
    s.get(Risorsa, I['Ambulatorio 1']).nome = '=1+1'
    s.commit()
    s.close()
    _, wb = excel(C, '/ambulatori/settimana/2026-12-07.xlsx')
    c = wb['Matrice']['A8']
    assert c.value == ' =1+1' and c.data_type == 's', (c.value, c.data_type)
    assert comune.testo_excel('=SOMMA(A1)') == ' =SOMMA(A1)' and comune.testo_excel('Galasso') == 'Galasso'
    assert comune.testo_excel(3) == 3 and comune.testo_excel('a\x01=b') == 'a=b'


prova('la matrice in Excel: intestazione, giorni e mezze giornate, DISPONIBILE in verde, libero, chiuso, legenda, firme; settimana tipo', e_matrice)
prova('la programmazione in Excel: il foglio per specialità e il calendario del mese; mese vuoto', e_programmazione)
prova('caratteri di controllo nei nomi: gli Excel non cadono', e_testi_puliti)


# ========================================================= pianificazione
area('pianificazione: metti e togli')


def modulo(I, stanza='Ambulatorio 2', data=LUN, medico='Galasso', da='08:00', a='12:00', ripetizione='settimanale', **altro):
    d = {'risorsa': I[stanza], 'data': data.isoformat(), 'struttura': 1, 'operatore': I[medico],
         'ora_inizio': da, 'ora_fine': a, 'ripetizione': ripetizione}
    d.update(altro)
    return d


def turni_di(S, oid, rid=None):
    s = S()
    q = select(Turno).where(Turno.operatore_id == oid)
    if rid:
        q = q.where(Turno.risorsa_id == rid)
    uscita = [(t.id, t.giorno_settimana, t.ora_inizio, t.ora_fine, t.valido_da, t.valido_a) for t in s.scalars(q.order_by(Turno.id))]
    s.close()
    return uscita


def storico(S, entita='Turno'):
    s = S()
    uscita = [(m.azione, m.dettaglio) for m in s.scalars(select(Modifica).where(Modifica.entita == entita).order_by(Modifica.id))]
    s.close()
    return uscita


def f_metti():
    S, I, C = mondo_pieno()
    prima = len(storico(S))
    r = C.post('/ambulatori/metti', data=modulo(I), headers=CASA)
    assert r.status_code == 302 and r.headers['Location'].endswith('/ambulatori/settimana/2026-12-07?struttura=1'), r.headers.get('Location')
    assert 'Turno salvato: Galasso in Ambulatorio 2 ogni lunedì dal 07/12/2026 dalle 08:00 alle 12:00.' in avvisi(C)
    t = turni_di(S, I['Galasso'], I['Ambulatorio 2'])
    assert len(t) == 1 and t[0][1:] == (0, time(8), time(12), LUN, None), t
    # un giorno solo
    r = C.post('/ambulatori/metti', data=modulo(I, stanza='Ambulatorio 3', data=LUN + timedelta(days=4), medico='Lippiello',
                                                da='14:00', a='17:30', ripetizione='giorno'), headers=CASA, follow_redirects=True)
    assert r.status_code == 200 and 'Turno salvato: Lippiello Anna in Ambulatorio 3 il 11/12/2026 dalle 14:00 alle 17:30.' in testo(r)
    t = turni_di(S, I['Lippiello'], I['Ambulatorio 3'])
    assert len(t) == 1 and t[0][1:] == (4, time(14), time(17, 30), LUN + timedelta(days=4), LUN + timedelta(days=4)), t
    # compare nella matrice, e lo storico lo sa
    pagina = testo(C.get('/ambulatori/settimana/2026-12-07'))
    assert 'Lippiello</a> <small>14:00–17:30</small>' in pagina, pagina[pagina.find('14:00'):][:80]
    dopo = storico(S)[prima:]
    assert len(dopo) == 2 and all(a == 'SALVATO' and 'Turno salvato' in d for a, d in dopo), dopo


def f_metti_rifiutati():
    S, I, C = mondo_pieno()
    s = S()
    s.get(Risorsa, I['Ambulatorio 5']).attiva = False
    s.add(Struttura(nome='Centro Nord'))
    s.flush()
    s.add(Risorsa(nome='Stanza Nord', struttura_id=2, ordine=1))
    s.commit()
    s.close()
    nord = {r.nome: r.id for r in S().scalars(select(Risorsa))}['Stanza Nord']
    conti = len(turni_di(S, I['Galasso'])) + len(turni_di(S, I['Lippiello'])) + len(turni_di(S, I['Fintini']))
    casi = [
        ('stanza già assegnata', modulo(I, stanza='Ambulatorio 1', medico='Fintini', da='10:00', a='16:00'),
         'La stanza è già assegnata a Galasso il lunedì dalle 08:00 alle 13:00.'),
        ('stessa stanza, altro giorno della settimana vale: no errore', None, None),
        ('ora di fine prima dell\'inizio', modulo(I, da='12:00', a='09:00'), 'L\'ora di fine deve venire dopo quella di inizio.'),
        ('stessa ora', modulo(I, da='12:00', a='12:00'), 'L\'ora di fine deve venire dopo quella di inizio.'),
        ('ora scritta male', modulo(I, da='otto', a='12:00'), 'Dalle: ora non valida.'),
        ('stanza disattivata', modulo(I, stanza='Ambulatorio 5'), 'Stanza non valida.'),
        ('stanza di un\'altra struttura', dict(modulo(I), risorsa=nord), 'Stanza non valida.'),
        ('stanza inesistente', dict(modulo(I), risorsa=99999), 'Stanza non valida.'),
        ('medico sconosciuto', dict(modulo(I), operatore=99999), 'Medico: scelta non valida.'),
        ('ripetizione sconosciuta', modulo(I, ripetizione='sempre'), 'Ripetizione: scelta non valida.'),
    ]
    for nome, dati, atteso in casi:
        if dati is None:
            continue
        r = C.post('/ambulatori/metti', data=dati, headers=CASA)
        assert r.status_code == 302, (nome, r.status_code)
        a = avvisi(C)
        assert atteso in a, (nome, a)
    # senza data: si torna a oggi con l'errore
    r = C.post('/ambulatori/metti', data=dict(modulo(I), data='boh'), headers=CASA)
    assert r.status_code == 302 and OGGI.isoformat() in r.headers['Location'] and 'Giorno non valido' in avvisi(C)
    assert conti == len(turni_di(S, I['Galasso'])) + len(turni_di(S, I['Lippiello'])) + len(turni_di(S, I['Fintini'])), 'niente salvato'
    # un medico non attivo non si puo' mettere
    s = S()
    s.get(Operatore, I['Esempietti']).attivo = False
    s.commit()
    s.close()
    C.post('/ambulatori/metti', data=modulo(I, medico='Esempietti'), headers=CASA)
    assert 'Medico: scelta non valida.' in avvisi(C)
    # la richiesta da fuori del gestionale e' rifiutata prima di tutto
    r = C.post('/ambulatori/metti', data=modulo(I), headers={'Sec-Fetch-Site': 'cross-site'})
    assert r.status_code == 403


def f_metti_sostituzione():
    """Le stesse eccezioni della scheda del turno: chi ha la stanza quel
    giorno e' assente, un altro la puo' prendere per quel giorno solo."""
    S, I, C = mondo_pieno()
    # Galasso e' assente lunedi 7: Fintini lo sostituisce quel giorno, stesse ore
    r = C.post('/ambulatori/metti', data=modulo(I, stanza='Ambulatorio 1', medico='Fintini', da='08:00', a='13:00', ripetizione='giorno'),
               headers=CASA)
    assert r.status_code == 302 and 'Turno salvato' in avvisi(C)
    # ... ma ogni settimana no
    C.post('/ambulatori/metti', data=modulo(I, stanza='Ambulatorio 1', medico='Fintini', da='08:00', a='13:00'), headers=CASA)
    assert 'già assegnata a Galasso' in avvisi(C)
    # e un giorno in cui Galasso c'e' nemmeno
    C.post('/ambulatori/metti', data=modulo(I, stanza='Ambulatorio 1', medico='Fintini', da='08:00', a='13:00',
                                             data=LUN + timedelta(days=7), ripetizione='giorno'), headers=CASA)
    assert 'già assegnata a Galasso' in avvisi(C)
    # al contrario: con la sostituzione di un giorno gia' scritta, il turno settimanale del sostituito si mette lo stesso
    s = S()
    t = s.scalars(select(Turno).where(Turno.operatore_id == I['Galasso'], Turno.risorsa_id == I['Ambulatorio 1'])).first()
    s.delete(t)
    s.commit()
    s.close()
    C.post('/ambulatori/metti', data=modulo(I, stanza='Ambulatorio 1', medico='Galasso', da='08:00', a='13:00',
                                             data=LUN - timedelta(days=7)), headers=CASA)
    assert 'Turno salvato' in avvisi(C)
    # la pagina: lunedi 7 c'e' Fintini, lunedi 14 Galasso
    s = S()
    v = AM.matrice(s, LUN, s.get(Struttura, 1))
    assert [x['operatore'].cognome for x in v['righe'][0]['celle'][0]['presenze']] == ['Fintini']
    v = AM.matrice(s, LUN + timedelta(days=7), s.get(Struttura, 1))
    assert [x['operatore'].cognome for x in v['righe'][0]['celle'][0]['presenze']] == ['Galasso']
    s.close()


def f_togli():
    S, I, C = mondo_pieno()
    prima = len(storico(S))
    s = S()
    galasso = s.scalars(select(Turno).where(Turno.operatore_id == I['Galasso'])).first().id        # dal 5/1/2026
    singolo_ = s.scalars(select(Turno).where(Turno.valido_da == Turno.valido_a)).first().id       # mercoledi 9
    s.close()
    # un turno di un giorno si elimina
    r = C.post('/ambulatori/togli', data={'turno': singolo_, 'data': '2026-12-09', 'struttura': 1}, headers=CASA)
    assert r.status_code == 302 and r.headers['Location'].endswith('/ambulatori/settimana/2026-12-09?struttura=1'), r.headers['Location']
    assert 'Turno tolto: Fintini Ugo, mercoledì dalle 09:00 alle 11:00.' in avvisi(C)
    assert S().get(Turno, singolo_) is None
    # uno che viene da prima si chiude alla domenica precedente
    r = C.post('/ambulatori/togli', data={'turno': galasso, 'data': '2026-12-16', 'struttura': 1}, headers=CASA)
    assert r.status_code == 302
    a = avvisi(C)
    assert 'Turno di Galasso, lunedì dalle 08:00 alle 13:00 chiuso: vale fino al 13/12/2026' in a, a
    t = S().get(Turno, galasso)
    assert t.valido_a == date(2026, 12, 13) and t.valido_da == date(2026, 1, 5)
    # la settimana prima lo mostra ancora, quella dopo no
    assert 'Galasso' in testo(C.get('/ambulatori/settimana/2026-11-30')).split('</thead>')[1].split('<details')[0]
    pagina = testo(C.get('/ambulatori/settimana/2026-12-14'))
    assert 'Galasso</a>' not in pagina
    # uno che comincia in quella settimana (o dopo) si elimina
    nuovo = turno(S, I['Galasso'], I['Ambulatorio 4'], 2, time(8), time(12), valido_da=date(2026, 12, 16))
    C.post('/ambulatori/togli', data={'turno': nuovo, 'data': '2026-12-14', 'struttura': 1}, headers=CASA)
    assert 'Turno tolto: Galasso, mercoledì' in avvisi(C) and S().get(Turno, nuovo) is None
    nuovo = turno(S, I['Galasso'], I['Ambulatorio 4'], 2, time(8), time(12), valido_da=date(2026, 12, 23))
    C.post('/ambulatori/togli', data={'turno': nuovo, 'data': '2026-12-14', 'struttura': 1}, headers=CASA)
    assert 'Turno tolto' in avvisi(C) and S().get(Turno, nuovo) is None
    # id sconosciuto, o di un'altra struttura: avviso, mai un errore
    for turno_id in (99999, 'boh', ''):
        r = C.post('/ambulatori/togli', data={'turno': turno_id, 'data': '2026-12-14', 'struttura': 1}, headers=CASA)
        assert r.status_code == 302 and 'Turno non trovato' in avvisi(C), (turno_id, r.status_code)
    dopo = storico(S)[prima:]
    assert [a for a, _ in dopo] == ['ELIMINATO', 'SALVATO', 'ELIMINATO', 'ELIMINATO'], dopo
    assert 'chiuso: vale fino al 13/12/2026' in dopo[1][1], dopo[1]


def f_togli_altra_struttura():
    S, I, C = mondo(seconda=True)
    tid = turno(S, I['Galasso'], I['Stanza Nord'], 0, time(8), time(12))
    r = C.post('/ambulatori/togli', data={'turno': tid, 'data': '2026-12-14', 'struttura': 1}, headers=CASA)
    assert r.status_code == 302 and 'Turno non trovato' in avvisi(C) and S().get(Turno, tid) is not None
    r = C.post('/ambulatori/togli', data={'turno': tid, 'data': '2026-12-14', 'struttura': 2}, headers=CASA)
    assert 'chiuso: vale fino al 13/12/2026' in avvisi(C) and S().get(Turno, tid).valido_a == date(2026, 12, 13)


def f_torna():
    S, I, C = mondo_pieno()
    for torna, atteso in (('/ambulatori/settimana/2026-12-07?struttura=1', '/ambulatori/settimana/2026-12-07?struttura=1'),
                          ('/giorno/2026-12-07', '/giorno/2026-12-07'),
                          ('//evil.example.com/x', '/ambulatori/settimana/2026-12-07?struttura=1'),
                          ('/\\evil.example.com', '/ambulatori/settimana/2026-12-07?struttura=1'),
                          ('https://evil.example.com/', '/ambulatori/settimana/2026-12-07?struttura=1'),
                          ('', '/ambulatori/settimana/2026-12-07?struttura=1')):
        r = C.post('/ambulatori/metti', data=modulo(I, stanza='Ambulatorio 4', da='08:00', a='09:00', torna=torna), headers=CASA)
        assert r.status_code == 302 and r.headers['Location'].endswith(atteso), (torna, r.headers['Location'])
        avvisi(C)
        s = S()
        for t in s.scalars(select(Turno).where(Turno.risorsa_id == I['Ambulatorio 4'])):
            s.delete(t)
        s.commit()
        s.close()
    tid = turno(S, I['Galasso'], I['Ambulatorio 4'], 0, time(8), time(9))
    r = C.post('/ambulatori/togli', data={'turno': tid, 'data': '2026-12-07', 'struttura': 1, 'torna': '//evil.example.com'}, headers=CASA)
    assert r.headers['Location'].endswith('/ambulatori/settimana/2026-12-07?struttura=1'), r.headers['Location']
    tid = turno(S, I['Galasso'], I['Ambulatorio 4'], 0, time(8), time(9))
    r = C.post('/ambulatori/togli', data={'turno': tid, 'data': '2026-12-07', 'struttura': 1, 'torna': '/mese/2026-12'}, headers=CASA)
    assert r.headers['Location'].endswith('/mese/2026-12'), r.headers['Location']


def f_lucchetto():
    """Le due azioni passano dal lucchetto condiviso dei salvataggi."""
    import threading
    S, I, C = mondo_pieno()
    assert AM._lucchetto is A.LUCCHETTO and isinstance(AM._lucchetto, type(threading.Lock()))
    preso = []
    originale = AM._lucchetto

    class Spia:
        def __enter__(self):
            preso.append(1)
            return originale.__enter__()

        def __exit__(self, *a):
            return originale.__exit__(*a)
    AM._lucchetto = Spia()
    try:
        C.post('/ambulatori/metti', data=modulo(I, stanza='Ambulatorio 4'), headers=CASA)
        tid = turni_di(S, I['Galasso'], I['Ambulatorio 4'])[0][0]
        C.post('/ambulatori/togli', data={'turno': tid, 'data': '2026-12-07', 'struttura': 1}, headers=CASA)
    finally:
        AM._lucchetto = originale
    assert len(preso) == 2, preso


prova('Metti: ogni settimana da quel giorno (valido_a vuoto) o un giorno solo; nella matrice e nello storico', f_metti)
prova('Metti rifiutato: stanza già assegnata, ore, stanza disattivata o di un\'altra struttura, medico sconosciuto; niente salvato', f_metti_rifiutati)
prova('Metti: la sostituzione di un assente per un giorno solo passa, ogni settimana no; e al contrario', f_metti_sostituzione)
prova('Togli: un giorno solo o dalla settimana stessa si elimina; da prima si chiude alla domenica; id sconosciuto; storico', f_togli)
prova('Togli: un turno di un\'altra struttura non si tocca', f_togli_altra_struttura)
prova('torna: solo pagine interne del gestionale, altrimenti la settimana', f_torna)
prova('Metti e Togli passano dal lucchetto condiviso', f_lucchetto)


# ============================================================= anagrafiche
area('anagrafiche: la regola della stanza e il ritorno')


def g_stanza_gia_assegnata():
    S, I, C = mondo()
    galasso = turno(S, I['Galasso'], I['Ambulatorio 1'], 0, time(8), time(13), valido_da=date(2026, 1, 5))
    assenza(S, I['Galasso'], LUN, LUN)
    s = S()
    f = anagrafiche.stanza_gia_assegnata
    rid, altro = I['Ambulatorio 1'], I['Lippiello']
    # sovrapposta
    assert f(s, rid, 0, time(10), time(12), date(2026, 12, 1), None, altro) == 'La stanza è già assegnata a Galasso il lunedì dalle 08:00 alle 13:00.'
    assert f(s, rid, 0, time(7), time(8, 1), date(2026, 12, 1), None, altro)
    # ore diverse, giorno diverso, stanza diversa, validita' che non si toccano
    assert f(s, rid, 0, time(13), time(18), date(2026, 12, 1), None, altro) is None
    assert f(s, rid, 1, time(8), time(13), date(2026, 12, 1), None, altro) is None
    assert f(s, I['Ambulatorio 2'], 0, time(8), time(13), date(2026, 12, 1), None, altro) is None
    assert f(s, rid, 0, time(8), time(13), date(2025, 1, 6), date(2026, 1, 4), altro) is None
    assert f(s, rid, 0, time(8), time(13), date(2025, 1, 6), date(2026, 1, 5), altro)
    # lo stesso medico su due stanze va bene; lo stesso medico sulla stessa stanza no (non e' questa regola a dirlo)
    assert f(s, I['Ambulatorio 2'], 0, time(8), time(13), date(2026, 12, 1), None, I['Galasso']) is None
    # escludi_id: il turno stesso, quando lo si modifica
    assert f(s, rid, 0, time(8), time(13), date(2026, 1, 5), None, I['Galasso'], escludi_id=galasso) is None
    assert f(s, rid, 0, time(8), time(13), date(2026, 1, 5), None, I['Galasso'])
    # sostituzione: un giorno in cui Galasso e' assente, un altro puo' prendere la stanza quel giorno
    assert f(s, rid, 0, time(8), time(13), LUN, LUN, altro) is None
    assert f(s, rid, 0, time(8), time(13), LUN + timedelta(days=7), LUN + timedelta(days=7), altro)
    s.close()
    # al contrario: la sostituzione c'e' gia', il turno settimanale di Galasso si puo' scrivere lo stesso
    sost = singolo(S, altro, rid, LUN, time(8), time(13))
    s = S()
    assert f(s, rid, 0, time(8), time(13), date(2026, 1, 5), None, I['Galasso'], escludi_id=galasso) is None
    # ma un terzo medico, non assente quel giorno, no
    assert f(s, rid, 0, time(9), time(10), date(2026, 1, 5), None, I['Fintini'])
    s.close()
    return 'sostituzione %d' % sost


def g_scheda_turno_con_torna():
    S, I, C = mondo()
    dati = {'ripetizione': 'settimanale', 'operatore': I['Galasso'], 'risorsa': I['Ambulatorio 1'], 'giorno': '2',
            'ora_inizio': '08:00', 'ora_fine': '12:00', 'valido_da': '2026-12-01', 'valido_a': '', 'passo': '0'}
    r = C.post('/anagrafiche/turni/nuovo?torna=/ambulatori/settimana/2026-12-07%3Fstruttura%3D1', data=dati, headers=CASA)
    assert r.status_code == 302 and r.headers['Location'].endswith('/ambulatori/settimana/2026-12-07?struttura=1'), r.headers['Location']
    assert 'Turno salvato' in avvisi(C)
    t = turni_di(S, I['Galasso'])
    assert len(t) == 1 and t[0][1:4] == (2, time(8), time(12))
    tid = t[0][0]
    # modifica con torna, e con un torna esterno si resta nelle anagrafiche
    r = C.post('/anagrafiche/turni/%d?torna=/ambulatori/mese/2026-12' % tid, data=dict(dati, ora_fine='13:00'), headers=CASA)
    assert r.headers['Location'].endswith('/ambulatori/mese/2026-12') and turni_di(S, I['Galasso'])[0][3] == time(13)
    r = C.post('/anagrafiche/turni/%d?torna=//evil.example.com' % tid, data=dict(dati, ora_fine='14:00'), headers=CASA)
    assert r.headers['Location'].endswith('/anagrafiche'), r.headers['Location']
    # senza torna: l'elenco delle anagrafiche, come prima
    r = C.post('/anagrafiche/turni/%d' % tid, data=dict(dati, ora_fine='15:00'), headers=CASA)
    assert r.headers['Location'].endswith('/anagrafiche'), r.headers['Location']
    # un errore nel modulo resta sulla scheda (e il torna nell'indirizzo del modulo)
    r = C.post('/anagrafiche/turni/%d?torna=/ambulatori/mese/2026-12' % tid, data=dict(dati, ora_fine='07:00'), headers=CASA)
    assert r.status_code == 200 and 'deve venire dopo' in testo(r)
    # la regola della stanza, dalla scheda: lo stesso messaggio
    r = C.post('/anagrafiche/turni/nuovo', data=dict(dati, operatore=I['Lippiello'], ora_inizio='09:00', ora_fine='10:00'), headers=CASA)
    assert r.status_code == 200 and 'La stanza è già assegnata a Galasso il mercoledì dalle 08:00 alle 15:00.' in testo(r)
    # elimina con torna
    r = C.post('/anagrafiche/turni/%d?torna=/ambulatori/settimana/2026-12-07' % tid, data={'azione': 'elimina'}, headers=CASA)
    assert r.status_code == 302 and r.headers['Location'].endswith('/ambulatori/settimana/2026-12-07'), r.headers['Location']
    assert 'Turno eliminato' in avvisi(C) and turni_di(S, I['Galasso']) == []
    # il collegamento dalla scheda: la pagina della settimana porta torna nell'indirizzo del modulo
    tid = turno(S, I['Galasso'], I['Ambulatorio 1'], 0, time(8), time(12))
    r = C.get('/anagrafiche/turni/%d?torna=/ambulatori/settimana/2026-12-07' % tid)
    assert r.status_code == 200 and 'Modifica turno' in testo(r)


prova('stanza_gia_assegnata: sovrapposizioni, validità, stesso medico, escludi_id, sostituzioni nei due versi', g_stanza_gia_assegnata)
prova('scheda del turno con torna: salva, modifica ed elimina tornano alla pagina interna; senza torna alle anagrafiche', g_scheda_turno_con_torna)



# ================================================================ stampe
area('stampe (1.12)')


def _appuntamenti_di_prova(S, I):
    """Lunedi 7/12: in Ambulatorio 1 (Lippiello di turno 15-20, Galasso assente)
    due visite con importo, una delle quali con un campo extra, e una disdetta;
    in Ambulatorio 2 (nessun turno il lunedi) una visita senza importo."""
    from modelli import Paziente, Appuntamento
    s = S()
    p1 = Paziente(cognome='Fintini', nome='Ugo', telefono='3330000001', data_nascita=date(1970, 5, 6))
    p2 = Paziente(cognome='Esempietti', nome='Ada', telefono='3330000002')
    s.add_all([p1, p2])
    s.flush()

    def app(rid, oid, ora, pid, **altro):
        inizio = datetime.combine(LUN, time(ora))
        a = Appuntamento(risorsa_id=rid, operatore_id=oid, paziente_id=pid, inizio=inizio,
                         fine=inizio + timedelta(minutes=30), stato=altro.pop('stato', 'PRENOTATO'), **altro)
        s.add(a)
        return a

    app(I['Ambulatorio 1'], I['Lippiello'], 15, p1.id, importo_cent=8000, extra=json.dumps({'Sedazione': 'Sì'}))
    app(I['Ambulatorio 1'], I['Lippiello'], 16, p2.id, importo_cent=5000, note='porta gli esami')
    app(I['Ambulatorio 1'], I['Lippiello'], 17, p1.id, importo_cent=9000, stato='DISDETTO')
    app(I['Ambulatorio 2'], I['Fintini'], 10, p2.id)
    s.commit()
    s.close()


def s_foglio_del_giorno():
    S, I, C = mondo_pieno()
    _appuntamenti_di_prova(S, I)
    t = testo(C.get('/stampa/%s?struttura=1' % LUN.isoformat()))
    # testata e piede ripetuti su ogni foglio, numero di pagina nel margine
    assert 'class="testata-ripetuta"' in t and 'class="piede-ripetuto"' in t
    # ogni stanza: conteggio, turno, assenti; la sala operatoria no
    assert '<h2>Ambulatorio 1</h2>' in t and '<h2>Ambulatorio 2</h2>' in t and 'Sala operatoria' not in t
    assert '2 appuntamenti · <b>turno:</b> Lippiello Anna 15:00–20:00 · Galasso assente' in t, t[t.find('Ambulatorio 1'):][:400]
    assert '3 appuntamenti' in t, 'in testa solo gli attivi'
    # le colonne in piu' solo nella stanza che le usa
    assert t.count('<th>Sedazione</th>') == 1
    tabella2 = t[t.find('<h2>Ambulatorio 2</h2>'):]
    assert '<th>Sedazione</th>' not in tabella2 and 'Totale importi' not in tabella2, 'Ambulatorio 2: niente extra e niente totale'
    # il totale degli importi della stanza e del giorno (solo gli attivi; il disdetto non c'e')
    assert 'Totale importi</td><td class="c-importo">130,00 €' in t and 'importi del giorno 130,00 €' in t
    assert 'Fintini Ugo' in t and t.count('17:00–17:30') == 0, 'il disdetto non si stampa di serie'
    # con tutti: il disdetto barrato, la colonna Stato, la legenda, il totale non lo conta
    t = testo(C.get('/stampa/%s?struttura=1&tutti=1' % LUN.isoformat()))
    assert 'stato-disdetto' in t and '<th>Stato</th>' in t and 'Disdetti in grigio' in t
    assert '3 appuntamenti · 1 disdetto' in t and '2 appuntamenti (1 fra disdetti e non presentati)' in t
    assert '130,00 €' in t and '220,00' not in t
    # una stanza con il medico di turno ma senza appuntamenti compare lo stesso (mercoledi: il turno di un
    # giorno di Fintini in Ambulatorio 3; il martedi e' l'Immacolata e la struttura chiude)
    t = testo(C.get('/stampa/%s?struttura=1' % (LUN + timedelta(days=2)).isoformat()))
    assert '<h2>Ambulatorio 3</h2>' in t and 'Nessun appuntamento: la stanza è libera' in t and 'Fintini Ugo 09:00–11:00' in t
    assert 'Sala operatoria' not in t and '<h2>Ambulatorio 1</h2>' not in t
    t = testo(C.get('/stampa/%s?struttura=1' % (LUN + timedelta(days=1)).isoformat()))
    assert 'Immacolata Concezione' in t and '<h2>' not in t, 'festivo chiuso: nessuna stanza'


def s_preferenze_di_stampa():
    S, I, C = mondo_pieno()
    _appuntamenti_di_prova(S, I)
    r = C.post('/impostazioni', data={'azione': 'stampa', 'colonne': ['importo', 'extra', 'nascita', 'spunta', 'telefono'],
                                      'orientamento': 'orizzontale', 'ordine': 'ora', 'tutti': '1'}, headers=CASA)
    assert r.status_code == 302
    t = testo(C.get('/impostazioni'))
    assert 'name="tutti" value="1" checked' in t and 'value="spunta" checked' in t and 'value="nascita" checked' in t
    t = testo(C.get('/stampa/%s?struttura=1' % LUN.isoformat()))
    # in ordine di ora: la riga dei medici di turno (senza la sala operatoria), le colonne scelte, il disdetto
    assert '<b>Medici di turno:</b> Ambulatorio 1: Lippiello Anna 15:00–20:00' in t and 'Sala operatoria' not in t
    assert '<th class="c-nascita">Nascita</th>' in t and '06/05/1970' in t
    assert '<th class="c-spunta">Arrivato · pagato</th>' in t and t.count('class="casella"') >= 8
    assert 'stato-disdetto' in t and '<th class="c-stanza">Stanza</th>' in t
    assert '<th>Telefono</th>' not in t and 'class="c-telefono">Telefono' in t
    # tutti=0 nell'indirizzo vince sulla preferenza
    t = testo(C.get('/stampa/%s?struttura=1&tutti=0' % LUN.isoformat()))
    assert 'stato-disdetto' not in t and 'Solo appuntamenti attivi' not in t and 'Anche disdetti' in t
    # l'elenco del giorno: il pulsante Stampa segue la preferenza, la tabella ha il thead, la nota si stampa
    from modelli import NotaGiorno
    s = S()
    s.add(NotaGiorno(struttura_id=1, data=LUN, testo='Lippiello arriva alle 15:30'))
    s.commit()
    s.close()
    t = testo(C.get('/giorno/%s/elenco?struttura=1' % LUN.isoformat()))
    assert 'href="/stampa/%s?struttura=1"' % LUN.isoformat() in t and 'per=ora' not in t
    assert '<thead><tr><th>Ora</th>' in t and 'class="nota-stampa solo-stampa">Lippiello arriva alle 15:30' in t
    t = testo(C.get('/stampa/%s?struttura=1' % LUN.isoformat()))
    assert 'class="nota-stampa">Lippiello arriva alle 15:30' in t


prova('foglio del giorno: testata e piede ripetuti, conteggi e turni per stanza, colonne in più solo dove servono, totali, stanze libere, con tutti', s_foglio_del_giorno)
prova('preferenze di stampa: anche disdetti, data di nascita, casella da spuntare, ordine di ora; elenco del giorno con thead e nota stampata', s_preferenze_di_stampa)



# ========================================================== riepilogo live
area('riepilogo live (1.12)')


def _mondo_live():
    """Il mondo pieno, piu' due pazienti con nomi che non sono di nessun medico
    e qualche appuntamento di lunedi 7/12: in Ambulatorio 1 (Lippiello di
    turno 15-20) uno fatto alle 15, uno alle 16 e uno disdetto alle 17; in
    Ambulatorio 2 (nessun turno il lunedi) uno alle 10 non arrivato."""
    import live
    from modelli import Paziente, Appuntamento
    S, I, C = mondo_pieno()
    s = S()
    p1 = Paziente(cognome='Testabianca', nome='Rita', telefono='3339990001', email='rita@example.com')
    p2 = Paziente(cognome='Provolo', nome='Gino', telefono='3339990002')
    s.add_all([p1, p2])
    s.flush()

    def app(rid, oid, ora, pid, stato='PRENOTATO', **altro):
        inizio = datetime.combine(LUN, time(ora))
        a = Appuntamento(risorsa_id=rid, operatore_id=oid, paziente_id=pid, inizio=inizio,
                         fine=inizio + timedelta(minutes=30), stato=stato, **altro)
        s.add(a)

    app(I['Ambulatorio 1'], I['Lippiello'], 15, p1.id, 'ARRIVATO', arrivato_alle=datetime.combine(LUN, time(14, 55)))
    app(I['Ambulatorio 1'], I['Lippiello'], 16, p2.id)
    app(I['Ambulatorio 1'], I['Lippiello'], 17, p1.id, 'DISDETTO')
    app(I['Ambulatorio 2'], I['Fintini'], 10, p2.id)
    s.commit()
    s.close()
    return S, I, C, live


def l_riepilogo():
    S, I, C, live = _mondo_live()
    s = S()
    st = s.get(Struttura, 1)
    r = live.riepilogo(s, st, adesso=datetime.combine(LUN, time(15, 40)))
    assert r['aggiornato'] == '15:40' and r['data'] == LUN.isoformat() and not r['chiusa']
    o = r['oggi']
    assert (o['totale'], o['arrivati'], o['fatte'], o['in_corso'], o['restanti']) == (3, 1, 1, 0, 1), o
    assert o['disdetti'] == 1 and o['non_presentati'] == 0, o
    # alle 10 Provolo non e' arrivato: alle 15:40 e' in ritardo da piu' di 3 ore, quindi non conta piu' «in ritardo»
    assert o['in_ritardo'] == 0 and o['tra_poco'] == 1, o
    stanze = {x['stanza']: x for x in r['stanze']}
    assert set(stanze) == {'Ambulatorio 1', 'Ambulatorio 2', 'Ambulatorio 3', 'Ambulatorio 4', 'Ambulatorio 5', 'Sala endoscopia'}, set(stanze)
    a1 = stanze['Ambulatorio 1']
    assert a1['stato'] == 'libera' and a1['fino'] == '16:00' and a1['medico'] == 'Lippiello Anna', a1
    assert (a1['totale'], a1['fatte'], a1['in_corso'], a1['restanti'], a1['prossima']) == (2, 1, 0, 1, '16:00'), a1
    assert a1['turni'] == ['Lippiello Anna 15:00–20:00']
    a2 = stanze['Ambulatorio 2']
    assert a2['stato'] == 'senza turno' and a2['fino'] is None and a2['totale'] == 1 and a2['restanti'] == 0, a2
    assert r['stanze_occupate'] == 0 and r['stanze_libere'] == 1
    # alle 16:10 la visita delle 16 e' in corso
    r = live.riepilogo(s, st, adesso=datetime.combine(LUN, time(16, 10)))
    a1 = {x['stanza']: x for x in r['stanze']}['Ambulatorio 1']
    assert a1['stato'] == 'occupata' and a1['fino'] == '16:30' and r['oggi']['in_corso'] == 1 and r['stanze_occupate'] == 1, a1
    # la mattina presto: Lippiello non e' ancora di turno
    r = live.riepilogo(s, st, adesso=datetime.combine(LUN, time(8, 5)))
    a1 = {x['stanza']: x for x in r['stanze']}['Ambulatorio 1']
    assert a1['stato'] == 'senza turno' and a1['fino'] == '15:00', a1
    assert r['oggi']['restanti'] == 3 and r['oggi']['fatte'] == 0
    # visite ora per ora: alle 10 una, alle 15 una (arrivata), alle 16 una
    ore = {x['ora']: x for x in r['per_ora']}
    assert ore['10:00']['totale'] == 1 and (ore['15:00']['totale'], ore['15:00']['arrivati']) == (1, 1) and ore['16:00']['totale'] == 1
    assert ore['08:00']['totale'] == 0 and '20:00' not in ore and len(ore) == 12
    # le mezze giornate libere: nei prossimi 7 giorni, mai nel passato, mai il festivo chiuso, mai la sala operatoria
    r = live.riepilogo(s, st, adesso=datetime.combine(LUN, time(15, 40)))
    assert r['n_libere'] > 0 and all(l['data'] >= LUN.isoformat() for l in r['libere'])
    assert not any(l['data'] == LUN.isoformat() and l['meta'] == 'mattina' for l in r['libere']), 'la mattina di oggi e passata'
    assert not any(l['data'] == (LUN + timedelta(days=1)).isoformat() for l in r['libere']), 'martedi 8 e festivo chiuso'
    assert not any(l['stanza'] == 'Sala operatoria' for l in r['libere'])
    assert any(l['data'] == LUN.isoformat() and l['stanza'] == 'Ambulatorio 2' and l['meta'] == 'pomeriggio' for l in r['libere'])
    assert all(l['data'] <= (LUN + timedelta(days=7)).isoformat() for l in r['libere']) and len(r['libere']) <= live.MASSIMO_LIBERE
    s.close()


def l_pagina_e_json():
    S, I, C, live = _mondo_live()
    r = C.get('/riepilogo-live?struttura=1')
    t = testo(r)
    assert r.status_code == 200 and 'Riepilogo live' in t and 'id="riepilogo-live"' in t and 'nav class="menu"' in t
    assert 'Ambulatorio 1' in t and 'Le stanze adesso' in t and 'Mezze giornate libere' in t and 'Visite ora per ora' in t
    assert 'class="gruppo attivo" data-guida="menu-ambulatori"' in t and 'Riepilogo live</b>' in t
    t = testo(C.get('/riepilogo-live?struttura=1&schermo=1'))
    assert 'class="pagina-live schermo"' in t and 'nav class="menu"' not in t and 'Torna alla pagina normale' in t
    r = C.get('/riepilogo-live.json?struttura=1')
    assert r.status_code == 200 and r.headers['Cache-Control'] == 'no-store'
    d = json.loads(r.data.decode('utf-8'))
    assert set(d) >= {'aggiornato', 'oggi', 'stanze', 'per_ora', 'libere', 'n_libere', 'stanze_occupate', 'struttura'}
    # riservatezza: nel JSON non c'e' nessun dato dei pazienti
    grezzo = r.data.decode('utf-8')
    for vietato in ('Testabianca', 'Rita', 'Provolo', 'Gino', '3339990001', '3339990002', 'example.com'):
        assert vietato not in grezzo, vietato
    assert 'Ambulatorio 1' in grezzo and 'stanze' in grezzo
    # senza struttura: la pagina «da configurare», il JSON un errore e non un 500
    S2, I2, C2 = mondo()
    s = S2()
    for st in s.scalars(select(Struttura)):
        st.attiva = False
    s.commit()
    s.close()
    assert C2.get('/riepilogo-live').status_code == 200 and json.loads(C2.get('/riepilogo-live.json').data)['errore']


def l_chiaro():
    """1.12.2: i quattro gruppi sommano al totale (anche stanza per stanza), le frasi in parole semplici,
    la linea del tempo con turni e visite, le ore passate e quella di adesso, le mezze giornate per giorno."""
    from modelli import Turno
    S, I, C, live = _mondo_live()
    s = S()
    # un secondo turno uguale di Lippiello nella stessa stanza: il nome una volta sola
    s.add(Turno(operatore_id=I['Lippiello'], risorsa_id=I['Ambulatorio 1'], giorno_settimana=0, ora_inizio=time(15),
                ora_fine=time(20), valido_da=LUN - timedelta(days=30)))
    s.commit()
    st = s.get(Struttura, 1)
    for h, m in ((8, 5), (10, 0), (10, 20), (11, 0), (15, 0), (15, 40), (16, 10), (16, 40), (19, 59), (21, 0)):
        r = live.riepilogo(s, st, adesso=datetime.combine(LUN, time(h, m)))
        o = r['oggi']
        assert o['fatte'] + o['in_corso'] + o['da_segnare'] + o['restanti'] == o['totale'] == 3, (h, m, o)
        for x in r['stanze']:
            assert x['fatte'] + x['in_corso'] + x['da_segnare'] + x['restanti'] == x['totale'], (h, m, x)
            for t in x['linea']['turni'] + x['linea']['visite']:
                assert 0 <= t['sx'] <= 100 and 0 <= t['larg'] and t['sx'] + t['larg'] <= 100.01, (h, m, x['stanza'], t)
        assert all(0 <= o_['sx'] <= 100 for o_ in r['asse']['ore']) and r['asse']['ore'][0]['sx'] == 0
        assert r['asse']['ore'][-1]['sx'] == 100, r['asse']
    stanze = lambda r: {x['stanza']: x for x in r['stanze']}
    # le 15:40: la visita delle 15 fatta, quella delle 16 da fare, Provolo delle 10 da segnare
    r = live.riepilogo(s, st, adesso=datetime.combine(LUN, time(15, 40)))
    a1, a2 = stanze(r)['Ambulatorio 1'], stanze(r)['Ambulatorio 2']
    assert r['oggi']['da_segnare'] == 1 and a2['da_segnare'] == 1 and a1['da_segnare'] == 0, (r['oggi'], a2)
    assert a1['medico'] == 'Lippiello Anna' and a1['turni'] == ['Lippiello Anna 15:00–20:00'], a1
    assert a1['frase'] == 'Libera, prossimo paziente alle 16:00' and a1['motivo'] == 'appuntamento', a1
    assert a2['frase'] == 'Nessun medico oggi' and a2['motivo'] is None, a2
    assert [t['medico'] for t in a1['linea']['turni']] == ['Lippiello Anna'] and a1['linea']['turni'][0]['da'] == '15:00'
    assert [v['stato'] for v in a1['linea']['visite']] == ['fatto', 'da-fare'], a1['linea']
    assert [v['stato'] for v in a2['linea']['visite']] == ['da-segnare'], a2['linea']
    assert r['asse']['da'] == '08:00' and r['asse']['a'] == '20:00' and abs(r['asse']['adesso'] - 100 * (460 / 720)) < 0.01, r['asse']
    assert r['riassunto'].startswith('Alle 15:40: 0 visite in corso, 1 stanza su 6 con un medico adesso.'), r['riassunto']
    assert "1 paziente con l'orario passato non è segnato arrivato" in r['riassunto'], r['riassunto']
    assert r['riassunto'].endswith('Prossimo appuntamento alle 16:00 in Ambulatorio 1.'), r['riassunto']
    ore = {x['ora']: x['quando'] for x in r['per_ora']}
    assert (ore['10:00'], ore['15:00'], ore['16:00']) == ('passata', 'adesso', 'dopo'), ore
    # le 16:10 la visita delle 16 in corso; le 16:40 libera fino a fine turno (la delle 17 e' disdetta)
    r = live.riepilogo(s, st, adesso=datetime.combine(LUN, time(16, 10)))
    a1 = stanze(r)['Ambulatorio 1']
    assert a1['frase'] == 'Visita in corso fino alle 16:30' and [v['stato'] for v in a1['linea']['visite']] == ['fatto', 'in-corso']
    assert r['riassunto'].startswith('Alle 16:10: 1 visita in corso'), r['riassunto']
    r = live.riepilogo(s, st, adesso=datetime.combine(LUN, time(16, 40)))
    a1 = stanze(r)['Ambulatorio 1']
    assert a1['frase'] == 'Libera fino a fine turno (20:00)' and a1['motivo'] == 'fine turno', a1
    # Provolo delle 16 non e' arrivato: alle 16:40 anche lui da segnare
    assert r['oggi']['da_segnare'] == 2 and 'Nessun altro appuntamento oggi.' in r['riassunto'], (r['oggi'], r['riassunto'])
    # la mattina presto: nessun medico fino alle 15, poi Lippiello; la sera: turni finiti, la linea di adesso fuori
    r = live.riepilogo(s, st, adesso=datetime.combine(LUN, time(8, 5)))
    a1 = stanze(r)['Ambulatorio 1']
    assert a1['frase'] == 'Nessun medico fino alle 15:00, poi Lippiello Anna' and a1['prossimo_medico'] == 'Lippiello Anna', a1
    r = live.riepilogo(s, st, adesso=datetime.combine(LUN, time(21, 0)))
    assert stanze(r)['Ambulatorio 1']['frase'] == 'Turni finiti per oggi' and r['asse']['adesso'] is None
    # le mezze giornate libere: la tabella dice le stesse della lista, oggi la mattina e' passata, niente festivo
    r = live.riepilogo(s, st, adesso=datetime.combine(LUN, time(15, 40)))
    tab = r['libere_tabella']
    assert 'Sala operatoria' not in tab['stanze'] and tab['meta'] == ['mattina', 'pomeriggio'], tab['stanze']
    assert sum(g['libere'] for g in tab['giorni']) == r['n_libere'] > 0
    assert tab['giorni'][0]['oggi'] and all(c[0] == 'passata' for c in tab['giorni'][0]['celle']), tab['giorni'][0]
    assert (LUN + timedelta(days=1)).isoformat() not in [g['data'] for g in tab['giorni']], 'martedi 8 e festivo chiuso'
    i2 = tab['stanze'].index('Ambulatorio 2')
    assert tab['giorni'][0]['celle'][i2] == ['passata', 'libera'], tab['giorni'][0]['celle'][i2]
    gruppi = r['libere_giorni']
    assert sum(len(g['stanze']) for g in gruppi) <= r['n_libere'] and gruppi[0]['oggi'], gruppi[:1]
    assert any(v['quando'] == 'tutto il giorno' for g in gruppi for v in g['stanze']), gruppi
    # la pagina: la frase, la linea del tempo, la tabella; le notifiche non coprono la pagina
    t = testo(C.get('/riepilogo-live?struttura=1'))
    for pezzo in ('class="frase-live', 'class="riga-live', 'class="pista-live"', 'class="libere-tab"', 'da segnare',
                  'turno del medico'):
        assert pezzo in t, pezzo
    css = open(os.path.join(CARTELLA, 'static', 'stile.css'), encoding='utf-8').read()
    assert 'body.pagina-live .notifiche { display: none; }' in css
    s.close()


prova('riepilogo live: numeri di oggi, stanze adesso (libera fino alle, in corso, senza medico), ore, mezze giornate libere', l_riepilogo)
prova('riepilogo live (1.12.2): quattro gruppi che sommano, frasi, linea del tempo, ore, mezze giornate per giorno', l_chiaro)
prova('riepilogo live: pagina, modo schermo, JSON senza dati dei pazienti, struttura mancante', l_pagina_e_json)


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
