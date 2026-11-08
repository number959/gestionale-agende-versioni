# -*- coding: utf-8 -*-
"""Campagna generativa sul gestionale.

Non 2000 assert scritti a mano: 2000 casi generati, ognuno confrontato con un
oracolo indipendente o con un invariante che deve valere sempre.

I guasti vengono raggruppati per causa: della stessa causa si tengono i primi
tre esempi e poi quel filone si chiude. Se le cause distinte superano la soglia
la campagna si ferma del tutto, perche' andare avanti non aggiunge informazione.
Ogni guasto riporta la semenza che lo riproduce.
"""
import io
import os
import random
import re
import sys
import time as orologio
from datetime import datetime, date, time, timedelta

from sqlalchemy import select, func

DB = 'campagna.db'
LIMITE_ESEMPI = 3        # esempi tenuti per ogni causa
LIMITE_CAUSE = 8         # cause distinte oltre le quali si interrompe
BUDGET_SECONDI = 600

if os.path.exists(DB):
    os.remove(DB)

import seed
import servizi
import marchio
import app as A
from modelli import (Appuntamento, Risorsa, Operatore, Prestazione,
                     Paziente, Turno, Struttura)

Sessione = seed.popola('sqlite:///' + DB)
A.Sessione = Sessione
A.app.config['TESTING'] = True
CL = A.app.test_client()
AVVIO = orologio.monotonic()


# ===================================================== raccolta dei guasti
class Raccolta:
    def __init__(self):
        self.casi = 0
        self.per_area = {}
        self.guasti = {}          # firma -> {'area','esempi':[...], 'conteggio'}
        self.chiuse = set()
        self.interrotta = None

    def firma(self, area, messaggio):
        """Due guasti con la stessa causa devono produrre la stessa firma:
        si azzerano i numeri e le date, che cambiano a ogni caso."""
        m = re.sub(r'\d+', 'N', messaggio)
        m = re.sub(r"\s+", ' ', m).strip()[:120]
        return '%s|%s' % (area, m)

    def caso(self, area):
        self.casi += 1
        self.per_area[area] = self.per_area.get(area, 0) + 1

    def guasto(self, area, messaggio, riproduci):
        f = self.firma(area, messaggio)
        if f in self.chiuse:
            self.guasti[f]['conteggio'] += 1
            return
        g = self.guasti.setdefault(f, {'area': area, 'esempi': [], 'conteggio': 0})
        g['conteggio'] += 1
        g['esempi'].append((messaggio, riproduci))
        if len(g['esempi']) >= LIMITE_ESEMPI:
            self.chiuse.add(f)
        if len(self.guasti) >= LIMITE_CAUSE:
            self.interrotta = 'raggiunte %d cause distinte' % len(self.guasti)

    def basta(self):
        if self.interrotta:
            return True
        if orologio.monotonic() - AVVIO > BUDGET_SECONDI:
            self.interrotta = 'budget di tempo esaurito'
            return True
        return False


R = Raccolta()


def prova(area, riproduci, corpo):
    R.caso(area)
    try:
        corpo()
    except AssertionError as e:
        R.guasto(area, str(e) or 'asserzione fallita', riproduci)
    except Exception as e:
        R.guasto(area, '%s: %s' % (type(e).__name__, e), riproduci)


# ===================================================== mondo di prova
def prepara():
    s = Sessione()
    st = s.scalars(select(Struttura)).first()
    esistenti = {r.nome for r in s.scalars(select(Risorsa))}
    for i in range(7, 11):
        nome = 'Stanza prova %d' % i
        if nome not in esistenti:
            r = Risorsa(nome=nome, ordine=i)
            s.add(r)
            r.struttura = st
    if not s.scalars(select(Operatore).where(Operatore.cognome == 'Prova A')).first():
        s.add_all([Operatore(cognome='Prova A', colore='#334455'),
                   Operatore(cognome='Prova B', colore='#556677')])
    s.commit()
    prima = s.scalars(select(Struttura)).first().id
    dati = dict(
        risorse=[r.id for r in s.scalars(select(Risorsa))
                 if r.struttura_id == prima],
        tutte_le_risorse=[r.id for r in s.scalars(select(Risorsa))],
        operatori=[o.id for o in s.scalars(select(Operatore))],
        prestazioni=[p.id for p in s.scalars(select(Prestazione))],
        strutture=[x.id for x in s.scalars(select(Struttura))])
    s.close()
    return dati


