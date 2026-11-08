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


# ======================================================= fogli Excel comuni
# Lo stesso aspetto per tutti i file Excel del programma (dalla 1.12): il
# titolo blu con la struttura e il periodo, la riga «esportato il», le
# intestazioni bianche su blu con i bordi sottili, i numeri in formato
# italiano (ore, euro, date), la riga dei totali, il foglio A4 che sta nella
# larghezza della pagina con le intestazioni ripetute e «Pagina X di Y».
# Prima ogni export aveva il suo stile (ciano, solo grassetto, blu...) e quasi
# nessuno stava in una pagina.
EXCEL_BLU = '154381'
EXCEL_BORDO = '9AA5AD'
EXCEL_GRIGIO = '5B6B75'
EXCEL_ZEBRA = 'F3F5F8'
EXCEL_CARATTERE = 'Calibri'
FORMATO_ORA = 'hh:mm'
FORMATO_EURO = '#,##0.00 €'
FORMATO_DATA = 'dd/mm/yyyy'
FORMATO_DATA_ORA = 'dd/mm/yyyy hh:mm'
FORMATO_ORE = '0.00'
FORMATO_PERCENTO = '0.0"%"'


def bordo_excel(spessore='thin', colore=EXCEL_BORDO):
    """Il bordo di una cella, uguale sui quattro lati."""
    from openpyxl.styles import Border, Side
    lato = Side(style=spessore, color=colore)
    return Border(left=lato, right=lato, top=lato, bottom=lato)


def carattere_excel(**altro):
    """Il carattere delle celle (Calibri 10), con le varianti chieste."""
    from openpyxl.styles import Font
    altro.setdefault('name', EXCEL_CARATTERE)
    altro.setdefault('size', 10)
    return Font(**altro)


def stile_intestazione_excel(cella, testo=None):
    """Una cella di intestazione: bianco in grassetto su blu, centrata, a capo
    se serve, con il bordo."""
    from openpyxl.styles import Alignment, PatternFill
    if testo is not None:
        cella.value = testo_excel(testo)
    cella.font = carattere_excel(bold=True, color='FFFFFF')
    cella.fill = PatternFill('solid', fgColor=EXCEL_BLU)
    cella.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    cella.border = bordo_excel()
    return cella


def _senza_e_commerciale(testo):
    """Nelle testate e nei pie' di pagina di Excel la «&» comanda: raddoppiata e' letterale."""
    return (testo or '').replace('&', '&&')


def apri_foglio_excel(ws, titolo, sottotitolo=None, struttura=None, adesso=None, colonne=1):
    """Le prime righe di un foglio: il titolo in blu (con il nome della
    struttura davanti, se non c'e' gia'), il sottotitolo (il periodo) e la riga
    «Esportato il ... dal Gestionale Agende». Con 'colonne' le righe si uniscono
    su quelle colonne, cosi' il titolo non viene tagliato sulla carta.
    Restituisce la prima riga libera, lasciandone una vuota."""
    from openpyxl.styles import Alignment
    adesso = adesso or datetime.now()
    nome = testo_excel(struttura.nome) if struttura is not None and getattr(struttura, 'nome', None) else ''
    testo_titolo = testo_excel(titolo)
    if nome and nome.lower() not in testo_titolo.lower():
        testo_titolo = '%s — %s' % (nome, testo_titolo)
    c = ws.cell(1, 1, testo_titolo)
    c.font = carattere_excel(size=14, bold=True, color=EXCEL_BLU)
    c.alignment = Alignment(vertical='center')
    ws.row_dimensions[1].height = 22
    riga = 2
    if sottotitolo:
        ws.cell(riga, 1, testo_excel(sottotitolo)).font = carattere_excel(size=11, bold=True)
        riga += 1
    ws.cell(riga, 1, 'Esportato il %s alle %s dal Gestionale Agende'
            % (adesso.strftime('%d/%m/%Y'), adesso.strftime('%H:%M'))).font = carattere_excel(size=9, italic=True,
                                                                                               color=EXCEL_GRIGIO)
    if colonne > 1:
        for r in range(1, riga + 1):
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=colonne)
    return riga + 2


