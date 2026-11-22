"""Prove nel browser: le tendine e i riquadri che si aprono sopra la pagina si
vedono per intero, senza niente sopra (nota del giorno, avvisi, griglia) e
senza pezzi tagliati, su un gestionale avviato con i dati di prova (vedi
LEGGIMI, «Prove»):
    python prove_tendine_browser.py http://127.0.0.1:5001
- la tendina Aiuto del menu (dalla tappa 2 l'unica rimasta: Segreteria e
  Configura sono voci con le loro linguette) su tutte le pagine del menu e
  delle linguette;
- «Stampa e scarica» nella griglia, nei giorni con la nota del giorno, la sala
  operatoria, gli appunti da confermare, la chiusura della struttura, un festivo;
- i risultati della ricerca rapida (Cerca, nella barra in alto);
- i suggerimenti del paziente e del luogo di nascita nella prenotazione, nella
  scheda del paziente e nella lista d'attesa;
- il riquadro dei tasti rapidi e le notifiche.
Per ogni voce il punto al centro e quelli ai due lati devono essere proprio
della voce (document.elementFromPoint): se un altro riquadro ci sta sopra, o la
voce esce dallo schermo, la prova lo dice. A 1366x657 (lo schermo della
segreteria con le barre del browser) e a 1920x969. Non salva niente.

Dalla tappa 2 (la cornice: menu a sinistra, barra in alto, linguette):
- menu, barra e linguette non coprono niente della pagina, e niente copre le loro voci, a 1366x657, 1024x657 e
  683x657, in cima alla pagina e scorsa in fondo (CORNICE_COPRE, con il gemello: un riquadro della pagina messo apposta
  sotto il menu viene visto);
- ogni pagina del menu e delle sue linguette si raggiunge da lì (il giro parte dalle voci del menu e passa per le
  linguette di ognuna);
- i tasti G, E, C e D portano alla pagina giusta, con la struttura e il giorno della pagina;
- in stampa la cornice sparisce (con il media «print»: nessun pezzo con data-cornice si vede, e la pagina comincia
  dal bordo).

Nella versione animata la tendina «Stampa e scarica» finiva sotto la nota del
giorno, gli avvisi e la griglia: ogni riquadro che entra con un'animazione sta
su un piano suo, e quelli dopo nella pagina coprivano la barra. Ora la barra ha
un piano più alto (stile.css, .barra).

Le tendine, la ricerca rapida, le notifiche e i tasti rapidi si cercano per ruolo e nome, come un lettore di
schermo, con gli aiuti di aiuti_browser.py (tappa 1 della base); il controllo di cosa c'è sopra resta quello
visivo (elementFromPoint), sui pezzi trovati così."""
import os
import sys
from datetime import date, timedelta
from urllib.parse import urlparse

from playwright.sync_api import Error as ErrorePlaywright, sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aiuti_browser import (GRUPPI, apri_comandi, apri_gruppo, cerca_rapido, linguette, menu,  # noqa: E402
                           prepara_domande)

from aiuti_browser import indirizzo_di_prova  # noqa: E402
B = indirizzo_di_prova(sys.argv)   # mai la porta 5000, quella del programma vero
esiti = []
oggi = date.today()
mar = oggi - timedelta(days=(oggi.weekday() - 1) % 7)       # i giorni dei dati di prova (strumenti/demo.py)
GIORNI = [('oggi', oggi), ('domani', oggi + timedelta(days=1)), ('con la sala operatoria', mar),
          ('con la nota del giorno', mar + timedelta(days=2)), ('chiuso (vigilia di Natale)', date(oggi.year, 12, 24)),
          ('festivo (8 dicembre)', date(oggi.year, 12, 8))]
# GRUPPI (aiuti_browser): le voci del menu con una tendina, per nome; dalla tappa 2 solo Aiuto
STAMPA = 'Stampa e scarica'                             # la tendina dei comandi della griglia

