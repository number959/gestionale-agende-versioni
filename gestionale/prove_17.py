# -*- coding: utf-8 -*-
"""Prove della 1.7: il codice fiscale controllato (con il motivo) e calcolato
dai dati, sesso e luogo di nascita del paziente, i luoghi (comuni anche
soppressi e stati esteri), la scheda e la prenotazione, l'aggiornamento
dello schema che completa i pazienti gia' in archivio, la pagina Controllo
dei codici fiscali, importazione, unione, segnaposto.

Calcolo e lettura si confrontano anche con una libreria indipendente,
python-codicefiscale (pip install python-codicefiscale), su migliaia di casi
generati; senza la libreria quelle prove si saltano e lo dicono (il
programma non la usa). Tutti i nomi sono inventati."""
import json
import os
import random
import re
import shutil
import sqlite3
import string
import sys
import traceback
from datetime import date, datetime, time, timedelta
from html import unescape

import logging
logging.getLogger().setLevel(logging.CRITICAL)

from sqlalchemy import select

import servizi
import viste
import pazienti
import importa
import documenti
import novita
import guida
import comune
import codice_fiscale as CF
import app as A
from modelli import (crea_sessione, VERSIONE_SCHEMA, Struttura, Risorsa, Operatore, Prestazione, Appuntamento,
                     Paziente, Attivita, leggi_impostazione, scrivi_impostazione)

try:
    from codicefiscale import codicefiscale as ORACOLO
except ImportError:
    ORACOLO = None

A.app.config['TESTING'] = True
CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = os.path.join(CARTELLA, 'prove_17_tmp')
shutil.rmtree(PROVVISORIA, ignore_errors=True)
os.makedirs(PROVVISORIA)
esiti, _area, _n = [], [''], [0]
OGGI = date.today()
SOLO = [x for x in os.environ.get('PROVE_SOLO', '').split(',') if x]
NAPOLI = 'F839'
FINTINI = CF.calcola('Fintini', 'Prova', date(1980, 1, 1), 'M', NAPOLI)        # FNTPRV80A01F839W


def area(nome):
    _area[0] = nome


