# -*- coding: utf-8 -*-
"""Prove nel browser della cornice nuova (tappa 2 della base, 22/11/2026): menu a sinistra, barra in alto,
linguette. Su un gestionale di prova avviato con i dati di prova (vedi LEGGIMI, «Prove»):

    python strumenti/demo.py --porta 5001        # in un'altra finestra
    python prove_cornice_browser.py http://127.0.0.1:5001

Non salva niente. Le pagine sono tutte quelle senza parametri di indirizzi.txt che rispondono con una pagina intera
(i pezzi chiesti dalle pagine, i JSON e gli Excel si saltano, e si contano).
1. Ogni pagina, a 1366x657 (lo schermo della segreteria con le barre del browser):
   - si apre con la cornice nuova (menu largo 248 px a sinistra, alto quanto la finestra; la barra in alto, alta 62
     px, con la ricerca; la pagina accanto e sotto), senza errori JavaScript e senza errori nella console; solo i
     fogli da stampare restano senza cornice (SENZA_CORNICE);
   - accende una voce sola del menu e, se ha le linguette, una linguetta sola (aria-current); e le linguette ci sono
     in tutte le pagine di una voce che le ha;
   - in stampa (il media «print») la cornice non si vede e la pagina comincia dal bordo, larga quanto il foglio;
   - il menu sta nella finestra e scorre per conto suo: scorrendo la parte delle voci la pagina non si muove, l'ultima
     voce si raggiunge, Aiuto e Configura restano in fondo; scorrendo la pagina il menu resta fermo; niente della
     cornice esce dal bordo destro e la pagina non viene spinta di lato (una pagina può scorrere di lato per il suo
     contenuto: lo dice, ma non è la cornice).
2. Ogni pagina si raggiunge con soli clic partendo dalla home: le pagine delle voci e delle linguette dal menu e dalle
   linguette (e quelle che stavano nel menu di prima, DAL_MENU, proprio da lì), le altre con un clic in più dentro
   una pagina raggiunta così. Dopo ogni clic su una voce o una linguetta, nella pagina nuova è accesa proprio quella.
3. I tasti G, E, C e D portano alla pagina giusta, con la struttura e il giorno della pagina da cui si parte, e lì
   accendono la voce e la linguetta giuste; dalla seconda struttura ogni voce e linguetta che porta la struttura la
   porta ancora.
4. Sotto 1200 px (1199, 1024 e 683) il menu è a sole icone: largo al più 80 px, il nome delle voci non si vede ma c'è
   per i lettori di schermo (si trovano per ruolo e nome) e nel title; al posto del logo le iniziali. A 1200 px il
   contrario (il gemello naturale).
5. Ogni pagina registra le domande del browser (prepara_domande): nessuna è attesa.
Ogni controllo ha il suo gemello, in fondo: lo stesso controllo, sulla pagina guastata apposta (un menu tolto, due
voci accese, il menu in stampa, il menu che non scorre o non resta fermo, un pezzo largo nel menu, un errore
JavaScript, una linguetta che porta altrove, il tasto G tolto, i nomi visibili nel menu stretto, una domanda), deve
trovare il guasto.

Menu, linguette, barra e ricerca si cercano per ruolo e nome con aiuti_browser.py; le misure (dove sta il menu, cosa
scorre, cosa esce dal bordo) si prendono sui contenitori data-cornice, come fa prove_tendine_browser.py."""
import json
import os
import re
import sys
from datetime import date, timedelta
from urllib.parse import parse_qsl, urlsplit

from playwright.sync_api import Error as ErrorePlaywright, sync_playwright

CARTELLA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CARTELLA)
from aiuti_browser import (apri_gruppo, barra_in_alto, indirizzo_di_prova, linguetta, linguetta_accesa, linguette,  # noqa: E402
                           menu, nome_voce, prepara_domande, principale, voce_accesa, voce_attiva, voce_del_menu,
                           zona_ricerca)

B = indirizzo_di_prova(sys.argv)   # mai la porta 5000, quella del programma vero
esiti = []
OGGI = date.today()
ALTRO = OGGI + timedelta(days=9)                     # un giorno che non è oggi (e nemmeno di questa settimana)
LARGO, ALTO = 1366, 657
MENU_LARGO, BARRA_ALTA = 248, 62                     # le misure delle tavole Nefro-*
# le pagine senza parametri che restano senza cornice: i fogli da stampare (prove_senza_menu.py ha il loro gemello)
SENZA_CORNICE = {'guida.stampa'}
# le pagine che nel menu di prima stavano nel menu o nelle sue tendine (prove_menu_principale.html, la copia ferma del
# menu del ramo principale): nella cornice nuova si raggiungono con un clic sul menu, o due (la voce e la linguetta).
# Una lista scritta qui, non presa da menu.py: se una voce o una linguetta porta altrove, la pagina manca
DAL_MENU = {
    'cruscotto.oggi', 'giorno', 'viste.settimana', 'viste.mese', 'viste.elenco_giorno', 'sala.giornata',
    'pazienti.elenco', 'personale.mese', 'ambulatori.settimana', 'ambulatori.mese', 'live.pagina',
    'ambulatori.riepilogo', 'esportazioni.pagina', 'dovesifa.pagina', 'viste.conferme', 'segreteria.da_confermare',
    'segreteria.chiusura', 'segreteria.cose_da_fare', 'segreteria.attesa', 'viste.disponibilita', 'cassa.cassa_giorno',
    'viste.statistiche', 'guida.indice', 'aggiornamenti.novita_pagina', 'anagrafiche.elenco', 'dovesifa.strutture',
    'invii.pagina', 'importa.carica', 'viste.impostazioni', 'aggiornamenti.pagina',
}
# la linguetta che porta in un'altra area (menu.py, fuori=True): nella pagina nuova accende la voce e la linguetta di lì
FUORI = {'Elenco del giorno': ('Agenda', 'Elenco')}
# le pagine che non si aprono con un clic: solo dopo un modulo che salva (qui non si salva niente)
SOLO_DOPO_UN_MODULO = {'segreteria.avvisa_spostati': '«Sposta gli appuntamenti» la apre dopo lo spostamento'}
# le voci e le linguette che non portano la struttura (come nel menu di prima: Pazienti, Configura e le sue pagine)
SENZA_STRUTTURA = {'Pazienti', 'Configura', 'Anagrafiche', 'Strutture del gruppo', 'Email e WhatsApp',
                   'Importa da Excel', 'Impostazioni', 'Aggiornamenti'}
