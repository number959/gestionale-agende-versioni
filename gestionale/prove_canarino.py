# -*- coding: utf-8 -*-
"""La guardia del Modo schermo (tappa 1 della base, 21/11/2026).

Le pagine sotto /riepilogo-live* sono quelle che possono vedere gli altri PC (il «portiere» della rete lascia
passare solo loro): lì non deve mai comparire un dato di un paziente. Il «paziente canarino» ha cognome, nome,
telefoni, email, codice fiscale e note che non possono comparire per caso; ha appuntamenti di oggi in ogni
stato, un intervento in sala, un posto in lista d'attesa, e il suo nome è scritto anche in una cosa da fare,
nella nota del giorno e in un appunto. Nessuno di questi testi deve uscire da /riepilogo-live*, con e senza
schermo, per ogni struttura e, nelle statistiche, per i sei periodi con nome, degli ambulatori e della sala operatoria.
Il gemello: gli stessi dati compaiono nelle pagine normali (la scheda del paziente e la giornata), così si sa
che il canarino c'è davvero e che la prova non passa per caso.

    python prove_canarino.py
"""
import os
import re
import shutil
import sys
import tempfile
from datetime import date, datetime, time, timedelta

from prove_dove import dove

PROVVISORIA = tempfile.mkdtemp(prefix='prove-canarino-')

import seed  # noqa: E402
import app as A  # noqa: E402
from modelli import (Paziente, Appuntamento, Risorsa, Operatore, Struttura, Attesa, Attivita,  # noqa: E402
                     NotaGiorno, Appunto)
from sqlalchemy import select  # noqa: E402

A.app.config['TESTING'] = True
Sessione = seed.popola('sqlite:///' + os.path.join(PROVVISORIA, 'prove.db'))
A.Sessione = Sessione
C = A.app.test_client()

# i testi del canarino: nessuno può comparire per caso in una pagina
CANARINO = {
    'cognome': 'Canarinazzi', 'nome': 'Zebedeo', 'telefono': '0009876543', 'telefono2': '0009871111',
    'email': 'zebedeo.canarinazzi@example.com', 'codice_fiscale': 'CNRZBD80A01H501X',
    'note': 'nota-canarino-paziente',
}
CERCATI = ['canarinazzi', 'zebedeo', '9876543', '9871111', 'cnrzbd80', 'nota-canarino', 'attesa-canarino',
           'appunto-canarino', 'cosa-canarino', 'giorno-canarino']
esiti = []


