# -*- coding: utf-8 -*-
"""Funzioni di servizio usate da piu' pagine: numeri e date che arrivano
dall'indirizzo, ritorno sicuro dopo un'azione, struttura scelta, risposte
JSON, colore dei medici nuovi, file Excel da scaricare, collegamenti email.

Prima erano copiate in ogni modulo, e due copie si erano gia' allontanate
(i suggerimenti dei pazienti senza "no-store", il mese "202609" letto in un
posto e non nell'altro). I moduli le importano con lo stesso nome di prima."""
import json
import logging
import os
import re
import ssl
from datetime import date, datetime, timedelta
from io import BytesIO
from urllib.parse import quote

from flask import Response, request, send_file
from sqlalchemy import select

from modelli import Struttura, Operatore, percorso_db
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
VERSIONE = '1.12'

# nella griglia il colore e' il modo piu' rapido per distinguerli
PALETTE = ['#154381', '#5B7F3E', '#A8582B', '#6B4E9B', '#B3261E',
           '#0F7C8C', '#8A6D1F', '#4A5560', '#C2185B', '#2E7D32']
MIME_XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
# il file, accanto al database, con i certificati in piu' di cui fidarsi (un
# antivirus o un proxy della rete che riscrive i certificati dei siti: ci si
# mette il suo). Si legge se c'e'; di solito non c'e'
FILE_CERTIFICATI = 'certificati.pem'
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
    controllo (anche quelli gia' salvati prima della 1.11), il resto com'e'.
    Un testo che comincia con «=» (un nome scritto cosi' per sbaglio) openpyxl
    lo scriverebbe come formula: davanti ci va uno spazio (1.12)."""
    if not isinstance(valore, str):
        return valore
    testo = testo_pulito(valore)
    return ' ' + testo if testo.startswith('=') else testo


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


# ================================================== connessioni protette
def cartella_dati():
    """La cartella del database: li' stanno anche backup, aggiornamenti e
    il file dei certificati in piu'."""
    import viste                                   # qui, non in testa: viste importa comune
    percorso, _ = viste.percorso_database()
    return os.path.dirname(percorso or percorso_db())


def elenco_mozilla():
    """Il file con i certificati delle autorita' riconosciute da Mozilla
    (il pacchetto certifi, dentro l'eseguibile), o None se manca."""
    try:
        import certifi
        percorso = certifi.where()
    except (ImportError, OSError):
        return None
    return percorso if os.path.isfile(percorso) else None


def file_certificati():
    return os.path.join(cartella_dati(), FILE_CERTIFICATI)


def contesto_tls():
    """La connessione protetta (gli aggiornamenti, le email) che riconosce il
    certificato del sito. Si fida dei certificati che conosce il sistema (su
    Windows il suo elenco), di quelli delle autorita' riconosciute da Mozilla
    portati dentro il programma (certifi) e, se c'e', di quelli nel file
    certificati.pem accanto al database.

    Perche' l'elenco di Windows da solo non basta: Windows ha pochi
    certificati di partenza e aggiunge una radice nuova solo la prima volta
    che la incontra con Edge o con un suo programma. Il gestionale usa
    l'elenco cosi' com'e', senza farglielo fare: quando GitHub e' passato a
    radici nuove (2025) il controllo degli aggiornamenti della 1.9 sul PC
    della clinica diceva «il certificato del sito degli aggiornamenti non e'
    valido», mentre il browser apriva il sito senza problemi. Dalla 1.12
    l'elenco di Mozilla viaggia con il programma, e non dipende piu' da cosa
    ha gia' visto Windows."""
    contesto = ssl.create_default_context()
    for percorso in (elenco_mozilla(), file_certificati()):
        if percorso and os.path.isfile(percorso):
            try:
                contesto.load_verify_locations(cafile=percorso)
            except (OSError, ssl.SSLError) as e:
                logging.getLogger('gestionale').warning('certificati in %s non letti: %s', percorso, e)
    return contesto


def certificati_in_uso():
    """Una riga per l'assistenza: da dove arrivano i certificati di cui il
    programma si fida."""
    parti = ['quelli del sistema']
    mozilla = elenco_mozilla()
    if mozilla:
        try:
            import certifi
            parti.append('l\'elenco Mozilla del %s' % certifi.__version__.replace('.', '-'))
        except (ImportError, AttributeError):
            parti.append('l\'elenco Mozilla')
    if os.path.isfile(file_certificati()):
        parti.append('il file %s' % FILE_CERTIFICATI)
    return ', '.join(parti[:-1]) + ' e ' + parti[-1] if len(parti) > 1 else parti[0]


# i motivi per cui un certificato non passa, nelle parole di OpenSSL, spiegati
MOTIVI_CERTIFICATO = (
    ('unable to get local issuer', 'è firmato da un\'autorità che questo PC non conosce'),
    ('unable to get issuer', 'è firmato da un\'autorità che questo PC non conosce'),
    ('self-signed', 'è autofirmato: in mezzo c\'è un proxy o un antivirus che riscrive i certificati'),
    ('self signed', 'è autofirmato: in mezzo c\'è un proxy o un antivirus che riscrive i certificati'),
    ('has expired', 'risulta scaduto: se il sito funziona nel browser, la data del PC è sbagliata'),
    ('not yet valid', 'non è ancora valido: la data del PC è indietro'),
    ('hostname mismatch', 'è di un altro sito: qualcosa nella rete si mette in mezzo'),
    ('doesn\'t match', 'è di un altro sito: qualcosa nella rete si mette in mezzo'),
)


def spiega_certificato(errore):
    """Perche' un certificato non passa, in parole semplici (con il motivo di
    OpenSSL fra parentesi, per l'assistenza)."""
    motivo = getattr(errore, 'verify_message', '') or str(errore)
    for pezzo, testo in MOTIVI_CERTIFICATO:
        if pezzo in motivo.lower():
            return '%s (%s)' % (testo, motivo)
    return motivo


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
