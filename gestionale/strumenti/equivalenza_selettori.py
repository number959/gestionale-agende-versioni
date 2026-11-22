# -*- coding: utf-8 -*-
"""Prima di togliere un selettore vecchio (classi, tag, id) da una prova nel browser, il selettore nuovo (ruolo e
nome, con gli aiuti di aiuti_browser.py) deve trovare lo stesso elemento, uno solo, sulla stessa pagina (tappa 1
della base, 22/11/2026). Non è una raccolta di prove (non sta in tutte_le_prove.py): è lo strumento del cambio.

    python strumenti/demo.py --porta 5077 --dati <cartella>          # in un'altra finestra, appena avviato
    python strumenti/equivalenza_selettori.py http://127.0.0.1:5077

Per ogni coppia: quanti elementi trova il vecchio, quanti il nuovo, e se sono gli stessi (element_handle e a === b
nella pagina). «uno»: tutti e due uno solo e lo stesso; «lista»: le stesse liste, nello stesso ordine; «nessuno»:
tutti e due zero. In più vai_dal_menu su ogni voce del menu (arriva dove porta il suo href), rispondi con OK e
Annulla, e i nomi messi dalla tappa 1 (aria-current, aria-label delle tendine, zona dei messaggi, notifiche, tasti
rapidi, avvisi dei turni, videoguida). Finisce con «N confronti, N uguali».

Un selettore nuovo si aggiunge qui con il suo vecchio, si fa girare, e solo dopo si cambia la raccolta. Cambia i
dati della prova (un tariffario e una persona creati ed eliminati, un turno messo e annullato): solo su un
gestionale di prova, mai su quello vero."""
import os
import re
import sys
from datetime import date, timedelta

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aiuti_browser import (GRUPPI, apri_comandi, apri_gruppo, cerca_rapido, gruppo, gruppo_attivo,  # noqa: E402
                           menu, messaggi, nella_zona, nome_voce, prepara_domande, rispondi, tendina_aperta,
                           vai_dal_menu, voce_attiva, zona_messaggi)

if len(sys.argv) < 2 or sys.argv[1].rstrip('/').endswith(':5000'):
    sys.exit('uso: python strumenti/equivalenza_selettori.py http://127.0.0.1:<porta di un gestionale DI PROVA>\n'
             '(cambia i dati: mai sul gestionale vero, che sta sulla 5000)')
B = sys.argv[1].rstrip('/')
OGGI = date.today()
LUN = OGGI - timedelta(days=OGGI.weekday()) + timedelta(days=7)
esiti = []


def ok(n, c, d=''):
    esiti.append(bool(c))
    print(('OK ' if c else 'KO ') + n, '' if c else d)


def stesso(pg, nome, vecchio, nuovo, modo='uno', visibili=False):
    """vecchio: selettore CSS (stringa) o Locator; nuovo: Locator per ruolo e nome. visibili: del vecchio solo i
    pezzi visibili (i ruoli non vedono quelli nascosti, le classi sì)."""
    v = pg.locator(vecchio) if isinstance(vecchio, str) else vecchio
    if visibili:
        v = v.filter(visible=True)
    hv, hn = v.element_handles(), nuovo.element_handles()
    uguali = sum(1 for a, b in zip(hv, hn) if pg.evaluate('([a, b]) => a === b', [a, b]))
    if modo == 'uno':
        buono = len(hv) == 1 and len(hn) == 1 and uguali == 1
    elif modo == 'nessuno':
        buono = len(hv) == len(hn) == 0
    else:
        buono = len(hv) == len(hn) > 0 and uguali == len(hv)
    ok('%s [%s]' % (nome, modo if modo != 'lista' else 'lista di %d' % len(hv)), buono,
       'vecchio %d, nuovo %d, uguali %d (%s)' % (len(hv), len(hn), uguali, vecchio if isinstance(vecchio, str) else 'locator'))
    return buono


def testo_b(a):
    """Le parole in grassetto di una voce del menu, senza il contatore."""
    return a.locator('b').evaluate('b => b.firstChild.textContent.trim()')