def _e_numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def tabella_excel(ws, riga, intestazioni, larghezze, righe, formati=None, totali=None, zebra=False, a_capo=(),
                  stile_riga=None, filtro=True, blocca=True):
    """Una tabella che comincia alla riga 'riga': l'intestazione, le righe dei
    dati con i bordi e i testi ripuliti (testo_excel), i formati per colonna
    ({colonna: formato}, colonne da 1), la riga dei totali ({colonna: 'somma' |
    'conta' | un valore}, in grassetto con la riga sopra piu' spessa; senza
    niente nella prima colonna ci va «Totale»), le colonne con il testo lungo
    da mandare a capo, uno stile per riga (una funzione che dai valori della
    riga dice {'font': ..., 'fill': ...} oppure None: per esempio i disdetti in
    grigio), il filtro automatico e i riquadri bloccati sotto l'intestazione.
    Restituisce la prima riga libera dopo la tabella (una vuota in mezzo)."""
    from openpyxl.styles import Alignment, Border, PatternFill, Side
    from openpyxl.utils import get_column_letter
    formati = formati or {}
    bordo = bordo_excel()
    for c, testo in enumerate(intestazioni, start=1):
        stile_intestazione_excel(ws.cell(riga, c), testo)
        if larghezze and c <= len(larghezze) and larghezze[c - 1]:
            ws.column_dimensions[get_column_letter(c)].width = larghezze[c - 1]
    ws.row_dimensions[riga].height = 30 if any(
        len(str(t)) > (larghezze[i] if larghezze and i < len(larghezze) and larghezze[i] else 12)
        for i, t in enumerate(intestazioni)) else 18
    normale = carattere_excel()
    zebra_fill = PatternFill('solid', fgColor=EXCEL_ZEBRA)
    r = riga + 1
    for n, valori in enumerate(righe):
        extra = stile_riga(valori) if stile_riga else None
        for c, v in enumerate(valori, start=1):
            cella = ws.cell(r, c, testo_excel(v))
            cella.border = bordo
            cella.font = (extra or {}).get('font') or normale
            if c in formati and (v is not None):
                cella.number_format = formati[c]
            if c in a_capo:
                cella.alignment = Alignment(wrap_text=True, vertical='top')
            elif _e_numero(v):
                cella.alignment = Alignment(horizontal='right', vertical='top')
            else:
                cella.alignment = Alignment(vertical='top')
            if (extra or {}).get('fill') is not None:
                cella.fill = extra['fill']
            elif zebra and n % 2:
                cella.fill = zebra_fill
        r += 1
    fine_dati = r - 1
    if totali:
        spesso = Side(style='medium', color=EXCEL_BLU)
        sottile = Side(style='thin', color=EXCEL_BORDO)
        for c in range(1, len(intestazioni) + 1):
            cella = ws.cell(r, c)
            cella.border = Border(left=sottile, right=sottile, top=spesso, bottom=sottile)
            cella.font = carattere_excel(bold=True)
            regola = totali.get(c)
            if regola == 'somma':
                cella.value = sum(v[c - 1] for v in righe if c - 1 < len(v) and _e_numero(v[c - 1]))
            elif regola == 'conta':
                cella.value = len(righe)
            elif regola is not None:
                cella.value = testo_excel(regola)
            if _e_numero(cella.value):
                cella.alignment = Alignment(horizontal='right')
                if c in formati:
                    cella.number_format = formati[c]
        if 1 not in totali:
            ws.cell(r, 1).value = 'Totale'
        r += 1
    if blocca:
        ws.freeze_panes = 'A%d' % (riga + 1)
    if filtro and righe:
        ws.auto_filter.ref = 'A%d:%s%d' % (riga, get_column_letter(len(intestazioni)), fine_dati)
    return r + 1


def imposta_stampa_excel(ws, orizzontale=True, righe_titolo=None, colonne_titolo=None, struttura=None, periodo='',
                         margine=0.4):
    """Il foglio su carta: A4, orizzontale o verticale, largo quanto la pagina
    (anche su piu' pagine in altezza), le righe (e le colonne) da ripetere in
    ogni pagina, in testa «struttura · periodo», in fondo la societa' (o la
    struttura) a sinistra e «Pagina X di Y» a destra."""
    from openpyxl.worksheet.properties import PageSetupProperties
    ws.page_setup.orientation = 'landscape' if orizzontale else 'portrait'
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    if righe_titolo:
        ws.print_title_rows = righe_titolo
    if colonne_titolo:
        ws.print_title_cols = colonne_titolo
    nome = testo_excel(struttura.nome) if struttura is not None and getattr(struttura, 'nome', None) else ''
    testa = ' · '.join(x for x in (nome, periodo) if x)
    if testa:
        ws.oddHeader.center.text = _senza_e_commerciale(testa)
    societa = (getattr(struttura, 'societa', '') or '') if struttura is not None else ''
    ws.oddFooter.left.text = _senza_e_commerciale(testo_excel(societa or nome or 'Gestionale Agende'))
    ws.oddFooter.right.text = 'Pagina &P di &N'
    ws.page_margins.left = ws.page_margins.right = margine
    ws.page_margins.top = ws.page_margins.bottom = 0.6
    return ws
