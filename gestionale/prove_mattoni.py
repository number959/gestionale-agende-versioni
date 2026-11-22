# -*- coding: utf-8 -*-
"""I mattoni della veste nuova (tappa 1-bis, 22/11/2026), senza browser.

- Gettoni (static/gettoni.css): ogni coppia testo/fondo dei pezzi ha contrasto almeno 4,5:1, in chiaro e in scuro, anche
  per i colori della struttura (il predefinito, quelli delle prove, una griglia di tinte; strumenti/leggi_gettoni.py
  risolve var() e color-mix() come il browser); ogni colore di testo di veste.css ha la sua coppia; ogni colore ha il
  suo valore scuro, solo a schermo.
- Nessun colore scritto a mano nei file nuovi (veste.css, _pezzi.html, il catalogo, la testa di base.html).
- Lo strato (base.html): i fogli di oggi dentro @layer vecchio, nell'ordine di ogni variante, con il :root del colore
  della struttura; nessun sotto-strato; gettoni.css e veste.css fuori, dopo; i fogli da stampare come prima.
- Prefisso: veste.css ha solo classi v- (più quelle tenute per il JavaScript di oggi), nessuna già usata dalle pagine di
  oggi, e nessun selettore senza un pezzo v-.
- I pezzi (_pezzi.html) con le variabili rigide: agganci di JavaScript, guida e prove; icone che esistono; euro() uguale
  ai tre modi di oggi.
- marchio.tema: le cinque varianti di sempre non cambiano (copia ferma qui sotto) e i fondi chiari sono quelli dei gettoni.
- L'autoriparazione controlla anche gettoni.css e veste.css (app.risorse_presenti), e prove_installato.py li chiede.
- Il lanciatore (strumenti/tutte_le_prove.py) lancia ogni raccolta della cartella: ogni prove*.py che non è un aiuto, e
  ogni file che scrive la riga finale di una raccolta, sta in SENZA_BROWSER o in NEL_BROWSER (revisione dell'unione con
  l'accesso dagli altri PC: una riga persa in un conflitto lasciava tutto verde).
Ogni prova ha il suo gemello: la stessa prova su un file cambiato apposta (il mutante) deve cadere.

    python prove_mattoni.py
"""
import glob
import os
import random
import re
import shutil
import sys
import tempfile

from prove_dove import dove

CARTELLA = os.path.dirname(os.path.abspath(__file__))
PROVVISORIA = tempfile.mkdtemp(prefix='prove-mattoni-')

import jinja2  # noqa: E402
import seed  # noqa: E402
import app as A  # noqa: E402
import marchio  # noqa: E402
from modelli import importo_in_testo  # noqa: E402
from strumenti import leggi_gettoni as L  # noqa: E402
from strumenti import tutte_le_prove as TP  # noqa: E402

A.app.config['TESTING'] = True
A.Sessione = seed.popola('sqlite:///' + os.path.join(PROVVISORIA, 'prove.db'))
A._registro = None
esiti = []


def prova(nome, f):
    try:
        esiti.append(('OK', nome, f() or ''))
    except AssertionError as e:
        esiti.append(('ROTTO', nome, '%s · %s' % (dove(e), str(e)[:900] or 'asserzione fallita')))
    except Exception as e:
        esiti.append(('ERRORE', nome, '%s · %r' % (dove(e), e)))


def leggi(rel):
    with open(os.path.join(CARTELLA, rel), encoding='utf-8') as f:
        return f.read()


def cade(f, *argomenti):
    """Il gemello: la prova f sui file cambiati apposta deve cadere (AssertionError). Torna il suo messaggio."""
    try:
        f(*argomenti)
    except AssertionError as e:
        return str(e) or 'caduta'
    raise AssertionError('il mutante passa: la prova non lo vede')


def cambia(testo, vecchio, nuovo):
    assert vecchio in testo, 'il mutante non si applica: %r' % vecchio[:80]
    return testo.replace(vecchio, nuovo, 1)


GETTONI, VESTE, PEZZI, BASE = (leggi('static/gettoni.css'), leggi('static/veste.css'), leggi('templates/_pezzi.html'),
                               leggi('templates/base.html'))
TEMA_SCURO, CATALOGO = leggi('static/tema-scuro.css'), leggi('strumenti/catalogo_pezzi.html')
COLORI = L.COLORI_DI_PROVA + L.griglia_di_colori()


# ================================================================ gettoni: contrasti
def controlla_contrasti(gettoni, veste, coppie=L.COPPIE):
    male, minimo = [], (99, '')
    for colore in COLORI:
        for tema in ('chiaro', 'scuro'):
            for testo, fondo, dove_, x in L.contrasti(colore, tema, coppie, gettoni=gettoni, tema_scuro=TEMA_SCURO, base=BASE):
                if x is None:
                    male.append('%s su %s (%s): un gettone non si risolve in un colore' % (testo, fondo, dove_))
                elif x < 4.5:
                    male.append('%s su %s in %s con %s (%s): %.2f' % (testo, fondo, tema, colore, dove_, x))
                elif x < minimo[0]:
                    minimo = (x, '%s su %s in %s con %s' % (testo, fondo, tema, colore))
    assert not male, '%d coppie sotto 4,5:1: %s' % (len(male), sorted(set(male))[:6])
    # ogni colore di testo usato da veste.css ha almeno una coppia (una regola nuova non passa senza la sua)
    nel_css = set(re.findall(r'(?<![-\w])color\s*:\s*var\(--v-([\w-]+)\)', L.senza_commenti(veste)))
    senza = sorted(nel_css - {t for t, _, _ in coppie})
    assert not senza, 'colori di testo di veste.css senza una coppia in strumenti/leggi_gettoni.py: %s' % senza
    return minimo


def g_contrasti():
    x, dove_ = controlla_contrasti(GETTONI, VESTE)
    return '%d coppie × %d colori della struttura × 2 temi; la più bassa %.2f (%s)' % (len(L.COPPIE), len(COLORI), x, dove_)