VISIBILI = r"""(trovate) => {
  const voci = trovate.filter(e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden');
  const male = [];
  const nome = (e) => (e.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 32);
  const chi = (t) => t ? t.tagName.toLowerCase() + (t.className && typeof t.className === 'string' ? '.' + t.className.trim().split(/\s+/)[0] : '')
    + ((t.closest('[class]') && t.closest('[class]') !== t) ? ' dentro .' + String(t.closest('[class]').className).trim().split(/\s+/)[0] : '') : 'niente';
  for (const e of voci) {
    e.scrollIntoView({block: 'nearest', inline: 'nearest'});
    const r = e.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) { continue; }
    if (r.left < -1 || r.right > innerWidth + 1 || r.top < -1 || r.bottom > innerHeight + 1) { male.push(nome(e) + ': fuori dallo schermo'); continue; }
    const y = r.top + r.height / 2;
    for (const x of [r.left + 5, r.left + r.width / 2, r.right - 5]) {
      const t = document.elementFromPoint(x, y);
      if (!(t && (t === e || e.contains(t)))) { male.push(nome(e) + ': sopra c\'è ' + chi(t)); break; }
    }
  }
  return {n: voci.length, male: male};
}"""


# menu, barra e linguette non coprono niente della pagina (dentro <main>), e niente copre le loro voci: per ogni pezzo
# che si vede nella finestra, il punto al centro e quello a 5 pixel dal bordo sinistro. Le notifiche (la campanella di
# oggi, in basso a destra, si chiudono) e i messaggi non sono qui: sono riquadri che stanno sopra la pagina apposta
CORNICE_COPRE = r"""() => {
  const cornice = [...document.querySelectorAll('[data-cornice="menu"], [data-cornice="barra"], [data-cornice="linguette"]')];
  const della = (t) => cornice.find(c => c.contains(t));
  const nome = (e) => e.tagName.toLowerCase() + ' «' + (e.textContent || e.value || '').trim().replace(/\s+/g, ' ').slice(0, 24) + '»';
  const male = [];
  const punti = (r) => [[r.left + Math.min(5, r.width / 2), r.top + r.height / 2], [r.left + r.width / 2, r.top + r.height / 2]]
    .filter(([x, y]) => x >= 0 && y >= 0 && x < innerWidth && y < innerHeight);
  let pagina = 0, voci = 0;
  for (const e of document.querySelectorAll('main a, main button, main input:not([type=hidden]), main select, main textarea, ' +
                                            'main h1, main h2, main th, main td, main label, main li, [data-prova-sotto-al-menu]')) {
    const r = e.getBoundingClientRect();
    if (r.width < 4 || r.height < 4 || getComputedStyle(e).visibility === 'hidden') { continue; }
    if (r.bottom <= 0 || r.top >= innerHeight || r.right <= 0 || r.left >= innerWidth) { continue; }
    pagina += 1;
    for (const [x, y] of punti(r)) {
      const t = document.elementFromPoint(x, y);
      if (t && della(t) && !e.contains(t)) { male.push(nome(e) + ' sotto ' + della(t).getAttribute('data-cornice')); break; }
    }
  }
  for (const c of cornice) {
    for (const e of c.querySelectorAll('a, button, input')) {
      const r = e.getBoundingClientRect();
      if (r.width < 4 || r.height < 4 || r.bottom <= 0 || r.top >= innerHeight || r.right <= 0 || r.left >= innerWidth) { continue; }
      if (e.closest('.v-menu-scorre') && (r.top < e.closest('.v-menu-scorre').getBoundingClientRect().top - 1 ||
          r.bottom > e.closest('.v-menu-scorre').getBoundingClientRect().bottom + 1)) { continue; }   // la parte del menu che scorre
      voci += 1;
      for (const [x, y] of punti(r)) {
        const t = document.elementFromPoint(x, y);
        if (!(t && (t === e || e.contains(t)))) { male.push(c.getAttribute('data-cornice') + ' ' + nome(e) + ': sopra c\'è ' + (t ? nome(t) : 'niente')); break; }
      }
    }
  }
  return {pagina: pagina, voci: voci, male: male};
}"""


