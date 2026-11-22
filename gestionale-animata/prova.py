# -*- coding: utf-8 -*-
"""Il pacchetto di prova per Giovanni: il gestionale di oggi, con le sue pagine, sui dati inventati, da provare
sul suo PC anche accanto al programma della clinica, senza toccarlo (tappa 1 della base).

    GestionaleProva-tappa1-<commit>-<giorno>.exe          (doppio clic; lo costruisce strumenti/crea_prova.py)
    python prova.py [--dati CARTELLA] [--porta 5050] [--da-capo] [--senza-browser]

Le pagine sono quelle del programma, senza nessun cambio: in piu' c'e' solo una cornice arancione con
«Versione di prova» e il titolo della scheda che comincia con «PROVA». Rispetto al programma vero
(app.principale) cambia tutto quello che potrebbe toccare la clinica:
- la cartella dei dati e' sua: %LOCALAPPDATA%\\GestionaleAgendeProva (mai ...\\GestionaleAgende), o --dati;
  li' stanno prova.db, prova.log, gestionale.lock e gestionale.pid (il lucchetto di autoripara.entra), il
  diario dell'autoriparazione e la cartella di lavoro delle importazioni;
- la porta e' la 5050 (se occupata 5051-5059): mai la 5000 ne' le 5001-5009 del programma vero;
- chiave e nome del cookie suoi: il cookie del browser va per indirizzo (127.0.0.1), non per porta, e con
  nome e chiave uguali a quelli del programma vero (app.py) i messaggi «Salvato» della prova comparirebbero
  nel programma vero e al contrario;
- il nome del programma per /salute e' suo: il programma vero non scambia mai la prova per se stesso;
- niente email, WhatsApp o registrazione del numero (le funzioni che vanno su internet dicono di no),
  nessun thread degli invii, delle copie o degli aggiornamenti, nessun custode e nessun riavvio da solo;
  «Backup ora», «Ripristina» e la cartella dei backup dicono di no; il controllo degli aggiornamenti non ha
  indirizzo e se se ne scrive uno non va su internet; «Aggiorna adesso» e il popup non ci sono (non e' il
  programma installato);
- non si installa: niente Setup, collegamenti sul desktop o avvio automatico;
- i dati inventati (strumenti/dati_prova.py, gli stessi di strumenti/demo.py) si rifanno all'avvio se il
  giorno e' cambiato, se il pacchetto e' un altro o se il database non e' integro, poi nomi e logo della
  clinica diventano inventati (dati_prova.nomi_inventati). Si rifanno solo all'avvio: aperta oltre la
  mezzanotte, la prova mostra i dati di ieri fino al prossimo avvio.
Le difese le controlla prove_prova.py (nel giro di strumenti/tutte_le_prove.py)."""
import argparse
import json
import logging
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import threading
import types
from datetime import date, datetime
from logging.handlers import RotatingFileHandler

QUI = os.path.dirname(os.path.abspath(__file__))
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, QUI)

NOME_CARTELLA = 'GestionaleAgendeProva'
NOME_VERO = 'GestionaleAgende'                    # la cartella del programma della clinica: mai toccarla
PORTA = 5050
RISERVA = tuple(range(5051, 5060))
PORTE_DEL_PROGRAMMA_VERO = range(5000, 5010)      # app.py 5000, autoripara.PORTE_DI_RISERVA 5001-5009
COOKIE = 'gestionale_prova'
PROGRAMMA = 'Gestionale Agende (prova)'
FILE_DB = 'prova.db'
FILE_REGISTRO = 'prova.log'
FILE_SEGNO = 'dati-della-prova.json'              # giorno e pacchetto con cui sono stati fatti i dati
FILE_FIRMA = 'firma_prova.json'                   # la scrive strumenti/crea_prova.py, va dentro l'eseguibile


# =========================================================== firma e cartella
def cartella_risorse():
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return QUI