def gemello_contrasti():
    a = cade(controlla_contrasti, cambia(GETTONI, '--v-testo-tenue: #5B687C;', '--v-testo-tenue: #8A95A5;'), VESTE)
    b = cade(controlla_contrasti, cambia(GETTONI, 'color-mix(in srgb, var(--primario) 82%, #000000)',
                                         'color-mix(in srgb, var(--primario) 80%, #FFFFFF)'), VESTE)
    c = cade(controlla_contrasti, GETTONI, VESTE + '\n.v-x { color: var(--v-segno-grigio); }')
    assert 'testo-tenue' in a and 'primario-premuto' in b and 'segno-grigio' in c, (a, b, c)


def controlla_contorni(gettoni, coppie=L.COPPIE_CONTORNO, colori=None):
    """Il contorno del fuoco della tastiera: almeno 3:1 sui fondi dove sta, in chiaro e in scuro, per ogni colore."""
    male, minimo = [], (99, '')
    for colore in colori or COLORI:
        for tema in ('chiaro', 'scuro'):
            for testo, fondo, dove_, x in L.contrasti(colore, tema, coppie, gettoni=gettoni, tema_scuro=TEMA_SCURO, base=BASE):
                if x is None or x < 3:
                    male.append('%s su %s in %s con %s (%s): %s' % (testo, fondo, tema, colore, dove_, x and '%.2f' % x))
                elif x < minimo[0]:
                    minimo = (x, '%s su %s in %s con %s' % (testo, fondo, tema, colore))
    assert not male, '%d contorni sotto 3:1: %s' % (len(male), sorted(set(male))[:6])
    return minimo


def g_contorni():
    x, dove_ = controlla_contorni(GETTONI)
    return '%d coppie × %d colori × 2 temi; il più basso %.2f (%s)' % (len(L.COPPIE_CONTORNO), len(COLORI), x, dove_)


def gemello_contorni():
    # il contorno di prima (il colore della struttura con un quarto di bianco): con il verde #2E7D32 sotto 3:1
    prima = cambia(GETTONI, '--v-fuoco: var(--v-primario-testo);', '--v-fuoco: var(--primario-fuoco);')
    a = cade(controlla_contorni, prima, L.COPPIE_CONTORNO, ['#2E7D32'])
    assert 'fuoco su' in a and '#2E7D32' in a and 'in chiaro' in a, a
    # con il blu di oggi il contorno di prima bastava: il controllo non cade per il colore predefinito
    controlla_contorni(prima, L.COPPIE_CONTORNO, ['#154381'])


# ================================================================ gettoni: il valore scuro
def controlla_scuro(gettoni):
    css = L.senza_commenti(gettoni)
    chiaro, scuro = L.gettoni_css(gettoni)
    assert re.search(r'@media\s+screen\s*\{\s*html\.scuro\s*\{', css), 'il tema scuro dei gettoni non è sotto @media screen'
    colori = {n for n, v in chiaro.items() if re.search(r'#[0-9A-Fa-f]{3,8}\b|rgba?\(', v)}
    senza = sorted(colori - set(scuro))
    assert not senza, 'gettoni senza il valore scuro: %s' % senza
    assert len(colori) >= 30, 'solo %d gettoni con un colore: non li legge più?' % len(colori)
    return '%d colori, ognuno con il suo valore scuro' % len(colori)


def g_scuro():
    return controlla_scuro(GETTONI)


def gemello_scuro():
    cade(controlla_scuro, cambia(GETTONI, '    --v-sabbia: #3B3729;\n', ''))
    cade(controlla_scuro, cambia(GETTONI, '@media screen {\n  html.scuro {', '@media all {\n  html.scuro {'))


# ================================================================ nessun colore scritto a mano nei file nuovi
COLORE_A_MANO = re.compile(r'#[0-9A-Fa-f]{3,8}\b|\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklch|oklab|color-mix)\(|'
                           r'(?<![-\w])(?:white|black|red|blue|green|gray|grey|navy|silver|orange|purple|yellow)(?![-\w])',
                           re.I)
# tutti i 148 nomi di colore del CSS (teal, crimson, gold…; Pillow li ha già in ImageColor.colormap, transparent no):
# contano nel CSS (i fogli, i blocchi <style> e gli attributi style="…" dei modelli), non nel testo delle pagine
from PIL import ImageColor  # noqa: E402
NOME_DI_COLORE = re.compile(r'(?<![-\w])(?:%s)(?![-\w])' % '|'.join(sorted(ImageColor.colormap, key=len, reverse=True)), re.I)


def css_del_modello(testo):
    """Il CSS scritto in un modello: i blocchi <style> e gli attributi style="…"."""
    blocchi = re.findall(r'<style[^>]*>(.*?)</style>', testo, re.S)
    attributi = [a or b for a, b in re.findall(r'''\sstyle\s*=\s*(?:"([^"]*)"|'([^']*)')''', testo)]
    return '\n'.join(blocchi + attributi)


def testa_nuova(base):
    """Le righe della testa di base.html che la tappa 1-bis ha scritto: dallo strato ai fogli nuovi."""
    return base[base.index('{%- if carta %}'):base.index('<link rel="icon"')]


def controlla_colori(file_):
    male = []
    for nome, testo in file_.items():
        if nome.endswith('.css'):
            testo = css = L.senza_commenti(testo)
        else:
            testo = re.sub(r'\{#.*?#\}', '', testo, flags=re.S)
            css = L.senza_commenti(css_del_modello(testo))
        male += ['%s: %s' % (nome, m.group(0)) for m in COLORE_A_MANO.finditer(testo)]
        male += ['%s: %s' % (nome, m.group(0)) for m in NOME_DI_COLORE.finditer(css)]
    assert not male, 'colori scritti a mano: %s' % male[:8]


def g_colori():
    file_ = {'static/veste.css': VESTE, 'templates/_pezzi.html': PEZZI,
             'strumenti/catalogo_pezzi.html': CATALOGO, 'templates/base.html (testa)': testa_nuova(BASE)}
    file_.update({'templates/' + n: leggi('templates/' + n) for n in CORNICE})      # dalla tappa 2, la cornice
    controlla_colori(file_)
    return '%d file' % len(file_)


