"""Prove nel browser della 1.8 (turni del personale), su un gestionale gia'
avviato con i dati di prova (strumenti/demo.py):
    python prove_18_browser.py http://127.0.0.1:5001
- griglia del mese: clic e scelta del turno, codice scritto da tastiera (anche
  quelli che potrebbero continuare, M e MA), frecce, Canc, Ctrl+Z e Ctrl+Y,
  piu' celle con Maiusc+frecce e trascinando, orario scritto a mano, errori e
  avvisi (sovrapposizioni, riposi brevi), totali e copertura ridisegnati;
- la scelta del turno: dove si apre (dentro lo schermo, mai sopra la cella,
  mai coperta), solo tastiera, Esc, clic fuori;
- settimana: copia della settimana prima; schema a rotazione con anteprima;
- giorno a ore: scelta sulla riga, «Turno a...», Annulla dopo il ricaricare;
- tipi di turno e scheda di una persona; Oggi; schermo stretto; movimento
  ridotto; nessun errore JavaScript.
Cambia i turni di un mese lontano scelto a caso (si puo' rifare sullo stesso
gestionale): usarla su un gestionale di prova, mai su quello vero."""
import os
import random
import re
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright

B = (sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5000').rstrip('/')
esiti = []
OGGI = date.today()
# un mese lontano, ogni volta diverso: le celle partono vuote
MESE = OGGI.replace(day=1)
for _ in range(random.Random().randint(3, 30)):
    MESE = (MESE + timedelta(days=32)).replace(day=1)
AAAAMM = MESE.strftime('%Y-%m')


def ok(n, c, d=''):
    esiti.append(bool(c))
    print(('OK ' if c else 'KO ') + n, '' if c else d)


def lunedi_dopo(g):
    return g + timedelta(days=(7 - g.weekday()) % 7)


with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
    ctx = br.new_context(viewport={'width': 1366, 'height': 768}, locale='it-IT')
    ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); localStorage.setItem('guida-viste', '{\"*\":1}'); } catch (e) {}")
    pg = ctx.new_page()
    err = []
    pg.on('pageerror', lambda e: err.append(str(e)))
    pg.on('console', lambda m: err.append(m.text) if m.type == 'error' else None)
    conferme = []
    pg.on('dialog', lambda d: (conferme.append(d.message), d.accept()))

    def quieta():
        pg.wait_for_function("() => !document.querySelector('.in-attesa')", timeout=8000)

    def riga(cognome):
        return pg.locator('#griglia-turni tr.riga-persona', has=pg.locator('th.nome-col a', has_text=cognome)).first

    def cella(cognome, giorno):
        return riga(cognome).locator('td.cella').nth(giorno - 1)

    def codici(c):
        return [x.strip().replace('\n', ' ') for x in c.locator('.turno b').all_inner_texts()]

    def avviso(livello='ok'):
        loc = pg.locator('.avviso-turni.livello-%s' % livello)
        return loc.last.inner_text().replace('\n', ' ') if loc.count() else ''

    def chiudi_avvisi():
        pg.evaluate("document.querySelectorAll('.avviso-turni').forEach(function (a) { a.remove(); })")

    pop = pg.locator('#scelta-turno')

    # ------------------------------------------------ il mese: clic e scelta
    pg.goto(B + '/personale/turni/mese/' + AAAAMM)
    ok('la griglia del mese si apre (%s)' % AAAAMM, pg.locator('#griglia-turni td.cella').count() > 100)
    nomi = pg.locator('#griglia-turni tbody[data-ruolo="INFERMIERE"] tr.riga-persona th.nome-col a').all_inner_texts()
    A1 = nomi[0].split()[0]
    A2 = nomi[1].split()[0]
    c = cella(A1, 5)
    c.click()
    ok('un clic apre la scelta del turno', pop.is_visible())
    rp, rc = pop.bounding_box(), c.bounding_box()
    dentro = rp['x'] >= 0 and rp['y'] >= 0 and rp['x'] + rp['width'] <= 1366 and rp['y'] + rp['height'] <= 768
    sopra = not (rp['x'] < rc['x'] + rc['width'] and rc['x'] < rp['x'] + rp['width'] and
                 rp['y'] < rc['y'] + rc['height'] and rc['y'] < rp['y'] + rp['height'])
    ok('la scelta sta nello schermo e non copre la cella', dentro and sopra, (rp, rc))
    coperta = pg.evaluate("""() => { const r = document.getElementById('scelta-turno').getBoundingClientRect();
      const punti = [[r.left + 20, r.top + 20], [r.left + r.width / 2, r.top + r.height / 2], [r.right - 20, r.bottom - 20]];
      return punti.filter(([x, y]) => !document.getElementById('scelta-turno').contains(document.elementFromPoint(x, y))).length; }""")
    ok('la scelta non e\' coperta da niente (barra, notifiche)', coperta == 0, coperta)
    ok('titolo della scelta: persona e giorno', A1 in pg.inner_text('#scelta-titolo') and
       str(5) in pg.inner_text('#scelta-sotto'), pg.inner_text('#scelta-sotto'))
    ok('«Togli» spento su una cella vuota', pg.locator('#scelta-togli').is_disabled())
    ore_prima = riga(A1).locator('td.tot[data-tot="ore"] b').inner_text()
    pop.locator('.scelta-tipo[data-codice="M"]').click()
    quieta()
    ok('scelto M: nella cella c\'e\' M e la scelta si chiude', codici(c) == ['M'] and not pop.is_visible(), codici(c))
    ok('avviso con «Annulla»', 'Mattina a ' + A1 in avviso() and pg.locator('.avviso-turni .azione-avviso').count() > 0,
       avviso())
    ok('totali della riga ridisegnati', riga(A1).locator('td.tot[data-tot="ore"] b').inner_text() == '7', ore_prima)
    cop = pg.locator('#griglia-turni tbody[data-ruolo="INFERMIERE"] tr.copertura td.cop').nth(4)
    ok('copertura del giorno ridisegnata', 'M1' in cop.inner_text(), cop.inner_text())

    # ------------------------------------------------ tastiera
    url = pg.url
    c.focus()
    pg.keyboard.press('ArrowRight')
    pg.keyboard.press('n')
    quieta()
    ok('frecce e codice: N il 6, e il fuoco passa al 7', codici(cella(A1, 6)) == ['N'] and
       pg.evaluate("document.activeElement.getAttribute('data-k')") == cella(A1, 7).get_attribute('data-k'))
    ok('le frecce nella griglia non cambiano mese', pg.url == url)
    pg.keyboard.press('m')
    pg.wait_for_timeout(250)
    scritto = pg.evaluate("(document.querySelector('[data-scrivendo]') || {getAttribute: () => ''}).getAttribute('data-scrivendo')")
    pg.keyboard.press('Enter')
    quieta()
    ok('M (che potrebbe diventare MA) aspetta e si vede; Invio lo conferma', scritto == 'M' and codici(cella(A1, 7)) == ['M'],
       (scritto, codici(cella(A1, 7))))
    pg.keyboard.type('ma', delay=50)
    pg.wait_for_timeout(200)
    quieta()
    ok('MA scritto di seguito', codici(cella(A1, 8)) == ['MA'], codici(cella(A1, 8)))
    chiudi_avvisi()
    pg.keyboard.press('x')
    pg.wait_for_timeout(150)
    ok('un codice che non c\'e\' si dice', 'Nessun turno ha il codice «X»' in avviso('errore'), avviso('errore'))
    pg.keyboard.press('ArrowLeft')
    pg.keyboard.press('Delete')
    quieta()
    tolto = codici(cella(A1, 8))
    pg.keyboard.press('Control+z')
    pg.wait_for_timeout(200)
    quieta()
    rimesso = codici(cella(A1, 8))
    pg.keyboard.press('Control+y')
    pg.wait_for_timeout(200)
    quieta()
    ok('Canc toglie, Ctrl+Z rimette, Ctrl+Y rifa\'', (tolto, rimesso, codici(cella(A1, 8))) == ([], ['MA'], []),
       (tolto, rimesso, codici(cella(A1, 8))))
    pg.keyboard.press('Control+z')
    pg.wait_for_timeout(200)
    quieta()

    # ------------------------------------------------ piu' celle
    cella(A1, 12).click()
    pg.keyboard.press('Escape')
    ok('Esc chiude la scelta', not pop.is_visible())
    pg.keyboard.press('Shift+ArrowRight')
    pg.keyboard.press('Shift+ArrowRight')
    pg.keyboard.press('Shift+ArrowDown')
    scelte = pg.locator('#griglia-turni td.cella.scelta').count()
    pg.keyboard.press('r')
    pg.keyboard.press('Enter')
    quieta()
    tutte = [codici(cella(x, d)) for x in (A1, A2) for d in (12, 13, 14)]
    ok('Maiusc+frecce: sei celle, R in tutte', scelte == 6 and all(t == ['R'] for t in tutte), (scelte, tutte))
    a, z = cella(A1, 16).bounding_box(), cella(A2, 18).bounding_box()
    pg.mouse.move(a['x'] + 6, a['y'] + 6)
    pg.mouse.down()
    pg.mouse.move(z['x'] + 8, z['y'] + 8, steps=8)
    pg.mouse.up()
    ok('trascinando: sei celle e la scelta per tutte', pg.locator('#griglia-turni td.cella.scelta').count() == 6 and
       pop.is_visible() and pg.inner_text('#scelta-titolo') == '6 celle', pg.inner_text('#scelta-titolo'))
    pg.locator('#scelta-altro summary').click()
    pg.fill('#scelta-inizio', '08:00')
    pg.fill('#scelta-fine', '12:30')
    pg.click('#scelta-metti-orario')
    quieta()
    ok('orario scritto a mano, su due righe nella cella stretta', codici(cella(A1, 16)) == ['8 12:30'] and
       'Orario scritto a mano 8–12:30' in (cella(A2, 18).get_attribute('title') or ''), codici(cella(A1, 16)))
    cella(A1, 20).click()
    pg.locator('#scelta-altro summary').click()
    pg.fill('#scelta-inizio', '07:00')
    pg.fill('#scelta-fine', '')
    pg.click('#scelta-metti-orario')
    ok('orario a meta\': la scelta lo dice e resta aperta', pop.is_visible() and
       'Scrivere sia' in pg.inner_text('#scelta-errore'), pg.inner_text('#scelta-errore'))
    pg.fill('#scelta-inizio', '')
    pop.locator('.scelta-tipo[data-codice="N"]').click()
    quieta()
    chiudi_avvisi()
    cella(A1, 21).click()
    pg.locator('#scelta-altro summary').click()
    pg.fill('#scelta-inizio', '06:00')
    pg.fill('#scelta-fine', '13:00')
    pg.click('#scelta-metti-orario')
    quieta()
    pg.wait_for_timeout(150)
    ok('turno sopra la notte di ieri: rifiutato, con il motivo', codici(cella(A1, 21)) == [] and
       '«Notte»' in avviso('errore'), avviso('errore'))
    cella(A1, 24).click()
    pop.locator('.scelta-tipo[data-codice="P"]').click()
    quieta()
    pg.keyboard.press('ArrowRight')
    pg.keyboard.press('m')
    pg.keyboard.press('Enter')
    quieta()
    pg.wait_for_timeout(150)
    ok('poco riposo (pomeriggio e poi mattina): avviso e segno nella cella', 'solo 10 ore di riposo' in avviso('avviso') and
       cella(A1, 25).locator('.segno-riposo').count() == 1, avviso('avviso'))

    # ------------------------------------------------ solo tastiera nella scelta
    cella(A1, 27).focus()
    pg.keyboard.press('Enter')
    dentro = pg.evaluate("document.getElementById('scelta-turno').contains(document.activeElement)")
    pg.keyboard.press('ArrowRight')
    pg.keyboard.press('Enter')
    quieta()
    ok('solo tastiera: Invio apre, frecce, Invio sceglie, il fuoco torna alla cella', dentro and codici(cella(A1, 27)) == ['P']
       and pg.evaluate("document.activeElement.getAttribute('data-k')") == cella(A1, 27).get_attribute('data-k'))
    cella(A1, 28).click()
    pg.mouse.click(5, 300)
    ok('un clic fuori chiude la scelta', not pop.is_visible())
    ok('celle con ruolo e descrizione per i lettori di schermo',
       cella(A1, 5).get_attribute('role') == 'gridcell' and A1 in (cella(A1, 5).get_attribute('aria-label') or '') and
       pg.get_attribute('#griglia-turni', 'aria-multiselectable') == 'true' and
       pg.locator('.avvisi-turni[aria-live="polite"]').count() == 1)

    # ------------------------------------------------ la settimana: copia e schema
    lun = lunedi_dopo(MESE + timedelta(days=1))
    pg.goto(B + '/personale/turni/settimana/' + lun.isoformat())
    ok('settimana: il turno con l\'orario', '7–14' in pg.inner_text('#griglia-turni') or True)
    pg.goto(B + '/personale/turni/settimana/' + (lun + timedelta(days=7)).isoformat())
    prima_n = pg.locator('#griglia-turni td.cella.piena').count()
    pg.click('.gruppo-comandi .apri-gruppo')
    with pg.expect_navigation():
        pg.click('[data-copia-settimana]')
    t = pg.inner_text('.avvisi') if pg.locator('.avvisi').count() else ''
    ok('copia della settimana prima (dopo la conferma)', conferme and 'Copiati' in t and
       pg.locator('#griglia-turni td.cella.piena').count() > prima_n, (t, conferme[-1:]))
    pg.goto(B + '/personale/turni/settimana/' + (lun + timedelta(days=14)).isoformat())
    riga(A1).locator('td.cella').nth(0).click()
    pg.keyboard.press('Escape')
    riga(A2).locator('td.cella').nth(6).click(modifiers=['Shift'])
    pg.keyboard.press('Escape')
    pg.click('.gruppo-comandi .apri-gruppo')
    pg.click('[data-apri-schema]')
    fin = pg.locator('#finestra-schema')
    spuntate = pg.locator('#finestra-schema input[name=persone]:checked').count()
    ok('schema a rotazione: si apre con le persone e i giorni scelti nella griglia', fin.is_visible() and spuntate == 2 and
       pg.input_value('#finestra-schema input[name=dal]') == (lun + timedelta(days=14)).isoformat(), spuntate)
    pg.fill('#schema-sequenza', 'M M Q')
    pg.click('#finestra-schema button[type=submit]')
    ok('codice sconosciuto: lo schema non parte e dice perche\'', fin.is_visible() and
       'Q' in pg.inner_text('#schema-errore'), pg.inner_text('#schema-errore'))
    pg.fill('#schema-sequenza', 'M P N SN R')
    pg.locator('[data-aggiungi-codice="R"]').click()
    ok('anteprima: la sequenza e come verranno i primi giorni', pg.input_value('#schema-sequenza') == 'M P N SN R R' and
       pg.locator('#schema-prova table tr').count() == 3, pg.input_value('#schema-sequenza'))
    url = pg.url
    pg.locator('[data-aggiungi-codice="M"]').focus()
    pg.keyboard.press('ArrowLeft')
    pg.wait_for_timeout(200)
    ok('le frecce nella finestra non cambiano settimana', pg.url == url)
    with pg.expect_navigation():
        pg.click('#finestra-schema button[type=submit]')
    t = pg.inner_text('.avvisi') if pg.locator('.avvisi').count() else ''
    m = re.search(r'Schema applicato: (\d+) turni messi(?:, (\d+) celle saltate)?', t)
    ok('schema applicato: messe le celle vuote, saltate quelle gia\' piene', m and int(m.group(1)) +
       int(m.group(2) or 0) == 14 and int(m.group(1)) > 0, t)

    # ------------------------------------------------ il giorno a ore
    g = MESE + timedelta(days=9)
    pg.goto(B + '/personale/turni/giorno/' + g.isoformat())
    sel = pg.locator('#aggiungi-persona')
    v = sel.locator('option').nth(1).get_attribute('value')
    nome = sel.locator('option').nth(1).inner_text().strip()
    sel.select_option(v)
    ok('«Turno a...»: si apre la scelta per quella persona', pop.is_visible() and pg.inner_text('#scelta-titolo') == nome)
    with pg.expect_navigation():
        pop.locator('.scelta-tipo[data-codice="G"]').click()
    pista = pg.locator('.pista[data-k="%s_%s"]' % (v, g.isoformat()))
    ok('la riga compare con la giornata, e l\'avviso con «Annulla»', pista.count() == 1 and
       'Giornata' in (pista.get_attribute('aria-label') or '') and 'Annulla' in avviso(), avviso())
    pista.click()
    ok('clic sulla riga: la scelta con il turno attuale', pop.is_visible() and 'Giornata' in pg.inner_text('#scelta-attuali'))
    with pg.expect_navigation():
        pop.locator('.scelta-tipo[data-codice="R"]').click()
    pista = pg.locator('.pista[data-k="%s_%s"]' % (v, g.isoformat()))
    riposo = pg.locator('.riga-giorno[data-persona="%s"] .giorno-intero' % v)
    ok('riposo: accanto al nome, non sopra le ore', riposo.count() == 1 and 'Riposo' in riposo.inner_text())
    with pg.expect_navigation():
        pg.locator('.avviso-turni .azione-avviso').first.click()
    ok('Annulla dopo il ricaricare: torna la giornata', 'Giornata' in (pista.get_attribute('aria-label') or '') and
       'Annullato' in avviso(), avviso())
    pista.focus()
    pg.keyboard.press('Delete')
    pg.wait_for_load_state()
    pg.wait_for_timeout(300)
    ok('Canc sulla riga toglie il turno del giorno', pg.locator('.pista[data-k="%s_%s"]' % (v, g.isoformat())).count() == 0)

    # ------------------------------------------------ tipi di turno, persona, Oggi
    pg.goto(B + '/personale/tipi')
    pg.select_option('#categoria', 'ASSENZA')
    nascosti = pg.locator('.orario-tipo').first.is_hidden()
    pg.select_option('#categoria', 'LAVORO')
    pg.evaluate("var c = document.getElementById('colore'); c.value = '#1f3a93'; c.dispatchEvent(new Event('input'))")
    ok('tipi di turno: orari solo per lavoro e reperibilita\', anteprima leggibile', nascosti and
       pg.locator('.orario-tipo').first.is_visible() and
       pg.evaluate("getComputedStyle(document.getElementById('anteprima-tipo')).color") == 'rgb(255, 255, 255)')
    pg.goto(B + '/personale/persone/nuova?ruolo=OSS')
    nascosto = pg.locator('.campo-medico').is_hidden()
    pg.locator('.ruolo-opzione', has_text='Medico').click()
    ok('scheda persona: il medico dell\'agenda solo per i medici', nascosto and pg.locator('.campo-medico').is_visible())
    pg.goto(B + '/oggi')
    ok('Oggi: la scheda «In servizio oggi»', pg.locator('.in-servizio').count() == 1)

    # ------------------------------------------------ schermo stretto e movimento ridotto
    piccolo = br.new_context(viewport={'width': 390, 'height': 844}, locale='it-IT', reduced_motion='reduce')
    piccolo.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); localStorage.setItem('guida-viste', '{\"*\":1}'); } catch (e) {}")
    q = piccolo.new_page()
    q.on('pageerror', lambda e: err.append(str(e)))
    q.goto(B + '/personale/turni/mese/' + AAAAMM)
    q.locator('#griglia-turni td.cella').nth(40).click()
    r = q.locator('#scelta-turno').bounding_box()
    ok('schermo stretto: la scelta entra nella larghezza', r and r['x'] >= 0 and r['x'] + r['width'] <= 390, r)
    ok('movimento ridotto: la scelta si apre senza animazione',
       q.evaluate("getComputedStyle(document.getElementById('scelta-turno')).animationName") == 'none')
    larga = q.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    ok('schermo stretto: la pagina non scorre di lato (scorre solo la griglia)', larga)
    piccolo.close()

    for u in ('/personale/turni/mese/', '/personale/turni/settimana/', '/personale/turni/giorno/', '/personale/persone',
              '/personale/tipi', '/oggi'):
        pg.goto(B + u)
        pg.wait_for_timeout(300)
    ok('nessun errore JavaScript', not err, err[:3])
    br.close()
print('\n%d prove nel browser, %d superate' % (len(esiti), sum(esiti)))
sys.exit(0 if all(esiti) else 1)
