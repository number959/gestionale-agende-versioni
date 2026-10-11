# -*- coding: utf-8 -*-
"""Scrive templates/_icone.html, le icone del programma come macro Jinja, a
partire dalle SVG di Lucide (https://lucide.dev, licenza ISC; le icone
derivate da Feather sono MIT): solo quelle elencate qui sotto, dentro il
programma, niente da scaricare quando gira.

    npm pack lucide-static@1.55.0        (o la versione nuova)
    tar xzf lucide-static-*.tgz
    python strumenti/genera_icone.py package/icons

Nelle pagine: {% from "_icone.html" import icona %} ... {{ icona('moon') }}.
La licenza di Lucide e' in static/icone/LICENZE.txt (va tenuta)."""
import os
import re
import sys

QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONE = [
    # ruoli del personale
    'stethoscope', 'heart-pulse', 'hand-heart', 'microscope', 'clipboard-list', 'spray-can', 'users',
    # viste e comandi dei turni
    'calendar-days', 'calendar-range', 'clock', 'user-plus', 'settings-2', 'copy', 'repeat', 'printer',
    'file-spreadsheet', 'chevron-left', 'chevron-right', 'x', 'trash-2', 'eraser', 'triangle-alert', 'info',
    'check', 'keyboard', 'plus', 'funnel', 'calendar-clock', 'wand-sparkles', 'square-pen',
    # tipi di turno
    'sun', 'sunset', 'moon', 'phone-call', 'tree-palm', 'thermometer', 'coffee', 'bed',
]


def main():
    if len(sys.argv) != 2 or not os.path.isdir(sys.argv[1]):
        print(__doc__)
        return 2
    cartella = sys.argv[1]
    voci = []
    for nome in ICONE:
        testo = open(os.path.join(cartella, nome + '.svg'), encoding='utf-8').read()
        corpo = re.search(r'<svg[^>]*>(.*)</svg>', testo, re.S).group(1)
        corpo = ''.join(x.strip() for x in corpo.splitlines() if x.strip())
        corpo = re.sub(r'\s*/>', '/>', corpo)
        voci.append("  '%s': '%s'," % (nome, corpo.replace("'", "\\'")))
    versione = re.search(r'lucide-static v([\d.]+)', open(os.path.join(cartella, ICONE[0] + '.svg')).read())
    uscita = """{#- Icone di Lucide (lucide.dev) v%s, licenza ISC (vedi static/icone/LICENZE.txt).
    Scritto da strumenti/genera_icone.py: non modificare a mano.
    icona(nome, classe, titolo): l'SVG in linea, del colore del testo intorno;
    senza titolo e' decorativa (aria-hidden), con il titolo la legge il lettore di schermo. -#}
{%%- set _icone = {
%s
} -%%}
{%%- macro icona(nome, classe='', titolo=none) -%%}
<svg class="icona {{ classe }}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" {%%- if titolo %%} role="img" aria-label="{{ titolo }}"{%%- else %%} aria-hidden="true" focusable="false"{%%- endif %%}>{%%- if titolo %%}<title>{{ titolo }}</title>{%%- endif %%}{{ _icone.get(nome, '')|safe }}</svg>
{%%- endmacro -%%}
""" % (versione.group(1) if versione else '?', '\n'.join(voci))
    destinazione = os.path.join(QUI, 'templates', '_icone.html')
    with open(destinazione, 'w', encoding='utf-8', newline='\n') as f:
        f.write(uscita)
    print('scritto %s: %d icone' % (destinazione, len(ICONE)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
