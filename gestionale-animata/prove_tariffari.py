# -*- coding: utf-8 -*-
"""Prove dei tariffari dei medici (1.12.6, tariffari.py).

- la lettura degli Excel: titolo, intestazioni, piu' coppie voce-prezzo (le sezioni), colonne Sezione, Modalita',
  Dettagli, righe di sezione, la riga senza nome che continua la voce (singola e pacchetto), le note, piu' fogli, i
  prezzi scritti in tanti modi, i file sbagliati;
- le proposte: medici dal nome del tariffario, prestazioni dal nome della voce (anche i sinonimi), mai i pacchetti;
- il caricamento con l'anteprima: medici, prestazioni collegate o create, la sostituzione di un tariffario con lo
  stesso nome, l'annullamento, il file che non c'e' piu';
- il prezzo proposto nella prenotazione: convenzione, poi tariffario del medico, poi listino; i tariffari spenti e
  i pacchetti non contano;
- la scheda (cambia, aggiungi, togli, errori), il controllo per medico, la stampa, il riquadro nella scheda del
  medico, le protezioni in Anagrafiche, lo schema 12.

Nomi e prezzi inventati."""
import logging
import os
import shutil
import sys
import tempfile
import traceback
from io import BytesIO

CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = tempfile.mkdtemp(prefix='prove_tariffari_')
os.environ['LOCALAPPDATA'] = os.path.join(PROVVISORIA, 'localappdata')
os.environ['NO_PROXY'] = os.environ['no_proxy'] = '127.0.0.1,localhost'
sys.path.insert(0, CARTELLA)
logging.getLogger().setLevel(logging.CRITICAL)

from openpyxl import Workbook  # noqa: E402
from sqlalchemy import select  # noqa: E402

import app as A  # noqa: E402
import cassa  # noqa: E402
import servizi  # noqa: E402
import tariffari as T  # noqa: E402
import viste  # noqa: E402
from modelli import (crea_sessione, Struttura, Operatore, Prestazione, Tariffa, Tariffario,  # noqa: E402
                     TariffarioMedico, VoceTariffario, VERSIONE_SCHEMA)

A.app.config['TESTING'] = True
esiti, _area, _n = [], [''], [0]
SOLO = [x for x in os.environ.get('PROVE_SOLO', '').split(',') if x]
CASA = {'Sec-Fetch-Site': 'same-origin'}


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


def mondo():
    """Un database nuovo: la struttura, cinque medici inventati (due del «gruppo Fittizi»), prestazioni con e senza
    listino. (S, ids, client)."""
    _n[0] += 1
    S = crea_sessione('sqlite:///' + os.path.join(PROVVISORIA, 'db_%d.db' % _n[0]))
    s = S()
    servizi.prepara_primo_avvio(s)
    st = s.get(Struttura, 1)
    st.nome = 'Clinica Prova'
    s.add_all([Operatore(cognome='Esempietti', nome='Rita', specialita='gastroenterologia'),
               Operatore(cognome='Testabianca', nome='Lia', specialita='neurologia'),
               Operatore(cognome='Fittizi', nome='Ugo', specialita='endocrinologia'),
               Operatore(cognome='Fittizi', nome='Ada', specialita='endocrinologia'),
               Operatore(cognome='Provolo', nome='Gino'),
               Operatore(cognome='Spento', nome='Dino', attivo=False)])
    # EGDS, Colonscopia e Controllo ci sono dal primo avvio: si mette il listino a due
    for p in s.scalars(select(Prestazione)):
        p.tariffa_cent = {'EGDS': 15000, 'Colonscopia': 25000}.get(p.nome)
    s.add_all([Prestazione(nome='Visita neurologica', durata_min=30, tariffa_cent=9000),
               Prestazione(nome='Ecografia tiroide', durata_min=20, tariffa_cent=7000)])
    s.commit()
    I = {o.cognome + (' ' + o.nome if o.cognome == 'Fittizi' else ''): o.id for o in s.scalars(select(Operatore))}
    I.update({p.nome: p.id for p in s.scalars(select(Prestazione))})
    s.close()
    A.Sessione = S
    A._registro = None
    viste._sessionmaker = lambda: S
    return S, I, A.app.test_client()