PRIMA_VOLTA = ("try { localStorage.setItem('guida-benvenuto','1'); "
               "localStorage.setItem('guida-viste', '{\"*\":1}'); } catch (e) {}")


def ok(nome, condizione, dettaglio=''):
    esiti.append(bool(condizione))
    print(('OK ' if condizione else 'KO ') + nome, '' if condizione else dettaglio, flush=True)


def senza_numero(testo):
    """Il nome di una voce senza il contatore («Segreteria 3» → «Segreteria») e su una riga sola."""
    return re.sub(r'\s+\d+$', '', ' '.join((testo or '').split()))


# ---------------------------------------------------------------- le pagine e i loro indirizzi
def leggi_indirizzi():
    """(pagine senza parametri che rispondono 200 o con un rimando, regole per dire di quale funzione è un indirizzo)."""
    with open(os.path.join(CARTELLA, 'indirizzi.txt'), encoding='utf-8') as f:
        righe = [r.split('\t') for r in f.read().splitlines() if r and not r.startswith('#')]
    pagine = [r[1] for r in righe if len(r) == 4 and 'GET' in r[0].split(',') and re.match(r'^(200|30\d)', r[3])]
    regole = []
    for r in righe:
        if 'GET' not in r[0].split(','):
            continue
        pezzi = re.split(r'(<[^>]+>)', r[1])
        espr = ''.join(('\\d+' if p.startswith('<int:') else '.+' if p.startswith('<path:') else '[^/]+')
                       if p.startswith('<') else re.escape(p) for p in pezzi)
        fisso = sum(len(p) for p in pezzi if not p.startswith('<'))
        regole.append((re.compile('^' + espr + '$'), fisso, r[2]))
    return pagine, regole


PAGINE, REGOLE = leggi_indirizzi()


def funzione_di(href):
    """La funzione (endpoint) che risponde a un indirizzo, dalle regole di indirizzi.txt (la più precisa)."""
    percorso = urlsplit(href).path
    trovate = sorted(((fisso, ep) for espr, fisso, ep in REGOLE if espr.match(percorso)), reverse=True)
    return trovate[0][1] if trovate else None


# ---------------------------------------------------------------- i controlli (funzioni pure: le usano anche i gemelli)
MISURE = r"""() => {
  const r = (s) => { const e = document.querySelector(s); if (!e || !e.getClientRects().length) { return null; }
    const b = e.getBoundingClientRect(); return {l: b.left, r: b.right, t: b.top, b: b.bottom, w: b.width, h: b.height}; };
  return {menu: r('[data-cornice="menu"]'), barra: r('[data-cornice="barra"]'), linguette: r('[data-cornice="linguette"]'),
          main: r('main'), larghezza: innerWidth, altezza: innerHeight,
          cornici: [...document.querySelectorAll('[data-cornice]')].map(e => e.getAttribute('data-cornice'))};
}"""


def problemi_cornice(pg):
    """La cornice nuova c'è ed è al suo posto: menu (per ruolo, e il contenitore largo 248 px, a sinistra, alto quanto
    la finestra), barra in alto (per ruolo, alta 62 px, accanto al menu) con la ricerca, la pagina accanto e sotto."""
    p = []
    if menu(pg).count() != 1 or not menu(pg).is_visible():
        p.append('il menu (navigation «Pagine») non c\'è una volta sola')
    if barra_in_alto(pg).count() != 1 or not barra_in_alto(pg).is_visible():
        p.append('la barra in alto (banner) non c\'è')
    elif zona_ricerca(pg).get_by_role('searchbox').count() != 1:
        p.append('la ricerca rapida non è nella barra in alto')
    m = pg.evaluate(MISURE)
    me, ba, li, ma = m['menu'], m['barra'], m['linguette'], m['main']
    if not me or not ba or not ma:
        return p + ['manca un pezzo: %s' % m['cornici']]
    if abs(me['l']) > 1 or abs(me['t']) > 1 or abs(me['w'] - MENU_LARGO) > 0.5 or me['h'] < m['altezza'] - 1:
        p.append('il menu non è a sinistra, largo %d e alto quanto la finestra: %s' % (MENU_LARGO, me))
    if ba['l'] < me['r'] - 1 or abs(ba['t']) > 1 or abs(ba['h'] - BARRA_ALTA) > 2:
        p.append('la barra non è in alto accanto al menu, alta %d: %s' % (BARRA_ALTA, ba))
    sopra = li['b'] if li else ba['b']
    if li and li['t'] < ba['b'] - 1:
        p.append('le linguette sotto la barra: %s' % li)
    if ma['l'] < me['r'] - 1 or ma['t'] < sopra - 1 or ma['r'] > m['larghezza'] + 1:
        p.append('la pagina non sta accanto al menu e sotto la barra: %s' % ma)
    return p


