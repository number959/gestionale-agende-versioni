# -*- coding: utf-8 -*-
"""Backup automatico del database, dentro il programma.

La copia si fa con l'API di backup di SQLite, non copiando il file: cosi'
e' coerente anche se in quel momento qualcuno sta salvando un appuntamento.
Ogni copia viene aperta e verificata (PRAGMA integrity_check) prima di
prendere il posto definitivo; un file a meta' non finisce mai fra i backup.

Una copia al giorno, fatta da un thread che si sveglia ogni ora: il PC della
segreteria puo' restare acceso per settimane o essere spento ogni sera, e in
entrambi i casi la copia del giorno c'e'. Si tengono le ultime 30 copie
giornaliere piu' la prima di ciascuno degli ultimi 12 mesi.

Lo stato (ultima copia riuscita, ultimo errore) sta in memoria e non nel
database: una cartella di rete irraggiungibile non deve rallentare le pagine,
e un ripristino non deve riportare indietro anche lo stato dei backup.
"""
import logging
import os
import re
import shutil
import sqlite3
import threading
import time as orologio
from urllib.request import pathname2url
from datetime import datetime, date, timedelta

NOME = re.compile(r'agende-(\d{4}-\d{2}-\d{2})_(\d{6})(?:-([a-z0-9-]+))?\.db$')
COPIE_GIORNALIERE = 30
COPIE_MENSILI = 12
# 1.11: fra una copia del giorno e l'altra, una copia «recente» ogni due ore se il
# database e' cambiato: se un giorno serve rimettere una copia, si perdono al
# massimo due ore di lavoro invece di un giorno. Se ne tengono solo le ultime.
COPIE_RECENTI = 3
OGNI_RECENTE = timedelta(hours=2)
MOTIVO_RECENTE = 'recente'
DANNEGGIATI = 'danneggiati'

stato = {'ultimo_ok': None, 'ultimo_file': None, 'ultimo_errore': None, 'errore_il': None,
         'in_corso': False, 'riserva': None, 'orologio': None}
_lucchetto = threading.Lock()


def cartella_predefinita(percorso_db):
    return os.path.join(os.path.dirname(os.path.abspath(percorso_db)), 'backup')


def solo_lettura(percorso):
    """Una connessione che non crea il file se manca e non lo scrive (1.11:
    controllare una copia sparita lasciava un file vuoto al suo posto)."""
    return sqlite3.connect('file:%s?mode=ro' % pathname2url(os.path.abspath(percorso)), uri=True)


def _verifica(percorso):
    if not os.path.isfile(percorso):
        raise RuntimeError('la copia non c\'è più: %s' % os.path.basename(percorso))
    c = solo_lettura(percorso)
    try:
        esito = c.execute('PRAGMA integrity_check').fetchone()[0]
        tabelle = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        c.close()
    if esito != 'ok':
        raise RuntimeError('la copia non è integra: %s' % esito)
    if 'appuntamenti' not in tabelle:
        raise RuntimeError('il file non è un database del gestionale')


def esegui(percorso_db, cartella, motivo=''):
    """Fa una copia verificata. Restituisce il percorso del file."""
    if not os.path.exists(percorso_db):
        raise RuntimeError('database non trovato: %s' % percorso_db)
    with _lucchetto:
        stato['in_corso'] = True
        try:
            os.makedirs(cartella, exist_ok=True)
            adesso = datetime.now()
            nome = 'agende-%s%s.db' % (adesso.strftime('%Y-%m-%d_%H%M%S'),
                                       ('-' + motivo) if motivo else '')
            finale = os.path.join(cartella, nome)
            temporaneo = finale + '.parziale'
            # 1.11: una copia che non si scrive (disco pieno, chiavetta tolta) o che non passa
            # il controllo non lascia mai il suo .parziale
            try:
                sorgente = sqlite3.connect(percorso_db)
                copia = sqlite3.connect(temporaneo)
                try:
                    sorgente.backup(copia)
                finally:
                    copia.close()
                    sorgente.close()
                _verifica(temporaneo)
                os.replace(temporaneo, finale)
            except BaseException:
                try:
                    os.remove(temporaneo)
                except OSError:
                    pass
                raise
            # 1.11: l'orologio del PC indietro (una copia «del futuro» c'e' gia'): la
            # rotazione non deve cancellare la copia appena fatta, e la pagina lo dice
            futuro = [c for c in elenco(cartella) if c['quando'] > adesso + timedelta(days=1)]
            stato['orologio'] = futuro[0]['quando'] if futuro else None
            if not motivo:
                stato.update(ultimo_ok=adesso, ultimo_file=finale, ultimo_errore=None, errore_il=None)
            if not motivo or motivo == MOTIVO_RECENTE:
                ruota(cartella, proteggi=nome)
            return finale
        except Exception as e:
            if not motivo:
                stato.update(ultimo_errore=str(e), errore_il=datetime.now())
            raise
        finally:
            stato['in_corso'] = False


