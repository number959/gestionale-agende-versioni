# -*- coding: utf-8 -*-
"""I dati di prova di strumenti/dati_prova.py (quelli di demo.py e del pacchetto di prova) non cambiano
senza volerlo (tappa 1 della base, 22/11/2026).

In quattro momenti fermi (un martedi, una domenica sera, l'ultimo dell'anno alle 23:59 e il 29 febbraio 2028)
fai_dati gira in un processo a parte con l'orologio fermo dall'inizio (anche nei valori che il programma mette
da se', default=datetime.now), e ogni tabella del database diventa testo: schema e righe in ordine di rowid
(quindi anche gli id), date come distanza da oggi («G-6»), BLOB come impronta, il logo come misura (lo riscrive
Pillow: i byte cambiano fra Linux e Windows), la password protetta come «password-protetta» (con DPAPI di
Windows cambia a ogni volta). Numero di righe e impronta di ogni tabella si confrontano con
dati_prova_atteso.txt (uguale nelle due cartelle). In piu': fai_dati non importa app.py; nomi_inventati (il
pacchetto di prova) non lascia nessun nome della clinica, cambia logo e informative e non toglie righe; e il
gemello: senza nomi_inventati i nomi della clinica ci sono (il controllo li sa trovare).

    python prove_dati_prova.py              # confronta
    python prove_dati_prova.py --scrivi     # riscrive dati_prova_atteso.txt (cambio voluto: stesso commit)
"""
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import date, datetime

from prove_dove import dove

CARTELLA = os.path.dirname(os.path.abspath(__file__))
ATTESO = os.path.join(CARTELLA, 'dati_prova_atteso.txt')
MOMENTI = ['2026-11-24T09:30:00', '2026-11-29T18:00:00', '2026-12-31T23:59:00', '2028-02-29T07:00:00']
PROVVISORIA = tempfile.mkdtemp(prefix='prove-dati-prova-')

# il figlio: ferma l'orologio PRIMA di importare il programma (cosi' anche i default delle colonne), poi
# fai_dati, i nomi della clinica trovati e, se chiesto, nomi_inventati
FIGLIO = r'''
import datetime as DT, json, os, sys
q = DT.datetime.fromisoformat(sys.argv[1])
vd, vm = DT.date, DT.datetime
class MD(type):
    def __instancecheck__(c, o): return isinstance(o, vd)
    def __subclasscheck__(c, s): return issubclass(s, vd)
class MM(type):
    def __instancecheck__(c, o): return isinstance(o, vm)
    def __subclasscheck__(c, s): return issubclass(s, vm)
class Data(vd, metaclass=MD):
    @classmethod
    def today(c): return c(q.year, q.month, q.day)
class Momento(vm, metaclass=MM):
    @classmethod
    def now(c, tz=None): return c(q.year, q.month, q.day, q.hour, q.minute, q.second)
    @classmethod
    def today(c): return c.now()
DT.date, DT.datetime = Data, Momento
sys.path.insert(0, sys.argv[3]); os.chdir(sys.argv[3])
from strumenti import dati_prova
S = dati_prova.fai_dati(sys.argv[2])
uscita = {'app': 'app' in sys.modules, 'prima': dati_prova.nomi_della_clinica(S)}
if len(sys.argv) > 4:
    uscita['rimasti'] = dati_prova.nomi_inventati(S)
print(json.dumps(uscita))
'''

DATA = re.compile(r'(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)')
esiti = []


