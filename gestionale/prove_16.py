# -*- coding: utf-8 -*-
"""Prove della 1.6: «Aggiorna adesso» (il programma si accorge da solo delle
versioni nuove, scarica il Setup, lo controlla e lo installa), la pagina delle
novita' e le videoguide.

Niente rete vera: gli aggiornamenti arrivano da una cartella o da un finto
sito https su 127.0.0.1 che rimanda i file a un altro indirizzo, come fa
GitHub. Il Setup non parte davvero: si controlla il comando che lo
avvierebbe. La prova vera, con il Setup che chiude, aggiorna e riapre il
programma, si fa con l'eseguibile su Windows (vedi LEGGIMI)."""
import hashlib
import json
import os
import random
import re
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time as orologio
import traceback
from datetime import date, datetime, timedelta
from html import unescape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# i finti server stanno su 127.0.0.1: niente proxy di sistema in mezzo
os.environ['NO_PROXY'] = os.environ['no_proxy'] = '127.0.0.1,localhost'
import logging
logging.getLogger().setLevel(logging.CRITICAL)      # gli errori voluti delle prove non sporcano l'uscita

import mimetypes
from sqlalchemy import select

import servizi
import viste
import guida
import novita
import backup
import comune
import aggiornamenti as AG
import app as A
from modelli import (crea_sessione, Struttura, Risorsa, Operatore, Prestazione, Appuntamento, Paziente, Invio,
                     leggi_impostazione, scrivi_impostazione)

A.app.config['TESTING'] = True
CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = os.path.join(CARTELLA, 'prove_16_tmp')
shutil.rmtree(PROVVISORIA, ignore_errors=True)
os.makedirs(PROVVISORIA)
esiti, _area, _n = [], [''], [0]
OGGI = date.today()
SOLO = [x for x in os.environ.get('PROVE_SOLO', '').split(',') if x]
# l'indirizzo predefinito vero (le versioni su GitHub) si prova a parte e senza rete
# (i_predefinito_vero, i_rimetti_predefinito): le altre prove partono da un programma
# senza indirizzo, cosi' nessuna va su internet
PREDEFINITO_VERO = AG.INDIRIZZO_PREDEFINITO
AG.INDIRIZZO_PREDEFINITO = ''
ORIGINALI = {k: getattr(AG, k) for k in ('lancia', 'installato', 'contesto_tls', 'ATTESA_RETE', 'ATTESA_PRIMA_DEL_SETUP',
                                          'INDIRIZZO_PREDEFINITO', 'controlla_in_sottofondo', 'apri', '_un_controllo')}


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
    finally:
        for k, v in ORIGINALI.items():
            setattr(AG, k, v)
        azzera()


def azzera():
    AG.stato.update(controllato_il=None, errore=None, errore_il=None, disponibile=None, pronto=None,
                    scaricati=0, totale=0, in_corso=False, partito=None)


# ================================================================ il mondo
def mondo(con_dati=False):
    """Un gestionale nuovo, ognuno nella sua cartella: accanto al database
    nascono le cartelle "aggiornamenti" e "backup"."""
    _n[0] += 1
    dove = os.path.join(PROVVISORIA, 'm%d' % _n[0])
    os.makedirs(dove)
    S = crea_sessione('sqlite:///' + os.path.join(dove, 'agende.db'))
    s = S()
    servizi.prepara_primo_avvio(s)
    if con_dati:
        p = Paziente(cognome='Fintini', nome='Prova', telefono='3330000001')
        o = Operatore(cognome='Provolo', nome='Ugo')
        s.add_all([p, o])
        s.flush()
        st = s.scalars(select(Risorsa)).first()
        nove = datetime.combine(OGGI, datetime.min.time()).replace(hour=9)
        s.add(Appuntamento(risorsa_id=st.id, operatore_id=o.id, paziente_id=p.id, inizio=nove,
                           fine=nove + timedelta(minutes=30), stato='PRENOTATO'))
    s.commit()
    s.close()
    A.Sessione = S
    A._registro = None
    viste._sessionmaker = lambda: S
    azzera()
    return S, A.app.test_client(), dove


def fabbrica():
    return A.Sessione()


def html(r):
    return r.get_data(as_text=True)


def testo(r):
    return ' '.join(unescape(re.sub(r'<[^>]+>', ' ', html(r))).split())


def avvisi(C):
    with C.session_transaction() as sess:
        return ' '.join(t for _, t in sess.get('_flashes', []))


def imposta(S, **valori):
    s = S()
    for k, v in valori.items():
        scrivi_impostazione(s, k, v)
    s.commit()
    s.close()


def leggi(S, chiave, difetto=''):
    s = S()
    try:
        return leggi_impostazione(s, chiave, difetto)
    finally:
        s.close()


def setup_finto(byte=1300000, seme=16):
    return b'MZ' + random.Random(seme).randbytes(byte - 2)


def manifesto(numero, dati, **cambi):
    m = {'programma': 'Gestionale Agende', 'variante': AG.VARIANTE, 'versione': numero, 'file': AG.NOME_SETUP,
         'byte': len(dati), 'sha256': hashlib.sha256(dati).hexdigest(), 'pubblicata': OGGI.isoformat(),
         'novita': [{'versione': numero, 'voci': [{'titolo': 'Correzioni', 'testo': 'Piccole correzioni di prova.'}]}]
         + novita.per_manifesto()}
    m.update(cambi)
    return m


def pubblica(dove, numero='1.6.1', dati=None, **cambi):
    """Una cartella con il file delle versioni e il Setup, come la release su GitHub."""
    dati = setup_finto() if dati is None else dati
    os.makedirs(dove, exist_ok=True)
    with open(os.path.join(dove, AG.NOME_SETUP), 'wb') as f:
        f.write(dati)
    with open(os.path.join(dove, AG.MANIFESTO), 'w', encoding='utf-8') as f:
        json.dump(manifesto(numero, dati, **cambi), f)
    return dove


def nuova_versione(passo=1):
    """Una versione sicuramente piu' nuova di quella installata (con un passo piu'
    lungo, una ancora piu' nuova), di quattro numeri al massimo come vuole il file
    delle versioni: dalla 1.7 la 1.7.1, dalla 1.7.1 la 1.7.1.1."""
    n = novita.numeri(comune.VERSIONE)
    n = n + [passo] if len(n) < 4 else n[:-1] + [n[-1] + passo]
    return '.'.join(str(x) for x in n)


def pronto(S, dove):
    """Un gestionale con l'aggiornamento gia' scaricato e controllato."""
    sorgente = pubblica(os.path.join(dove, 'pubblicata'), nuova_versione())
    imposta(S, aggiornamenti_indirizzo=sorgente)
    AG.controlla(fabbrica)
    assert AG.stato['pronto'] and not AG.stato['errore'], AG.stato
    return sorgente


# ================================================= versioni e novita'
area('versioni e novità')


def confronta_come_il_setup(a, b):
    """ConfrontaVersioni di installer.iss, riga per riga (Pascal): SoloNumeri,
    PrimoNumero con StrToIntDef(Trim(...), 0)."""
    def solo_numeri(v):
        v = v.strip(' ')
        return v[:v.index(' ')] if ' ' in v else v

    def str_to_int_def(t):
        t = t.strip(' ')
        return int(t) if re.fullmatch(r'[+-]?\d+', t) and abs(int(t)) < 2 ** 31 else 0

    def primo_numero(t):
        if '.' not in t:
            return str_to_int_def(t), ''
        i = t.index('.')
        return str_to_int_def(t[:i]), t[i + 1:]
    a, b, r = solo_numeri(a), solo_numeri(b), 0
    while r == 0 and (a != '' or b != ''):
        x, a = primo_numero(a)
        y, b = primo_numero(b)
        r = -1 if x < y else (1 if x > y else 0)
    return r


def n_confronto():
    for a, b, atteso in (('1.6', '1.6.0', 0), ('1.6.1', '1.6', 1), ('1.5', '1.6', -1), ('1.10', '1.9', 1),
                         ('1.6 animata', '1.6', 0), ('1.4.6 animata', '1.5', -1), ('2', '1.99.99', 1), ('', '0', 0)):
        assert novita.confronta(a, b) == atteso, (a, b, novita.confronta(a, b))
        assert confronta_come_il_setup(a, b) == atteso, ('setup', a, b)
    caso = random.Random(6)
    pezzi = ['1', '6', '0', '10', '2', '', 'x', '01', ' 3']
    for _ in range(3000):
        a = '.'.join(caso.choice(pezzi) for _ in range(caso.randint(1, 4))) + caso.choice(['', ' animata'])
        b = '.'.join(caso.choice(pezzi) for _ in range(caso.randint(1, 4))) + caso.choice(['', ' animata'])
        assert novita.confronta(a, b) == confronta_come_il_setup(a, b), (a, b)
    return '3000 coppie a caso: stesso risultato del Setup'