def guarda_la_cornice(pg, dove):
    """Menu, barra e linguette non coprono la pagina e non sono coperti: in cima e con la pagina scorsa in fondo."""
    for posto, y in (('in cima', 0), ('in fondo', 100000)):
        pg.evaluate('(y) => window.scrollTo(0, y)', y)
        pg.wait_for_timeout(150)
        r = pg.evaluate(CORNICE_COPRE)
        ok('%s, %s: menu, barra e linguette non coprono niente (%d pezzi della pagina, %d voci)' % (dove, posto, r['pagina'], r['voci']),
           r['voci'] >= 10 and not r['male'], r['male'][:4] or r)
    pg.evaluate('window.scrollTo(0, 0)')


def zona_notifiche(pg):
    """La zona delle notifiche in alto a destra (role="region", nome Notifiche, in _menu.html)."""
    return pg.get_by_role('region', name='Notifiche', exact=True)


def fine_animazioni(pg):
    """Le notifiche dell'animata entrano scorrendo da destra, una dopo l'altra: si aspetta che siano ferme le
    animazioni delle notifiche, i riquadri che stanno nella zona. Non quelle dei pezzi dentro: la barretta del
    tempo che resta scorre per 15 secondi."""
    pg.wait_for_function("(zona) => document.getAnimations().every(a => a.playState !== 'running' || !(a.effect && "
                         "a.effect.target && a.effect.target.parentElement === zona))",
                         arg=zona_notifiche(pg).element_handle(), timeout=8000)


def ok(nome, condizione, dettaglio=''):
    esiti.append(bool(condizione))
    print(('OK ' if condizione else 'KO ') + nome, '' if condizione else dettaglio)


def controlla(pg, voci, nome):
    """voci: un Locator (le voci di una tendina, i risultati, le righe); None se la tendina non si è aperta (la
    prova è già caduta in apri)."""
    if voci is None:
        return
    r = voci.evaluate_all(VISIBILI)
    ok(nome + ' (%d voci)' % r['n'], r['n'] > 0 and not r['male'], r['male'][:4] or 'nessuna voce visibile')


def apri(pg, nome, dove):
    """Apre con un clic la tendina «Stampa e scarica» della pagina o un gruppo del menu (per nome) e torna le sue
    voci; se non si apre la prova cade qui e la raccolta va avanti."""
    try:
        tendina = apri_comandi(pg, nome) if nome == STAMPA else apri_gruppo(pg, nome)
    except (AssertionError, ErrorePlaywright) as e:
        ok('%s: %s si apre' % (dove, nome), False, str(e)[:200])
        return None
    pg.wait_for_timeout(350)                 # nell'animata la tendina entra in .18 s
    return tendina.get_by_role('link')


def chiudi(pg):
    pg.keyboard.press('Escape')
    pg.mouse.move(3, 3)
    pg.wait_for_timeout(150)


def rapida(pg, testo, dove):
    """I risultati della ricerca rapida del menu per testo (cerca_rapido di aiuti_browser.py)."""
    try:
        risultati = cerca_rapido(pg, testo)
    except (AssertionError, ErrorePlaywright) as e:
        ok('%s: la ricerca rapida risponde' % dove, False, str(e)[:200])
        return None
    pg.wait_for_timeout(300)
    return risultati


def scrivi(pg, campo, testo, attesa):
    pg.click(campo)
    pg.fill(campo, '')
    pg.keyboard.type(testo, delay=40)
    pg.wait_for_selector(attesa, timeout=5000)
    pg.wait_for_timeout(300)


