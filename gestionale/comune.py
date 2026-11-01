# -*- coding: utf-8 -*-
"""Funzioni di servizio usate da piu' pagine: numeri e date che arrivano
dall'indirizzo, ritorno sicuro dopo un'azione, struttura scelta, risposte
JSON, colore dei medici nuovi, file Excel da scaricare, collegamenti email.

Prima erano copiate in ogni modulo, e due copie si erano gia' allontanate
(i suggerimenti dei pazienti senza "no-store", il mese "202609" letto in un
posto e non nell'altro). I moduli le importano con lo stesso nome di prima."""
import json
import re
from datetime import date, datetime, timedelta
from io import BytesIO
from urllib.parse import quote

from flask import Response, request, send_file
from sqlalchemy import select

from modelli import Struttura, Operatore
import servizi

# SQLite conserva interi fino a 2^63-1: un numero piu' grande scritto nella
# barra degli indirizzi arriverebbe alla query e la farebbe cadere con un
# errore interno. Oltre quel limite l'indirizzo semplicemente non esiste.
MASSIMO_ID = 2 ** 63 - 1
# le date dell'agenda: fuori da qui, un indirizzo scritto a mano. Oltre questi
# estremi sommare o sottrarre un giorno manderebbe in OverflowError
PRIMA = date(2000, 1, 1)
ULTIMA = date(2100, 12, 31)
# colori proposti ai medici nuovi, uno diverso per ciascuno finche' bastano:
# la versione del programma: la stessa di installer.iss (una prova controlla
# che coincidano), mostrata in Aiuto per sapere cosa e' installato
VERSIONE = '1.11'

# nella griglia il colore e' il modo piu' rapido per distinguerli
PALETTE = ['#154381', '#5B7F3E', '#A8582B', '#6B4E9B', '#B3261E',
           '#0F7C8C', '#8A6D1F', '#4A5560', '#C2185B', '#2E7D32']
MIME_XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
# Outlook non apre un collegamento mailto molto piu' lungo di 2000 caratteri,
# contati sull'indirizzo codificato (uno spazio diventa %20, una "è" %C3%A8)
MASSIMO_MAILTO = 1900


# i caratteri di controllo che openpyxl rifiuta (resta solo quello che un testo puo' avere: a
# capo, ritorno e tabulazione). \x0b e \x0c sono gli «a capo manuali» di Word, che un Ctrl+V
# porta in una casella di testo: diventano un a capo
_CONTROLLO = re.compile(r'[\x00-\x08\x0e-\x1f\x7f]')


def testo_pulito(testo):
    """Un testo scritto in un modulo, senza i caratteri di controllo che poi
    farebbero cadere l'Excel del planning o del riepilogo (1.11)."""
    if not testo:
        return testo
    return _CONTROLLO.sub('', str(testo).replace('\x0b', '\n').replace('\x0c', '\n'))


def testo_excel(valore):
    """Un valore per una cella di openpyxl: i testi senza caratteri di
    controllo (anche quelli gia' salvati prima della 1.11), il resto com'e'."""
    return testo_pulito(valore) if isinstance(valore, str) else valore


def intero(valore, difetto=0):
    """Gli id arrivano dalla barra degli indirizzi: possono essere qualunque cosa,
    anche un numero di trenta cifre che SQLite non sa confrontare."""
    try:
        v = int(valore)
    except (TypeError, ValueError):
        return difetto
    return v if -MASSIMO_ID <= v <= MASSIMO_ID else difetto


def data_da(testo, difetto=None):
    """La data dell'indirizzo, 'aaaa-mm-gg', riportata fra PRIMA e ULTIMA; se
    non si legge, 'difetto' o oggi."""
    try:
        g = datetime.strptime(testo or '', '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return difetto if difetto is not None else date.today()
    return min(max(g, PRIMA), ULTIMA)


def mese_da(aaaamm):
    """(primo, ultimo giorno) del mese 'aaaa-mm' o 'aaaamm'; se non si legge,
    il mese in corso."""
    m = re.fullmatch(r'(\d{4})-?(\d{2})', aaaamm or '')
    oggi = date.today()
    anno, numero = (int(m.group(1)), int(m.group(2))) if m else (oggi.year, oggi.month)
    if not (1 <= numero <= 12 and PRIMA.year <= anno < ULTIMA.year):
        anno, numero = oggi.year, oggi.month
    primo = date(anno, numero, 1)
    ultimo = date(anno + (numero == 12), numero % 12 + 1, 1) - timedelta(days=1)
    return primo, ultimo


def giorno_breve(g):
    """'martedì 13 ottobre'."""
    return '%s %d %s' % (servizi.GIORNI[g.weekday()], g.day, servizi.MESI[g.month - 1])


def destinazione_sicura(torna, ripiego):
    """Dove tornare dopo un'azione: solo indirizzi interni. '//sito' o '/\\sito'
    porterebbero fuori dal programma."""
    torna = torna or ''
    if re.fullmatch(r'/(?![/\\])[^\s\\]*', torna) and len(torna) < 500:
        return torna
    return ripiego


def struttura_scelta(s):
    """(struttura chiesta nell'indirizzo o nel modulo, se esiste e' attiva,
    altrimenti la prima; elenco delle strutture attive)."""
    strutture = s.scalars(select(Struttura).where(Struttura.attiva == True).order_by(Struttura.id)).all()
    if not strutture:
        return None, []
    sid = intero(request.values.get('struttura'))
    st = next((x for x in strutture if x.id == sid), strutture[0])
    return st, strutture


def json_sicuro(dati):
    """JSON che non si puo' leggere come HTML (< > & codificati) e che il
    browser non conserva nella sua cache: dentro ci sono nomi e telefoni."""
    testo = json.dumps(dati, ensure_ascii=False)
    testo = testo.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    r = Response(testo, mimetype='application/json')
    r.headers['X-Content-Type-Options'] = 'nosniff'
    r.headers['Cache-Control'] = 'no-store'
    return r


def colore_libero(s):
    """Il primo colore della tavolozza non ancora usato da un medico."""
    usati = {c.lower() for c in s.scalars(select(Operatore.colore)) if c}
    return next((c for c in PALETTE if c.lower() not in usati), PALETTE[0])


def scarica_excel(libro, nome):
    """Il file Excel da scaricare nasce in memoria: nella cartella temporanea
    di Windows non ne resta una copia, e i fogli hanno nomi e telefoni dei
    pazienti. 'libro' e' un Workbook di openpyxl o un BytesIO gia' scritto."""
    if hasattr(libro, 'save'):
        dati = BytesIO()
        libro.save(dati)
    else:
        dati = libro
    dati.seek(0)
    return send_file(dati, mimetype=MIME_XLSX, as_attachment=True, download_name=nome)


def indirizzo_mail(email, oggetto, testo, coda):
    """Il collegamento mailto: con oggetto e testo gia' scritti. Se
    l'indirizzo codificato supera MASSIMO_MAILTO, il testo si ferma
    all'ultima riga intera che ci sta e finisce con 'coda'."""
    base = 'mailto:%s?subject=%s&body=' % (quote(email.strip(), safe='@.+'), quote(oggetto))
    corpo = quote(testo)
    if len(base) + len(corpo) <= MASSIMO_MAILTO:
        return base + corpo
    righe = testo.split('\n')
    while righe:
        righe.pop()
        corpo = quote('\n'.join(righe + [coda]))
        if len(base) + len(corpo) <= MASSIMO_MAILTO:
            return base + corpo
    return base
