"""Prove nel browser della 1.9 (Dove si fa), su un gestionale gia' avviato con
i dati di prova (strumenti/demo.py, che importa il database delle prestazioni
inventato di strumenti/catalogo_prova.py):
    python prove_19_browser.py http://127.0.0.1:5001
- il tasto D, la pagina senza ricerca (branche, strutture, ultimi indirizzati);
- la ricerca mentre si scrive, senza ricaricare la pagina, con l'indirizzo che
  la segue; branche, correzioni, frecce dal campo ai risultati;
- la scheda della struttura: si apre dal risultato, dentro la finestra (sotto la
  barra in alto; scorrendo la pagina sale in cima), la pagina le lascia posto, Esc la chiude e si torna al risultato; il messaggio cambiato
  va anche nei collegamenti di WhatsApp ed email; Copia; Segna come indirizzato
  con Annulla; WhatsApp e Stampa si segnano da sole, una volta sola;
- il paziente scelto dalla pagina; la ricerca rapida della barra in alto;
- schermo stretto, tema scuro, nessun errore JavaScript.
La cornice (il menu, la ricerca rapida, le domande del browser) si cerca per
ruolo e nome con gli aiuti di aiuti_browser.py, come un lettore di schermo
(tappa 1 della base); una domanda del browser che nessuno aspettava fa cadere
la prova.
Segna e toglie pazienti indirizzati: usarla su un gestionale di prova, mai su
quello vero."""
import os
import re
import sys
from urllib.parse import unquote

from playwright.sync_api import Error as ErrorePlaywright, sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aiuti_browser import barra_in_alto, menu, prepara_domande, zona_ricerca  # noqa: E402

from aiuti_browser import indirizzo_di_prova  # noqa: E402
B = indirizzo_di_prova(sys.argv)   # mai la porta 5000, quella del programma vero
esiti = []


def ok(n, c, d=''):
    esiti.append(bool(c))
    print(('OK ' if c else 'KO ') + n, '' if c else d)


def dentro_la_finestra(scheda, barra, finestra):
    """La scheda di Dove si fa è dove deve stare (tappa 2): comincia subito sotto la barra in alto, o in cima alla
    finestra se la barra è già scorsa via; finisce dentro la finestra; arriva al bordo destro."""
    if not scheda:
        return False
    sotto = max(0, barra['y'] + barra['height']) if barra else 0
    return (abs(scheda['y'] - sotto) <= 1 and scheda['height'] > 100 and
            scheda['y'] + scheda['height'] <= finestra['height'] + 1 and
            abs(scheda['x'] + scheda['width'] - finestra['width']) <= 1)


