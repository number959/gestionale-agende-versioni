# -*- coding: utf-8 -*-
"""«Aggiorna adesso»: il programma si accorge da solo delle versioni nuove e
si aggiorna con un clic.

Da dove: di partenza le versioni del Gestionale Agende su GitHub
(INDIRIZZO_PREDEFINITO), e alla clinica non c'e' niente da scrivere. In
Configura → Aggiornamenti se ne puo' scrivere un altro:
- la pagina delle versioni di un progetto GitHub: basta l'indirizzo del
  progetto, https://github.com/<utente>/<progetto>, che diventa
  https://github.com/<utente>/<progetto>/releases/latest/download/ (l'ultima
  versione pubblicata);
- un altro indirizzo https, oppure una cartella (di rete, di Google Drive
  sincronizzata, una chiavetta).
Lasciato vuoto non si controlla niente; «Rimetti l'indirizzo predefinito»
torna a quello di partenza. Un indirizzo http non si accetta: lungo la strada
qualcuno potrebbe cambiare il file.

Cosa legge: aggiornamento.json (nella versione animata
aggiornamento-animata.json), scritto da strumenti/prepara_aggiornamento.py
accanto al Setup: versione, nome del Setup, dimensione, impronta SHA-256 e
novita'.

Quando: due minuti dopo l'avvio e poi ogni sei ore, o con «Controlla adesso».
Se la versione e' piu' nuova il Setup si scarica in silenzio nella cartella
"aggiornamenti" accanto ai dati e si controlla (dimensione, impronta, che sia
un programma Windows); poi compare la notifica «Aggiornamento disponibile».

«Aggiorna adesso»:
1. copia di sicurezza del database (backup "prima-di-aggiornare");
2. aspetta che non ci siano email a meta';
3. avvia il Setup senza domande (/SILENT: solo la barra di avanzamento). Il
   Setup chiude il gestionale, lo sostituisce e lo riapre (installer.iss,
   [Run] con Check: WizardSilent). Parte con "cmd /c start": cosi' non e' un
   processo figlio del gestionale, e il "taskkill /T" con cui il Setup chiude
   il gestionale non chiude anche lui. E parte senza le variabili d'ambiente
   interne dell'eseguibile (ambiente_pulito), che il gestionale riaperto
   prenderebbe per sue;
4. la pagina rimasta aperta nel browser aspetta che il programma torni e apre
   le novita', con le videoguide.

Al primo avvio dopo l'aggiornamento (dopo_avvio) si registra com'e' andata,
si segna la versione avviata (per la notifica delle novita') e si cancellano
i Setup gia' installati.

Lo stato (ultimo controllo, errore, Setup pronto) sta in memoria, come per i
backup: una rete lenta non deve rallentare le pagine."""
import hashlib
import json
import logging
import os
import re
import socket
import ssl
import subprocess
import sys
import threading
import time as orologio
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import select, func

from modelli import (cartella_risorse, percorso_db, leggi_impostazione, scrivi_impostazione, Appuntamento,
                     Paziente, Invio, Impostazione)
from comune import VERSIONE, json_sicuro
import backup
import novita
import viste

bp = Blueprint('aggiornamenti', __name__)

PROGRAMMA = 'Gestionale Agende'
# la versione animata ha un file delle versioni e un Setup suoi: si riconosce dai suoi file
VARIANTE = 'animata' if os.path.exists(os.path.join(cartella_risorse(), 'static', 'animazioni.css')) else 'normale'
MANIFESTO = 'aggiornamento-animata.json' if VARIANTE == 'animata' else 'aggiornamento.json'
NOME_SETUP = 'GestionaleAgende-animata-setup.exe' if VARIANTE == 'animata' else 'GestionaleAgende-setup.exe'
# di partenza: le versioni del Gestionale Agende su GitHub, un progetto pubblico con le sole
# "Releases" (vedi LEGGIMI, «Pubblicare un aggiornamento»). Vale finche' nella pagina non se
# ne scrive un altro; «Rimetti l'indirizzo predefinito» ci riporta
INDIRIZZO_PREDEFINITO = 'https://github.com/number959/gestionale-agende-versioni'
CHIAVE = 'aggiornamenti_indirizzo'
ATTESA_INIZIALE = 120                 # secondi dopo l'avvio
INTERVALLO = 6 * 3600
GIORNI_NOVITA = 14                    # per quanti giorni la notifica delle novita'
ATTESA_RETE = 30                      # secondi: oltre, "internet non risponde"
MASSIMO_MANIFESTO = 256 * 1024
MINIMO_SETUP = 1024 * 1024
MASSIMO_SETUP = 500 * 1024 * 1024
PARAMETRI_SETUP = '/SILENT /NOCANCEL /SUPPRESSMSGBOXES /NORESTART'
MOTIVO_COPIA = 'prima-di-aggiornare'
ATTESA_PRIMA_DEL_SETUP = 1.5          # secondi: la pagina d'attesa arriva al browser prima che il programma si chiuda
VERSIONE_VALIDA = re.compile(r'\d{1,4}(\.\d{1,4}){0,3}')
# cambia a ogni avvio: la pagina che aspetta il riavvio se ne accorge
AVVIATO_IL = '%s-%d' % (datetime.now().isoformat(timespec='seconds'), os.getpid())

