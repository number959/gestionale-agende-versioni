# -*- coding: utf-8 -*-
"""Secondo giro: modifica, eliminazione, celle impilate, mezzanotte, concorrenza vera."""
import os, threading, traceback, urllib.request
import tempfile
from datetime import datetime, date, time, timedelta
from sqlalchemy import select

if os.path.exists('prove2.db'): os.remove('prove2.db')
import seed, servizi, app as A
from modelli import Appuntamento, Risorsa, Operatore, Prestazione, Paziente

Sessione = seed.popola('sqlite:///prove2.db')
A.Sessione = Sessione
A.app.config['TESTING'] = True
G = date(2026, 9, 15)
esiti = []

def prova(nome, f):
    try:
        esiti.append(('OK  ', nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', nome, str(e)))
    except Exception:
        esiti.append(('ERRORE', nome, traceback.format_exc().strip().splitlines()[-1]))

def rif():
    s = Sessione()
    return (s,
            s.scalars(select(Risorsa).where(Risorsa.nome == 'Ambulatorio 1')).first(),
            s.scalars(select(Operatore).where(Operatore.cognome == 'Lippiello')).first(),
            s.scalars(select(Prestazione).where(Prestazione.nome == 'Controllo')).first())

def modifica_senza_spostare():
    s, amb1, lip, p = rif()
    a = s.scalars(select(Appuntamento).where(
        Appuntamento.inizio == datetime.combine(G, time(9, 0)))).first()
    c = A.app.test_client()
    r = c.post('/appuntamento/%d' % a.id, data={
        'struttura': 1, 'risorsa': a.risorsa_id, 'operatore': a.operatore_id,
        'prestazione': a.prestazione_id, 'data': G.isoformat(), 'ora': '09:00',
        'durata': '30', 'paziente': 'Coppola', 'note': 'nota nuova'},
        follow_redirects=True)
    s2 = Sessione(); b = s2.get(Appuntamento, a.id); nota = b.note; s2.close(); s.close()
    assert nota == 'nota nuova', 'la modifica in loco viene bloccata da un conflitto con se stessa'

def eliminazione():
    s, amb1, lip, p = rif()
    i = datetime.combine(G, time(13, 0))
    a = Appuntamento(risorsa=amb1, operatore=lip, prestazione=p, inizio=i,
                     fine=i + timedelta(minutes=30))
    s.add(a); s.commit(); aid = a.id; s.close()
    A.app.test_client().post('/appuntamento/%d' % aid,
                             data={'azione': 'elimina', 'struttura': 1})
    s2 = Sessione(); resta = s2.get(Appuntamento, aid); s2.close()
    assert resta is None, "l'eliminazione non ha rimosso la riga"

def celle_impilate():
    s, amb1, lip, p = rif()           # due controlli da 20 minuti nella stessa fascia
    for minuto in (0, 20):
        i = datetime.combine(G, time(14, minuto))
        s.add(Appuntamento(risorsa=amb1, operatore=lip, prestazione=p,
                           inizio=i, fine=i + timedelta(minutes=20)))
    s.commit()
    celle = servizi.griglia(s, G, 1)['colonne'][0]['celle']
    impilate = [c for c in celle if c['stato'] == 'occupata' and len(c.get('apps', [])) == 2]
    s.close()
    assert impilate, 'due appuntamenti nella stessa fascia: uno dei due sparisce'
    return 'due voci nella stessa cella'

def oltre_mezzanotte():
    s, amb1, lip, p = rif()
    i = datetime.combine(G, time(23, 30))
    s.add(Appuntamento(risorsa=amb1, operatore=lip, prestazione=p,
                       inizio=i, fine=i + timedelta(minutes=60)))
    s.commit()
    v = servizi.griglia(s, G, 1)
    ultima = v['colonne'][0]['celle'][-1]
    s.close()
    assert len(v['fasce']) == len(v['colonne'][0]['celle']), 'fasce e celle disallineate'
    assert ultima['righe'] == 1, 'la cella delle 23:30 sfora la tabella'
    return 'ultima fascia %s' % v['fasce'][-1]

def porta_libera():
    # Una porta scelta dal sistema: con una porta fissa due giri di prove insieme
    # (versione normale e animata) si pestavano i piedi.
    import socket
    with socket.socket() as so:
        so.bind(('127.0.0.1', 0))
        return so.getsockname()[1]

def concorrenza_waitress():
    from waitress import serve
    porta = porta_libera()
    t = threading.Thread(target=serve, kwargs=dict(app=A.app, host='127.0.0.1',
                                                   port=porta, threads=4), daemon=True)
    t.start()
    import time as T; T.sleep(2)
    errori = []
    def colpo(n):
        try:
            u = 'http://127.0.0.1:%d/giorno/2026-09-%02d?struttura=%d' % (porta, 10 + n % 5, 1 + n % 2)
            with urllib.request.urlopen(u, timeout=15) as r:
                if r.status != 200: errori.append(r.status)
        except Exception as e:
            errori.append(repr(e)[:90])
    fili = [threading.Thread(target=colpo, args=(n,)) for n in range(24)]
    for f in fili: f.start()
    for f in fili: f.join()
    assert not errori, '%d richieste fallite: %s' % (len(errori), errori[:2])
    return '24 richieste su 4 thread, nessun errore'

def export_con_impilate():
    s = Sessione()
    f = servizi.esporta_giorno(s, G, 1, os.path.join(tempfile.gettempdir(), 'prove2-export.xlsx'))
    import openpyxl
    ws = openpyxl.load_workbook(f).active
    atteso = 2 + len(servizi.griglia(s, G, 1)['fasce'])
    s.close()
    assert ws.max_row <= atteso, 'export: %d righe contro %d' % (ws.max_row, atteso)
    return '%d righe' % ws.max_row

for nome, f in [('modifica senza spostare orario', modifica_senza_spostare),
                ('eliminazione appuntamento', eliminazione),
                ('due appuntamenti brevi nella stessa fascia', celle_impilate),
                ('appuntamento a cavallo di mezzanotte', oltre_mezzanotte),
                ('export con celle impilate', export_con_impilate),
                ('concorrenza sul server waitress', concorrenza_waitress)]:
    prova(nome, f)

print()
for stato, nome, msg in esiti:
    print('%-7s %-44s %s' % (stato, nome, msg))
print('\n%d prove, %d da sistemare' % (len(esiti), len([e for e in esiti if e[0] != 'OK  '])))