with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
    ctx = br.new_context(viewport={'width': 1366, 'height': 768}, locale='it-IT')
    ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); localStorage.setItem('guida-viste', '{\"*\":1}'); "
                        "localStorage.setItem('gestionale-tema', 'chiaro'); } catch (e) {}")
    ctx.grant_permissions(['clipboard-read', 'clipboard-write'], origin=B)
    # WhatsApp non si apre davvero: una pagina finta al posto di wa.me
    ctx.route(re.compile(r'^https://wa\.me/'), lambda r: r.fulfill(status=200, content_type='text/plain', body='finto'))
    pg = ctx.new_page()
    domande = prepara_domande(pg)            # subito: ogni domanda del browser passa da qui (nessuna e' attesa)
    err = []
    pg.on('pageerror', lambda e: err.append(str(e)))
    pg.on('console', lambda m: err.append(m.text) if m.type == 'error' else None)

    def avviso():
        loc = pg.locator('#avvisi-dove .avviso-turni')
        return loc.last.inner_text().replace('\n', ' ') if loc.count() else ''

    def chiudi_avvisi():
        pg.evaluate("document.querySelectorAll('#avvisi-dove .avviso-turni').forEach(function (a) { a.remove(); })")

    def risultati():
        return [x.strip() for x in pg.locator('#risultati-dove .voce-dove h2').all_inner_texts()]

    def scrivi(testo_):
        pg.fill('#q-dove', testo_)
        pg.wait_for_function("() => document.getElementById('risultati-dove').getAttribute('aria-busy') === 'false'")
        pg.wait_for_timeout(450)

    def n_registro():
        return pg.evaluate("""() => fetch('/dove-si-fa/registro').then(r => r.text()).then(t => {
            const m = t.match(/<b>(\\d+)<\\/b> in tutto/); return m ? +m[1] : 0; })""")

    # ------------------------------------------------ il tasto D e la pagina senza ricerca
    pg.goto(B + '/oggi')
    pg.keyboard.press('d')
    pg.wait_for_url(re.compile(r'/dove-si-fa/'))
    ok('il tasto D apre Dove si fa', '/dove-si-fa/' in pg.url)
    ok('il campo di ricerca e\' pronto per scrivere', pg.evaluate("document.activeElement.id") == 'q-dove')
    ok('senza ricerca: branche, strutture e ultimi indirizzati',
       pg.locator('.branche-dove a').count() >= 15 and pg.locator('a.sede-grande').count() == 6 and
       pg.locator('.recenti-dove li').count() >= 3)
    # dalla tappa 2 il menu sta a sinistra: largo al massimo 248 px e la pagina non scorre di lato per lui
    m = menu(pg).bounding_box()
    ok('il menu sta a sinistra e la pagina non scorre di lato', m['x'] < 248 and m['x'] + m['width'] <= 248 and
       pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), m)

    # ------------------------------------------------ la ricerca mentre si scrive
    pg.evaluate('window.__stessa = 1')
    scrivi('risonanza ginocchio')
    ok('risultati mentre si scrive', risultati() == ['RM ginocchio', 'RM ginocchio con mezzo di contrasto'], risultati())
    ok('senza ricaricare la pagina', pg.evaluate('window.__stessa') == 1)
    ok('l\'indirizzo segue la ricerca', 'q=risonanza%20ginocchio' in pg.url, pg.url)
    scrivi('ecocardiogrma')
    ok('parola scritta male: corretta, con il risultato', 'ecco quelle con «ecocardiogramma»' in
       pg.locator('.corretta-dove').inner_text() and risultati() == ['Ecocardiogramma'])
    scrivi('visita cardiologica')
    ok('«si fa anche qui» con il collegamento per prenotare',
       pg.locator('.nostri-dove a[href*="/appuntamento?prestazione="]').count() == 1)
    pg.fill('#q-dove', '')
    pg.wait_for_timeout(500)
    pg.locator('.branche-dove a', has_text='Cardiologia').click()
    pg.wait_for_timeout(600)
    ok('una branca dall\'elenco: scelta e risultati', pg.input_value('#branca-dove') == 'CARDIOLOGIA' and
       len(risultati()) == 5 and 'branca=CARDIOLOGIA' in pg.url, (pg.input_value('#branca-dove'), risultati()))
    pg.select_option('#branca-dove', '')
    pg.wait_for_timeout(500)
    scrivi('holter')
    pg.focus('#q-dove')
    pg.keyboard.press('ArrowDown')
    primo = pg.evaluate("document.activeElement.classList.contains('sede') && document.activeElement.textContent.trim()")
    pg.keyboard.press('ArrowRight')
    secondo = pg.evaluate("document.activeElement.classList.contains('sede') && document.activeElement.textContent.trim()")
    pg.keyboard.press('ArrowLeft')
    pg.keyboard.press('ArrowUp')
    ok('frecce: dal campo alle strutture, fra le strutture e di nuovo nel campo',
       primo and secondo and primo != secondo and pg.evaluate("document.activeElement.id") == 'q-dove', (primo, secondo))

    # Invio nel campo: alla prima struttura (anche se la ricerca e' ancora in viaggio)
    pg.fill('#q-dove', 'mammografia')
    pg.keyboard.press('Enter')
    pg.wait_for_timeout(700)
    ok('Invio nel campo porta alla prima struttura', pg.evaluate(
        "document.activeElement.classList.contains('sede') && document.activeElement.dataset.voce") and
       risultati() == ['Mammografia'], risultati())
    # una struttura senza prestazione: cosa si fa li', e un clic su una branca la cerca
    pg.fill('#q-dove', '')
    pg.wait_for_timeout(500)
    pg.locator('a.sede-grande', has_text='Centro Nord').click()
    pg.wait_for_selector('#scheda-dove:not([hidden]) .branche-scheda')
    pg.wait_for_function("() => document.getAnimations().every(a => a.playState !== 'running')")
    ok('la scheda è dentro la finestra appena aperta (sotto la barra in alto)',
       dentro_la_finestra(pg.locator('#scheda-dove').bounding_box(), barra_in_alto(pg).bounding_box(), pg.viewport_size),
       (pg.locator('#scheda-dove').bounding_box(), barra_in_alto(pg).bounding_box()))
    n_branche = pg.locator('.branche-scheda li').count()
    pg.locator('.branche-scheda a', has_text='Cardiologia').click()
    pg.wait_for_timeout(600)
    ok('scheda senza prestazione: cosa si fa li\', e una branca si apre con un clic, solo per quella struttura',
       n_branche >= 5 and pg.input_value('#branca-dove') == 'CARDIOLOGIA' and pg.locator('#scheda-dove').is_hidden() and
       len(risultati()) == 5 and 'Solo le prestazioni di Centro Nord' in ' '.join(pg.locator('.filtro-sede').inner_text().split()) and
       'sede=' in pg.url, (n_branche, pg.input_value('#branca-dove'), risultati(), pg.url))
    pg.select_option('#branca-dove', '')
    pg.wait_for_timeout(600)
    tutte_cn = len(risultati())
    pg.locator('.filtro-sede a', has_text='tutte le strutture').click()
    pg.wait_for_timeout(600)
    ok('il filtro della struttura si toglie', tutte_cn == 29 and pg.locator('.filtro-sede').count() == 0 and
       'sede=' not in pg.url and pg.locator('.branche-dove').count() == 1, (tutte_cn, pg.url))

    # ------------------------------------------------ la scheda della struttura
    scrivi('rm ginocchio')
    chip = pg.locator('#risultati-dove a.sede', has_text='Centro Nord').first
    chip.focus()
    pg.keyboard.press('Enter')
    pg.wait_for_selector('#scheda-dove:not([hidden]) .dentro-scheda')
    pg.wait_for_function("() => document.getAnimations().every(a => a.playState !== 'running')")
    pg.wait_for_timeout(200)
    sc = pg.locator('#scheda-dove')
    ok('Invio sulla struttura apre la sua scheda', 'Centro Nord' in sc.locator('h2').inner_text() and
       'RM ginocchio' in sc.inner_text())
    ok('la struttura scelta si vede fra i risultati', 'scelta' in (chip.get_attribute('class') or ''))
    ok('l\'indirizzo ricorda la scheda aperta', 'gruppo=' in pg.url and 'voce=' in pg.url, pg.url)
    r = sc.bounding_box()
    finestra = pg.viewport_size
    ok('la scheda è dentro la finestra: sotto la barra in alto, fino al bordo destro',
       dentro_la_finestra(r, barra_in_alto(pg).bounding_box(), finestra), (r, barra_in_alto(pg).bounding_box()))
    # scorrendo la pagina la barra in alto se ne va e la scheda sale in cima, sempre dentro (la pagina si allunga
    # apposta: con pochi risultati non scorrerebbe)
    pg.evaluate("document.body.style.minHeight = '3000px'; window.scrollTo(0, 400)")
    pg.wait_for_timeout(300)
    ok('scorrendo la pagina la scheda sale in cima e resta dentro la finestra',
       pg.evaluate('window.scrollY') > 0 and dentro_la_finestra(sc.bounding_box(), barra_in_alto(pg).bounding_box(), finestra)
       and sc.bounding_box()['y'] < r['y'], (pg.evaluate('window.scrollY'), sc.bounding_box()))
    pg.evaluate("window.scrollTo(0, 0); document.body.style.minHeight = ''")
    pg.wait_for_timeout(300)
    # il gemello: la scheda messa dove la metteva dove.js fino alla tappa 1 (sotto il menu, che ora è alto quanto la
    # finestra) non passa il controllo; poi dove.js la rimette a posto da solo (scroll)
    sotto_il_menu = menu(pg).bounding_box()
    sc.evaluate('(s, y) => { s.style.top = y + "px"; }', round(sotto_il_menu['y'] + sotto_il_menu['height']))
    ok('gemello: la scheda sotto il menu (dove.js di prima) non è dentro la finestra',
       not dentro_la_finestra(sc.bounding_box(), barra_in_alto(pg).bounding_box(), finestra), sc.bounding_box())
    pg.evaluate("window.dispatchEvent(new Event('scroll'))")
    pg.wait_for_timeout(100)
    ok('…e dove.js la rimette sotto la barra', dentro_la_finestra(sc.bounding_box(), barra_in_alto(pg).bounding_box(), finestra),
       sc.bounding_box())
    pag = pg.locator('#pagina-dove').bounding_box()
    ok('la pagina lascia posto alla scheda (i risultati non finiscono sotto)', pag['x'] + pag['width'] <= r['x'] + 1,
       (pag, r))
    area_ = sc.locator('#messaggio-dove')
    ok('il messaggio per il paziente e\' gia\' scritto', area_.input_value().startswith(
        'Buongiorno,\nla prestazione «RM ginocchio» si può fare presso Centro Nord (Caserta).'), area_.input_value()[:80])
    area_.focus()
    pg.keyboard.press('Control+End')
    pg.keyboard.type('\nPortare la richiesta del medico.')
    wa = sc.locator('[data-azione="whatsapp"]').get_attribute('href')
    em = sc.locator('[data-azione="email"]').get_attribute('href')
    ok('il messaggio cambiato va nei collegamenti di WhatsApp ed email',
       unquote(wa.split('text=', 1)[1]).endswith('Portare la richiesta del medico.') and
       unquote(em.split('body=', 1)[1]).endswith('Portare la richiesta del medico.'), (wa[-60:], em[-60:]))
    chiudi_avvisi()
    sc.locator('[data-azione="copia"]').click()
    pg.wait_for_timeout(400)
    appunti = pg.evaluate('navigator.clipboard.readText()')
    # su Windows gli appunti rendono gli a capo come CRLF: il testo e' lo stesso
    appunti = appunti.replace('\r\n', '\n')
    ok('Copia: il messaggio negli appunti', appunti == area_.input_value() and 'Messaggio copiato' in avviso(),
       (appunti[-40:], avviso()))
    prima = n_registro()
    chiudi_avvisi()
    sc.locator('[data-azione="segna"]').click()
    pg.wait_for_timeout(600)
    ok('Segna come indirizzato: nel registro, con l\'avviso', n_registro() == prima + 1 and
       avviso().startswith('Segnato: Paziente indirizzato a Centro Nord per «RM ginocchio» (al telefono)'), avviso())
    pg.locator('#avvisi-dove .azione-avviso', has_text='Annulla').click()
    pg.wait_for_timeout(600)
    ok('Annulla: tolto dal registro', n_registro() == prima and 'Tolto dal registro' in avviso(), avviso())
    chiudi_avvisi()
    with pg.expect_popup() as finestra:
        sc.locator('[data-azione="whatsapp"]').click()
    finestra.value.close()
    pg.wait_for_timeout(600)
    ok('WhatsApp si apre e si segna da solo', n_registro() == prima + 1 and '(WhatsApp)' in avviso(), avviso())
    chiudi_avvisi()
    with pg.expect_popup() as finestra:
        sc.locator('[data-azione="stampa"]').click()
    foglio = finestra.value
    foglio.wait_for_load_state()
    ok('Stampa: il foglio per il paziente', 'Dove fare «RM ginocchio»' in foglio.locator('h1').inner_text())
    foglio.close()
    pg.wait_for_timeout(500)
    ok('la stessa scheda si segna una volta sola', n_registro() == prima + 1 and 'Già segnato' in avviso(), avviso())
    chiudi_avvisi()
    pg.keyboard.press('Escape')
    pg.wait_for_timeout(300)
    ok('Esc chiude la scheda e si torna alla struttura', sc.is_hidden() and
       pg.evaluate("document.activeElement.classList.contains('sede')") and 'gruppo=' not in pg.url)
    # la scheda resta sotto il menu anche scorrendo: quando il menu esce, sale fino in cima
    scrivi('eco')
    pg.locator('#risultati-dove a.sede').first.click()
    pg.wait_for_selector('#scheda-dove:not([hidden]) .dentro-scheda')
    pg.mouse.move(300, 500)
    pg.mouse.wheel(0, 600)
    pg.wait_for_timeout(400)
    ok('scorrendo la pagina la scheda sale fino in cima', sc.bounding_box()['y'] <= 1, sc.bounding_box())
    pg.keyboard.press('Escape')

    # ------------------------------------------------ per un paziente
    pg.goto(B + '/dove-si-fa/?q=mammografia')
    pg.fill('#paziente-dove', 'Cuo')
    pg.wait_for_selector('#suggerimenti-paziente-dove button')
    pg.keyboard.press('Enter')
    pg.wait_for_url(re.compile(r'paziente=\d+'))
    ok('paziente scelto dalla pagina', 'Per Cuomo Maria' in pg.locator('.paziente-dove').inner_text() and
       risultati() == ['Mammografia'])
    pg.locator('#risultati-dove a.sede').first.click()
    pg.wait_for_selector('#scheda-dove:not([hidden]) .dentro-scheda')
    ok('il messaggio porta il nome del paziente e WhatsApp va al suo numero',
       pg.locator('#messaggio-dove').input_value().startswith('Gentile Maria Cuomo,') and
       pg.locator('[data-azione="whatsapp"]').get_attribute('href').startswith('https://wa.me/39347'))

    # ------------------------------------------------ la ricerca rapida (dalla tappa 2 nella barra in alto)
    # il tasto / porta nel campo (resta: prova la scorciatoia), poi si scrive come una persona; i risultati sono i
    # collegamenti della zona di ricerca del menu: per «holter» solo prestazioni, la prima e' Holter ECG
    pg.goto(B + '/oggi')
    pg.keyboard.press('/')
    pg.keyboard.type('holter')
    zona = zona_ricerca(pg)
    rapidi = zona.get_by_role('link')
    try:
        rapidi.or_(zona.get_by_text('Nessun risultato.')).first.wait_for(timeout=5000)
    except ErrorePlaywright:
        pass                                 # niente risultati: la prova qui sotto cade e dice cosa c'e'
    voce = rapidi.first.inner_text() if rapidi.count() else ''
    ok('ricerca rapida: le prestazioni e dove si fanno', voce.startswith('Holter ECG') and 'si fa a:' in voce,
       voce or zona.inner_text())
    if voce:
        rapidi.first.click()
        pg.wait_for_url(re.compile(r'/dove-si-fa/\?q=holter'))
        pg.wait_for_timeout(300)
    ok('dalla ricerca rapida: la prestazione in evidenza, pronta da scegliere', bool(voce) and
       pg.locator('.voce-dove.evidenziata h2').inner_text() == 'Holter ECG' and
       pg.evaluate("document.activeElement.classList.contains('sede')"), pg.url)

    # ------------------------------------------------ schermo stretto e tema scuro
    piccolo = br.new_context(viewport={'width': 390, 'height': 844}, locale='it-IT')
    piccolo.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); localStorage.setItem('guida-viste', '{\"*\":1}'); "
                            "localStorage.setItem('gestionale-tema', 'scuro'); } catch (e) {}")
    q = piccolo.new_page()
    domande_q = prepara_domande(q)
    q.on('pageerror', lambda e: err.append(str(e)))
    q.goto(B + '/dove-si-fa/?q=rm+ginocchio')
    ok('schermo stretto: la pagina non scorre di lato',
       q.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"))
    q.locator('#risultati-dove a.sede').first.click()
    q.wait_for_selector('#scheda-dove:not([hidden]) .dentro-scheda')
    # nella versione animata la scheda entra scorrendo da destra: si misura a movimento finito
    q.wait_for_function("() => document.getAnimations().every(a => a.playState !== 'running')")
    r = q.locator('#scheda-dove').bounding_box()
    ok('schermo stretto: la scheda occupa la larghezza dello schermo', abs(r['x']) <= 1 and abs(r['width'] - 390) <= 1, r)
    ok('tema scuro: la scheda e\' scura', q.evaluate(
        "getComputedStyle(document.getElementById('scheda-dove')).backgroundColor") != 'rgb(255, 255, 255)')
    piccolo.close()

    for u in ('/dove-si-fa/', '/dove-si-fa/strutture', '/dove-si-fa/registro', '/dove-si-fa/strutture/1'):
        pg.goto(B + u)
        pg.wait_for_timeout(300)
    ok('nessun errore JavaScript', not err, err[:3])
    ok('nessuna domanda del browser inattesa', not domande.inattese and not domande_q.inattese,
       domande.inattese + domande_q.inattese)
    br.close()
print('\n%d prove nel browser, %d superate' % (len(esiti), sum(esiti)))
sys.exit(0 if all(esiti) else 1)
