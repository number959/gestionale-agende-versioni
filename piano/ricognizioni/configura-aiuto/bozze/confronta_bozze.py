# Confronta le pagine di oggi e quelle delle bozze con il lettore del lanciatore (strumenti/confronta_rami.py):
# moduli, collegamenti, segni (data-tasto, data-guida), righe di testo. Stampa le differenze.
import sys, os, difflib
sys.path.insert(0, '/home/user/gestionale-agende-versioni/gestionale/strumenti')
from confronta_rami import Lettore
V = os.path.dirname(os.path.abspath(__file__))
def leggi(f):
    l = Lettore(); l.feed(open(f, encoding='utf-8').read()); return l
def principale(l):
    # solo il contenuto: il menu di oggi (nav.menu) è uguale nelle due e cambia in tappa 2
    return l
for nome in sys.argv[1:]:
    a, b = leggi(os.path.join(V, 'misure/html-oggi', nome + '.html')), leggi(os.path.join(V, 'misure/html-bozza', nome + '.html'))
    print('=' * 20, nome)
    print('moduli uguali:', a.moduli == b.moduli)
    if a.moduli != b.moduli:
        for x, y in zip(a.moduli, b.moduli):
            if x != y: print('  oggi ', x, '\n  bozza', y)
        print('  numero', len(a.moduli), len(b.moduli))
    sa = [x for x in a.segni]; sb = [x for x in b.segni if not (x.startswith('data-guida=') and x not in a.segni)]
    print('segni uguali (data-guida nuovi della tappa 1 tolti):', sa == sb, [x for x in b.segni if x not in a.segni][:8])
    print('collegamenti: aggiunti', [x for x in b.collegamenti if x not in a.collegamenti][:10], 'tolti', [x for x in a.collegamenti if x not in b.collegamenti][:10],
          'stesso ordine:', [x for x in a.collegamenti] == [x for x in b.collegamenti if x in a.collegamenti])
    d = [r for r in difflib.unified_diff(a.testo, b.testo, lineterm='', n=0) if not r.startswith(('---', '+++', '@@'))]
    print('testo: %d righe diverse' % len(d)); print('\n'.join('   ' + r for r in d[:40]))
