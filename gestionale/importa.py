# -*- coding: utf-8 -*-
"""Importazione da Excel e CSV: la rubrica dei pazienti e le agende che
l'accettazione tiene oggi nei fogli.

Il riconoscimento delle colonne mette insieme due indizi:
1. il nome della colonna, confrontato con un elenco di sinonimi dopo aver
   tolto accenti, maiuscole e punteggiatura;
2. il contenuto, letto su un campione di righe: date, orari, telefoni,
   email, codici fiscali, nomi di persona.
Un indizio sul contenuto puo' smentire il nome: una colonna TELEFONO che
contiene sempre lo stesso numero per lo stesso medico e' il telefono del
medico, non del paziente (succede nelle agende degli interventi).

Le agende a blocchi, con piu' sale affiancate e le stesse colonne ripetute
per ciascuna sala, si riconoscono dalle intestazioni che si ripetono; il
nome della sala sta nella riga sopra. Giorno e data scritti una volta per
blocco, anche in celle unite, valgono per le righe sotto.

Niente si salva finche' non si conferma, e prima di importare si fa un
backup. Ogni riga scartata ha il suo motivo."""
import csv
import difflib
import hashlib
import io
import json
import math
import os
import re
import secrets
import tempfile
import threading
import time as orologio
import unicodedata
from datetime import date, datetime, time, timedelta
from types import SimpleNamespace

from flask import (Blueprint, render_template, request, redirect, url_for, flash, abort,
                   send_file)
from sqlalchemy import select

from modelli import (Struttura, Risorsa, Operatore, Prestazione, Paziente, Appuntamento, NotaGiorno, Appunto,
                     STATI_ATTIVI, ETICHETTA_STATO, ETICHETTA_TIPO_VISITA, leggi_impostazione,
                     scrivi_impostazione, importo_in_testo, leggi_degenza, e_campo_degenza,
                     MASSIMO_IMPORTO)
import servizi
from comune import colore_libero
import pazienti
import segreteria
import backup

bp = Blueprint('importa', __name__)
_fornitore = None
_lucchetto = threading.Lock()

MASSIMO_FILE = 10 * 1024 * 1024
MASSIMO_RIGHE = 20000
MASSIMO_COLONNE = 80
RIGHE_ANTEPRIMA = 40


def collega(app, fornitore_sessione, lucchetto=None):
    global _fornitore, _lucchetto
    _fornitore = fornitore_sessione
    if lucchetto is not None:
        _lucchetto = lucchetto
    app.register_blueprint(bp)


def ses():
    return _fornitore()


# ================================================================ campi
CAMPI_PAZIENTI = [
    ('ignora', '— non importare'), ('cognome_nome', 'Cognome e nome insieme'),
    ('cognome', 'Cognome'), ('nome', 'Nome'), ('telefono', 'Telefono / cellulare'),
    ('telefono2', 'Altro telefono'), ('email', 'Email'), ('codice_fiscale', 'Codice fiscale'),
    ('data_nascita', 'Data di nascita'), ('indirizzo', 'Indirizzo'), ('inviato_da', 'Inviato da'),
    ('note', 'Note'),
]
CAMPI_APPUNTAMENTI = [
    ('ignora', '— non importare'), ('data', 'Data'), ('ora', 'Ora'), ('ora_fine', 'Ora di fine'),
    ('durata', 'Durata in minuti'), ('stanza', 'Stanza / sala'), ('medico', 'Medico'),
    ('telefono_medico', 'Telefono del medico'), ('prestazione', 'Prestazione / intervento'),
    ('cognome_nome', 'Paziente: cognome e nome'), ('cognome', 'Paziente: cognome'),
    ('nome', 'Paziente: nome'), ('telefono', 'Paziente: telefono'), ('email', 'Paziente: email'),
    ('codice_fiscale', 'Paziente: codice fiscale'), ('data_nascita', 'Paziente: data di nascita'),
    ('indirizzo', 'Paziente: indirizzo'), ('convenzione', 'Convenzione / assicurazione'), ('importo', 'Importo'), ('tipo', 'Tipo di visita'),
    ('stato', 'Stato'), ('note', 'Note'), ('extra', 'Campo in più'),
]
# campi che possono comparire piu' volte: gli altri valgono per una colonna sola.
# L'indirizzo spesso e' diviso (via, CAP, citta'): le parti si mettono in fila
RIPETIBILI = {'ignora', 'extra', 'note', 'indirizzo'}

SINONIMI = {
    'cognome_nome': ['cognome e nome', 'nome e cognome', 'cognome nome', 'nome cognome', 'nominativo',
                     'paziente', 'pazienti', 'assistito', 'cliente', 'nominativo paziente'],
    'cognome': ['cognome', 'cognome paziente'],
    'nome': ['nome', 'nome paziente'],
    'telefono': ['telefono', 'tel', 'cellulare', 'cell', 'recapito', 'telefono cellulare', 'mobile',
                 'numero', 'n telefono', 'tel cell', 'recapito telefonico', 'telefono paziente', 'contatto'],
    'telefono2': ['telefono fisso', 'tel fisso', 'fisso', 'altro telefono', 'telefono 2', 'tel 2',
                  'telefono casa', 'secondo telefono'],
    'email': ['email', 'e mail', 'mail', 'posta elettronica', 'indirizzo email', 'e mail paziente',
              'indirizzo e mail', 'indirizzo mail', 'indirizzo di posta elettronica', 'indirizzo posta elettronica',
              'email paziente'],
    # "indirizzo email" resta all'email: il nome intero vale piu' della prima parola
    # non "via": una cella "Via Roma 1" sembrerebbe un'intestazione
    'indirizzo': ['indirizzo', 'residenza', 'domicilio', 'indirizzo di residenza', 'indirizzo residenza',
                  'indirizzo paziente', 'residente in', 'residente a', 'abitazione', 'cap', 'citta',
                  'citta di residenza', 'comune di residenza'],
    'codice_fiscale': ['codice fiscale', 'cf', 'c f', 'cod fiscale', 'cod fisc', 'p iva c f', 'c f p iva'],
    'data_nascita': ['data di nascita', 'data nascita', 'nato il', 'nata il', 'nascita', 'd n'],
    'inviato_da': ['inviato da', 'inviante', 'medico inviante', 'medico curante', 'provenienza'],
    'note': ['note', 'annotazioni', 'osservazioni', 'nota'],
    'data': ['data', 'data appuntamento', 'data visita', 'data intervento', 'giorno data'],
    'ora': ['ora', 'orario', 'ore', 'inizio', 'ora inizio', 'dalle', 'h'],
    'ora_fine': ['fine', 'ora fine', 'alle', 'termine', 'ora termine'],
    'durata': ['durata', 'minuti', 'durata minuti', 'durata min'],
    'stanza': ['stanza', 'sala', 'ambulatorio', 'studio', 'sala operatoria', 'locale'],
    'medico': ['medico', 'dottore', 'dott', 'dr', 'operatore', 'specialista', 'chirurgo', 'medico specialista'],
    'prestazione': ['prestazione', 'intervento', 'esame', 'visita', 'tipo esame', 'procedura',
                    'trattamento', 'servizio', 'prestazioni'],
    'convenzione': ['convenzione', 'assicurazione', 'assicurazione medico', 'ente', 'fondo',
                    'convenzione assicurazione'],
    'importo': ['importo', 'prezzo', 'costo', 'tariffa', 'euro', 'totale', 'onorario', 'importo euro'],
    'tipo': ['tipo', 'tipo visita', 'tipologia'],
    'stato': ['stato', 'esito'],
}

GIORNI_SETTIMANA = {'lunedi', 'martedi', 'mercoledi', 'giovedi', 'venerdi', 'sabato', 'domenica',
                    'lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom'}

# nomi propri comuni: servono a dividere "DE FITTIZI TERESA" in cognome e nome
NOMI_PROPRI = set("""
adele adriana agata agnese alba alberta alessandra alessia alice alma amalia ambra anastasia andrea
angela angelica angelina anita anna annalisa annamaria antonella antonia antonietta arianna assunta
aurora barbara beatrice benedetta bianca bruna camilla carla carlotta carmela carmen carolina
caterina cecilia chiara cinzia clara claudia concetta cristina daniela debora deborah denise diana
donatella dora elena eleonora elisa elisabetta elvira emanuela emilia emma enza erica erika ester
eva fabiana fabiola federica filomena fiorella flavia francesca gabriella gaia gemma gennara
giada gilda gina ginevra gioia giorgia giovanna gisella giulia giuliana giuseppina gloria grazia
graziella ida ilaria immacolata imma ines irene iolanda isabella jessica laura lea letizia lidia
lina linda lisa livia lorena loredana lucia luciana lucrezia luisa luna maddalena mafalda manuela
mara margherita maria mariana marianna marina marisa marta martina matilde melania melissa michela
milena miriam monica nadia nancy natalia nicoletta nina noemi nunzia olga ornella paola patrizia
pasqualina pia raffaella rebecca rita roberta romina rosa rosalba rosanna rosaria rossana sabrina
samanta samantha sara serena silvana silvia simona simonetta sofia sonia stefania susanna tania
tatiana teresa tiziana valentina valeria vanessa vera veronica viola virginia vittoria viviana
wanda yvonne luana raffaela tamara sharon noemi asia aurora giusy ketty rosy titti mena lella
alessandrina annunziata carmelina ciretta concettina filomena gelsomina immacolata lucia nunzia
pina ada agnese brunella doriana gianna ivana jole marilena mirella nella nicla ornella sabina
thais annarita mariarosaria mariagrazia mariacarmela mariateresa annachiara egle tommasina marika
carola lorenza vivian gerardina vincenza giusi mariapia rosamaria nunziatina
achille adriano agostino alberto alessandro alessio alfonso alfredo aldo amedeo andrea angelo
antonino antonio armando arturo attilio aurelio bartolomeo benedetto biagio bruno carlo carmine
ciro claudio corrado cosimo cristian cristiano damiano daniele dario davide diego domenico donato
edoardo elia emanuele emilio enrico enzo ernesto eugenio fabio fabrizio federico felice ferdinando
filippo flavio francesco franco gabriele gaetano gennaro giacomo giampaolo giancarlo gianluca
gianni gino giorgio giovanni girolamo giulio giuseppe gregorio guido ignazio lorenzo luca luciano
luigi manuel marcello marco mariano mario martino massimo matteo mattia maurizio michele mirko
nicola nicolo oreste orazio pasquale paolo patrizio pellegrino piero pierluigi pietro raffaele
renato riccardo rino roberto rocco rodolfo romano rosario ruggero salvatore samuele sandro sergio
silvio simone stefano teodoro tommaso ugo umberto valerio vincenzo vito vittorio
fulvio oscar fedele massimiliano michelangelo gianfranco pierpaolo luigino
""".split())
PARTICELLE = {'de', 'di', 'da', 'del', 'della', 'dello', 'degli', 'dei', 'la', 'lo', 'le', 'li', 'dal',
              'dalla', 'd', 'mc', 'van', 'von'}


def norma(testo):
    """Per confrontare intestazioni: minuscolo, senza accenti, la
    punteggiatura diventa spazio. 'Cod. Fiscale' -> 'cod fiscale'."""
    t = unicodedata.normalize('NFKD', str(testo or ''))
    t = ''.join(c for c in t if not unicodedata.combining(c)).lower()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', t).split())


def punteggio_intestazione(intestazione):
    """{campo: punteggio} dal solo nome della colonna."""
    n = norma(intestazione)
    uscita = {}
    if not n:
        return uscita
    parole = n.split()
    for campo, sinonimi in SINONIMI.items():
        migliore = 0
        for sin in sinonimi:
            if n == sin:
                migliore = max(migliore, 10)
            elif n.startswith(sin + ' '):
                migliore = max(migliore, 7)
            else:
                sp = sin.split()
                for i in range(len(parole) - len(sp) + 1):
                    if parole[i:i + len(sp)] == sp:
                        migliore = max(migliore, 5)
        if migliore:
            uscita[campo] = migliore
    return uscita


# ============================================================ lettura file
def leggi_file(dati, nome):
    """[{'nome': nome del foglio, 'righe': [[valore, ...], ...]}]. Le celle
    unite prendono tutte il valore della cella in alto a sinistra."""
    nome = nome or ''
    estensione = os.path.splitext(nome)[1].lower()
    if estensione in ('.csv', '.txt'):
        righe, oltre = _leggi_csv(dati)
        return [{'nome': os.path.splitext(os.path.basename(nome))[0] or 'CSV', 'righe': righe,
                 'file': os.path.basename(nome), 'oltre': oltre}]
    if estensione == '.xls':
        raise ValueError('Il formato .xls del vecchio Excel non si legge: aprirlo in Excel e salvarlo come '
                         '"Cartella di lavoro di Excel (.xlsx)".')
    if not dati.startswith(b'PK'):
        raise ValueError('Il file non è un Excel .xlsx né un CSV.')
    from openpyxl import load_workbook
    try:
        wb = load_workbook(io.BytesIO(dati), data_only=True)
    except Exception as e:
        raise ValueError('Il file Excel non si apre: %s' % e)
    fogli = []
    for ws in wb.worksheets:
        max_r = min(ws.max_row or 0, MASSIMO_RIGHE + 30)
        max_c = min(ws.max_column or 0, MASSIMO_COLONNE)
        righe = [[None] * max_c for _ in range(max_r)]
        for r_i, riga in enumerate(ws.iter_rows(min_row=1, max_row=max_r, max_col=max_c, values_only=True)):
            for c_i, v in enumerate(riga):
                righe[r_i][c_i] = v
        for m in ws.merged_cells.ranges:
            v = ws.cell(m.min_row, m.min_col).value
            for r in range(m.min_row, min(m.max_row, max_r) + 1):
                for c in range(m.min_col, min(m.max_col, max_c) + 1):
                    righe[r - 1][c - 1] = v
        while righe and all(v in (None, '') for v in righe[-1]):
            righe.pop()
        # le righe oltre il massimo non si leggono, ma si contano per dirlo. Solo
        # quelle scritte: max_row conta anche le righe vuote con un formato
        oltre = 0
        if (ws.max_row or 0) > max_r:
            for riga in ws.iter_rows(min_row=max_r + 1, max_col=max_c or None, values_only=True):
                if any(not vuoto(v) for v in riga):
                    oltre += 1
        fogli.append({'nome': ws.title, 'righe': righe, 'file': os.path.basename(nome), 'oltre': oltre})
    # il planning esportato dal gestionale ha la data nel nome del primo foglio
    data_libro = next((d for d in (data_dal_nome(f['nome']) for f in fogli) if d), None)
    for f in fogli:
        f['data_libro'] = data_libro
    return fogli


