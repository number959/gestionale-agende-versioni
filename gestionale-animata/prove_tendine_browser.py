"""Prove nel browser: le tendine e i riquadri che si aprono sopra la pagina si
vedono per intero, senza niente sopra (nota del giorno, avvisi, griglia) e
senza pezzi tagliati, su un gestionale avviato con i dati di prova (vedi
LEGGIMI, «Prove»):
    python prove_tendine_browser.py http://127.0.0.1:5001
- i gruppi del menu (Segreteria, Aiuto, Configura) su tutte le pagine del menu;
- «Stampa e scarica» nella griglia, nei giorni con la nota del giorno, la sala
  operatoria, gli appunti da confermare, la chiusura della struttura, un festivo;
- i risultati della ricerca rapida (Cerca);
- i suggerimenti del paziente e del luogo di nascita nella prenotazione, nella
  scheda del paziente e nella lista d'attesa;
- il riquadro dei tasti rapidi e le notifiche.
Per ogni voce il punto al centro e quelli ai due lati devono essere proprio
della voce (document.elementFromPoint): se un altro riquadro ci sta sopra, o la
voce esce dallo schermo, la prova lo dice. A 1366x657 (lo schermo della
segreteria con le barre del browser) e a 1920x969. Non salva niente.

Nella versione animata la tendina «Stampa e scarica» finiva sotto la nota del
giorno, gli avvisi e la griglia: ogni riquadro che entra con un'animazione sta
su un piano suo, e quelli dopo nella pagina coprivano la barra. Ora la barra ha
un piano più alto (stile.css, .barra)."""
import os
import sys
from datetime import date, timedelta
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