def coppie_112(pg, err):
    """Le coppie di prove_112_browser.py (gli ambulatori) che non sono già nel giro: le tendine del menu aperte (la
    diagnosi di apri_stampa_e_scarica), «Metti» e la «×» come nella raccolta, con i messaggi e la domanda (alla fine
    i dati sono come prima), le tendine della pagina lette come le legge la raccolta, il gruppo attivo in ogni pagina,
    le notifiche e il menu nella dashboard e nel modo schermo (in una scheda nuova: niente notifiche chiuse prima)."""
    aperte_vecchio = ("() => [...document.querySelectorAll('nav.menu .gruppo')].filter(g => { const t = g.querySelector('.tendina');"
                      " return t && getComputedStyle(t).display !== 'none'; }).length")    # il TENDINE_MENU_APERTE di prima
    pg.goto(B + '/ambulatori/settimana/%s?struttura=1' % LUN.isoformat())
    pg.wait_for_selector('#matrice-ambulatori')
    pg.mouse.move(2, 500)
    pg.wait_for_timeout(150)
    ok('112: nessuna tendina del menu aperta, per stile e per ruolo', pg.evaluate(aperte_vecchio) == tendina_aperta(pg).count() == 0,
       (pg.evaluate(aperte_vecchio), tendina_aperta(pg).count()))
    t = apri_gruppo(pg, 'Ambulatori')
    ok('112: una tendina del menu aperta, per stile e per ruolo', pg.evaluate(aperte_vecchio) == tendina_aperta(pg).count() == 1,
       (pg.evaluate(aperte_vecchio), tendina_aperta(pg).count()))
    stesso(pg, '112: la tendina aperta del menu', pg.locator('nav.menu .gruppo .tendina').filter(visible=True), tendina_aperta(pg))
    stesso(pg, '112: le voci del gruppo attivo (come le legge la raccolta)', 'nav.menu .gruppo.attivo .tendina a', t.get_by_role('link'), 'lista')
    pg.keyboard.press('Escape')
    pg.mouse.move(2, 500)
    pg.wait_for_timeout(150)
    ok('112: dopo Esc nessuna tendina, per stile e per ruolo', pg.evaluate(aperte_vecchio) == tendina_aperta(pg).count() == 0,
       (pg.evaluate(aperte_vecchio), tendina_aperta(pg).count()))
    stesso(pg, '112 matrice: il gruppo attivo', 'nav.menu .gruppo.attivo .apri-gruppo', gruppo(pg, 'Ambulatori'))
    ok('112 matrice: gruppo_attivo() è Ambulatori', gruppo_attivo(pg) == 'Ambulatori', gruppo_attivo(pg))
    # «Metti» Galasso in una cella libera, poi la «×»: Annulla lascia il turno, OK lo toglie
    cella = pg.locator('#matrice-ambulatori td.libera:has(details.metti)').first
    chiave = cella.get_attribute('data-cella')
    cella.locator('details.metti summary').click()
    modulo = cella.locator('details.metti form')
    modulo.wait_for(state='visible')
    modulo.locator('select[name=operatore]').select_option(label='Galasso')
    with pg.expect_navigation():
        modulo.locator('button[type=submit]').click()
    stesso(pg, '112: la zona dei messaggi dopo «Metti»', '.avvisi', zona_messaggi(pg))
    ok('112: messaggi() è il testo di .avvisi («Turno salvato»)',
       messaggi(pg) == pg.locator('.avvisi').inner_text() and 'Turno salvato: Galasso' in messaggi(pg), messaggi(pg)[:150])
    cella = pg.locator('td[data-cella="%s"]' % chiave)
    x = cella.get_by_role('button', name=re.compile('^Togli '))
    stesso(pg, '112: la «×» di Galasso', cella.locator('form.togli-turno button'), x)
    with rispondi(pg, si=False) as d:
        x.click()
    ok('112: la «×» fa la domanda a rispondi(), Annulla lascia il turno',
       (d.testo or '').startswith('Togliere Galasso') and cella.locator('form.togli-turno').count() == 1, d.testo)
    with pg.expect_navigation():
        with rispondi(pg) as d:
            x.click()
    stesso(pg, '112: la zona dei messaggi dopo la «×»', '.avvisi', zona_messaggi(pg))
    ok('112: messaggi() è il testo di .avvisi («Turno tolto»), la cella di nuovo libera',
       messaggi(pg) == pg.locator('.avvisi').inner_text() and 'Turno tolto: Galasso' in messaggi(pg)
       and pg.locator('td[data-cella="%s"] .disponibile' % chiave).count() == 1, messaggi(pg)[:150])
    tp = apri_comandi(pg, 'Stampa e scarica')
    stesso(pg, '112 matrice: Stampa e scarica (tendina)', '.gruppo-comandi .tendina', tp)
    stesso(pg, '112 matrice: Stampa e scarica (voci, come le legge la raccolta)', '.gruppo-comandi .tendina a', tp.get_by_role('link'), 'lista')
    pg.mouse.click(5, 760)
    pg.wait_for_timeout(150)

    pg.goto(B + '/ambulatori/mese/%s?struttura=1' % LUN.strftime('%Y-%m'))
    pg.wait_for_selector('#programmazione-ambulatori')
    stesso(pg, '112 mese: il gruppo attivo', 'nav.menu .gruppo.attivo .apri-gruppo', gruppo(pg, 'Ambulatori'))
    ok('112 mese: gruppo_attivo() è Ambulatori', gruppo_attivo(pg) == 'Ambulatori', gruppo_attivo(pg))
    t = apri_comandi(pg, 'Altre esportazioni')
    stesso(pg, '112 mese: Altre esportazioni (voci)', '[data-guida="programmazione-altre"] .tendina a', t.get_by_role('link'), 'lista')
    pg.set_viewport_size({'width': 390, 'height': 844})
    pg.reload()
    stesso(pg, '112 mese sul telefono: Altre esportazioni (pulsante)', '[data-guida="programmazione-altre"] .apri-gruppo',
           pg.get_by_role('button', name='Altre esportazioni'))
    t = apri_comandi(pg, 'Altre esportazioni')
    stesso(pg, '112 mese sul telefono: Altre esportazioni (tendina)', '[data-guida="programmazione-altre"] .tendina', t)
    pg.set_viewport_size({'width': 1366, 'height': 820})
    pg.goto(B + '/esportazioni?struttura=1&data=%s' % OGGI.isoformat())
    stesso(pg, '112 esportazioni: il gruppo attivo', 'nav.menu .gruppo.attivo .apri-gruppo', gruppo(pg, 'Ambulatori'))
    pg.goto(B + '/ambulatori/riepilogo?struttura=1&periodo=oggi')
    stesso(pg, '112 riepilogo del periodo: il gruppo attivo', 'nav.menu .gruppo.attivo .apri-gruppo', gruppo(pg, 'Ambulatori'))
    ok('112 riepilogo del periodo: gruppo_attivo() è Ambulatori', gruppo_attivo(pg) == 'Ambulatori', gruppo_attivo(pg))

    p2 = pg.context.new_page()
    p2.on('pageerror', lambda e: err.append(str(e)))
    domande2 = prepara_domande(p2)
    notifiche = p2.get_by_role('region', name='Notifiche', exact=True)
    anche_nascoste = p2.get_by_role('region', name='Notifiche', exact=True, include_hidden=True)
    stile = "() => getComputedStyle(document.getElementById('notifiche')).display"
    p2.goto(B + '/ambulatori/riepilogo?struttura=1')
    try:
        p2.wait_for_selector('#notifiche .notifica', timeout=8000)
    except Exception:  # noqa: BLE001  senza notifiche la coppia qui sotto cade da sola
        pass
    stesso(p2, '112 riepilogo: le notifiche', '#notifiche .notifica', notifiche.get_by_role('status'), 'lista')
    stesso(p2, '112 riepilogo: le notifiche (anche nascoste)', '#notifiche .notifica',
           anche_nascoste.get_by_role('status', include_hidden=True), 'lista')
    ok('112 riepilogo: la zona delle notifiche si vede, per stile e per ruolo', p2.evaluate(stile) != 'none' and notifiche.count() == 1,
       (p2.evaluate(stile), notifiche.count()))
    p2.goto(B + '/riepilogo-live?struttura=1')
    p2.wait_for_selector('#riepilogo-live .frase-live')
    stesso(p2, '112 riepilogo live: il menu', 'nav.menu', menu(p2))
    ok('112 riepilogo live: le notifiche nascoste, per stile e per ruolo (la zona c\'è)',
       p2.evaluate(stile) == 'none' and notifiche.count() == 0 and anche_nascoste.count() == 1,
       (p2.evaluate(stile), notifiche.count(), anche_nascoste.count()))
    stesso(p2, '112 riepilogo live: la zona delle notifiche, nascosta', '#notifiche', anche_nascoste)
    stesso(p2, '112 riepilogo live: nessuna notifica, nemmeno nascosta', '#notifiche .notifica',
           anche_nascoste.get_by_role('status', include_hidden=True), 'nessuno')
    for indirizzo, col_menu in (('/riepilogo-live?struttura=1&schermo=1', False), ('/riepilogo-live/statistiche?struttura=1', True),
                                ('/riepilogo-live/statistiche?struttura=1&schermo=1', False)):
        p2.goto(B + indirizzo)
        p2.wait_for_selector('.frase-live')
        stesso(p2, '112 %s: %s' % (indirizzo, 'il menu' if col_menu else 'nessun menu'), 'nav.menu', menu(p2), 'uno' if col_menu else 'nessuno')
    ok('112: nessuna domanda inattesa nella seconda scheda', not domande2.inattese, domande2.inattese)
    p2.close()