def testo(r):
    return r.data.decode('utf-8')


def avvisi(c):
    with c.session_transaction() as sess:
        m = sess.get('_flashes', [])
        sess['_flashes'] = []
    return ' '.join(x[1] for x in m)


def libro(fogli):
    """Un Excel in memoria: fogli = [(titolo del foglio, [righe])]."""
    wb = Workbook()
    wb.remove(wb.active)
    for nome, righe in fogli:
        ws = wb.create_sheet(nome)
        for r in righe:
            ws.append(list(r))
    uscita = BytesIO()
    wb.save(uscita)
    return uscita.getvalue()


SEMPLICE = ('Tariffario', [('TARIFFARIO  GRUPPO FITTIZI', None), ('Prestazione ', 'Prezzo (€)'),
                           ('Prima visita endocrinologica (con ecografia)', 170), ('Visita di controllo', 110),
                           ('Ecografia tiroide', 95.5), ('CITOLOGICO', '75')])
DOPPIO = ('Tariffario', [('TARIFFARIO DOTT. ESEMPIETTI', None, None, None),
                         ('Prestazione con eventuale sedazione', 'Prezzo (€)', 'ISTOLOGICO', 'PREZZO'),
                         ('Gastroscopia', 210, '1 SEDE', 60), ('Colonscopia', 290, '2 SEDI', 80),
                         ('Polipectomia', 140, '3 SEDI', 100), (None, None, '4 SEDI', 120)])
COMPLETO = ('Testabianca', [('Tariffario Dott.ssa Testabianca (Neurologia)',),
                            ('Sezione', 'Prestazione', 'Modalità', 'Prezzo (€)', 'Dettagli'),
                            ('1. VISITE SPECIALISTICHE', None, None, None, None),
                            (None, 'Visita Specialistica Neurologica', None, '€ 120,00', None),
                            (None, 'Block Test', None, '€ 45,00', None),
                            ('Trattamenti e pacchetti', 'PRP Articolazioni', 'Singola', '€ 280,00', '1 Provetta'),
                            (None, None, 'Pacchetto', '€ 1.100,00', '5 Provette (1 a settimana)'),
                            (None, 'Ozonoterapia', 'Singola', 75, '1 Provetta'),
                            (None, None, 'Pacchetto', '€ 480', '10 Provette'),
                            (None, 'Voce senza prezzo chiaro', None, 'su richiesta', None),
                            ('Nota: le tariffe valgono per la singola seduta o per il pacchetto intero.',),
                            ('Nota: il piano si decide in visita.',)])


# ================================================================== lettura
area('lettura dei file')