def accese(pg):
    """(voci accese, linguette accese, problemi): una voce sola del menu (aria-current page, o true sul pulsante della
    tendina Aiuto) e, se la pagina ha le linguette, una linguetta sola (page); nessun altro aria-current nella cornice."""
    p = []
    n_voci = voce_attiva(pg).count()
    if n_voci != 1:
        p.append('%d voci accese nel menu: %s' % (n_voci, voce_accesa(pg)))
    if menu(pg).locator('[aria-current]').count() != n_voci:
        p.append('aria-current di un altro tipo nel menu')
    n_l = 0
    file = linguette(pg).count()
    if file > 1:
        p.append('%d file di linguette' % file)
    elif file == 1:
        n_l = linguette(pg).locator('[aria-current]').count()
        if n_l != 1 or linguette(pg).locator('[aria-current="page"]').count() != 1:
            p.append('%d linguette accese: %s' % (n_l, linguetta_accesa(pg)))
    if pg.locator('[data-cornice] [aria-current]').count() != n_voci + n_l:
        p.append('aria-current fuori dal menu e dalle linguette, nella cornice')
    return voce_accesa(pg), (linguetta_accesa(pg) if file else None), p


IN_STAMPA = r"""() => ({cornice: [...document.querySelectorAll('[data-cornice]')].filter(e => e.getClientRects().length &&
                       getComputedStyle(e).visibility !== 'hidden').map(e => e.getAttribute('data-cornice')),
                     main: (() => { const b = document.querySelector('main').getBoundingClientRect(); return [b.left, b.width]; })(),
                     larghezza: innerWidth})"""


def problemi_stampa(pg):
    """Con il media «print»: nessun contenitore della cornice si vede, la pagina comincia dal bordo ed è larga quanto il
    foglio (con il menu soltanto nascosto la colonna resterebbe vuota)."""
    pg.emulate_media(media='print')
    try:
        r = pg.evaluate(IN_STAMPA)
    finally:
        pg.emulate_media(media='screen')
    p = []
    if r['cornice']:
        p.append('in stampa si vede: %s' % r['cornice'])
    if r['main'][0] > 1 or r['main'][1] < r['larghezza'] - 2:
        p.append('in stampa la pagina non comincia dal bordo o non è larga quanto il foglio: %s' % r['main'])
    return p


IL_MENU = r"""() => {
  const lato = document.querySelector('[data-cornice="menu"]');
  const nav = lato && lato.querySelector('nav');
  const out = {problemi: [], note: []};
  if (!nav) { out.problemi.push('il menu non c\'è'); return out; }
  const nome = (e) => (e.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 24);
  const voci = [...nav.querySelectorAll('a, button')].filter(e => e.getClientRects().length && !e.closest('[role=menu]'));
  const finestra = (e) => { const a = e.getBoundingClientRect(); return a.top >= -1 && a.bottom <= innerHeight + 1 && a.left >= -1 && a.right <= innerWidth + 1; };
  const rl = lato.getBoundingClientRect();
  if (rl.top < -1 || rl.bottom > innerHeight + 1) { out.problemi.push('il menu non sta nella finestra: ' + Math.round(rl.top) + '-' + Math.round(rl.bottom)); }
  if (lato.scrollWidth > lato.clientWidth + 1) { out.problemi.push('il menu scorre di lato: ' + lato.scrollWidth + ' su ' + lato.clientWidth); }
  const scorrevoli = [...nav.querySelectorAll('*')].filter(e => ['auto', 'scroll'].includes(getComputedStyle(e).overflowY));
  if (scorrevoli.length !== 1) { out.problemi.push('parti del menu che scorrono per conto loro: ' + scorrevoli.length); return out; }
  const s = scorrevoli[0];
  const nella = voci.filter(v => s.contains(v)), fondo = voci.filter(v => !s.contains(v));
  out.voci = [nella.length, fondo.length];
  out.trabocca = s.scrollHeight > s.clientHeight + 1;
  if (s.scrollWidth > s.clientWidth + 1) { out.problemi.push('la parte delle voci scorre anche di lato'); }
  if (!nella.length || !fondo.length) { out.problemi.push('voci nella parte che scorre e in fondo: ' + out.voci); return out; }
  const y0 = scrollY, x0 = scrollX;
  const fuori = (lista) => lista.filter(v => !finestra(v)).map(nome);
  if (fuori(fondo).length) { out.problemi.push('in fondo non si vedono: ' + fuori(fondo)); }
  s.scrollTop = s.scrollHeight;
  if (out.trabocca) {
    const u = nella[nella.length - 1].getBoundingClientRect(), q = s.getBoundingClientRect();
    if (s.scrollTop <= 0) { out.problemi.push('la parte delle voci non scorre'); }
    if (u.top < q.top - 1 || u.bottom > q.bottom + 1 || !finestra(nella[nella.length - 1])) { out.problemi.push('l\'ultima voce non si raggiunge: ' + nome(nella[nella.length - 1])); }
  }
  if (scrollY !== y0 || scrollX !== x0) { out.problemi.push('scorrendo il menu la pagina si è mossa'); }
  if (fuori(fondo).length) { out.problemi.push('scorso il menu, in fondo non si vedono: ' + fuori(fondo)); }
  s.scrollTop = 0;
  out.alta = document.scrollingElement.scrollHeight > innerHeight + 40;
  if (out.alta) {
    window.scrollTo(0, 1e6);
    const r2 = lato.getBoundingClientRect();
    if (Math.abs(r2.top) > 1 || r2.bottom > innerHeight + 1 || !scrollY) { out.problemi.push('scorrendo la pagina il menu non resta fermo: ' + Math.round(r2.top)); }
    window.scrollTo(0, 0);
  }
  // di lato: niente della cornice esce dal bordo destro, e la pagina (main) non viene spinta oltre
  const cornice = [...document.querySelectorAll('[data-cornice="menu"], [data-cornice="barra"], [data-cornice="linguette"]')];
  const oltre = [...document.querySelectorAll('body *')].filter(e => { const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0 && b.right > innerWidth + 1; });
  const della = oltre.filter(e => cornice.some(c => c.contains(e)));
  if (della.length) { out.problemi.push('fuori dal bordo destro, nella cornice: ' + della.slice(0, 3).map(e => e.tagName.toLowerCase() + ' «' + nome(e) + '»')); }
  const m = document.querySelector('main').getBoundingClientRect();
  if (m.right > innerWidth + 1) { out.problemi.push('la pagina è spinta oltre il bordo destro: ' + Math.round(m.right)); }
  if (document.scrollingElement.scrollWidth > innerWidth) {
    const dentro = oltre.filter(e => e.closest('main') && e !== document.querySelector('main'));
    out.note.push('la pagina scorre di lato per il suo contenuto (' + document.scrollingElement.scrollWidth + ' px: ' +
                  dentro.slice(0, 1).map(e => e.tagName.toLowerCase() + (e.className ? '.' + String(e.className).split(' ')[0] : '')) + ')');
    if (!dentro.length) { out.problemi.push('la pagina scorre di lato, e non per il suo contenuto'); }
  }
  return out;
}"""