with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
    errori = []
    domande = []
    for larghezza, altezza in ((1366, 657), (1920, 969)):
        ctx = br.new_context(viewport={'width': larghezza, 'height': altezza})
        ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); "
                            "localStorage.setItem('guida-viste', '{\"*\":1}'); } catch (e) {}")
        pg = ctx.new_page()
        domande.append(prepara_domande(pg))       # ogni domanda del browser passa da qui: nessuna è attesa
        pg.on('pageerror', lambda e: errori.append(str(e)))
        dim = '%dx%d' % (larghezza, altezza)

        # ---------------------------------------------- la griglia del giorno
        for nome, g in GIORNI:
            pg.goto(B + '/giorno/%s?struttura=1' % g.isoformat())
            pg.wait_for_timeout(800)          # le animazioni d'entrata finite
            dove = '%s, giorno %s' % (dim, nome)
            controlla(pg, apri(pg, STAMPA, dove), '%s: Stampa e scarica' % dove)
            for gruppo in GRUPPI:
                controlla(pg, apri(pg, gruppo, dove), '%s: %s' % (dove, gruppo))
            chiudi(pg)
            if nome == 'oggi':
                # appena aperta la pagina, mentre le animazioni d'entrata sono ancora in corso. Le notifiche già
                # viste nella prima visita non tornerebbero per due ore (gestionale.js, vistaDaPoco): si dimenticano,
                # così tornano come in una sessione nuova, quante che siano nei dati di prova
                pg.evaluate("() => { try { sessionStorage.removeItem('notifiche-viste'); } catch (e) {} }")
                pg.goto(B + '/giorno/%s?struttura=1' % g.isoformat())
                controlla(pg, apri(pg, STAMPA, '%s, giorno appena aperto' % dim), '%s, giorno appena aperto: Stampa e scarica' % dim)
                chiudi(pg)
                # le notifiche arrivano 0,8 secondi dopo la pagina: si aspettano (prima si guardava subito e il
                # controllo non partiva quasi mai). I dati di prova ne hanno sempre (almeno «Aggiornamento
                # disponibile» e «Messaggi non partiti»): se non arrivano la prova cade, non si salta
                notifiche = zona_notifiche(pg).get_by_role('status')
                try:
                    notifiche.first.wait_for(timeout=5000)
                except ErrorePlaywright:
                    pass
                if notifiche.count():
                    fine_animazioni(pg)
                    # di ognuna il riquadro, il collegamento e il titolo: il titolo (<b>) non ha un ruolo e si
                    # prende dentro le notifiche trovate per ruolo, come lo prendeva la prova di prima
                    controlla(pg, notifiche.or_(notifiche.get_by_role('link')).or_(notifiche.locator('p, b, strong')),
                              '%s: notifiche' % dim)
                else:
                    ok('%s: notifiche (arrivano)' % dim, False, 'nessuna notifica in 5 secondi')
                pg.keyboard.press('?')
                pg.wait_for_timeout(300)
                controlla(pg, pg.get_by_role('dialog', name='Tasti rapidi', exact=True).get_by_role('row'), '%s: tasti rapidi' % dim)
                pg.keyboard.press('Escape')

        # ---------------------------------------------- tutte le pagine del menu e delle linguette
        if larghezza == 1366:
            pg.goto(B + '/giorno/%s?struttura=1' % oggi.isoformat())
            indirizzi = []

            def aggiungi(hrefs):
                for h in hrefs:
                    if h and not h.startswith('#') and urlparse(h).path not in [urlparse(x).path for x in indirizzi]:
                        indirizzi.append(h)
            voci = menu(pg).get_by_role('link', include_hidden=True).evaluate_all('as => as.map(a => a.getAttribute("href"))')
            aggiungi(voci)
            # le linguette di ogni voce: si raggiungono dalla pagina della voce
            for h in list(indirizzi):
                pg.goto(B + h if h.startswith('/') else h)
                if linguette(pg).count():
                    aggiungi(linguette(pg).get_by_role('link').evaluate_all('as => as.map(a => a.getAttribute("href"))'))
            dal_menu = list(indirizzi)
            for extra in ('/appuntamento?data=%s&struttura=1' % mar.isoformat(), '/pazienti/nuovo', '/attesa/nuova'):
                indirizzi.append(extra)
            for h in indirizzi:
                pg.goto(B + h if h.startswith('/') else h)
                pg.wait_for_timeout(600)
                dove = '%s, %s' % (dim, urlparse(h).path)
                for gruppo in GRUPPI:
                    controlla(pg, apri(pg, gruppo, dove), '%s: %s' % (dove, gruppo))
                chiudi(pg)
                guarda_la_cornice(pg, dove)
            ok('%s: pagine del menu e delle linguette provate (%d)' % (dim, len(dal_menu)), len(dal_menu) >= 28, dal_menu)
            # il gemello di CORNICE_COPRE: un riquadro della pagina messo apposta sotto il menu si vede
            pg.goto(B + '/pazienti')
            pg.evaluate("""() => { const d = document.createElement('div'); d.setAttribute('data-prova-sotto-al-menu', '');
                d.textContent = 'riquadro di prova'; d.style.cssText = 'position: fixed; left: 20px; top: 300px; width: 120px; height: 30px;';
                document.querySelector('main').appendChild(d); }""")
            r = pg.evaluate(CORNICE_COPRE)
            ok('gemello: un riquadro della pagina sotto il menu viene visto', any('riquadro di prova' in m for m in r['male']), r['male'])

        # ---------------------------------------------- ricerca rapida e suggerimenti
        for pagina in ('/giorno/%s?struttura=1' % mar.isoformat(), '/pazienti'):
            pg.goto(B + pagina)
            pg.wait_for_timeout(600)
            dove = '%s, %s' % (dim, pagina.split('?')[0])
            controlla(pg, rapida(pg, 'Sep', dove), '%s: risultati della ricerca rapida' % dove)
            chiudi(pg)
        # i suggerimenti sono il contenuto delle pagine (prenotazione, scheda, lista d'attesa), non la cornice:
        # restano con i loro selettori fino alla tappa della loro area
        pg.goto(B + '/appuntamento?data=%s&struttura=1' % mar.isoformat())
        pg.wait_for_timeout(600)
        scrivi(pg, '#cerca_paziente', 'Sep', '#suggerimenti button')
        controlla(pg, pg.locator('#suggerimenti button'), '%s, prenotazione: suggerimenti del paziente' % dim)
        chiudi(pg)
        scrivi(pg, '#luogo_nascita_testo', 'nap', '#suggerimenti-luogo button')
        controlla(pg, pg.locator('#suggerimenti-luogo button'), '%s, prenotazione: suggerimenti del luogo di nascita' % dim)
        chiudi(pg)
        pg.goto(B + '/pazienti/nuovo')
        pg.wait_for_timeout(600)
        scrivi(pg, '#luogo_nascita_testo', 'san gi', '#suggerimenti-luogo button')
        controlla(pg, pg.locator('#suggerimenti-luogo button'), '%s, scheda nuova: suggerimenti del luogo di nascita' % dim)
        chiudi(pg)
        pg.goto(B + '/attesa/nuova')
        pg.wait_for_timeout(600)
        scrivi(pg, '#cerca_paziente', 'Sep', '#suggerimenti button')
        controlla(pg, pg.locator('#suggerimenti button'), '%s, lista d\'attesa: suggerimenti del paziente' % dim)
        ctx.close()

    # ---------------------------------------------- la cornice a 1024 e 683 (menu a sole icone), tasti, stampa
    for larghezza, altezza in ((1024, 657), (683, 657)):
        ctx = br.new_context(viewport={'width': larghezza, 'height': altezza})
        ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); "
                            "localStorage.setItem('guida-viste', '{\"*\":1}'); } catch (e) {}")
        pg = ctx.new_page()
        domande.append(prepara_domande(pg))
        pg.on('pageerror', lambda e: errori.append(str(e)))
        dim = '%dx%d' % (larghezza, altezza)
        for h in dal_menu:
            pg.goto(B + h if h.startswith('/') else h)
            pg.wait_for_timeout(400)
            guarda_la_cornice(pg, '%s, %s' % (dim, urlparse(h).path))
        pg.goto(B + '/giorno/%s?struttura=1' % mar.isoformat())
        pg.wait_for_timeout(400)
        controlla(pg, apri(pg, 'Aiuto', '%s, giorno' % dim), '%s, giorno: Aiuto' % dim)
        chiudi(pg)
        ctx.close()

    ctx = br.new_context(viewport={'width': 1366, 'height': 657})
    ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); "
                        "localStorage.setItem('guida-viste', '{\"*\":1}'); } catch (e) {}")
    pg = ctx.new_page()
    domande.append(prepara_domande(pg))
    pg.on('pageerror', lambda e: errori.append(str(e)))
    # i tasti G, E, C e D (gestionale.js clicca il primo [data-tasto]): dalla settimana della seconda struttura, in un
    # giorno che non è oggi, portano alla pagina giusta con struttura e giorno
    altro = oggi + timedelta(days=9)
    partenza = B + '/settimana/%s?struttura=2' % altro.isoformat()
    for tasto, atteso in (('g', '/giorno/%s?struttura=2' % altro.isoformat()),
                          ('e', '/giorno/%s/elenco?struttura=2' % altro.isoformat()),
                          ('c', '/conferme?struttura=2'), ('d', '/dove-si-fa/?struttura=2')):
        pg.goto(partenza)
        pg.wait_for_timeout(300)
        pg.mouse.click(900, 600)                    # il fuoco nella pagina, fuori dai campi
        try:
            with pg.expect_navigation(timeout=5000):
                pg.keyboard.press(tasto)
        except ErrorePlaywright:
            pass
        ok('tasto %s: %s' % (tasto.upper(), atteso), pg.url == B + atteso, pg.url)
    # in stampa la cornice sparisce e la pagina comincia dal bordo (le 8 pagine che si stampano le confronta in PDF
    # strumenti/confronta_rami.py)
    IN_STAMPA = """() => ({cornice: [...document.querySelectorAll('[data-cornice]')].filter(e => e.getClientRects().length)
                        .map(e => e.getAttribute('data-cornice')), sinistra: document.querySelector('main').getBoundingClientRect().left})"""
    for h in ('/mese/%s?struttura=1' % oggi.isoformat()[:7], '/cassa/%s?struttura=1' % oggi.isoformat(), '/conferme'):
        pg.goto(B + h)
        pg.emulate_media(media='print')
        r = pg.evaluate(IN_STAMPA)
        ok('in stampa la cornice sparisce: %s' % urlparse(h).path, not r['cornice'] and r['sinistra'] < 1, r)
        pg.emulate_media(media='screen')
    # il gemello: con il menu rimesso in stampa (una regola aggiunta nella pagina) il controllo lo vede
    pg.add_style_tag(content='@media print { [data-cornice="menu"] { display: flex !important; } }')
    pg.emulate_media(media='print')
    r = pg.evaluate(IN_STAMPA)
    ok('gemello: il menu rimesso in stampa si vede', r['cornice'] == ['menu'], r)
    pg.emulate_media(media='screen')
    pg.reload()
    pg.add_style_tag(content='@media print { main { margin-left: 248px !important; } }')    # il posto del menu lasciato
    pg.emulate_media(media='print')
    r = pg.evaluate(IN_STAMPA)
    ok('gemello: la pagina spostata a destra in stampa si vede', not r['cornice'] and r['sinistra'] >= 247, r)
    pg.emulate_media(media='screen')
    ctx.close()
    ok('nessun errore JavaScript', not errori, errori[:3])
    inattese = [x for d in domande for x in d.inattese]
    ok('nessuna domanda del browser inattesa', not inattese, inattese)
    br.close()
print('\n%d prove nel browser, %d superate' % (len(esiti), sum(esiti)))
sys.exit(0 if all(esiti) else 1)