def n_novita_dati():
    versioni = [v for v, _ in novita.NOVITA]
    assert versioni[0] == comune.VERSIONE, 'novita.py non comincia dalla versione del programma: %s' % versioni[0]
    assert all(novita.confronta(versioni[i], versioni[i + 1]) > 0 for i in range(len(versioni) - 1)), versioni
    for v, voci in novita.NOVITA:
        assert voci and AG.VERSIONE_VALIDA.fullmatch(v), v
        for x in voci:
            assert set(x) == {'titolo', 'testo', 'guida'} and x['titolo'] and len(x['testo']) > 20, x
            assert x['guida'] is None or x['guida'] in guida.PER_SLUG, 'guida inesistente: %s' % x['guida']
    # nel file delle versioni passano intere
    m = AG.valida(json.dumps(manifesto(nuova_versione(), setup_finto())).encode())
    assert m['novita'][1:] == novita.per_manifesto(), 'novità perse nel file delle versioni'
    assert [v for v, _ in novita.dopo('1.5', '1.6')] == ['1.6']
    assert [v for v, _ in novita.dopo('', '1.6')] == ['1.6']
    assert [v for v, _ in novita.dopo('1.4.6', '1.6')] == ['1.6', '1.5']
    assert novita.dopo('1.6', '1.6') == [] and novita.dopo('1.7', '1.6') == []


prova('confronto delle versioni identico a quello del Setup (installer.iss)', n_confronto)
prova('novità: versioni in ordine, guide esistenti, passano intere nel file delle versioni', n_novita_dati)


# ============================================================ indirizzo
area('indirizzo degli aggiornamenti')


def i_normalizza():
    gh = 'https://github.com/rossi/gestionale/releases/latest/download/'
    for scritto, atteso in (
            ('https://github.com/rossi/gestionale', gh), ('https://github.com/rossi/gestionale/', gh),
            ('  "https://github.com/rossi/gestionale.git"  ', gh), ('https://www.github.com/rossi/gestionale/releases', gh),
            ('https://github.com/rossi/gestionale/releases/tag/v1.6', gh),
            ('HTTPS://github.com/rossi/gestionale/releases/latest', gh),
            ('https://github.com/rossi/gestionale/releases/download/v1.6/GestionaleAgende-setup.exe',
             'https://github.com/rossi/gestionale/releases/download/v1.6/'),
            ('https://esempio.example.com/agg', 'https://esempio.example.com/agg/'),
            ('https://esempio.example.com:8443/agg/aggiornamento.json?x=1#y', 'https://esempio.example.com:8443/agg/'),
            ('https://esempio.example.com', 'https://esempio.example.com/'),
            ('', ''), ('   ', '')):
        base, errore = AG.normalizza(scritto)
        assert errore is None and base == atteso, (scritto, base, errore)
    cartella = os.path.join(PROVVISORIA, 'una cartella')
    assert AG.normalizza(cartella) == (os.path.normpath(cartella), None)
    assert AG.normalizza(os.path.join(cartella, AG.MANIFESTO)) == (os.path.normpath(cartella), None)
    for sbagliato in ('http://github.com/rossi/gestionale', 'ftp://esempio.example.com/x', 'file:///etc/passwd',
                      'javascript:alert(1)', 'https://utente:segreto@esempio.example.com/', 'https://github.com/rossi',
                      'https://github.com/../x', 'https://:80/', 'https://esempio.example.com:porta/', 'cartella/relativa',
                      'aggiornamenti', 'https://esempio.example.com/\x00', 'https://x.example.com/' + 'a' * 500):
        base, errore = AG.normalizza(sbagliato)
        assert base is None and errore, (sbagliato, base, errore)
    assert 'https' in AG.normalizza('http://esempio.example.com/')[1]


def i_pagina_salva():
    S, C, dove = mondo()
    t = testo(C.get('/aggiornamenti'))
    assert 'spenti' in t and 'Versione installata: %s' % comune.VERSIONE in t, t[:400]
    controllati = []
    AG.controlla_in_sottofondo = lambda fabbrica=None: controllati.append(1)
    r = C.post('/aggiornamenti', data={'azione': 'indirizzo', 'indirizzo': 'https://github.com/rossi/gestionale'})
    assert r.status_code == 302 and controllati == [1], (r.status_code, controllati)
    assert leggi(S, AG.CHIAVE) == 'https://github.com/rossi/gestionale/releases/latest/download/'
    assert 'releases/latest/download/' in html(C.get('/aggiornamenti'))
    r = C.post('/aggiornamenti', data={'azione': 'indirizzo', 'indirizzo': 'http://sito.example.com/'})
    assert 'https://' in avvisi(C) and leggi(S, AG.CHIAVE).startswith('https://github.com'), 'http accettato'
    C.get('/aggiornamenti')
    C.post('/aggiornamenti', data={'azione': 'indirizzo', 'indirizzo': ''})
    assert leggi(S, AG.CHIAVE, 'manca') == '' and 'spenti' in avvisi(C), 'spegnere non riuscito'
    C.get('/aggiornamenti')
    # "Controlla adesso" senza indirizzo: lo dice, non controlla
    n = len(controllati)
    C.post('/aggiornamenti', data={'azione': 'controlla'})
    assert len(controllati) == n and 'indirizzo' in avvisi(C)
    # con l'indirizzo, Controlla adesso parte
    imposta(S, aggiornamenti_indirizzo=PROVVISORIA)
    C.get('/aggiornamenti')
    C.post('/aggiornamenti', data={'azione': 'controlla'})
    assert len(controllati) == n + 1


def i_predefinito():
    S, C, dove = mondo()
    sorgente = pubblica(os.path.join(dove, 'pubblicata'), nuova_versione())
    AG.INDIRIZZO_PREDEFINITO = sorgente
    assert AG.indirizzo_configurato(fabbrica) == sorgente, 'senza riga nelle impostazioni vale il predefinito'
    imposta(S, aggiornamenti_indirizzo='')
    assert AG.indirizzo_configurato(fabbrica) == '', 'svuotato nella pagina: spento anche con il predefinito'


def i_predefinito_vero():
    """L'indirizzo con cui esce il programma: le versioni del Gestionale Agende su
    GitHub. Alla clinica non c'e' niente da scrivere."""
    gh = 'https://github.com/number959/gestionale-agende-versioni'
    assert PREDEFINITO_VERO == gh, PREDEFINITO_VERO
    assert AG.normalizza(PREDEFINITO_VERO) == (gh + '/releases/latest/download/', None)
    AG.INDIRIZZO_PREDEFINITO = PREDEFINITO_VERO
    S, C, dove = mondo()
    assert AG.indirizzo_configurato(fabbrica) == AG.predefinito() == gh + '/releases/latest/download/'
    h = html(C.get('/aggiornamenti'))
    t = testo(C.get('/aggiornamenti'))
    assert 'value="%s"' % gh in h, 'nel campo l\'indirizzo predefinito'
    stato_pagina = t.split('Da dove arrivano')[0]
    assert 'spenti' not in stato_pagina and 'Il programma controlla da solo poco dopo l\'avvio' in stato_pagina, stato_pagina
    assert 'Controlla adesso' in stato_pagina, 'manca Controlla adesso'
    assert 'È l\'indirizzo predefinito , le versioni del Gestionale Agende su GitHub' in t, t[-900:]
    assert 'rimetti-predefinito' not in h, '«Rimetti l\'indirizzo predefinito» con il predefinito già in uso'


def i_rimetti_predefinito():
    AG.INDIRIZZO_PREDEFINITO = PREDEFINITO_VERO
    S, C, dove = mondo()
    controllati = []
    AG.controlla_in_sottofondo = lambda fabbrica=None: controllati.append(AG.indirizzo_configurato(fabbrica))
    altra = os.path.normpath(os.path.join(dove, 'altra'))
    C.post('/aggiornamenti', data={'azione': 'indirizzo', 'indirizzo': altra})
    assert leggi(S, AG.CHIAVE) == altra and controllati == [altra], controllati
    h = html(C.get('/aggiornamenti'))
    assert 'form="rimetti-predefinito"' in h and '<form method="post" id="rimetti-predefinito" hidden>' in h, 'manca Rimetti'
    assert 'È l\'indirizzo predefinito' not in testo(C.get('/aggiornamenti'))
    r = C.post('/aggiornamenti', data={'azione': 'predefinito'})
    assert r.status_code == 302 and 'Rimesso l\'indirizzo predefinito' in avvisi(C), avvisi(C)
    assert leggi(S, AG.CHIAVE, 'nessuna riga') == 'nessuna riga', 'resta la riga: non seguirebbe un predefinito nuovo'
    assert controllati[-1] == AG.predefinito(), ('dopo Rimetti il controllo parte dal predefinito', controllati)
    h = html(C.get('/aggiornamenti'))
    assert 'value="%s"' % PREDEFINITO_VERO in h and 'rimetti-predefinito' not in h
    # spenti (indirizzo vuoto): la pagina dice come riaccenderli
    C.post('/aggiornamenti', data={'azione': 'indirizzo', 'indirizzo': ''})
    assert leggi(S, AG.CHIAVE, 'nessuna riga') == '' and AG.indirizzo_configurato(fabbrica) == ''
    C.get('/aggiornamenti')
    t = testo(C.get('/aggiornamenti'))
    assert 'spenti' in t and 'Rimetti l\'indirizzo predefinito li riaccende' in t, t[:500]
    n = len(controllati)
    C.post('/aggiornamenti', data={'azione': 'predefinito'})
    assert len(controllati) == n + 1 and AG.indirizzo_configurato(fabbrica) == AG.predefinito()
    # scritto a mano (anche con .git o con la pagina delle versioni): e' il predefinito, niente riga
    for scritto in (PREDEFINITO_VERO + '.git', PREDEFINITO_VERO + '/releases'):
        C.post('/aggiornamenti', data={'azione': 'indirizzo', 'indirizzo': altra})
        assert leggi(S, AG.CHIAVE) == altra
        C.post('/aggiornamenti', data={'azione': 'indirizzo', 'indirizzo': scritto})
        assert leggi(S, AG.CHIAVE, 'nessuna riga') == 'nessuna riga', scritto
    # un programma costruito senza indirizzo predefinito: niente pulsante, Rimetti spegne
    AG.INDIRIZZO_PREDEFINITO = ''
    C.post('/aggiornamenti', data={'azione': 'indirizzo', 'indirizzo': altra})
    h = html(C.get('/aggiornamenti'))
    assert 'rimetti-predefinito' not in h and 'È l\'indirizzo predefinito' not in h and 'li riaccende' not in h
    n = len(controllati)
    C.post('/aggiornamenti', data={'azione': 'predefinito'})
    assert AG.indirizzo_configurato(fabbrica) == '' and len(controllati) == n