def gemello_colori():
    cade(controlla_colori, {'veste.css': VESTE + '\n.v-x { border-color: #123456; }'})
    cade(controlla_colori, {'_pezzi.html': PEZZI + '<span style="color: red">x</span>'})
    cade(controlla_colori, {'catalogo': CATALOGO + '<i style="background: rgb(1, 2, 3)"></i>'})
    cade(controlla_colori, {'_menu.html': leggi('templates/_menu.html') + '<span style="color: #1C4184">x</span>'})
    controlla_colori({'commenti.css': '/* #FFFFFF nei commenti va bene */ .v-x { color: var(--v-testo); }'})
    # i colori con un nome qualsiasi del CSS, non solo i dodici più comuni; nel testo della pagina una parola resta parola
    assert 'Teal' in cade(controlla_colori, {'veste.css': VESTE + '\n.v-x { border-color: Teal; }'})
    assert 'crimson' in cade(controlla_colori, {'_pezzi.html': PEZZI + '<span style="background: crimson">x</span>'})
    assert 'gold' in cade(controlla_colori, {'catalogo': CATALOGO + '<style>.cat-x { outline: 1px solid gold; }</style>'})
    controlla_colori({'testo.html': '<p>Gold e Tan, nomi inventati: nel testo non sono colori</p>'})


# ================================================================ lo strato in base.html
def rendi_base(sorgente_base=None):
    """La pagina vuota fatta con base.html (o con un base.html cambiato): normale e animata, pagina e foglio da stampare."""
    env = A.app.jinja_env
    if sorgente_base is not None:
        env = env.overlay(loader=jinja2.ChoiceLoader([jinja2.DictLoader({'base.html': sorgente_base}), A.app.jinja_loader]))
        env.globals.update(A.app.jinja_env.globals)
    uscita = {}
    with A.app.test_request_context('/'):
        for nome, carta, variante in (('pagina', False, 'normale'), ('carta', True, 'normale'),
                                      ('animata', False, 'animata'), ('carta animata', True, 'animata')):
            contesto = {}
            A.app.update_template_context(contesto)
            contesto['variante'] = variante
            s = '{% extends "base.html" %}' + ('{% set foglio_carta = true %}' if carta else '') + '{% block menu %}{% endblock %}'
            uscita[nome] = env.from_string(s).render(contesto)
    return uscita


def controlla_strato(p):
    fogli = lambda h: re.findall(r'<link rel="stylesheet" href="/static/([\w.-]+)">', h)
    strato = lambda h: re.findall(r'@import url\("/static/([\w.-]+)"\) layer\(([\w.-]+)\);', h)
    for nome, attesi in (('pagina', ['stile.css', 'tema-scuro.css']), ('animata', ['stile.css', 'animazioni.css', 'tema-scuro.css'])):
        h = p[nome]
        assert [f for f, _ in strato(h)] == attesi, '%s: fogli nello strato %s, attesi %s' % (nome, strato(h), attesi)
        assert {s for _, s in strato(h)} == {'vecchio'}, '%s: uno strato solo, «vecchio» (niente sotto-strati): %s' % (nome, strato(h))
        # il colore della struttura sta nello strato: fuori vincerebbe su html.scuro di tema-scuro.css
        assert re.search(r'<style>@layer vecchio \{ :root \{ --primario: #[0-9a-f]{6};', h), '%s: il :root della struttura è fuori dallo strato' % nome
        assert not re.search(r'<style>:root', h), '%s: un :root della struttura fuori dallo strato' % nome
        assert re.findall(r'@layer ([\w.,\s-]+?)\s*[;{]', h) == ['vecchio', 'vecchio'], \
            '%s: lo strato si dichiara una volta prima degli @import, poi il :root: %s' % (nome, re.findall(r'@layer [^;{]*', h))
        assert h.index('@layer vecchio;') < h.index('@import'), '%s: lo strato si dichiara prima degli @import' % nome
        assert fogli(h) == ['gettoni.css', 'veste.css'], '%s: fuori dallo strato %s' % (nome, fogli(h))
        assert h.index('@layer vecchio {') < h.index('/static/gettoni.css') < h.index('/static/veste.css'), '%s: ordine' % nome
        assert ("classList.add('anim')" in h) == (nome == 'animata'), '%s: lo script delle animazioni' % nome
    # i fogli da stampare come prima: i link di oggi, senza strato e senza fogli nuovi
    for nome, attesi in (('carta', ['stile.css', 'tema-scuro.css']), ('carta animata', ['stile.css', 'animazioni.css', 'tema-scuro.css'])):
        h = p[nome]
        assert fogli(h) == attesi and '@layer' not in h and '@import' not in h, '%s: %s' % (nome, fogli(h))
        assert re.search(r'<style>:root \{ --primario: #[0-9a-f]{6}; --primario-scuro: #[0-9a-f]{6}; --primario-tenue: '
                         r'#[0-9a-f]{6}; --primario-chiaro: #[0-9a-f]{6}; --primario-fuoco: #[0-9a-f]{6}; \}</style>', h), nome
        assert 'if (true)' in h, '%s: il foglio da stampare resta chiaro' % nome


def s_strato():
    controlla_strato(rendi_base())
    return 'normale e animata, pagine e fogli da stampare'


def gemello_strato():
    fuori = cambia(BASE, "<style>@layer vecchio { :root { --primario: {{ tema.primario }};", "<style>:root { --primario: {{ tema.primario }};")
    fuori = cambia(fuori, "--primario-testo: {{ tema.testo }}; } }</style>", "--primario-testo: {{ tema.testo }}; }</style>")
    assert ':root della struttura' in cade(controlla_strato, rendi_base(fuori))
    sotto = cambia(BASE, "filename='tema-scuro.css') }}\") layer(vecchio);", "filename='tema-scuro.css') }}\") layer(vecchio.tema);")
    assert 'sotto-strati' in cade(controlla_strato, rendi_base(sotto))
    ordine = cambia(BASE, "@import url(\"{{ url_for('static', filename='animazioni.css') }}\") layer(vecchio);\n{%- endif %}\n"
                          "@import url(\"{{ url_for('static', filename='tema-scuro.css') }}\") layer(vecchio);",
                    "{%- endif %}\n@import url(\"{{ url_for('static', filename='tema-scuro.css') }}\") layer(vecchio);\n"
                    "{%- if variante == 'animata' %}\n@import url(\"{{ url_for('static', filename='animazioni.css') }}\") layer(vecchio);\n{%- endif %}")
    assert 'animata' in cade(controlla_strato, rendi_base(ordine))
    dentro = cambia(BASE, "<link rel=\"stylesheet\" href=\"{{ url_for('static', filename='veste.css') }}\">",
                    "<style>@import url(\"{{ url_for('static', filename='veste.css') }}\") layer(vecchio);</style>")
    cade(controlla_strato, rendi_base(dentro))
    carta = cambia(BASE, "{%- if carta %}\n<link rel=\"stylesheet\" href=\"{{ url_for('static', filename='stile.css') }}\">",
                   "{%- if carta %}\n<link rel=\"stylesheet\" href=\"{{ url_for('static', filename='gettoni.css') }}\">\n"
                   "<link rel=\"stylesheet\" href=\"{{ url_for('static', filename='stile.css') }}\">")
    assert 'carta' in cade(controlla_strato, rendi_base(carta))


