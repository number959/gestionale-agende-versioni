# -*- coding: utf-8 -*-
"""Autoriparazione (dalla 1.11): il programma si accorge da solo dei guasti
piu' comuni e li ripara, senza perdere dati e dicendo cosa ha fatto.

Chi usa il programma non e' un tecnico: quando qualcosa si blocca puo' solo
cliccare di nuovo l'icona. Per questo i controlli stanno all'avvio e in un
thread che gira mentre il programma e' aperto (il «custode"):

1. **Un gestionale solo.** Il primo che parte tiene un lucchetto sul file
   `gestionale.lock` (lo rilascia Windows quando il programma si chiude, anche
   se si chiude male) e scrive in `gestionale.pid` chi e' e su che porta
   risponde. Il secondo clic apre solo la pagina. Se il gestionale aperto non
   risponde piu' (bloccato), il secondo clic lo chiude e riparte al suo
   posto; un programma che non e' il gestionale non si chiude mai. Se la porta
   5000 e' presa da un altro programma, il gestionale si apre su un'altra
   porta (5001-5009) e lo scrive nel diario.
2. **Il database.** Prima di aprirlo si controlla che sia integro (PRAGMA
   quick_check). Se manca o e' vuoto ma ci sono copie di sicurezza, si rimette
   la piu' recente che passa il controllo completo. Se e' danneggiato, il file
   viene prima messo da parte (`backup\\danneggiati`, non si cancella mai), poi
   si prova a ricostruirlo senza perdere niente (VACUUM INTO, poi REINDEX); se
   non basta, si rimette l'ultima copia buona e il recupero parziale resta da
   parte per l'assistenza; senza copie si tiene il recupero parziale. Lo stesso
   controllo il custode lo ripete ogni mezz'ora, e subito dopo un errore
   «malformed»: la riparazione mentre il programma e' aperto tiene fermi i
   salvataggi (LUCCHETTO).
3. **I lavori in sottofondo** (copie di sicurezza, email e WhatsApp, controllo
   degli aggiornamenti) se si fermano ripartono.
4. **Lo spazio sul disco**: sotto i 300 MB lo dice, prima che i salvataggi e
   le copie non riescano piu'.

Quello che fa lo scrive nel diario `autoriparazione.json`, accanto al
database e non dentro (il database e' proprio la cosa che si ripara): la
pagina Configura → Controllo del programma lo mostra, e la campanella avvisa
nei giorni dopo. Nel diario sta anche la cartella dei backup scelta nelle
impostazioni, per trovare le copie anche quando il database non si legge.

Nessun import di Flask: lo usa anche l'avvio, prima che il server esista."""
import http.client
import json
import logging
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time as orologio
import zlib
from datetime import datetime, timedelta

import backup

PROGRAMMA = 'Gestionale Agende'


def _porta_scelta():
    # GESTIONALE_PORTA serve solo alle prove (che non toccano mai la 5000): al PC della clinica non c'e'
    try:
        p = int(os.environ.get('GESTIONALE_PORTA') or 5000)
    except ValueError:
        return 5000
    return p if 1024 <= p <= 65535 else 5000


PORTA = _porta_scelta()
PORTE_DI_RISERVA = tuple(range(5001, 5010))
FILE_LUCCHETTO = 'gestionale.lock'
FILE_PID = 'gestionale.pid'
FILE_DIARIO = 'autoriparazione.json'
CARTELLA_DANNEGGIATI = 'danneggiati'          # dentro backup\
MASSIMO_EVENTI = 100
SPAZIO_MINIMO = 300 * 1024 * 1024
OGNI_CONTROLLO_DB = 30 * 60                     # secondi fra due controlli del database
OGNI_GIRO = 30                                  # secondi fra due giri del custode (e due battiti)
# il battito: il custode lo scrive in gestionale.pid a ogni giro. Un gestionale che non
# risponde alle pagine ma batte e' occupato, non bloccato: il secondo clic aspetta
BATTITO_SCADUTO = 90                            # secondi senza battito: il programma e' fermo
ATTESA_OCCUPATO = 150                           # secondi che il secondo clic aspetta uno occupato
# un gestionale che sta partendo (con una riparazione in corso, per esempio) non
# risponde ancora: prima di questo tempo il secondo clic non lo chiude
ATTESA_AVVIO = 10 * 60
INTESTAZIONE = b'SQLite format 3\x00'
# il riavvio da solo: quando, e mai piu' di tre volte in un'ora (un guasto che
# torna subito non deve far ripartire il programma all'infinito)
MASSIMO_RIAVVII_ORA = 3
FERME_TANTE = 5 * 60            # tre pagine ferme da piu' di cinque minuti...
FERMA_UNA = 30 * 60             # ...o una ferma da mezz'ora: il programma e' bloccato
NOMI_LAVORI = {'backup': 'le copie di sicurezza', 'invii': 'l\'invio di email e WhatsApp',
               'aggiornamenti': 'il controllo degli aggiornamenti'}

_cartella = [None]                     # la cartella dei dati, accanto al database
_diario = threading.Lock()
_sveglia = threading.Event()           # un errore "malformed" chiede un controllo subito
_sorvegliati = {}                      # nome -> (thread attuale, riavvia)
_istanza = [None]                      # il lucchetto del gestionale principale (entra)
_riavvio = {'comando': None, 'occupato': None, 'ferme': None, 'risorse': None, 'fili': 4}
stato = {'ultimo_giro': None, 'controllo_db': None, 'esito_db': None, 'dettaglio_db': '',
         'spazio_libero': None, 'porta': None, 'riavvii': 0}


# ================================================================ il diario
def imposta_cartella(cartella):
    _cartella[0] = cartella


def percorso_diario(cartella=None):
    cartella = cartella or _cartella[0]
    return os.path.join(cartella, FILE_DIARIO) if cartella else None


def leggi_diario(cartella=None):
    """Il diario come dizionario; vuoto se manca o non si legge (anche
    scritto a meta': non deve mai fermare l'avvio)."""
    percorso = percorso_diario(cartella)
    dati = {}
    if percorso:
        try:
            with open(percorso, encoding='utf-8') as f:
                dati = json.load(f)
        except (OSError, ValueError):
            dati = {}
    if not isinstance(dati, dict):
        dati = {}
    if not isinstance(dati.get('eventi'), list):
        dati['eventi'] = []
    dati['eventi'] = [e for e in dati['eventi'] if isinstance(e, dict) and isinstance(e.get('testo'), str)
                      and isinstance(e.get('quando'), str)]
    return dati


def _sostituisci(provvisorio, finale, tentativi=20):
    """os.replace che riprova: su Windows un antivirus o un'altra copia del
    programma che sta leggendo tengono il file aperto per un attimo."""
    for i in range(tentativi):
        try:
            os.replace(provvisorio, finale)
            return
        except PermissionError:
            if i == tentativi - 1:
                raise
            orologio.sleep(0.1)