def problemi_menu_che_scorre(pg):
    r = pg.evaluate(IL_MENU)
    return r['problemi'], r


# nell'animata le pagine entrano muovendosi (per meno di un secondo): un pezzo spostato in giù allunga la pagina, e in
# fondo il menu fermo salirebbe di quei pixel. Le misure si prendono quando sono finite le animazioni della pagina
# (dentro <main>), tranne quelle che non finiscono mai; il numero che pulsa nel menu e le notifiche non spostano la
# pagina. Il modo stampa le fa ripartire: per questo la stampa si guarda per ultima
FERME = ("() => document.getAnimations().every(a => a.playState !== 'running' || "
         "!isFinite(a.effect.getComputedTiming().endTime) || !a.effect.target || !a.effect.target.closest('main'))")


def aspetta_animazioni(pg):
    try:
        pg.wait_for_function(FERME, timeout=4000)
    except ErrorePlaywright:
        pass


def errori_di(lista, dove):
    """Gli errori JavaScript e della console arrivati mentre si guardava una pagina (e svuota la lista)."""
    trovati = list(lista)
    del lista[:]
    return ['%s: %s' % (dove, e) for e in trovati]


# ---------------------------------------------------------------- 1. ogni pagina
def documenti(ctx):
    """(pagine intere, pezzi e altro saltati): una richiesta per indirizzo, seguendo i rimandi."""
    intere, saltate = [], []
    for u in PAGINE:
        r = ctx.request.get(B + u)
        corpo = r.text() if 'text/html' in r.headers.get('content-type', '') else ''
        if r.status == 200 and re.search(r'<html[\s>]', corpo[:600], re.I):
            intere.append(u)
        else:
            saltate.append('%s (%d, %s)' % (u, r.status, 'un pezzo di pagina' if corpo else
                                            r.headers.get('content-type', '').split(';')[0]))
    return intere, saltate


def guarda_le_pagine(pg, errori, pagine):
    """Il giro della parte 1. Torna {funzione: (indirizzo, voce accesa, linguetta accesa)} delle pagine con la cornice."""
    viste, trabocca, scorrono_di_lato, con_cornice = {}, 0, [], 0
    for u in pagine:
        pg.goto(B + u)
        pg.wait_for_timeout(200)
        aspetta_animazioni(pg)
        funzione = pg.evaluate('document.body.dataset.pagina')
        if funzione in SENZA_CORNICE:
            r = pg.evaluate(MISURE)
            ok('%s: un foglio da stampare, senza cornice' % u, not r['cornici'] and menu(pg).count() == 0, r['cornici'])
            e = errori_di(errori, u)
            ok('%s: nessun errore JavaScript' % u, not e, e[:3])
            continue
        con_cornice += 1
        p = problemi_cornice(pg)
        ok('%s (%s): si apre con la cornice nuova a %dx%d' % (u, funzione, LARGO, ALTO), not p, p)
        voce, lingua, p = accese(pg)
        ok('%s: una voce sola accesa (%s)%s' % (u, voce, ', una linguetta sola (%s)' % lingua if lingua else ''), not p, p)
        viste[funzione] = (u, voce, lingua)
        p, r = problemi_menu_che_scorre(pg)
        trabocca += 1 if r.get('trabocca') else 0
        if r.get('note'):
            scorrono_di_lato.append('%s: %s' % (u, r['note'][0]))
        ok('%s: il menu scorre per conto suo e non spinge la pagina di lato%s' % (u, ' (%s)' % r['note'][0] if r.get('note') else ''),
           not p, p)
        p = problemi_stampa(pg)
        ok('%s: in stampa la cornice non si vede' % u, not p, p)
        e = errori_di(errori, u)
        ok('%s: nessun errore JavaScript' % u, not e, e[:3])
    return viste, (trabocca, con_cornice), scorrono_di_lato


def senza_linguette(viste):
    """(voci che hanno le linguette, pagine di quelle voci che non le hanno)."""
    con = {v for _, v, l in viste.values() if l}
    return con, sorted('%s (%s)' % (u, v) for u, v, l in viste.values() if v in con and not l)