def elenco(cartella):
    """Le copie presenti, dalla piu' recente: dict(nome, percorso, quando, dimensione, motivo)."""
    uscita = []
    try:
        nomi = os.listdir(cartella)
    except OSError:
        return []
    for nome in nomi:
        m = NOME.match(nome)
        if not m:
            continue
        percorso = os.path.join(cartella, nome)
        try:
            dimensione = os.path.getsize(percorso)
        except OSError:
            continue
        quando = datetime.strptime(m.group(1) + m.group(2), '%Y-%m-%d%H%M%S')
        uscita.append({'nome': nome, 'percorso': percorso, 'quando': quando,
                       'dimensione': dimensione, 'motivo': m.group(3) or ''})
    return sorted(uscita, key=lambda x: x['quando'], reverse=True)


def da_tenere(copie, giornaliere=COPIE_GIORNALIERE, mensili=COPIE_MENSILI, recenti=COPIE_RECENTI):
    """Delle copie automatiche si tengono le ultime 'giornaliere' e la piu'
    vecchia di ciascuno degli ultimi 'mensili' mesi; delle «recenti» le ultime
    'recenti'. Le copie con un altro motivo (prima di un ripristino, prima di
    un aggiornamento) si tengono sempre."""
    automatiche = [c for c in copie if not c['motivo']]
    tenute = {c['nome'] for c in copie if c['motivo'] and c['motivo'] != MOTIVO_RECENTE}
    tenute |= {c['nome'] for c in [c for c in copie if c['motivo'] == MOTIVO_RECENTE][:recenti]}
    tenute |= {c['nome'] for c in automatiche[:giornaliere]}
    per_mese = {}
    for c in automatiche:                      # dalla piu' recente: resta la piu' vecchia
        per_mese[(c['quando'].year, c['quando'].month)] = c
    for chiave in sorted(per_mese, reverse=True)[:mensili]:
        tenute.add(per_mese[chiave]['nome'])
    return tenute


def ruota(cartella, proteggi=None):
    """Toglie le copie che non servono piu'. 'proteggi' (la copia appena
    fatta) non si toglie mai: con l'orologio del PC indietro sarebbe la piu'
    vecchia, e sparirebbe appena fatta."""
    copie = elenco(cartella)
    tenute = da_tenere(copie)
    if proteggi:
        tenute.add(proteggi)
    for c in copie:
        if c['nome'] not in tenute:
            try:
                os.remove(c['percorso'])
            except OSError as e:
                logging.warning('backup %s non eliminato: %s', c['nome'], e)


def fatto_oggi(cartella):
    oggi = date.today()
    return any(c['quando'].date() == oggi and not c['motivo'] for c in elenco(cartella))


def copia_grezza(percorso_db, momento=None):
    """Il database cosi' com'e' (con il suo giornale), copiato byte per byte in
    backup\\danneggiati accanto al database: per un database rovinato, che una
    copia vera (verificata) non la passerebbe. Non si cancella mai: serve
    all'assistenza. Restituisce il percorso della copia del database."""
    cartella = os.path.join(cartella_predefinita(percorso_db), DANNEGGIATI)
    os.makedirs(cartella, exist_ok=True)
    momento = momento or datetime.now().strftime('%Y-%m-%d_%H%M%S')
    principale = os.path.join(cartella, 'danneggiato-%s.db' % momento)
    for coda in ('', '-journal', '-wal', '-shm'):
        if os.path.exists(percorso_db + coda):
            shutil.copyfile(percorso_db + coda, principale + coda)
    return principale