# ================================================================ prefisso: i nomi nuovi non pestano quelli vecchi
TENUTE = {'primario', 'gruppo-comandi', 'apri-gruppo', 'tendina', 'aperto', 'numeri', 'allarme'}   # agganci del JavaScript di oggi
# dalla tappa 2: tre classi delle pagine di oggi che la cornice nasconde, sposta o accorcia, solo dentro la cornice (in
# un selettore che comincia da un pezzo v-, «.v-cornice .marchio»): il logo della pagina (c'è già nel menu; resta in
# stampa), «Prima volta qui?» della guida, che in basso a sinistra coprirebbe Aiuto e Configura, e il riquadro dei
# Turni, alto quanto la finestra meno il menu in alto di prima (sotto la barra nuova finiva oltre il bordo)
DALLA_CORNICE = {'marchio', 'giro-invito', 'scorri-turni'}
NUOVI = {'veste.css', 'gettoni.css', '_pezzi.html',
         '_menu.html', '_barra.html', '_linguette.html',        # dalla tappa 2 i modelli della cornice, fatti con i pezzi v-
         # 1.13, accesso dagli altri PC: la riga di chi è entrato (v-utente-rete) è nuova, non una pagina di oggi
         '_utente_rete.html'}
CORNICE = ('_menu.html', '_barra.html', '_linguette.html', '_notifiche.html', '_utente_rete.html')


def classi_vecchie():
    """Le classi delle pagine di oggi: fogli di stile, modelli e JavaScript, delle due cartelle."""
    classi = set()
    for cartella in (CARTELLA, os.path.join(os.path.dirname(CARTELLA), 'gestionale-animata')):
        for f in glob.glob(os.path.join(cartella, 'static', '*.css')):
            if os.path.basename(f) not in NUOVI:
                classi |= set(re.findall(r'\.([a-zA-Z_][\w-]*)', re.sub(r'url\([^)]*\)|\d+\.\d+', '', L.senza_commenti(open(f, encoding='utf-8').read()))))
        for f in glob.glob(os.path.join(cartella, 'templates', '*.html')):
            if os.path.basename(f) not in NUOVI:
                for m in re.finditer(r'class="([^"]*)"', open(f, encoding='utf-8').read()):
                    nuove_di_base = os.path.basename(f) == 'base.html'     # dalla tappa 2 la griglia della cornice (v-cornice)
                    classi |= {c for c in re.split(r'\s+', re.sub(r'\{[{%].*?[}%]\}', ' ', m.group(1)))
                               if c and not (nuove_di_base and c.startswith('v-'))}
        for f in glob.glob(os.path.join(cartella, 'static', '*.js')):
            t = open(f, encoding='utf-8').read()
            classi |= set(re.findall(r"classList\.(?:add|remove|toggle|contains)\('([\w-]+)'", t))
            classi |= set(re.findall(r"className\s*=\s*'([\w\s-]+)'", t))
    return classi


FUNZIONE_DI_SCELTA = re.compile(r':(not|is|where|matches|-webkit-any|-moz-any)\(')


def tocca_un_pezzo(sel):
    """Il selettore prende solo un pezzo v- (o quello che c'è dentro)? Un .v- dentro :not() non basta
    (a:not(.v-bottone) prende tutti i collegamenti di oggi); dentro :is() e :where() conta solo se ce l'hanno tutte le
    scelte (:where(.v-pagina, body) a prende anche quelli di oggi). Dentro :has() conta: la regola vale solo dove c'è
    un pezzo nuovo, e le pagine di oggi non ne hanno."""
    m = FUNZIONE_DI_SCELTA.search(sel)
    if not m:
        return '.v-' in sel
    fine, livello = m.end(), 1
    while livello and fine < len(sel):
        livello += {'(': 1, ')': -1}.get(sel[fine], 0)
        fine += 1
    scelte = L._argomenti(sel[m.end():fine - 1])
    al_posto = '.v-' if m.group(1) != 'not' and all(tocca_un_pezzo(s) for s in scelte) else ''
    return tocca_un_pezzo(sel[:m.start()] + al_posto + sel[fine:])


def controlla_prefisso(veste, vecchie):
    css = L.senza_commenti(veste)
    usate = set(re.findall(r'\.([a-zA-Z_][\w-]*)', re.sub(r'url\([^)]*\)|\d*\.\d+', '', css)))
    senza = sorted(c for c in usate if not c.startswith('v-') and c not in TENUTE | DALLA_CORNICE)
    assert not senza, 'classi senza il prefisso v-: %s' % senza
    # quelle della cornice solo dopo un pezzo v- (dentro la cornice), mai da sole
    for regola in re.findall(r'([^{}]+)\{', re.sub(r'@[\w-]+[^{;]*\{', '{', css)):
        for sel in re.split(r',(?![^(]*\))', regola):
            for c in DALLA_CORNICE:
                m = re.search(r'\.%s(?![\w-])' % re.escape(c), sel)
                if m:
                    assert '.v-' in sel[:m.start()], 'la classe di oggi «%s» fuori dalla cornice: %r' % (c, sel.strip())
    pestate = sorted(c for c in usate if c.startswith('v-') and c in vecchie)
    assert not pestate, 'classi v- già usate dalle pagine di oggi: %s' % pestate
    vecchie_v = sorted(c for c in vecchie if c.startswith('v-'))
    assert not vecchie_v, 'le pagine di oggi usano già il prefisso v-: %s' % vecchie_v
    # nessuna regola senza un pezzo v- (body, a, input… cambierebbero le pagine di oggi, fuori dallo strato vincerebbero)
    for regola in re.findall(r'([^{}]+)\{', re.sub(r'@[\w-]+[^{;]*\{', '{', css)):
        for sel in re.split(r',(?![^(]*\))', regola):
            sel = sel.strip()
            if sel and not re.match(r'^(from|to|\d+%)$', sel):
                assert tocca_un_pezzo(sel), 'selettore senza un pezzo v-: %r' % sel
    return '%d classi, %d di oggi controllate' % (len(usate), len(vecchie))