def coppie_guida_tendine(br, err):
    """Le coppie di prove_guida_browser.py e prove_tendine_browser.py, fatte come le fanno quelle raccolte: la
    tendina di Segreteria aperta con un clic e chiusa con Esc, Configura aperta passandoci sopra, «Stampa e
    scarica» aperta e chiusa con un clic fuori (a 1366x820); poi a 1366x657 le voci di «Stampa e scarica» e dei
    gruppi nei giorni particolari della griglia e su tutte le pagine del menu, i tasti rapidi, la ricerca rapida
    anche su Pazienti, le notifiche della griglia. In una scheda sua: un pezzo che non si trova si conta e il giro
    di prima arriva in fondo lo stesso."""
    from aiuti_browser import principale
    ctx = br.new_context(viewport={'width': 1366, 'height': 820}, locale='it-IT')
    ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); localStorage.setItem('guida-viste', '{\"*\":1}'); } catch (e) {}")
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: err.append(str(e)))
    domande = prepara_domande(pg)
    try:
        pg.goto(B + '/giorno/%s?struttura=1' % OGGI.isoformat())
        # le notifiche arrivano 0,8 secondi dopo la pagina; prove_tendine guarda il riquadro e il collegamento
        zona = pg.get_by_role('region', name='Notifiche', exact=True)
        notifiche = zona.get_by_role('status')
        try:
            notifiche.first.wait_for(timeout=5000)
        except Exception:  # noqa: BLE001  senza notifiche le coppie qui sotto cadono da sole
            pass
        stesso(pg, 'tendine: la zona delle notifiche (.notifiche)', '.notifiche', zona)
        stesso(pg, 'tendine: le notifiche della griglia', '.notifiche .notifica', notifiche, 'lista')
        stesso(pg, 'tendine: i loro collegamenti', '.notifiche .notifica a', notifiche.get_by_role('link'), 'lista')
        # prove_guida: clic, Esc, passandoci sopra, «Stampa e scarica», clic fuori
        pg.mouse.move(700, 700)
        gruppo(pg, 'Segreteria').click()
        pg.wait_for_timeout(150)
        stesso(pg, 'guida: Segreteria aperta al clic', '[data-guida="menu-segreteria"] .tendina', tendina_aperta(pg), visibili=True)
        stesso(pg, '   la sua voce «Conferme»', '[data-guida="menu-segreteria"] .tendina a[data-tasto="c"]',
               tendina_aperta(pg).get_by_role('link', name=nome_voce('Conferme')))
        pg.keyboard.press('Escape')
        pg.mouse.move(700, 700)
        pg.wait_for_timeout(150)
        stesso(pg, 'guida: dopo Esc nessuna tendina', '[data-guida="menu-segreteria"] .tendina', tendina_aperta(pg), 'nessuno', visibili=True)
        gruppo(pg, 'Configura').hover()
        pg.wait_for_timeout(150)
        stesso(pg, 'guida: Configura aperta passandoci sopra', '[data-guida="menu-configura"] .tendina', tendina_aperta(pg), visibili=True)
        stesso(pg, '   la sua voce «Anagrafiche»', pg.locator('[data-guida="menu-configura"] .tendina a', has=pg.locator('b', has_text='Anagrafiche')),
               tendina_aperta(pg).get_by_role('link', name=nome_voce('Anagrafiche')))
        pg.mouse.move(700, 700)
        pg.wait_for_timeout(150)
        stesso(pg, 'guida: Stampa e scarica (il pulsante nella pagina)', '[data-guida="giorno-stampa"] .apri-gruppo',
               principale(pg).get_by_role('button', name=nome_voce('Stampa e scarica')))
        t = apri_comandi(pg, 'Stampa e scarica')
        stesso(pg, 'guida: Stampa e scarica aperta', '[data-guida="giorno-stampa"] .tendina', t, visibili=True)
        pg.mouse.click(700, 760)
        pg.wait_for_timeout(150)
        stesso(pg, 'guida: clic fuori, chiusa', '[data-guida="giorno-stampa"] .tendina', t, 'nessuno', visibili=True)

        # prove_tendine, a 1366x657 come la segreteria
        pg.set_viewport_size({'width': 1366, 'height': 657})
        mar = OGGI - timedelta(days=(OGGI.weekday() - 1) % 7)
        giorni = [('oggi', OGGI), ('domani', OGGI + timedelta(days=1)), ('con la sala operatoria', mar),
                  ('con la nota del giorno', mar + timedelta(days=2)), ('chiuso', date(OGGI.year, 12, 24)),
                  ('festivo', date(OGGI.year, 12, 8))]
        tre = ('Segreteria', 'Aiuto', 'Configura')

        def voci_dei_gruppi(dove):
            for g in tre:
                t = apri_gruppo(pg, g)
                stesso(pg, '   %s: voci di %s' % (dove, g), '[data-guida="menu-%s"] .tendina a' % g.lower(), t.get_by_role('link'),
                       'lista', visibili=True)
            pg.keyboard.press('Escape')
            pg.mouse.move(3, 3)
            pg.wait_for_timeout(150)

        for nome, g in giorni:
            pg.goto(B + '/giorno/%s?struttura=1' % g.isoformat())
            t = apri_comandi(pg, 'Stampa e scarica')
            stesso(pg, 'tendine, giorno %s: voci di Stampa e scarica' % nome, '[data-guida="giorno-stampa"] .tendina a',
                   t.get_by_role('link'), 'lista', visibili=True)
            voci_dei_gruppi('giorno %s' % nome)
        pg.goto(B + '/giorno/%s?struttura=1' % OGGI.isoformat())
        pg.keyboard.press('?')
        pg.wait_for_timeout(300)
        stesso(pg, 'tendine: le righe dei tasti rapidi', '#aiuto-tasti tr',
               pg.get_by_role('dialog', name='Tasti rapidi', exact=True).get_by_role('row'), 'lista')
        pg.keyboard.press('Escape')
        prima = pg.eval_on_selector_all('.menu a[href]', 'as => as.map(a => a.getAttribute("href"))')
        dopo = menu(pg).get_by_role('link', include_hidden=True).evaluate_all('as => as.map(a => a.getAttribute("href"))')
        ok('tendine: gli indirizzi del menu per ruolo sono quelli di «.menu a[href]» (%d)' % len(dopo), dopo == prima, (prima, dopo))
        visti = []
        for h in dopo:
            percorso = h.split('?')[0]
            if h.startswith('#') or percorso in visti:
                continue
            visti.append(percorso)
            pg.goto(B + h if h.startswith('/') else h)
            pg.wait_for_timeout(300)
            voci_dei_gruppi('pagina %s' % percorso)
        for pagina in ('/giorno/%s?struttura=1' % mar.isoformat(), '/pazienti'):
            pg.goto(B + pagina)
            corta = pagina.split('?')[0]
            stesso(pg, 'tendine, %s: il campo della ricerca rapida' % corta, '#ricerca-rapida', menu(pg).get_by_role('search').get_by_role('searchbox'))
            r = cerca_rapido(pg, 'Sep')
            pg.wait_for_timeout(300)
            stesso(pg, '   i risultati di «Sep»', '#risultati-rapidi a.voce-rapida', r, 'lista')
            pg.keyboard.press('Escape')
    except Exception as e:  # noqa: BLE001
        ok('coppie di prove_guida e prove_tendine: arrivano in fondo', False, '%s: %s' % (type(e).__name__, str(e)[:400]))
    ok('coppie di prove_guida e prove_tendine: nessuna domanda inattesa', not domande.inattese, domande.inattese)
    ctx.close()


