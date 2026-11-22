# -*- coding: utf-8 -*-
"""Prove dei mattoni della veste nuova (tappa 1-bis), senza browser: gettoni, strato, prefisso, pezzi.
(Bozza: nel programma userà prova() e mondo() come le altre raccolte; qui gira da sola.)

    python prove_mattoni.py                  # sulla cartella del programma
    python prove_mattoni.py --bozze CARTELLA # templates/ e static/ presi prima da CARTELLA"""
import glob
import os
import random
import re
import sys

CARTELLA = os.environ.get('GESTIONALE_CARTELLA') or os.path.dirname(os.path.abspath(__file__))
BOZZE = sys.argv[sys.argv.index('--bozze') + 1] if '--bozze' in sys.argv else None
sys.path.insert(0, CARTELLA)
os.chdir(CARTELLA)
import marchio  # noqa: E402
from modelli import importo_in_testo  # noqa: E402


def file_(rel):
    if BOZZE and os.path.exists(os.path.join(BOZZE, rel)):
        return os.path.join(BOZZE, rel)
    return os.path.join(CARTELLA, rel)


def leggi(rel):
    return open(file_(rel), encoding='utf-8').read()


def senza_commenti(css):
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


esiti = []


def prova(nome, f):
    try:
        f()
        esiti.append(('ok', nome, ''))
    except AssertionError as e:
        esiti.append(('NO', nome, str(e)))


# ------------------------------------------------------------------ gettoni
COPPIE = [('testo', 'fondo'), ('testo', 'superficie'), ('testo', 'superficie-tenue'), ('testo', 'incasso'),
          ('testo-medio', 'superficie'), ('testo-medio', 'incasso'), ('testo-medio', 'fondo'),
          ('testo-tenue', 'superficie'), ('testo-tenue', 'fondo'), ('testo-tenue', 'incasso'),
          ('testo-tenue', 'superficie-tenue'), ('testo-tenue', 'chiuso'),
          ('verde-testo', 'occupato'), ('verde-testo', 'arrivato'), ('verde', 'superficie'),
          ('confermato-testo', 'confermato'), ('rosso', 'rosso-fondo'), ('rosso', 'superficie'),
          ('rosso-forte', 'rosso-fondo'), ('avviso-testo', 'avviso-fondo'), ('avviso-testo', 'sabbia'),
          ('ok-testo', 'ok-fondo'), ('sala-testo', 'sala-fondo'), ('testo', 'disponibile'),
          ('testo-su-pieno', 'verde-pieno'), ('testo-su-pieno', 'rosso-pieno'), ('testo-su-pieno', 'sala-pieno')]


def gettoni():
    css = senza_commenti(leggi('static/gettoni.css'))
    chiaro = dict(re.findall(r'--v-([\w-]+):\s*(#[0-9A-Fa-f]{6})\s*;', css[css.index(':root'):css.index('@media screen')]))
    scuro = dict(chiaro)
    scuro.update(re.findall(r'--v-([\w-]+):\s*(#[0-9A-Fa-f]{6})\s*;', css[css.index('html.scuro'):]))
    return chiaro, scuro


def g_contrasti():
    chiaro, scuro = gettoni()
    male = []
    for t, f in COPPIE:
        for tema, v in (('chiaro', chiaro), ('scuro', scuro)):
            x = marchio.contrasto(v[t], v[f])
            if x < 4.5:
                male.append('%s/%s in %s: %.2f' % (t, f, tema, x))
    assert not male, male


def g_ogni_gettone_ha_lo_scuro():
    css = senza_commenti(leggi('static/gettoni.css'))
    chiaro = set(re.findall(r'--v-([\w-]+):\s*#', css[:css.index('@media screen')]))
    scuro = set(re.findall(r'--v-([\w-]+):', css[css.index('html.scuro'):]))
    # chi ha lo stesso valore nei due temi lo dice qui, una volta sola
    uguali = {'testo-su-pieno'} if 'testo-su-pieno' not in scuro else set()
    assert not (chiaro - scuro - uguali), 'gettoni senza valore scuro: %s' % sorted(chiaro - scuro - uguali)
    assert '@media screen' in css and 'html.scuro' in css