def p_prefisso():
    return controlla_prefisso(VESTE, classi_vecchie())


def gemello_prefisso():
    vecchie = classi_vecchie()
    assert 'senza il prefisso' in cade(controlla_prefisso, VESTE + '\n.voce { color: var(--v-testo); }', vecchie)
    # le due classi di oggi che la cornice nasconde o sposta: mai da sole o prima del pezzo v-
    assert 'fuori dalla cornice' in cade(controlla_prefisso, VESTE + '\n.marchio { display: none; }', vecchie)
    assert 'fuori dalla cornice' in cade(controlla_prefisso, VESTE + '\n.giro-invito .v-x { left: 0; }', vecchie)
    assert 'senza un pezzo v-' in cade(controlla_prefisso, VESTE + '\nbody { margin: 0; }', vecchie)
    assert 'già usate' in cade(controlla_prefisso, VESTE, vecchie | {'v-scheda'})
    # un .v- dentro :not() o in una sola scelta di :where() non basta: la regola prenderebbe i collegamenti di oggi
    assert 'senza un pezzo v-' in cade(controlla_prefisso, VESTE + '\na:not(.v-bottone) { color: var(--v-testo); }', vecchie)
    assert 'senza un pezzo v-' in cade(controlla_prefisso, VESTE + '\n:where(.v-pagina, body) a { color: var(--v-testo); }', vecchie)
    assert tocca_un_pezzo(':where(.v-pagina) a:not([class])') and tocca_un_pezzo('.v-campo :is(input:not([type=radio]), select)')
    assert tocca_un_pezzo('.v-barra-comandi:has(.aperto)') and not tocca_un_pezzo(':is(.v-scheda, .elenco) td')
    assert {'voce', 'bottone', 'elenco', 'passo', 'anim'} <= vecchie, 'le classi di oggi non si leggono più'


# ================================================================ i pezzi, con le variabili rigide
def ambiente_pezzi(sorgente=None):
    env = A.app.jinja_env
    if sorgente is not None:
        env = env.overlay(loader=jinja2.ChoiceLoader([jinja2.DictLoader({'_pezzi.html': sorgente}), A.app.jinja_loader]))
    return env


PROVA_DEI_PEZZI = r"""{% from "_pezzi.html" import intestazione, scheda, tabella, pillola, conta, striscia, barra_comandi,
                                       passo, tendina, linguette, stampa_e_scarica, euro %}
<!--intestazione-->{% call intestazione('Cassa', sopra='Cassa · Sede', sotto='Quanto si è incassato', classe_titolo='giorno') %}<a href="/x">Mese</a>{% endcall %}<!--/intestazione-->
<!--scheda-->{% call scheda('Incassi', sotto='Del giorno', id='incassi', attaccata=true, guida='cassa-incassi') %}corpo{% endcall %}<!--/scheda-->
<!--tabella-->{% call tabella(classe='elenco', guida='cassa-tabella') %}<tr><td>1</td></tr>{% endcall %}<!--/tabella-->
<!--pillola-->{{ pillola('NON_PRESENTATO', 'Non presentato') }}{{ pillola('ARRIVATO', 'Arrivato', dopo='10:21') }}<!--/pillola-->
<!--conta-->[{{ conta(0) }}][{{ conta(0, zero=true) }}][{{ conta(3, '3 da confermare') }}]<!--/conta-->
<!--striscia-->{{ striscia([(294, 'appuntamenti'), {'numero': '915,00 €', 'prima': 'incassati'},
    {'numero': 2, 'cosa': 'non presentati', 'allarme': true, 'guida': 'cassa-allarme'},
    {'parti': [('200,0', 'ore prenotate su'), ('530,0', 'di turno (38%)')]}], classe='numeri grandi') }}<!--/striscia-->
<!--barra-->{% call barra_comandi(guida='barra') %}{{ passo('/ieri', 'indietro', 'Giorno precedente', tasto='precedente') }}{% call tendina() %}<select name="struttura"><option>1</option></select>{% endcall %}{% endcall %}<!--/barra-->
<!--linguette-->{{ linguette([{'testo': 'Giorno', 'indirizzo': '/g', 'accesa': true, 'tasto': 'g', 'titolo': 'il giorno'},
    {'testo': 'Elenco', 'indirizzo': '/e', 'icona': 'chevron-right', 'conta': 2, 'guida': 'linguetta-elenco'}], etichetta='Viste') }}<!--/linguette-->
<!--stampa-->{{ stampa_e_scarica([{'testo': 'Stampa del giorno', 'sotto': 'il foglio', 'indirizzo': '/s', 'nuova_scheda': true},
    {'testo': 'Nascosta', 'indirizzo': '/n', 'visibile': false}]) }}
{% call stampa_e_scarica(testo='Strumenti', icona_bottone=none) %}<button type="button" role="menuitem" data-apri-schema>{{ '' }}<b>Schema</b></button>{% endcall %}<!--/stampa-->
<!--euro-->[{{ euro(125050) }}][{{ euro(0, se_zero='—') }}][{{ euro(91500, simbolo=true) }}][{{ euro(None) }}]<!--/euro-->"""


def pezzo(h, nome):
    return h[h.index('<!--%s-->' % nome):h.index('<!--/%s-->' % nome)]