prova('indirizzo: GitHub, altri siti https, cartelle; http e il resto rifiutati', i_normalizza)
prova('pagina: salvare, rifiutare http, spegnere; Controlla adesso senza indirizzo', i_pagina_salva)
prova('indirizzo predefinito usato finché nella pagina non se ne scrive un altro', i_predefinito)
prova('il programma esce con l\'indirizzo delle versioni su GitHub: niente da scrivere alla clinica', i_predefinito_vero)
prova('«Rimetti l\'indirizzo predefinito»: dopo un altro indirizzo o dopo averli spenti', i_rimetti_predefinito)


# ================================================= controllo da una cartella
area('controllo e scaricamento (cartella)')


def c_nuova_versione():
    S, C, dove = mondo()
    nuova = nuova_versione()
    sorgente = pubblica(os.path.join(dove, 'pubblicata'), nuova)
    imposta(S, aggiornamenti_indirizzo=sorgente)
    assert AG.controlla(fabbrica) is True
    st = AG.stato
    assert st['errore'] is None and st['disponibile']['versione'] == nuova, st
    assert st['pronto'] == os.path.join(dove, 'aggiornamenti', AG.nome_locale(st['disponibile'])), st['pronto']
    assert AG.file_giusto(st['pronto'], st['disponibile']) and st['scaricati'] == st['totale'] > 0
    assert not [n for n in os.listdir(os.path.join(dove, 'aggiornamenti')) if n.endswith('.parziale')]
    n = json.loads(html(C.get('/notifiche.json')))
    agg = [x for x in n if x['chiave'] == 'aggiornamento-%s' % nuova]
    assert agg and agg[0]['link'] == '/aggiornamenti' and 'Aggiorna adesso' in agg[0]['testo'], n
    t = testo(C.get('/aggiornamenti'))
    assert 'È pronta la versione %s' % nuova in t and 'Correzioni. Piccole correzioni di prova.' in t, t
    assert 'data-guida="aggiorna-adesso"' in html(C.get('/aggiornamenti'))
    # le novita' delle versioni gia' installate non si ripetono
    assert 'Videoguide' not in t, 'novità già installate mostrate di nuovo'
    return 'scaricato e controllato: %s' % os.path.basename(st['pronto'])


def c_stessa_o_vecchia():
    S, C, dove = mondo()
    for versione in (comune.VERSIONE, comune.VERSIONE + '.0', '1.5', '0.9'):
        sorgente = pubblica(os.path.join(dove, 'p' + versione), versione)
        imposta(S, aggiornamenti_indirizzo=sorgente)
        AG.controlla(fabbrica)
        assert AG.stato['disponibile'] is None and AG.stato['pronto'] is None and AG.stato['errore'] is None, (versione, AG.stato)
        assert AG.stato['controllato_il'] is not None
    t = testo(C.get('/aggiornamenti'))
    assert 'Il programma è aggiornato' in t, t
    assert not [x for x in json.loads(html(C.get('/notifiche.json'))) if x['chiave'].startswith('aggiornamento')]
    assert not os.path.exists(os.path.join(dove, 'aggiornamenti')) or not os.listdir(os.path.join(dove, 'aggiornamenti'))


def c_manifesti_sbagliati():
    S, C, dove = mondo()
    dati = setup_finto()
    casi = [({'programma': 'Altro programma'}, 'non è del Gestionale'),
            ({'variante': 'normale' if AG.VARIANTE == 'animata' else 'animata'}, 'è per la versione'),
            ({'versione': '1.6.1-beta'}, 'versione non è valida'), ({'versione': 161}, 'versione non è valida'),
            ({'file': '../GestionaleAgende-setup.exe'}, 'nome del Setup'), ({'file': 'cartella/setup.exe'}, 'nome del Setup'),
            ({'file': 'setup.bat'}, 'nome del Setup'), ({'file': 'C:\\setup.exe'}, 'nome del Setup'),
            ({'byte': True}, 'dimensione'), ({'byte': '1300000'}, 'dimensione'), ({'byte': 1000}, 'dimensione'),
            ({'byte': 10 ** 10}, 'dimensione'), ({'sha256': 'abc'}, 'impronta'), ({'sha256': None}, 'impronta')]
    for i, (cambi, atteso) in enumerate(casi):
        sorgente = pubblica(os.path.join(dove, 'p%d' % i), nuova_versione(), dati, **cambi)
        imposta(S, aggiornamenti_indirizzo=sorgente)
        AG.controlla(fabbrica)
        assert AG.stato['errore'] and atteso in AG.stato['errore'] and not AG.stato['pronto'], (cambi, AG.stato['errore'])
    for i, contenuto in enumerate((b'non json', b'\xff\xfe\x00', b'[1, 2]', b'null', b' ' * (300 * 1024), b'[' * 50000)):
        sorgente = os.path.join(dove, 'r%d' % i)
        os.makedirs(sorgente)
        open(os.path.join(sorgente, AG.MANIFESTO), 'wb').write(contenuto)
        imposta(S, aggiornamenti_indirizzo=sorgente)
        AG.controlla(fabbrica)
        assert AG.stato['errore'] and not AG.stato['pronto'], (contenuto[:10], AG.stato)
    assert not os.path.exists(os.path.join(dove, 'aggiornamenti')) or not os.listdir(os.path.join(dove, 'aggiornamenti'))
    # qualunque cosa arrivi, valida() risponde con un dizionario controllato o con ErroreAggiornamento
    caso = random.Random(16)
    valori = [None, True, 0, -1, 1300000, 10 ** 30, 1.5, '', 'x', '1.6.1', AG.NOME_SETUP, 'a' * 64, [], {}, [1], {'a': 1},
              [{'versione': '1.7', 'voci': [{'titolo': 1, 'testo': []}]}], [{'versione': 'x', 'voci': 'y'}]]
    chiavi = ['programma', 'variante', 'versione', 'file', 'byte', 'sha256', 'novita', 'pubblicata']
    buoni = 0
    for _ in range(1500):
        m = manifesto(nuova_versione(), dati)
        for k in caso.sample(chiavi, caso.randint(0, 3)):
            m[k] = caso.choice(valori)
        try:
            v = AG.valida(json.dumps(m).encode())
        except AG.ErroreAggiornamento:
            continue
        buoni += 1
        assert set(v) == {'versione', 'file', 'byte', 'sha256', 'novita', 'pubblicata'} and type(v['byte']) is int
        assert all(set(n) == {'versione', 'voci'} and all(set(x) == {'titolo', 'testo'} for x in n['voci']) for n in v['novita'])
    return '1500 file delle versioni storpiati: %d accettati, tutti puliti' % buoni