# ---------------------------------------------------------------- 2. si raggiungono con soli clic
def clicca(pg, link, attesa=10000):
    """Un clic su un collegamento come una persona; torna la pagina dove si arriva (una scheda nuova se si apre lì)."""
    pg.mouse.move(700, 500)
    if link.get_attribute('target') == '_blank':
        with pg.context.expect_page(timeout=attesa) as nuova:
            link.click()
        altra = nuova.value
        altra.wait_for_load_state()
        return altra
    with pg.expect_navigation(timeout=attesa):
        link.click()
    return pg


def ripeti(pg, passi):
    """Dalla home, solo clic: ('voce', nome), ('aiuto', nome), ('linguetta', nome), ('pagina', indirizzo)."""
    pg.goto(B + '/')
    for tipo, cosa in passi:
        if tipo == 'voce':
            pg = clicca(pg, voce_del_menu(pg, cosa))
        elif tipo == 'aiuto':
            pg = clicca(pg, voce_del_menu(pg, 'Aiuto', cosa))
        elif tipo == 'linguetta':
            pg = clicca(pg, linguetta(pg, cosa))
        else:
            link = principale(pg).locator('a[href=%s]' % json.dumps(cosa)).first
            pg = clicca(pg, link)
    pg.wait_for_timeout(150)
    return pg


def collegamenti_della_pagina(pg):
    """I collegamenti della pagina (dentro <main>, fuori dalla cornice) che si vedono: gli indirizzi interni."""
    return principale(pg).evaluate("""m => [...m.querySelectorAll('a[href]')].filter(a => a.getClientRects().length &&
        !a.closest('[data-cornice]')).map(a => a.getAttribute('href')).filter(h => h.startsWith('/'))""")


def dopo_il_clic(pg, voce, lingua):
    """Problemi della pagina dopo il clic su una voce (e una linguetta): sono accese proprio quelle."""
    voce_attesa, lingua_attesa = FUORI.get(lingua, (voce, lingua))
    v, l, p = accese(pg)
    if v != voce_attesa:
        p.append('accesa la voce %s invece di %s' % (v, voce_attesa))
    if lingua is not None and l != lingua_attesa:
        p.append('accesa la linguetta %s invece di %s' % (l, lingua_attesa))
    return p


def raggiungi(pg, viste):
    """Il giro della parte 2. Torna {funzione: passi}."""
    strade, pagine_note = {}, []                         # pagine_note: (passi, collegamenti della pagina)
    pg.goto(B + '/')
    voci = [senza_numero(t) for t in menu(pg).get_by_role('link').all_inner_texts()]
    pulsanti = [senza_numero(t) for t in menu(pg).get_by_role('button').all_inner_texts()]
    aiuto = []
    if 'Aiuto' in pulsanti:
        for a in apri_gruppo(pg, 'Aiuto').get_by_role('link').all():
            if (a.get_attribute('href') or '#') != '#':
                aiuto.append(' '.join(a.inner_text().split('\n')[0].split()))
    ok('dalla home: le voci del menu e quelle della tendina Aiuto che aprono una pagina (%d e %d)' % (len(voci), len(aiuto)),
       len(voci) >= 10 and len(aiuto) >= 2 and 'Aiuto' in pulsanti, (voci, pulsanti, aiuto))
    da_provare = [[('voce', v)] for v in voci] + [[('aiuto', a)] for a in aiuto]
    while da_provare:
        passi = da_provare.pop(0)
        nome = ' › '.join(c for _, c in passi)
        try:
            arrivo = ripeti(pg, passi)
        except (AssertionError, ErrorePlaywright) as e:
            ok('dalla home, %s: si apre' % nome, False, str(e)[:200])
            continue
        funzione = arrivo.evaluate('document.body.dataset.pagina')
        tipo, cosa = passi[-1]
        voce = 'Aiuto' if passi[0][0] == 'aiuto' else passi[0][1]
        p = dopo_il_clic(arrivo, voce, cosa if tipo == 'linguetta' else None)
        ok('dalla home, %s → %s, e lì è accesa' % (nome, funzione), funzione and not p, p)
        strade.setdefault(funzione, passi)
        pagine_note.append((passi, collegamenti_della_pagina(arrivo)))
        if len(passi) == 1 and tipo == 'voce' and linguette(arrivo).count() == 1:
            for t in linguette(arrivo).get_by_role('link').all_inner_texts():
                da_provare.append(passi + [('linguetta', senza_numero(t))])
    dirette = set(strade)
    mancano = sorted(DAL_MENU - dirette)
    ok('le %d pagine del menu di prima si raggiungono dal menu e dalle linguette' % len(DAL_MENU), not mancano, mancano)
    # le altre: un clic in più, dentro una pagina raggiunta così (fino a tre clic dentro le pagine)
    restano = [f for f in viste if f not in strade and f not in SOLO_DOPO_UN_MODULO]
    restano += [f for f in SENZA_CORNICE if f not in strade]
    for giro in range(3):
        nuove = []
        for f in list(restano):
            u = PERCORSI.get(f)
            candidati = [(passi, h) for passi, hrefs in pagine_note for h in hrefs if funzione_di(h) == f]
            candidati.sort(key=lambda c: (urlsplit(c[1]).path != u, len(c[0])))      # prima lo stesso indirizzo
            if not candidati:
                continue
            passi, h = candidati[0]
            try:
                arrivo = ripeti(pg, passi + [('pagina', h)])
                arrivata = arrivo.evaluate('document.body.dataset.pagina')
            except (AssertionError, ErrorePlaywright) as e:
                arrivata, arrivo = 'errore: %s' % str(e)[:120], None
            strada = ' › '.join(c for _, c in passi) + ' › ' + urlsplit(h).path
            ok('dalla home, %s → %s' % (strada, f), arrivata == f, arrivata)
            if arrivata == f:
                strade[f] = passi + [('pagina', h)]
                restano.remove(f)
                if arrivo is pg:
                    nuove.append((strade[f], collegamenti_della_pagina(pg)))
            if arrivo is not None and arrivo is not pg:
                arrivo.close()
        pagine_note += nuove
        if not restano or not nuove:
            break
    ok('ogni pagina si raggiunge con soli clic dalla home (%d dal menu e dalle linguette, %d con un clic in una pagina)'
       % (len(dirette), len(strade) - len(dirette)), not restano, restano)
    return strade


