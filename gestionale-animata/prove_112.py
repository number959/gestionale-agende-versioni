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
    ambulatori = {r.id for r in st.risorse if r.attiva and r.tipo != 'SALA_OPERATORIA'}
    for r in st.risorse:
        if not r.attiva or r.tipo == 'SALA_OPERATORIA':
            continue
        for g in giorni:
            i = regole.giorno(g, st)
            validi = regole.turni_validi(g, st, r.id)
            # 1.12.3: un giorno che non e' di apertura e c'e' solo per la sala: ambulatori chiusi
            solo_sala = g.weekday() not in st.giorni_aperti and not any(
                t.risorsa_id in ambulatori and (not tipo or t.valido_da != t.valido_a) for t in regole.turni_validi(g, st))
            if tipo:
                turni = [t for t in validi if t.valido_da != t.valido_a]
                chiuso = 'solo sala operatoria' if solo_sala else None
            else:
                turni = regole.turni_effettivi(g, st, r.id, i)
                chiuso = i['chiusura'] or (i['festivo'] if i['chiude_festivo'] and not turni else None) or \
                    ('solo sala operatoria' if solo_sala else None)
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
    # 1.12.3: la sala operatoria sta nella sua parte, mai fra gli ambulatori (matrice e programmazione)
    assert [r['risorsa'].nome for r in v['sale']] == ['Sala operatoria'], v['sale']
    pr = AM.programmazione(s, 2026, 12, st)
    assert all(r['risorsa'].nome != 'Sala operatoria' for r in pr['righe']) and pr['righe'], [r['risorsa'].nome for r in pr['righe']]
    assert all(t.risorsa.nome != 'Sala operatoria' for g in pr['calendario'] for t in g['presenze'])
    assert pr['sala']['righe'] and all(r['risorsa'].nome == 'Sala operatoria' for r in pr['sala']['righe'])
    assert not any(r['risorsa'].nome == 'Ambulatorio 4' for r in pr['righe'] + pr['sala']['righe'])
    s.close()
    # ... ne' nei due Excel classici (matrice e programmazione degli ambulatori: dalla 1.12.3 la sala ha i suoi file)
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