stato = {'controllato_il': None, 'errore': None, 'errore_il': None, 'disponibile': None, 'pronto': None,
         'scaricati': 0, 'totale': 0, 'in_corso': False, 'partito': None}
_un_controllo = threading.Lock()
_attivi = [0]                         # controlli in corso o in attesa del loro turno
_conto = threading.Lock()
_fornitore = None
_lucchetto = threading.Lock()
_fabbrica = None
_thread = None
_sveglia = threading.Event()


class ErroreAggiornamento(Exception):
    pass


def collega(app, fornitore_sessione, lucchetto=None, fabbrica=None):
    """fabbrica: una funzione che restituisce una sessione nuova, per il thread."""
    global _fornitore, _lucchetto, _fabbrica
    _fornitore = fornitore_sessione
    if lucchetto is not None:
        _lucchetto = lucchetto
    _fabbrica = fabbrica
    app.register_blueprint(bp)


def ses():
    return _fornitore()


def sessione_nuova(fabbrica=None):
    if fabbrica is not None:
        return fabbrica()
    if _fabbrica is not None:
        return _fabbrica()
    return _fornitore().session_factory()


def installato():
    """Il programma e' quello installato con il Setup (non i sorgenti delle prove)."""
    return bool(getattr(sys, 'frozen', False))


def cartella():
    """La cartella dei Setup scaricati, accanto al database."""
    percorso, _ = viste.percorso_database()
    return os.path.join(os.path.dirname(percorso or percorso_db()), 'aggiornamenti')


# ================================================================ indirizzo
def normalizza(testo):
    """(indirizzo da usare, errore). '' = aggiornamenti spenti; altrimenti un
    indirizzo https che finisce con '/' oppure una cartella."""
    t = (testo or '').strip().strip('"\'').strip()
    if not t:
        return '', None
    if len(t) > 400 or any(ord(c) < 32 for c in t):
        return None, 'Indirizzo non valido.'
    if re.match(r'[A-Za-z][A-Za-z0-9+.-]*://', t):
        try:
            u = urllib.parse.urlsplit(t)
            host = (u.hostname or '').lower()
            u.port                         # una porta che non e' un numero: ValueError
        except ValueError:
            return None, 'Indirizzo non valido.'
        if u.scheme.lower() != 'https':
            return None, ('Serve un indirizzo che comincia con https:// (oppure una cartella): con http lungo la strada '
                          'qualcuno potrebbe cambiare il file.')
        if not host or u.username is not None or u.password is not None:
            return None, 'Indirizzo non valido.'
        parti = [urllib.parse.unquote(p) for p in u.path.split('/') if p]
        if host in ('github.com', 'www.github.com'):
            nome = re.compile(r'\.?[A-Za-z0-9][A-Za-z0-9._-]{0,99}')   # niente "." o ".." da soli
            if len(parti) < 2 or not all(nome.fullmatch(p) for p in parti[:2]):
                return None, 'Per GitHub basta l\'indirizzo del progetto: https://github.com/<utente>/<progetto>.'
            utente, progetto = parti[0], re.sub(r'\.git$', '', parti[1])
            # una versione precisa resta quella; tutto il resto porta all'ultima pubblicata
            if len(parti) >= 5 and parti[2:4] == ['releases', 'download'] and nome.fullmatch(parti[4]):
                return 'https://github.com/%s/%s/releases/download/%s/' % (utente, progetto, parti[4]), None
            return 'https://github.com/%s/%s/releases/latest/download/' % (utente, progetto), None
        percorso = u.path or '/'
        if re.search(r'\.(json|exe)$', percorso, re.I):          # incollato l'indirizzo di un file: la sua cartella
            percorso = percorso.rsplit('/', 1)[0] + '/'
        if not percorso.endswith('/'):
            percorso += '/'
        return urllib.parse.urlunsplit(('https', u.netloc, percorso, '', '')), None
    if not os.path.isabs(t):
        return None, ('Serve un indirizzo https:// oppure una cartella completa, per esempio \\\\server\\aggiornamenti '
                      'o G:\\Il mio Drive\\Aggiornamenti.')
    if re.search(r'\.(json|exe)$', t, re.I):
        t = os.path.dirname(t)
    return os.path.normpath(t), None


