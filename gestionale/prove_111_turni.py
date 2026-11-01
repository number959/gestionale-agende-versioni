# -*- coding: utf-8 -*-
"""Prove della 1.11: i difetti dei turni del personale trovati dalla revisione
del codice di novembre 2026, uno per uno. Ognuno era stato riprodotto da un
controllo indipendente prima di correggerlo; qui ogni prova lo rifa' e
controlla la correzione (le prove sono state verificate anche rimettendo il
difetto: devono fallire).

- Annulla (Ctrl+Z) dopo aver tolto o cambiato il turno di chi non e' piu' in
  servizio, o un turno di un tipo non piu' in uso: non rimetteva niente, e in
  un blocco di celle non rimetteva nemmeno i turni dei colleghi.
- Con il filtro per area, una cella che sembrava vuota sostituiva di nascosto
  il turno di un'altra area (con la sua nota), il turno nuovo prendeva l'area
  di quello nascosto e non si vedeva; Canc toglieva anche i turni nascosti.

Il terzo difetto (Ctrl+Z mentre si scrive un codice, o mentre una modifica si
sta ancora salvando) e' della pagina: le sue prove sono in prove_18_browser.py.
Tutti i nomi sono inventati."""
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import traceback
from collections import defaultdict
from datetime import date, time, timedelta

CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = tempfile.mkdtemp(prefix='prove_111_turni_')
os.environ['LOCALAPPDATA'] = os.path.join(PROVVISORIA, 'localappdata')
sys.path.insert(0, CARTELLA)
logging.getLogger().setLevel(logging.CRITICAL)

from sqlalchemy import select  # noqa: E402

import app as A  # noqa: E402
import servizi  # noqa: E402
import viste  # noqa: E402
from modelli import crea_sessione, Persona, TipoTurno, TurnoPersonale  # noqa: E402

A.app.config['TESTING'] = True
esiti, _area, _n = [], [''], [0]
SOLO = [x for x in os.environ.get('PROVE_SOLO', '').split(',') if x]
CAMBIA = '/personale/turni/cambia'
OGGI = date.today()


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
def mondo():
    """Un gestionale nuovo con quattro infermieri, tutti in servizio."""
    _n[0] += 1
    S = crea_sessione('sqlite:///' + os.path.join(PROVVISORIA, 'db_%d.db' % _n[0]))
    s = S()
    servizi.prepara_primo_avvio(s)
    s.add_all([Persona(cognome='Fittizi', nome='Ada', ruolo='INFERMIERE', minuti_settimana=36 * 60),
               Persona(cognome='Esempio', nome='Bruno', ruolo='INFERMIERE', minuti_settimana=36 * 60),
               Persona(cognome='Fintoni', nome='Paolo', ruolo='INFERMIERE'),
               Persona(cognome='Testabianca', nome='Rita', ruolo='INFERMIERE')])
    s.commit()
    s.close()
    A.Sessione = S
    A._registro = None
    viste._sessionmaker = lambda: S
    return S, A.app.test_client()


def persone(S):
    s = S()
    try:
        return {p.cognome: p.id for p in s.scalars(select(Persona))}
    finally:
        s.close()


def tipi(S):
    s = S()
    try:
        return {t.codice: t.id for t in s.scalars(select(TipoTurno))}
    finally:
        s.close()


def k(pid, g):
    return '%d_%s' % (pid, g.isoformat())


def cambia(C, **dati):
    r = C.post(CAMBIA, json=dati)
    try:
        return r.status_code, json.loads(r.get_data(as_text=True))
    except ValueError:
        return r.status_code, None


def lunedi(g=None):
    g = g or OGGI
    return g - timedelta(days=g.weekday())


def stato(S):
    """Tutti i turni: {(persona, giorno): [(codice, inizio, fine, area, note)]} in ordine."""
    s = S()
    try:
        fuori = defaultdict(list)
        for t in s.scalars(select(TurnoPersonale)):
            fuori[(t.persona_id, t.giorno)].append((t.tipo.codice if t.tipo is not None else None,
                                                    t.inizio.strftime('%H:%M') if t.inizio else '',
                                                    t.fine.strftime('%H:%M') if t.fine else '',
                                                    t.area or '', t.note or ''))
        return {x: sorted(v, key=lambda y: (y[1], y[0] or '')) for x, v in fuori.items()}
    finally:
        s.close()