def a_lettura():
    """I tre modi di scrivere un tariffario, e piu' fogli in un file."""
    t = T.leggi_tariffari(libro([SEMPLICE]), 'gruppo.xlsx')
    assert [x['nome'] for x in t] == ['Gruppo Fittizi'], t
    v = t[0]['voci']
    assert [(x['sezione'], x['nome'], x['importo_cent']) for x in v] == [
        ('', 'Prima visita endocrinologica (con ecografia)', 17000), ('', 'Visita di controllo', 11000),
        ('', 'Ecografia tiroide', 9550), ('', 'Citologico', 7500)], v
    t = T.leggi_tariffari(libro([DOPPIO]), 'esempietti.xlsx')[0]
    assert t['nome'] == 'Dott. Esempietti', t['nome']
    assert [(x['sezione'], x['nome'], x['importo_cent']) for x in t['voci']] == [
        ('Prestazione con eventuale sedazione', 'Gastroscopia', 21000),
        ('Prestazione con eventuale sedazione', 'Colonscopia', 29000),
        ('Prestazione con eventuale sedazione', 'Polipectomia', 14000),
        ('Istologico', '1 sede', 6000), ('Istologico', '2 sedi', 8000), ('Istologico', '3 sedi', 10000),
        ('Istologico', '4 sedi', 12000)], t['voci']
    t = T.leggi_tariffari(libro([COMPLETO]), 'neuro.xlsx')[0]
    assert t['nome'] == 'Dott.ssa Testabianca (Neurologia)', t['nome']
    assert [(x['sezione'], x['nome'], x['modalita'], x['importo_cent'], x['dettagli']) for x in t['voci']] == [
        ('Visite specialistiche', 'Visita Specialistica Neurologica', '', 12000, ''),
        ('Visite specialistiche', 'Block Test', '', 4500, ''),
        ('Trattamenti e pacchetti', 'PRP Articolazioni', 'Singola', 28000, '1 Provetta'),
        ('Trattamenti e pacchetti', 'PRP Articolazioni', 'Pacchetto', 110000, '5 Provette (1 a settimana)'),
        ('Trattamenti e pacchetti', 'Ozonoterapia', 'Singola', 7500, '1 Provetta'),
        ('Trattamenti e pacchetti', 'Ozonoterapia', 'Pacchetto', 48000, '10 Provette')], t['voci']
    assert t['note'] == 'le tariffe valgono per la singola seduta o per il pacchetto intero.\nil piano si decide in visita.'
    assert any('su richiesta' in a for a in t['avvisi']), t['avvisi']
    # piu' fogli: uno per tariffario; un foglio senza prezzi si salta
    tutti = T.leggi_tariffari(libro([SEMPLICE, DOPPIO, ('Appunti', [('solo testo',), ('niente prezzi',)]), COMPLETO]))
    assert [x['nome'] for x in tutti] == ['Gruppo Fittizi', 'Dott. Esempietti', 'Dott.ssa Testabianca (Neurologia)']
    # senza titolo: il nome del foglio, poi quello del file
    assert T.leggi_tariffari(libro([('Dott. Provolo', [('Voce', 'Tariffa'), ('Visita', 80)])]))[0]['nome'] == 'Dott. Provolo'
    assert T.leggi_tariffari(libro([('Foglio1', [('Voce', 'Tariffa'), ('Visita', 80)])]),
                             'TARIFFARIO_DOTT_PROVOLO.xlsx')[0]['nome'] == 'Dott Provolo'


def a_prezzi_e_file_sbagliati():
    for grezzo, cent in ((180, 18000), (95.5, 9550), ('130', 13000), ('€ 130,00', 13000), ('€ 1.000,00', 100000),
                         ('1.500', 150000), ('1500,5', 150050), (' 80 € ', 8000), ('0', 0)):
        assert T.leggi_importo(grezzo) == cent, (grezzo, T.leggi_importo(grezzo))
    for grezzo in (None, '', 'su richiesta', '-5', '1e3', 'nan', True, -10, '12,345'):
        assert T.leggi_importo(grezzo) is None, grezzo
    for dati, parola in ((b'non sono un excel', 'non si apre'), (b'', 'vuoto'),
                         (libro([('X', [('Nome', 'Cognome'), ('Ugo', 'Fittizi')])]), 'nessun tariffario')):
        try:
            T.leggi_tariffari(dati)
            raise AssertionError('accettato: %r' % dati[:20])
        except T.ErroreTariffario as e:
            assert parola in str(e), str(e)


prova('tre modi di scrivere un tariffario (semplice, due colonne di prezzi, sezioni e pacchetti), piu\' fogli, nomi',
      a_lettura)
prova('prezzi scritti in tanti modi; file che non sono un tariffario', a_prezzi_e_file_sbagliati)


# ================================================================== proposte
area('proposte di medici e prestazioni')