def predefinito():
    """L'indirizzo predefinito come lo usa il programma ('' se non c'e')."""
    return normalizza(INDIRIZZO_PREDEFINITO)[0] or ''


def indirizzo_scritto(s):
    return leggi_impostazione(s, CHIAVE, INDIRIZZO_PREDEFINITO)


def indirizzo_configurato(fabbrica=None):
    s = sessione_nuova(fabbrica)
    try:
        return normalizza(indirizzo_scritto(s))[0] or ''
    finally:
        s.close()


# ================================================================== lettura
def contesto_tls():
    return ssl.create_default_context()


class _SoloHttps(urllib.request.HTTPRedirectHandler):
    """GitHub rimanda il file a un altro indirizzo: lo si segue, ma solo se resta https."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.lower().startswith('https://'):
            raise ErroreAggiornamento('il sito degli aggiornamenti rimanda a un indirizzo non sicuro')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def apri(base, nome):
    """Il file 'nome' all'indirizzo 'base' (https o cartella), aperto in lettura."""
    if base.startswith('https://'):
        apertura = urllib.request.build_opener(urllib.request.HTTPSHandler(context=contesto_tls()), _SoloHttps)
        richiesta = urllib.request.Request(base + urllib.parse.quote(nome), headers={
            'User-Agent': 'GestionaleAgende/%s (%s)' % (VERSIONE, VARIANTE), 'Cache-Control': 'no-cache'})
        try:
            return apertura.open(richiesta, timeout=ATTESA_RETE)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                if nome == MANIFESTO:
                    raise ErroreAggiornamento('all\'indirizzo degli aggiornamenti non c\'è il file %s: lì non è stata '
                                              'ancora pubblicata nessuna versione, oppure è stata pubblicata senza quel '
                                              'file, oppure l\'indirizzo è sbagliato' % nome)
                raise ErroreAggiornamento('all\'indirizzo degli aggiornamenti non c\'è il file %s: la versione è stata '
                                          'pubblicata senza quel file' % nome)
            raise ErroreAggiornamento('il sito degli aggiornamenti ha risposto con l\'errore %d' % e.code)
        except urllib.error.URLError as e:
            if isinstance(e.reason, ssl.SSLCertVerificationError):
                raise ErroreAggiornamento('il certificato del sito degli aggiornamenti non è valido')
            if isinstance(e.reason, (socket.timeout, TimeoutError)):
                raise ErroreAggiornamento('internet non risponde: si riprova più tardi')
            raise ErroreAggiornamento('internet non raggiungibile (%s): si riprova più tardi' % e.reason)
    try:
        return open(os.path.join(base, nome), 'rb')
    except FileNotFoundError:
        if not os.path.isdir(base):
            raise ErroreAggiornamento('la cartella degli aggiornamenti non si raggiunge: %s' % base)
        raise ErroreAggiornamento('nella cartella degli aggiornamenti non c\'è il file %s' % nome)
    except OSError as e:
        raise ErroreAggiornamento('la cartella degli aggiornamenti non si legge: %s' % e)