def in_servizio(S, pid, si):
    s = S()
    s.get(Persona, pid).attiva = si
    s.commit()
    s.close()


def codici(d, chiave):
    return [v['codice'] or v['orario'] for v in d['celle'][chiave]['turni']]


def cella_della_pagina(C, url, chiave):
    """Il contenuto della cella nella pagina (per vedere cosa compare con un filtro)."""
    pagina = C.get(url).get_data(as_text=True)
    m = re.search(r'<td[^>]*data-k="%s"[^>]*>(.*?)</td>' % chiave, pagina, re.S)
    assert m, 'cella %s non trovata in %s' % (chiave, url)
    return m.group(1)


# ================================================================ 1. annulla con chi non e' piu' in servizio
area('annulla: chi non e\' in servizio, tipi non piu\' in uso')


def a_non_in_servizio():
    """Canc sul turno di chi non e' piu' in servizio (la sua riga resta nella griglia), poi Annulla e Rifai."""
    S, C = mondo()
    P, T = persone(S), tipi(S)
    g = lunedi() + timedelta(days=14)
    a = P['Fittizi']
    st_code, d = cambia(C, azione='metti', celle=[k(a, g)], tipo=T['M'], area='Degenza', note='nota prova')
    assert d['ok'], d
    in_servizio(S, a, False)
    assert ('data-k="%s"' % k(a, g)) in C.get('/personale/turni/mese/%s' % g.strftime('%Y-%m')).get_data(as_text=True), \
        'la riga di chi non e\' in servizio, con i suoi turni, deve restare nella griglia'
    prima = stato(S)
    st_code, d = cambia(C, azione='togli', celle=[k(a, g)])
    assert d['ok'] and d['fatti'] == 1 and not stato(S), d
    st_code, d2 = cambia(C, azione='ripristina', stato=d['prima'])
    assert st_code == 200 and d2['ok'] and d2['fatti'] == 1, ('annulla rifiutato', d2.get('errori'))
    assert stato(S) == prima, ('annulla: il turno non e\' tornato com\'era', stato(S))
    assert [v['codice'] for v in d2['celle'][k(a, g)]['turni']] == ['M'], d2['celle'][k(a, g)]
    st_code, d3 = cambia(C, azione='ripristina', stato=d2['prima'])
    assert d3['ok'] and not stato(S), ('rifai', d3.get('errori'))
    st_code, d4 = cambia(C, azione='ripristina', stato=d3['prima'])
    assert d4['ok'] and stato(S) == prima, ('annulla di nuovo', d4.get('errori'))
    # un turno sostituito (non solo tolto) torna anche lui
    st_code, d = cambia(C, azione='ripristina', stato={k(a, g): [{'tipo': T['P'], 'area': 'Degenza'}]})
    assert d['ok'] and stato(S)[(a, g)][0][0] == 'P', d
    st_code, d2 = cambia(C, azione='ripristina', stato=d['prima'])
    assert d2['ok'] and stato(S) == prima, d2.get('errori')
    # ma dalla pagina un turno nuovo a chi non e' in servizio non si mette, ne' si aggiunge
    for azione in ('metti', 'aggiungi'):
        st_code, d = cambia(C, azione=azione, celle=[k(a, g + timedelta(days=1))], tipo=T['M'])
        assert not d['ok'] and 'non più in servizio' in ' '.join(d['errori']), (azione, d)
    assert stato(S) == prima