def _scrivi_json(percorso, dati):
    provvisorio = '%s.%d.tmp' % (percorso, os.getpid())
    with open(provvisorio, 'w', encoding='utf-8') as f:
        json.dump(dati, f, ensure_ascii=False, indent=1)
    _sostituisci(provvisorio, percorso)


def _modifica_diario(cambia, cartella=None):
    percorso = percorso_diario(cartella)
    if not percorso:
        return
    with _diario:
        dati = leggi_diario(cartella)
        cambia(dati)
        dati['eventi'] = dati['eventi'][-MASSIMO_EVENTI:]
        try:
            _scrivi_json(percorso, dati)
        except OSError:
            logging.exception('autoriparazione: diario non scritto')


def annota(testo, livello='ok', dettaglio='', cartella=None, tipo=''):
    """Una riga del diario. livello: 'ok' (riparato da solo), 'attenzione'
    (riparato, ma qualcosa va controllato), 'errore' (serve l'assistenza)."""
    {'ok': logging.info, 'attenzione': logging.warning}.get(livello, logging.error)(
        'autoriparazione: %s%s', testo, (' (%s)' % dettaglio) if dettaglio else '')
    evento = {'quando': datetime.now().isoformat(timespec='seconds'), 'testo': testo, 'livello': livello,
              'dettaglio': dettaglio}
    if tipo:
        evento['tipo'] = tipo
    _modifica_diario(lambda d: d['eventi'].append(evento), cartella)
    return evento


def ricorda(cartella=None, **valori):
    """Si ricorda fuori dal database cose che servono quando il database non
    si legge: la cartella dei backup scelta, l'ultimo avvio riuscito."""
    _modifica_diario(lambda d: d.update(valori), cartella)


def eventi(dal=None, cartella=None):
    """Gli eventi del diario, dal piu' recente; solo quelli da 'dal' in poi."""
    uscita = []
    for e in reversed(leggi_diario(cartella)['eventi']):
        try:
            quando = datetime.fromisoformat(e['quando'])
        except ValueError:
            continue
        if dal is None or quando >= dal:
            uscita.append(dict(e, quando=quando))
    return uscita


# ============================================================ il database
def controlla_database(percorso, completo=False, attesa=10):
    """(esito, dettaglio). esito: 'ok', 'mancante', 'vuoto' (zero byte o senza
    tabelle), 'occupato' (bloccato da un altro programma per piu' di 'attesa'
    secondi: non e' un guasto) o 'danneggiato'. Non crea mai il file."""
    if not os.path.exists(percorso):
        return 'mancante', ''
    try:
        dimensione = os.path.getsize(percorso)
        with open(percorso, 'rb') as f:
            testa = f.read(16)
    except OSError as e:
        return 'occupato', str(e)
    # con il giornale di un salvataggio interrotto decide SQLite: aprendo il file lo
    # rimette com'era, anche la testa scritta a meta' da una corrente saltata
    giornale = os.path.exists(percorso + '-journal')
    if dimensione == 0 and not giornale:
        return 'vuoto', 'il file è vuoto (0 byte)'
    if dimensione and testa != INTESTAZIONE and not giornale:
        return 'danneggiato', 'il file non è un database'
    try:
        c = sqlite3.connect(percorso, timeout=attesa)
        try:
            righe = c.execute('PRAGMA %s(20)' % ('integrity_check' if completo else 'quick_check')).fetchall()
            tabelle = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        finally:
            c.close()
    except sqlite3.OperationalError as e:
        testo = str(e).lower()
        if any(p in testo for p in ('locked', 'busy', 'unable to open', 'readonly', 'disk i/o')):
            return 'occupato', str(e)
        return 'danneggiato', str(e)
    except sqlite3.DatabaseError as e:
        return 'danneggiato', str(e)
    esiti = [str(r[0]) for r in righe]
    if esiti != ['ok']:
        return 'danneggiato', '; '.join(esiti[:3])
    if not tabelle:
        return 'vuoto', 'il database non ha tabelle'
    return 'ok', ''


def _integro(percorso):
    try:
        backup._verifica(percorso)
        return True
    except Exception:
        return False


def cartelle_backup(percorso_db, scelta=None, cartella=None):
    """Dove cercare le copie: la cartella scelta (passata, o ricordata nel
    diario se il database non si legge) e quella accanto al database."""
    uscita = []
    # il diario sta accanto al database
    ricordata = leggi_diario(cartella or os.path.dirname(os.path.abspath(percorso_db))).get('cartella_backup')
    for c in (scelta, ricordata if isinstance(ricordata, str) else None, backup.cartella_predefinita(percorso_db)):
        if c:
            c = os.path.abspath(c)
            if c not in uscita:
                uscita.append(c)
    return uscita


def copia_buona(cartelle):
    """La copia piu' recente che passa il controllo completo, o None. Quelle
    «prima del ripristino» per ultime: sono lo stato che qualcuno ha scelto
    di lasciare."""
    copie = []
    for c in cartelle:
        copie += backup.elenco(c)
    # per ultime anche le copie «del futuro»: fatte con l'orologio del PC avanti, la data nel
    # nome non dice quanto sono recenti, e messe prima sarebbero rimesse al posto di una buona
    domani = datetime.now() + timedelta(days=1)
    copie.sort(key=lambda x: (x['quando'] > domani, x['motivo'] == 'prima-del-ripristino',
                              -x['quando'].timestamp()))
    for x in copie:
        if _integro(x['percorso']):
            return x
        logging.warning('autoriparazione: la copia %s non passa il controllo', x['nome'])
    return None


def _file_del_database(percorso):
    """Il database e i file che SQLite gli tiene accanto."""
    return [p for p in (percorso, percorso + '-journal', percorso + '-wal', percorso + '-shm') if os.path.exists(p)]


def _metti_da_parte(percorso, momento):
    """Copia il database com'e' (con il suo giornale) in backup\\danneggiati.
    Restituisce la cartella. Non si cancella mai niente: serve all'assistenza."""
    return os.path.dirname(backup.copia_grezza(percorso, momento))


GIORNI_DANNEGGIATI = 90       # «Svuota» toglie solo i file messi da parte da piu' di tre mesi


def _file_danneggiati(percorso_db):
    """[(percorso, quando, byte)] dei file in backup\\danneggiati (database e giornali).
    'quando' viene dal nome (danneggiato-AAAA-MM-GG_HHMMSS.db, come li scrive
    backup.copia_grezza), altrimenti dalla data del file."""
    cartella = os.path.join(backup.cartella_predefinita(percorso_db), backup.DANNEGGIATI)
    try:
        nomi = os.listdir(cartella)
    except OSError:
        return []
    uscita = []
    for nome in nomi:
        percorso = os.path.join(cartella, nome)
        if not os.path.isfile(percorso):
            continue
        m = re.match(r'danneggiato-(\d{4}-\d{2}-\d{2}_\d{6})\.db', nome)
        try:
            quando = (datetime.strptime(m.group(1), '%Y-%m-%d_%H%M%S') if m
                      else datetime.fromtimestamp(os.path.getmtime(percorso)))
            uscita.append((percorso, quando, os.path.getsize(percorso)))
        except (ValueError, OSError, OverflowError):
            continue
    return uscita


