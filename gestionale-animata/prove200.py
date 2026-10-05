# -*- coding: utf-8 -*-
"""Terza suite. Molte prove generate a matrice: se una rompe, il nome dice quale caso."""
import os
import tempfile
import random
import time as clock
import traceback
from datetime import datetime, date, time, timedelta

from sqlalchemy import select

DB = 'prove200.db'
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
G = date(2026, 9, 15)

esiti, _area = [], ['']


def prova(nome, f):
    try:
        esiti.append(('OK', _area[0], nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', _area[0], nome, str(e) or 'asserzione fallita'))
    except Exception:
        esiti.append(('ERRORE', _area[0], nome,
                      traceback.format_exc().strip().splitlines()[-1]))


def area(n):
    _area[0] = n


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


def metti(s, h, m, durata, g=G, stanza='Ambulatorio 1', medico='Lippiello'):
    r, o, p = rif(s, stanza, medico)
    i = datetime.combine(g, time(h, m))
    a = Appuntamento(risorsa=r, operatore=o, prestazione=p, inizio=i,
                     fine=i + timedelta(minutes=durata))
    s.add(a)
    s.commit()
    return a


# =====================================================================
area('modello: colore')
COLORI = [
    ('#0087B4', True), ('#000000', True), ('#ffffff', True), ('#AbCdEf', True),
    ('#fff', False), ('#12345', False), ('#1234567', False), ('', False),
    (None, False), ('red', False), ('rgb(1,2,3)', False),
    ('#12345Z', False), ('javascript:alert(1)', False),
    ('#0087B4; content: url(x)', False), ('  #0087B4  ', False),
    ('#0087b4\n', False), ('#0087B4\t', False), ('#0087B4 ', False),
]


def fai_colore(valore, valido):
    def f():
        s = S()
        o = s.scalars(select(Operatore).where(Operatore.cognome == 'Marino')).first()
        prima = o.colore
        o.colore = valore
        ottenuto = o.colore_sicuro
        o.colore = prima
        s.commit(); s.close()
        if valido:
            assert ottenuto == valore, '%r respinto a torto (dato %r)' % (valore, ottenuto)
        else:
            assert ottenuto == '#154381', '%r accettato: %r' % (valore, ottenuto)
    return f


for v, ok in COLORI:
    prova('colore %r %s' % (v, 'accettato' if ok else 'respinto'), fai_colore(v, ok))


# =====================================================================
area('modello: etichette')
ETICHETTE = [
    ('Rossi', 'Mario', 'Rossi Mario'), ('Rossi', '', 'Rossi'),
    ('Rossi', None, 'Rossi'), ('De Luca', 'Anna Maria', 'De Luca Anna Maria'),
    ("D'Amico", 'Nino', "D'Amico Nino"), ('Sanmartinò', 'Andrè', 'Sanmartinò Andrè'),
]


def fai_etichetta(cognome, nome, atteso):
    def f():
        p = Paziente(cognome=cognome, nome=nome)
        o = Operatore(cognome=cognome, nome=nome)
        assert p.etichetta == atteso, 'paziente: %r' % p.etichetta
        assert o.etichetta == atteso, 'operatore: %r' % o.etichetta
    return f


for c, n, att in ETICHETTE:
    prova('etichetta %r + %r' % (c, n), fai_etichetta(c, n, att))


# =====================================================================
area('modello: validita turni')
def fai_vale_il(giorno_turno, giorno_prova, da, a, atteso, nota):
    def f():
        t = Turno(giorno_settimana=giorno_turno, ora_inizio=time(8, 0),
                  ora_fine=time(14, 0), valido_da=da, valido_a=a)
        assert t.vale_il(giorno_prova) == atteso, \
            'vale_il(%s) = %s' % (giorno_prova, t.vale_il(giorno_prova))
    return f


MAR = date(2026, 9, 15)     # martedi
MER = date(2026, 9, 16)
VALIDITA = [
    (1, MAR, date(2026, 1, 1), None, True, 'aperto a destra'),
    (1, MAR, date(2026, 9, 15), None, True, 'inizia proprio quel giorno'),
    (1, MAR, date(2026, 9, 16), None, False, 'inizia il giorno dopo'),
    (1, MAR, date(2026, 1, 1), date(2026, 9, 15), True, 'finisce proprio quel giorno'),
    (1, MAR, date(2026, 1, 1), date(2026, 9, 14), False, 'finito il giorno prima'),
    (1, MAR, date(2026, 10, 1), date(2026, 12, 31), False, 'tutto nel futuro'),
    (1, MAR, date(2025, 1, 1), date(2025, 12, 31), False, 'tutto nel passato'),
    (2, MAR, date(2026, 1, 1), None, False, 'giorno di settimana diverso'),
    (2, MER, date(2026, 1, 1), None, True, 'giorno di settimana giusto'),
    (0, date(2026, 9, 14), date(2026, 1, 1), None, True, 'lunedi'),
    (5, date(2026, 9, 19), date(2026, 1, 1), None, True, 'sabato'),
    (6, date(2026, 9, 20), date(2026, 1, 1), None, True, 'domenica'),
]
for gt, gp, da, a, att, nota in VALIDITA:
    prova('turno %s' % nota, fai_vale_il(gt, gp, da, a, att, nota))


# =====================================================================
area('fasce della giornata')
def fai_fasce(orari, primo_atteso, ultimo_atteso, nota):
    def f():
        finti = []
        for h, m, durata in orari:
            i = datetime.combine(G, time(h, m))
            finti.append(type('X', (), {'inizio': i,
                                        'fine': i + timedelta(minutes=durata)})())
        elenco = servizi.fasce(finti)
        assert elenco[0].strftime('%H:%M') == primo_atteso, \
            'prima fascia %s invece di %s' % (elenco[0], primo_atteso)
        assert elenco[-1].strftime('%H:%M') == ultimo_atteso, \
            'ultima fascia %s invece di %s' % (elenco[-1], ultimo_atteso)
        passi = [(datetime.combine(G, elenco[i + 1]) - datetime.combine(G, elenco[i])).seconds // 60
                 for i in range(len(elenco) - 1)]
        assert set(passi) == {30}, 'passo non costante: %s' % set(passi)
        return '%s -> %s (%d fasce)' % (primo_atteso, ultimo_atteso, len(elenco))
    return f


CASI_FASCE = [
    ([], '08:00', '19:30', 'nessun appuntamento'),
    ([(10, 0, 30)], '08:00', '19:30', 'tutto dentro la finestra'),
    ([(7, 0, 30)], '07:00', '19:30', 'uno alle 07:00'),
    ([(6, 15, 30)], '06:00', '19:30', 'uno alle 06:15'),
    ([(0, 0, 30)], '00:00', '19:30', 'uno a mezzanotte'),
    ([(20, 0, 30)], '08:00', '20:00', 'uno alle 20:00'),
    ([(23, 30, 30)], '08:00', '23:30', 'uno alle 23:30'),
    ([(22, 0, 60)], '08:00', '22:30', 'finisce alle 23:00'),
    ([(6, 0, 30), (22, 0, 30)], '06:00', '22:00', 'agli estremi'),
    ([(19, 30, 30)], '08:00', '19:30', 'ultima fascia standard'),
    ([(19, 45, 30)], '08:00', '20:00', 'sfora di un quarto d ora'),
    ([(8, 0, 720)], '08:00', '19:30', 'dodici ore filate'),
]
for orari, primo, ultimo, nota in CASI_FASCE:
    prova('fasce: %s' % nota, fai_fasce(orari, primo, ultimo, nota))


# =====================================================================
area('collocazione di ogni mezz ora')
def fai_mezzora(h, m):
    def f():
        s = S(); pulisci(s)
        a = metti(s, h, m, 20)
        v = servizi.griglia(s, G, 1)
        col = v['colonne'][0]
        trovate = [f2 for f2, c in zip(v['fasce'], col['celle'])
                   if c['stato'] == 'occupata' and any(x.id == a.id for x in c['apps'])]
        assert len(trovate) == 1, 'comparso %d volte' % len(trovate)
        assert trovate[0] == time(h, m), \
            'collocato alle %s invece che alle %02d:%02d' % (trovate[0], h, m)
        assert len(col['celle']) == len(v['fasce']), 'celle e fasce disallineate'
        s.close()
    return f


for h in range(24):
    for m in (0, 30):
        prova('appuntamento alle %02d:%02d' % (h, m), fai_mezzora(h, m))


# =====================================================================
area('durate')
for durata in (5, 10, 15, 20, 25, 29, 30, 31, 35, 45, 59, 60, 61, 90, 119, 120, 180, 300):
    def fai_durata(d):
        def f():
            s = S(); pulisci(s)
            metti(s, 9, 0, d)
            col = servizi.griglia(s, G, 1)['colonne'][0]
            occ = [c for c in col['celle'] if c['stato'] == 'occupata']
            coperte = [c for c in col['celle'] if c['stato'] == 'coperta']
            s.close()
            assert len(occ) == 1, '%d celle occupate' % len(occ)
            atteso = max(1, -(-d // 30))
            assert occ[0]['righe'] == atteso, \
                '%d minuti: %d fasce invece di %d' % (d, occ[0]['righe'], atteso)
            assert len(coperte) == atteso - 1, \
                'celle coperte %d invece di %d' % (len(coperte), atteso - 1)
        return f
    prova('durata %d minuti' % durata, fai_durata(durata))


# =====================================================================
area('conflitti a piu appuntamenti')
def conflitti_multipli():
    s = S(); pulisci(s)
    metti(s, 9, 0, 30); metti(s, 10, 0, 30); metti(s, 11, 0, 30)
    r, o, _ = rif(s)
    i = datetime.combine(G, time(9, 0))
    c = servizi.conflitti(s, r.id, o.id, i, i + timedelta(minutes=180))
    s.close()
    assert len(c) == 3, 'segnalati %d conflitti su 3' % len(c)
    return '3 conflitti elencati'


def conflitto_messaggio_utile():
    s = S(); pulisci(s)
    metti(s, 10, 0, 30)
    r, o, _ = rif(s)
    i = datetime.combine(G, time(10, 0))
    c = servizi.conflitti(s, r.id, o.id, i, i + timedelta(minutes=30))
    s.close()
    assert 'Ambulatorio 1' in c[0] and '10:00' in c[0], 'messaggio poco utile: %s' % c[0]
    return c[0][:60]


def conflitto_medico_nomina_stanza():
    s = S(); pulisci(s)
    metti(s, 10, 0, 30)
    r, o, _ = rif(s, 'Ambulatorio 3', 'Lippiello')
    i = datetime.combine(G, time(10, 0))
    c = servizi.conflitti(s, r.id, o.id, i, i + timedelta(minutes=30))
    s.close()
    assert 'Ambulatorio 1' in c[0], 'non dice dove si trova il medico: %s' % c[0]
    return c[0][:60]


def conflitto_giorno_diverso():
    s = S(); pulisci(s); pulisci(s, G + timedelta(days=1))
    metti(s, 10, 0, 30)
    r, o, _ = rif(s)
    i = datetime.combine(G + timedelta(days=1), time(10, 0))
    c = servizi.conflitti(s, r.id, o.id, i, i + timedelta(minutes=30))
    s.close()
    assert not c, 'conflitto fra giorni diversi: %s' % c[:1]


def conflitto_a_mezzanotte():
    s = S(); pulisci(s)
    r, o, p = rif(s)
    i = datetime.combine(G, time(23, 30))
    s.add(Appuntamento(risorsa=r, operatore=o, prestazione=p, inizio=i,
                       fine=i + timedelta(minutes=60)))
    s.commit()
    i2 = datetime.combine(G + timedelta(days=1), time(0, 15))
    c = servizi.conflitti(s, r.id, o.id, i2, i2 + timedelta(minutes=30))
    s.close()
    assert c, 'un appuntamento che sfora la mezzanotte non blocca il giorno dopo'


def escludi_id_inesistente():
    s = S(); pulisci(s)
    metti(s, 10, 0, 30)
    r, o, _ = rif(s)
    i = datetime.combine(G, time(10, 0))
    c = servizi.conflitti(s, r.id, o.id, i, i + timedelta(minutes=30), escludi_id=999999)
    s.close()
    assert c, 'escludendo un id inesistente il conflitto va comunque segnalato'


def stanza_libera_altro_medico():
    s = S(); pulisci(s)
    metti(s, 10, 0, 30, stanza='Ambulatorio 1', medico='Lippiello')
    r, o, _ = rif(s, 'Ambulatorio 2', 'Esposito')
    i = datetime.combine(G, time(10, 0))
    c = servizi.conflitti(s, r.id, o.id, i, i + timedelta(minutes=30))
    s.close()
    assert not c, 'altra stanza e altro medico non dovrebbero entrare in conflitto'


for nome, f in [('tre conflitti elencati tutti', conflitti_multipli),
                ('il messaggio nomina stanza e ora', conflitto_messaggio_utile),
                ('il conflitto sul medico nomina la stanza', conflitto_medico_nomina_stanza),
                ('nessun conflitto fra giorni diversi', conflitto_giorno_diverso),
                ('conflitto a cavallo della mezzanotte', conflitto_a_mezzanotte),
                ('escludi_id inesistente non maschera nulla', escludi_id_inesistente),
                ('stanza e medico diversi: via libera', stanza_libera_altro_medico)]:
    prova(nome, f)


# =====================================================================
area('rotte con parametri sporchi')
SPORCHI = ['abc', '', '-1', '0', '999999', '1.5', '1e3', 'null', 'NaN',
           "1'", '1;2', '%00', 'null%20', '../1', '<script>', '1 OR 1=1',
           '٣', '١٢٣', '+1', ' 1 ']
for v in SPORCHI:
    def fai_struttura(valore):
        def f():
            r = CL.get('/giorno/2026-09-15?struttura=%s' % valore)
            assert r.status_code < 500, 'HTTP %d' % r.status_code
            return 'HTTP %d' % r.status_code
        return f
    prova('struttura=%r' % v, fai_struttura(v))

for v in SPORCHI[:10]:
    def fai_risorsa(valore):
        def f():
            r = CL.get('/appuntamento?risorsa=%s&data=2026-09-15' % valore)
            assert r.status_code < 500, 'HTTP %d' % r.status_code
            return 'HTTP %d' % r.status_code
        return f
    prova('risorsa=%r sul form' % v, fai_risorsa(v))

DATE_URL = ['2026-09-15', '2026-13-01', '2026-00-10', '2026-02-30', '0000-01-01',
            '9999-12-31', 'oggi', '15/09/2026', '2026-9-5', '', '2026-09-15T10:00',
            '../../etc/passwd', '2026-09-15%00']
for v in DATE_URL:
    def fai_data(valore):
        def f():
            r = CL.get('/giorno/%s' % valore)
            assert r.status_code < 500, 'HTTP %d' % r.status_code
            return 'HTTP %d' % r.status_code
        return f
    prova('giorno/%r' % v, fai_data(v))

for v in DATE_URL[:8]:
    def fai_export(valore):
        def f():
            r = CL.get('/esporta/%s' % valore)
            assert r.status_code < 500, 'HTTP %d' % r.status_code
            return 'HTTP %d' % r.status_code
        return f
    prova('esporta/%r' % v, fai_export(v))


# =====================================================================
area('modulo di salvataggio')
def base_modulo(s):
    r, o, p = rif(s)
    return {'struttura': 1, 'risorsa': r.id, 'operatore': o.id, 'prestazione': p.id,
            'data': G.isoformat(), 'ora': '16:00', 'durata': '30'}


MANCANTI = ['risorsa', 'operatore', 'prestazione', 'data', 'ora', 'durata', 'struttura']
for campo in MANCANTI:
    def fai_mancante(c):
        def f():
            s = S(); pulisci(s); d = base_modulo(s); s.close()
            d.pop(c)
            r = CL.post('/appuntamento', data=d)
            assert r.status_code < 500, 'HTTP %d senza %s' % (r.status_code, c)
            return 'HTTP %d' % r.status_code
        return f
    prova('POST senza il campo %s' % campo, fai_mancante(campo))

VALORI_ORA = ['16:00', '00:00', '23:59', '25:00', '16:60', '16', '', 'abc',
              '16:00:00', '4 PM', '16.00', '−16:00']
for v in VALORI_ORA:
    def fai_ora(valore):
        def f():
            s = S(); pulisci(s); d = base_modulo(s); s.close()
            d['ora'] = valore
            r = CL.post('/appuntamento', data=d)
            assert r.status_code < 500, 'HTTP %d con ora %r' % (r.status_code, valore)
            return 'HTTP %d' % r.status_code
        return f
    prova('POST con ora %r' % v, fai_ora(v))

VALORI_DURATA = ['30', '5', '0', '-5', '', 'abc', '1e3', '999999', '4.5', '  30  ']
for v in VALORI_DURATA:
    def fai_dur(valore):
        def f():
            s = S(); pulisci(s); d = base_modulo(s); s.close()
            d['durata'] = valore
            r = CL.post('/appuntamento', data=d)
            assert r.status_code < 500, 'HTTP %d con durata %r' % (r.status_code, valore)
            s2 = S()
            a = s2.scalars(select(Appuntamento).where(
                Appuntamento.inizio == datetime.combine(G, time(16, 0)))).first()
            brutto = a is not None and a.fine <= a.inizio
            s2.close()
            assert not brutto, 'durata %r ha prodotto un appuntamento a rovescio' % valore
            return 'HTTP %d' % r.status_code
        return f
    prova('POST con durata %r' % v, fai_dur(v))


def eliminazione_senza_id():
    r = CL.post('/appuntamento', data={'azione': 'elimina', 'struttura': 1})
    assert r.status_code < 500, 'HTTP %d' % r.status_code
    return 'HTTP %d' % r.status_code


def eliminazione_due_volte():
    s = S(); pulisci(s)
    a = metti(s, 16, 30, 30); aid = a.id; s.close()
    CL.post('/appuntamento/%d' % aid, data={'azione': 'elimina', 'struttura': 1})
    r = CL.post('/appuntamento/%d' % aid, data={'azione': 'elimina', 'struttura': 1})
    assert r.status_code == 404, 'seconda eliminazione -> HTTP %d' % r.status_code
    return '404 alla seconda'


prova('eliminazione senza id', eliminazione_senza_id)
prova('eliminazione ripetuta', eliminazione_due_volte)


# =====================================================================
area('testo ostile')
PAYLOAD = [
    '<script>alert(1)</script>', '<img src=x onerror=alert(1)>',
    '"><svg onload=alert(1)>', "'><iframe src=javascript:alert(1)>",
    '{{ 7*7 }}', '${7*7}', '<%= 7*7 %>', '{% raw %}x{% endraw %}',
    'a' * 500, '\x00nullo', 'Rossi\tMario', '../../../etc/passwd',
    'ò' * 100, '🙂🙃' * 20, 'Rossi&amp;Figli',
]
for testo in PAYLOAD:
    def fai_payload(t):
        def f():
            s = S(); pulisci(s)
            r, o, p = rif(s)
            paz = Paziente(cognome=t[:200].replace('\x00', ''), telefono='333')
            s.add(paz); s.flush()
            i = datetime.combine(G, time(10, 0))
            s.add(Appuntamento(risorsa=r, operatore=o, prestazione=p, paziente=paz,
                               inizio=i, fine=i + timedelta(minutes=30)))
            s.commit()
            resp = CL.get('/giorno/2026-09-15?struttura=1')
            html = resp.get_data(as_text=True)
            esp = CL.get('/esporta/2026-09-15?struttura=1')
            memorizzato = paz.cognome
            s.close()
            assert resp.status_code == 200, 'griglia HTTP %d' % resp.status_code
            assert esp.status_code == 200, 'export HTTP %d' % esp.status_code
            # il testo del paziente non deve arrivare in pagina con i suoi marcatori
            if '<' in memorizzato or '>' in memorizzato:
                assert memorizzato not in html, 'testo del paziente non filtrato'
            assert '<script>alert' not in html, 'script eseguibile in pagina'
            assert 'onerror=alert(1)>' not in html, 'handler attivo in pagina'
            # un'espressione valutata darebbe 49 al posto del testo: il testo deve
            # comparire tale e quale. Cercare "49" in tutta la pagina non basta:
            # puo' stare in un numero qualsiasi (la versione del logo, per esempio)
            if '7*7' in memorizzato:
                assert '7*7' in html and '>49<' not in html, 'espressione del template valutata'
        return f
    prova('paziente %r' % testo[:22], fai_payload(testo))


# =====================================================================
area('export')
def fai_export_giorno(g, nota):
    def f():
        s = S()
        percorso = os.path.join(tempfile.gettempdir(), 'e-%s.xlsx' % g.isoformat())
        servizi.esporta_giorno(s, g, 1, percorso)
        import openpyxl
        ws = openpyxl.load_workbook(percorso).active
        v = servizi.griglia(s, g, 1)
        s.close()
        assert ws.max_row <= 2 + len(v['fasce']), \
            '%d righe contro %d' % (ws.max_row, 2 + len(v['fasce']))
        fuori = [str(m) for m in ws.merged_cells.ranges if m.max_row > ws.max_row]
        assert not fuori, 'merge oltre la tabella: %s' % fuori[:1]
        assert ws.freeze_panes == 'B3', 'riquadri non bloccati'
        assert os.path.getsize(percorso) > 3000, 'file troppo piccolo'
        return '%d righe, %d colonne' % (ws.max_row, ws.max_column)
    return f


GIORNI_EXPORT = [date(2026, 9, 15), date(2026, 9, 20), date(2026, 9, 14),
                 date(2026, 12, 25), date(2027, 1, 1), date(2028, 2, 29),
                 date(2026, 10, 25), date(2026, 3, 29)]
for g in GIORNI_EXPORT:
    prova('export del %s' % g.isoformat(), fai_export_giorno(g, ''))


def export_con_tutto_pieno():
    s = S(); g = date(2026, 11, 3); pulisci(s, g)
    for h in range(8, 20):
        for m in (0, 30):
            metti(s, h, m, 30, g=g)
    percorso = os.path.join(tempfile.gettempdir(), 'e-pieno.xlsx')
    servizi.esporta_giorno(s, g, 1, percorso)
    import openpyxl
    ws = openpyxl.load_workbook(percorso).active
    pieni = sum(1 for r in range(3, ws.max_row + 1) if ws.cell(r, 2).value)
    s.close()
    assert pieni == 24, '%d celle compilate su 24' % pieni
    return '24 fasce piene'


prova('export con la giornata tutta piena', export_con_tutto_pieno)


# =====================================================================
area('invarianti su dati casuali')
def fai_giro(semenza):
    def f():
        casuale = random.Random(semenza * 7919)
        s = S()
        giorno = date(2027, 1, 1) + timedelta(days=semenza)
        pulisci(s, giorno)
        stanze = ['Ambulatorio 1', 'Ambulatorio 2', 'Ambulatorio 3']
        creati = {n: [] for n in stanze}
        for _ in range(casuale.randint(4, 18)):
            stanza = casuale.choice(stanze)
            h = casuale.randint(5, 22)
            m = casuale.choice([0, 3, 7, 15, 20, 25, 30, 38, 45, 52, 59])
            durata = casuale.choice([5, 10, 15, 20, 25, 30, 45, 50, 60, 75, 90, 150])
            r, o, p = rif(s, stanza, casuale.choice(['Lippiello', 'Esposito', 'Russo']))
            i = datetime.combine(giorno, time(h, m))
            fine = i + timedelta(minutes=durata)
            if fine.date() != giorno:
                continue
            if servizi.conflitti(s, r.id, o.id, i, fine):
                continue
            a = Appuntamento(risorsa=r, operatore=o, prestazione=p, inizio=i, fine=fine)
            s.add(a)
            try:
                s.commit()
            except Exception:
                s.rollback()
                continue
            creati[stanza].append(a.id)

        v = servizi.griglia(s, giorno, 1)
        assert len(v['fasce']) == len(set(v['fasce'])), 'fasce duplicate'
        for col in v['colonne']:
            celle = col['celle']
            nome = col['risorsa'].nome
            assert len(celle) == len(v['fasce']), \
                '%s: celle %d contro fasce %d' % (nome, len(celle), len(v['fasce']))
            visti = [a.id for c in celle if c['stato'] == 'occupata' for a in c['apps']]
            if nome in creati:
                assert sorted(visti) == sorted(creati[nome]), \
                    '%s: in griglia %d su %d creati' % (nome, len(visti), len(creati[nome]))
            assert len(visti) == len(set(visti)), '%s: doppioni in griglia' % nome
            coperte = len([c for c in celle if c['stato'] == 'coperta'])
            estese = sum(c['righe'] - 1 for c in celle if c['stato'] == 'occupata')
            assert coperte == estese, \
                '%s: coperte %d contro estensioni %d' % (nome, coperte, estese)
            for i2, c in enumerate(celle):
                if c['stato'] == 'occupata':
                    assert i2 + c['righe'] <= len(celle), '%s: estensione oltre la tabella' % nome

        resp = CL.get('/giorno/%s?struttura=1' % giorno.isoformat())
        assert resp.status_code == 200, 'griglia HTTP %d' % resp.status_code
        servizi.esporta_giorno(s, giorno, 1, os.path.join(tempfile.gettempdir(), 'fuzz2.xlsx'))
        totale = sum(len(x) for x in creati.values())
        s.close()
        return '%d appuntamenti su 3 stanze' % totale
    return f


for semenza in range(1, 31):
    prova('giro casuale %02d' % semenza, fai_giro(semenza))


# =====================================================================
area('calendario')
DATE_CONFINE = [
    (date(2026, 1, 1), 'capodanno'), (date(2026, 1, 31), 'fine gennaio'),
    (date(2026, 2, 28), 'fine febbraio non bisestile'), (date(2026, 3, 1), 'primo marzo'),
    (date(2026, 3, 29), 'ora legale'), (date(2026, 10, 25), 'ora solare'),
    (date(2026, 4, 30), 'fine mese di 30'), (date(2026, 5, 1), 'primo maggio'),
    (date(2026, 6, 30), 'fine giugno'), (date(2026, 8, 15), 'ferragosto'),
    (date(2026, 12, 31), 'san silvestro'), (date(2027, 1, 1), 'anno nuovo'),
    (date(2028, 2, 29), 'ventinove febbraio'), (date(2028, 3, 1), 'dopo il bisestile'),
    (date(2030, 12, 31), 'fra quattro anni'),
]
for g, nota in DATE_CONFINE:
    def fai_conf(giorno):
        def f():
            s = S()
            v = servizi.griglia(s, giorno, 1)
            resp = CL.get('/giorno/%s?struttura=1' % giorno.isoformat())
            et = servizi.etichetta_giorno(giorno)
            s.close()
            assert len(v['fasce']) >= 24, '%d fasce' % len(v['fasce'])
            assert resp.status_code == 200, 'HTTP %d' % resp.status_code
            assert str(giorno.year) in et, 'etichetta senza anno: %s' % et
            return et
        return f
    prova('%s (%s)' % (g.isoformat(), nota), fai_conf(g))


# =====================================================================
area('prestazioni')
def griglia_carica():
    s = S(); g = date(2027, 6, 1); pulisci(s, g)
    stanze = ['Ambulatorio 1', 'Ambulatorio 2', 'Ambulatorio 3', 'Ambulatorio 4']
    n = 0
    for stanza in stanze:
        for h in range(8, 20):
            for m in (0, 30):
                metti(s, h, m, 30, g=g, stanza=stanza,
                      medico={'Ambulatorio 1': 'Lippiello', 'Ambulatorio 2': 'Esposito',
                              'Ambulatorio 3': 'Russo', 'Ambulatorio 4': 'Marino'}[stanza])
                n += 1
    avvio = clock.time()
    v = servizi.griglia(s, g, 1)
    durata = clock.time() - avvio
    s.close()
    assert durata < 3.0, 'griglia con %d appuntamenti in %.2f secondi' % (n, durata)
    return '%d appuntamenti in %.2f s' % (n, durata)


def pagina_carica():
    avvio = clock.time()
    r = CL.get('/giorno/2027-06-01?struttura=1')
    durata = clock.time() - avvio
    assert r.status_code == 200, 'HTTP %d' % r.status_code
    assert durata < 5.0, 'pagina servita in %.2f secondi' % durata
    return '%.2f s, %d KB' % (durata, len(r.get_data()) // 1024)


def export_carico():
    s = S()
    avvio = clock.time()
    servizi.esporta_giorno(s, date(2027, 6, 1), 1, os.path.join(tempfile.gettempdir(), 'e-carico.xlsx'))
    durata = clock.time() - avvio
    s.close()
    assert durata < 10.0, 'export in %.2f secondi' % durata
    return '%.2f s' % durata


def molte_pagine_di_fila():
    avvio = clock.time()
    for n in range(30):
        r = CL.get('/giorno/2026-09-%02d?struttura=%d' % (1 + n % 28, 1 + n % 2))
        assert r.status_code == 200, 'HTTP %d al giro %d' % (r.status_code, n)
    durata = clock.time() - avvio
    assert durata < 20.0, '30 pagine in %.2f secondi' % durata
    return '30 pagine in %.2f s' % durata


for nome, f in [('griglia con quasi 100 appuntamenti', griglia_carica),
                ('pagina con la giornata piena', pagina_carica),
                ('export della giornata piena', export_carico),
                ('trenta pagine di fila', molte_pagine_di_fila)]:
    prova(nome, f)


# =====================================================================
area('avvio del programma')
def nomi_risolti():
    import app as mod
    for nome in ('percorso_db', 'prepara_registro', 'porta_in_uso',
                 'cartella_risorse', 'principale', 'avvia', 'salva', 'elenchi'):
        assert hasattr(mod, nome), 'app.py non espone %s' % nome
    return '8 nomi presenti'


def registro_scrivibile():
    import app as mod
    percorso = mod.prepara_registro()
    logging_ok = os.path.exists(os.path.dirname(percorso))
    assert logging_ok, 'cartella del registro non creata: %s' % percorso
    return os.path.basename(percorso)


def cartella_risorse_valida():
    import app as mod
    base = mod.cartella_risorse()
    assert os.path.isdir(os.path.join(base, 'templates')), 'templates non trovati in %s' % base
    assert os.path.isdir(os.path.join(base, 'static')), 'static non trovati in %s' % base
    return base


def porta_libera_e_occupata():
    import app as mod
    assert mod.porta_in_uso(59999) is False, 'porta 59999 data per occupata'
    return 'rilevamento porta funzionante'


def percorso_database():
    from modelli import percorso_db
    p = percorso_db()
    assert os.path.isdir(os.path.dirname(p)), 'cartella del database non creata'
    assert p.endswith('agende.db'), 'nome del database inatteso: %s' % p
    return p


for nome, f in [('tutti i nomi usati esistono', nomi_risolti),
                ('il registro degli errori e scrivibile', registro_scrivibile),
                ('templates e static raggiungibili', cartella_risorse_valida),
                ('rilevamento della porta in uso', porta_libera_e_occupata),
                ('percorso del database', percorso_database)]:
    prova(nome, f)


# =====================================================================
ordine = []
for _, ar, _, _ in esiti:
    if ar not in ordine:
        ordine.append(ar)

print()
for ar in ordine:
    gruppo = [e for e in esiti if e[1] == ar]
    rotti = [e for e in gruppo if e[0] != 'OK']
    print('%-34s %3d prove  %s' % (ar, len(gruppo),
                                   'tutte a posto' if not rotti else '%d DA SISTEMARE' % len(rotti)))

guasti = [e for e in esiti if e[0] != 'OK']
if guasti:
    print('\nDettaglio:')
    for stato, ar, nome, msg in guasti:
        print('  %-7s [%s] %s\n          %s' % (stato, ar, nome, msg))

print('\n%d prove totali, %d superate, %d da sistemare'
      % (len(esiti), len(esiti) - len(guasti), len(guasti)))