def a_tipo_non_in_uso():
    """Un tipo di turno «eliminato» quando era gia' usato resta nei turni messi: sostituirlo o toglierlo si annulla."""
    S, C = mondo()
    P, T = persone(S), tipi(S)
    g = lunedi() + timedelta(days=14)
    b = P['Esempio']
    st_code, d = cambia(C, azione='metti', celle=[k(b, g)], tipo=T['G'], area='Ambulatori', note='giornata lunga')
    assert d['ok'], d
    C.post('/personale/tipi', data={'azione': 'elimina_tipo', 'id': T['G']})
    s = S()
    assert s.get(TipoTurno, T['G']).attivo is False, 'il tipo usato deve restare, non piu\' in uso'
    s.close()
    prima = stato(S)
    # M al posto della G (dalla tastiera), poi Annulla
    st_code, d = cambia(C, azione='metti', celle=[k(b, g)], tipo=T['M'], tieni_area=True)
    assert d['ok'] and stato(S)[(b, g)][0][0] == 'M', d
    st_code, d2 = cambia(C, azione='ripristina', stato=d['prima'])
    assert d2['ok'] and d2['fatti'] == 1, ('annulla rifiutato', d2.get('errori'))
    assert stato(S) == prima, ('la G non e\' tornata', stato(S))
    st_code, d3 = cambia(C, azione='ripristina', stato=d2['prima'])
    assert d3['ok'] and stato(S)[(b, g)][0][0] == 'M', ('rifai', d3.get('errori'))
    st_code, d4 = cambia(C, azione='ripristina', stato=d3['prima'])
    assert d4['ok'] and stato(S) == prima, d4.get('errori')
    # Canc sulla G, poi Annulla
    st_code, d = cambia(C, azione='togli', celle=[k(b, g)])
    assert d['ok'] and not stato(S), d
    st_code, d2 = cambia(C, azione='ripristina', stato=d['prima'])
    assert d2['ok'] and stato(S) == prima, ('Canc e Annulla: la G non e\' tornata', d2.get('errori'))
    # dalla pagina la G non si mette piu'
    st_code, d = cambia(C, azione='metti', celle=[k(b, g + timedelta(days=1))], tipo=T['G'])
    assert not d['ok'] and 'non è più in uso' in d['errori'][0], d
    assert stato(S) == prima


def a_blocco_misto():
    """Un blocco di 3 persone per 4 giorni, una non piu' in servizio: Canc su tutto, Annulla rimette tutti e 12."""
    S, C = mondo()
    P, T = persone(S), tipi(S)
    g = lunedi() + timedelta(days=14)
    ids = [P['Fittizi'], P['Esempio'], P['Fintoni']]
    celle = [k(pid, g + timedelta(days=i)) for i in range(4) for pid in ids]
    st_code, d = cambia(C, azione='metti', celle=celle, tipo=T['P'], area='Degenza')
    assert d['ok'] and d['fatti'] == 12, d
    in_servizio(S, ids[1], False)
    prima = stato(S)
    st_code, d = cambia(C, azione='togli', celle=celle)
    assert d['ok'] and d['fatti'] == 12 and not stato(S), d
    st_code, d2 = cambia(C, azione='ripristina', stato=d['prima'])
    assert d2['ok'] and d2['fatti'] == 12, ('annulla del blocco', d2['fatti'], d2.get('errori'))
    assert stato(S) == prima, 'annulla: non sono tornati tutti e 12 i turni'
    st_code, d3 = cambia(C, azione='ripristina', stato=d2['prima'])
    assert d3['ok'] and not stato(S), ('rifai del blocco', d3.get('errori'))
    st_code, d4 = cambia(C, azione='ripristina', stato=d3['prima'])
    assert d4['ok'] and stato(S) == prima, d4.get('errori')


def a_sovrapposti_ancora_no():
    """Anche per chi non e' in servizio l'annulla resta tutto o niente: un turno di prima che adesso si
    sovrappone a un altro non si rimette, e non cambia niente."""
    S, C = mondo()
    P, T = persone(S), tipi(S)
    g = lunedi() + timedelta(days=14)
    a, b = P['Fittizi'], P['Esempio']
    cambia(C, azione='metti', celle=[k(a, g)], tipo=T['N'])
    cambia(C, azione='metti', celle=[k(b, g)], tipo=T['M'])
    st_code, d = cambia(C, azione='togli', celle=[k(a, g), k(b, g)])
    assert d['fatti'] == 2, d
    # la mattina dopo, un turno dalle 6: la notte di prima non ci sta piu'
    cambia(C, azione='metti', celle=[k(a, g + timedelta(days=1))], inizio='6', fine='13')
    in_servizio(S, a, False)
    adesso = stato(S)
    st_code, d2 = cambia(C, azione='ripristina', stato=d['prima'])
    assert not d2['ok'] and d2['fatti'] == 0 and 'Non si può annullare' in d2['errori'][0], d2
    assert stato(S) == adesso, 'un annulla non riuscito ha cambiato qualcosa'


prova('Canc e cambio sul turno di chi non e\' piu\' in servizio: Annulla e Rifai lo rimettono', a_non_in_servizio)
prova('un tipo di turno non piu\' in uso: sostituito o tolto, Annulla lo rimette', a_tipo_non_in_uso)
prova('blocco di 12 celle con una persona non in servizio: Annulla rimette tutto', a_blocco_misto)
prova('annulla tutto o niente: le sovrapposizioni restano rifiutate', a_sovrapposti_ancora_no)