# ---------------------------------------------------------------- 3. i tasti e la struttura
def premi(pg, tasto):
    """Preme un tasto con il fuoco nella pagina (fuori dai campi) e torna l'indirizzo dove si arriva ('' se nessuno)."""
    pg.evaluate('document.activeElement && document.activeElement.blur && document.activeElement.blur()')
    try:
        with pg.expect_navigation(timeout=4000):
            pg.keyboard.press(tasto)
    except ErrorePlaywright:
        return ''
    pg.wait_for_timeout(150)
    return pg.url[len(B):] if pg.url.startswith(B) else pg.url


def attesi_dei_tasti(sid, giorno):
    q = '?struttura=%s' % sid if sid else ''
    return {'g': ('/giorno/%s%s' % (giorno, q), 'Agenda', 'Giorno'),
            'e': ('/giorno/%s/elenco%s' % (giorno, q), 'Agenda', 'Elenco'),
            'c': ('/conferme%s' % q, 'Segreteria', 'Conferme'),
            'd': ('/dove-si-fa/%s' % q, 'Dove si fa', None)}


def struttura_portata(pg, sid):
    """Le voci e le linguette della cornice (anche quelle nascoste) che non portano la struttura sid."""
    cose = menu(pg).get_by_role('link', include_hidden=True).all() + linguette(pg).get_by_role('link').all()
    senza = []
    for a in cose:
        nome = senza_numero(a.inner_text() or a.text_content())
        h = a.get_attribute('href') or ''
        if h.startswith('#') or nome in SENZA_STRUTTURA or (h.startswith('/aiuto')):
            continue
        if dict(parse_qsl(urlsplit(h).query)).get('struttura') != str(sid):
            senza.append('%s %s' % (nome, h))
    return senza, len(cose)


# ---------------------------------------------------------------- 4. il menu stretto
STRETTO = r"""() => {
  const lato = document.querySelector('[data-cornice="menu"]');
  const nav = lato.querySelector('nav');
  const marchio = lato.querySelector('[data-iniziali]');
  const voci = [...nav.querySelectorAll('a, button')].filter(e => e.getClientRects().length && !e.closest('[role=menu]'));
  // il nome di una voce si vede se un suo pezzo di testo (non il contatore) sta in una scatola più grande di 2x2 px,
  // senza clip e senza visibility hidden
  const siVede = (v) => {
    const giro = document.createTreeWalker(v, NodeFilter.SHOW_TEXT);
    for (let t = giro.nextNode(); t; t = giro.nextNode()) {
      const testo = t.textContent.trim();
      if (!testo || /^\d+$/.test(testo)) { continue; }
      const e = t.parentElement, b = e.getBoundingClientRect(), cs = getComputedStyle(e);
      if (b.width > 2 && b.height > 2 && cs.visibility !== 'hidden' && (cs.clipPath === 'none' || !cs.clipPath) &&
          (cs.clip === 'auto' || !cs.clip)) { return true; }
    }
    return false;
  };
  const logo = lato.querySelector('img');
  return {larghezza: lato.getBoundingClientRect().width,
          voci: voci.map(v => ({nome: (v.textContent || '').trim().replace(/\s+/g, ' ').replace(/\s*\d+$/, '').replace(/(\D)\d+$/, '$1'),
                               title: v.getAttribute('title'), larga: v.getBoundingClientRect().width, vede: siVede(v)})),
          logo: !!(logo && logo.getClientRects().length),
          iniziali: marchio ? getComputedStyle(marchio, '::before').content : null,
          scritte: marchio ? marchio.getAttribute('data-iniziali') : null};
}"""


def problemi_stretto(pg, stretto):
    """Sotto 1200 px (stretto=True): menu largo al più 80 px, i nomi non si vedono ma ci sono nel title e per i lettori
    di schermo (per ruolo e nome si trova la voce, che si vede), le iniziali al posto del logo. Da 1200 px: 248 px, i
    nomi si vedono, niente iniziali."""
    r = pg.evaluate(STRETTO)
    p = []
    if not r['voci']:
        return ['nessuna voce nel menu']
    if stretto:
        if r['larghezza'] > 80:
            p.append('il menu è largo %d px' % r['larghezza'])
        p += ['«%s»: il nome si vede' % v['nome'] for v in r['voci'] if v['vede']]
        p += ['«%s»: larga %d px' % (v['nome'], v['larga']) for v in r['voci'] if v['larga'] > 60]
        p += ['«%s»: title %r' % (v['nome'], v['title']) for v in r['voci'] if v['title'] != v['nome']]
        for v in r['voci']:
            trovata = menu(pg).get_by_role('link', name=nome_voce(v['nome'])).or_(
                menu(pg).get_by_role('button', name=nome_voce(v['nome'])))
            if trovata.count() != 1 or not trovata.is_visible():
                p.append('«%s»: per ruolo e nome %d voci' % (v['nome'], trovata.count()))
        if r['logo'] or not r['iniziali'] or r['iniziali'] in ('none', 'normal') or not (r['scritte'] or '').strip():
            p.append('al posto del logo non ci sono le iniziali: logo %s, iniziali %s' % (r['logo'], r['iniziali']))
    else:
        if abs(r['larghezza'] - MENU_LARGO) > 0.5:
            p.append('il menu è largo %d px' % r['larghezza'])
        p += ['«%s»: il nome non si vede' % v['nome'] for v in r['voci'] if not v['vede']]
        if r['iniziali'] not in ('none', 'normal', None):
            p.append('le iniziali anche nel menu largo: %s' % r['iniziali'])
    return p, len(r['voci'])