def testo_byte(byte):
    """«3 KB», «12,5 MB»: per la pagina e il diario."""
    if byte < 1048576:
        return '%d KB' % max(1, byte // 1024) if byte else '0 KB'
    return ('%.1f MB' % (byte / 1048576)).replace('.', ',')


def dimensione_danneggiati(percorso_db, piu_vecchi_di_giorni=GIORNI_DANNEGGIATI, adesso=None):
    """Quanto occupa backup\\danneggiati: file e byte in tutto, e quelli «vecchi»
    (messi da parte da piu' di 'piu_vecchi_di_giorni' giorni: quelli che «Svuota»
    toglie), con i testi pronti per la pagina."""
    limite = (adesso or datetime.now()) - timedelta(days=piu_vecchi_di_giorni)
    tutti = _file_danneggiati(percorso_db)
    vecchi = [x for x in tutti if x[1] < limite]
    byte, byte_vecchi = sum(b for _, _, b in tutti), sum(b for _, _, b in vecchi)
    return {'file': len(tutti), 'byte': byte, 'testo': testo_byte(byte),
            'vecchi': len(vecchi), 'byte_vecchi': byte_vecchi, 'testo_vecchi': testo_byte(byte_vecchi)}


def svuota_danneggiati(percorso_db, piu_vecchi_di_giorni=GIORNI_DANNEGGIATI, adesso=None):
    """Cancella i file rovinati messi da parte da piu' di 'piu_vecchi_di_giorni'
    giorni; quelli recenti restano (possono servire all'assistenza). Solo su
    richiesta, dalla pagina Controllo del programma: il programma da solo non
    cancella mai niente. Restituisce (file cancellati, byte liberati, file che non
    si sono potuti cancellare) e, se ha tolto qualcosa, lo annota nel diario."""
    limite = (adesso or datetime.now()) - timedelta(days=piu_vecchi_di_giorni)
    cancellati, liberati, non_riusciti = 0, 0, 0
    for percorso, quando, byte in _file_danneggiati(percorso_db):
        if quando >= limite:
            continue
        try:
            os.remove(percorso)
        except OSError:
            logging.exception('autoriparazione: file rovinato non cancellato: %s', percorso)
            non_riusciti += 1
            continue
        cancellati += 1
        liberati += byte
    if cancellati:
        annota('Svuotati, su richiesta, i file rovinati messi da parte da più di %d giorni: %d file, %s liberati%s'
               % (piu_vecchi_di_giorni, cancellati, testo_byte(liberati),
                  '' if not non_riusciti else ' (%d non si sono potuti cancellare)' % non_riusciti), 'ok', tipo='danneggiati')
    return cancellati, liberati, non_riusciti


def _pagina_con_righe(percorso, numero):
    """La pagina 'numero' del file e' una pagina di una tabella con delle righe?
    (Il tipo della pagina e' il suo primo byte: 13 foglia e 5 interna di una
    tabella; 10 e 2 sono di un indice; le altre non hanno dati.) True anche se
    non si legge: nel dubbio, dati."""
    try:
        with open(percorso, 'rb') as f:
            testa = f.read(100)
            misura = int.from_bytes(testa[16:18], 'big')
            misura = 65536 if misura == 1 else misura
            f.seek((numero - 1) * misura + (100 if numero == 1 else 0))
            pagina = f.read(5)
    except (OSError, ValueError):
        return True
    if len(pagina) < 5:
        return True
    return pagina[0] in (0x0D, 0x05) and int.from_bytes(pagina[3:5], 'big') > 0


def _solo_indici(percorso):
    """Il controllo di SQLite trova guasti solo negli indici (o in pagine che
    non contengono dati)? Allora le tabelle sono intere e, rifatti gli indici
    dai dati, non si perde niente. False se non si sa.

    Attenzione alle pagine «never used»: puo' essere una pagina di una tabella
    con le sue righe rimasta fuori dall'albero (una scrittura persa quando e'
    saltata la corrente: la pagina interna torna com'era prima e le righe piu'
    recenti non si raggiungono piu'). Quelle sono righe perse, non spazio
    vuoto: la revisione della 1.11 l'ha trovato, prima diceva «niente perso»."""
    try:
        c = sqlite3.connect(percorso)
        try:
            indici = c.execute("SELECT name, rootpage FROM sqlite_master WHERE type = 'index'").fetchall()
            # SQLite mette piu' messaggi in una riga sola, uno per linea
            messaggi = [x.strip() for r in c.execute('PRAGMA quick_check(200)').fetchall()
                        for x in str(r[0]).splitlines() if x.strip()]
        finally:
            c.close()
    except sqlite3.Error:
        return False
    radici = {r for _, r in indici if r}
    nomi = {n for n, _ in indici}
    for m in messaggi:
        if m == 'ok' or m.startswith('*** in database'):
            continue
        albero = re.match(r'Tree (\d+) page', m)
        if albero:
            if int(albero.group(1)) in radici:
                continue
            return False
        indice = re.search(r'\bindex (\S+)', m)
        if indice and indice.group(1) in nomi:
            continue
        pagina = re.match(r'Page (\d+):? (?:is )?never used', m)
        if pagina:
            if _pagina_con_righe(percorso, int(pagina.group(1))):
                return False
            continue
        if re.match(r'(Freelist|freelist)', m):
            continue
        return False
    return True


def _ricostruisci(danneggiato, lavoro):
    """Prova a rifare il database senza perdere niente. (percorso, modo) o
    (None, None). VACUUM INTO legge tutte le righe e rifa' tabelle e indici;
    se una pagina dei dati non si legge si ferma, e allora non serve. Copia
    pero' gli indici cosi' come sono (l'ottimizzazione «xfer» di SQLite): con
    un indice rovinato si ferma anche lui, e ci pensa il recupero tabella per
    tabella, che gli indici li rifa' dai dati."""
    nuovo = os.path.join(lavoro, 'ricostruito.db')
    try:
        c = sqlite3.connect(danneggiato)
        try:
            c.execute('VACUUM INTO ?', (nuovo,))
        finally:
            c.close()
        if _integro(nuovo):
            return nuovo, 'ricostruito'
    except sqlite3.Error as e:
        logging.info('autoriparazione: VACUUM INTO non riuscito: %s', e)
    secondo = os.path.join(lavoro, 'indici.db')
    try:
        for p in _file_del_database(danneggiato):
            shutil.copyfile(p, secondo + p[len(danneggiato):])
        c = sqlite3.connect(secondo)
        try:
            c.execute('REINDEX')
            c.commit()
        finally:
            c.close()
        if _integro(secondo):
            return secondo, 'indici rifatti'
    except sqlite3.Error as e:
        logging.info('autoriparazione: REINDEX non riuscito: %s', e)
    return None, None


def _copia_tabella(sorgente, destinazione, nome, colonne):
    """Copia le righe che si leggono, saltando i punti rotti. (copiate, punti
    rotti). Ogni volta che una lettura si ferma si riparte dalla prima riga
    leggibile dopo; se si ferma di nuovo senza aver copiato niente, la riga
    successiva si salta: cosi' si va sempre avanti."""
    segnaposto = ', '.join('?' * colonne)
    copiate, problemi, ultimo, ultimo_al_guasto = 0, 0, 0, None
    while True:
        try:
            cursore = sorgente.execute('SELECT rowid, * FROM "%s" WHERE rowid > ? ORDER BY rowid' % nome, (ultimo,))
            while True:
                righe = cursore.fetchmany(200)
                if not righe:
                    return copiate, problemi
                for r in righe:
                    destinazione.execute('INSERT OR IGNORE INTO "%s" VALUES (%s)' % (nome, segnaposto), r[1:])
                    ultimo = r[0]
                    copiate += 1
        except sqlite3.DatabaseError:
            problemi += 1
            if problemi > 1000:
                return copiate, problemi
            if ultimo == ultimo_al_guasto:
                ultimo += 1                  # nessun passo avanti: la riga dopo non si legge
            ultimo_al_guasto = ultimo
            prossima = None
            for salto in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 5000, 20000, 100000, 1000000):
                try:
                    r = sorgente.execute('SELECT rowid FROM "%s" WHERE rowid >= ? ORDER BY rowid LIMIT 1' % nome,
                                         (ultimo + salto,)).fetchone()
                except sqlite3.DatabaseError:
                    continue
                if r is None:
                    return copiate, problemi
                prossima = r[0]
                break
            if prossima is None:
                return copiate, problemi
            ultimo = prossima - 1
            ultimo_al_guasto = ultimo