# ================================================================ 2. il filtro per area
area('modifiche con il filtro per area')


def f_cella_che_sembra_vuota():
    """Con il filtro Degenza la cella di chi fa un pomeriggio in Ambulatori e' vuota: scrivendo M il pomeriggio
    (con la sua nota) resta, la M prende l'area del filtro e compare nella cella."""
    S, C = mondo()
    P, T = persone(S), tipi(S)
    lun = lunedi() + timedelta(days=14)
    g = lun + timedelta(days=1)
    dal, al = lun.isoformat(), (lun + timedelta(days=6)).isoformat()
    a = P['Fittizi']
    cambia(C, azione='metti', celle=[k(a, g)], tipo=T['P'], area='Ambulatori', note='cambio con collega')
    prima = stato(S)
    url = '/personale/turni/settimana/%s?area=Degenza' % lun.isoformat()
    assert 'class="turno' not in cella_della_pagina(C, url, k(a, g)), 'con il filtro il turno nascosto non si vede'
    # quello che manda la pagina scrivendo M da tastiera nella vista filtrata
    st_code, d = cambia(C, azione='metti', celle=[k(a, g)], tipo=T['M'], tieni_area=True, dal=dal, al=al,
                        area_filtro='Degenza')
    assert d['ok'] and d['fatti'] == 1, d
    dopo = stato(S)
    assert dopo[(a, g)] == [('M', '07:00', '14:00', 'Degenza', ''), ('P', '14:00', '21:00', 'Ambulatori', 'cambio con collega')], \
        ('il turno nascosto deve restare e la M avere l\'area del filtro', dopo[(a, g)])
    assert codici(d, k(a, g)) == ['M'] and d['celle'][k(a, g)]['turni'][0]['area'] == 'Degenza', \
        ('la M deve comparire nella cella ridisegnata', d['celle'][k(a, g)])
    assert d['copertura']['INFERMIERE_%s' % g.isoformat()]['testo'] == 'M1', d['copertura']
    assert 'class="turno' in cella_della_pagina(C, url, k(a, g)), 'la M deve comparire anche ricaricando la pagina'
    # Annulla e Rifai riguardano la cella intera: torna esattamente com'era
    assert d['prima'] == {k(a, g): [{'tipo': T['P'], 'inizio': '14:00', 'fine': '21:00', 'area': 'Ambulatori',
                                     'note': 'cambio con collega'}]}, d['prima']
    st_code, d2 = cambia(C, azione='ripristina', stato=d['prima'], dal=dal, al=al, area_filtro='Degenza')
    assert d2['ok'] and stato(S) == prima and codici(d2, k(a, g)) == [], (d2.get('errori'), stato(S))
    st_code, d3 = cambia(C, azione='ripristina', stato=d2['prima'], dal=dal, al=al, area_filtro='Degenza')
    assert d3['ok'] and stato(S) == dopo, d3.get('errori')


def f_sovrapposto_nascosto():
    """Un turno che si sovrappone a quello nascosto (o un riposo) si rifiuta con il motivo, e non cambia niente."""
    S, C = mondo()
    P, T = persone(S), tipi(S)
    g = lunedi() + timedelta(days=15)
    a = P['Fittizi']
    cambia(C, azione='metti', celle=[k(a, g)], tipo=T['P'], area='Ambulatori', note='cambio con collega')
    prima = stato(S)
    for codice in ('G', 'R', 'F'):
        st_code, d = cambia(C, azione='metti', celle=[k(a, g)], tipo=T[codice], tieni_area=True, area_filtro='Degenza')
        assert not d['ok'] and d['fatti'] == 0 and '«Pomeriggio»' in ' '.join(d['errori']), (codice, d)
        assert stato(S) == prima, (codice, 'il turno nascosto e\' stato toccato', stato(S))


