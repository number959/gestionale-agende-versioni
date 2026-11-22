# La carta delle pagine che si stampano: oggi (5191) contro bozza (5192), PDF come Ctrl+P, pixel per pixel
import os, sys
sys.path.insert(0, '/home/user/gestionale-agende-versioni/gestionale/strumenti')
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', '/opt/pw-browsers')
from fogli_pdf import confronta_foglio
from playwright.sync_api import sync_playwright
QUI = os.path.dirname(os.path.abspath(__file__))
with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pagine = {'principale': br.new_page(), 'qui': br.new_page()}
    basi = {'principale': 'http://127.0.0.1:5191', 'qui': 'http://127.0.0.1:5192'}
    for percorso in sys.argv[1:]:
        cartella = os.path.join(QUI, 'stampa', percorso.strip('/').replace('/', '_').replace('?', '_'))
        righe = confronta_foglio(pagine, basi, percorso, cartella)
        print(percorso, 'UGUALE in stampa' if not righe else '\n  ' + '\n  '.join(righe))
    br.close()