def g_nessun_colore_a_mano():
    """I colori stanno solo in gettoni.css (e nei fogli di oggi): veste.css, _pezzi.html e i modelli nuovi usano var()."""
    colore = re.compile(r'#[0-9A-Fa-f]{3,8}\b|\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklch|color-mix)\(|'
                        r'(?<![-\w])(?:white|black|red|blue|green|gray|grey|navy|silver)(?![-\w])', re.I)
    male = []
    for rel in ('static/veste.css', 'templates/_pezzi.html'):
        testo = senza_commenti(leggi(rel)) if rel.endswith('.css') else re.sub(r'\{#.*?#\}', '', leggi(rel), flags=re.S)
        male += ['%s: %s' % (rel, m.group(0)) for m in colore.finditer(testo)]
    assert not male, male


# ------------------------------------------------------------------ strato e base.html
def s_base_html():
    import app as A
    from jinja2 import ChoiceLoader, FileSystemLoader
    if BOZZE:
        A.app.jinja_loader = ChoiceLoader([FileSystemLoader(os.path.join(BOZZE, 'templates')), A.app.jinja_loader])
        A.app.jinja_env.cache = {}
    import seed
    import tempfile
    A.Sessione = seed.popola('sqlite:///' + os.path.join(tempfile.mkdtemp(), 'mattoni.db'))
    A._registro = None
    with A.app.test_request_context('/'):
        from flask import render_template_string
        pagina = render_template_string('{% extends "base.html" %}{% block menu %}{% endblock %}')
        carta = render_template_string('{% extends "base.html" %}{% set foglio_carta = true %}{% block menu %}{% endblock %}')
        animata = render_template_string('{% extends "base.html" %}{% block menu %}{% endblock %}', variante='animata')
        carta_animata = render_template_string('{% extends "base.html" %}{% set foglio_carta = true %}{% block menu %}{% endblock %}',
                                               variante='animata')
    fogli = lambda h: re.findall(r'<link rel="stylesheet" href="/static/([\w.-]+)">', h)
    strato = lambda h: re.findall(r'@import url\("/static/([\w.-]+)"\) layer\(vecchio\);', h)
    # le pagine: i fogli di oggi nello strato, nell'ordine di oggi; poi gettoni e veste fuori
    assert strato(pagina) == ['stile.css', 'tema-scuro.css'] and fogli(pagina) == ['gettoni.css', 'veste.css'], (strato(pagina), fogli(pagina))
    assert strato(animata) == ['stile.css', 'animazioni.css', 'tema-scuro.css'], strato(animata)
    assert "classList.add('anim')" in animata and "classList.add('anim')" not in pagina
    assert pagina.index('@layer vecchio;') < pagina.index('@import'), 'lo strato si dichiara prima degli @import'
    # i fogli da stampare: come prima, senza strato e senza i fogli nuovi
    assert fogli(carta) == ['stile.css', 'tema-scuro.css'] and not strato(carta), fogli(carta)
    assert fogli(carta_animata) == ['stile.css', 'animazioni.css', 'tema-scuro.css'], fogli(carta_animata)
    # il colore della struttura sta nello strato (fuori, in scuro vincerebbe su tema-scuro.css: collegamenti blu scuro)
    assert re.search(r'<style>@layer vecchio \{ :root \{ --primario:', pagina), 'il :root della struttura è fuori dallo strato'
    assert re.search(r'<style>:root \{ --primario:', carta)
    # l'ordine: strato prima, poi gettoni e veste
    assert pagina.index('tema-scuro.css') < pagina.index('@layer vecchio {') < pagina.index('gettoni.css') < pagina.index('veste.css')


# ------------------------------------------------------------------ prefisso: i nomi nuovi non pestano quelli vecchi
TENUTE = {'primario', 'gruppo-comandi', 'apri-gruppo', 'tendina'}   # agganci del JavaScript di oggi


def classi_vecchie():
    classi = set()
    for f in glob.glob(os.path.join(CARTELLA, 'static', '*.css')):
        if os.path.basename(f) in ('veste.css', 'gettoni.css', 'vecchio.css'):
            continue
        classi |= set(re.findall(r'\.([a-zA-Z_][\w-]*)', senza_commenti(open(f, encoding='utf-8').read())))
    for f in glob.glob(os.path.join(CARTELLA, 'templates', '*.html')):
        if os.path.basename(f) == '_pezzi.html':
            continue
        for m in re.finditer(r'class="([^"]*)"', open(f, encoding='utf-8').read()):
            classi |= {c for c in re.split(r'\s+', re.sub(r'\{[{%].*?[}%]\}', ' ', m.group(1))) if c}
    for f in glob.glob(os.path.join(CARTELLA, 'static', '*.js')):
        t = open(f, encoding='utf-8').read()
        classi |= set(re.findall(r"classList\.(?:add|remove|toggle|contains)\('([\w-]+)'", t))
    return classi