def c_setup_rovinato():
    S, C, dove = mondo()
    dati = setup_finto()
    casi = (('impronta', dati[:-1] + bytes([dati[-1] ^ 1]), {}, 'impronta'),
            ('corto', dati[:-1000], {'byte': len(dati), 'sha256': hashlib.sha256(dati).hexdigest()}, 'interrotto'),
            ('lungo', dati + b'x' * 5000, {'byte': len(dati), 'sha256': hashlib.sha256(dati).hexdigest()}, 'più grande'),
            ('non exe', b'PK' + dati[2:], {}, 'programma Windows'))
    for nome, contenuto, cambi, atteso in casi:
        sorgente = os.path.join(dove, nome)
        os.makedirs(sorgente)
        open(os.path.join(sorgente, AG.NOME_SETUP), 'wb').write(contenuto)
        m = manifesto(nuova_versione(), contenuto if nome == 'non exe' else dati, **cambi)
        open(os.path.join(sorgente, AG.MANIFESTO), 'w').write(json.dumps(m))
        imposta(S, aggiornamenti_indirizzo=sorgente)
        AG.controlla(fabbrica)
        assert AG.stato['errore'] and atteso in AG.stato['errore'] and not AG.stato['pronto'], (nome, AG.stato['errore'])
        assert AG.stato['disponibile'] is not None, 'la versione si sa, anche se il Setup non va'
        resti = os.listdir(os.path.join(dove, 'aggiornamenti'))
        assert resti == [], (nome, resti)
    t = testo(C.get('/aggiornamenti'))
    assert 'È uscita la versione' in t and 'Non è ancora stata scaricata' in t, t


def c_gia_scaricato():
    S, C, dove = mondo()
    sorgente = pronto(S, dove)
    primo = AG.stato['pronto']
    aperti = []
    vero = AG.apri
    AG.apri = lambda base, nome: (aperti.append(nome), vero(base, nome))[1]
    try:
        AG.controlla(fabbrica)
        assert AG.stato['pronto'] == primo and aperti == [AG.MANIFESTO], aperti
        # dopo un riavvio lo stato in memoria non c'e' piu': il file gia' scaricato si riusa
        azzera()
        aperti.clear()
        AG.controlla(fabbrica)
        assert AG.stato['pronto'] == primo and aperti == [AG.MANIFESTO], ('riscaricato', aperti)
        # un file rovinato nella cartella si riscarica
        with open(primo, 'r+b') as f:
            f.seek(100)
            f.write(b'\x00\x00\x00')
        azzera()
        aperti.clear()
        AG.controlla(fabbrica)
        assert aperti == [AG.MANIFESTO, AG.NOME_SETUP] and AG.file_giusto(primo, AG.stato['disponibile']), aperti
    finally:
        AG.apri = vero
    assert sorgente


def c_cartella_irraggiungibile():
    S, C, dove = mondo()
    imposta(S, aggiornamenti_indirizzo=os.path.join(dove, 'non-esiste'))
    AG.controlla(fabbrica)
    assert 'non si raggiunge' in AG.stato['errore'], AG.stato['errore']
    vuota = os.path.join(dove, 'vuota')
    os.makedirs(vuota)
    imposta(S, aggiornamenti_indirizzo=vuota)
    AG.controlla(fabbrica)
    assert "non c'è il file %s" % AG.MANIFESTO in AG.stato['errore'], AG.stato['errore']
    t = testo(C.get('/aggiornamenti'))
    assert 'Ultimo controllo non riuscito' in t and AG.MANIFESTO in t, t


def c_un_controllo_alla_volta():
    S, C, dove = mondo()
    sorgente = pubblica(os.path.join(dove, 'pubblicata'), nuova_versione())
    imposta(S, aggiornamenti_indirizzo=sorgente)
    vero = AG.apri
    entrati, via = threading.Event(), threading.Event()

    def lento(base, nome):
        entrati.set()
        via.wait(5)
        return vero(base, nome)
    AG.apri = lento
    try:
        t = threading.Thread(target=AG.controlla, args=(fabbrica,))
        t.start()
        assert entrati.wait(5)
        assert AG.controlla(fabbrica) is False, 'due controlli insieme'
        assert json.loads(html(C.get('/aggiornamenti/stato.json')))['in_corso'] is True
        assert 'Controllo in corso' in testo(C.get('/aggiornamenti'))
        # cambiato l'indirizzo mentre il controllo e' in corso: il nuovo controllo aspetta e poi parte
        altra = pubblica(os.path.join(dove, 'altra'), nuova_versione(5))
        C.post('/aggiornamenti', data={'azione': 'indirizzo', 'indirizzo': altra})
        via.set()
        t.join(10)
        for _ in range(100):
            if not AG.stato['in_corso'] and AG.stato['disponibile'] and AG.stato['disponibile']['versione'] == nuova_versione(5):
                break
            orologio.sleep(0.1)
    finally:
        AG.apri = vero
    assert AG.stato['pronto'] and not AG.stato['in_corso'], AG.stato
    assert AG.stato['disponibile']['versione'] == nuova_versione(5), ('controllato il vecchio indirizzo', AG.stato)


prova('versione nuova in una cartella: scaricata, controllata, notifica e pagina', c_nuova_versione)
prova('stessa versione o più vecchia: niente da fare, "il programma è aggiornato"', c_stessa_o_vecchia)
prova('file delle versioni sbagliati o storpiati: errore chiaro, niente scaricato', c_manifesti_sbagliati)
prova('Setup rovinato, troncato, più lungo o non exe: non si tiene niente', c_setup_rovinato)
prova('Setup già scaricato: non si riscarica (anche dopo un riavvio), se rovinato sì', c_gia_scaricato)
prova('cartella irraggiungibile o senza file: errore detto nella pagina', c_cartella_irraggiungibile)
prova('un controllo alla volta; la pagina dice "controllo in corso"; l\'indirizzo nuovo si controlla dopo', c_un_controllo_alla_volta)


def c_in_corso_fra_due_controlli():
    """Il controllo delle sei ore finisce mentre quello chiesto dalla pagina
    aspetta il suo turno: in mezzo la pagina non deve vedere "finito" (si
    ricaricherebbe con il risultato vecchio e non seguirebbe quello nuovo)."""
    S, C, dove = mondo()
    sorgente = pubblica(os.path.join(dove, 'pubblicata'), nuova_versione())
    imposta(S, aggiornamenti_indirizzo=sorgente)
    vero_apri = AG.apri
    entrato, via, lascia = threading.Event(), threading.Event(), threading.Event()

    class Lucchetto:
        """Il secondo controllo resta "in attesa del suo turno" finche' la prova lo lascia passare."""

        def __init__(self):
            self.vero, self.chiamate = threading.Lock(), 0

        def acquire(self, blocking=True, timeout=-1):
            self.chiamate += 1
            if self.chiamate == 2:
                lascia.wait(5)
            return self.vero.acquire(blocking, timeout)

        def release(self):
            self.vero.release()

    def lento(base, nome):
        if not entrato.is_set():
            entrato.set()
            via.wait(5)
        return vero_apri(base, nome)
    AG.apri, AG._un_controllo = lento, Lucchetto()
    try:
        primo = threading.Thread(target=AG.controlla, args=(fabbrica,))          # quello delle sei ore
        primo.start()
        assert entrato.wait(5)
        altra = pubblica(os.path.join(dove, 'altra'), nuova_versione(5))
        C.post('/aggiornamenti', data={'azione': 'indirizzo', 'indirizzo': altra})   # il secondo aspetta
        via.set()
        primo.join(10)
        assert not primo.is_alive(), 'il primo controllo non finisce'
        d = json.loads(html(C.get('/aggiornamenti/stato.json')))
        assert d['in_corso'] is True, 'fra un controllo e l\'altro la pagina vede "finito": %s' % d
        assert 'data-in-corso="1"' in html(C.get('/aggiornamenti'))
        lascia.set()
        for _ in range(100):
            if not AG.stato['in_corso']:
                break
            orologio.sleep(0.1)
    finally:
        lascia.set()
        via.set()
        for _ in range(100):                     # anche se la prova si rompe: niente controlli rimasti a meta'
            if AG._attivi == [0]:
                break
            orologio.sleep(0.1)
    assert not AG.stato['in_corso'] and AG.stato['disponibile']['versione'] == nuova_versione(5), AG.stato
    assert AG._attivi == [0], AG._attivi


prova('"controllo in corso" resta acceso finché un altro controllo aspetta il suo turno', c_in_corso_fra_due_controlli)


def c_pagina_coerente():
    """Il controllo finisce mentre la pagina si compone (successo davvero nel browser):
    la pagina mostra una fotografia sola dello stato, mai "uscita ma non scaricata"
    di una versione che intanto e' pronta."""
    S, C, dove = mondo()
    sorgente = pubblica(os.path.join(dove, 'pubblicata'), nuova_versione())
    imposta(S, aggiornamenti_indirizzo=sorgente)
    m = AG.leggi_manifesto(sorgente)
    AG.stato.update(in_corso=True, disponibile=m, pronto=None)          # a meta' controllo
    vero = AG.render_template

    def e_intanto_finisce(*a, **k):                    # il controllo finisce proprio mentre la pagina si compone
        AG.stato.update(in_corso=False, pronto=AG.scarica(sorgente, m))
        return vero(*a, **k)
    AG.render_template = e_intanto_finisce
    try:
        t = html(C.get('/aggiornamenti'))
    finally:
        AG.render_template = vero
    assert 'Non è ancora stata scaricata' not in t, 'stato mescolato: versione "non scaricata" mentre era pronta'
    assert 'data-in-corso="1"' in t and 'Controllo in corso' in t, 'la pagina deve seguire il controllo e ricaricarsi'
    assert 'È pronta la versione %s' % nuova_versione() in html(C.get('/aggiornamenti'))


