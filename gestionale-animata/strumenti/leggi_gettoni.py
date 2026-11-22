# -*- coding: utf-8 -*-
"""I gettoni di static/gettoni.css letti come li legge il browser (tappa 1-bis della veste nuova, 22/11/2026): per le
prove (prove_mattoni.py) e per il catalogo dei pezzi (strumenti/catalogo_pezzi.py).

Per un colore della struttura e un tema (chiaro o scuro) si mettono insieme, nell'ordine in cui valgono nella pagina:
- le varianti del colore che base.html scrive nello strato «vecchio» (--primario: {{ tema.primario }}…, marchio.tema);
- in scuro, le varianti scure di tema-scuro.css (html.scuro { --primario-scuro: color-mix(…) … });
- i gettoni di gettoni.css (:root), e in scuro quelli di html.scuro.
Poi ogni gettone si risolve fino al colore: var(--x), var(--x, ripiego), color-mix(in srgb, A P%, B) e #rrggbb.

COPPIE sono le coppie testo/fondo che i pezzi di veste.css usano davvero (dove: il pezzo): tutte devono avere almeno
4,5:1, in chiaro e in scuro, anche per i colori della struttura. Una regola nuova di veste.css con un colore di testo
nuovo aggiunge qui la sua coppia (prove_mattoni.py controlla che ogni colore di testo di veste.css ne abbia una)."""
import colorsys
import os
import re

CARTELLA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (testo, fondo, dove): i nomi dei gettoni senza «--v-»
COPPIE = [
    ('testo', 'fondo', 'testo della pagina'), ('testo', 'superficie', 'schede, campi, bottoni'),
    ('testo', 'superficie-tenue', 'menu laterale'), ('testo', 'incasso', 'riga del totale'),
    ('testo-medio', 'superficie', 'celle delle tabelle'), ('testo-medio', 'incasso', 'intestazioni, linguette non scelte'),
    ('testo-medio', 'fondo', 'etichette fuori dalle schede'), ('testo-tenue', 'superficie', 'righe piccole, sottotitoli delle schede'),
    ('testo-tenue', 'fondo', 'sopratitolo e sottotitolo della pagina'), ('testo-tenue', 'incasso', 'righe spente sul totale'),
    ('testo-tenue', 'superficie-tenue', 'righe piccole del menu'), ('testo-tenue', 'chiuso', 'pillola Disdetto, bottone spento'),
    ('verde-testo', 'occupato', 'pillola Arrivato'), ('verde-testo', 'arrivato', 'arrivato nella griglia'),
    ('verde', 'superficie', '✓ di confermato'), ('confermato-testo', 'confermato', 'pillola Confermato'),
    ('rosso', 'rosso-fondo', 'pillola Non presentato'), ('rosso', 'superficie', 'bottone pericolo, numero in allarme'),
    ('rosso-forte', 'rosso-fondo', 'riquadro di errore'), ('avviso-testo', 'avviso-fondo', 'riquadro di avviso'),
    ('avviso-testo', 'sabbia', 'scheda «Da confermare»'), ('ok-testo', 'ok-fondo', 'riquadro ok'),
    ('sala-testo', 'sala-fondo', 'pillola della Sala'), ('testo', 'disponibile', 'stanza senza medico'),
    ('testo-su-pieno', 'verde-pieno', 'targhetta «arrivato 10:21»'), ('testo-su-pieno', 'rosso-pieno', 'segno rosso pieno'),
    ('testo-su-pieno', 'sala-pieno', 'segno della Sala'),
    # quelle che dipendono dal colore della struttura
    ('testo-su-pieno', 'primario', 'bottone principale, contatore'),
    ('testo-su-pieno', 'primario-premuto', 'bottone principale sotto il mouse'),
    ('primario-testo', 'primario-tinta', 'linguetta accesa'), ('primario-testo', 'incasso', 'linguetta sotto il mouse'),
    ('primario-testo', 'superficie', 'bottone sotto il mouse'), ('collegamento', 'fondo', 'collegamenti nella pagina'),
    ('collegamento', 'superficie', 'collegamenti nelle schede'), ('testo', 'primario-tinta', 'voce della tendina sotto il mouse'),
    ('testo-medio', 'primario-tinta', 'riga piccola della voce sotto il mouse'),
    # la cornice (tappa 2): voci del menu, voce accesa e sotto il mouse, percorso e ricerca della barra in alto
    ('testo-medio', 'superficie-tenue', 'voci del menu'), ('primario-testo', 'superficie-tenue', 'voce del menu accesa, iniziali'),
]

# i colori della struttura su cui si provano le coppie: il predefinito, quello delle tavole, quelli delle prove, alcuni
# al limite (chiari, grigi, gialli) e una griglia di tinte; il programma li passa da marchio.leggibile() (marchio.tema)
COLORI_DI_PROVA = ['#154381', '#1C4184', '#6b4e9b', '#2e7d32', '#767676', '#0087B4', '#5B7F3E', '#C62828', '#FFD700',
                   '#00A0A0', '#FFFFFF', '#000000']


def griglia_di_colori():
    uscita = []
    for h in range(0, 360, 10):
        for s in (.35, .6, .9):
            for luce in (.3, .45, .6, .8):
                uscita.append('#%02X%02X%02X' % tuple(round(x * 255) for x in colorsys.hls_to_rgb(h / 360, luce, s)))
    return uscita