MONDO = prepara()
GIORNO_BASE = date(2027, 1, 1)      # zona franca: nessun dato seminato nel 2027
_contatore_giorni = [0]


def giorno_nuovo():
    _contatore_giorni[0] += 1
    return GIORNO_BASE + timedelta(days=_contatore_giorni[0])


def libera(s, risorsa_id, inizio):
    return not s.scalars(select(Appuntamento).where(
        Appuntamento.risorsa_id == risorsa_id, Appuntamento.inizio == inizio)).first()


# =====================================================================
# 1. oracolo dei conflitti: implementazione indipendente della sovrapposizione
# =====================================================================
def sovrappongono(i1, f1, i2, f2):
    return i1 < f2 and i2 < f1


def caso_oracolo(semenza):
    c = random.Random(semenza)

    def corpo():
        s = Sessione()
        g = giorno_nuovo()
        stanze = c.sample(MONDO['risorse'], 2)
        medici = c.sample(MONDO['operatori'], 2)
        pid = c.choice(MONDO['prestazioni'])
        esistenti = []
        for _ in range(c.randint(1, 6)):
            rid, oid = c.choice(stanze), c.choice(medici)
            i = datetime.combine(g, time(c.randint(0, 22), c.choice([0, 7, 15, 23, 30, 45, 52])))
            f = i + timedelta(minutes=c.choice([5, 20, 30, 45, 60, 75, 120]))
            if f.date() != g or not libera(s, rid, i):
                continue
            s.add(Appuntamento(risorsa_id=rid, operatore_id=oid, prestazione_id=pid,
                               inizio=i, fine=f))
            s.commit()
            esistenti.append((rid, oid, i, f))

        rid, oid = c.choice(stanze), c.choice(medici)
        i = datetime.combine(g, time(c.randint(0, 22), c.choice([0, 11, 30, 41, 59])))
        f = i + timedelta(minutes=c.choice([5, 15, 30, 60, 90]))

        atteso = any((r == rid or o == oid) and sovrappongono(i, f, i2, f2)
                     for r, o, i2, f2 in esistenti)
        ottenuto = bool(servizi.conflitti(s, rid, oid, i, f))
        s.close()
        assert ottenuto == atteso, (
            'oracolo dice %s, codice dice %s' % ('conflitto' if atteso else 'libero',
                                                 'conflitto' if ottenuto else 'libero'))
    return corpo


# =====================================================================
# 2. invarianti della griglia
# =====================================================================
def caso_griglia(semenza):
    c = random.Random(semenza * 7919)

    def corpo():
        s = Sessione()
        g = giorno_nuovo()
        sid = MONDO['strutture'][0]
        creati = {}
        for _ in range(c.randint(2, 18)):
            rid = c.choice(MONDO['risorse'])
            i = datetime.combine(g, time(c.randint(0, 23), c.randint(0, 59)))
            f = i + timedelta(minutes=c.choice([5, 10, 17, 30, 45, 60, 95, 180, 600]))
            if f.date() != g or not libera(s, rid, i):
                continue
            a = Appuntamento(risorsa_id=rid, operatore_id=c.choice(MONDO['operatori']),
                             prestazione_id=c.choice(MONDO['prestazioni']), inizio=i, fine=f)
            s.add(a)
            s.commit()
            creati.setdefault(rid, []).append(a.id)

        v = servizi.griglia(s, g, sid)
        nfasce = len(v['fasce'])
        for col in v['colonne']:
            celle = col['celle']
            assert len(celle) == nfasce, 'celle N contro fasce N'
            visti = [a.id for x in celle if x['stato'] == 'occupata' for a in x['apps']]
            attesi = creati.get(col['risorsa'].id, [])
            assert sorted(visti) == sorted(attesi), \
                'stanza N: in griglia N appuntamenti su N creati'
            assert len(visti) == len(set(visti)), 'un appuntamento compare due volte'
            coperte = len([x for x in celle if x['stato'] == 'coperta'])
            estensioni = sum(x['righe'] - 1 for x in celle if x['stato'] == 'occupata')
            assert coperte == estensioni, 'coperte N contro estensioni N'
            for k, x in enumerate(celle):
                if x['stato'] == 'occupata':
                    assert k + x['righe'] <= nfasce, 'estensione oltre la tabella'
        # le fasce devono essere consecutive e senza salti
        for k in range(1, nfasce):
            atteso = (servizi._minuti(v['fasce'][k - 1]) + servizi.PASSO) % (24 * 60)
            assert servizi._minuti(v['fasce'][k]) == atteso, 'salto fra le fasce'
        r = CL.get('/giorno/%s?struttura=%d' % (g.isoformat(), sid))
        s.close()
        assert r.status_code == 200, 'griglia HTTP N'
    return corpo