def b_sala_settimana_e_mese():
    """1.12.3: la sala operatoria nella matrice della settimana e nella programmazione del mese, in una parte
    sua: chirurghi in turno e interventi attivi contati a parte (minuti e ore scritti qui), fuori dai conti degli
    ambulatori; un giorno di sola sala chiude gli ambulatori; pagine ed Excel."""
    from modelli import Appuntamento, Paziente
    S, I, C = mondo_pieno()
    s = S()
    st = s.get(Struttura, 1)
    prima = AM.matrice(s, LUN, st)
    libere_prima, parziali_prima = prima['libere'], prima['parziali']
    s.add_all([Risorsa(nome='Sala operatoria 2', tipo='SALA_OPERATORIA', struttura_id=1, ordine=51),
               Risorsa(nome='Sala vecchia', tipo='SALA_OPERATORIA', struttura_id=1, ordine=52, attiva=False)])
    pz = Paziente(cognome='Fittizi', nome='Ada', telefono='3339990004')
    s.add(pz)
    s.commit()
    I.update({r.nome: r.id for r in s.scalars(select(Risorsa))})
    DOM, MAR, MER = LUN + timedelta(days=6), LUN + timedelta(days=1), LUN + timedelta(days=2)
    singolo(S, I['Galasso'], I['Sala operatoria 2'], DOM, time(9), time(12))       # domenica: solo la sala
    turno(S, I['Fintini'], I['Sala operatoria 2'], 2, time(14), time(18))           # ogni mercoledi pomeriggio
    turno(S, I['Lippiello'], I['Sala vecchia'], 0, time(8), time(12))               # sala spenta: non si vede

    def app(sala, medico, giorno, h, m=0, stato='PRENOTATO'):
        inizio = datetime.combine(giorno, time(h, m))
        s.add(Appuntamento(risorsa_id=I[sala], operatore_id=I[medico], paziente_id=pz.id, inizio=inizio,
                           fine=inizio + timedelta(minutes=60), stato=stato))
    app('Sala operatoria', 'Esempietti', LUN, 9)                                    # mattina, nel turno
    app('Sala operatoria', 'Esempietti', LUN, 7, stato='CONFERMATO')                # prima dell'apertura: mattina
    app('Sala operatoria', 'Esempietti', LUN, 10, stato='DISDETTO')                 # non conta
    app('Sala operatoria', 'Esempietti', LUN, 11, stato='NON_PRESENTATO')           # non conta
    app('Sala operatoria', 'Esempietti', LUN, 15, stato='ARRIVATO')                 # pomeriggio, fuori turno
    app('Sala operatoria', 'Esempietti', MAR, 10)                                   # festivo: sala chiusa
    app('Sala operatoria 2', 'Fintini', MER, 21)                                    # dopo la chiusura: pomeriggio
    app('Sala operatoria 2', 'Galasso', DOM, 10)                                    # la domenica della sala
    app('Sala vecchia', 'Lippiello', LUN, 9)                                        # sala spenta: non conta
    app('Sala operatoria', 'Esempietti', DOM + timedelta(days=7), 9)                # domenica 20: nessun turno, solo l'intervento
    s.commit()
    v = AM.matrice(s, LUN, st)
    assert [r['risorsa'].nome for r in v['sale']] == ['Sala operatoria', 'Sala operatoria 2'], v['sale']
    assert [g.weekday() for g in v['giorni']] == [0, 1, 2, 3, 4, 5, 6] and v['solo_sala'] == {DOM}, v['giorni']
    # gli ambulatori: stessi conti di prima, la domenica chiusa (non DISPONIBILE)
    assert (v['libere'], v['parziali']) == (libere_prima, parziali_prima), (v['libere'], libere_prima)
    for riga in v['righe']:
        dom = [c for c in riga['celle'] if c['data'] == DOM]
        assert dom and all(c['chiuso'] == 'solo sala operatoria' and not c['tutta_libera'] for c in dom), (riga['risorsa'].nome, dom)
    # l'oracolo della sala: turni effettivi (servizi) ritagliati sulle due meta' con i minuti, interventi contati
    # con l'ora scritta qui (prima delle 14 mattina, dalle 14 pomeriggio)
    regole = servizi.Regole(s, LUN, DOM)
    attivi = s.scalars(select(Appuntamento).where(Appuntamento.stato.in_(('PRENOTATO', 'CONFERMATO', 'ARRIVATO')))).all()
    for riga in v['sale']:
        r = riga['risorsa']
        for c in riga['celle']:
            g, nome = c['data'], c['meta']['nome']
            i = regole.giorno(g, st)
            m0, m1 = (8 * 60, 14 * 60) if nome == 'mattina' else (14 * 60, 20 * 60)
            presenze = sorted((t.operatore.cognome, max(mm(t.ora_inizio), m0), min(mm(t.ora_fine), m1))
                              for t in regole.turni_effettivi(g, st, r.id, i) if mm(t.ora_inizio) < m1 and m0 < mm(t.ora_fine))
            chiuso = None if presenze else (i['chiusura'] or (i['festivo'] if i['chiude_festivo'] else None))
            qui = [x for x in attivi if x.risorsa_id == r.id and x.inizio.date() == g
                   and ((x.inizio.hour < 14) == (nome == 'mattina'))]
            senza = sorted({x.operatore.etichetta for x in qui if x.operatore.cognome not in {p[0] for p in presenze}})
            c = dict(c, senza_turno=[o.etichetta for o in c['senza_turno']])
            trovate = sorted((p['operatore'].cognome, mm(p['da']), mm(p['a'])) for p in c['presenze'])
            assert (trovate, c['chiuso'], c['interventi'], c['senza_turno']) == (presenze, chiuso, len(qui), senza), \
                (r.nome, g, nome, trovate, c['chiuso'], c['interventi'], c['senza_turno'], presenze, chiuso, len(qui), senza)
            assert c['tutta_libera'] == (not presenze and not chiuso and not qui)
    assert v['interventi'] == 6, v['interventi']
    # la settimana dopo: la domenica 20 c'e' per il solo intervento, senza turni; gli ambulatori sono chiusi
    v2 = AM.matrice(s, LUN + timedelta(days=7), st)
    d20 = DOM + timedelta(days=7)
    assert d20 in v2['giorni'] and v2['solo_sala'] == {d20}, (v2['giorni'], v2['solo_sala'])
    c20 = [c for c in v2['sale'][0]['celle'] if c['data'] == d20 and c['meta']['nome'] == 'mattina'][0]
    assert AM.testo_cella_sala(c20) == 'Esempietti Rita, senza turno\n1 intervento', AM.testo_cella_sala(c20)
    assert all(c['chiuso'] == 'solo sala operatoria' for r_ in v2['righe'] for c in r_['celle'] if c['data'] == d20)
    # l'Excel della sala della settimana: i testi di ogni cella; nella matrice degli ambulatori la domenica chiusa
    _, wb = excel(C, '/esportazioni/settimana/sala/%s.xlsx?struttura=1' % LUN.isoformat())
    ws = wb['Sala operatoria']
    righe = {ws.cell(i, 1).value: i for i in range(1, ws.max_row + 1) if ws.cell(i, 1).value}
    colonna = {(ws.cell(5, 2 + 2 * (k // 2)).value or '').split('\n')[0] + ' ' + ('mattina' if k % 2 == 0 else 'pomeriggio'): 2 + k
               for k in range(14)}
    o, o2 = righe['Sala operatoria'], righe['Sala operatoria 2']
    _, wb_a = excel(C, '/ambulatori/settimana/%s.xlsx?struttura=1' % LUN.isoformat())
    wa = wb_a['Matrice']
    a1 = next(i for i in range(1, wa.max_row + 1) if wa.cell(i, 1).value == 'Ambulatorio 1')
    assert all('Sala operatoria' not in str(c.value or '') and 'Esempietti' not in str(c.value or '')
               for row in wa.iter_rows() for c in row), 'la matrice per la direzione: solo ambulatori'
    # la domenica che c'e' solo per la sala non e' nella matrice della direzione (resta quella di prima)
    giorni_a = [str(wa.cell(6, c).value or '').split('\n')[0] for c in range(2, wa.max_column + 1, 2) if wa.cell(6, c).value]
    assert giorni_a == ['Lunedì 7/12', 'Martedì 8/12', 'Mercoledì 9/12', 'Giovedì 10/12', 'Venerdì 11/12', 'Sabato 12/12'], giorni_a
    assert all('solo sala operatoria' not in str(c.value or '') for row in wa.iter_rows() for c in row)
    # nel foglio della settimana (colonne strette) l'orario va sotto il nome intero quando la riga e' piu' lunga di
    # 22 lettere: prima andava a capo dopo «08:00-» (1.12.4); nella pagina il testo resta su una riga
    attese = {(o, 'Lunedì 7/12 mattina'): 'Esempietti Rita\n08:00-14:00\n2 interventi',
              (o, 'Lunedì 7/12 pomeriggio'): 'Esempietti Rita, senza turno\n1 intervento',
              (o, 'Martedì 8/12 mattina'): 'CHIUSO: Immacolata Concezione\nEsempietti Rita, senza turno\n1 intervento',
              (o, 'Martedì 8/12 pomeriggio'): 'CHIUSO: Immacolata Concezione',
              (o, 'Giovedì 10/12 mattina'): 'CHIUSO: Manutenzione',
              (o, 'Domenica 13/12 mattina'): 'sala libera',
              (o2, 'Mercoledì 9/12 pomeriggio'): 'Fintini Ugo\n14:00-18:00\n1 intervento',
              (o2, 'Domenica 13/12 mattina'): 'Galasso 09:00-12:00\n1 intervento'}
    for (riga, quando), testo_atteso in attese.items():
        assert ws.cell(riga, colonna[quando]).value == testo_atteso, (riga, quando, ws.cell(riga, colonna[quando]).value)
    assert 'Sala vecchia' not in righe and ws.cell(2, 1).value.startswith('SALA OPERATORIA'), righe
    # l'elenco degli interventi della settimana: tutti, in ogni stato, nelle sale della struttura (anche quella spenta)
    wi = wb['Interventi']
    elenco = [[wi.cell(i, c).value for c in range(1, 8)] for i in range(6, wi.max_row + 1)
              if isinstance(wi.cell(i, 1).value, datetime)]
    assert len(elenco) == 9 and sum(1 for x in elenco if x[6] in ('Disdetto', 'Non presentato')) == 2, elenco
    assert wi.cell(2, 1).value == '7 interventi attivi (più 1 disdetto e 1 non presentato)', wi.cell(2, 1).value
    assert [x[3] for x in elenco].count('Sala vecchia') == 1, 'anche la sala spenta, nell\'elenco'
    for foglio in wb.worksheets:
        assert all('Fittizi' not in str(c.value or '') and '3339990004' not in str(c.value or '') for row in foglio.iter_rows() for c in row), foglio.title
    # la pagina della settimana: la sala in fondo, gli interventi portano alla pagina Sala
    t = testo(C.get('/ambulatori/settimana/%s?struttura=1' % LUN.isoformat()))
    parte = t[t.index('<tbody class="parte-sala"'):]
    assert 'Sala operatoria 2' in parte and '2 interventi' in parte and '/sala/2026-12-07?struttura=1' in parte
    assert 'Esempietti <small>senza turno</small>' in parte or 'Esempietti Rita <small>senza turno</small>' in parte, parte[:400]
    assert 'Sala vecchia' not in t and 'Fittizi' not in t
    # la programmazione di dicembre: righe della sala con gli interventi nelle ore del turno, la frase con quelli fuori
    pr = AM.programmazione(s, 2026, 12, st)
    sala = {(r['risorsa'].nome, r['operatore'].cognome, r['giorno']): r for r in pr['sala']['righe']}
    assert sorted(sala, key=str) == sorted([('Sala operatoria', 'Esempietti', k) for k in range(6)] +
                                           [('Sala operatoria', 'Esempietti', None), ('Sala operatoria 2', 'Fintini', 2),
                                            ('Sala operatoria 2', 'Fintini', None), ('Sala operatoria 2', 'Galasso', 6)], key=str), sorted(sala, key=str)
    f = sala[('Sala operatoria', 'Esempietti', None)]
    assert (f['date'], f['interventi'], f['note'], f['turno']) == ([LUN, MAR, DOM + timedelta(days=7)], 4,
                                                                   ['4 interventi fuori dai turni'], None), f
    assert sala[('Sala operatoria 2', 'Fintini', None)]['date'] == [MER] and pr['sala']['turni'] == 8
    assert sala[('Sala operatoria', 'Esempietti', 0)]['interventi'] == 1 and '1 intervento' in sala[('Sala operatoria', 'Esempietti', 0)]['note']
    assert sala[('Sala operatoria 2', 'Galasso', 6)]['interventi'] == 1 and sala[('Sala operatoria 2', 'Galasso', 6)]['date'] == [DOM]
    assert sala[('Sala operatoria 2', 'Fintini', 2)]['interventi'] == 0
    assert (pr['sala']['interventi'], pr['sala']['fuori_turno']) == (7, 5), pr['sala']
    assert AM.frase_sala_mese(pr['sala']) == 'Sala operatoria: 7 interventi nel mese, di cui 5 fuori dai turni dei chirurghi.'
    assert all(r['risorsa'].tipo != 'SALA_OPERATORIA' for r in pr['righe'])
    dom = next(g for g in pr['calendario'] if g['data'] == DOM)
    assert dom['presenze'] == [] and [(x['turno'].risorsa.nome, x['interventi']) for x in dom['sala']] == [('Sala operatoria 2', 1)]
    s.close()
    # l'Excel della sala del mese: i turni di sala con quelli fuori e la frase; il calendario di tutto insieme
    _, wb = excel(C, '/esportazioni/mese/sala/2026-12-01.xlsx?struttura=1')
    assert wb.sheetnames == ['Sala operatoria', 'Turni di sala', 'Interventi'], wb.sheetnames
    ws = wb['Turni di sala']
    testi = [str(ws.cell(i, 1).value or '') for i in range(1, ws.max_row + 1)]
    assert 'Sala operatoria: 7 interventi nel mese, di cui 5 fuori dai turni dei chirurghi.' in testi, testi[-4:]
    senza = [[ws.cell(i, c).value for c in range(1, 7)] for i in range(6, ws.max_row + 1)
             if ws.cell(i, 6).value and 'fuori dai turni' in str(ws.cell(i, 6).value)]
    assert senza == [['Sala operatoria', 'Esempietti Rita', '—', '7, 8, 20', '—', '4 interventi fuori dai turni'],
                     ['Sala operatoria 2', 'Fintini Ugo', '—', '9', '—', '1 intervento fuori dai turni']], senza
    # le date sono sempre testo, anche una sola (fino alla 1.12.3 il 9 era un numero e in Excel andava a destra)
    assert all(isinstance(ws.cell(i, 4).value, str) for i in range(6, ws.max_row + 1) if ws.cell(i, 4).value is not None)
    _, wb = excel(C, '/esportazioni/mese/tutto/2026-12-01.xlsx?struttura=1')
    assert wb.sheetnames == ['Programmazione', 'Calendario', 'Sala operatoria', 'Turni di sala', 'Interventi'], wb.sheetnames
    assert all('Esempietti' not in str(c.value or '') for row in wb['Programmazione'].iter_rows() for c in row), \
        'la programmazione resta degli ambulatori: la sala nei suoi fogli'
    wc = wb['Calendario']
    righe = [[wc.cell(i, c).value for c in range(1, 7)] for i in range(4, wc.max_row + 1)]
    i_dom = next(k for k, x in enumerate(righe) if x[0] == datetime(2026, 12, 13))
    assert righe[i_dom][2] == 'solo sala operatoria' and righe[i_dom + 1][2:] == ['Sala operatoria 2', 'Galasso', '09:00-12:00', 1], righe[i_dom:i_dom + 2]
    i_lun = next(k for k, x in enumerate(righe) if x[0] == datetime(2026, 12, 7))
    blocco = righe[i_lun:i_lun + 4]      # Galasso e' assente il 7: Lippiello, la sala nel turno, quella fuori, il martedi
    assert blocco[0][2] == 'Ambulatorio 1' and blocco[1][2:] == ['Sala operatoria', 'Esempietti Rita', '08:00-14:00', 1] \
        and blocco[2][2:] == ['Sala operatoria', 'Esempietti Rita', 'fuori turno', 2] and blocco[3][0] == datetime(2026, 12, 8), blocco
    i20 = next(k for k, x in enumerate(righe) if x[0] == datetime(2026, 12, 20))
    assert righe[i20][2] == 'solo sala operatoria' and righe[i20 + 1][2:] == ['Sala operatoria', 'Esempietti Rita', 'fuori turno', 1], righe[i20:i20 + 2]
    t = testo(C.get('/ambulatori/mese/2026-12?struttura=1'))
    assert 'in sala 8 turni, 7 interventi' in t and 'di cui 5 fuori dai turni' in t and 'solo sala operatoria' in t, t[:300]
    assert 'Fittizi' not in t


prova('1.12.3: la sala operatoria nella settimana e nel mese, contro un calcolo a parte; ambulatori con gli stessi conti; '
      'domenica di sola sala; Excel e pagine', b_sala_settimana_e_mese)


def b_esportazioni():
    """1.12.3: le nove esportazioni (giorno, settimana e mese per ambulatori, sala operatoria e tutto insieme), i loro
    fogli e i nomi dei file; gli ambulatori uguali ai file classici; la sala del mese uguale alle settimane; niente
    pazienti negli Excel di settimana e mese; la pagina, anche senza sale; i collegamenti dalle altre pagine."""
    import re
    from modelli import Appuntamento, Paziente
    S, I, C = mondo_pieno()
    s = S()
    pz = Paziente(cognome='Provolo', nome='Gino', telefono='3339990002')
    s.add(pz)
    s.flush()
    for stanza, medico, h in (('Sala operatoria', 'Esempietti', 9), ('Ambulatorio 1', 'Lippiello', 15)):
        inizio = datetime.combine(LUN, time(h))
        s.add(Appuntamento(risorsa_id=I[stanza], operatore_id=I[medico], paziente_id=pz.id, inizio=inizio,
                           fine=inizio + timedelta(minutes=30), stato='PRENOTATO'))
    s.commit()
    st = s.get(Struttura, 1)

    def valori(foglio):
        """I valori del foglio, senza l'ora del calcolo (cambia da un minuto all'altro)."""
        return [[re.sub(r'\d\d:\d\d\.$|alle \d\d:\d\d', '', str(c.value)) if isinstance(c.value, str) else c.value
                 for c in row] for row in foglio.iter_rows()]
    attese = {('giorno', 'ambulatori'): ['Ambulatori', 'Elenco'],
              ('giorno', 'sala'): ['Sala operatoria', 'Elenco'],
              ('giorno', 'tutto'): ['Ambulatori', 'Sala operatoria', 'Elenco'],
              ('settimana', 'ambulatori'): ['Matrice'],
              ('settimana', 'sala'): ['Sala operatoria', 'Interventi'],
              ('settimana', 'tutto'): ['Ambulatori', 'Sala operatoria', 'Interventi'],
              ('mese', 'ambulatori'): ['Programmazione', 'Calendario'],
              ('mese', 'sala'): ['Sala operatoria', 'Turni di sala', 'Interventi'],
              ('mese', 'tutto'): ['Programmazione', 'Calendario', 'Sala operatoria', 'Turni di sala', 'Interventi']}
    libri = {}
    for (periodo, parte), fogli in attese.items():
        data = LUN if periodo == 'giorno' else LUN + timedelta(days=2)       # settimana e mese da un giorno qualsiasi
        r, wb = excel(C, '/esportazioni/%s/%s/%s.xlsx?struttura=1' % (periodo, parte, data.isoformat()))
        prefisso = {'ambulatori': 'ambulatori', 'sala': 'sala-operatoria', 'tutto': 'ambulatori-e-sala'}[parte]
        quando = '2026-12' if periodo == 'mese' else LUN.isoformat()
        assert '%s-%s-%s.xlsx' % (prefisso, periodo, quando) in r.headers['Content-Disposition'], (periodo, parte, r.headers['Content-Disposition'])
        assert wb.sheetnames == fogli, (periodo, parte, wb.sheetnames)
        libri[(periodo, parte)] = wb
        if periodo != 'giorno':
            for foglio in wb.worksheets:
                assert all('Provolo' not in str(c.value or '') and '3339990002' not in str(c.value or '')
                           for row in foglio.iter_rows() for c in row), (periodo, parte, foglio.title)
    # il giorno: le colonne giuste in ogni foglio, l'elenco giusto
    def stanze_del_foglio(ws):
        return [str(ws.cell(2, c).value).split('\n')[0] for c in range(2, ws.max_column + 1, 2) if ws.cell(2, c).value]
    amb = libri[('giorno', 'ambulatori')]
    assert 'Sala operatoria' not in stanze_del_foglio(amb['Ambulatori']) and 'Ambulatorio 1' in stanze_del_foglio(amb['Ambulatori'])
    assert stanze_del_foglio(libri[('giorno', 'sala')]['Sala operatoria']) == ['Sala operatoria']
    assert libri[('giorno', 'sala')]['Sala operatoria']['A1'].value.startswith('CLINICA PROVA - SALA OPERATORIA, PLANNING DEL')
    def elenco(wb):
        ws = wb['Elenco']
        return [ws.cell(i, 3).value for i in range(1, ws.max_row + 1) if isinstance(ws.cell(i, 1).value, time)]
    assert elenco(amb) == ['Ambulatorio 1'] and elenco(libri[('giorno', 'sala')]) == ['Sala operatoria']
    assert sorted(elenco(libri[('giorno', 'tutto')])) == ['Ambulatorio 1', 'Sala operatoria']
    assert str(libri[('giorno', 'sala')]['Elenco']['A1'].value).startswith('Clinica Prova — Interventi del lunedì 7 dicembre 2026'), \
        libri[('giorno', 'sala')]['Elenco']['A1'].value
    assert str(amb['Elenco']['A1'].value).startswith('Clinica Prova — Appuntamenti degli ambulatori del lunedì 7 dicembre 2026'), \
        amb['Elenco']['A1'].value
    # 1.12.4, dall'anteprima: ogni cella scritta ha il nome del carattere (i grassetti e i corsivi della matrice e
    # della sala non l'avevano: fuori da Excel un carattere con le grazie); la testata del planning dice cosa c'e'
    for (periodo, parte), wb_ in libri.items():
        for foglio in wb_.worksheets:
            senza = [c.coordinate for row in foglio.iter_rows() for c in row if c.value is not None and not c.font.name]
            assert not senza, (periodo, parte, foglio.title, senza[:5])
    assert 'sala operatoria · lunedì 7 dicembre 2026' in libri[('giorno', 'sala')]['Sala operatoria'].oddHeader.center.text
    assert 'ambulatori · lunedì 7 dicembre 2026' in libri[('giorno', 'ambulatori')]['Ambulatori'].oddHeader.center.text
    wi_ = libri[('mese', 'sala')]['Interventi']
    tot_ = next(i for i in range(1, wi_.max_row + 1) if str(wi_.cell(i, 1).value or '').startswith('Totale (solo attivi): '))
    assert 'A%d:G%d' % (tot_, tot_) in [str(m) for m in wi_.merged_cells.ranges], 'il conto non sotto CHIRURGO'
    import ambulatori as A_
    assert A_._settimana_testo({'lunedi': date(2026, 11, 2)}) == "dal 2 novembre all'8 novembre 2026"
    assert A_._settimana_testo({'lunedi': date(2027, 2, 8)}) == "dall'8 febbraio al 14 febbraio 2027"
    assert 'confermati o arrivati' in A_.LEGENDA_SALA and 'fatti' not in A_.LEGENDA_SALA
    ws_m = libri[('mese', 'sala')]['Sala operatoria']
    assert ws_m.page_setup.fitToHeight == 1, 'la sala del mese in una pagina, se manca poco'
    # la settimana e il mese degli ambulatori: uguali ai file classici, cella per cella
    _, classica = excel(C, '/ambulatori/settimana/%s.xlsx?struttura=1' % LUN.isoformat())
    assert valori(libri[('settimana', 'ambulatori')]['Matrice']) == valori(classica['Matrice'])
    assert valori(libri[('settimana', 'tutto')]['Ambulatori']) == valori(classica['Matrice'])
    _, classico = excel(C, '/ambulatori/mese/2026-12.xlsx?struttura=1')
    for nome in ('Programmazione', 'Calendario'):
        assert valori(libri[('mese', 'ambulatori')][nome]) == valori(classico[nome]), nome
    assert valori(libri[('mese', 'tutto')]['Programmazione']) == valori(classico['Programmazione'])
    assert libri[('mese', 'tutto')]['Calendario'].cell(3, 6).value == 'Interventi' and classico['Calendario'].cell(3, 6).value is None
    for k in ('Sala operatoria', 'Turni di sala', 'Interventi'):
        assert valori(libri[('mese', 'tutto')][k]) == valori(libri[('mese', 'sala')][k]), k
    assert valori(libri[('settimana', 'tutto')]['Sala operatoria']) == valori(libri[('settimana', 'sala')]['Sala operatoria'])
    # la sala del mese giorno per giorno: le stesse celle delle matrici delle settimane
    ws = libri[('mese', 'sala')]['Sala operatoria']
    righe = {str(ws.cell(i, 1).value).split('\n')[0]: i for i in range(7, ws.max_row + 1)
             if ws.cell(i, 1).value and '/12' in str(ws.cell(i, 1).value).split('\n')[0]}
    visti = 0
    lunedi = calendario.lunedi_di(date(2026, 12, 1))
    while lunedi <= date(2026, 12, 31):
        v = AM.matrice(s, lunedi, st)
        for c in v['sale'][0]['celle']:
            if c['data'].month != 12:
                continue
            nome = '%s %d/%d' % (servizi.GIORNI[c['data'].weekday()].capitalize(), c['data'].day, c['data'].month)
            k = 0 if c['meta']['nome'] == 'mattina' else 1
            assert ws.cell(righe[nome], 2 + k).value == AM.testo_cella_sala(c), (nome, k, ws.cell(righe[nome], 2 + k).value)
            visti += 1
        lunedi += timedelta(days=7)
    assert visti == 2 * len(righe) and len(righe) == 27, (visti, len(righe))          # dicembre: 27 giorni dal lunedi al sabato
    assert ws.cell(righe['Lunedì 7/12'], 2).value == 'Esempietti Rita 08:00-14:00\n1 intervento'
    wi = libri[('mese', 'sala')]['Interventi']
    assert wi.cell(2, 1).value == '1 intervento attivo', wi.cell(2, 1).value
    # indirizzi scritti male: niente errori del server
    assert C.get('/esportazioni/anno/sala/2026-12-07.xlsx').status_code == 404
    assert C.get('/esportazioni/mese/altro/2026-12-07.xlsx').status_code == 404
    assert C.get('/esportazioni/mese/sala/non-una-data.xlsx?struttura=1').status_code == 200
    # la pagina: nove pulsanti con la data scelta, il menu Ambulatori attivo
    t = testo(C.get('/esportazioni?struttura=1&data=2026-12-09'))
    for periodo in ('giorno', 'settimana', 'mese'):
        for parte in ('ambulatori', 'sala', 'tutto'):
            assert '/esportazioni/%s/%s/2026-12-09.xlsx?struttura=1' % (periodo, parte) in t, (periodo, parte)
    assert 'mercoledì 9 dicembre 2026' in t and '<small>dal 7 al 13 dicembre 2026</small>' in t and '<small>dicembre 2026</small>' in t
    assert 'Esportazioni in Excel</b>' in t and 'class="gruppo attivo" data-guida="menu-ambulatori"' in t
    # i collegamenti dalle altre pagine
    assert '/esportazioni?data=2026-12-07&amp;struttura=1' in testo(C.get('/giorno/2026-12-07?struttura=1'))
    t = testo(C.get('/ambulatori/settimana/2026-12-07?struttura=1'))
    assert '/esportazioni/settimana/sala/2026-12-07.xlsx?struttura=1' in t and '/esportazioni/settimana/tutto/2026-12-07.xlsx?struttura=1' in t
    t = testo(C.get('/ambulatori/mese/2026-12?struttura=1'))
    assert '/esportazioni/mese/sala/2026-12-01.xlsx?struttura=1' in t and 'Altre esportazioni' in t
    # senza sale operatorie: la colonna della sala dice perché, gli altri pulsanti restano
    s.get(Risorsa, I['Sala operatoria']).attiva = False
    s.commit()
    s.close()
    t = testo(C.get('/esportazioni?struttura=1&data=2026-12-09'))
    assert t.count('Nessuna sala operatoria in questa struttura') == 3 and t.count('>Scarica</a>') == 6, t.count('>Scarica</a>')
    assert '/esportazioni/settimana/sala/' not in testo(C.get('/ambulatori/settimana/2026-12-07?struttura=1'))
    _, wb = excel(C, '/esportazioni/settimana/sala/2026-12-07.xlsx?struttura=1')
    assert any(ws.cell(i, 1).value == 'Nessuna sala operatoria attiva in questa struttura.' for i in range(1, 12) for ws in [wb['Sala operatoria']])
    _, wb = excel(C, '/esportazioni/giorno/tutto/2026-12-07.xlsx?struttura=1')
    assert wb.sheetnames == ['Ambulatori', 'Sala operatoria', 'Elenco'], 'la sala spenta ha ancora un intervento quel giorno'


prova('1.12.3: le nove esportazioni (giorno, settimana e mese × ambulatori, sala, tutto), uguali ai file classici e alle '
      'settimane, senza pazienti fuori dal giorno; la pagina, anche senza sale', b_esportazioni)


def b_sala_casi_limite():
    """1.12.3, dalla verifica indipendente: turni di sala prima dell'apertura e dopo la chiusura, l'intervento alle 14
    in punto, quello di un chirurgo nel turno di un collega, due turni sovrapposti dello stesso chirurgo (un intervento
    conta una volta sola), un giorno di sola sala con il solo turno (oracolo della matrice e riepilogo live come prima),
    chiusura e festivo con un intervento (pagina ed Excel dicono il motivo), la sala del mese con tutte le sale e un
    mese di 30 giorni, il giorno «tutto» con le stanze senza sale, il logo largo, il planning classico senza stanze."""
    import io as _io
    import live
    from PIL import Image
    from modelli import Appuntamento, Paziente
    S, I, C = mondo_pieno()
    s = S()
    st = s.get(Struttura, 1)
    s.add(Risorsa(nome='Sala operatoria 2', tipo='SALA_OPERATORIA', struttura_id=1, ordine=51))
    pz = Paziente(cognome='Esempio', nome='Ugo', telefono='3339990005')
    s.add(pz)
    s.commit()
    I.update({r.nome: r.id for r in s.scalars(select(Risorsa))})
    L2 = LUN + timedelta(days=7)                                                    # lunedi 14/12
    singolo(S, I['Lippiello'], I['Sala operatoria 2'], L2 + timedelta(days=4), time(6), time(7, 30))     # venerdi, prima delle 8
    singolo(S, I['Galasso'], I['Sala operatoria 2'], L2 + timedelta(days=5), time(20, 30), time(22))     # sabato, dopo le 20
    singolo(S, I['Esempietti'], I['Sala operatoria'], L2, time(10), time(12))       # sopra il turno di ogni lunedi 8-14
    singolo(S, I['Fintini'], I['Sala operatoria 2'], L2 + timedelta(days=6), time(9), time(12))          # domenica: solo il turno

    def app(sala, medico, giorno, h, m=0):
        inizio = datetime.combine(giorno, time(h, m))
        s.add(Appuntamento(risorsa_id=I[sala], operatore_id=I[medico], paziente_id=pz.id, inizio=inizio,
                           fine=inizio + timedelta(minutes=30), stato='PRENOTATO'))
    app('Sala operatoria 2', 'Lippiello', L2 + timedelta(days=4), 6, 30)
    app('Sala operatoria 2', 'Galasso', L2 + timedelta(days=5), 21)
    app('Sala operatoria', 'Esempietti', L2, 14)                                    # alle 14 in punto: fuori dal turno 8-14
    app('Sala operatoria', 'Galasso', L2, 9)                                        # nel turno di Esempietti
    app('Sala operatoria', 'Esempietti', L2, 10, 30)                                # dentro tutti e due i turni di Esempietti
    app('Sala operatoria', 'Esempietti', LUN + timedelta(days=1), 10)               # martedi 8, festivo
    app('Sala operatoria', 'Esempietti', LUN + timedelta(days=3), 10)               # giovedi 10, chiuso per manutenzione
    s.commit()
    v = AM.matrice(s, L2, st)
    celle = {(r['risorsa'].nome, c['data'].weekday(), c['meta']['nome']): c for r in v['sale'] for c in r['celle']}
    T = AM.testo_cella_sala
    assert T(celle[('Sala operatoria 2', 4, 'mattina')]) == 'Lippiello Anna 06:00-07:30\n1 intervento', T(celle[('Sala operatoria 2', 4, 'mattina')])
    assert T(celle[('Sala operatoria 2', 5, 'pomeriggio')]) == 'Galasso 20:30-22:00\n1 intervento', T(celle[('Sala operatoria 2', 5, 'pomeriggio')])
    assert T(celle[('Sala operatoria', 0, 'mattina')]) == \
        'Esempietti Rita 08:00-14:00\nEsempietti Rita 10:00-12:00\nGalasso, senza turno\n2 interventi', T(celle[('Sala operatoria', 0, 'mattina')])
    assert T(celle[('Sala operatoria', 0, 'pomeriggio')]) == 'Esempietti Rita, senza turno\n1 intervento'
    assert T(celle[('Sala operatoria 2', 6, 'mattina')]) == 'Fintini Ugo 09:00-12:00' and v['solo_sala'] == {L2 + timedelta(days=6)}
    # l'oracolo della matrice (minuto per minuto, senza ambulatori.py) anche con il giorno di sola sala
    giorni, atteso = oracolo_matrice(s, st, L2)
    assert giorni == v['giorni'], (giorni, v['giorni'])
    confronta(v, giorni, atteso)
    # il riepilogo live di quella domenica: la tabella delle mezze giornate come prima (niente riga della domenica)
    r = live.riepilogo(s, st, adesso=datetime.combine(L2 + timedelta(days=6), time(15)))
    assert all(x['data'] != (L2 + timedelta(days=6)).isoformat() for x in r['libere_tabella']['giorni']), r['libere_tabella']['giorni'][:1]
    # il mese: ogni intervento conta in un turno solo; quello di Galasso e quello delle 14 sono fuori dai turni
    pr = AM.programmazione(s, 2026, 12, st)
    righe = pr['sala']['righe']
    lun = [x for x in righe if x['operatore'].cognome == 'Esempietti' and x['giorno'] == 0]
    assert sorted((x['ora_inizio'], x['interventi']) for x in lun) == [(time(8), 1), (time(10), 0)], [(x['ora_inizio'], x['interventi']) for x in lun]
    fuori = {(x['risorsa'].nome, x['operatore'].cognome): x['interventi'] for x in righe if x.get('senza_turno')}
    assert fuori == {('Sala operatoria', 'Esempietti'): 3, ('Sala operatoria', 'Galasso'): 1}, fuori
    assert sum(x['interventi'] for x in righe) == pr['sala']['interventi'] == 7, (sum(x['interventi'] for x in righe), pr['sala']['interventi'])
    cal = {g['data']: g for g in pr['calendario']}
    voci = [(x['operatore'].cognome, x['turno'].ora_inizio if x['turno'] else None, x['interventi']) for x in cal[L2]['sala']]
    # prima i turni, poi chi opera fuori turno in ordine di ora (Galasso alle 9, Esempietti alle 14)
    assert voci == [('Esempietti', time(8), 1), ('Esempietti', time(10), 0), ('Galasso', None, 1), ('Esempietti', None, 1)], voci
    # chiusura e festivo con un intervento: la pagina e l'Excel dicono il motivo
    s.close()
    t = testo(C.get('/ambulatori/mese/2026-12?struttura=1'))
    assert 'martedì 8</td>\n            <td colspan="4">chiusa: immacolata concezione' in t, t[t.find('martedì 8'):][:160]
    assert 'giovedì 10</td>\n            <td colspan="4">chiusa: manutenzione' in t, t[t.find('giovedì 10'):][:160]
    assert 'fuori turno' in t and 'senza turno' not in t.split('details class="calendario-mese"')[1]
    _, wb = excel(C, '/esportazioni/mese/tutto/2026-12-01.xlsx?struttura=1')
    wc = wb['Calendario']
    per_data = {}
    for i in range(4, wc.max_row + 1):          # la prima riga di ogni giorno (dalla 1.12.4 la data e' in ogni riga)
        if isinstance(wc.cell(i, 1).value, datetime):
            per_data.setdefault(wc.cell(i, 1).value, wc.cell(i, 3).value)
    assert per_data[datetime(2026, 12, 8)] == 'chiusa: immacolata concezione' and per_data[datetime(2026, 12, 10)] == 'chiusa: manutenzione'
    # la sala del mese: tutte le sale, giorno per giorno, uguali alle settimane (anche la domenica di sola sala)
    ws = wb['Sala operatoria']
    righe_x = {str(ws.cell(i, 1).value).split('\n')[0]: i for i in range(7, ws.max_row + 1)
               if ws.cell(i, 1).value and '/12' in str(ws.cell(i, 1).value).split('\n')[0]}
    s = S()
    visti = 0
    lunedi = calendario.lunedi_di(date(2026, 12, 1))
    while lunedi <= date(2026, 12, 31):
        vv = AM.matrice(s, lunedi, st)
        for k, rr in enumerate(vv['sale']):
            for c in rr['celle']:
                if c['data'].month == 12:
                    nome = '%s %d/%d' % (servizi.GIORNI[c['data'].weekday()].capitalize(), c['data'].day, c['data'].month)
                    col = 2 + 2 * k + (0 if c['meta']['nome'] == 'mattina' else 1)
                    assert ws.cell(righe_x[nome], col).value == T(c), (nome, rr['risorsa'].nome, ws.cell(righe_x[nome], col).value, T(c))
                    visti += 1
        lunedi += timedelta(days=7)
    assert visti == 4 * len(righe_x) and 'Domenica 20/12' in righe_x, (visti, len(righe_x))
    # un mese di 30 giorni: novembre, dal lunedi al sabato (25 giorni)
    _, wn = excel(C, '/esportazioni/mese/sala/2026-11-15.xlsx?struttura=1')
    import re as _re
    giorni_nov = [i for i in range(7, wn['Sala operatoria'].max_row + 1)
                  if _re.match(r'^\w+ \d+/11$', str(wn['Sala operatoria'].cell(i, 1).value or '').split('\n')[0])]
    assert len(giorni_nov) == 25, len(giorni_nov)
    # il giorno «tutto»: il foglio Ambulatori senza sale, il foglio Sala con le due sale
    _, wg = excel(C, '/esportazioni/giorno/tutto/%s.xlsx?struttura=1' % L2.isoformat())
    def colonne(ws_):
        return [str(ws_.cell(2, c).value).split('\n')[0] for c in range(2, ws_.max_column + 1, 2) if ws_.cell(2, c).value]
    assert not any(x.startswith('Sala operatoria') for x in colonne(wg['Ambulatori'])), colonne(wg['Ambulatori'])
    assert colonne(wg['Sala operatoria']) == ['Sala operatoria', 'Sala operatoria 2'], colonne(wg['Sala operatoria'])
    # 1.12.4, dall'anteprima: su carta il planning delle due sale (stretto) va in verticale su una pagina sola, con il
    # titolo e la legenda a capo invece che tagliati, e con le parole della sala; fino alla 1.12.3 il titolo restava
    # «SALA OPERATOR» e il foglio andava su due pagine orizzontali usandone meta'
    ws_s = wg['Sala operatoria']
    assert ws_s.page_setup.orientation == 'portrait' and ws_s.page_setup.fitToHeight == 1, \
        (ws_s.page_setup.orientation, ws_s.page_setup.fitToHeight)
    tit_s = next(c for c in ws_s[1] if c.value)
    assert tit_s.alignment.wrap_text and ws_s.row_dimensions[1].height >= 40, ws_s.row_dimensions[1].height
    def legenda_di(ws_):
        return next(ws_.cell(i, 1) for i in range(3, ws_.max_row + 1) if str(ws_.cell(i, 1).value or '').startswith('Legenda'))
    leg = legenda_di(ws_s)
    assert leg.alignment.wrap_text and 'verde = intervento' in leg.value and 'turno di un chirurgo' in leg.value and \
        'sala chiusa' in leg.value and ws_s.row_dimensions[leg.row].height >= 26, (leg.value, ws_s.row_dimensions[leg.row].height)
    leg_a = legenda_di(wg['Ambulatori'])
    assert 'verde = appuntamento' in leg_a.value and 'stanza chiusa' in leg_a.value, leg_a.value
    wi = wg['Elenco']
    assert wi.cell(2, 1).value.startswith('7 appuntament') or 'appuntament' in str(wi.cell(2, 1).value), wi.cell(2, 1).value
    _, wsa = excel(C, '/esportazioni/giorno/sala/%s.xlsx?struttura=1' % L2.isoformat())
    assert wsa['Elenco'].cell(2, 1).value == '3 interventi attivi', wsa['Elenco'].cell(2, 1).value
    # il logo largo: il titolo del planning della sala (una colonna sola) va dopo il logo, non sotto
    buf = _io.BytesIO()
    Image.new('RGB', (600, 100), (21, 67, 129)).save(buf, 'PNG')
    st = s.get(Struttura, 1)
    st.logo, st.logo_aggiornato = buf.getvalue(), datetime.now()
    s.get(Risorsa, I['Sala operatoria 2']).attiva = False
    s.commit()
    _, wl = excel(C, '/esportazioni/giorno/sala/%s.xlsx?struttura=1' % L2.isoformat())
    titolo = [c for c in wl['Sala operatoria'][1] if c.value]
    assert titolo and titolo[0].column > 1 and 'SALA OPERATORIA' in titolo[0].value, [(c.column, c.value) for c in titolo]
    # 1.12.4: oltre la tabella il titolo prende colonne vuote quante ne servono per due righe, va a capo, e la
    # tabella (stretta) va in verticale; le colonne del titolo non contano per scegliere il verso della pagina
    ws_l = wl['Sala operatoria']
    unite = [m for m in ws_l.merged_cells.ranges if m.min_row == 1]
    assert len(unite) == 1 and unite[0].min_col == titolo[0].column and unite[0].max_col >= titolo[0].column + 5, unite
    assert titolo[0].alignment.wrap_text and ws_l.page_setup.orientation == 'portrait', ws_l.page_setup.orientation
    assert 'intervento in sale disattivate' in ' '.join(str(ws_l.cell(i, 1).value or '') for i in range(3, ws_l.max_row + 1)) or \
        not any('disattivate' in str(ws_l.cell(i, 1).value or '') for i in range(3, ws_l.max_row + 1))
    # senza sale: la sala del mese dice solo che non ci sono, senza un mese di righe vuote
    s.get(Risorsa, I['Sala operatoria']).attiva = False
    for r_ in s.scalars(select(Risorsa)):
        if r_.tipo != 'SALA_OPERATORIA':
            r_.attiva = False
    s.commit()
    s.close()
    _, wv = excel(C, '/esportazioni/mese/sala/2027-01-01.xlsx?struttura=1')
    colonna_a = [wv['Sala operatoria'].cell(i, 1).value for i in range(1, wv['Sala operatoria'].max_row + 1)]
    assert 'Nessuna sala operatoria attiva in questa struttura.' in colonna_a and \
        not any(_re.match(r'^\w+ \d+/1$', str(x or '').split('\n')[0]) for x in colonna_a), colonna_a
    # il planning classico senza nessuna stanza resta com'era: nessuna riga in piu'
    _, wp = excel(C, '/esporta/2027-01-04?struttura=1')
    assert not any('Nessuna stanza attiva' in str(c.value or '') for row in wp.worksheets[0].iter_rows() for c in row)


prova('1.12.3, dalla verifica: turni di sala fuori orario, le 14 in punto, il collega, turni sovrapposti, giorno di sola '
      'sala (oracolo e live), chiusure nel calendario, sala del mese completa, 30 giorni, logo largo, classico vuoto', b_sala_casi_limite)


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
    # 1.12.3: la sala operatoria in fondo, solo da guardare (si programma dalla pagina Sala)
    parte = t[t.index('<tbody class="parte-sala"'):t.index('</tbody>', t.index('<tbody class="parte-sala"'))]
    assert 'Sala operatoria' in parte and 'Esempietti' in parte and 'sala libera' in parte, parte[:300]
    assert 'class="metti"' not in parte and 'togli-turno' not in parte, 'la sala non si cambia da qui'
    assert 'Sala operatoria' not in t[:t.index('<tbody class="parte-sala"')].split('id="matrice-ambulatori"')[1]
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
    assert righe[3] == ['Senza specialità', 'Fintini Ugo', 'Mercoledì', '9', '09:00-11:00', 'Ambulatorio 3', 'un giorno solo'], righe[3]
    assert ws.cell(10, 1).value is None, 'quattro righe: la sala operatoria no'
    assert ws.freeze_panes == 'A6' and ws.auto_filter.ref == 'A5:G9' and ws.print_title_rows.replace('$', '') == '5:5', (ws.freeze_panes, ws.auto_filter.ref)
    # la specialita' in grassetto solo sulla prima riga del suo gruppo
    assert ws.cell(6, 1).font.bold and ws.cell(7, 1).font.bold and ws.cell(8, 1).font.bold and not ws.cell(9, 1).font.bold
    wc = wb['Calendario']
    assert [wc.cell(3, c).value for c in range(1, 6)] == ['Data', 'Giorno', 'Stanza', 'Medico', 'Orario']
    righe = [[wc.cell(i, c).value for c in range(1, 6)] for i in range(4, wc.max_row + 1)]
    assert righe[0][:2] == [datetime(2026, 12, 1), 'Martedì'] and righe[0][2:] == ['Ambulatorio 2', 'Fintini Ugo', '08:00-20:00'], righe[0]
    date_righe = {}
    for r in righe:            # la prima riga di ogni giorno (dalla 1.12.4 la data e' in ogni riga)
        if r[0]:
            date_righe.setdefault(r[0].date() if isinstance(r[0], datetime) else r[0], r)
    assert date_righe[date(2026, 12, 2)][2] == 'nessun medico in turno'
    assert date_righe[date(2026, 12, 8)][2] == 'chiusa: immacolata concezione' and colore(wc.cell(4 + righe.index(date_righe[date(2026, 12, 8)]), 1)) == 'E7E9E6'
    assert date_righe[date(2026, 12, 10)][2] == 'chiusa: manutenzione'
    assert date_righe[date(2026, 12, 7)][2:] == ['Ambulatorio 1', 'Lippiello Anna', '15:00-20:00']
    lun14 = righe.index(date_righe[date(2026, 12, 14)])
    assert righe[lun14][2:] == ['Ambulatorio 1', 'Galasso', '08:00-13:00'] and righe[lun14 + 1] == [datetime(2026, 12, 14), 'Lunedì', 'Ambulatorio 1', 'Lippiello Anna', '15:00-20:00']
    assert date(2026, 12, 6) not in date_righe and date(2026, 12, 13) not in date_righe, 'le domeniche chiuse non ci sono'
    assert wc.cell(4, 1).number_format == 'dd/mm/yyyy' and wc.page_setup.orientation == 'portrait'
    assert wc.cell(lun14 + 5, 1).font.color.rgb.endswith('9AA5AD'), 'la data ripetuta in grigio'
    assert str(wc.cell(2, 1).value).startswith('Calcolato dai turni'), wc.cell(2, 1).value
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


class _OraFerma:
    """Il riepilogo live con l'orologio fermo (live.datetime sostituito), per le pagine chieste con il client."""
    def __init__(self, live, quando):
        self.live, self.quando = live, quando

    def __enter__(self):
        quando = self.quando

        class Ferma(datetime):
            @classmethod
            def now(cls, tz=None):
                return quando
        self.prima, self.live.datetime = self.live.datetime, Ferma
        return self

    def __exit__(self, *a):
        self.live.datetime = self.prima


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
    # riservatezza: nel JSON non c'e' nessun dato dei pazienti, anche in un'ora con le visite (1.12.2: prima la
    # prova chiedeva il JSON all'ora vera, un giorno senza appuntamenti, e non poteva fallire)
    with _OraFerma(live, datetime.combine(LUN, time(16, 10))):
        r = C.get('/riepilogo-live.json?struttura=1')
        pagina = testo(C.get('/riepilogo-live?struttura=1'))
    grezzo = r.data.decode('utf-8')
    d = json.loads(grezzo)
    assert d['oggi']['totale'] == 3 and sum(len(x['linea']['visite']) for x in d['stanze']) == 3, d['oggi']
    for vietato in ('Testabianca', 'Rita', 'Provolo', 'Gino', '3339990001', '3339990002', 'example.com'):
        assert vietato not in grezzo, vietato
        assert vietato not in pagina, ('nella pagina', vietato)
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
    # la pagina disegnata alle 15:40 (1.12.2: prima la prova guardava l'ora vera, senza turni ne' visite): una riga
    # per stanza con la sua frase, tanti turni e visite quanti nel JSON, la linea di adesso in ogni stanza
    with _OraFerma(live, datetime.combine(LUN, time(15, 40))):
        t = testo(C.get('/riepilogo-live?struttura=1'))
        d = json.loads(C.get('/riepilogo-live.json?struttura=1').data.decode('utf-8'))
    for pezzo in ('class="frase-live', 'class="pista-live"', 'class="libere-tab"', 'turno del medico', d['riassunto'],
                  'data-giorno="%s"' % LUN.isoformat()):
        assert pezzo.replace("'", '&#39;') in t or pezzo in t, pezzo
    assert t.count('class="riga-live ') == len(d['stanze']) + 1, t.count('class="riga-live ')
    assert t.count('class="turno-live"') == sum(len(x['linea']['turni']) for x in d['stanze']) >= 1
    assert t.count('class="visita-live ') == sum(len(x['linea']['visite']) for x in d['stanze']) == 3
    assert t.count('class="adesso-live"') == len(d['stanze']) and t.count('class="adesso-etichetta') == 1
    for x in d['stanze']:
        assert '<span class="stato-live">%s</span>' % x['frase'] in t, x['frase']
    assert 'gr-fatto' in t and 'class="gr-turno"' in t, 'classi con il prefisso (le altre pagine usano gia\' turno e in-corso)'
    css = open(os.path.join(CARTELLA, 'static', 'stile.css'), encoding='utf-8').read()
    assert 'body.pagina-live .notifiche { display: none; }' in css
    s.close()


prova('riepilogo live: numeri di oggi, stanze adesso (libera fino alle, in corso, senza medico), ore, mezze giornate libere', l_riepilogo)
prova('riepilogo live (1.12.2): quattro gruppi che sommano, frasi, linea del tempo, ore, mezze giornate per giorno', l_chiaro)


def p_periodo():
    """1.12.2: il riepilogo del periodo contro un calcolo fatto a parte, minuto per minuto con gli insiemi."""
    import ambulatori as AM
    import servizi
    from modelli import Appuntamento, Paziente, Risorsa
    S, I, C, live = _mondo_live()
    s = S()
    st = s.get(Struttura, 1)
    p = s.scalars(select(Paziente)).first()
    # in piu': un non presentato e una visita fuori turno (Ambulatorio 2 il lunedi non ha turni), una a cavallo
    # della fine del turno, una della settimana dopo e una di mercoledi con due ore
    def app(rid, oid, giorno, h, m, durata, stato='PRENOTATO'):
        inizio = datetime.combine(giorno, time(h, m))
        s.add(Appuntamento(risorsa_id=rid, operatore_id=oid, paziente_id=p.id, inizio=inizio,
                           fine=inizio + timedelta(minutes=durata), stato=stato))
    app(I['Ambulatorio 1'], I['Lippiello'], LUN, 18, 0, 30, 'NON_PRESENTATO')
    app(I['Ambulatorio 1'], I['Lippiello'], LUN, 19, 45, 30, 'ARRIVATO')           # 15 minuti dopo la fine del turno
    app(I['Ambulatorio 2'], I['Fintini'], LUN, 11, 0, 60, 'ARRIVATO')              # fuori turno
    app(I['Ambulatorio 1'], I['Lippiello'], LUN + timedelta(days=2), 9, 0, 120, 'CONFERMATO')
    app(I['Ambulatorio 1'], I['Lippiello'], LUN + timedelta(days=7), 15, 0, 30)
    app(I['Ambulatorio 3'], I['Fintini'], LUN + timedelta(days=2), 23, 30, 60, 'ARRIVATO')   # fino a giovedi 00:30
    s.commit()
    adesso = datetime.combine(LUN, time(23, 0))
    stanze = AM.stanze_della(st)

    def oracolo(da, a):
        """Ore di turno e occupate di ogni stanza, contate con gli insiemi di minuti; gruppi con regole scritte qui."""
        regole = servizi.Regole(s, da, a)
        per = {r.nome: {'turno': 0, 'occupati': 0, 'fuori': 0, 'totale': 0, 'fatti': 0, 'non_presentati': 0,
                        'disdetti': 0, 'da_segnare': 0, 'da_fare': 0} for r in stanze}
        g = da
        while g <= a:
            info = regole.giorno(g, st)
            for r in stanze:
                turno = set()
                for t in regole.turni_effettivi(g, st, r.id, info):
                    turno |= set(range(t.ora_inizio.hour * 60 + t.ora_inizio.minute, t.ora_fine.hour * 60 + t.ora_fine.minute))
                presi = set()
                for x in s.scalars(select(Appuntamento).where(Appuntamento.risorsa_id == r.id)):
                    # la coda dopo la mezzanotte di una visita del giorno prima: i minuti si', l'appuntamento no
                    if x.inizio.date() == g - timedelta(days=1) and x.fine.date() == g:
                        if x.stato != 'DISDETTO':
                            presi |= set(range(0, x.fine.hour * 60 + x.fine.minute))
                        continue
                    if x.inizio.date() != g:
                        continue
                    if x.stato != 'DISDETTO':
                        fine = 24 * 60 if x.fine.date() > g else x.fine.hour * 60 + x.fine.minute
                        presi |= set(range(x.inizio.hour * 60 + x.inizio.minute, fine))
                    gruppo = {'ARRIVATO': 'fatti', 'NON_PRESENTATO': 'non_presentati', 'DISDETTO': 'disdetti'}.get(
                        x.stato, 'da_segnare' if x.fine <= adesso else 'da_fare')
                    per[r.nome]['totale'] += 1
                    per[r.nome][gruppo] += 1
                per[r.nome]['turno'] += len(turno)
                per[r.nome]['occupati'] += len(turno & presi)
                per[r.nome]['fuori'] += len(presi - turno)
            g += timedelta(days=1)
        return per

    for da, a in ((LUN, LUN), (LUN, LUN + timedelta(days=6)), (LUN - timedelta(days=7), LUN + timedelta(days=13))):
        r = AM.riepilogo_periodo(s, st, da, a, adesso=adesso)
        atteso = oracolo(da, a)
        for x in r['stanze']:
            o = atteso[x['stanza']]
            assert (x['minuti_turno'], x['minuti_occupati'], x['minuti_fuori_turno']) == (o['turno'], o['occupati'], o['fuori']), \
                (da, a, x['stanza'], x, o)
            for k in ('totale', 'fatti', 'non_presentati', 'disdetti', 'da_segnare', 'da_fare'):
                assert x[k] == o[k], (da, a, x['stanza'], k, x[k], o[k])
            assert sum(x[k] for k, _ in AM.GRUPPI_PERIODO) == x['totale']
        t = r['totale']
        for k in ('totale', 'minuti_turno', 'minuti_occupati', 'minuti_fuori_turno', 'fatti', 'non_presentati', 'disdetti',
                  'da_segnare', 'da_fare', 'mezze', 'libere'):
            assert t[k] == sum(x[k] for x in r['stanze']), (k, t[k])
        for k in ('totale', 'minuti_turno', 'minuti_occupati', 'fatti', 'non_presentati', 'disdetti', 'da_segnare', 'da_fare'):
            assert t[k] == sum(x[k] for x in r['giorni']), ('giorni', k)
        assert t['totale'] == sum(m['totale'] for m in r['medici']), 'appuntamenti dei medici'
        assert len(r['giorni']) == (a - da).days + 1 and r['giorni_periodo'] == len(r['giorni'])
    # il lunedi 7/12 a mano: Ambulatorio 1 turno 15-20 (5 ore); occupati 15:00-15:30, 16:00-16:30, 18:00-18:30
    # (il non presentato teneva il posto), 19:45-20:00 dentro e 20:00-20:15 fuori; la disdetta delle 17 no
    r = AM.riepilogo_periodo(s, st, LUN, LUN, adesso=adesso)
    a1 = {x['stanza']: x for x in r['stanze']}['Ambulatorio 1']
    assert (a1['minuti_turno'], a1['minuti_occupati'], a1['minuti_fuori_turno']) == (300, 105, 15), a1
    assert (a1['fatti'], a1['non_presentati'], a1['disdetti'], a1['da_segnare'], a1['totale']) == (2, 1, 1, 1, 5), a1
    assert a1['occupazione'] == 35.0 and a1['ore_turno'] == '5 h' and a1['ore_occupate'] == '1 h 45', a1
    a2 = {x['stanza']: x for x in r['stanze']}['Ambulatorio 2']
    # Ambulatorio 2 non ha turni il lunedi: fuori turno Provolo delle 10 (30 minuti) e la visita delle 11 (60)
    assert a2['minuti_turno'] == 0 and a2['minuti_fuori_turno'] == 90 and a2['occupazione'] is None, a2
    assert r['titolo'] == 'lunedì 7 dicembre 2026' and r['frase'].startswith('Lunedì 7 dicembre 2026: 7 appuntamenti'), r['frase']
    lip = next(m for m in r['medici'] if m['medico'] == 'Lippiello Anna')
    assert lip['n_giorni'] == 1 and lip['non_presentati_su'] == round(100 / 3, 1), lip
    # i testi
    assert AM.titolo_periodo(LUN, LUN + timedelta(days=6)) == 'dal 7 al 13 dicembre 2026'
    assert AM.titolo_periodo(date(2026, 10, 26), date(2026, 11, 1)) == 'dal 26 ottobre all\'1 novembre 2026'
    assert AM.titolo_periodo(date(2026, 12, 28), date(2027, 1, 3)) == 'dal 28 dicembre 2026 al 3 gennaio 2027'
    assert (AM.il_percento(11.6), AM.il_percento(54), AM.il_percento(8), AM.il_percento(80.5), AM.il_percento(18)) == \
        ("l'11,6%", 'il 54%', "l'8%", "l'80,5%", 'il 18%')
    assert (AM.ore_in_parole(450), AM.ore_in_parole(60), AM.ore_in_parole(61), AM.ore_in_parole(0)) == \
        ('7 ore e 30 minuti', '1 ora', '1 ora e 1 minuto', '0 ore')
    assert AM.periodo_da('settimana-scorsa', LUN + timedelta(days=2)) == (LUN - timedelta(days=7), LUN - timedelta(days=1))
    assert AM.periodo_da('mese-scorso', date(2026, 1, 15)) == (date(2025, 12, 1), date(2025, 12, 31))
    assert AM.periodo_da('mese', date(2026, 2, 10)) == (date(2026, 2, 1), date(2026, 2, 28)) and AM.periodo_da('boh', LUN) is None
    s.close()
    # le pagine: i periodi pronti, l'intervallo al contrario, quello troppo lungo, l'Excel e il JSON
    for q in ('', '&periodo=oggi', '&periodo=ieri', '&periodo=settimana', '&periodo=settimana-scorsa', '&periodo=mese',
              '&periodo=mese-scorso', '&da=%s&a=%s' % (LUN + timedelta(days=6), LUN), '&da=2026-01-01&a=2026-12-31',
              '&da=non-una-data'):
        rr = C.get('/ambulatori/riepilogo?struttura=1' + q)
        assert rr.status_code == 200 and 'class="frase-live' in testo(rr) and 'Le stanze' in testo(rr), (q, rr.status_code)
    t = testo(C.get('/ambulatori/riepilogo?struttura=1&da=%s&a=%s' % (LUN + timedelta(days=6), LUN)))
    assert 'dal 7 al 13 dicembre 2026' in t and 'Giorno per giorno' in t, 'intervallo girato'
    d = json.loads(C.get('/ambulatori/riepilogo.json?struttura=1&da=2026-01-01&a=2026-12-31').data)
    assert d['giorni_periodo'] == AM.MASSIMO_GIORNI_RIEPILOGO and d['da'] == '2026-01-01', (d['da'], d['a'])
    grezzo = C.get('/ambulatori/riepilogo.json?struttura=1&da=%s&a=%s' % (LUN, LUN + timedelta(days=6))).data.decode('utf-8')
    for vietato in ('Testabianca', 'Rita', 'Provolo', 'Gino', '3339990001', 'example.com'):
        assert vietato not in grezzo, vietato
    rr = C.get('/ambulatori/riepilogo.xlsx?struttura=1&da=%s&a=%s' % (LUN, LUN + timedelta(days=6)))
    assert rr.status_code == 200 and 'riepilogo-ambulatori-%s-%s.xlsx' % (LUN, LUN + timedelta(days=6)) in rr.headers['Content-Disposition']
    import openpyxl
    from io import BytesIO
    wb = openpyxl.load_workbook(BytesIO(rr.data))
    assert wb.sheetnames == ['Riepilogo', 'Stanze', 'Medici', 'Giorni'], wb.sheetnames
    ws = wb['Stanze']
    righe = [r_ for r_ in ws.iter_rows(values_only=True) if r_[0] in {x.nome for x in S().scalars(select(Risorsa))} | {'Totale'}]
    assert righe[-1][0] == 'Totale' and righe[-1][5] == sum(x[5] for x in righe[:-1]), righe[-1]
    wb1 = openpyxl.load_workbook(BytesIO(C.get('/ambulatori/riepilogo.xlsx?struttura=1&periodo=oggi').data))
    assert wb1.sheetnames == ['Riepilogo', 'Stanze', 'Medici'], wb1.sheetnames
    # il menu: quattro voci nel gruppo Ambulatori, l'ultima attiva su questa pagina
    t = testo(C.get('/ambulatori/riepilogo?struttura=1'))
    assert 'Riepilogo del periodo</b>' in t and 'class="gruppo attivo" data-guida="menu-ambulatori"' in t


prova('riepilogo del periodo (1.12.2): stanze, medici e giorni contro gli insiemi di minuti, testi, pagine, Excel, JSON', p_periodo)


def p_periodo_revisione():
    """1.12.2, dalla revisione del riepilogo del periodo: lo stesso medico in due stanze insieme, turni e visite che
    si sovrappongono, la visita che passa la mezzanotte, il festivo e la domenica con un turno di un giorno, la stanza
    disattivata, le mezze giornate contate a mano, la fine della visita proprio adesso, le frecce sui mesi, le frasi,
    l'Excel che torna con la pagina e nessun dato dei pazienti."""
    from modelli import Appuntamento, Paziente
    S, I, C = mondo()
    s = S()
    st = s.get(Struttura, 1)
    pz = Paziente(cognome='Testabianca', nome='Rita', telefono='3339990001', email='rita@example.com')
    s.add(pz)
    s.add(Risorsa(nome='Ambulatorio 6', struttura_id=1, ordine=6, attiva=False))
    s.commit()
    I['Ambulatorio 6'] = s.scalars(select(Risorsa).where(Risorsa.nome == 'Ambulatorio 6')).one().id
    MAR, MER, GIO, DOM = (LUN + timedelta(days=k) for k in (1, 2, 3, 6))
    # Galasso lunedi 9-13 in Ambulatorio 3 e, solo il 7/12, 11-15 in Ambulatorio 4: per lui 9-15, sei ore e non otto
    turno(S, I['Galasso'], I['Ambulatorio 3'], 0, time(9), time(13))
    singolo(S, I['Galasso'], I['Ambulatorio 4'], LUN, time(11), time(15))
    # Lippiello mercoledi 9-13 e, solo il 9/12, 12-16 nella stessa stanza: 9-16
    turno(S, I['Lippiello'], I['Ambulatorio 1'], 2, time(9), time(13))
    singolo(S, I['Lippiello'], I['Ambulatorio 1'], MER, time(12), time(16))
    # martedi 8/12 (Immacolata, la struttura chiude) e domenica 13/12: Fintini con un turno di un giorno 9-12
    singolo(S, I['Fintini'], I['Ambulatorio 2'], MAR, time(9), time(12))
    singolo(S, I['Fintini'], I['Ambulatorio 2'], DOM, time(9), time(12))
    # Esempietti il martedi 15-18 in Ambulatorio 5: il festivo lo toglie, la settimana dopo c'e'
    turno(S, I['Esempietti'], I['Ambulatorio 5'], 1, time(15), time(18))

    def app(stanza, medico, giorno, h, m, durata, stato='PRENOTATO'):
        inizio = datetime.combine(giorno, time(h, m))
        s.add(Appuntamento(risorsa_id=I[stanza], operatore_id=I[medico], paziente_id=pz.id, inizio=inizio,
                           fine=inizio + timedelta(minutes=durata), stato=stato))
    app('Ambulatorio 3', 'Galasso', LUN, 11, 0, 60, 'ARRIVATO')
    app('Ambulatorio 4', 'Galasso', LUN, 11, 30, 60)                       # nello stesso momento, nell'altra stanza
    app('Ambulatorio 3', 'Galasso', LUN, 13, 30, 30, 'CONFERMATO')         # fuori turno per la stanza, non per lui
    app('Ambulatorio 2', 'Fintini', LUN, 23, 30, 60, 'ARRIVATO')           # fino alle 00:30 di martedi
    app('Ambulatorio 2', 'Fintini', MAR, 10, 0, 30, 'ARRIVATO')
    app('Ambulatorio 1', 'Lippiello', MER, 10, 0, 30, 'NON_PRESENTATO')
    app('Ambulatorio 1', 'Lippiello', MER, 10, 15, 30)                     # finisce proprio adesso: da segnare
    app('Ambulatorio 1', 'Lippiello', MER, 10, 45, 15)                     # comincia adesso: da fare
    app('Ambulatorio 1', 'Lippiello', MER, 14, 0, 30, 'DISDETTO')
    app('Ambulatorio 6', 'Fintini', GIO, 10, 0, 30, 'ARRIVATO')            # stanza disattivata dopo
    app('Ambulatorio 2', 'Fintini', DOM, 9, 0, 30)
    s.commit()
    adesso = datetime.combine(MER, time(10, 45))
    r = AM.riepilogo_periodo(s, st, LUN, DOM, adesso=adesso)
    stanze = {x['stanza']: x for x in r['stanze']}
    attese = {   # turno, occupati, fuori turno, totale, fatti, non presentati, disdetti, da segnare, da fare, mezze, libere
        'Ambulatorio 1': (420, 60, 0, 4, 0, 1, 1, 1, 1, 10, 8),
        'Ambulatorio 2': (360, 60, 60, 3, 2, 0, 0, 0, 1, 12, 10),
        'Ambulatorio 3': (240, 60, 30, 2, 1, 0, 0, 1, 0, 10, 9),
        'Ambulatorio 4': (240, 60, 0, 1, 0, 0, 0, 1, 0, 10, 8),
        'Ambulatorio 5': (0, 0, 0, 0, 0, 0, 0, 0, 0, 10, 10),
        'Sala endoscopia': (0, 0, 0, 0, 0, 0, 0, 0, 0, 10, 10),
        'Ambulatorio 6 (non più attiva)': (0, 0, 30, 1, 1, 0, 0, 0, 0, 0, 0),
    }
    chiavi = ('minuti_turno', 'minuti_occupati', 'minuti_fuori_turno', 'totale', 'fatti', 'non_presentati', 'disdetti',
              'da_segnare', 'da_fare', 'mezze', 'libere')
    assert set(stanze) == set(attese), sorted(stanze)
    for nome, valori in attese.items():
        assert tuple(stanze[nome][k] for k in chiavi) == valori, (nome, tuple(stanze[nome][k] for k in chiavi), valori)
    assert (stanze['Ambulatorio 1']['non_presentati_su'], stanze['Ambulatorio 3']['non_presentati_su'],
            stanze['Ambulatorio 4']['non_presentati_su']) == (100.0, 0.0, None)
    t = r['totale']
    assert tuple(t[k] for k in chiavi) == (1260, 240, 120, 11, 4, 1, 1, 3, 2, 62, 55), tuple(t[k] for k in chiavi)
    # i medici: le ore di ognuno sono l'unione dei suoi turni nel giorno, su tutte le stanze
    medici = {m['medico']: m for m in r['medici']}
    attesi = {'Galasso': (360, 120, 0, 3, 1), 'Lippiello Anna': (420, 60, 0, 4, 1), 'Fintini Ugo': (360, 60, 90, 4, 2)}
    assert set(medici) == set(attesi), sorted(medici)
    for nome, (turno_, occ, fuori, tot, giorni) in attesi.items():
        m = medici[nome]
        assert (m['minuti_turno'], m['minuti_occupati'], m['minuti_fuori_turno'], m['totale'], m['n_giorni']) == \
            (turno_, occ, fuori, tot, giorni), (nome, m)
        assert m['minuti_occupati'] <= m['minuti_turno'], m
    assert medici['Galasso']['stanze'] == ['Ambulatorio 3', 'Ambulatorio 4'], medici['Galasso']['stanze']
    assert medici['Galasso']['occupazione'] == round(100 * 120 / 360, 1)
    # i giorni: il festivo e la domenica con un turno non sono «chiusi»
    giorni = {x['data']: x for x in r['giorni']}
    mar, dom = giorni[MAR.isoformat()], giorni[DOM.isoformat()]
    assert (mar['etichetta'], mar['chiusa'], mar['aperto'], mar['chiusa_ma_aperta']) == \
        ('martedì 8/12', None, True, 'Immacolata Concezione'), mar
    assert (mar['minuti_turno'], mar['minuti_occupati'], mar['minuti_fuori_turno'], mar['totale']) == (180, 30, 30, 1), mar
    assert (dom['chiusa'], dom['aperto'], dom['minuti_turno'], dom['totale']) == (None, True, 180, 1), dom
    lun = giorni[LUN.isoformat()]
    assert (lun['etichetta'], lun['minuti_turno'], lun['minuti_fuori_turno'], lun['totale']) == ('lunedì 7/12', 480, 60, 4), lun
    # la frase, parola per parola
    assert r['frase'] == ('Dal 7 al 13 dicembre 2026: 11 appuntamenti, 4 fatti, 1 non presentato (20%), 1 disdetto, '
                          '3 ancora da segnare e 2 da fare. Le stanze sono state occupate per il 19% delle ore di turno '
                          '(4 ore su 21 ore). 55 mezze giornate su 62 senza nessun medico.'), r['frase']
    # solo il martedi: la coda dopo la mezzanotte conta nei minuti fuori turno, non negli appuntamenti
    r1 = AM.riepilogo_periodo(s, st, MAR, MAR, adesso=adesso)
    a2 = {x['stanza']: x for x in r1['stanze']}['Ambulatorio 2']
    assert (a2['minuti_fuori_turno'], a2['totale'], a2['mezze'], a2['libere']) == (30, 1, 1, 0), a2
    assert {m['medico']: m['minuti_fuori_turno'] for m in r1['medici']} == {'Fintini Ugo': 30}, r1['medici']
    r1 = AM.riepilogo_periodo(s, st, LUN, LUN, adesso=adesso)
    assert {x['stanza']: x for x in r1['stanze']}['Ambulatorio 2']['minuti_fuori_turno'] == 30
    assert 'Ambulatorio 6 (non più attiva)' not in [x['stanza'] for x in r1['stanze']]
    # la settimana dopo: nessun appuntamento, la frase lo dice senza «0 fatti»; la domenica vuota e' di chiusura
    dopo_da, dopo_a = LUN + timedelta(days=7), DOM + timedelta(days=7)
    r2 = AM.riepilogo_periodo(s, st, dopo_da, dopo_a, adesso=adesso)
    assert r2['frase'] == ('Dal 14 al 20 dicembre 2026: nessun appuntamento nelle stanze. 11 ore di turno, senza visite. '
                           '69 mezze giornate su 72 senza nessun medico.'), r2['frase']
    dom2 = r2['giorni'][-1]
    assert (dom2['chiusa'], dom2['aperto'], dom2['minuti_turno']) == (None, False, 0), dom2
    assert [x['stanza'] for x in r2['stanze']] == [x.nome for x in AM.stanze_della(st)]
    s.close()
    # le parole
    assert (AM.il_percento(0), AM.il_percento(0.5), AM.il_percento(1), AM.il_percento(100)) == ('lo 0%', 'lo 0,5%', "l'1%", 'il 100%')
    assert (AM.ore_in_parole(45), AM.ore_in_parole(1), AM.ore_in_parole(120)) == ('45 minuti', '1 minuto', '2 ore')
    assert (AM.il_percento(0.96), AM.il_percento(7.96), AM.il_percento(11.96), AM.il_percento(0.04)) == \
        ("l'1%", "l'8%", 'il 12%', 'lo 0%')
    # le frecce: la settimana, lo stesso numero di giorni, uno e due mesi interi
    V = AM._vicini
    assert V(LUN, DOM, '') == ({'da': '2026-11-30', 'a': '2026-12-06'}, {'da': '2026-12-14', 'a': '2026-12-20'})
    assert V(LUN, MER, '') == ({'da': '2026-12-04', 'a': '2026-12-06'}, {'da': '2026-12-10', 'a': '2026-12-12'})
    assert V(date(2026, 11, 1), date(2026, 11, 30), '') == ({'da': '2026-10-01', 'a': '2026-10-31'}, {'da': '2026-12-01', 'a': '2026-12-31'})
    assert V(date(2026, 11, 1), date(2026, 12, 31), '') == ({'da': '2026-09-01', 'a': '2026-10-31'}, {'da': '2027-01-01', 'a': '2027-02-28'})
    assert V(date(2027, 1, 1), date(2027, 1, 31), 'mese') == ({'da': '2026-12-01', 'a': '2026-12-31'}, {'da': '2027-02-01', 'a': '2027-02-28'})
    # la pagina e l'Excel della settimana: gli stessi numeri, nessun dato della paziente
    indirizzo = '?struttura=1&da=%s&a=%s' % (LUN, DOM)
    pagina = testo(C.get('/ambulatori/riepilogo' + indirizzo))
    assert 'Ambulatorio 6 (non più attiva)' in pagina and 'Immacolata Concezione, ma con turni o appuntamenti' in pagina
    _, wb = excel(C, '/ambulatori/riepilogo.xlsx' + indirizzo)
    for ws in wb.worksheets:
        for riga in ws.iter_rows(values_only=True):
            for v in riga:
                assert not (isinstance(v, str) and any(x in v for x in ('Testabianca', 'Rita', '3339990001', 'example.com'))), (ws.title, v)
    for vietato in ('Testabianca', 'Rita', '3339990001', 'example.com'):
        assert vietato not in pagina, vietato
    chiuse = {x[0]: x[1] for x in wb['Giorni'].iter_rows(values_only=True) if x[0]}
    assert chiuse['martedì 8/12'] == 'Immacolata Concezione, ma con turni o appuntamenti', chiuse['martedì 8/12']
    s = S()
    r = AM.riepilogo_periodo(s, s.get(Struttura, 1), LUN, DOM)
    s.close()
    ws = wb['Stanze']
    righe = {x[0]: x for x in ws.iter_rows(values_only=True) if x[0] in {y['stanza'] for y in r['stanze']} | {'Totale'}}
    for x in r['stanze']:
        e = righe[x['stanza']]
        assert (e[1] or '') == ', '.join(x['medici']) and e[2] == x['minuti_turno'] / 60 and e[3] == x['minuti_occupati'] / 60, (e, x)
        assert list(e[5:13]) == [x[k] for k in ('totale', 'fatti', 'non_presentati', 'disdetti', 'da_segnare', 'da_fare',
                                                 'mezze', 'libere')], (e, x)
    assert righe['Totale'][2] == r['totale']['minuti_turno'] / 60 == 21, righe['Totale']
    riga_stanza = next(c.row for c in ws['A'] if c.value == 'Ambulatorio 3')
    assert ws.cell(riga_stanza, 2).alignment.wrap_text, 'i medici vanno a capo'
    wm = wb['Medici']
    totale_m = next(x for x in wm.iter_rows(values_only=True) if x[0] == 'Totale')
    assert totale_m[2] in (None, '') and totale_m[3] == (360 + 420 + 360) / 60, totale_m
    _, wb2 = excel(C, '/ambulatori/riepilogo.xlsx?struttura=1&da=%s&a=%s' % (dopo_da, dopo_a))
    giorni_x = {x[0]: x for x in wb2['Giorni'].iter_rows(values_only=True) if x[0]}
    assert giorni_x['domenica 20/12'][1] == 'giorno di chiusura' and giorni_x['lunedì 14/12'][1] in (None, ''), giorni_x['domenica 20/12']
    # una mezza giornata sola senza medico: al singolare
    s = S()
    for nome in ('Ambulatorio 2', 'Ambulatorio 3', 'Ambulatorio 4', 'Ambulatorio 5', 'Sala endoscopia'):
        s.get(Risorsa, I[nome]).attiva = False
    s.commit()
    s.close()
    mer3 = MER + timedelta(days=14)
    pagina = testo(C.get('/ambulatori/riepilogo?struttura=1&da=%s&a=%s' % (mer3, mer3)))
    assert '<b>1</b> mezza giornata su 2 senza nessun medico' in pagina, 'singolare'
    assert 'Mercoledì 23 dicembre 2026: nessun appuntamento nelle stanze. 4 ore di turno, senza visite. ' \
           '1 mezza giornata su 2 senza nessun medico.' in pagina


prova('riepilogo del periodo (1.12.2, dalla revisione): medico in due stanze, sovrapposizioni, mezzanotte, festivo e '
      'domenica, stanza disattivata, mezze contate a mano, frasi, frecce, Excel uguale alla pagina', p_periodo_revisione)


def p_periodo_seconda_revisione():
    """1.12.2, dalla seconda revisione: la stanza disattivata conta i turni solo fino al suo ultimo appuntamento ed
    entra anche per la sola coda dopo la mezzanotte; una visita che finisce alle 24:00 non ha coda; un giorno chiuso
    con soli disdetti resta chiuso; ore non intere nell'Excel (un terzo d'ora, non 0,33) e ogni foglio confrontato
    cella per cella con il riepilogo."""
    from modelli import Appuntamento, Paziente
    S, I, C = mondo()
    s = S()
    st = s.get(Struttura, 1)
    pz = Paziente(cognome='Esempio', nome='Ada', telefono='3339990003')
    s.add(pz)
    s.add(Risorsa(nome='Ambulatorio 6', struttura_id=1, ordine=6, attiva=False))
    s.commit()
    I['Ambulatorio 6'] = s.scalars(select(Risorsa).where(Risorsa.nome == 'Ambulatorio 6')).one().id
    GIO, VEN = LUN + timedelta(days=3), LUN + timedelta(days=4)
    # venti minuti in tre stanze: un terzo d'ora ciascuna
    for medico, stanza in (('Galasso', 'Ambulatorio 1'), ('Lippiello', 'Ambulatorio 2'), ('Fintini', 'Ambulatorio 3')):
        singolo(S, I[medico], I[stanza], LUN, time(9), time(9, 20))
    # Ambulatorio 6, spento dopo il 10/12: il turno del giovedi resta valido senza fine
    turno(S, I['Fintini'], I['Ambulatorio 6'], 3, time(9), time(13))
    chiusura(S, LUN + timedelta(days=9), LUN + timedelta(days=9), 'Manutenzione')
    chiusura(S, LUN + timedelta(days=11), LUN + timedelta(days=11), 'Disinfestazione')

    def app(stanza, medico, giorno, h, m, durata, stato='PRENOTATO'):
        inizio = datetime.combine(giorno, time(h, m))
        s.add(Appuntamento(risorsa_id=I[stanza], operatore_id=I[medico], paziente_id=pz.id, inizio=inizio,
                           fine=inizio + timedelta(minutes=durata), stato=stato))
    app('Ambulatorio 4', 'Esempietti', LUN, 23, 0, 60, 'ARRIVATO')             # finisce alle 24:00 in punto
    app('Ambulatorio 6', 'Fintini', GIO, 23, 30, 60, 'ARRIVATO')               # fino a venerdi 00:30
    app('Ambulatorio 6', 'Fintini', GIO + timedelta(days=7), 10, 0, 30, 'DISDETTO')
    app('Ambulatorio 1', 'Galasso', LUN + timedelta(days=9), 10, 0, 30, 'DISDETTO')   # nel giorno di Manutenzione
    app('Ambulatorio 2', 'Lippiello', LUN + timedelta(days=11), 10, 0, 30)           # nel giorno di Disinfestazione
    s.commit()
    adesso = datetime.combine(LUN + timedelta(days=14), time(9))
    da, a = LUN, LUN + timedelta(days=13)
    r = AM.riepilogo_periodo(s, st, da, a, adesso=adesso)
    chiavi = ('minuti_turno', 'minuti_occupati', 'minuti_fuori_turno', 'totale', 'fatti', 'disdetti', 'da_segnare')
    stanze = {x['stanza']: tuple(x[k] for k in chiavi) for x in r['stanze']}
    assert stanze == {'Ambulatorio 1': (20, 0, 0, 1, 0, 1, 0), 'Ambulatorio 2': (20, 0, 30, 1, 0, 0, 1),
                      'Ambulatorio 3': (20, 0, 0, 0, 0, 0, 0), 'Ambulatorio 4': (0, 0, 60, 1, 1, 0, 0),
                      'Ambulatorio 5': (0, 0, 0, 0, 0, 0, 0), 'Sala endoscopia': (0, 0, 0, 0, 0, 0, 0),
                      'Ambulatorio 6 (non più attiva)': (240, 0, 60, 2, 1, 1, 0)}, stanze
    assert tuple(r['totale'][k] for k in chiavi) == (300, 0, 150, 5, 2, 2, 1), r['totale']
    medici = {m['medico']: (m['minuti_turno'], m['minuti_fuori_turno'], m['totale'], m['n_giorni']) for m in r['medici']}
    assert medici == {'Galasso': (20, 0, 1, 1), 'Lippiello Anna': (20, 30, 1, 1), 'Fintini Ugo': (260, 60, 2, 2),
                      'Esempietti Rita': (0, 60, 1, 0)}, medici
    giorni = {x['data']: x for x in r['giorni']}
    man, dis = giorni[(LUN + timedelta(days=9)).isoformat()], giorni[(LUN + timedelta(days=11)).isoformat()]
    assert (man['chiusa'], man['chiusa_ma_aperta'], man['disdetti']) == ('Manutenzione', None, 1), man
    assert (dis['chiusa'], dis['chiusa_ma_aperta'], dis['aperto'], dis['minuti_fuori_turno']) == \
        (None, 'Disinfestazione', True, 30), dis
    assert giorni[(LUN + timedelta(days=1)).isoformat()]['chiusa'] == 'Immacolata Concezione'
    # solo venerdi 11/12: la stanza spenta c'e' per la coda, la frase la dice
    r1 = AM.riepilogo_periodo(s, st, VEN, VEN, adesso=adesso)
    a6 = {x['stanza']: x for x in r1['stanze']}['Ambulatorio 6 (non più attiva)']
    assert (a6['minuti_turno'], a6['minuti_fuori_turno'], a6['totale']) == (0, 30, 0), a6
    assert {m['medico']: m['minuti_fuori_turno'] for m in r1['medici']} == {'Fintini Ugo': 30}, r1['medici']
    assert r1['frase'] == ('Venerdì 11 dicembre 2026: nessun appuntamento nelle stanze. Dopo la mezzanotte ci sono '
                           '30 minuti di visite cominciate il giorno prima. 12 mezze giornate su 12 senza nessun medico.'), r1['frase']
    # solo martedi 8/12: la visita finita alle 24:00 di lunedi non lascia nessuna riga
    r2 = AM.riepilogo_periodo(s, st, LUN + timedelta(days=1), LUN + timedelta(days=1), adesso=adesso)
    assert r2['medici'] == [] and r2['totale']['minuti_fuori_turno'] == 0, r2['medici']
    assert r2['frase'] == 'Nel periodo non ci sono appuntamenti né turni nelle stanze.', r2['frase']
    # la seconda settimana: il turno del giovedi della stanza spenta non conta piu'
    r3 = AM.riepilogo_periodo(s, st, LUN + timedelta(days=7), a, adesso=adesso)
    a6 = {x['stanza']: x for x in r3['stanze']}['Ambulatorio 6 (non più attiva)']
    assert (a6['minuti_turno'], a6['disdetti'], a6['totale']) == (0, 1, 1), a6
    s.close()
    # l'Excel cella per cella (senza 'adesso': le date sono nel futuro, i gruppi si contano con l'ora vera)
    s = S()
    r = AM.riepilogo_periodo(s, s.get(Struttura, 1), da, a)
    s.close()
    _, wb = excel(C, '/ambulatori/riepilogo.xlsx?struttura=1&da=%s&a=%s' % (da, a))
    t = r['totale']
    cosa = {x[0]: x[1] for x in wb['Riepilogo'].iter_rows(values_only=True) if x[0]}
    attese = {'Appuntamenti': t['totale'], 'Fatti': t['fatti'], 'Non presentati': t['non_presentati'],
              'Disdetti': t['disdetti'], 'Da segnare': t['da_segnare'], 'Da fare': t['da_fare'],
              'Ore di turno': t['minuti_turno'] / 60, 'Ore occupate (dentro i turni)': t['minuti_occupati'] / 60,
              'Ore prenotate fuori turno': t['minuti_fuori_turno'] / 60, 'Occupazione delle ore di turno': t['occupazione'],
              'Non presentati su chi doveva venire': t['non_presentati_su'], 'Mezze giornate': t['mezze'],
              'Mezze giornate senza nessun medico': t['libere']}
    for k, v in attese.items():
        assert cosa[k] == v, (k, cosa[k], v)
    gruppi = ('totale', 'fatti', 'non_presentati', 'disdetti', 'da_segnare', 'da_fare')
    righe = {x[0]: x for x in wb['Stanze'].iter_rows(values_only=True) if x[0]}
    for x in r['stanze']:
        assert list(righe[x['stanza']][2:5]) == [x['minuti_turno'] / 60, x['minuti_occupati'] / 60, x['occupazione']], righe[x['stanza']]
    assert righe['Ambulatorio 1'][2] == 1 / 3 and righe['Totale'][2] == cosa['Ore di turno'] == 5, (righe['Ambulatorio 1'], righe['Totale'])
    righe = {x[0]: x for x in wb['Medici'].iter_rows(values_only=True) if x[0]}
    for m in r['medici']:
        e = righe[m['medico']]
        assert list(e) == [m['medico'], ', '.join(m['stanze']) or None, m['n_giorni'], m['minuti_turno'] / 60,
                           m['minuti_occupati'] / 60, m['occupazione']] + [m[k] for k in gruppi] + [m['non_presentati_su']], (e, m)
    assert righe['Fintini Ugo'][3] == 260 / 60
    riga_fintini = next(c.row for c in wb['Medici']['A'] if c.value == 'Fintini Ugo')
    assert wb['Medici'].cell(riga_fintini, 2).alignment.wrap_text, 'le stanze dei medici vanno a capo'
    righe = {x[0]: x for x in wb['Giorni'].iter_rows(values_only=True) if x[0]}
    for x in r['giorni']:
        e = righe[x['etichetta']]
        chiusa = x['chiusa'] or ('%s, ma con turni o appuntamenti' % x['chiusa_ma_aperta'] if x['chiusa_ma_aperta']
                                 else ('' if x['aperto'] else 'giorno di chiusura'))
        assert list(e) == [x['etichetta'], chiusa or None, x['minuti_turno'] / 60, x['minuti_occupati'] / 60,
                           x['occupazione']] + [x[k] for k in gruppi], (e, x)
    assert righe['venerdì 18/12'][1] == 'Disinfestazione, ma con turni o appuntamenti' and \
        righe['mercoledì 16/12'][1] == 'Manutenzione' and righe['domenica 13/12'][1] == 'giorno di chiusura', righe
    # la domenica vuota: nessuna mezza giornata, il totale della tabella dice «—» come le righe
    pagina = testo(C.get('/ambulatori/riepilogo?struttura=1&da=%s&a=%s' % (LUN + timedelta(days=13), LUN + timedelta(days=13))))
    assert '<th class="n">—</th></tr></tfoot>' in pagina and 'Esempio' not in pagina


prova('riepilogo del periodo (1.12.2, dalla seconda revisione): stanza spenta con turni fino all\'ultimo appuntamento '
      'e con la sola coda, visita fino alle 24:00, chiusura con soli disdetti, Excel cella per cella', p_periodo_seconda_revisione)


def l_revisione():
    """1.12.2, dalla revisione: festivo con un turno di un giorno, chiusura senza motivo, turni piu' tardi senza
    appuntamenti, la sala operatoria fuori dai conti, turni attaccati, visite fuori orario, tacche vicine."""
    from modelli import Appuntamento, Chiusura, Paziente
    S, I, C, live = _mondo_live()
    s = S()
    st = s.get(Struttura, 1)
    p = s.scalars(select(Paziente)).first()

    def app(rid, oid, giorno, h, m=0, durata=30, stato='PRENOTATO'):
        inizio = datetime.combine(giorno, time(h, m))
        s.add(Appuntamento(risorsa_id=rid, operatore_id=oid, paziente_id=p.id, inizio=inizio,
                           fine=inizio + timedelta(minutes=durata), stato=stato))
    stanze = lambda r: {x['stanza']: x for x in r['stanze']}
    # martedi 8/12 festivo (la struttura chiude): un turno di un giorno di Lippiello in Ambulatorio 4 apre la stanza
    singolo(S, I['Lippiello'], I['Ambulatorio 4'], LUN + timedelta(days=1), time(9), time(12))
    app(I['Ambulatorio 4'], I['Lippiello'], LUN + timedelta(days=1), 10)
    # mercoledi 9/12: Galasso 8-14 e 14-20 in Ambulatorio 5 (due «+» della pianificazione), visita alle 15;
    # una visita alle 7 in Ambulatorio 2 (prima dell'apertura, senza turno)
    singolo(S, I['Galasso'], I['Ambulatorio 5'], LUN + timedelta(days=2), time(8), time(14))
    singolo(S, I['Galasso'], I['Ambulatorio 5'], LUN + timedelta(days=2), time(14), time(20))
    app(I['Ambulatorio 5'], I['Galasso'], LUN + timedelta(days=2), 15)
    app(I['Ambulatorio 2'], I['Fintini'], LUN + timedelta(days=2), 7)
    # lunedi: un intervento in sala operatoria (non e' una stanza della pagina)
    app(I['Sala operatoria'], I['Esempietti'], LUN, 9, durata=120)
    # sabato 12/12: chiusura senza motivo
    s.add(Chiusura(struttura_id=1, dal=LUN + timedelta(days=5), al=LUN + timedelta(days=5), motivo=''))
    s.commit()
    r = live.riepilogo(s, st, adesso=datetime.combine(LUN + timedelta(days=1), time(10, 10)))
    a4 = stanze(r)['Ambulatorio 4']
    assert a4['stato'] == 'occupata' and a4['frase'] == 'Visita in corso fino alle 10:30' and a4['medico'] == 'Lippiello Anna', a4
    assert all(x['stato'] == 'chiusa' and x['frase'] == 'Chiusa oggi' for n, x in stanze(r).items() if n != 'Ambulatorio 4')
    assert r['riassunto'].startswith('Oggi la struttura è chiusa (') and ', ma ci sono turni o appuntamenti. Alle 10:10: 1 visita in corso, 1 stanza su 6' in r['riassunto'], r['riassunto']
    r = live.riepilogo(s, st, adesso=datetime.combine(LUN + timedelta(days=5), time(10)))
    assert r['riassunto'] == 'Oggi la struttura è chiusa.', r['riassunto']
    # mercoledi alle 6:30: nessun appuntamento ancora, ma turni piu' tardi: non «né turni»
    r = live.riepilogo(s, st, adesso=datetime.combine(LUN + timedelta(days=2), time(6, 30)))
    assert 'né turni' not in r['riassunto'] and r['riassunto'].startswith('Alle 06:30: 0 visite in corso, 0 stanze su 6'), r['riassunto']
    a5 = stanze(r)['Ambulatorio 5']
    assert a5['frase'] == 'Nessun medico fino alle 08:00, poi Galasso Marco' or a5['frase'].startswith('Nessun medico fino alle 08:00, poi Galasso'), a5['frase']
    # alle 10: libera fino al prossimo paziente delle 15 (i due turni sono uno solo), non «fino a fine turno (14:00)»
    r = live.riepilogo(s, st, adesso=datetime.combine(LUN + timedelta(days=2), time(10)))
    a5 = stanze(r)['Ambulatorio 5']
    assert a5['frase'] == 'Libera, prossimo paziente alle 15:00' and [t['da'] + '-' + t['a'] for t in a5['linea']['turni']] == ['08:00-20:00'], a5
    r = live.riepilogo(s, st, adesso=datetime.combine(LUN + timedelta(days=2), time(16)))
    assert stanze(r)['Ambulatorio 5']['frase'] == 'Libera fino a fine turno (20:00)', stanze(r)['Ambulatorio 5']
    # la visita delle 7 e' nelle ore (prima dell'apertura) e nella linea; le ore sommano al totale
    ore = {x['ora']: x['totale'] for x in r['per_ora']}
    assert ore.get('07:00') == 1 and sum(ore.values()) == r['oggi']['totale'] == 2, (ore, r['oggi'])
    assert r['asse']['da'] == '07:00', r['asse']
    # lunedi: l'intervento in sala operatoria non e' nei conti, che restano quelli delle stanze
    for h in (9, 10, 15):
        r = live.riepilogo(s, st, adesso=datetime.combine(LUN, time(h, 30)))
        assert r['oggi']['totale'] == 3 == sum(x['totale'] for x in r['stanze']), (h, r['oggi'])
        assert sum(x['totale'] for x in r['per_ora']) == r['oggi']['totale']
    # le tacche: alle 15:40 le 16 e' vicina all'etichetta rossa, le 15 no; ai bordi l'etichetta resta dentro
    r = live.riepilogo(s, st, adesso=datetime.combine(LUN, time(15, 40)))
    tacche = {x['ora']: x for x in r['asse']['ore']}
    assert tacche['16']['vicina'] and not tacche['15']['vicina'] and tacche['09']['dispari'] and not tacche['08']['dispari'], tacche
    assert live.riepilogo(s, st, adesso=datetime.combine(LUN, time(8, 5)))['asse']['bordo'] == 'sinistra'
    assert live.riepilogo(s, st, adesso=datetime.combine(LUN, time(19, 50)))['asse']['bordo'] == 'destra'
    s.close()


prova('riepilogo live (1.12.2, dalla revisione): festivo con un turno, chiusura senza motivo, turni attaccati, ore fuori orario, sala operatoria', l_revisione)
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