def p_prefisso():
    css = senza_commenti(leggi('static/veste.css'))
    usate = set(re.findall(r'\.([a-zA-Z_][\w-]*)', re.sub(r'url\([^)]*\)|\d+\.\d+', '', css)))
    senza = sorted(c for c in usate if not c.startswith('v-') and c not in TENUTE)
    assert not senza, 'classi senza il prefisso v-: %s' % senza
    vecchie = classi_vecchie()
    pestate = sorted(c for c in usate if c.startswith('v-') and c in vecchie)
    assert not pestate, 'classi v- già usate dalle pagine di oggi: %s' % pestate
    assert not any(c.startswith('v-') for c in vecchie), sorted(c for c in vecchie if c.startswith('v-'))
    # e nessuna regola su un elemento nudo (body, a, input...) che cambierebbe le pagine di oggi
    for regola in re.findall(r'([^{}]+)\{', re.sub(r'@[\w-]+[^{;]*\{', '{', css)):   # senza le righe @media
        for sel in re.split(r',(?![^(]*\))', regola):     # le virgole dentro :is(...) non separano
            sel = sel.strip()
            if sel and not sel.startswith(('from', 'to')) and not re.match(r'^\d', sel):
                assert '.v-' in sel, 'selettore senza un pezzo v-: %r' % sel


# ------------------------------------------------------------------ pezzi
def pz_euro():
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
    cartelle = ([os.path.join(BOZZE, 'templates')] if BOZZE else []) + [os.path.join(CARTELLA, 'templates')]
    env = Environment(loader=FileSystemLoader(cartelle), undefined=StrictUndefined)
    env.filters['euro'] = importo_in_testo
    t = env.from_string(
        "{% from '_pezzi.html' import euro %}"
        "{% macro cassa(c) %}{{ '{:,.2f}'.format(c / 100.0).replace(',', 'x').replace('.', ',').replace('x', '.') }}{% endmacro %}"
        "{% macro stat(c) %}{% if c %}{{ cassa(c) }}{% else %}—{% endif %}{% endmacro %}"
        "{{ c|euro }}|{{ cassa(c) }}|{{ stat(c) }}|{{ euro(c) }}|{{ euro(c, se_zero='—') }}")
    r = random.Random(13)
    for c in [0, 1, -1, 99, 100, 12345, 125050, -125050] + [r.randint(-10 ** 9, 10 ** 9) for _ in range(3000)]:
        a, b, s, n1, n2 = t.render(c=c).split('|')
        assert a == b == n1 and s == n2, (c, a, b, s, n1, n2)
    assert env.from_string("{% from '_pezzi.html' import euro %}[{{ euro(None) }}][{{ euro(None, se_zero='—') }}]").render() == '[][—]'


def pz_agganci():
    """I pezzi tengono gli agganci del JavaScript di oggi (gestionale.js:531, 714; guida.js:130)."""
    t = leggi('templates/_pezzi.html')
    for x in ('class="gruppo-comandi', 'apri-gruppo', 'class="tendina" role="menu"', 'aria-haspopup="true"',
              'aria-expanded="false"', 'aria-current="page"', 'data-tasto', 'data-guida'):
        assert x in t, x


for nome, f in [('gettoni: contrasti testo/fondo almeno 4,5:1 in chiaro e in scuro', g_contrasti),
                ('gettoni: ogni colore ha il suo valore scuro, solo sullo schermo', g_ogni_gettone_ha_lo_scuro),
                ('gettoni: nessun colore scritto a mano in veste.css e _pezzi.html', g_nessun_colore_a_mano),
                ('strato: base.html, fogli di oggi nello strato nell\'ordine di ogni variante, fogli da stampare come prima, :root nello strato', s_base_html),
                ('prefisso: classi v- che non pestano le vecchie, nessun elemento nudo', p_prefisso),
                ('pezzi: euro() uguale ai tre modi di oggi', pz_euro),
                ('pezzi: agganci di JavaScript, guida e prove', pz_agganci)]:
    prova(nome, f)
for e, n, d in esiti:
    print('%-3s %s%s' % (e, n, ('\n      ' + d[:600]) if d else ''))
sys.exit(1 if any(e == 'NO' for e, _, _ in esiti) else 0)
