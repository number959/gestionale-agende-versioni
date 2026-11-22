# Quali icone usano le tavole nella cornice: confronto delle SVG con il pacchetto Lucide locale.
import re, os, glob, sys
S = sys.argv[1]
L = os.path.join(S, 'lucide_pacchetto/estratto/package/icons')
def norma(x):
    x = re.sub(r'\s+', ' ', x)
    x = re.sub(r'<(\w+)([^>]*)>\s*</\1>', r'<\1\2/>', x)
    x = re.sub(r'\s*/>', '/>', x)
    parti = re.findall(r'<(path|circle|rect|line|polyline|polygon|ellipse)\b([^>]*)/?>', x)
    out = []
    for tag, attrs in parti:
        a = dict(re.findall(r'([\w-]+)="([^"]*)"', attrs))
        a = {k: v for k, v in a.items() if k not in ('fill', 'stroke', 'stroke-width')}
        out.append(tag + str(sorted(a.items())))
    return tuple(sorted(out))
indice = {}
for f in glob.glob(os.path.join(L, '*.svg')):
    t = open(f).read()
    corpo = t[t.find('>', t.find('<svg')) + 1:t.rfind('</svg>')]
    indice.setdefault(norma(corpo), os.path.basename(f)[:-4])
V = os.path.join(S, 'veste-cornice/tavole')
for nome in ['Nefro-Agenda1-Giorno', 'Seg1-Conferme', 'Main']:
    t = open(os.path.join(V, nome + '.dc.html')).read()
    print('==', nome)
    # voci del menu: svg seguita dal testo della voce
    for m in re.finditer(r'<svg[^>]*>(.*?)</svg>\s*(?:<span[^>]*>)?([^<]{0,40})', t, flags=re.S):
        etichetta = re.sub(r'\s+', ' ', m.group(2)).strip()
        k = norma(m.group(1))
        print('  %-28s %s' % (indice.get(k, '?'), etichetta[:40]))