def valida(dati):
    """Il file delle versioni letto -> dizionario controllato, oppure
    ErroreAggiornamento: niente di quello che arriva da fuori passa senza
    controllo (versione, nome del file, dimensione, impronta, novita')."""
    try:
        m = json.loads(dati.decode('utf-8-sig'))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise ErroreAggiornamento('il file %s non si legge: non è un file delle versioni' % MANIFESTO)
    if not isinstance(m, dict) or m.get('programma') != PROGRAMMA:
        raise ErroreAggiornamento('il file %s non è del Gestionale Agende' % MANIFESTO)
    if m.get('variante') != VARIANTE:
        raise ErroreAggiornamento('il file delle versioni è per la versione "%s" del programma, qui c\'è la "%s"'
                                  % (str(m.get('variante'))[:20], VARIANTE))
    versione, nome, byte, impronta = m.get('versione'), m.get('file'), m.get('byte'), m.get('sha256')
    if not isinstance(versione, str) or not VERSIONE_VALIDA.fullmatch(versione):
        raise ErroreAggiornamento('nel file delle versioni la versione non è valida')
    if not isinstance(nome, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}\.exe', nome):
        raise ErroreAggiornamento('nel file delle versioni il nome del Setup non è valido')
    if type(byte) is not int or not MINIMO_SETUP <= byte <= MASSIMO_SETUP:
        raise ErroreAggiornamento('nel file delle versioni la dimensione del Setup non è valida')
    if not isinstance(impronta, str) or not re.fullmatch(r'[0-9A-Fa-f]{64}', impronta):
        raise ErroreAggiornamento('nel file delle versioni l\'impronta del Setup non è valida')
    elenco = []
    for v in m.get('novita') if isinstance(m.get('novita'), list) else []:
        if not (isinstance(v, dict) and isinstance(v.get('versione'), str) and VERSIONE_VALIDA.fullmatch(v['versione'])
                and isinstance(v.get('voci'), list)):
            continue
        voci = [{'titolo': x['titolo'][:120], 'testo': x['testo'][:800]} for x in v['voci'][:30]
                if isinstance(x, dict) and isinstance(x.get('titolo'), str) and isinstance(x.get('testo'), str)]
        if voci:
            elenco.append({'versione': v['versione'], 'voci': voci})
        if len(elenco) >= 40:
            break
    pubblicata = m.get('pubblicata')
    if not isinstance(pubblicata, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', pubblicata):
        pubblicata = ''
    return {'versione': versione, 'file': nome, 'byte': byte, 'sha256': impronta.lower(), 'novita': elenco,
            'pubblicata': pubblicata}


def leggi_manifesto(base):
    with apri(base, MANIFESTO) as f:
        dati = f.read(MASSIMO_MANIFESTO + 1)
    if len(dati) > MASSIMO_MANIFESTO:
        raise ErroreAggiornamento('il file %s è troppo grande: non è quello giusto' % MANIFESTO)
    return valida(dati)


def novita_del_manifesto(m):
    """Le novita' della versione da installare e di quelle saltate, dalla piu' nuova."""
    scelte = [v for v in m['novita'] if novita.confronta(v['versione'], VERSIONE) > 0
              and novita.confronta(v['versione'], m['versione']) <= 0]
    return sorted(scelte, key=lambda v: novita.numeri(v['versione']), reverse=True)


# ============================================================ scaricamento
def nome_locale(m):
    """Il nome del Setup scaricato: lo decide il programma, non il file che arriva da fuori."""
    return 'GestionaleAgende%s-setup-%s.exe' % ('-animata' if VARIANTE == 'animata' else '', m['versione'])


def file_giusto(percorso, m):
    """Il file e' il Setup del file delle versioni: dimensione, impronta e
    intestazione dei programmi Windows ("MZ")."""
    try:
        if os.path.getsize(percorso) != m['byte']:
            return False
        h = hashlib.sha256()
        with open(percorso, 'rb') as f:
            inizio = f.read(2)
            h.update(inizio)
            for blocco in iter(lambda: f.read(1024 * 1024), b''):
                h.update(blocco)
        return inizio == b'MZ' and h.hexdigest() == m['sha256']
    except OSError:
        return False


def scarica(base, m):
    """Scarica il Setup nella cartella degli aggiornamenti (se non c'e' gia')
    e lo controlla. Restituisce il percorso."""
    dove = cartella()
    os.makedirs(dove, exist_ok=True)
    finale = os.path.join(dove, nome_locale(m))
    if os.path.exists(finale) and file_giusto(finale, m):
        return finale
    parziale = finale + '.parziale'
    stato.update(scaricati=0, totale=m['byte'])
    try:
        h, n = hashlib.sha256(), 0
        with apri(base, m['file']) as sorgente, open(parziale, 'wb') as uscita:
            while True:
                blocco = sorgente.read(256 * 1024)
                if not blocco:
                    break
                n += len(blocco)
                if n > m['byte']:
                    raise ErroreAggiornamento('il Setup è più grande di quanto dice il file delle versioni: non si installa')
                h.update(blocco)
                uscita.write(blocco)
                stato['scaricati'] = n
        if n != m['byte']:
            raise ErroreAggiornamento('scaricamento interrotto (%.1f MB su %.1f): si riprova più tardi'
                                      % (n / 1048576, m['byte'] / 1048576))
        if h.hexdigest() != m['sha256']:
            raise ErroreAggiornamento('il Setup scaricato non corrisponde all\'impronta pubblicata: non si installa')
        with open(parziale, 'rb') as f:
            if f.read(2) != b'MZ':
                raise ErroreAggiornamento('il file scaricato non è un programma Windows: non si installa')
        os.replace(parziale, finale)
        return finale
    finally:
        if os.path.exists(parziale):
            try:
                os.remove(parziale)
            except OSError:
                pass


def spiega(e):
    if isinstance(e, ErroreAggiornamento):
        return str(e)
    if isinstance(e, (socket.timeout, TimeoutError)):
        return 'internet non risponde: si riprova più tardi'
    if isinstance(e, OSError):
        return 'errore di rete o del disco: %s' % e
    return str(e) or e.__class__.__name__


def _entra():
    with _conto:
        _attivi[0] += 1
        stato['in_corso'] = True


def _esci():
    """'in corso' resta vero finche' un altro controllo aspetta il suo turno: la
    pagina che segue l'avanzamento non deve ricaricarsi fra un controllo e
    l'altro, mostrando il risultato di quello vecchio (per esempio del
    controllo delle sei ore, mentre si e' appena premuto «Controlla adesso»)."""
    with _conto:
        _attivi[0] -= 1
        stato['in_corso'] = _attivi[0] > 0


def controlla(fabbrica=None, scarica_setup=True, aspetta=False, _gia_contato=False):
    """Un controllo: legge il file delle versioni e, se la versione e' piu'
    nuova, scarica il Setup. Non solleva eccezioni: com'e' andata sta in
    'stato'. Se c'e' gia' un controllo in corso: con 'aspetta' si fa dopo di
    lui (per esempio con l'indirizzo appena cambiato), altrimenti False."""
    if not _gia_contato:
        _entra()
    lucchetto = _un_controllo
    try:
        if not (lucchetto.acquire(timeout=600) if aspetta else lucchetto.acquire(blocking=False)):
            return False
        try:
            return _controlla(fabbrica, scarica_setup)
        finally:
            lucchetto.release()
    finally:
        _esci()


def _controlla(fabbrica, scarica_setup):
    stato.update(scaricati=0, totale=0)
    try:
        base = indirizzo_configurato(fabbrica)
        if not base:
            stato.update(controllato_il=None, errore=None, errore_il=None, disponibile=None, pronto=None)
            return True
        m = leggi_manifesto(base)
        stato.update(controllato_il=datetime.now(), errore=None, errore_il=None)
        if novita.confronta(m['versione'], VERSIONE) <= 0:
            stato.update(disponibile=None, pronto=None)
            return True
        gia = stato['pronto']
        stato['disponibile'] = m
        if gia and os.path.basename(gia) == nome_locale(m) and file_giusto(gia, m):
            return True
        stato['pronto'] = None
        if scarica_setup:
            stato['pronto'] = scarica(base, m)
            logging.info('aggiornamento alla versione %s scaricato: %s', m['versione'], stato['pronto'])
        return True
    except Exception as e:
        stato.update(errore=spiega(e), errore_il=datetime.now())
        logging.warning('aggiornamenti: %s', stato['errore'])
        return True


def controlla_in_sottofondo(fabbrica=None):
    """Per i pulsanti: il controllo parte e la pagina torna subito (mostra
    l'avanzamento). Si conta prima che il thread parta: la pagina che si apre
    subito dopo dice gia' "controllo in corso", e un controllo che finisce
    intanto non lo spegne."""
    _entra()
    t = threading.Thread(target=controlla, args=(fabbrica or _fabbrica,), kwargs={'aspetta': True, '_gia_contato': True},
                         name='controllo-aggiornamenti', daemon=True)
    try:
        t.start()
    except BaseException:
        _esci()
        raise
    return t


def avvia(fabbrica, attesa_iniziale=ATTESA_INIZIALE, intervallo=INTERVALLO):
    """Il thread dei controlli: dopo 'attesa_iniziale' secondi e poi ogni 'intervallo'."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return _thread

    def giro():
        _sveglia.wait(attesa_iniziale)
        _sveglia.clear()
        while True:
            try:
                # il Setup appena installato all'avvio era ancora aperto (non si cancella un
                # programma in uso): ci si riprova a ogni giro
                for nota in pulisci():
                    logging.info('aggiornamenti: %s', nota)
                controlla(fabbrica)
            except Exception:
                logging.exception('aggiornamenti: controllo')
            _sveglia.wait(intervallo)
            _sveglia.clear()
    _thread = threading.Thread(target=giro, name='aggiornamenti', daemon=True)
    _thread.start()
    return _thread


# ============================================================ installazione
def percorso_segno():
    return os.path.join(cartella(), 'in-corso.json')


def scrivi_segno(dati):
    os.makedirs(cartella(), exist_ok=True)
    with open(percorso_segno(), 'w', encoding='utf-8') as f:
        json.dump(dati, f, ensure_ascii=False)


def leggi_segno():
    try:
        with open(percorso_segno(), encoding='utf-8') as f:
            dati = json.load(f)
        return dati if isinstance(dati, dict) else {}
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return {}


def cancella_segno():
    try:
        os.remove(percorso_segno())
    except OSError:
        pass


def cmd():
    return os.path.join(os.environ.get('SystemRoot') or r'C:\Windows', 'System32', 'cmd.exe')


def ambiente_pulito():
    """L'ambiente per il Setup senza le variabili che l'eseguibile a file unico
    (PyInstaller) passa al suo processo figlio (_PYI_..., _MEI...). Il Setup le
    passerebbe al gestionale che riapre, che si crederebbe il figlio di un
    processo ormai chiuso e si fermerebbe con "Security validation failure:
    invalid originating onefile parent process". Cosi' riparte come da un doppio
    clic sull'icona."""
    return {k: v for k, v in os.environ.items() if not k.upper().startswith(('_PYI_', '_MEI'))}


def lancia(percorso, registro):
    """Avvia il Setup senza domande e staccato dal gestionale (vedi in cima)."""
    comando = '"%s" /c start "" "%s" %s /LOG="%s"' % (cmd(), percorso, PARAMETRI_SETUP, registro)
    subprocess.Popen(comando, env=ambiente_pulito(), creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                     close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def aspetta_invii(massimo=20, fabbrica=None):
    """Se un'email sta partendo proprio adesso, la si lascia finire: chiudere
    il programma a meta' invio la farebbe ripartire due volte."""
    fine = orologio.monotonic() + massimo
    while orologio.monotonic() < fine:
        try:
            s = sessione_nuova(fabbrica)
            try:
                n = s.scalar(select(func.count()).select_from(Invio).where(Invio.stato == 'IN_CORSO'))
            finally:
                s.close()
        except Exception:
            return
        if not n:
            return
        orologio.sleep(1)


def _parti(percorso, registro):
    orologio.sleep(ATTESA_PRIMA_DEL_SETUP)
    aspetta_invii()
    try:
        lancia(percorso, registro)
    except Exception as e:
        logging.exception('aggiornamento: il Setup non parte')
        stato.update(partito=None, errore='il Setup non è partito: %s' % e, errore_il=datetime.now())
        cancella_segno()


def dopo_avvio(s, adesso=None):
    """All'avvio del programma: la versione avviata (per le novita'), com'e'
    andato un «Aggiorna adesso», i Setup gia' installati da cancellare.
    Restituisce le righe per il registro."""
    adesso = adesso or datetime.now()
    note = []
    precedente = leggi_impostazione(s, 'versione_avviata', '')
    if precedente != VERSIONE:
        if precedente:
            nuova = novita.confronta(precedente, VERSIONE) < 0
        else:
            # la prima volta che si registra: se ci sono gia' dati arriva da una versione vecchia
            nuova = s.scalars(select(Appuntamento.id).limit(1)).first() is not None or \
                s.scalars(select(Paziente.id).limit(1)).first() is not None
        scrivi_impostazione(s, 'versione_precedente', precedente)
        scrivi_impostazione(s, 'versione_avviata', VERSIONE)
        scrivi_impostazione(s, 'novita_dal', adesso.date().isoformat() if nuova else '')
        s.commit()
        note.append('versione %s avviata la prima volta%s' % (VERSIONE, ' (prima c\'era la %s)' % precedente if precedente else ''))
    segno = leggi_segno()
    if segno is not None:
        cancella_segno()
        arrivo = segno.get('a') if isinstance(segno.get('a'), str) else ''
        if arrivo and novita.confronta(VERSIONE, arrivo) >= 0:
            scrivi_impostazione(s, 'aggiornamento_fallito', '')
            note.append('aggiornamento dalla %s alla %s riuscito' % (segno.get('da'), arrivo))
        elif arrivo:
            scrivi_impostazione(s, 'aggiornamento_fallito', json.dumps(
                {'a': arrivo, 'quando': str(segno.get('quando') or ''), 'log': str(segno.get('log') or '')}, ensure_ascii=False))
            note.append('aggiornamento alla %s NON riuscito, resta la %s: dettagli in %s' % (arrivo, VERSIONE, segno.get('log')))
        s.commit()
    note += pulisci()
    return note


def pulisci():
    """Via i Setup gia' installati (versione uguale o piu' vecchia) e quelli a meta'."""
    note = []
    dove = cartella()
    try:
        nomi = os.listdir(dove)
    except OSError:
        return note
    for nome in nomi:
        m = re.fullmatch(r'GestionaleAgende(?:-animata)?-setup-(\d+(?:\.\d+)*)\.exe(\.parziale)?', nome)
        if m and (m.group(2) or novita.confronta(m.group(1), VERSIONE) <= 0):
            try:
                os.remove(os.path.join(dove, nome))
                note.append('cancellato il Setup già installato %s' % nome)
            except OSError:
                pass
    return note


def leggi_fallito(s):
    try:
        d = json.loads(leggi_impostazione(s, 'aggiornamento_fallito', '') or 'null')
    except ValueError:
        return None
    return d if isinstance(d, dict) and d.get('a') else None


# ================================================================== novita'
def novita_da_annunciare(s, adesso=None):
    """Le novita' della notifica: nei GIORNI_NOVITA dopo l'aggiornamento,
    finche' la pagina delle novita' non e' stata aperta."""
    adesso = adesso or datetime.now()
    dal = leggi_impostazione(s, 'novita_dal', '')
    if not dal or leggi_impostazione(s, 'novita_vista', '') == VERSIONE:
        return []
    try:
        giorno = date.fromisoformat(dal)
    except ValueError:
        return []
    if not 0 <= (adesso.date() - giorno).days < GIORNI_NOVITA:
        return []
    return novita.dopo(leggi_impostazione(s, 'versione_precedente', ''), VERSIONE)


def notifiche(s, adesso=None):
    """Per le notifiche a scomparsa: aggiornamento pronto, aggiornamento non
    riuscito, novita' della versione appena installata."""
    uscita = []
    vista = dict(stato)                 # una fotografia sola: il controllo puo' cambiare lo stato intanto
    m, pronto = vista['disponibile'], vista['pronto']
    if m and pronto and novita.confronta(m['versione'], VERSIONE) > 0:
        uscita.append({'chiave': 'aggiornamento-%s' % m['versione'], 'titolo': 'Aggiornamento disponibile',
                       'testo': 'È pronta la versione %s. Aggiorna adesso: circa un minuto, e i dati restano.' % m['versione'],
                       'link': url_for('aggiornamenti.pagina'), 'azioni': [], 'livello': 'normale'})
    fallito = leggi_fallito(s)
    if fallito:
        uscita.append({'chiave': 'aggiornamento-fallito-%s' % fallito.get('quando', ''), 'titolo': 'Aggiornamento non riuscito',
                       'testo': 'Il programma è rimasto alla versione %s: si può riprovare da Configura → Aggiornamenti.' % VERSIONE,
                       'link': url_for('aggiornamenti.pagina'), 'azioni': [], 'livello': 'errore'})
    voci = novita_da_annunciare(s, adesso)
    if voci:
        n = sum(len(v) for _, v in voci)
        uscita.append({'chiave': 'novita-%s' % VERSIONE, 'titolo': 'Novità della versione %s' % VERSIONE,
                       'testo': '%d %s, con i video: un minuto per vederle.' % (n, 'cosa nuova' if n == 1 else 'cose nuove'),
                       'link': url_for('aggiornamenti.novita_pagina'), 'azioni': [], 'livello': 'normale'})
    return uscita


# =================================================================== pagine
@bp.route('/aggiornamenti', methods=['GET', 'POST'])
def pagina():
    s = ses()
    if request.method == 'POST':
        azione = request.form.get('azione')
        if azione in ('indirizzo', 'predefinito'):
            if azione == 'predefinito':
                base, errore = predefinito(), None
            else:
                base, errore = normalizza(request.form.get('indirizzo'))
            if errore:
                flash(errore, 'errore')
                return redirect(url_for('aggiornamenti.pagina') + '#indirizzo')
            with _lucchetto:
                if azione == 'predefinito' or (base and base == predefinito()):
                    # quello predefinito: nessuna riga nelle impostazioni, cosi' si segue
                    # il programma anche se un giorno l'indirizzo predefinito cambia
                    riga = s.get(Impostazione, CHIAVE)
                    if riga is not None:
                        s.delete(riga)
                else:
                    scrivi_impostazione(s, CHIAVE, base)
                s.commit()
            stato.update(controllato_il=None, errore=None, errore_il=None, disponibile=None, pronto=None)
            if base:
                controlla_in_sottofondo()
                flash('%s: il programma controlla subito se c\'è una versione nuova.'
                      % ('Rimesso l\'indirizzo predefinito' if azione == 'predefinito' else 'Indirizzo salvato'), 'ok')
            else:
                flash('Aggiornamenti automatici spenti: si aggiorna a mano, con il Setup.', 'ok')
        elif azione == 'controlla':
            if not indirizzo_configurato():
                flash('Prima va scritto l\'indirizzo degli aggiornamenti, qui sotto.', 'errore')
            else:
                controlla_in_sottofondo()
        return redirect(url_for('aggiornamenti.pagina'))
    fallito = leggi_fallito(s)
    if fallito:                       # detto una volta, qui; la notifica sparisce
        with _lucchetto:
            scrivi_impostazione(s, 'aggiornamento_fallito', '')
            s.commit()
    # lo stato si legge una volta sola: un controllo che finisce mentre la pagina si
    # compone non deve mostrare la versione nuova come "non ancora scaricata"
    vista = dict(stato)
    m = vista['disponibile']
    scritto = indirizzo_scritto(s)
    base, quello_predefinito = normalizza(scritto)[0] or '', predefinito()
    return render_template('aggiornamenti.html', versione=VERSIONE, variante=VARIANTE, scritto=scritto,
                           base=base, predefinito=quello_predefinito,
                           usa_predefinito=bool(quello_predefinito and base == quello_predefinito), stato=vista, m=m,
                           novita_nuove=novita_del_manifesto(m) if m else [],
                           pronto=bool(vista['pronto'] and os.path.exists(vista['pronto'])),
                           fallito=fallito, manifesto=MANIFESTO, nome_setup=NOME_SETUP, sezione='aggiornamenti')


@bp.route('/aggiornamenti/aggiorna', methods=['POST'])
def aggiorna():
    m, percorso = stato['disponibile'], stato['pronto']
    torna = redirect(url_for('aggiornamenti.pagina'))
    if not m or not percorso or novita.confronta(m['versione'], VERSIONE) <= 0:
        flash('Non c\'è un aggiornamento pronto: «Controlla adesso», poi di nuovo «Aggiorna adesso».', 'errore')
        return torna
    if not installato():
        flash('Questa copia del programma non è quella installata con il Setup: da qui non si aggiorna. Il Setup '
              'scaricato è %s.' % percorso, 'errore')
        return torna
    if not file_giusto(percorso, m):
        stato['pronto'] = None
        flash('Il Setup scaricato non è più integro: «Controlla adesso» lo scarica di nuovo.', 'errore')
        return torna
    s = ses()
    percorso_db_, _ = viste.percorso_database()
    try:
        copia = backup.esegui(percorso_db_, viste.cartella_effettiva(s, percorso_db_), MOTIVO_COPIA)
    except Exception as e:
        flash('La copia di sicurezza non è riuscita (%s): l\'aggiornamento non parte.' % e, 'errore')
        return torna
    registro = os.path.join(cartella(), 'setup-%s.log' % m['versione'])
    scrivi_segno({'da': VERSIONE, 'a': m['versione'], 'quando': datetime.now().isoformat(timespec='seconds'),
                  'copia': copia, 'log': registro})
    stato['partito'] = datetime.now()
    logging.info('aggiornamento alla versione %s: copia di sicurezza %s, parte il Setup %s', m['versione'], copia, percorso)
    threading.Thread(target=_parti, args=(percorso, registro), name='aggiornamento', daemon=True).start()
    return render_template('aggiornamento_in_corso.html', da=VERSIONE, a=m['versione'], avviato=AVVIATO_IL,
                           copia=os.path.basename(copia), sezione='aggiornamenti')


@bp.route('/aggiornamenti/stato.json')
def stato_json():
    vista = dict(stato)
    m = vista['disponibile']
    return json_sicuro({'versione': VERSIONE, 'avviato': AVVIATO_IL, 'in_corso': vista['in_corso'],
                        'scaricati': vista['scaricati'], 'totale': vista['totale'],
                        'disponibile': m['versione'] if m else None, 'pronto': bool(vista['pronto']),
                        'partito': bool(vista['partito']), 'errore': vista['errore']})


@bp.route('/aiuto/novita')
def novita_pagina():
    s = ses()
    precedente = leggi_impostazione(s, 'versione_precedente', '')
    recenti = novita.dopo(precedente, VERSIONE) or novita.dopo('', VERSIONE)
    viste_qui = {v for v, _ in recenti}
    altre = [(v, voci) for v, voci in novita.NOVITA if v not in viste_qui and novita.confronta(v, VERSIONE) <= 0]
    if leggi_impostazione(s, 'novita_vista', '') != VERSIONE:
        with _lucchetto:
            scrivi_impostazione(s, 'novita_vista', VERSIONE)
            s.commit()
    return render_template('novita.html', recenti=recenti, altre=altre, versione=VERSIONE, sezione='aiuto')
