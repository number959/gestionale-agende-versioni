# -*- coding: utf-8 -*-
"""Prove della 1.10: le fasce di ogni turno, la "programmazione" dell'ambulatorio.

Un turno puo' avere la sua durata delle fasce (Turno.passo): dall'ora di
inizio, ogni tot minuti, e la prestazione occupa le fasce intere che tocca.
Qui:
- senza turni a fasce proprie tutto e' come nella 1.9.1: griglia del giorno,
  agenda del medico, controlli, avvisi e prima disponibilita' confrontati con
  le funzioni della 1.9.1 (copiate qui sotto e mai piu' cambiate) su tanti
  giorni inventati a caso;
- con le fasce proprie: i pezzi della colonna e le celle della griglia
  confrontati con un calcolo fatto a parte (minuto per minuto, riga per
  riga); i controlli contro un calcolo delle fasce toccate fatto a parte; la
  prima disponibilita' contro il controllo vero provato ora per ora;
- i casi scritti a mano: fasce da 15 in una struttura da 30, fasce da 20 con
  una visita da 30 (due fasce) e un esame da 10 (una fascia intera), fasce
  da 45, turno che comincia fuori dalle fasce della struttura o finisce dopo
  la chiusura; appuntamenti gia' presi prima delle fasce (si possono sempre
  modificare, e salvando il turno arriva l'avviso); spostare;
- le pagine: griglia e agenda del medico con le righe giuste (ogni riga ha
  tutte le colonne, contando le celle alte piu' righe), il modulo del turno,
  l'Excel del giorno, il mese e la settimana, la guida e le novita';
- l'aggiornamento del database dalla versione 10 alla 11.
Dati inventati.

    python prove_110.py                   # tutte
    PROVE_GIRI=400 python prove_110.py    # piu' giorni inventati per i confronti (predefinito 120)
    PROVE_SOLO=c_mano_20 python prove_110.py"""
import io
import os
import random
import re
import shutil
import sqlite3
import sys
import traceback
from bisect import bisect_right
from datetime import date, datetime, time, timedelta
from html import unescape
from html.parser import HTMLParser
from math import gcd

import logging
logging.getLogger().setLevel(logging.CRITICAL)

from sqlalchemy import select

import guida
import novita
import servizi
import viste
import app as A
from servizi import _minuti, orario, fasce, Regole
from modelli import (crea_sessione, Struttura, Risorsa, Operatore, Prestazione, Appuntamento, Turno, Assenza,
                     STATI_ATTIVI, PASSI_AMMESSI, PASSI_TURNO, VERSIONE_SCHEMA)

A.app.config['TESTING'] = True
CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = os.path.join(CARTELLA, 'prove_110_tmp')
shutil.rmtree(PROVVISORIA, ignore_errors=True)
os.makedirs(PROVVISORIA)
esiti, _area, _n = [], [''], [0]
SOLO = [x for x in os.environ.get('PROVE_SOLO', '').split(',') if x]
GIRI = max(10, int(os.environ.get('PROVE_GIRI', '120') or 120))

OGGI = date.today()
# un martedi nel futuro, con tutta la settimana lontana dai festivi
MAR = OGGI + timedelta(days=(1 - OGGI.weekday()) % 7 + 14)
while any(servizi.calendario.festivo(MAR + timedelta(days=k)) for k in range(-1, 6)):
    MAR += timedelta(days=7)
LUNEDI = MAR - timedelta(days=1)
SETTIMANA = [LUNEDI + timedelta(days=i) for i in range(6)]


def area(nome):
    _area[0] = nome


