# -*- coding: utf-8 -*-
"""Prove su logo, colori, societa' e strutture multiple.

La parte piu' delicata e' l'aggiornamento: sul PC della segreteria c'e' gia'
un database della versione 1.1, senza le colonne del logo. Le prove partono
dallo schema esatto di quella versione e verificano che l'aggiornamento
aggiunga le colonne senza toccare i dati.
"""
import io
import os
import random
import re
import sqlite3
import struct
import threading
import traceback
import zlib
from html import unescape
from datetime import datetime, date, time, timedelta

from PIL import Image
from sqlalchemy import select, func, create_engine

import servizi
import marchio
import modelli
import app as A
from modelli import (Base, crea_sessione, Struttura, Risorsa, Operatore, Turno,
                     Appuntamento, Prestazione, COLORE_PREDEFINITO)

A.app.config['TESTING'] = True
CARTELLA = os.path.dirname(os.path.abspath(__file__))
_file = []
esiti = []
_area = ['']
OGGI = date.today()
MARTEDI = OGGI + timedelta(days=((1 - OGGI.weekday()) % 7) or 7)

# schema della tabella strutture nella versione 1.1, preso dal database che creava
SCHEMA_V11 = """CREATE TABLE strutture (
    id INTEGER NOT NULL,
    nome VARCHAR(80) NOT NULL,
    attiva BOOLEAN NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (nome)
)"""


def area(nome):
    _area[0] = nome


