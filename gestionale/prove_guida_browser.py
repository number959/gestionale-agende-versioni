"""Prove nel browser della guida sullo schermo e del menu, su un
gestionale gia' avviato con i dati di prova:
    python prove_guida_browser.py http://127.0.0.1:5001
Non usarla sul database vero (non modifica niente, ma e' pensata per i dati di prova).
Il menu, le tendine e le domande del browser si cercano per ruolo e nome, come un lettore di schermo, con gli
aiuti di aiuti_browser.py (tappa 1 della base): una veste nuova puo' cambiare classi e posti senza rompere la
prova, un nome che sparisce la fa cadere."""
import os, re, sys, datetime as dt
from playwright.sync_api import Error as ErrorePlaywright, sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guida
from aiuti_browser import apri_comandi, gruppo, menu, nome_voce, prepara_domande, principale, tendina_aperta
from aiuti_browser import indirizzo_di_prova  # noqa: E402
B = indirizzo_di_prova(sys.argv)   # mai la porta 5000, quella del programma vero
esiti = []
def ok(n, c, d=''):
    esiti.append(bool(c)); print(('OK ' if c else 'KO ') + n, '' if c else d)
oggi = dt.date.today()
with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
    ctx = br.new_context(viewport={'width': 1366, 'height': 820})
    pg = ctx.new_page(); err = []
    domande = prepara_domande(pg)       # ogni domanda del browser passa da qui: nessuna e' attesa
    pg.on('pageerror', lambda e: err.append(str(e))); pg.on('console', lambda m: err.append(m.text) if m.type == 'error' else None)
    # primo avvio: l'invito al giro su Oggi
    pg.goto(B + '/oggi'); pg.wait_for_timeout(700)
    ok('primo avvio: invito al giro', pg.locator('.giro-invito').count() == 1)
    # dalla tappa 2 il menu sta a sinistra (prova d'aspetto: prima «menu su una riga a 1366 pixel»): largo 248, fermo
    # in cima, e la pagina non scorre di lato
    alt = menu(pg).evaluate('n => { const r = n.getBoundingClientRect(); return [r.left, r.right, r.top, '
                            'document.documentElement.scrollWidth, innerWidth]; }')
    ok('menu a sinistra a 1366 pixel', alt[0] >= 0 and alt[1] <= 248 and alt[2] < 140 and alt[3] <= alt[4], alt)
    pg.click('.giro-invito button.primario'); pg.wait_for_timeout(600)
    ok('il giro parte', pg.locator('.giro-fumetto').count() == 1)
    # gemello di «Esc chiude» (piu' sotto): durante il giro body.giro-in-corso c'è
    ok('durante il giro la pagina lo sa (body.giro-in-corso)', pg.evaluate("document.body.classList.contains('giro-in-corso')"))
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
    # tendine, per ruolo e nome: aperta vuol dire che si vede e che il pulsante lo dice (aria-expanded, quello che
    # sente chi usa un lettore di schermo); col mouse sopra la tendina si vede anche se il clic non fa niente
    # dalla tappa 2 nel menu resta una tendina sola, Aiuto (Segreteria e Configura sono voci con le loro linguette)
    aiuto = gruppo(pg, 'Aiuto')
    aiuto.click(); pg.wait_for_timeout(150)
    aperte = tendina_aperta(pg)
    ok('Aiuto si apre al clic', aperte.count() == 1 and aperte.get_by_role('link', name=nome_voce('Come fare…')).is_visible()
       and aiuto.get_attribute('aria-expanded') == 'true',
       {'tendine aperte': aperte.count(), 'aria-expanded': aiuto.get_attribute('aria-expanded')})
    pg.keyboard.press('Escape'); pg.mouse.move(700, 700); pg.wait_for_timeout(150)
    ok('Esc chiude la tendina', aperte.count() == 0 and aiuto.get_attribute('aria-expanded') == 'false',
       {'tendine aperte': aperte.count(), 'aria-expanded': aiuto.get_attribute('aria-expanded')})
    # chiusa con Esc resta chiusa finché mouse e fuoco non escono dal gruppo (gestionale.js): il fuoco esce, poi il mouse
    # torna sopra (prima si provava su un altro gruppo, Configura, che dalla tappa 2 è una voce)
    pg.evaluate('document.activeElement && document.activeElement.blur()'); pg.wait_for_timeout(100)
    aiuto.hover(); pg.wait_for_timeout(150)
    ok('Aiuto si apre passandoci sopra', aperte.get_by_role('link', name=nome_voce('Novità')).is_visible(),
       {'tendine aperte': aperte.count()})
    pg.mouse.move(700, 700); pg.wait_for_timeout(150)
    stampa = None
    try:
        stampa = apri_comandi(pg, 'Stampa e scarica'); pg.wait_for_timeout(150)
        pulsante = principale(pg).get_by_role('button', name=nome_voce('Stampa e scarica'))
        ok('Stampa e scarica si apre', stampa.is_visible() and pulsante.get_attribute('aria-expanded') == 'true',
           {'aria-expanded': pulsante.get_attribute('aria-expanded')})
    except (AssertionError, ErrorePlaywright) as e:
        ok('Stampa e scarica si apre', False, str(e)[:200])
    pg.mouse.click(700, 760); pg.wait_for_timeout(150)
    ok('clic fuori: si chiude', stampa is None or stampa.count() == 0)
    pg.keyboard.press('c'); pg.wait_for_timeout(800)
    ok('tasto C: le conferme, dalla voce Segreteria del menu', '/conferme' in pg.url, pg.url)
    # ogni guida sullo schermo, dall'articolo fino alla fine
    for a in guida.ARTICOLI:
        if not any('sel' in x for x in a['passi']):
            continue
        # il mouse lontano dal menu: nell'animata la pagina entra muovendosi, e Playwright
        # puo' rifare il clic portando il pulsante in cima alla finestra; il mouse resterebbe
        # li', sopra un gruppo del menu (fino alla tappa 2 Segreteria), che si apre e copre la pagina dopo
        pg.mouse.move(700, 700)
        pg.goto(B + '/aiuto/' + a['slug']); pg.wait_for_timeout(200)
        link = pg.locator('[data-guida-mostra]')
        if not link.count():
            ok('%s: pulsante Mostrami' % a['slug'], False); continue
        if a['endpoint'] != a['apri'][0]:
            continue    # la pagina giusta va aperta a mano (per esempio un appuntamento esistente)
        link.click()
        # il primo passo arriva dopo che la pagina e' caricata: su un PC lento (il Windows di GitHub,
        # con le animazioni dell'animata) puo' volerci piu' di un secondo
        try:
            pg.wait_for_selector('.giro-fumetto', timeout=8000)
        except Exception:
            pass
        pg.wait_for_timeout(300)
        passi = 0
        while pg.locator('.giro-fumetto').count() and passi < 30:
            passi += 1
            pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(120)
        ok('%s: giro completo (%d passi)' % (a['slug'], passi), passi >= 1 and pg.locator('.giro-fumetto').count() == 0)
    ok('nessun errore JavaScript', not err, err[:3])
    ok('nessuna domanda del browser inattesa', not domande.inattese, domande.inattese)
    br.close()
print('%d / %d' % (sum(esiti), len(esiti)))
sys.exit(0 if all(esiti) else 1)
