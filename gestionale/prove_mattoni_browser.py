# -*- coding: utf-8 -*-
"""I mattoni della veste nuova nel browser (tappa 1-bis, 22/11/2026), sul catalogo dei pezzi.

Non usa il gestionale di prova che riceve (demo.py non ha il catalogo e dalla tappa 1 non cambia): avvia da sé il
catalogo (strumenti/catalogo_pezzi.py) su una porta libera di 127.0.0.1, con i suoi dati inventati.
- In chiaro e in scuro, campo, tendina, bottone, collegamento come bottone, collegamento e bottone principale nuovi
  prendono i colori dei gettoni (getComputedStyle contro strumenti/leggi_gettoni.py): senza lo strato «vecchio»,
  html.scuro a e html.scuro select di tema-scuro.css vincerebbero (il gemello toglie lo strato e lo vede).
- A 1366, 1024 e 683 px, in chiaro e in scuro: niente scorrimento di lato, nessun errore JavaScript.
- La tendina «Stampa e scarica» si apre con il clic (gestionale.js di oggi) e niente la copre, nemmeno la barra che
  viene dopo (il gemello toglie la regola che la porta sopra e la vede coperta).

    python prove_mattoni_browser.py [URL del gestionale di prova, non usato]
"""
import os
import re
import sys
import tempfile

from prove_dove import dove

CARTELLA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(CARTELLA, 'strumenti'))
sys.path.insert(0, CARTELLA)

from playwright.sync_api import sync_playwright  # noqa: E402
import catalogo_pezzi  # noqa: E402
from strumenti import leggi_gettoni as L  # noqa: E402

esiti = []