def firma():
    """{'tappa', 'commit', 'giorno', 'costruito'} del pacchetto. Dentro l'eseguibile da firma_prova.json; dai
    sorgenti dal git (con «+modifiche» se ci sono file cambiati), e il giorno e' oggi."""
    try:
        with open(os.path.join(cartella_risorse(), FILE_FIRMA), encoding='utf-8') as f:
            d = json.load(f)
        if isinstance(d, dict) and all(isinstance(d.get(k), str) for k in ('tappa', 'commit', 'giorno')):
            d.setdefault('costruito', '')
            return d
    except (OSError, ValueError):
        pass
    commit = 'sorgenti'
    try:
        commit = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=QUI, capture_output=True, text=True,
                                timeout=10).stdout.strip() or commit
        if subprocess.run(['git', 'status', '--porcelain', '--', '.'], cwd=QUI, capture_output=True, text=True,
                          timeout=10).stdout.strip():
            commit += '+modifiche'
    except (OSError, subprocess.SubprocessError):
        pass
    return {'tappa': '?', 'commit': commit, 'giorno': date.today().isoformat(), 'costruito': ''}


def cartella_vera():
    """Dove sta il database della clinica (come modelli.percorso_db, ma senza chiamarla: quella crea la
    cartella)."""
    return os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), NOME_VERO)


def cartella_predefinita():
    return os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), NOME_CARTELLA)


def cartella_sicura(cartella):
    """La cartella della prova, assoluta e creata. Mai quella del programma vero, ne' una che la contiene o
    che sta dentro, ne' una con un agende.db: SystemExit con la spiegazione."""
    c = os.path.normcase(os.path.abspath(cartella))
    vera = os.path.normcase(os.path.abspath(cartella_vera()))
    if c == vera or c.startswith(vera + os.sep) or vera.startswith(c.rstrip(os.sep) + os.sep) or \
            os.path.exists(os.path.join(cartella, 'agende.db')):
        raise SystemExit('La cartella %s è (o contiene) quella del programma della clinica: la prova non la usa.'
                         % cartella)
    os.makedirs(cartella, exist_ok=True)
    return os.path.abspath(cartella)


def leggi_json(percorso):
    try:
        with open(percorso, encoding='utf-8') as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def scrivi_json(percorso, dati):
    provvisorio = percorso + '.nuovo'
    with open(provvisorio, 'w', encoding='utf-8') as f:
        json.dump(dati, f, ensure_ascii=False)
    os.replace(provvisorio, percorso)