prova('la pagina legge lo stato una volta sola (controllo che finisce mentre si compone)', c_pagina_coerente)


# ============================================== controllo via https (finto)
area('controllo via https (finto GitHub)')


def certificato():
    cert, chiave = os.path.join(PROVVISORIA, 'cert.pem'), os.path.join(PROVVISORIA, 'chiave.pem')
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '2', '-subj', '/CN=127.0.0.1',
                    '-addext', 'subjectAltName=IP:127.0.0.1,DNS:localhost', '-keyout', chiave, '-out', cert],
                   check=True, capture_output=True)
    return cert, chiave


CERT, CHIAVE = certificato()


class Gestore(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.server.richieste.append((self.path, dict(self.headers)))
        risposta = self.server.percorsi.get(self.path.split('?')[0])
        if risposta is None:
            self.send_response(404)
            self.end_headers()
            return
        stato, intestazioni, corpo = risposta
        self.send_response(stato)
        for k, v in intestazioni.items():
            self.send_header(k, v)
        self.send_header('Content-Length', str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)


class SitoFinto(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(('127.0.0.1', 0), Gestore)
        contesto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        contesto.load_cert_chain(CERT, CHIAVE)
        self.socket = contesto.wrap_socket(self.socket, server_side=True)
        self.percorsi, self.richieste = {}, []
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def radice(self):
        return 'https://127.0.0.1:%d' % self.server_address[1]

    def come_github(self, numero, dati, **cambi):
        """/u/r/releases/latest/download/<file> rimanda (302) a /cdn/<file>, come GitHub."""
        self.percorsi.clear()
        self.richieste.clear()
        m = json.dumps(manifesto(numero, dati, **cambi)).encode()
        for nome, corpo, tipo in ((AG.MANIFESTO, m, 'application/json'), (AG.NOME_SETUP, dati, 'application/octet-stream')):
            self.percorsi['/u/r/releases/latest/download/' + nome] = (302, {'Location': self.radice + '/cdn/' + nome}, b'')
            self.percorsi['/cdn/' + nome] = (200, {'Content-Type': tipo}, corpo)
        return self.radice + '/u/r/releases/latest/download/'


SITO = SitoFinto()
FIDATO = ssl.create_default_context(cafile=CERT)


def h_come_github():
    S, C, dove = mondo()
    AG.contesto_tls = lambda: FIDATO
    dati = setup_finto(seme=3)
    base = SITO.come_github(nuova_versione(), dati)
    assert AG.normalizza(base) == (base, None)
    imposta(S, aggiornamenti_indirizzo=base)
    AG.controlla(fabbrica)
    assert AG.stato['errore'] is None and AG.stato['pronto'], AG.stato
    assert open(AG.stato['pronto'], 'rb').read() == dati
    percorsi = [p for p, _ in SITO.richieste]
    assert percorsi == ['/u/r/releases/latest/download/' + AG.MANIFESTO, '/cdn/' + AG.MANIFESTO,
                        '/u/r/releases/latest/download/' + AG.NOME_SETUP, '/cdn/' + AG.NOME_SETUP], percorsi
    agente = SITO.richieste[0][1].get('User-Agent', '')
    assert agente.startswith('GestionaleAgende/%s' % comune.VERSIONE), agente
    return 'seguiti i rimandi come su GitHub'


def h_rimando_http():
    S, C, dove = mondo()
    AG.contesto_tls = lambda: FIDATO
    base = SITO.come_github(nuova_versione(), setup_finto())
    SITO.percorsi['/u/r/releases/latest/download/' + AG.MANIFESTO] = (302, {'Location': 'http://127.0.0.1:9/x.json'}, b'')
    imposta(S, aggiornamenti_indirizzo=base)
    AG.controlla(fabbrica)
    assert 'non sicuro' in (AG.stato['errore'] or ''), AG.stato
    # anche per il Setup
    base = SITO.come_github(nuova_versione(), setup_finto())
    SITO.percorsi['/u/r/releases/latest/download/' + AG.NOME_SETUP] = (302, {'Location': 'http://127.0.0.1:9/s.exe'}, b'')
    AG.controlla(fabbrica)
    assert 'non sicuro' in (AG.stato['errore'] or '') and not AG.stato['pronto'], AG.stato


def h_errori_del_sito():
    S, C, dove = mondo()
    AG.contesto_tls = lambda: FIDATO
    base = SITO.come_github(nuova_versione(), setup_finto())
    imposta(S, aggiornamenti_indirizzo=base)
    del SITO.percorsi['/cdn/' + AG.MANIFESTO]
    AG.controlla(fabbrica)
    assert "non c'è il file %s" % AG.MANIFESTO in AG.stato['errore'], AG.stato['errore']
    assert 'non è stata ancora pubblicata nessuna versione' in AG.stato['errore'], 'GitHub senza versioni: va detto'
    # file delle versioni c'e', il Setup no: pubblicata senza il Setup
    base = SITO.come_github(nuova_versione(), setup_finto())
    del SITO.percorsi['/cdn/' + AG.NOME_SETUP]
    AG.controlla(fabbrica)
    assert AG.stato['errore'] == ("all'indirizzo degli aggiornamenti non c'è il file %s: la versione è stata pubblicata "
                                  "senza quel file" % AG.NOME_SETUP), AG.stato['errore']
    assert AG.stato['pronto'] is None and not os.listdir(os.path.join(dove, 'aggiornamenti'))
    SITO.percorsi['/cdn/' + AG.MANIFESTO] = (500, {}, b'errore')
    AG.controlla(fabbrica)
    assert "errore 500" in AG.stato['errore'], AG.stato['errore']


def h_certificato_non_valido():
    S, C, dove = mondo()
    base = SITO.come_github(nuova_versione(), setup_finto())
    imposta(S, aggiornamenti_indirizzo=base)
    AG.controlla(fabbrica)                         # con i certificati veri: quello finto non vale
    assert 'certificato' in (AG.stato['errore'] or ''), AG.stato['errore']


def h_senza_risposta():
    S, C, dove = mondo()
    muto = socket.socket()
    muto.bind(('127.0.0.1', 0))
    muto.listen(5)
    AG.ATTESA_RETE = 1
    imposta(S, aggiornamenti_indirizzo='https://127.0.0.1:%d/agg/' % muto.getsockname()[1])
    inizio = orologio.monotonic()
    AG.controlla(fabbrica)
    durata = orologio.monotonic() - inizio
    muto.close()
    assert 'non risponde' in (AG.stato['errore'] or '') and durata < 10, (AG.stato['errore'], durata)
    chiuso = socket.socket()
    chiuso.bind(('127.0.0.1', 0))
    porta = chiuso.getsockname()[1]
    chiuso.close()
    imposta(S, aggiornamenti_indirizzo='https://127.0.0.1:%d/agg/' % porta)
    AG.controlla(fabbrica)
    assert 'internet non raggiungibile' in (AG.stato['errore'] or ''), AG.stato['errore']


prova('come su GitHub: il file rimanda a un altro indirizzo, si segue; User-Agent del programma', h_come_github)
prova('rimando a un indirizzo http: rifiutato (file delle versioni e Setup)', h_rimando_http)
prova('file mancante (404) o errore del sito (500): detto in chiaro', h_errori_del_sito)
prova('certificato non valido: non si scarica niente', h_certificato_non_valido)
prova('sito che non risponde o porta chiusa: errore entro il tempo, niente blocchi', h_senza_risposta)


# ======================================================== Aggiorna adesso
area('Aggiorna adesso')


def a_aggiorna_adesso():
    S, C, dove = mondo(con_dati=True)
    pronto(S, dove)
    lanciati = []
    AG.lancia = lambda percorso, registro: lanciati.append((percorso, registro))
    AG.installato = lambda: True
    AG.ATTESA_PRIMA_DEL_SETUP = 0
    r = C.post('/aggiornamenti/aggiorna')
    t = html(r)
    assert r.status_code == 200 and 'id="attesa-aggiornamento"' in t, (r.status_code, t[:300])
    assert 'data-avviato="%s"' % AG.AVVIATO_IL in t and 'data-a="%s"' % nuova_versione() in t
    copie = backup.elenco(os.path.join(dove, 'backup'))
    assert len(copie) == 1 and copie[0]['motivo'] == AG.MOTIVO_COPIA, copie
    backup._verifica(copie[0]['percorso'])
    segno = AG.leggi_segno()
    assert segno['da'] == comune.VERSIONE and segno['a'] == nuova_versione() and segno['copia'] == copie[0]['percorso'], segno
    for _ in range(50):
        if lanciati:
            break
        orologio.sleep(0.1)
    assert lanciati == [(AG.stato['pronto'], os.path.join(dove, 'aggiornamenti', 'setup-%s.log' % nuova_versione()))], lanciati
    assert AG.stato['partito'] is not None
    d = json.loads(html(C.get('/aggiornamenti/stato.json')))
    assert d['partito'] is True and d['avviato'] == AG.AVVIATO_IL and d['versione'] == comune.VERSIONE, d
    # nella pagina dei backup la copia si riconosce
    assert 'prima di aggiornare' in testo(C.get('/impostazioni'))
    return 'copia di sicurezza, segno, Setup avviato'


def a_comando_setup():
    catturati = []

    class Finto:
        def __init__(self, comando, **opzioni):
            catturati.append((comando, opzioni))
    vero = subprocess.Popen
    subprocess.Popen = Finto
    # le variabili che l'eseguibile a file unico mette nel suo ambiente: il Setup non deve passarle al gestionale riaperto
    interne = {'_PYI_APPLICATION_HOME_DIR': 'C:\\Temp\\_MEI123', '_PYI_PARENT_PROCESS_LEVEL': '1', '_PYI_ARCHIVE_FILE': 'x.exe',
               '_MEIPASS2': 'C:\\Temp\\_MEI123', '_pyi_minuscolo': 'x'}
    os.environ.update(interne)
    try:
        AG.lancia(r'C:\Users\Federica Corso\AppData\Local\GestionaleAgende\aggiornamenti\GestionaleAgende-setup-1.6.1.exe',
                  r'C:\Users\Federica Corso\AppData\Local\GestionaleAgende\aggiornamenti\setup-1.6.1.log')
    finally:
        subprocess.Popen = vero
        for k in interne:
            os.environ.pop(k, None)
    comando, opzioni = catturati[0]
    assert isinstance(comando, str), 'il comando va passato intero, con le virgolette'
    atteso = ('"%s" /c start "" "C:\\Users\\Federica Corso\\AppData\\Local\\GestionaleAgende\\aggiornamenti\\'
              'GestionaleAgende-setup-1.6.1.exe" /SILENT /NOCANCEL /SUPPRESSMSGBOXES /NORESTART /LOG="C:\\Users\\'
              'Federica Corso\\AppData\\Local\\GestionaleAgende\\aggiornamenti\\setup-1.6.1.log"') % AG.cmd()
    assert comando == atteso, comando
    assert 'System32' in AG.cmd() and AG.cmd().lower().endswith('cmd.exe'), AG.cmd()
    assert opzioni['creationflags'] == getattr(subprocess, 'CREATE_NO_WINDOW', 0) and opzioni['stdin'] == subprocess.DEVNULL
    ambiente = opzioni['env']
    assert not [k for k in ambiente if k.upper().startswith(('_PYI_', '_MEI'))], 'variabili interne passate al Setup'
    assert ambiente == dict(os.environ), 'il resto dell\'ambiente deve restare uguale'
    return comando[:60] + '…'


def a_rifiuti():
    S, C, dove = mondo()
    lanciati = []
    AG.lancia = lambda percorso, registro: lanciati.append(percorso)
    AG.ATTESA_PRIMA_DEL_SETUP = 0
    AG.installato = lambda: True
    r = C.post('/aggiornamenti/aggiorna')
    assert r.status_code == 302 and 'Non c\'è un aggiornamento pronto' in avvisi(C)
    pronto(S, dove)
    C.get('/aggiornamenti')
    AG.installato = lambda: False
    C.post('/aggiornamenti/aggiorna')
    assert 'non è quella installata' in avvisi(C)
    AG.installato = lambda: True
    with open(AG.stato['pronto'], 'r+b') as f:
        f.seek(500)
        f.write(b'XX')
    C.get('/aggiornamenti')
    C.post('/aggiornamenti/aggiorna')
    assert 'non è più integro' in avvisi(C) and AG.stato['pronto'] is None
    # copia di sicurezza non riuscita: l'aggiornamento non parte
    azzera()
    AG.controlla(fabbrica)
    vero = backup.esegui
    backup.esegui = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('disco pieno'))
    try:
        C.get('/aggiornamenti')
        C.post('/aggiornamenti/aggiorna')
        assert 'copia di sicurezza non è riuscita (disco pieno)' in avvisi(C)
    finally:
        backup.esegui = vero
    orologio.sleep(0.3)
    assert lanciati == [] and AG.leggi_segno() is None and AG.stato['partito'] is None, (lanciati, AG.leggi_segno())


def a_aspetta_invii():
    S, C, dove = mondo(con_dati=True)
    s = S()
    a = s.scalars(select(Appuntamento)).first()
    x = Invio(canale='EMAIL', motivo='PROMEMORIA', destinatario='fintini@example.com', appuntamento_id=a.id,
              stato='IN_CORSO', creato_il=datetime.now(), prossimo=datetime.now())
    s.add(x)
    s.commit()
    xid = x.id
    s.close()

    def finisce():
        orologio.sleep(1.2)
        s2 = S()
        s2.get(Invio, xid).stato = 'INVIATO'
        s2.commit()
        s2.close()
    threading.Thread(target=finisce).start()
    inizio = orologio.monotonic()
    AG.aspetta_invii(massimo=8, fabbrica=fabbrica)
    durata = orologio.monotonic() - inizio
    assert 1.0 < durata < 4, durata
    s = S()
    s.get(Invio, xid).stato = 'IN_CORSO'
    s.commit()
    s.close()
    inizio = orologio.monotonic()
    AG.aspetta_invii(massimo=1, fabbrica=fabbrica)
    assert orologio.monotonic() - inizio < 3, 'non si aspetta all\'infinito'
    return 'aspettata l\'email in partenza (%.1f s)' % durata


def a_setup_non_parte():
    S, C, dove = mondo()
    pronto(S, dove)
    AG.installato = lambda: True
    AG.ATTESA_PRIMA_DEL_SETUP = 0

    def guasto(percorso, registro):
        raise OSError('accesso negato')
    AG.lancia = guasto
    C.post('/aggiornamenti/aggiorna')
    for _ in range(50):
        if AG.stato['errore']:
            break
        orologio.sleep(0.1)
    d = json.loads(html(C.get('/aggiornamenti/stato.json')))
    assert d['partito'] is False and 'non è partito' in d['errore'] and 'accesso negato' in d['errore'], d
    assert AG.leggi_segno() is None, 'segno rimasto: al prossimo avvio direbbe "non riuscito"'


prova('Aggiorna adesso: copia di sicurezza, segno, pagina d\'attesa, Setup avviato', a_aggiorna_adesso)
prova('il comando che avvia il Setup: cmd /c start, silenzioso, registro, percorsi con spazi, ambiente pulito', a_comando_setup)
prova('rifiuti: niente pronto, copia non installata, Setup rovinato, copia di sicurezza fallita', a_rifiuti)
prova('un\'email che sta partendo si lascia finire, ma non si aspetta all\'infinito', a_aspetta_invii)
prova('il Setup non parte: lo dice la pagina d\'attesa, nessun segno rimasto', a_setup_non_parte)


# ================================================ dopo l'avvio e novita'
area('dopo l\'avvio e novità')


def notifiche_di(C):
    return json.loads(html(C.get('/notifiche.json')))


def d_prima_volta_con_dati():
    S, C, dove = mondo(con_dati=True)
    s = S()
    note = AG.dopo_avvio(s)
    s.close()
    assert leggi(S, 'versione_avviata') == comune.VERSIONE and leggi(S, 'novita_dal') == OGGI.isoformat(), note
    n = [x for x in notifiche_di(C) if x['chiave'] == 'novita-%s' % comune.VERSIONE]
    k = len(novita.NOVITA[0][1])
    assert n and n[0]['link'] == '/aiuto/novita' and '%d %s' % (k, 'cosa nuova' if k == 1 else 'cose nuove') in n[0]['testo'], \
        notifiche_di(C)
    t = testo(C.get('/aiuto/novita'))
    assert 'Novità della versione %s' % comune.VERSIONE in t, t[:300]
    for x in novita.NOVITA[0][1]:
        assert x['titolo'] in t, x['titolo']
    assert leggi(S, 'novita_vista') == comune.VERSIONE
    assert not [x for x in notifiche_di(C) if x['chiave'].startswith('novita')], 'aperta la pagina, la notifica resta'


def d_installazione_nuova():
    S, C, dove = mondo()
    s = S()
    AG.dopo_avvio(s)
    s.close()
    assert leggi(S, 'versione_avviata') == comune.VERSIONE and leggi(S, 'novita_dal', 'x') == ''
    assert not [x for x in notifiche_di(C) if x['chiave'].startswith('novita')]


def d_quattordici_giorni():
    S, C, dove = mondo()
    imposta(S, versione_avviata='1.5')
    s = S()
    AG.dopo_avvio(s, adesso=datetime(2026, 10, 5, 9, 0))
    assert leggi_impostazione(s, 'versione_precedente') == '1.5' and leggi_impostazione(s, 'novita_dal') == '2026-10-05'
    for giorni, atteso in ((0, True), (13, True), (14, False), (-1, False)):
        voci = AG.novita_da_annunciare(s, datetime(2026, 10, 5, 9, 0) + timedelta(days=giorni))
        assert bool(voci) == atteso, (giorni, voci)
    # al secondo avvio della stessa versione non si riparte da capo
    AG.dopo_avvio(s, adesso=datetime(2026, 10, 9, 9, 0))
    assert leggi_impostazione(s, 'novita_dal') == '2026-10-05' and leggi_impostazione(s, 'versione_precedente') == '1.5'
    s.close()
    # la pagina mostra le novita' dalla 1.5 esclusa in poi, le altre fra le precedenti
    t = testo(C.get('/aiuto/novita'))
    assert 'Versioni precedenti' in t and 'Versione 1.5: %d novità' % len(dict(novita.NOVITA)['1.5']) in t, t


def d_ritorno_indietro():
    S, C, dove = mondo(con_dati=True)
    imposta(S, versione_avviata='9.0')
    s = S()
    AG.dopo_avvio(s)
    s.close()
    assert leggi(S, 'novita_dal', 'x') == '' and leggi(S, 'versione_precedente') == '9.0'
    assert not [x for x in notifiche_di(C) if x['chiave'].startswith('novita')]


def d_segni():
    S, C, dove = mondo()
    s = S()
    AG.dopo_avvio(s)
    # riuscito
    AG.scrivi_segno({'da': '1.5', 'a': comune.VERSIONE, 'quando': '2026-10-04T10:00:00', 'log': 'x.log'})
    note = AG.dopo_avvio(s)
    assert AG.leggi_segno() is None and any('riuscito' in n for n in note) and not AG.leggi_fallito(s), note
    # non riuscito: la versione e' rimasta quella di prima
    AG.scrivi_segno({'da': comune.VERSIONE, 'a': nuova_versione(), 'quando': '2026-10-04T11:00:00', 'log': 'C:\\x\\setup.log'})
    note = AG.dopo_avvio(s)
    s.close()
    assert AG.leggi_segno() is None and any('NON riuscito' in n for n in note), note
    n = [x for x in notifiche_di(C) if x['titolo'] == 'Aggiornamento non riuscito']
    assert n and n[0]['livello'] == 'errore', notifiche_di(C)
    t = testo(C.get('/aggiornamenti'))
    assert 'non è riuscito' in t and 'setup.log' in t, t
    assert 'non è riuscito' not in testo(C.get('/aggiornamenti')), 'detto una volta basta'
    assert not [x for x in notifiche_di(C) if x['titolo'] == 'Aggiornamento non riuscito']
    # segno rovinato: si toglie e basta
    os.makedirs(AG.cartella(), exist_ok=True)
    open(AG.percorso_segno(), 'w').write('{rotto')
    s = S()
    AG.dopo_avvio(s)
    s.close()
    assert AG.leggi_segno() is None


def d_pulizia():
    S, C, dove = mondo()
    c = os.path.join(dove, 'aggiornamenti')
    os.makedirs(c)
    pre = 'GestionaleAgende%s-setup-' % ('-animata' if AG.VARIANTE == 'animata' else '')
    nuova = nuova_versione()
    nomi = [pre + '1.5.exe', pre + comune.VERSIONE + '.exe', pre + nuova + '.exe', pre + nuova + '.exe.parziale',
            'setup-1.5.log', 'altro.txt']
    for n in nomi:
        open(os.path.join(c, n), 'w').write('x')
    s = S()
    AG.dopo_avvio(s)
    s.close()
    assert sorted(os.listdir(c)) == sorted([pre + nuova + '.exe', 'setup-1.5.log', 'altro.txt']), os.listdir(c)


prova('primo avvio della 1.6 con dati già presenti: notifica delle novità finché non si aprono', d_prima_volta_con_dati)
prova('installazione nuova: nessuna notifica delle novità', d_installazione_nuova)
prova('novità per 14 giorni dall\'aggiornamento; il secondo avvio non ricomincia', d_quattordici_giorni)
prova('tornando a una versione più vecchia niente novità', d_ritorno_indietro)
prova('esito di Aggiorna adesso al riavvio: riuscito, non riuscito (detto una volta), segno rovinato', d_segni)
prova('all\'avvio via i Setup già installati e quelli a metà', d_pulizia)


# ===================================================== pagine e sicurezza
area('pagine, menu e sicurezza')


def p_pagine_e_menu():
    S, C, dove = mondo()
    t = html(C.get('/aggiornamenti'))
    menu = t.split('<nav class="menu"')[1].split('</nav>')[0]
    assert 'Aggiornamenti' in menu and 'Novità' in menu, 'voci del menu'
    assert re.search(r'class="gruppo[^"]*attivo"[^>]*data-guida="menu-configura"', t), 'Configura non evidenziato'
    assert re.search(r'class="gruppo[^"]*attivo"[^>]*data-guida="menu-aiuto"', html(C.get('/aiuto/novita')))
    t = html(C.get('/aiuto'))
    assert 'href="/aiuto/novita"' in t and 'href="/aggiornamenti"' in t, 'collegamenti in Aiuto'
    assert C.get('/aiuto/novita').status_code == 200
    # pagina della guida all'aggiornamento: punta alla pagina giusta
    t = html(C.get('/aiuto/aggiornare'))
    assert 'href="/aggiornamenti?guida=aggiornare"' in t, 'Mostrami sullo schermo'


def p_stato_json():
    S, C, dove = mondo()
    r = C.get('/aggiornamenti/stato.json')
    d = json.loads(html(r))
    assert set(d) == {'versione', 'avviato', 'in_corso', 'scaricati', 'totale', 'disponibile', 'pronto', 'partito', 'errore'}
    assert r.headers['Cache-Control'] == 'no-store' and r.headers['X-Content-Type-Options'] == 'nosniff'


def p_da_fuori():
    S, C, dove = mondo()
    pronto(S, dove)
    lanciati = []
    AG.lancia = lambda p, r: lanciati.append(p)
    AG.installato = lambda: True
    for intestazioni in ({'Origin': 'http://sito-cattivo.example.com'}, {'Sec-Fetch-Site': 'cross-site'},
                         {'Referer': 'http://sito-cattivo.example.com/pagina'}):
        assert C.post('/aggiornamenti/aggiorna', headers=intestazioni).status_code == 403, intestazioni
        assert C.post('/aggiornamenti', data={'azione': 'indirizzo', 'indirizzo': 'https://x.example.com/'},
                      headers=intestazioni).status_code == 403
    assert lanciati == [] and not backup.elenco(os.path.join(dove, 'backup'))
    assert leggi(S, AG.CHIAVE) != 'https://x.example.com/'


prova('pagine e menu: Configura → Aggiornamenti, Aiuto → Novità, collegamenti', p_pagine_e_menu)
prova('stato.json: campi, niente cache', p_stato_json)
prova('una pagina di un altro sito non può far partire l\'aggiornamento né cambiare l\'indirizzo', p_da_fuori)


# ============================================================= videoguide
area('videoguide')


def v_ogni_articolo():
    S, C, dove = mondo()
    with open(os.path.join(CARTELLA, 'static', 'video', 'durate.json'), encoding='utf-8') as f:
        durate = json.load(f)
    totale = 0
    for a in guida.ARTICOLI:
        p = os.path.join(CARTELLA, 'static', 'video', a['slug'] + '.webm')
        assert os.path.exists(p), 'video mancante: ' + a['slug']
        dati = open(p, 'rb').read()
        assert dati[:4] == b'\x1a\x45\xdf\xa3' and len(dati) > 50000, a['slug']
        totale += len(dati)
        secondi = durate.get(a['slug'])
        assert secondi and 20 <= secondi <= 300, (a['slug'], secondi)
        t = html(C.get('/aiuto/' + a['slug']))
        m = re.search(r'<a class="bottone primario guarda-video" href="([^"]+)" data-video="([^"]*)"', t)
        assert m and m.group(1) == '/static/video/%s.webm' % a['slug'], a['slug']
        pulsante = re.search(r'data-guida="guarda-video">(.*?)</a>', t, re.S)
        assert pulsante and 'Guarda il video <small>%d:%02d</small>' % divmod(int(round(secondi)), 60) in pulsante.group(1), \
            (a['slug'], secondi, pulsante.group(1) if pulsante else None)
    assert set(durate) == {a['slug'] for a in guida.ARTICOLI}, 'durate di video che non esistono più'
    t = html(C.get('/aiuto'))
    assert t.count('class="con-video"') == len(guida.ARTICOLI), 'segno "video" nell\'indice'
    # anche la guida stampata dice dove sono i video, e quanto durano
    t = testo(C.get('/aiuto/stampa'))
    for a in guida.ARTICOLI:
        assert 'Video di %d:%02d nel programma: Aiuto → Come fare… → %s → Guarda il video.' % (
            divmod(int(round(durate[a['slug']])), 60) + (a['titolo'],)) in t, ('stampa', a['slug'])
    return '%d video, %.1f MB' % (len(guida.ARTICOLI), totale / 1048576)


def v_servizio():
    S, C, dove = mondo()
    r = C.get('/static/video/prenotare.webm')
    assert r.status_code == 200 and r.mimetype == 'video/webm', (r.status_code, r.mimetype)
    intero = r.get_data()
    r.close()
    r = C.get('/static/video/prenotare.webm', headers={'Range': 'bytes=100-199'})
    assert r.status_code == 206 and r.get_data() == intero[100:200] and r.headers['Content-Range'].startswith('bytes 100-199/'), \
        (r.status_code, r.headers.get('Content-Range'))
    r.close()
    for nome, tipo in (('x.webm', 'video/webm'), ('x.js', 'text/javascript'), ('x.css', 'text/css'), ('x.woff2', 'font/woff2')):
        assert mimetypes.guess_type(nome)[0] == tipo, (nome, mimetypes.guess_type(nome))
    assert guida.video('non-esiste') is None and guida.video('../app') is None and guida.video('') is None


def v_formato():
    if not shutil.which('ffprobe'):
        return 'ffprobe non installato: prova saltata'
    with open(os.path.join(CARTELLA, 'static', 'video', 'durate.json'), encoding='utf-8') as f:
        durate = json.load(f)
    for a in guida.ARTICOLI:
        p = os.path.join(CARTELLA, 'static', 'video', a['slug'] + '.webm')
        assert os.path.exists(p), 'video mancante: ' + a['slug']
        r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                            'stream=codec_name,width,height:format=duration', '-of', 'json', p], capture_output=True, text=True)
        d = json.loads(r.stdout)
        v = d['streams'][0]
        assert (v['codec_name'], v['width'], v['height']) == ('vp9', 1366, 768), (a['slug'], v)
        assert abs(float(d['format']['duration']) - durate[a['slug']]) < 0.6, (a['slug'], d['format'], durate[a['slug']])
        assert len(d['streams']) == 1, 'audio nel video'
    return 'VP9 1366×768, durate giuste'