def prova(nome, f):
    try:
        esiti.append(('OK', nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', nome, '%s · %s' % (dove(e), str(e)[:900] or 'asserzione fallita')))
    except Exception as e:
        esiti.append(('ERRORE', nome, '%s · %r' % (dove(e), e)))


def cade(f, *argomenti):
    try:
        f(*argomenti)
    except AssertionError as e:
        return str(e) or 'caduta'
    raise AssertionError('il mutante passa: la prova non lo vede')


A = catalogo_pezzi.registra(catalogo_pezzi.prepara(tempfile.mkdtemp(prefix='prove-mattoni-browser-')))
SERVER, PORTA = catalogo_pezzi.avvia_in_un_filo(A)
INDIRIZZO = 'http://127.0.0.1:%d/catalogo-pezzi' % PORTA
PW = sync_playwright().start()
BROWSER = PW.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)

SENZA_STRATO = re.compile(r'<style>@layer vecchio;\n(@import url\("/static/[\w.-]+"\) layer\(vecchio\);\n?)+</style>')


def apri(tema, larghezza=1366, mutante=None):
    """La pagina del catalogo; mutante: 'strato' toglie lo strato (i fogli di oggi diventano normali <link>),
    'sopra' toglie da veste.css la regola che porta sopra la barra con la tendina aperta."""
    ctx = BROWSER.new_context(viewport={'width': larghezza, 'height': catalogo_pezzi.ALTEZZA}, reduced_motion='reduce')
    # un mutante che non si applica si segna qui e si dice dopo il caricamento (RuntimeError: la prova finisce in
    # ERRORE). Un assert dentro il gestore di route.fulfill arriverebbe solo a BROWSER.close() e fermerebbe tutta la
    # raccolta senza resoconto: succede proprio quando la regola che il mutante toglie manca già davvero
    non_applicati = []
    ctx.add_init_script("try { localStorage.setItem('gestionale-tema', '%s'); } catch (e) {}" % tema)
    if mutante == 'strato':
        def senza_strato(route):
            r = route.fetch()
            corpo = r.text()
            nuovo = SENZA_STRATO.sub(lambda m: ''.join('<link rel="stylesheet" href="/static/%s">' % f for f in
                                                       re.findall(r'/static/([\w.-]+)', m.group(0))), corpo)
            nuovo = nuovo.replace('<style>@layer vecchio { :root {', '<style>:root {').replace('} }</style>', '}</style>', 1)
            if nuovo == corpo:
                non_applicati.append('strato')
            route.fulfill(response=r, body=nuovo)
        ctx.route(re.compile(r'.*/catalogo-pezzi(\?.*)?$'), senza_strato)
    if mutante == 'margini':
        def senza_margini(route):
            r = route.fetch()
            corpo = r.text()
            nuovo = corpo.replace('  margin: 0;                         /* anche quando la barra è il modulo di oggi', '  /* ')
            if nuovo == corpo:
                non_applicati.append('margini')
            route.fulfill(response=r, body=nuovo)
        ctx.route(re.compile(r'.*/static/veste\.css$'), senza_margini)
    if mutante == 'sopra':
        def senza_sopra(route):
            r = route.fetch()
            corpo = r.text()
            nuovo = corpo.replace('.v-barra-comandi:is(:hover, :focus-within), .v-barra-comandi:has(.aperto) { z-index: 41; }', '')
            if nuovo == corpo:
                non_applicati.append('sopra (la regola che porta sopra la barra aperta)')
            route.fulfill(response=r, body=nuovo)
        ctx.route(re.compile(r'.*/static/veste\.css$'), senza_sopra)
    p = ctx.new_page()
    p.errori = []
    p.on('pageerror', lambda e: p.errori.append(str(e)))
    p.on('console', lambda m: p.errori.append(m.text) if m.type == 'error' else None)
    p.goto(INDIRIZZO, wait_until='load')
    p.evaluate('document.fonts.ready')
    if non_applicati:
        ctx.close()
        raise RuntimeError('il mutante non si applica: %s' % ', '.join(non_applicati))
    return ctx, p


def rgb(esa):
    return 'rgb(%d, %d, %d)' % tuple(int(esa[i:i + 2], 16) for i in (1, 3, 5))


def come_rgb(calcolato):
    """Il colore calcolato dal browser scritto come rgb(): i colori di color-mix() arrivano come color(srgb r g b)."""
    m = re.fullmatch(r'color\(srgb ([\d.]+) ([\d.]+) ([\d.]+)\)', calcolato)
    return 'rgb(%d, %d, %d)' % tuple(round(float(x) * 255) for x in m.groups()) if m else calcolato


# il pezzo, la proprietà calcolata e il gettone che deve darla
COLORI_DEI_PEZZI = [
    ('.v-campo input#cat-cognome', 'background-color', 'v-superficie'),
    ('.v-campo input#cat-cognome', 'color', 'v-testo'),
    ('.v-campo input#cat-cognome', 'border-top-color', 'v-riga-campo'),
    ('.v-tendina select', 'background-color', 'v-superficie'),
    ('.v-tendina select', 'color', 'v-testo'),
    ('button.v-bottone:not(.v-principale):not(.v-pericolo):not([disabled])', 'background-color', 'v-superficie'),
    ('button.v-bottone:not(.v-principale):not(.v-pericolo):not([disabled])', 'color', 'v-testo'),
    ('.cat-fila a.v-bottone', 'color', 'v-testo'),
    ('.cat-fila button.v-principale', 'background-color', 'v-primario'),
    ('.cat-fila button.v-principale', 'color', 'v-testo-su-pieno'),
    ('.v-intestazione .v-sotto a', 'color', 'v-collegamento'),
    ('.v-linguetta[aria-current]', 'color', 'v-primario-testo'),
    ('.v-linguetta[aria-current]', 'background-color', 'v-primario-tinta'),
    ('.v-pagina', 'background-color', 'v-fondo'),
]


def controlla_colori(tema, mutante=None):
    ctx, p = apri(tema, mutante=mutante)
    try:
        colore = p.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--primario').trim()")
        valori = L.Valori(colore, tema)
        male = []
        for sel, prop, gettone in COLORI_DEI_PEZZI:
            atteso = rgb(valori.risolvi(gettone))
            visto = p.evaluate('([s, k]) => getComputedStyle(document.querySelector(s))[k.replace(/-(.)/g, (_, c) => c.toUpperCase())]',
                               [sel, prop])
            visto = come_rgb(visto)
            if visto != atteso:
                male.append('%s %s: %s, il gettone --%s è %s' % (sel, prop, visto, gettone, atteso))
        scuro = p.evaluate("document.documentElement.classList.contains('scuro')")
        assert scuro == (tema == 'scuro'), 'il tema non è quello chiesto'
        assert not male, '%s: %s' % (tema, male)
        assert not p.errori, p.errori
        return len(COLORI_DEI_PEZZI)
    finally:
        ctx.close()


def b_colori():
    return '%d colori in chiaro, %d in scuro' % (controlla_colori('chiaro'), controlla_colori('scuro'))


def gemello_colori():
    messaggio = cade(controlla_colori, 'scuro', 'strato')
    assert 'a.v-bottone color' in messaggio or 'select background-color' in messaggio, messaggio


# i pezzi che tengono una classe di oggi (per JavaScript, animata e prove): stile.css darebbe loro i suoi margini
MARGINI = [('table.v-tabella.elenco', 'margin-bottom'), ('p.v-vuoto.vuoto', 'margin-bottom'),
           ('form.ricerca.v-barra-comandi', 'margin-bottom'), ('ul.v-striscia.numeri', 'margin-bottom'),
           ('ul.v-striscia.numeri .v-striscia-numero', 'margin-right')]


def controlla_margini(mutante=None):
    ctx, p = apri('chiaro', mutante=mutante)
    try:
        male = []
        for sel, prop in MARGINI:
            assert p.locator(sel).count(), 'nel catalogo non c\'è %s' % sel
            visto = p.evaluate('([s, k]) => getComputedStyle(document.querySelector(s)).getPropertyValue(k)', [sel, prop])
            if visto != '0px':
                male.append('%s %s: %s' % (sel, prop, visto))
        assert not male, 'margini delle classi di oggi non azzerati: %s' % male
        return len(MARGINI)
    finally:
        ctx.close()


def b_margini():
    return '%d pezzi' % controlla_margini()


def gemello_margini():
    assert 'form.ricerca' in cade(controlla_margini, 'margini')


def b_larghezze():
    righe = []
    for tema in ('chiaro', 'scuro'):
        for larghezza in catalogo_pezzi.LARGHEZZE:
            ctx, p = apri(tema, larghezza)
            try:
                m = p.evaluate('({pagina: document.documentElement.scrollWidth, finestra: window.innerWidth})')
                assert m['pagina'] <= m['finestra'], '%s %d: la pagina scorre di lato (%d px)' % (tema, larghezza, m['pagina'])
                assert not p.errori, '%s %d: %s' % (tema, larghezza, p.errori)
                righe.append(str(larghezza))
            finally:
                ctx.close()
    return '1366, 1024 e 683 px, in chiaro e in scuro'


def controlla_tendina(tema, mutante=None):
    ctx, p = apri(tema, mutante=mutante)
    try:
        gruppo = p.locator('.v-barra-comandi .v-stampa').first
        gruppo.locator('.apri-gruppo').click()
        p.wait_for_timeout(150)
        voci = gruppo.locator('.tendina a')
        assert gruppo.locator('.tendina').is_visible(), 'la tendina non si apre'
        assert gruppo.locator('.apri-gruppo').get_attribute('aria-expanded') == 'true', 'aria-expanded non cambia'
        coperte = []
        for i in range(voci.count()):
            box = voci.nth(i).bounding_box()
            sopra = p.evaluate('([x, y, s]) => { const e = document.elementFromPoint(x, y); return !!e && !!e.closest(s); }',
                               [box['x'] + box['width'] / 2, box['y'] + box['height'] / 2, '.v-stampa .tendina'])
            if not sopra:
                coperte.append(voci.nth(i).inner_text().split('\n')[0])
        assert not coperte, 'voci della tendina coperte: %s' % coperte
        return voci.count()
    finally:
        ctx.close()


def b_tendina():
    return '%d voci in chiaro, %d in scuro, nessuna coperta' % (controlla_tendina('chiaro'), controlla_tendina('scuro'))


def gemello_tendina():
    assert 'coperte' in cade(controlla_tendina, 'chiaro', 'sopra')


prova('in chiaro e in scuro campo, tendina, bottoni e collegamenti nuovi prendono i colori dei gettoni', b_colori)
prova('gemello: senza lo strato, in scuro i fogli di oggi vincono sui pezzi nuovi', gemello_colori)
prova('i pezzi che tengono una classe di oggi (elenco, vuoto, ricerca, numeri) non ne prendono i margini', b_margini)
prova('gemello: senza il margine zero della barra, form.ricerca riprende i suoi 18 px', gemello_margini)
prova('niente scorrimento di lato né errori JavaScript a 1366, 1024 e 683 px, in chiaro e in scuro', b_larghezze)
prova('«Stampa e scarica» si apre con il clic e niente la copre, nemmeno la barra dopo', b_tendina)
prova('gemello: senza la regola che porta sopra la barra aperta, la barra dopo copre la tendina', gemello_tendina)

BROWSER.close()
PW.stop()
SERVER.close()
for esito, nome, dettaglio in esiti:
    print('%-6s %s %s' % (esito, nome, dettaglio))
rotte = [e for e in esiti if e[0] != 'OK']
print('%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(rotte), len(rotte)))
sys.exit(1 if rotte else 0)
