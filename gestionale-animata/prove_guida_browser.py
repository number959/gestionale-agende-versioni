"""Prove nel browser della guida sullo schermo e del menu a gruppi, su un
gestionale gia' avviato con i dati di prova:
    python prove_guida_browser.py http://127.0.0.1:5000
Non usarla sul database vero (non modifica niente, ma e' pensata per i dati di prova)."""
import os, re, sys, datetime as dt
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guida
B = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5000'
esiti = []
def ok(n, c, d=''):
    esiti.append(bool(c)); print(('OK ' if c else 'KO ') + n, '' if c else d)
oggi = dt.date.today()
with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
    ctx = br.new_context(viewport={'width': 1366, 'height': 820})
    pg = ctx.new_page(); err = []
    pg.on('pageerror', lambda e: err.append(str(e))); pg.on('console', lambda m: err.append(m.text) if m.type == 'error' else None)
    # primo avvio: l'invito al giro su Oggi
    pg.goto(B + '/oggi'); pg.wait_for_timeout(700)
    ok('primo avvio: invito al giro', pg.locator('.giro-invito').count() == 1)
    alt = pg.evaluate("[document.querySelector('nav.menu').offsetHeight, document.querySelector('nav.menu').scrollWidth, innerWidth]")
    ok('menu su una riga a 1366 pixel', alt[0] < 45 and alt[1] <= alt[2], alt)
    pg.click('.giro-invito button.primario'); pg.wait_for_timeout(600)
    ok('il giro parte', pg.locator('.giro-fumetto').count() == 1)
    n = len([x for x in guida.PER_SLUG['come-e-fatto']['passi']])
    ok('conta i passi', pg.locator('.giro-conto').text_content() == '1 di %d' % n, pg.locator('.giro-conto').text_content())
    pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(300)
    luce = pg.evaluate("(() => { const l = document.querySelector('.giro-riflettore').getBoundingClientRect(); const m = document.querySelector('[data-guida=\"menu-oggi\"]').getBoundingClientRect(); return [l.left <= m.left, l.right >= m.right, l.top <= m.top, l.bottom >= m.bottom]; })()")
    ok('il riflettore contorna il punto indicato', all(luce), luce)
    pg.keyboard.press('ArrowLeft'); pg.wait_for_timeout(200)
    ok('freccia a sinistra: passo indietro', pg.locator('.giro-conto').text_content().startswith('1 di'))
    pg.keyboard.press('Escape'); pg.wait_for_timeout(200)
    ok('Esc chiude', pg.locator('.giro-fumetto').count() == 0 and not pg.evaluate("document.body.classList.contains('giro-in-corso')"))
    pg.reload(); pg.wait_for_timeout(500)
    ok('l\'invito non ricompare', pg.locator('.giro-invito').count() == 0)
    # durante il giro le frecce non cambiano giorno nella griglia
    u = B + '/giorno/%s?struttura=1' % oggi
    pg.goto(u + '&guida=griglia'); pg.wait_for_timeout(1000)
    ok('?guida= avvia il giro e sparisce dall\'indirizzo', pg.locator('.giro-fumetto').count() == 1 and 'guida=' not in pg.url, pg.url)
    pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(500)
    ok('frecce durante il giro: la pagina resta la stessa', pg.url.startswith(B + '/giorno/%s' % oggi), pg.url)
    pg.keyboard.press('Escape')
    # tendine
    pg.click('[data-guida="menu-segreteria"] .apri-gruppo'); pg.wait_for_timeout(150)
    ok('Segreteria si apre al clic', pg.locator('[data-guida="menu-segreteria"] .tendina').is_visible())
    pg.keyboard.press('Escape'); pg.mouse.move(700, 700); pg.wait_for_timeout(150)
    ok('Esc chiude la tendina', not pg.locator('[data-guida="menu-segreteria"] .tendina').is_visible())
    pg.hover('[data-guida="menu-configura"]'); pg.wait_for_timeout(150)
    ok('Configura si apre passandoci sopra', pg.locator('[data-guida="menu-configura"] .tendina').is_visible())
    pg.mouse.move(700, 700); pg.wait_for_timeout(150)
    pg.click('[data-guida="giorno-stampa"] .apri-gruppo'); pg.wait_for_timeout(150)
    ok('Stampa e scarica si apre', pg.locator('[data-guida="giorno-stampa"] .tendina').is_visible())
    pg.mouse.click(700, 760); pg.wait_for_timeout(150)
    ok('clic fuori: si chiude', not pg.locator('[data-guida="giorno-stampa"] .tendina').is_visible())
    pg.keyboard.press('c'); pg.wait_for_timeout(800)
    ok('tasto C: conferme anche dal menu a gruppi', '/conferme' in pg.url, pg.url)
    # ogni guida sullo schermo, dall'articolo fino alla fine
    for a in guida.ARTICOLI:
        if not any('sel' in x for x in a['passi']):
            continue
        pg.goto(B + '/aiuto/' + a['slug']); pg.wait_for_timeout(200)
        link = pg.locator('[data-guida-mostra]')
        if not link.count():
            ok('%s: pulsante Mostrami' % a['slug'], False); continue
        if a['endpoint'] != a['apri'][0]:
            continue    # la pagina giusta va aperta a mano (per esempio un appuntamento esistente)
        link.click(); pg.wait_for_timeout(900)
        passi = 0
        while pg.locator('.giro-fumetto').count() and passi < 30:
            passi += 1
            pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(120)
        ok('%s: giro completo (%d passi)' % (a['slug'], passi), passi >= 1 and pg.locator('.giro-fumetto').count() == 0)
    ok('nessun errore JavaScript', not err, err[:3])
    br.close()
print('%d / %d' % (sum(esiti), len(esiti)))
sys.exit(0 if all(esiti) else 1)