def b_proposte():
    S, I, C = mondo()
    s = S()
    assert set(T.medici_proposti(s, 'Gruppo Fittizi')) == {I['Fittizi Ugo'], I['Fittizi Ada']}
    assert T.medici_proposti(s, 'Dott. Esempietti') == [I['Esempietti']]
    assert T.medici_proposti(s, 'Dott. Spento') == [], 'i medici non attivi non si propongono'
    assert T.medici_proposti(s, 'Tariffario generale') == []
    prest = s.scalars(select(Prestazione)).all()
    def p(nome, modalita=''):
        return T.prestazione_proposta({'nome': nome, 'modalita': modalita}, prest)
    assert p('Gastroscopia') == I['EGDS'], 'gastroscopia = EGDS'
    assert p('COLONSCOPIA') == I['Colonscopia'] and p('Visita di controllo') == I['Controllo']
    assert p('Visita Neurologica') == I['Visita neurologica'] and p('Ecografia della tiroide') == I['Ecografia tiroide']
    assert p('Ozonoterapia') is None and p('1 sede') is None and p('Colonscopia', 'Pacchetto') is None
    s.close()


prova('medici dal nome del tariffario, prestazioni dal nome della voce (sinonimi, articoli), mai i pacchetti',
      b_proposte)


# ================================================================== caricamento
area('caricamento con l\'anteprima')


def carica(C, dati, nome='tariffari.xlsx'):
    r = C.post('/cassa/tariffari', data={'azione': 'carica', 'file': (BytesIO(dati), nome)},
               content_type='multipart/form-data', headers=CASA)
    assert r.status_code == 302 and '/cassa/tariffari/anteprima/' in r.headers['Location'], (r.status_code, avvisi(C))
    return r.headers['Location']