# =========================================================== porte verso fuori chiuse
def chiudi_le_porte(cartella, db):
    """Prima di tutto il resto: nessun modulo del programma puo' aprire il database vero, mandare messaggi,
    fare copie, cercare aggiornamenti, riavviarsi o scrivere nella cartella temporanea di Windows. Ogni
    sostituzione e' controllata da prove_prova.py: una funzione nuova che va su internet va aggiunta qui."""
    import modelli
    import aggiornamenti
    import autoripara
    import backup
    import importa
    import invii

    def percorso_della_prova():
        return db
    vero = modelli.percorso_db           # preso PRIMA del giro: dopo il primo cambio il confronto non varrebbe piu'
    cambiati = [m for m in list(sys.modules.values()) if getattr(m, 'percorso_db', None) is vero]
    for m in cambiati:
        m.percorso_db = percorso_della_prova                # modelli, app, comune, aggiornamenti...
    nomi = {getattr(m, '__name__', '') for m in cambiati}
    assert {'modelli', 'app', 'comune', 'aggiornamenti'} <= nomi, 'percorso_db non sostituito: %s' % sorted(nomi)

    def niente_invii(*_, **__):
        raise invii.ErroreInvio('versione di prova: email e WhatsApp non partono mai', permanente=True)
    invii.manda_email = invii.manda_whatsapp = invii.registra_numero = niente_invii
    invii.avvia = lambda *_, **__: None

    def niente_aggiornamenti(*_, **__):
        raise aggiornamenti.ErroreAggiornamento('versione di prova: non cerca e non installa aggiornamenti')
    aggiornamenti.INDIRIZZO_PREDEFINITO = ''
    aggiornamenti.leggi_manifesto = aggiornamenti.scarica = aggiornamenti.apri = niente_aggiornamenti
    aggiornamenti.lancia = niente_aggiornamenti
    aggiornamenti.installato = lambda: False            # niente popup ne' «Aggiorna adesso» (e' frozen, non installato)
    aggiornamenti.avvia = lambda *_, **__: None

    def niente_copie(*_, **__):
        raise RuntimeError('versione di prova: le copie di sicurezza non si fanno e non si rimettono')
    backup.esegui = backup.ripristina = backup.avvia_automatico = niente_copie

    # le importazioni lavorano in %TEMP%\gestionale-importazioni, la stessa cartella del programma vero
    # (importa.cartella_lavoro, che li' cancella i file di ieri): qui nella cartella della prova
    importa.tempfile = types.SimpleNamespace(gettempdir=lambda: cartella)

    autoripara.PROGRAMMA = PROGRAMMA                    # /salute e il secondo clic: solo la prova riconosce la prova
    autoripara.riavvia_programma = lambda *_, **__: False
    autoripara.imposta_riavvio = lambda *_, **__: None
    autoripara.avvia_custode = lambda *_, **__: None


# =========================================================== i dati
def integro(db):
    try:
        c = sqlite3.connect('file:%s?mode=ro' % db.replace('\\', '/'), uri=True)
        try:
            return c.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
        finally:
            c.close()
    except sqlite3.Error:
        return False


def pacchetto(sig):
    return '%s %s' % (sig.get('commit'), sig.get('costruito') or '')


def dati_pronti(cartella, sig, da_capo=False):
    """Il sessionmaker sul database della prova, rifatto se serve: (S, rifatti, rimasti)."""
    from modelli import crea_sessione
    db = os.path.join(cartella, FILE_DB)
    segno_file = os.path.join(cartella, FILE_SEGNO)
    segno = leggi_json(segno_file)
    oggi = date.today().isoformat()
    if not da_capo and os.path.isfile(db) and segno.get('giorno') == oggi and \
            segno.get('pacchetto') == pacchetto(sig) and integro(db):
        return crea_sessione('sqlite:///' + db), False, segno.get('rimasti', [])
    try:
        os.remove(segno_file)          # se fai_dati si ferma a meta', al prossimo avvio si rifa'
    except OSError:
        pass
    from strumenti import dati_prova
    S = dati_prova.fai_dati(db)        # cancella prova.db, -wal e -shm
    rimasti = dati_prova.nomi_inventati(S)
    scrivi_json(segno_file, {'giorno': oggi, 'pacchetto': pacchetto(sig), 'tappa': sig.get('tappa'),
                             'fatti_il': datetime.now().isoformat(timespec='seconds'), 'rimasti': rimasti})
    return S, True, rimasti


# =========================================================== la cornice in ogni pagina
CORNICE = ('<div id="cornice-prova" aria-hidden="true" style="position:fixed;inset:0;border:4px solid #B45309;'
           'pointer-events:none;z-index:2147483646"></div>'
           '<div id="versione-prova" role="note" style="position:fixed;top:0;left:50%%;transform:translateX(-50%%);'
           'z-index:2147483647;background:#B45309;color:#fff;font:600 12px/1.5 Inter,Segoe UI,Arial,sans-serif;'
           'padding:1px 10px 3px;border-radius:0 0 6px 6px;white-space:nowrap">Versione di prova &middot; %s'
           ' &middot; dati inventati%s &middot; <a href="/prova/chiudi" style="color:#fff">Chiudi la prova</a></div>')