# ---------------------------------------------------------------- il giro
PERCORSI = {}                                       # funzione -> indirizzo senza parametri
with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get('CHROMIUM') or None)
    errori, domande = [], []

    def nuova_scheda(pagina):
        domande.append(prepara_domande(pagina))     # subito: ogni domanda del browser passa da qui, nessuna è attesa
        pagina.on('pageerror', lambda e: errori.append('errore JavaScript: %s' % e))
        pagina.on('console', lambda m: errori.append('console: %s' % m.text) if m.type == 'error' else None)

    ctx = br.new_context(viewport={'width': LARGO, 'height': ALTO})
    ctx.add_init_script(PRIMA_VOLTA)
    ctx.on('page', nuova_scheda)
    pg = ctx.new_page()

    # ---------------------------------------------- 1. ogni pagina senza parametri
    intere, saltate = documenti(ctx)
    ok('pagine senza parametri: %d intere da provare (saltati %d fra pezzi di pagina, JSON, Excel e risposte non 200)'
       % (len(intere), len(saltate)), len(intere) >= 50, saltate)
    viste, trabocca, di_lato = guarda_le_pagine(pg, errori, intere)
    for u in intere:
        r = ctx.request.get(B + u)
        f = re.search(r'data-pagina="([^"]*)"', r.text())
        if f:
            PERCORSI.setdefault(f.group(1), urlsplit(r.url).path)
    ok('a %dx%d il menu non ci sta e scorre per conto suo (in %d pagine su %d)' % ((LARGO, ALTO) + trabocca),
       trabocca[0] >= 1, trabocca)
    # le linguette ci sono in tutte le pagine di una voce che le ha
    con_linguette, senza = senza_linguette(viste)
    ok('le linguette ci sono in tutte le pagine delle voci che le hanno (%s)' % ', '.join(sorted(con_linguette)),
       len(con_linguette) >= 4 and not senza, senza)
    guasta = dict(viste)
    guasta['segreteria.attesa_scheda'] = (guasta['segreteria.attesa_scheda'][0], 'Segreteria', None)
    ok('gemello: una pagina della Segreteria senza linguette si vede', senza_linguette(guasta)[1] == ['/attesa/nuova (Segreteria)'],
       senza_linguette(guasta)[1])

    # ---------------------------------------------- 2. con soli clic dalla home
    strade = raggiungi(pg, viste)

    # ---------------------------------------------- 3. i tasti, la struttura e il giorno
    for partenza, sid, giorno in (('/cassa/%s?struttura=2' % ALTRO, 2, ALTRO), ('/ambulatori/settimana/%s?struttura=2' % ALTRO, 2, ALTRO),
                                  ('/giorno/%s/elenco?struttura=2' % ALTRO, 2, ALTRO), ('/pazienti', None, OGGI),
                                  ('/anagrafiche', None, OGGI)):
        for tasto, (atteso, voce, lingua) in attesi_dei_tasti(sid, giorno.isoformat()).items():
            pg.goto(B + partenza)
            pg.wait_for_timeout(250)
            arrivo = premi(pg, tasto)
            p = dopo_il_clic(pg, voce, lingua) if arrivo else ['nessuna pagina']
            ok('tasto %s da %s: %s, con %s acceso' % (tasto.upper(), urlsplit(partenza).path, atteso, voce),
               arrivo == atteso and not p, (arrivo, p))
        if sid:
            pg.goto(B + partenza)
            senza, quante = struttura_portata(pg, sid)
            ok('da %s: ogni voce e linguetta che porta la struttura porta la %s (%d collegamenti)' % (urlsplit(partenza).path, sid, quante),
               quante >= 12 and not senza, senza)

    # ---------------------------------------------- 4. sotto 1200 px solo le icone
    for larghezza, stretto in ((1199, True), (1200, False), (1024, True), (683, True)):
        pg.set_viewport_size({'width': larghezza, 'height': ALTO})
        for u in ('/giorno/%s?struttura=2' % ALTRO, '/conferme?struttura=1', '/anagrafiche'):
            pg.goto(B + u)
            pg.wait_for_timeout(300)
            pr, n = problemi_stretto(pg, stretto)
            ok('%d px, %s: %s (%d voci)' % (larghezza, urlsplit(u).path, 'menu a sole icone, i nomi per i lettori di schermo e nel title'
                                            if stretto else 'menu largo con i nomi', n), not pr, pr)
    pg.set_viewport_size({'width': LARGO, 'height': ALTO})
    e = errori_di(errori, 'giri')
    ok('nessun errore JavaScript nei giri (clic, tasti, menu stretto)', not e, e[:3])

    # ---------------------------------------------- i gemelli: gli stessi controlli vedono la pagina guastata, per il motivo giusto
    def gemello(nome, problemi, parola):
        ok('gemello: %s' % nome, any(parola in x for x in problemi), problemi)

    pg.goto(B + '/pazienti')
    pg.evaluate("document.querySelector('[data-cornice=\"menu\"]').remove()")
    gemello('senza il menu la cornice non c\'è', problemi_cornice(pg), 'menu (navigation')
    pg.goto(B + '/conferme')
    pg.evaluate("document.querySelector('nav.menu a[href^=\"/pazienti\"]').setAttribute('aria-current', 'page')")
    gemello('due voci accese si vedono', accese(pg)[2], '2 voci accese')
    pg.goto(B + '/conferme')
    pg.evaluate("[...document.querySelectorAll('[data-cornice=\"linguette\"] a')][1].setAttribute('aria-current', 'page')")
    gemello('due linguette accese si vedono', accese(pg)[2], '2 linguette accese')
    pg.goto(B + '/conferme')
    pg.add_style_tag(content='@media print { [data-cornice="menu"] { display: flex !important; } }')
    gemello('il menu rimesso in stampa si vede', problemi_stampa(pg), "in stampa si vede: ['menu']")
    pg.goto(B + '/conferme')
    pg.add_style_tag(content='@media print { main { margin-left: 248px !important; } }')
    gemello('in stampa la colonna del menu lasciata vuota si vede', problemi_stampa(pg), 'non comincia dal bordo')
    pg.goto(B + '/impostazioni')
    pg.add_style_tag(content='[data-cornice="menu"] nav * { overflow: visible !important; }')
    gemello('il menu che non scorre per conto suo si vede', problemi_menu_che_scorre(pg)[0], 'parti del menu che scorrono')
    pg.goto(B + '/impostazioni')
    pg.add_style_tag(content='[data-cornice="menu"] { position: static !important; }')
    gemello('il menu che non resta fermo scorrendo la pagina si vede', problemi_menu_che_scorre(pg)[0], 'non resta fermo')
    pg.goto(B + '/impostazioni')
    pg.evaluate("""() => { const s = [...document.querySelectorAll('[data-cornice="menu"] nav *')].find(e => getComputedStyle(e).overflowY === 'auto');
                   const voci = s.querySelectorAll('a'); voci[voci.length - 1].style.cssText = 'position: fixed; top: 900px;'; }""")
    gemello('l\'ultima voce che non si raggiunge si vede', problemi_menu_che_scorre(pg)[0], 'ultima voce non si raggiunge')
    pg.goto(B + '/impostazioni')
    pg.evaluate("""() => { const d = document.createElement('div'); d.style.cssText = 'width: 1600px; height: 4px;';
                   document.querySelector('[data-cornice="menu"]').appendChild(d); }""")
    gemello('un pezzo largo nel menu si vede', problemi_menu_che_scorre(pg)[0], 'fuori dal bordo destro, nella cornice')
    pg.goto(B + '/impostazioni')
    pg.add_style_tag(content='main { min-width: 1300px !important; }')
    gemello('la pagina spinta oltre il bordo destro si vede', problemi_menu_che_scorre(pg)[0], 'spinta oltre il bordo destro')
    pg.goto(B + '/pazienti')
    pg.evaluate("setTimeout(() => { throw new Error('errore di prova'); }, 0)")
    pg.wait_for_timeout(200)
    gemello('un errore JavaScript della pagina si vede', errori_di(errori, 'gemello'), 'errore di prova')
    # una linguetta che porta altrove: dopo il clic è accesa un'altra linguetta
    pg.goto(B + '/conferme')
    pg.evaluate("""() => { const a = [...document.querySelectorAll('[data-cornice="linguette"] a')].find(a => a.textContent.includes('attesa'));
                   a.setAttribute('href', '/disponibilita'); }""")
    pg = clicca(pg, linguetta(pg, "Lista d'attesa"))
    gemello('una linguetta che porta a un indirizzo sbagliato si vede', dopo_il_clic(pg, 'Segreteria', "Lista d'attesa"),
            'accesa la linguetta Prima disponibilità')
    pg.goto(B + '/pazienti')
    pg.evaluate("document.querySelectorAll('[data-tasto=\"g\"]').forEach(e => e.removeAttribute('data-tasto'))")
    arrivo = premi(pg, 'g')
    ok('gemello: il tasto G tolto si vede (nessuna pagina)', arrivo == '', arrivo)
    pg.goto(B + '/giorno/%s?struttura=2' % ALTRO)
    pg.evaluate("document.querySelector('nav.menu a[href^=\"/personale/turni\"]').setAttribute('href', '/personale/turni')")
    gemello('una voce che perde la struttura si vede', struttura_portata(pg, 2)[0], 'Turni /personale/turni')
    pg.set_viewport_size({'width': 1199, 'height': ALTO})
    pg.goto(B + '/conferme')
    pg.add_style_tag(content='[data-cornice="menu"] nav span { position: static !important; width: auto !important; '
                             'height: auto !important; clip: auto !important; clip-path: none !important; }')
    gemello('a 1199 px i nomi visibili nel menu si vedono', problemi_stretto(pg, True)[0], 'il nome si vede')
    pg.set_viewport_size({'width': LARGO, 'height': ALTO})
    errori_di(errori, 'gemelli')
    # una domanda del browser che nessuno aspetta: in una scheda a parte, fuori dal conto finale
    prova = br.new_page()
    d = prepara_domande(prova)
    prova.goto(B + '/pazienti')
    prova.evaluate("setTimeout(() => confirm('domanda di prova'), 0)")
    prova.wait_for_timeout(300)
    ok('gemello: una domanda del browser inattesa si vede', d.inattese == ['domanda di prova'], d.inattese)
    prova.close()

    inattese = [x for d in domande for x in d.inattese]
    ok('nessuna domanda del browser inattesa', not inattese, inattese)
    ctx.close()
    br.close()
if di_lato:
    print('\nNota: pagine che scorrono di lato per il loro contenuto, non per la cornice:\n  ' + '\n  '.join(di_lato))
print('\n%d prove nel browser, %d superate' % (len(esiti), sum(esiti)))
sys.exit(0 if all(esiti) else 1)