def coppie_18_tariffari(br, err):
    """Le coppie di prove_18_browser.py e prove_tariffari_browser.py (le domande), fatte come le fanno quelle
    raccolte: «Strumenti» della settimana dei turni, «Copia la settimana prima» con la sua domanda (OK) e i
    messaggi dopo, «Schema a rotazione…» con due celle scelte; «Elimina» di una persona (OK) e i messaggi dopo;
    i messaggi dopo «Carica tariffario» e «Elimina il tariffario» di un tariffario senza apostrofo (OK). In una
    scheda sua: un pezzo che non si trova si conta e il giro di prima arriva in fondo lo stesso. Alla fine i dati
    di prova sono come prima: la settimana copiata è lontana e quella prima è vuota (niente da copiare)."""
    import tempfile
    from openpyxl import Workbook
    from aiuti_browser import principale
    ctx = br.new_context(viewport={'width': 1366, 'height': 768}, locale='it-IT')
    ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); localStorage.setItem('guida-viste', '{\"*\":1}'); } catch (e) {}")
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: err.append(str(e)))
    domande = prepara_domande(pg)
    try:
        # prove_18: la settimana dei turni, «Strumenti», «Copia la settimana prima» con OK, i messaggi
        lun = OGGI - timedelta(days=OGGI.weekday()) + timedelta(days=7 * 41)
        pg.goto(B + '/personale/turni/settimana/%s' % lun.isoformat())
        strumenti = principale(pg).get_by_role('button', name=nome_voce('Strumenti'))
        stesso(pg, '18 settimana: il pulsante Strumenti', '.gruppo-comandi .apri-gruppo', strumenti)
        t = apri_comandi(pg, 'Strumenti')
        stesso(pg, '18 settimana: la tendina di Strumenti', '.gruppo-comandi .tendina', t)
        copia = t.get_by_role('menuitem', name=nome_voce('Copia la settimana prima'))
        stesso(pg, '18 settimana: Copia la settimana prima', '[data-copia-settimana]', copia)
        with pg.expect_navigation():
            with rispondi(pg) as d:
                copia.click()
        ok('18 settimana: la copia fa la domanda a rispondi() (OK)',
           (d.testo or '').startswith('Copiare qui i turni della settimana prima?'), d.testo)
        stesso(pg, '18 settimana: la zona dei messaggi dopo la copia', '.avvisi', zona_messaggi(pg))
        ok('18 settimana: messaggi() è il testo di .avvisi', messaggi(pg) == pg.locator('.avvisi').inner_text()
           and 'la settimana prima' in messaggi(pg), messaggi(pg)[:150])
        # prove_18: due celle scelte (due persone), poi «Strumenti» e «Schema a rotazione…»
        pg.goto(B + '/personale/turni/settimana/%s' % (lun + timedelta(days=7)).isoformat())
        righe = pg.locator('#griglia-turni tbody[data-ruolo="INFERMIERE"] tr.riga-persona')
        righe.nth(0).locator('td.cella').nth(0).click()
        pg.keyboard.press('Escape')
        righe.nth(1).locator('td.cella').nth(6).click(modifiers=['Shift'])
        pg.keyboard.press('Escape')
        stesso(pg, '18 settimana, celle scelte: il pulsante Strumenti', '.gruppo-comandi .apri-gruppo', strumenti)
        t = apri_comandi(pg, 'Strumenti')
        schema = t.get_by_role('menuitem', name=nome_voce('Schema a rotazione…'))
        stesso(pg, '18 settimana, celle scelte: Schema a rotazione…', '[data-apri-schema]', schema)
        schema.click()
        ok('18 settimana: lo schema si apre con le due persone scelte', pg.locator('#finestra-schema').is_visible()
           and pg.locator('#finestra-schema input[name=persone]:checked').count() == 2,
           pg.locator('#finestra-schema input[name=persone]:checked').count())
        # prove_18: «Elimina» di una persona con l'apostrofo, OK, i messaggi
        pg.goto(B + '/personale/persone/nuova?ruolo=OSS')
        pg.fill('#cognome', "D'Esempio")
        pg.fill('#nome', 'Carla')
        with pg.expect_navigation():
            pg.click('.modulo-persona button.primario')
        with pg.expect_navigation():
            pg.locator('table.elenco-persone tr', has_text="D'Esempio Carla").last.get_by_role('link', name='Modifica').click()
        scheda = pg.url
        elimina = pg.get_by_role('button', name='Elimina', exact=True)
        stesso(pg, '18 persona: Elimina', '.elimina-persona button[type=submit]', elimina)
        with pg.expect_navigation():
            with rispondi(pg) as d:
                elimina.click()
        ok("18 persona: la domanda «Eliminare D'Esempio Carla?» a rispondi(), OK la elimina",
           d.testo == "Eliminare D'Esempio Carla?" and pg.request.get(scheda).status == 404, d.testo)
        stesso(pg, '18 persona: la zona dei messaggi dopo «Elimina»', '.avvisi', zona_messaggi(pg))
        ok('18 persona: messaggi() è il testo di .avvisi («Persona eliminata»)',
           messaggi(pg) == pg.locator('.avvisi').inner_text() and 'Persona eliminata' in messaggi(pg), messaggi(pg)[:150])
        # prove_tariffari: «Carica tariffario» con un Excel inventato, i messaggi; «Elimina il tariffario» con OK
        file = os.path.join(tempfile.mkdtemp(prefix='equivalenza_tariffari_'), 'tariffario-prova-guarino.xlsx')
        wb = Workbook()
        for r in (('TARIFFARIO DOTT. GUARINO', None), ('Prestazione', 'Prezzo (€)'), ('Visita diabetologica', 95),
                  ('Visita di controllo', 65), ('Piano alimentare', 40)):
            wb.active.append(list(r))
        wb.save(file)
        pg.goto(B + '/cassa/tariffari')
        pg.set_input_files('input[name="file"]', file)
        pg.click('button:has-text("Carica tariffario")')
        pg.wait_for_selector('.tariffario-proposto')
        with pg.expect_navigation():
            pg.click('button:has-text("Salva i tariffari")')
        stesso(pg, 'tariffari: la zona dei messaggi dopo «Salva i tariffari»', '.avvisi', zona_messaggi(pg))
        ok('tariffari: messaggi() è il testo di .avvisi («Tariffari caricati»)', messaggi(pg) == pg.locator('.avvisi').inner_text()
           and 'Tariffari caricati: Dott. Guarino' in messaggi(pg), messaggi(pg)[:150])
        pg.locator('a', has_text='Dott. Guarino').first.click()
        pg.wait_for_selector('.scheda-tariffario')
        scheda = pg.url
        elimina = pg.get_by_role('button', name='Elimina il tariffario')
        stesso(pg, 'tariffari: Elimina il tariffario (nome senza apostrofo)', 'button:has-text("Elimina il tariffario")', elimina)
        with pg.expect_navigation():
            with rispondi(pg) as d:
                elimina.click()
        ok('tariffari: la domanda «Eliminare il tariffario «Dott. Guarino»?…» a rispondi(), OK lo elimina',
           (d.testo or '').startswith('Eliminare il tariffario «Dott. Guarino»?') and pg.request.get(scheda).status == 404, d.testo)
        stesso(pg, 'tariffari: la zona dei messaggi dopo «Elimina il tariffario»', '.avvisi', zona_messaggi(pg))
    except Exception as e:  # noqa: BLE001
        ok('coppie di prove_18 e prove_tariffari: arrivano in fondo', False, '%s: %s' % (type(e).__name__, str(e)[:400]))
    ok('coppie di prove_18 e prove_tariffari: nessuna domanda inattesa', not domande.inattese, domande.inattese)
    ctx.close()


