# -*- coding: utf-8 -*-
"""Prove della 1.4.5: le segnalazioni di una revisione esterna del codice
(Gemini, 27/09/2026), una per una.

- "confermate": il difetto c'era; la prova lo riproduce e controlla la
  correzione;
- "respinte": il comportamento segnalato e' voluto o gia' protetto; la prova
  fissa quello giusto, cosi' una "correzione" futura che lo rompe si vede.

Dove si puo' il risultato si confronta con un calcolo fatto a parte (un
oracolo) e non con quello che il programma stesso ha prodotto."""
import io
import os
import re
import shutil
import sys
import threading
import traceback
from datetime import date, datetime, time, timedelta
from html import unescape

from sqlalchemy import select

import servizi
import sala
import cruscotto
import importa
import anagrafiche
import pazienti
import viste
import app as A
from modelli import (crea_sessione, Struttura, Risorsa, Operatore, Appuntamento, Prestazione, Paziente,
                     Turno, Appunto, Attesa, leggi_impostazione)

A.app.config['TESTING'] = True
CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = os.path.join(CARTELLA, 'prove_145_tmp')
shutil.rmtree(PROVVISORIA, ignore_errors=True)
os.makedirs(PROVVISORIA)
esiti, _area, _n = [], [''], [0]
OGGI = date.today()
# un martedi nel futuro, lontano dai festivi
MAR = OGGI + timedelta(days=(1 - OGGI.weekday()) % 7 + 14)
while servizi.calendario.festivo(MAR) or any(servizi.calendario.festivo(MAR + timedelta(days=7 * k))
                                             for k in range(1, 4)):
    MAR += timedelta(days=7)
LUNEDI = MAR - timedelta(days=1)


def area(nome):
    _area[0] = nome