def _recupera(danneggiato, lavoro):
    """Recupero tabella per tabella di quello che si legge. (percorso,
    righe copiate, problemi) o (None, 0, problemi) se non si legge nemmeno
    l'elenco delle tabelle."""
    nuovo = os.path.join(lavoro, 'recuperato.db')
    src = sqlite3.connect(danneggiato)
    try:
        schema = src.execute("SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL").fetchall()
    except sqlite3.DatabaseError as e:
        src.close()
        return None, 0, [str(e)]
    problemi, copiate = [], 0
    dst = sqlite3.connect(nuovo)
    try:
        tabelle = [(n, q) for t, n, q in schema if t == 'table' and not n.startswith('sqlite_')]
        if not any(n == 'appuntamenti' for n, _ in tabelle):
            return None, 0, ['la tabella degli appuntamenti non si legge']
        for nome, ddl in tabelle:
            try:
                dst.execute(ddl)
                colonne = len(dst.execute('PRAGMA table_info("%s")' % nome).fetchall())
                n, rotte = _copia_tabella(src, dst, nome, colonne)
                copiate += n
                if rotte:
                    problemi.append('%s: %d punti non leggibili' % (nome, rotte))
            except sqlite3.DatabaseError as e:
                problemi.append('%s: %s' % (nome, e))
        for tipo, nome, ddl in schema:
            if tipo in ('index', 'view', 'trigger'):
                try:
                    dst.execute(ddl)
                except sqlite3.DatabaseError as e:
                    problemi.append('%s %s: %s' % (tipo, nome, e))
        dst.commit()
    finally:
        dst.close()
        src.close()
    if not _integro(nuovo):
        return None, copiate, problemi + ['il recupero non passa il controllo']
    return nuovo, copiate, problemi


def _metti_al_posto(sorgente, percorso, motore=None):
    backup.metti_al_posto(sorgente, percorso, motore)


def _quando(copia):
    return copia['quando'].strftime('%d/%m/%Y alle %H:%M')


def ripara(percorso, cartelle=None, motore=None, esito=None):
    """Ripara il database se serve. None se non c'era niente da fare (anche
    un database nuovo, al primo avvio), altrimenti l'evento scritto nel
    diario. Il chiamante tiene fermi i salvataggi, se il programma e' aperto."""
    esito, dettaglio = esito or controlla_database(percorso)
    if esito in ('ok', 'occupato'):
        return None
    cartelle = cartelle or cartelle_backup(percorso)
    momento = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    cartella_dati = os.path.dirname(os.path.abspath(percorso))
    if esito in ('mancante', 'vuoto'):
        copia = copia_buona(cartelle)
        if copia is None:
            return None                  # il primo avvio: si comincia con un database nuovo
        if esito == 'vuoto':
            _metti_da_parte(percorso, momento)
        _metti_al_posto(copia['percorso'], percorso, motore)
        return annota('Il database %s: è stata rimessa la copia di sicurezza del %s. Gli appuntamenti '
                      'salvati dopo quell\'ora vanno ricontrollati.' % (
                          'non c\'era' if esito == 'mancante' else 'era vuoto', _quando(copia)),
                      'attenzione', dettaglio, cartella_dati)
    # danneggiato
    lavoro = os.path.join(cartella_dati, 'riparazione-%s' % momento)
    os.makedirs(lavoro, exist_ok=True)
    try:
        parte = _metti_da_parte(percorso, momento)
        copia_lavoro = os.path.join(lavoro, 'danneggiato.db')
        for p in _file_del_database(percorso):
            shutil.copyfile(p, copia_lavoro + p[len(percorso):])
        # «senza perdere niente» si dice solo se il controllo trova guasti solo negli
        # indici: una ricostruzione riuscita non basta (le righe di una pagina rimasta
        # fuori dall'albero non le legge nessuno, e sparirebbero senza dirlo)
        solo_indici = _solo_indici(copia_lavoro)
        nuovo, modo = _ricostruisci(copia_lavoro, lavoro)
        if nuovo and solo_indici:
            _metti_al_posto(nuovo, percorso, motore)
            return annota('Il database era danneggiato ed è stato riparato senza perdere niente (%s). '
                          'Il file di prima è in %s.' % (modo, parte), 'ok', dettaglio, cartella_dati)
        recuperato, righe, problemi = _recupera(copia_lavoro, lavoro)
        if nuovo and not solo_indici:
            # ricostruito, ma qualcosa puo' mancare: vale come un recupero parziale
            recuperato, problemi = nuovo, problemi + ['righe forse rimaste fuori (pagine senza albero)']
        if recuperato and not problemi and solo_indici:
            # tutte le righe lette, i guasti erano solo negli indici: niente perso
            _metti_al_posto(recuperato, percorso, motore)
            return annota('Il database era danneggiato ed è stato riparato senza perdere niente (indici rifatti '
                          'dai dati). Il file di prima è in %s.' % parte, 'ok', dettaglio, cartella_dati)
        copia = copia_buona(cartelle)
        if copia is not None:
            if recuperato:
                shutil.copyfile(recuperato, os.path.join(parte, 'recuperato-%s.db' % momento))
            _metti_al_posto(copia['percorso'], percorso, motore)
            return annota('Il database era danneggiato e non si poteva riparare per intero: è stata rimessa '
                          'la copia di sicurezza del %s. Gli appuntamenti salvati dopo quell\'ora vanno '
                          'ricontrollati. Il file danneggiato%s è in %s, per l\'assistenza.' % (
                              _quando(copia), ' e quello che se ne è recuperato' if recuperato else '', parte),
                          'attenzione', '%s; %s' % (dettaglio, '; '.join(problemi[:5])), cartella_dati)
        if recuperato:
            _metti_al_posto(recuperato, percorso, motore)
            return annota('Il database era danneggiato e non c\'erano copie di sicurezza: è stato recuperato '
                          'quello che si leggeva (%d righe). Qualche dato può mancare: chiamare l\'assistenza. '
                          'Il file danneggiato è in %s.' % (righe, parte),
                          'errore', '; '.join(problemi[:5]), cartella_dati)
        # niente da recuperare e nessuna copia: il programma riparte vuoto, il file resta da parte
        if motore is not None:
            motore.dispose()
        for p in _file_del_database(percorso):
            os.remove(p)
        return annota('Il database era danneggiato, non si leggeva e non c\'erano copie di sicurezza: il '
                      'programma riparte vuoto. Il file danneggiato è in %s: chiamare l\'assistenza.' % parte,
                      'errore', dettaglio, cartella_dati)
    finally:
        shutil.rmtree(lavoro, ignore_errors=True)