def prova(nome, f):
    if SOLO and f.__name__ not in SOLO:
        return
    try:
        esiti.append(('OK', _area[0], nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', _area[0], nome, str(e)[:900] or 'asserzione fallita'))
    except Exception:
        esiti.append(('ERRORE', _area[0], nome, traceback.format_exc().strip().splitlines()[-1]))


def percorso_nuovo(nome='db'):
    _n[0] += 1
    return os.path.join(PROVVISORIA, '%s_%d.db' % (nome, _n[0]))


def collega(S):
    A.Sessione = S
    A._registro = None
    viste._sessionmaker = lambda: S
    return A.app.test_client()


def html(r):
    return r.get_data(as_text=True)


def testo(r):
    return unescape(re.sub(r'<[^>]+>', ' ', html(r)))


def _id(x):
    return x.id if x is not None else None


def hm(m):
    return '%02d:%02d' % (m // 60, m % 60)


def ora(m):
    return time(m // 60, m % 60)


def quando(g, m):
    return datetime.combine(g, time(0, 0)) + timedelta(minutes=m)


MEDICI = [('Fintini', 'Ugo'), ('Esempietti', 'Anna'), ('Provolo', 'Rita'), ('Testabianca', 'Elio')]


def mondo():
    """Primo avvio (cinque ambulatori e una sala endoscopia, struttura da 8 a 20
    a fasce di 30 minuti), quattro medici inventati."""
    S = crea_sessione('sqlite:///' + percorso_nuovo())
    s = S()
    servizi.prepara_primo_avvio(s, 'Sede di prova')
    st = s.get(Struttura, 1)
    st.ora_apertura, st.ora_chiusura, st.passo = time(8, 0), time(20, 0), 30
    s.add_all([Operatore(cognome=c, nome=n) for c, n in MEDICI])
    s.commit()
    s.close()
    return S


def ids(S):
    s = S()
    d = {r.nome: r.id for r in s.scalars(select(Risorsa))}
    d.update({o.cognome: o.id for o in s.scalars(select(Operatore))})
    d.update({p.nome: p.id for p in s.scalars(select(Prestazione))})
    s.close()
    return d


def turno(S, stanza, medico, dalle, alle, passo=None, g=MAR):
    s = S()
    t = Turno(operatore_id=medico, risorsa_id=stanza, giorno_settimana=g.weekday(), ora_inizio=dalle,
              ora_fine=alle, valido_da=g - timedelta(days=60), passo=passo)
    s.add(t)
    s.commit()
    tid = t.id
    s.close()
    return tid


def app_(S, stanza, medico, inizio, minuti, stato='PRENOTATO', prestazione=None):
    s = S()
    a = Appuntamento(risorsa_id=stanza, operatore_id=medico, inizio=inizio, fine=inizio + timedelta(minutes=minuti),
                     stato=stato, prestazione_id=prestazione)
    s.add(a)
    s.commit()
    aid = a.id
    s.close()
    return aid


def colonna(v, nome):
    return next(c for c in v['colonne'] if c['risorsa'].nome == nome)


def cella_breve(c):
    """Una cella della griglia in poche parole: (stato, ora, righe, appuntamenti o turno)."""
    if c['stato'] == 'occupata':
        return ('occupata', c['ora'].strftime('%H:%M'), c['righe'], tuple(a.id for a in c['apps']))
    if c['stato'] == 'coperta':
        return ('coperta', c['ora'].strftime('%H:%M'), 1)
    return (c['stato'], c['ora'].strftime('%H:%M'), c['righe'], _id(c.get('turno')))


def senza_coperte(celle):
    return [cella_breve(c) for c in celle if c['stato'] != 'coperta']


# ======================================================== la 1.9.1, ferma
# Copiate dalla 1.9.1 (servizi.py, tag v1.9.1) e da non cambiare piu': senza
# turni a fasce proprie la 1.10 deve dare esattamente quello che davano queste.
# Usano le funzioni di servizi.py che dalla 1.9.1 non sono cambiate (orario,
# fasce, Regole, _minuti: le prove lo controllano confrontando i sorgenti, se
# c'e' git).
def griglia_191(ses, g, struttura_id, regole=None):
    st = ses.get(Struttura, struttura_id) if struttura_id else None
    regole = regole or Regole(ses, g, g)
    info = regole.giorno(g, st)
    risorse = ses.scalars(
        select(Risorsa).where(Risorsa.struttura_id == struttura_id,
                              Risorsa.attiva == True).order_by(Risorsa.ordine)).all()
    inizio_g = datetime.combine(g, time(0, 0))
    appuntamenti = ses.scalars(
        select(Appuntamento).where(Appuntamento.inizio >= inizio_g,
                                   Appuntamento.inizio < inizio_g + timedelta(days=1))
    ).all()
    ids_ = {r.id for r in risorse}
    del_giorno = [a for a in appuntamenti if a.risorsa_id in ids_ and a.stato in STATI_ATTIVI]
    annullati = sorted([a for a in appuntamenti if a.risorsa_id in ids_ and a.stato not in STATI_ATTIVI],
                       key=lambda x: x.inizio)
    apertura, ultima, passo = orario(st)
    elenco = fasce(del_giorno, apertura, ultima, passo)
    primo = _minuti(elenco[0])
    effettivi = regole.turni_effettivi(g, st, info=info)
    validi = regole.turni_validi(g, st)
    colonne = []
    for r in risorse:
        app_r = sorted([a for a in del_giorno if a.risorsa_id == r.id], key=lambda x: x.inizio)
        turni_r = [t for t in effettivi if t.risorsa_id == r.id]
        assenti = [(t.operatore, info['assenze'][t.operatore_id]) for t in validi
                   if t.risorsa_id == r.id and t.operatore_id in info['assenze']]
        per_fascia = {}
        for a in app_r:
            i = (_minuti(a.inizio.time()) - primo) // passo
            per_fascia.setdefault(max(0, min(i, len(elenco) - 1)), []).append(a)
        celle, copre_fino = [], -1
        for i, f in enumerate(elenco):
            lista = per_fascia.get(i)
            if lista:
                fine = max(_minuti(x.fine.time()) if x.fine.date() == g else 24 * 60 for x in lista)
                n = max(1, -(-(fine - (primo + i * passo)) // passo))
                n = min(n, len(elenco) - i)
                invaso = next((k for k in range(i + 1, i + n) if k in per_fascia), None)
                if invaso:
                    n = invaso - i
                celle.append({'stato': 'occupata', 'ora': f, 'apps': lista, 'righe': n})
                copre_fino = i + n - 1
            elif i <= copre_fino:
                celle.append({'stato': 'coperta', 'ora': f, 'righe': 1})
            else:
                dentro = next((t for t in turni_r if t.ora_inizio <= f < t.ora_fine), None)
                celle.append({'stato': 'aperta' if dentro else 'chiusa', 'ora': f, 'turno': dentro, 'righe': 1})
        colonne.append({'risorsa': r, 'celle': celle, 'turni': turni_r, 'assenti': assenti,
                        'occupate': len(app_r), 'libere': sum(1 for c in celle if c['stato'] == 'aperta')})
    return {'fasce': elenco, 'colonne': colonne, 'annullati': annullati, 'giorno': info,
            'struttura': st, 'passo': passo}


def conflitti_191(ses, risorsa_id, operatore_id, inizio, fine, escludi_id=None):
    motivi = []
    q = select(Appuntamento).where(Appuntamento.inizio < fine, Appuntamento.fine > inizio,
                                   Appuntamento.stato.in_(STATI_ATTIVI))
    if escludi_id:
        q = q.where(Appuntamento.id != escludi_id)
    sovrapposti = ses.scalars(q).all()

    for a in sovrapposti:
        if a.risorsa_id == risorsa_id:
            motivi.append('La stanza %s è già occupata dalle %s alle %s da %s.'
                          % (a.risorsa.nome, a.inizio.strftime('%H:%M'), a.fine.strftime('%H:%M'),
                             a.operatore.etichetta))
        elif a.operatore_id == operatore_id:
            motivi.append('%s è già in %s dalle %s alle %s.'
                          % (a.operatore.etichetta, a.risorsa.nome, a.inizio.strftime('%H:%M'),
                             a.fine.strftime('%H:%M')))
    return motivi


def fuori_turno_191(ses, risorsa_id, operatore_id, inizio, fine):
    stanza = ses.get(Risorsa, risorsa_id)
    st = stanza.struttura if stanza is not None else None
    g = inizio.date()
    regole = Regole(ses, g, g)
    info = regole.giorno(g, st)
    avvisi = []
    if operatore_id in info['assenze']:
        medico = ses.get(Operatore, operatore_id)
        avvisi.append('%s risulta assente il %s (%s).' % (
            medico.etichetta if medico else 'Il medico', g.strftime('%d/%m'), info['assenze'][operatore_id]))
    if info['chiusura']:
        avvisi.append('La struttura risulta chiusa il %s (%s).' % (g.strftime('%d/%m'), info['chiusura']))
    elif info['festivo']:
        avvisi.append('Il %s è festivo: %s.' % (g.strftime('%d/%m'), info['festivo']))
    if operatore_id not in info['assenze'] and not info['chiusura']:
        dentro = any(t.operatore_id == operatore_id and t.ora_inizio <= inizio.time()
                     and fine.time() <= t.ora_fine and fine.date() == g
                     for t in regole.turni_effettivi(g, st, risorsa_id, info=info))
        if not dentro:
            avvisi.append('Fascia fuori dai turni previsti per questa stanza.')
    return ' '.join(avvisi) or None


def settimana_medico_191(ses, lunedi, operatore_id, struttura_id):
    st = ses.get(Struttura, struttura_id) if struttura_id else None
    giorni = [lunedi + timedelta(days=i) for i in range(7)]
    regole = Regole(ses, giorni[0], giorni[-1])
    stanze = {r.id: r for r in ses.scalars(select(Risorsa).where(Risorsa.struttura_id == struttura_id))}
    inizio = datetime.combine(giorni[0], time(0, 0))
    apps = [a for a in ses.scalars(select(Appuntamento).where(
        Appuntamento.operatore_id == operatore_id, Appuntamento.inizio >= inizio,
        Appuntamento.inizio < inizio + timedelta(days=7),
        Appuntamento.stato.in_(STATI_ATTIVI))) if a.risorsa_id in stanze]
    apertura, ultima, passo = orario(st)
    elenco = fasce(apps, apertura, ultima, passo)
    primo = _minuti(elenco[0])
    turni = {g: [t for t in regole.turni_effettivi(g, st) if t.operatore_id == operatore_id] for g in giorni}
    info = {g: regole.giorno(g, st) for g in giorni}
    aperti = st.giorni_aperti if st is not None else set(range(6))
    giorni = [g for g in giorni if g.weekday() in aperti or turni[g] or any(a.inizio.date() == g for a in apps)]

    def fine_nel_giorno(a):
        return _minuti(a.fine.time()) if a.fine.date() == a.inizio.date() else 24 * 60

    righe = []
    for i, f in enumerate(elenco):
        celle = []
        m = _minuti(f)
        for g in giorni:
            del_giorno = [a for a in apps if a.inizio.date() == g]
            qui = [a for a in del_giorno
                   if max(0, min((_minuti(a.inizio.time()) - primo) // passo, len(elenco) - 1)) == i]
            copre = next((a for a in del_giorno if a not in qui
                          and _minuti(a.inizio.time()) < m < fine_nel_giorno(a)), None)
            turno_ = None if copre else next((t for t in turni[g] if t.ora_inizio <= f < t.ora_fine), None)
            celle.append({'data': g, 'ora': f, 'apps': sorted(qui, key=lambda x: x.inizio),
                          'turno': turno_, 'copre': copre})
        righe.append({'ora': f, 'celle': celle})
    return {'giorni': giorni, 'righe': righe, 'info': info, 'turni': turni, 'totale': len(apps), 'passo': passo}


def disponibilita_191(ses, operatore_id, durata, dal, struttura_id=None, giorni=60, massimo=15,
                      risorsa_id=None, dalle=None, alle=None):
    trovati = []
    adesso = datetime.now()
    durata = max(5, int(durata or 30))
    strutture = {s.id: s for s in ses.scalars(select(Struttura))}
    regole = Regole(ses, dal, dal + timedelta(days=giorni))
    for n in range(giorni + 1):
        g = dal + timedelta(days=n)
        candidati = []
        for st in strutture.values():
            if struttura_id and st.id != struttura_id:
                continue
            info = regole.giorno(g, st)
            for t in regole.turni_effettivi(g, st, risorsa_id, info=info):
                if t.operatore_id == operatore_id:
                    candidati.append((st, t))
        if not candidati:
            continue
        inizio_g = datetime.combine(g, time(0, 0))
        occupati = ses.scalars(select(Appuntamento).where(
            Appuntamento.inizio < inizio_g + timedelta(days=1), Appuntamento.fine > inizio_g,
            Appuntamento.stato.in_(STATI_ATTIVI))).all()
        visti, del_giorno = set(), []
        for st, t in candidati:
            passo = st.passo_min
            m = _minuti(t.ora_inizio)
            while m + durata <= _minuti(t.ora_fine):
                inizio = inizio_g + timedelta(minutes=m)
                fine = inizio + timedelta(minutes=durata)
                ora_ = inizio.time()
                if (inizio > adesso and (dalle is None or ora_ >= dalle) and (alle is None or ora_ < alle)
                        and (inizio, t.risorsa_id) not in visti
                        and not any(a.inizio < fine and a.fine > inizio and
                                    (a.risorsa_id == t.risorsa_id or a.operatore_id == operatore_id)
                                    for a in occupati)):
                    visti.add((inizio, t.risorsa_id))
                    del_giorno.append({'inizio': inizio, 'fine': fine, 'risorsa': t.risorsa, 'struttura': st})
                m += passo
        trovati += sorted(del_giorno, key=lambda x: (x['inizio'], x['risorsa'].ordine))
        if len(trovati) >= massimo:
            return trovati[:massimo]
    return sorted(trovati, key=lambda x: (x['inizio'], x['risorsa'].ordine))


# =========================================================== i calcoli a parte
def pezzi_oracolo(primo, fine, passo, apertura, turni):
    """I pezzi della colonna minuto per minuto: un minuto dentro un turno a
    fasce proprie (l'ultimo in ordine di inizio, se due si sovrappongono) sta
    nella fascia numero (minuto - inizio del turno) // durata; gli altri nella
    fascia della struttura, aperta se un turno senza fasce proprie ne copre
    l'inizio. Minuti di fila nella stessa fascia = un pezzo."""
    a = _minuti(apertura)
    propri = sorted((t for t in turni if t.passo_proprio), key=lambda x: (x.ora_inizio, x.id or 0))
    normali = [t for t in turni if not t.passo_proprio]
    pezzi = []
    for m in range(primo, fine):
        dentro = [t for t in propri if _minuti(t.ora_inizio) <= m < _minuti(t.ora_fine)]
        if dentro:
            t = dentro[-1]
            chiave = ('turno', id(t), (m - _minuti(t.ora_inizio)) // t.passo_proprio)
        else:
            s0 = a + ((m - a) // passo) * passo
            t = next((x for x in normali if _minuti(x.ora_inizio) <= s0 < _minuti(x.ora_fine)), None)
            chiave = ('struttura', s0)
        if pezzi and pezzi[-1][3] == chiave:
            pezzi[-1][1] = m + 1
        else:
            pezzi.append([m, m + 1, t, chiave])
    return [(p[0], p[1], p[2]) for p in pezzi]


def celle_oracolo(elenco, pezzi, apps, g):
    """Riga per riga, di chi e': dell'appuntamento cominciato nel suo pezzo, o
    nel pezzo con appuntamenti piu' vicino sopra se arriva oltre l'inizio del
    pezzo della riga; altrimenti del pezzo libero. Righe di fila con lo stesso
    padrone fanno una cella."""
    inizi = [p[0] for p in pezzi]

    def pezzo_di(m):
        return max(0, bisect_right(inizi, m) - 1)

    def fine_in(a):
        return _minuti(a.fine.time()) if a.fine.date() == g else 24 * 60

    per_pezzo = {}
    for a in sorted(apps, key=lambda x: x.inizio):
        per_pezzo.setdefault(pezzo_di(_minuti(a.inizio.time())), []).append(a)
    padroni = []
    for f in elenco:
        k = pezzo_di(_minuti(f))
        j = max((x for x in per_pezzo if x <= k), default=None)
        if j is not None and (j == k or pezzi[k][0] < max(fine_in(a) for a in per_pezzo[j])):
            padroni.append(('occupata', j))
        else:
            padroni.append(('libera', k))
    celle, r = [], 0
    while r < len(elenco):
        q = r
        while q + 1 < len(elenco) and padroni[q + 1] == padroni[r]:
            q += 1
        tipo, k = padroni[r]
        p = pezzi[k]
        if tipo == 'occupata':
            celle.append(('occupata', hm(p[0]), q - r + 1, tuple(a.id for a in per_pezzo[k])))
        else:
            celle.append(('aperta' if p[2] is not None else 'chiusa', hm(p[0]), q - r + 1, _id(p[2])))
        celle += [('coperta', elenco[x].strftime('%H:%M'), 1) for x in range(r + 1, q + 1)]
        r = q + 1
    return celle


def blocco_oracolo(t, s, e):
    """[s, e) (minuti) piu' le fasce intere del turno t che tocca."""
    if t is None or not t.passo_proprio:
        return s, e
    ts, te, c = _minuti(t.ora_inizio), _minuti(t.ora_fine), t.passo_proprio
    b0, b1 = s, e
    k = ts
    while k < te:
        f0, f1 = k, min(k + c, te)
        if f0 < e and f1 > s:
            b0, b1 = min(b0, f0), max(b1, f1)
        k += c
    return b0, b1


def base_oracolo(passo, apertura, turni):
    propri = [t for t in turni if t.passo_proprio]
    if not propri:
        return passo
    a, b = _minuti(apertura), passo
    for t in propri:
        b = gcd(gcd(gcd(b, t.passo_proprio), abs(_minuti(t.ora_inizio) - a)), abs(_minuti(t.ora_fine) - a))
    return max(5, b)


# ================================================== giorni inventati a caso
def svuota(s):
    for m in (Appuntamento, Turno, Assenza):
        s.query(m).delete()
    s.commit()


def riempi(s, rng, proprie=0.0, giorni=(MAR,), solo_validi=False, quanti=25):
    """Orario della struttura, turni (al massimo due per stanza e giorno, senza
    sovrapporsi, come vuole il modulo dei turni) e appuntamenti inventati.
    'proprie': la probabilita' che un turno abbia fasce sue. Con solo_validi
    gli appuntamenti si mettono solo se i controlli li accettano."""
    st = s.get(Struttura, 1)
    st.passo = rng.choice(PASSI_AMMESSI)
    st.ora_apertura = time(rng.choice((7, 8, 8, 9)), rng.choice((0, 0, 30)))
    st.ora_chiusura = time(rng.choice((13, 18, 19, 20)), rng.choice((0, 30)))
    stanze = sorted(r.id for r in s.scalars(select(Risorsa).where(Risorsa.struttura_id == 1)))
    medici = sorted(o.id for o in s.scalars(select(Operatore)))
    for g in giorni:
        for rid in stanze:
            k = rng.choice((0, 1, 1, 2))
            punti = sorted(rng.sample(range(6 * 12, 21 * 12 + 1), 2 * k))
            for j in range(k):
                a_, b_ = punti[2 * j] * 5, punti[2 * j + 1] * 5
                passo = None
                if rng.random() < proprie:
                    passo = rng.choice(PASSI_TURNO)
                elif rng.random() < 0.15:
                    passo = rng.choice((0, 25, 7))          # non valide: come senza fasce proprie
                s.add(Turno(operatore_id=rng.choice(medici), risorsa_id=rid, giorno_settimana=g.weekday(),
                            ora_inizio=ora(a_), ora_fine=ora(b_), valido_da=g - timedelta(days=7),
                            valido_a=g + timedelta(days=7) if rng.random() < 0.5 else None, passo=passo))
        if rng.random() < 0.2:
            s.add(Assenza(operatore_id=rng.choice(medici), dal=g, al=g, motivo='ferie'))
    s.commit()
    prestazioni = [p.id for p in s.scalars(select(Prestazione))]
    presi = set()                     # due attivi non cominciano nello stesso istante nella stessa stanza
    for g in giorni:
        for _ in range(rng.randint(0, quanti)):
            m = rng.randrange(6 * 12, 22 * 12) * 5
            if rng.random() < 0.1:
                m += rng.choice((1, 2, 3, 7))                # orari storti
            durata = rng.choice((5, 10, 15, 20, 25, 30, 40, 45, 60, 90, 120))
            if rng.random() < 0.03:
                m, durata = 23 * 60, 120                     # finisce il giorno dopo
            inizio = quando(g, m)
            fine = inizio + timedelta(minutes=durata)
            rid, oid = rng.choice(stanze), rng.choice(medici)
            stato = rng.choice(('PRENOTATO', 'PRENOTATO', 'PRENOTATO', 'CONFERMATO', 'ARRIVATO', 'DISDETTO',
                                'NON_PRESENTATO'))
            if stato in STATI_ATTIVI and (rid, inizio) in presi:
                continue
            if solo_validi and stato in STATI_ATTIVI and servizi.conflitti(s, rid, oid, inizio, fine):
                continue
            if stato in STATI_ATTIVI:
                presi.add((rid, inizio))
            s.add(Appuntamento(risorsa_id=rid, operatore_id=oid, inizio=inizio, fine=fine, stato=stato,
                               prestazione_id=rng.choice(prestazioni)))
            if solo_validi:
                s.flush()
    s.commit()


def giro(S, semenza, **opzioni):
    rng = random.Random(semenza)
    s = S()
    svuota(s)
    riempi(s, rng, **opzioni)
    return s, rng


# ============================================================ come prima
area('senza fasce proprie, come la 1.9.1')


def _funzioni_ferme():
    """Le funzioni di servizi.py che le copie della 1.9.1 usano non sono
    cambiate (se c'e' git con il tag v1.9.1)."""
    import ast
    import subprocess
    radice = os.path.dirname(CARTELLA)
    cartella = os.path.basename(CARTELLA)
    try:
        vecchio = subprocess.run(['git', 'show', 'v1.9.1:%s/servizi.py' % cartella], cwd=radice,
                                 capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return 'git non disponibile: confronto dei sorgenti saltato'
    if vecchio.returncode != 0:
        return 'senza il tag v1.9.1: confronto dei sorgenti saltato'

    def funzioni(sorgente):
        albero = ast.parse(sorgente)
        righe = sorgente.splitlines()
        return {n.name: '\n'.join(righe[n.lineno - 1:n.end_lineno]) for n in albero.body
                if isinstance(n, (ast.FunctionDef, ast.ClassDef))}

    prima = funzioni(vecchio.stdout.decode('utf-8'))
    ora_ = funzioni(open(os.path.join(CARTELLA, 'servizi.py'), encoding='utf-8').read())
    for nome in ('_minuti', '_allinea', 'orario', 'fasce', 'Regole', 'e_di_un_giorno'):
        assert prima[nome] == ora_[nome], 'cambiata dalla 1.9.1: %s' % nome
    import inspect
    for nome, f in (('griglia', griglia_191), ('conflitti', conflitti_191), ('fuori_turno', fuori_turno_191),
                    ('settimana_medico', settimana_medico_191), ('disponibilita', disponibilita_191)):
        # la copia qui sopra fa le stesse cose dell'originale (tolti commenti e docstring)
        def pulita(src):
            albero = ast.parse(src)
            fn = albero.body[0]
            if isinstance(fn.body[0], ast.Expr) and isinstance(getattr(fn.body[0], 'value', None), ast.Constant):
                fn.body = fn.body[1:]
            fn.name = 'f'
            return ast.dump(albero, annotate_fields=False).replace("'ids_'", "'ids'").replace("'ora_'", "'ora'") \
                .replace("'turno_'", "'turno'")
        assert pulita(prima[nome]) == pulita(inspect.getsource(f)), 'la copia della 1.9.1 non e\' fedele: ' + nome


def _vista_191(v):
    def cella(c):
        k = (c['stato'], c['ora'], c['righe'])
        if c['stato'] == 'occupata':
            return k + (tuple(a.id for a in c['apps']),)
        if c['stato'] in ('aperta', 'chiusa'):
            return k + (_id(c.get('turno')),)
        return k
    return (v['fasce'], v['passo'], [a.id for a in v['annullati']],
            [(c['risorsa'].id, c['occupate'], c['libere'], [t.id for t in c['turni']],
              [(o.id, m) for o, m in c['assenti']], [cella(x) for x in c['celle']]) for c in v['colonne']])


def _differenza(a, b, cosa):
    """Dove due viste cominciano a essere diverse, per il messaggio."""
    if a[:3] != b[:3]:
        return '%s: fasce, passo o annullati diversi' % cosa
    for x, y in zip(a[3], b[3]):
        if x[:5] != y[:5]:
            return '%s, stanza %s: %r invece di %r' % (cosa, x[0], x[:5], y[:5])
        for i, (c1, c2) in enumerate(zip(x[5], y[5])):
            if c1 != c2:
                return '%s, stanza %s, riga %d: %r invece di %r' % (cosa, x[0], i, c1, c2)
        if len(x[5]) != len(y[5]):
            return '%s, stanza %s: %d celle invece di %d' % (cosa, x[0], len(x[5]), len(y[5]))
    return '%s: diverse' % cosa


def a_griglia_come_prima():
    S = mondo()
    for n in range(GIRI):
        s, _ = giro(S, 1000 + n, proprie=0.0, giorni=(MAR, MAR + timedelta(days=1)))
        for g in (MAR, MAR + timedelta(days=1)):
            nuova, vecchia = servizi.griglia(s, g, 1), griglia_191(s, g, 1)
            a, b = _vista_191(nuova), _vista_191(vecchia)
            assert a == b, _differenza(a, b, 'giorno %d, %s' % (n, g))
            assert not nuova['misto'] and nuova['base'] == nuova['passo'] and nuova['altezza_riga'] == 36
            assert all(nuova['etichette']) and all(not c['fasce_proprie'] for c in nuova['colonne'])
        s.close()
    return '%d giorni inventati' % (2 * GIRI)


def a_settimana_medico_come_prima():
    S = mondo()
    I = ids(S)
    confrontate = 0
    for n in range(max(10, GIRI // 3)):
        s, rng = giro(S, 2000 + n, proprie=0.0, giorni=SETTIMANA, solo_validi=True, quanti=12)
        for cognome, _ in MEDICI:
            oid = I[cognome]
            nuova, vecchia = servizi.settimana_medico(s, LUNEDI, oid, 1), settimana_medico_191(s, LUNEDI, oid, 1)

            def breve(v):
                # dove cominciano appuntamenti, turno e copre non contano: la pagina mostra gli appuntamenti
                return (v['giorni'], v['passo'], v['totale'], [r['ora'] for r in v['righe']],
                        {g: [t.id for t in x] for g, x in v['turni'].items()},
                        [[(c['data'], c['ora'], tuple(a.id for a in c['apps'])) +
                          ((None, None) if c['apps'] else (_id(c['turno']), c['copre'] is not None))
                          for c in r['celle']] for r in v['righe']])
            a, b = breve(nuova), breve(vecchia)
            if a != b:
                for i, (x, y) in enumerate(zip(a[5], b[5])):
                    assert x == y, 'giro %d, %s, riga %d: %r invece di %r' % (n, cognome, i, x, y)
                assert a == b, 'giro %d, %s: %r' % (n, cognome, [x == y for x, y in zip(a, b)])
            assert not nuova['misto'] and nuova['base'] == nuova['passo']
            confrontate += 1
        s.close()
    return '%d settimane di un medico' % confrontate


def a_controlli_come_prima():
    S = mondo()
    casi = 0
    for n in range(GIRI):
        s, rng = giro(S, 3000 + n, proprie=0.0)
        stanze = sorted(r.id for r in s.scalars(select(Risorsa)))
        medici = sorted(o.id for o in s.scalars(select(Operatore)))
        tutti = [a.id for a in s.scalars(select(Appuntamento))]
        for _ in range(12):
            m = rng.randrange(6 * 12, 22 * 12) * 5 + rng.choice((0, 0, 0, 3))
            inizio = quando(MAR, m)
            fine = inizio + timedelta(minutes=rng.choice((5, 10, 20, 30, 45, 60, 120)))
            rid, oid = rng.choice(stanze), rng.choice(medici)
            escludi = rng.choice(tutti) if tutti and rng.random() < 0.3 else None
            assert servizi.conflitti(s, rid, oid, inizio, fine, escludi) == \
                conflitti_191(s, rid, oid, inizio, fine, escludi), (n, rid, oid, inizio, fine, escludi)
            assert servizi.fuori_turno(s, rid, oid, inizio, fine) == fuori_turno_191(s, rid, oid, inizio, fine), \
                (n, rid, oid, inizio, fine)
            casi += 1
        s.close()
    return '%d prenotazioni provate' % casi


def a_disponibilita_come_prima():
    S = mondo()
    I = ids(S)
    casi = 0
    for n in range(max(10, GIRI // 3)):
        s, rng = giro(S, 4000 + n, proprie=0.0, giorni=SETTIMANA, quanti=15)
        for cognome, _ in MEDICI:
            durata = rng.choice((10, 20, 30, 45, 60, 90))
            dalle = rng.choice((None, time(9, 0), time(13, 0)))

            def breve(x):
                return [(p['inizio'], p['fine'], p['risorsa'].id, p['struttura'].id) for p in x]
            a = breve(servizi.disponibilita(s, I[cognome], durata, LUNEDI, 1, giorni=6, massimo=40, dalle=dalle))
            b = breve(disponibilita_191(s, I[cognome], durata, LUNEDI, 1, giorni=6, massimo=40, dalle=dalle))
            assert a == b, 'giro %d, %s, %d minuti: %r invece di %r' % (n, cognome, durata, a[:5], b[:5])
            casi += 1
        s.close()
    return '%d ricerche' % casi


prova('le funzioni della 1.9.1 copiate qui sono fedeli, e quelle che usano non sono cambiate', _funzioni_ferme)
prova('griglia del giorno identica alla 1.9.1 (orari, turni, assenze, appuntamenti storti o sovrapposti)',
      a_griglia_come_prima)
prova('agenda della settimana del medico identica alla 1.9.1', a_settimana_medico_come_prima)
prova('controlli e avvisi della prenotazione identici alla 1.9.1', a_controlli_come_prima)
prova('prima disponibilità identica alla 1.9.1', a_disponibilita_come_prima)


# ============================================================ fasce proprie a caso
area('fasce proprie, contro un calcolo a parte')


def b_pezzi():
    """pezzi_colonna contro il calcolo minuto per minuto, anche con turni che si
    sovrappongono, orari fuori dalle fasce, colonne piu' corte o piu' lunghe."""
    rng = random.Random(77)

    class T(object):
        def __init__(self, i, a_, b_, passo):
            self.id, self.ora_inizio, self.ora_fine, self.passo = i, ora(a_), ora(b_), passo

        @property
        def passo_proprio(self):
            return self.passo if self.passo in PASSI_TURNO else None

    for n in range(GIRI * 6):
        passo = rng.choice(PASSI_AMMESSI)
        apertura = ora(rng.randrange(6 * 12, 10 * 12) * 5)
        turni = []
        for i in range(rng.randint(0, 4)):
            a_ = rng.randrange(5 * 12, 21 * 12) * 5
            b_ = a_ + rng.randrange(1, 9 * 12) * 5
            turni.append(T(i + 1, a_, min(b_, 23 * 60 + 55), rng.choice(PASSI_TURNO + (None, None, 25))))
        primo = _minuti(apertura) - rng.choice((0, 0, passo, 2 * passo)) - rng.choice((0, 5, 10))
        fine = primo + rng.randrange(1, 16 * 12) * 5
        fine = min(fine, 24 * 60)
        atteso = pezzi_oracolo(primo, fine, passo, apertura, turni)
        trovato = [(p[0], p[1], p[2]) for p in servizi.pezzi_colonna(primo, fine, passo, apertura, turni)]
        assert trovato == atteso, 'giro %d: %r\ninvece di %r' % (n, trovato[:8], atteso[:8])
    return '%d colonne' % (GIRI * 6)


def _griglia_attesa(s, g):
    """La griglia come deve venire, rifatta da capo: righe, poi per ogni stanza
    pezzi e celle con i calcoli a parte."""
    st = s.get(Struttura, 1)
    regole = Regole(s, g, g)
    effettivi = regole.turni_effettivi(g, st)
    apertura, ultima, passo = orario(st)
    base = base_oracolo(passo, apertura, effettivi)
    stanze = s.scalars(select(Risorsa).where(Risorsa.struttura_id == 1, Risorsa.attiva == True)
                       .order_by(Risorsa.ordine)).all()
    inizio_g = datetime.combine(g, time(0, 0))
    attivi = [a for a in s.scalars(select(Appuntamento).where(
        Appuntamento.inizio >= inizio_g, Appuntamento.inizio < inizio_g + timedelta(days=1)))
        if a.stato in STATI_ATTIVI and a.risorsa_id in {r.id for r in stanze}]
    # la tabella finisce dove finiva con le fasce della struttura (se nessun appuntamento va oltre)
    elenco = fasce(attivi, apertura, ora(_minuti(ultima) + passo - base), base)
    primo, fine = _minuti(elenco[0]), _minuti(elenco[0]) + len(elenco) * base
    colonne = {}
    for r in stanze:
        turni_r = [t for t in effettivi if t.risorsa_id == r.id]
        pezzi = pezzi_oracolo(primo, fine, passo, apertura, turni_r)
        colonne[r.id] = celle_oracolo(elenco, pezzi, [a for a in attivi if a.risorsa_id == r.id], g)
    return base, elenco, colonne, effettivi, passo, apertura


def b_griglia():
    S = mondo()
    miste = 0
    for n in range(GIRI):
        s, _ = giro(S, 5000 + n, proprie=0.7)
        v = servizi.griglia(s, MAR, 1)
        base, elenco, colonne, effettivi, passo, apertura = _griglia_attesa(s, MAR)
        assert v['base'] == base and v['fasce'] == elenco, (n, v['base'], base, v['fasce'][:3], elenco[:3])
        propri = [t for t in effettivi if t.passo_proprio]
        assert v['misto'] == bool(propri), n
        miste += v['misto']
        assert v['etichette'] == [(_minuti(f) - _minuti(apertura)) % passo == 0 for f in elenco], n
        for c in v['colonne']:
            atteso = colonne[c['risorsa'].id]
            trovato = [x if x[0] == 'coperta' else x for x in (cella_breve(y) for y in c['celle'])]
            if trovato != atteso:
                for i, (x, y) in enumerate(zip(trovato, atteso)):
                    assert x == y, 'giro %d, %s, riga %d (%s): %r invece di %r' % (
                        n, c['risorsa'].nome, i, elenco[i], x, y)
                assert False, 'giro %d, %s: %d celle invece di %d' % (n, c['risorsa'].nome, len(trovato), len(atteso))
            assert c['libere'] == sum(1 for x in atteso if x[0] == 'aperta'), n
            assert c['fasce_proprie'] == sorted({t.passo_proprio for t in c['turni'] if t.passo_proprio}), n
            # ogni appuntamento attivo della stanza compare una volta sola
            visti = [a.id for x in c['celle'] if x['stato'] == 'occupata' for a in x['apps']]
            assert len(visti) == len(set(visti)) == c['occupate'], (n, visti, c['occupate'])
            assert sum(x['righe'] for x in c['celle'] if x['stato'] != 'coperta') == len(elenco), n
        # altezza delle righe: una fascia della struttura alta almeno 36 pixel, la piu' corta almeno 24
        h = v['altezza_riga']
        if base == passo:
            assert h == 36, (n, h)
        else:
            minima = min([passo] + [t.passo_proprio for t in propri])
            assert h * passo / base >= 36 - passo / base and h * minima / base >= 24 - minima / base and h >= 8, \
                (n, h, passo, base, minima)
        s.close()
    assert miste > GIRI // 3, miste
    return '%d giorni, %d con fasce proprie' % (GIRI, miste)


def _turno_fasce(turni, rid, m):
    return next((t for t in turni if t.risorsa_id == rid and t.passo_proprio
                 and _minuti(t.ora_inizio) <= m < _minuti(t.ora_fine)), None)


def _turno_fasce_per(turni, rid, m, f):
    """1.11: quello che copre l'inizio, altrimenti il primo che [m, f) tocca."""
    return _turno_fasce(turni, rid, m) or next(
        (t for t in turni if t.risorsa_id == rid and t.passo_proprio
         and _minuti(t.ora_inizio) < f and _minuti(t.ora_fine) > m), None)


def _tipo(motivo):
    if motivo.startswith('La stanza '):
        return 'stanza'
    if motivo.startswith('In ') and ' la fascia delle ' in motivo:
        return 'fascia'
    return 'medico'


def b_controlli():
    """I motivi per non salvare contro il calcolo delle fasce toccate fatto a
    parte: la stessa stanza con orari che si toccano, o con fasce in comune nel
    turno a fasce proprie (tranne quelle che l'appuntamento modificato aveva
    gia' in comune); lo stesso medico altrove con orari che si toccano."""
    S = mondo()
    casi = fasce_ = 0
    for n in range(GIRI):
        s, rng = giro(S, 6000 + n, proprie=0.8)
        st = s.get(Struttura, 1)
        effettivi = Regole(s, MAR, MAR).turni_effettivi(MAR, st)
        stanze = sorted(r.id for r in s.scalars(select(Risorsa)))
        medici = sorted(o.id for o in s.scalars(select(Operatore)))
        inizio_g = datetime.combine(MAR, time(0, 0))
        tutti = [(a.id, a.risorsa_id, a.operatore_id, int((a.inizio - inizio_g).total_seconds() // 60),
                  int((a.fine - inizio_g).total_seconds() // 60), a.stato in STATI_ATTIVI)
                 for a in s.scalars(select(Appuntamento))]
        in_fasce = [x for x in tutti if x[5] and (_turno_fasce(effettivi, x[1], x[4]) or
                                                  _turno_fasce(effettivi, x[1], x[3]))]
        for _ in range(15):
            caso = rng.random()
            if tutti and caso < 0.35:
                # si modifica uno gia' preso: stesso posto, medico diverso, oppure spostato di poco
                x = rng.choice(tutti)
                rid, oid = x[1], rng.choice(medici)
                m = x[3] + rng.choice((0, 0, 5, -5, 10, 20, -20))
                durata = max(5, x[4] - x[3] + rng.choice((0, 0, 10, -5)))
                escludi = x
            elif in_fasce and caso < 0.7:
                # subito prima o subito dopo uno gia' preso in un turno a fasce proprie, nella sua stanza:
                # li' contano le fasce intere
                x = rng.choice(in_fasce)
                rid, oid = x[1], rng.choice(medici)
                durata = rng.choice((5, 10, 15, 20, 30, 40))
                m = (x[4] + rng.choice((0, 0, 5, 10, 15)) if rng.random() < 0.6
                     else x[3] - durata - rng.choice((0, 0, 5, 10)))
                escludi = None
            else:
                rid, oid = rng.choice(stanze), rng.choice(medici)
                m = rng.randrange(7 * 12, 21 * 12) * 5 + rng.choice((0, 0, 0, 0, 2))
                durata = rng.choice((5, 10, 15, 20, 30, 40, 45, 60))
                escludi = None
            t = _turno_fasce_per(effettivi, rid, m, m + durata)
            b = blocco_oracolo(t, m, m + durata)
            prima = None
            if t is not None and escludi is not None and escludi[5] and escludi[1] == rid:
                prima = blocco_oracolo(t, escludi[3], escludi[4])
            attesi = []
            for x in tutti:
                if not x[5] or (escludi is not None and x[0] == escludi[0]):
                    continue
                reale = x[3] < m + durata and x[4] > m
                if x[1] == rid:
                    if reale:
                        attesi.append('stanza')
                        continue
                    bx = blocco_oracolo(t, x[3], x[4])
                    # 1.11: si perdonano solo le fasce gia' divise, non l'intero appuntamento
                    i0, i1 = max(bx[0], b[0]), min(bx[1], b[1])
                    if i0 < i1 and not (prima and prima[0] <= i0 and i1 <= prima[1]):
                        attesi.append('fascia')
                elif x[2] == oid and reale:
                    attesi.append('medico')
            motivi = servizi.conflitti(s, rid, oid, quando(MAR, m), quando(MAR, m + durata),
                                       escludi[0] if escludi else None)
            assert sorted(_tipo(x) for x in motivi) == sorted(attesi), (n, rid, oid, hm(m), durata, escludi,
                                                                        motivi, attesi)
            fasce_ += 'fascia' in attesi
            # l'avviso dell'orario a meta' fascia
            avviso = servizi.fuori_turno(s, rid, oid, quando(MAR, m), quando(MAR, m + durata)) or ''
            # l'avviso guarda il turno dove l'appuntamento comincia (1.11: i controlli invece
            # anche quello che tocca soltanto)
            t_inizio = _turno_fasce(effettivi, rid, m)
            b_inizio = blocco_oracolo(t_inizio, m, m + durata)
            storto = t_inizio is not None and (m - _minuti(t_inizio.ora_inizio)) % t_inizio.passo_proprio != 0
            frase = 'alle %s non ne comincia una' % hm(m)
            assert (frase in avviso) == storto, (n, hm(m), avviso)
            if storto:
                assert 'occupa la fascia intera (%s-%s)' % (hm(b_inizio[0]), hm(b_inizio[1])) in avviso, (avviso, b)
            vecchio = fuori_turno_191(s, rid, oid, quando(MAR, m), quando(MAR, m + durata))
            assert avviso.startswith(vecchio or ''), (avviso, vecchio)
            casi += 1
        s.close()
    assert fasce_ > casi // 25, (fasce_, casi)
    return '%d prenotazioni provate, %d fermate solo dalle fasce intere' % (casi, fasce_)


def b_disponibilita():
    """La prima disponibilita' contro il controllo vero, ora per ora: ogni
    inizio di fascia del turno del medico (o del passo della struttura, nei
    turni senza fasce proprie) in cui conflitti() non trova niente."""
    S = mondo()
    I = ids(S)
    casi = 0
    for n in range(max(10, GIRI // 6)):
        s, rng = giro(S, 7000 + n, proprie=0.8, giorni=(MAR, MAR + timedelta(days=1)), solo_validi=True)
        st = s.get(Struttura, 1)
        regole = Regole(s, MAR, MAR + timedelta(days=1))
        for cognome, _ in MEDICI:
            oid = I[cognome]
            durata = rng.choice((10, 15, 20, 30, 40, 45, 60))
            attesi = []
            for g in (MAR, MAR + timedelta(days=1)):
                for t in regole.turni_effettivi(g, st):
                    if t.operatore_id != oid:
                        continue
                    m = _minuti(t.ora_inizio)
                    while m + durata <= _minuti(t.ora_fine):
                        if not servizi.conflitti(s, t.risorsa_id, oid, quando(g, m), quando(g, m + durata)):
                            attesi.append((quando(g, m), t.risorsa_id))
                        m += t.passo_proprio or st.passo_min
            attesi = sorted(set(attesi), key=lambda x: (x[0], s.get(Risorsa, x[1]).ordine))
            trovati = [(p['inizio'], p['risorsa'].id)
                       for p in servizi.disponibilita(s, oid, durata, MAR, 1, giorni=1, massimo=10000)]
            assert trovati == attesi, 'giro %d, %s, %d minuti: %r\ninvece di %r' % (
                n, cognome, durata, trovati[:6], attesi[:6])
            casi += 1
        s.close()
    return '%d ricerche' % casi


def b_settimana_medico():
    """L'agenda del medico con le fasce proprie: ogni giorno e' la colonna dei
    suoi turni, divisa come nel calcolo a parte; le chiavi di prima (apps,
    turno, copre) dicono lo stesso."""
    S = mondo()
    I = ids(S)
    viste_ = 0
    for n in range(max(10, GIRI // 3)):
        s, rng = giro(S, 8000 + n, proprie=0.7, giorni=SETTIMANA, solo_validi=True, quanti=10)
        st = s.get(Struttura, 1)
        regole = Regole(s, LUNEDI, LUNEDI + timedelta(days=6))
        apertura, ultima, passo = orario(st)
        for cognome, _ in MEDICI:
            oid = I[cognome]
            v = servizi.settimana_medico(s, LUNEDI, oid, 1)
            turni = {g: [t for t in regole.turni_effettivi(g, st) if t.operatore_id == oid] for g in v['giorni']}
            base = base_oracolo(passo, apertura, [t for x in turni.values() for t in x])
            assert v['base'] == base, (n, cognome, v['base'], base)
            elenco = [r['ora'] for r in v['righe']]
            primo = _minuti(elenco[0])
            apps = [a for a in s.scalars(select(Appuntamento).where(Appuntamento.operatore_id == oid))
                    if a.stato in STATI_ATTIVI and LUNEDI <= a.inizio.date() <= LUNEDI + timedelta(days=6)]
            for k, g in enumerate(v['giorni']):
                pezzi = pezzi_oracolo(primo, primo + len(elenco) * base, passo, apertura, turni[g])
                attese = celle_oracolo(elenco, pezzi, [a for a in apps if a.inizio.date() == g], g)
                trovate = []
                for i, r in enumerate(v['righe']):
                    c = r['celle'][k]
                    assert c['data'] == g and c['ora'] == elenco[i]
                    if c['stato'] == 'occupata':
                        trovate.append(('occupata', c['inizio'].strftime('%H:%M'), c['righe'],
                                        tuple(a.id for a in c['apps'])))
                        assert c['copre'] is None and c['apps']
                    elif c['stato'] == 'coperta':
                        trovate.append(('coperta', c['ora'].strftime('%H:%M'), 1))
                        assert not c['apps']
                    else:
                        trovate.append((c['stato'], c['inizio'].strftime('%H:%M'), c['righe'], _id(c['turno'])))
                        assert c['copre'] is None and not c['apps']
                assert trovate == attese, 'giro %d, %s, %s: %r\ninvece di %r' % (
                    n, cognome, g, [x for x, y in zip(trovate, attese) if x != y][:3],
                    [y for x, y in zip(trovate, attese) if x != y][:3])
                # copre: le righe dentro un appuntamento cominciato sopra
                for i, (r, x) in enumerate(zip(v['righe'], attese)):
                    c = r['celle'][k]
                    if x[0] == 'coperta':
                        j = i
                        while attese[j][0] == 'coperta':
                            j -= 1
                        if attese[j][0] == 'occupata':
                            assert c['copre'] is not None and c['turno'] is None, (n, cognome, g, i)
                        else:
                            assert c['copre'] is None and _id(c['turno']) == attese[j][3], (n, cognome, g, i)
            viste_ += 1
        s.close()
    return '%d settimane' % viste_


prova('pezzi della colonna come il calcolo minuto per minuto', b_pezzi)
prova('griglia con fasce proprie come il calcolo riga per riga (righe, celle, libere, altezza)', b_griglia)
prova('controlli: le fasce intere bloccano, i casi di prima no; avviso dell\'orario a metà fascia', b_controlli)
prova('prima disponibilità: tutti e soli gli inizi di fascia che il controllo accetta', b_disponibilita)
prova('agenda del medico con fasce proprie come il calcolo a parte', b_settimana_medico)


# ============================================================ casi a mano
area('casi scritti a mano')


def c_mano_15():
    """Struttura a fasce di 30 minuti; la sala endoscopia il martedi dalle 8 alle
    13 a fasce di 15. Una colonscopia di 40 minuti alle 8 occupa tre fasce
    (fino alle 8:45), una EGDS di 20 alle 9 ne occupa due; l'ambulatorio 1, senza
    fasce proprie, resta a 30 minuti."""
    S = mondo()
    I = ids(S)
    sala, amb = I['Sala endoscopia'], I['Ambulatorio 1']
    turno(S, sala, I['Fintini'], time(8, 0), time(13, 0), passo=15)
    turno(S, amb, I['Esempietti'], time(8, 0), time(13, 0))
    colo = app_(S, sala, I['Fintini'], quando(MAR, 8 * 60), 40, prestazione=I['Colonscopia'])
    egds = app_(S, sala, I['Fintini'], quando(MAR, 9 * 60), 20, prestazione=I['EGDS'])
    visita = app_(S, amb, I['Esempietti'], quando(MAR, 8 * 60), 30)
    s = S()
    v = servizi.griglia(s, MAR, 1)
    assert v['base'] == 15 and v['passo'] == 30 and v['misto'] and v['altezza_riga'] == 24, \
        (v['base'], v['misto'], v['altezza_riga'])
    assert v['fasce'][0] == time(8, 0) and v['fasce'][-1] == time(19, 45) and len(v['fasce']) == 48, v['fasce'][-1]
    assert v['etichette'][:4] == [True, False, True, False]
    c = colonna(v, 'Sala endoscopia')
    tid = c['turni'][0].id
    attese = [('occupata', '08:00', 3, (colo,)), ('aperta', '08:45', 1, tid), ('occupata', '09:00', 2, (egds,))]
    attese += [('aperta', hm(m), 1, tid) for m in range(9 * 60 + 30, 13 * 60, 15)]
    attese += [('chiusa', hm(m), 2, None) for m in range(13 * 60, 20 * 60, 30)]
    assert senza_coperte(c['celle']) == attese, senza_coperte(c['celle'])[:6]
    assert c['libere'] == 15 and c['fasce_proprie'] == [15], (c['libere'], c['fasce_proprie'])
    c = colonna(v, 'Ambulatorio 1')
    tid = c['turni'][0].id
    attese = [('occupata', '08:00', 2, (visita,))] + [('aperta', hm(m), 2, tid) for m in range(8 * 60 + 30, 13 * 60, 30)]
    attese += [('chiusa', hm(m), 2, None) for m in range(13 * 60, 20 * 60, 30)]
    assert senza_coperte(c['celle']) == attese, senza_coperte(c['celle'])[:4]
    assert c['libere'] == 9 and c['fasce_proprie'] == []
    # le altre stanze, senza turni: chiuse a fasce di 30
    assert senza_coperte(colonna(v, 'Ambulatorio 2')['celle']) == [('chiusa', hm(m), 2, None)
                                                                   for m in range(8 * 60, 20 * 60, 30)]
    # la prima disponibilita' segue le fasce da 15 nella sala, quelle da 30 nell'ambulatorio
    p = servizi.disponibilita(s, I['Fintini'], 30, MAR, 1, giorni=0, massimo=4)
    assert [x['inizio'].strftime('%H:%M') for x in p] == ['09:30', '09:45', '10:00', '10:15'], p
    p = servizi.disponibilita(s, I['Esempietti'], 30, MAR, 1, giorni=0, massimo=3)
    assert [x['inizio'].strftime('%H:%M') for x in p] == ['08:30', '09:00', '09:30'], p
    s.close()


def c_mano_20():
    """Il caso della programmazione: ambulatorio 2 dalle 9 alle 12 a fasce di 20
    minuti, in una struttura a fasce di 30. Una prima visita di 30 minuti
    occupa due fasce (9:00-9:40); un esame di 10 minuti occupa comunque la
    fascia intera: nessun buco da 10 minuti prenotabile."""
    S = mondo()
    I = ids(S)
    amb = I['Ambulatorio 2']
    turno(S, amb, I['Provolo'], time(9, 0), time(12, 0), passo=20)
    visita = app_(S, amb, I['Provolo'], quando(MAR, 9 * 60), 30, prestazione=I['Prima visita'])
    s = S()
    v = servizi.griglia(s, MAR, 1)
    assert v['base'] == 10 and len(v['fasce']) == 72 and v['altezza_riga'] == 12, (v['base'], v['altezza_riga'])
    c = colonna(v, 'Ambulatorio 2')
    tid = c['turni'][0].id
    assert senza_coperte(c['celle'])[:3] == [('chiusa', '08:00', 3, None), ('chiusa', '08:30', 3, None),
                                             ('occupata', '09:00', 4, (visita,))], senza_coperte(c['celle'])[:3]
    assert senza_coperte(c['celle'])[3:10] == [('aperta', hm(m), 2, tid) for m in range(9 * 60 + 40, 12 * 60, 20)]
    # alle 9:30 (orari veri liberi) no: la fascia delle 9:20 e' della visita
    motivi = servizi.conflitti(s, amb, I['Esempietti'], quando(MAR, 9 * 60 + 30), quando(MAR, 10 * 60))
    assert motivi == ["In Ambulatorio 2 la fascia delle 09:20 è già occupata dall'appuntamento delle 09:00-09:30 "
                      "di Provolo Rita: nel turno di Provolo Rita le fasce sono da 20 minuti e ogni prestazione "
                      "occupa fasce intere."], motivi
    avviso = servizi.fuori_turno(s, amb, I['Provolo'], quando(MAR, 9 * 60 + 30), quando(MAR, 10 * 60))
    assert avviso == ("Le fasce di questo turno sono da 20 minuti dalle 09:00: alle 09:30 non ne comincia una, "
                      "l'appuntamento occupa la fascia intera (09:20-10:00)."), avviso
    assert servizi.conflitti(s, amb, I['Provolo'], quando(MAR, 9 * 60 + 40), quando(MAR, 10 * 60 + 10)) == []
    assert servizi.fuori_turno(s, amb, I['Provolo'], quando(MAR, 9 * 60 + 40), quando(MAR, 10 * 60 + 10)) is None
    p = servizi.disponibilita(s, I['Provolo'], 30, MAR, 1, giorni=0)
    assert [x['inizio'].strftime('%H:%M') for x in p] == ['09:40', '10:00', '10:20', '10:40', '11:00', '11:20'], p
    s.close()
    # un esame di 10 minuti alle 10:20 prende la fascia intera: alle 10:30 non entra niente
    esame = app_(S, amb, I['Provolo'], quando(MAR, 10 * 60 + 20), 10)
    s = S()
    motivi = servizi.conflitti(s, amb, I['Provolo'], quando(MAR, 10 * 60 + 30), quando(MAR, 10 * 60 + 40))
    assert len(motivi) == 1 and 'la fascia delle 10:20' in motivi[0], motivi
    c = colonna(servizi.griglia(s, MAR, 1), 'Ambulatorio 2')
    assert ('occupata', '10:20', 2, (esame,)) in senza_coperte(c['celle'])
    assert not any(x[1] == '10:30' for x in senza_coperte(c['celle'])), 'mai una fascia libera alle 10:30'
    p = servizi.disponibilita(s, I['Provolo'], 10, MAR, 1, giorni=0)
    assert [x['inizio'].strftime('%H:%M') for x in p] == ['09:40', '10:00', '10:40', '11:00', '11:20', '11:40'], p
    # un altro medico nello stesso momento, in un'altra stanza: nessun problema di fasce
    assert servizi.conflitti(s, I['Ambulatorio 3'], I['Esempietti'], quando(MAR, 10 * 60 + 30),
                             quando(MAR, 10 * 60 + 40)) == []
    # un disdetto libera le sue fasce
    s.get(Appuntamento, esame).stato = 'DISDETTO'
    s.commit()
    assert servizi.conflitti(s, amb, I['Provolo'], quando(MAR, 10 * 60 + 30), quando(MAR, 10 * 60 + 40)) == []
    s.close()


def c_mano_45_e_bordi():
    """Fasce di 45 minuti (righe da 15); un turno che comincia alle 8:10, fuori
    dalle fasce della struttura (righe da 10); un turno che va oltre la
    chiusura (la tabella finisce dove finiva)."""
    S = mondo()
    I = ids(S)
    turno(S, I['Ambulatorio 3'], I['Fintini'], time(8, 0), time(12, 30), passo=45)
    lunga = app_(S, I['Ambulatorio 3'], I['Fintini'], quando(MAR, 8 * 60), 40)
    s = S()
    v = servizi.griglia(s, MAR, 1)
    assert v['base'] == 15, v['base']
    c = colonna(v, 'Ambulatorio 3')
    tid = c['turni'][0].id
    assert senza_coperte(c['celle'])[:7] == [('occupata', '08:00', 3, (lunga,))] + \
        [('aperta', hm(m), 3, tid) for m in range(8 * 60 + 45, 12 * 60 + 30, 45)] + \
        [('chiusa', '12:30', 2, None)], senza_coperte(c['celle'])[:7]
    assert servizi.blocco(c['turni'][0], quando(MAR, 9 * 60 + 40), quando(MAR, 9 * 60 + 50)) == \
        (quando(MAR, 9 * 60 + 30), quando(MAR, 10 * 60 + 15))
    s.close()
    # dalle 8:10 a fasce di 20: il pezzo 8:00-8:10 resta della struttura (chiuso)
    S = mondo()
    I = ids(S)
    turno(S, I['Ambulatorio 4'], I['Provolo'], time(8, 10), time(10, 10), passo=20)
    s = S()
    v = servizi.griglia(s, MAR, 1)
    assert v['base'] == 10, v['base']
    c = colonna(v, 'Ambulatorio 4')
    tid = c['turni'][0].id
    assert senza_coperte(c['celle'])[:8] == [('chiusa', '08:00', 1, None)] + \
        [('aperta', hm(m), 2, tid) for m in range(8 * 60 + 10, 10 * 60 + 10, 20)] + \
        [('chiusa', '10:10', 2, None)], senza_coperte(c['celle'])[:8]
    p = servizi.disponibilita(s, I['Provolo'], 20, MAR, 1, giorni=0)
    assert [x['inizio'].strftime('%H:%M') for x in p] == [hm(m) for m in range(8 * 60 + 10, 10 * 60 + 10, 20)], p
    s.close()
    # oltre la chiusura: struttura fino alle 14, turno dalle 13 alle 16 a fasce di 20
    S = mondo()
    I = ids(S)
    s = S()
    s.get(Struttura, 1).ora_chiusura = time(14, 0)
    s.commit()
    s.close()
    turno(S, I['Ambulatorio 5'], I['Testabianca'], time(13, 0), time(16, 0), passo=20)
    s = S()
    v = servizi.griglia(s, MAR, 1)
    assert v['fasce'][-1] == time(13, 50) and v['base'] == 10, (v['fasce'][-1], v['base'])
    c = colonna(v, 'Ambulatorio 5')
    assert senza_coperte(c['celle'])[-3:] == [('aperta', '13:00', 2, c['turni'][0].id),
                                              ('aperta', '13:20', 2, c['turni'][0].id),
                                              ('aperta', '13:40', 2, c['turni'][0].id)], senza_coperte(c['celle'])[-3:]
    s.close()
    # un appuntamento oltre la tabella la allunga, con le righe fitte
    app_(S, I['Ambulatorio 5'], I['Testabianca'], quando(MAR, 15 * 60), 20)
    s = S()
    v = servizi.griglia(s, MAR, 1)
    assert v['fasce'][-1] == time(15, 10), v['fasce'][-1]
    s.close()


def c_blocco():
    class T(object):
        ora_inizio, ora_fine, passo_proprio = time(8, 0), time(13, 0), 15
    t = T()

    def b(a_, b_):
        x = servizi.blocco(t, quando(MAR, a_), quando(MAR, b_))
        return hm(int((x[0] - quando(MAR, 0)).total_seconds() // 60)), hm(int((x[1] - quando(MAR, 0)).total_seconds() // 60))
    assert b(8 * 60 + 5, 8 * 60 + 20) == ('08:00', '08:30')
    assert b(8 * 60, 8 * 60 + 15) == ('08:00', '08:15')
    assert b(12 * 60 + 50, 13 * 60 + 20) == ('12:45', '13:20')      # finisce dopo il turno: l'ora vera
    assert b(7 * 60 + 50, 8 * 60 + 10) == ('07:50', '08:15')        # comincia prima: l'ora vera
    assert b(13 * 60, 13 * 60 + 30) == ('13:00', '13:30')           # fuori dal turno
    assert b(8 * 60 + 7, 8 * 60 + 7) == ('08:00', '08:15')
    assert servizi.blocco(None, quando(MAR, 600), quando(MAR, 610)) == (quando(MAR, 600), quando(MAR, 610))
    # base delle righe e altezza
    T.passo_proprio = None
    assert servizi.base_righe(30, time(8, 0), [t]) == 30
    for passo_, inizio, fine, atteso in ((15, time(8, 0), time(13, 0), 15), (20, time(9, 0), time(12, 0), 10),
                                         (45, time(8, 0), time(12, 30), 15), (40, time(8, 10), time(12, 10), 10),
                                         (20, time(8, 7), time(12, 7), 5), (30, time(8, 0), time(13, 0), 30)):
        T.passo_proprio, T.ora_inizio, T.ora_fine = passo_, inizio, fine
        assert servizi.base_righe(30, time(8, 0), [t]) == atteso, (passo_, inizio, atteso)
    assert servizi.ultima_riga(time(19, 30), 30, 15) == time(19, 45)
    assert servizi.ultima_riga(time(19, 30), 30, 30) == time(19, 30)
    T.passo_proprio = 15
    assert servizi.altezza_riga(30, 30, [t]) == 36
    assert servizi.altezza_riga(30, 15, [t]) == 24
    T.passo_proprio = 20
    assert servizi.altezza_riga(30, 10, [t]) == 12
    T.passo_proprio = 10
    assert servizi.altezza_riga(30, 5, [t]) == 12
    T.passo_proprio = 60
    assert servizi.altezza_riga(30, 30, [t]) == 36


prova('fasce da 15 in una struttura da 30: colonscopia su tre fasce, EGDS su due, il resto come prima', c_mano_15)
prova('fasce da 20: visita da 30 su due fasce, esame da 10 su una intera, controlli e avvisi', c_mano_20)
prova('fasce da 45, turno alle 8:10, turno oltre la chiusura, appuntamento oltre la tabella', c_mano_45_e_bordi)
prova('blocco, righe e altezza nei casi limite', c_blocco)


# ============================================================ prima delle fasce
area('appuntamenti presi prima delle fasce')


def d_gia_presi():
    """Due visite prese a fasce di 30 (9:00-9:30 e 9:30-10:00); poi il turno passa
    a fasce di 20: salvando il turno arriva l'avviso; le due visite si possono
    modificare (nota, medico) senza errori; spostarne una in una fascia libera
    va, in una occupata no; una nuova alle 9:20 no."""
    S = mondo()
    I = ids(S)
    C = collega(S)
    amb = I['Ambulatorio 3']
    tid = turno(S, amb, I['Esempietti'], time(9, 0), time(12, 0))
    prima = app_(S, amb, I['Esempietti'], quando(MAR, 9 * 60), 30, prestazione=I['Prima visita'])
    seconda = app_(S, amb, I['Esempietti'], quando(MAR, 9 * 60 + 30), 30, prestazione=I['Prima visita'])
    dati = {'operatore': str(I['Esempietti']), 'risorsa': str(amb), 'giorno': str(MAR.weekday()),
            'ora_inizio': '09:00', 'ora_fine': '12:00', 'valido_da': (MAR - timedelta(days=60)).isoformat(),
            'valido_a': '', 'ripetizione': 'settimanale', 'passo': '20'}
    r = C.post('/anagrafiche/turni/%d' % tid, data=dati, follow_redirects=True)
    t = testo(r)
    assert 'Turno salvato' in t and 'fasce da 20 minuti' in t, t[:300]
    assert 'Ci sono 2 appuntamenti già prenotati in questo turno che non stanno nelle fasce da 20 minuti' in t and \
        'il primo il %s alle 09:00' % MAR.strftime('%d/%m') in t, re.findall(r'appuntament[^.]*\.', t)[:3]
    s = S()
    assert s.get(Turno, tid).passo == 20
    s.close()
    # modificare la prima (una nota) va bene, anche se divide una fascia con la seconda
    modulo = {'risorsa': str(amb), 'operatore': str(I['Esempietti']), 'prestazione': str(I['Prima visita']),
              'data': MAR.isoformat(), 'ora': '09:00', 'durata': '30', 'struttura': '1', 'paziente': 'Fittizi',
              'nome_paziente': 'Teresa', 'telefono': '3330000001', 'tipo': '', 'convenzione': '', 'importo': '',
              'note': 'portare gli esami', 'degenza': ''}
    r = C.post('/appuntamento/%d' % prima, data=modulo, follow_redirects=True)
    assert 'fascia' not in testo(r) or 'già occupata' not in testo(r), testo(r)[:400]
    s = S()
    assert s.get(Appuntamento, prima).note == 'portare gli esami'
    # cambiare medico alla seconda (stesso posto): nessun errore di fasce
    assert servizi.conflitti(s, amb, I['Provolo'], quando(MAR, 9 * 60 + 30), quando(MAR, 10 * 60), seconda) == []
    # rimettere attiva una disdetta controlla tutto: la seconda disdetta e rimessa no
    a2 = s.get(Appuntamento, seconda)
    a2.stato = 'DISDETTO'
    s.commit()
    motivi = servizi.imposta_stato(s, a2, 'PRENOTATO')
    assert len(motivi) == 1 and 'la fascia delle 09:20' in motivi[0], motivi
    s.rollback()
    a2 = s.get(Appuntamento, seconda)
    a2.stato = 'PRENOTATO'
    s.commit()
    # spostare la seconda alle 9:40 (fascia libera) va bene; alle 9:20 no
    assert servizi.sposta(s, s.get(Appuntamento, seconda), quando(MAR, 9 * 60 + 20)) != []
    s.rollback()
    assert servizi.sposta(s, s.get(Appuntamento, seconda), quando(MAR, 9 * 60 + 40)) == []
    s.commit()
    # una nuova alle 9:20 no (la fascia e' della prima), alle 10:20 si'
    assert servizi.conflitti(s, amb, I['Esempietti'], quando(MAR, 9 * 60 + 30), quando(MAR, 9 * 60 + 40)) != []
    assert servizi.conflitti(s, amb, I['Esempietti'], quando(MAR, 10 * 60 + 20), quando(MAR, 10 * 60 + 40)) == []
    s.close()
    # salvando di nuovo il turno l'avviso non c'e' piu': la seconda ora sta nelle fasce
    r = C.post('/anagrafiche/turni/%d' % tid, data=dati, follow_redirects=True)
    assert 'non stanno nelle fasce' not in testo(r) and 'non sta nelle fasce' not in testo(r), testo(r)[:300]


def d_sposta_pagina():
    """Spostare dalla pagina: in una fascia occupata no (con la spiegazione), in
    una libera si'; le proposte seguono le fasce."""
    S = mondo()
    I = ids(S)
    C = collega(S)
    sala = I['Sala endoscopia']
    turno(S, sala, I['Fintini'], time(8, 0), time(13, 0), passo=15)
    app_(S, sala, I['Fintini'], quando(MAR, 8 * 60), 40, prestazione=I['Colonscopia'])
    egds = app_(S, sala, I['Fintini'], quando(MAR, 10 * 60), 20, prestazione=I['EGDS'])
    r = C.get('/appuntamento/%d/sposta?dal=%s' % (egds, MAR.isoformat()))
    proposte = re.findall(r'name="inizio" value="([^"]+)"><input type="hidden" name="risorsa"', html(r))
    giorno = MAR.isoformat()
    assert r.status_code == 200 and proposte[:5] == ['%sT%s' % (giorno, x) for x in
                                                     ('08:45', '09:00', '09:15', '09:30', '10:30')], proposte[:6]
    r = C.post('/appuntamento/%d/sposta' % egds, data={'inizio': '%sT08:40' % MAR.isoformat(), 'risorsa': str(sala)},
               follow_redirects=True)
    t = testo(r)
    assert 'Non spostato' in t and 'la fascia delle 08:30' in t and 'fasce sono da 15 minuti' in t, t[:600]
    s = S()
    assert s.get(Appuntamento, egds).inizio == quando(MAR, 10 * 60)
    s.close()
    r = C.post('/appuntamento/%d/sposta' % egds, data={'inizio': '%sT08:45' % MAR.isoformat(), 'risorsa': str(sala)},
               follow_redirects=True)
    assert 'Spostato' in testo(r), testo(r)[:400]
    s = S()
    assert s.get(Appuntamento, egds).inizio == quando(MAR, 8 * 60 + 45)
    s.close()


prova('presi prima delle fasce: avviso salvando il turno, modifiche sempre possibili, spostamenti controllati',
      d_gia_presi)
prova('spostare dalla pagina: fascia occupata no, libera sì, proposte sulle fasce', d_sposta_pagina)


# ============================================================ pagine
area('pagine')


class Tabella(HTMLParser):
    """Le righe del corpo della prima tabella con la classe data: per ogni
    riga le celle (tag, righe occupate, classe, testo); e le intestazioni."""

    def __init__(self, classe):
        super().__init__(convert_charrefs=True)
        self.classe, self.livello, self.finita = classe, 0, False
        self.corpo = self.testa = False
        self.righe, self.intestazioni, self.cella = [], [], None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.finita:
            return
        if tag == 'table':
            if self.livello:
                self.livello += 1
            elif self.classe in (a.get('class') or '').split():
                self.livello = 1
            return
        if self.livello != 1:
            return
        if tag == 'tbody':
            self.corpo = True
        elif tag == 'thead':
            self.testa = True
        elif tag == 'tr' and self.corpo:
            self.righe.append([])
        elif tag in ('td', 'th') and (self.corpo or self.testa):
            self.cella = {'tag': tag, 'righe': int(a.get('rowspan') or 1), 'classe': a.get('class') or '',
                          'testo': '', 'stile': a.get('style') or ''}
            (self.righe[-1] if self.corpo else self.intestazioni).append(self.cella)
        elif tag == 'a' and self.cella is not None:
            self.cella.setdefault('link', []).append((a.get('href') or '', a.get('class') or '', a.get('style') or ''))

    def handle_endtag(self, tag):
        if tag == 'table' and self.livello:
            self.livello -= 1
            self.finita = not self.livello
        elif tag == 'tbody':
            self.corpo = False
        elif tag == 'thead':
            self.testa = False
        elif tag in ('td', 'th'):
            self.cella = None

    def handle_data(self, d):
        if self.cella is not None:
            self.cella['testo'] += d


def tabella(pagina, classe='griglia'):
    t = Tabella(classe)
    t.feed(pagina)
    return t


def disposta(t, colonne):
    """Ogni riga, con le celle alte piu' righe che arrivano da sopra, ha
    esattamente 'colonne' celle, e nessuna va oltre il fondo."""
    prese = set()
    for i, r in enumerate(t.righe):
        c = 0
        for cella in r:
            while (i, c) in prese:
                c += 1
            for k in range(cella['righe']):
                assert (i + k, c) not in prese, 'riga %d, colonna %d: due celle nello stesso posto' % (i + k, c)
                prese.add((i + k, c))
            c += 1
        n = sum(1 for x, _ in prese if x == i)
        assert n == colonne, 'riga %d: %d celle invece di %d' % (i, n, colonne)
    assert all(x < len(t.righe) for x, _ in prese), 'una cella va oltre il fondo della tabella'
    return len(t.righe)


def mondo_15():
    S = mondo()
    I = ids(S)
    sala, amb = I['Sala endoscopia'], I['Ambulatorio 1']
    turno(S, sala, I['Fintini'], time(8, 0), time(13, 0), passo=15)
    turno(S, amb, I['Fintini'], time(14, 0), time(18, 0))
    turno(S, I['Ambulatorio 2'], I['Esempietti'], time(9, 0), time(12, 0), passo=20)
    app_(S, sala, I['Fintini'], quando(MAR, 8 * 60), 40, prestazione=I['Colonscopia'])
    app_(S, sala, I['Fintini'], quando(MAR, 9 * 60), 20, prestazione=I['EGDS'])
    app_(S, amb, I['Fintini'], quando(MAR, 14 * 60), 60, prestazione=I['Prima visita'])
    app_(S, I['Ambulatorio 2'], I['Esempietti'], quando(MAR, 9 * 60), 30, prestazione=I['Prima visita'])
    return S, I


def e_giorno():
    S, I = mondo_15()
    C = collega(S)
    r = C.get('/giorno/%s?struttura=1' % MAR.isoformat())
    p = html(r)
    assert r.status_code == 200
    t = tabella(p)
    s = S()
    v = servizi.griglia(s, MAR, 1)
    assert disposta(t, 1 + len(v['colonne'])) == len(v['fasce'])
    s.close()
    # righe da 5 minuti (15 e 20 insieme): 8 pixel, cosi' la fascia da 15 e' alta 24
    assert v['base'] == 5 and 'class="fasce-miste" style="--riga: 8px"' in p, re.findall(r'<tbody[^>]*>', p)
    intest = [x['testo'] for x in t.intestazioni]
    sala = next(x for x in intest if 'Sala endoscopia' in x)
    assert "fasce da 15'" in sala and "fasce da 20'" in next(x for x in intest if 'Ambulatorio 2' in x), intest
    assert 'fasce da' not in next(x for x in intest if 'Ambulatorio 1' in x)
    # le fasce libere della sala dicono la loro ora e portano a quell'ora
    libere = [(l[0], c['testo']) for r_ in t.righe for c in r_ if 'aperta' in c['classe'] for l in c.get('link', [])
              if 'con-ora' in l[1]]
    assert any(re.search(r'ora=08(:|%3A)45', h) and '08:45' in x for h, x in libere), libere[:3]
    assert any(re.search(r'ora=09(:|%3A)40', h) and '09:40' in x for h, x in libere), libere[:3]
    # quelle dell'ambulatorio 1, senza fasce proprie: "libero", alte quanto una fascia da 30 (6 righe da 5)
    amb1 = [c for r_ in t.righe for c in r_ if 'aperta' in c['classe'] and any('risorsa=%d' % I['Ambulatorio 1'] in l[0]
                                                                                for l in c.get('link', []))]
    assert amb1 and all(c['testo'].strip() == 'libero' and c['righe'] == 6 for c in amb1), \
        [(c['testo'], c['righe']) for c in amb1][:3]
    # righe a meta' fascia della struttura: segnate, l'ora resta per la linea dell'ora
    assert len(re.findall(r'<tr class="[^"]*\bsotto-fascia\b', p)) == sum(1 for e in v['etichette'] if not e)
    # la colonscopia delle 8 occupa tre fasce da 15 = 9 righe da 5
    colo = next(c for r_ in t.righe for c in r_ if 'Colonscopia' in c['testo'])
    assert colo['righe'] == 9, colo['righe']
    # senza fasce proprie (un altro giorno): la griglia di sempre
    r = C.get('/giorno/%s?struttura=1' % (MAR + timedelta(days=1)).isoformat())
    p = html(r)
    for classe in ('fasce-miste', 'fasce-turno', 'con-ora', 'sotto-fascia'):
        assert not re.search(r'class="[^"]*\b%s\b' % classe, p), classe
    disposta(tabella(p), 7)


def e_settimana():
    S, I = mondo_15()
    C = collega(S)
    for cognome in ('Fintini', 'Esempietti', 'Provolo'):
        r = C.get('/settimana/%s?struttura=1&medico=%d' % (MAR.isoformat(), I[cognome]))
        p = html(r)
        assert r.status_code == 200
        t = tabella(p, 'agenda-medico')
        s = S()
        v = servizi.settimana_medico(s, LUNEDI, I[cognome], 1)
        s.close()
        assert disposta(t, 1 + len(v['giorni'])) == len(v['righe']), cognome
        if cognome == 'Fintini':
            assert v['misto'] and v['base'] == 15 and 'class="fasce-miste"' in p, (v['misto'], v['base'])
            assert "fasce da 15'" in ' '.join(x['testo'] for x in t.intestazioni)
            assert re.search(r'ora=08%3A45|ora=08:45', p) and '08:45<span> libero</span>' in p
        elif cognome == 'Provolo':
            assert not v['misto'] and 'class="fasce-miste"' not in p
    # la settimana per stanza e il mese: le fasce libere sono quelle dei turni
    r = C.get('/settimana/%s?struttura=1' % MAR.isoformat())
    assert r.status_code == 200
    s = S()
    v = servizi.griglia(s, MAR, 1)
    libere = sum(c['libere'] for c in v['colonne'])
    m = servizi.mese(s, MAR.year, MAR.month, 1)
    assert m['giorni'][MAR]['libere'] == libere, (m['giorni'][MAR]['libere'], libere)
    m = servizi.mese(s, MAR.year, MAR.month, 1, I['Fintini'])
    assert m['giorni'][MAR]['libere'] == colonna(v, 'Sala endoscopia')['libere'] + colonna(v, 'Ambulatorio 1')['libere']
    s.close()
    assert C.get('/mese/%04d-%02d?struttura=1' % (MAR.year, MAR.month)).status_code == 200


def e_excel():
    from openpyxl import load_workbook
    S, I = mondo_15()
    s = S()
    dati = io.BytesIO()
    servizi.esporta_giorno(s, MAR, 1, dati)
    v = servizi.griglia(s, MAR, 1)
    s.close()
    dati.seek(0)
    ws = load_workbook(dati).worksheets[0]
    assert ws.max_row == 2 + len(v['fasce']), (ws.max_row, len(v['fasce']))
    orari = [ws.cell(r, 1).value for r in range(3, 3 + len(v['fasce']))]
    assert orari == v['fasce'], orari[:4]
    k = [c['risorsa'].nome for c in v['colonne']].index('Sala endoscopia')
    colonna_xl = 2 + 2 * k
    fusioni = {(m.min_row, m.max_row) for m in ws.merged_cells.ranges if m.min_col == colonna_xl}
    assert (3, 11) in fusioni and (15, 20) in fusioni, sorted(fusioni)       # 8:00-8:45 e 9:00-9:30, righe da 5
    assert 'Colonscopia' in str(ws.cell(3, colonna_xl + 1).value), ws.cell(3, colonna_xl + 1).value


def e_turno_modulo():
    S = mondo()
    I = ids(S)
    C = collega(S)
    p = html(C.get('/anagrafiche/turni/nuovo'))
    scelta = re.search(r'<select[^>]*name="passo".*?</select>', p, re.S)
    assert scelta, 'manca la durata delle fasce'
    valori = re.findall(r'<option value="([^"]*)"', scelta.group(0))
    assert valori == ['0'] + [str(x) for x in PASSI_TURNO], valori
    assert 'Come la struttura (30 minuti)' in scelta.group(0) and 'selected' in scelta.group(0).split('</option>')[0]
    dati = {'operatore': str(I['Provolo']), 'risorsa': str(I['Ambulatorio 4']), 'giorno': '1', 'ora_inizio': '09:00',
            'ora_fine': '12:00', 'valido_da': MAR.isoformat(), 'valido_a': '', 'ripetizione': 'settimanale'}
    r = C.post('/anagrafiche/turni/nuovo', data=dict(dati, passo='15'), follow_redirects=True)
    assert 'Turno salvato' in testo(r) and 'fasce da 15 minuti' in testo(r), testo(r)[:300]
    s = S()
    t = s.scalars(select(Turno)).one()
    tid = t.id
    assert t.passo == 15 and t.passo_proprio == 15
    s.close()
    p = html(C.get('/anagrafiche/turni/%d' % tid))
    scelta = re.search(r'<select[^>]*name="passo".*?</select>', p, re.S).group(0)
    assert re.search(r'<option value="15"[^>]*selected', scelta), scelta[:300]
    assert "fasce da 15'" in html(C.get('/anagrafiche')), 'l\'elenco dei turni non dice le fasce'
    # una scelta che non c'e': errore, niente salvato
    r = C.post('/anagrafiche/turni/%d' % tid, data=dict(dati, passo='25'), follow_redirects=True)
    assert 'Durata delle fasce: scelta non valida.' in testo(r)
    r = C.post('/anagrafiche/turni/%d' % tid, data=dict(dati, passo='abc'), follow_redirects=True)
    assert 'Durata delle fasce: scelta non valida.' in testo(r)
    s = S()
    assert s.get(Turno, tid).passo == 15
    s.close()
    # un modulo senza il campo (di una versione precedente) non cambia le fasce
    r = C.post('/anagrafiche/turni/%d' % tid, data=dict(dati, ora_fine='12:30'), follow_redirects=True)
    assert 'Turno salvato' in testo(r)
    s = S()
    assert s.get(Turno, tid).passo == 15 and s.get(Turno, tid).ora_fine == time(12, 30)
    s.close()
    # "Come la struttura": torna vuoto
    r = C.post('/anagrafiche/turni/%d' % tid, data=dict(dati, passo='0'), follow_redirects=True)
    assert 'Turno salvato' in testo(r) and 'fasce da' not in testo(r).split('Turno salvato')[1][:120]
    s = S()
    assert s.get(Turno, tid).passo is None
    s.close()


def e_guida():
    a = guida.PER_SLUG['fasce-turno']
    assert a['condizione'] == 'thead .fasce-turno' and a['endpoint'] == 'giorno'
    voci = dict(novita.NOVITA)['1.10']
    assert len(voci) >= 3 and all(x.get('guida') == 'fasce-turno' for x in voci), voci
    S, I = mondo_15()
    C = collega(S)
    p = html(C.get('/giorno/%s?struttura=1' % MAR.isoformat()))
    # i passi della guida trovano i loro elementi nella pagina
    t = tabella(p)
    assert 'class="fasce-turno"' in p.split('</thead>')[0]
    assert any('con-ora' in l[1] for r_ in t.righe for c in r_ for l in c.get('link', []))
    assert any('occupata' in c['classe'] and 'Colonscopia' in c['testo'] for r_ in t.righe for c in r_)
    r = C.get('/aiuto/fasce-turno')
    assert r.status_code == 200 and a['titolo'] in testo(r)
    # "Mostrami sullo schermo" apre il primo giorno con un turno a fasce proprie (qui ogni martedi)
    primo = OGGI + timedelta(days=(1 - OGGI.weekday()) % 7)
    m = re.search(r'href="([^"]+)" data-guida-mostra', html(r))
    assert m and m.group(1).replace('&amp;', '&') == '/giorno/%s?struttura=1&guida=fasce-turno' % primo.isoformat(), \
        m and m.group(1)
    # senza turni a fasce proprie: oggi, come le altre guide della griglia
    C2 = collega(mondo())
    m = re.search(r'href="([^"]+)" data-guida-mostra', html(C2.get('/aiuto/fasce-turno')))
    assert m and m.group(1).replace('&amp;', '&') == '/giorno/%s?guida=fasce-turno' % OGGI.isoformat(), m and m.group(1)
    C = collega(S)
    passi = C.get('/aiuto/fasce-turno/passi.json').get_json()
    assert passi['slug'] == 'fasce-turno' and len(passi['passi']) >= 4, passi
    # e nella pagina c'e' ogni elemento che i passi illuminano
    for x in passi['passi']:
        if x.get('sel') == 'thead .fasce-turno':
            assert 'class="fasce-turno"' in p.split('</thead>')[0]
        elif x.get('sel') == 'td.aperta a.con-ora':
            assert re.search(r'<td class="aperta"[^>]*><a class="posa con-ora"', p)
        elif x.get('sel') == 'td.occupata':
            assert any('occupata' in c['classe'] and x.get('contiene', '') in c['testo'] for r_ in t.righe for c in r_)
        else:
            assert not x.get('sel'), x


prova('griglia: righe complete, fasce dette in testa, ore nelle fasce libere, sotto-fasce, come prima senza',
      e_giorno)
prova('agenda del medico, settimana per stanza e mese con le fasce proprie', e_settimana)
prova('Excel del giorno con le righe fitte e le celle unite', e_excel)
prova('modulo del turno: durata delle fasce, scelta sbagliata, modulo vecchio, come la struttura', e_turno_modulo)
prova('guida e novità della 1.10', e_guida)


# ============================================================ database
area('database')


def f_migrazione():
    """Un database della 1.9.1 (versione 10, senza la colonna): alla prima
    apertura copia di sicurezza, colonna nuova vuota, dati intatti, griglia come
    prima."""
    percorso = percorso_nuovo('vecchio')
    S0 = crea_sessione('sqlite:///' + percorso)
    s = S0()
    servizi.prepara_primo_avvio(s, 'Sede di prova')
    s.add(Operatore(cognome='Fintini', nome='Ugo'))
    s.commit()
    s.add(Turno(operatore_id=1, risorsa_id=1, giorno_settimana=MAR.weekday(), ora_inizio=time(9, 0),
                ora_fine=time(12, 0), valido_da=MAR - timedelta(days=30)))
    s.add(Appuntamento(risorsa_id=1, operatore_id=1, inizio=quando(MAR, 9 * 60), fine=quando(MAR, 9 * 60 + 40)))
    s.commit()
    prima = _vista_191(griglia_191(s, MAR, 1))
    s.close()
    S0.motore.dispose()
    c = sqlite3.connect(percorso)
    if sqlite3.sqlite_version_info >= (3, 35):
        c.execute('ALTER TABLE turni DROP COLUMN passo')
    else:                                            # SQLite vecchio: la tabella rifatta senza
        colonne = [r[1] for r in c.execute('PRAGMA table_info(turni)') if r[1] != 'passo']
        c.execute('CREATE TABLE turni_x AS SELECT %s FROM turni' % ', '.join(colonne))
        c.execute('DROP TABLE turni')
        c.execute('ALTER TABLE turni_x RENAME TO turni')
    c.execute("UPDATE impostazioni SET valore = '10' WHERE chiave = 'versione_schema'")
    c.commit()
    assert 'passo' not in [r[1] for r in c.execute('PRAGMA table_info(turni)')]
    c.close()
    S = crea_sessione('sqlite:///' + percorso)
    note = ' | '.join(S.migrazioni)
    assert S.versione_precedente == 10 and VERSIONE_SCHEMA == 11, (S.versione_precedente, VERSIONE_SCHEMA)
    assert 'prima-della-versione-11' in note and 'da 10 a 11' in note, note
    assert 'turni.passo' in S.colonne_aggiunte, S.colonne_aggiunte
    assert os.listdir(os.path.join(os.path.dirname(percorso), 'backup')), 'copia di sicurezza mancante'
    s = S()
    t = s.scalars(select(Turno)).one()
    assert t.passo is None and t.passo_proprio is None and t.ora_inizio == time(9, 0)
    assert s.scalars(select(Appuntamento)).one().fine == quando(MAR, 9 * 60 + 40)
    dopo = servizi.griglia(s, MAR, 1)
    assert _vista_191(dopo) == prima and not dopo['misto']
    t.passo = 20
    s.commit()
    assert servizi.griglia(s, MAR, 1)['misto']
    s.close()
    S2 = crea_sessione('sqlite:///' + percorso)
    assert S2.versione_precedente == VERSIONE_SCHEMA and not S2.migrazioni


prova('aggiornamento dalla versione 10: copia di sicurezza, colonna nuova vuota, dati e griglia intatti',
      f_migrazione)


# =====================================================================
if __name__ == '__main__':
    aree = []
    for e in esiti:
        if e[1] not in aree:
            aree.append(e[1])
    for a in aree:
        mie = [e for e in esiti if e[1] == a]
        rotte = [e for e in mie if e[0] != 'OK']
        print('%-45s %2d prove  %s' % (a, len(mie), 'tutte a posto' if not rotte else '%d DA SISTEMARE' % len(rotte)))
    rotte = [e for e in esiti if e[0] != 'OK']
    if rotte or os.environ.get('DETTAGLIO'):
        print('\nDettaglio:')
        for e in esiti:
            if e[0] != 'OK' or os.environ.get('DETTAGLIO'):
                print('  %-6s [%s] %s\n         %s' % (e[0], e[1], e[2], e[3]))
    print('\n%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(rotte), len(rotte)))
    shutil.rmtree(PROVVISORIA, ignore_errors=True)
    sys.exit(1 if rotte else 0)