def leggi(rel, cartella=None):
    with open(os.path.join(cartella or CARTELLA, rel), encoding='utf-8') as f:
        return f.read()


def senza_commenti(css):
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


def dichiarazioni(corpo):
    """{nome: valore} delle variabili (--nome: valore;) di un blocco."""
    return {n: v.strip() for n, v in re.findall(r'--([\w-]+)\s*:\s*([^;]+);', corpo)}


def gettoni_css(testo):
    """(chiaro, scuro) di gettoni.css: le dichiarazioni di :root e quelle di html.scuro dentro @media screen."""
    css = senza_commenti(testo)
    radice = re.search(r':root\s*\{([^}]*)\}', css)
    scuro = re.search(r'@media\s+screen\s*\{\s*html\.scuro\s*\{([^}]*)\}', css)
    return dichiarazioni(radice.group(1)) if radice else {}, dichiarazioni(scuro.group(1)) if scuro else {}


def primario_scuro(testo_tema_scuro):
    """Le varianti scure del colore della struttura in tema-scuro.css (html.scuro { --primario-…: … })."""
    uscita = {}
    for corpo in re.findall(r'html\.scuro\s*\{([^}]*)\}', senza_commenti(testo_tema_scuro)):
        uscita.update({n: v for n, v in dichiarazioni(corpo).items() if n.startswith('primario')})
    return uscita


def variabili_della_struttura(testo_base):
    """{variabile: chiave di marchio.tema} come le scrive base.html nello strato (--primario-tinta: {{ tema.tinta }})."""
    strato = re.search(r'@layer vecchio \{ :root \{(.*?)\} \}', testo_base, re.S)
    return dict(re.findall(r'--([\w-]+):\s*\{\{\s*tema\.(\w+)\s*\}\}', strato.group(1))) if strato else {}


def _rgb(c):
    c = c.strip()
    if re.fullmatch(r'#[0-9A-Fa-f]{3}', c):
        c = '#' + ''.join(x * 2 for x in c[1:])
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def _esa(t):
    return '#%02X%02X%02X' % tuple(max(0, min(255, round(x))) for x in t)


def _argomenti(testo):
    """Gli argomenti di una funzione CSS separati dalle virgole di primo livello."""
    parti, livello, corrente = [], 0, ''
    for c in testo:
        if c == ',' and not livello:
            parti.append(corrente.strip())
            corrente = ''
            continue
        livello += (c == '(') - (c == ')')
        corrente += c
    return parti + [corrente.strip()]


class Valori:
    """I gettoni di una pagina per un colore della struttura e un tema; risolve(nome) dà il colore #RRGGBB (o None)."""

    def __init__(self, colore, tema, gettoni=None, tema_scuro=None, base=None, cartella=None):
        import marchio
        cartella = cartella or CARTELLA
        gettoni = gettoni if gettoni is not None else leggi(os.path.join('static', 'gettoni.css'), cartella)
        tema_scuro = tema_scuro if tema_scuro is not None else leggi(os.path.join('static', 'tema-scuro.css'), cartella)
        base = base if base is not None else leggi(os.path.join('templates', 'base.html'), cartella)
        t = marchio.tema(colore)
        self.v = {n: t[k] for n, k in variabili_della_struttura(base).items()}
        chiaro, scuro = gettoni_css(gettoni)
        if tema == 'scuro':
            self.v.update(primario_scuro(tema_scuro))
        self.v.update(chiaro)
        if tema == 'scuro':
            self.v.update(scuro)

    def risolvi(self, nome, giro=0):
        valore = self.v.get(nome)
        return None if valore is None or giro > 20 else self.valuta(valore, giro + 1)

    def valuta(self, valore, giro=0):
        valore = valore.strip()
        if re.fullmatch(r'#[0-9A-Fa-f]{3}|#[0-9A-Fa-f]{6}', valore):
            return _esa(_rgb(valore))
        m = re.fullmatch(r'var\(\s*--([\w-]+)\s*(?:,(.*))?\)', valore, re.S)
        if m:
            trovato = self.risolvi(m.group(1), giro)
            return trovato if trovato is not None or m.group(2) is None else self.valuta(m.group(2), giro)
        m = re.fullmatch(r'color-mix\(\s*in\s+srgb\s*,(.*)\)', valore, re.S)
        if m:
            (a, pa), (b, pb) = [(re.sub(r'\s+\d+(\.\d+)?%$', '', x).strip(), re.search(r'(\d+(?:\.\d+)?)%$', x))
                                for x in _argomenti(m.group(1))]
            ca, cb = self.valuta(a, giro), self.valuta(b, giro)
            if ca is None or cb is None:
                return None
            qa = float(pa.group(1)) / 100 if pa else (1 - float(pb.group(1)) / 100 if pb else .5)
            return _esa(tuple(x * qa + y * (1 - qa) for x, y in zip(_rgb(ca), _rgb(cb))))
        return None


def contrasti(colore, tema, coppie=COPPIE, **kw):
    """[(testo, fondo, dove, contrasto)] delle coppie per un colore della struttura e un tema."""
    import marchio
    v = Valori(colore, tema, **kw)
    uscita = []
    for testo, fondo, dove in coppie:
        a, b = v.risolvi('v-' + testo), v.risolvi('v-' + fondo)
        uscita.append((testo, fondo, dove, marchio.contrasto(a, b) if a and b else None))
    return uscita