def _leggi_csv(dati):
    """(righe, oltre): le righe della tabella e quante righe scritte restano
    fuori perche' oltre il massimo che si legge."""
    # Excel "Testo Unicode (.txt)" scrive UTF-16 con il BOM e le tabulazioni;
    # "CSV UTF-8" ha il suo BOM; il CSV di sempre e' Windows-1252
    codifiche = ('utf-8-sig', 'cp1252', 'latin-1')
    if dati.startswith((b'\xff\xfe', b'\xfe\xff')):
        codifiche = ('utf-16',) + codifiche
    for codifica in codifiche:
        try:
            testo = dati.decode(codifica)
            break
        except UnicodeDecodeError:
            continue
    testo = testo.replace('\x00', '')
    campione = testo[:5000]
    try:
        dialetto = csv.Sniffer().sniff(campione, delimiters=';,\t')
        separatore = dialetto.delimiter
    except csv.Error:
        separatore = ';' if campione.count(';') >= campione.count(',') else ','
    righe, oltre = [], 0
    # newline='': gli a capo li riconosce il modulo csv, anche quelli del Mac (\r)
    try:
        for riga in csv.reader(io.StringIO(testo, newline=''), delimiter=separatore):
            if len(righe) >= MASSIMO_RIGHE + 30:
                # oltre il massimo non si tiene niente, ma le righe scritte si
                # contano: l'anteprima deve dire che non vengono lette
                if any(x.strip() for x in riga):
                    oltre += 1
                continue
            righe.append([x if x.strip() != '' else None for x in riga][:MASSIMO_COLONNE])
    except csv.Error as e:
        raise ValueError('Il file di testo non si legge come tabella (%s): salvarlo da Excel come '
                         '"CSV (delimitato dal separatore di elenco)".' % e)
    larghezza = max((len(r) for r in righe), default=0)
    return [r + [None] * (larghezza - len(r)) for r in righe], oltre


# ============================================================ valori
def vuoto(v):
    return v is None or (isinstance(v, str) and not v.strip())


def come_data(v):
    """date o None. Accetta date e datetime di Excel, '24/09/2026',
    '24/9/26', '2026-09-24', '24-09-2026', '24.09.2026'."""
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return None                  # un numero in una colonna data: meglio non indovinare
    t = str(v or '').strip()
    m = re.fullmatch(r'(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T].*)?', t)
    if m:
        a, me, g = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.fullmatch(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2}|\d{4})(?: .*)?', t)
        if not m:
            return None
        g, me, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if a < 100:
            a += 2000 if a < 70 else 1900
    try:
        d = date(a, me, g)
    except ValueError:
        return None
    return d if date(1900, 1, 1) <= d <= date(2100, 12, 31) else None


ANNO_DUE_CIFRE = re.compile(r'\s*\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2}(?: .*)?\s*')


def come_nascita(v, avvisi):
    """La data di nascita. Con l'anno a due cifre ("12/03/65") il secolo non
    c'e', e come_data (fatta per gli appuntamenti) darebbe il 2065: qui, come
    per il codice fiscale, vale la data piu' recente che non sia nel futuro
    (65 -> 1965, 24 -> 2024). Dal 2000 in poi un bambino e una persona nata
    cento anni prima non si distinguono: la riga si segnala da controllare."""
    d = come_data(v)
    if d is None or not (isinstance(v, str) and ANNO_DUE_CIFRE.fullmatch(v)):
        return d
    oggi = date.today()
    for secolo in (2000, 1900):
        try:
            scelta = d.replace(year=secolo + d.year % 100)
        except ValueError:                  # il 29 febbraio di un anno che non lo ha
            continue
        if scelta <= oggi:
            if secolo == 2000:
                avvisi.append('data di nascita con l\'anno a due cifre: letta come %s, controllarla'
                              % scelta.strftime('%d/%m/%Y'))
            return scelta
    return None


