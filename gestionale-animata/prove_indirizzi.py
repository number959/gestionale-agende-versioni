# -*- coding: utf-8 -*-
"""L'elenco degli indirizzi del programma (tappa 1 della base, 21/11/2026).

indirizzi.txt, uguale nelle due cartelle, ha una riga per ogni indirizzo: metodi, indirizzo e nome della
funzione che risponde; per le pagine GET senza parametri anche come rispondono sui dati di prova di seed.py
(200, oppure un rimando e dove porta, con le cifre scritte N perché le date cambiano). Se un indirizzo
sparisce o cambia, o una pagina risponde in un altro modo, la prova cade: la veste nuova non deve togliere né
spostare niente. Un indirizzo nuovo si aggiunge apposta, e il file cambiato va nello stesso commit:

    python prove_indirizzi.py              # confronta
    python prove_indirizzi.py --scrivi     # riscrive indirizzi.txt (poi si guarda git diff)
"""
import os
import re
import shutil
import sys
import tempfile

CARTELLA = os.path.dirname(os.path.abspath(__file__))
ELENCO = os.path.join(CARTELLA, 'indirizzi.txt')
PROVVISORIA = tempfile.mkdtemp(prefix='prove-indirizzi-')

import seed  # noqa: E402
import app as A  # noqa: E402

A.app.config['TESTING'] = True
A.Sessione = seed.popola('sqlite:///' + os.path.join(PROVVISORIA, 'prove.db'))
C = A.app.test_client()


def risposta(regola):
    r = C.get(regola)
    if r.status_code in (301, 302, 303, 307, 308):
        dove = re.sub(r'^https?://[^/]+', '', r.headers.get('Location', '')).split('?')[0]
        return '%d → %s' % (r.status_code, re.sub(r'\d+', 'N', dove))
    return str(r.status_code)


def righe_di_adesso():
    righe = []
    for r in sorted(A.app.url_map.iter_rules(), key=lambda r: (r.rule, r.endpoint)):
        metodi = ','.join(sorted(m for m in r.methods if m not in ('HEAD', 'OPTIONS')))
        riga = '%s\t%s\t%s' % (metodi, r.rule, r.endpoint)
        if 'GET' in r.methods and not r.arguments and r.endpoint != 'static':
            riga += '\t' + risposta(r.rule)
        righe.append(riga)
    return righe


try:
    adesso = righe_di_adesso()
finally:
    shutil.rmtree(PROVVISORIA, ignore_errors=True)

if '--scrivi' in sys.argv:
    with open(ELENCO, 'w', encoding='utf-8', newline='\n') as f:
        f.write('# Gli indirizzi del programma: metodi, indirizzo, funzione e, per le pagine GET senza parametri,\n'
                '# la risposta sui dati di prova. Lo scrive «python prove_indirizzi.py --scrivi»; lo controlla\n'
                '# prove_indirizzi.py. Un cambiamento qui è un cambiamento degli indirizzi: va spiegato nel commit.\n')
        f.write('\n'.join(adesso) + '\n')
    print('scritto %s: %d indirizzi' % (os.path.basename(ELENCO), len(adesso)))
    sys.exit(0)

with open(ELENCO, encoding='utf-8') as f:
    attesi = [r for r in f.read().splitlines() if r and not r.startswith('#')]


def chiave(riga):
    return '\t'.join(riga.split('\t')[:2])          # metodi e indirizzo


prima = {chiave(r): r for r in attesi}
ora = {chiave(r): r for r in adesso}
problemi = []
for k in sorted(set(prima) | set(ora)):
    if k not in ora:
        problemi.append('SPARITO   ' + prima[k])
    elif k not in prima:
        problemi.append('NUOVO     ' + ora[k] + '   (se è voluto: python prove_indirizzi.py --scrivi)')
    elif prima[k] != ora[k]:
        problemi.append('CAMBIATO  ' + prima[k] + '   ora: ' + ora[k])
for p in problemi:
    print('ROTTO  ' + p)
totali = len(set(prima) | set(ora))
print('%d prove totali, %d superate, %d da sistemare' % (totali, totali - len(problemi), len(problemi)))
sys.exit(1 if problemi else 0)
