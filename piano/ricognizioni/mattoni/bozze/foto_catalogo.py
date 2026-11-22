"""Foto del catalogo: 1366x657, 1024 e 683 px, in chiaro e in scuro, pagina intera; più la tendina aperta."""
import os, sys
from playwright.sync_api import sync_playwright
URL, FOTO = sys.argv[1], sys.argv[2]
os.makedirs(FOTO, exist_ok=True)
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
    for larga in (1366, 1024, 683):
        for tema in ('chiaro', 'scuro'):
            ctx = b.new_context(viewport={'width': larga, 'height': 657})
            ctx.add_init_script("try { localStorage.setItem('gestionale-tema', '%s'); } catch (e) {}" % tema)
            p = ctx.new_page(); err = []
            p.on('pageerror', lambda e: err.append(str(e)))
            p.on('console', lambda m: err.append(m.text) if m.type == 'error' else None)
            p.goto(URL, wait_until='load'); p.wait_for_timeout(800)
            p.add_style_tag(content='#notifiche, .notifiche { visibility: hidden !important; }')
            p.screenshot(path=os.path.join(FOTO, 'catalogo-%d-%s.png' % (larga, tema)), full_page=True)
            largo = p.evaluate('document.documentElement.scrollWidth')
            if larga == 1366:
                p.locator('.v-stampa .apri-gruppo').click(); p.wait_for_timeout(200)
                p.locator('.v-barra-comandi').screenshot(path=os.path.join(FOTO, 'barra-tendina-%s.png' % tema))
                box = p.locator('.v-stampa .tendina').bounding_box()
                p.screenshot(path=os.path.join(FOTO, 'tendina-aperta-%s.png' % tema),
                             clip={'x': 0, 'y': max(0, box['y'] - 120), 'width': 1366, 'height': box['height'] + 160})
                p.keyboard.press('Escape')
                # fuoco della tastiera su un bottone e su un campo
                p.locator('#cat-cognome').focus(); p.wait_for_timeout(100)
                p.locator('#cat-cognome').screenshot(path=os.path.join(FOTO, 'campo-fuoco-%s.png' % tema))
            stili = p.evaluate("""() => { const q = s => getComputedStyle(document.querySelector(s));
                return { campo: [q('#cat-cognome').backgroundColor, q('#cat-cognome').color, q('#cat-cognome').borderTopColor],
                         bottone: [q('.v-barra-comandi .v-principale').backgroundColor, q('.v-barra-comandi .v-principale').color],
                         normale: [q('.cat-fila .v-bottone').backgroundColor, q('.cat-fila .v-bottone').color],
                         link: q('.v-tabella td a').color, linguetta: [q('.v-linguetta[aria-current]').backgroundColor, q('.v-linguetta[aria-current]').color] }; }""")
            print(larga, tema, 'largo', largo, 'errori', err, stili, flush=True)
            ctx.close()
    b.close()
