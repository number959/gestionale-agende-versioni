# Testi della tavola che oggi non ci sono, e testi fissi del modello che la tavola non ha.
# python3 confronta_testi.py TAVOLA modello.html[,altro.html] pagina-oggi
import re, sys, html, os
V = os.path.dirname(os.path.abspath(__file__))
T = '/home/user/gestionale-agende-versioni/gestionale/templates/'
tav, modelli, pag = sys.argv[1], sys.argv[2].split(','), sys.argv[3]
norm = lambda s: re.sub(r'\s+', ' ', html.unescape(s)).strip()
def letterali(f):
    s = open(T + f, encoding='utf-8').read()
    s = re.sub(r'\{#.*?#\}', ' ', s, flags=re.S)
    s = re.sub(r'<script.*?</script>', ' ', s, flags=re.S)
    s = re.sub(r'\{%.*?%\}|\{\{.*?\}\}', '\x00', s, flags=re.S)
    out = []
    # testo fra i tag e valori di title/placeholder/aria-label
    for m in re.finditer(r'(?:title|placeholder|aria-label)="([^"]*)"', s):
        out += [x for x in m.group(1).split('\x00')]
    s = re.sub(r'<[^>]*>', '\x00', s)
    out += s.split('\x00')
    return [norm(x) for x in out if len(norm(x)) >= 4 and re.search('[a-zà-ù]{3}', norm(x))]
tv = [norm(x) for x in open(os.path.join(V, 'misure', 'testi-tavola-%s.txt' % tav), encoding='utf-8').read().split('\n')]
tv = [re.sub(r'^@(title|aria|placeholder) ', '', x) for x in tv if x]
pg = [norm(x) for x in open(os.path.join(V, 'misure', 'testi-pagina-%s.txt' % pag), encoding='utf-8').read().split('\n')]
pg = [re.sub(r'^@(title|aria|placeholder) ', '', x) for x in pg if x]
lett = sum((letterali(f) for f in modelli), [])
tutto_tav = ' '.join(tv); tutto_oggi = ' '.join(lett + pg)
print('## testi fissi di oggi (%s) che la tavola %s non ha' % (','.join(modelli), tav))
visti = set()
for x in lett:
    if x not in tutto_tav and x not in visti:
        visti.add(x); print('-', x[:160])
print('## testi della tavola che oggi non ci sono (né nel modello né nella pagina di prova)')
visti = set()
for x in tv:
    if len(x) >= 3 and x not in tutto_oggi and x not in visti and re.search('[A-Za-zà-ù]{3}', x):
        visti.add(x); print('-', x[:160])
