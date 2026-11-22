# -*- coding: utf-8 -*-
"""BOZZA per la tappa 6 (non è nel repository): le tre frasi approvate, con 1 e con più.

Le tre funzioni si incollano in prove_14.py (aree «chiusura», «da confermare», «lista d'attesa»), che ha già
mondo(), ids(), nuovo_app(), crea_paz(), avvisi() e html(); qui sono ricopiate solo per farle girare da sole.
Le prove vanno nel PRIMO passo della tappa insieme alle due righe di prove_15.py che oggi aspettano la frase
sbagliata (righe 1398 e 1517: «messi in agenda» con un appunto solo), cioè fra le «parole approvate» dell'elenco
del pacchetto: sul codice di oggi le tre prove cadono (è il loro mutante), dopo la correzione passano.
    cd <cartella del programma> && python prove_frasi_bozza.py
"""
import os
import shutil
import sys
import traceback
from datetime import date, datetime, time, timedelta

from sqlalchemy import select

import app as A
import prove_messaggi as PM
import servizi
import viste
from modelli import crea_sessione, Appunto, Attesa, Operatore, Paziente, Prestazione, Risorsa, Turno, Struttura

A.app.config['TESTING'] = True
PM.segui(A.app)
CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = os.path.join(CARTELLA, 'prove_frasi_tmp')
shutil.rmtree(PROVVISORIA, ignore_errors=True)
os.makedirs(PROVVISORIA)
OGGI = date.today()
MAR = OGGI + timedelta(days=(1 - OGGI.weekday()) % 7 + 14)
while servizi.calendario.festivo(MAR):
    MAR += timedelta(days=7)
_n = [0]
esiti = []


def mondo():
    _n[0] += 1
    S = crea_sessione('sqlite:///' + os.path.join(PROVVISORIA, 'db_%d.db' % _n[0]))
    s = S()
    servizi.prepara_primo_avvio(s)
    lip = Operatore(cognome='Lippiello', nome='Anna', colore='#154381')
    s.add(lip)
    s.flush()
    stanze = {r.nome: r for r in s.scalars(select(Risorsa))}
    for g in range(7):
        s.add(Turno(operatore=lip, risorsa=stanze['Ambulatorio 1'], giorno_settimana=g,
                    ora_inizio=time(8, 0), ora_fine=time(14, 0), valido_da=date(2020, 1, 1)))
    s.commit()
    s.close()
    A.Sessione = S
    A._registro = None
    viste._sessionmaker = lambda: S
    return S, PM.segna(A.app.test_client())


def ids(S):
    s = S()
    d = {r.nome: r.id for r in s.scalars(select(Risorsa))}
    d.update({o.cognome: o.id for o in s.scalars(select(Operatore))})
    d.update({p.nome: p.id for p in s.scalars(select(Prestazione))})
    s.close()
    return d


def nuovo_app(S, stanza, medico, g, h, m, minuti=30, stato='PRENOTATO'):
    from modelli import Appuntamento
    s = S()
    i = datetime.combine(g, time(h, m))
    a = Appuntamento(risorsa_id=stanza, operatore_id=medico, inizio=i, fine=i + timedelta(minutes=minuti), stato=stato)
    s.add(a)
    s.commit()
    aid = a.id
    s.close()
    return aid


def prova(nome, f):
    try:
        f()
        esiti.append(('OK', nome, ''))
    except AssertionError as e:
        esiti.append(('ROTTO', nome, str(e)))
    except Exception:
        esiti.append(('ERRORE', nome, traceback.format_exc().strip().splitlines()[-1]))


# ------------------------------------------------------------------ da incollare in prove_14.py
def fr_messo_in_agenda():
    """«1 appuntamento messo in agenda.» (non «messi»); con due, «2 appuntamenti messi in agenda.»"""
    S, C = mondo()
    I = ids(S)
    for ora, cognome in (('09:00', 'Uno'), ('09:30', 'Due'), ('10:00', 'Tre')):
        C.post('/da-confermare', data={'testo': 'Richiama', 'giorno': MAR.isoformat(), 'ora': ora,
                                       'operatore': str(I['Lippiello']), 'risorsa': str(I['Ambulatorio 1']),
                                       'cognome': cognome, 'telefono': '3470005001', 'struttura': '1'})
    PM.avvisi(C)
    s = S()
    tre = [x.id for x in s.scalars(select(Appunto).order_by(Appunto.id))]
    s.close()
    assert len(tre) == 3, tre
    C.post('/da-confermare/prenota', data={'scelti': [str(tre[0])], 'risorsa': ''})
    m = PM.avvisi(C)
    assert '1 appuntamento messo in agenda.' in m, 'con uno: %r' % m
    C.post('/da-confermare/prenota', data={'scelti': [str(tre[1]), str(tre[2])], 'risorsa': ''})
    m = PM.avvisi(C)
    assert '2 appuntamenti messi in agenda.' in m, 'con due: %r' % m


def fr_segnati_come():
    """Chiusura: «1 appuntamento segnato come arrivato.»; «2 appuntamenti segnati come non presentati.»"""
    S, C = mondo()
    I = ids(S)
    ieri = OGGI - timedelta(days=1)
    a = [nuovo_app(S, I['Ambulatorio 1'], I['Lippiello'], ieri, 9 + k, 0) for k in range(3)]
    C.post('/chiusura/%s?struttura=1' % ieri, data={'azione': 'arrivati', 'scelti': [str(a[0])], 'struttura': '1'})
    m = PM.avvisi(C)
    assert '1 appuntamento segnato come arrivato.' in m, 'con uno: %r' % m
    C.post('/chiusura/%s?struttura=1' % ieri, data={'azione': 'non_presentati', 'scelti': [str(a[1]), str(a[2])],
                                                     'struttura': '1'})
    m = PM.avvisi(C)
    assert '2 appuntamenti segnati come non presentati.' in m, 'con due: %r' % m


def fr_un_giorno():
    """Lista d'attesa: sotto la data «1 giorno» (non «1 giorni»), «3 giorni» con più."""
    S, C = mondo()
    s = S()
    for cognome, giorni in (('Unogiorno', 1), ('Tregiorni', 3)):
        p = Paziente(cognome=cognome, nome='Prova', telefono='3331110001')
        s.add(p)
        s.flush()
        s.add(Attesa(paziente_id=p.id, creato_il=datetime.combine(OGGI - timedelta(days=giorni), time(10, 0))))
    s.commit()
    s.close()
    t = C.get('/attesa').get_data(as_text=True)
    assert '>1 giorno<' in t and '1 giorni' not in t, 'singolare: %r' % t[t.find('giorn') - 60:t.find('giorn') + 20]
    assert '>3 giorni<' in t, 'plurale'


prova('frase approvata: «1 appuntamento messo in agenda.», con due «messi»', fr_messo_in_agenda)
prova('frase approvata: «segnato come arrivato», «segnati come non presentati»', fr_segnati_come)
prova('frase approvata: «1 giorno» nella lista d\'attesa, «3 giorni» con più', fr_un_giorno)

for e in esiti:
    print('%-6s %s %s' % e)
print('%d da sistemare' % sum(1 for e in esiti if e[0] != 'OK'))
shutil.rmtree(PROVVISORIA, ignore_errors=True)
sys.exit(0 if all(e[0] == 'OK' for e in esiti) else 1)
