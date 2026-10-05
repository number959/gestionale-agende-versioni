# -*- coding: utf-8 -*-
"""Prove della 1.4.6: la seconda parte della revisione esterna del codice
(Gemini, 27/09/2026): bug 21-27, il modulo comune, WAL e Excel in memoria.

- "confermate": il difetto c'era; la prova lo riproduce e controlla la
  correzione;
- "respinte": il comportamento segnalato e' voluto o gia' protetto; la prova
  fissa quello giusto, cosi' una "correzione" futura che lo rompe si vede."""
import os
import re
import shutil
import sys
import tempfile
import traceback
from datetime import date, datetime, time, timedelta
from html import unescape
from urllib.parse import unquote

from sqlalchemy import select

import servizi
import sala
import importa
import pazienti
import documenti
import viste
import app as A
from modelli import (crea_sessione, Struttura, Risorsa, Operatore, Appuntamento, Paziente, Turno, Assenza,
                     COLONNE_AGGIUNTE, leggi_impostazione)

A.app.config['TESTING'] = True
CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = os.path.join(CARTELLA, 'prove_146_tmp')
shutil.rmtree(PROVVISORIA, ignore_errors=True)
os.makedirs(PROVVISORIA)
esiti, _area, _n = [], [''], [0]
OGGI = date.today()
MAR = OGGI + timedelta(days=(1 - OGGI.weekday()) % 7 + 14)
while servizi.calendario.festivo(MAR) or any(servizi.calendario.festivo(MAR + timedelta(days=7 * k))
                                             for k in range(1, 9)):
    MAR += timedelta(days=7)
G = MAR.strftime('%d/%m/%Y')


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
    s.close()
    return d


def nuovo_app(S, stanza, medico, inizio, minuti=30, stato='PRENOTATO', **altro):
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


def agenda(righe_dati):
    righe_ = [['Data', 'Ora', 'Durata', 'Stanza', 'Medico', 'Paziente', 'Telefono']]
    righe_ += [list(r) for r in righe_dati]
    return importa.analizza({'nome': 'agenda', 'righe': righe_})


# ============================================================ confermate
area('segnalazioni confermate')


def c21_medico_attivo_prima():
    """BUG 21. Un medico non piu' attivo si prendeva gli appuntamenti di un
    omonimo attivo; con due medici attivi dallo stesso cognome se ne prendeva
    uno in silenzio."""
    S, C = mondo()
    s = S()
    mario = Operatore(cognome='Rossi', nome='Mario', attivo=False)
    marco = Operatore(cognome='Rossi', nome='Marco')
    s.add_all([mario, marco])
    s.flush()
    solo = Operatore(cognome='Rossi', nome='')                  # scheda con il solo cognome
    anna = Operatore(cognome='Esposito', nome='Anna')
    luca = Operatore(cognome='Esposito', nome='Luca')
    s.add_all([solo, anna, luca])
    s.commit()
    ops = s.scalars(select(Operatore)).all()
    casi = [('ROSSI MARIO', mario), ('Marco Rossi', marco), ('ROSSI M.', marco), ('ROSSI', solo),
            ('ESPOSITO', anna), ('ESPOSITO L.', luca), ('BIANCHI', None)]
    sbagliati = [(t, (importa.trova_medico(ops, t) or Operatore(cognome='nessuno')).etichetta,
                  atteso.etichetta if atteso else 'nessuno')
                 for t, atteso in casi if importa.trova_medico(ops, t) is not atteso]
    assert not sbagliati, sbagliati
    # senza la scheda "Rossi" da sola, "ROSSI" e' l'unico Rossi attivo
    s.delete(solo)
    s.commit()
    ops = s.scalars(select(Operatore)).all()
    assert importa.trova_medico(ops, 'ROSSI') is marco, importa.trova_medico(ops, 'ROSSI').etichetta
    s.close()
    # nell'importazione: due Esposito attivi, si sceglie ma si avvisa; nessun medico nuovo
    S, C = mondo()
    s = S()
    s.add_all([Operatore(cognome='Esposito', nome='Anna'), Operatore(cognome='Esposito', nome='Luca')])
    s.commit()
    a = agenda([(G, '09:00', 30, 'Ambulatorio 1', 'ESPOSITO', 'Alfa Primo', '3330000001')])
    piano = importa.prepara(s, a, importa.opzioni_da({'struttura': '1'}, a))
    r = piano['righe'][0]
    assert r['esito'] == 'nuovo' and r['medico'] is not None and not piano['nuovi_medici'], \
        (r['esito'], r['medico'], piano['nuovi_medici'])
    assert any('Esposito Anna' in x and 'Esposito Luca' in x for x in r['avvisi']), r['avvisi']
    s.close()