def c_carica():
    S, I, C = mondo()
    dove = carica(C, libro([SEMPLICE, DOPPIO, COMPLETO]))
    t = testo(C.get(dove))
    assert t.count('name="carica_') == 3 and 'Gruppo Fittizi' in t and 'Dott. Esempietti' in t
    # le proposte: i medici spuntati, le prestazioni scelte
    assert 'name="medici_0" value="%d" checked' % I['Fittizi Ugo'] in t and \
        'name="medici_0" value="%d" checked' % I['Fittizi Ada'] in t
    assert 'name="medici_1" value="%d" checked' % I['Esempietti'] in t
    assert 'name="medici_2" value="%d" checked' % I['Testabianca'] in t
    assert '<option value="%d" selected>EGDS</option>' % I['EGDS'] in t
    s = S()
    assert s.scalars(select(Tariffario)).all() == [], 'niente salvato prima della conferma'
    s.close()
    dati = {'azione': 'salva', 'carica_0': '1', 'nome_0': 'Gruppo Fittizi', 'medici_0': [str(I['Fittizi Ugo']), str(I['Fittizi Ada'])],
            'carica_1': '1', 'nome_1': 'Dott. Esempietti', 'medici_1': [str(I['Esempietti'])],
            'prestazione_1_0': str(I['EGDS']), 'prestazione_1_1': str(I['Colonscopia']), 'prestazione_1_2': 'nuova',
            'nome_2': 'non caricato', 'medici_2': [str(I['Testabianca'])],
            'prestazione_0_1': str(I['Controllo']), 'prestazione_0_0': '99999'}
    r = C.post(dove, data=dati, headers=CASA)
    assert r.status_code == 302 and r.headers['Location'].endswith('/cassa/tariffari'), r.status_code
    a = avvisi(C)
    assert 'Tariffari caricati: Gruppo Fittizi (4 voci, 2 medici); Dott. Esempietti (7 voci, 1 medico).' in a and \
        'Prestazioni nuove create: 1' in a, a
    s = S()
    tar = {t.nome: t for t in s.scalars(select(Tariffario))}
    assert set(tar) == {'Gruppo Fittizi', 'Dott. Esempietti'}, 'il terzo non spuntato non si carica'
    e = tar['Dott. Esempietti']
    assert e.id_medici == {I['Esempietti']} and e.origine == 'tariffari.xlsx' and e.attivo
    collegate = {v.nome: v.prestazione.nome if v.prestazione else None for v in e.voci}
    assert collegate['Gastroscopia'] == 'EGDS' and collegate['Colonscopia'] == 'Colonscopia' and \
        collegate['Polipectomia'] == 'Polipectomia' and collegate['1 sede'] is None, collegate
    assert s.scalars(select(Prestazione).where(Prestazione.nome == 'Polipectomia')).one().durata_min == T.DURATA_NUOVA
    g = tar['Gruppo Fittizi']
    assert g.id_medici == {I['Fittizi Ugo'], I['Fittizi Ada']}
    assert [v.prestazione_id for v in g.voci] == [None, I['Controllo'], None, None], 'un id che non esiste non si collega'
    s.close()
    # di nuovo lo stesso tariffario: si sostituisce, niente doppioni; il file usato non c'e' piu'
    assert C.post(dove, data=dati, headers=CASA).status_code == 302 and 'non c\'è più' in avvisi(C)
    dove = carica(C, libro([('Tariffario', [('TARIFFARIO GRUPPO FITTIZI',), ('Prestazione', 'Prezzo'), ('Visita', 99)])]))
    assert 'C\'è già il tariffario «Gruppo Fittizi» (4 voci)' in testo(C.get(dove))
    C.post(dove, data={'azione': 'salva', 'carica_0': '1', 'nome_0': 'gruppo  fittizi', 'medici_0': [str(I['Fittizi Ada'])]},
           headers=CASA)
    s = S()
    tutti = s.scalars(select(Tariffario)).all()
    assert len(tutti) == 2 and len(s.scalars(select(VoceTariffario)).all()) == 7 + 1, 'sostituito, non aggiunto'
    g = next(t for t in tutti if t.id == tar['Gruppo Fittizi'].id)
    assert [v.nome for v in g.voci] == ['Visita'] and g.id_medici == {I['Fittizi Ada']}
    s.close()
    # annulla
    dove = carica(C, libro([SEMPLICE]))
    C.post(dove, data={'azione': 'annulla'}, headers=CASA)
    assert 'annullato' in avvisi(C) and C.get(dove).status_code == 302
    # file sbagliati e troppo grandi
    r = C.post('/cassa/tariffari', data={'azione': 'carica', 'file': (BytesIO(b'ciao'), 'x.xlsx')},
               content_type='multipart/form-data', headers=CASA)
    assert r.status_code == 302 and 'non si apre' in avvisi(C)
    r = C.post('/cassa/tariffari', data={'azione': 'carica', 'file': (BytesIO(b'x' * (T.MASSIMO_FILE + 1)), 'x.xlsx')},
               content_type='multipart/form-data', headers=CASA)
    assert 'supera 5 MB' in avvisi(C)
    assert C.get('/cassa/tariffari/anteprima/' + '0' * 32).status_code == 302


prova('caricamento: anteprima con le proposte, conferma con medici e prestazioni (anche nuove), sostituzione dello '
      'stesso tariffario, annulla, file sbagliati', c_carica)


# ================================================================== prezzi
area('il prezzo proposto nella prenotazione')


def tariffario(S, nome, medici, voci, attivo=True):
    s = S()
    t = Tariffario(nome=nome, attivo=attivo)
    for oid in medici:
        t.medici.append(TariffarioMedico(operatore_id=oid))
    for i, (nome_v, pid, cent, modalita) in enumerate(voci):
        t.voci.append(VoceTariffario(nome=nome_v, prestazione_id=pid, importo_cent=cent, modalita=modalita, ordine=i))
    s.add(t)
    s.commit()
    tid = t.id
    s.close()
    return tid


