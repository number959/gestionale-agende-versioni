# -*- coding: utf-8 -*-
"""Prove su medici, turni, stanze, prestazioni e struttura.

A differenza delle altre suite, qui ogni scenario parte dal database vuoto
del primo avvio, lo stesso che trova la segreteria dopo l'installazione.
Le altre partono da seed.py, che inserisce i medici direttamente: ed e'
per questo che non si erano accorte che dall'interfaccia non si potevano
inserire.
"""
import os
import random
import re
import threading
import traceback
from datetime import datetime, date, time, timedelta

from sqlalchemy import select, func

import servizi
import app as A
import anagrafiche as AN
from modelli import (crea_sessione, Struttura, Risorsa, Operatore, Prestazione,
                     Turno, Appuntamento, Modifica)

A.app.config['TESTING'] = True
CARTELLA = os.path.dirname(os.path.abspath(__file__))
_file = []
esiti = []
_area = ['']

OGGI = date.today()
MARTEDI = OGGI + timedelta(days=((1 - OGGI.weekday()) % 7) or 7)   # prossimo martedi
MARTEDI_PASSATO = MARTEDI - timedelta(days=28)


def area(nome):
    _area[0] = nome


def prova(nome, f):
    try:
        esiti.append(('OK', _area[0], nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', _area[0], nome, str(e) or 'asserzione fallita'))
    except Exception:
        esiti.append(('ERRORE', _area[0], nome,
                      traceback.format_exc().strip().splitlines()[-1]))


def mondo():
    """Database nuovo come dopo l'installazione: solo il primo avvio."""
    percorso = os.path.join(CARTELLA, 'prove_anag_%d.db' % len(_file))
    if os.path.exists(percorso):
        os.remove(percorso)
    _file.append(percorso)
    Sessione = crea_sessione('sqlite:///' + percorso)
    s = Sessione()
    servizi.prepara_primo_avvio(s)
    s.close()
    A.Sessione = Sessione
    A._registro = None          # la sessione per thread va ricreata sul nuovo database
    return Sessione, A.app.test_client()


def html(r):
    return r.get_data(as_text=True)


def id_da(S, modello, **filtri):
    s = S()
    o = s.scalars(select(modello).filter_by(**filtri)).first()
    ident = o.id if o else None
    s.close()
    return ident


def conta(S, modello, *condizioni):
    s = S()
    n = s.scalar(select(func.count()).select_from(modello).where(*condizioni)) if condizioni \
        else s.scalar(select(func.count()).select_from(modello))
    s.close()
    return n


def nuovo_medico(c, cognome, nome='', colore='#154381', attivo=True, specialita=''):
    dati = {'cognome': cognome, 'nome': nome, 'specialita': specialita, 'colore': colore}
    if attivo:
        dati['attivo'] = '1'
    return c.post('/anagrafiche/medici/nuovo', data=dati)


def nuovo_turno(c, oid, rid, giorno=1, dalle='08:00', alle='14:00', da=None, a=''):
    return c.post('/anagrafiche/turni/nuovo', data={
        'operatore': str(oid), 'risorsa': str(rid), 'giorno': str(giorno),
        'ora_inizio': dalle, 'ora_fine': alle,
        'valido_da': (da or OGGI).isoformat(), 'valido_a': a.isoformat() if a else ''})


def stato_fasce(S, g, nome_stanza):
    s = S()
    sid = s.scalars(select(Struttura)).first().id
    v = servizi.griglia(s, g, sid)
    col = [x for x in v['colonne'] if x['risorsa'].nome == nome_stanza]
    s.close()
    if not col:
        return None
    return {f.strftime('%H:%M'): cella['stato'] for f, cella in zip(v['fasce'], col[0]['celle'])}


def stanza_id(S, nome):
    return id_da(S, Risorsa, nome=nome)


def svuota_avvisi(c):
    """I messaggi di conferma restano in coda fino alla pagina successiva:
    cercando un nome in pagina si rischia di trovarlo li' e non dove serve."""
    c.get('/anagrafiche')


def reindirizza_elenco(r):
    return r.status_code == 302 and r.headers.get('Location', '').endswith('/anagrafiche')


# =====================================================================
area('primo avvio')
S, C = mondo()


def pa_contenuto():
    assert id_da(S, Struttura, nome=servizi.NOME_INIZIALE), 'la struttura non si chiama %s' % servizi.NOME_INIZIALE
    assert conta(S, Risorsa) == 6, '%d stanze invece di 6' % conta(S, Risorsa)
    assert conta(S, Prestazione) == 6, 'prestazioni: %d' % conta(S, Prestazione)
    assert conta(S, Operatore) == 0 and conta(S, Turno) == 0, 'medici o turni gia presenti'
    return '1 struttura, 6 stanze, 6 prestazioni, 0 medici, 0 turni'


def pa_ripetuto():
    s = S()
    secondo = servizi.prepara_primo_avvio(s)
    s.close()
    assert secondo is None, 'il secondo avvio ha ricreato la struttura'
    assert conta(S, Risorsa) == 6, 'stanze duplicate al secondo avvio'


def pa_griglia_guida():
    r = C.get('/giorno/%s' % MARTEDI.isoformat())
    assert r.status_code == 200, 'HTTP %d' % r.status_code
    assert 'Per cominciare vanno inseriti i medici' in html(r), 'la griglia non dice cosa fare'


def pa_modulo_senza_medici():
    r = C.get('/appuntamento?data=%s' % MARTEDI.isoformat())
    assert r.status_code == 200, 'HTTP %d' % r.status_code
    assert 'Manca ancora un medico' in html(r), 'nessuna spiegazione'
    assert '<form method="post">' not in html(r), 'il modulo con il menu medici vuoto e ancora visibile'


def pa_elenco_guida():
    t = html(C.get('/anagrafiche'))
    assert 'Per cominciare' in t and 'Aggiungi un medico' in t, 'manca la guida al primo avvio'


def pa_turno_senza_medici():
    r = C.get('/anagrafiche/turni/nuovo')
    assert r.status_code == 302 and '/anagrafiche/medici/nuovo' in r.headers['Location'], \
        'senza medici il turno non rimanda all inserimento medico (%d)' % r.status_code


prova('il primo avvio crea struttura, stanze e prestazioni', pa_contenuto)
prova('il secondo avvio non duplica nulla', pa_ripetuto)
prova('la griglia vuota spiega cosa inserire', pa_griglia_guida)
prova('il modulo di prenotazione senza medici spiega il motivo', pa_modulo_senza_medici)
prova('la pagina anagrafiche mostra la guida', pa_elenco_guida)
prova('il turno senza medici rimanda all inserimento', pa_turno_senza_medici)


# =====================================================================
area('medici')
S, C = mondo()


def me_modulo():
    t = html(C.get('/anagrafiche/medici/nuovo'))
    assert 'name="cognome"' in t and 'type="color"' in t, 'campi mancanti'
    assert 'value="%s"' % AN.PALETTE[0] in t, 'colore predefinito non proposto'


def me_crea():
    r = nuovo_medico(C, 'Lippiello', colore='#5B7F3E', specialita='Ginecologia')
    assert reindirizza_elenco(r), 'HTTP %d' % r.status_code
    s = S()
    o = s.scalars(select(Operatore).where(Operatore.cognome == 'Lippiello')).first()
    s.close()
    assert o and o.attivo and o.colore == '#5b7f3e', 'medico non salvato come richiesto'


def me_colore_successivo():
    t = html(C.get('/anagrafiche/medici/nuovo'))
    assert 'value="%s"' % AN.PALETTE[0] in t, 'il primo colore libero non e proposto'
    nuovo_medico(C, 'Galasso', colore=AN.PALETTE[0])
    t = html(C.get('/anagrafiche/medici/nuovo'))
    assert 'value="%s"' % AN.PALETTE[2] in t, 'dopo due medici non propone il terzo colore'


def fai_rifiuto_medico(dati, frammento):
    def f():
        prima = conta(S, Operatore)
        r = C.post('/anagrafiche/medici/nuovo', data=dati)
        assert r.status_code == 200, 'atteso il modulo di nuovo, HTTP %d' % r.status_code
        assert frammento in html(r), 'messaggio atteso assente: %s' % frammento
        assert conta(S, Operatore) == prima, 'salvato nonostante l errore'
    return f


def me_valori_mantenuti():
    t = html(C.post('/anagrafiche/medici/nuovo', data={
        'cognome': '', 'nome': 'Mariarosaria', 'specialita': 'Cardiologia', 'colore': '#123456'}))
    assert 'Mariarosaria' in t and 'Cardiologia' in t, 'dopo l errore i dati digitati spariscono'


def me_colore_ripulito():
    r = nuovo_medico(C, 'Ripulito', colore=' #ABCDEF\n')
    assert reindirizza_elenco(r), 'HTTP %d' % r.status_code
    s = S(); o = s.scalars(select(Operatore).where(Operatore.cognome == 'Ripulito')).first(); s.close()
    assert o.colore == '#abcdef', 'colore salvato cosi: %r' % o.colore


def me_omonimo_con_nome():
    r = nuovo_medico(C, 'Lippiello', nome='Anna')
    assert reindirizza_elenco(r), 'stesso cognome con nome diverso rifiutato'


def me_modifica():
    oid = id_da(S, Operatore, cognome='Galasso')
    r = C.post('/anagrafiche/medici/%d' % oid, data={
        'cognome': 'Galasso', 'nome': 'Pietro', 'specialita': 'Gastroenterologia',
        'colore': '#6B4E9B', 'attivo': '1'})
    assert reindirizza_elenco(r), 'HTTP %d' % r.status_code
    s = S(); o = s.get(Operatore, oid); s.close()
    assert o.nome == 'Pietro' and o.specialita == 'Gastroenterologia', 'modifica non salvata'


def me_disattiva():
    oid = id_da(S, Operatore, cognome='Galasso')
    C.post('/anagrafiche/medici/%d' % oid, data={
        'cognome': 'Galasso', 'nome': 'Pietro', 'colore': '#6B4E9B'})       # senza "attivo"
    svuota_avvisi(C)
    modulo = html(C.get('/appuntamento?data=%s' % MARTEDI.isoformat()))
    # l'opzione va cercata con il nome: anche stanze e prestazioni hanno opzioni con lo stesso numero
    assert not re.search(r'<option value="%d"[^>]*>Galasso' % oid, modulo), 'medico disattivato ancora prenotabile'
    assert re.search(r'<option value="\d+"[^>]*>Lippiello', modulo), 'la prova non vede nemmeno i medici attivi'
    elenco = html(C.get('/anagrafiche'))
    assert 'Galasso' in elenco and 'non attivo' in elenco, 'medico disattivato sparito dall elenco'


def me_elimina_libero():
    nuovo_medico(C, 'Temporaneo')
    oid = id_da(S, Operatore, cognome='Temporaneo')
    r = C.post('/anagrafiche/medici/%d' % oid, data={'azione': 'elimina'})
    assert reindirizza_elenco(r), 'HTTP %d' % r.status_code
    assert id_da(S, Operatore, cognome='Temporaneo') is None, 'non eliminato'


def me_elimina_usato():
    oid = id_da(S, Operatore, cognome='Lippiello', nome='')
    s = S()
    i = datetime.combine(MARTEDI, time(9, 0))
    s.add(Appuntamento(risorsa_id=stanza_id(S, 'Ambulatorio 1'), operatore_id=oid,
                       inizio=i, fine=i + timedelta(minutes=30)))
    s.commit(); s.close()
    r = C.post('/anagrafiche/medici/%d' % oid, data={'azione': 'elimina'}, follow_redirects=True)
    t = html(r)
    assert 'non si può eliminare' in t and '1 appuntamento' in t, 'rifiuto non spiegato'
    assert id_da(S, Operatore, id=oid), 'eliminato un medico con appuntamenti'


def me_inesistente():
    assert C.get('/anagrafiche/medici/99999').status_code == 404, 'GET senza 404'
    assert C.post('/anagrafiche/medici/99999', data={'cognome': 'X'}).status_code == 404, 'POST senza 404'


def me_log():
    n = conta(S, Modifica, Modifica.entita == 'Operatore')
    assert n >= 3, 'modifiche ai medici non registrate nello storico (%d)' % n


prova('il modulo nuovo medico propone il primo colore libero', me_modulo)
prova('inserimento di un medico', me_crea)
prova('ogni nuovo medico riceve un colore diverso', me_colore_successivo)
for nome, dati, frammento in [
        ('cognome vuoto', {'cognome': '', 'colore': '#123456'}, 'Cognome: campo obbligatorio'),
        ('cognome di soli spazi', {'cognome': '   ', 'colore': '#123456'}, 'Cognome: campo obbligatorio'),
        ('cognome oltre 60 caratteri', {'cognome': 'X' * 61, 'colore': '#123456'}, 'al massimo 60'),
        ('colore a parole', {'cognome': 'Rossi', 'colore': 'red'}, 'Colore: formato non valido'),
        ('colore corto', {'cognome': 'Rossi', 'colore': '#12345'}, 'Colore: formato non valido'),
        ('colore con codice', {'cognome': 'Rossi', 'colore': 'javascript:alert(1)'}, 'Colore: formato non valido'),
        ('doppione con maiuscole diverse', {'cognome': 'LIPPIELLO', 'colore': '#123456'}, 'Esiste già un medico'),
        ('doppione con spazi attorno', {'cognome': '  Lippiello ', 'colore': '#123456'}, 'Esiste già un medico')]:
    prova('rifiutato: %s' % nome, fai_rifiuto_medico(dati, frammento))
prova('colore con spazi o a capo attorno: salvato pulito', me_colore_ripulito)
prova('dopo un errore i dati digitati restano', me_valori_mantenuti)
prova('stesso cognome con nome diverso ammesso', me_omonimo_con_nome)
prova('modifica di un medico', me_modifica)
prova('medico disattivato: non prenotabile, ancora in elenco', me_disattiva)
prova('eliminazione di un medico mai usato', me_elimina_libero)
prova('medico con appuntamenti: eliminazione rifiutata', me_elimina_usato)
prova('medico inesistente: 404', me_inesistente)
prova('le modifiche finiscono nello storico', me_log)


# =====================================================================
area('turni')
S, C = mondo()
nuovo_medico(C, 'Lippiello')
nuovo_medico(C, 'Galasso')
LIP, GAL = id_da(S, Operatore, cognome='Lippiello'), id_da(S, Operatore, cognome='Galasso')
A1, A2 = stanza_id(S, 'Ambulatorio 1'), stanza_id(S, 'Ambulatorio 2')


def tu_apre_fasce():
    r = nuovo_turno(C, LIP, A1, giorno=1, dalle='08:00', alle='14:00')
    assert reindirizza_elenco(r), 'turno non salvato (HTTP %d)' % r.status_code
    f = stato_fasce(S, MARTEDI, 'Ambulatorio 1')
    assert f['08:00'] == 'aperta' and f['13:30'] == 'aperta', 'fasce del turno non aperte'
    assert f['14:00'] == 'chiusa', 'la fascia delle 14:00, fuori turno, risulta aperta'
    lun = stato_fasce(S, MARTEDI - timedelta(days=1), 'Ambulatorio 1')
    assert lun['10:00'] == 'chiusa', 'il turno del martedi apre anche il lunedi'


def tu_guida_sparisce():
    t = html(C.get('/giorno/%s' % MARTEDI.isoformat()))
    assert 'Per cominciare' not in t and 'Mancano i turni' not in t, 'avviso di primo avvio ancora visibile'


def tu_stesso_medico_due_stanze():
    r = nuovo_turno(C, LIP, A2, giorno=1, dalle='08:00', alle='14:00')
    assert reindirizza_elenco(r), 'lo stesso medico su due ambulatori insieme e stato rifiutato'


def tu_sovrapposto():
    r = nuovo_turno(C, GAL, A1, giorno=1, dalle='13:00', alle='16:00')
    assert r.status_code == 200, 'turno sovrapposto accettato'
    assert 'già assegnata a Lippiello' in html(r), 'il rifiuto non dice con chi si sovrappone'


def tu_adiacente():
    r = nuovo_turno(C, GAL, A1, giorno=1, dalle='14:00', alle='18:00')
    assert reindirizza_elenco(r), 'turno che inizia quando finisce l altro rifiutato'


def tu_periodi_disgiunti():
    r = nuovo_turno(C, GAL, A2, giorno=1, dalle='09:00', alle='11:00',
                    da=OGGI - timedelta(days=90), a=OGGI - timedelta(days=30))
    assert reindirizza_elenco(r), 'turno scaduto considerato sovrapposto a uno attuale'


def fai_rifiuto_turno(dati, frammento):
    def f():
        prima = conta(S, Turno)
        base = {'operatore': str(LIP), 'risorsa': str(stanza_id(S, 'Ambulatorio 3')), 'giorno': '3',
                'ora_inizio': '08:00', 'ora_fine': '12:00', 'valido_da': OGGI.isoformat(), 'valido_a': ''}
        base.update(dati)
        r = C.post('/anagrafiche/turni/nuovo', data=base)
        assert r.status_code == 200, 'atteso il modulo di nuovo, HTTP %d' % r.status_code
        assert frammento in html(r), 'messaggio atteso assente: %s' % frammento
        assert conta(S, Turno) == prima, 'turno salvato nonostante l errore'
    return f


def tu_modifica_nome_nuovo():
    tid = id_da(S, Turno, operatore_id=GAL, risorsa_id=A1)
    r = C.post('/anagrafiche/turni/%d' % tid, data={
        'operatore': str(LIP), 'risorsa': str(A1), 'giorno': '1', 'ora_inizio': '14:00',
        'ora_fine': '18:00', 'valido_da': OGGI.isoformat(), 'valido_a': ''}, follow_redirects=True)
    t = html(r)
    assert 'Turno salvato: Lippiello' in t, 'il messaggio riporta il medico di prima'
    s = S(); x = s.get(Turno, tid); s.close()
    assert x.operatore_id == LIP, 'cambio di medico non salvato'


def tu_modifica_senza_conflitto_con_se():
    tid = id_da(S, Turno, operatore_id=LIP, risorsa_id=A1, ora_inizio=time(8, 0))
    r = C.post('/anagrafiche/turni/%d' % tid, data={
        'operatore': str(LIP), 'risorsa': str(A1), 'giorno': '1', 'ora_inizio': '08:00',
        'ora_fine': '13:00', 'valido_da': OGGI.isoformat(), 'valido_a': ''})
    assert reindirizza_elenco(r), 'il turno va in conflitto con se stesso'


def tu_preselezione():
    t = html(C.get('/anagrafiche/turni/nuovo?medico=%d' % GAL))
    assert re.search(r'<option value="%d" selected>Galasso' % GAL, t), 'medico non preselezionato'


def tu_elimina():
    tid = id_da(S, Turno, operatore_id=LIP, risorsa_id=A2)
    r = C.post('/anagrafiche/turni/%d' % tid, data={'azione': 'elimina'})
    assert reindirizza_elenco(r), 'HTTP %d' % r.status_code
    f = stato_fasce(S, MARTEDI, 'Ambulatorio 2')
    assert f['10:00'] == 'chiusa', 'eliminato il turno, le fasce restano aperte'


prova('un turno apre esattamente le sue fasce', tu_apre_fasce)
prova('dopo il primo turno l avviso di primo avvio sparisce', tu_guida_sparisce)
prova('stesso medico su due ambulatori insieme: ammesso', tu_stesso_medico_due_stanze)
prova('due medici nella stessa stanza e fascia: rifiutato', tu_sovrapposto)
prova('turno che inizia quando finisce l altro: ammesso', tu_adiacente)
prova('periodi di validita disgiunti: ammesso', tu_periodi_disgiunti)
for nome, dati, frammento in [
        ('fine uguale all inizio', {'ora_fine': '08:00'}, 'deve venire dopo'),
        ('fine prima dell inizio', {'ora_inizio': '12:00', 'ora_fine': '08:00'}, 'deve venire dopo'),
        ('fine validita prima dell inizio', {'valido_a': (OGGI - timedelta(days=1)).isoformat()}, 'viene prima'),
        ('ora impossibile', {'ora_inizio': '25:00'}, 'Dalle: ora non valida'),
        ('ora vuota', {'ora_fine': ''}, 'Alle: ora non valida'),
        ('giorno 7', {'giorno': '7'}, 'Giorno della settimana: scelta non valida'),
        ('medico inesistente', {'operatore': '99999'}, 'Medico: scelta non valida'),
        ('stanza inesistente', {'risorsa': '99999'}, 'Stanza: scelta non valida'),
        ('data di inizio vuota', {'valido_da': ''}, 'Valido dal: campo obbligatorio'),
        ('data fuori intervallo', {'valido_da': '1900-01-01'}, 'fuori dall'),
        ('data assurda', {'valido_da': '2026-02-30'}, 'data non valida')]:
    prova('rifiutato: %s' % nome, fai_rifiuto_turno(dati, frammento))
prova('cambiando medico il messaggio riporta quello nuovo', tu_modifica_nome_nuovo)
prova('modificando un turno non va in conflitto con se stesso', tu_modifica_senza_conflitto_con_se)
prova('link da un medico: medico preselezionato', tu_preselezione)
prova('eliminato un turno le sue fasce si chiudono', tu_elimina)


# =====================================================================
area('stanze')
S, C = mondo()
nuovo_medico(C, 'Lippiello')
LIP = id_da(S, Operatore, cognome='Lippiello')
SID = id_da(S, Struttura, nome=servizi.NOME_INIZIALE)


def dati_stanza(nome, tipo='AMBULATORIO', ordine='1', attiva=True):
    d = {'nome': nome, 'tipo': tipo, 'struttura': str(SID), 'ordine': str(ordine)}
    if attiva:
        d['attiva'] = '1'
    return d


def st_rinomina():
    rid = stanza_id(S, 'Ambulatorio 1')
    r = C.post('/anagrafiche/stanze/%d' % rid, data=dati_stanza('Studio Lippiello', ordine=1))
    assert reindirizza_elenco(r), 'HTTP %d' % r.status_code
    svuota_avvisi(C)
    t = html(C.get('/giorno/%s' % MARTEDI.isoformat()))
    assert re.search(r'<th>Studio Lippiello\s*<span class="sotto">', t), 'nome nuovo assente dall intestazione'
    assert not re.search(r'<th>Ambulatorio 1\s*<span', t), 'il nome vecchio e ancora in griglia'


def fai_rifiuto_stanza(dati, frammento):
    def f():
        prima = conta(S, Risorsa)
        r = C.post('/anagrafiche/stanze/nuova', data=dati)
        assert r.status_code == 200, 'HTTP %d' % r.status_code
        assert frammento in html(r), 'messaggio atteso assente: %s' % frammento
        assert conta(S, Risorsa) == prima, 'stanza creata nonostante l errore'
    return f


def st_nuova_in_griglia():
    r = C.post('/anagrafiche/stanze/nuova', data=dati_stanza('Sala A', tipo='SALA_OPERATORIA', ordine=0))
    assert reindirizza_elenco(r), 'HTTP %d' % r.status_code
    s = S()
    v = servizi.griglia(s, MARTEDI, SID)
    nomi = [c['risorsa'].nome for c in v['colonne']]
    s.close()
    assert nomi[0] == 'Sala A', 'con posizione 0 la stanza dovrebbe essere la prima colonna: %s' % nomi


def st_disattiva_libera():
    rid = stanza_id(S, 'Ambulatorio 5')
    r = C.post('/anagrafiche/stanze/%d' % rid, data=dati_stanza('Ambulatorio 5', ordine=5, attiva=False))
    assert reindirizza_elenco(r), 'HTTP %d' % r.status_code
    assert stato_fasce(S, MARTEDI, 'Ambulatorio 5') is None, 'stanza disattivata ancora in griglia'


def st_disattiva_con_futuro():
    rid = stanza_id(S, 'Ambulatorio 4')
    s = S()
    i = datetime.combine(MARTEDI, time(10, 0))
    s.add(Appuntamento(risorsa_id=rid, operatore_id=LIP, inizio=i, fine=i + timedelta(minutes=30)))
    s.commit(); s.close()
    r = C.post('/anagrafiche/stanze/%d' % rid, data=dati_stanza('Ambulatorio 4', ordine=4, attiva=False))
    assert r.status_code == 200 and 'da oggi in poi' in html(r), 'disattivata con prenotazioni future'
    s = S(); x = s.get(Risorsa, rid); s.close()
    assert x.attiva, 'la stanza risulta disattivata'


def st_elimina_usata():
    rid = stanza_id(S, 'Ambulatorio 4')
    r = C.post('/anagrafiche/stanze/%d' % rid, data={'azione': 'elimina'}, follow_redirects=True)
    assert 'non si può eliminare' in html(r), 'rifiuto non spiegato'
    assert stanza_id(S, 'Ambulatorio 4'), 'eliminata una stanza con appuntamenti'


def st_elimina_libera():
    rid = stanza_id(S, 'Ambulatorio 5')
    r = C.post('/anagrafiche/stanze/%d' % rid, data={'azione': 'elimina'})
    assert reindirizza_elenco(r), 'HTTP %d' % r.status_code
    assert stanza_id(S, 'Ambulatorio 5') is None, 'stanza non eliminata'


prova('rinominata una stanza, la griglia mostra il nome nuovo', st_rinomina)
for nome, dati, frammento in [
        ('nome vuoto', dati_stanza(''), 'Nome: campo obbligatorio'),
        ('nome gia usato con maiuscole diverse', dati_stanza('AMBULATORIO 2'), 'Esiste già una stanza'),
        ('tipo inventato', dati_stanza('Nuova', tipo='CUCINA'), 'Tipo: scelta non valida'),
        ('posizione non numerica', dati_stanza('Nuova', ordine='abc'), 'serve un numero intero'),
        ('posizione oltre 999', dati_stanza('Nuova', ordine='1000'), 'deve stare fra 0 e 999'),
        ('struttura inesistente', dict(dati_stanza('Nuova'), struttura='999'), 'Struttura: scelta non valida')]:
    prova('rifiutato: %s' % nome, fai_rifiuto_stanza(dati, frammento))
prova('nuova stanza in griglia nella posizione indicata', st_nuova_in_griglia)
prova('stanza senza prenotazioni disattivata: esce dalla griglia', st_disattiva_libera)
prova('stanza con prenotazioni future: disattivazione rifiutata', st_disattiva_con_futuro)
prova('stanza con appuntamenti: eliminazione rifiutata', st_elimina_usata)
prova('stanza inutilizzata: eliminata', st_elimina_libera)


# =====================================================================
area('prestazioni e struttura')
S, C = mondo()
nuovo_medico(C, 'Lippiello')
LIP = id_da(S, Operatore, cognome='Lippiello')


def pr_crea():
    r = C.post('/anagrafiche/prestazioni/nuova', data={'nome': 'Isteroscopia', 'durata': '40'})
    assert reindirizza_elenco(r), 'HTTP %d' % r.status_code
    assert 'Isteroscopia (40 min)' in html(C.get('/appuntamento?data=%s' % MARTEDI.isoformat())), \
        'prestazione nuova assente dal modulo di prenotazione'


def fai_rifiuto_prest(dati, frammento):
    def f():
        prima = conta(S, Prestazione)
        r = C.post('/anagrafiche/prestazioni/nuova', data=dati)
        assert r.status_code == 200 and frammento in html(r), 'messaggio atteso assente: %s' % frammento
        assert conta(S, Prestazione) == prima, 'prestazione creata nonostante l errore'
    return f


def pr_elimina_usata():
    pid = id_da(S, Prestazione, nome='Controllo')
    s = S()
    i = datetime.combine(MARTEDI, time(11, 0))
    s.add(Appuntamento(risorsa_id=stanza_id(S, 'Ambulatorio 1'), operatore_id=LIP,
                       prestazione_id=pid, inizio=i, fine=i + timedelta(minutes=20)))
    s.commit(); s.close()
    r = C.post('/anagrafiche/prestazioni/%d' % pid, data={'azione': 'elimina'}, follow_redirects=True)
    assert 'non si può eliminare' in html(r), 'rifiuto non spiegato'
    assert id_da(S, Prestazione, nome='Controllo'), 'eliminata una prestazione in uso'


def pr_elimina_libera():
    pid = id_da(S, Prestazione, nome='Isteroscopia')
    r = C.post('/anagrafiche/prestazioni/%d' % pid, data={'azione': 'elimina'})
    assert reindirizza_elenco(r) and id_da(S, Prestazione, nome='Isteroscopia') is None, 'non eliminata'


def sr_rinomina():
    sid = id_da(S, Struttura, nome=servizi.NOME_INIZIALE)
    # solo il nome: i campi non inviati restano come sono
    r = C.post('/anagrafiche/strutture/%d' % sid, data={'nome': 'Studio Esempio - Poliambulatorio'})
    assert reindirizza_elenco(r), 'HTTP %d' % r.status_code
    svuota_avvisi(C)
    t = html(C.get('/giorno/%s' % MARTEDI.isoformat()))
    assert re.search(r'<option value="%d" selected>Studio Esempio - Poliambulatorio</option>' % sid, t), \
        'nome nuovo assente dal menu delle strutture'


def sr_vuoto():
    sid = id_da(S, Struttura, nome='Studio Esempio - Poliambulatorio')
    r = C.post('/anagrafiche/strutture/%d' % sid, data={'nome': '  '})
    assert r.status_code == 200 and 'campo obbligatorio' in html(r), 'nome vuoto accettato'


prova('nuova prestazione disponibile nella prenotazione', pr_crea)
for nome, dati, frammento in [
        ('doppione con maiuscole diverse', {'nome': 'isteroscopia', 'durata': '30'}, 'Esiste già la prestazione'),
        ('durata 4 minuti', {'nome': 'Breve', 'durata': '4'}, 'deve stare fra 5 e 1440'),
        ('durata oltre un giorno', {'nome': 'Lunga', 'durata': '1441'}, 'deve stare fra 5 e 1440'),
        ('durata non numerica', {'nome': 'Strana', 'durata': 'mezzora'}, 'serve un numero intero'),
        ('nome vuoto', {'nome': '', 'durata': '30'}, 'Nome: campo obbligatorio')]:
    prova('prestazione rifiutata: %s' % nome, fai_rifiuto_prest(dati, frammento))
prova('prestazione in uso: eliminazione rifiutata', pr_elimina_usata)
prova('prestazione inutilizzata: eliminata', pr_elimina_libera)
prova('rinominata la struttura, la griglia la mostra', sr_rinomina)
prova('nome della struttura vuoto: rifiutato', sr_vuoto)


# =====================================================================
area('percorso completo')
S, C = mondo()


def pc_dal_nulla_alla_prenotazione():
    """Quello che fara' la segreteria il primo giorno, tutto dall'interfaccia."""
    assert reindirizza_elenco(nuovo_medico(C, 'Lippiello', specialita='Ginecologia')), 'medico'
    lip = id_da(S, Operatore, cognome='Lippiello')
    a1 = stanza_id(S, 'Ambulatorio 1')
    assert reindirizza_elenco(nuovo_turno(C, lip, a1, giorno=1, dalle='08:00', alle='14:00')), 'turno'
    griglia = html(C.get('/giorno/%s' % MARTEDI.isoformat()))
    assert 'ora=09:30' in griglia and 'libero' in griglia, 'nessuna fascia prenotabile in griglia'
    pid = id_da(S, Prestazione, nome='Prima visita')
    r = C.post('/appuntamento', data={
        'struttura': str(id_da(S, Struttura, nome=servizi.NOME_INIZIALE)), 'risorsa': str(a1),
        'operatore': str(lip), 'prestazione': str(pid), 'data': MARTEDI.isoformat(),
        'ora': '09:30', 'durata': '30', 'paziente': 'Esposito', 'telefono': '0815551234'},
        follow_redirects=True)
    t = html(r)
    assert 'Appuntamento salvato.' in t, 'prenotazione non salvata'
    assert 'fuori dai turni' not in t, 'dentro il turno segnalato come fuori turno'
    assert 'Esposito' in t, 'appuntamento non visibile nella griglia'
    r = C.get('/esporta/%s' % MARTEDI.isoformat())
    import io, openpyxl
    ws = openpyxl.load_workbook(io.BytesIO(r.data)).active
    testi = ' '.join(str(c.value) for riga in ws.iter_rows() for c in riga if c.value)
    assert 'Esposito' in testi and 'Lippiello' in testi, 'appuntamento assente dall Excel'
    return 'medico, turno, prenotazione ed export dall interfaccia'




def pc_propone_medico_di_turno():
    """Aprendo una fascia libera il modulo deve proporre chi e' di turno li',
    non il primo medico in ordine alfabetico."""
    assert reindirizza_elenco(nuovo_medico(C, 'Amato')), 'medico'      # viene prima di Lippiello
    lip, ama = id_da(S, Operatore, cognome='Lippiello'), id_da(S, Operatore, cognome='Amato')
    a1, a3 = stanza_id(S, 'Ambulatorio 1'), stanza_id(S, 'Ambulatorio 3')
    assert reindirizza_elenco(nuovo_turno(C, ama, a3, giorno=1, dalle='08:00', alle='12:00')), 'turno'
    t = html(C.get('/appuntamento?data=%s&ora=10:30&risorsa=%d' % (MARTEDI.isoformat(), a1)))
    assert re.search(r'<option value="%d" selected>Lippiello' % lip, t), 'Ambulatorio 1: non propone Lippiello'
    t = html(C.get('/appuntamento?data=%s&ora=10:30&risorsa=%d' % (MARTEDI.isoformat(), a3)))
    assert re.search(r'<option value="%d" selected>Amato' % ama, t), 'Ambulatorio 3: non propone Amato'
    t = html(C.get('/appuntamento?data=%s&ora=16:00&risorsa=%d' % (MARTEDI.isoformat(), a1)))
    assert ' selected>Lippiello' not in t and ' selected>Amato' not in t, 'fuori turno propone comunque qualcuno'
    t = html(C.get('/appuntamento?data=%s&ora=pippo&risorsa=%d' % (MARTEDI.isoformat(), a1)))
    assert 'Nuovo appuntamento' in t, 'ora non valida nell indirizzo manda in errore'



prova('dal database vuoto alla prenotazione esportata', pc_dal_nulla_alla_prenotazione)
prova('la fascia libera propone il medico di turno', pc_propone_medico_di_turno)


# =====================================================================
area('regressione disattivati')
S, C = mondo()
nuovo_medico(C, 'Lippiello')
nuovo_medico(C, 'Galasso')
LIP, GAL = id_da(S, Operatore, cognome='Lippiello'), id_da(S, Operatore, cognome='Galasso')


def rd_medico_disattivato_resta():
    a3 = stanza_id(S, 'Ambulatorio 3')
    s = S()
    i = datetime.combine(MARTEDI, time(10, 0))
    x = Appuntamento(risorsa_id=a3, operatore_id=GAL, inizio=i, fine=i + timedelta(minutes=30))
    s.add(x); s.commit(); aid = x.id; s.close()
    C.post('/anagrafiche/medici/%d' % GAL, data={'cognome': 'Galasso', 'colore': '#154381'})
    t = html(C.get('/appuntamento/%d' % aid))
    assert re.search(r'<option value="%d" selected>Galasso' % GAL, t), \
        'il medico disattivato non e selezionato nella modifica'
    r = C.post('/appuntamento/%d' % aid, data={
        'struttura': '1', 'risorsa': str(a3), 'operatore': str(GAL),
        'prestazione': str(id_da(S, Prestazione, nome='Controllo')), 'data': MARTEDI.isoformat(),
        'ora': '10:00', 'durata': '30', 'note': 'solo una nota'})
    s = S(); y = s.get(Appuntamento, aid); s.close()
    assert y.operatore_id == GAL and y.note == 'solo una nota', \
        'salvando una nota l appuntamento ha cambiato medico'


def rd_stanza_disattivata_resta():
    a2 = stanza_id(S, 'Ambulatorio 2')
    s = S()
    i = datetime.combine(MARTEDI_PASSATO, time(9, 0))
    x = Appuntamento(risorsa_id=a2, operatore_id=LIP, inizio=i, fine=i + timedelta(minutes=30))
    s.add(x); s.commit(); aid = x.id; s.close()
    r = C.post('/anagrafiche/stanze/%d' % a2, data={'nome': 'Ambulatorio 2', 'tipo': 'AMBULATORIO',
                                                    'struttura': '1', 'ordine': '2'})
    assert reindirizza_elenco(r), 'stanza con soli appuntamenti passati non disattivata'
    t = html(C.get('/appuntamento/%d' % aid))
    assert re.search(r'<option value="%d"[^>]* selected>Ambulatorio 2' % a2, t), \
        'la stanza disattivata non e selezionata nella modifica'


prova('medico disattivato: modificando l appuntamento non cambia medico', rd_medico_disattivato_resta)
prova('stanza disattivata: resta selezionata negli appuntamenti passati', rd_stanza_disattivata_resta)


# =====================================================================
area('robustezza')
S, C = mondo()
nuovo_medico(C, 'Lippiello')
VELENI = ['', ' ', '0', '-1', '99999', '1.5', 'abc', '<script>x</script>', "' OR 1=1 --",
          '\x00', 'A' * 300, 'àèìòù', '🙂', '25:99', '2026-13-45', '#GGGGGG', '#FFFFFF', 'on', '1']
PERCORSI = ['/anagrafiche/medici/nuovo', '/anagrafiche/stanze/nuova', '/anagrafiche/prestazioni/nuova',
            '/anagrafiche/turni/nuovo', '/anagrafiche/strutture/1']
CAMPI = ['cognome', 'nome', 'specialita', 'colore', 'attivo', 'tipo', 'struttura', 'ordine', 'attiva',
         'durata', 'operatore', 'risorsa', 'giorno', 'ora_inizio', 'ora_fine', 'valido_da', 'valido_a',
         'azione']


def ro_vuoti():
    guasti = []
    for p in PERCORSI:
        r = C.post(p, data={})
        if r.status_code >= 500:
            guasti.append('%s -> %d' % (p, r.status_code))
    assert not guasti, guasti


def ro_casuali():
    caso = random.Random(4242)
    guasti = []
    for n in range(400):
        p = caso.choice(PERCORSI)
        dati = {k: caso.choice(VELENI) for k in caso.sample(CAMPI, caso.randint(1, 10))}
        dati.pop('azione', None)       # le eliminazioni hanno prove dedicate
        r = C.post(p, data=dati)
        if r.status_code >= 500:
            guasti.append('%s %s -> %d' % (p, sorted(dati), r.status_code))
    assert not guasti, '%d risposte 5xx, per esempio %s' % (len(guasti), guasti[:2])
    s = S()
    medici_vuoti = s.scalar(select(func.count()).select_from(Operatore).where(
        func.trim(Operatore.cognome) == ''))
    colori = [c for c in s.scalars(select(Operatore.colore)) if not re.fullmatch(r'#[0-9a-f]{6}', c or '')]
    turni_storti = s.scalar(select(func.count()).select_from(Turno).where(Turno.ora_fine <= Turno.ora_inizio))
    stanze_vuote = s.scalar(select(func.count()).select_from(Risorsa).where(func.trim(Risorsa.nome) == ''))
    s.close()
    assert not medici_vuoti, 'salvati medici senza cognome'
    assert not colori, 'salvati colori non validi: %s' % colori[:3]
    assert not turni_storti, 'salvati turni con fine non successiva all inizio'
    assert not stanze_vuote, 'salvate stanze senza nome'
    return '400 invii con valori sporchi, nessun 5xx, nessun dato incoerente'


def ro_escaping():
    nuovo_medico(C, '<script>alert(1)</script>', nome='<img src=x onerror=alert(2)>')
    oid = id_da(S, Operatore, cognome='<script>alert(1)</script>')
    nuovo_turno(C, oid, stanza_id(S, 'Ambulatorio 3'), giorno=1)
    for pagina in ('/anagrafiche', '/giorno/%s' % MARTEDI.isoformat(),
                   '/appuntamento?data=%s' % MARTEDI.isoformat(), '/anagrafiche/medici/%d' % oid):
        t = html(C.get(pagina))
        assert '<script>alert(1)' not in t and '<img src=x' not in t, 'testo non neutralizzato in %s' % pagina


def ro_doppio_clic():
    barriera = threading.Barrier(2)

    def invia():
        cl = A.app.test_client()
        barriera.wait()
        nuovo_medico(cl, 'Doppioclic')

    fili = [threading.Thread(target=invia) for _ in range(2)]
    for f in fili: f.start()
    for f in fili: f.join()
    n = conta(S, Operatore, Operatore.cognome == 'Doppioclic')
    assert n == 1, 'due invii simultanei hanno creato %d medici' % n


def ro_id_non_numerici():
    for p in ('/anagrafiche/medici/abc', '/anagrafiche/stanze/-1', '/anagrafiche/turni/1.5',
              '/anagrafiche/prestazioni/99999', '/anagrafiche/strutture/0'):
        r = C.get(p)
        assert r.status_code == 404, '%s -> %d invece di 404' % (p, r.status_code)


prova('invii vuoti su ogni pagina: nessun errore 5xx', ro_vuoti)
prova('400 invii casuali con valori sporchi', ro_casuali)
prova('testo malevolo nei nomi: neutralizzato ovunque', ro_escaping)
prova('doppio clic su Salva: un solo medico', ro_doppio_clic)
prova('indirizzi con id impossibili: 404', ro_id_non_numerici)


# =====================================================================
ordine = []
for e in esiti:
    if e[1] not in ordine:
        ordine.append(e[1])
print()
for ar in ordine:
    gruppo = [e for e in esiti if e[1] == ar]
    rotti = [e for e in gruppo if e[0] != 'OK']
    print('%-26s %3d prove  %s' % (ar, len(gruppo), 'tutte a posto' if not rotti else '%d DA SISTEMARE' % len(rotti)))
guasti = [e for e in esiti if e[0] != 'OK']
if guasti:
    print('\nDettaglio:')
    for stato, ar, nome, msg in guasti:
        print('  %-6s [%s] %s\n         %s' % (stato, ar, nome, msg))
print('\n%d prove totali, %d superate, %d da sistemare'
      % (len(esiti), len(esiti) - len(guasti), len(guasti)))

A._registro = None
for f in _file:
    try:
        os.remove(f)
    except OSError:
        pass
