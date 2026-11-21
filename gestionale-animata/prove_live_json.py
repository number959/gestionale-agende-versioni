# -*- coding: utf-8 -*-
"""I numeri del Modo schermo per i programmi, chiave per chiave (tappa 1 della base, 21/11/2026).

/riepilogo-live.json e /riepilogo-live/statistiche.json sono quello che leggono gli altri PC e chi un giorno
vorrà collegarci un altro programma: la veste nuova non li deve cambiare di una virgola. Su un mondo di prova
con nomi tutti inventati (anche medici e strutture) e l'orologio fermo (lunedì 7/12/2026 alle 7:30, 9:10, 10:20,
15:40, 16:10 e 21:00, e la domenica prima), i JSON di ogni struttura, e le statistiche di oggi, ieri, questa
settimana e la scorsa, questo mese e lo scorso e di un periodo scritto con le date, degli ambulatori e della sala
operatoria, devono essere uguali a riepilogo_live_atteso.json in ogni chiave
e a ogni livello. Se una differenza è voluta (un numero nuovo), il file si riscrive e va nello stesso commit:

    python prove_live_json.py              # confronta
    python prove_live_json.py --scrivi     # riscrive riepilogo_live_atteso.json (poi si guarda git diff)
"""
import datetime as DT
import json
import os
import shutil
import sys
import tempfile
from datetime import date, datetime, time, timedelta

from prove_dove import dove

CARTELLA = os.path.dirname(os.path.abspath(__file__))
ATTESO = os.path.join(CARTELLA, 'riepilogo_live_atteso.json')
PROVVISORIA = tempfile.mkdtemp(prefix='prove-live-json-')

import seed  # noqa: E402
import app as A  # noqa: E402
from modelli import Paziente, Appuntamento, Risorsa, Operatore, Struttura  # noqa: E402
from sqlalchemy import select  # noqa: E402

A.app.config['TESTING'] = True
Sessione = seed.popola('sqlite:///' + os.path.join(PROVVISORIA, 'prove.db'))
A.Sessione = Sessione
C = A.app.test_client()
esiti = []
LUN = date(2026, 12, 7)
ORARI = [datetime.combine(LUN, time(h, m)) for h, m in ((7, 30), (9, 10), (10, 20), (15, 40), (16, 10), (21, 0))]
ORARI.append(datetime.combine(LUN - timedelta(days=1), time(10, 0)))          # la domenica prima
# i periodi delle statistiche: i sei con nome (ambulatori.periodo_da) e uno scritto con le date
PERIODI = ['periodo=%s' % n for n in ('oggi', 'ieri', 'settimana', 'settimana-scorsa', 'mese', 'mese-scorso')]
PERIODI.append('da=2026-11-25&a=2026-12-09')