def prova(nome, f):
    try:
        esiti.append(('OK', nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', nome, '%s · %s' % (dove(e), str(e) or 'asserzione fallita')))
    except Exception as e:
        esiti.append(('ERRORE', nome, '%s · %r' % (dove(e), e)))


def prepara():
    s = Sessione()
    oggi = date.today()
    p = Paziente(**CANARINO)
    s.add(p)
    s.flush()
    ambulatori = s.scalars(select(Risorsa).where(Risorsa.tipo == 'AMBULATORIO').order_by(Risorsa.id)).all()
    sale = s.scalars(select(Risorsa).where(Risorsa.tipo == 'SALA_OPERATORIA').order_by(Risorsa.id)).all()
    medico = s.scalars(select(Operatore).order_by(Operatore.id)).first()
    stati = ['PRENOTATO', 'CONFERMATO', 'ARRIVATO', 'NON_PRESENTATO', 'DISDETTO']
    for i, stato in enumerate(stati):
        inizio = datetime.combine(oggi, time(8 + i, 15))
        s.add(Appuntamento(risorsa_id=ambulatori[i % len(ambulatori)].id, operatore_id=medico.id, paziente_id=p.id,
                           inizio=inizio, fine=inizio + timedelta(minutes=30), stato=stato,
                           note='nota-canarino-appuntamento', arrivato_alle=inizio if stato == 'ARRIVATO' else None))
    inizio = datetime.combine(oggi, time(9, 0))
    s.add(Appuntamento(risorsa_id=sale[0].id, operatore_id=medico.id, paziente_id=p.id, inizio=inizio,
                       fine=inizio + timedelta(hours=2), stato='CONFERMATO', note='nota-canarino-intervento'))
    for st in s.scalars(select(Struttura)).all():
        s.add(NotaGiorno(struttura_id=st.id, data=oggi, testo='giorno-canarino: oggi Canarinazzi Zebedeo porta gli esami'))
        s.add(Appunto(testo='appunto-canarino da confermare', giorno=oggi, struttura_id=st.id,
                      cognome='Canarinazzi', nome='Zebedeo'))
    s.add(Attivita(testo='cosa-canarino: richiamare Canarinazzi Zebedeo', per_il=oggi, paziente_id=p.id))
    s.add(Attesa(paziente_id=p.id, dal=oggi, entro=oggi + timedelta(days=14), note='attesa-canarino'))
    s.commit()
    pid = p.id
    strutture = [st.id for st in s.scalars(select(Struttura)).all()]
    s.close()
    return pid, strutture


PID, STRUTTURE = prepara()


def testo(r):
    return r.get_data(as_text=True).lower()


def trovati(t):
    return [c for c in CERCATI if c in t]


def indirizzi_dello_schermo():
    """Tutti gli indirizzi GET sotto /riepilogo-live, presi dall'elenco del programma, con ogni parametro."""
    radici = sorted({r.rule for r in A.app.url_map.iter_rules()
                     if r.rule.startswith('/riepilogo-live') and 'GET' in r.methods and not r.arguments})
    assert len(radici) >= 4, radici
    out = []
    for radice in radici:
        varianti = ['']
        if 'statistiche' in radice:
            varianti = ['periodo=%s&parte=%s' % (per, parte)
                        for per in ('oggi', 'ieri', 'settimana', 'settimana-scorsa', 'mese', 'mese-scorso')
                        for parte in ('ambulatori', 'sala')]
        for sid in STRUTTURE:
            for schermo in ('', 'schermo=1'):
                for v in varianti:
                    q = '&'.join(x for x in ('struttura=%d' % sid, schermo, v) if x)
                    out.append(radice + '?' + q)
    return out


def g_scheda_paziente():
    t = testo(C.get('/pazienti/%d' % PID))
    for c in ('canarinazzi', 'zebedeo', '9876543', 'zebedeo.canarinazzi@example.com', 'cnrzbd80'):
        assert c in t, 'nella scheda del paziente manca %s: il canarino non è stato preparato bene' % c


def g_giornata():
    r = C.get('/', follow_redirects=True)
    assert r.status_code == 200, r.status_code
    assert 'canarinazzi' in testo(r), 'nella pagina di oggi il canarino non c\'è'


def g_conti():
    """Il canarino entra nei conti della dashboard: la guardia guarda pagine con i suoi appuntamenti dentro."""
    import json
    per_struttura = [json.loads(C.get('/riepilogo-live.json?struttura=%d' % sid).get_data(as_text=True))
                     for sid in STRUTTURE]
    totale = sum((d.get('oggi') or {}).get('totale', 0) or 0 for d in per_struttura if isinstance(d, dict))
    assert totale >= 3, 'i tre appuntamenti attivi del canarino non sono nei conti di oggi: %r' % totale


def p_schermo():
    controllate = 0
    for url in indirizzi_dello_schermo():
        r = C.get(url)
        assert r.status_code == 200, (url, r.status_code)
        visti = trovati(testo(r))
        assert not visti, 'dati del canarino in %s: %s' % (url, visti)
        controllate += 1
    return '%d pagine' % controllate


def p_gemello_html():
    """Il gemello del controllo «niente nomi»: lo stesso controllo, su una pagina normale di oggi, i nomi li trova
    (se il modo di cercare non vedesse niente, la prova sopra passerebbe da sola)."""
    t = testo(C.get('/', follow_redirects=True))
    assert trovati(t), 'il controllo non trova il canarino nemmeno dove c\'è'


prova('gemello: il canarino è nella sua scheda (nome, telefono, email, codice fiscale)', g_scheda_paziente)
prova('gemello: il canarino è nella pagina di oggi', g_giornata)
prova('gemello: gli appuntamenti attivi del canarino entrano nei conti della dashboard', g_conti)
prova('gemello: il controllo dei testi trova il canarino dove c\'è', p_gemello_html)
prova('nessun dato del canarino sotto /riepilogo-live*, con e senza schermo, ogni struttura e periodo', p_schermo)

shutil.rmtree(PROVVISORIA, ignore_errors=True)
for esito, nome, dettaglio in esiti:
    print('%-6s %s %s' % (esito, nome, dettaglio))
rotte = [e for e in esiti if e[0] != 'OK']
print('%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(rotte), len(rotte)))
sys.exit(1 if rotte else 0)