def pulisci_avanzi(percorso_db, cartelle=None):
    """Quello che resta di un lavoro interrotto (il programma chiuso a meta'):
    copie .parziale, cartelle di riparazione, il .nuovo di una sostituzione.
    Solo all'avvio, prima che partano i backup. Restituisce quanti."""
    n = 0
    cartella_dati = os.path.dirname(os.path.abspath(percorso_db))
    for c in cartelle or cartelle_backup(percorso_db):
        try:
            nomi = os.listdir(c)
        except OSError:
            continue
        for nome in nomi:
            if nome.endswith('.parziale') and nome.startswith('agende-'):
                try:
                    os.remove(os.path.join(c, nome))
                    n += 1
                except OSError:
                    pass
    try:
        nomi = os.listdir(cartella_dati)
    except OSError:
        nomi = []
    for nome in nomi:
        p = os.path.join(cartella_dati, nome)
        if nome.startswith('riparazione-') and os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
            n += 1
        elif nome == os.path.basename(percorso_db) + '.nuovo' or (
                nome.startswith(FILE_DIARIO + '.') and nome.endswith('.tmp')) or (
                nome.startswith(FILE_PID + '.') and nome.endswith('.tmp')):
            try:
                os.remove(p)
                n += 1
            except OSError:
                pass
    return n


def all_avvio(percorso_db):
    """I controlli prima di aprire il database: avanzi, integrita',
    riparazione. Restituisce l'evento della riparazione o None. Non ferma
    mai l'avvio: un guasto qui si scrive nel registro e si va avanti."""
    try:
        cartelle = cartelle_backup(percorso_db)
        # gli avanzi solo accanto al database: leggere all'avvio una cartella di rete spenta
        # farebbe aspettare (i .parziale nella cartella scelta non restano piu': li toglie la copia)
        pulisci_avanzi(percorso_db, [backup.cartella_predefinita(percorso_db)])
        esito, dettaglio = controlla_database(percorso_db)
        stato.update(controllo_db=datetime.now(), esito_db=esito, dettaglio_db=dettaglio)
        if esito == 'occupato':
            logging.warning('autoriparazione: database occupato all\'avvio: %s', dettaglio)
        evento = ripara(percorso_db, cartelle, esito=(esito, dettaglio))
        if evento:
            stato.update(esito_db=controlla_database(percorso_db)[0])
        return evento
    except Exception as e:
        logging.exception('autoriparazione: controllo del database all\'avvio')
        annota('Il controllo del database all\'avvio non è riuscito.', 'errore', str(e))
        return None


# ============================================================ un gestionale solo
def prendi_lucchetto(cartella):
    """Il file aperto e bloccato, o None se lo tiene gia' un altro gestionale.
    Il blocco lo toglie il sistema quando il processo finisce, comunque finisca."""
    percorso = os.path.join(cartella, FILE_LUCCHETTO)
    try:
        f = open(percorso, 'a+b')
    except OSError:
        return None
    try:
        f.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    return f


_avviato = [None]


def scrivi_pid(cartella, porta, fase):
    """Chi tiene il lucchetto, su che porta risponde e in che fase e' ('avvio'
    finche' non risponde, poi 'in servizio'; 'riparazione' mentre ripara il
    database), da quando, e l'ultimo battito."""
    adesso = datetime.now().isoformat(timespec='seconds')
    _avviato[0] = _avviato[0] or adesso
    try:
        _scrivi_json(os.path.join(cartella, FILE_PID), {
            'pid': os.getpid(), 'porta': porta, 'fase': fase, 'eseguibile': sys.executable,
            'quando': adesso, 'battito': adesso, 'avviato': _avviato[0]})
    except OSError:
        logging.exception('autoriparazione: %s non scritto', FILE_PID)


def batti(cartella=None, fase=None):
    """Il battito del gestionale principale (lo scrive il custode a ogni giro):
    chi clicca di nuovo l'icona capisce che il programma e' vivo anche se le
    pagine sono lente. Con 'fase' cambia anche la fase (e da quando)."""
    cartella = cartella or _cartella[0]
    if not cartella or _istanza[0] is None:
        return
    info = leggi_pid(cartella)
    if info.get('pid') != os.getpid():
        return
    adesso = datetime.now().isoformat(timespec='seconds')
    info['battito'] = adesso
    if fase and fase != info.get('fase'):
        info['fase'], info['quando'] = fase, adesso
    try:
        _scrivi_json(os.path.join(cartella, FILE_PID), info)
    except OSError:
        logging.exception('autoriparazione: battito non scritto')


def _secondi_da(testo):
    """Da quanti secondi (dalla data scritta nel file), o None se non si legge."""
    try:
        return (datetime.now() - datetime.fromisoformat(testo)).total_seconds()
    except (TypeError, ValueError):
        return None


def leggi_pid(cartella):
    try:
        with open(os.path.join(cartella, FILE_PID), encoding='utf-8') as f:
            dati = json.load(f)
    except (OSError, ValueError):
        return {}
    return dati if isinstance(dati, dict) else {}


def porta_in_uso(porta):
    with socket.socket() as s:
        s.settimeout(0.4)
        return s.connect_ex(('127.0.0.1', porta)) == 0


def salute(porta, attesa=5.0):
    """La risposta di /salute del gestionale su quella porta, o None se non
    risponde (o non e' il gestionale)."""
    try:
        c = http.client.HTTPConnection('127.0.0.1', porta, timeout=attesa)
        try:
            c.request('GET', '/salute', headers={'Host': '127.0.0.1:%d' % porta})
            r = c.getresponse()
            if r.status != 200:
                return None
            dati = json.loads(r.read(4096).decode('utf-8'))
        finally:
            c.close()
    except (OSError, ValueError, http.client.HTTPException):
        return None
    return dati if isinstance(dati, dict) and dati.get('programma') == PROGRAMMA else None