def d_prezzi():
    S, I, C = mondo()
    tariffario(S, 'Dott. Esempietti', [I['Esempietti']], [('Gastroscopia', I['EGDS'], 21000, ''),
                                                          ('Colonscopia', I['Colonscopia'], 29000, 'Singola'),
                                                          ('Colonscopia', I['Colonscopia'], 99000, 'Pacchetto')])
    tariffario(S, 'Vecchio', [I['Provolo']], [('Gastroscopia', I['EGDS'], 1000, '')], attivo=False)
    s = S()
    s.add(Tariffa(prestazione_id=I['EGDS'], convenzione='Assicurazione Prova', importo_cent=12000))
    s.commit()
    m = cassa.mappa_tariffe(s)
    assert m[str(I['EGDS'])] == {'': '150,00', 'assicurazione prova': '120,00', 'medico:%d' % I['Esempietti']: '210,00'}, m
    assert m[str(I['Colonscopia'])] == {'': '250,00', 'medico:%d' % I['Esempietti']: '290,00'}, 'il pacchetto non vale'
    assert 'medico:%d' % I['Provolo'] not in m[str(I['EGDS'])], 'un tariffario spento non vale'
    tp = cassa.tariffa_per
    assert tp(s, I['EGDS'], '', I['Esempietti']) == 21000 and tp(s, I['EGDS'], '', I['Provolo']) == 15000
    assert tp(s, I['EGDS'], 'assicurazione  prova', I['Esempietti']) == 12000, 'prima la convenzione'
    assert tp(s, I['EGDS'], 'Privato', I['Esempietti']) == 21000 and tp(s, I['Controllo'], '', I['Esempietti']) is None
    s.close()
    # nella pagina dell'appuntamento le tariffe arrivano al modulo
    t = testo(C.get('/appuntamento?data=2026-12-07&ora=10:00&risorsa=1&struttura=1'))
    assert '&#34;medico:%d&#34;: &#34;210,00&#34;' % I['Esempietti'] in t or '"medico:%d": "210,00"' % I['Esempietti'] in t, \
        t[t.find('data-tariffe'):t.find('data-tariffe') + 300]


prova('prima la convenzione, poi il tariffario del medico, poi il listino; spenti e pacchetti non contano; '
      'il modulo di prenotazione riceve i prezzi', d_prezzi)


# ================================================================== scheda
area('scheda, controllo, stampa, anagrafiche')