def controlla_pezzi(sorgente=None):
    env = ambiente_pezzi(sorgente)
    assert env.undefined is A.VariabileMancante, 'le prove girano senza le variabili rigide'
    with A.app.test_request_context('/'):
        h = env.from_string(PROVA_DEI_PEZZI).render()
    p = {n: pezzo(h, n) for n in ('intestazione', 'scheda', 'tabella', 'pillola', 'conta', 'striscia', 'barra', 'linguette', 'stampa', 'euro')}
    assert '<h1 class="v-titolo giorno">Cassa</h1>' in p['intestazione'] and '<a href="/x">Mese</a>' in p['intestazione']
    assert 'aria-labelledby="incassi"' in p['scheda'] and 'id="incassi"' in p['scheda'] and 'data-guida="cassa-incassi"' in p['scheda']
    assert 'class="v-tabella elenco"' in p['tabella'] and 'data-guida="cassa-tabella"' in p['tabella']
    assert 'v-pillola-non_presentato' in p['pillola'] and 'Arrivato 10:21' in p['pillola'] and 'aria-hidden="true"' in p['pillola']
    assert p['conta'].count('v-conta') == 2 and '[]' in p['conta'] and '>0</span>' in p['conta']
    s = p['striscia']
    assert s.count('<li ') == 4 and '<ul class="v-striscia numeri grandi"' in s, 'la striscia è un ul.numeri (animazioni.js)'
    assert re.sub(r'<[^>]+>', '', s).split() == ['294', 'appuntamenti', 'incassati', '915,00', '€', '2', 'non', 'presentati',
                                                 '200,0', 'ore', 'prenotate', 'su', '530,0', 'di', 'turno', '(38%)'], \
        'il testo letto della striscia: %s' % re.sub(r'<[^>]+>', '', s).split()
    assert s.count('<b class="v-striscia-numero">') == 5 and 'class="v-striscia-voce allarme v-allarme" data-guida="cassa-allarme"' in s
    b = p['barra']
    assert 'data-tasto="precedente"' in b and 'href="/ieri"' in b and 'title="Giorno precedente"' in b and 'data-guida="barra"' in b
    assert 'aria-label' not in b, 'il passo non cambia il nome letto con un aria-label'
    assert '<label class="v-tendina"><select name="struttura">' in b
    li = p['linguette']
    assert 'aria-current="page"' in li and li.count('aria-current') == 1 and 'data-tasto="g"' in li and 'title="il giorno"' in li, 'linguette: aria-current, data-tasto, title: %s' % li
    assert 'aria-label="Viste"' in li and 'data-guida="linguetta-elenco"' in li and 'v-conta' in li
    st = p['stampa']
    for x in ('class="gruppo-comandi v-stampa"', 'class="v-bottone apri-gruppo"', 'aria-haspopup="true"',
              'aria-expanded="false"', 'class="tendina" role="menu"', 'target="_blank"', 'data-apri-schema'):
        assert x in st, 'manca %s in «Stampa e scarica»' % x
    assert 'Nascosta' not in st and '<small>il foglio</small>' in st
    assert p['euro'] == '<!--euro-->[1.250,50][—][915,00 €][]', p['euro']
    # le icone: nessuna vuota (un nome sconosciuto disegna un svg vuoto senza errore)
    icone = re.findall(r'<svg class="icona[^>]*>(.*?)</svg>', h)
    assert len(icone) >= 6, 'poche icone nei pezzi: %d' % len(icone)
    vuote = [i for i, x in enumerate(icone) if not x.strip()]
    assert not vuote, 'icone vuote (nome che non esiste in _icone.html): %d su %d' % (len(vuote), len(icone))
    return '12 pezzi'


def pz_pezzi():
    return controlla_pezzi()


def gemello_pezzi():
    assert 'aria-current' in cade(controlla_pezzi, cambia(PEZZI, 'v.accesa %} aria-current="page"{% endif %}', 'v.accesa %}{% endif %}'))
    assert 'icone vuote' in cade(controlla_pezzi, cambia(PEZZI, "{{ icona('chevron-down') }}</label>", "{{ icona('freccia-giu') }}</label>"))
    assert 'striscia' in cade(controlla_pezzi, cambia(PEZZI, '<ul class="v-striscia', '<div class="v-striscia'))
    assert 'gruppo-comandi' in cade(controlla_pezzi, cambia(PEZZI, 'class="gruppo-comandi v-stampa"', 'class="v-stampa"'))


def icone_usate(*testi):
    """I nomi delle icone scritti nei pezzi e nel catalogo: icona('nome') e gli argomenti icona…='nome'."""
    nomi = set()
    for t in testi:
        nomi |= set(re.findall(r"icona\('([a-z0-9-]+)'", t)) | set(re.findall(r"icona(?:_\w+)?\s*[=:]\s*'([a-z0-9-]+)'", t))
        nomi |= set(re.findall(r"'icona'\s*:\s*'([a-z0-9-]+)'", t))
    return nomi


def controlla_icone(*testi):
    disponibili = set(re.findall(r"'([a-z0-9-]+)': '", leggi('templates/_icone.html')))
    usate = icone_usate(*testi)
    mancano = sorted(usate - disponibili)
    assert not mancano, 'icone che _icone.html non ha (strumenti/genera_icone.py): %s' % mancano
    assert {'chevron-down', 'id-card'} <= disponibili, 'mancano le icone della veste nuova'
    return '%d icone usate' % len(usate)


def i_icone():
    return controlla_icone(PEZZI, CATALOGO)


def gemello_icone():
    assert 'freccia-giu' in cade(controlla_icone, PEZZI + "{{ icona('freccia-giu') }}")
    assert 'tessera' in cade(controlla_icone, CATALOGO + "{'testo': 'x', 'icona': 'tessera'}")


# ================================================================ euro(): uguale ai tre modi di oggi
MODI_DI_OGGI = (
    "{% macro cassa(c) %}{{ '{:,.2f}'.format(c / 100.0).replace(',', 'x').replace('.', ',').replace('x', '.') }}{% endmacro %}"
    "{% macro stat(c) %}{% if c %}{{ cassa(c) }}{% else %}—{% endif %}{% endmacro %}")