def _stesso_nome(a, b):
    a, b = os.path.basename(a or '').lower(), os.path.basename(b or '').lower()
    if not a or not b:
        return False
    if a == b:
        return True
    # in prova, python.exe e pythonw.exe (o python3 e python3.13) sono lo stesso programma
    return a.startswith('python') and b.startswith('python')


def _stesso_percorso(a, b):
    """Lo stesso eseguibile, con il percorso intero (1.11: il solo nome,
    «Gestionale.exe», puo' essere anche di un altro programma)."""
    a, b = os.path.normcase(os.path.abspath(a or '')), os.path.normcase(os.path.abspath(b or ''))
    return a == b or (os.path.dirname(a) == os.path.dirname(b) and _stesso_nome(a, b))


def _processo_windows(pid):
    """(percorso dell'eseguibile, avvio come datetime) del processo, o None
    se non si legge (allora vale il controllo con tasklist)."""
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)           # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return None
        try:
            buf = ctypes.create_unicode_buffer(1024)
            n = wintypes.DWORD(1024)
            if not k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
                return None
            tempi = [wintypes.FILETIME() for _ in range(4)]
            if not k32.GetProcessTimes(h, *[ctypes.byref(t) for t in tempi]):
                return None
            centinaia = (tempi[0].dwHighDateTime << 32) | tempi[0].dwLowDateTime   # dal 1601, 100 ns
            avvio = datetime(1601, 1, 1) + timedelta(microseconds=centinaia // 10)
            # l'ora del sistema e' UTC: in ora locale come i datetime del programma
            avvio = avvio + (datetime.now() - datetime.utcnow())
            return buf.value, avvio
        finally:
            k32.CloseHandle(h)
    except Exception:
        return None


def _avvio_linux(pid):
    """L'ora di avvio del processo (da /proc), o None."""
    try:
        with open('/proc/%d/stat' % pid) as f:
            campi = f.read().rsplit(')', 1)[1].split()
        with open('/proc/stat') as f:
            boot = next(int(r.split()[1]) for r in f if r.startswith('btime'))
        return datetime.fromtimestamp(boot + int(campi[19]) / os.sysconf('SC_CLK_TCK'))
    except (OSError, ValueError, IndexError, StopIteration):
        return None


def processo_nostro(pid, avviato_entro=None):
    """Il processo 'pid' esiste ed e' il gestionale (lo stesso eseguibile, con
    il percorso)? Con 'avviato_entro' (quando il gestionale ha scritto il file)
    anche: avviato prima di allora; un processo nato dopo ha solo riusato il
    numero. Mai chiudere un programma che non e' il nostro."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0 or pid == os.getpid():
        return False
    margine = timedelta(seconds=5)
    if os.name == 'nt':
        dati = _processo_windows(pid)
        if dati is not None:
            percorso, avvio = dati
            if not _stesso_percorso(percorso, sys.executable):
                return False
            return avviato_entro is None or avvio <= avviato_entro + margine
        try:
            r = subprocess.run(['tasklist', '/FI', 'PID eq %d' % pid, '/FO', 'CSV', '/NH'],
                               capture_output=True, text=True, errors='replace', timeout=20,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except (OSError, subprocess.SubprocessError):
            return False
        riga = (r.stdout or '').strip().splitlines()
        if not riga or not riga[0].startswith('"'):
            return False                         # "Nessuna attivita' in esecuzione..."
        return _stesso_nome(riga[0].split('","')[0].strip('"'), sys.executable)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        if not _stesso_percorso(os.path.realpath('/proc/%d/exe' % pid), os.path.realpath(sys.executable)):
            return False
    except OSError:
        return False
    avvio = _avvio_linux(pid)
    return avviato_entro is None or avvio is None or avvio <= avviato_entro + margine


def chiudi_processo(pid):
    if os.name == 'nt':
        # senza /T: il browser aperto dal gestionale e' un suo «figlio», e /T chiuderebbe
        # anche quello, con le pagine della segreteria
        subprocess.run(['taskkill', '/F', '/PID', str(int(pid))], capture_output=True, timeout=30,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    else:
        import signal
        try:
            os.kill(int(pid), signal.SIGKILL)
        except OSError:
            pass


def _sana(risposta):
    """Il gestionale risponde ed e' utilizzabile: non tutti i suoi thread sono
    fermi su una pagina da minuti."""
    return bool(risposta) and not risposta.get('bloccato')


def entra(cartella, porta=None, riserva=None, attesa=15.0, tentativi=2, aspetta_chiusura=20.0,
          aspetta_occupato=None):
    """Decide all'avvio: questo e' il gestionale principale o ce n'e' gia'
    uno? Restituisce dict(principale, porta, lucchetto, nota):
    - principale False: ce n'e' gia' uno che risponde (o che sta partendo),
      si apre solo la pagina su 'porta';
    - principale True: si avvia il server su 'porta'; 'lucchetto' va tenuto
      aperto finche' il programma gira."""
    porta = porta or PORTA
    riserva = PORTE_DI_RISERVA if riserva is None else riserva
    imposta_cartella(cartella)
    f = prendi_lucchetto(cartella)
    nota = ''
    if f is None:
        info = leggi_pid(cartella)
        sua = info.get('porta') if isinstance(info.get('porta'), int) else porta
        fine_attesa = orologio.monotonic() + (ATTESA_OCCUPATO if aspetta_occupato is None else aspetta_occupato)
        while True:
            for _ in range(max(1, tentativi)):
                if _sana(salute(sua, attesa)):
                    return dict(principale=False, porta=sua, lucchetto=None, nota='già aperto')
            info = leggi_pid(cartella)
            sua = info.get('porta') if isinstance(info.get('porta'), int) else sua
            da_quando = _secondi_da(info.get('quando'))
            if info.get('fase') in ('avvio', 'riparazione') and da_quando is not None and da_quando < ATTESA_AVVIO:
                return dict(principale=False, porta=sua, lucchetto=None,
                            nota='sta partendo' if info.get('fase') == 'avvio' else 'sta riparando')
            # 1.11: le pagine non rispondono ma il custode batte: e' occupato (salvataggi in coda,
            # una riparazione lunga), non bloccato. Si aspetta; fermo da troppo, si chiude
            battito = _secondi_da(info.get('battito'))
            if battito is None or battito > BATTITO_SCADUTO or orologio.monotonic() > fine_attesa:
                break
            orologio.sleep(min(5.0, max(0.2, fine_attesa - orologio.monotonic())))
        pid = info.get('pid')
        try:
            avviato = datetime.fromisoformat(info.get('avviato') or info.get('quando') or '')
        except (TypeError, ValueError):
            avviato = None
        if not processo_nostro(pid, avviato):
            # il lucchetto lo tiene qualcuno che non si riconosce: non si chiude niente
            logging.warning('autoriparazione: il gestionale aperto non risponde, ma il processo %s non si '
                            'riconosce: non lo chiudo', pid)
            return dict(principale=False, porta=sua, lucchetto=None, nota='non risponde')
        chiudi_processo(pid)
        fine = orologio.monotonic() + aspetta_chiusura
        while f is None and orologio.monotonic() < fine:
            orologio.sleep(0.2)
            f = prendi_lucchetto(cartella)
        if f is None:
            annota('Il programma aperto non rispondeva e non si è chiuso: riavviare il computer.', 'errore',
                   'processo %s' % pid, cartella)
            return dict(principale=False, porta=sua, lucchetto=None, nota='non si chiude')
        nota = 'chiuso il gestionale bloccato'
        annota('Il programma non rispondeva: è stato chiuso e riaperto da solo.', 'ok',
               'processo %s, porta %s' % (pid, sua), cartella)
        # la porta del processo chiuso si libera appena il sistema ha finito
        fine = orologio.monotonic() + 10
        while porta_in_uso(sua) and orologio.monotonic() < fine:
            orologio.sleep(0.2)
    scelta = porta
    if porta_in_uso(porta):
        libere = [p for p in riserva if not porta_in_uso(p)]
        if libere:
            scelta = libere[0]
            annota('La porta %d era occupata da un altro programma: il gestionale si apre su '
                   'http://127.0.0.1:%d/.' % (porta, scelta), 'attenzione', '', cartella)
    stato['porta'] = scelta
    _istanza[0] = f
    scrivi_pid(cartella, scelta, 'avvio')
    return dict(principale=True, porta=scelta, lucchetto=f, nota=nota)


# ============================================================ il custode
def sorveglia(nome, attuale, riavvia):
    """Un lavoro in sottofondo da tenere vivo: attuale() da' il thread (o
    None), riavvia() lo fa ripartire e da' il thread nuovo."""
    _sorvegliati[nome] = (attuale, riavvia)


def lavori():
    """[(nome, descrizione, vivo)] dei lavori sorvegliati, per la pagina."""
    uscita = []
    for nome, (attuale, _) in sorted(_sorvegliati.items()):
        try:
            t = attuale()
        except Exception:
            t = None
        uscita.append((nome, NOMI_LAVORI.get(nome, nome), bool(t is not None and t.is_alive())))
    return uscita


def chiedi_controllo():
    """Un errore del database in una pagina: il custode controlla subito."""
    _sveglia.set()


def controlla_lavori():
    note = []
    for nome, (attuale, riavvia) in list(_sorvegliati.items()):
        try:
            t = attuale()
            if t is not None and t.is_alive():
                continue
            riavvia()
            stato['riavvii'] += 1
            note.append(annota('Il lavoro in sottofondo per %s si era fermato: è ripartito da solo.' % (
                NOMI_LAVORI.get(nome, nome)), 'ok'))
        except Exception as e:
            logging.exception('autoriparazione: %s non riparte', nome)
            note.append(annota('Il lavoro in sottofondo per %s si è fermato e non riparte: chiudere e '
                               'riaprire il programma.' % NOMI_LAVORI.get(nome, nome), 'errore', str(e)))
    return note


def controlla_spazio(cartella):
    try:
        libero = shutil.disk_usage(cartella).free
    except OSError:
        return None
    stato['spazio_libero'] = libero
    return libero


def controlla_e_ripara(percorso_db, motore, lucchetto, dopo=None, completo=False):
    """Il controllo del database a programma aperto; se e' danneggiato, la
    riparazione con i salvataggi fermi. dopo() riporta il database alla
    versione del programma (una copia di sicurezza puo' essere vecchia).
    Restituisce (esito, evento)."""
    esito, dettaglio = controlla_database(percorso_db, completo=completo)
    stato.update(controllo_db=datetime.now(), esito_db=esito, dettaglio_db=dettaglio)
    if esito in ('ok', 'occupato'):
        return esito, None
    with lucchetto:
        esito, dettaglio = controlla_database(percorso_db, completo=completo)   # con i salvataggi fermi
        # mentre ripara le pagine possono aspettare: chi clicca di nuovo l'icona non lo chiude
        batti(fase='riparazione')
        try:
            evento = ripara(percorso_db, motore=motore, esito=(esito, dettaglio))
        except Exception as e:
            # per esempio Windows che non lascia sostituire un file ancora aperto: all'avvio si puo'
            logging.exception('autoriparazione: riparazione a programma aperto')
            stato.update(esito_db='danneggiato', dettaglio_db=str(e))
            return esito, annota('Il database ha un problema e a programma aperto non si è riparato: chiudere '
                                 'e riaprire il programma, si ripara all\'avvio.', 'errore', str(e))
        if evento is not None and dopo is not None:
            try:
                dopo()
            except Exception as e:
                logging.exception('autoriparazione: dopo la riparazione')
                annota('Dopo la riparazione il database non si è aggiornato: chiudere e riaprire il programma.',
                       'errore', str(e))
    batti(fase='in servizio')
    stato.update(esito_db=controlla_database(percorso_db)[0])
    return esito, evento


# ============================================================ il riavvio da solo
def imposta_riavvio(comando, occupato=None, ferme=None, risorse=None, fili=4):
    """Lo chiama l'avvio del programma. comando: gli argomenti per farlo
    ripartire; occupato(): True se non e' il momento (un aggiornamento in
    corso); ferme(): da quanti secondi e' ferma ciascuna pagina in corso;
    risorse(): False se mancano i file del programma; fili: le richieste che il
    server serve insieme."""
    _riavvio.update(comando=comando, occupato=occupato, ferme=ferme, risorse=risorse, fili=fili)


def motivo_per_riavviare():
    """Perche' il programma va fatto ripartire, o None. Solo guasti che da
    dentro non si riparano: i file del programma spariti (la pulizia dei file
    temporanei di Windows cancella la cartella in cui l'eseguibile si apre) o
    le pagine ferme da troppo tempo (il programma non risponde piu')."""
    try:
        if _riavvio['risorse'] is not None and not _riavvio['risorse']():
            return 'non trovava più i suoi file (forse cancellati dalla pulizia di Windows)'
        if _riavvio['ferme'] is not None:
            eta = _riavvio['ferme']()
            if sum(1 for x in eta if x > FERME_TANTE) >= max(1, _riavvio['fili'] - 1) or \
                    any(x > FERMA_UNA for x in eta):
                return 'era bloccato su una pagina da troppo tempo'
    except Exception:
        logging.exception('autoriparazione: controllo per il riavvio')
    return None


def _ambiente_pulito():
    # come per il Setup di «Aggiorna adesso»: senza le variabili dell'eseguibile
    # (_PYI_..., _MEI...) il programma riaperto si fermerebbe
    return {k: v for k, v in os.environ.items() if not k.upper().startswith(('_PYI_', '_MEI'))}


def _lancia(comando):
    """Fa ripartire il programma fra due secondi, staccato da questo, che
    intanto si chiude e libera porta e lucchetto."""
    if os.name == 'nt':
        cmd = os.path.join(os.environ.get('SystemRoot') or r'C:\Windows', 'System32', 'cmd.exe')
        riga = '"%s" /c ping -n 3 127.0.0.1 >nul & start "" %s' % (cmd, ' '.join('"%s"' % a for a in comando))
        subprocess.Popen(riga, env=_ambiente_pulito(), close_fds=True,
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    else:
        subprocess.Popen(['sh', '-c', 'sleep 2; exec "$@"', 'sh'] + list(comando), env=_ambiente_pulito(),
                         start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True)


def riavvia_programma(motivo, lancia=None, esci=None, adesso=None):
    """Chiude il programma e lo fa ripartire. False se non si e' fatto: senza
    comando (le prove, o il programma di prova), durante un aggiornamento, o
    dopo tre riavvii nell'ultima ora (allora lo dice e lascia fare a chi c'e')."""
    if not _riavvio['comando']:
        return False
    adesso = adesso or datetime.now()
    try:
        if _riavvio['occupato'] is not None and _riavvio['occupato']():
            return False
    except Exception:
        return False
    recenti = [e for e in eventi(adesso - timedelta(hours=1)) if e.get('tipo') in ('riavvio', 'troppi-riavvii')]
    if sum(1 for e in recenti if e.get('tipo') == 'riavvio') >= MASSIMO_RIAVVII_ORA:
        if not any(e.get('tipo') == 'troppi-riavvii' for e in recenti):
            annota('Il programma %s e si è già riavviato da solo %d volte in un\'ora: chiudere e riaprire il '
                   'programma (o riavviare il computer); se succede ancora, chiamare l\'assistenza.' % (
                       motivo, MASSIMO_RIAVVII_ORA), 'errore', tipo='troppi-riavvii')
        return False
    annota('Il programma %s: si è riavviato da solo.' % motivo, 'ok', tipo='riavvio')
    if _istanza[0] is not None:
        try:
            _istanza[0].close()              # il lucchetto: il programma che riparte lo trova libero
        except OSError:
            pass
        _istanza[0] = None
    try:
        (lancia or _lancia)(_riavvio['comando'])
    except Exception:
        logging.exception('autoriparazione: il programma non riparte')
        # si resta aperti: il lucchetto torna a questo programma (altrimenti un secondo clic
        # aprirebbe un altro gestionale sullo stesso database)
        _istanza[0] = prendi_lucchetto(_cartella[0]) if _cartella[0] else None
        return False
    logging.shutdown()
    (esci or os._exit)(0)
    return True


def un_giro(percorso_db, motore, lucchetto, dopo=None, forza_db=False, adesso=None):
    """Quello che il custode fa a ogni risveglio. Restituisce gli eventi."""
    adesso = adesso or datetime.now()
    note = controlla_lavori()
    if percorso_db:
        controlla_spazio(os.path.dirname(os.path.abspath(percorso_db)))
        ultimo = stato['controllo_db']
        if forza_db or ultimo is None or (adesso - ultimo).total_seconds() >= OGNI_CONTROLLO_DB:
            try:
                # chiamato da un errore «malformed»: il controllo completo. Quello veloce non
                # vede un indice che non corrisponde piu' ai dati (1.11)
                _, evento = controlla_e_ripara(percorso_db, motore, lucchetto, dopo, completo=forza_db)
                if evento:
                    note.append(evento)
            except Exception as e:
                logging.exception('autoriparazione: controllo del database')
                stato.update(esito_db='errore', dettaglio_db=str(e))
    motivo = motivo_per_riavviare()
    if motivo:
        riavvia_programma(motivo)
    batti()
    stato['ultimo_giro'] = adesso
    return note


_custode = [None]


def avvia_custode(percorso_db, motore, lucchetto, dopo=None, intervallo=None):
    if _custode[0] is not None and _custode[0].is_alive():
        return _custode[0]
    intervallo = intervallo or OGNI_GIRO

    def giro():
        while True:
            forza = _sveglia.wait(intervallo)
            _sveglia.clear()
            try:
                un_giro(percorso_db, motore, lucchetto, dopo, forza_db=forza)
            except Exception:
                logging.exception('autoriparazione: giro del custode')
    t = threading.Thread(target=giro, name='custode', daemon=True)
    t.start()
    _custode[0] = t
    return t


# ============================================================ per le pagine
def problemi_attuali():
    """I problemi che ci sono adesso (non quelli gia' riparati): [(livello, testo)]."""
    uscita = []
    if stato.get('schema_nuovo'):
        uscita.append(('errore', 'Il database è stato usato da una versione più nuova del programma: installare '
                                 'l\'ultima versione (Configura → Aggiornamenti, o il Setup nuovo).'))
    libero = stato.get('spazio_libero')
    if libero is not None and libero < SPAZIO_MINIMO:
        uscita.append(('errore', 'Sul disco restano solo %d MB liberi: liberare spazio, altrimenti i '
                                 'salvataggi e le copie di sicurezza non riescono.' % (libero // (1024 * 1024))))
    if stato.get('esito_db') == 'danneggiato':
        uscita.append(('errore', 'Il database ha un problema che non si è riparato da solo: chiudere e '
                                 'riaprire il programma; se resta, chiamare l\'assistenza.'))
    for nome, descrizione, vivo in lavori():
        if not vivo:
            uscita.append(('errore', 'Il lavoro in sottofondo per %s è fermo.' % descrizione))
    return uscita


def _impronta(testo):
    # hash() cambia a ogni avvio: la chiave di una notifica chiusa deve restare la stessa
    return '%08x' % zlib.crc32(testo.encode('utf-8'))


def notifiche(adesso, collegamento, giorni=3):
    """Le notifiche della campanella: le riparazioni degli ultimi giorni e i
    problemi di adesso. Ognuna con la sua chiave: chiusa una volta, non torna."""
    uscita = []
    for e in eventi(adesso - timedelta(days=giorni)):
        if e.get('tipo') == 'danneggiati':
            continue                   # l'ha chiesto chi usa il programma: non e' una riparazione da annunciare
        uscita.append({'chiave': 'autoripara-%s-%s' % (e['quando'].strftime('%Y%m%d%H%M%S'), _impronta(e['testo'])),
                       'titolo': 'Riparato da solo' if e['livello'] == 'ok' else 'Controllo del programma',
                       'testo': e['testo'], 'link': collegamento, 'azioni': [],
                       'livello': 'errore' if e['livello'] == 'errore' else 'normale'})
    for livello, testo in problemi_attuali():
        uscita.append({'chiave': 'autoripara-adesso-%s-%s' % (adesso.date().isoformat(), _impronta(testo)),
                       'titolo': 'Controllo del programma', 'testo': testo, 'link': collegamento,
                       'azioni': [], 'livello': livello})
    return uscita