def v_novita_con_video():
    S, C, dove = mondo()
    t = html(C.get('/aiuto/novita'))
    for x in novita.NOVITA[0][1]:
        if x['guida']:
            assert 'href="/static/video/%s.webm" data-video="%s"' % (x['guida'], x['titolo']) in t, x
            assert 'href="/aiuto/%s"' % x['guida'] in t


prova('ogni guida ha il suo video, con la durata, nell\'articolo e nell\'indice', v_ogni_articolo)
prova('i video si servono come video/webm e si possono scorrere (Range)', v_servizio)
prova('formato dei video: VP9, 1366×768, senza audio, durata come in durate.json', v_formato)
prova('pagina delle novità: ogni novità con la sua guida ha il video', v_novita_con_video)


# ===================================================== installatore e strumenti
area('installatore e strumenti')


def s_installer():
    raw = open(os.path.join(CARTELLA, 'installer.iss'), 'rb').read()
    assert raw.startswith(b'\xef\xbb\xbf') and b'\r\n' in raw and b'\n' not in raw.replace(b'\r\n', b''), 'BOM e CRLF'
    t = raw[3:].decode('utf-8').replace('\r\n', '\n')
    assert '#define Versione "%s"' % comune.VERSIONE in t
    run = t.split('[Run]')[1].split('\n[')[0]
    righe = [r for r in run.split('\n') if r.startswith('Filename:')]
    assert len(righe) == 2, righe
    assert 'postinstall' in righe[0] and 'skipifsilent' in righe[0], righe[0]
    assert 'Parameters: "--avvio-automatico"' in righe[1] and 'Flags: nowait' in righe[1] and 'Check: WizardSilent' in righe[1], righe[1]
    codice = t.split('[Code]', 1)[1].split('\n')
    assert not [r for r in codice if r.lstrip().startswith('#')]
    m = re.search(r'OutputBaseFilename=(\S+)', t)
    assert m and m.group(1) + '.exe' == AG.NOME_SETUP, (m.group(1) if m else None, AG.NOME_SETUP)
    assert ('animata' in t.split('AppVersion=')[1].split('\n')[0]) == (AG.VARIANTE == 'animata')


