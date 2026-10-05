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
import sqlite3
import threading
import time as orologio
from datetime import datetime, date

NOME = re.compile(r'agende-(\d{4}-\d{2}-\d{2})_(\d{6})(?:-([a-z0-9-]+))?\.db$')
COPIE_GIORNALIERE = 30
COPIE_MENSILI = 12

stato = {'ultimo_ok': None, 'ultimo_file': None, 'ultimo_errore': None, 'errore_il': None,
         'in_corso': False}
_lucchetto = threading.Lock()


def cartella_predefinita(percorso_db):
    return os.path.join(os.path.dirname(os.path.abspath(percorso_db)), 'backup')


def _verifica(percorso):
    c = sqlite3.connect(percorso)
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
            sorgente = sqlite3.connect(percorso_db)
            copia = sqlite3.connect(temporaneo)
            try:
                sorgente.backup(copia)
            finally:
                copia.close()
                sorgente.close()
            try:
                _verifica(temporaneo)
            except Exception:
                os.remove(temporaneo)
                raise
            os.replace(temporaneo, finale)
            if not motivo:
                stato.update(ultimo_ok=adesso, ultimo_file=finale, ultimo_errore=None, errore_il=None)
                ruota(cartella)
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


def da_tenere(copie, giornaliere=COPIE_GIORNALIERE, mensili=COPIE_MENSILI):
    """Delle copie automatiche si tengono le ultime 'giornaliere' e la piu'
    vecchia di ciascuno degli ultimi 'mensili' mesi. Le copie con un motivo
    (prima di un ripristino, prima di un aggiornamento) si tengono sempre."""
    automatiche = [c for c in copie if not c['motivo']]
    tenute = {c['nome'] for c in copie if c['motivo']}
    tenute |= {c['nome'] for c in automatiche[:giornaliere]}
    per_mese = {}
    for c in automatiche:                      # dalla piu' recente: resta la piu' vecchia
        per_mese[(c['quando'].year, c['quando'].month)] = c
    for chiave in sorted(per_mese, reverse=True)[:mensili]:
        tenute.add(per_mese[chiave]['nome'])
    return tenute


def ruota(cartella):
    copie = elenco(cartella)
    tenute = da_tenere(copie)
    for c in copie:
        if c['nome'] not in tenute:
            try:
                os.remove(c['percorso'])
            except OSError as e:
                logging.warning('backup %s non eliminato: %s', c['nome'], e)


def fatto_oggi(cartella):
    oggi = date.today()
    return any(c['quando'].date() == oggi and not c['motivo'] for c in elenco(cartella))


def ripristina(percorso_db, file_backup, motore, cartella):
    """Rimette al suo posto una copia. Prima fa una copia di sicurezza del
    database attuale, cosi' anche un ripristino sbagliato si puo' annullare.
    Il chiamante deve tenere fermi i salvataggi (lucchetto) e chiudere le
    sessioni; qui si chiudono le connessioni del motore."""
    _verifica(file_backup)
    sicurezza = esegui(percorso_db, cartella, 'prima-del-ripristino')
    motore.dispose()
    sorgente = sqlite3.connect(file_backup)
    destinazione = sqlite3.connect(percorso_db)
    try:
        sorgente.backup(destinazione)
    finally:
        destinazione.close()
        sorgente.close()
    motore.dispose()
    return sicurezza


def avvia_automatico(percorso_db, leggi_cartella, attesa_iniziale=90, intervallo=3600):
    """Thread che fa la copia del giorno se manca. leggi_cartella() restituisce
    la cartella scelta nelle impostazioni (si rilegge a ogni giro)."""
    def giro():
        orologio.sleep(attesa_iniziale)
        while True:
            try:
                cartella = leggi_cartella() or cartella_predefinita(percorso_db)
                if not fatto_oggi(cartella):
                    finale = esegui(percorso_db, cartella)
                    logging.info('backup fatto: %s', finale)
                elif stato['ultimo_ok'] is None:
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
    if stato['ultimo_errore'] and (stato['ultimo_ok'] is None or
                                   stato['errore_il'] and stato['errore_il'] > stato['ultimo_ok']):
        return 'Backup non riuscito: %s. Controllare la cartella in Impostazioni.' % stato['ultimo_errore']
    if stato['ultimo_ok'] is not None and (adesso - stato['ultimo_ok']).days >= 3:
        return 'Ultimo backup riuscito %d giorni fa.' % (adesso - stato['ultimo_ok']).days
    return None
