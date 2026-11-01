# -*- coding: utf-8 -*-
"""L'autoriparazione sul programma INSTALLATO, con l'eseguibile vero: si
lancia con il Python di Windows (nel Windows finto di strumenti/wine, o su un
PC di prova), MAI sul PC della clinica: ferma e chiude il programma e rovina
apposta un indice del suo database.

    python strumenti/prova_autoriparazione_installato.py "C:\\...\\Gestionale.exe" "C:\\...\\GestionaleAgende"

1. il programma risponde; un secondo avvio non ne apre un altro;
2. il programma si blocca (fermato con NtSuspendProcess, come un programma che
   non risponde piu'): l'avvio dopo lo chiude e ne apre uno nuovo, e il diario
   lo dice;
3. a programma chiuso si rovina un indice del database: all'avvio dopo il
   programma lo ripara senza perdere niente.

Alla fine il programma resta aperto, come prima."""
import ctypes
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request

ESEGUIBILE, DATI = sys.argv[1], sys.argv[2]
PORTA = int(os.environ.get('PORTA', '5000'))
esiti = []


def controlla(nome, ok, dettaglio=''):
    esiti.append((bool(ok), nome, dettaglio))
    print(('OK ' if ok else 'KO ') + nome + ('' if ok else '  ' + str(dettaglio)[:300]), flush=True)


def salute(attesa=3):
    try:
        with urllib.request.urlopen('http://127.0.0.1:%d/salute' % PORTA, timeout=attesa) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception:
        return None


def aspetta(condizione, secondi):
    fine = time.monotonic() + secondi
    while time.monotonic() < fine:
        d = salute()
        if condizione(d):
            return d
        time.sleep(1)
    return None


def avvia():
    return subprocess.Popen([ESEGUIBILE, '--avvio-automatico'], close_fds=True)


def eventi():
    try:
        with open(os.path.join(DATI, 'autoriparazione.json'), encoding='utf-8') as f:
            return [e.get('testo', '') for e in json.load(f).get('eventi', [])]
    except (OSError, ValueError):
        return []


def sospendi(pid):
    k32, ntdll = ctypes.windll.kernel32, ctypes.windll.ntdll
    h = k32.OpenProcess(0x0800, False, pid)            # PROCESS_SUSPEND_RESUME
    if not h:
        return False
    try:
        return ntdll.NtSuspendProcess(h) == 0
    finally:
        k32.CloseHandle(h)


def vivo(pid):
    r = subprocess.run(['tasklist', '/FI', 'PID eq %d' % pid, '/FO', 'CSV', '/NH'], capture_output=True, text=True,
                       errors='replace')
    return (r.stdout or '').strip().startswith('"')


def chiudi_tutti():
    """Chiude il programma per davvero: il processo di /salute (con /T anche il
    suo figlio) e poi per nome, e aspetta che il processo non ci sia piu'."""
    d = salute(5)
    if d:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(d['pid'])], capture_output=True)
    subprocess.run(['taskkill', '/F', '/T', '/IM', os.path.basename(ESEGUIBILE)], capture_output=True)
    fine = time.monotonic() + 60
    while time.monotonic() < fine and (salute(2) or (d and vivo(d['pid']))):
        time.sleep(1)
    return not salute(2)


# 1. aperto, e un secondo avvio non fa niente
d = salute() or (avvia() and aspetta(bool, 120))
controlla('il programma risponde', d, d)
primo = d['pid'] if d else None
p = avvia()
try:
    p.wait(120)
except subprocess.TimeoutExpired:
    pass
d = salute()
controlla('secondo avvio: resta il programma di prima', d and d['pid'] == primo and p.poll() is not None, (d, p.poll()))

# 2. il programma si blocca: l'avvio dopo lo sostituisce
controlla('programma fermato (non risponde piu\')', primo and sospendi(primo) and salute(3) is None, primo)
prima = len(eventi())
t0 = time.monotonic()
avvia()
d = aspetta(lambda x: x and x['pid'] != primo, 180)
controlla('bloccato: chiuso e riaperto da solo in %.0f secondi' % (time.monotonic() - t0), d, d)
controlla('il diario dice che non rispondeva', any('non rispondeva' in t for t in eventi()[prima:]), eventi()[-3:])

# 3. indice rovinato a programma chiuso: riparato all'avvio, niente perso
controlla('programma chiuso', chiudi_tutti())
db = os.path.join(DATI, 'agende.db')
c = sqlite3.connect(db)
pagina = c.execute("SELECT rootpage FROM sqlite_master WHERE name = 'ix_appuntamenti_inizio'").fetchone()[0]
misura = c.execute('PRAGMA page_size').fetchone()[0]
conti = {t: c.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0]
         for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")}
c.close()
with open(db, 'r+b') as f:
    f.seek((pagina - 1) * misura)
    f.write(b'\xA5' * misura)
prima = len(eventi())
avvia()
d = aspetta(bool, 180)
controlla('database rovinato: il programma riparte', d, d)
nuovi = eventi()[prima:]
controlla('riparato senza perdere niente', any('senza perdere niente' in t for t in nuovi), nuovi)
c = sqlite3.connect(db)
esito = c.execute('PRAGMA integrity_check').fetchone()[0]
dopo = {t: c.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0] for t in conti}
c.close()
controlla('database integro, tutte le righe di tutte le tabelle', esito == 'ok' and dopo == conti, (esito, conti, dopo))
copie = os.listdir(os.path.join(DATI, 'backup', 'danneggiati'))
controlla('il file rovinato messo da parte', any(x.startswith('danneggiato-') for x in copie), copie)

print('%d controlli, %d a posto' % (len(esiti), sum(1 for e in esiti if e[0])))
sys.exit(0 if all(e[0] for e in esiti) else 1)