def prova(nome, f):
    try:
        esiti.append(('OK', nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', nome, '%s · %s' % (dove(e), str(e) or 'asserzione fallita')))
    except Exception as e:
        esiti.append(('ERRORE', nome, '%s · %r' % (dove(e), e)))


def prepara():
    """Nomi inventati al posto di quelli di seed.py, e una giornata di lunedì con appuntamenti in ogni stato."""
    s = Sessione()
    for st, nome in zip(s.scalars(select(Struttura).order_by(Struttura.id)), ('Ambulatori Esempio', 'Clinica Provetta')):
        st.nome = nome
    inventati = [('Medicorossi', 'Ada'), ('Dottorelli', 'Bruno'), ('Curanti', 'Carla'), ('Visitoni', 'Dario'),
                 ('Ricettari', 'Elsa'), ('Fonendi', 'Furio'), ('Garzini', 'Gaia')]
    medici = s.scalars(select(Operatore).order_by(Operatore.id)).all()
    for o, (c, n) in zip(medici, inventati):
        o.cognome, o.nome = c, n
    stanze = {r.nome: r for r in s.scalars(select(Risorsa))}
    pazienti = [Paziente(cognome=c, nome=n, telefono=t) for c, n, t in
                (('Provetti', 'Ada', '0001110001'), ('Saggio', 'Bruno', '0001110002'), ('Fittizi', 'Carla', '0001110003'))]
    s.add_all(pazienti)
    s.flush()

    def app(stanza, medico, h, m, minuti, paziente, stato, **altro):
        inizio = datetime.combine(LUN, time(h, m))
        s.add(Appuntamento(risorsa_id=stanze[stanza].id, operatore_id=medici[medico].id, paziente_id=pazienti[paziente].id,
                           inizio=inizio, fine=inizio + timedelta(minutes=minuti), stato=stato, **altro))

    app('Ambulatorio 1', 0, 9, 0, 30, 0, 'ARRIVATO', arrivato_alle=datetime.combine(LUN, time(8, 55)))
    app('Ambulatorio 1', 0, 9, 30, 30, 1, 'PRENOTATO')
    app('Ambulatorio 1', 0, 10, 0, 30, 2, 'CONFERMATO')
    app('Ambulatorio 1', 0, 11, 0, 30, 0, 'DISDETTO')
    app('Ambulatorio 1', 0, 11, 30, 30, 1, 'NON_PRESENTATO')
    app('Ambulatorio 2', 2, 15, 0, 30, 2, 'PRENOTATO')
    app('Ambulatorio 2', 2, 16, 0, 30, 0, 'ARRIVATO', arrivato_alle=datetime.combine(LUN, time(15, 50)))
    app('Sala endoscopia', 1, 10, 0, 45, 1, 'CONFERMATO')
    app('Sala A', 1, 8, 0, 120, 2, 'CONFERMATO')
    app('Sala B', 3, 14, 0, 90, 0, 'PRENOTATO')
    s.commit()
    strutture = [st.id for st in s.scalars(select(Struttura).order_by(Struttura.id))]
    s.close()
    return strutture


STRUTTURE = prepara()


class OraFerma:
    """L'orologio fermo in tutti i moduli del programma che leggono datetime.now() o date.today()."""

    def __init__(self, quando):
        self.quando = quando

    def __enter__(self):
        quando = self.quando

        class Data(DT.date):
            @classmethod
            def today(cls):
                return quando.date()

        class Momento(DT.datetime):
            @classmethod
            def now(cls, tz=None):
                return quando

            @classmethod
            def today(cls):
                return quando
        self.cambiati = []
        for m in list(sys.modules.values()):
            f = getattr(m, '__file__', None) or ''
            if not f.startswith(CARTELLA) or os.path.basename(f).startswith('prove'):
                continue
            for nome, vero, finto in (('datetime', DT.datetime, Momento), ('date', DT.date, Data)):
                if getattr(m, nome, None) is vero:
                    setattr(m, nome, finto)
                    self.cambiati.append((m, nome, vero))
        return self

    def __exit__(self, *a):
        for m, nome, vero in self.cambiati:
            setattr(m, nome, vero)


def leggi(indirizzo):
    r = C.get(indirizzo)
    assert r.status_code == 200, (indirizzo, r.status_code)
    return json.loads(r.get_data(as_text=True))


def adesso():
    """Tutti i JSON, uno per caso: {'2026-12-07 15:40 · /riepilogo-live.json?struttura=1': {...}}."""
    out = {}
    for quando in ORARI:
        with OraFerma(quando):
            for sid in STRUTTURE:
                u = '/riepilogo-live.json?struttura=%d' % sid
                out['%s · %s' % (quando.strftime('%Y-%m-%d %H:%M'), u)] = leggi(u)
    with OraFerma(ORARI[3]):
        for sid in STRUTTURE:
            for periodo in PERIODI:
                for parte in ('ambulatori', 'sala'):
                    u = '/riepilogo-live/statistiche.json?struttura=%d&%s&parte=%s' % (sid, periodo, parte)
                    out['%s · %s' % (ORARI[3].strftime('%Y-%m-%d %H:%M'), u)] = leggi(u)
    return out


def primo_punto_diverso(a, b, posto=''):
    """Dove due JSON cominciano a essere diversi: (posto, di qua, di là); None se sono uguali. Non basta ==:
    per Python 1 e 1.0, o 1 e True, sono uguali, e anche due elenchi che li contengono."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in list(a) + [k for k in b if k not in a]:
            d = primo_punto_diverso(a.get(k, '(manca)'), b.get(k, '(manca)'), '%s[%r]' % (posto, k))
            if d:
                return d
        return None
    elif isinstance(a, list) and isinstance(b, list):
        for i in range(max(len(a), len(b))):
            d = primo_punto_diverso(a[i] if i < len(a) else '(manca)', b[i] if i < len(b) else '(manca)', '%s[%d]' % (posto, i))
            if d:
                return d
        return None
    elif type(a) is type(b) and a == b:
        return None
    return posto or '(tutto)', a, b


try:
    ORA = adesso()
except Exception:
    shutil.rmtree(PROVVISORIA, ignore_errors=True)
    raise

if '--scrivi' in sys.argv:
    with open(ATTESO, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(ORA, f, ensure_ascii=False, indent=1)
        f.write('\n')
    shutil.rmtree(PROVVISORIA, ignore_errors=True)
    print('scritto %s: %d casi' % (os.path.basename(ATTESO), len(ORA)))
    sys.exit(0)

with open(ATTESO, encoding='utf-8') as f:
    PRIMA = json.load(f)


def p_uguali():
    diversi = []
    for caso in sorted(set(PRIMA) | set(ORA)):
        d = primo_punto_diverso(PRIMA.get(caso, '(manca)'), ORA.get(caso, '(manca)'))
        if d:
            diversi.append('%s %s: prima %.120r, ora %.120r' % (caso, d[0], d[1], d[2]))
    assert not diversi, '%d casi diversi; il primo: %s' % (len(diversi), diversi[0])
    return '%d casi' % len(ORA)


def g_ci_sono_numeri():
    """Il gemello: i JSON confrontati hanno davvero dentro le visite della giornata (non sono vuoti per caso)."""
    d = ORA['2026-12-07 10:20 · /riepilogo-live.json?struttura=%d' % STRUTTURE[0]]
    assert d['oggi']['totale'] >= 4 and d['oggi']['arrivati'] >= 1, d['oggi']
    assert any(x.get('linea', {}).get('visite') for x in d['stanze']), 'nessuna visita nelle linee del tempo'
    assert d['aggiornato'] == '10:20', d['aggiornato']
    sera = ORA['2026-12-07 21:00 · /riepilogo-live.json?struttura=%d' % STRUTTURE[0]]
    assert sera != d, 'alle 10:20 e alle 21:00 i numeri sono uguali: l\'orologio non è fermo dove si crede'
    # i periodi chiesti sono quelli giusti: un nome che il programma non conosce ricadrebbe sulla settimana
    giorni = {p: ORA['2026-12-07 15:40 · /riepilogo-live/statistiche.json?struttura=%d&%s&parte=ambulatori'
                     % (STRUTTURE[0], p)]['giorni_periodo'] for p in PERIODI}
    attesi = [1, 1, 7, 7, 31, 30, 15]
    assert [giorni[p] for p in PERIODI] == attesi, giorni
    sala = ORA['2026-12-07 15:40 · /riepilogo-live/statistiche.json?struttura=%d&periodo=oggi&parte=sala' % STRUTTURE[1]]
    amb = ORA['2026-12-07 15:40 · /riepilogo-live/statistiche.json?struttura=%d&periodo=oggi&parte=ambulatori' % STRUTTURE[1]]
    assert sala != amb, 'le statistiche della sala operatoria sono uguali a quelle degli ambulatori'


def g_trova_le_differenze():
    """Il gemello del confronto: una differenza in fondo a un JSON (un orario dentro una visita) si trova, con il posto."""
    caso = '2026-12-07 10:20 · /riepilogo-live.json?struttura=%d' % STRUTTURE[0]
    altro = json.loads(json.dumps(ORA[caso]))
    stanza = next(x for x in altro['stanze'] if x.get('linea', {}).get('visite'))
    visita = stanza['linea']['visite'][0]
    k = sorted(visita)[0]
    visita[k] = '(cambiato)'
    d = primo_punto_diverso(ORA[caso], altro)
    assert d and d[0].endswith("['visite'][0][%r]" % k) and d[2] == '(cambiato)', d
    assert primo_punto_diverso({'a': 1}, {'a': 1.0}), 'un intero diventato decimale deve contare'
    assert primo_punto_diverso([True], [1]), 'un vero/falso diventato numero deve contare'
    assert primo_punto_diverso({'a': [1, 2]}, {'a': [1, 2, 3]})[0] == "['a'][2]"
    assert primo_punto_diverso(ORA, json.loads(json.dumps(ORA))) is None


def g_nomi_inventati():
    """Nel file di riferimento ci sono solo i nomi inventati del mondo di prova."""
    with open(ATTESO, encoding='utf-8') as f:
        testo = f.read()
    assert 'Medicorossi' in testo and 'Ambulatori Esempio' in testo, 'il file non ha i nomi del mondo di prova'
    s = Sessione()
    from modelli import Paziente as P
    vietati = [p.cognome for p in s.scalars(select(P))]
    s.close()
    trovati = [n for n in vietati if n and n in testo]
    assert not trovati, 'nomi di pazienti nel file di riferimento: %s' % trovati


prova('i JSON del Modo schermo sono uguali al riferimento, chiave per chiave, a ogni livello', p_uguali)
prova('gemello: nei JSON ci sono le visite della giornata e l\'orologio è fermo', g_ci_sono_numeri)
prova('gemello: il confronto trova una differenza in fondo e dice dove', g_trova_le_differenze)
prova('nel riferimento solo nomi inventati e nessun paziente', g_nomi_inventati)

shutil.rmtree(PROVVISORIA, ignore_errors=True)
for esito, nome, dettaglio in esiti:
    print('%-6s %s %s' % (esito, nome, dettaglio))
rotte = [e for e in esiti if e[0] != 'OK']
print('%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(rotte), len(rotte)))
sys.exit(1 if rotte else 0)
