# -*- coding: utf-8 -*-
"""Il pacchetto di prova (prova.py) non tocca il programma della clinica (tappa 1 della base, 22/11/2026).

Nel processo della prova:
- le porte 5000-5009 (e quelle non valide) si rifiutano, prima di creare qualsiasi cartella;
- la cartella dei dati: mai quella del programma vero, una che la contiene, una che sta dentro o una con un
  agende.db; quella predefinita e' %LOCALAPPDATA%\\GestionaleAgendeProva, e la cartella vera non si crea;
- OGNI sostituzione di chiudi_le_porte, con un elenco scritto qui (non quello di prova.py): percorso_db in
  ogni modulo, email, WhatsApp, registrazione del numero, aggiornamenti, Setup, copie, ripristino,
  importazioni, autoriparazione; una funzione sostituita che torna quella di prima fa cadere la prova;
- la guardia: nei sorgenti, ogni chiamata che puo' andare in rete o lanciare un programma (urlopen, SMTP,
  HTTPConnection, subprocess, webbrowser, socket) sta in una funzione sostituita o in una ammessa qui con il
  perche': una chiamata nuova fa cadere la prova finche' non la si copre in prova.py;
- i dati: fatti, ripresi lo stesso giorno, rifatti con un altro giorno o con il database rovinato;
- le pagine sono quelle del programma con la sola cornice (e «PROVA» nel titolo): tolta la cornice, l'HTML
  e' identico; i pezzi di pagina e il JSON restano senza; cookie e chiave suoi; la cartella dei backup no.
In un processo a parte, come si avvia davvero (python prova.py, con una cartella dei dati di Windows finta
che contiene una cartella vera finta), con una guardia che ferma e scrive ogni connessione verso fuori e ogni
programma lanciato: prova di email, WhatsApp e numero, «Backup ora», cartella dei backup, aggiornamenti da
un indirizzo GitHub, «Aggiorna adesso», un'importazione, il secondo avvio, «Chiudi la prova». Alla fine:
nessuna connessione verso fuori, solo git (la firma dai sorgenti), nessun thread di invii, copie,
aggiornamenti o custode, e la cartella vera finta identica a prima (impronta di ogni file).

    python prove_prova.py
"""
import ast
import hashlib
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import types
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from http.cookiejar import CookieJar

from prove_dove import dove

CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = tempfile.mkdtemp(prefix='prove-prova-')
VUOTA = os.path.join(PROVVISORIA, 'locale-vuota')      # LOCALAPPDATA di questo processo: senza cartella vera
FINTA = os.path.join(PROVVISORIA, 'locale-finta')      # LOCALAPPDATA del processo a parte: con la cartella vera finta
TEMP_FINTA = os.path.join(PROVVISORIA, 'temp')         # la cartella temporanea del processo a parte
for c in (VUOTA, FINTA, TEMP_FINTA):
    os.makedirs(c)
os.environ['LOCALAPPDATA'] = VUOTA
os.environ.pop('GESTIONALE_PORTA', None)
sys.path.insert(0, CARTELLA)

import prova  # noqa: E402

esiti = []