def prova(nome, f):
    if SOLO and f.__name__ not in SOLO:
        return
    try:
        esiti.append(('OK', _area[0], nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', _area[0], nome, str(e) or 'asserzione fallita'))
    except Exception:
        esiti.append(('ERRORE', _area[0], nome, traceback.format_exc().strip().splitlines()[-1]))


# ================================================================ il mondo
def percorso_nuovo(nome='db'):
    _n[0] += 1
    dove = os.path.join(PROVVISORIA, 'm%d' % _n[0])
    os.makedirs(dove)
    return os.path.join(dove, '%s.db' % nome)


def mondo():
    """Un gestionale nuovo: stanze e prestazioni di partenza, un medico di prova."""
    S = crea_sessione('sqlite:///' + percorso_nuovo())
    s = S()
    servizi.prepara_primo_avvio(s)
    s.get(Struttura, 1).giorni_apertura = '1111110'
    s.add(Operatore(cognome='Provolo', nome='Ugo'))
    s.add(Prestazione(nome='Visita di prova', durata_min=30))
    s.commit()
    s.close()
    A.Sessione = S
    A._registro = None
    viste._sessionmaker = lambda: S
    return S, A.app.test_client()


def html(r):
    return r.get_data(as_text=True)


def testo(r):
    return ' '.join(unescape(re.sub(r'<[^>]+>', ' ', html(r))).split())


def avvisi(C):
    with C.session_transaction() as sess:
        m = sess.get('_flashes', [])
        sess['_flashes'] = []
    return [(c, unescape(t)) for c, t in m]


def testo_avvisi(C):
    return ' '.join(t for _, t in avvisi(C))


def paziente(S, **cerca):
    s = S()
    try:
        q = select(Paziente)
        for k, v in cerca.items():
            q = q.where(getattr(Paziente, k) == v)
        p = s.scalars(q.order_by(Paziente.id.desc())).first()
        if p is not None:
            s.expunge(p)
        return p
    finally:
        s.close()


def nuovo_paziente(S, **campi):
    s = S()
    p = Paziente(**campi)
    s.add(p)
    s.commit()
    pid = p.id
    s.close()
    return pid


def prossimo_giorno_feriale(da=None):
    g = (da or OGGI) + timedelta(days=7)
    while g.weekday() >= 5:
        g += timedelta(days=1)
    return g


def prenota(C, S, ora='10:00', giorno=None, **campi):
    s = S()
    stanza = s.scalars(select(Risorsa).where(Risorsa.nome == 'Ambulatorio 1')).first()
    medico = s.scalars(select(Operatore).where(Operatore.cognome == 'Provolo')).first()
    prest = s.scalars(select(Prestazione).where(Prestazione.nome == 'Visita di prova')).first()
    dati = {'risorsa': stanza.id, 'operatore': medico.id, 'prestazione': prest.id, 'struttura': 1,
            'data': (giorno or prossimo_giorno_feriale()).isoformat(), 'ora': ora, 'durata': '30', 'tipo': '',
            'degenza': '', 'paziente': 'Fintini', 'nome_paziente': 'Prova', 'telefono': '333 000 0101'}
    s.close()
    dati.update(campi)
    return C.post('/appuntamento', data=dati)


def scheda(C, **campi):
    dati = {'cognome': 'Fintini', 'nome': 'Prova', 'telefono': '3330000101', 'canale': 'WHATSAPP', 'promemoria': '1'}
    dati.update(campi)
    return C.post('/pazienti/nuovo', data=dati)


# ========================================================= forma e lettura
area('forma e lettura del codice')


def f_difetti():
    assert FINTINI == 'FNTPRV80A01F839W', FINTINI
    assert CF.pulisci(' fntprv 80a01-f839.w ') == FINTINI and CF.valido(' fntprv 80a01 f839w')
    casi = [
        ('FNTPRV80A01F839', 'ha 15 caratteri: ne servono 16'),
        ('FNTPRV80A01F839WW', 'ha 17 caratteri'),
        ('FNTPRV80A01F839/', 'caratteri che non vanno'),
        ('FNT1RV80A01F839W', 'I primi sei caratteri devono essere lettere'),
        ('FNTPRVA0A01F839W', 'Al 7° e all\'8° posto va l\'anno'),
        ('FNTPRV80Z01F839W', 'Al 9° posto va la lettera del mese'),
        ('FNTPRV80A0AF839W', 'Al 10° e all\'11° posto va il giorno'),
        ('FNTPRV80A35F839W', 'Il giorno di nascita «35» non esiste'),
        ('FNTPRV80B30F839W', 'La data di nascita del codice, 30 febbraio, non esiste'),
        ('FNTPRV80A01F8A9W', 'Dal 12° al 15° posto va il codice del luogo'),
        ('FNTPRV80A01F8391', 'L\'ultimo carattere deve essere una lettera'),
        ('FNTPRV80A01F839X', 'con questi caratteri sarebbe «W»'),
    ]
    for cf, atteso in casi:
        motivo = CF.difetto(cf)
        assert atteso in motivo, (cf, motivo)
        assert not CF.valido(cf), cf
    # il 29 febbraio dell'anno 00 esiste (2000): valido, e letto nel 2000
    primi = 'FNTPRV00B29F839'
    cf = primi + CF.carattere_controllo(primi)
    assert CF.valido(cf) and CF.nascita(cf, date(2026, 1, 1)) == date(2000, 2, 29), CF.nascita(cf)
    # un errore di battitura qualsiasi in un codice giusto: sempre trovato
    for i in range(16):
        for c in string.ascii_uppercase + string.digits:
            sbagliato = FINTINI[:i] + c + FINTINI[i + 1:]
            if sbagliato != FINTINI:
                assert not CF.valido(sbagliato) or CF.leggi(sbagliato) is not None, sbagliato
    return '%d difetti, ognuno con il suo motivo' % len(casi)


def f_omocodia():
    base = CF.calcola('Esempietti', 'Maria Rosa', date(1975, 3, 12), 'F', 'H892')
    varianti = set()
    cifre = list(CF.POSIZIONI_CIFRE)
    for n in range(1, len(cifre) + 1):
        primi = list(base[:15])
        for i in cifre[-n:]:                   # da destra, come fa l'Agenzia delle Entrate
            primi[i] = CF.OMOCODIA[int(primi[i])]
        primi = ''.join(primi)
        varianti.add(primi + CF.carattere_controllo(primi))
    if ORACOLO is not None:
        varianti |= set(ORACOLO.decode(base)['omocodes'])
    letto = CF.leggi(base)
    for v in varianti:
        assert CF.valido(v), v
        d = CF.leggi(v)
        assert (d['sesso'], d['data_nascita'], d['luogo']) == (letto['sesso'], letto['data_nascita'], letto['luogo']), v
        assert d['omocodico'] == (v != base), v
        assert CF.senza_omocodia(v)[:15] == base[:15]
        assert CF.confronta(v, 'Esempietti', 'Maria Rosa', date(1975, 3, 12), 'F', 'H892') == [], v
    return '%d varianti omocodiche accettate e lette come il codice di base' % len(varianti)


def f_secolo():
    oggi = date(2026, 10, 5)
    for anno, atteso in ((25, date(2025, 1, 15)), (26, date(2026, 1, 15)), (27, date(1927, 1, 15)), (99, date(1999, 1, 15)),
                         (0, date(2000, 1, 15))):
        primi = 'FNTPRV%02dA15F839' % anno
        cf = primi + CF.carattere_controllo(primi)
        assert CF.nascita(cf, oggi) == atteso, (anno, CF.nascita(cf, oggi))
    # nato oggi ma fra un mese: il secolo prima
    primi = 'FNTPRV26S05F839'                  # S = novembre
    assert CF.nascita(primi + CF.carattere_controllo(primi), oggi) == date(1926, 11, 5)
    # le donne: giorno + 40
    primi = 'FNTPRV80A41F839'
    d = CF.leggi(primi + CF.carattere_controllo(primi))
    assert d['sesso'] == 'F' and d['data_nascita'] == date(1980, 1, 1), d


prova('motivi precisi: lunghezza, posto per posto, data inesistente, controllo', f_difetti)
prova('omocodia: le cifre diventate lettere si accettano e si leggono', f_omocodia)
prova('secolo della data, donne con il giorno + 40', f_secolo)


# =================================================================== calcolo
area('calcolo')


def c_regole():
    casi = [
        (('Fo', 'Ia', date(1990, 5, 3), 'M', NAPOLI), 'FOXIAX90E03F839'),          # corti: si aggiunge X
        (('Rossetti', 'Gianfranco', date(1980, 1, 1), 'M', NAPOLI), 'RSSGFR80A01F839'),   # 4+ consonanti: 1a, 3a, 4a
        (('De Luca', 'Ciro', date(1980, 1, 1), 'M', NAPOLI), 'DLCCRI80A01F839'),
        (("D'Angelo", 'Maria Rosa', date(1950, 2, 28), 'F', 'Z112'), 'DNGMRS50B68Z112'),   # donna: giorno + 40; estero
        (("Dell'Àquila", 'Niccolò', date(2001, 12, 31), 'M', NAPOLI), 'DLLNCL01T31F839'),
        (('Müller-Lüdenscheidt', 'Jürgen ß', date(2001, 12, 31), 'M', 'Z112'), 'MLLJGN01T31Z112'),
        (('Testabianca', 'Lia', date(1990, 11, 23), 'F', 'G964'), 'TSTLIA90S63G964'),
    ]
    for argomenti, primi in casi:
        cf = CF.calcola(*argomenti)
        assert cf == primi + CF.carattere_controllo(primi), (argomenti, cf)
        assert CF.valido(cf)
    assert CF.lettere_cognome('A') == 'AXX' and CF.lettere_nome('') == 'XXX'


def c_oracolo():
    if ORACOLO is None:
        return 'saltata: manca python-codicefiscale'
    caso = random.Random(17)
    attivi = [x for x in CF.tabella() if x.esiste]
    vocali, consonanti = 'AEIOU', 'BCDFGHLMNPRSTVZ'

    def parola():
        n = caso.randint(1, 9)
        p = ''.join(caso.choice(consonanti if caso.random() < 0.6 else vocali) for _ in range(n)).capitalize()
        if caso.random() < 0.1:
            p = caso.choice(["D'", 'De ', 'Della ', 'Di ', 'Lo ']) + p
        if caso.random() < 0.05:
            p = p.replace('A', 'À').replace('E', 'È')
        return p
    n = 0
    for _ in range(3000):
        cognome, nome = parola(), parola() + (' ' + parola() if caso.random() < 0.2 else '')
        nascita = date(1900, 1, 1) + timedelta(days=caso.randint(0, (OGGI - date(1900, 1, 1)).days))
        sesso = caso.choice('MF')
        luogo = caso.choice(attivi).codice
        nostro = CF.calcola(cognome, nome, nascita, sesso, luogo)
        loro = ORACOLO.encode(lastname=cognome, firstname=nome, gender=sesso,
                              birthdate=datetime.combine(nascita, time()), birthplace=luogo)
        assert nostro == loro, (cognome, nome, nascita, sesso, luogo, nostro, loro)
        n += 1
    return '%d codici calcolati uguali a quelli della libreria indipendente' % n


def c_oracolo_lettura():
    if ORACOLO is None:
        return 'saltata: manca python-codicefiscale'
    caso = random.Random(71)
    attivi = [x for x in CF.tabella() if x.esiste]
    letti, rifiutati = 0, 0
    for _ in range(1500):
        nascita = date(1925, 1, 1) + timedelta(days=caso.randint(0, 30000))
        if nascita > OGGI:
            continue
        cf = CF.calcola(''.join(caso.choice(string.ascii_uppercase) for _ in range(6)),
                        ''.join(caso.choice(string.ascii_uppercase) for _ in range(5)),
                        nascita, caso.choice('MF'), caso.choice(attivi).codice)
        loro = ORACOLO.decode(cf)
        nostro = CF.leggi(cf)
        assert nostro['sesso'] == loro['gender'], cf
        assert (nostro['data_nascita'].day, nostro['data_nascita'].month, nostro['data_nascita'].year % 100) == (
            loro['birthdate'].day, loro['birthdate'].month, loro['birthdate'].year % 100), cf
        assert nostro['luogo'] == loro['birthplace']['code'], cf
        letti += 1
        # un carattere cambiato: tutti e due lo rifiutano
        i = caso.randrange(16)
        c = caso.choice([x for x in string.ascii_uppercase + string.digits if x != cf[i]])
        sbagliato = cf[:i] + c + cf[i + 1:]
        assert CF.valido(sbagliato) == ORACOLO.is_valid(sbagliato), (sbagliato, CF.difetto(sbagliato))
        rifiutati += not CF.valido(sbagliato)
    return '%d letti come la libreria, %d codici storpiati rifiutati da tutti e due' % (letti, rifiutati)


def c_mancano():
    try:
        CF.calcola('Fintini', '', None, 'X', 'Napoli')
        assert False, 'calcolato senza dati'
    except CF.DatiMancanti as e:
        assert e.mancano == ['nome', 'sesso', 'data di nascita', 'luogo di nascita'], e.mancano
    try:
        CF.calcola("'", 'Prova', date(1980, 1, 1), 'M', NAPOLI)
        assert False
    except CF.DatiMancanti as e:
        assert e.mancano == ['cognome'], e.mancano


prova('regole: consonanti e vocali, nomi lunghi, accenti, apostrofi, stranieri, donne, estero', c_regole)
prova('calcolo uguale a quello di una libreria indipendente, 3000 casi', c_oracolo)
prova('lettura uguale alla libreria; un carattere storpiato rifiutato da tutti e due', c_oracolo_lettura)
prova('dati mancanti: si dice quali', c_mancano)


# ================================================================ confronto
area('confronto con i dati')


def k_confronta():
    assert CF.confronta(FINTINI, 'Fintini', 'Prova', date(1980, 1, 1), 'M', NAPOLI) == []
    assert CF.confronta(FINTINI, "fintini", 'PROVA') == []                      # maiuscole e minuscole
    assert CF.confronta(FINTINI, '', '', None, '', '') == []                     # niente da confrontare
    assert CF.confronta(FINTINI, cognome='Fantini') == [], 'Fantini ha le stesse lettere: FNT'
    casi = [({'cognome': 'Rossi'}, 'Le lettere del cognome non tornano: per «Rossi» sarebbero RSS'),
            ({'cognome': 'Esempietti'}, 'per «Esempietti» sarebbero SMP, nel codice fiscale c\'è FNT'),
            ({'nome': 'Pietro'}, 'Le lettere del nome non tornano'),
            ({'data_nascita': date(1980, 1, 2)}, 'La data di nascita (02/01/1980) non corrisponde a quella del codice fiscale (01/01/1980)'),
            ({'sesso': 'F'}, 'Il sesso (F) non corrisponde a quello del codice fiscale (M)'),
            ({'luogo': 'H892'}, 'Il luogo di nascita (San Giorgio a Cremano (NA)) non corrisponde a quello del codice fiscale (Napoli (NA))')]
    for dati, atteso in casi:
        avvisi_ = CF.confronta(FINTINI, **dati)
        assert len(avvisi_) == 1 and atteso in avvisi_[0], (dati, avvisi_)
    # stesso giorno di un altro secolo: va bene (nel codice il secolo non c'e')
    assert CF.confronta(FINTINI, data_nascita=date(1880, 1, 1)) == []
    assert CF.confronta('FNTPRV80A01F839X', 'Rossi') == [], 'avvisi su un codice non valido'


prova('avvisi quando il codice non corrisponde a cognome, nome, data, sesso, luogo', k_confronta)


# =================================================================== luoghi
area('luoghi di nascita')


def l_dati():
    with open(os.path.join(CARTELLA, 'dati', 'luoghi_nascita.json'), encoding='utf-8') as f:
        d = json.load(f)
    assert 'MIT' in d['fonte'] and 'ISTAT' in d['fonte'], d['fonte']
    t = CF.tabella()
    comuni = [x for x in t if x.esiste and not x.estero]
    stati = {x.codice for x in t if x.estero}
    assert 7800 <= len(comuni) <= 8100, len(comuni)
    assert len(stati) >= 200, len(stati)
    attivi = {}
    for x in t:
        if x.esiste:
            assert x.codice not in attivi, 'due luoghi esistenti con il codice %s' % x.codice
            attivi[x.codice] = x
        assert re.fullmatch(r'[A-Z][0-9]{3}', x.codice), x.codice
        assert x.estero == x.codice.startswith('Z'), (x.codice, x.provincia)
    assert attivi['F839'].testo == 'Napoli (NA)' and attivi['Z112'].testo == 'Germania (estero)'
    assert CF.luogo('Z118').al is not None and CF.luogo('Z118').nome == 'Jugoslavia'
    # i periodi di uno stesso codice non si sovrappongono: un codice, un luogo per volta. Nei dati
    # ufficiali c'e' una sola eccezione, D588, usato fino al 1928 sia per Filago sia per Marne
    per_codice = {}
    for x in t:
        per_codice.setdefault(x.codice, []).append(x)
    sovrapposti = set()
    for codice, righe in per_codice.items():
        righe = sorted(righe, key=lambda x: x.dal or date.min)
        for a, b in zip(righe, righe[1:]):
            if a.al is None or (b.dal is not None and b.dal <= a.al):
                sovrapposti.add(codice)
    assert sovrapposti <= {'D588'}, sovrapposti
    nomi = {x.nome for x in t}
    for n in ('San Giorgio a Cremano', "Cassano d'Adda", "Sant'Agata de' Goti", 'Sotto il Monte Giovanni XXIII',
              "L'Aquila", 'Ne', "Stati Uniti d'America"):
        assert n in nomi, n
    return '%d comuni esistenti, %d stati, %d righe' % (len(comuni), len(stati), len(t))


def l_cerca():
    def primi(q, giorno=None, n=3):
        return [x['testo'] for x in CF.cerca_luoghi(q, giorno)[:n]]
    assert primi('napoli')[0] == 'Napoli (NA)'
    assert primi('nap')[0] == 'Napoli (NA)' and 'Arena Po (PV)' not in primi('nap', n=12), 'pezzi in mezzo alle parole'
    assert primi('s giorgio cremano') == ['San Giorgio a Cremano (NA)']
    assert primi("sant'anastasia")[0] == "Sant'Anastasia (NA)" and primi('santanastasia')[0] == "Sant'Anastasia (NA)"
    assert set(primi('castro', n=2)) == {'Castro (BG)', 'Castro (LE)'}
    assert primi('castro le') == ['Castro (LE)'] and primi('Castro (LE)') == ['Castro (LE)']
    assert primi('montecorvino pu')[0] == 'Montecorvino Pugliano (SA)', 'sigla presa per una provincia'
    assert primi('bozen')[0] == 'Bolzano (BZ)'
    assert primi('germania') == ['Germania (estero)']
    assert primi('abano', date(1920, 1, 1))[0] == 'Abano (PD)' and primi('abano')[0] == 'Abano Terme (PD)'
    storico = [x for x in CF.cerca_luoghi('jugoslavia') if x['codice'] == 'Z118'][0]
    assert storico['periodo'] == 'fino al 2003', storico
    assert CF.cerca_luoghi('n') == [] or CF.cerca_luoghi('') == []
    assert len(CF.cerca_luoghi('san')) == 12


def l_risolvi():
    assert CF.risolvi_luogo('Napoli') == ('F839', '')
    assert CF.risolvi_luogo('  napoli (na) ') == ('F839', '')
    codice, errore = CF.risolvi_luogo('Castro')
    assert not codice and 'più luoghi chiamati «Castro»' in errore, errore
    assert CF.risolvi_luogo('Castro (LE)')[0] == 'M261' and CF.risolvi_luogo('castro bg')[0] == 'C337'
    assert CF.risolvi_luogo('Germania (estero)')[0] == 'Z112' and CF.risolvi_luogo('germany')[0] == 'Z112'
    assert CF.risolvi_luogo('Bozen')[0] == 'A952'
    codice, errore = CF.risolvi_luogo('Atlantide')
    assert not codice and 'non si trova' in errore
    assert CF.risolvi_luogo('') == ('', '')
    assert CF.testo_luogo('A952', date(1925, 6, 1)) == 'Bolzano (TN)' and CF.testo_luogo('A952') == 'Bolzano (BZ)'
    assert CF.testo_luogo('Q999') == '' and not CF.codice_conosciuto('Q999')


def l_periodo():
    assert 'esiste dal 28/05/1975' in CF.avviso_periodo('M261', date(1960, 1, 1))
    assert CF.avviso_periodo('M261', date(1980, 1, 1)) == ''
    assert 'non esisteva più' in CF.avviso_periodo('Z118', date(2010, 1, 1))
    assert CF.avviso_periodo('Q999', date(2010, 1, 1)) == '' and CF.avviso_periodo('F839', None) == ''
    e = CF.esamina('', 'Fintini', 'Prova', date(1960, 1, 1), 'M', 'M261')
    assert e['stato'] == 'calcolato' and 'esiste dal' in ' '.join(e['avvisi']), e


prova('il file dei luoghi: fonte, comuni, stati, periodi, nomi ufficiali', l_dati)
prova('suggerimenti: inizi di parola, province, stati, nomi bilingui, comuni soppressi', l_cerca)
prova('luogo scritto a mano: unico, con la provincia, ambiguo, sconosciuto, nome di allora', l_risolvi)
prova('comune nato dopo la nascita o soppresso prima: avviso', l_periodo)


# ======================================================= scheda del paziente
area('scheda del paziente')


def s_dal_codice():
    S, C = mondo()
    r = scheda(C, codice_fiscale=' fntprv 80a01 f839w ')
    assert r.status_code == 302, testo(r)[:500]
    cat = avvisi(C)
    assert cat and cat[0][0] == 'ok', cat
    p = paziente(S, cognome='Fintini')
    assert (p.codice_fiscale, p.sesso, p.luogo_nascita, p.data_nascita) == (FINTINI, 'M', NAPOLI, date(1980, 1, 1)), \
        (p.codice_fiscale, p.sesso, p.luogo_nascita, p.data_nascita)
    t = html(C.get('/pazienti/%d' % p.id))
    assert 'value="Napoli (NA)"' in t and 'value="F839"' in t and '<option value="M" selected>' in t, 'scheda riaperta'


def s_calcolato():
    S, C = mondo()
    r = scheda(C, cognome='Esempietti', nome='Maria Rosa', sesso='F', data_nascita='1975-03-12',
               luogo_nascita_testo='San Giorgio a Cremano')
    assert r.status_code == 302, testo(r)[:400]
    messaggio = testo_avvisi(C)
    p = paziente(S, cognome='Esempietti')
    atteso = CF.calcola('Esempietti', 'Maria Rosa', date(1975, 3, 12), 'F', 'H892')
    assert p.codice_fiscale == atteso and p.luogo_nascita == 'H892', (p.codice_fiscale, p.luogo_nascita)
    assert 'Codice fiscale calcolato dai dati: %s' % atteso in messaggio and 'tessera sanitaria' in messaggio, messaggio
    # mancano dati: nessun codice, nessun errore
    r = scheda(C, cognome='Fittizi', nome='Ada', sesso='F', data_nascita='1975-03-12', telefono='3330000777')
    assert r.status_code == 302 and paziente(S, cognome='Fittizi').codice_fiscale == ''


def s_non_valido():
    S, C = mondo()
    r = scheda(C, codice_fiscale='FNTPRV80A01F839X', indirizzo='Via di Prova 9')
    assert r.status_code == 200, r.status_code
    messaggio = testo(r)                       # con un errore il modulo torna con il messaggio dentro
    assert 'Codice fiscale: non valido. Il carattere di controllo' in messaggio and '«W»' in messaggio, messaggio
    assert paziente(S, cognome='Fintini') is None, 'salvato con il codice sbagliato'
    t = html(r)
    assert 'value="FNTPRV80A01F839X"' in t and 'value="Via di Prova 9"' in t, 'il modulo ha perso i dati scritti'


def s_luogo():
    S, C = mondo()
    for scritto, atteso, errore in (('Napoli', NAPOLI, ''), ('castro (le)', 'M261', ''), ('Castro', None, 'più luoghi'),
                                    ('Atlantide', None, 'non si trova')):
        r = scheda(C, cognome='Fittizi', nome=scritto, luogo_nascita_testo=scritto, doppione_confermato='1')
        if atteso:
            assert r.status_code == 302 and paziente(S, nome=scritto).luogo_nascita == atteso, (scritto, testo_avvisi(C))
            avvisi(C)
        else:
            assert r.status_code == 200 and errore in testo(r), scritto
    # il codice scelto dall'elenco vale piu' del testo
    scheda(C, cognome='Fittizi', nome='Codice', luogo_nascita='H892', luogo_nascita_testo='Roma (RM)', doppione_confermato='1')
    assert paziente(S, nome='Codice').luogo_nascita == 'H892'
    r = scheda(C, cognome='Fittizi', nome='Rotto', luogo_nascita='<x>', doppione_confermato='1')
    assert r.status_code == 200 and 'Luogo di nascita: non valido' in testo(r)
    r = scheda(C, cognome='Fittizi', nome='Sesso', sesso='X', doppione_confermato='1')
    assert r.status_code == 200 and 'Sesso: scelta non valida' in testo(r)


def s_avvisi():
    S, C = mondo()
    scheda(C, nome='Pietro', codice_fiscale=FINTINI, data_nascita='1980-01-02')
    cat = avvisi(C)
    assert cat[0][0] == 'avviso', cat
    assert 'Le lettere del nome non tornano' in cat[0][1] and 'La data di nascita (02/01/1980)' in cat[0][1], cat
    p = paziente(S, cognome='Fintini')
    assert p.data_nascita == date(1980, 1, 2), 'la data scritta deve restare'


def s_doppione():
    S, C = mondo()
    nuovo_paziente(S, cognome='Fintini', nome='Prova', telefono='3399999999', codice_fiscale=FINTINI)
    r = scheda(C, cognome='Fintoni', nome='Prova', telefono='3381111111', codice_fiscale=FINTINI)
    assert r.status_code == 200 and 'Potrebbe essere già in anagrafica' in testo(r), 'stesso codice fiscale non segnalato'
    r = scheda(C, cognome='Fintoni', nome='Prova', telefono='3381111111', codice_fiscale=FINTINI, doppione_confermato='1')
    assert r.status_code == 302


def s_segno_calcolato():
    S, C = mondo()
    calcolato = CF.calcola('Esempietti', 'Maria Rosa', date(1975, 3, 12), 'F', 'H892')
    dati = dict(cognome='Esempietti', nome='Maria Rosa', sesso='F', data_nascita='1975-03-12', luogo_nascita='H892')
    scheda(C, codice_fiscale=calcolato, cf_calcolato='1', **dati)
    assert 'calcolato dai dati' in testo_avvisi(C)
    # il segno c'e' ma il codice e' stato cambiato (omocodico, scritto dalla tessera): vale come scritto
    primi = calcolato[:14] + 'V'
    omocodico = primi + CF.carattere_controllo(primi)
    scheda(C, codice_fiscale=omocodico, cf_calcolato='1', doppione_confermato='1', telefono='3330000999', **dati)
    m = testo_avvisi(C)
    assert 'calcolato' not in m and paziente(S, codice_fiscale=omocodico) is not None, m


prova('dal codice valido: sesso, luogo e data di nascita; la scheda li mostra', s_dal_codice)
prova('codice vuoto e tutti i dati: calcolato e salvato, con l\'invito a controllarlo', s_calcolato)
prova('codice non valido: non si salva, il motivo, il modulo tiene i dati', s_non_valido)
prova('luogo scritto a mano o scelto dall\'elenco; luogo e sesso non validi', s_luogo)
prova('codice che non corrisponde ai dati: si salva, con gli avvisi', s_avvisi)
prova('stesso codice fiscale di un altro paziente: possibile doppione', s_doppione)
prova('codice calcolato nel modulo: detto calcolato solo se non e\' stato cambiato', s_segno_calcolato)


# ============================================================ prenotazione
area('prenotazione')


def p_nuovo():
    S, C = mondo()
    r = prenota(C, S, codice_fiscale=FINTINI)
    assert r.status_code == 302, testo(r)[:500]
    avvisi(C)
    p = paziente(S, cognome='Fintini')
    assert (p.sesso, p.luogo_nascita, p.data_nascita) == ('M', NAPOLI, date(1980, 1, 1))
    r = prenota(C, S, ora='11:00', paziente='Esempietti', nome_paziente='Maria Rosa', telefono='333 000 0102',
                sesso='F', data_nascita='1975-03-12', luogo_nascita_testo='san giorgio a cremano')
    assert r.status_code == 302, testo(r)[:500]
    m = testo_avvisi(C)
    atteso = CF.calcola('Esempietti', 'Maria Rosa', date(1975, 3, 12), 'F', 'H892')
    assert paziente(S, cognome='Esempietti').codice_fiscale == atteso and 'calcolato dai dati: %s' % atteso in m, m
    r = prenota(C, S, ora='12:00', paziente='Fittizi', telefono='333 000 0103', codice_fiscale='FTTDAA80A01F839A')
    assert r.status_code == 200 and 'Codice fiscale: non valido' in testo(r), testo(r)[:300]
    assert paziente(S, cognome='Fittizi') is None


def p_non_sostituisce():
    """Il paziente scelto ha gia' un codice (qui omocodico, dalla tessera):
    il codice calcolato dai dati nel modulo non lo sostituisce."""
    S, C = mondo()
    primi = FINTINI[:14] + 'V'
    vero = primi + CF.carattere_controllo(primi)
    pid = nuovo_paziente(S, cognome='Fintini', nome='Prova', telefono='3330000101', codice_fiscale=vero)
    r = prenota(C, S, paziente_id=str(pid), sesso='M', data_nascita='1980-01-01', luogo_nascita='F839',
                codice_fiscale=FINTINI, cf_calcolato='1')
    assert r.status_code == 302, testo(r)[:300]
    assert paziente(S, id=pid).codice_fiscale == vero, 'codice della tessera sostituito da quello calcolato'
    # e un codice calcolato non fa riconoscere un altro paziente
    nuovo_paziente(S, cognome='Esempietti', nome='Ada', telefono='3390000001',
                   codice_fiscale=CF.calcola('Esempietti', 'Ada', date(1970, 1, 1), 'F', NAPOLI))
    prenota(C, S, ora='11:00', paziente='Esempietti', nome_paziente='Ada', telefono='3390000002', sesso='F',
            data_nascita='1970-01-01', luogo_nascita='F839')
    s = S()
    n = len(s.scalars(select(Paziente).where(Paziente.cognome == 'Esempietti')).all())
    s.close()
    assert n == 2, 'riconosciuto dal codice calcolato: %d schede' % n


def p_ricerca():
    S, C = mondo()
    nuovo_paziente(S, cognome='Fintini', nome='Prova', telefono='3330000101', codice_fiscale=FINTINI, sesso='M',
                   luogo_nascita=NAPOLI, data_nascita=date(1980, 1, 1))
    d = json.loads(html(C.get('/pazienti/cerca?q=fintini')))
    assert d[0]['sesso'] == 'M' and d[0]['luogo'] == NAPOLI and d[0]['luogo_testo'] == 'Napoli (NA)', d


prova('paziente nuovo: dal codice, calcolato dai dati, codice non valido', p_nuovo)
prova('il codice della scheda non viene sostituito da quello calcolato', p_non_sostituisce)
prova('ricerca del modulo: anche sesso e luogo di nascita', p_ricerca)


# ======================================================= pazienti in archivio
area('pazienti gia\' in archivio')


def a_migrazione():
    percorso = percorso_nuovo('v7')
    S0 = crea_sessione('sqlite:///' + percorso)
    s = S0()
    servizi.prepara_primo_avvio(s)
    s.add_all([Paziente(cognome='Fintini', nome='Prova', codice_fiscale=' fntprv 80a01f839w'),
               Paziente(cognome='Esempietti', nome='Maria Rosa', data_nascita=date(1975, 3, 13),
                        codice_fiscale=CF.calcola('Esempietti', 'Maria Rosa', date(1975, 3, 12), 'F', 'H892')),
               Paziente(cognome='Provolo', nome='Ugo', codice_fiscale='PRVGUO69L04F839Z'),
               Paziente(cognome='Fittizi', nome='Ada')])
    s.commit()
    s.close()
    S0.motore.dispose()
    c = sqlite3.connect(percorso)
    c.execute('ALTER TABLE pazienti DROP COLUMN sesso')
    c.execute('ALTER TABLE pazienti DROP COLUMN luogo_nascita')
    c.execute("UPDATE impostazioni SET valore = '7' WHERE chiave = 'versione_schema'")
    c.commit()
    c.close()
    S = crea_sessione('sqlite:///' + percorso)
    assert S.versione_precedente == 7 and {'pazienti.sesso', 'pazienti.luogo_nascita'} <= set(S.colonne_aggiunte)
    note = ' | '.join(S.migrazioni)
    assert 'prima-della-versione-%d' % VERSIONE_SCHEMA in note and '2 pazienti completati' in note and \
        '1 riscritti' in note, note
    assert os.listdir(os.path.join(os.path.dirname(percorso), 'backup')), 'copia di sicurezza mancante'
    s = S()
    p = {x.cognome: x for x in s.scalars(select(Paziente))}
    assert (p['Fintini'].codice_fiscale, p['Fintini'].sesso, p['Fintini'].luogo_nascita, p['Fintini'].data_nascita) == (
        FINTINI, 'M', NAPOLI, date(1980, 1, 1))
    assert p['Esempietti'].data_nascita == date(1975, 3, 13), 'data scritta toccata'
    assert (p['Esempietti'].sesso, p['Esempietti'].luogo_nascita) == ('F', 'H892')
    assert (p['Provolo'].codice_fiscale, p['Provolo'].sesso, p['Provolo'].luogo_nascita) == ('PRVGUO69L04F839Z', '', ''), \
        'codice non valido toccato'
    assert (p['Fittizi'].sesso, p['Fittizi'].luogo_nascita) == ('', '')
    s.close()
    S2 = crea_sessione('sqlite:///' + percorso)
    assert S2.versione_precedente == VERSIONE_SCHEMA >= 8 and not S2.migrazioni


def popola_archivio(S):
    domani = datetime.combine(OGGI + timedelta(days=1), time(10, 0))
    s = S()
    stanza = s.scalars(select(Risorsa)).first()
    medico = s.scalars(select(Operatore)).first()
    prest = s.scalars(select(Prestazione)).first()
    lia = CF.calcola('Testabianca', 'Lia', date(1990, 11, 23), 'F', 'G964')
    persone = [Paziente(cognome='Fintini', nome='Prova', codice_fiscale=FINTINI, sesso='M', luogo_nascita=NAPOLI,
                        data_nascita=date(1980, 1, 1)),
               Paziente(cognome='Sbagliati', nome='Ada', codice_fiscale='SBGDAA80A41F839Z'),
               Paziente(cognome='Provolo', nome='Hugo', codice_fiscale=CF.calcola('Provolo', 'Ugo', date(1969, 7, 4), 'M', NAPOLI)),
               Paziente(cognome='Testabianca', nome='Lia', telefono='3330000104', codice_fiscale=lia),
               Paziente(cognome='Testabianca', nome='Lia', telefono='3330000105', codice_fiscale=lia),
               Paziente(cognome='Esempietti', nome='Maria Rosa', sesso='F', data_nascita=date(1975, 3, 12), luogo_nascita='H892'),
               Paziente(cognome='Zeta', nome='Senza'),
               Paziente(cognome='Alfa', nome='Con Appuntamento')]
    s.add_all(persone)
    s.flush()
    s.add(Appuntamento(risorsa_id=stanza.id, operatore_id=medico.id, prestazione_id=prest.id, paziente_id=persone[-1].id,
                       inizio=domani, fine=domani + timedelta(minutes=30), stato='PRENOTATO'))
    s.commit()
    s.close()


def a_pagina():
    S, C = mondo()
    popola_archivio(S)
    s = S()
    r = pazienti.esamina_archivio(s)
    s.close()
    assert [p.cognome for p, _ in r['non_validi']] == ['Sbagliati'] and 'carattere di controllo' in r['non_validi'][0][1]
    assert [p.cognome for p, _ in r['non_coerenti']] == ['Provolo'] and 'nome' in r['non_coerenti'][0][1][0]
    assert len(r['doppi']) == 1 and [p.telefono for p in r['doppi'][0]] == ['3330000104', '3330000105']
    assert [p.cognome for p, _ in r['calcolabili']] == ['Esempietti']
    assert [p.cognome for p, _ in r['senza']][0] == 'Alfa', 'prima chi ha un appuntamento'
    assert r['senza_totale'] == 2 and r['da_vedere'] == 4 and r['validi'] == 4, r
    t = testo(C.get('/pazienti/codici-fiscali'))
    for frammento in ('4 da vedere', 'Non validi (1)', 'Sbagliati Ada', 'Non corrispondono ai dati della scheda (1)',
                      'Le lettere del nome non tornano', 'Lo stesso codice su più schede (1)', 'Da calcolare (1)',
                      'Calcola e salva il codice', 'Senza codice fiscale (2)'):
        assert frammento in t, frammento
    assert 'href="/pazienti/codici-fiscali"' in html(C.get('/pazienti')), 'collegamento dalla pagina Pazienti'


def a_calcola_tutti():
    S, C = mondo()
    popola_archivio(S)
    cartella_backup = os.path.join(PROVVISORIA, 'backup_cf_%d' % _n[0])
    s = S()
    scrivi_impostazione(s, 'backup_cartella', cartella_backup)
    s.commit()
    s.close()
    r = C.post('/pazienti/codici-fiscali', data={'azione': 'calcola'})
    assert r.status_code == 302
    m = testo_avvisi(C)
    assert 'Calcolato 1 codice fiscale dai dati' in m and 'prima-dei-codici-fiscali' in m, m
    assert [f for f in os.listdir(cartella_backup) if f.endswith('-prima-dei-codici-fiscali.db')], 'copia mancante'
    atteso = CF.calcola('Esempietti', 'Maria Rosa', date(1975, 3, 12), 'F', 'H892')
    assert paziente(S, cognome='Esempietti').codice_fiscale == atteso
    C.post('/pazienti/codici-fiscali', data={'azione': 'calcola'})
    assert 'nessun codice fiscale da calcolare' in testo_avvisi(C)


def a_da_fuori():
    S, C = mondo()
    popola_archivio(S)
    r = C.post('/pazienti/codici-fiscali', data={'azione': 'calcola'}, headers={'Origin': 'http://sito-cattivo.example.com'})
    assert r.status_code == 403 and paziente(S, cognome='Esempietti').codice_fiscale == ''


prova('aggiornamento dello schema: dai codici validi sesso, luogo e data; il resto non si tocca', a_migrazione)
prova('pagina di controllo: non validi, non coerenti, doppi, da calcolare, senza codice', a_pagina)
prova('«Calcola e salva»: copia di sicurezza, codici scritti, una volta sola', a_calcola_tutti)
prova('una pagina di un altro sito non puo\' calcolare i codici', a_da_fuori)


# ============================================================ altri punti
area('importazione, unione, moduli, pagine')


def x_importa():
    S, C = mondo()
    s = S()
    indice = importa.IndicePazienti(s)
    dati = dict(cognome='Fintini', nome='Prova', telefono='3330000101', telefono2='', email='', codice_fiscale=FINTINI,
                data_nascita=None, indirizzo='')
    p, come = importa.crea_o_completa_paziente(s, indice, dati)
    assert come == 'nuovo' and (p.sesso, p.luogo_nascita, p.data_nascita) == ('M', NAPOLI, date(1980, 1, 1))
    q = Paziente(cognome='Esempietti', nome='Maria Rosa', telefono='3330000102')
    s.add(q)
    s.flush()
    indice = importa.IndicePazienti(s)
    calcolato = CF.calcola('Esempietti', 'Maria Rosa', date(1975, 3, 12), 'F', 'H892')
    p2, come = importa.crea_o_completa_paziente(s, indice, dict(dati, cognome='Esempietti', nome='Maria Rosa',
                                                                telefono='3330000102', codice_fiscale=calcolato))
    assert p2.id == q.id and come == 'aggiornato' and (q.sesso, q.luogo_nascita) == ('F', 'H892'), (come, q.sesso)
    s.rollback()
    s.close()


def x_unisci():
    S, C = mondo()
    s = S()
    a = Paziente(cognome='Fintini', nome='Prova', telefono='3330000101')
    b = Paziente(cognome='Fintini', nome='Prova', codice_fiscale=FINTINI)
    s.add_all([a, b])
    s.flush()
    pazienti.unisci(s, a, b)
    assert (a.codice_fiscale, a.sesso, a.luogo_nascita, a.data_nascita) == (FINTINI, 'M', NAPOLI, date(1980, 1, 1))
    s.rollback()
    s.close()


def x_segnaposto():
    assert {'luogo_nascita', 'sesso'} <= set(documenti.SEGNAPOSTO_MODULI)
    S, C = mondo()
    s = S()
    stanza = s.scalars(select(Risorsa)).first()
    p = Paziente(cognome='Fintini', nome='Prova', sesso='M', luogo_nascita=NAPOLI, data_nascita=date(1980, 1, 1))
    inizio = datetime.combine(OGGI + timedelta(days=3), time(9, 0))
    a = Appuntamento(risorsa=stanza, operatore=s.scalars(select(Operatore)).first(),
                     prestazione=s.scalars(select(Prestazione)).first(), paziente=p, inizio=inizio,
                     fine=inizio + timedelta(minutes=30))
    t = documenti.compila('{paziente}, nato a {luogo_nascita} il {data_nascita}, sesso {sesso}', a)
    assert t == 'Fintini Prova, nato a Napoli (NA) il 01/01/1980, sesso M', t
    s.rollback()
    s.close()


def x_risposte_json():
    S, C = mondo()
    r = C.get('/pazienti/codice-fiscale?cf=%s&cognome=Fintini&nome=Prova' % FINTINI.lower())
    d = json.loads(html(r))
    assert r.headers['Cache-Control'] == 'no-store'
    assert d['stato'] == 'valido' and d['da_cf'] == {'data_nascita': '1980-01-01', 'sesso': 'M', 'luogo': NAPOLI,
                                                      'luogo_testo': 'Napoli (NA)'} and d['avvisi'] == [], d
    d = json.loads(html(C.get('/pazienti/codice-fiscale?cf=FNTPRV80A01F839X')))
    assert d['stato'] == 'non_valido' and '«W»' in d['messaggio'], d
    d = json.loads(html(C.get('/pazienti/codice-fiscale?cognome=Fintini&nome=Prova&sesso=M&data_nascita=1980-01-01'
                              '&luogo_testo=napoli')))
    assert d['stato'] == 'calcolato' and d['calcolato'] == FINTINI and d['luogo'] == NAPOLI, d
    d = json.loads(html(C.get('/pazienti/codice-fiscale?cognome=Fintini&nome=Prova&sesso=M')))
    assert d['stato'] == 'incompleto' and d['mancano'] == ['data di nascita', 'luogo di nascita'], d
    assert 'Si calcola da solo quando ci sono anche: data di nascita, luogo di nascita.' == d['messaggio'], d['messaggio']
    d = json.loads(html(C.get('/pazienti/codice-fiscale')))
    assert d['stato'] == 'incompleto' and d['messaggio'].startswith('Dal codice fiscale si riempiono'), d
    d = json.loads(html(C.get('/pazienti/codice-fiscale?cf=' + 'A' * 5000 + '&cognome=' + 'B' * 5000)))
    assert d['stato'] == 'non_valido'
    d = json.loads(html(C.get('/pazienti/luoghi?q=pozzuoli')))
    assert d[0]['codice'] == 'G964' and d[0]['testo'] == 'Pozzuoli (NA)', d
    assert json.loads(html(C.get('/pazienti/luoghi?q=p'))) == []
    assert '<' not in html(C.get('/pazienti/luoghi?q=%3Cscript%3E'))


def x_pagine():
    S, C = mondo()
    for u in ('/pazienti/nuovo', '/appuntamento'):
        t = html(C.get(u))
        for frammento in ('id="sesso"', 'id="luogo_nascita_testo"', 'id="luogo_nascita"', 'id="esito-cf"',
                          'data-controllo="/pazienti/codice-fiscale"', 'data-indirizzo="/pazienti/luoghi"',
                          'data-guida="codice-fiscale"', 'data-guida="luogo-nascita"'):
            assert frammento in t, (u, frammento)
    pid = nuovo_paziente(S, cognome='Fintini', nome='Prova', telefono='3330000101', codice_fiscale=FINTINI, sesso='M',
                         luogo_nascita=NAPOLI, data_nascita=date(1980, 1, 1))
    t = html(C.get('/appuntamento?paziente_id=%d' % pid))
    assert 'value="Napoli (NA)"' in t and '<option value="M" selected>' in t, 'prenotazione per un paziente scelto'


def x_versione():
    # la 1.7 o una piu' nuova: il numero, le sue novita' in cima e quelle della 1.7, ognuna con la sua guida
    assert novita.confronta(comune.VERSIONE, '1.7') >= 0 and novita.NOVITA[0][0] == comune.VERSIONE
    for v in novita.NOVITA[0][1] + dict(novita.NOVITA)['1.7']:
        assert v['guida'] in guida.PER_SLUG, v
    for nome in ('codice-fiscale', 'controllo-codici-fiscali'):
        assert nome in guida.PER_SLUG, nome
    iss = open(os.path.join(CARTELLA, 'installer.iss'), encoding='utf-8-sig').read()
    assert '#define Versione "%s"' % comune.VERSIONE in iss
    spec = open(os.path.join(CARTELLA, 'gestionale.spec'), encoding='utf-8').read()
    assert "('dati', 'dati')" in spec, 'i luoghi non finiscono nell\'eseguibile'
    assert VERSIONE_SCHEMA >= 8


def x_generatore():
    sys.path.insert(0, os.path.join(CARTELLA, 'strumenti'))
    try:
        import genera_luoghi_nascita as G
    except ImportError as e:
        return 'saltata: %s' % e
    for grezzo, atteso in (('San Giorgio A Cremano', 'San Giorgio a Cremano'), ("Cassano D'Adda", "Cassano d'Adda"),
                           ("Sant'Agata De' Goti", "Sant'Agata de' Goti"), ('Sotto Il Monte Giovanni Xxiii',
                                                                             'Sotto il Monte Giovanni XXIII'),
                           ("L'Aquila", "L'Aquila"), ('Ne', 'Ne'), ('Alcara Li Fusi', 'Alcara li Fusi')):
        assert G.nome_ufficiale(grezzo) == atteso, (grezzo, G.nome_ufficiale(grezzo))
    righe = [{'dal': '1900-01-01', 'al': '1920-12-31'}, {'dal': '1921-01-01', 'al': '1950-06-30'},
             {'dal': '1960-01-01', 'al': ''}]
    assert G.unisci_periodi(righe) == [{'dal': '1900-01-01', 'al': '1950-06-30'}, {'dal': '1960-01-01', 'al': ''}]


prova('importazione: sesso, luogo e data dal codice fiscale, anche per chi c\'era gia\'', x_importa)
prova('unione di due schede: completa sesso e luogo dal codice', x_unisci)
prova('moduli ed email: {luogo_nascita} e {sesso}', x_segnaposto)
prova('controllo mentre si scrive e suggerimenti dei luoghi: risposte, limiti, protezione', x_risposte_json)
prova('scheda e prenotazione hanno i campi nuovi', x_pagine)
prova('versione 1.7, novità con le loro guide, luoghi dentro l\'eseguibile, schema 8', x_versione)
prova('generatore dei luoghi: nomi ufficiali, periodi uniti', x_generatore)


# =====================================================================
if __name__ == '__main__':
    aree = []
    for e in esiti:
        if e[1] not in aree:
            aree.append(e[1])
    for a in aree:
        mie = [e for e in esiti if e[1] == a]
        rotte = [e for e in mie if e[0] != 'OK']
        print('%-48s %2d prove  %s' % (a, len(mie), 'tutte a posto' if not rotte else '%d DA SISTEMARE' % len(rotte)))
    saltate = [e for e in esiti if e[0] == 'OK' and str(e[3]).startswith('saltata')]
    rotte = [e for e in esiti if e[0] != 'OK']
    if rotte or saltate or os.environ.get('DETTAGLIO'):
        print('\nDettaglio:')
        for e in esiti:
            if e[0] != 'OK' or str(e[3]).startswith('saltata') or os.environ.get('DETTAGLIO'):
                print('  %-6s [%s] %s\n         %s' % (e[0], e[1], e[2], e[3]))
    print('\n%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(rotte), len(rotte)))
    shutil.rmtree(PROVVISORIA, ignore_errors=True)
    sys.exit(1 if rotte else 0)