def e_scheda():
    S, I, C = mondo()
    tid = tariffario(S, 'Dott. Esempietti', [I['Esempietti']], [('Gastroscopia', I['EGDS'], 21000, ''),
                                                                ('Polipectomia', None, 14000, '')])
    t = testo(C.get('/cassa/tariffari/%d' % tid))
    assert t.count('name="voce"') == 2 + T.NUOVE_RIGHE and 'value="210,00"' in t
    s = S()
    ids = [v.id for v in s.get(Tariffario, tid).voci]
    s.close()
    base = {'azione': 'salva', 'nome': 'Dott.ssa Esempietti', 'attivo': '1', 'note': 'Prezzi IVA esente.',
            'medici': [str(I['Esempietti']), str(I['Provolo']), '99999'],
            'voce_id': [str(ids[0]), str(ids[1]), '', '', ''],
            'sezione': ['Esami', 'Esami', 'Istologico', '', ''], 'voce': ['Gastroscopia', 'Polipectomia', '1 sede', '', ''],
            'modalita': ['', '', '', '', ''], 'prezzo': ['220', '140,00', '€ 60', '', ''], 'dettagli': ['', '', 'per sede', '', ''],
            'prestazione': [str(I['EGDS']), '', '', '', ''], 'togli': [str(ids[1])]}
    r = C.post('/cassa/tariffari/%d' % tid, data=base, headers=CASA)
    assert r.status_code == 302 and 'salvato: 2 voci' in avvisi(C)
    s = S()
    x = s.get(Tariffario, tid)
    assert (x.nome, x.note, x.id_medici) == ('Dott.ssa Esempietti', 'Prezzi IVA esente.', {I['Esempietti'], I['Provolo']})
    assert [(v.sezione, v.nome, v.importo_cent, v.dettagli, v.prestazione_id) for v in x.voci] == [
        ('Esami', 'Gastroscopia', 22000, '', I['EGDS']), ('Istologico', '1 sede', 6000, 'per sede', None)]
    s.close()
    # un prezzo sbagliato o una voce senza nome: niente cambia
    sbagliato = dict(base, prezzo=['22o', '', '', '', ''], togli=[])
    C.post('/cassa/tariffari/%d' % tid, data=sbagliato, headers=CASA)
    assert 'prezzo «22o» non valido' in avvisi(C)
    C.post('/cassa/tariffari/%d' % tid, data=dict(base, voce=['', '', '', '', ''], togli=[]), headers=CASA)
    assert 'manca il nome della voce' in avvisi(C)
    s = S()
    assert [v.importo_cent for v in s.get(Tariffario, tid).voci] == [22000, 6000], 'niente cambiato dopo un errore'
    s.close()
    # spento: i prezzi non si propongono piu'
    C.post('/cassa/tariffari/%d' % tid, data=dict(base, attivo='', togli=[]), headers=CASA)
    s = S()
    assert not s.get(Tariffario, tid).attivo and T.prezzi_dei_medici(s) == {}
    s.close()
    # la stampa: testata, sezioni, prezzi, note
    t = testo(C.get('/cassa/tariffari/%d/stampa' % tid))
    assert 'Tariffario · Dott.ssa Esempietti' in t and '<h2 class="sezione-stampa">Esami</h2>' in t and \
        '€ 220,00' in t and 'Prezzi IVA esente.' in t and 'Clinica Prova' in t
    assert C.get('/cassa/tariffari/99999').status_code == 404 and C.get('/cassa/tariffari/99999/stampa').status_code == 404
    # elimina
    C.post('/cassa/tariffari/%d' % tid, data={'azione': 'elimina'}, headers=CASA)
    s = S()
    assert s.scalars(select(Tariffario)).all() == [] and s.scalars(select(TariffarioMedico)).all() == [] and \
        s.scalars(select(VoceTariffario)).all() == []
    s.close()
    # nuovo a mano
    r = C.post('/cassa/tariffari', data={'azione': 'nuovo', 'nome': 'Dott. Provolo'}, headers=CASA)
    assert r.status_code == 302 and '/cassa/tariffari/' in r.headers['Location']


