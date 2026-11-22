# Confronta le pagine di oggi (porta 5191) e le bozze (5192) con il Lettore del lanciatore (strumenti/confronta_rami.py)
import sys
sys.path.insert(0, '/home/user/gestionale-agende-versioni/gestionale/strumenti')
from confronta_rami import leggi, riassunto, differenze
PAGINE = sys.argv[1:] or ['/conferme', '/conferme?data=2026-11-23&struttura=1', '/chiusura/2026-11-17', '/chiusura/2026-11-22',
                          '/chiusura/2026-11-25', '/cassa/2026-11-17', '/cassa/2026-11-19', '/attesa', '/attesa?chiuse=1']
for p in PAGINE:
    a = riassunto(*leggi(5191, p), True)[0]
    b = riassunto(*leggi(5192, p), True)[0]
    d = differenze(a, b)
    print('==', p, 'UGUALE' if not d else '')
    for x in d:
        if x.startswith('testo'):
            ta, tb = a.get('testo', []), b.get('testo', [])
            print('   testo: solo oggi', [t for t in ta if t not in tb][:12], '| solo bozza', [t for t in tb if t not in ta][:12])
        else:
            print('  ', x[:600])