def c22_segnaposto_con_le_maiuscole():
    """BUG 22 (in parte). {Paziente} o {DATA}, per esempio da un testo scritto
    in Word che mette la maiuscola a inizio frase, restavano scritti cosi'."""
    S, C = mondo()
    I = ids(S)
    s = S()
    p = Paziente(cognome='Verdi', nome='Lia')
    s.add(p)
    s.commit()
    pid = p.id
    s.close()
    aid = nuovo_app(S, I['Ambulatorio 1'], I['Borrelli'], datetime.combine(MAR, time(9, 0)), paziente_id=pid)
    s = S()
    a = s.get(Appuntamento, aid)
    t = documenti.compila('{Paziente} · {DATA} · {Giorno-1} · {ora} · {Boh}', a)
    atteso = '%s · %s · %s · 09:00 · {Boh}' % (a.paziente.etichetta, MAR.strftime('%d/%m/%Y'),
                                               documenti.compila('{giorno-1}', a))
    assert t == atteso, (t, atteso)
    m = viste.testo_messaggio(a, '{Paziente}, il {Giorno} alle {ORA}.')
    assert m == viste.testo_messaggio(a, '{paziente}, il {giorno} alle {ora}.'), m
    s.close()


def _mailto(pagina):
    m = re.search(r'href="(mailto:[^"]+)"', pagina)
    return unescape(m.group(1)) if m else None