def prova(nome, f):
    try:
        esiti.append(('OK', _area[0], nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', _area[0], nome, str(e) or 'asserzione fallita'))
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


def mondo():
    """Primo avvio (cinque ambulatori e una sala endoscopia), una sala
    operatoria, due medici."""
    S = crea_sessione('sqlite:///' + percorso_nuovo())
    s = S()
    servizi.prepara_primo_avvio(s)
    s.add(Risorsa(nome='Sala A', tipo='SALA_OPERATORIA', struttura_id=1, ordine=10))
    s.add_all([Operatore(cognome='Borrelli', nome='Ugo'), Operatore(cognome='Lippi', nome='Anna')])
    s.commit()
    s.close()
    return S, collega(S)


def ids(S):
    s = S()
    d = {r.nome: r.id for r in s.scalars(select(Risorsa))}
    d.update({o.cognome: o.id for o in s.scalars(select(Operatore))})
    d.update({p.nome: p.id for p in s.scalars(select(Prestazione))})
    s.close()
    return d


def nuovo_app(S, stanza, medico, inizio, minuti=60, stato='PRENOTATO', **altro):
    s = S()
    a = Appuntamento(risorsa_id=stanza, operatore_id=medico, inizio=inizio,
                     fine=inizio + timedelta(minutes=minuti), stato=stato, **altro)
    s.add(a)
    s.commit()
    aid = a.id
    s.close()
    return aid


def html(r):
    return r.get_data(as_text=True)


def testo(r):
    return ' '.join(unescape(re.sub(r'<[^>]+>', ' ', html(r))).split())


def avvisi(C):
    with C.session_transaction() as sess:
        m = sess.get('_flashes', [])
        sess['_flashes'] = []
    return unescape(re.sub(r'<[^>]+>', '', ' '.join(str(x[1]) for x in m)))


def modulo_app(I, stanza, medico, g, ora='09:00', **altro):
    d = {'risorsa': str(I[stanza]), 'operatore': str(I[medico]), 'prestazione': str(I['Intervento']),
         'data': g.isoformat(), 'ora': ora, 'durata': '60', 'struttura': '1', 'paziente': 'Rossi',
         'nome_paziente': 'Marta', 'telefono': '3331112222', 'tipo': '', 'convenzione': '', 'importo': '',
         'note': '', 'degenza': ''}
    d.update(altro)
    return d


def agenda(righe_dati):
    """Un foglio d'agenda semplice: una riga per appuntamento."""
    righe_ = [['Data', 'Ora', 'Durata', 'Stanza', 'Medico', 'Paziente', 'Telefono', 'Importo']]
    for r in righe_dati:
        righe_.append(list(r))
    return importa.analizza({'nome': 'agenda', 'righe': righe_})


def piano_di(S, righe_dati, **opzioni):
    s = S()
    a = agenda(righe_dati)
    f = {'struttura': '1'}
    f.update(opzioni)
    return s, importa.prepara(s, a, importa.opzioni_da(f, a))


def per_riga(piano):
    return {r['n']: r for r in piano['righe']}


G = MAR.strftime('%d/%m/%Y')


# ============================================================ confermate
area('segnalazioni confermate')


def c01_tre_righe_stessa_ora():
    """BUG 01. Tre righe nella stessa stanza alla stessa ora: la terza
    risultava 'nuova' in anteprima e poi, al momento di scrivere, spariva
    fra gli scartati senza diventare un appunto."""
    S, C = mondo()
    s, piano = piano_di(S, [
        (G, '09:00', 30, 'Ambulatorio 1', 'Borrelli', 'Alfa Primo', '3330000001', None),
        (G, '09:00', 30, 'Ambulatorio 1', 'Borrelli', 'Beta Secondo', '3330000002', None),
        (G, '09:00', 30, 'Ambulatorio 1', 'Borrelli', 'Gamma Terzo', '3330000003', None),
        # una lunga e due che le cadono dentro, una dopo l'altra
        (G, '11:00', 60, 'Ambulatorio 2', 'Lippi', 'Delta Quarto', '3330000004', None),
        (G, '11:30', 15, 'Ambulatorio 2', 'Lippi', 'Epsilon Quinto', '3330000005', None),
        (G, '11:45', 10, 'Ambulatorio 2', 'Lippi', 'Zeta Sesto', '3330000006', None),
        (G, '12:00', 30, 'Ambulatorio 2', 'Lippi', 'Eta Settimo', '3330000007', None),
    ])
    esiti_ = [r['esito'] for r in sorted(piano['righe'], key=lambda r: r['n'])]
    # oracolo: una riga entra se non si sovrappone a nessuna gia' entrata della stessa stanza
    presi, atteso = {}, []
    for r in sorted(piano['righe'], key=lambda r: (r['inizio'], r['n'])):
        k = r['stanza'].id
        if any(r['inizio'] < b['fine'] and b['inizio'] < r['fine'] for b in presi.get(k, [])):
            atteso.append((r['n'], 'conflitto'))
        else:
            presi.setdefault(k, []).append(r)
            atteso.append((r['n'], 'nuovo'))
    atteso = [e for _, e in sorted(atteso)]
    assert esiti_ == atteso, 'anteprima %s, attesi %s' % (esiti_, atteso)
    assert esiti_.count('nuovo') == 3, esiti_
    esito = importa.esegui(s, piano, 'agenda.xlsx')
    assert esito['appuntamenti'] == 3 and esito['appunti'] == 4 and not esito['scartati'], esito
    s.close()
    return 'anteprima e scrittura coincidono: 3 in agenda, 4 da confermare, nessuna persa'


def c02_serie_con_degenza():
    """BUG 02. La serie copiava tutto dal primo appuntamento tranne degenza e
    notti (dalla 1.4.3 non stanno piu' fra i campi in piu')."""
    S, C = mondo()
    I = ids(S)
    r = C.post('/appuntamento', data=modulo_app(I, 'Sala A', 'Borrelli', MAR, degenza='RICOVERO', notti='2',
                                                 ripeti='1', ripeti_ogni='1', ripeti_unita='settimane',
                                                 ripeti_volte='3'))
    assert r.status_code == 302, 'salvataggio: %s' % avvisi(C)
    s = S()
    apps = s.scalars(select(Appuntamento).order_by(Appuntamento.inizio)).all()
    assert len(apps) == 3 and len({a.serie for a in apps}) == 1, [(a.inizio, a.serie) for a in apps]
    assert [(a.degenza, a.notti) for a in apps] == [('RICOVERO', 2)] * 3, [(a.degenza, a.notti) for a in apps]
    assert all(not a.checklist for a in apps), 'la checklist non si copia: ogni intervento ha la sua'
    notti = sala.notti_occupate(s, 1, MAR, MAR + timedelta(days=16))
    occupate = sorted(n for n, x in notti.items() if x)
    attese = sorted(MAR + timedelta(days=7 * k + i) for k in range(3) for i in range(2))
    s.close()
    assert occupate == attese, 'letti: %s invece di %s' % (occupate, attese)


def c03_stanza_con_soli_disdetti():
    """BUG 03. Una stanza con appuntamenti futuri tutti disdetti non si
    poteva disattivare; con uno ancora prenotato resta il blocco."""
    S, C = mondo()
    I = ids(S)
    nuovo_app(S, I['Ambulatorio 3'], I['Borrelli'], datetime.combine(MAR, time(9, 0)), stato='DISDETTO')
    campi = {'nome': 'Ambulatorio 3', 'tipo': 'AMBULATORIO', 'struttura': '1', 'ordine': '3'}
    r = C.post('/anagrafiche/stanze/%d' % I['Ambulatorio 3'], data=campi)
    assert r.status_code == 302, 'disattivazione rifiutata: %s' % testo(r)[:300]
    s = S()
    assert s.get(Risorsa, I['Ambulatorio 3']).attiva is False
    s.close()
    nuovo_app(S, I['Ambulatorio 4'], I['Borrelli'], datetime.combine(MAR, time(9, 0)))
    nuovo_app(S, I['Ambulatorio 4'], I['Borrelli'], datetime.combine(MAR, time(10, 0)), stato='DISDETTO')
    campi.update(nome='Ambulatorio 4', ordine='4')
    r = C.post('/anagrafiche/stanze/%d' % I['Ambulatorio 4'], data=campi)
    assert r.status_code == 200 and 'ha 1 appuntamento da oggi in poi' in testo(r), testo(r)[:300]
    s = S()
    assert s.get(Risorsa, I['Ambulatorio 4']).attiva is True
    s.close()


def c04_assenza_da_oggi():
    """BUG 04. Assenza che comincia oggi: l'elenco "da spostare" contava anche
    gli appuntamenti di stamattina gia' passati, lo spostamento in blocco no."""
    adesso = datetime.now().replace(second=0, microsecond=0)
    if adesso.time() < time(0, 30) or adesso.time() > time(22, 0):
        return 'saltata: serve un orario con un prima e un dopo nello stesso giorno'
    S, C = mondo()
    I = ids(S)
    passato = nuovo_app(S, I['Ambulatorio 1'], I['Borrelli'], adesso - timedelta(minutes=20), minuti=10)
    futuro = nuovo_app(S, I['Ambulatorio 1'], I['Borrelli'], adesso + timedelta(minutes=60), minuti=10)
    domani = nuovo_app(S, I['Ambulatorio 1'], I['Borrelli'],
                       datetime.combine(OGGI + timedelta(days=1), time(9, 0)), minuti=10)
    s = S()
    elenco = {a.id for a in anagrafiche.appuntamenti_da_spostare(s, OGGI, OGGI + timedelta(days=1),
                                                                operatore_id=I['Borrelli'])}
    s.close()
    pagina = html(C.get('/sposta?medico=%d&dal=%s&al=%s' % (I['Borrelli'], OGGI, OGGI + timedelta(days=1))))
    in_pagina = {int(x) for x in re.findall(r'href="/appuntamento/(\d+)"', pagina)}
    assert elenco == {futuro, domani}, 'da spostare: %s (passato=%d)' % (sorted(elenco), passato)
    assert in_pagina == elenco, 'la pagina dello spostamento ne mostra altri: %s' % sorted(in_pagina)


def c07_stesso_medico_scritto_in_due_modi():
    """BUG 07. "ROSSETTI" e "MARCO ROSSETTI" diventano un solo medico nuovo,
    ma il controllo "stesso medico in due stanze alla stessa ora" non lo
    vedeva."""
    S, C = mondo()
    s, piano = piano_di(S, [
        (G, '10:00', 30, 'Ambulatorio 1', 'ROSSETTI', 'Alfa Primo', '3330000001', None),
        (G, '10:00', 30, 'Ambulatorio 2', 'MARCO ROSSETTI', 'Beta Secondo', '3330000002', None),
        (G, '11:00', 30, 'Ambulatorio 1', 'ROSSETTI', 'Gamma Terzo', '3330000003', None),
    ])
    medici = [(m['cognome'], m['nome']) for m in piano['nuovi_medici']]
    assert medici == [('Rossetti', 'Marco')], medici
    assert piano['medici_doppi'] == 1, 'medici doppi: %d' % piano['medici_doppi']
    doppie = [r['n'] for r in piano['righe'] if any('anche in un\'altra stanza' in x for x in r['avvisi'])]
    assert len(doppie) == 1, doppie
    esito = importa.esegui(s, piano, 'agenda.xlsx')
    assert esito['medici'] == 1 and esito['appuntamenti'] == 3, esito
    s.close()


def c08_occupata_dopo_l_anteprima():
    """BUG 08. Se la stanza veniva occupata fra l'anteprima e l'importazione,
    la riga finiva fra gli scartati anche con "gli scarti diventano appunti"."""
    S, C = mondo()
    I = ids(S)
    s, piano = piano_di(S, [(G, '09:00', 30, 'Ambulatorio 1', 'Borrelli', 'Alfa Primo', '3330000001', None),
                            (G, '10:00', 30, 'Ambulatorio 1', 'Borrelli', 'Beta Secondo', '3330000002', None)])
    assert [r['esito'] for r in piano['righe']] == ['nuovo', 'nuovo']
    # nel frattempo, dal modulo di prenotazione
    nuovo_app(S, I['Ambulatorio 1'], I['Lippi'], datetime.combine(MAR, time(9, 15)), minuti=20)
    esito = importa.esegui(s, piano, 'agenda.xlsx')
    assert esito['appuntamenti'] == 1 and esito['appunti'] == 1 and not esito['scartati'], esito
    x = s.scalars(select(Appunto)).one()
    assert x.paziente is not None and x.paziente.cognome == 'Alfa' and 'occupata' in x.testo.lower(), x.testo
    assert x.testo[0].isupper()
    s.close()
    # e l'appunto da una riga il cui motivo era solo l'indicazione "sceglierla in alto"
    S, C = mondo()
    s = S()
    r = {'motivo': ': sceglierla in alto, "Stanze"', 'inizio': datetime.combine(MAR, time(9, 0)),
         'fine': datetime.combine(MAR, time(9, 30)), 'n': 7, 'paziente': None}
    x, _ = importa.crea_appunto(s, r, s.get(Struttura, 1), importa.IndicePazienti(s), {}, {}, {}, 'f.xlsx')
    assert x.testo and x.testo[0].isupper(), repr(x.testo)
    s.close()


def c09_importi_come_il_modulo():
    """BUG 09. L'importazione accettava fino a un milione, il modulo fino a
    centomila: un appuntamento importato con 150.000 non si poteva piu'
    salvare dal modulo. Ora vale lo stesso limite."""
    campioni = ['0', '80', '80,5', '80,50', '1.250,50', '1250.5', '99999,99', '100000', '100.000,00',
                '100000,01', '150000', '1.000.000', '12,345', '1e3', '-5', 'abc', '€ 80', '80 €']
    diversi = []
    for t in campioni:
        try:
            m = A.leggi_importo(t)
        except ValueError:
            m = 'no'
        try:
            i = importa.come_importo(t)
        except ValueError:
            i = 'no'
        if m != i:
            diversi.append((t, m, i))
    for v in (100000, 100000.01, 150000, 80.5):
        try:
            i = importa.come_importo(v)
        except ValueError:
            i = 'no'
        atteso = int(round(v * 100)) if v <= 100000 else 'no'
        if i != atteso:
            diversi.append((v, atteso, i))
    assert not diversi, 'modulo e importazione leggono diverso: %s' % diversi
    S, C = mondo()
    s, piano = piano_di(S, [(G, '09:00', 30, 'Ambulatorio 1', 'Borrelli', 'Alfa Primo', '3330000001', 150000)])
    r = piano['righe'][0]
    assert r['importo'] is None and 'importo non valido: tolto' in r['avvisi'], (r['importo'], r['avvisi'])
    s.close()


def c10_telefono_corto_in_prenotazione():
    """BUG 10a. Il modulo di prenotazione (e la lista d'attesa) accettavano un
    telefono di due cifre, che poi la scheda del paziente rifiuta."""
    S, C = mondo()
    I = ids(S)
    r = C.post('/appuntamento', data=modulo_app(I, 'Ambulatorio 1', 'Borrelli', MAR, telefono='12'))
    assert r.status_code == 200 and 'servono almeno 6 cifre' in avvisi(C) + testo(r), 'telefono corto accettato'
    s = S()
    assert s.scalars(select(Appuntamento)).first() is None and s.scalars(select(Paziente)).first() is None
    s.close()
    r = C.post('/appuntamento', data=modulo_app(I, 'Ambulatorio 1', 'Borrelli', MAR, telefono=''))
    assert r.status_code == 302, 'senza telefono si deve poter prenotare: %s' % avvisi(C)
    r = C.post('/attesa/nuova', data={'paziente': 'Verdi', 'nome_paziente': 'Lia', 'telefono': '12'})
    assert 'servono almeno 6 cifre' in avvisi(C) + testo(r), 'lista d\'attesa: telefono corto accettato'
    s = S()
    assert s.scalars(select(Attesa)).first() is None
    s.close()
    r = C.post('/attesa/nuova', data={'paziente': 'Verdi', 'nome_paziente': 'Lia', 'telefono': '333 123 9999'})
    assert r.status_code == 302, 'lista d\'attesa con un telefono giusto: %s' % avvisi(C)
    s = S()
    assert len(s.scalars(select(Attesa)).all()) == 1
    s.close()


def c10_stessa_persona_scritta_diversa():
    """BUG 10b. Senza scegliere dall'elenco, la prenotazione riconosceva la
    scheda solo con il cognome identico (maiuscole a parte) e il primo
    telefono: accenti, apostrofi curvi o il secondo telefono creavano un
    doppione."""
    S, C = mondo()
    s = S()
    nigro = Paziente(cognome='NIGRÒ', nome='ANNA', telefono='3331234567', telefono2='081 555 1234')
    dangelo = Paziente(cognome="D'ANGELO", nome='Rosa', telefono='+39 328 111 2233')
    senza = Paziente(cognome='Rossi', nome='')                   # scheda senza telefono
    s.add_all([nigro, dangelo, senza])
    s.commit()
    casi = [('Nigrò', 'Anna', '3331234567', nigro.id), ('nigro', '', '0815551234', nigro.id),
            ('D’Angelo', 'Rosa', '3281112233', dangelo.id), ('D Angelo', '', '328 111 2233', dangelo.id),
            ('Nigrò', 'Marco', '3331234567', None),      # stesso telefono, altro nome: altra persona
            ('Nigrò', 'Anna', '3339999999', None),       # altro telefono: altra scheda
            # un "telefono" senza cifre non e' un telefono uguale a quello vuoto: prima
            # la prenotazione finiva sulla scheda di un altro Rossi senza telefono
            ('Rossi', 'Marta', 'non ha telefono', None)]
    vecchi = (nigro.id, dangelo.id, senza.id)
    sbagliati = []
    for cognome, nome, tel, atteso in casi:
        p = pazienti.trova_o_crea(s, None, cognome, nome, tel)
        giusto = p.id == atteso if atteso is not None else p.id not in vecchi
        if not giusto:
            sbagliati.append((cognome, nome, tel, 'trovato %s' % p.id, 'atteso %s' % (atteso or 'nuovo')))
        s.rollback()
    s.close()
    assert not sbagliati, sbagliati


def c12_settimana_medico_intervento_lungo():
    """BUG 12. Nella settimana di un medico, le mezz'ore occupate da un
    appuntamento lungo comparivano come "libero" (con il link per prenotare)."""
    S, C = mondo()
    I = ids(S)
    s = S()
    s.add(Turno(operatore_id=I['Borrelli'], risorsa_id=I['Ambulatorio 1'], giorno_settimana=MAR.weekday(),
                ora_inizio=time(9, 0), ora_fine=time(13, 0), valido_da=OGGI))
    s.commit()
    s.close()
    nuovo_app(S, I['Ambulatorio 1'], I['Borrelli'], datetime.combine(MAR, time(9, 0)), minuti=90)
    nuovo_app(S, I['Ambulatorio 2'], I['Borrelli'], datetime.combine(MAR, time(11, 0)), minuti=40)
    s = S()
    v = servizi.settimana_medico(s, LUNEDI, I['Borrelli'], 1)
    s.close()
    k = v['giorni'].index(MAR)
    stato = {}
    for riga in v['righe']:
        c = riga['celle'][k]
        stato[riga['ora'].strftime('%H:%M')] = 'occupata' if c['apps'] else ('libera' if c['turno'] else '-')
    # oracolo: una fascia e' libera se sta nel turno e nessun appuntamento del medico la tocca
    atteso = {}
    for ora in stato:
        f = datetime.combine(MAR, datetime.strptime(ora, '%H:%M').time())
        if ora in ('09:00', '11:00'):
            atteso[ora] = 'occupata'
        elif any(f < datetime.combine(MAR, a) + timedelta(minutes=m) and datetime.combine(MAR, a) < f
                 for a, m in ((time(9, 0), 90), (time(11, 0), 40))):
            atteso[ora] = '-'
        elif time(9, 0) <= f.time() < time(13, 0):
            atteso[ora] = 'libera'
        else:
            atteso[ora] = '-'
    diversi = {o: (stato[o], atteso[o]) for o in stato if stato[o] != atteso[o]}
    assert not diversi, 'fasce sbagliate (trovato, atteso): %s' % diversi
    pagina = html(C.get('/settimana/%s?struttura=1&medico=%d' % (MAR, I['Borrelli'])))
    for ora in ('09:30', '10:00', '11:30'):
        assert 'data=%s&amp;ora=%s' % (MAR, ora) not in pagina, 'link "libero" alle %s' % ora
    assert 'data=%s&amp;ora=10:30' % MAR in pagina, 'alle 10:30 la fascia e\' libera'


def c13_importo_zero_non_da_incassare():
    """BUG 13 (in parte). Un arrivato con importo 0 (gratuito) restava "da
    incassare" in Oggi e in Cassa; la chiusura della giornata no."""
    S, C = mondo()
    I = ids(S)
    adesso = datetime.now().replace(second=0, microsecond=0)
    base = datetime.combine(OGGI, time(0, 1))
    gratis = nuovo_app(S, I['Ambulatorio 1'], I['Borrelli'], base, minuti=5, stato='ARRIVATO', importo_cent=0)
    pagante = nuovo_app(S, I['Ambulatorio 2'], I['Borrelli'], base, minuti=5, stato='ARRIVATO', importo_cent=8000)
    senza = nuovo_app(S, I['Ambulatorio 3'], I['Borrelli'], base, minuti=5, stato='ARRIVATO')
    s = S()
    q = cruscotto.quadro_di_oggi(s, s.get(Struttura, 1), adesso)
    s.close()
    assert {a.id for a in q['da_incassare']} == {pagante, senza}, [a.id for a in q['da_incassare']]
    pagina = html(C.get('/cassa/%s?struttura=1' % OGGI))
    elenco = pagina.split('<th>Incassa</th>', 1)[1] if '<th>Incassa</th>' in pagina else ''
    in_cassa = {int(x) for x in re.findall(r'href="/appuntamento/(\d+)[^"]*#incasso"', elenco)}
    assert in_cassa == {pagante, senza}, 'in cassa: %s (gratuito=%d)' % (sorted(in_cassa), gratis)


def c15_pazienti_nuovi_per_struttura():
    """BUG 15. Con piu' strutture, "pazienti nuovi" (e "come ci hanno
    conosciuto") contavano i pazienti di tutte."""
    S, C = mondo()
    I = ids(S)
    s = S()
    s.add(Struttura(nome='Altra sede'))
    s.flush()
    s.add(Risorsa(nome='Studio', struttura_id=2, ordine=1))
    ieri = datetime.now() - timedelta(days=1)
    a = Paziente(cognome='Alfa', provenienza='PASSAPAROLA', creato_il=ieri)
    b = Paziente(cognome='Beta', provenienza='INTERNET', creato_il=ieri)
    c = Paziente(cognome='Gamma', creato_il=ieri)              # solo in lista d'attesa
    s.add_all([a, b, c])
    s.commit()
    studio = s.scalars(select(Risorsa.id).where(Risorsa.nome == 'Studio')).one()
    pa, pb = a.id, b.id
    s.close()
    nuovo_app(S, I['Ambulatorio 1'], I['Borrelli'], datetime.combine(MAR, time(9, 0)), paziente_id=pa)
    nuovo_app(S, studio, I['Lippi'], datetime.combine(MAR, time(9, 0)), paziente_id=pb)
    s = S()
    uno = servizi.statistiche(s, 1, OGGI - timedelta(days=3), OGGI)
    due = servizi.statistiche(s, 2, OGGI - timedelta(days=3), OGGI)
    assert (uno['pazienti_nuovi'], due['pazienti_nuovi']) == (1, 1), (uno['pazienti_nuovi'], due['pazienti_nuovi'])
    assert sum(n for _, n in uno['per_provenienza']) == 1
    # con una struttura sola si contano tutti, anche chi non ha ancora un appuntamento
    s.get(Struttura, 2).attiva = False
    s.commit()
    unica = servizi.statistiche(s, 1, OGGI - timedelta(days=3), OGGI)
    s.close()
    assert unica['pazienti_nuovi'] == 3, unica['pazienti_nuovi']


def _aspetta_il_lucchetto(fai):
    """Con il lucchetto preso da un altro salvataggio, la richiesta deve
    aspettare; libero il lucchetto, deve andare a buon fine."""
    fatto = []
    t = threading.Thread(target=lambda: fatto.append(fai()))
    A.LUCCHETTO.acquire()
    try:
        t.start()
        t.join(0.6)
        in_attesa = t.is_alive()
    finally:
        A.LUCCHETTO.release()
    t.join(10)
    return in_attesa, fatto


def c16_eliminazione_sotto_lucchetto():
    """BUG 16. L'eliminazione di un appuntamento (e le impostazioni)
    scrivevano senza il lucchetto che serializza i salvataggi."""
    S, C = mondo()
    I = ids(S)
    aid = nuovo_app(S, I['Ambulatorio 1'], I['Borrelli'], datetime.combine(MAR, time(9, 0)))
    in_attesa, fatto = _aspetta_il_lucchetto(
        lambda: C.post('/appuntamento/%d' % aid, data={'azione': 'elimina'}).status_code)
    assert in_attesa, 'l\'eliminazione non ha aspettato il lucchetto'
    assert fatto == [302], fatto
    s = S()
    assert s.get(Appuntamento, aid) is None
    s.close()
    in_attesa, fatto = _aspetta_il_lucchetto(
        lambda: C.post('/impostazioni', data={'azione': 'testo', 'testo': 'Promemoria {giorno}',
                                              'oggetto': 'Promemoria'}).status_code)
    assert in_attesa, 'le impostazioni non hanno aspettato il lucchetto'
    s = S()
    assert fatto == [302] and leggi_impostazione(s, 'testo_promemoria') == 'Promemoria {giorno}', fatto
    s.close()


def c19_prenota_appunti_senza_errore_500():
    """BUG 19 (difesa). Se il vincolo unico del database scatta mentre si
    mettono in agenda piu' appunti insieme, niente errore 500: un messaggio
    e nessun appuntamento a meta'."""
    S, C = mondo()
    I = ids(S)
    s = S()
    for cognome in ('Alfa', 'Beta'):
        s.add(Appunto(testo='da confermare', giorno=MAR, ora=time(9, 0), durata_min=30, struttura_id=1,
                      risorsa_id=I['Ambulatorio 1'], operatore_id=I['Borrelli'], cognome=cognome))
    s.commit()
    scelti = [str(x.id) for x in s.scalars(select(Appunto))]
    s.close()
    vero = servizi.conflitti
    servizi.conflitti = lambda *a, **k: []          # il controllo che normalmente lo impedisce
    try:
        r = C.post('/da-confermare/prenota', data={'scelti': scelti, 'risorsa': ''})
    finally:
        servizi.conflitti = vero
    assert r.status_code == 302, 'HTTP %d' % r.status_code
    assert 'già presa' in avvisi(C)
    s = S()
    assert s.scalars(select(Appuntamento)).first() is None, 'appuntamenti rimasti a meta\''
    assert all(x.aperto for x in s.scalars(select(Appunto))), 'appunti chiusi senza appuntamento'
    s.close()


def c20_csv_testo_unicode():
    """BUG 20. Excel, "Salva come → Testo Unicode (.txt)", scrive UTF-16 con
    le tabulazioni: si leggeva come cp1252, con un byte nullo ogni lettera."""
    righe_ = [['Cognome', 'Nome', 'Telefono', 'Note'],
              ['NIGRÒ', 'Anna', '3331234567', 'è più comodo il martedì'],
              ["D'ANGELO", 'Rosa', '3281112233', '']]
    testo_ = '\r\n'.join('\t'.join(r) for r in righe_) + '\r\n'
    for codifica in ('utf-16', 'utf-16-be'):
        dati = testo_.encode(codifica) if codifica == 'utf-16' else b'\xfe\xff' + testo_.encode('utf-16-be')
        fogli = importa.leggi_file(dati, 'rubrica.txt')
        letto = [[x or '' for x in r] for r in fogli[0]['righe']]
        assert letto == righe_, '%s: %s' % (codifica, letto[:2])
    # i file di sempre non cambiano
    assert importa.leggi_file(testo_.encode('cp1252'), 'r.csv')[0]['righe'][1][0] == 'NIGRÒ'
    assert importa.leggi_file(b'\xef\xbb\xbf' + testo_.encode('utf-8'), 'r.csv')[0]['righe'][1][3] == \
        'è più comodo il martedì'
    # a capo del Mac (\r) e un byte nullo sperduto: prima, errore 500 al caricamento
    for dati in ('\r'.join(';'.join(r) for r in righe_).encode('cp1252'),
                 ('\r\n'.join(';'.join(r) for r in righe_)).encode('cp1252').replace(b'Rosa', b'Ro\x00sa')):
        letto = [[x or '' for x in r] for r in importa.leggi_file(dati, 'r.csv')[0]['righe']]
        assert letto == righe_, letto
    S, C = mondo()
    r = C.post('/importa', data={'file': (io.BytesIO(testo_.encode('utf-16')), 'rubrica.txt'), 'tipo': ''},
               content_type='multipart/form-data')
    assert r.status_code == 302 and '/importa/' in r.headers['Location'], 'caricamento: HTTP %d' % r.status_code
    anteprima = C.get(r.headers['Location'])
    assert anteprima.status_code == 200 and 'Rosa' in testo(anteprima), 'anteprima: HTTP %d' % anteprima.status_code


prova('BUG 01 · tre righe alla stessa ora: anteprima e scrittura coincidono', c01_tre_righe_stessa_ora)
prova('BUG 02 · la serie copia degenza e notti', c02_serie_con_degenza)
prova('BUG 03 · stanza con soli disdetti: si disattiva', c03_stanza_con_soli_disdetti)
prova('BUG 04 · assenza da oggi: elenco e spostamento in blocco coincidono', c04_assenza_da_oggi)
prova('BUG 07 · stesso medico scritto in due modi: doppio segnalato', c07_stesso_medico_scritto_in_due_modi)
prova('BUG 08 · stanza occupata dopo l\'anteprima: diventa un appunto', c08_occupata_dopo_l_anteprima)
prova('BUG 09 · importi: importazione e modulo con le stesse regole', c09_importi_come_il_modulo)
prova('BUG 10a · telefono di due cifre: rifiutato in prenotazione', c10_telefono_corto_in_prenotazione)
prova('BUG 10b · accenti, apostrofi, secondo telefono: niente doppioni', c10_stessa_persona_scritta_diversa)
prova('BUG 12 · settimana del medico: niente "libero" dentro un intervento', c12_settimana_medico_intervento_lungo)
prova('BUG 13 · importo 0: non e\' da incassare', c13_importo_zero_non_da_incassare)
prova('BUG 15 · pazienti nuovi della struttura scelta', c15_pazienti_nuovi_per_struttura)
prova('BUG 16 · eliminazione e impostazioni aspettano il lucchetto', c16_eliminazione_sotto_lucchetto)
prova('BUG 19 · vincolo del database: messaggio, non errore 500', c19_prenota_appunti_senza_errore_500)
prova('BUG 20 · file "Testo Unicode" di Excel', c20_csv_testo_unicode)


# =============================================================== respinte
area('segnalazioni respinte')


def r05_ritorno_dopo_nuovo_paziente():
    """BUG 05. Il ritorno dopo "nuovo paziente" accetta solo indirizzi che
    cominciano con /appuntamento: non puo' portare fuori dal programma."""
    S, C = mondo()
    for torna in ('//esempio.invalid/x', '/\\esempio.invalid', 'https://esempio.invalid', '/appuntamento\\x'):
        r = C.post('/pazienti/nuovo', data={'cognome': 'Prova%d' % len(torna), 'telefono': '3331234567',
                                            'torna': torna, 'doppione_confermato': '1'})
        luogo = r.headers.get('Location', '')
        assert r.status_code == 302 and luogo.startswith('/') and not luogo.startswith(('//', '/\\')) and \
            'esempio.invalid' not in luogo, (torna, luogo)
    r = C.post('/pazienti/nuovo', data={'cognome': 'Ultimo', 'telefono': '3331230000', 'doppione_confermato': '1',
                                        'torna': '/appuntamento?data=%s&ora=09:00' % MAR})
    assert re.fullmatch(r'/appuntamento\?data=[\d-]+&ora=09:00&paziente_id=\d+', r.headers['Location']), \
        r.headers['Location']


def r06_messaggio_senza_parentesi_sole():
    """BUG 06, prima parte. Nel testo dei messaggi non c'e' nessuna
    sostituzione "a vuoto": i segnaposto vuoti non lasciano parentesi,
    virgole o punti sospesi. La sostituzione proposta al loro posto avrebbe
    tolto proprio quelle per "()", " ." e ".."."""
    S, C = mondo()
    I = ids(S)
    aid = nuovo_app(S, I['Ambulatorio 1'], I['Borrelli'], datetime.combine(MAR, time(9, 0)))
    s = S()
    a = s.get(Appuntamento, aid)
    modello = 'Gentile {paziente}, ({prestazione}) il {giorno} presso {struttura}{indirizzo} ({stanza}, ) .' \
              '{preparazione} Per disdire {recapito}..'
    t = viste.testo_messaggio(a, modello)
    s.close()
    for brutto in ('()', '( ', ' )', ' .', '..', '  ', ', )', '(, '):
        assert brutto not in t, '%r nel messaggio: %s' % (brutto, t)


def r11_degenza_fuori_dalle_sale():
    """BUG 11. La degenza non e' solo delle sale operatorie: il modulo la
    mostra per endoscopia e "altro" (si nasconde solo negli ambulatori, e
    resta visibile se gia' indicata) e il posto letto e' della struttura,
    non della stanza. Toglierla fuori dalle sale perderebbe un dato che
    chi prenota vede, e i letti risulterebbero liberi quando non lo sono."""
    S, C = mondo()
    I = ids(S)
    r = C.post('/appuntamento', data=modulo_app(I, 'Sala endoscopia', 'Lippi', MAR, degenza='NOTTE'))
    assert r.status_code == 302, avvisi(C)
    s = S()
    a = s.scalars(select(Appuntamento)).one()
    assert a.degenza == 'NOTTE'
    assert [x.id for x in sala.notti_occupate(s, 1, MAR, MAR)[MAR]] == [a.id], 'il letto della notte non conta'
    s.close()
    js = open(os.path.join(CARTELLA, 'static', 'gestionale.js'), encoding='utf-8').read()
    assert "tipo !== 'AMBULATORIO'" in js and '!(degenza && degenza.value)' in js


def r14_moduli_segnaposto_sconosciuto():
    """BUG 14. I moduli da stampare hanno un elenco di segnaposto loro
    (quello mostrato sotto il modulo): {recapito} non c'e' e, come ogni
    segnaposto sconosciuto, resta scritto com'e', cosi' si vede. {paziente}
    e' l'etichetta della scheda (cognome e nome), come nei fogli ufficiali."""
    import documenti
    assert 'recapito' not in documenti.SEGNAPOSTO_MODULI
    S, C = mondo()
    I = ids(S)
    s = S()
    p = Paziente(cognome='ESPOSITO', nome='ANNA')
    s.add(p)
    s.commit()
    pid = p.id
    s.close()
    aid = nuovo_app(S, I['Ambulatorio 1'], I['Borrelli'], datetime.combine(MAR, time(9, 0)), paziente_id=pid)
    s = S()
    a = s.get(Appuntamento, aid)
    t = documenti.compila('{paziente} · {recapito}', a)
    assert t == '%s · {recapito}' % a.paziente.etichetta, t
    s.close()


def r17_orario_rovinato():
    """BUG 17. Il modulo non accetta una chiusura prima dell'apertura; e se
    il database avesse un orario rovinato, la griglia regge lo stesso."""
    S, C = mondo()
    s = S()
    st = s.get(Struttura, 1)
    st.ora_apertura, st.ora_chiusura = time(21, 0), time(20, 0)
    s.commit()
    ap, ultima, passo = servizi.orario(st)
    assert ap <= ultima and servizi.fasce([], ap, ultima, passo), (ap, ultima)
    s.close()
    assert C.get('/giorno/%s?struttura=1' % MAR).status_code == 200
    r = C.post('/anagrafiche/strutture/1', data={'nome': 'La mia struttura', 'ora_apertura': '21:00',
                                                 'ora_chiusura': '20:00', 'passo': '30', 'sezione_orario': '1'})
    assert 'La chiusura deve venire dopo l\'apertura' in testo(r) + avvisi(C)


def r18_ultima_fascia_entro_mezzanotte():
    """BUG 18. Con l'apertura alle 08:15 e fasce da 30', l'ultima fascia e'
    quella delle 23:15: quella delle 23:45 finirebbe dopo mezzanotte. Un
    appuntamento alle 23:45 si vede lo stesso, nell'ultima fascia."""
    class Finto:
        inizio = datetime.combine(MAR, time(23, 45))
        fine = datetime.combine(MAR, time(23, 59))
    f = servizi.fasce([Finto()], time(8, 15), time(19, 45), 30)
    ultima = f[-1].hour * 60 + f[-1].minute
    assert ultima + 30 <= 24 * 60 and f[-1] == time(23, 15), f[-1]
    S, C = mondo()
    I = ids(S)
    s = S()
    st = s.get(Struttura, 1)
    st.ora_apertura, st.ora_chiusura = time(8, 15), time(20, 15)
    s.commit()
    s.close()
    aid = nuovo_app(S, I['Ambulatorio 1'], I['Borrelli'], datetime.combine(MAR, time(23, 45)), minuti=14)
    assert '/appuntamento/%d' % aid in html(C.get('/giorno/%s?struttura=1' % MAR)), 'appuntamento sparito'


prova('BUG 05 · ritorno dopo "nuovo paziente": sempre interno', r05_ritorno_dopo_nuovo_paziente)
prova('BUG 06a · messaggi: nessuna parentesi o punto sospeso', r06_messaggio_senza_parentesi_sole)
prova('BUG 11 · degenza in endoscopia: resta e occupa il letto', r11_degenza_fuori_dalle_sale)
prova('BUG 14 · moduli: segnaposto sconosciuto resta visibile', r14_moduli_segnaposto_sconosciuto)
prova('BUG 17 · orario rovinato: la griglia regge, il modulo rifiuta', r17_orario_rovinato)
prova('BUG 18 · l\'ultima fascia finisce entro mezzanotte', r18_ultima_fascia_entro_mezzanotte)


# =====================================================================
if __name__ == '__main__':
    aree = []
    for e in esiti:
        if e[1] not in aree:
            aree.append(e[1])
    for a in aree:
        mie = [e for e in esiti if e[1] == a]
        rotte = [e for e in mie if e[0] != 'OK']
        print('%-40s %2d prove  %s' % (a, len(mie), 'tutte a posto' if not rotte else '%d DA SISTEMARE' % len(rotte)))
    rotte = [e for e in esiti if e[0] != 'OK']
    if rotte or os.environ.get('DETTAGLIO'):
        print('\nDettaglio:')
        for e in esiti:
            if e[0] != 'OK' or os.environ.get('DETTAGLIO'):
                print('  %-6s [%s] %s\n         %s' % (e[0], e[1], e[2], e[3]))
    print('\n%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(rotte), len(rotte)))
    shutil.rmtree(PROVVISORIA, ignore_errors=True)
    sys.exit(1 if rotte else 0)