def scritta(sig):
    try:
        giorno = date.fromisoformat(sig['giorno']).strftime('%d/%m/%Y')
    except ValueError:
        giorno = sig['giorno']
    return 'tappa %s &middot; %s &middot; %s' % (sig['tappa'], sig['commit'], giorno)


PAGINA_CHIUDI = ('<!doctype html><html lang="it"><head><meta charset="utf-8"><title>Chiudi la prova</title></head>'
                 '<body><form method="post" style="font:16px Segoe UI,Arial,sans-serif;margin:3em">'
                 '<p>Chiudere la versione di prova? Il programma della clinica non cambia.</p>'
                 '<button>Chiudi la prova</button> <a href="/">Torna alla prova</a></form></body></html>')
PAGINA_CHIUSA = ('<!doctype html><html lang="it"><head><meta charset="utf-8"><title>Prova chiusa</title></head>'
                 '<body><p style="font:16px Segoe UI,Arial,sans-serif;margin:3em">La versione di prova è chiusa. '
                 'Si riapre con un doppio clic sul file.</p></body></html>')


def collega_la_prova(A, sig, rimasti):
    """Chiave e cookie suoi, il no alla cartella dei backup, la cornice e /prova/chiudi."""
    from flask import Response, flash, redirect, request
    from markupsafe import escape
    A.app.secret_key = secrets.token_hex(32)           # chiave sua, nuova a ogni avvio
    A.app.config['SESSION_COOKIE_NAME'] = COOKIE
    testo = scritta({k: str(escape(v)) for k, v in sig.items()})
    avviso = ' &middot; <b>attenzione: nomi della clinica rimasti, vedi prova.log</b>' if rimasti else ''
    cornice = CORNICE % (testo, avviso)

    @A.app.before_request
    def niente_cartella_dei_backup():
        # Impostazioni → cartella dei backup crea la cartella scritta e ci prova un file (viste.impostazioni):
        # dalla prova niente cartelle fuori dalla sua (e niente elenco delle copie del programma vero)
        if request.method == 'POST' and request.path == '/impostazioni' and request.form.get('azione') == 'cartella':
            flash('Versione di prova: la cartella dei backup non si cambia.', 'errore')
            return redirect('/impostazioni')
        return None

    @A.app.after_request
    def metti_la_cornice(r):
        if r.direct_passthrough or r.is_streamed or r.mimetype != 'text/html' or not 200 <= r.status_code < 300:
            return r
        html = r.get_data(as_text=True)
        if '<body' not in html:
            return r                    # i pezzi di pagina chiesti dagli script (Dove si fa) restano come sono
        html = re.sub(r'(<body\b[^>]*>)', lambda m: m.group(1) + cornice, html, count=1)
        html = re.sub(r'<title>', '<title>PROVA &middot; ', html, count=1)
        r.set_data(html)
        return r

    @A.app.route('/prova/chiudi', methods=['GET', 'POST'])
    def chiudi_la_prova():
        if request.method == 'POST':  # solo dalle pagine della prova: lo controlla app.solo_dal_gestionale
            logging.info('prova chiusa dalla pagina')
            threading.Timer(0.5, os._exit, [0]).start()
            return Response(PAGINA_CHIUSA, mimetype='text/html')
        return Response(PAGINA_CHIUDI, mimetype='text/html')


# =========================================================== avvio
def prepara_registro(cartella):
    percorso = os.path.join(cartella, FILE_REGISTRO)
    gestore = RotatingFileHandler(percorso, maxBytes=2 * 1024 * 1024, backupCount=1, encoding='utf-8')
    logging.basicConfig(level=logging.INFO, handlers=[gestore], force=True,
                        format='%(asctime)s %(levelname)s %(message)s')
    return percorso


