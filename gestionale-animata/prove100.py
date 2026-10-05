# -*- coding: utf-8 -*-
"""Suite estesa. Ogni prova ha un nome parlante: se rompe si sa dove guardare."""
import os
import tempfile
import random
import threading
import traceback
from datetime import datetime, date, time, timedelta

from sqlalchemy import select

DB = 'prove100.db'
if os.path.exists(DB):
    os.remove(DB)

import seed
import servizi
import app as A
from modelli import (Appuntamento, Risorsa, Operatore, Prestazione,
                     Paziente, Turno, Struttura)

Sessione = seed.popola('sqlite:///' + DB)
A.Sessione = Sessione
A.app.config['TESTING'] = True
CL = A.app.test_client()
G = date(2026, 9, 15)          # martedi con turni attivi
DOM = date(2026, 9, 20)        # domenica, nessun turno

esiti = []
_area = ['']


def prova(nome, f):
    try:
        esiti.append(('OK', _area[0], nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', _area[0], nome, str(e) or 'asserzione fallita'))
    except Exception:
        ultima = traceback.format_exc().strip().splitlines()[-1]
        esiti.append(('ERRORE', _area[0], nome, ultima))


def area(nome):
    _area[0] = nome


def S():
    return Sessione()


def rif(s, stanza='Ambulatorio 1', medico='Lippiello', prestazione='Controllo'):
    return (s.scalars(select(Risorsa).where(Risorsa.nome == stanza)).first(),
            s.scalars(select(Operatore).where(Operatore.cognome == medico)).first(),
            s.scalars(select(Prestazione).where(Prestazione.nome == prestazione)).first())


def pulisci(s, g=G):
    i = datetime.combine(g, time(0, 0))
    for a in s.scalars(select(Appuntamento).where(
            Appuntamento.inizio >= i, Appuntamento.inizio < i + timedelta(days=1))):
        s.delete(a)
    s.commit()


def metti(s, stanza, medico, h, m, durata, g=G, prestazione='Controllo'):
    r, o, p = rif(s, stanza, medico, prestazione)
    i = datetime.combine(g, time(h, m))
    a = Appuntamento(risorsa=r, operatore=o, prestazione=p, inizio=i,
                     fine=i + timedelta(minutes=durata))
    s.add(a)
    s.commit()
    return a


# =====================================================================
area('conflitti')
# matrice di sovrapposizioni: esistente 10:00-11:00 in Ambulatorio 1
CASI_CONFLITTO = [
    ('identico', 10, 0, 60, True),
    ('inizio prima, fine dentro', 9, 30, 60, True),
    ('inizio dentro, fine dopo', 10, 30, 60, True),
    ('contenuto', 10, 15, 15, True),
    ('contenente', 9, 0, 180, True),
    ('finisce esattamente all inizio', 9, 0, 60, False),
    ('inizia esattamente alla fine', 11, 0, 60, False),
    ('finisce al minuto esatto di inizio', 8, 59, 61, False),
    ('un minuto dopo la fine', 11, 1, 30, False),
    ('sovrapposizione di un minuto in coda', 9, 0, 61, True),
    ('sovrapposizione di un minuto in testa', 10, 59, 30, True),
    ('molto prima', 8, 0, 30, False),
    ('molto dopo', 15, 0, 30, False),
]


def fai_conflitto(nome, h, m, durata, atteso, stessa_stanza=True, stesso_medico=True):
    def f():
        s = S()
        pulisci(s)
        metti(s, 'Ambulatorio 1', 'Lippiello', 10, 0, 60)
        stanza = 'Ambulatorio 1' if stessa_stanza else 'Ambulatorio 3'
        med = 'Lippiello' if stesso_medico else 'Esposito'
        r, o, _ = rif(s, stanza, med)
        i = datetime.combine(G, time(h, m))
        c = servizi.conflitti(s, r.id, o.id, i, i + timedelta(minutes=durata))
        s.close()
        assert bool(c) == atteso, 'atteso %s, ottenuto %s' % (
            'conflitto' if atteso else 'via libera', c[:1] or 'via libera')
    return f


for nome, h, m, d, atteso in CASI_CONFLITTO:
    prova('stessa stanza, stesso medico: %s' % nome,
          fai_conflitto(nome, h, m, d, atteso))

for nome, h, m, d, atteso in CASI_CONFLITTO[:6]:
    prova('stanza diversa, stesso medico: %s' % nome,
          fai_conflitto(nome, h, m, d, atteso, stessa_stanza=False))

for nome, h, m, d, atteso in CASI_CONFLITTO[:6]:
    prova('stessa stanza, medico diverso: %s' % nome,
          fai_conflitto(nome, h, m, d, atteso, stesso_medico=False))


def conflitto_esclude_se_stesso():
    s = S(); pulisci(s)
    a = metti(s, 'Ambulatorio 1', 'Lippiello', 10, 0, 60)
    c = servizi.conflitti(s, a.risorsa_id, a.operatore_id, a.inizio, a.fine,
                          escludi_id=a.id)
    s.close()
    assert not c, 'un appuntamento va in conflitto con se stesso: %s' % c[:1]


def conflitto_fra_strutture():
    s = S(); pulisci(s)
    metti(s, 'Ambulatorio 1', 'Lippiello', 10, 0, 60)
    r, o, _ = rif(s, 'Sala A', 'Lippiello')       # altra struttura
    i = datetime.combine(G, time(10, 30))
    c = servizi.conflitti(s, r.id, o.id, i, i + timedelta(minutes=30))
    s.close()
    assert c, 'lo stesso medico risulta libero in due strutture nello stesso momento'


prova('un appuntamento non va in conflitto con se stesso', conflitto_esclude_se_stesso)
prova('lo stesso medico non puo stare in due strutture', conflitto_fra_strutture)


# =====================================================================
area('collocazione oraria')
ORARI = [(8, 0, '08:00'), (8, 1, '08:00'), (8, 29, '08:00'), (8, 30, '08:30'),
         (8, 31, '08:30'), (10, 45, '10:30'), (11, 59, '11:30'), (19, 30, '19:30'),
         (7, 0, '07:00'), (6, 15, '06:00'), (20, 0, '20:00'), (23, 30, '23:30'),
         (0, 0, '00:00'), (12, 5, '12:00'), (17, 55, '17:30')]


def fai_collocazione(h, m, fascia_attesa):
    def f():
        s = S(); pulisci(s)
        a = metti(s, 'Ambulatorio 1', 'Lippiello', h, m, 20)
        v = servizi.griglia(s, G, 1)
        col = v['colonne'][0]
        trovata = [f2 for f2, c in zip(v['fasce'], col['celle'])
                   if c['stato'] == 'occupata' and any(x.id == a.id for x in c['apps'])]
        s.close()
        assert trovata, 'appuntamento delle %02d:%02d non compare in griglia' % (h, m)
        assert trovata[0].strftime('%H:%M') == fascia_attesa, \
            'finito nella fascia %s invece di %s' % (trovata[0].strftime('%H:%M'), fascia_attesa)
    return f


for h, m, att in ORARI:
    prova('%02d:%02d finisce nella fascia %s' % (h, m, att), fai_collocazione(h, m, att))


DURATE = [(5, 1), (20, 1), (30, 1), (31, 2), (45, 2), (60, 2), (90, 3), (120, 4), (240, 8)]


def fai_durata(durata, righe_attese):
    def f():
        s = S(); pulisci(s)
        metti(s, 'Ambulatorio 1', 'Lippiello', 10, 0, durata)
        col = servizi.griglia(s, G, 1)['colonne'][0]
        cella = [c for c in col['celle'] if c['stato'] == 'occupata'][0]
        s.close()
        assert cella['righe'] == righe_attese, \
            '%d minuti occupano %d fasce invece di %d' % (durata, cella['righe'], righe_attese)
    return f


for d, n in DURATE:
    prova('%d minuti occupano %d fasce' % (d, n), fai_durata(d, n))


# =====================================================================
area('turni')
def fai_turno(giorno, ora, atteso, nota=''):
    def f():
        s = S()
        pulisci(s, giorno)          # isolamento: la giornata parte pulita
        col = servizi.griglia(s, giorno, 1)['colonne'][0]
        cella = [c for c in zip(servizi.griglia(s, giorno, 1)['fasce'], col['celle'])
                 if c[0] == ora]
        s.close()
        assert cella, 'fascia %s assente' % ora
        stato = cella[0][1]['stato']
        assert stato == atteso, 'fascia %s in stato %s invece di %s' % (ora, stato, atteso)
    return f


prova('martedi 10:00 Ambulatorio 1 aperto', fai_turno(G, time(10, 0), 'aperta'))
prova('martedi 15:00 Ambulatorio 1 chiuso', fai_turno(G, time(15, 0), 'chiusa'))
prova('martedi 14:00 fine turno esclusa', fai_turno(G, time(14, 0), 'chiusa'))
prova('martedi 13:30 ultima fascia del turno', fai_turno(G, time(13, 30), 'aperta'))
prova('domenica tutto chiuso', fai_turno(DOM, time(10, 0), 'chiusa'))


def turno_scaduto():
    s = S()
    t = s.scalars(select(Turno)).first()
    t.valido_a = date(2026, 9, 1)
    s.commit()
    col = servizi.griglia(s, G, 1)['colonne'][0]
    aperte = [c for c in col['celle'] if c['stato'] == 'aperta']
    t.valido_a = None
    s.commit(); s.close()
    assert not aperte, 'turno scaduto il 01/09 ancora attivo il 15/09'


def turno_futuro():
    s = S()
    t = s.scalars(select(Turno)).first()
    vecchio, t.valido_da = t.valido_da, date(2026, 12, 1)
    s.commit()
    col = servizi.griglia(s, G, 1)['colonne'][0]
    aperte = [c for c in col['celle'] if c['stato'] == 'aperta']
    t.valido_da = vecchio
    s.commit(); s.close()
    assert not aperte, 'turno che parte a dicembre gia attivo a settembre'


def turno_giorno_sbagliato():
    s = S()
    lun = date(2026, 9, 14)
    col = servizi.griglia(s, lun, 1)['colonne'][0]
    aperte = [c for c in col['celle'] if c['stato'] == 'aperta']
    s.close()
    assert not aperte, 'turno del martedi attivo anche di lunedi'


def fuori_turno_segnalato():
    s = S()
    r, o, _ = rif(s)
    i = datetime.combine(G, time(16, 0))
    avv = servizi.fuori_turno(s, r.id, o.id, i, i + timedelta(minutes=30))
    s.close()
    assert avv, 'le 16:00 sono fuori turno ma non viene segnalato'


def dentro_turno_non_segnalato():
    s = S()
    r, o, _ = rif(s)
    i = datetime.combine(G, time(10, 0))
    avv = servizi.fuori_turno(s, r.id, o.id, i, i + timedelta(minutes=30))
    s.close()
    assert avv is None, 'le 10:00 sono dentro il turno ma vengono segnalate'


def turno_a_cavallo_della_fine():
    s = S()
    r, o, _ = rif(s)
    i = datetime.combine(G, time(13, 45))          # finisce alle 14:15, oltre il turno
    avv = servizi.fuori_turno(s, r.id, o.id, i, i + timedelta(minutes=30))
    s.close()
    assert avv, 'appuntamento che sfora la fine turno non segnalato'


prova('turno scaduto non apre fasce', turno_scaduto)
prova('turno non ancora valido non apre fasce', turno_futuro)
prova('turno del martedi non vale il lunedi', turno_giorno_sbagliato)
prova('fascia fuori turno viene segnalata', fuori_turno_segnalato)
prova('fascia dentro turno non viene segnalata', dentro_turno_non_segnalato)
prova('appuntamento che sfora la fine turno', turno_a_cavallo_della_fine)


# =====================================================================
area('rotte http')
ROTTE = [
    ('/', (302,)), ('/giorno/2026-09-15', (200,)), ('/giorno/2026-09-20', (200,)),
    ('/giorno/2026-02-30', (200,)), ('/giorno/non-una-data', (200,)),
    ('/giorno/', (404,)), ('/giorno/2026-09-15?struttura=2', (200,)),
    ('/giorno/2026-09-15?struttura=999', (200,)),
    ('/giorno/2026-09-15?struttura=abc', (200, 400)),
    ('/giorno/2026-09-15?struttura=-1', (200,)),
    ('/giorno/2026-09-15?struttura=', (200,)),
    ('/appuntamento', (200,)), ('/appuntamento?data=2026-09-15&ora=09:00', (200,)),
    ('/appuntamento?risorsa=abc', (200, 400)),
    ('/appuntamento?risorsa=999', (200,)),
    ('/appuntamento/999999', (404,)),
    ('/appuntamento/abc', (404,)),
    ('/anagrafiche', (200,)),
    ('/esporta/2026-09-15', (200,)),
    ('/esporta/2026-09-20', (200,)),
    ('/esporta/non-una-data', (200,)),
    ('/pagina-che-non-esiste', (404,)),
    ('/static/stile.css', (200,)),
    ('/static/logo-posillipo.png', (200,)),
]


def fai_rotta(url, attesi):
    def f():
        r = CL.get(url)
        assert r.status_code in attesi, 'HTTP %d (attesi %s)' % (r.status_code, attesi)
        return 'HTTP %d' % r.status_code
    return f


for url, attesi in ROTTE:
    prova('GET %s' % url, fai_rotta(url, attesi))


def post_senza_campi():
    r = CL.post('/appuntamento', data={})
    assert r.status_code in (400, 200), 'POST vuoto -> HTTP %d' % r.status_code
    return 'HTTP %d' % r.status_code


def post_risorsa_inesistente():
    s = S(); _, o, p = rif(s); oid, pid = o.id, p.id; s.close()
    r = CL.post('/appuntamento', data={
        'struttura': 1, 'risorsa': 99999, 'operatore': oid, 'prestazione': pid,
        'data': G.isoformat(), 'ora': '16:00', 'durata': '30'})
    s2 = S()
    orfani = [a for a in s2.scalars(select(Appuntamento)) if a.risorsa is None]
    s2.close()
    assert not orfani, 'creato un appuntamento con stanza inesistente'


def post_prestazione_inesistente():
    s = S(); r, o, _ = rif(s); rid, oid = r.id, o.id; s.close()
    resp = CL.post('/appuntamento', data={
        'struttura': 1, 'risorsa': rid, 'operatore': oid, 'prestazione': 99999,
        'data': G.isoformat(), 'ora': '16:30', 'durata': '30'})
    assert resp.status_code < 500, 'prestazione inesistente -> HTTP %d' % resp.status_code
    return 'HTTP %d' % resp.status_code


def post_durata_negativa():
    s = S(); r, o, p = rif(s); rid, oid, pid = r.id, o.id, p.id; s.close()
    CL.post('/appuntamento', data={
        'struttura': 1, 'risorsa': rid, 'operatore': oid, 'prestazione': pid,
        'data': G.isoformat(), 'ora': '17:00', 'durata': '-30'})
    s2 = S()
    a = s2.scalars(select(Appuntamento).where(
        Appuntamento.inizio == datetime.combine(G, time(17, 0)))).first()
    brutto = a is not None and a.fine <= a.inizio
    s2.close()
    assert not brutto, 'accettata una durata negativa'


def post_ora_malformata():
    s = S(); r, o, p = rif(s); rid, oid, pid = r.id, o.id, p.id; s.close()
    resp = CL.post('/appuntamento', data={
        'struttura': 1, 'risorsa': rid, 'operatore': oid, 'prestazione': pid,
        'data': G.isoformat(), 'ora': '25:99', 'durata': '30'})
    assert resp.status_code < 500, 'ora 25:99 -> HTTP %d' % resp.status_code
    return 'HTTP %d' % resp.status_code


def post_data_malformata():
    s = S(); r, o, p = rif(s); rid, oid, pid = r.id, o.id, p.id; s.close()
    resp = CL.post('/appuntamento', data={
        'struttura': 1, 'risorsa': rid, 'operatore': oid, 'prestazione': pid,
        'data': '32/13/2026', 'ora': '10:00', 'durata': '30'})
    assert resp.status_code < 500, 'data assurda -> HTTP %d' % resp.status_code
    return 'HTTP %d' % resp.status_code


prova('POST senza alcun campo', post_senza_campi)
prova('POST con stanza inesistente', post_risorsa_inesistente)
prova('POST con prestazione inesistente', post_prestazione_inesistente)
prova('POST con durata negativa', post_durata_negativa)
prova('POST con ora malformata', post_ora_malformata)
prova('POST con data malformata', post_data_malformata)


# =====================================================================
area('testo e escaping')
VELENI = [
    ('script', '<script>alert(1)</script>'),
    ('immagine con onerror', '<img src=x onerror=alert(1)>'),
    ('virgolette', 'D\'Amico "detto Nino"'),
    ('accenti', 'Andrè Sanmartinò'),
    ('ampersand', 'Rossi & Figli'),
    ('nome lunghissimo', 'A' * 300),
    ('a capo', 'Rossi\nMario'),
    ('emoji', 'Rossi 🙂'),
    ('sql', "'; DROP TABLE appuntamenti; --"),
]


def fai_veleno(nome, testo):
    def f():
        s = S(); pulisci(s)
        r, o, p = rif(s)
        paz = Paziente(cognome=testo[:250], telefono='333')
        s.add(paz); s.flush()
        i = datetime.combine(G, time(10, 0))
        s.add(Appuntamento(risorsa=r, operatore=o, prestazione=p, paziente=paz,
                           inizio=i, fine=i + timedelta(minutes=30)))
        s.commit()
        resp = CL.get('/giorno/2026-09-15?struttura=1')
        html = resp.get_data(as_text=True)
        s2 = S()
        tabella_viva = s2.scalars(select(Appuntamento)).first() is not None
        s2.close(); s.close()
        assert resp.status_code == 200, 'HTTP %d' % resp.status_code
        assert '<script' not in html.replace('<script', '', 0) or True
        assert '<script>alert' not in html, 'tag script passato intero'
        assert '<img src=x' not in html, 'tag img passato intero'
        if '&lt;img' in html or '&lt;script' in html:
            pass                     # marcatori resi inerti da Jinja, come deve essere
        assert tabella_viva, 'la tabella appuntamenti e sparita'
    return f


for nome, testo in VELENI:
    prova('paziente con %s' % nome, fai_veleno(nome, testo))


def colori_strani():
    valori = ['red', '#fff', 'javascript:alert(1)', '', None,
              '#12345Z', '#0087B4', 'blue; content: url(x)']
    s = S()
    o = s.scalars(select(Operatore).where(Operatore.cognome == 'Marino')).first()
    originale = o.colore
    cattivi = []
    for v in valori:
        o.colore = v
        s.commit()
        if o.colore_sicuro not in ('#154381', '#0087B4'):
            cattivi.append(v)
    o.colore = originale
    s.commit(); s.close()
    assert not cattivi, 'colori passati senza controllo: %s' % cattivi


prova('colori non validi ricadono sul default', colori_strani)


# =====================================================================
area('integrita dati')
def cancellare_medico_con_appuntamenti():
    s = S(); pulisci(s)
    o = Operatore(cognome='Temporaneo', colore='#123456')
    r, _, p = rif(s)
    s.add(o); s.flush()
    i = datetime.combine(G, time(10, 0))
    s.add(Appuntamento(risorsa=r, operatore=o, prestazione=p,
                       inizio=i, fine=i + timedelta(minutes=30)))
    s.commit()
    s.delete(o)
    try:
        s.commit()
    except Exception:
        s.rollback()
        s.close()
        return 'la cancellazione viene rifiutata'
    resp = CL.get('/giorno/2026-09-15?struttura=1')
    s.close()
    assert resp.status_code == 200, \
        'medico cancellato con appuntamenti aperti: la griglia va in errore %d' % resp.status_code


def cancellare_stanza_con_appuntamenti():
    s = S(); pulisci(s)
    st = s.scalars(select(Struttura)).first()
    r = Risorsa(nome='Stanza usa e getta', ordine=99)
    s.add(r); r.struttura = st; s.flush()
    _, o, p = rif(s)
    i = datetime.combine(G, time(10, 0))
    s.add(Appuntamento(risorsa=r, operatore=o, prestazione=p,
                       inizio=i, fine=i + timedelta(minutes=30)))
    s.commit()
    s.delete(r)
    try:
        s.commit()
    except Exception:
        s.rollback(); s.close()
        return 'la cancellazione viene rifiutata'
    resp = CL.get('/giorno/2026-09-15?struttura=1')
    s.close()
    assert resp.status_code == 200, \
        'stanza cancellata con appuntamenti aperti: griglia in errore %d' % resp.status_code


def appuntamento_senza_paziente():
    s = S(); pulisci(s)
    metti(s, 'Ambulatorio 1', 'Lippiello', 10, 0, 30)
    resp = CL.get('/giorno/2026-09-15?struttura=1')
    s.close()
    assert resp.status_code == 200, 'appuntamento senza paziente -> HTTP %d' % resp.status_code


def appuntamento_senza_prestazione():
    s = S(); pulisci(s)
    r, o, _ = rif(s)
    i = datetime.combine(G, time(10, 0))
    s.add(Appuntamento(risorsa=r, operatore=o, inizio=i,
                       fine=i + timedelta(minutes=30)))
    s.commit()
    resp = CL.get('/giorno/2026-09-15?struttura=1')
    esp = CL.get('/esporta/2026-09-15')
    s.close()
    assert resp.status_code == 200 and esp.status_code == 200, \
        'appuntamento senza prestazione: griglia %d export %d' % (resp.status_code, esp.status_code)


def stanza_disattivata():
    s = S(); pulisci(s)
    r, o, p = rif(s)
    metti(s, 'Ambulatorio 1', 'Lippiello', 10, 0, 30)
    r.attiva = False
    s.commit()
    v = servizi.griglia(s, G, 1)
    nomi = [c['risorsa'].nome for c in v['colonne']]
    r.attiva = True
    s.commit(); s.close()
    assert 'Ambulatorio 1' not in nomi, 'stanza disattivata ancora in griglia'


def fine_prima_dell_inizio():
    s = S(); pulisci(s)
    r, o, p = rif(s)
    i = datetime.combine(G, time(10, 0))
    s.add(Appuntamento(risorsa=r, operatore=o, prestazione=p,
                       inizio=i, fine=i - timedelta(minutes=30)))
    s.commit()
    resp = CL.get('/giorno/2026-09-15?struttura=1')
    s.close()
    assert resp.status_code == 200, 'fine prima dell inizio manda in errore la griglia'


def struttura_senza_stanze():
    s = S()
    st = Struttura(nome='Struttura vuota')
    s.add(st); s.commit(); sid = st.id
    v = servizi.griglia(s, G, sid)
    resp = CL.get('/giorno/2026-09-15?struttura=%d' % sid)
    esp = CL.get('/esporta/2026-09-15?struttura=%d' % sid)
    s.delete(st); s.commit(); s.close()
    assert v['colonne'] == [], 'colonne non vuote'
    assert resp.status_code == 200, 'griglia HTTP %d' % resp.status_code
    assert esp.status_code == 200, 'export HTTP %d' % esp.status_code


prova('cancellare un medico con appuntamenti', cancellare_medico_con_appuntamenti)
prova('cancellare una stanza con appuntamenti', cancellare_stanza_con_appuntamenti)
prova('appuntamento senza paziente', appuntamento_senza_paziente)
prova('appuntamento senza prestazione', appuntamento_senza_prestazione)
prova('stanza disattivata esce dalla griglia', stanza_disattivata)
prova('fine prima dell inizio non fa esplodere nulla', fine_prima_dell_inizio)
prova('struttura senza stanze', struttura_senza_stanze)


# =====================================================================
area('export')
def fai_export(g, nota, controllo):
    def f():
        s = S()
        percorso = os.path.join(tempfile.gettempdir(), 'exp-%s.xlsx' % g.isoformat())
        servizi.esporta_giorno(s, g, 1, percorso)
        import openpyxl
        ws = openpyxl.load_workbook(percorso).active
        esito = controllo(s, ws, g)
        s.close()
        return esito
    return f


def exp_righe(s, ws, g):
    atteso = 2 + len(servizi.griglia(s, g, 1)['fasce'])
    assert ws.max_row <= atteso, '%d righe contro %d' % (ws.max_row, atteso)
    return '%d righe' % ws.max_row


def exp_colonne(s, ws, g):
    n = len(servizi.griglia(s, g, 1)['colonne'])
    assert ws.max_column >= 1 + 2 * n, 'colonne insufficienti'
    return '%d colonne' % ws.max_column


def exp_logo(s, ws, g):
    assert len(ws._images) == 1, '%d immagini' % len(ws._images)
    return 'logo presente'


def exp_titolo(s, ws, g):
    # dalla 1.2 il titolo porta il nome della struttura e sta subito dopo il logo
    titoli = [c for c in ws[1] if c.value]
    assert titoli and 'PLANNING DEL' in str(titoli[0].value), 'titolo assente'
    assert 'CLINICA POSILLIPO' in str(titoli[0].value), 'titolo senza il nome della struttura'
    assert titoli[0].column > 1, 'titolo in A1, sotto al logo'
    return '%s in %s' % (titoli[0].value, titoli[0].coordinate)


def exp_merge_dentro(s, ws, g):
    fuori = [str(m) for m in ws.merged_cells.ranges if m.max_row > ws.max_row]
    assert not fuori, 'merge oltre la tabella: %s' % fuori[:2]
    return '%d merge' % len(ws.merged_cells.ranges)


def exp_ore(s, ws, g):
    fasce = servizi.griglia(s, g, 1)['fasce']
    assert ws.cell(3, 1).value == fasce[0], 'prima ora sbagliata'
    assert ws.cell(2 + len(fasce), 1).value == fasce[-1], 'ultima ora sbagliata'
    return '%s -> %s' % (fasce[0], fasce[-1])


for nome, controllo in [('righe entro il previsto', exp_righe),
                        ('colonne per ogni stanza', exp_colonne),
                        ('logo incorporato', exp_logo),
                        ('titolo della giornata', exp_titolo),
                        ('merge dentro la tabella', exp_merge_dentro),
                        ('colonna ore coerente', exp_ore)]:
    prova('export %s (giorno pieno)' % nome, fai_export(G, '', controllo))

for nome, controllo in [('righe entro il previsto', exp_righe),
                        ('merge dentro la tabella', exp_merge_dentro)]:
    prova('export %s (domenica vuota)' % nome, fai_export(DOM, '', controllo))


# =====================================================================
area('invarianti su dati casuali')
def fai_giro(semenza):
    def f():
        casuale = random.Random(semenza)
        s = S()
        giorno = date(2026, 10, 1) + timedelta(days=semenza % 28)
        pulisci(s, giorno)
        r, o, p = rif(s)
        creati = []
        for _ in range(casuale.randint(3, 14)):
            h = casuale.randint(6, 22)
            m = casuale.choice([0, 5, 10, 15, 20, 25, 30, 40, 45, 50, 55])
            durata = casuale.choice([5, 10, 15, 20, 30, 45, 60, 90, 120])
            i = datetime.combine(giorno, time(h, m))
            fine = i + timedelta(minutes=durata)
            if fine.date() != giorno:
                continue
            if servizi.conflitti(s, r.id, o.id, i, fine):
                continue
            a = Appuntamento(risorsa=r, operatore=o, prestazione=p, inizio=i, fine=fine)
            s.add(a); s.commit()
            creati.append(a.id)

        v = servizi.griglia(s, giorno, 1)
        col = v['colonne'][0]
        celle = col['celle']

        assert len(celle) == len(v['fasce']), \
            'celle %d contro fasce %d' % (len(celle), len(v['fasce']))

        visti = [a.id for c in celle if c['stato'] == 'occupata' for a in c['apps']]
        assert sorted(visti) == sorted(creati), \
            'in griglia %d appuntamenti su %d creati' % (len(visti), len(creati))
        assert len(visti) == len(set(visti)), 'qualche appuntamento compare due volte'

        coperte = len([c for c in celle if c['stato'] == 'coperta'])
        estese = sum(c['righe'] - 1 for c in celle if c['stato'] == 'occupata')
        assert coperte == estese, \
            'celle coperte %d contro estensioni %d: la tabella si sfalsa' % (coperte, estese)

        for i, c in enumerate(celle):
            if c['stato'] == 'occupata':
                assert i + c['righe'] <= len(celle), 'estensione oltre la tabella'

        resp = CL.get('/giorno/%s?struttura=1' % giorno.isoformat())
        assert resp.status_code == 200, 'griglia HTTP %d' % resp.status_code
        servizi.esporta_giorno(s, giorno, 1, os.path.join(tempfile.gettempdir(), 'fuzz.xlsx'))
        s.close()
        return '%d appuntamenti' % len(creati)
    return f


for semenza in range(1, 13):
    prova('giro casuale %d: ogni appuntamento visibile una volta sola' % semenza,
          fai_giro(semenza))


# =====================================================================
area('concorrenza')
def due_prenotazioni_insieme():
    s = S(); pulisci(s)
    r, o, p = rif(s); rid, oid, pid = r.id, o.id, p.id; s.close()
    barriera = threading.Barrier(2)
    esiti_post = []

    def prenota():
        c = A.app.test_client()
        barriera.wait()
        try:
            c.post('/appuntamento', data={
                'struttura': 1, 'risorsa': rid, 'operatore': oid, 'prestazione': pid,
                'data': G.isoformat(), 'ora': '10:00', 'durata': '30'})
            esiti_post.append('ok')
        except Exception as e:
            esiti_post.append(repr(e)[:60])

    fili = [threading.Thread(target=prenota) for _ in range(2)]
    for f in fili: f.start()
    for f in fili: f.join()
    s2 = S()
    n = len(s2.scalars(select(Appuntamento).where(
        Appuntamento.inizio == datetime.combine(G, time(10, 0)))).all())
    s2.close()
    assert n == 1, 'due prenotazioni simultanee hanno creato %d appuntamenti' % n


def letture_parallele():
    errori = []

    def leggi(n):
        c = A.app.test_client()
        try:
            r = c.get('/giorno/2026-09-%02d?struttura=%d' % (10 + n % 8, 1 + n % 2))
            if r.status_code != 200:
                errori.append(r.status_code)
        except Exception as e:
            errori.append(repr(e)[:60])

    fili = [threading.Thread(target=leggi, args=(n,)) for n in range(20)]
    for f in fili: f.start()
    for f in fili: f.join()
    assert not errori, '%d errori: %s' % (len(errori), errori[:2])
    return '20 letture'


def export_parallelo():
    errori = []

    def esporta(n):
        c = A.app.test_client()
        try:
            r = c.get('/esporta/2026-09-15')
            if r.status_code != 200:
                errori.append(r.status_code)
        except Exception as e:
            errori.append(repr(e)[:60])

    fili = [threading.Thread(target=esporta, args=(n,)) for n in range(6)]
    for f in fili: f.start()
    for f in fili: f.join()
    assert not errori, errori[:2]
    return '6 export insieme'


def vincolo_database():
    s = S(); pulisci(s)
    r, o, pr = rif(s)
    i = datetime.combine(G, time(10, 0))
    s.add(Appuntamento(risorsa=r, operatore=o, prestazione=pr, inizio=i,
                       fine=i + timedelta(minutes=30)))
    s.commit()
    s.add(Appuntamento(risorsa=r, operatore=o, prestazione=pr, inizio=i,
                       fine=i + timedelta(minutes=30)))
    try:
        s.commit()
        s.close()
        raise AssertionError('il database accetta due appuntamenti identici')
    except AssertionError:
        raise
    except Exception:
        s.rollback(); s.close()
        return 'rifiutato dal vincolo sulla tabella'


prova('due prenotazioni simultanee sulla stessa fascia', due_prenotazioni_insieme)
prova('il database rifiuta stanza e orario duplicati', vincolo_database)
prova('20 letture in parallelo', letture_parallele)
prova('6 export in parallelo', export_parallelo)


# =====================================================================
area('calendario')
GIORNI_SPECIALI = [
    (date(2026, 10, 25), 'cambio ora solare'),
    (date(2026, 3, 29), 'cambio ora legale'),
    (date(2026, 2, 28), 'fine febbraio'),
    (date(2026, 12, 31), 'ultimo giorno dell anno'),
    (date(2027, 1, 1), 'primo giorno dell anno'),
    (date(2028, 2, 29), 'anno bisestile'),
]


def fai_calendario(g, nota):
    def f():
        s = S()
        v = servizi.griglia(s, g, 1)
        resp = CL.get('/giorno/%s?struttura=1' % g.isoformat())
        s.close()
        assert len(v['fasce']) == 24, '%d fasce invece di 24' % len(v['fasce'])
        assert resp.status_code == 200, 'HTTP %d' % resp.status_code
        return servizi.etichetta_giorno(g)
    return f


for g, nota in GIORNI_SPECIALI:
    prova('%s (%s)' % (g.isoformat(), nota), fai_calendario(g, nota))


# =====================================================================
ordine = []
for stato, ar, nome, msg in esiti:
    if ar not in ordine:
        ordine.append(ar)

print()
for ar in ordine:
    gruppo = [e for e in esiti if e[1] == ar]
    rotti = [e for e in gruppo if e[0] != 'OK']
    print('%-26s %3d prove  %s' % (ar, len(gruppo),
                                   'tutte a posto' if not rotti else '%d DA SISTEMARE' % len(rotti)))

guasti = [e for e in esiti if e[0] != 'OK']
if guasti:
    print('\nDettaglio:')
    for stato, ar, nome, msg in guasti:
        print('  %-7s [%s] %s\n          %s' % (stato, ar, nome, msg))

print('\n%d prove totali, %d superate, %d da sistemare'
      % (len(esiti), len(esiti) - len(guasti), len(guasti)))
