"""Genera static/tema-scuro.css da static/stile.css.

Ogni regola di stile.css che ha un colore diventa una regola "html.scuro ..."
con il colore girato per il fondo scuro: i fondi chiari diventano scuri, il
testo scuro diventa chiaro, la tinta resta la stessa (il verde degli arrivati
resta verde, il rosso dei disdetti resta rosso). In fondo al file si aggiungono
le correzioni a mano. Si rilancia dopo ogni modifica dei colori di stile.css:

    python strumenti/genera_tema_scuro.py
"""
import colorsys
import os
import re

CARTELLA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORGENTE = os.path.join(CARTELLA, 'static', 'stile.css')
DESTINAZIONE = os.path.join(CARTELLA, 'static', 'tema-scuro.css')

FONDO = ('background', 'background-color')
TESTO = ('color',)
BORDI = ('border', 'border-top', 'border-bottom', 'border-left', 'border-right', 'border-color',
         'border-left-color', 'border-bottom-color', 'outline', 'box-shadow', 'text-decoration-color')


def esadecimale(h):
    h = h.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def in_esadecimale(rgb):
    return '#%02X%02X%02X' % tuple(max(0, min(255, round(x * 255))) for x in rgb)


# i grigi della pagina hanno un corrispondente fisso, cosi' le superfici sono una famiglia sola
FISSI = {
    'fondo': {'#FFFFFF': '#1C242D', '#F4F5F3': '#141A21', '#F0F1EE': '#222B35', '#EEF0EE': '#222B35',
              '#EEF1F2': '#222B35', '#E9EAE7': '#222B35', '#E8ECEF': '#232C36', '#F4F7FB': '#202A35',
              '#E4E8EA': '#10151B', '#EEF3FA': '#22303F'},
    'testo': {'#16263F': '#E1E7ED', '#46596A': '#A9B7C4', '#5B6B75': '#9AA8B4', '#6A7A84': '#8C9AA6',
              '#8C979E': '#7F8C97', '#4B606D': '#A2B0BC', '#7A8790': '#8795A0', '#93A3AE': '#7C8A96'},
    'bordo': {'#CFD5D8': '#2E3843', '#B8C0C4': '#45525F', '#E4E8EA': '#28313B', '#9AA5AB': '#56636F',
              '#C9D2DE': '#34414F', '#FFFFFF': '#FFFFFF'},
}


def gira(h, ruolo):
    chiave = '#' + ''.join(c * 2 for c in h.lstrip('#')).upper() if len(h) == 4 else h.upper()
    if chiave in FISSI[ruolo]:
        return FISSI[ruolo][chiave]
    r, g, b = esadecimale(h)
    hh, l, s = colorsys.rgb_to_hls(r, g, b)
    if ruolo == 'fondo':
        if l > .9:                      # bianchi e grigi chiarissimi: superfici
            l2 = .12 + (1 - l) * .9
            s = min(s, .18)
        elif l > .6:                    # fondi tenui colorati (verdi, gialli, rosa)
            l2 = .16 + (1 - l) * .25
            s = min(s, .45)
        else:                           # fondi pieni (pulsanti verdi, rossi): restano, un po' piu' spenti
            l2 = max(l * .9, .22)
    elif ruolo == 'testo':
        if l > .85:
            return h                    # testo bianco su fondo colorato: resta bianco
        l2 = .92 - l * .45 if l < .45 else max(l, .72)
        s = min(s, .6)
    else:                               # bordi e ombre
        if l > .55:
            l2 = .22 + (1 - l) * .35
            s = min(s, .25)
        else:
            l2 = min(.7, l + .25)
    return in_esadecimale(colorsys.hls_to_rgb(hh, l2, s))


def converti(valore, ruolo):
    return re.sub(r'#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b', lambda m: gira(m.group(0), ruolo), valore)


def regole(css):
    """(selettori, dichiarazioni, @media) per le regole semplici; i @media
    di stampa e le animazioni si saltano."""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    i, n, fuori = 0, len(css), []
    pila = []
    corrente = ''
    while i < n:
        c = css[i]
        if c == '{':
            testa = corrente.strip()
            corrente = ''
            if testa.startswith('@'):
                pila.append(testa)
            else:
                j = css.index('}', i)
                corpo = css[i + 1:j]
                fuori.append((testa, corpo, pila[-1] if pila else ''))
                i = j + 1
                continue
        elif c == '}':
            if pila:
                pila.pop()
            corrente = ''
        else:
            corrente += c
        i += 1
    return fuori


def main():
    css = open(SORGENTE, encoding='utf-8').read()
    uscita = ['/* GENERATO da strumenti/genera_tema_scuro.py partendo da stile.css: non modificare a mano',
              '   la parte generata; le correzioni stanno in fondo. Vale solo sullo schermo. */',
              '@media screen {']
    for selettori, corpo, media in regole(css):
        if media and ('print' in media or 'keyframes' in media or 'reduced-motion' in media):
            continue
        nuove = []
        for d in corpo.split(';'):
            if ':' not in d:
                continue
            prop, val = d.split(':', 1)
            prop, val = prop.strip().lower(), val.strip()
            if not re.search(r'#[0-9A-Fa-f]{3,6}\b', val):
                continue
            ruolo = 'fondo' if prop in FONDO else 'testo' if prop in TESTO else 'bordo' if prop in BORDI else None
            if ruolo is None:
                continue
            nuove.append('%s: %s' % (prop, converti(val, ruolo)))
        if nuove:
            sel = ', '.join('html.scuro ' + x.strip() if not x.strip().startswith('body') else
                            'html.scuro ' + x.strip() for x in selettori.split(','))
            riga = '  %s { %s; }' % (sel, '; '.join(nuove))
            if media and 'print' not in media:
                riga = '  %s { %s }' % (media, riga.strip())
            uscita.append(riga)
    uscita.append('}')
    uscita.append(open(os.path.join(CARTELLA, 'strumenti', 'tema-scuro-correzioni.css'), encoding='utf-8').read())
    open(DESTINAZIONE, 'w', encoding='utf-8').write('\n'.join(uscita) + '\n')
    print('scritto', DESTINAZIONE, len(uscita), 'righe')


if __name__ == '__main__':
    main()
