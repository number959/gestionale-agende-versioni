# -*- coding: utf-8 -*-
"""«Aggiorna adesso» per intero sul programma INSTALLATO (per esempio nel
Windows finto di strumenti/wine): indirizzo degli aggiornamenti (una
cartella), controllo e scaricamento, notifica, clic nel browser, Setup
silenzioso che chiude, aggiorna e riapre il programma, pagina d'attesa che va
alle novita', esito nel registro, copia di sicurezza, dati intatti, Setup
installato tolto al primo giro del controllo (due minuti dopo l'avvio).

Serve una versione piu' nuova di quella installata, pubblicata in una cartella
che il programma vede (Setup + file delle versioni, come li scrive
CREA_SETUP.bat): per una prova, la stessa versione con un altro numero
(comune.py, installer.iss e una voce in novita.py), costruita con
strumenti/wine/costruisci.sh.

    python strumenti/prova_aggiorna_adesso.py <cartella vista da Windows> <versione nuova> <cartella dei dati> [display] [cartella per le foto]

Esempio nel Windows finto: C:\\aggiornamenti-prova  1.7.1
$WINEPREFIX/drive_c/users/$USER/AppData/Local/GestionaleAgende  :93  /tmp/foto
Cambia l'indirizzo degli aggiornamenti del programma installato: mai sul PC
della clinica."""
import json, os, re, sqlite3, subprocess, sys, time, urllib.parse, urllib.request
from playwright.sync_api import sync_playwright

B = 'http://127.0.0.1:5000'
CARTELLA, DOPO, DATI = sys.argv[1:4]
DISPLAY = sys.argv[4] if len(sys.argv) > 4 else os.environ.get('DISPLAY', ':93')
FOTO = sys.argv[5] if len(sys.argv) > 5 else os.path.join(os.environ.get('TMPDIR', '/tmp'), 'foto-aggiorna-adesso')
os.makedirs(FOTO, exist_ok=True)
esiti = []


def controlla(nome, ok, dettaglio=''):
    esiti.append((bool(ok), nome, dettaglio))
    print(('OK ' if ok else 'KO ') + nome + ('' if ok else '  ' + str(dettaglio)[:400]), flush=True)


def stato():
    with urllib.request.urlopen(B + '/aggiornamenti/stato.json', timeout=30) as r:
        return json.loads(r.read())


def conta():
    c = sqlite3.connect(os.path.join(DATI, 'agende.db'), timeout=10)
    try:
        return {t: c.execute('select count(*) from %s' % t).fetchone()[0] for t in ('appuntamenti', 'pazienti', 'operatori')}
    finally:
        c.close()


def schermo(nome):
    subprocess.run(['import', '-window', 'root', '-display', DISPLAY, os.path.join(FOTO, nome)], capture_output=True)


prima = stato()
righe_prima = conta()
print('prima:', prima, righe_prima, flush=True)
dati = urllib.parse.urlencode({'azione': 'indirizzo', 'indirizzo': CARTELLA}).encode()
class SenzaRimandi(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None
try:
    r = urllib.request.build_opener(SenzaRimandi).open(urllib.request.Request(B + '/aggiornamenti', data=dati), timeout=30)
    codice = r.status
except urllib.error.HTTPError as e:
    codice = e.code
controlla('indirizzo salvato (cartella %s)' % CARTELLA, codice == 302, codice)
inizio = time.time()
while time.time() - inizio < 300:
    s = stato()
    if not s['in_corso'] and (s['pronto'] or s['errore']):
        break
    time.sleep(2)
controlla('controllo e scaricamento: pronta la %s (%.0f s)' % (DOPO, time.time() - inizio),
          s['pronto'] and s['disponibile'] == DOPO and not s['errore'], s)
with urllib.request.urlopen(B + '/notifiche.json', timeout=30) as r:
    notifiche = json.loads(r.read())
controlla('notifica «Aggiornamento disponibile»', any(n['titolo'] == 'Aggiornamento disponibile' for n in notifiche),
          [n['titolo'] for n in notifiche])

with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_page(viewport={'width': 1366, 'height': 860})
    pg.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); localStorage.setItem('guida-viste', '{\"*\":1}'); } catch (e) {}")
    pg.goto(B + '/aggiornamenti')
    controlla('pagina: «È pronta la versione %s»' % DOPO, pg.locator('h2.pronta').count() == 1 and DOPO in pg.text_content('h2.pronta'))
    pg.screenshot(path=os.path.join(FOTO, '1-pronta.png'))
    pg.click('form[data-guida="aggiorna-adesso"] button')
    pg.wait_for_selector('#attesa-aggiornamento', timeout=30000)
    pg.screenshot(path=os.path.join(FOTO, '2-attesa.png'))
    controlla('pagina d\'attesa', 'Aggiornamento alla versione %s' % DOPO in pg.text_content('h1'))
    fine = time.time() + 360
    n = 0
    arrivata = False
    while time.time() < fine:
        if re.search(r'/aiuto/novita$', pg.url):
            arrivata = True
            break
        if n < 40 and int(time.time()) % 3 == 0:
            n += 1
            schermo('setup-%02d.png' % n)
        pg.wait_for_timeout(1000)
    durata = time.time() - (fine - 360)
    controlla('dopo il riavvio la pagina va da sola alle novità (%.0f s)' % durata, arrivata, pg.url)
    pg.wait_for_timeout(800)
    pg.screenshot(path=os.path.join(FOTO, '3-novita.png'), full_page=True)
    controlla('novità della versione %s' % DOPO, 'Novità della versione %s' % DOPO in (pg.text_content('h1') or ''))
    br.close()

dopo = stato()
controlla('programma riaperto alla %s (avviato cambiato)' % DOPO, dopo['versione'] == DOPO and dopo['avviato'] != prima['avviato'], dopo)
registro = open(os.path.join(DATI, 'gestionale.log'), encoding='utf-8', errors='replace').read()
controlla('registro: «aggiornamento dalla %s alla %s riuscito»' % (prima['versione'], DOPO),
          'aggiornamento dalla %s alla %s riuscito' % (prima['versione'], DOPO) in registro, registro[-1500:])
controlla('registro: copia di sicurezza e Setup avviato', re.search(r'aggiornamento alla versione %s: copia di sicurezza .*prima-di-aggiornare\.db, parte il Setup'
                                                                    % re.escape(DOPO), registro), registro[-1500:])
copie = [f for f in os.listdir(os.path.join(DATI, 'backup')) if f.endswith('-prima-di-aggiornare.db')]
controlla('copia «prima di aggiornare» fra i backup', copie, os.listdir(os.path.join(DATI, 'backup')))
cartella = os.listdir(os.path.join(DATI, 'aggiornamenti'))
controlla('segno tolto, registro del Setup tenuto', 'in-corso.json' not in cartella and 'setup-%s.log' % DOPO in cartella, cartella)
inizio = time.time()
while time.time() - inizio < 240 and [f for f in os.listdir(os.path.join(DATI, 'aggiornamenti')) if f.endswith('.exe')]:
    time.sleep(5)
cartella = os.listdir(os.path.join(DATI, 'aggiornamenti'))
controlla('Setup installato tolto dal primo giro del controllo (%.0f s dopo)' % (time.time() - inizio),
          not [f for f in cartella if f.endswith('.exe')], cartella)
righe_dopo = conta()
controlla('dati intatti %s' % righe_dopo, righe_dopo == righe_prima, (righe_prima, righe_dopo))
print('%d controlli, %d a posto' % (len(esiti), sum(1 for e in esiti if e[0])))
sys.exit(0 if all(e[0] for e in esiti) else 1)