def f_area_del_filtro():
    """In una cella vuota, con il filtro: i turni con orario prendono l'area del filtro (se non se ne scrive
    un'altra), riposi e assenze no."""
    S, C = mondo()
    P, T = persone(S), tipi(S)
    g = lunedi() + timedelta(days=14)
    b = P['Esempio']
    casi = [
        (dict(azione='metti', tipo=T['M'], tieni_area=True), 'Degenza'),           # da tastiera
        (dict(azione='metti', tipo=T['P']), 'Degenza'),                             # dalla scelta, senza area
        (dict(azione='metti', inizio='8', fine='12'), 'Degenza'),                   # orario scritto a mano
        (dict(azione='metti', tipo=T['RE'], tieni_area=True), 'Degenza'),           # reperibilita'
        (dict(azione='metti', tipo=T['P'], area='Ambulatori'), 'Ambulatori'),       # l'area scritta vince
        (dict(azione='metti', tipo=T['R'], tieni_area=True), ''),                  # un riposo non ha area
        (dict(azione='metti', tipo=T['F']), ''),                                    # un'assenza nemmeno
    ]
    for i, (dati, attesa) in enumerate(casi):
        gi = g + timedelta(days=i)
        st_code, d = cambia(C, celle=[k(b, gi)], area_filtro='Degenza', **dati)
        assert d['ok'], (dati, d)
        assert stato(S)[(b, gi)][0][3] == attesa, (dati, stato(S)[(b, gi)])
        if attesa in ('Degenza', ''):
            assert len(d['celle'][k(b, gi)]['turni']) == 1, ('il turno deve comparire nella cella', dati)
    # un secondo turno nello stesso giorno (spezzato): anche lui nell'area del filtro
    gi = g + timedelta(days=2)
    st_code, d = cambia(C, azione='aggiungi', celle=[k(b, gi)], inizio='15', fine='18', area_filtro='Degenza')
    assert d['ok'] and [x[3] for x in stato(S)[(b, gi)]] == ['Degenza', 'Degenza'], (d, stato(S)[(b, gi)])
    assert len(d['celle'][k(b, gi)]['turni']) == 2, d['celle'][k(b, gi)]


def f_canc_solo_quelli_visti():
    """Canc con il filtro toglie solo i turni che si vedono (riposi e assenze compresi); Annulla rimette la cella."""
    S, C = mondo()
    P, T = persone(S), tipi(S)
    g = lunedi() + timedelta(days=14)
    c, d_ = P['Fintoni'], P['Testabianca']
    cambia(C, azione='metti', celle=[k(c, g)], inizio='07:00', fine='11:00', area='Degenza')
    cambia(C, azione='aggiungi', celle=[k(c, g)], inizio='15:00', fine='19:00', area='Ambulatori', note='nascosto')
    cambia(C, azione='metti', celle=[k(c, g + timedelta(days=1))], tipo=T['P'], area='Ambulatori')
    cambia(C, azione='metti', celle=[k(d_, g)], tipo=T['R'])
    prima = stato(S)
    st_code, d = cambia(C, azione='togli', celle=[k(c, g), k(c, g + timedelta(days=1)), k(d_, g)],
                        area_filtro='Degenza')
    assert d['ok'] and d['fatti'] == 2, d
    dopo = stato(S)
    assert dopo.get((c, g)) == [(None, '15:00', '19:00', 'Ambulatori', 'nascosto')], \
        ('Canc deve togliere solo il turno della Degenza', dopo.get((c, g)))
    assert dopo.get((c, g + timedelta(days=1))) == prima[(c, g + timedelta(days=1))], 'cella con soli turni nascosti toccata'
    assert (d_, g) not in dopo, 'il riposo si vede con ogni filtro: Canc lo toglie'
    assert sorted(d['prima']) == sorted([k(c, g), k(d_, g)]), d['prima']
    assert len(d['prima'][k(c, g)]) == 2, 'per Annulla serve la cella intera'
    st_code, d2 = cambia(C, azione='ripristina', stato=d['prima'], area_filtro='Degenza')
    assert d2['ok'] and stato(S) == prima, (d2.get('errori'), stato(S))
    # il turno indicato dalla scelta (la crocetta accanto al turno) si toglie come prima
    s = S()
    visto = s.scalars(select(TurnoPersonale).where(TurnoPersonale.persona_id == c, TurnoPersonale.giorno == g,
                                                   TurnoPersonale.area == 'Degenza')).first().id
    s.close()
    st_code, d = cambia(C, azione='togli', celle=[k(c, g)], turno=visto, area_filtro='Degenza')
    assert d['ok'] and d['fatti'] == 1 and len(stato(S)[(c, g)]) == 1, d