def controlla_euro(sorgente=None):
    env = jinja2.Environment(loader=jinja2.ChoiceLoader([jinja2.DictLoader({'_pezzi.html': sorgente or PEZZI}),
                                                         jinja2.FileSystemLoader(os.path.join(CARTELLA, 'templates'))]),
                             undefined=jinja2.StrictUndefined)
    env.filters['euro'] = importo_in_testo
    t = env.from_string("{% from '_pezzi.html' import euro %}" + MODI_DI_OGGI +
                        "{{ c|euro }}|{{ cassa(c) }}|{{ stat(c) }}|{{ euro(c) }}|{{ euro(c, se_zero='—') }}")
    r = random.Random(13)
    for c in [0, 1, -1, 99, 100, 12345, 125050, -125050, 10 ** 11] + [r.randint(-10 ** 9, 10 ** 9) for _ in range(3000)]:
        a, b, s, n1, n2 = t.render(c=c).split('|')
        assert a == b == n1 and s == n2, 'euro(%r): oggi %r / %r / %r, il pezzo %r / %r' % (c, a, b, s, n1, n2)
    assert env.from_string("{% from '_pezzi.html' import euro %}[{{ euro(None) }}][{{ euro(None, se_zero='—') }}]").render() == '[][—]'
    return '3009 importi'


def pz_euro():
    return controlla_euro()


def gemello_euro():
    cade(controlla_euro, cambia(PEZZI, '{{ se_zero }}', '-'))
    cade(controlla_euro, cambia(PEZZI, '{{ cent|euro }}', '{{ (cent or 0)|euro }}'))


# ================================================================ marchio.tema
def tema_di_sempre(colore):
    """Copia ferma delle cinque varianti di marchio.tema fino alla 1.12.7: non si tocca."""
    base = marchio.leggibile(colore) or '#154381'
    return {'primario': base, 'scuro': marchio.mescola(base, '#000000', 0.28), 'tenue': marchio.mescola(base, '#ffffff', 0.92),
            'chiaro': marchio.mescola(base, '#ffffff', 0.62), 'fuoco': marchio.mescola(base, '#ffffff', 0.25)}


def controlla_tema(tema, gettoni):
    for c in COLORI + [None, '', 'rosso', '#12345']:
        t, sempre = tema(c), tema_di_sempre(c)
        assert {k: t[k] for k in sempre} == sempre, 'marchio.tema(%r) cambia le varianti di sempre: %s' % (c, t)
        assert set(t) == set(sempre) | {'tinta', 'bordo', 'profondo', 'testo'}, sorted(t)
    chiaro, _ = L.gettoni_css(gettoni)
    fondi = tuple(chiaro['v-' + n].upper() for n in ('fondo', 'incasso', 'superficie'))
    assert tuple(x.upper() for x in marchio.FONDI_DEL_TESTO) == fondi, \
        'marchio.FONDI_DEL_TESTO %s, i gettoni %s' % (marchio.FONDI_DEL_TESTO, fondi)
    t = tema('#1C4184')
    assert (t['tinta'], t['bordo'], t['profondo']) == ('#e7edf9', '#bacced', '#112851'), t
    return '%d colori' % len(COLORI)


def m_tema():
    return controlla_tema(marchio.tema, GETTONI)


def gemello_tema():
    cade(controlla_tema, lambda c: dict(marchio.tema(c), scuro=marchio.mescola(marchio.tema(c)['primario'], '#000000', .3)), GETTONI)
    cade(controlla_tema, marchio.tema, cambia(GETTONI, '--v-incasso: #EEF2F8;', '--v-incasso: #E9EEF6;'))


# ================================================================ autoriparazione e programma installato
def controlla_risorse(cartella_static):
    vera = A.app.static_folder
    try:
        A.app.static_folder = cartella_static
        assert A.risorse_presenti(), 'con tutti i file risorse_presenti() dice che mancano'
        for nome in ('gettoni.css', 'veste.css', 'stile.css'):
            os.rename(os.path.join(cartella_static, nome), os.path.join(cartella_static, nome + '.via'))
            try:
                assert not A.risorse_presenti(), 'senza %s risorse_presenti() non se ne accorge' % nome
            finally:
                os.rename(os.path.join(cartella_static, nome + '.via'), os.path.join(cartella_static, nome))
    finally:
        A.app.static_folder = vera


def r_risorse():
    copia = tempfile.mkdtemp(prefix='static-', dir=PROVVISORIA)
    for nome in ('stile.css', 'gettoni.css', 'veste.css'):
        shutil.copy2(os.path.join(CARTELLA, 'static', nome), copia)
    controlla_risorse(copia)
    installato = leggi('strumenti/prove_installato.py')
    assert "'/static/gettoni.css'" in installato and "'/static/veste.css'" in installato, 'prove_installato.py non li chiede'
    return 'gettoni.css e veste.css'


def gemello_risorse():
    vecchie = A.RISORSE_DA_CONTROLLARE
    try:
        A.RISORSE_DA_CONTROLLARE = tuple(x for x in vecchie if x[1] != 'veste.css')
        assert 'veste.css' in cade(r_risorse)
    finally:
        A.RISORSE_DA_CONTROLLARE = vecchie


# ================================================================ il lanciatore lancia tutte le raccolte
def l_lanciatore():
    problemi = TP.fuori_elenco()
    assert not problemi, '; '.join(problemi)
    presenti = [n for n in TP.SENZA_BROWSER + TP.NEL_BROWSER if os.path.exists(os.path.join(CARTELLA, n))]
    assert {'prove_accessi.py', 'prove_menu.py', 'prove_mattoni.py'} <= set(TP.SENZA_BROWSER), TP.SENZA_BROWSER
    assert {'prove_accessi_browser.py', 'prove_cornice_browser.py'} <= set(TP.NEL_BROWSER), TP.NEL_BROWSER
    return '%d raccolte negli elenchi, %d aiuti fuori' % (len(presenti), len(TP.AIUTI))


