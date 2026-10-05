# -*- coding: utf-8 -*-
"""Il PDF della guida «Come fare» (tutti gli articoli, con le immagini), dalla
pagina /aiuto/stampa di un gestionale di prova avviato con i dati finti:

    python strumenti/demo.py --porta 5001        (in un'altra finestra)
    python strumenti/genera_pdf_guida.py http://127.0.0.1:5001 [file.pdf]

Senza nome del file: «Guida Gestionale Agende <versione>.pdf» nella cartella
in cui si lancia. Serve Playwright con Chromium. Le immagini della guida sono
quelle di static/guida (strumenti/genera_immagini_guida.py): rigenerarle
prima, se le pagine sono cambiate."""
import os
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comune  # noqa: E402

B = (sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5001').rstrip('/')
USCITA = sys.argv[2] if len(sys.argv) > 2 else 'Guida Gestionale Agende %s.pdf' % comune.VERSIONE

with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
    ctx = br.new_context(viewport={'width': 1366, 'height': 820}, locale='it-IT')
    ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); "
                        "localStorage.setItem('gestionale-tema','chiaro'); } catch (e) {}")
    pg = ctx.new_page()
    errori = []
    pg.on('pageerror', lambda e: errori.append(str(e)))
    pg.goto(B + '/aiuto/stampa', wait_until='load')
    pg.wait_for_function('Array.from(document.images).every(i => i.complete)', timeout=30000)
    rotte = pg.evaluate('Array.from(document.images).filter(i => !i.naturalWidth).map(i => i.src)')
    titolo = pg.text_content('h1') or ''
    pg.pdf(path=USCITA, format='A4', prefer_css_page_size=True, print_background=True,
           margin={'top': '12mm', 'bottom': '12mm', 'left': '12mm', 'right': '12mm'})
    br.close()

pagine = open(USCITA, 'rb').read().count(b'/Type /Page') - open(USCITA, 'rb').read().count(b'/Type /Pages')
print('%s: %.1f MB, circa %d pagine (%s)' % (USCITA, os.path.getsize(USCITA) / 1048576, pagine, ' '.join(titolo.split())))
if errori or rotte:
    print('Da guardare: errori JavaScript %s, immagini mancanti %s' % (errori, rotte))
    sys.exit(1)
