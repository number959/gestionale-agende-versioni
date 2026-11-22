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
from aiuti_browser import apri_comandi, apri_gruppo, cerca_rapido, menu, prepara_domande  # noqa: E402

from aiuti_browser import indirizzo_di_prova  # noqa: E402
B = indirizzo_di_prova(sys.argv)   # mai la porta 5000, quella del programma vero
esiti = []
oggi = date.today()
mar = oggi - timedelta(days=(oggi.weekday() - 1) % 7)       # i giorni dei dati di prova (strumenti/demo.py)
GIORNI = [('oggi', oggi), ('domani', oggi + timedelta(days=1)), ('con la sala operatoria', mar),
          ('con la nota del giorno', mar + timedelta(days=2)), ('chiuso (vigilia di Natale)', date(oggi.year, 12, 24)),
          ('festivo (8 dicembre)', date(oggi.year, 12, 8))]
GRUPPI = ('Segreteria', 'Aiuto', 'Configura')          # i gruppi del menu, per nome
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

        # ---------------------------------------------- tutte le pagine del menu
        if larghezza == 1366:
            pg.goto(B + '/giorno/%s?struttura=1' % oggi.isoformat())
            indirizzi = []
            for h in menu(pg).get_by_role('link', include_hidden=True).evaluate_all('as => as.map(a => a.getAttribute("href"))'):
                if h and not h.startswith('#') and urlparse(h).path not in [urlparse(x).path for x in indirizzi]:
                    indirizzi.append(h)
            for extra in ('/appuntamento?data=%s&struttura=1' % mar.isoformat(), '/pazienti/nuovo', '/attesa/nuova'):
                indirizzi.append(extra)
            for h in indirizzi:
                pg.goto(B + h if h.startswith('/') else h)
                pg.wait_for_timeout(600)
                dove = '%s, %s' % (dim, urlparse(h).path)
                for gruppo in GRUPPI:
                    controlla(pg, apri(pg, gruppo, dove), '%s: %s' % (dove, gruppo))
                chiudi(pg)
            ok('%s: pagine del menu provate (%d)' % (dim, len(indirizzi)), len(indirizzi) >= 15, indirizzi)

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
    ok('nessun errore JavaScript', not errori, errori[:3])
    inattese = [x for d in domande for x in d.inattese]
    ok('nessuna domanda del browser inattesa', not inattese, inattese)
    br.close()
print('\n%d prove nel browser, %d superate' % (len(esiti), sum(esiti)))
sys.exit(0 if all(esiti) else 1)