def metti_al_posto(sorgente, percorso_db, motore=None):
    """Mette la copia 'sorgente' al posto del database. Con il programma aperto
    (motore) si scrive dentro il file che c'e' con l'API di backup di SQLite:
    chi ha il file aperto vede subito il contenuto nuovo (su Windows un file
    aperto non si sostituisce). Se il file e' troppo rovinato per riceverla
    (la testa illeggibile), o a programma chiuso, si sostituisce il file; i
    giornali del file vecchio vanno via prima (applicati al file nuovo lo
    rovinerebbero: chi chiama li ha gia' messi da parte, se servono)."""
    # 1.11: prima di tutto la copia da rimettere deve esserci ed essere buona. Una copia
    # sparita (tolta dalla rotazione mentre si ripristinava) veniva creata vuota da
    # sqlite3.connect e scritta al posto del database: si perdeva tutto
    _verifica(sorgente)
    if motore is not None:
        motore.dispose()
        try:
            src = solo_lettura(sorgente)
            dst = sqlite3.connect(percorso_db, timeout=30)
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()
            _verifica(percorso_db)
            motore.dispose()
            return
        except Exception as e:
            logging.info('copia dentro il database non riuscita (%s): si sostituisce il file', e)
        motore.dispose()
    for coda in ('-journal', '-wal', '-shm'):
        if os.path.exists(percorso_db + coda):
            os.remove(percorso_db + coda)
    provvisorio = percorso_db + '.nuovo'
    shutil.copyfile(sorgente, provvisorio)
    _verifica(provvisorio)                 # quello che prende il posto del database e' buono
    for i in range(50):
        try:
            os.replace(provvisorio, percorso_db)
            break
        except PermissionError:
            if i == 49:
                raise
            orologio.sleep(0.1)
    if motore is not None:
        motore.dispose()


def ripristina(percorso_db, file_backup, motore, cartella):
    """Rimette al suo posto una copia. Prima fa una copia di sicurezza del
    database attuale, cosi' anche un ripristino sbagliato si puo' annullare.
    Il chiamante deve tenere fermi i salvataggi (lucchetto) e chiudere le
    sessioni; qui si chiudono le connessioni del motore.

    1.11: se il database attuale e' rovinato la copia di sicurezza vera non
    riesce (non passa il controllo): prima il ripristino si fermava proprio
    quando serviva. Ora il database rovinato si copia cosi' com'e' fra i
    danneggiati e il ripristino va avanti."""
    _verifica(file_backup)
    try:
        sicurezza = esegui(percorso_db, cartella, 'prima-del-ripristino')
    except Exception:
        try:
            _verifica(percorso_db)
        except Exception as guasto:
            logging.warning('ripristino sopra un database rovinato (%s): copiato fra i danneggiati', guasto)
            sicurezza = copia_grezza(percorso_db)
        else:
            # 1.11: la cartella scelta non si raggiunge (chiavetta tolta): la copia di prima
            # del ripristino va accanto al database, come per «Aggiorna adesso»
            predefinita = cartella_predefinita(percorso_db)
            if os.path.normcase(os.path.abspath(cartella)) == os.path.normcase(os.path.abspath(predefinita)):
                raise
            sicurezza = esegui(percorso_db, predefinita, 'prima-del-ripristino')
    metti_al_posto(file_backup, percorso_db, motore)
    return sicurezza