def e_controllo():
    S, I, C = mondo()
    tariffario(S, 'Dott. Esempietti', [I['Esempietti']], [('Gastroscopia', I['EGDS'], 21000, '')])
    tariffario(S, 'Gruppo Fittizi', [I['Fittizi Ugo'], I['Fittizi Ada']], [('Visita', None, 10000, '')])
    tariffario(S, 'Dott.ssa Testabianca', [I['Testabianca']], [('Visita', I['Visita neurologica'], 12000, '')], attivo=False)
    tariffario(S, 'Senza nessuno', [], [('Visita', I['Controllo'], 5000, '')])
    tariffario(S, 'Doppio', [I['Esempietti']], [('Gastroscopia', I['EGDS'], 19000, '')])
    s = S()
    c = T.controllo_medici(s)
    stati = {r['medico'].etichetta: r['stato'] for r in c['righe']}
    assert stati == {'Esempietti Rita': 'attivo', 'Fittizi Ada': 'scollegato', 'Fittizi Ugo': 'scollegato',
                     'Provolo Gino': 'nessuno', 'Testabianca Lia': 'spento'}, stati
    assert 'Spento Dino' not in stati, 'solo i medici attivi'
    r = next(x for x in c['righe'] if x['medico'].cognome == 'Esempietti')
    assert r['doppi'] == ['EGDS'] and 'Due prezzi diversi per EGDS' in r['testo'] and r['n_prestazioni'] == 1
    assert [t.nome for t in c['senza_medici']] == ['Senza nessuno'] and c['con_tariffario'] == 1
    assert T.prezzi_dei_medici(s)[(I['Esempietti'], I['EGDS'])] == (21000, 'Dott. Esempietti'), 'vale il primo'
    s.close()
    t = testo(C.get('/cassa/tariffari'))
    assert 'stato-tariffario-attivo' in t and 'stato-tariffario-scollegato' in t and 'non ha nessun medico' in t
    assert '1 medico su 5 con il tariffario attivo' in t, t[t.find('Per ogni medico'):t.find('Per ogni medico') + 300]
    # la scheda del medico in Anagrafiche
    t = testo(C.get('/anagrafiche/medici/%d' % I['Esempietti']))
    assert '<h2>Tariffario</h2>' in t and 'Dott. Esempietti' in t and 'il prezzo si propone da solo per 1 prestazione' in t
    t = testo(C.get('/anagrafiche/medici/%d' % I['Provolo']))
    assert '<h2>Tariffario</h2>' in t and 'Nessun tariffario: vale il listino.' in t and 'Email automatiche' in t
    # le protezioni: un medico o una prestazione di un tariffario non si eliminano
    C.post('/anagrafiche/medici/%d' % I['Esempietti'], data={'azione': 'elimina'}, headers=CASA)
    assert 'non si può eliminare' in avvisi(C)
    C.post('/anagrafiche/prestazioni/%d' % I['EGDS'], data={'azione': 'elimina'}, headers=CASA)
    assert 'usata da 2 voci dei tariffari' in avvisi(C)
    s = S()
    assert s.get(Operatore, I['Esempietti']) is not None and s.get(Prestazione, I['EGDS']) is not None
    s.close()
    # i collegamenti alle pagine
    assert '/cassa/tariffari' in testo(C.get('/cassa/listino')) and '/cassa/tariffari' in testo(C.get('/impostazioni'))


def e_schema():
    import sqlite3
    S, I, C = mondo()
    p = os.path.join(PROVVISORIA, 'db_%d.db' % _n[0])
    c = sqlite3.connect(p)
    tabelle = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {'tariffari', 'tariffari_medici', 'voci_tariffario'} <= tabelle and VERSIONE_SCHEMA == 12
    # un database della 1.12.5 (schema 11): le tabelle nuove arrivano, vuote, dopo la copia di sicurezza
    for t in ('voci_tariffario', 'tariffari_medici', 'tariffari'):
        c.execute('DROP TABLE %s' % t)
    c.execute("UPDATE impostazioni SET valore = '11' WHERE chiave = 'versione_schema'")
    c.commit()
    c.close()
    S2 = crea_sessione('sqlite:///' + p)
    assert S2.versione_precedente == 11 and any('prima-della-versione-12' in m for m in S2.migrazioni), S2.migrazioni
    s = S2()
    assert s.scalars(select(Tariffario)).all() == [] and s.scalars(select(Operatore)).first() is not None
    s.close()


prova('scheda: cambia, aggiungi, togli, medici, note; errori senza cambiare niente; spento; stampa; elimina; nuovo',
      e_scheda)
prova('controllo dei medici (attivo, senza collegamenti, spento, nessuno, doppi prezzi, senza medici), riquadro nella '
      'scheda del medico, protezioni in Anagrafiche, collegamenti', e_controllo)
prova('schema 12: tabelle nuove, aggiornamento dalla 11 con la copia di sicurezza', e_schema)


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
    rotte = [e for e in esiti if e[0] != 'OK']
    if rotte or os.environ.get('DETTAGLIO'):
        print('\nDettaglio:')
        for e in esiti:
            if e[0] != 'OK' or os.environ.get('DETTAGLIO'):
                print('  %-6s [%s] %s\n         %s' % (e[0], e[1], e[2], e[3]))
    print('\n%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(rotte), len(rotte)))
    shutil.rmtree(PROVVISORIA, ignore_errors=True)
    sys.exit(1 if rotte else 0)