def prova(nome, f):
    try:
        esiti.append(('OK', nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', nome, '%s · %s' % (dove(e), str(e) or 'asserzione fallita')))
    except Exception as e:
        esiti.append(('ERRORE', nome, '%s · %r' % (dove(e), e)))


def testo_del_database(percorso, oggi):
    """{tabella: 'righe impronta'}."""
    def valore(v):
        if isinstance(v, bytes):
            if v.startswith(b'\x89PNG'):
                from io import BytesIO
                from PIL import Image
                return 'png:%dx%d' % Image.open(BytesIO(v)).size
            return 'blob:%d:%s' % (len(v), hashlib.sha256(v).hexdigest()[:16])
        if isinstance(v, str):
            if v.startswith(('dpapi:', 'chiaro:')):
                return 'password-protetta'
            return DATA.sub(lambda m: 'G%+d' % (date(*map(int, m.groups())) - oggi).days, v)
        return v
    c = sqlite3.connect(percorso)
    try:
        tabelle = {}
        for nome, sql in c.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE "
                                   "'sqlite_%' ORDER BY name"):
            righe = c.execute('SELECT * FROM "%s" ORDER BY rowid' % nome).fetchall()
            corpo = sql + '\n' + '\n'.join(repr(tuple(valore(v) for v in r)) for r in righe)
            tabelle[nome] = '%d %s' % (len(righe), hashlib.sha256(corpo.encode('utf-8')).hexdigest()[:20])
        return tabelle
    finally:
        c.close()


def lancia(momento, nomi=False):
    """Il figlio in partenza: (processo, percorso del database)."""
    d = tempfile.mkdtemp(prefix='m-', dir=PROVVISORIA)
    db = os.path.join(d, 'prova.db')
    p = subprocess.Popen([sys.executable, '-c', FIGLIO, momento, db, CARTELLA] + (['nomi'] if nomi else []),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
    return p, db


def raccogli(p, db, momento):
    uscita, errori = p.communicate(timeout=600)
    if p.returncode:
        raise AssertionError('fai_dati non riuscito alle %s:\n%s' % (momento, errori[-2000:]))
    info = json.loads(uscita.strip().splitlines()[-1])
    return db, info, testo_del_database(db, datetime.fromisoformat(momento).date())


# tutti i figli insieme (ognuno ha il suo database), poi le prove sui risultati
in_corso = [(m, False) + lancia(m) for m in MOMENTI] + [(MOMENTI[0], True) + lancia(MOMENTI[0], nomi=True)]
fatti = {}
for m, nomi, p, db in in_corso:
    try:
        fatti[(m, nomi)] = raccogli(p, db, m)
    except Exception as e:
        fatti[(m, nomi)] = e

if '--scrivi' in sys.argv and all(not isinstance(fatti[(m, False)], Exception) for m in MOMENTI):
    with open(ATTESO, 'w', encoding='utf-8', newline='\n') as f:
        f.write('# Dati di prova (strumenti/dati_prova.py) con l\'orologio fermo: momento, tabella, righe, impronta.\n'
                '# Lo scrive «python prove_dati_prova.py --scrivi»: un cambio qui e\' un cambio dei dati di prova.\n')
        for m in MOMENTI:
            for t, v in sorted(fatti[(m, False)][2].items()):
                f.write('%s\t%s\t%s\n' % (m, t, v))
    print('riscritto %s: guardare git diff prima del commit' % os.path.basename(ATTESO))
ATTESI = {}
with open(ATTESO, encoding='utf-8') as f:
    for riga in f:
        if riga.strip() and not riga.startswith('#'):
            m, t, v = riga.rstrip('\n').split('\t')
            ATTESI.setdefault(m, {})[t] = v


def risultato(m, nomi=False):
    r = fatti[(m, nomi)]
    if isinstance(r, Exception):
        raise r
    return r


def uguali_al_riferimento(m):
    def f():
        _, info, tabelle = risultato(m)
        assert not info['app'], 'fai_dati ha importato app.py: deve bastare da solo (lo collega chi chiama)'
        assert m in ATTESI, 'il momento %s manca in %s' % (m, os.path.basename(ATTESO))
        diverse = ['%s (atteso %s, adesso %s)' % (t, ATTESI[m].get(t), tabelle.get(t))
                   for t in sorted(set(ATTESI[m]) | set(tabelle)) if ATTESI[m].get(t) != tabelle.get(t)]
        assert not diverse, 'tabelle diverse dal riferimento: %s' % '; '.join(diverse)
        return '%d tabelle, %d righe' % (len(tabelle), sum(int(v.split()[0]) for v in tabelle.values()))
    return f


def g_ci_sono_i_dati():
    """Gemello: il riferimento non e' vuoto e l'orologio e' davvero fermo (i giorni contano)."""
    _, _, martedi = risultato(MOMENTI[0])
    _, _, domenica = risultato(MOMENTI[1])
    assert int(martedi['appuntamenti'].split()[0]) > 20 and int(martedi['turni_personale'].split()[0]) > 1000, \
        'troppo pochi dati: %s, %s' % (martedi['appuntamenti'], martedi['turni_personale'])
    assert martedi['appuntamenti'] != domenica['appuntamenti'], 'martedi e domenica danno gli stessi appuntamenti'


def p_nomi_inventati():
    db, info, tabelle = risultato(MOMENTI[0], nomi=True)
    assert info['rimasti'] == [], 'dopo nomi_inventati restano nomi della clinica: %s' % info['rimasti']
    _, _, prima = risultato(MOMENTI[0])
    assert {t: v.split()[0] for t, v in tabelle.items()} == {t: v.split()[0] for t, v in prima.items()}, \
        'nomi_inventati ha cambiato il numero di righe di qualche tabella'
    vero_db = risultato(MOMENTI[0])[0]
    c, v = sqlite3.connect(db), sqlite3.connect(vero_db)
    try:
        logo = c.execute('SELECT logo FROM strutture WHERE id = 1').fetchone()[0]
        logo_vero = v.execute('SELECT logo FROM strutture WHERE id = 1').fetchone()[0]
        assert logo and logo_vero and logo != logo_vero, 'il logo della prova e\' ancora quello della clinica'
        nome, colore = c.execute('SELECT nome, colore FROM strutture WHERE id = 1').fetchone()
        assert nome == 'Clinica Esempio', nome
        assert colore == v.execute('SELECT colore FROM strutture WHERE id = 1').fetchone()[0], 'il colore e\' cambiato'
        informative = c.execute("SELECT nome, dimensione FROM allegati_regole WHERE upper(nome) LIKE 'INFORMATIVA%'").fetchall()
        assert informative and all(dim < 1000 for _, dim in informative), \
            'informative ancora vere: %s' % informative
        medici = [r[0] for r in c.execute('SELECT cognome FROM operatori ORDER BY id')]
        assert 'Provetti' in medici and 'Saggiatori' in medici, medici
    finally:
        c.close()
        v.close()


def g_i_nomi_si_trovano():
    """Gemello: senza nomi_inventati il controllo trova la clinica e i due medici (non e' un controllo vuoto)."""
    _, info, _ = risultato(MOMENTI[0])
    trovati = ' '.join(info['prima'])
    for atteso in ('strutture.nome: posillipo', 'operatori.cognome: lippiello', 'operatori.cognome: galasso'):
        assert atteso in trovati, '%s non trovato fra i nomi della clinica: %s' % (atteso, info['prima'])


for m in MOMENTI:
    prova('i dati di prova delle %s sono uguali al riferimento' % m.replace('T', ' ')[:16], uguali_al_riferimento(m))
prova('gemello: nei dati ci sono appuntamenti e turni, e i giorni contano', g_ci_sono_i_dati)
prova('nomi_inventati: niente nomi della clinica, logo e informative inventati, stesse righe', p_nomi_inventati)
prova('gemello: senza nomi_inventati la clinica e i due medici si trovano', g_i_nomi_si_trovano)

shutil.rmtree(PROVVISORIA, ignore_errors=True)
for esito, nome, dettaglio in esiti:
    print('%-6s %s %s' % (esito, nome, dettaglio))
rotte = [e for e in esiti if e[0] != 'OK']
print('%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(rotte), len(rotte)))
sys.exit(1 if rotte else 0)