def come_ora(v):
    """time o None. Accetta orari di Excel, frazioni di giorno, '9:30',
    '09.30', '9', '9,30', e i numeri: in Excel chi scrive 9,30 in una cella
    normale salva il numero 9.3, che e' 9:30 (come 9.45 e' 9:45)."""
    if isinstance(v, time):
        return v.replace(second=0, microsecond=0)
    if isinstance(v, datetime):
        return v.time().replace(second=0, microsecond=0)
    if isinstance(v, float) and 0 <= v < 1:
        minuti = int(round(v * 24 * 60))
        return time(minuti // 60 % 24, minuti % 60)
    if isinstance(v, float) and 1 <= v < 24:
        # 9.0 -> 9:00, 9.3 -> 9:30, 9.45 -> 9:45: le cifre dopo la virgola sono i
        # minuti. Con piu' di due cifre (9.333) non e' un orario scritto a mano
        centesimi = v * 100
        if abs(centesimi - round(centesimi)) > 1e-6:
            return None
        h = int(v)
        mi = int(round(centesimi)) - h * 100
        return time(h, mi) if 0 <= mi <= 59 else None
    t = str(v if v is not None else '').strip().lower().replace('ore', '').strip()
    # "9,3" e' il 9,30 di una cella numerica salvata in un CSV: una cifra sola
    # dopo la virgola o il punto sono le decine dei minuti
    m = re.fullmatch(r'(\d{1,2})(?:[:.,h](\d{2})|[.,](\d))?', t)
    if not m:
        return None
    h = int(m.group(1))
    mi = int(m.group(2) or 0) if m.group(3) is None else int(m.group(3)) * 10
    if h > 23 or mi > 59:
        return None
    return time(h, mi)


def come_minuti(v):
    """La durata in minuti o None se non si legge. 45 e '45' sono minuti; una
    cella di Excel con l'orario (0:45, 1:30) o con la durata ([h]:mm) e il
    testo '1:30' sono ore e minuti. 'INF', 'nan', '1e999' non sono durate."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, datetime):
        return None                      # una data non e' una durata
    if isinstance(v, time):
        return v.hour * 60 + v.minute
    if isinstance(v, timedelta):
        return int(v.total_seconds() // 60)
    if isinstance(v, (int, float)):
        numero = float(v)
    else:
        t = str(v).strip()
        m = re.fullmatch(r'(\d{1,2})\s*[:h]\s*(\d{2})', t, re.I)
        if m:
            return int(m.group(1)) * 60 + int(m.group(2)) if int(m.group(2)) < 60 else None
        try:
            numero = float(t.replace(',', '.'))
        except ValueError:
            return None
    # "inf" e "nan" sono numeri per Python, ma non durate (e int() si fermerebbe)
    if not math.isfinite(numero):
        return None
    return int(numero)


def come_telefono(v):
    """Il numero come testo, con le sole cifre (e il + iniziale). Excel
    salva i numeri come interi: 3331234567 e non '3331234567'."""
    if isinstance(v, bool) or v is None:
        return ''
    if isinstance(v, (int, float)):
        return str(int(v)) if v == int(v) else ''
    t = str(v).strip()
    gruppi = re.findall(r'\+?\d[\d\s./\-]{4,}\d', t)
    if not gruppi:
        return ''
    numero = gruppi[0]
    piu = numero.startswith('+')
    return ('+' if piu else '') + re.sub(r'\D', '', numero)


def e_telefono(v):
    c = come_telefono(v)
    return 6 <= len(re.sub(r'\D', '', c)) <= 15 and not isinstance(v, float)


def come_importo(v):
    """Centesimi o None. ValueError se c'e' qualcosa ma non e' un importo, o se
    supera quello che il modulo di prenotazione accetta."""
    if vuoto(v):
        return None
    if isinstance(v, bool):
        raise ValueError(v)
    if isinstance(v, (int, float)):
        if v < 0 or v > MASSIMO_IMPORTO:
            raise ValueError(v)
        return int(round(v * 100))
    t = str(v).replace('€', '').replace('eur', '').replace('EUR', '').replace(' ', '').strip()
    if ',' in t:
        t = t.replace('.', '').replace(',', '.')
    elif re.fullmatch(r'\d{1,3}(\.\d{3})+', t):
        t = t.replace('.', '')
    if not re.fullmatch(r'\d+(\.\d{1,2})?', t):
        raise ValueError(v)
    valore = float(t)
    if valore > MASSIMO_IMPORTO:
        raise ValueError(v)
    return int(round(valore * 100))


def testo_di(v):
    if vuoto(v):
        return ''
    # math.isfinite: int() di un numero infinito si fermerebbe con un errore
    if isinstance(v, float) and math.isfinite(v) and v == int(v):
        v = int(v)
    if isinstance(v, datetime):
        return v.strftime('%d/%m/%Y %H:%M') if v.time() != time(0, 0) else v.strftime('%d/%m/%Y')
    if isinstance(v, date):
        return v.strftime('%d/%m/%Y')
    if isinstance(v, time):
        return v.strftime('%H:%M')
    return ' '.join(str(v).split())


def iniziali_maiuscole(testo):
    """'DE FITTIZI TERESA' -> 'De Fittizi Teresa', "D'ARCO" -> "D'Arco". Un
    testo gia' scritto con le maiuscole giuste resta com'e'."""
    if not testo or not testo.isupper():
        return testo
    return re.sub(r"[A-Za-zÀ-ÿ]+", lambda m: m.group(0).capitalize(), testo.lower())


def e_nome_proprio(parola):
    n = norma(parola)
    if n.replace(' ', '') in NOMI_PROPRI:
        return True
    # "M.ROSARIA", "A. MARIA": un'iniziale puntata e poi un nome (non "D'ANDREA")
    m = re.fullmatch(r"[^\W\d_]\.\s?([^\W\d_]+)", parola.strip())
    return bool(m) and norma(m.group(1)) in NOMI_PROPRI


APOSTROFO = re.compile(r"^(d|dell|dall|l|de|dei|degl)['’]\w", re.I)


def dividi_nome(testo):
    """(cognome, nome, sicuro). Nelle agende il cognome viene di solito
    prima: 'ROSSI MARTA'. Si usano i nomi propri noti per capire dove sta il
    nome; le particelle (DE, DI, DELLA...) restano col cognome. Se non si
    capisce, l'ultima parola e' il nome e la riga va controllata."""
    parole = testo.split()
    if not parole:
        return '', '', True
    if len(parole) == 1:
        return parole[0], '', True
    # "DI NARDO", "DE LUCA": solo il cognome, con la sua particella
    if len(parole) == 2 and norma(parole[0]) in PARTICELLE and not e_nome_proprio(parole[1]):
        return ' '.join(parole), '', True
    # nome in fondo: 'DE FITTIZI TERESA', 'SERRA MARIA ELENA'
    for k in (2, 1):
        coda, testa = parole[-k:], parole[:-k]
        # la testa e' un cognome se ha una particella (DE LUCA) o una parola
        # che non e' un nome; se sono tutti nomi (MARIA ROSA) non si sa
        if testa and all(e_nome_proprio(p) for p in coda) and not all(
                e_nome_proprio(p) and norma(p) not in PARTICELLE for p in testa) \
                and norma(testa[-1]) not in PARTICELLE:
            return ' '.join(testa), ' '.join(coda), True
    # nome all'inizio: 'ANNA VITALE'
    for k in (2, 1):
        testa, coda = parole[:k], parole[k:]
        if coda and all(e_nome_proprio(p) for p in testa) and not e_nome_proprio(coda[0]) \
                and norma(testa[-1]) not in PARTICELLE:
            return ' '.join(coda), ' '.join(testa), True
    # "ANTONYO D'ANDREA": il cognome con l'apostrofo e' in fondo (nome scritto male davanti)
    if len(parole) == 2 and APOSTROFO.match(parole[1]) and not APOSTROFO.match(parole[0]):
        return parole[1], parole[0], False
    # due parole sconosciute, una che finisce per vocale come i cognomi italiani e una
    # no, come molti nomi stranieri: "JENNYFER SERAFINI" -> Serafini Jennyfer. Resta un dubbio
    if len(parole) == 2 and not any(e_nome_proprio(p) for p in parole):
        vocale = [norma(p)[-1:] in 'aeiou' for p in parole]
        if vocale == [False, True]:
            return parole[1], parole[0], False
    # due nomi propri ('MARIA ROSA'): prima il cognome, per convenzione, ma e' un dubbio
    return ' '.join(parole[:-1]), parole[-1], False


# =============================================================== analisi
def descrivi_colonna(valori):
    """Frazioni del campione non vuoto che sembrano di ciascun tipo."""
    pieni = [v for v in valori if not vuoto(v)]
    n = len(pieni)
    if not n:
        return {'pieni': 0}
    oggi = date.today()
    date_ = [come_data(v) for v in pieni]
    date_ok = [d for d in date_ if d]
    anni = sorted(d.year for d in date_ok)
    testi = [str(v).strip() for v in pieni if isinstance(v, str)]
    parole_nome = [t for t in testi if re.fullmatch(r"[A-Za-zÀ-ÿ'’ .]+", t) and not norma(t) in GIORNI_SETTIMANA]
    distinti = len({testo_di(v).lower() for v in pieni})
    return {
        'pieni': n,
        'data': len(date_ok) / n,
        'anno_mediano': anni[len(anni) // 2] if anni else None,
        'ora': sum(1 for v in pieni if isinstance(v, (time, datetime)) and not come_data(v) or
                   (not isinstance(v, (date, datetime)) and come_ora(v) is not None and
                    not (isinstance(v, int) and v > 23) and not e_telefono(v))) / n,
        'telefono': sum(1 for v in pieni if e_telefono(v)) / n,
        'email': sum(1 for v in pieni if isinstance(v, str) and pazienti.email_valida(v.strip())) / n,
        'cf': sum(1 for v in pieni if isinstance(v, str) and pazienti.codice_fiscale_valido(v.strip().replace(' ', ''))) / n,
        'numero': sum(1 for v in pieni if isinstance(v, (int, float)) and not isinstance(v, bool) and
                      not e_telefono(v) and 0 <= v < 100000) / n,
        'giorno_settimana': sum(1 for t in testi if norma(t) in GIORNI_SETTIMANA) / n,
        'nome2': sum(1 for t in parole_nome if len(t.split()) >= 2) / n,
        'nome1': sum(1 for t in parole_nome if len(t.split()) == 1) / n,
        'distinti': distinti,
        'recente': bool(anni) and anni[len(anni) // 2] >= oggi.year - 3,
    }


def punteggi(intestazione, d, tipo):
    """{campo: punteggio} per una colonna, da nome e contenuto insieme. Un
    campo che vuole un certo contenuto (date, telefoni...) non si assegna a
    una colonna che non lo contiene, qualunque sia il nome."""
    da_nome = punteggio_intestazione(intestazione)
    pieni = d.get('pieni', 0)
    p = {}

    def serve(campo, frazione, soglia=0.5, peso=9):
        if pieni == 0:
            p[campo] = da_nome.get(campo, 0) * 0.5
        elif frazione >= soglia:
            p[campo] = da_nome.get(campo, 0) + peso * frazione

    if d.get('giorno_settimana', 0) >= 0.7:
        return {'ignora': 20}
    campi = dict(CAMPI_APPUNTAMENTI if tipo == 'appuntamenti' else CAMPI_PAZIENTI)
    for campo in campi:
        if campo in ('ignora', 'extra'):
            continue
        if campo in ('data', 'data_nascita'):
            vecchio = d.get('anno_mediano') and d['anno_mediano'] < date.today().year - 5
            if campo == 'data' and not vecchio:
                serve(campo, d.get('data', 0), peso=10)
            elif campo == 'data_nascita' and (vecchio or da_nome.get('data_nascita')):
                serve(campo, d.get('data', 0), peso=10)
        elif campo in ('ora', 'ora_fine'):
            serve(campo, d.get('ora', 0), peso=9 if campo == 'ora' else 1)
        elif campo in ('telefono', 'telefono2', 'telefono_medico'):
            if campo == 'telefono_medico':
                continue                           # si decide dopo, dal legame con il medico
            serve(campo, d.get('telefono', 0), peso=8 if campo == 'telefono' else 2)
        elif campo == 'email':
            serve(campo, d.get('email', 0), peso=10)
        elif campo == 'codice_fiscale':
            serve(campo, d.get('cf', 0), peso=10)
        elif campo in ('importo', 'durata'):
            serve(campo, d.get('numero', 0) + (1 if pieni and d.get('numero', 0) == 0 and da_nome.get(campo) else 0),
                  soglia=0.6, peso=3)
        elif campo == 'cognome_nome':
            if d.get('data', 0) < 0.3 and d.get('telefono', 0) < 0.3:
                p[campo] = da_nome.get(campo, 0) + 4 * d.get('nome2', 0) + 1 * d.get('nome1', 0)
        elif campo in ('cognome', 'nome'):
            if d.get('data', 0) < 0.3 and d.get('telefono', 0) < 0.3:
                p[campo] = da_nome.get(campo, 0) + 2 * d.get('nome1', 0)
        else:
            if d.get('data', 0) < 0.5 and d.get('telefono', 0) < 0.5 and d.get('ora', 0) < 0.5:
                p[campo] = da_nome.get(campo, 0)
    return {k: v for k, v in p.items() if v > 0}


def trova_intestazioni(righe):
    """L'indice della riga con i nomi delle colonne, fra le prime 20."""
    migliore, indice = -1, 0
    for i, r in enumerate(righe[:20]):
        # distinti: una cella unita riempita su otto colonne e' un testo solo
        testi = list(dict.fromkeys(norma(v) for v in r if isinstance(v, str) and norma(v)))
        if len(testi) < 2:
            continue
        riconosciute = sum(1 for t in testi if max(punteggio_intestazione(t).values(), default=0) >= 5)
        sotto = sum(1 for rr in righe[i + 1:i + 8] if sum(1 for v in rr if not vuoto(v)) >= 2)
        # anche senza nomi riconosciuti (Colonna1, Colonna2...) una riga di testi
        # con i dati sotto e' la riga delle intestazioni
        punti = riconosciute * 3 + len(testi) * 0.5 + sotto * 0.5
        # "STANZA 1, STANZA 2, STANZA 3": etichette dei blocchi, non nomi di colonne
        prime = {x.split()[0] for x in testi}
        if len(testi) >= 2 and len(prime) == 1 and all(len(x.split()) == 2 for x in testi):
            punti *= 0.3
        if punti > migliore:
            migliore, indice = punti, i
    return indice


def trova_gruppi(intestazioni, righe, h):
    """Blocchi affiancati con le stesse colonne (SALA A | SALA B). Restituisce
    (comuni, gruppi): comuni = colonne prima del primo blocco (giorno, ora),
    gruppi = [{'nome': 'SALA A', 'colonne': [...]}]."""
    n = [norma(x) for x in intestazioni]
    sotto = [r for r in righe[h + 1:h + 401] if any(not vuoto(v) for v in r)]

    def senza_nome_con_dati(j):
        # una colonna senza intestazione ma piena (le date accanto a GIORNO, senza
        # cella unita) conta; un separatore vuoto no, e in un foglio lungo
        # nemmeno una cella sparsa
        piene = sum(1 for r in sotto if j < len(r) and not vuoto(r[j]))
        return piene >= max(1, len(sotto) // 10)
    tutte = [i for i, x in enumerate(n) if x or senza_nome_con_dati(i)]
    for i, x in enumerate(n):
        if not x:
            continue
        posizioni = [j for j, y in enumerate(n) if y == x]
        if len(posizioni) < 2 or posizioni[0] != i:
            continue
        passo = posizioni[1] - posizioni[0]
        if passo < 2:
            continue
        def blocco(p):
            # le colonne vuote in fondo (separatori fra le sale) non contano
            b = n[p:p + passo]
            while b and not b[-1]:
                b.pop()
            return b
        schema = blocco(i)

        def quasi_uguale(b):
            # una sala puo' avere una colonna diversa dall'altra (RECAPITO PZ al
            # posto di ASSICURAZIONE MEDICO): conta che il grosso coincida
            if len(b) != len(schema):
                return False
            diverse = sum(1 for x, y in zip(b, schema) if x != y)
            return diverse <= max(1, len(schema) // 4)
        buoni = [p for p in posizioni if quasi_uguale(blocco(p))]
        # tutti i blocchi devono essere uguali e in fila
        if len(buoni) < 2 or any(b - a != passo for a, b in zip(buoni, buoni[1:])):
            continue
        comuni = [j for j in tutte if j < i]
        gruppi = []
        for k, inizio in enumerate(buoni):
            colonne = [j for j in range(inizio, min(inizio + passo, len(n))) if n[j]]
            nome = ''
            for r in range(h - 1, max(-1, h - 4), -1):
                nome = next((str(righe[r][j]).strip() for j in range(inizio, min(inizio + passo, len(n)))
                             if j < len(righe[r]) and isinstance(righe[r][j], str) and righe[r][j].strip()), '')
                if nome:
                    break
            gruppi.append({'nome': nome or 'Blocco %d' % (k + 1), 'colonne': colonne, 'inizio': inizio,
                           'fine': inizio + passo})
        return comuni, gruppi
    # una tabellina a parte, oltre una colonna vuota (RIEPILOGO STATO con i conteggi):
    # poche righe piene contro le molte della tabella, non sono colonne dei dati
    for s in range(1, len(n)):
        if s in tutte:
            continue
        sinistra, destra = [j for j in tutte if j < s], [j for j in tutte if j > s]
        if not sinistra or not destra:
            continue
        piene_s = sum(1 for r in sotto if any(j < len(r) and not vuoto(r[j]) for j in sinistra))
        piene_d = sum(1 for r in sotto if any(j < len(r) and not vuoto(r[j]) for j in destra))
        if piene_s >= 5 and piene_d <= max(2, piene_s * 0.2):
            tutte = sinistra
            break
    return [], [{'nome': '', 'colonne': tutte, 'inizio': 0, 'fine': len(n)}]


def colonna_di(pos, j, gruppo):
    """L'indice della colonna di una posizione per un blocco. 'c3': colonna comune;
    'g2': terza colonna di ogni blocco; 'g2b1': terza colonna del solo secondo
    blocco, quando i blocchi hanno li' intestazioni diverse (None negli altri)."""
    if pos.startswith('c'):
        return j
    if 'b' in pos:
        return j if gruppo['inizio'] <= j < gruppo.get('fine', j + 1) else None
    return gruppo['inizio'] + int(pos[1:])


def data_dal_nome(nome):
    t = (nome or '').strip()
    m = re.fullmatch(r'(\d{1,2})[\-./ ](\d{1,2})[\-./ ](\d{4})', t)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def data_nel_titolo(righe_sopra):
    """La data scritta sopra la tabella ("Data: 25/09/2026", "Venerdì 25 Settembre
    2026"), per i fogli di un giorno solo. Se ce n'e' piu' d'una diversa, niente."""
    trovate = set()
    for r in righe_sopra:
        for v in r:
            if isinstance(v, datetime) or isinstance(v, date):
                trovate.add(v.date() if isinstance(v, datetime) else v)
            elif isinstance(v, str):
                for m in re.finditer(r'\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b', v):
                    try:
                        trovate.add(date(int(m.group(3)), int(m.group(2)), int(m.group(1))))
                    except ValueError:
                        pass
                for m in re.finditer(r'\b(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})\b', v):
                    mese = norma(m.group(2))
                    if mese in servizi.MESI:
                        try:
                            trovate.add(date(int(m.group(3)), servizi.MESI.index(mese) + 1, int(m.group(1))))
                        except ValueError:
                            pass
    return trovate.pop() if len(trovate) == 1 else None


def analizza(foglio, tipo=None, mappa=None):
    """Riconosce intestazioni, blocchi e campi di un foglio.

    mappa: {posizione: campo} scelta a mano nell'anteprima; la posizione e'
    'c<indice>' per le colonne comuni e 'g<indice nel blocco>' per quelle dei
    blocchi, che valgono per tutti i blocchi."""
    righe = foglio['righe']
    if not righe:
        raise ValueError('Il foglio è vuoto.')
    h = trova_intestazioni(righe)
    larghezza = max(len(r) for r in righe)
    intestazioni = [(righe[h][j] if j < len(righe[h]) else None) for j in range(larghezza)]
    intestazioni = [testo_di(x) for x in intestazioni]
    comuni, gruppi = trova_gruppi(intestazioni, righe, h)
    dati = righe[h + 1:]
    campione = dati[:400]

    def valori_colonna(j):
        return [r[j] if j < len(r) else None for r in campione]

    primo = gruppi[0]
    posizioni = [('c%d' % j, j) for j in comuni]
    for j in primo['colonne']:
        k = j - primo['inizio']
        nomi = {norma(intestazioni[g['inizio'] + k]) if g['inizio'] + k < len(intestazioni) else '' for g in gruppi}
        if len(nomi) == 1:
            posizioni.append(('g%d' % k, j))
        else:
            # intestazione diversa fra i blocchi: una posizione per blocco
            posizioni += [('g%db%d' % (k, b), g['inizio'] + k) for b, g in enumerate(gruppi)
                          if g['inizio'] + k < len(intestazioni) and intestazioni[g['inizio'] + k]]
    descrizioni = {}
    for pos, j in posizioni:
        if pos.startswith('g') and 'b' not in pos and len(gruppi) > 1:
            valori = []
            for g in gruppi:
                valori += valori_colonna(colonna_di(pos, j, g))
        else:
            valori = valori_colonna(j)
        descrizioni[pos] = descrivi_colonna(valori)

    if tipo not in ('pazienti', 'appuntamenti'):
        tipo = indovina_tipo(intestazioni, descrizioni, posizioni)
    elenco_campi = CAMPI_APPUNTAMENTI if tipo == 'appuntamenti' else CAMPI_PAZIENTI
    ammessi = {c for c, _ in elenco_campi}

    candidati = []
    for pos, j in posizioni:
        for campo, punti in punteggi(intestazioni[j], descrizioni[pos], tipo).items():
            if campo in ammessi:
                candidati.append((punti, pos, campo))
    candidati.sort(key=lambda x: (-x[0], x[1]))
    assegnati, presi = {}, set()
    for punti, pos, campo in candidati:
        if pos in assegnati or (campo not in RIPETIBILI and campo in presi):
            continue
        if punti < 3:
            continue
        assegnati[pos] = campo
        presi.add(campo)
    for pos, j in posizioni:
        if pos not in assegnati:
            d = descrizioni[pos]
            # una seconda colonna di telefoni ("Tel." e "Cell") diventa l'altro telefono
            if d.get('telefono', 0) >= 0.5 and 'telefono' in presi and 'telefono2' in ammessi \
                    and 'telefono2' not in presi:
                assegnati[pos] = 'telefono2'
                presi.add('telefono2')
                continue
            assegnati[pos] = 'extra' if (tipo == 'appuntamenti' and intestazioni[j] and d.get('pieni')) else 'ignora'

    # una colonna di telefoni che segue il medico (stesso numero per lo stesso
    # medico, meno numeri che pazienti) e' il telefono del medico
    note_analisi = []
    pos_tel = next((p for p, c in assegnati.items() if c == 'telefono'), None)
    pos_med = next((p for p, c in assegnati.items() if c == 'medico'), None)
    pos_paz = next((p for p, c in assegnati.items() if c in ('cognome_nome', 'cognome')), None)
    if tipo == 'appuntamenti' and pos_tel and pos_med and telefono_del_medico(
            dati, gruppi, comuni, posizioni, pos_tel, pos_med, pos_paz):
        assegnati[pos_tel] = 'telefono_medico'
        note_analisi.append('La colonna "%s" ha sempre lo stesso numero per lo stesso medico: è il '
                            'telefono del medico, non del paziente.' % intestazioni[dict(posizioni)[pos_tel]])

    # TELEFONO accanto all'OPERATORE e, piu' avanti, RECAPITO PZ: il primo e' del medico
    # anche quando i numeri sono troppo pochi per capirlo dal contenuto
    pos_tel = next((p for p, c in assegnati.items() if c == 'telefono'), None)
    if tipo == 'appuntamenti' and pos_tel and pos_med:
        def del_paziente(p):
            n = norma(intestazioni[dict(posizioni)[p]])
            return bool(re.search(r'\b(pz|paz|paziente|pazienti|assistito)\b', n)) and \
                bool(re.search(r'\b(tel|telefono|cell|cellulare|recapito|numero)\b', n))
        altro = next((p for p, _ in posizioni if p != pos_tel and del_paziente(p) and
                      descrizioni[p].get('telefono', 0) >= 0.5), None)
        if altro and not del_paziente(pos_tel):
            assegnati[pos_tel] = 'telefono_medico'
            assegnati[altro] = 'telefono'
            note_analisi.append('La colonna "%s" è il telefono del medico: quello dei pazienti è "%s".' % (
                intestazioni[dict(posizioni)[pos_tel]], intestazioni[dict(posizioni)[altro]]))

    # il telefono diventato del medico lascia libero il posto: l'altra colonna di
    # telefoni (RECAPITO PZ, il secondo telefono) e' quella dei pazienti
    if 'telefono' not in assegnati.values() and tipo == 'appuntamenti' or \
            'telefono' not in assegnati.values() and 'telefono2' in assegnati.values():
        altre = [p for p, _ in posizioni if assegnati.get(p) in ('telefono2', 'extra', 'ignora')
                 and descrizioni[p].get('telefono', 0) >= 0.5]
        altre.sort(key=lambda p: assegnati[p] != 'telefono2')
        if altre:
            assegnati[altre[0]] = 'telefono'

    # le scelte fatte a mano vincono
    if mappa:
        for pos, campo in mappa.items():
            if pos in assegnati and campo in ammessi:
                assegnati[pos] = campo
    return {
        'riga_intestazioni': h, 'intestazioni': intestazioni, 'comuni': comuni, 'gruppi': gruppi,
        'posizioni': posizioni, 'campi': assegnati, 'descrizioni': descrizioni, 'tipo': tipo,
        'dati': dati, 'note': note_analisi, 'nome_foglio': foglio['nome'],
        'data_foglio': data_dal_nome(foglio['nome']) or data_nel_titolo(righe[:h]) or foglio.get('data_libro'),
        # nome del file, del foglio e titoli sopra le intestazioni: "AGENDA - DOTT.SSA LIPPIELLO"
        'titolo': ' | '.join([foglio.get('file') or '', foglio['nome']] + [
            testo_di(v) for r in righe[:h] for v in r if isinstance(v, str)]),
        'firma': hashlib.sha1(json.dumps([tipo, [norma(x) for x in intestazioni]]).encode()).hexdigest()[:16],
    }


def indovina_tipo(intestazioni, descrizioni, posizioni):
    orari = any(d.get('ora', 0) >= 0.6 for d in descrizioni.values())
    da_nome = set()
    for _, j in posizioni:
        da_nome |= {c for c, v in punteggio_intestazione(intestazioni[j]).items() if v >= 5}
    if orari or ({'data'} & da_nome and {'medico', 'prestazione', 'stanza', 'ora'} & da_nome):
        return 'appuntamenti'
    return 'pazienti'


def telefono_del_medico(dati, gruppi, comuni, posizioni, pos_tel, pos_med, pos_paz=None):
    """La colonna dei telefoni segue il medico e non il paziente: ogni medico
    ha un numero solo, e lo stesso numero compare accanto a pazienti diversi.
    Il telefono di un paziente condiviso da piu' pazienti e' un'eccezione
    (una famiglia); qui e' la regola."""
    per_medico, per_numero, righe_viste = {}, {}, 0
    for n, r in enumerate(dati[:3000]):
        for g in gruppi:
            def valore(pos):
                if pos is None:
                    return None
                j = colonna_di(pos, dict(posizioni)[pos], g)
                return r[j] if j is not None and j < len(r) else None
            tel, med = come_telefono(valore(pos_tel)), testo_di(valore(pos_med)).lower()
            if tel and med:
                chi = testo_di(valore(pos_paz)).lower() or ('riga-%d-%d' % (n, g['inizio']))
                per_medico.setdefault(med, set()).add(tel)
                per_numero.setdefault(tel, set()).add(chi)
                righe_viste += 1
    if len(per_medico) < 2 or righe_viste < 4:
        return False
    uno_per_medico = sum(1 for v in per_medico.values() if len(v) == 1) / len(per_medico)
    condivisi = sum(len(chi) for chi in per_numero.values() if len(chi) >= 2) / righe_viste
    return uno_per_medico >= 0.8 and condivisi >= 0.4


# ============================================================ preparazione
class IndicePazienti:
    """I pazienti gia' presenti, indicizzati per trovarli in fretta mentre si
    importano migliaia di righe; quelli creati dall'importazione si
    aggiungono man mano, cosi' due righe della stessa persona fanno una
    scheda sola."""

    def __init__(self, s):
        self.per_cf, self.per_nome, self.per_tel = {}, {}, {}
        for p in s.scalars(select(Paziente)):
            self.aggiungi(p)

    def aggiungi(self, p):
        """Si puo' chiamare di nuovo per la stessa scheda, quando si completa: non
        compare due volte (sembrerebbero due schede con lo stesso nome)."""
        def metti(lista):
            if not any(x is p for x in lista):
                lista.append(p)
        if p.codice_fiscale:
            self.per_cf[p.codice_fiscale.upper()] = p
        metti(self.per_nome.setdefault(pazienti.semplifica(p.cognome) + '|' + pazienti.semplifica(p.nome), []))
        for t in (p.telefono, p.telefono2):
            if t:
                metti(self.per_tel.setdefault(pazienti.telefono_confronto(t), []))

    def trova(self, cognome, nome, telefono, cf):
        """(paziente o None, avviso)"""
        if cf and cf.upper() in self.per_cf:
            return self.per_cf[cf.upper()], ''
        tel = pazienti.telefono_confronto(telefono) if telefono else ''
        simili = self.per_nome.get(pazienti.semplifica(cognome) + '|' + pazienti.semplifica(nome), [])
        if simili:
            if tel:
                for p in simili:
                    if tel in (pazienti.telefono_confronto(p.telefono), pazienti.telefono_confronto(p.telefono2)):
                        return p, ''
                senza = [p for p in simili if not p.telefono and not p.telefono2]
                if senza:
                    return senza[0], ''
                return None, 'omonimo con un altro telefono: scheda nuova'
            if len(simili) > 1:
                return simili[0], 'più schede con questo nome: usata la prima'
            return simili[0], ''
        if tel and not nome:
            for p in self.per_tel.get(tel, []):
                if pazienti.semplifica(p.cognome) == pazienti.semplifica(cognome):
                    return p, ''
        return None, ''


def medici_possibili(operatori, testo):
    """I medici dell'anagrafica che il nome scritto nel file puo' indicare,
    dal passo migliore: il nome come e' scritto nella scheda ('ROSSI MARCO',
    'MARCO ROSSI', o 'ROSSI' se la scheda ha solo il cognome), poi cognome e
    iniziale del nome ('LANDOLFI F.'), poi il solo cognome. In ogni passo
    prima i medici attivi: uno che non c'e' piu' non si prende gli
    appuntamenti di un omonimo."""
    t = pazienti.semplifica(testo)
    if not t:
        return []
    passi = ([], [], [])
    for o in sorted(operatori, key=lambda o: (not o.attivo, o.id or 0)):
        c, n = pazienti.semplifica(o.cognome), pazienti.semplifica(o.nome)
        if not c:
            continue
        if t in (c + n, n + c):
            passi[0].append(o)
        elif n and len(t) == len(c) + 1 and t.startswith(c) and t[-1] == n[0]:
            passi[1].append(o)
        elif t == c:
            passi[2].append(o)
    return next((p for p in passi if p), [])


def trova_medico(operatori, testo):
    possibili = medici_possibili(operatori, testo)
    return possibili[0] if possibili else None


def omonimi(possibili):
    """Piu' medici attivi (o, se nessuno lo e', piu' medici) per lo stesso
    nome: se ne prende il primo, ma nell'anteprima va detto."""
    attivi = [o for o in possibili if o.attivo]
    return (attivi or possibili) if len(attivi or possibili) > 1 else []


RADICI = ('plastica', 'scopia', 'ectomia', 'tomia', 'grafia', 'terapia', 'protesi', 'visita',
          'controllo', 'intervento', 'biopsia', 'pessi', 'ecografia', 'infiltrazione', 'asportazione',
          'rimozione', 'sostituzione', 'lipoma', 'seno', 'addominoplastica', 'blefaroplastica',
          'additiva', 'riduttiva', 'settoplastica', 'rinoplastica', 'otoplastica', 'liposuzione')


def grafia_migliore(varianti):
    """Fra nomi quasi uguali ('MASTOPALSTICA' e 'MASTOPLASTICA') quello con
    piu' parole mediche riconoscibili; a parita', il piu' usato."""
    def voto(v):
        testo, righe = v
        n = norma(testo)
        return (sum(1 for r in RADICI if r in n), righe)
    return max(varianti, key=voto)[0]


ABBREVIAZIONI = {'sost': 'sostituzione', 'sostit': 'sostituzione', 'rim': 'rimozione', 'mastopl': 'mastoplastica',
                 'blefaro': 'blefaroplastica', 'dx': 'destra', 'sx': 'sinistra', 'bilat': 'bilaterale',
                 'monolat': 'monolaterale', 'egds': 'egds', 'e': 'con', 'piu': 'con'}


def espandi(testo):
    """'Sost, protesi +pessi' e 'Sostituzione protesi con pessi' si confrontano uguali."""
    t = norma(str(testo or '').replace('+', ' con '))
    return ''.join(ABBREVIAZIONI.get(x, x) for x in t.split())


def simile(a, b):
    if espandi(a) == espandi(b):
        return True
    a, b = pazienti.semplifica(a), pazienti.semplifica(b)
    if len(a) < 6 or len(b) < 6:
        return a == b
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.9


def leggi_stato(testo):
    t = norma(testo)
    if not t:
        return None
    for chiave, stato in (('disdett', 'DISDETTO'), ('annullat', 'DISDETTO'), ('non present', 'NON_PRESENTATO'),
                          ('assente', 'NON_PRESENTATO'), ('confermat', 'CONFERMATO'), ('arrivat', 'ARRIVATO'),
                          ('present', 'ARRIVATO'), ('eseguit', 'ARRIVATO'), ('fatt', 'ARRIVATO'),
                          ('prenotat', 'PRENOTATO')):
        if chiave in t:
            return stato
    return None


def leggi_tipo(testo):
    t = norma(testo)
    for codice, etichetta in ETICHETTA_TIPO_VISITA.items():
        if codice and norma(etichetta) == t:
            return codice
    if 'prima' in t:
        return 'PRIMA_VISITA'
    if 'controll' in t:
        return 'CONTROLLO'
    if 'urgen' in t:
        return 'URGENZA'
    return ''


def opzioni_da(f, analisi):
    def intero(chiave, difetto, minimo, massimo):
        try:
            v = int(f.get(chiave) or difetto)
        except (TypeError, ValueError):
            v = difetto
        return min(max(v, minimo), massimo)
    def spunta(chiave):
        # la casella ha davanti un campo nascosto "0": conta se fra i valori c'e' "1"
        valori = f.getlist(chiave) if hasattr(f, 'getlist') else ([f[chiave]] if chiave in f else [])
        return True if not valori else ('1' in valori or 'on' in valori)
    return {
        'struttura': intero('struttura', 0, 0, 2 ** 62),
        'durata': intero('durata', passo_orari(analisi) or 30, 5, 600),
        'passati': f.get('passati') if f.get('passati') in ('ARRIVATO', 'PRENOTATO', 'salta') else 'ARRIVATO',
        'maiuscole': spunta('maiuscole'),
        'crea_medici': spunta('crea_medici'),
        'crea_prestazioni': spunta('crea_prestazioni'),
        'unisci_simili': spunta('unisci_simili'),
        'appunti': spunta('appunti'),
        'data': come_data(f.get('data')) if f.get('data') else analisi.get('data_foglio'),
        'stanze': {k[7:]: v for k, v in f.items() if k.startswith('stanza_')},
        # per i file di un medico solo o di una stanza sola, senza la colonna
        'medico': intero('medico_file', 0, 0, 2 ** 62),
        'medico_scelto': 'medico_file' in f and f.get('medico_file') != 'titolo',
    }


def passo_orari(analisi):
    """Il passo fra un orario e il successivo nella colonna degli orari:
    un'agenda a righe di un'ora dice che gli appuntamenti durano un'ora."""
    pos = next((p for p, c in analisi['campi'].items() if c == 'ora'), None)
    if pos is None:
        return None
    j = dict(analisi['posizioni'])[pos]
    orari = [o.hour * 60 + o.minute for o in (come_ora(r[j]) for r in analisi['dati'][:1000] if j < len(r))
             if o is not None]
    # il passo piu' frequente fra una riga e la successiva: qualche 8:30 in
    # un'agenda a righe di un'ora non fa diventare di mezz'ora tutti gli interventi
    differenze = [b - a for a, b in zip(orari, orari[1:]) if 0 < b - a <= 240]
    if not differenze:
        return None
    passo = max(set(differenze), key=lambda x: (differenze.count(x), -x))
    return passo if 5 <= passo <= 240 else None


def valori_riga(analisi, riga, gruppo):
    """{campo: [valori]} di una riga per un blocco, piu' le colonne comuni."""
    uscita = {}
    for pos, j in analisi['posizioni']:
        campo = analisi['campi'][pos]
        if campo == 'ignora':
            continue
        j = colonna_di(pos, j, gruppo)
        if j is None:
            continue
        v = riga[j] if j < len(riga) else None
        uscita.setdefault(campo, []).append((analisi['intestazioni'][j], v, pos.startswith('c')))
    return uscita


def prepara(s, analisi, opzioni):
    if analisi['tipo'] == 'pazienti':
        return prepara_pazienti(s, analisi, opzioni)
    return prepara_appuntamenti(s, analisi, opzioni)


NON_PAZIENTE = re.compile(r'\b(blocc\w*|annull\w*|disdic\w*|disdett\w*|rinvi\w*|sospes\w*|d d d|'
                          r'da definire|non prenotare)\b')
PAROLE_DISDETTA = re.compile(r'\b(disdic\w*|disdett\w*|annull\w*|rinvi\w*|d d d)\b')


def _paziente_da(campi, opzioni, avvisi):
    """cognome, nome, telefono, telefono2, email, cf, nascita, dubbio, vuoto."""
    def primo(campo):
        for _, v, _ in campi.get(campo, []):
            if not vuoto(v):
                return v
        return None
    bello = iniziali_maiuscole if opzioni.get('maiuscole') else (lambda x: x)
    cognome = testo_di(primo('cognome'))
    nome = testo_di(primo('nome'))
    dubbio = False
    annotazioni = []
    insieme = testo_di(primo('cognome_nome'))
    # "SERAFINI?": il nome c'e', ma e' da confermare (il solo "?" e' un paziente da definire)
    da_confermare = bool(re.search(r'[^\W\d_].*\?\s*$', insieme))
    # "RUSSO LINA(BIANCHI)": fra parentesi e' un'annotazione, non il nome
    for x in re.findall(r'\(([^)]*)\)', insieme):
        if x.strip():
            annotazioni.append('(%s)' % x.strip())
    insieme = re.sub(r'\([^)]*\)', ' ', insieme)
    # "?D.SSA LIPPIELLO BLOCCA", "IL DOTTORE ANNULLA A D.D.D": una nota al posto del paziente
    if insieme and NON_PAZIENTE.search(norma(insieme)):
        annotazioni.append(' '.join(insieme.strip(' ?').split()))
        avvisi.append('al posto del paziente c\'è una nota: "%s"' % ' '.join(insieme.strip(' ?').split()))
        insieme = ''
    insieme = insieme.strip(' ?-/.x') if not re.fullmatch(r"[?\-/. x]*", insieme) else ''
    if insieme and not cognome:
        cognome, nome_diviso, sicuro = dividi_nome(insieme)
        # colonna "Nome e Cognome": nei casi dubbi vale l'ordine dell'intestazione
        intestazione = norma(next((i for i, v, _ in campi.get('cognome_nome', []) if not vuoto(v)), ''))
        if not sicuro and re.search(r'\bnome\b.*\bcognome\b', intestazione) and nome_diviso:
            parole = insieme.split()
            cognome, nome_diviso = ' '.join(parole[1:]), parole[0]
        nome = nome or nome_diviso
        dubbio = not sicuro
        if dubbio:
            avvisi.append('nome e cognome da verificare')
    if re.fullmatch(r"[?\-/. x]*", cognome or ''):
        cognome = ''
    grezzo = testo_di(primo('telefono'))
    for x in re.findall(r'\(([^)]*)\)', grezzo):
        if x.strip() and not re.sub(r'\D', '', x):
            annotazioni.append('telefono: %s' % x.strip().lower())
    telefono = come_telefono(primo('telefono'))
    if primo('telefono') is not None and not vuoto(primo('telefono')) and len(re.sub(r'\D', '', telefono)) < 6:
        avvisi.append('telefono non valido: tolto')
        telefono = ''
    telefono2 = come_telefono(primo('telefono2'))
    if len(re.sub(r'\D', '', telefono2)) < 6:
        telefono2 = ''
    email = testo_di(primo('email'))
    if email and ' ' in email and pazienti.email_valida(email.replace(' ', '')):
        email = email.replace(' ', '')
        avvisi.append('email con uno spazio: tolto')
    if email and not pazienti.email_valida(email):
        avvisi.append('email non valida: tolta')
        email = ''
    cf = testo_di(primo('codice_fiscale')).upper().replace(' ', '')
    if cf and not pazienti.codice_fiscale_valido(cf):
        avvisi.append('codice fiscale non valido: tolto')
        cf = ''
    nascita = come_nascita(primo('data_nascita'), avvisi) if primo('data_nascita') is not None else None
    if nascita and nascita > date.today():
        avvisi.append('data di nascita nel futuro: tolta')
        nascita = None
    # via, CAP e citta' in colonne diverse diventano una riga sola
    indirizzo = ', '.join(dict.fromkeys(testo_di(v) for _, v, _ in campi.get('indirizzo', []) if not vuoto(v)))
    return dict(cognome=bello(cognome)[:60], nome=bello(nome)[:60], telefono=telefono[:30],
                telefono2=telefono2[:30], email=email[:120], codice_fiscale=cf[:16],
                data_nascita=nascita, indirizzo=indirizzo[:200], dubbio=dubbio, annotazioni=annotazioni,
                da_confermare=da_confermare)


def prepara_pazienti(s, analisi, opzioni):
    indice = IndicePazienti(s)
    righe = []
    for n, riga in enumerate(analisi['dati'], start=analisi['riga_intestazioni'] + 2):
        if all(vuoto(v) for v in riga):
            continue
        campi = valori_riga(analisi, riga, analisi['gruppi'][0])
        avvisi = []
        p = _paziente_da(campi, opzioni, avvisi)
        note = ' '.join(testo_di(v) for _, v, _ in campi.get('note', []) if not vuoto(v))[:2000]
        inviato = ' '.join(testo_di(v) for _, v, _ in campi.get('inviato_da', []) if not vuoto(v))[:80]
        r = {'n': n, 'paziente': p, 'note': note, 'inviato_da': inviato, 'avvisi': avvisi,
             'esito': 'nuovo', 'motivo': '', 'esistente': None}
        if not p['cognome']:
            r['esito'], r['motivo'] = 'scartato', 'manca il cognome'
        else:
            esistente, avviso = indice.trova(p['cognome'], p['nome'], p['telefono'], p['codice_fiscale'])
            if avviso:
                avvisi.append(avviso)
            if esistente is not None and getattr(esistente, 'riga', None):
                r['esito'], r['motivo'] = 'doppio', 'stessa persona della riga %d' % esistente.riga
                # all'importazione questa riga completa la scheda della prima: qui
                # si fa lo stesso, cosi' le righe dopo la trovano come la troveranno
                if completa_campi(esistente, p):
                    indice.aggiungi(esistente)
            elif esistente is not None:
                r['esito'], r['esistente'] = 'esistente', esistente
            else:
                # nell'indice come se esistesse gia': le righe dopo la trovano
                indice.aggiungi(SimpleNamespace(riga=n, **{k: p[k] for k in (
                    'cognome', 'nome', 'telefono', 'telefono2', 'codice_fiscale', 'email', 'data_nascita',
                    'indirizzo')}))
        righe.append(r)
    return {'tipo': 'pazienti', 'righe': righe, 'conteggi': conta(righe),
            'nuovi_medici': [], 'nuove_prestazioni': [], 'nuove_stanze': [], 'unioni': [],
            'medici_doppi': 0, 'note_giorno': {}}


def conta(righe):
    c = {}
    for r in righe:
        c[r['esito']] = c.get(r['esito'], 0) + 1
    c['dubbi'] = sum(1 for r in righe if r.get('avvisi'))
    return c


def prepara_appuntamenti(s, analisi, opzioni):
    st = s.get(Struttura, opzioni['struttura']) if opzioni['struttura'] else None
    if st is None:
        st = s.scalars(select(Struttura).where(Struttura.attiva == True).order_by(Struttura.id)).first()
    stanze = {r.id: r for r in s.scalars(select(Risorsa).where(Risorsa.struttura_id == st.id))} if st else {}
    operatori = s.scalars(select(Operatore)).all()
    prestazioni = s.scalars(select(Prestazione)).all()
    bello = iniziali_maiuscole if opzioni['maiuscole'] else (lambda x: x)
    adesso = datetime.now()
    indice = IndicePazienti(s)

    # il nome di una stanza nuova, come si salvera': al massimo 60 caratteri
    def nome_stanza(testo):
        return bello(' '.join(testo.split()))[:60].strip()

    # stanza di ciascun blocco: scelta a mano, trovata per nome o da creare. Un
    # nome lungo e' salvato tagliato a 60 caratteri: il mese dopo si deve
    # ritrovare anche cosi', altrimenti si crea di nuovo e il database rifiuta
    def stanza_per_nome(nome):
        chiavi = {pazienti.semplifica(nome), pazienti.semplifica(nome_stanza(nome))}
        return next((r for r in stanze.values() if pazienti.semplifica(r.nome) in chiavi), None)

    # "Sala Rossa" e "sala rossa" nello stesso file sono una stanza sola (come i
    # medici): ogni stanza nuova ha il nome della prima volta che compare
    nomi_stanze_nuove = {}

    def stanza_nuova(testo):
        nome = nome_stanza(testo)
        return nomi_stanze_nuove.setdefault(pazienti.semplifica(nome), nome)

    # il medico di tutto il file: scelto nell'anteprima, oppure cercato nel titolo
    mappati = set(analisi['campi'].values())
    medico_file = None
    medico_titolo_nuovo = ''   # nel titolo, ma non ancora fra i medici: si crea
    if 'medico' not in mappati:
        if opzioni['medico']:
            medico_file = s.get(Operatore, opzioni['medico'])
        elif not opzioni.get('medico_scelto'):
            medico_file = medico_dal_titolo(operatori, analisi.get('titolo', ''))
            if medico_file is None:
                medico_titolo_nuovo = nome_medico_nel_titolo(analisi.get('titolo', ''))

    scelta_stanze = {}
    for k, g in enumerate(analisi['gruppi']):
        scelta = opzioni['stanze'].get(str(k))
        if scelta and scelta.isdigit() and int(scelta) in stanze:
            scelta_stanze[k] = ('esistente', stanze[int(scelta)])
        elif g['nome'] and stanza_per_nome(g['nome']):
            scelta_stanze[k] = ('esistente', stanza_per_nome(g['nome']))
        elif g['nome']:
            scelta_stanze[k] = ('nuova', stanza_nuova(g['nome']))
        elif 'stanza' not in mappati and stanza_dal_titolo(stanze.values(), analisi.get('titolo', '')) \
                and not (scelta or '').isdigit():
            scelta_stanze[k] = ('esistente', stanza_dal_titolo(stanze.values(), analisi.get('titolo', '')))
        else:
            scelta_stanze[k] = ('colonna', None)

    righe, ultima_data = [], None
    nomi_medici, nomi_prestazioni, note_giorno = {}, {}, {}
    for n, riga in enumerate(analisi['dati'], start=analisi['riga_intestazioni'] + 2):
        if all(vuoto(v) for v in riga):
            continue
        for k, g in enumerate(analisi['gruppi']):
            campi = valori_riga(analisi, riga, g)

            def primo(campo, solo_blocco=False):
                for _, v, comune in campi.get(campo, []):
                    if not vuoto(v) and not (solo_blocco and comune):
                        return v
                return None

            data = come_data(primo('data')) if primo('data') is not None else None
            if data:
                ultima_data = data
            # nel blocco non c'e' niente: fascia vuota dell'agenda
            propri = [campo for campo, valori in campi.items()
                      if campo not in ('data', 'ora', 'ora_fine') and any(not vuoto(v) and not c for _, v, c in valori)]
            if len(analisi['gruppi']) > 1 and not propri:
                continue
            if not propri and not campi.get('cognome_nome') and not campi.get('cognome'):
                continue
            if not any(not vuoto(v) for campo in ('medico', 'prestazione', 'cognome_nome', 'cognome', 'stanza')
                       for _, v, _ in campi.get(campo, [])):
                # solo testo libero ("NESSUNA SECONDA SALA..."): e' una nota per quel giorno
                testi = [testo_di(v) for campo in ('extra', 'note') for _, v, c in campi.get(campo, [])
                         if not vuoto(v) and not c]
                giorno_nota = data or ultima_data or opzioni.get('data')
                if testi and giorno_nota:
                    prefisso = (g['nome'].strip() + ': ') if g['nome'] else ''
                    note_giorno.setdefault(giorno_nota, [])
                    for x in testi:
                        if prefisso + x not in note_giorno[giorno_nota]:
                            note_giorno[giorno_nota].append(prefisso + x)
                continue
            avvisi = []
            data = data or ultima_data or opzioni.get('data')
            ora = come_ora(primo('ora')) if primo('ora') is not None else None
            r = {'n': n, 'gruppo': k, 'avvisi': avvisi, 'esito': 'nuovo', 'motivo': '', 'esistente': None}
            righe.append(r)
            if data is None:
                r['esito'], r['motivo'] = 'scartato', 'manca la data'
                continue
            if ora is None:
                r['esito'], r['motivo'] = 'scartato', 'manca l\'ora'
                continue
            r['inizio'] = datetime.combine(data, ora)
            # medico ("Dott. Galasso" e' Galasso: il titolo non e' una parte del nome)
            medico_testo = senza_titolo(testo_di(primo('medico')))
            if not medico_testo and medico_file is not None:
                medico_testo = medico_file.etichetta
            elif not medico_testo and medico_titolo_nuovo:
                medico_testo = medico_titolo_nuovo
            # quello che manca (medico, stanza) scarta la riga, ma la riga si legge
            # tutta lo stesso: diventa un appunto da confermare con i dati che ha
            mancante = ''
            if not medico_testo:
                mancante = 'manca il medico: sceglierlo in alto, "Medico di tutto il file"'
            # "BIANCARDI X ROSSETTI": opera Biancardi, per conto di Rossetti
            per_conto = re.fullmatch(r"(.+?)\s+(?:x|per)\s+(.+)", medico_testo.strip(), re.I)
            if per_conto:
                medico_testo = per_conto.group(1).strip()
                r['nota_medico'] = 'per conto di %s' % bello(per_conto.group(2).strip())
                avvisi.append('medico %s per conto di %s' % (bello(medico_testo), bello(per_conto.group(2).strip())))
            r['medico_testo'] = medico_testo
            if medico_file is not None and not testo_di(primo('medico')):
                r['medico'] = medico_file
            else:
                possibili = medici_possibili(operatori, medico_testo)
                r['medico'] = possibili[0] if possibili else None
                doppi = omonimi(possibili)
                if doppi:
                    avvisi.append('%s: in anagrafica ci sono %s; scelto %s' % (
                        bello(medico_testo), ' e '.join(o.etichetta for o in doppi), doppi[0].etichetta))
            if r['medico'] is None and medico_testo:
                chiave = pazienti.semplifica(medico_testo)
                nomi_medici.setdefault(chiave, {'testo': medico_testo, 'righe': 0})
                nomi_medici[chiave]['righe'] += 1
                r['medico_chiave'] = chiave
            r['telefono_medico'] = come_telefono(primo('telefono_medico'))
            # prestazione
            prest_testo = testo_di(primo('prestazione'))
            if prest_testo.endswith('?'):
                prest_testo = prest_testo.rstrip(' ?')
                avvisi.append('prestazione con il punto interrogativo: da confermare')
            r['prestazione_testo'] = prest_testo
            r['prestazione'] = next((p for p in prestazioni if prest_testo and
                                     pazienti.semplifica(p.nome) == pazienti.semplifica(prest_testo)), None)
            if prest_testo and r['prestazione'] is None:
                chiave = pazienti.semplifica(prest_testo)
                nomi_prestazioni.setdefault(chiave, {'testo': prest_testo, 'righe': 0})
                nomi_prestazioni[chiave]['righe'] += 1
                r['prestazione_chiave'] = chiave
            # stanza
            modo, stanza = scelta_stanze[k]
            if modo == 'colonna':
                testo_stanza = testo_di(primo('stanza'))
                if not testo_stanza:
                    mancante = mancante or 'manca la stanza: sceglierla in alto, "Stanze"'
                    r['stanza'], r['stanza_nuova'] = None, None
                else:
                    stanza = stanza_per_nome(testo_stanza)
                    r['stanza'] = stanza
                    r['stanza_nuova'] = None if stanza else stanza_nuova(testo_stanza)
            elif modo == 'esistente':
                r['stanza'], r['stanza_nuova'] = stanza, None
            else:
                r['stanza'], r['stanza_nuova'] = None, stanza
            # fine
            fine = None
            ora_fine = come_ora(primo('ora_fine')) if primo('ora_fine') is not None else None
            if ora_fine and ora_fine > ora:
                fine = datetime.combine(data, ora_fine)
            elif primo('durata') is not None:
                # una durata che non si legge, o fuori misura (meno di 5 minuti, piu'
                # di un giorno), si segnala: vale quella della prestazione o del file
                minuti = come_minuti(primo('durata'))
                if minuti is not None and 5 <= minuti <= 24 * 60:
                    fine = r['inizio'] + timedelta(minutes=minuti)
                else:
                    avvisi.append('durata non valida: "%s"' % testo_di(primo('durata'))[:20])
            r['durata_esplicita'] = fine is not None
            if fine is None:
                minuti = r['prestazione'].durata_min if r['prestazione'] else opzioni['durata']
                fine = r['inizio'] + timedelta(minutes=minuti)
            r['fine'] = fine
            # paziente
            p = _paziente_da(campi, opzioni, avvisi)
            r['paziente'] = p
            if p.get('da_confermare') and p['cognome']:
                mancante = mancante or 'paziente da confermare: "%s"' % testo_di(primo('cognome_nome'))
            if not p['cognome']:
                avvisi.append('paziente non indicato')
            else:
                esistente, avviso = indice.trova(p['cognome'], p['nome'], p['telefono'], p['codice_fiscale'])
                r['esistente'] = esistente
                if avviso:
                    avvisi.append(avviso)
            # il resto
            r['convenzione'] = testo_di(primo('convenzione'))[:80]
            try:
                r['importo'] = come_importo(primo('importo'))
            except ValueError:
                r['importo'] = None
                avvisi.append('importo non valido: tolto')
            r['tipo'] = leggi_tipo(testo_di(primo('tipo')))
            stato = leggi_stato(testo_di(primo('stato')))
            note = [testo_di(v) for _, v, _ in campi.get('note', []) if not vuoto(v)] + p.get('annotazioni', []) + \
                ([r['nota_medico']] if r.get('nota_medico') else [])
            # "DISDICE" nelle note, "IL DOTTORE ANNULLA" al posto del paziente: disdetto
            if stato is None and any(PAROLE_DISDETTA.search(norma(x)) for x in note):
                stato = 'DISDETTO'
                avvisi.append('disdetto, dalle note')
            if stato is None:
                if r['fine'] <= adesso:
                    if opzioni['passati'] == 'salta':
                        r['esito'], r['motivo'] = 'saltato', 'appuntamento già passato'
                        continue
                    stato = opzioni['passati']
                else:
                    stato = 'PRENOTATO'
            r['stato'] = stato
            if not p['cognome'] and testo_di(primo('cognome_nome')) in ('?',):
                note.append('paziente da definire')
            r['note'] = ' '.join(note)[:4000]
            r['extra'], r['degenza'], r['notti'] = {}, '', None
            for intestazione, v, _ in campi.get('extra', []):
                if not vuoto(v):
                    etichetta = ' '.join(intestazione.split()) or 'Altro'
                    if etichetta.isupper():
                        etichetta = etichetta.lower().capitalize()
                    if e_campo_degenza(etichetta):
                        # la degenza e' un campo dell'appuntamento: conta i letti
                        letta = leggi_degenza(testo_di(v))
                        if letta and not r['degenza']:
                            r['degenza'], r['notti'] = letta
                        elif not letta:
                            r['note'] = (r['note'] + ' %s: %s' % (etichetta, testo_di(v)[:40])).strip()[:4000]
                        continue
                    r['extra'][etichetta[:40].rstrip('?').strip() or 'Altro'] = testo_di(v)[:80]
            if mancante and r['esito'] == 'nuovo':
                r['esito'], r['motivo'] = 'scartato', mancante

    # medici e prestazioni nuovi, con i nomi quasi uguali riuniti
    nuovi_medici = []
    for chiave, x in sorted(nomi_medici.items(), key=lambda kv: -kv[1]['righe']):
        cognome, nome, _ = dividi_nome(x['testo'])
        nuovi_medici.append({'chiave': chiave, 'testo': x['testo'], 'cognome': bello(cognome)[:60],
                             'nome': bello(nome)[:60], 'righe': x['righe'], 'alias': []})
    # "ROSSETTI" e "MARCO ROSSETTI" nello stesso file sono lo stesso medico
    per_cognome = {}
    for m in nuovi_medici:
        per_cognome.setdefault(pazienti.semplifica(m['cognome']), []).append(m)
    for gruppo in per_cognome.values():
        nomi = {pazienti.semplifica(m['nome']) for m in gruppo if m['nome']}
        if len(gruppo) < 2 or len(nomi) > 1:
            continue
        capo = max(gruppo, key=lambda m: (bool(m['nome']), m['righe']))
        for m in gruppo:
            if m is not capo:
                capo['alias'].append(m['chiave'])
                capo['righe'] += m['righe']
                nuovi_medici.remove(m)
    # le righe dei nomi riuniti puntano al medico che resta: altrimenti il
    # controllo "stesso medico in due stanze" vedrebbe due medici diversi
    riunito = {al: m['chiave'] for m in nuovi_medici for al in m['alias']}
    for r in righe:
        if r.get('medico_chiave') in riunito:
            r['medico_chiave'] = riunito[r['medico_chiave']]
    unioni, nuove_prestazioni, alias = [], [], {}

    def bel_nome(testo):
        return (testo.lower().capitalize() if testo.isupper() else testo)[:80]

    for chiave, x in sorted(nomi_prestazioni.items(), key=lambda kv: (-kv[1]['righe'], kv[0])):
        bersaglio = None
        if opzioni['unisci_simili']:
            bersaglio = next((p for p in prestazioni if simile(p.nome, x['testo'])), None)
            if bersaglio is not None:
                alias[chiave] = ('esistente', bersaglio)
                unioni.append((x['testo'], bersaglio.nome, x['righe']))
                continue
            gia = next((np for np in nuove_prestazioni if simile(np['testo'], x['testo'])), None)
            if gia is not None:
                alias[chiave] = ('nuova', gia['chiave'])
                gia['varianti'].append((x['testo'], x['righe']))
                gia['righe'] += x['righe']
                continue
        nuove_prestazioni.append({'chiave': chiave, 'testo': x['testo'], 'righe': x['righe'],
                                  'durata': opzioni['durata'], 'varianti': [(x['testo'], x['righe'])]})
        alias[chiave] = ('nuova', chiave)
    for np in nuove_prestazioni:
        np['nome'] = bel_nome(grafia_migliore(np['varianti']))
        for testo, quante in np['varianti']:
            if bel_nome(testo) != np['nome']:
                unioni.append((testo, np['nome'], quante))
    for r in righe:
        if not r.get('inizio'):
            continue
        # anche le righe scartate: se diventano appunti, la prestazione e' quella giusta
        if r.get('prestazione_chiave') and r['prestazione_chiave'] in alias:
            modo, cosa = alias[r['prestazione_chiave']]
            if modo == 'esistente':
                r['prestazione'], r['prestazione_chiave'] = cosa, None
            else:
                r['prestazione_chiave'] = cosa
        if r['esito'] != 'nuovo':
            continue
        if r.get('medico_chiave') and not opzioni['crea_medici']:
            r['esito'], r['motivo'] = 'scartato', 'medico non in anagrafica: %s' % r['medico_testo']
        elif r.get('prestazione_chiave') and not opzioni['crea_prestazioni']:
            r['esito'], r['motivo'] = 'scartato', 'prestazione non in elenco: %s' % r['prestazione_testo']

    # durate non scritte: non oltre l'appuntamento successivo della stessa stanza
    per_stanza = {}
    for r in righe:
        if r['esito'] == 'nuovo':
            chiave = r['stanza'].id if r.get('stanza') else 'nuova:' + (r.get('stanza_nuova') or '')
            per_stanza.setdefault(chiave, []).append(r)
    passo_file = passo_orari(analisi)
    for chiave, lista in per_stanza.items():
        lista.sort(key=lambda x: x['inizio'])
        # un appuntamento disdetto (o non presentato) non occupa la stanza, come
        # in agenda: non accorcia quello prima, non ne blocca un altro alla stessa
        # ora e non e' mai in conflitto. Si importa com'e'
        attivi = [x for x in lista if x.get('stato') in STATI_ATTIVI]
        for a, b in zip(attivi, attivi[1:]):
            if not a['durata_esplicita'] and a['inizio'] < b['inizio'] < a['fine']:
                a['fine'] = b['inizio']
                # nelle agende a righe da un quarto d'ora la riga dopo e' il posto dopo:
                # si segnala solo quando resta meno di una riga
                if (b['inizio'] - a['inizio']).total_seconds() / 60 < (passo_file or 0):
                    a['avvisi'].append('durata ridotta fino all\'appuntamento successivo')
        # due o piu' righe nella stessa stanza alla stessa ora: entra la prima.
        # Il confronto e' con l'ultima entrata, non con la riga prima: quella
        # puo' essere a sua volta in conflitto (tre righe alle 9:00)
        entrata = None
        for b in attivi:
            if b['esito'] != 'nuovo':
                continue
            if entrata is None or b['inizio'] >= entrata['fine']:
                entrata = b
                continue
            a = entrata
            chi = ' '.join(x for x in (a['paziente'].get('cognome', ''), a['paziente'].get('nome', ''))
                           if x) if a.get('paziente') else ''
            b['esito'], b['motivo'] = 'conflitto', 'la stanza è già occupata alle %s%s (riga %d del file)' % (
                a['inizio'].strftime('%H:%M'), (' da ' + chi) if chi else '', a['n'])

    # contro il database: stanza occupata o appuntamento gia' presente
    for r in righe:
        if r['esito'] != 'nuovo' or not r.get('stanza'):
            continue
        attiva = r.get('stato') in STATI_ATTIVI
        if attiva:
            presenti = s.scalars(select(Appuntamento).where(
                Appuntamento.risorsa_id == r['stanza'].id, Appuntamento.inizio < r['fine'],
                Appuntamento.fine > r['inizio'], Appuntamento.stato.in_(STATI_ATTIVI))).all()
        else:
            # una riga disdetta non trova mai la stanza occupata; si cerca solo se e'
            # gia' stata importata (in qualunque stato), per non metterla due volte
            presenti = s.scalars(select(Appuntamento).where(
                Appuntamento.risorsa_id == r['stanza'].id, Appuntamento.inizio == r['inizio'])).all()
        if presenti:
            def stesso(a):
                """La riga e' questo appuntamento, gia' importato: stessa ora e
                stesso paziente, o entrambi senza paziente e con lo stesso medico."""
                if a.inizio != r['inizio']:
                    return False
                if r['esistente'] is not None and a.paziente_id == r['esistente'].id:
                    return True
                if a.paziente is not None and r['paziente']['cognome']:
                    return pazienti.semplifica(a.paziente.cognome) == pazienti.semplifica(r['paziente']['cognome'])
                if a.paziente_id is None and not r['paziente']['cognome']:
                    return r.get('medico') is not None and a.operatore_id == r['medico'].id
                return False
            uguale = next((a for a in presenti if stesso(a)), None)
            if uguale is not None:
                r['esito'], r['motivo'] = 'presente', 'già in agenda'
                r['appuntamento_presente'] = uguale
            elif attiva:
                a = presenti[0]
                r['esito'], r['motivo'] = 'conflitto', 'stanza già occupata dalle %s alle %s%s' % (
                    a.inizio.strftime('%H:%M'), a.fine.strftime('%H:%M'),
                    ' (%s)' % a.paziente.etichetta if a.paziente else '')

    # stesso medico in due stanze alla stessa ora: si importa, ma si segnala (un
    # appuntamento disdetto non occupa il medico, come non occupa la stanza)
    medici_doppi = 0
    buoni = [r for r in righe if r['esito'] == 'nuovo' and r.get('stato') in STATI_ATTIVI]
    for i, a in enumerate(buoni):
        chi_a = a['medico'].id if a.get('medico') else a.get('medico_chiave')
        for b in buoni[i + 1:]:
            chi_b = b['medico'].id if b.get('medico') else b.get('medico_chiave')
            if chi_a == chi_b and a['inizio'] < b['fine'] and b['inizio'] < a['fine']:
                b['avvisi'].append('%s è anche in un\'altra stanza alla stessa ora (riga %d)' % (b['medico_testo'], a['n']))
                medici_doppi += 1

    # i da confermare di un'importazione di prima (lo stesso file importato di
    # nuovo, o aggiornato): una riga che andrebbe fra i da confermare e c'e' gia'
    # non si aggiunge un'altra volta, nemmeno se quello e' stato chiuso (chi l'ha
    # chiuso non lo vuole di nuovo); una riga che ora entra in agenda, o c'e' gia',
    # chiude il suo da confermare ancora aperto. L'anteprima lo dice, l'importazione
    # fa questo e niente altro
    vecchi = appunti_importati(s, st, [r['inizio'] for r in righe if r.get('inizio')])
    da_chiudere = set()
    for r in righe:
        if not r.get('inizio'):
            continue
        uguali = [x for x in vecchi.get((r['inizio'].date(), r['inizio'].time()), []) if stesso_appunto(x, r)]
        if not uguali:
            continue
        if r['esito'] in ('scartato', 'conflitto') and opzioni.get('appunti', True):
            aperto = any(x.aperto for x in uguali)
            r['esito'], r['motivo'] = 'appunto', 'già fra i da confermare%s: %s' % (
                '' if aperto else ' (chiuso)', r['motivo'])
        elif r['esito'] in ('nuovo', 'presente') and r.get('stato') in STATI_ATTIVI:
            r['chiude_appunti'] = [x for x in uguali if x.aperto]
            da_chiudere.update(x.id for x in r['chiude_appunti'])
    return {'tipo': 'appuntamenti', 'righe': righe, 'conteggi': conta(righe), 'struttura': st,
            'appunti_da_chiudere': len(da_chiudere),
            'nuovi_medici': nuovi_medici if opzioni['crea_medici'] else [],
            'nuove_prestazioni': nuove_prestazioni if opzioni['crea_prestazioni'] else [],
            'nuove_stanze': sorted({r['stanza_nuova'] for r in righe if r.get('stanza_nuova') and r['esito'] == 'nuovo'}),
            'unioni': unioni, 'medici_doppi': medici_doppi, 'note_giorno': note_giorno,
            'appunti': opzioni.get('appunti', True),
            'medico_file': medico_file, 'medico_titolo_nuovo': medico_titolo_nuovo, 'senza_pazienti': not ({'cognome_nome', 'cognome'} & mappati),
            'stanze_scelte': {k: (v[1].id if v[0] == 'esistente' else None) for k, v in scelta_stanze.items()}}


def appunti_importati(s, st, inizi):
    """{(giorno, ora): [appunti]}: i da confermare nati da un'importazione (di
    qualunque file: il nome cambia, "agenda (2).xlsx") nei giorni del file,
    aperti e chiusi."""
    if not inizi or st is None:
        return {}
    giorni = [x.date() for x in inizi]
    uscita = {}
    for x in s.scalars(select(Appunto).where(
            Appunto.origine.like('Importazione %'), Appunto.struttura_id == st.id,
            Appunto.giorno >= min(giorni), Appunto.giorno <= max(giorni))):
        if x.ora is not None:
            uscita.setdefault((x.giorno, x.ora.replace(second=0, microsecond=0)), []).append(x)
    return uscita


def stesso_appunto(x, r):
    """L'appunto x (dello stesso giorno e della stessa ora) e' quello di questa
    riga: stesso paziente, e medico e stanza uguali quando li hanno tutti e due.
    Un appunto senza stanza o senza medico ("manca la stanza") e' della riga che
    ora li ha. Il numero di riga non conta: aggiungendo righe al file cambia."""
    medico, stanza = r.get('medico'), r.get('stanza')
    if medico is not None and x.operatore_id is not None and x.operatore_id != medico.id:
        return False
    if stanza is not None and x.risorsa_id is not None and x.risorsa_id != stanza.id:
        return False
    p = r.get('paziente') or {}
    if not p.get('cognome'):
        return x.paziente_id is None and not x.cognome
    if r.get('esistente') is not None:
        return x.paziente_id == r['esistente'].id
    return x.paziente_id is None and pazienti.semplifica(x.cognome) == pazienti.semplifica(p['cognome'])


def parole_titolo(titolo):
    return set(norma(titolo).split())


def medico_dal_titolo(operatori, titolo):
    """Il medico nominato nel titolo del file ("AGENDA - DOTT.SSA LIPPIELLO"),
    se ce n'e' uno solo."""
    parole = parole_titolo(titolo)
    trovati = [o for o in operatori if o.attivo and norma(o.cognome) and
               set(norma(o.cognome).split()) <= parole and len(norma(o.cognome)) >= 3]
    return trovati[0] if len(trovati) == 1 else None


# anche "D.SSA", come la scrive l'accettazione ("?D.SSA LIPPIELLO BLOCCA")
TITOLI_MEDICO = re.compile(
    r"\b(?:d\.\s?ssa|dott(?:\.?\s?ssa|oressa|ore|or)?|dr(?:\.?\s?ssa)?|prof(?:\.?\s?ssa|essoressa|essore)?)\b\.?",
    re.I)


def senza_titolo(testo):
    """Il nome del medico senza "Dott.", "Dott.ssa", "D.SSA", "Dr.", "Prof.":
    "DOTT.SSA GALASSO" -> "GALASSO". Senza togliere il titolo, nella colonna
    del medico diventava un medico nuovo "Galasso Dott." accanto a quello che
    c'era. Una cella con il solo titolo resta vuota (manca il medico); un nome
    senza titolo resta com'e'."""
    if not TITOLI_MEDICO.search(testo or ''):
        return testo
    return ' '.join(TITOLI_MEDICO.sub(' ', testo).split()).lstrip(' .')
NON_NOMI = {'gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic',
            'gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto',
            'settembre', 'ottobre', 'novembre', 'dicembre', 'agenda', 'anno', 'e', 'ed', 'di', 'xlsx',
            'csv', 'sala', 'ambulatorio', 'stanza', 'studio', 'data', 'ora', 'orario', 'medico', 'totale',
            'lunedi', 'martedi', 'mercoledi', 'giovedi', 'venerdi', 'sabato', 'domenica', 'visite', 'visita'}


def nome_medico_nel_titolo(titolo):
    """Il nome dopo "Dott.", "Dott.ssa", "Dr.", "Prof." nel titolo, per un medico
    che non c'e' ancora: "AGENDA ENDOSCOPIA DR. GALASSO OTT-NOV-DIC" -> "GALASSO".
    Ci si ferma al primo mese, anno o parola che non e' un nome."""
    trovati = set()
    titolo = titolo or ''
    for m in TITOLI_MEDICO.finditer(titolo):
        parole = []
        dopo = re.split(r'[/,;:()|\-–—]|\s{2,}', titolo[m.end():].strip(' .'))[0]
        for p in re.split(r'[\s.]+', dopo.strip(' .'))[:3]:
            if len(p) < 2 or not all(c.isalpha() or c == "'" for c in p) or norma(p) in NON_NOMI \
                    or TITOLI_MEDICO.fullmatch(p):
                break
            parole.append(p)
        if parole:
            trovati.add(' '.join(parole))
    # lo stesso nome nel nome del file e nel titolo del foglio conta una volta
    per_chiave = {pazienti.semplifica(x): x for x in sorted(trovati, key=len)}
    return next(iter(per_chiave.values())) if len(per_chiave) == 1 else ''


GENERICHE = {'sala', 'ambulatorio', 'stanza', 'studio', 'box', 'locale', 'di', 'della', 'del'}


def stanza_dal_titolo(stanze, titolo):
    """La stanza nominata nel titolo ("AGENDA ENDOSCOPIA" -> Sala endoscopia):
    contano le parole che la distinguono, non "sala" o "ambulatorio"."""
    parole = parole_titolo(titolo)
    trovate = []
    for r in stanze:
        proprie = set(norma(r.nome).split()) - GENERICHE
        if proprie and proprie <= parole and not all(x.isdigit() for x in proprie):
            trovate.append(r)
    if len(trovate) > 1:
        # "SALA ENDOSCOPIA ... A PARTIRE DALLE 9": vince "endoscopia", non la "a" di Sala A
        def peso(r):
            return max(len(x) for x in set(norma(r.nome).split()) - GENERICHE)
        trovate.sort(key=peso, reverse=True)
        if peso(trovate[0]) >= 3 and peso(trovate[1]) < 3:
            return trovate[0]
    return trovate[0] if len(trovate) == 1 else None


# ============================================================== esecuzione
def completa_campi(esistente, dati):
    """I campi vuoti della scheda presi dalla riga, senza sovrascrivere niente;
    un telefono diverso va nell'altro telefono. True se qualcosa e' cambiato.
    La stessa regola vale nell'anteprima della rubrica, sulla scheda che
    l'importazione creera' dalla riga di prima della stessa persona."""
    cambiato = False
    for campo in ('nome', 'telefono', 'email', 'codice_fiscale', 'data_nascita', 'indirizzo'):
        if dati.get(campo) and not getattr(esistente, campo):
            setattr(esistente, campo, dati[campo])
            cambiato = True
    if dati.get('telefono2') and not esistente.telefono2 and pazienti.telefono_confronto(dati['telefono2']) != \
            pazienti.telefono_confronto(esistente.telefono):
        esistente.telefono2 = dati['telefono2']
        cambiato = True
    if dati.get('telefono') and esistente.telefono and not esistente.telefono2 and \
            pazienti.telefono_confronto(dati['telefono']) != pazienti.telefono_confronto(esistente.telefono):
        esistente.telefono2 = dati['telefono']
        cambiato = True
    return cambiato


def crea_o_completa_paziente(s, indice, dati, note='', inviato_da=''):
    esistente, _ = indice.trova(dati['cognome'], dati['nome'], dati['telefono'], dati['codice_fiscale'])
    if esistente is not None:
        cambiato = completa_campi(esistente, dati)
        if note and note not in (esistente.note or ''):
            esistente.note = ((esistente.note or '') + '\n' + note).strip()[:2000]
            cambiato = True
        if inviato_da and not esistente.inviato_da:
            esistente.inviato_da = inviato_da
        if pazienti.completa_da_codice(esistente):
            cambiato = True
        indice.aggiungi(esistente)
        return esistente, ('aggiornato' if cambiato else 'uguale')
    p = Paziente(cognome=dati['cognome'], nome=dati['nome'], telefono=dati['telefono'],
                 telefono2=dati['telefono2'], email=dati['email'], codice_fiscale=dati['codice_fiscale'],
                 data_nascita=dati['data_nascita'], indirizzo=dati.get('indirizzo', ''), note=note,
                 inviato_da=inviato_da, sesso='', luogo_nascita='')
    pazienti.completa_da_codice(p)          # sesso, luogo e data di nascita dal codice fiscale
    s.add(p)
    s.flush()
    indice.aggiungi(p)
    return p, 'nuovo'


def crea_appunto(s, r, st, indice, medici, prestazioni, stanze, nome_file):
    """Una riga in conflitto o incompleta diventa un appunto da confermare, con
    tutto quello che si e' letto: medico, stanza, prestazione, paziente (la sua
    scheda si crea o si completa, come per le righe importate)."""
    paz, come = None, ''
    if r.get('paziente') and r['paziente'].get('cognome'):
        paz, come = crea_o_completa_paziente(s, indice, r['paziente'])
    motivo = (r.get('motivo') or '').replace(': sceglierla in alto, "Stanze"', '').replace(
        ': sceglierlo in alto, "Medico di tutto il file"', '').strip() or 'da confermare'
    stanza = r.get('stanza') or stanze.get(r.get('stanza_nuova'))
    medico = r.get('medico') or medici.get(r.get('medico_chiave'))
    prest = r.get('prestazione') or prestazioni.get(r.get('prestazione_chiave'))
    durata = int((r['fine'] - r['inizio']).total_seconds() // 60) if r.get('fine') else None
    x = Appunto(testo=motivo[:1].upper() + motivo[1:1000], giorno=r['inizio'].date(), ora=r['inizio'].time(),
                durata_min=durata if durata and durata >= 5 else None,
                struttura_id=st.id if st else None, risorsa_id=stanza.id if stanza else None,
                operatore_id=medico.id if medico else None, prestazione_id=prest.id if prest else None,
                paziente_id=paz.id if paz else None, note=((r.get('note') or '') + (
                    ' Degenza: %s' % r['degenza'] if r.get('degenza') else '')).strip()[:4000],
                origine=('Importazione %s, riga %d' % (nome_file, r['n']))[:200])
    s.add(x)
    return x, come


def esegui(s, piano, nome_file):
    """Scrive nel database quello che l'anteprima ha mostrato. Il chiamante
    tiene il lucchetto e ha gia' fatto il backup; qui si fa il commit."""
    esito = {'pazienti_nuovi': 0, 'pazienti_aggiornati': 0, 'appuntamenti': 0, 'medici': 0,
             'prestazioni': 0, 'stanze': 0, 'scartati': [], 'primo_giorno': None}
    indice = IndicePazienti(s)
    if piano['tipo'] == 'pazienti':
        # una persona si conta una volta sola: la scheda creata dalla prima riga e
        # completata dalla seconda e' un paziente nuovo, non anche uno aggiornato
        nuovi, aggiornati = set(), set()
        for r in piano['righe']:
            # la riga doppia completa la scheda della stessa persona, come una
            # gia' in anagrafica: altrimenti i suoi dati si perdevano
            if r['esito'] not in ('nuovo', 'esistente', 'doppio'):
                if r['esito'] in ('scartato',):
                    esito['scartati'].append((r['n'], r['motivo']))
                continue
            p, come = crea_o_completa_paziente(s, indice, r['paziente'], r['note'], r['inviato_da'])
            if come == 'nuovo':
                nuovi.add(p.id)
            elif come == 'aggiornato' and p.id not in nuovi:
                aggiornati.add(p.id)
        esito['pazienti_nuovi'], esito['pazienti_aggiornati'] = len(nuovi), len(aggiornati)
        servizi.registra(s, 'Importazione', None, 'PAZIENTI', '%s: %d nuovi, %d aggiornati' % (
            nome_file, esito['pazienti_nuovi'], esito['pazienti_aggiornati']))
        s.commit()
        return esito

    st = piano['struttura']
    medici = {}
    for m in piano['nuovi_medici']:
        o = Operatore(cognome=m['cognome'] or m['testo'][:60], nome=m['nome'], colore=colore_libero(s), attivo=True)
        s.add(o)
        s.flush()
        medici[m['chiave']] = o
        for alias in m.get('alias', []):
            medici[alias] = o
        esito['medici'] += 1
    prestazioni = {}
    for p in piano['nuove_prestazioni']:
        esistente = s.scalars(select(Prestazione).where(Prestazione.nome == p['nome'])).first()
        if esistente is None:
            esistente = Prestazione(nome=p['nome'], durata_min=p['durata'])
            s.add(esistente)
            s.flush()
            esito['prestazioni'] += 1
        prestazioni[p['chiave']] = esistente
    stanze = {}
    # le stanze della struttura per nome semplificato: una stanza che c'e' gia'
    # con lo stesso nome (anche scritto con altre maiuscole) si usa, non se ne
    # crea un'altra. Con un nome uguale il database rifiuterebbe tutta
    # l'importazione; con le maiuscole diverse ci sarebbero due stanze
    gia = s.scalars(select(Risorsa).where(Risorsa.struttura_id == st.id)).all()
    per_chiave = {pazienti.semplifica(r.nome): r for r in gia}
    ordine = max([r.ordine for r in gia] or [0])
    for nome in piano['nuove_stanze']:
        r = per_chiave.get(pazienti.semplifica(nome))
        if r is None:
            ordine += 1
            tipo = 'SALA_OPERATORIA' if 'sala' in nome.lower() and 'endosc' not in nome.lower() else 'AMBULATORIO'
            r = Risorsa(nome=nome, tipo=tipo, struttura_id=st.id, ordine=ordine, attiva=True)
            s.add(r)
            s.flush()
            per_chiave[pazienti.semplifica(nome)] = r
            esito['stanze'] += 1
        stanze[nome] = r
    campi_extra = {}
    esito['appunti'] = 0

    def da_confermare(r):
        """La riga non entra in agenda ma non si perde: diventa un appunto,
        se l'importazione lo prevede; altrimenti resta fra gli scartati."""
        if not (piano.get('appunti') and r.get('inizio')):
            esito['scartati'].append((r['n'], r['motivo']))
            return
        _, come = crea_appunto(s, r, st, indice, medici, prestazioni, stanze, nome_file)
        esito['appunti'] += 1
        if come == 'nuovo':
            esito['pazienti_nuovi'] += 1
        elif come == 'aggiornato':
            esito['pazienti_aggiornati'] += 1

    esito['appunti_chiusi'] = 0

    def chiudi_appunti(r, a):
        """La riga e' in agenda: i suoi da confermare di un'importazione di prima
        (quelli che l'anteprima ha contato) si chiudono, come con Prenota."""
        for x in r.get('chiude_appunti') or []:
            if segreteria.chiudi_appunto_prenotato(s, x.id, a):
                esito['appunti_chiusi'] += 1

    for r in piano['righe']:
        if r['esito'] != 'nuovo':
            if r['esito'] in ('scartato', 'conflitto'):
                da_confermare(r)
            elif r['esito'] == 'presente':
                chiudi_appunti(r, r.get('appuntamento_presente'))
            # 'appunto': e' gia' fra i da confermare, non se ne fa un altro
            continue
        stanza = r['stanza'] or stanze.get(r.get('stanza_nuova'))
        medico = r['medico'] or medici.get(r.get('medico_chiave'))
        prest = r['prestazione'] or prestazioni.get(r.get('prestazione_chiave'))
        if stanza is None or medico is None:
            esito['scartati'].append((r['n'], 'stanza o medico mancanti'))
            continue
        # ricontrollo al momento di scrivere: l'agenda puo' essere cambiata dopo l'anteprima
        occupato = s.scalars(select(Appuntamento).where(
            Appuntamento.risorsa_id == stanza.id, Appuntamento.inizio < r['fine'],
            Appuntamento.fine > r['inizio'], Appuntamento.stato.in_(STATI_ATTIVI))).first()
        if occupato is not None and r['stato'] in STATI_ATTIVI:
            r['motivo'] = 'stanza occupata alle %s' % occupato.inizio.strftime('%H:%M')
            da_confermare(r)
            continue
        paz = None
        if r['paziente']['cognome']:
            paz, come = crea_o_completa_paziente(s, indice, r['paziente'])
            if come == 'nuovo':
                esito['pazienti_nuovi'] += 1
            elif come == 'aggiornato':
                esito['pazienti_aggiornati'] += 1
        if r.get('telefono_medico') and not medico.telefono:
            medico.telefono = r['telefono_medico'][:30]
        a = Appuntamento(risorsa_id=stanza.id, operatore_id=medico.id, paziente_id=paz.id if paz else None,
                         prestazione_id=prest.id if prest else None, inizio=r['inizio'], fine=r['fine'],
                         stato=r['stato'], note=r['note'], tipo=r['tipo'], convenzione=r['convenzione'],
                         importo_cent=r['importo'], degenza=r.get('degenza') or '', notti=r.get('notti'),
                         extra=json.dumps(r['extra'], ensure_ascii=False) if r['extra'] else '')
        s.add(a)
        s.flush()
        esito['appuntamenti'] += 1
        chiudi_appunti(r, a)
        if esito['primo_giorno'] is None or r['inizio'].date() < esito['primo_giorno']:
            esito['primo_giorno'] = r['inizio'].date()
        if prest is not None and r['extra']:
            campi_extra.setdefault(prest.id, (prest, []))
            for etichetta in r['extra']:
                if etichetta not in campi_extra[prest.id][1]:
                    campi_extra[prest.id][1].append(etichetta)
    for giorno, testi in piano.get('note_giorno', {}).items():
        n = s.scalars(select(NotaGiorno).where(NotaGiorno.struttura_id == st.id, NotaGiorno.data == giorno)).first()
        if n is None:
            n = NotaGiorno(struttura_id=st.id, data=giorno, testo='')
            s.add(n)
        for x in testi:
            if x not in (n.testo or ''):
                n.testo = ((n.testo or '') + '\n' + x).strip()[:1000]
        esito['note'] = esito.get('note', 0) + 1
    # i campi in piu' diventano campi della prestazione: altrimenti al primo
    # salvataggio dal modulo andrebbero persi
    for prest, etichette in campi_extra.values():
        presenti = [e for e, _ in prest.elenco_campi_extra]
        aggiunte = [e for e in etichette if e.lower() not in {x.lower() for x in presenti}]
        if aggiunte:
            prest.campi_extra = ', '.join(
                [e + ('?' if si else '') for e, si in prest.elenco_campi_extra] + aggiunte)[:200]
    servizi.registra(s, 'Importazione', None, 'APPUNTAMENTI', '%s: %d appuntamenti, %d pazienti nuovi' % (
        nome_file, esito['appuntamenti'], esito['pazienti_nuovi']))
    s.commit()
    return esito


# ============================================================ file in attesa
def cartella_lavoro():
    c = os.path.join(tempfile.gettempdir(), 'gestionale-importazioni')
    os.makedirs(c, exist_ok=True)
    # i caricamenti di ieri non servono piu'
    for nome in os.listdir(c):
        try:
            if orologio.time() - os.path.getmtime(os.path.join(c, nome)) > 86400:
                os.remove(os.path.join(c, nome))
        except OSError:
            pass
    return c


def percorso_caricato(token, estensione='.dat'):
    if not re.fullmatch(r'[0-9a-f]{32}', token or ''):
        abort(404)
    return os.path.join(cartella_lavoro(), token + estensione)


def carica_caricato(token):
    p = percorso_caricato(token)
    if not os.path.exists(p):
        return None, None
    with open(percorso_caricato(token, '.json'), encoding='utf-8') as f:
        meta = json.load(f)
    with open(p, 'rb') as f:
        return f.read(), meta


# ================================================================ pagine
@bp.route('/importa', methods=['GET', 'POST'])
def carica():
    s = ses()
    if request.method == 'POST':
        f = request.files.get('file')
        if f is None or not f.filename:
            flash('Scegliere un file Excel (.xlsx) o CSV.', 'errore')
            return redirect(url_for('importa.carica'))
        dati = f.read(MASSIMO_FILE + 1)
        if len(dati) > MASSIMO_FILE:
            flash('Il file supera 10 MB.', 'errore')
            return redirect(url_for('importa.carica'))
        try:
            fogli = leggi_file(dati, f.filename)
        except ValueError as e:
            flash(str(e), 'errore')
            return redirect(url_for('importa.carica'))
        if not any(x['righe'] for x in fogli):
            flash('Il file non contiene righe.', 'errore')
            return redirect(url_for('importa.carica'))
        token = secrets.token_hex(16)
        with open(percorso_caricato(token), 'wb') as out:
            out.write(dati)
        with open(percorso_caricato(token, '.json'), 'w', encoding='utf-8') as out:
            json.dump({'nome': os.path.basename(f.filename)[:120], 'tipo': request.form.get('tipo') or ''}, out)
        return redirect(url_for('importa.anteprima', token=token, tipo=request.form.get('tipo') or ''))
    return render_template('importa.html', sezione='importa',
                           strutture=s.scalars(select(Struttura).where(Struttura.attiva == True)).all())


FOGLI_ACCESSORI = re.compile(r'\b(istruzion\w*|leggimi|legenda|riepilog\w*|note|info|guida|esempi\w*)\b')


def righe_piene(foglio):
    return sum(1 for r in foglio['righe'] if sum(1 for v in r if v not in (None, '')) >= 3)


def accessorio(foglio):
    return bool(FOGLI_ACCESSORI.search(norma(foglio.get('nome'))))


def foglio_successivo(fogli, indice):
    """Dopo aver importato un mese, il mese dopo dello stesso file."""
    return next((i for i in range(indice + 1, len(fogli))
                 if not accessorio(fogli[i]) and righe_piene(fogli[i])), None)


def foglio_di_dati(fogli):
    """Il foglio da proporre: il primo che somiglia a una tabella. Un foglio di
    istruzioni in testa (due colonne di testo) ha piu' righe di un mese vuoto,
    ma nessuna con tre celle scritte: si guarda a quelle, e fra i fogli con
    almeno meta' delle righe del piu' pieno vince il primo, cosi' in un file
    con un foglio per mese si parte dal primo mese."""
    conta = [righe_piene(x) for x in fogli]
    # istruzioni e riepiloghi vengono dopo, anche se contengono una tabella d'esempio
    accessori = [accessorio(x) for x in fogli]
    for solo_dati in (True, False):
        scelti = [(i, n) for i, n in enumerate(conta) if n and not (solo_dati and accessori[i])]
        if scelti:
            soglia = max(n for _, n in scelti) / 2
            return next(i for i, n in scelti if n >= soglia)
    return next((i for i, x in enumerate(fogli) if len(x['righe']) > 1), 0)


def avviso_righe_oltre(foglio):
    """Il foglio ha piu' righe di quelle che si leggono: l'anteprima e la pagina
    finale lo dicono, le righe in piu' non restano fuori senza saperlo."""
    n = foglio.get('oltre') or 0
    if not n:
        return ''
    massimo = MASSIMO_RIGHE + 30

    def cifre(x):
        return '{:,}'.format(x).replace(',', '.')
    return ('Righe non lette: %s, dalla riga %s in poi. Il programma legge al massimo %s righe per foglio: '
            'per importare anche quelle, dividere il file in più file più piccoli.'
            % (cifre(n), cifre(massimo + 1), cifre(massimo)))


def _analisi_dalla_richiesta(dati, meta, f):
    fogli = leggi_file(dati, meta['nome'])
    indice_foglio = 0
    try:
        indice_foglio = min(max(int(f.get('foglio') or 0), 0), len(fogli) - 1)
    except ValueError:
        pass
    if 'foglio' not in f:
        indice_foglio = foglio_di_dati(fogli)
    tipo = f.get('tipo') or meta.get('tipo') or None
    mappa = {k[6:]: v for k, v in f.items() if k.startswith('campo_')}
    # cambiato il foglio o il contenuto: le colonne scelte prima non valgono piu'
    if f.get('tipo_precedente') and f.get('tipo_precedente') != f.get('tipo') or \
            f.get('foglio_precedente') and f.get('foglio_precedente') != f.get('foglio'):
        mappa = {}
    if not mappa and tipo is None:
        analisi = analizza(fogli[indice_foglio])
        salvata = leggi_impostazione(ses(), 'importazione:' + analisi['firma'], '')
        if salvata:
            try:
                analisi = analizza(fogli[indice_foglio], analisi['tipo'], json.loads(salvata))
                analisi['note'].append('Colonne impostate come nell\'ultima importazione di un file uguale.')
            except ValueError:
                pass
        return fogli, indice_foglio, analisi
    return fogli, indice_foglio, analizza(fogli[indice_foglio], tipo, mappa or None)


@bp.route('/importa/<token>', methods=['GET', 'POST'])
def anteprima(token):
    s = ses()
    dati, meta = carica_caricato(token)
    if dati is None:
        flash('Il file caricato non c\'è più: caricarlo di nuovo.', 'errore')
        return redirect(url_for('importa.carica'))
    f = request.values
    try:
        fogli, indice_foglio, analisi = _analisi_dalla_richiesta(dati, meta, f)
    except ValueError as e:
        flash(str(e), 'errore')
        return redirect(url_for('importa.carica'))
    opzioni = opzioni_da(f, analisi)
    strutture = s.scalars(select(Struttura).where(Struttura.attiva == True).order_by(Struttura.id)).all()
    if analisi['tipo'] == 'appuntamenti' and not strutture:
        flash('Serve almeno una struttura attiva.', 'errore')
        return redirect(url_for('importa.carica'))
    piano = prepara(s, analisi, opzioni)
    if request.method == 'POST' and f.get('azione') == 'importa':
        with _lucchetto:
            try:
                import viste
                percorso, _ = viste.percorso_database()
                if percorso:
                    backup.esegui(percorso, viste.cartella_effettiva(s, percorso), 'prima-dell-importazione')
            except Exception as e:
                flash('Importazione annullata: il backup di sicurezza non è riuscito (%s).' % e, 'errore')
                return redirect(request.url)
            try:
                esito = esegui(s, piano, meta['nome'])
            except Exception as e:
                s.rollback()
                flash('Importazione non riuscita, niente è stato salvato: %s' % e, 'errore')
                return redirect(request.url)
            scrivi_impostazione(s, 'importazione:' + analisi['firma'], json.dumps(analisi['campi']))
            s.commit()
        with open(percorso_caricato(token, '.esito.json'), 'w', encoding='utf-8') as out:
            json.dump({'scartati': esito['scartati'], 'nome': meta['nome']}, out)
        dopo = foglio_successivo(fogli, indice_foglio)
        return render_template('importa_esito.html', esito=esito, piano=piano, meta=meta, token=token,
                               foglio=fogli[indice_foglio].get('nome'),
                               righe_oltre=avviso_righe_oltre(fogli[indice_foglio]),
                               prossimo=(dopo, fogli[dopo].get('nome')) if dopo is not None else None,
                               sid=piano['struttura'].id if piano.get('struttura') else None,
                               sezione='importa')
    campi = CAMPI_APPUNTAMENTI if analisi['tipo'] == 'appuntamenti' else CAMPI_PAZIENTI
    colonne = []
    for pos, j in analisi['posizioni']:
        campione = [testo_di(r[j]) for r in analisi['dati'][:200] if j < len(r) and not vuoto(r[j])][:3]
        colonne.append({'pos': pos, 'intestazione': analisi['intestazioni'][j] or '(senza nome)',
                        'campo': analisi['campi'][pos], 'campione': campione,
                        'lettera': lettera_colonna(j)})
    stanze = s.scalars(select(Risorsa).where(Risorsa.struttura_id == piano['struttura'].id)
                       .order_by(Risorsa.ordine)).all() if piano.get('struttura') else []
    righe_mostrate = [r for r in piano['righe'] if r['esito'] not in ('nuovo', 'esistente') or r['avvisi']][:RIGHE_ANTEPRIMA]
    righe_mostrate += [r for r in piano['righe'] if r not in righe_mostrate][:max(0, RIGHE_ANTEPRIMA - len(righe_mostrate))]
    righe_mostrate.sort(key=lambda r: (r['n'], r.get('gruppo', 0)))
    medici = s.scalars(select(Operatore).where(Operatore.attivo == True)
                       .order_by(Operatore.cognome, Operatore.nome)).all()
    return render_template('importa_anteprima.html', token=token, meta=meta, fogli=fogli, medici=medici,
                           indice_foglio=indice_foglio, analisi=analisi, opzioni=opzioni, piano=piano,
                           righe_oltre=avviso_righe_oltre(fogli[indice_foglio]),
                           colonne=colonne, campi=campi, strutture=strutture, stanze=stanze,
                           righe=righe_mostrate, etichetta_stato=ETICHETTA_STATO,
                           importo_in_testo=importo_in_testo, sezione='importa',
                           sid=piano['struttura'].id if piano.get('struttura') else None)


def lettera_colonna(j):
    lettere = ''
    j += 1
    while j:
        j, resto = divmod(j - 1, 26)
        lettere = chr(65 + resto) + lettere
    return lettere


@bp.route('/importa/<token>/scarti.xlsx')
def scarti(token):
    from openpyxl import Workbook
    p = percorso_caricato(token, '.esito.json')
    if not os.path.exists(p):
        abort(404)
    with open(p, encoding='utf-8') as f:
        esito = json.load(f)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Righe non importate'
    ws.append(['Riga del file', 'Motivo'])
    for n, motivo in esito['scartati']:
        ws.append([n, motivo])
    ws.column_dimensions['B'].width = 70
    uscita = io.BytesIO()
    wb.save(uscita)
    uscita.seek(0)
    return send_file(uscita, as_attachment=True, download_name='righe-non-importate.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