def prova(nome, f):
    try:
        esiti.append(('OK', _area[0], nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', _area[0], nome, str(e) or 'asserzione fallita'))
    except Exception:
        esiti.append(('ERRORE', _area[0], nome, traceback.format_exc().strip().splitlines()[-1]))


def percorso_nuovo():
    p = os.path.join(CARTELLA, 'prove_pers_%d.db' % len(_file))
    if os.path.exists(p):
        os.remove(p)
    _file.append(p)
    return p


def collega(Sessione):
    A.Sessione = Sessione
    A._registro = None
    return A.app.test_client()


def mondo():
    """Installazione nuova: primo avvio su database vuoto."""
    S = crea_sessione('sqlite:///' + percorso_nuovo())
    s = S()
    servizi.prepara_primo_avvio(s)
    s.close()
    return S, collega(S)


def database_v11(strutture=('Clinica Posillipo', 'Villa dei Fiori')):
    """Un database come lo lasciava la versione 1.1, con dati dentro."""
    p = percorso_nuovo()
    c = sqlite3.connect(p)
    c.execute(SCHEMA_V11)
    c.commit()
    c.close()
    # le altre tabelle non sono cambiate: le crea lo schema attuale, saltando strutture
    motore = create_engine('sqlite:///' + p)
    Base.metadata.create_all(motore, tables=[t for n, t in Base.metadata.tables.items() if n != 'strutture'])
    motore.dispose()
    c = sqlite3.connect(p)
    for i, nome in enumerate(strutture, start=1):
        c.execute('INSERT INTO strutture (id, nome, attiva) VALUES (?, ?, 1)', (i, nome))
        for k in range(1, 4):
            c.execute('INSERT INTO risorse (nome, tipo, struttura_id, ordine, attiva) VALUES (?, ?, ?, ?, 1)',
                      ('Ambulatorio %d' % k, 'AMBULATORIO', i, k))
    c.execute("INSERT INTO operatori (cognome, nome, specialita, colore, attivo) VALUES ('Lippiello', '', '', '#154381', 1)")
    c.execute("INSERT INTO prestazioni (nome, durata_min, campi_extra) VALUES ('Controllo', 20, '')")
    inizio = datetime.combine(MARTEDI, time(9, 0))
    c.execute("INSERT INTO appuntamenti (risorsa_id, operatore_id, prestazione_id, inizio, fine, stato, note) "
              "VALUES (1, 1, 1, ?, ?, 'CONFERMATO', 'dalla 1.1')",
              (inizio.isoformat(' '), (inizio + timedelta(minutes=20)).isoformat(' ')))
    c.commit()
    c.close()
    return p


def conta_righe(p, tabella):
    c = sqlite3.connect(p)
    n = c.execute('SELECT COUNT(*) FROM %s' % tabella).fetchone()[0]
    c.close()
    return n


def immagine(fmt='PNG', larghezza=420, altezza=140, colore=(46, 125, 50), margine=60, fondo=(255, 255, 255)):
    im = Image.new('RGB', (larghezza + 2 * margine, altezza + 2 * margine), fondo)
    im.paste(Image.new('RGB', (larghezza, altezza), colore), (margine, margine))
    b = io.BytesIO()
    im.save(b, fmt)
    return b.getvalue()


def invia_struttura(c, sid, file=None, nome_file='logo.png', **campi):
    s = A.Sessione()
    st = s.get(Struttura, sid)
    dati = {'nome': st.nome, 'societa': st.societa or '', 'colore': st.colore_sicuro}
    s.close()
    dati.update(campi)
    if file is not None:
        dati['logo'] = (io.BytesIO(file), nome_file)
    return c.post('/anagrafiche/strutture/%d' % sid, data=dati, content_type='multipart/form-data')


def leggi(S, sid):
    s = S()
    st = s.get(Struttura, sid)
    ris = dict(nome=st.nome, societa=st.societa, colore=st.colore, logo=st.logo,
               aggiornato=st.logo_aggiornato)
    s.close()
    return ris


def html(r):
    return r.get_data(as_text=True)


def e_png(dati):
    return dati is not None and dati[:8] == b'\x89PNG\r\n\x1a\n'


# =====================================================================
area('aggiornamento dalla 1.1')


def ag_colonne_aggiunte():
    p = database_v11()
    S = crea_sessione('sqlite:///' + p)
    # le quattro del logo della 1.2, e sulle strutture anche quelle della 1.3
    attese = {'strutture.societa', 'strutture.colore', 'strutture.logo', 'strutture.logo_aggiornato'}
    attese |= {'strutture.' + c for c, _ in modelli.COLONNE_AGGIUNTE['strutture'][4:]}
    assert set(S.colonne_aggiunte) == attese, 'aggiunte: %s' % S.colonne_aggiunte
    S2 = crea_sessione('sqlite:///' + p)
    assert S2.colonne_aggiunte == [], 'al secondo avvio aggiunge ancora: %s' % S2.colonne_aggiunte
    return '%d colonne al primo avvio, nessuna al secondo' % len(attese)


def ag_dati_intatti():
    p = database_v11()
    prima = {t: conta_righe(p, t) for t in ('strutture', 'risorse', 'operatori', 'appuntamenti', 'prestazioni')}
    crea_sessione('sqlite:///' + p)
    dopo = {t: conta_righe(p, t) for t in prima}
    assert prima == dopo, 'righe cambiate: %s -> %s' % (prima, dopo)
    c = sqlite3.connect(p)
    nota = c.execute('SELECT note FROM appuntamenti').fetchone()[0]
    c.close()
    assert nota == 'dalla 1.1', 'appuntamento alterato'
    return str(dopo)


def ag_logo_solo_a_posillipo():
    p = database_v11()
    S = crea_sessione('sqlite:///' + p)
    s = S()
    aggiornate = servizi.dopo_aggiornamento(s, S.colonne_aggiunte)
    s.close()
    assert aggiornate == ['Clinica Posillipo'], 'aggiornate: %s' % aggiornate
    assert e_png(leggi(S, 1)['logo']), 'Posillipo senza logo dopo l aggiornamento'
    assert leggi(S, 2)['logo'] is None, 'logo assegnato anche a Villa dei Fiori'
    assert leggi(S, 1)['colore'] == COLORE_PREDEFINITO, 'colore cambiato: %s' % leggi(S, 1)['colore']


def ag_logo_tolto_resta_tolto():
    p = database_v11(('Clinica Posillipo',))
    S = crea_sessione('sqlite:///' + p)
    s = S()
    servizi.dopo_aggiornamento(s, S.colonne_aggiunte)
    s.close()
    c = collega(S)
    r = invia_struttura(c, 1, rimuovi_logo='1')
    assert r.status_code == 302, 'rimozione HTTP %d' % r.status_code
    S2 = crea_sessione('sqlite:///' + p)          # riavvio del programma
    s = S2()
    rimesse = servizi.dopo_aggiornamento(s, S2.colonne_aggiunte)
    s.close()
    assert rimesse == [] and leggi(S2, 1)['logo'] is None, 'al riavvio il logo tolto e tornato'


def ag_pagine_dopo_aggiornamento():
    p = database_v11()
    S = crea_sessione('sqlite:///' + p)
    s = S()
    servizi.dopo_aggiornamento(s, S.colonne_aggiunte)
    s.close()
    c = collega(S)
    for u in ('/giorno/%s?struttura=1' % MARTEDI.isoformat(), '/giorno/%s?struttura=2' % MARTEDI.isoformat(),
              '/anagrafiche', '/anagrafiche/strutture/1', '/appuntamento/1', '/esporta/%s' % MARTEDI.isoformat()):
        r = c.get(u)
        assert r.status_code == 200, '%s -> HTTP %d' % (u, r.status_code)
    t = html(c.get('/giorno/%s?struttura=1' % MARTEDI.isoformat()))
    assert '<img src="/logo/1?v=' in t, 'Posillipo senza logo in griglia'
    assert 'Lippiello' in t, 'appuntamento della 1.1 sparito dalla griglia'


def ag_installazione_nuova():
    S, c = mondo()
    assert S.colonne_aggiunte == [], 'database nuovo: colonne aggiunte %s' % S.colonne_aggiunte
    st = leggi(S, 1)
    assert st['nome'] == servizi.NOME_INIZIALE, 'nome iniziale: %s' % st['nome']
    assert st['logo'] is None and st['colore'] == COLORE_PREDEFINITO, 'installazione nuova non neutra'
    t = html(c.get('/giorno/%s' % MARTEDI.isoformat()))
    assert 'class="marchio-nome">%s<' % servizi.NOME_INIZIALE in t, 'senza logo non compare il nome'
    t = html(c.get('/anagrafiche'))
    assert 'Dare il nome alla struttura e caricare il logo' in t, 'la guida non chiede nome e logo'


prova('aggiunge le 4 colonne una volta sola', ag_colonne_aggiunte)
prova('strutture, stanze, medici e appuntamenti intatti', ag_dati_intatti)
prova('il logo della clinica solo alle strutture Posillipo', ag_logo_solo_a_posillipo)
prova('un logo tolto non torna al riavvio', ag_logo_tolto_resta_tolto)
prova('dopo l aggiornamento tutte le pagine rispondono', ag_pagine_dopo_aggiornamento)
prova('installazione nuova: nome generico, niente logo', ag_installazione_nuova)


# =====================================================================
area('caricamento del logo')
S, C = mondo()


def fai_formato(fmt):
    def f():
        r = invia_struttura(C, 1, immagine(fmt), nome_file='logo.' + fmt.lower())
        assert r.status_code == 302, 'HTTP %d' % r.status_code
        st = leggi(S, 1)
        assert e_png(st['logo']), 'salvato in un formato diverso da PNG'
        im = Image.open(io.BytesIO(st['logo']))
        assert im.height <= marchio.ALTEZZA_MAX, 'alto %d' % im.height
        assert st['aggiornato'] is not None, 'data del logo non impostata'
        return '%dx%d' % im.size
    return f


def lo_rifilato():
    invia_struttura(C, 1, immagine(larghezza=300, altezza=100, margine=200))
    im = Image.open(io.BytesIO(leggi(S, 1)['logo']))
    assert im.size == (300, 100), 'margini non tolti: %s' % (im.size,)


def lo_sfondo_trasparente():
    # quadrato rosso con un foro bianco al centro, piu' una barra, su fondo bianco
    fondo = Image.new('RGB', (300, 120), (255, 255, 255))
    fondo.paste(Image.new('RGB', (80, 80), (200, 30, 40)), (20, 20))
    fondo.paste(Image.new('RGB', (30, 30), (255, 255, 255)), (45, 45))      # il foro
    fondo.paste(Image.new('RGB', (150, 30), (200, 30, 40)), (130, 45))
    b = io.BytesIO()
    fondo.save(b, 'JPEG', quality=95)
    invia_struttura(C, 1, b.getvalue(), nome_file='logo.jpg')
    im = Image.open(io.BytesIO(leggi(S, 1)['logo'])).convert('RGBA')
    # il JPG sfuma i bordi netti: la rifilatura puo' tenere 1-2 pixel in piu'
    assert abs(im.width - 260) <= 3 and abs(im.height - 80) <= 3, 'rifilatura: %s' % (im.size,)
    # rifilato, il disegno parte da circa (0,0): il foro e' tra 25 e 55,
    # l'angolo in alto a destra e' fondo collegato al bordo
    assert im.getpixel((im.width - 1, 0))[3] == 0, 'lo sfondo bianco del JPG e rimasto'
    assert im.getpixel((40, 40))[3] == 255, 'il bianco dentro il disegno e stato reso trasparente'
    trasparenti = sum(1 for p in (im.get_flattened_data() if hasattr(im, 'get_flattened_data') else im.getdata()) if p[3] == 0)
    return '%d pixel di sfondo resi trasparenti, foro interno intatto' % trasparenti


def lo_colore_segue_logo():
    invia_struttura(C, 1, colore=COLORE_PREDEFINITO, rimuovi_logo='1')
    invia_struttura(C, 1, immagine(colore=(46, 125, 50)), colore=leggi(S, 1)['colore'])
    colore = leggi(S, 1)['colore']
    r, g, b = (int(colore[i:i + 2], 16) for i in (1, 3, 5))
    assert g > r and g > b, 'il colore non segue il logo verde: %s' % colore
    return colore


def lo_colore_scelto_vince():
    invia_struttura(C, 1, immagine(colore=(46, 125, 50)), colore='#6b4e9b')
    assert leggi(S, 1)['colore'] == '#6b4e9b', 'il colore scelto e stato sostituito: %s' % leggi(S, 1)['colore']


def lo_colore_chiaro_scurito():
    r = invia_struttura(C, 1, colore='#ffff00')
    c = leggi(S, 1)['colore']
    assert marchio.contrasto(c, '#ffffff') >= 4.5, 'colore salvato illeggibile: %s' % c
    t = html(C.get(r.headers['Location']))
    assert 'troppo chiaro' in t, 'nessun avviso sul colore scurito'
    return c


def fai_rifiuto(nome, dati, frammento):
    def f():
        prima = leggi(S, 1)
        r = invia_struttura(C, 1, dati, nome_file=nome)
        assert r.status_code == 200, 'accettato (HTTP %d)' % r.status_code
        # la pagina e' HTML: l'apostrofo arriva come &#39;
        assert frammento in unescape(html(r)), 'messaggio atteso assente: %s' % frammento
        dopo = leggi(S, 1)
        assert dopo['logo'] == prima['logo'], 'il logo precedente e stato toccato'
    return f


def bomba():
    lato = 20000
    corpo = zlib.compress((b'\x00' + b'\x00' * lato) * lato, 9)

    def blocco(tipo, dati):
        return struct.pack('>I', len(dati)) + tipo + dati + struct.pack('>I', zlib.crc32(tipo + dati) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + blocco(b'IHDR', struct.pack('>IIBBBBB', lato, lato, 8, 0, 0, 0, 0))
            + blocco(b'IDAT', corpo) + blocco(b'IEND', b''))


def lo_oltre_4mb():
    # oltre il limite del server (12 MB, per i documenti allegati): rinvio con spiegazione
    r = invia_struttura(C, 1, b'\x89PNG' + b'0' * (13 * 1024 * 1024))
    assert r.status_code == 302, 'atteso il rinvio al modulo, HTTP %d' % r.status_code
    t = html(C.get(r.headers['Location']))
    assert 'troppo grande' in t, 'nessuna spiegazione per il file troppo grande'
    # 5 MB passano il server ma non il controllo del logo
    r = invia_struttura(C, 1, b'\x89PNG' + b'0' * (5 * 1024 * 1024))
    assert 'supera 3 MB' in html(r) + html(C.get('/anagrafiche/strutture/1')), 'logo da 5 MB accettato'


def lo_senza_file():
    prima = leggi(S, 1)['logo']
    r = invia_struttura(C, 1, societa='Solo il nome cambia S.r.l.')
    assert r.status_code == 302, 'HTTP %d' % r.status_code
    assert leggi(S, 1)['logo'] == prima, 'salvando senza file il logo e cambiato'
    assert leggi(S, 1)['societa'] == 'Solo il nome cambia S.r.l.', 'societa non salvata'


def lo_togli():
    r = invia_struttura(C, 1, rimuovi_logo='1')
    assert r.status_code == 302 and leggi(S, 1)['logo'] is None, 'logo non tolto'
    assert C.get('/logo/1').status_code == 404, 'il logo tolto e ancora servito'
    t = html(C.get('/giorno/%s' % MARTEDI.isoformat()))
    assert 'marchio-nome' in t and '<img src="/logo/' not in t, 'senza logo la pagina non mostra il nome'


def lo_carica_e_togli_insieme():
    r = invia_struttura(C, 1, immagine(), rimuovi_logo='1')
    assert r.status_code == 302 and e_png(leggi(S, 1)['logo']), 'con file e spunta insieme vince il file nuovo'


def lo_nome_file_strano():
    r = invia_struttura(C, 1, immagine(), nome_file='../../Windows/System32/evil.png')
    assert r.status_code == 302 and e_png(leggi(S, 1)['logo']), 'nome del file con percorso: HTTP %d' % r.status_code


for fmt in ('PNG', 'JPEG', 'WEBP', 'GIF', 'BMP'):
    prova('logo in %s: salvato come PNG' % fmt, fai_formato(fmt))
prova('i margini vuoti vengono tolti', lo_rifilato)
prova('lo sfondo bianco di un JPG diventa trasparente', lo_sfondo_trasparente)
prova('colore non toccato: segue il logo', lo_colore_segue_logo)
prova('colore cambiato insieme al logo: vince la scelta', lo_colore_scelto_vince)
prova('colore troppo chiaro: scurito e segnalato', lo_colore_chiaro_scurito)
for nome, dati, frammento in [
        ('testo.png', b'questo non e un logo', 'non è un\'immagine leggibile'),
        ('disegno.svg', b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', 'non è un\'immagine leggibile'),
        ('troncato.png', immagine()[:200], 'non è un\'immagine leggibile'),
        ('vuoto.png', b'', None),
        ('bianco.png', immagine(colore=(255, 255, 255)), 'risulta vuoto'),
        ('minuscolo.png', immagine(larghezza=4, altezza=4, margine=0), 'troppo piccolo'),
        ('bomba.png', bomba(), 'troppo grande'),
        ('pesante.png', b'\x89PNG' + b'0' * (3 * 1024 * 1024 + 100), 'supera 3 MB')]:
    if frammento is None:
        continue        # un file vuoto il browser non lo invia come file: equivale a nessun file
    prova('rifiutato: %s' % nome, fai_rifiuto(nome, dati, frammento))
prova('oltre i limiti: rinvio al modulo con spiegazione', lo_oltre_4mb)
prova('salvando senza file il logo resta', lo_senza_file)
prova('togli il logo: al suo posto il nome', lo_togli)
prova('file nuovo e spunta insieme: vince il file', lo_carica_e_togli_insieme)
prova('nome del file con un percorso dentro', lo_nome_file_strano)


# =====================================================================
area('servizio del logo')


def se_intestazioni():
    r = C.get('/logo/1')
    assert r.status_code == 200 and r.mimetype == 'image/png', '%d %s' % (r.status_code, r.mimetype)
    assert r.headers.get('X-Content-Type-Options') == 'nosniff', 'manca nosniff'
    assert 'max-age=31536000' in (r.headers.get('Cache-Control') or ''), 'cache: %s' % r.headers.get('Cache-Control')
    assert r.headers.get('ETag'), 'manca ETag'
    assert e_png(r.data), 'contenuto non PNG'


def se_inesistenti():
    for u in ('/logo/99999', '/logo/abc', '/logo/-1', '/logo/'):
        assert C.get(u).status_code == 404, '%s non da 404' % u


def se_versione_cambia():
    # due caricamenti uno dopo l'altro, senza attese: capita anche nello stesso secondo
    versioni = []
    for colore in ((120, 40, 160), (200, 30, 40), (30, 120, 60)):
        invia_struttura(C, 1, immagine(colore=colore))
        versioni.append(re.search(r'/logo/1\?v=(\d+)', html(C.get('/anagrafiche'))).group(1))
    assert len(set(versioni)) == 3, 'caricato un logo nuovo, l indirizzo resta uguale: %s' % versioni
    etag = C.get('/logo/1').headers.get('ETag')
    assert versioni[-1] in etag, 'ETag non allineato alla versione: %s' % etag


def se_colonna_differita():
    s = S()
    st = s.scalars(select(Struttura)).first()
    caricato = 'logo' in st.__dict__
    s.close()
    assert not caricato, 'il logo viene letto a ogni consultazione della struttura'


prova('intestazioni: PNG, nosniff, cache lunga, ETag', se_intestazioni)
prova('logo inesistente: 404', se_inesistenti)
prova('cambiando logo cambia l indirizzo', se_versione_cambia)
prova('il logo non si legge a ogni pagina', se_colonna_differita)


# =====================================================================
area('colori e testo nelle pagine')
S, C = mondo()


def co_colore_per_struttura():
    C.post('/anagrafiche/strutture/nuova', data={'nome': 'Seconda sede', 'societa': '', 'colore': '#2e7d32'})
    invia_struttura(C, 1, colore='#6b4e9b')
    t1 = html(C.get('/giorno/%s?struttura=1' % MARTEDI.isoformat()))
    t2 = html(C.get('/giorno/%s?struttura=2' % MARTEDI.isoformat()))
    assert '--primario: #6b4e9b' in t1, 'struttura 1 senza il suo colore'
    assert '--primario: #2e7d32' in t2, 'struttura 2 senza il suo colore'


def co_colore_manomesso():
    s = S()
    st = s.get(Struttura, 1)
    st.colore = 'red; } </style><script>alert(1)</script>'
    s.commit()
    s.close()
    t = html(C.get('/giorno/%s?struttura=1' % MARTEDI.isoformat()))
    assert '<script>alert(1)' not in t, 'colore iniettato nella pagina'
    assert '--primario: %s' % COLORE_PREDEFINITO in t, 'colore non valido senza ripiego'
    invia_struttura(C, 1, colore='#6b4e9b')


def co_testo_malevolo():
    r = invia_struttura(C, 1, nome='<script>alert(1)</script>', societa='<img src=x onerror=alert(2)>')
    assert r.status_code == 302, 'HTTP %d' % r.status_code
    for u in ('/giorno/%s?struttura=1' % MARTEDI.isoformat(), '/anagrafiche', '/anagrafiche/strutture/1'):
        t = html(C.get(u))
        assert '<script>alert(1)' not in t and '<img src=x' not in t, 'testo non neutralizzato in %s' % u
    invia_struttura(C, 1, nome='Prima sede', societa='')


def co_nessuna_struttura():
    s = S()
    for st in s.scalars(select(Struttura)):
        st.attiva = False
    s.commit()
    s.close()
    r = C.get('/giorno/%s' % MARTEDI.isoformat())
    assert r.status_code == 200 and 'Nessuna stanza configurata' in html(r), 'HTTP %d' % r.status_code
    s = S()
    for st in s.scalars(select(Struttura)):
        st.attiva = True
    s.commit()
    s.close()


def co_colore_non_inviato():
    invia_struttura(C, 1, colore='#6b4e9b')
    r = C.post('/anagrafiche/strutture/1', data={'nome': 'Prima sede'})
    assert r.status_code == 302, 'senza il campo colore: HTTP %d' % r.status_code
    assert leggi(S, 1)['colore'] == '#6b4e9b', 'colore perso: %s' % leggi(S, 1)['colore']


def co_colore_non_valido():
    r = invia_struttura(C, 1, colore='rosso')
    t = html(r)
    assert r.status_code == 200 and 'Colore: formato non valido' in t, 'colore non valido accettato'
    assert 'value="#6b4e9b"' in t, 'il campo non ripropone il colore precedente'
    assert leggi(S, 1)['colore'] == '#6b4e9b', 'colore cambiato nonostante l errore'


prova('ogni struttura ha il suo colore', co_colore_per_struttura)
prova('campo colore non inviato: il colore resta', co_colore_non_inviato)
prova('colore non valido: errore, il campo ripropone il precedente', co_colore_non_valido)
prova('colore manomesso nel database: ripiego, niente iniezione', co_colore_manomesso)
prova('nome e societa con codice: neutralizzati', co_testo_malevolo)
prova('nessuna struttura attiva: la pagina spiega', co_nessuna_struttura)


# =====================================================================
area('strutture multiple')
S, C = mondo()


def sm_nuova_con_logo():
    r = C.post('/anagrafiche/strutture/nuova', content_type='multipart/form-data', data={
        'nome': 'Sede due', 'societa': 'Due S.r.l.', 'colore': COLORE_PREDEFINITO,
        'logo': (io.BytesIO(immagine(colore=(200, 30, 40))), 'rosso.png')})
    assert r.status_code == 302, 'HTTP %d' % r.status_code
    s = S()
    st = s.scalars(select(Struttura).where(Struttura.nome == 'Sede due')).first()
    sid, colore, ha = st.id, st.colore, st.ha_logo
    s.close()
    assert ha, 'la struttura nuova non ha il logo'
    r_, g_, b_ = (int(colore[i:i + 2], 16) for i in (1, 3, 5))
    assert r_ > g_ and r_ > b_, 'colore non preso dal logo rosso: %s' % colore
    t = html(C.get('/giorno/%s?struttura=%d' % (MARTEDI.isoformat(), sid)))
    assert '<img src="/logo/%d?v=' % sid in t, 'griglia della sede due senza il suo logo'
    t = html(C.get('/anagrafiche/stanze/nuova'))
    assert 'Sede due' in t, 'la sede due non si puo scegliere per le stanze'


def sm_doppione():
    r = C.post('/anagrafiche/strutture/nuova', data={'nome': 'SEDE DUE', 'colore': COLORE_PREDEFINITO})
    assert r.status_code == 200 and 'Esiste già una struttura' in html(r), 'doppione accettato'


def sm_elimina_con_stanze():
    r = C.post('/anagrafiche/strutture/1', data={'azione': 'elimina'}, follow_redirects=True)
    t = html(r)
    assert 'non si può eliminare' in t and 'è usata da 6 stanze' in t, 'rifiuto non spiegato'


def sm_elimina_vuota():
    s = S()
    sid = s.scalars(select(Struttura).where(Struttura.nome == 'Sede due')).first().id
    s.close()
    r = C.post('/anagrafiche/strutture/%d' % sid, data={'azione': 'elimina'})
    assert r.status_code == 302, 'HTTP %d' % r.status_code
    s = S()
    rimasta = s.get(Struttura, sid)
    s.close()
    assert rimasta is None, 'struttura senza stanze non eliminata'


def sm_ultima():
    S2, C2 = mondo()
    s = S2()
    for r in s.scalars(select(Risorsa)):
        s.delete(r)
    s.commit()
    s.close()
    r = C2.post('/anagrafiche/strutture/1', data={'azione': 'elimina'}, follow_redirects=True)
    assert 'unica struttura' in html(r), 'eliminata l ultima struttura'
    collega(S)


def sm_inesistente():
    assert C.get('/anagrafiche/strutture/99999').status_code == 404, 'nessun 404'


def sm_senza_stanze():
    r = C.post('/anagrafiche/strutture/nuova', data={'nome': 'Sede vuota', 'colore': '#6b4e9b'})
    assert r.status_code == 302, 'HTTP %d' % r.status_code
    sid = id_struttura('Sede vuota')
    t = html(C.get('/giorno/%s?struttura=%d' % (MARTEDI.isoformat(), sid)))
    assert 'non ha ancora stanze' in t, 'struttura senza stanze: griglia vuota senza spiegazione'
    collegamento = '/anagrafiche/stanze/nuova?struttura=%d' % sid
    assert collegamento in t, 'manca il collegamento per aggiungere la stanza'
    t = html(C.get(collegamento))
    assert re.search(r'<option value="%d" selected>Sede vuota</option>' % sid, t), \
        'il modulo della stanza non propone la struttura da cui si arriva'
    r = C.post('/anagrafiche/stanze/nuova', data={'nome': 'Studio A', 'tipo': 'AMBULATORIO',
                                                  'struttura': str(sid), 'ordine': '1', 'attiva': '1'})
    assert r.status_code == 302, 'stanza non salvata: HTTP %d' % r.status_code
    t = html(C.get('/giorno/%s?struttura=%d' % (MARTEDI.isoformat(), sid)))
    assert 'non ha ancora stanze' not in t and 'Studio A' in t, 'la stanza nuova non compare in griglia'


def sm_prenotazione_nella_sede_giusta():
    """Dalla griglia della seconda sede, "Nuovo appuntamento" deve proporre le
    sue stanze, non la prima stanza della prima sede."""
    sid = id_struttura('Sede vuota')
    s = S()
    stanza = s.scalars(select(Risorsa).where(Risorsa.nome == 'Studio A')).first().id
    s.close()
    C.post('/anagrafiche/medici/nuovo', data={'cognome': 'Bianchi', 'colore': '#154381', 'attivo': '1'})
    t = html(C.get('/appuntamento?data=%s&struttura=%d' % (MARTEDI.isoformat(), sid)))
    sel = re.search(r'<select id="risorsa".*?</select>', t, re.S).group(0)
    assert '<optgroup label="Sede vuota">' in sel, 'stanze non raggruppate per struttura'
    prima = re.search(r'<option value="(\d+)"', sel).group(1)
    assert int(prima) == stanza, 'la prima stanza proposta e di un altra sede'
    s = S()
    medico = s.scalars(select(Operatore).where(Operatore.cognome == 'Bianchi')).first().id
    prest = s.scalars(select(Prestazione)).first().id
    s.close()
    # il modulo arriva dalla prima sede ma la stanza scelta e della seconda
    r = C.post('/appuntamento', data={'struttura': '1', 'risorsa': str(stanza), 'operatore': str(medico),
                                      'prestazione': str(prest), 'data': MARTEDI.isoformat(), 'ora': '10:00',
                                      'durata': '30', 'paziente': 'Verdi', 'telefono': ''})
    assert r.status_code == 302 and 'struttura=%d' % sid in r.headers['Location'], \
        'dopo il salvataggio non torna alla sede della stanza: %s' % r.headers.get('Location')
    s = S()
    aid = s.scalars(select(Appuntamento).where(Appuntamento.risorsa_id == stanza)).first().id
    s.close()
    t = html(C.get('/appuntamento/%d' % aid))          # senza ?struttura=
    assert 'struttura=%d' % sid in re.search(r'href="([^"]*)">Torna alla giornata', t).group(1), \
        'modificando, "Torna alla giornata" porta a un altra sede'
    r = C.post('/appuntamento/%d' % aid, data={'azione': 'elimina', 'struttura': '1'})
    assert r.status_code == 302 and 'struttura=%d' % sid in r.headers['Location'], \
        'dopo l eliminazione non torna alla sede giusta: %s' % r.headers.get('Location')


def id_struttura(nome):
    s = S()
    sid = s.scalars(select(Struttura).where(Struttura.nome == nome)).first().id
    s.close()
    return sid


prova('nuova struttura con logo, colore e stanze', sm_nuova_con_logo)
prova('struttura senza stanze: la griglia spiega e porta al modulo', sm_senza_stanze)
prova('prenotazione dalla seconda sede: stanze e ritorno giusti', sm_prenotazione_nella_sede_giusta)
prova('nome gia usato: rifiutato', sm_doppione)
prova('struttura con stanze: eliminazione rifiutata', sm_elimina_con_stanze)
prova('struttura senza stanze: eliminata', sm_elimina_vuota)
prova('l ultima struttura non si elimina', sm_ultima)
prova('struttura inesistente: 404', sm_inesistente)


# =====================================================================
area('export in Excel')
S, C = mondo()


def ex_foglio(sid=1):
    import openpyxl
    r = C.get('/esporta/%s?struttura=%d' % (MARTEDI.isoformat(), sid))
    assert r.status_code == 200, 'HTTP %d' % r.status_code
    return openpyxl.load_workbook(io.BytesIO(r.data)).active


def ex_con_logo():
    invia_struttura(C, 1, immagine(larghezza=600, altezza=150, margine=0), nome='Studio Uno', societa='Uno S.r.l.')
    ws = ex_foglio()
    assert len(ws._images) == 1, '%d immagini' % len(ws._images)
    # nel file c'e' il PNG intero (nitido in stampa); la misura a video e'
    # quella dell'ancoraggio, in EMU: 9525 per pixel
    ext = ws._images[0].anchor.ext
    larghezza, altezza = ext.width / 9525, ext.height / 9525
    assert altezza == 35 and abs(larghezza - 140) <= 2, 'logo a video %dx%d' % (larghezza, altezza)
    titoli = [c for c in ws[1] if c.value]
    assert titoli and 'STUDIO UNO' in titoli[0].value, 'titolo senza il nome della struttura'
    assert titoli[0].column > 1, 'titolo sopra al logo, in A1'
    assert ws.oddFooter.left.text == 'Uno S.r.l.', 'societa assente dal piede di pagina'
    return '%s in %s' % (titoli[0].value, titoli[0].coordinate)


def ex_senza_logo():
    invia_struttura(C, 1, rimuovi_logo='1', societa='')
    ws = ex_foglio()
    assert len(ws._images) == 0, 'immagine senza logo'
    assert ws['A1'].value and 'STUDIO UNO' in ws['A1'].value, 'senza logo il titolo non e in A1'


prova('con logo: immagine, titolo dopo il logo, societa nel piede', ex_con_logo)
prova('senza logo: nessuna immagine, titolo in A1', ex_senza_logo)


# =====================================================================
area('robustezza')
S, C = mondo()


def ro_casuali():
    caso = random.Random(2026)
    guasti = []
    base = immagine()
    for n in range(150):
        tipo = caso.random()
        if tipo < 0.3:
            dati = bytes(caso.getrandbits(8) for _ in range(caso.randint(1, 4000)))
        elif tipo < 0.7:
            dati = bytearray(base)                      # PNG valido con byte alterati
            for _ in range(caso.randint(1, 40)):
                dati[caso.randrange(len(dati))] = caso.getrandbits(8)
            dati = bytes(dati)
        else:
            dati = base[:caso.randint(1, len(base))]    # PNG troncato a caso
        r = invia_struttura(C, 1, dati, nome_file=caso.choice(['a.png', 'b.jpg', 'c', '.png', 'x.svg']))
        if r.status_code >= 500:
            guasti.append(r.status_code)
        logo = leggi(S, 1)['logo']
        if logo is not None and not e_png(logo):
            guasti.append('logo non PNG nel database')
        if logo is not None:
            Image.open(io.BytesIO(logo)).load()        # deve sempre decodificarsi
    assert not guasti, guasti[:3]
    return '150 file alterati, nessun 5xx, nel database sempre un PNG valido o niente'


def ro_parallelo():
    errori = []
    barriera = threading.Barrier(3)

    def carica(colore):
        c = A.app.test_client()
        barriera.wait()
        try:
            r = invia_struttura(c, 1, immagine(colore=colore))
            if r.status_code != 302:
                errori.append(r.status_code)
        except Exception as e:
            errori.append(repr(e)[:80])

    fili = [threading.Thread(target=carica, args=(c,)) for c in [(200, 30, 40), (30, 120, 60), (40, 60, 200)]]
    for f in fili: f.start()
    for f in fili: f.join()
    assert not errori, errori
    assert e_png(leggi(S, 1)['logo']), 'dopo tre caricamenti insieme il logo non e valido'


def ro_numeri_enormi():
    """Un numero oltre il limite di SQLite nell'indirizzo non deve far cadere la pagina."""
    guasti = []
    for n in ('9' * 25, '-' + '9' * 25, str(2 ** 63 - 1), str(2 ** 63)):
        for u in ('/logo/%s', '/appuntamento/%s', '/anagrafiche/strutture/%s', '/anagrafiche/stanze/%s',
                  '/anagrafiche/medici/%s', '/anagrafiche/turni/%s', '/anagrafiche/prestazioni/%s',
                  '/giorno/%s?struttura=%%s' % MARTEDI.isoformat(), '/esporta/%s?struttura=%%s' % MARTEDI.isoformat(),
                  '/appuntamento?struttura=%s', '/appuntamento?risorsa=%s', '/anagrafiche/stanze/nuova?struttura=%s'):
            r = C.get(u % n)
            if r.status_code >= 500:
                guasti.append('%s -> %d' % (u % n, r.status_code))
        r = C.post('/appuntamento', data={'struttura': n, 'risorsa': n, 'operatore': n, 'prestazione': n,
                                          'data': MARTEDI.isoformat(), 'ora': '09:00'})
        if r.status_code >= 500:
            guasti.append('POST appuntamento %s -> %d' % (n, r.status_code))
    assert not guasti, guasti[:4]
    return '48 indirizzi e 4 moduli con numeri fuori scala, nessun errore interno'


prova('150 file alterati a caso', ro_casuali)
prova('numeri oltre il limite di SQLite negli indirizzi', ro_numeri_enormi)
prova('tre caricamenti contemporanei', ro_parallelo)


# =====================================================================
ordine = []
for e in esiti:
    if e[1] not in ordine:
        ordine.append(e[1])
print()
for ar in ordine:
    gruppo = [e for e in esiti if e[1] == ar]
    rotti = [e for e in gruppo if e[0] != 'OK']
    print('%-28s %3d prove  %s' % (ar, len(gruppo), 'tutte a posto' if not rotti else '%d DA SISTEMARE' % len(rotti)))
guasti = [e for e in esiti if e[0] != 'OK']
if guasti:
    print('\nDettaglio:')
    for stato, ar, nome, msg in guasti:
        print('  %-6s [%s] %s\n         %s' % (stato, ar, nome, msg))
if os.environ.get('DETTAGLIO'):
    print('\nNote delle prove superate:')
    for stato, ar, nome, msg in esiti:
        if stato == 'OK' and msg:
            print('  [%s] %s: %s' % (ar, nome, msg))
print('\n%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(guasti), len(guasti)))

A._registro = None
for f in _file:
    try:
        os.remove(f)
    except OSError:
        pass
# le copie di sicurezza fatte dagli aggiornamenti di schema provati qui
import shutil
shutil.rmtree(os.path.join(CARTELLA, 'backup'), ignore_errors=True)