def giro(br):
    ctx = br.new_context(viewport={'width': 1366, 'height': 820}, locale='it-IT')
    ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); localStorage.setItem('guida-viste', '{\"*\":1}'); "
                        "localStorage.setItem('gestionale-tema', 'chiaro'); } catch (e) {}")
    pg = ctx.new_page()
    err = []
    pg.on('pageerror', lambda e: err.append(str(e)))
    domande = prepara_domande(pg)

    # ======================================================== il menu (pagina Giorno)
    pg.goto(B + '/giorno/%s?struttura=1' % OGGI.isoformat())
    pg.wait_for_timeout(500)
    stesso(pg, 'la barra del menu', 'nav.menu', menu(pg))
    stesso(pg, 'la barra del menu (querySelector(".menu"))', pg.locator('.menu').first, menu(pg))
    ok('«.menu» trova solo la barra', pg.locator('.menu').count() == 1, pg.locator('.menu').count())
    for g in GRUPPI:
        dg = 'menu-' + g.lower()
        stesso(pg, 'pulsante del gruppo %s' % g, '[data-guida="%s"] .apri-gruppo' % dg, gruppo(pg, g))
        stesso(pg, 'tendina di %s per nome, anche chiusa' % g, '[data-guida="%s"] .tendina' % dg,
               menu(pg).get_by_role('menu', name=g, exact=True, include_hidden=True))
        pg.mouse.move(2, 500)
        t = apri_gruppo(pg, g)
        stesso(pg, 'tendina aperta di %s' % g, '[data-guida="%s"] .tendina' % dg, t)
        stesso(pg, '   è quella con il nome «%s»' % g, '[data-guida="%s"] .tendina' % dg, tendina_aperta(pg).and_(
            menu(pg).get_by_role('menu', name=g, exact=True)))
        stesso(pg, 'voci visibili di %s' % g, '[data-guida="%s"] .tendina a' % dg, t.get_by_role('link'), 'lista', visibili=True)
        # ogni voce per nome: il testo in grassetto basta e trova una voce sola
        for a in pg.locator('[data-guida="%s"] .tendina a' % dg).filter(visible=True).all():
            testo = testo_b(a)
            stesso(pg, '   voce «%s» → «%s»' % (testo, (a.get_attribute('href') or '')[:40]), a,
                   t.get_by_role('link', name=nome_voce(testo)))
        ok('   aria-expanded="true" sul pulsante aperto', gruppo(pg, g).get_attribute('aria-expanded') == 'true')
        pg.keyboard.press('Escape')
        pg.mouse.move(2, 500)
        pg.wait_for_timeout(150)
    for testo in ('Oggi', 'Giorno', 'Settimana', 'Mese', 'Sala', 'Pazienti', 'Turni', 'Dove si fa', 'Cassa', 'Statistiche'):
        stesso(pg, 'voce in vista «%s»' % testo, pg.locator('nav.menu > a', has_text=re.compile('^' + testo + '$')),
               menu(pg).get_by_role('link', name=nome_voce(testo)))
    stesso(pg, 'tutti i collegamenti del menu (anche nelle tendine chiuse)', '.menu a[href]',
           menu(pg).get_by_role('link', include_hidden=True), 'lista')
    # passandoci sopra (prima il fuoco fuori dal menu: dopo Esc il gruppo resta «chiuso» finché il fuoco è dentro)
    pg.mouse.click(700, 760)
    pg.hover('[data-guida="menu-configura"]')
    pg.wait_for_timeout(200)
    stesso(pg, 'Configura aperta passandoci sopra', '[data-guida="menu-configura"] .tendina', tendina_aperta(pg), visibili=True)
    stesso(pg, '   per nome', '[data-guida="menu-configura"] .tendina', menu(pg).get_by_role('menu', name='Configura', exact=True),
           visibili=True)
    ok('   passandoci sopra aria-expanded resta "false" (lo cambia solo il clic)', gruppo(pg, 'Configura').get_attribute('aria-expanded') == 'false')
    pg.mouse.move(2, 500)
    pg.wait_for_timeout(200)
    ok('chiusa: nessuna tendina del menu per ruolo', tendina_aperta(pg).count() == 0, tendina_aperta(pg).count())

    # ======================================================== «Stampa e scarica» della griglia
    stesso(pg, 'Stampa e scarica (pulsante)', '[data-guida="giorno-stampa"] .apri-gruppo', pg.get_by_role('button', name='Stampa e scarica'))
    tp = apri_comandi(pg, 'Stampa e scarica')
    stesso(pg, 'Stampa e scarica (tendina, apri_comandi)', '[data-guida="giorno-stampa"] .tendina', tp)
    stesso(pg, 'Stampa e scarica (voci)', '[data-guida="giorno-stampa"] .tendina a', tp.get_by_role('link'), 'lista', visibili=True)
    pg.mouse.click(700, 760)
    pg.wait_for_timeout(150)
    ok('clic fuori: nessuna tendina per ruolo', pg.get_by_role('menu').count() == 0)

    # ======================================================== ricerca rapida e tasti rapidi
    cerca = menu(pg).get_by_role('search').get_by_role('searchbox')
    stesso(pg, 'campo della ricerca rapida', '#ricerca-rapida', cerca)
    stesso(pg, 'campo della ricerca rapida (per nome)', '#ricerca-rapida', pg.get_by_role('searchbox', name='Cerca un paziente'))
    risultati = cerca_rapido(pg, 'Sep')
    stesso(pg, 'risultati della ricerca rapida (cerca_rapido)', '#risultati-rapidi a.voce-rapida', risultati, 'lista')
    pg.keyboard.press('Escape')
    pg.mouse.click(700, 760)
    pg.keyboard.press('?')
    pg.wait_for_timeout(200)
    riquadro = pg.get_by_role('dialog', name='Tasti rapidi', exact=True)
    stesso(pg, 'tasti rapidi: il riquadro', '#aiuto-tasti', riquadro)
    stesso(pg, 'tasti rapidi: righe', '#aiuto-tasti tr', riquadro.get_by_role('row'), 'lista')
    ok('tasti rapidi: il titolo come intestazione', riquadro.get_by_role('heading', name='Tasti rapidi').count() == 1)
    pg.keyboard.press('Escape')
    pg.wait_for_timeout(150)
    stesso(pg, 'tasti rapidi chiusi: nessun riquadro', pg.locator('#aiuto-tasti').filter(visible=True), riquadro, 'nessuno')

    # ======================================================== notifiche (Oggi)
    pg.goto(B + '/oggi')
    lista = pg.evaluate("() => fetch(document.getElementById('notifiche').getAttribute('data-indirizzo')).then(r => r.json())")
    altre = [x['chiave'] for x in lista if x['titolo'] != 'Aggiornamento disponibile']
    pg.evaluate("(c) => sessionStorage.setItem('notifiche-chiuse', JSON.stringify(c))", altre)
    pg.evaluate("sessionStorage.removeItem('notifiche-viste')")
    pg.reload()
    pg.wait_for_selector('.notifica', timeout=5000)
    zona = pg.get_by_role('region', name='Notifiche', exact=True)
    stesso(pg, 'la zona delle notifiche', '#notifiche', zona)
    stesso(pg, 'notifiche', '#notifiche .notifica', zona.get_by_role('status'), 'lista')
    agg = zona.get_by_role('status').filter(has_text='Aggiornamento disponibile')
    stesso(pg, 'notifica «Aggiornamento disponibile»', '.notifica:has-text("Aggiornamento disponibile")', agg)
    stesso(pg, 'il suo collegamento', '.notifica:has-text("Aggiornamento disponibile") a', agg.get_by_role('link'))
    stesso(pg, 'il suo «Chiudi»', '.notifica:has-text("Aggiornamento disponibile") .chiudi-notifica',
           agg.get_by_role('button', name='Chiudi'))

    # ======================================================== voce e gruppo della pagina aperta (aria-current)
    pagine = [('/oggi', 'Oggi', None), ('/giorno/%s?struttura=1' % OGGI.isoformat(), 'Giorno', None),
              ('/personale/turni/mese/', 'Turni', None), ('/pazienti', 'Pazienti', None),
              ('/ambulatori/settimana/%s?struttura=1' % LUN.isoformat(), 'Pianificazione della settimana', 'Ambulatori'),
              ('/esportazioni', 'Esportazioni in Excel', 'Ambulatori'), ('/conferme', 'Conferme', 'Segreteria'),
              ('/impostazioni', 'Impostazioni', 'Configura'), ('/aiuto/novita', None, 'Aiuto')]
    for indirizzo, voce, g in pagine:
        pg.goto(B + indirizzo)
        corto = indirizzo.split('?')[0]
        if voce:
            stesso(pg, '%s: la voce della pagina aperta' % corto, 'nav.menu a.attivo', voce_attiva(pg))
            stesso(pg, '   ed è «%s»' % voce, voce_attiva(pg), menu(pg).get_by_role('link', name=nome_voce(voce), include_hidden=True))
        else:
            stesso(pg, '%s: nessuna voce della pagina aperta' % corto, 'nav.menu a.attivo', voce_attiva(pg), 'nessuno')
        ok('   aria-current solo sulla voce con la classe attivo (la barra dei turni ha il suo, fuori dal menu)',
           pg.locator('nav.menu [aria-current]').count() == pg.locator('nav.menu a.attivo, nav.menu .gruppo.attivo').count(),
           pg.locator('nav.menu [aria-current]').count())
        stesso(pg, '%s: il gruppo attivo' % corto, 'nav.menu .gruppo.attivo .apri-gruppo', menu(pg).locator('button[aria-current="true"]'),
               'uno' if g else 'nessuno')
        ok('   gruppo_attivo() è %s' % g, gruppo_attivo(pg) == g, gruppo_attivo(pg))

    # ======================================================== vai_dal_menu: ogni voce porta dove porta il suo href
    pg.goto(B + '/giorno/%s?struttura=1' % OGGI.isoformat())
    voci = [('Pazienti', None), ('Turni', None), ('Dove si fa', None), ('Cassa', None), ('Statistiche', None),
            ('Oggi', None), ('Settimana', None), ('Mese', None), ('Sala', None), ('Giorno', None)]
    for g in GRUPPI:
        for a in pg.locator('[data-guida="menu-%s"] .tendina a' % g.lower()).all():
            if (a.get_attribute('href') or '#') != '#':
                voci.append((g, testo_b(a)))
    for g, v in voci:
        atteso = (pg.locator('nav.menu > a', has_text=re.compile('^' + g + '$')) if v is None else
                  pg.locator('nav.menu .tendina a', has=pg.locator('b', has_text=v))).first.get_attribute('href')
        try:
            arrivo = vai_dal_menu(pg, g, v)
            dopo = pg.request.get(B + atteso).url          # dove porta l'href, anche dopo un reindirizzamento (Turni)
            ok('vai_dal_menu(%r%s) → %s' % (g, '' if v is None else ', %r' % v, atteso.split('?')[0]),
               arrivo.split('?')[0] == dopo.split('?')[0], (arrivo, dopo))
        except Exception as e:  # noqa: BLE001
            ok('vai_dal_menu(%r, %r)' % (g, v), False, str(e)[:200])
        pg.goto(B + '/giorno/%s?struttura=1' % OGGI.isoformat())

    # ======================================================== Ambulatori: Stampa e scarica, la «×»
    pg.goto(B + '/ambulatori/settimana/%s?struttura=1' % LUN.isoformat())
    pg.wait_for_selector('#matrice-ambulatori')
    stesso(pg, 'matrice: Stampa e scarica', '.gruppo-comandi .apri-gruppo', pg.get_by_role('button', name='Stampa e scarica'))
    t = apri_comandi(pg, 'Stampa e scarica')
    for vecchio, nuovo in (('Ambulatori e sala in Excel', 'Ambulatori e sala in Excel'), ('La matrice in Excel', 'La matrice in Excel'),
                           ('settimana tipo', 'La settimana tipo in Excel')):
        stesso(pg, 'matrice: voce «%s»' % nuovo, pg.locator('.gruppo-comandi .tendina a', has_text=vecchio),
               t.get_by_role('link', name=nome_voce(nuovo)))
    pg.mouse.click(5, 760)
    pg.mouse.move(2, 500)
    t = apri_gruppo(pg, 'Ambulatori')
    stesso(pg, 'menu: le voci del gruppo attivo', 'nav.menu .gruppo.attivo .tendina a', t.get_by_role('link'), 'lista', visibili=True)
    pg.keyboard.press('Escape')
    pg.mouse.click(5, 760)
    cella = pg.locator('#matrice-ambulatori td.occupata:has(form.togli-turno)').first
    chiave = cella.get_attribute('data-cella')
    stesso(pg, 'la «×» di una cella (aria-label «Togli …»)', 'td[data-cella="%s"] form.togli-turno button' % chiave,
           pg.locator('td[data-cella="%s"]' % chiave).get_by_role('button', name=re.compile('^Togli ')))
    nomi_x = pg.get_by_role('button', name=re.compile('^Togli ')).count()
    ok('le «×» si contano per nome come per classe', nomi_x == pg.locator('form.togli-turno button').count(), nomi_x)

    # ======================================================== Programmazione del mese: Altre esportazioni
    pg.goto(B + '/ambulatori/mese/%s?struttura=1' % LUN.strftime('%Y-%m'))
    stesso(pg, 'mese: Altre esportazioni (pulsante)', '[data-guida="programmazione-altre"] .apri-gruppo', pg.get_by_role('button', name='Altre esportazioni'))
    t = apri_comandi(pg, 'Altre esportazioni')
    stesso(pg, 'mese: Altre esportazioni (tendina)', '[data-guida="programmazione-altre"] .tendina', t)
    stesso(pg, 'mese: «La sala operatoria del mese»', pg.locator('[data-guida="programmazione-altre"] .tendina a', has_text='La sala operatoria del mese'),
           t.get_by_role('link', name=nome_voce('La sala operatoria del mese')))
    pg.mouse.click(5, 760)
    coppie_112(pg, err)

    # ======================================================== Turni della settimana: Strumenti (role=menuitem)
    lun_t = OGGI - timedelta(days=OGGI.weekday())
    pg.goto(B + '/personale/turni/settimana/%s' % (lun_t + timedelta(days=7 * 40)).isoformat())
    stesso(pg, 'turni: Strumenti', '.gruppo-comandi .apri-gruppo', pg.get_by_role('button', name='Strumenti'))
    t = apri_comandi(pg, 'Strumenti')
    stesso(pg, 'turni: Copia la settimana prima', '[data-copia-settimana]', t.get_by_role('menuitem', name=nome_voce('Copia la settimana prima')))
    stesso(pg, 'turni: Schema a rotazione…', '[data-apri-schema]', t.get_by_role('menuitem', name=nome_voce('Schema a rotazione…')))
    with rispondi(pg, si=False) as d:
        t.get_by_role('menuitem', name=nome_voce('Copia la settimana prima')).click()
    ok('rispondi: «Copia la settimana prima» fa la domanda, Annulla la lascia', d.testo and d.testo.startswith('Copiare qui i turni'), d.testo)

    # ======================================================== videoguida, Mostrami
    pg.goto(B + '/aiuto/prenotare')
    video = pg.get_by_role('link', name=nome_voce('Guarda il video'))
    stesso(pg, 'Guarda il video', 'a[data-guida="guarda-video"]', video)
    stesso(pg, 'Mostrami sullo schermo', '[data-guida-mostra]', pg.get_by_role('link', name='Mostrami sullo schermo'))
    titolo = video.get_attribute('data-video')
    video.click()
    pg.wait_for_timeout(300)
    finestra = pg.get_by_role('dialog', name='Videoguida: %s' % titolo, exact=True)
    stesso(pg, 'la finestra del video, con il titolo nel nome', 'dialog.finestra-video', finestra)
    stesso(pg, 'il suo «Chiudi»', 'dialog.finestra-video .testa-video button', finestra.get_by_role('button', name='Chiudi'))
    stesso(pg, 'il video (tag dentro la finestra per ruolo)', 'dialog.finestra-video video', finestra.locator('video'))
    ok('il titolo scritto è quello del nome', pg.locator('dialog.finestra-video .testa-video b').inner_text() == titolo,
       pg.locator('dialog.finestra-video .testa-video b').inner_text())
    pg.keyboard.press('Escape')

    # ======================================================== domande e messaggi: un tariffario con l'apostrofo
    pg.goto(B + '/cassa/tariffari')
    pg.fill('section[data-guida="tariffari-nuovo"] input[name="nome"]', "Tariffario dell'esempio")
    with pg.expect_navigation():
        pg.click('section[data-guida="tariffari-nuovo"] button[type=submit]')
    scheda = pg.url
    stesso(pg, 'Elimina il tariffario', 'button:has-text("Elimina il tariffario")', pg.get_by_role('button', name='Elimina il tariffario'))
    with rispondi(pg, si=False) as d:
        pg.get_by_role('button', name='Elimina il tariffario').click()
    ok('rispondi(si=False): la domanda con il nome intero, il tariffario resta',
       d.testo == "Eliminare il tariffario «Tariffario dell'esempio»? Le prenotazioni già fatte restano con i loro prezzi."
       and pg.request.get(scheda).status == 200, d.testo)
    if pg.request.get(scheda).status == 200:            # senza la domanda (1.12.7) il modulo è già partito
        with pg.expect_navigation():
            with rispondi(pg, si=True) as d:
                pg.get_by_role('button', name='Elimina il tariffario').click()
        ok('rispondi(si=True): eliminato', pg.request.get(scheda).status == 404, d.testo)
    else:
        ok('rispondi(si=True): eliminato', False, 'il tariffario era già stato eliminato senza domanda')
    stesso(pg, 'la zona dei messaggi', '.avvisi', zona_messaggi(pg))
    eliminato = "Tariffario «Tariffario dell'esempio» eliminato."
    ok('messaggi(): il testo dei messaggi', messaggi(pg) == pg.locator('.avvisi').inner_text() and eliminato in messaggi(pg), messaggi(pg))
    va, dettaglio = nella_zona(pg, eliminato, False)
    ok('nella_zona(): il messaggio una volta sola, nella zona, non rosso', va, dettaglio)

    # ======================================================== una persona con l'apostrofo: «Elimina»
    pg.goto(B + '/personale/persone/nuova?ruolo=OSS')
    pg.fill('#cognome', "D'Esempio")
    pg.fill('#nome', 'Anna')
    with pg.expect_navigation():
        pg.click('.modulo-persona button.primario')
    with pg.expect_navigation():
        pg.locator('table.elenco-persone tr', has_text="D'Esempio Anna").last.get_by_role('link', name='Modifica').click()
    scheda = pg.url
    stesso(pg, 'persona: Elimina', '.elimina-persona button[type=submit]', pg.get_by_role('button', name='Elimina', exact=True))
    with rispondi(pg, si=False) as d:
        pg.get_by_role('button', name='Elimina', exact=True).click()
    ok("persona: domanda «Eliminare D'Esempio Anna?», Annulla la lascia", d.testo == "Eliminare D'Esempio Anna?"
       and pg.request.get(scheda).status == 200, d.testo)
    if pg.request.get(scheda).status == 200:
        with pg.expect_navigation():
            with rispondi(pg) as d:
                pg.get_by_role('button', name='Elimina', exact=True).click()
        ok('persona: OK la elimina', pg.request.get(scheda).status == 404, d.testo)
    else:
        ok('persona: OK la elimina', False, 'la persona era già stata eliminata senza domanda')

    # ======================================================== avvisi della griglia dei turni, con «Annulla»
    mese = (OGGI.replace(day=1) + timedelta(days=32 * 30)).replace(day=1)
    pg.goto(B + '/personale/turni/mese/' + mese.strftime('%Y-%m'))
    pg.locator('#griglia-turni tr.riga-persona td.cella').nth(4).click()
    pg.locator('#scelta-turno .scelta-tipo[data-codice="M"]').click()
    pg.wait_for_function("() => !document.querySelector('.in-attesa')", timeout=8000)
    annulla = pg.get_by_role('button', name='Annulla', exact=True)
    stesso(pg, 'turni: «Annulla» dell\'avviso', '.avviso-turni .azione-avviso', annulla)
    stesso(pg, 'turni: l\'avviso fatto (livello ok, role=status)', '.avviso-turni.livello-ok', pg.get_by_role('status').filter(has=annulla))
    annulla.click()
    pg.wait_for_function("() => !document.querySelector('.in-attesa')", timeout=8000)

    # ======================================================== il giro della guida (primo avvio, senza memoria)
    ctx2 = br.new_context(viewport={'width': 1366, 'height': 820}, locale='it-IT')
    g2 = ctx2.new_page()
    g2.goto(B + '/oggi')
    g2.wait_for_timeout(700)
    stesso(g2, 'invito al giro', '.giro-invito', g2.get_by_role('status').filter(has=g2.get_by_role('button', name='Fai il giro')))
    stesso(g2, 'invito: Fai il giro', '.giro-invito button.primario', g2.get_by_role('button', name='Fai il giro'))
    g2.get_by_role('button', name='Fai il giro').click()
    g2.wait_for_timeout(600)
    fum = g2.get_by_role('dialog', name=re.compile(r'^Guida: '))
    stesso(g2, 'fumetto del giro', '.giro-fumetto', fum)
    stesso(g2, 'titolo del passo', '.giro-fumetto h3', fum.get_by_role('heading', level=3))
    stesso(g2, 'conto dei passi («1 di N»)', '.giro-conto', fum.get_by_text(re.compile(r'^\d+ di \d+$')))
    stesso(g2, 'Avanti', '.giro-fumetto .bottone.primario', fum.get_by_role('button', name='Avanti'))
    stesso(g2, 'Chiudi la guida', '.giro-fumetto .giro-chiudi', fum.get_by_role('button', name='Chiudi la guida'))
    g2.keyboard.press('Escape')
    ctx2.close()
    coppie_guida_tendine(br, err)
    coppie_18_tariffari(br, err)

    ok('nessun errore JavaScript', not err, err[:3])
    ok('nessuna domanda inattesa', not domande.inattese, domande.inattese)


with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
    try:
        giro(br)
    except Exception as e:  # noqa: BLE001  un pezzo che non si trova ferma il giro: si conta e si dice dove
        ok('il giro arriva in fondo', False, '%s: %s' % (type(e).__name__, str(e)[:400]))
    br.close()
print('\n%d confronti, %d uguali' % (len(esiti), sum(esiti)))
sys.exit(0 if all(esiti) else 1)