def c23_mail_del_medico_entro_il_limite():
    """BUG 23, e di piu'. L'agenda del medico per email si tagliava a meta'
    riga; e il limite di 1800 caratteri era sul testo prima della codifica
    (spazi, a capo e lettere accentate la raddoppiano): l'indirizzo mailto
    superava i circa 2000 caratteri che Outlook accetta. Stesso limite per il
    riepilogo del mese."""
    S, C = mondo()
    I = ids(S)
    s = S()
    o = s.get(Operatore, I['Borrelli'])
    o.email = 'borrelli@example.it'
    s.commit()
    for k in range(40):
        p = Paziente(cognome='Dell\'Àcqua%02d' % k, nome='Nicolò Mattìa')
        s.add(p)
        s.flush()
        inizio = datetime.combine(MAR, time(8, 0)) + timedelta(minutes=15 * k)
        s.add(Appuntamento(risorsa_id=I['Ambulatorio %d' % (1 + k % 5)], operatore_id=o.id, paziente_id=p.id,
                           inizio=inizio, fine=inizio + timedelta(minutes=15), stato='PRENOTATO',
                           note='portare gli esami precedenti, è a digiuno'))
    s.commit()
    # i testi interi, come li scrive il programma
    import segreteria
    import cruscotto
    apps = [a for a in servizi.elenco_giorno(s, MAR, None, ('PRENOTATO',)) if a.operatore_id == o.id]
    primo = MAR.replace(day=1)
    ultimo = (primo + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    interi = [segreteria.testo_agenda(o, MAR, apps),
              cruscotto.testo_riepilogo(cruscotto.riepilogo_medici(s, primo, ultimo, o.id, None)[0], primo, '')]
    s.close()
    import comune
    limite = comune.MASSIMO_MAILTO
    for (indirizzo, coda), intero in zip((('/agenda-medico/%s?medico=%d' % (MAR, I['Borrelli']), 'agenda completa'),
                                          ('/riepilogo-medici/%s?medico=%d' % (MAR.strftime('%Y-%m'), I['Borrelli']),
                                           'elenco completo')), interi):
        assert len(intero) > 1800, 'testo di prova troppo corto: %d' % len(intero)
        href = _mailto(html(C.get(indirizzo)))
        assert href, 'nessun collegamento email in %s' % indirizzo
        assert len(href) <= limite, '%s: mailto di %d caratteri' % (indirizzo, len(href))
        righe = unquote(href.split('&body=', 1)[1]).split('\n')
        assert coda in righe[-1], righe[-1]
        # le righe prima della coda sono l'inizio del testo intero, righe intere
        assert intero.split('\n')[:len(righe) - 1] == righe[:-1], 'righe tagliate o cambiate'
    # un'agenda corta non si taglia
    S, C = mondo()
    I = ids(S)
    s = S()
    s.get(Operatore, I['Lippi']).email = 'lippi@example.it'
    s.commit()
    s.close()
    nuovo_app(S, I['Ambulatorio 2'], I['Lippi'], datetime.combine(MAR, time(9, 0)))
    href = _mailto(html(C.get('/agenda-medico/%s?medico=%d' % (MAR, I['Lippi']))))
    corpo = unquote(href.split('&body=', 1)[1])
    assert '09:00-09:30' in corpo and 'completa' not in corpo, corpo


def c24_assenti_in_ordine():
    """BUG 24. I chirurghi assenti comparivano in ordine di inserimento, e
    c'erano anche quelli non piu' attivi."""
    S, C = mondo()
    s = S()
    giorni = ''.join('1' if i == MAR.weekday() else '0' for i in range(7))
    zeta = Operatore(cognome='Zeta', nome='Ugo', giorni_sala=giorni)
    alfa = Operatore(cognome='Alfa', nome='Rita', giorni_sala=giorni)
    via = Operatore(cognome='Beta', nome='Aldo', giorni_sala=giorni, attivo=False)
    s.add_all([zeta, alfa, via])
    s.flush()
    for o in (zeta, alfa, via):
        s.add(Assenza(operatore_id=o.id, dal=MAR, al=MAR, motivo='Ferie'))
    s.commit()
    assenti = [o.cognome for o in sala.chirurghi_del_giorno(s, MAR, 1, [])['assenti']]
    s.close()
    assert assenti == ['Alfa', 'Zeta'], assenti


def c25_turno_eliminato_con_appuntamenti():
    """BUG 25. Eliminando un turno non si sapeva che restavano appuntamenti
    gia' presi in quel turno (restano in agenda, ma fuori turno); e che per
    chiuderlo senza cambiare le statistiche passate c'e' "Fino al"."""
    S, C = mondo()
    I = ids(S)
    s = S()
    t = Turno(operatore_id=I['Borrelli'], risorsa_id=I['Ambulatorio 1'], giorno_settimana=MAR.weekday(),
              ora_inizio=time(8, 0), ora_fine=time(14, 0), valido_da=OGGI - timedelta(days=60),
              valido_a=MAR + timedelta(days=13))
    dopo = Turno(operatore_id=I['Borrelli'], risorsa_id=I['Ambulatorio 1'], giorno_settimana=MAR.weekday(),
                 ora_inizio=time(8, 0), ora_fine=time(14, 0), valido_da=MAR + timedelta(days=14))
    s.add_all([t, dopo])
    s.commit()
    tid = t.id
    s.close()
    B, A1, A2 = I['Borrelli'], I['Ambulatorio 1'], I['Ambulatorio 2']
    dentro = [nuovo_app(S, A1, B, datetime.combine(MAR, time(9, 0))),
              nuovo_app(S, A1, B, datetime.combine(MAR + timedelta(days=7), time(13, 30)))]
    for a in [(A1, B, datetime.combine(MAR, time(15, 0))),                           # fuori orario
              (A2, B, datetime.combine(MAR, time(10, 0))),                           # altra stanza
              (A1, B, datetime.combine(MAR + timedelta(days=1), time(9, 0))),       # altro giorno
              (A1, B, datetime.combine(MAR + timedelta(days=14), time(9, 0))),      # coperto dal turno dopo
              (A1, B, datetime.combine(OGGI - timedelta(days=7 - (MAR.weekday() - OGGI.weekday()) % 7), time(9, 0)))]:
        nuovo_app(S, *a)
    nuovo_app(S, A1, B, datetime.combine(MAR, time(11, 0)), stato='DISDETTO')
    pagina = testo(C.get('/anagrafiche/turni/%d' % tid))
    assert 'senza cambiare le statistiche passate' in pagina, 'la pagina non parla di "Fino al"'
    r = C.post('/anagrafiche/turni/%d' % tid, data={'azione': 'elimina'})
    assert r.status_code == 302
    messaggio = avvisi(C)
    assert 'Restano in agenda 2 appuntamenti' in messaggio and 'fuori turno' in messaggio, messaggio
    s = S()
    assert s.get(Turno, tid) is None and all(s.get(Appuntamento, x) for x in dentro)
    s.close()


def c27_richieste_da_altri_siti():
    """BUG 27, e di piu'. Una pagina qualsiasi aperta nello stesso browser
    poteva mandare moduli al gestionale (eliminare appuntamenti, cambiare le
    impostazioni); con il "DNS rebinding" poteva anche leggerne le pagine. Ora:
    solo indirizzi 127.0.0.1 o localhost, e i moduli solo dalle sue pagine.
    La correzione proposta lasciava passare "Origin: null" (una cornice
    isolata) e ogni porta di localhost."""
    S, C = mondo()
    I = ids(S)
    aid = nuovo_app(S, I['Ambulatorio 1'], I['Borrelli'], datetime.combine(MAR, time(9, 0)))
    assert C.get('/oggi').status_code == 200
    for host in ('127.0.0.1:5000', 'localhost:5000', 'localhost'):
        assert C.get('/oggi', headers={'Host': host}).status_code == 200, host
    for host in ('evil.example:5000', 'evil.example', '127.0.0.1.evil.example:5000', 'LOCALHOST.evil.example'):
        assert C.get('/pazienti/cerca?q=ro', headers={'Host': host}).status_code == 400, host
    casa = {'Host': '127.0.0.1:5000'}
    rifiutate = [{'Origin': 'http://evil.example'}, {'Origin': 'null'},
                 {'Origin': 'http://127.0.0.1:5001'}, {'Origin': 'http://localhost:5000.evil.example'},
                 {'Referer': 'http://evil.example/pagina'}, {'Sec-Fetch-Site': 'cross-site'},
                 {'Sec-Fetch-Site': 'same-site'}]
    for extra in rifiutate:
        r = C.post('/appuntamento/%d' % aid, data={'azione': 'elimina'}, headers=dict(casa, **extra))
        assert r.status_code == 403, (extra, r.status_code)
    s = S()
    assert s.get(Appuntamento, aid) is not None, 'appuntamento eliminato da un altro sito'
    s.close()
    buone = [{'Origin': 'http://127.0.0.1:5000'}, {'Referer': 'http://127.0.0.1:5000/giorno/x'},
             {'Origin': 'http://127.0.0.1:5000', 'Sec-Fetch-Site': 'same-origin'}, {}]
    for extra in buone:
        r = C.post('/impostazioni', data={'azione': 'testo', 'testo': 'Promemoria {giorno} %d' % len(extra),
                                          'oggetto': 'Promemoria'}, headers=dict(casa, **extra))
        assert r.status_code == 302, (extra, r.status_code)
    s = S()
    assert leggi_impostazione(s, 'testo_promemoria') == 'Promemoria {giorno} 0'
    s.close()


def c3_excel_in_memoria():
    """Sezione 3-4. I file Excel scaricati (con nomi e telefoni dei pazienti)
    restavano nella cartella temporanea di Windows. Ora nascono in memoria."""
    S, C = mondo()
    I = ids(S)
    nuovo_app(S, I['Ambulatorio 1'], I['Borrelli'], datetime.combine(MAR, time(9, 0)))
    mese = MAR.strftime('%Y-%m')
    prove_ = [('/esporta/%s?struttura=1' % MAR, 'planning-%s.xlsx' % MAR),
              ('/statistiche/excel?struttura=1&dal=%s&al=%s' % (MAR, MAR), 'statistiche-%s-%s.xlsx' % (MAR, MAR)),
              ('/cassa/mese/%s/excel?struttura=1' % mese, 'incassi-%s.xlsx' % mese),
              ('/riepilogo-medici/%s/excel' % mese, 'riepilogo-medici-%s.xlsx' % mese)]
    for indirizzo, nome in prove_:
        percorso = os.path.join(tempfile.gettempdir(), nome)
        if os.path.exists(percorso):
            os.remove(percorso)
        r = C.get(indirizzo)
        assert r.status_code == 200 and r.data[:2] == b'PK', (indirizzo, r.status_code)
        assert nome in r.headers.get('Content-Disposition', ''), r.headers.get('Content-Disposition')
        assert not os.path.exists(percorso), 'file rimasto in %s' % percorso


def c3_funzioni_comuni():
    """Sezione 3. Le funzioni di servizio erano copiate in piu' file, e due
    copie si erano gia' allontanate: i suggerimenti dei pazienti mentre si
    scrive (nomi e telefoni) non avevano "no-store" e restavano nella cache
    del browser; il mese "202609" valeva in un posto e non nell'altro."""
    import comune
    import anagrafiche
    import cassa
    import cruscotto
    import segreteria
    import documenti as d
    for modulo, nomi in ((A, ['intero', 'destinazione_sicura']), (cassa, ['intero', 'data_da', 'destinazione_sicura',
                                                                          'struttura_scelta', 'mese_da']),
                         (segreteria, ['intero', 'data_da', 'destinazione_sicura', 'struttura_scelta', 'json_sicuro',
                                       'giorno_breve']),
                         (sala, ['data_da', 'destinazione_sicura', 'struttura_scelta', 'giorno_breve']),
                         (viste, ['intero', 'data_da', 'struttura_scelta']), (d, ['intero']),
                         (pazienti, ['json_sicuro']), (cruscotto, ['mese_da']),
                         (importa, ['colore_libero']), (anagrafiche, ['colore_libero'])):
        for nome in nomi:
            assert getattr(modulo, nome) is getattr(comune, nome), '%s.%s non e\' quella comune' % (
                modulo.__name__, nome)
    assert cassa.mese_da('202609') == cruscotto.mese_da('2026-09') == (date(2026, 9, 1), date(2026, 9, 30))
    S, C = mondo()
    s = S()
    s.add(Paziente(cognome='Rossi', nome='Marta', telefono='3331112222'))
    s.commit()
    s.close()
    r = C.get('/pazienti/cerca?q=ros')
    assert r.status_code == 200 and 'Rossi' in html(r), html(r)[:200]
    assert r.headers.get('Cache-Control') == 'no-store', r.headers.get('Cache-Control')


prova('BUG 21 · medici: prima il nome intero, gli attivi prima; omonimi segnalati', c21_medico_attivo_prima)
prova('BUG 22 · segnaposto con le maiuscole', c22_segnaposto_con_le_maiuscole)
prova('BUG 23 · email del medico: righe intere, indirizzo entro il limite', c23_mail_del_medico_entro_il_limite)
prova('BUG 24 · chirurghi assenti in ordine, solo gli attivi', c24_assenti_in_ordine)
prova('BUG 25 · turno eliminato: avviso degli appuntamenti rimasti', c25_turno_eliminato_con_appuntamenti)
prova('BUG 27 · richieste da altri siti e DNS rebinding', c27_richieste_da_altri_siti)
prova('Sez. 3-4 · Excel scaricati senza file temporanei', c3_excel_in_memoria)
prova('Sez. 3 · funzioni comuni, una copia sola', c3_funzioni_comuni)


# =============================================================== respinte
area('segnalazioni respinte')


def r22_date_nei_moduli():
    """BUG 22, seconda parte. {giorno+999} non puo' uscire dal calendario: le
    date degli appuntamenti stanno fra il 1900 e il 2100."""
    S, C = mondo()
    I = ids(S)
    aid = nuovo_app(S, I['Ambulatorio 1'], I['Borrelli'], datetime(2100, 12, 31, 9, 0))
    s = S()
    a = s.get(Appuntamento, aid)
    assert documenti.compila('{data+999} {data-999}', a) == '%s %s' % (
        (date(2100, 12, 31) + timedelta(days=999)).strftime('%d/%m/%Y'),
        (date(2100, 12, 31) - timedelta(days=999)).strftime('%d/%m/%Y'))
    s.close()
    assert A.data_da_stringa('9999-12-31') <= date(2100, 12, 31)
    assert importa.come_data('31/12/9999') is None


def r26_nomi_delle_colonne():
    """BUG 26. I nomi nelle istruzioni di aggiornamento sono costanti scritte
    nel programma, non arrivano da fuori: un controllo in piu' non protegge
    da niente. Questa prova li controlla una volta per tutte."""
    nome = re.compile(r'[a-z_][a-z0-9_]*')
    for tabella, colonne in COLONNE_AGGIUNTE.items():
        assert nome.fullmatch(tabella), tabella
        for c, _tipo in colonne:
            assert nome.fullmatch(c), c


def r41_niente_wal():
    """Sezione 4.1. Il tempo d'attesa di SQLite e' gia' di 5 secondi (quello di
    Python); il WAL terrebbe le ultime modifiche in un file a parte, che la
    copia di BACKUP.bat non prende."""
    S = crea_sessione('sqlite:///' + percorso_nuovo())
    with S.motore.connect() as c:
        assert c.exec_driver_sql('PRAGMA busy_timeout').scalar() == 5000
        assert c.exec_driver_sql('PRAGMA journal_mode').scalar() == 'delete'
    bat = open(os.path.join(CARTELLA, 'BACKUP.bat'), encoding='utf-8', errors='replace').read()
    assert 'copy /y "%ORIGINE%"' in bat


prova('BUG 22b · date dei moduli dentro il calendario', r22_date_nei_moduli)
prova('BUG 26 · nomi delle colonne: costanti del programma', r26_nomi_delle_colonne)
prova('Sez. 4.1 · niente WAL: attesa gia\' di 5 secondi, BACKUP.bat copia il file', r41_niente_wal)


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