B = (sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5000').rstrip('/')
esiti = []
oggi = date.today()
mar = oggi - timedelta(days=(oggi.weekday() - 1) % 7)       # i giorni dei dati di prova (strumenti/demo.py)
GIORNI = [('oggi', oggi), ('domani', oggi + timedelta(days=1)), ('con la sala operatoria', mar),
          ('con la nota del giorno', mar + timedelta(days=2)), ('chiuso (vigilia di Natale)', date(oggi.year, 12, 24)),
          ('festivo (8 dicembre)', date(oggi.year, 12, 8))]
GRUPPI = ('menu-segreteria', 'menu-aiuto', 'menu-configura')

VISIBILI = r"""(sel) => {
  const voci = [...document.querySelectorAll(sel)].filter(e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden');
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


def fine_animazioni(pg):
    """Le notifiche dell'animata entrano scorrendo da destra, una dopo l'altra."""
    pg.wait_for_function("() => document.getAnimations().every(a => a.playState !== 'running' || !(a.effect && "
                         "a.effect.target && a.effect.target.classList && a.effect.target.classList.contains('notifica')))",
                         timeout=8000)


def ok(nome, condizione, dettaglio=''):
    esiti.append(bool(condizione))
    print(('OK ' if condizione else 'KO ') + nome, '' if condizione else dettaglio)


def controlla(pg, selettore, nome):
    r = pg.evaluate(VISIBILI, selettore)
    ok(nome + ' (%d voci)' % r['n'], r['n'] > 0 and not r['male'], r['male'][:4] or 'nessuna voce visibile')


def apri_gruppo(pg, gruppo):
    pg.click('[data-guida="%s"] .apri-gruppo' % gruppo)
    pg.wait_for_timeout(350)                 # nell'animata la tendina entra in .18 s


def chiudi(pg):
    pg.keyboard.press('Escape')
    pg.mouse.move(3, 3)
    pg.wait_for_timeout(150)


def scrivi(pg, campo, testo, attesa):
    pg.click(campo)
    pg.fill(campo, '')
    pg.keyboard.type(testo, delay=40)
    pg.wait_for_selector(attesa, timeout=5000)
    pg.wait_for_timeout(300)


with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
    errori = []
    for larghezza, altezza in ((1366, 657), (1920, 969)):
        ctx = br.new_context(viewport={'width': larghezza, 'height': altezza})
        ctx.add_init_script("try { localStorage.setItem('guida-benvenuto','1'); "
                            "localStorage.setItem('guida-viste', '{\"*\":1}'); } catch (e) {}")
        pg = ctx.new_page()
        pg.on('pageerror', lambda e: errori.append(str(e)))
        dim = '%dx%d' % (larghezza, altezza)

        # ---------------------------------------------- la griglia del giorno
        for nome, g in GIORNI:
            pg.goto(B + '/giorno/%s?struttura=1' % g.isoformat())
            pg.wait_for_timeout(800)          # le animazioni d'entrata finite
            apri_gruppo(pg, 'giorno-stampa')
            controlla(pg, '[data-guida="giorno-stampa"] .tendina a', '%s, giorno %s: Stampa e scarica' % (dim, nome))
            for gruppo in GRUPPI:
                apri_gruppo(pg, gruppo)
                controlla(pg, '[data-guida="%s"] .tendina a' % gruppo, '%s, giorno %s: %s' % (dim, nome, gruppo))
            chiudi(pg)
            if nome == 'oggi':
                # appena aperta la pagina, mentre le animazioni d'entrata sono ancora in corso
                pg.goto(B + '/giorno/%s?struttura=1' % g.isoformat())
                pg.wait_for_selector('[data-guida="giorno-stampa"] .apri-gruppo')
                apri_gruppo(pg, 'giorno-stampa')
                controlla(pg, '[data-guida="giorno-stampa"] .tendina a', '%s, giorno appena aperto: Stampa e scarica' % dim)
                chiudi(pg)
                if pg.locator('.notifiche .notifica').count():
                    fine_animazioni(pg)
                    controlla(pg, '.notifiche .notifica p, .notifiche .notifica b, .notifiche .notifica strong',
                              '%s: notifiche' % dim)
                pg.keyboard.press('?')
                pg.wait_for_timeout(300)
                controlla(pg, '#aiuto-tasti tr', '%s: tasti rapidi' % dim)
                pg.keyboard.press('Escape')

        # ---------------------------------------------- tutte le pagine del menu
        if larghezza == 1366:
            pg.goto(B + '/giorno/%s?struttura=1' % oggi.isoformat())
            indirizzi = []
            for h in pg.eval_on_selector_all('.menu a[href]', 'as => as.map(a => a.getAttribute("href"))'):
                if h and not h.startswith('#') and urlparse(h).path not in [urlparse(x).path for x in indirizzi]:
                    indirizzi.append(h)
            for extra in ('/appuntamento?data=%s&struttura=1' % mar.isoformat(), '/pazienti/nuovo', '/attesa/nuova'):
                indirizzi.append(extra)
            for h in indirizzi:
                pg.goto(B + h if h.startswith('/') else h)
                pg.wait_for_timeout(600)
                for gruppo in GRUPPI:
                    apri_gruppo(pg, gruppo)
                    controlla(pg, '[data-guida="%s"] .tendina a' % gruppo, '%s, %s: %s' % (dim, urlparse(h).path, gruppo))
                chiudi(pg)
            ok('%s: pagine del menu provate (%d)' % (dim, len(indirizzi)), len(indirizzi) >= 15, indirizzi)

        # ---------------------------------------------- ricerca rapida e suggerimenti
        for pagina in ('/giorno/%s?struttura=1' % mar.isoformat(), '/pazienti'):
            pg.goto(B + pagina)
            pg.wait_for_timeout(600)
            scrivi(pg, '#ricerca-rapida', 'Sep', '#risultati-rapidi a.voce-rapida')
            controlla(pg, '#risultati-rapidi a.voce-rapida', '%s, %s: risultati della ricerca rapida' % (dim, pagina.split('?')[0]))
            chiudi(pg)
        pg.goto(B + '/appuntamento?data=%s&struttura=1' % mar.isoformat())
        pg.wait_for_timeout(600)
        scrivi(pg, '#cerca_paziente', 'Sep', '#suggerimenti button')
        controlla(pg, '#suggerimenti button', '%s, prenotazione: suggerimenti del paziente' % dim)
        chiudi(pg)
        scrivi(pg, '#luogo_nascita_testo', 'nap', '#suggerimenti-luogo button')
        controlla(pg, '#suggerimenti-luogo button', '%s, prenotazione: suggerimenti del luogo di nascita' % dim)
        chiudi(pg)
        pg.goto(B + '/pazienti/nuovo')
        pg.wait_for_timeout(600)
        scrivi(pg, '#luogo_nascita_testo', 'san gi', '#suggerimenti-luogo button')
        controlla(pg, '#suggerimenti-luogo button', '%s, scheda nuova: suggerimenti del luogo di nascita' % dim)
        chiudi(pg)
        pg.goto(B + '/attesa/nuova')
        pg.wait_for_timeout(600)
        scrivi(pg, '#cerca_paziente', 'Sep', '#suggerimenti button')
        controlla(pg, '#suggerimenti button', '%s, lista d\'attesa: suggerimenti del paziente' % dim)
        ctx.close()
    ok('nessun errore JavaScript', not errori, errori[:3])
    br.close()
print('\n%d prove nel browser, %d superate' % (len(esiti), sum(esiti)))
sys.exit(0 if all(esiti) else 1)