def copia_del_giorno(percorso_db, cartella):
    """La copia del giorno, se manca, nella cartella scelta. Se quella non si
    raggiunge (chiavetta tolta, cartella di rete spenta) la copia va nella
    cartella accanto al database (1.11): meglio una copia li' che nessuna.
    Si riprova la cartella scelta a ogni giro; appena torna, la copia va di
    nuovo li'. Restituisce la cartella dove sta la copia del giorno."""
    predefinita = cartella_predefinita(percorso_db)
    if fatto_oggi(cartella):
        stato['riserva'] = None
        return cartella
    try:
        finale = esegui(percorso_db, cartella)
    except Exception as e:
        if os.path.abspath(cartella) == os.path.abspath(predefinita):
            raise
        errore = str(e)
        if not fatto_oggi(predefinita):
            finale = esegui(percorso_db, predefinita)
            logging.warning('backup nella cartella accanto al database (%s), quella scelta non va: %s', finale, errore)
        stato['riserva'] = {'cartella': cartella, 'errore': errore, 'il': datetime.now()}
        return predefinita
    stato['riserva'] = None
    logging.info('backup fatto: %s', finale)
    return cartella


def copia_recente(percorso_db, cartella, adesso=None):
    """Una copia «recente» se l'ultima copia della cartella ha piu' di due ore
    e il database e' cambiato dopo. Restituisce il file o None."""
    adesso = adesso or datetime.now()
    # le copie «del futuro» (fatte con l'orologio avanti) non contano come l'ultima
    copie = [c for c in elenco(cartella) if c['quando'] <= adesso + timedelta(days=1)]
    if not copie:
        return None
    ultima = copie[0]['quando']
    try:
        cambiato = datetime.fromtimestamp(os.path.getmtime(percorso_db))
    except OSError:
        return None
    if adesso - ultima < OGNI_RECENTE or cambiato <= ultima:
        return None
    finale = esegui(percorso_db, cartella, MOTIVO_RECENTE)
    logging.info('copia recente: %s', finale)
    return finale


def avvia_automatico(percorso_db, leggi_cartella, attesa_iniziale=90, intervallo=3600):
    """Thread che fa la copia del giorno se manca. leggi_cartella() restituisce
    la cartella scelta nelle impostazioni (si rilegge a ogni giro)."""
    def giro():
        orologio.sleep(attesa_iniziale)
        while True:
            try:
                cartella = copia_del_giorno(percorso_db, leggi_cartella() or cartella_predefinita(percorso_db))
                try:
                    copia_recente(percorso_db, cartella)
                except Exception as e:
                    logging.warning('copia recente non riuscita: %s', e)
                if stato['ultimo_ok'] is None:
                    recenti = elenco(cartella)
                    automatiche = [c for c in recenti if not c['motivo']]
                    if automatiche:
                        stato.update(ultimo_ok=automatiche[0]['quando'],
                                     ultimo_file=automatiche[0]['percorso'])
            except Exception as e:
                stato.update(ultimo_errore=str(e), errore_il=datetime.now())
                logging.error('backup non riuscito: %s', e)
            orologio.sleep(intervallo)
    t = threading.Thread(target=giro, name='backup', daemon=True)
    t.start()
    return t


def allarme(adesso=None):
    """Testo da mostrare in cima alla griglia se i backup non vanno, None
    altrimenti. Nessun allarme finche' il thread non ha fatto il primo giro."""
    adesso = adesso or datetime.now()
    testi = []
    # l'orologio indietro si dice insieme agli altri problemi, non al loro posto (1.11)
    if stato.get('orologio'):
        testi.append('L\'orologio del computer sembra indietro: c\'è già una copia di sicurezza del %s. '
                     'Controllare data e ora di Windows.' % stato['orologio'].strftime('%d/%m/%Y'))
    riserva = stato.get('riserva')
    if riserva:
        testi.append('La cartella dei backup scelta non si raggiunge (%s): le copie si fanno intanto nella '
                     'cartella accanto al database. Controllare la cartella in Impostazioni.' % riserva['errore'])
    elif stato['ultimo_errore'] and (stato['ultimo_ok'] is None or
                                     stato['errore_il'] and stato['errore_il'] > stato['ultimo_ok']):
        testi.append('Backup non riuscito: %s. Controllare la cartella in Impostazioni.' % stato['ultimo_errore'])
    elif stato['ultimo_ok'] is not None and (adesso - stato['ultimo_ok']).days >= 3:
        testi.append('Ultimo backup riuscito %d giorni fa.' % (adesso - stato['ultimo_ok']).days)
    return ' '.join(testi) or None