# =====================================================================
# 3. l'ordine di inserimento non deve cambiare il risultato
# =====================================================================
def caso_ordine(semenza):
    c = random.Random(semenza * 104729)

    def corpo():
        s = Sessione()
        rid = c.choice(MONDO['risorse'])
        oid = c.choice(MONDO['operatori'])
        pid = c.choice(MONDO['prestazioni'])
        blocchi = []
        usati = set()
        for _ in range(c.randint(3, 8)):
            m = c.randint(0, 22) * 60 + c.choice([0, 13, 30, 47])
            if m in usati:
                continue
            usati.add(m)
            blocchi.append((m, c.choice([10, 20, 30, 45, 60])))

        def costruisci(ordine, g):
            for m, durata in ordine:
                i = datetime.combine(g, time(m // 60, m % 60))
                f = i + timedelta(minutes=durata)
                if f.date() != g or not libera(s, rid, i):
                    continue
                s.add(Appuntamento(risorsa_id=rid, operatore_id=oid,
                                   prestazione_id=pid, inizio=i, fine=f))
                s.commit()
            v = servizi.griglia(s, g, MONDO['strutture'][0])
            col = [x for x in v['colonne'] if x['risorsa'].id == rid][0]
            return [(f.strftime('%H:%M'), x['stato'], x.get('righe'),
                     tuple(sorted(a.inizio.strftime('%H:%M') for a in x.get('apps', []))))
                    for f, x in zip(v['fasce'], col['celle'])]

        # intervallo di date riservato a questa prova: due casi non devono
        # mai incrociarsi, altrimenti il confronto trova differenze inesistenti
        g1 = date(2040, 1, 2) + timedelta(days=semenza * 28)
        g2 = g1 + timedelta(days=7)      # stesso giorno della settimana, stessi turni
        primo = costruisci(blocchi, g1)
        mescolato = blocchi[:]
        c.shuffle(mescolato)
        secondo = costruisci(mescolato, g2)
        s.close()
        assert primo == secondo, 'la griglia cambia a seconda dell ordine di inserimento'
    return corpo


# =====================================================================
# 4. rotte con parametri sporchi: mai un 5xx
# =====================================================================
VELENI = ['', ' ', '0', '-1', '999999999999', '1.5', 'abc', 'null', 'None', 'NaN',
          "1' OR '1'='1", '<script>x</script>', '../../etc/passwd', '%00', '\x00',
          'A' * 500, 'àèìòù', '🙂', '1;2', '[]', '{}', 'true', '0x1', '+1', '1e5',
          '2026-09-15', '25:99', '--', '\n', '\t',
          # oltre il limite degli interi di SQLite
          '9' * 25, '-' + '9' * 25, str(2 ** 63)]
PERCORSI = ['/giorno/%s', '/giorno/%s?struttura=%s', '/appuntamento?risorsa=%s',
            '/appuntamento?data=%s&ora=%s', '/appuntamento/%s', '/esporta/%s',
            '/esporta/%s?struttura=%s', '/giorno/2027-01-01?struttura=%s',
            '/logo/%s', '/logo/%s?v=%s', '/anagrafiche/strutture/%s', '/anagrafiche?struttura=%s',
            # 1.3
            '/settimana/%s?struttura=%s&medico=%s', '/mese/%s?medico=%s', '/giorno/%s/elenco',
            '/conferme?data=%s&struttura=%s', '/stampa/%s?per=%s&tutti=%s', '/appuntamento/%s/promemoria',
            '/disponibilita?medico=%s&prestazione=%s&durata=%s&dal=%s&fascia=%s',
            '/statistiche?dal=%s&al=%s', '/pazienti?q=%s', '/pazienti/cerca?q=%s', '/pazienti/%s',
            '/pazienti/%s/unisci?altro=%s&q=%s', '/anagrafiche/assenze/%s', '/anagrafiche/chiusure/%s',
            '/anagrafiche/turni/nuovo?ripetizione=%s&data=%s', '/impostazioni/backup/%s',
            '/appuntamento?paziente_id=%s&medico=%s&prestazione=%s&durata=%s',
            # 1.4
            '/chiusura/%s?struttura=%s', '/cassa/%s?struttura=%s', '/cassa/mese/%s', '/cassa/mese/%s/excel',
            '/cassa/listino', '/attesa?medico=%s&chiuse=%s', '/attesa/%s', '/attesa/per/%s',
            '/attesa/nuova?paziente_id=%s&medico=%s', '/appuntamento/%s/sposta?dal=%s&tutte=%s',
            '/sposta?medico=%s&dal=%s&al=%s&modo=%s&sostituto=%s', '/sposta/avvisi?ids=%s', '/serie/%s',
            '/cose-da-fare', '/notifiche.json?struttura=%s', '/cerca-tutto.json?q=%s&struttura=%s',
            '/agenda-medico/%s?medico=%s', '/documenti/%s', '/moduli/%s', '/appuntamento/%s/modulo/%s',
            '/importa/%s', '/importa/%s/scarti.xlsx']


def caso_rotta(semenza):
    c = random.Random(semenza * 15485863)
    modello = c.choice(PERCORSI)
    quanti = modello.count('%s')
    valori = [c.choice(VELENI) for _ in range(quanti)]
    try:
        url = modello % tuple(valori)
    except TypeError:
        url = modello

    def corpo():
        r = CL.get(url)
        assert r.status_code < 500, 'HTTP N su %s' % modello
    return corpo, url


# =====================================================================
# 5. moduli sporchi: mai un 5xx, mai una riga incoerente
# =====================================================================
def caso_modulo(semenza):
    c = random.Random(semenza * 32452843)
    campi = ['struttura', 'risorsa', 'operatore', 'prestazione', 'data', 'ora',
             'durata', 'paziente', 'telefono', 'note',
             # 1.4: ripetizione, provenienza, lista d'attesa, importo
             'ripeti', 'ripeti_ogni', 'ripeti_unita', 'ripeti_volte', 'provenienza', 'attesa', 'importo']
    dati = {}
    for k in campi:
        scelta = c.random()
        if scelta < 0.15:
            continue                                 # campo assente
        if scelta < 0.55:
            dati[k] = c.choice(VELENI)               # valore velenoso
        else:
            dati[k] = {'struttura': str(c.choice(MONDO['strutture'])),
                       'risorsa': str(c.choice(MONDO['risorse'])),
                       'operatore': str(c.choice(MONDO['operatori'])),
                       'prestazione': str(c.choice(MONDO['prestazioni'])),
                       'data': giorno_nuovo().isoformat(),
                       'ora': '%02d:%02d' % (c.randint(0, 23), c.choice([0, 15, 30, 45])),
                       'durata': str(c.choice([5, 30, 60, 0, -10, 99999])),
                       'paziente': c.choice(['Rossi', 'Àlvarez', '', 'B' * 400]),
                       'telefono': c.choice(['0815551234', '', '+39 333 1234567']),
                       'note': c.choice(['', 'nota', 'X' * 1000]),
                       'ripeti': c.choice(['1', '', 'on']),
                       'ripeti_ogni': str(c.choice([1, 2, 0, 53, -1])),
                       'ripeti_unita': c.choice(['giorni', 'settimane', 'mesi', 'anni']),
                       'ripeti_volte': str(c.choice([2, 3, 1, 60])),
                       'provenienza': c.choice(['', 'INTERNET', 'MARTE']),
                       'attesa': str(c.choice([0, 1, 999])),
                       'importo': c.choice(['', '80', '1.250,50', '1e3', '-5'])}[k]

    def corpo():
        s = Sessione()
        ultimo = s.scalar(select(func.max(Appuntamento.id))) or 0
        s.close()
        r = CL.post('/appuntamento', data=dati, follow_redirects=False)
        assert r.status_code < 500, 'HTTP N con %s' % sorted(dati)
        s = Sessione()
        cattivi = s.scalars(select(Appuntamento).where(
            Appuntamento.fine <= Appuntamento.inizio)).all()
        orfani = [a.id for a in s.scalars(select(Appuntamento))
                  if a.risorsa is None or a.operatore is None]
        s.close()
        s = Sessione()
        # solo le righe salvate da questo modulo: la parte "griglia" della
        # campagna inserisce apposta sovrapposizioni direttamente nel database
        attivi = s.scalars(select(Appuntamento).where(Appuntamento.stato.in_(('PRENOTATO', 'CONFERMATO', 'ARRIVATO')))).all()
        nuovi = [a for a in attivi if a.id > ultimo]
        sovrapposti = [(a.id, b.id) for a in nuovi for b in attivi
                       if b.id != a.id and a.risorsa_id == b.risorsa_id and a.inizio < b.fine and b.inizio < a.fine]
        serie_grandi = s.scalar(select(func.count()).select_from(Appuntamento).where(Appuntamento.serie != '')
                                .group_by(Appuntamento.serie).order_by(func.count().desc()).limit(1)) or 0
        s.close()
        assert not cattivi, 'salvata una riga con fine non successiva all inizio'
        assert not orfani, 'salvata una riga senza stanza o senza medico'
        assert not sovrapposti, 'due appuntamenti attivi sovrapposti nella stessa stanza'
        assert serie_grandi <= 52, 'serie oltre 52 appuntamenti'
    return corpo


# =====================================================================
# 6. ciclo completo dal browser: crea, rileggi, modifica, elimina
# =====================================================================
def caso_ciclo(semenza):
    c = random.Random(semenza * 49979687)

    def corpo():
        g = giorno_nuovo()
        rid = c.choice(MONDO['risorse'])
        oid = c.choice(MONDO['operatori'])
        pid = c.choice(MONDO['prestazioni'])
        h, m = c.randint(6, 20), c.choice([0, 10, 15, 30, 45])
        durata = c.choice([15, 30, 45, 60])
        base = {'struttura': MONDO['strutture'][0], 'risorsa': rid, 'operatore': oid,
                'prestazione': pid, 'data': g.isoformat(),
                'ora': '%02d:%02d' % (h, m), 'durata': str(durata),
                'paziente': 'Ciclo%d' % semenza, 'telefono': '0815550000'}
        r = CL.post('/appuntamento', data=base)
        assert r.status_code in (200, 302), 'creazione HTTP N'

        s = Sessione()
        inizio = datetime.combine(g, time(h, m))
        a = s.scalars(select(Appuntamento).where(
            Appuntamento.risorsa_id == rid, Appuntamento.inizio == inizio)).first()
        assert a is not None, 'appuntamento creato ma non ritrovato'
        assert a.fine == inizio + timedelta(minutes=durata), 'durata non rispettata'

        # deve comparire nella fascia che contiene il suo inizio
        v = servizi.griglia(s, g, MONDO['strutture'][0])
        col = [x for x in v['colonne'] if x['risorsa'].id == rid]
        if col:
            visto = [a.id for x in col[0]['celle'] if x['stato'] == 'occupata'
                     for a in x['apps']]
            assert a.id in visto, 'appuntamento salvato ma assente dalla griglia'
        aid = a.id
        s.close()

        # doppione sulla stessa fascia: deve essere rifiutato
        CL.post('/appuntamento', data=dict(base, paziente='Doppione'))
        s = Sessione()
        n = len(s.scalars(select(Appuntamento).where(
            Appuntamento.risorsa_id == rid, Appuntamento.inizio == inizio)).all())
        s.close()
        assert n == 1, 'creati N appuntamenti sulla stessa stanza e ora'

        # modifica in loco
        r = CL.post('/appuntamento/%d' % aid, data=dict(base, note='modificata'))
        assert r.status_code in (200, 302), 'modifica HTTP N'
        s = Sessione()
        b = s.get(Appuntamento, aid)
        assert b is not None and b.note == 'modificata', 'la modifica non ha avuto effetto'
        s.close()

        # eliminazione
        CL.post('/appuntamento/%d' % aid,
                data={'azione': 'elimina', 'struttura': MONDO['strutture'][0]})
        s = Sessione()
        resta = s.get(Appuntamento, aid)
        s.close()
        assert resta is None, 'eliminazione non effettuata'
    return corpo


# =====================================================================
# 7. export su giornate casuali
# =====================================================================
def caso_export(semenza):
    c = random.Random(semenza * 67867979)

    def corpo():
        s = Sessione()
        g = giorno_nuovo()
        for _ in range(c.randint(0, 6)):
            rid = c.choice(MONDO['risorse'])
            i = datetime.combine(g, time(c.randint(0, 22), c.randint(0, 59)))
            f = i + timedelta(minutes=c.choice([15, 30, 45, 90, 240]))
            if f.date() != g or not libera(s, rid, i):
                continue
            s.add(Appuntamento(risorsa_id=rid, operatore_id=c.choice(MONDO['operatori']),
                               prestazione_id=c.choice(MONDO['prestazioni']), inizio=i, fine=f))
            s.commit()
        sid = c.choice(MONDO['strutture'])
        # un file per processo: due campagne insieme (normale e animata) non si sovrascrivono
        import tempfile
        percorso = os.path.join(tempfile.gettempdir(), 'campagna-export-%d.xlsx' % os.getpid())
        servizi.esporta_giorno(s, g, sid, percorso)
        import openpyxl
        ws = openpyxl.load_workbook(percorso).active
        # 1.12: sotto la griglia una riga vuota, la legenda e la nota sulle stanze disattivate
        atteso = 2 + len(servizi.griglia(s, g, sid)['fasce']) + 3
        s.close()
        assert ws.max_row <= atteso, 'export N righe contro N attese'
        fuori = [str(x) for x in ws.merged_cells.ranges if x.max_row > atteso]
        assert not fuori, 'merge oltre la tabella'
    return corpo


# =====================================================================
# 8. turni casuali: una fascia e aperta se e solo se un turno la copre
# =====================================================================
def caso_turni(semenza):
    c = random.Random(semenza * 86028121)

    def corpo():
        s = Sessione()
        g = giorno_nuovo()
        rid = c.choice(MONDO['risorse'])
        oid = c.choice(MONDO['operatori'])
        h1 = c.randint(0, 20)
        h2 = c.randint(h1 + 1, 23)
        t = Turno(operatore_id=oid, risorsa_id=rid, giorno_settimana=g.weekday(),
                  ora_inizio=time(h1, c.choice([0, 30])), ora_fine=time(h2, c.choice([0, 30])),
                  valido_da=g - timedelta(days=1))
        s.add(t)
        s.commit()
        v = servizi.griglia(s, g, MONDO['strutture'][0])
        tutti = servizi.turni_del_giorno(s, g, rid)     # anche quelli gia' presenti
        col = [x for x in v['colonne'] if x['risorsa'].id == rid]
        if col:
            for f, cella in zip(v['fasce'], col[0]['celle']):
                if cella['stato'] in ('occupata', 'coperta'):
                    continue
                dentro = any(x.ora_inizio <= f < x.ora_fine for x in tutti)
                atteso = 'aperta' if dentro else 'chiusa'
                assert cella['stato'] == atteso, \
                    'fascia con turno %s-%s risulta %s invece di %s' % (
                        t.ora_inizio, t.ora_fine, cella['stato'], atteso)
        s.delete(t)
        s.commit()
        s.close()
    return corpo


# =====================================================================
# 9. strutture e loghi sporchi: nel database sempre strutture coerenti, e un
#    modulo rifiutato non cambia nulla
# =====================================================================
PNG = b'\x89PNG\r\n\x1a\n'
ESITI_STRUTTURE = {}
MOTIVI_RIFIUTO = {}


def logo_casuale(c):
    from PIL import Image, ImageDraw
    fmt = c.choice(['PNG', 'JPEG', 'GIF', 'WEBP', 'BMP'])
    w, h = c.randint(1, 900), c.randint(1, 400)
    im = Image.new('RGB', (w, h), c.choice([(255, 255, 255), (250, 250, 250), (0, 0, 0)]))
    d = ImageDraw.Draw(im)
    for _ in range(c.randint(0, 4)):
        x0, y0 = c.randint(0, w - 1), c.randint(0, h - 1)
        d.rectangle([x0, y0, c.randint(x0, w - 1), c.randint(y0, h - 1)],
                    fill=tuple(c.randint(0, 255) for _ in range(3)))
    b = io.BytesIO()
    im.save(b, fmt)
    dati = bytearray(b.getvalue())
    x = c.random()
    if x < 0.2:
        for _ in range(c.randint(1, 30)):
            dati[c.randrange(len(dati))] = c.getrandbits(8)
    elif x < 0.3:
        dati = dati[:c.randint(0, len(dati))]
    elif x < 0.35:
        dati = bytearray(c.getrandbits(8) for _ in range(c.randint(1, 3000)))
    return bytes(dati)


def fotografia_strutture():
    s = Sessione()
    foto = sorted((x.id, x.nome, x.societa, x.colore, x.attiva, x.logo_aggiornato)
                  for x in s.scalars(select(Struttura)))
    s.close()
    return foto


def caso_struttura(semenza):
    c = random.Random(semenza * 49979687)
    sid = c.choice(MONDO['strutture'] * 2 + [None, None, None, 99999])
    dati = {}
    # per campo: probabilita' che manchi e che sia velenoso; il resto sono
    # valori plausibili, fra cui doppioni, nomi lunghi e colori sbagliati
    for k, assente, veleno, buoni in (
            ('nome', 0.05, 0.15, ['Sede %d' % c.randint(1, 30), 'Clinica Posillipo', 'clinica posillipo',
                                  'Ä' * 80, 'N' * 81]),
            ('societa', 0.15, 0.15, ['', 'Esempio S.r.l.', 'S' * 121]),
            ('colore', 0.20, 0.15, ['#154381', '#ffff00', '#FFFFFF', '#000000', '#2e7d32',
                                    'red', '#12345', '#1234567', '#GGGGGG']),
            ('rimuovi_logo', 0.50, 0.10, ['1', 'on', ''])):
        x = c.random()
        if x < assente:
            continue
        dati[k] = c.choice(VELENI) if x < assente + veleno else c.choice(buoni)
    if c.random() < 0.4:
        dati['logo'] = (io.BytesIO(logo_casuale(c)), c.choice(['l.png', 'l.jpg', 'x', '.png', 'a/b.gif']))
    if c.random() < 0.08:
        dati['azione'] = 'elimina'
    url = '/anagrafiche/strutture/nuova' if sid is None else '/anagrafiche/strutture/%d' % sid

    def corpo():
        prima = fotografia_strutture()
        r = CL.post(url, data=dati, content_type='multipart/form-data')
        assert r.status_code < 500, 'HTTP N'
        chiave = {200: 'rifiutati', 302: 'salvati o rinviati', 404: 'inesistenti'}.get(r.status_code, str(r.status_code))
        ESITI_STRUTTURE[chiave] = ESITI_STRUTTURE.get(chiave, 0) + 1
        if r.status_code == 200:
            from html import unescape
            for m in re.findall(r'class="avviso errore">([^<]*)</div>', r.get_data(as_text=True)):
                m = re.sub(r'\d+', 'N', unescape(m) if m.startswith('Logo') else unescape(m).split(':')[0])[:60]
                MOTIVI_RIFIUTO[m] = MOTIVI_RIFIUTO.get(m, 0) + 1
        if 'logo' in dati and r.status_code == 302:
            ESITI_STRUTTURE['con logo nuovo, salvati'] = ESITI_STRUTTURE.get('con logo nuovo, salvati', 0) + 1
        if r.status_code in (200, 404):
            assert fotografia_strutture() == prima, 'modulo rifiutato ma strutture cambiate'
        s = Sessione()
        problemi = set()
        strutture = s.scalars(select(Struttura)).all()
        if not strutture:
            problemi.add('nessuna struttura rimasta')
        nomi = [x.nome.lower() for x in strutture]
        if len(nomi) != len(set(nomi)):
            problemi.add('nomi doppi')
        for x in strutture:
            if not x.nome.strip() or len(x.nome) > 80:
                problemi.add('nome non valido salvato')
            if not re.fullmatch(r'#[0-9a-fA-F]{6}', x.colore or ''):
                problemi.add('colore non valido nel database')
            elif marchio.contrasto(x.colore, '#ffffff') < 4.5:
                problemi.add('colore illeggibile salvato')
            if (x.logo is None) != (x.logo_aggiornato is None):
                problemi.add('logo e data disallineati')
            if x.logo is not None and x.logo[:8] != PNG:
                problemi.add('logo non PNG')
        s.close()
        assert not problemi, sorted(problemi)
        if r.status_code == 302:
            g = CL.get('/giorno/%s?struttura=%s' % (GIORNO_BASE.isoformat(), sid or ''))
            assert g.status_code == 200, 'griglia dopo il salvataggio: HTTP N'
    return corpo


# =====================================================================
PIANO = [
    ('oracolo conflitti', 600, lambda n: (caso_oracolo(n), 'semenza %d' % n)),
    ('invarianti griglia', 300, lambda n: (caso_griglia(n), 'semenza %d' % n)),
    ('ordine di inserimento', 100, lambda n: (caso_ordine(n), 'semenza %d' % n)),
    ('rotte con parametri sporchi', 600, None),
    ('moduli sporchi', 300, lambda n: (caso_modulo(n), 'semenza %d' % n)),
    ('ciclo crea/modifica/elimina', 150, lambda n: (caso_ciclo(n), 'semenza %d' % n)),
    ('export su giornate casuali', 100, lambda n: (caso_export(n), 'semenza %d' % n)),
    ('turni casuali', 100, lambda n: (caso_turni(n), 'semenza %d' % n)),
    ('strutture e loghi sporchi', 300, lambda n: (caso_struttura(n), 'semenza %d' % n)),
]

PROGRESSO = open('campagna-progresso.txt', 'w', buffering=1)
for area, quanti, fabbrica in PIANO:
    for n in range(1, quanti + 1):
        if n % 25 == 0:
            PROGRESSO.write('%s %d/%d  casi totali %d  cause %d\n'
                            % (area, n, quanti, R.casi, len(R.guasti)))
        if R.basta():
            break
        if fabbrica is None:
            corpo, url = caso_rotta(n)
            prova(area, url[:70], corpo)
        else:
            corpo, rip = fabbrica(n)
            prova(area, rip, corpo)
    if R.basta():
        break

# =====================================================================
print()
print('%-30s %s' % ('AREA', 'CASI'))
for area, quanti, _ in PIANO:
    n = R.per_area.get(area, 0)
    if n:
        print('%-30s %5d %s' % (area, n, '' if n >= quanti else '(interrotta)'))
print('-' * 45)
print('%-30s %5d' % ('totale casi eseguiti', R.casi))
if ESITI_STRUTTURE:
    print('strutture e loghi: ' + ', '.join('%s %d' % kv for kv in sorted(ESITI_STRUTTURE.items())))
if os.environ.get('DETTAGLIO') and MOTIVI_RIFIUTO:
    print('motivi dei moduli struttura rifiutati:')
    for m, n in sorted(MOTIVI_RIFIUTO.items(), key=lambda kv: -kv[1]):
        print('  %4d  %s' % (n, m))

if R.guasti:
    print('\n%d cause distinte di guasto:\n' % len(R.guasti))
    for f, g in R.guasti.items():
        print('  [%s] x%d' % (g['area'], g['conteggio']))
        for messaggio, rip in g['esempi'][:LIMITE_ESEMPI]:
            print('      %s' % messaggio)
            print('      riproduci con: %s' % rip)
        print()
else:
    print('\nNessun guasto: tutti i casi rispettano oracoli e invarianti.')

if R.interrotta:
    print('Campagna interrotta: %s' % R.interrotta)
print('Durata: %.1f s' % (orologio.monotonic() - AVVIO))