def gemello_lanciatore():
    """Le righe dei due lati del conflitto dell'unione tolte una per volta, un aiuto tolto dal suo elenco, un nome in due
    elenchi; in una cartella finta, una raccolta nuova con un altro nome e un aiuto che scrive la riga finale."""
    senza, nel = TP.SENZA_BROWSER, TP.NEL_BROWSER
    for tolto in ('prove_accessi.py', 'prove_menu.py', 'campagna.py'):
        p = TP.fuori_elenco(senza_browser=[x for x in senza if x != tolto])
        assert any(x.startswith(tolto + ' non è') for x in p), (tolto, p)
    for tolto in ('prove_accessi_browser.py', 'prove_cornice_browser.py'):
        p = TP.fuori_elenco(nel_browser=[x for x in nel if x != tolto])
        assert any(x.startswith(tolto + ' non è') for x in p), (tolto, p)
    p = TP.fuori_elenco(aiuti=[x for x in TP.AIUTI if x != 'prove_gemelli.py'])
    assert any(x.startswith('prove_gemelli.py non è') for x in p), p
    p = TP.fuori_elenco(nel_browser=nel + ['prove_menu.py'])
    assert any('più di un elenco' in x for x in p), p
    finta = tempfile.mkdtemp(prefix='lanciatore-', dir=PROVVISORIA)
    for nome, testo in (('prove_a.py', "print('%d prove totali, %d superate, %d da sistemare')"),
                        ('verifica_b.py', "print('Nessun guasto')"), ('prove_aiuto.py', 'def aiuto(): pass'),
                        ('prove_c.py', "print('%d / %d' % (1, 1))"), ('prove_d.py', "print(sum(e), '/', len(e))"),
                        ('altro.py', 'x = 1')):
        with open(os.path.join(finta, nome), 'w', encoding='utf-8') as f:
            f.write(testo)
    p = TP.fuori_elenco(finta, ['prove_a.py'], ['prove_c.py', 'prove_d.py'], ['prove_aiuto.py'])
    assert p == ['verifica_b.py non è in SENZA_BROWSER né in NEL_BROWSER (né fra gli AIUTI): non si lancerebbe mai'], p
    p = TP.fuori_elenco(finta, ['prove_a.py', 'verifica_b.py', 'altro.py'], ['prove_d.py'], ['prove_c.py', 'prove_x.py'])
    assert sorted(p) == ['altro.py si lancia, ma non scrive la riga finale di una raccolta',
                         'prove_aiuto.py non è in SENZA_BROWSER né in NEL_BROWSER (né fra gli AIUTI): non si lancerebbe mai',
                         'prove_c.py è fra gli aiuti, ma scrive la riga finale di una raccolta',
                         'prove_x.py è fra gli aiuti, ma nella cartella non c\'è'], p


prova('gettoni: contrasto almeno 4,5:1 di ogni coppia testo/fondo, in chiaro e in scuro, per ogni colore della struttura', g_contrasti)
prova('gemello: un testo chiaro, il premuto schiarito in scuro e un colore senza coppia fanno cadere i contrasti', gemello_contrasti)
prova('gettoni: il contorno del fuoco della tastiera almeno 3:1 sui fondi del menu e delle linguette, per ogni colore', g_contorni)
prova('gemello: il contorno di prima (il colore con un quarto di bianco) con un verde scende sotto 3:1', gemello_contorni)
prova('gettoni: ogni colore ha il suo valore scuro, solo a schermo', g_scuro)
prova('gemello: un valore scuro tolto, il tema scuro anche in stampa', gemello_scuro)
prova('nessun colore scritto a mano nei file nuovi (veste.css, _pezzi.html, catalogo, testa di base.html)', g_colori)
prova('gemello: un colore a mano in ogni file nuovo si vede, anche con un nome (teal, crimson, gold); nei commenti e nel testo no', gemello_colori)
prova('strato: fogli di oggi in @layer vecchio nell\'ordine di ogni variante, :root dentro, gettoni e veste fuori, fogli da stampare come prima', s_strato)
prova('gemello: :root fuori, sotto-strati, ordine dell\'animata, veste nello strato, fogli nuovi nella carta', gemello_strato)
prova('prefisso: solo classi v- in veste.css, nessuna classe di oggi pestata, nessun selettore senza un pezzo v-', p_prefisso)
prova('gemello: classe senza prefisso, elemento nudo, classe v- già usata, .v- solo dentro :not() o in una scelta di :where()', gemello_prefisso)
prova('pezzi con le variabili rigide: agganci di JavaScript, guida e prove, testo letto, icone non vuote', pz_pezzi)
prova('gemello: aria-current tolto, icona che non esiste, striscia senza ul, tendina senza gruppo-comandi', gemello_pezzi)
prova('icone dei pezzi e del catalogo tutte in _icone.html (chevron-down e id-card comprese)', i_icone)
prova('gemello: un\'icona che non esiste nei pezzi e nel catalogo', gemello_icone)
prova('euro() uguale ai tre modi di oggi, carattere per carattere', pz_euro)
prova('gemello: euro() con lo zero sbagliato o senza il vuoto per None', gemello_euro)
prova('marchio.tema: le cinque varianti di sempre ferme, quattro nuove, fondi chiari uguali ai gettoni', m_tema)
prova('gemello: una variante di sempre cambiata, un fondo dei gettoni diverso', gemello_tema)
prova('autoriparazione: risorse_presenti() controlla gettoni.css e veste.css; prove_installato.py li chiede', r_risorse)
prova('gemello: senza veste.css nell\'elenco l\'autoriparazione non se ne accorgerebbe', gemello_risorse)
prova('lanciatore: ogni raccolta della cartella è in SENZA_BROWSER o in NEL_BROWSER, gli aiuti a parte', l_lanciatore)
prova('gemello: una riga tolta da un elenco (prove_accessi, prove_menu…), un aiuto tolto, un nome in due elenchi, una raccolta '
      'con un altro nome, un aiuto con la riga finale', gemello_lanciatore)

shutil.rmtree(PROVVISORIA, ignore_errors=True)
for esito, nome, dettaglio in esiti:
    print('%-6s %s %s' % (esito, nome, dettaglio))
rotte = [e for e in esiti if e[0] != 'OK']
print('%d prove totali, %d superate, %d da sistemare' % (len(esiti), len(esiti) - len(rotte), len(rotte)))
sys.exit(1 if rotte else 0)