def s_crea_setup():
    raw = open(os.path.join(CARTELLA, 'CREA_SETUP.bat'), 'rb').read()
    assert b'\r\n' in raw and b'\n' not in raw.replace(b'\r\n', b''), 'CRLF'
    t = raw.decode('utf-8')
    dopo = t.split('installer.iss', 1)[1]
    assert 'strumenti\\prepara_aggiornamento.py' in dopo and AG.MANIFESTO in dopo and AG.NOME_SETUP in t, 'CREA_SETUP.bat'


def s_prepara_aggiornamento():
    uscita = os.path.join(PROVVISORIA, 'Output')
    os.makedirs(uscita)
    script = os.path.join(CARTELLA, 'strumenti', 'prepara_aggiornamento.py')
    r = subprocess.run([sys.executable, script, uscita], capture_output=True, text=True)
    assert r.returncode == 1 and 'Manca' in r.stdout, r.stdout
    open(os.path.join(uscita, AG.NOME_SETUP), 'wb').write(b'PK' + b'x' * 2000000)
    r = subprocess.run([sys.executable, script, uscita], capture_output=True, text=True)
    assert r.returncode == 1 and 'non è un programma' in r.stdout, r.stdout
    dati = setup_finto(2100000, 9)
    open(os.path.join(uscita, AG.NOME_SETUP), 'wb').write(dati)
    r = subprocess.run([sys.executable, script, uscita], capture_output=True, text=True)
    assert r.returncode == 0 and 'Pronto' in r.stdout, (r.stdout, r.stderr)
    grezzo = open(os.path.join(uscita, AG.MANIFESTO), 'rb').read()
    m = AG.valida(grezzo)
    assert m['versione'] == comune.VERSIONE and m['byte'] == len(dati) and m['sha256'] == hashlib.sha256(dati).hexdigest()
    assert m['file'] == AG.NOME_SETUP and m['novita'] == novita.per_manifesto() and m['pubblicata'] == OGGI.isoformat()
    # e il programma, leggendolo da quella cartella, non si aggiorna a se stesso
    S, C, dove = mondo()
    imposta(S, aggiornamenti_indirizzo=uscita)
    AG.controlla(fabbrica)
    assert AG.stato['errore'] is None and AG.stato['disponibile'] is None, AG.stato
    return 'file delle versioni accettato dal programma'