def f_senza_filtro_come_prima():
    """Senza filtro niente cambia: si sostituisce tutta la cella, tieni_area tiene l'area di prima."""
    S, C = mondo()
    P, T = persone(S), tipi(S)
    g = lunedi() + timedelta(days=14)
    a = P['Fittizi']
    cambia(C, azione='metti', celle=[k(a, g)], inizio='07:00', fine='11:00', area='Degenza')
    cambia(C, azione='aggiungi', celle=[k(a, g)], inizio='15:00', fine='19:00', area='Ambulatori')
    st_code, d = cambia(C, azione='metti', celle=[k(a, g)], tipo=T['P'], tieni_area=True, area_filtro='')
    assert d['ok'] and stato(S)[(a, g)] == [('P', '14:00', '21:00', 'Degenza', '')], stato(S)[(a, g)]
    st_code, d = cambia(C, azione='metti', celle=[k(a, g)], tipo=T['M'])
    assert stato(S)[(a, g)] == [('M', '07:00', '14:00', '', '')], stato(S)[(a, g)]
    cambia(C, azione='aggiungi', celle=[k(a, g)], inizio='15:00', fine='19:00', area='Ambulatori')
    st_code, d = cambia(C, azione='togli', celle=[k(a, g)])
    assert d['fatti'] == 1 and (a, g) not in stato(S), 'senza filtro Canc toglie tutta la cella'


def f_vista_del_giorno():
    """La vista del giorno con il filtro manda la stessa richiesta: la persona con un turno nascosto riceve il
    turno nuovo accanto a quello, e la riga compare."""
    S, C = mondo()
    P, T = persone(S), tipi(S)
    g = lunedi() + timedelta(days=16)
    a = P['Fittizi']
    cambia(C, azione='metti', celle=[k(a, g)], tipo=T['P'], area='Ambulatori', note='cambio con collega')
    url = '/personale/turni/giorno/%s?area=Degenza' % g.isoformat()
    assert ('data-k="%s"' % k(a, g)) not in C.get(url).get_data(as_text=True)
    st_code, d = cambia(C, azione='metti', celle=[k(a, g)], tipo=T['M'], tieni_area=True, dal=g.isoformat(),
                        al=g.isoformat(), area_filtro='Degenza')
    assert d['ok'] and [x[0] for x in stato(S)[(a, g)]] == ['M', 'P'], (d, stato(S))
    pagina = C.get(url).get_data(as_text=True)
    assert ('data-k="%s"' % k(a, g)) in pagina and 'Mattina 7–14, Degenza' in pagina, 'la M nella vista del giorno'


prova('cella che sembra vuota: il turno nascosto resta, il nuovo ha l\'area del filtro e si vede', f_cella_che_sembra_vuota)
prova('turno sopra uno nascosto, riposo o assenza con un turno nascosto: rifiutati con il motivo', f_sovrapposto_nascosto)
prova('area del filtro ai turni nuovi con orario (non a riposi e assenze), l\'area scritta vince', f_area_del_filtro)
prova('Canc con il filtro: solo i turni che si vedono; Annulla rimette la cella intera', f_canc_solo_quelli_visti)
prova('senza filtro tutto come prima: sostituire e togliere la cella intera', f_senza_filtro_come_prima)
prova('vista del giorno con il filtro: il turno nuovo accanto a quello nascosto', f_vista_del_giorno)


# =====================================================================
if __name__ == '__main__':
    aree = []
    for e in esiti:
        if e[1] not in aree:
            aree.append(e[1])
    for a in aree:
        mie = [e for e in esiti if e[1] == a]
        rotte = [e for e in mie if e[0] != 'OK']
        print('%-56s %2d prove  %s' % (a, len(mie), 'tutte a posto' if not rotte else '%d DA SISTEMARE' % len(rotte)))
    rotte = [e for e in esiti if e[0] != 'OK']
    if rotte or os.environ.get('DETTAGLIO'):
        print('\nDettaglio:')
        for e in esiti:
            if e[0] != 'OK' or os.environ.get('DETTAGLIO'):
                print('  %-6s [%s] %s\n         %s' % (e[0], e[1], e[2], e[3]))
    print('\n%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(rotte), len(rotte)))
    shutil.rmtree(PROVVISORIA, ignore_errors=True)
    sys.exit(1 if rotte else 0)
