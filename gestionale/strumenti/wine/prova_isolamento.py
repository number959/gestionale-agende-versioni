# -*- coding: utf-8 -*-
"""Il pacchetto di prova per Windows accanto al programma installato, nel Windows finto (Wine): la prova non
deve toccare il programma della clinica (tappa 1 della base, 22/11/2026).

    python3 strumenti/wine/prova_isolamento.py dist/windows/GestionaleProva-tappa1-<commit>-<giorno>.exe

Prima: il programma installato nel Windows finto (strumenti/wine/installa.sh con un Setup; i suoi dati in
...\\AppData\\Local\\GestionaleAgende) e il pacchetto costruito con strumenti/wine/costruisci.sh --prova.

Cosa fa: apre il programma installato su :5000 se non risponde (e aspetta che abbia fatto i suoi primi lavori:
la copia del giorno e il primo controllo degli aggiornamenti), prende l'impronta di ogni file della sua
cartella dei dati che non cambia da solo (agende.db, le copie, i Setup scaricati, i certificati) e il punto
del suo registro. Poi apre il pacchetto come un doppio clic, senza opzioni, sotto strace (ogni connect() dei
processi della prova finisce in un file), e lo usa: pagine con la cornice, prova dell'email, «Backup ora», un
indirizzo degli aggiornamenti di GitHub, un secondo doppio clic, «Chiudi la prova». Alla fine controlla:
- l'impronta della cartella dell'installato uguale a prima (agende.db compreso) e il suo registro senza invii
  ne' errori nuovi;
- l'installato sempre sulla 5000, con lo stesso processo, e la prova sulla 5050: porte, nomi del programma e
  cookie diversi; l'installato non scambia la prova per se stesso;
- la cartella della prova accanto a quella vera (...\\AppData\\Local\\GestionaleAgendeProva), con i suoi file;
- nessuna connessione dei processi della prova fuori da 127.0.0.1 (e niente nomi chiesti al DNS);
- dopo «Chiudi la prova» nessun processo della prova e la porta 5050 libera.
I dati dell'installato nel Windows finto possono venire in parte dalle agende vere: questo script non ne
stampa mai il contenuto, solo impronte e conteggi."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

QUI = os.path.dirname(os.path.abspath(__file__))
if len(sys.argv) < 2 or not os.path.isfile(sys.argv[1]) or not sys.argv[1].lower().endswith('.exe'):
    raise SystemExit('uso: python3 strumenti/wine/prova_isolamento.py <GestionaleProva-...exe>')
ESEGUIBILE = os.path.abspath(sys.argv[1])
NOME = os.path.basename(ESEGUIBILE)
assert NOME.lower().startswith('gestionaleprova-') and NOME.lower() != 'gestionale.exe', NOME

# l'ambiente di ambiente.sh (WINEPREFIX, WINE, schermo finto), letto da bash
uscita = subprocess.run(['bash', '-c', '. "%s/ambiente.sh" >/dev/null && avvia_schermo >/dev/null && '
                         'printf "%%s\\0" "$WINE" "$CARTELLA_DATI" && env -0' % QUI],
                        capture_output=True, check=True).stdout.decode('utf-8', 'replace').split('\0')
WINE, CARTELLA_VERA = uscita[0], uscita[1]
AMBIENTE = dict(x.split('=', 1) for x in uscita[2:] if '=' in x)
PREFISSO = AMBIENTE['WINEPREFIX']
C = os.path.join(PREFISSO, 'drive_c')
LOCALE = os.path.dirname(CARTELLA_VERA)
CARTELLA_PROVA = os.path.join(LOCALE, 'GestionaleAgendeProva')
INSTALLATO = os.path.join(LOCALE, 'Programs', 'Gestionale Agende', 'Gestionale.exe')
LAVORO = os.path.join(C, 'prova-isolamento')
VERA, PROVA = 'http://127.0.0.1:5000', 'http://127.0.0.1:5050'
# file che il programma installato cambia da solo mentre gira (battito, registro, diario)
CAMBIANO_DA_SOLI = {'gestionale.pid', 'gestionale.log', 'autoriparazione.json', 'gestionale.lock'}
esiti = []


def controlla(nome, condizione, dettaglio=''):
    esiti.append((bool(condizione), nome, dettaglio))
    print('%s %s%s' % ('OK  ' if condizione else 'NO  ', nome, ('  (%s)' % dettaglio) if dettaglio else ''), flush=True)


def impronta():
    voci = {}
    for radice, sotto, nomi in os.walk(CARTELLA_VERA):
        sotto.sort()
        for n in sorted(nomi):
            p = os.path.join(radice, n)
            rel = os.path.relpath(p, CARTELLA_VERA)
            if rel in CAMBIANO_DA_SOLI or re.fullmatch(r'gestionale\.log\.\d', rel):
                continue
            with open(p, 'rb') as f:
                voci[rel] = (os.path.getsize(p), hashlib.sha256(f.read()).hexdigest())
    return voci


senza_proxy = urllib.request.ProxyHandler({})


def chiedi(base, indirizzo, campi=None, cliente=None):
    """(codice, intestazioni, testo)."""
    dati = urllib.parse.urlencode(campi).encode() if campi is not None else None
    r = urllib.request.Request(base + indirizzo, data=dati)
    if dati is not None:
        r.add_header('Origin', base)
    try:
        with (cliente or urllib.request.build_opener(senza_proxy)).open(r, timeout=60) as x:
            return x.status, x.headers, x.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read().decode('utf-8', 'replace')
    except OSError as e:
        return None, {}, str(e)


def leggi_json(base, indirizzo):
    try:
        d = json.loads(chiedi(base, indirizzo)[2])
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


def salute(base):
    return leggi_json(base, '/salute')


def aspetta(condizione, secondi):
    fine = time.monotonic() + secondi
    while time.monotonic() < fine:
        if condizione():
            return True
        time.sleep(1)
    return condizione()


def in_wine(riga, registro, strace=None):
    """Lancia 'riga' nel Windows finto dentro un terminale finto (il Python dell'eseguibile lo vuole), staccato."""
    comando = ['script', '-qec', '%s %s' % (WINE, riga), '/dev/null']
    if strace:
        comando = ['strace', '-f', '-qq', '-e', 'trace=connect,execve,clone,clone3,fork,vfork', '-o', strace] + comando
    return subprocess.Popen(comando, cwd=C, env=AMBIENTE, stdin=subprocess.DEVNULL, stdout=open(registro, 'wb'),
                            stderr=subprocess.STDOUT, start_new_session=True)


def processi_della_prova(anche_strace=False):
    righe = subprocess.run(['ps', '-eo', 'pid=,args='], capture_output=True, text=True).stdout.splitlines()
    return [r for r in righe if 'GestionaleProva' in r and 'prova_isolamento' not in r
            and (anche_strace or ('strace' not in r and 'script -qec' not in r))]


def chiudi_tutto_della_prova():
    """I processi della prova rimasti (anche strace e il terminale finto): si chiudono per numero, mai per nome."""
    for r in processi_della_prova(anche_strace=True):
        try:
            os.kill(int(r.split()[0]), 9)
        except (OSError, ValueError):
            pass


def fermati(motivo):
    """La prova non e' partita: una foto dello schermo finto (una finestra d'errore di Windows si vede li') e via."""
    foto = os.path.join(LAVORO, 'schermo.png')
    if shutil.which('import'):
        subprocess.run(['import', '-window', 'root', foto], env=AMBIENTE, capture_output=True, timeout=30)
    chiudi_tutto_della_prova()
    print('\n%s. Lo schermo del Windows finto e\' in %s; i registri in %s.' % (motivo, foto, LAVORO), flush=True)
    sys.exit(1)


if not os.path.isfile(os.path.join(CARTELLA_VERA, 'agende.db')) or not os.path.isfile(INSTALLATO):
    raise SystemExit('Nel Windows finto non c\'e\' il programma installato: prima strumenti/wine/installa.sh con un Setup.')
if os.path.exists(LAVORO):
    shutil.rmtree(LAVORO)
os.makedirs(LAVORO)
print('Windows finto: %s\nprogramma installato: %s\npacchetto: %s\n' % (PREFISSO, INSTALLATO, NOME), flush=True)

# 1. il programma installato aperto, sulla 5000, con i primi lavori fatti
if salute(VERA).get('programma') != 'Gestionale Agende':
    print('apro il programma installato...', flush=True)
    in_wine('"C:\\\\users\\\\%s\\\\AppData\\\\Local\\\\Programs\\\\Gestionale Agende\\\\Gestionale.exe" --avvio-automatico; '
            'sleep 36000' % os.path.basename(os.path.dirname(os.path.dirname(LOCALE))), os.path.join(LAVORO, 'installato.out'))
controlla('il programma installato risponde sulla 5000', aspetta(lambda: salute(VERA).get('programma') == 'Gestionale Agende', 180),
          'versione %s' % salute(VERA).get('versione'))
with open(os.path.join(CARTELLA_VERA, 'gestionale.pid'), encoding='utf-8') as f:
    pid_vero = json.load(f)
avviato = time.mktime(time.strptime(pid_vero['avviato'], '%Y-%m-%dT%H:%M:%S'))
attesa = 150 - (time.time() - avviato)
if attesa > 0:
    print('aspetto %d s: la copia del giorno e il primo controllo degli aggiornamenti dell\'installato' % attesa, flush=True)
    time.sleep(attesa)
prima = impronta()
with open(os.path.join(CARTELLA_VERA, 'gestionale.log'), 'rb') as f:
    punto_del_registro = len(f.read())
salute_vera = salute(VERA)
controlla('cartella vera: impronta presa', 'agende.db' in prima, '%d file, agende.db compreso' % len(prima))

# 2. il pacchetto, come un doppio clic (senza opzioni), sotto strace
if salute(PROVA):
    raise SystemExit('Sulla 5050 risponde gia\' qualcosa: chiudere la prova aperta prima.')
# in Wine il connect() dei socket di Windows lo fa wineserver (uno solo per il Windows finto, lo stesso
# dell'installato): si guarda anche lui, per tutto il tempo della prova
server = [r.split()[0] for r in subprocess.run(['ps', '-eo', 'pid=,comm='], capture_output=True, text=True).stdout.splitlines()
          if r.split()[1:] in (['wineserver'], ['wineserver64'])]
del_server = os.path.join(LAVORO, 'connessioni-wineserver.txt')
spia = subprocess.Popen(['strace', '-f', '-qq', '-e', 'trace=connect', '-o', del_server, '-p', server[0]],
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) if server else None
time.sleep(2)
copia = os.path.join(LAVORO, NOME)
shutil.copy2(ESEGUIBILE, copia)
connessioni = [os.path.join(LAVORO, 'connessioni-%d.txt' % n) for n in (1, 2)]
t0 = time.time()
in_wine('C:\\\\prova-isolamento\\\\%s' % NOME, os.path.join(LAVORO, 'prova-1.out'), strace=connessioni[0])
controlla('la prova risponde sulla 5050', aspetta(lambda: salute(PROVA).get('programma') == 'Gestionale Agende (prova)', 300),
          '%.0f s dal doppio clic' % (time.time() - t0))
if not esiti[-1][0]:
    fermati('La prova non risponde dopo 5 minuti')
biscotti = CookieJar()
cliente = urllib.request.build_opener(senza_proxy, urllib.request.HTTPCookieProcessor(biscotti))
codice, intestazioni, oggi = chiedi(PROVA, '/', cliente=cliente)
m = re.search(r'Versione di prova &middot; (tappa [^<]*?) &middot; dati inventati', oggi)
controlla('pagina Oggi della prova con la cornice e «PROVA» nel titolo',
          codice == 200 and oggi.count('id="cornice-prova"') == 1 and '<title>PROVA &middot; ' in oggi, m.group(1) if m else '')
controlla('nella prova i nomi inventati', 'Clinica Esempio' in oggi and 'Posillipo' not in oggi)
_, _, t = chiedi(PROVA, '/invii', {'azione': 'prova_email', 'a': 'prova@example.it'}, cliente)
controlla('prova dell\'email: dice di no', 'non partono mai' in t)
_, _, t = chiedi(PROVA, '/impostazioni', {'azione': 'backup_ora'}, cliente)
controlla('«Backup ora»: dice di no', 'versione di prova' in t)
chiedi(PROVA, '/aggiornamenti', {'azione': 'indirizzo', 'indirizzo': 'https://github.com/esempio/esempio/releases/latest/download/'},
       cliente)
controlla('aggiornamenti da un indirizzo di GitHub: dice di no', aspetta(lambda: 'versione di prova' in (
    leggi_json(PROVA, '/aggiornamenti/stato.json').get('errore') or ''), 30))
# le pagine senza parametri di indirizzi.txt che rispondono 200 (le stesse di prove_indirizzi.py)
with open(os.path.join(QUI, '..', '..', 'indirizzi.txt'), encoding='utf-8') as f:
    pagine = [r.split('\t')[1] for r in f.read().splitlines()
              if not r.startswith('#') and r.count('\t') == 3 and r.split('\t')[3] == '200' and 'GET' in r.split('\t')[0]]
male, cornici = [], 0
for indirizzo in pagine:
    codice, intest, testo = chiedi(PROVA, indirizzo, cliente=cliente)
    if codice != 200:
        male.append('%s %s' % (indirizzo, codice))
    elif 'text/html' in intest.get('Content-Type', '') and '<body' in testo:
        cornici += 1
        if testo.count('id="cornice-prova"') != 1:
            male.append('%s senza cornice' % indirizzo)
controlla('le pagine della prova rispondono, con la cornice', not male and cornici > 20,
          ', '.join(male) or '%d pagine, %d con la cornice' % (len(pagine), cornici))


class SenzaRimandi(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


codice, intest, _ = chiedi(PROVA, '/impostazioni', {'azione': 'backup_ora'},
                           urllib.request.build_opener(senza_proxy, SenzaRimandi))
nomi_biscotti = sorted({v.split('=', 1)[0] for k, v in intest.items() if k.lower() == 'set-cookie'})
controlla('il cookie della prova ha il suo nome (quello dell\'installato e\' «session»)', nomi_biscotti == ['gestionale_prova'],
          ', '.join(nomi_biscotti) or 'nessun cookie (risposta %s)' % codice)
# un secondo doppio clic: apre solo la pagina della prima
t1 = time.time()
secondo = in_wine('C:\\\\prova-isolamento\\\\%s' % NOME, os.path.join(LAVORO, 'prova-2.out'), strace=connessioni[1])
aspetta(lambda: secondo.poll() is not None, 120)
controlla('il secondo doppio clic si chiude da solo e la prima resta aperta',
          secondo.poll() is not None and salute(PROVA).get('programma') == 'Gestionale Agende (prova)', '%.0f s' % (time.time() - t1))
# l'installato intanto: stesso processo, sempre sulla 5000, e non riconosce la prova come se stesso
controlla('l\'installato sempre sulla 5000 con lo stesso processo', salute(VERA).get('pid') == salute_vera.get('pid')
          and salute(VERA).get('programma') == 'Gestionale Agende', 'pid %s' % salute_vera.get('pid'))
controlla('porte e nomi diversi: 5000 «Gestionale Agende», 5050 «Gestionale Agende (prova)»',
          salute(PROVA).get('programma') == 'Gestionale Agende (prova)' and salute(PROVA).get('pid') != salute_vera.get('pid'))
# «Chiudi la prova»
codice, _, t = chiedi(PROVA, '/prova/chiudi', {}, cliente)
controlla('«Chiudi la prova»', codice == 200 and 'chiusa' in t)
controlla('dopo «Chiudi la prova» la 5050 e\' libera e non restano processi della prova',
          aspetta(lambda: not salute(PROVA) and not processi_della_prova(), 60), '; '.join(processi_della_prova())[:200])
chiudi_tutto_della_prova()             # strace e il terminale finto, se restano
time.sleep(2)
if spia is not None:
    spia.terminate()
    spia.wait(30)

# 3. i conti
dopo = impronta()
cambiati = sorted(k for k in set(prima) | set(dopo) if prima.get(k) != dopo.get(k))
controlla('la cartella del programma installato e\' identica (agende.db compreso)', not cambiati,
          ('cambiati: %s' % ', '.join(cambiati)) if cambiati else '%d file con la stessa impronta' % len(dopo))
with open(os.path.join(CARTELLA_VERA, 'gestionale.log'), 'rb') as f:
    nuove = f.read()[punto_del_registro:].decode('utf-8', 'replace').splitlines()
sospette = [r for r in nuove if re.search(r'invi|email|whatsapp|promemoria|ERROR|backup fatto|ripristin|porta', r, re.I)]
controlla('il registro dell\'installato: nessun invio, copia o errore nuovo', not sospette,
          '%d righe nuove%s' % (len(nuove), (', sospette: %d' % len(sospette)) if sospette else ''))
with open(os.path.join(CARTELLA_VERA, 'gestionale.pid'), encoding='utf-8') as f:
    pid_dopo = json.load(f)
controlla('il gestionale.pid dell\'installato e\' ancora il suo, sulla 5000',
          pid_dopo.get('pid') == pid_vero.get('pid') and pid_dopo.get('porta') == 5000)
file_prova = sorted(os.listdir(CARTELLA_PROVA)) if os.path.isdir(CARTELLA_PROVA) else []
controlla('la cartella della prova e\' accanto a quella vera, con i suoi file',
          {'prova.db', 'prova.log', 'gestionale.lock', 'gestionale.pid', 'dati-della-prova.json'} <= set(file_prova),
          ', '.join(file_prova))
def connessioni_fuori(nome):
    """Dal file di strace: (connessioni dei processi di Wine fuori da 127.0.0.1, connect() guardate, altri programmi
    Linux aperti, per esempio un browser aperto dal doppio clic, con le loro connessioni a parte)."""
    programma, prima_di, fuori, guardate, altri = {}, {}, [], 0, {}
    with open(nome, encoding='utf-8', errors='replace') as f:
        for riga in f:
            m = re.match(r'(\d+)\s+(.*)', riga)
            if not m:
                continue
            pid, resto = m.groups()
            figlio = re.match(r'(?:clone3?|v?fork)\(.*\) = (\d+)$', resto.strip())
            if figlio:
                programma[figlio.group(1)] = programma.get(pid, '')
                continue
            eseguito = re.match(r'execve\("([^"]+)"', resto)
            if eseguito and '= -1' not in resto:
                prima_di[pid] = programma.get(pid, '')
                programma[pid] = eseguito.group(1)
                continue
            if resto.startswith('<... execve resumed>') and '= -1' in resto and pid in prima_di:
                programma[pid] = prima_di.pop(pid)
                continue
            if resto.startswith('connect('):
                guardate += 1
                ind = re.search(r'sin6?_addr=inet_(?:addr|pton)\((?:AF_INET6, )?"([^"]+)"\)', resto)
                if ind and ind.group(1) not in ('127.0.0.1', '::1', '::ffff:127.0.0.1'):
                    di = programma.get(pid, '?')
                    voce = '%s%s' % (ind.group(1), ' (DNS)' if 'htons(53)' in resto else '')
                    if 'wine' in di or di in ('?', ''):
                        fuori.append(voce)
                    else:
                        altri.setdefault(os.path.basename(di), []).append(voce)
    for p in set(programma.values()):
        if p and 'wine' not in p and os.path.basename(p) not in ('script', 'sh', 'bash', 'dash', 'sleep'):
            altri.setdefault(os.path.basename(p), [])
    return fuori, guardate, altri


fuori, guardate, altri = [], 0, {}
for nome in connessioni:
    try:
        f_, g_, a_ = connessioni_fuori(nome)
    except OSError:
        f_, g_, a_ = ['%s mancante' % os.path.basename(nome)], 0, {}
    fuori += f_
    guardate += g_
    for k, v in a_.items():
        altri.setdefault(k, []).extend(v)
controlla('i processi della prova: nessuna connessione fuori da 127.0.0.1, nessun nome chiesto al DNS (strace)',
          not fuori and guardate > 0, ('verso: %s' % ', '.join(sorted(set(fuori)))) if fuori else '%d connect() guardate' % guardate)
locali, verso_fuori = 0, []
try:
    with open(del_server, encoding='utf-8', errors='replace') as f:
        for riga in f:
            ind = re.search(r'connect\(.*sin6?_addr=inet_(?:addr|pton)\((?:AF_INET6, )?"([^"]+)"\)', riga)
            if ind:
                if ind.group(1) in ('127.0.0.1', '::1', '::ffff:127.0.0.1'):
                    locali += 1
                else:
                    verso_fuori.append(ind.group(1))
except OSError:
    verso_fuori.append('wineserver non guardato')
# gemello: le connessioni della prova a se stessa (il secondo doppio clic chiede /salute) si devono vedere
controlla('wineserver durante la prova: nessuna connessione fuori da 127.0.0.1, ne\' della prova ne\' dell\'installato',
          not verso_fuori and locali > 0, ('verso: %s' % ', '.join(sorted(set(verso_fuori)))) if verso_fuori else
          '%d connessioni a 127.0.0.1 viste' % locali)
if altri:
    print('     programmi Linux aperti dalla prova (il browser del doppio clic), non contati: %s'
          % '; '.join('%s %s' % (k, sorted(set(v)) or '') for k, v in sorted(altri.items())), flush=True)
fallite = [e for e in esiti if not e[0]]
print('\n%d controlli, %d a posto%s' % (len(esiti), len(esiti) - len(fallite), '' if not fallite else ': DA GUARDARE'))
sys.exit(1 if fallite else 0)
