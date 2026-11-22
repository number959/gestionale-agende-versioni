# Le pagine della bozza (porta 5143, copia in prova/) contro quelle di oggi (riassunti-oggi.json), con il metodo del
# lanciatore (strumenti/confronta_rami.py): moduli, collegamenti, data-tasto/data-guida e righe di testo, in ordine.
import json, os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, '/home/user/gestionale-agende-versioni/gestionale/strumenti')
from confronta_rami import riassunto, leggi, uguali, differenze
V = os.path.dirname(os.path.abspath(__file__))
oggi = json.load(open(os.path.join(V, 'riassunti-oggi.json')))
esito = {}
for p, ra in oggi.items():
    rb, _ = riassunto(*leggi(5143, p), True)
    rb = json.loads(json.dumps(rb))
    if uguali(ra, rb):
        esito[p] = 'UGUALE'
    else:
        esito[p] = differenze(ra, rb)
        # dove cambia il testo: le righe vicine
        if ra.get('testo') != rb.get('testo'):
            a, b = ra['testo'], rb['testo']
            i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
            esito[p].append('primo testo diverso alla riga %d: oggi %r / bozza %r' % (i, a[i-1:i+3], b[i-1:i+3]))
for p, e in esito.items():
    print(p, '->', e if e == 'UGUALE' else '\n   ' + '\n   '.join(e))
json.dump(esito, open(os.path.join(V, 'confronto-bozze.json'), 'w'), ensure_ascii=False, indent=1)