def avvio_non_riuscito(registro, errore):
    """Senza finestra, un errore all'avvio non si vedrebbe: una pagina accanto al registro, nel browser."""
    import webbrowser
    from html import escape
    try:
        percorso = os.path.join(os.path.dirname(registro), 'avvio-non-riuscito.html')
        with open(percorso, 'w', encoding='utf-8') as f:
            f.write('<!doctype html><html lang="it"><meta charset="utf-8"><title>La prova non è partita</title>'
                    '<body style="font:16px Segoe UI,Arial,sans-serif;max-width:40em;margin:3em auto">'
                    '<h1>La versione di prova non è partita</h1><p>Il programma della clinica non è stato toccato. '
                    'Il dettaglio è nel registro <code>%s</code>.</p><p style="color:#5b6b75">Errore: %s</p>'
                    % (escape(registro), escape(str(errore)[:300])))
        webbrowser.open('file:///' + percorso.replace('\\', '/').lstrip('/'))
    except Exception:
        logging.exception("pagina dell'avvio non riuscito")


def principale(argomenti=None):
    p = argparse.ArgumentParser(description='Gestionale Agende, versione di prova con dati inventati.')
    # argparse legge l'aiuto con %: il % di Windows si scrive %% (Python 3.14 lo controlla gia' qui, non solo con --help)
    p.add_argument('--dati', default=None,
                   help='cartella dei dati della prova (di solito %%LOCALAPPDATA%%\\' + NOME_CARTELLA + ')')
    p.add_argument('--porta', type=int, default=PORTA)
    p.add_argument('--da-capo', action='store_true', help='rifa\' i dati inventati anche se sono di oggi')
    p.add_argument('--senza-browser', action='store_true')
    arg = p.parse_args(argomenti)
    if arg.porta in PORTE_DEL_PROGRAMMA_VERO or not 1024 <= arg.porta <= 65535:
        raise SystemExit('La porta %d è del programma della clinica (5000-5009) o non è valida.' % arg.porta)
    cartella = cartella_sicura(arg.dati or cartella_predefinita())
    db = os.path.join(cartella, FILE_DB)
    registro = prepara_registro(cartella)
    apri = not arg.senza_browser
    # il programma come lo usa la clinica: niente controlli in piu' delle prove
    os.environ.pop('GESTIONALE_PROVE_RIGIDE', None)
    sig = firma()
    logging.info('versione di prova %s, dati in %s', sig, cartella)
    os.chdir(cartella)                 # niente file relativi accanto all'eseguibile (Download, Desktop)
    try:
        import app as A                 # registra le pagine; nessun thread parte all'import
        import autoripara
        import viste
        chiudi_le_porte(cartella, db)
        riserva = [x for x in RISERVA if x != arg.porta]
        ingresso = autoripara.entra(cartella, porta=arg.porta, riserva=riserva)
        if not ingresso['principale']:
            logging.info('prova gia\' aperta sulla porta %d (%s): apro solo il browser', ingresso['porta'],
                         ingresso['nota'])
            if apri:
                import webbrowser
                webbrowser.open('http://127.0.0.1:%d/' % ingresso['porta'])
            return
        A._lucchetto_istanza = ingresso['lucchetto']
        S, rifatti, rimasti = dati_pronti(cartella, sig, arg.da_capo)
        if rimasti:
            logging.warning('nomi della clinica rimasti nel database della prova: %s', '; '.join(rimasti))
        logging.info('dati %s', 'rifatti' if rifatti else 'di oggi, ripresi')
        A.Sessione = S
        A._registro = None
        viste._sessionmaker = lambda: S
        collega_la_prova(A, sig, rimasti)

        def pronto(porta):
            autoripara.stato['porta'] = porta
            autoripara.scrivi_pid(cartella, porta, 'in servizio')
        A.avvia(porta=ingresso['porta'], apri=apri, riserva=riserva, pronto=pronto)
    except Exception as e:
        logging.exception('avvio della prova non riuscito')
        if apri:
            avvio_non_riuscito(registro, e)
        raise


if __name__ == '__main__':
    principale()