def s_video_indirizzi():
    assert guida.con_guida('/invii#regole', 'x') == '/invii?guida=x#regole'
    assert guida.con_guida('/mese/2026-10?struttura=1', 'mese') == '/mese/2026-10?struttura=1&guida=mese'
    assert guida.con_guida('/aiuto', 'aggiornare') == '/aiuto?guida=aggiornare'
    assert 'guida.con_guida(' in open(os.path.join(CARTELLA, 'strumenti', 'genera_video_guida.py'), encoding='utf-8').read()


def s_variante():
    animata = os.path.exists(os.path.join(CARTELLA, 'static', 'animazioni.css'))
    assert AG.VARIANTE == ('animata' if animata else 'normale')
    assert AG.MANIFESTO == ('aggiornamento-animata.json' if animata else 'aggiornamento.json')
    assert AG.NOME_SETUP == ('GestionaleAgende-animata-setup.exe' if animata else 'GestionaleAgende-setup.exe')


prova('installer.iss: versione, riavvio dopo il Setup silenzioso, BOM e CRLF, nome del Setup', s_installer)
prova('CREA_SETUP.bat scrive anche il file delle versioni', s_crea_setup)
prova('prepara_aggiornamento.py: file delle versioni giusto, accettato dal programma', s_prepara_aggiornamento)
prova('videoguide: la guida sullo schermo si apre anche su pagine con #ancora', s_video_indirizzi)
prova('versione normale e animata: ognuna il suo file delle versioni e il suo Setup', s_variante)


# ================================================================= thread
area('thread')


def t_thread():
    S, C, dove = mondo()
    sorgente = pubblica(os.path.join(dove, 'pubblicata'), nuova_versione())
    imposta(S, aggiornamenti_indirizzo=sorgente)
    # il Setup appena installato, rimasto perche' all'avvio era ancora aperto: lo toglie il thread
    os.makedirs(os.path.join(dove, 'aggiornamenti'))
    vecchio = os.path.join(dove, 'aggiornamenti', 'GestionaleAgende%s-setup-%s.exe' % (
        '-animata' if AG.VARIANTE == 'animata' else '', comune.VERSIONE))
    open(vecchio, 'wb').write(b'MZ')
    filo = AG.avvia(fabbrica, attesa_iniziale=0.2, intervallo=3600)
    assert filo.is_alive() and AG.avvia(fabbrica) is filo, 'un thread solo'
    for _ in range(100):
        if AG.stato['pronto']:
            break
        orologio.sleep(0.1)
    assert AG.stato['pronto'] and AG.stato['errore'] is None, AG.stato
    assert not os.path.exists(vecchio), 'Setup già installato rimasto nella cartella'
    return 'controllo partito da solo, Setup già installato tolto'


prova('il thread controlla da solo dopo l\'attesa iniziale e toglie i Setup già installati', t_thread)


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