def prova_(nome, f):
    try:
        esiti.append(('OK', nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', nome, '%s · %s' % (dove(e), str(e) or 'asserzione fallita')))
    except Exception as e:
        esiti.append(('ERRORE', nome, '%s · %r' % (dove(e), e)))


def impronta(cartella):
    """Ogni file (percorso, byte, ora di modifica, impronta) e ogni cartella."""
    voci = []
    for radice, sotto, nomi in os.walk(cartella):
        sotto.sort()
        voci.append(('cartella', os.path.relpath(radice, cartella)))
        for n in sorted(nomi):
            p = os.path.join(radice, n)
            st = os.stat(p)
            with open(p, 'rb') as f:
                voci.append((os.path.relpath(p, cartella), st.st_size, st.st_mtime_ns, hashlib.sha256(f.read()).hexdigest()))
    return voci


# =========================================================== nel processo della prova
class Passata(Exception):
    """La porta e' stata accettata: l'avvio e' arrivato alla cartella dei dati (e qui si ferma)."""


def p_porte():
    assert prova.PORTA == 5050 and set(prova.RISERVA) == set(range(5051, 5060)), (prova.PORTA, prova.RISERVA)
    vera = prova.cartella_sicura

    def ferma(cartella):
        raise Passata(cartella)
    prova.cartella_sicura = ferma              # una porta accettata non deve far partire il server qui
    try:
        for porta in list(range(5000, 5010)) + [80, 0, 70000]:
            cartella = os.path.join(PROVVISORIA, 'porta-%d' % porta)
            try:
                prova.principale(['--porta', str(porta), '--dati', cartella, '--senza-browser'])
            except SystemExit as e:
                assert 'porta' in str(e).lower(), 'porta %d rifiutata senza dire perche\': %s' % (porta, e)
            except Passata:
                raise AssertionError('la porta %d e\' stata accettata' % porta)
            assert not os.path.exists(cartella), 'con la porta %d rifiutata e\' stata creata la cartella' % porta
        # gemello: una porta buona arriva fino alla cartella
        try:
            prova.principale(['--porta', '5050', '--dati', os.path.join(PROVVISORIA, 'porta-5050'), '--senza-browser'])
        except Passata:
            pass
        else:
            raise AssertionError('la porta 5050 non arriva alla cartella dei dati')
    finally:
        prova.cartella_sicura = vera


def p_aiuto():
    """L'aiuto delle opzioni si legge: Python 3.14 (quello di CREA_PROVA.bat) controlla gli aiuti di argparse gia'
    all'avvio, e un % sbagliato fermava il doppio clic con una finestra d'errore (trovato in Wine, 22/11/2026)."""
    import contextlib
    import io
    uscita = io.StringIO()
    with contextlib.redirect_stdout(uscita):
        try:
            prova.principale(['--help'])
        except SystemExit as e:
            assert e.code in (0, None), 'uscita %s' % e.code
    testo = uscita.getvalue()
    assert '%LOCALAPPDATA%' in testo and prova.NOME_CARTELLA in testo and '--porta' in testo, testo[-400:]


def p_cartella_sicura():
    vera = os.path.join(VUOTA, 'GestionaleAgende')
    assert prova.cartella_vera() == vera, prova.cartella_vera()
    con_db = os.path.join(PROVVISORIA, 'con-un-database')
    os.makedirs(con_db)
    open(os.path.join(con_db, 'agende.db'), 'wb').close()
    for cattiva in (vera, VUOTA, os.path.join(vera, 'sotto'), con_db, vera + os.sep):
        try:
            prova.cartella_sicura(cattiva)
        except SystemExit as e:
            assert 'clinica' in str(e), str(e)
        else:
            raise AssertionError('la cartella %s e\' stata accettata' % cattiva)
    assert not os.path.exists(vera), 'la cartella vera e\' stata creata'
    assert prova.cartella_predefinita() == os.path.join(VUOTA, 'GestionaleAgendeProva')
    # gemello: le cartelle buone passano, anche quella che comincia come la vera
    for buona in (prova.cartella_predefinita(), os.path.join(VUOTA, 'GestionaleAgendeAltro')):
        assert prova.cartella_sicura(buona) == os.path.abspath(buona) and os.path.isdir(buona), buona


CART = os.path.join(PROVVISORIA, 'cartella-della-prova')
DB = os.path.join(CART, prova.FILE_DB)
os.makedirs(CART)
import modelli  # noqa: E402
import app as A  # noqa: E402
import aggiornamenti  # noqa: E402
import autoripara  # noqa: E402
import backup  # noqa: E402
import comune  # noqa: E402
import importa  # noqa: E402
import invii  # noqa: E402
import viste  # noqa: E402
import accessi  # noqa: E402

# l'elenco delle sostituzioni, scritto qui apposta (non preso da prova.py): (modulo, nome)
SOLLEVANO = {(invii, 'manda_email'): invii.ErroreInvio, (invii, 'manda_whatsapp'): invii.ErroreInvio,
             (invii, 'registra_numero'): invii.ErroreInvio,
             (aggiornamenti, 'leggi_manifesto'): aggiornamenti.ErroreAggiornamento,
             (aggiornamenti, 'scarica'): aggiornamenti.ErroreAggiornamento,
             (aggiornamenti, 'apri'): aggiornamenti.ErroreAggiornamento,
             (aggiornamenti, 'lancia'): aggiornamenti.ErroreAggiornamento,
             (accessi, 'presa_della_rete'): OSError,
             (backup, 'ripristina'): RuntimeError,
             (backup, 'avvia_automatico'): RuntimeError}
NON_FANNO_NIENTE = [(invii, 'avvia'), (aggiornamenti, 'avvia'), (autoripara, 'imposta_riavvio'),
                    (autoripara, 'avvia_custode')]
DANNO = {(aggiornamenti, 'installato'): False, (autoripara, 'riavvia_programma'): False}
# backup.esegui: le importazioni vogliono prima una copia; nella prova si fa, solo del database della prova e solo
# nella sua cartella (lo controlla p_sostituzioni)
COPIA_NELLA_PROVA = (backup, 'esegui')
# le chiamate che vanno in rete o lanciano programmi (vedi g_guardia): sostituite, o ammesse con il perche'
SOSTITUITE = {'%s.%s' % (m.__name__, n) for m, n in list(SOLLEVANO) + NON_FANNO_NIENTE + list(DANNO) + [COPIA_NELLA_PROVA]}
AMMESSE = {
    'app.porta_in_uso': 'si collega solo a 127.0.0.1',
    'app.presa_in_ascolto': 'il server della prova, solo su 127.0.0.1',
    'app.avvia': 'apre il browser sulla pagina della prova',
    'app.principale': 'l\'avvio del programma vero: la prova ha il suo (prova.principale)',
    'app.avvio_non_riuscito': 'del programma vero: la prova ha il suo (prova.avvio_non_riuscito)',
    'autoripara.porta_in_uso': 'si collega solo a 127.0.0.1',
    'autoripara.salute': 'chiede /salute solo a 127.0.0.1',
    'autoripara.processo_nostro': 'legge l\'elenco dei processi (tasklist), per il gestionale.pid della prova',
    'autoripara.chiudi_processo': 'solo il processo che processo_nostro riconosce, dal gestionale.pid della prova',
    'autoripara._lancia': 'la chiama solo riavvia_programma, che nella prova e\' sostituita',
    'prova.firma': 'git, solo dai sorgenti (nell\'eseguibile c\'e\' firma_prova.json)',
    'prova.principale': 'apre il browser sulla pagina della prova gia\' aperta',
    'prova.avvio_non_riuscito': 'apre nel browser la pagina dell\'errore, scritta nella cartella della prova',
}
ORIGINALI = {(m, n): getattr(m, n) for m, n in list(SOLLEVANO) + NON_FANNO_NIENTE + list(DANNO) + [COPIA_NELLA_PROVA]}
PDB_VERO = modelli.percorso_db
try:
    prova.chiudi_le_porte(CART, DB)
    NON_CHIUSE = None
except Exception as e:                       # lo dice p_sostituzioni, con il resto
    NON_CHIUSE = e


def p_sostituzioni():
    if NON_CHIUSE is not None:
        raise NON_CHIUSE
    for (m, n), errore in SOLLEVANO.items():
        f = getattr(m, n)
        assert f is not ORIGINALI[(m, n)], '%s.%s non e\' stata sostituita' % (m.__name__, n)
        try:
            f({'wa_token': '', 'email_utente': ''}, 'x', 'y')
        except errore as e:
            assert 'versione di prova' in str(e), '%s.%s: %s' % (m.__name__, n, e)
            assert not isinstance(e, invii.ErroreInvio) or e.permanente, '%s.%s: l\'errore va detto permanente' \
                % (m.__name__, n)
        else:
            raise AssertionError('%s.%s non dice di no' % (m.__name__, n))
    import threading
    prima = threading.active_count()
    for m, n in NON_FANNO_NIENTE:
        assert getattr(m, n) is not ORIGINALI[(m, n)], '%s.%s non e\' stata sostituita' % (m.__name__, n)
        assert getattr(m, n)(lambda: None) is None
    assert threading.active_count() == prima, 'un lavoro in sottofondo e\' partito'
    for (m, n), valore in DANNO.items():
        f = getattr(m, n)
        assert f is not ORIGINALI[(m, n)], '%s.%s non e\' stata sostituita' % (m.__name__, n)
        assert (f() if n == 'installato' else f('motivo')) is valore, '%s.%s non da\' %r' % (m.__name__, n, valore)
    assert backup.esegui is not ORIGINALI[COPIA_NELLA_PROVA], 'backup.esegui non e\' stata sostituita'
    try:
        backup.esegui(os.path.join(VUOTA, 'GestionaleAgende', 'agende.db'), VUOTA, 'x')
    except AssertionError:
        pass
    else:
        raise AssertionError('backup.esegui copia anche un database che non e\' quello della prova')
    assert aggiornamenti.INDIRIZZO_PREDEFINITO == '' and aggiornamenti.predefinito() == ''
    assert autoripara.PROGRAMMA == 'Gestionale Agende (prova)', 'nome del programma per /salute: %s' % autoripara.PROGRAMMA
    con_percorso = [m for m in list(sys.modules.values()) if callable(getattr(m, 'percorso_db', None))
                    and not isinstance(m, type)]
    nomi = {m.__name__ for m in con_percorso}
    assert {'modelli', 'app', 'comune', 'aggiornamenti'} <= nomi, nomi
    for m in con_percorso:
        assert m.percorso_db is not PDB_VERO and m.percorso_db() == DB, '%s.percorso_db: %s' % (m.__name__, m.percorso_db)
    assert importa.cartella_lavoro().startswith(CART + os.sep), importa.cartella_lavoro()
    assert aggiornamenti.cartella().startswith(CART + os.sep) and comune.cartella_dati() == CART
    assert not os.path.exists(os.path.join(VUOTA, 'GestionaleAgende')), 'la cartella vera e\' stata creata'
    return '%d sostituzioni' % (len(SOLLEVANO) + len(NON_FANNO_NIENTE) + len(DANNO) + len(con_percorso))


def chiamate_verso_fuori():
    """{'modulo.funzione': [righe]} delle chiamate che possono andare in rete o lanciare un programma."""
    primitive = {'urlopen', 'build_opener', 'SMTP', 'SMTP_SSL', 'HTTPConnection', 'HTTPSConnection',
                 'create_connection', 'Popen', 'startfile', 'connect_ex'}
    di_modulo = {('subprocess', 'run'), ('subprocess', 'call'), ('subprocess', 'check_output'),
                 ('subprocess', 'check_call'), ('webbrowser', 'open'), ('webbrowser', 'open_new'),
                 ('webbrowser', 'open_new_tab'), ('socket', 'socket'), ('os', 'system')}
    file_ = [n for n in os.listdir(CARTELLA) if n.endswith('.py') and not n.startswith(('prove', 'campagna'))]
    file_ += [os.path.join('strumenti', 'dati_prova.py'), os.path.join('strumenti', 'catalogo_prova.py')]
    trovate = {}
    for nome in sorted(file_):
        with open(os.path.join(CARTELLA, nome), encoding='utf-8') as f:
            albero = ast.parse(f.read())
        modulo = os.path.basename(nome)[:-3]
        for alto in albero.body:
            for n in ast.walk(alto):
                if not isinstance(n, ast.Call):
                    continue
                f = n.func
                trovata = isinstance(f, ast.Name) and f.id in primitive
                if isinstance(f, ast.Attribute):
                    v = f.value.id if isinstance(f.value, ast.Name) else getattr(f.value, 'attr', None)
                    trovata = f.attr in primitive or (v, f.attr) in di_modulo
                trovata = trovata or any(isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name)
                                         and (a.value.id, a.attr) in di_modulo for a in n.args)
                if trovata:
                    dove_ = alto.name if isinstance(alto, (ast.FunctionDef, ast.ClassDef)) else '(fuori dalle funzioni)'
                    trovate.setdefault('%s.%s' % (modulo, dove_), []).append(n.lineno)
    return trovate


def g_guardia():
    trovate = chiamate_verso_fuori()
    scoperte = ['%s (righe %s)' % (k, ', '.join(map(str, v))) for k, v in sorted(trovate.items())
                if k not in SOSTITUITE and k not in AMMESSE]
    assert not scoperte, ('chiamate verso fuori non coperte dal pacchetto di prova: %s. Vanno sostituite in '
                          'prova.chiudi_le_porte (e scritte qui), o ammesse qui con il perche\'' % '; '.join(scoperte))
    # gemello: la ricerca trova quelle che ci sono (se non trovasse niente, passerebbe sempre)
    for attesa in ('invii.manda_email', 'invii.manda_whatsapp', 'invii.registra_numero', 'aggiornamenti.apri',
                   'aggiornamenti.lancia', 'autoripara.salute', 'prova.firma'):
        assert attesa in trovate, '%s non trovata dalla guardia' % attesa
    vecchie = sorted(set(AMMESSE) - set(trovate))
    assert not vecchie, 'ammesse ma non piu\' nei sorgenti (da togliere da AMMESSE): %s' % vecchie
    return '%d funzioni con chiamate verso fuori, tutte coperte' % len(trovate)


SIG = {'tappa': '1', 'commit': 'abc1234', 'giorno': '2026-11-22', 'costruito': '2026-11-22T10:00:00'}


def lascia(S):
    """Chiude le connessioni al database: su Windows un file aperto non si cancella (fai_dati lo cancella)."""
    S.motore.dispose()


def p_dati():
    S, rifatti, rimasti = prova.dati_pronti(CART, SIG)
    assert rifatti and rimasti == [], (rifatti, rimasti)
    lascia(S)
    S, rifatti, _ = prova.dati_pronti(CART, SIG)
    assert not rifatti, 'lo stesso giorno i dati vanno ripresi, non rifatti'
    lascia(S)
    segno = os.path.join(CART, prova.FILE_SEGNO)
    with open(segno, encoding='utf-8') as f:
        d = json.load(f)
    d['giorno'] = (date.today() - timedelta(days=1)).isoformat()
    with open(segno, 'w', encoding='utf-8') as f:
        json.dump(d, f)
    caricato = os.path.join(CART, 'gestionale-importazioni', 'di-ieri.xlsx')
    os.makedirs(os.path.dirname(caricato), exist_ok=True)
    with open(caricato, 'wb') as f:
        f.write(b'x')
    S, rifatti, _ = prova.dati_pronti(CART, SIG)
    assert rifatti, 'con il segno di ieri i dati vanno rifatti'
    assert not os.path.exists(caricato), 'i file caricati ieri restano'
    lascia(S)
    S, rifatti, _ = prova.dati_pronti(CART, dict(SIG, costruito='2026-11-23T10:00:00'))
    assert rifatti, 'con un pacchetto nuovo i dati vanno rifatti'
    lascia(S)
    with open(DB, 'r+b') as f:                                  # il database rovinato
        f.seek(4096 * 3)
        f.write(b'\xff' * 4096)
    assert not prova.integro(DB)
    S, rifatti, _ = prova.dati_pronti(CART, dict(SIG, costruito='2026-11-23T10:00:00'))
    assert rifatti and prova.integro(DB), 'con il database rovinato i dati vanno rifatti'
    s = S()
    try:
        nome = s.execute(modelli.select(modelli.Struttura.nome).where(modelli.Struttura.id == 1)).scalar()
    finally:
        s.close()
    assert nome == 'Clinica Esempio', nome
    A.Sessione = S
    A._registro = None
    viste._sessionmaker = lambda: S


def pagine_senza_parametri():
    """(indirizzo, risposta attesa) delle pagine GET senza parametri di indirizzi.txt."""
    uscita = []
    with open(os.path.join(CARTELLA, 'indirizzi.txt'), encoding='utf-8') as f:
        for riga in f:
            parti = riga.rstrip('\n').split('\t')
            if not riga.startswith('#') and len(parti) == 4 and 'GET' in parti[0].split(','):
                uscita.append((parti[1], parti[3]))
    return uscita


def risposta(r):
    if r.status_code in (301, 302, 303, 307, 308):
        dove_ = re.sub(r'^https?://[^/]+', '', r.headers.get('Location', '')).split('?')[0]
        return '%d → %s' % (r.status_code, re.sub(r'\d+', 'N', dove_))
    return str(r.status_code)


ORE = re.compile(r'\b\d{1,2}[:.]\d{2}(?::\d{2})?\b')


def p_pagine_con_la_cornice():
    prova.collega_la_prova(A, SIG, [])
    cornice = prova.CORNICE % (prova.scritta(SIG), '')
    funzioni = A.app.after_request_funcs[None]
    metti = next(f for f in funzioni if f.__name__ == 'metti_la_cornice')
    C = A.app.test_client()
    pagine, diverse, cornici, verso_fuori = pagine_senza_parametri(), [], 0, 0
    assert len(pagine) > 50, 'troppo poche pagine in indirizzi.txt: %d' % len(pagine)
    for indirizzo, attesa in pagine:
        dopo = C.get(indirizzo)
        assert risposta(dopo) == attesa, '%s: %s invece di %s' % (indirizzo, risposta(dopo), attesa)
        if dopo.status_code != 200 or dopo.mimetype != 'text/html' or b'<body' not in dopo.data:
            if dopo.status_code >= 400 and dopo.mimetype == 'text/html':       # anche le pagine d'errore dicono PROVA
                assert b'id="cornice-prova"' in dopo.data, '%s: pagina d\'errore senza cornice' % indirizzo
            else:
                assert b'cornice-prova' not in dopo.data, '%s: la cornice in un pezzo di pagina' % indirizzo
            continue
        posto = funzioni.index(metti)
        funzioni.remove(metti)                     # la stessa pagina senza la cornice: il programma di oggi
        try:
            prima = C.get(indirizzo).get_data(as_text=True)
        finally:
            funzioni.insert(posto, metti)
        verso_fuori += len(prova.VERSO_FUORI.findall(prima))
        prima = prova.VERSO_FUORI.sub('href="/prova/contatto"', prima)
        testo = dopo.get_data(as_text=True)
        assert not prova.VERSO_FUORI.search(testo), '%s: un collegamento WhatsApp, telefono o email aperto' % indirizzo
        assert testo.count(cornice) == 1 and testo.count('id="cornice-prova"') == 1, '%s: cornice non una volta' % indirizzo
        assert '<title>PROVA &middot; ' in testo, '%s: il titolo non comincia con PROVA' % indirizzo
        assert 'cornice-prova' not in prima, '%s: cornice anche senza la prova' % indirizzo
        tolta = testo.replace(cornice, '', 1).replace('<title>PROVA &middot; ', '<title>', 1)
        if ORE.sub('H', tolta) != ORE.sub('H', prima):
            diverse.append(indirizzo)
        cornici += 1
    assert not diverse, 'pagine cambiate oltre alla cornice: %s' % diverse
    assert verso_fuori > 0, 'gemello: nessuna pagina aveva collegamenti WhatsApp, telefono o email da spegnere'
    # gemello: i pezzi di pagina e il JSON restano senza cornice
    for indirizzo in ('/salute', '/aggiornamenti/stato.json', '/dove-si-fa/risultati?q=eco'):
        r = C.get(indirizzo)
        assert r.status_code == 200 and b'cornice-prova' not in r.data, indirizzo
    assert C.get('/prova/chiudi').status_code == 200 and b'<form method="post"' in C.get('/prova/chiudi').data
    return '%d pagine con la cornice, identiche senza' % cornici


def p_cookie_e_cartella_dei_backup():
    C = A.app.test_client()
    r = C.post('/impostazioni', data={'azione': 'backup_ora'})
    assert r.status_code == 302
    biscotti = r.headers.getlist('Set-Cookie')
    assert any(b.startswith('gestionale_prova=') for b in biscotti), biscotti
    assert not any(b.startswith('session=') for b in biscotti), biscotti
    assert A.app.secret_key != 'gestionale-locale' and len(A.app.secret_key) >= 32
    copie = os.listdir(os.path.join(CART, 'backup')) if os.path.isdir(os.path.join(CART, 'backup')) else []
    assert any(c.endswith('.db') for c in copie), '«Backup ora» nella prova fa la copia nella sua cartella: %s' % copie
    assert not os.path.exists(os.path.join(VUOTA, 'GestionaleAgende')), 'la cartella vera e\' stata creata'
    altrove = os.path.join(PROVVISORIA, 'cartella-dei-backup-scritta')
    r = C.post('/impostazioni', data={'azione': 'cartella', 'cartella': altrove})
    assert r.status_code == 302 and not os.path.exists(altrove), 'la cartella dei backup e\' stata creata'
    assert 'la cartella dei backup non si cambia' in C.get('/impostazioni').get_data(as_text=True)


def p_cornice_dappertutto():
    """Su una piccola applicazione a parte: la cornice anche nelle pagine d'errore, i collegamenti verso fuori spenti,
    la scritta quando i dati sono di un altro giorno, la firma dai sorgenti senza firma_prova.json."""
    from flask import Flask
    finta = types.SimpleNamespace(app=Flask('finta'))

    @finta.app.route('/con-contatti')
    def con_contatti():
        return ('<!doctype html><html><head><title>T</title></head><body><a href="https://wa.me/39333?text=x">W</a>'
                '<a href="tel:333">T</a><a href="mailto:a@example.it">E</a></body></html>')
    prova.collega_la_prova(finta, SIG, [], giorno_dati=(date.today() - timedelta(days=1)).isoformat())
    C = finta.app.test_client()
    t = C.get('/con-contatti').get_data(as_text=True)
    assert t.count('href="/prova/contatto"') == 3 and 'wa.me' not in t and 'tel:' not in t, t
    assert 'di un altro giorno' in t, 'la scritta non dice che i dati sono di ieri'
    r = C.get('/non-esiste')
    assert r.status_code == 404 and 'id="cornice-prova"' in r.get_data(as_text=True), 'pagina 404 senza cornice'
    assert 'Nella versione di prova WhatsApp' in C.get('/prova/contatto').get_data(as_text=True)
    falsa = os.path.join(prova.cartella_risorse(), prova.FILE_FIRMA)
    assert not os.path.exists(falsa), falsa
    try:
        with open(falsa, 'w', encoding='utf-8') as f:
            json.dump({'tappa': '9', 'commit': 'vecchio', 'giorno': '2000-01-01'}, f)
        assert prova.firma()['commit'] != 'vecchio', 'dai sorgenti la firma viene da firma_prova.json'
    finally:
        os.remove(falsa)


prova_('le porte 5000-5009 si rifiutano, prima di creare la cartella', p_porte)
prova_('l\'aiuto delle opzioni si legge (Python 3.14 lo controlla all\'avvio)', p_aiuto)
prova_('la cartella dei dati non e\' mai quella della clinica', p_cartella_sicura)
prova_('ogni sostituzione di chiudi_le_porte e\' fatta e dice di no', p_sostituzioni)
prova_('guardia: ogni chiamata verso fuori nei sorgenti e\' sostituita o ammessa', g_guardia)
prova_('i dati: fatti, ripresi, rifatti con un altro giorno, un altro pacchetto o il database rovinato', p_dati)
prova_('le pagine di oggi con la sola cornice, nei pezzi e nel JSON niente', p_pagine_con_la_cornice)
prova_('cookie e chiave suoi; «Backup ora» copia nella cartella della prova; la cartella dei backup non si cambia', p_cookie_e_cartella_dei_backup)
prova_('cornice anche sugli errori, WhatsApp, telefono ed email spenti, dati di un altro giorno, firma', p_cornice_dappertutto)


# =========================================================== in un processo a parte, come si avvia davvero
GUARDIA = r'''
import json, os, socket, sys, threading
REGISTRO, SORGENTI, ARGOMENTI = sys.argv[1], sys.argv[2], sys.argv[3:]
LOCALI = ('127.0.0.1', 'localhost', '::1', '0.0.0.0', '', 'None')
def scrivi(voce):
    with open(REGISTRO, 'a', encoding='utf-8') as f:
        f.write(json.dumps(voce) + '\n')
def guardia(evento, a):
    if evento == 'socket.connect':
        if isinstance(a[1], tuple) and a[1] and str(a[1][0]) not in LOCALI:
            scrivi({'rete': 'connect', 'a': str(a[1][0])})
            raise ConnectionRefusedError('prove_prova: connessione verso fuori fermata')
    elif evento == 'socket.getaddrinfo':
        if str(a[0]) not in LOCALI:
            scrivi({'rete': 'getaddrinfo', 'a': str(a[0])})
            raise socket.gaierror('prove_prova: nome verso fuori fermato')
    elif evento == 'subprocess.Popen':
        scrivi({'processo': [str(x) for x in (a[1] if isinstance(a[1], (list, tuple)) else [a[1]])]})
    elif evento == 'os.startfile':
        scrivi({'processo': ['startfile', str(a[0])]})
sys.addaudithook(guardia)
_parti = threading.Thread.start
def parti(self):
    scrivi({'filo': self.name, 'funzione': getattr(getattr(self, '_target', None), '__qualname__', '')})
    return _parti(self)
threading.Thread.start = parti
try:                                           # gemello: la guardia ferma davvero un nome verso fuori
    socket.getaddrinfo('esempio-della-prova.invalid', 443)
except OSError:
    scrivi({'gemello': 'fermato'})
sys.path.insert(0, SORGENTI)
import prova
prova.principale(ARGOMENTI)
'''


def porta_libera():
    while True:
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            p = s.getsockname()[1]
        if not 5000 <= p < 5060:
            return p


PORTA = porta_libera()
BASE = 'http://127.0.0.1:%d' % PORTA
AMBIENTE = {k: v for k, v in os.environ.items() if k not in ('GESTIONALE_PORTA', 'GESTIONALE_PROVE_RIGIDE')}
AMBIENTE.update(LOCALAPPDATA=FINTA, TEMP=TEMP_FINTA, TMP=TEMP_FINTA, TMPDIR=TEMP_FINTA, PYTHONIOENCODING='utf-8')
VERA = os.path.join(FINTA, 'GestionaleAgende')
DATI = os.path.join(FINTA, 'GestionaleAgendeProva')
REGISTRI = os.path.join(PROVVISORIA, 'guardia-%d.jsonl')
cliente = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(CookieJar()))


