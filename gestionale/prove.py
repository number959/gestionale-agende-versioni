# -*- coding: utf-8 -*-
"""Prove sul gestionale. Cerca i casi che rompono, non quelli che funzionano."""
import os
import tempfile
import sys
import threading
import traceback
from datetime import datetime, date, time, timedelta

from sqlalchemy import select

DB = 'sqlite:///prove.db'
if os.path.exists('prove.db'):
    os.remove('prove.db')

import seed
import servizi
import app as A
from modelli import (crea_sessione, Appuntamento, Risorsa, Operatore,
                     Prestazione, Paziente)

Sessione = seed.popola(DB)
A.Sessione = Sessione
A.app.config['TESTING'] = True

esiti = []


def prova(nome, funzione):
    try:
        messaggio = funzione()
        esiti.append(('OK  ', nome, messaggio or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', nome, str(e)))
    except Exception:
        esiti.append(('ERRORE', nome, traceback.format_exc().strip().splitlines()[-1]))


G = date(2026, 9, 15)


def ctx():
    s = Sessione()
    amb1 = s.scalars(select(Risorsa).where(Risorsa.nome == 'Ambulatorio 1')).first()
    lip = s.scalars(select(Operatore).where(Operatore.cognome == 'Lippiello')).first()
    p = s.scalars(select(Prestazione).where(Prestazione.nome == 'Controllo')).first()
    return s, amb1, lip, p


# ------------------------------------------------- 1. orario non allineato
def orario_non_allineato():
    s, amb1, lip, p = ctx()
    i = datetime.combine(G, time(10, 45))          # non cade su :00 o :30
    s.add(Appuntamento(risorsa=amb1, operatore=lip, prestazione=p,
                       inizio=i, fine=i + timedelta(minutes=20)))
    s.commit()
    col = servizi.griglia(s, G, 1)['colonne'][0]
    visibile = any(c['stato'] == 'occupata' and any(x.inizio == i for x in c['apps'])
                   for c in col['celle'])
    s.close()
    assert visibile, 'appuntamento delle 10:45 salvato ma invisibile nella griglia'


# ---------------------------------------------- 2. orario fuori apertura
def fuori_apertura():
    s, amb1, lip, p = ctx()
    i = datetime.combine(G, time(7, 0))            # prima delle 08:00
    s.add(Appuntamento(risorsa=amb1, operatore=lip, prestazione=p,
                       inizio=i, fine=i + timedelta(minutes=30)))
    s.commit()
    col = servizi.griglia(s, G, 1)['colonne'][0]
    visibile = any(c['stato'] == 'occupata' and any(x.inizio == i for x in c['apps'])
                   for c in col['celle'])
    s.close()
    assert visibile, 'appuntamento delle 07:00 salvato ma invisibile nella griglia'


# ------------------------------------- 3. appuntamento a cavallo della fine
def sfora_fine_giornata():
    s, amb1, lip, p = ctx()
    i = datetime.combine(G, time(19, 30))
    s.add(Appuntamento(risorsa=amb1, operatore=lip, prestazione=p,
                       inizio=i, fine=i + timedelta(minutes=60)))
    s.commit()
    celle = servizi.griglia(s, G, 1)['colonne'][0]['celle']
    ultima = celle[-1]
    s.close()
    assert not (ultima['stato'] == 'occupata' and ultima['righe'] > 1), \
        'la cella delle 19:30 chiede %d righe ma ne resta 1: tabella e merge Excel sballati' % ultima.get('righe', 1)


# --------------------------------------------------- 4. durata a zero
def durata_zero():
    c = A.app.test_client()
    s, amb1, lip, p = ctx()
    r = c.post('/appuntamento', data={
        'struttura': 1, 'risorsa': amb1.id, 'operatore': lip.id, 'prestazione': p.id,
        'data': G.isoformat(), 'ora': '14:00', 'durata': '0',
        'paziente': 'Prova', 'note': ''}, follow_redirects=False)
    s2 = Sessione()
    a = s2.scalars(select(Appuntamento).where(
        Appuntamento.inizio == datetime.combine(G, time(14, 0)))).first()
    zero = a is not None and a.inizio == a.fine
    s.close(); s2.close()
    assert not zero, 'accettato un appuntamento di durata zero (%s)' % r.status_code


# ------------------------------------- 5. dati persi quando c'e' conflitto
def conflitto_perde_i_dati():
    c = A.app.test_client()
    s, amb1, lip, p = ctx()
    dati = {'struttura': 1, 'risorsa': amb1.id, 'operatore': lip.id,
            'prestazione': p.id, 'data': G.isoformat(), 'ora': '08:00',
            'durata': '30', 'paziente': 'Ricci', 'telefono': '3331112223',
            'note': 'richiamare il giorno prima'}
    r = c.post('/appuntamento', data=dati, follow_redirects=True)
    html = r.get_data(as_text=True)
    s.close()
    assert 'Ricci' in html, 'dopo il conflitto il form si riapre vuoto: si riscrive tutto da capo'


# -------------------------------------------- 6. pazienti diversi, stesso cognome
def omonimi():
    s, amb1, lip, p = ctx()
    c = A.app.test_client()
    for ora, tel in (('15:00', '3330000001'), ('15:30', '3330000002')):
        c.post('/appuntamento', data={
            'struttura': 1, 'risorsa': amb1.id, 'operatore': lip.id, 'prestazione': p.id,
            'data': G.isoformat(), 'ora': ora, 'durata': '30',
            'paziente': 'Improta', 'telefono': tel})
    n = len(s.scalars(select(Paziente).where(Paziente.cognome == 'Improta')).all())
    s.close()
    assert n >= 2, 'due pazienti con lo stesso cognome vengono fusi in uno solo'


# ----------------------------------------------- 7. iniezione nello stile
def colore_iniettabile():
    s = Sessione()
    o = s.scalars(select(Operatore).where(Operatore.cognome == 'Marino')).first()
    o.colore = 'red; background: url(x)'
    s.commit()
    c = A.app.test_client()
    html = c.get('/giorno/2026-09-15?struttura=1').get_data(as_text=True)
    o.colore = '#B3261E'
    s.commit(); s.close()
    assert 'background: url(x)' not in html, \
        "il campo colore finisce dentro l'attributo style senza controllo"


# ------------------------------------------ 8. richieste in parallelo
def richieste_parallele():
    c = A.app.test_client()
    errori = []

    def colpo():
        try:
            r = c.get('/giorno/2026-09-15?struttura=1')
            if r.status_code != 200:
                errori.append(r.status_code)
        except Exception as e:
            errori.append(repr(e))

    fili = [threading.Thread(target=colpo) for _ in range(12)]
    for f in fili: f.start()
    for f in fili: f.join()
    assert not errori, 'richieste in parallelo: %s' % errori[:3]


# ------------------------------------------------- 9. export coerente
def export_regge():
    s = Sessione()
    f = servizi.esporta_giorno(s, G, 1, os.path.join(tempfile.gettempdir(), 'prove-export.xlsx'))
    import openpyxl
    ws = openpyxl.load_workbook(f).active
    fasce = len(servizi.griglia(s, G, 1)['fasce'])
    s.close()
    assert ws.max_row <= 2 + fasce, \
        'export: %d righe contro le %d attese, un merge e uscito dalla tabella' % (ws.max_row, 2 + fasce)


# --------------------------------------------- 10. data non valida
def data_sballata():
    c = A.app.test_client()
    r = c.get('/giorno/2026-13-45')
    assert r.status_code == 200, 'data impossibile -> HTTP %s' % r.status_code
    return 'ripiega su oggi senza errore'


# --------------------------------------- 11. struttura inesistente
def struttura_inesistente():
    c = A.app.test_client()
    r = c.get('/giorno/2026-09-15?struttura=999')
    assert r.status_code == 200, 'struttura inesistente -> HTTP %s' % r.status_code
    return 'restituisce una griglia vuota'


# --------------------------------------- 12. appuntamento inesistente
def appuntamento_inesistente():
    c = A.app.test_client()
    r = c.get('/appuntamento/999999')
    assert r.status_code == 404, 'atteso 404, ricevuto %s' % r.status_code
    return '404 corretto'


for nome, f in [
    ('orario non allineato alla fascia (10:45)', orario_non_allineato),
    ('appuntamento fuori orario di apertura (07:00)', fuori_apertura),
    ('appuntamento che sfora la fine giornata', sfora_fine_giornata),
    ('durata zero rifiutata', durata_zero),
    ('conflitto: i dati digitati sopravvivono', conflitto_perde_i_dati),
    ('omonimi trattati come pazienti distinti', omonimi),
    ('colore operatore non iniettabile nello style', colore_iniettabile),
    ('12 richieste in parallelo', richieste_parallele),
    ('export senza merge fuori tabella', export_regge),
    ('data non valida nell URL', data_sballata),
    ('struttura inesistente', struttura_inesistente),
    ('appuntamento inesistente', appuntamento_inesistente),
]:
    prova(nome, f)

print()
for stato, nome, msg in esiti:
    print('%-7s %-46s %s' % (stato, nome, msg))
rotti = [e for e in esiti if e[0] != 'OK  ']
print('\n%d prove, %d da sistemare' % (len(esiti), len(rotti)))
sys.exit(0)