def prepara_la_cartella_vera():
    """Una cartella vera finta, come quella della clinica (solo dati inventati)."""
    os.makedirs(os.path.join(VERA, 'backup'))
    c = sqlite3.connect(os.path.join(VERA, 'agende.db'))
    c.execute('CREATE TABLE segno (testo TEXT)')
    c.execute("INSERT INTO segno VALUES ('database della clinica finto: non va toccato')")
    c.commit()
    c.close()
    for nome, testo in (('gestionale.log', 'registro finto\n'), ('gestionale.lock', ''),
                        ('gestionale.pid', json.dumps({'pid': 4, 'porta': 5000, 'fase': 'in servizio'})),
                        ('autoriparazione.json', '{}'), (os.path.join('backup', 'agende-2026-11-20_101010.db'), 'x')):
        with open(os.path.join(VERA, nome), 'w', encoding='utf-8') as f:
            f.write(testo)


def avvia(n, *argomenti):
    """Il processo della prova, con la guardia: (processo, file della guardia)."""
    registro = REGISTRI % n
    p = subprocess.Popen([sys.executable, '-c', GUARDIA, registro, CARTELLA] + list(argomenti), cwd=PROVVISORIA,
                         env=AMBIENTE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p, registro


def guardia_di(registro):
    try:
        with open(registro, encoding='utf-8') as f:
            return [json.loads(r) for r in f if r.strip()]
    except OSError:
        return []


def chiedi(indirizzo, campi=None, origine=BASE, corpo=None, tipo=None):
    """(codice, testo) della pagina, seguendo i rimandi (con i messaggi della pagina dopo)."""
    dati = corpo if corpo is not None else (urllib.parse.urlencode(campi).encode() if campi is not None else None)
    r = urllib.request.Request(BASE + indirizzo, data=dati)
    if dati is not None:
        r.add_header('Origin', origine)
        if tipo:
            r.add_header('Content-Type', tipo)
    try:
        with cliente.open(r, timeout=60) as risposta_:
            return risposta_.status, risposta_.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')


def aspetta(condizione, secondi):
    fine = time.monotonic() + secondi
    while time.monotonic() < fine:
        if condizione():
            return True
        time.sleep(0.3)
    return condizione()


def risponde():
    try:
        return json.loads(chiedi('/salute')[1]).get('programma') == 'Gestionale Agende (prova)'
    except (OSError, ValueError):
        return False


def scrivi_impostazioni(valori):
    c = sqlite3.connect(os.path.join(DATI, prova.FILE_DB), timeout=30)
    try:
        for k, v in valori.items():
            c.execute('INSERT OR REPLACE INTO impostazioni (chiave, valore) VALUES (?, ?)', (k, v))
        c.commit()
    finally:
        c.close()


def file_csv():
    confine = 'confine-della-prova'
    righe = 'Cognome;Nome;Telefono\r\nProvolo;Ugo;3330000103\r\nFintini;Prova;3330000101\r\n'
    corpo = ('--%s\r\nContent-Disposition: form-data; name="tipo"\r\n\r\npazienti\r\n'
             '--%s\r\nContent-Disposition: form-data; name="file"; filename="pazienti-finti.csv"\r\n'
             'Content-Type: text/csv\r\n\r\n%s\r\n--%s--\r\n' % (confine, confine, righe, confine)).encode('utf-8')
    return corpo, 'multipart/form-data; boundary=%s' % confine


def p_avvio_vero():
    prepara_la_cartella_vera()
    prima = impronta(VERA)
    p, registro = avvia(1, '--senza-browser', '--porta', str(PORTA))
    try:
        aspetta(lambda: p.poll() is not None or risponde(), 180)
        if p.poll() is not None:
            raise AssertionError('la prova si e\' fermata (uscita %s): %s' % (
                p.returncode, p.stdout.read().decode('utf-8', 'replace')[-1500:]))
        assert risponde(), 'la prova non risponde dopo 3 minuti'
        codice, oggi = chiedi('/')
        assert codice == 200 and 'id="cornice-prova"' in oggi and '<title>PROVA &middot; ' in oggi, 'pagina Oggi'
        assert 'Clinica Esempio' in oggi and 'Posillipo' not in oggi, 'nella pagina Oggi non ci sono i nomi inventati'
        # email e WhatsApp pronti a partire (la casella dei dati di prova c'e' gia', con i promemoria accesi)
        scrivi_impostazioni({'email_attiva': '1', 'wa_token': invii.proteggi('token-finto'),
                             'wa_numero_id': '123456789012345', 'wa_modello': 'promemoria_appuntamento'})
        _, t = chiedi('/invii', {'azione': 'prova_email', 'a': 'prova@example.it'})
        assert 'email e WhatsApp non partono mai' in t, 'la prova dell\'email non dice di no'
        _, t = chiedi('/invii', {'azione': 'prova_whatsapp', 'a': '3331234567'})
        assert 'email e WhatsApp non partono mai' in t, 'la prova di WhatsApp non dice di no'
        _, t = chiedi('/invii', {'azione': 'registra_whatsapp', 'pin': '123456'})
        assert 'email e WhatsApp non partono mai' in t, 'la registrazione del numero non dice di no'
        _, t = chiedi('/impostazioni', {'azione': 'backup_ora'})
        # nella prova la copia si fa, ma solo nella sua cartella (la cartella vera resta intatta: impronta in fondo)
        assert 'Backup non riuscito' not in t, '«Backup ora» nella prova non riesce: %s' % t[:300]
        altrove = os.path.join(PROVVISORIA, 'cartella-dei-backup-dal-browser')
        _, t = chiedi('/impostazioni', {'azione': 'cartella', 'cartella': altrove})
        assert 'non si cambia' in t and not os.path.exists(altrove), 'la cartella dei backup e\' cambiata'
        # aggiornamenti: un indirizzo di GitHub scritto a mano non va su internet
        indirizzo = 'https://github.com/esempio/esempio/releases/latest/download/'
        codice, t = chiedi('/aggiornamenti', {'azione': 'indirizzo', 'indirizzo': indirizzo})
        assert codice == 200, 'pagina Aggiornamenti con un indirizzo scritto: %d' % codice

        def errore_aggiornamenti():
            return 'versione di prova' in (json.loads(chiedi('/aggiornamenti/stato.json')[1]).get('errore') or '')
        assert aspetta(errore_aggiornamenti, 30), chiedi('/aggiornamenti/stato.json')[1]
        _, t = chiedi('/aggiornamenti/aggiorna', {})
        assert 'un aggiornamento pronto' in t, '«Aggiorna adesso» senza aggiornamento'
        corpo, tipo = file_csv()
        codice, _ = chiedi('/importa', corpo=corpo, tipo=tipo)
        lavoro = os.path.join(DATI, 'gestionale-importazioni')
        assert os.path.isdir(lavoro) and any(n.endswith('.dat') for n in os.listdir(lavoro)), \
            'il file importato non e\' nella cartella della prova (risposta %d)' % codice
        assert not os.path.exists(os.path.join(TEMP_FINTA, 'gestionale-importazioni')), 'importazione in %TEMP%'
        # il secondo avvio apre solo la pagina della prima
        p2, registro2 = avvia(2, '--senza-browser', '--porta', str(PORTA))
        try:
            p2.wait(90)
        except subprocess.TimeoutExpired:
            p2.kill()
            raise AssertionError('il secondo avvio non si chiude da solo')
        assert p2.returncode == 0, p2.stdout.read().decode('utf-8', 'replace')[-2000:]
        with open(os.path.join(DATI, prova.FILE_REGISTRO), encoding='utf-8') as f:
            assert "prova gia' aperta" in f.read(), 'il secondo avvio non dice che la prova e\' gia\' aperta'
        assert risponde(), 'dopo il secondo avvio la prima prova non risponde piu\''
        # «Chiudi la prova»: da un'altra porta no, dalla prova si'
        codice, t = chiedi('/prova/chiudi')
        assert codice == 200 and 'Chiudi la prova' in t
        assert chiedi('/prova/chiudi', {}, origine='http://127.0.0.1:5000')[0] == 403, 'chiusa da un\'altra porta'
        assert risponde()
        codice, t = chiedi('/prova/chiudi', {})
        assert codice == 200 and 'chiusa' in t, t[:300]
        p.wait(30)
        assert p.returncode == 0, 'uscita %s' % p.returncode
    finally:
        if p.poll() is None:
            p.kill()
            p.wait(10)
    voci = guardia_di(registro) + guardia_di(registro2)
    assert sum(1 for v in voci if v.get('gemello')) == 2, 'la guardia non ha fermato il nome del gemello: %s' % voci
    verso_fuori = [v for v in voci if 'rete' in v and v['a'] != 'esempio-della-prova.invalid']
    assert not verso_fuori, 'connessioni verso fuori: %s' % verso_fuori
    processi = [v['processo'] for v in voci if 'processo' in v and os.path.basename(v['processo'][0]) not in ('git', 'git.exe')]
    assert not processi, 'programmi lanciati: %s' % processi
    fili = [v['filo'] for v in voci if 'filo' in v]
    vietati = [f for f in fili if f in ('invii', 'backup', 'aggiornamenti', 'custode', 'aggiornamento')]
    assert not vietati, 'lavori in sottofondo partiti: %s' % vietati
    assert 'controllo-aggiornamenti' in fili, 'gemello: la guardia non ha visto i thread (%s)' % fili
    assert impronta(VERA) == prima, 'la cartella vera finta e\' cambiata'
    assert sorted(os.listdir(FINTA)) == ['GestionaleAgende', 'GestionaleAgendeProva'], os.listdir(FINTA)
    assert os.path.isfile(os.path.join(DATI, prova.FILE_DB)), 'il database della prova non e\' nella sua cartella'
    return 'porta %d, %d voci della guardia, %d thread' % (PORTA, len(voci), len(fili))


def p_porta_rifiutata_davvero():
    locale = os.path.join(PROVVISORIA, 'locale-porta')
    os.makedirs(locale)
    r = subprocess.run([sys.executable, os.path.join(CARTELLA, 'prova.py'), '--porta', '5000', '--senza-browser'],
                       cwd=PROVVISORIA, env=dict(AMBIENTE, LOCALAPPDATA=locale), capture_output=True, timeout=120)
    assert r.returncode != 0 and b'5000-5009' in r.stderr, (r.returncode, r.stderr[-500:])
    assert os.listdir(locale) == [], 'con la porta 5000 e\' stata creata una cartella: %s' % os.listdir(locale)


prova_('avviata davvero: nessuna connessione verso fuori, la cartella vera intatta, secondo avvio e chiusura',
       p_avvio_vero)
prova_('avviata davvero sulla porta 5000: si rifiuta', p_porta_rifiutata_davvero)

shutil.rmtree(PROVVISORIA, ignore_errors=True)
for esito, nome, dettaglio in esiti:
    print('%-6s %s %s' % (esito, nome, dettaglio))
rotte = [e for e in esiti if e[0] != 'OK']
print('%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(rotte), len(rotte)))
sys.exit(1 if rotte else 0)
