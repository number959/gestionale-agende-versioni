# -*- coding: utf-8 -*-
"""Il gestionale con i DATI DI PROVA intorno a oggi, su un server locale: per
le prove nel browser, le immagini e i video della guida, le dimostrazioni.
Mai con i dati veri: i nomi sono inventati (e scelti per non coincidere con
quelli dei file della clinica), le email sono @example.it.

    python strumenti/demo.py                      # dati in una cartella temporanea, porta 5001
    python strumenti/demo.py --dati C:\\prova --porta 5077
    python strumenti/demo.py --nomi-inventati     # anche clinica, medici e logo inventati

Ogni avvio ricomincia da capo (il database della prova si cancella e si rifa').
I dati li fa strumenti/dati_prova.py (fai_dati), gli stessi del pacchetto di
prova (prova.py): medici, turni, appuntamenti della settimana in ogni stato,
sala operatoria e posti letto, cassa, lista d'attesa, cose da fare, documenti,
email e WhatsApp gia' partiti (finti, il thread degli invii non parte), le
schede per la guida del codice fiscale (valido, sbagliato, che non torna,
doppio, da calcolare). Qui in piu' un aggiornamento finto gia' scaricato, cosi'
la pagina Aggiornamenti mostra «Aggiorna adesso». Con --nomi-inventati anche
nome, indirizzo e logo della clinica e i due medici veri diventano inventati,
come nel pacchetto di prova (dati_prova.nomi_inventati); senza, i dati sono
quelli di sempre.

Le prove nel browser (prove_*_browser.py) cambiano i dati: per immagini e
video meglio un server appena avviato."""
import argparse
import os
import sys
import tempfile

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SRC)
os.chdir(SRC)
parametri = argparse.ArgumentParser(description='Gestionale con i dati di prova.')
parametri.add_argument('--dati', default=os.path.join(tempfile.gettempdir(), 'gestionale-demo'),
                       help='cartella del database di prova (si svuota a ogni avvio)')
parametri.add_argument('--porta', type=int, default=5001)
parametri.add_argument('--nomi-inventati', action='store_true',
                       help='anche nome, indirizzo e logo della clinica e i due medici veri inventati')
ARG = parametri.parse_args()
os.makedirs(ARG.dati, exist_ok=True)
import app as A  # noqa: E402   prima dei dati, come prima: registra le pagine e collega i moduli
import viste  # noqa: E402
from strumenti import dati_prova  # noqa: E402

S = dati_prova.fai_dati(os.path.join(ARG.dati, 'demo.db'))
if ARG.nomi_inventati:
    rimasti = dati_prova.nomi_inventati(S)
    if rimasti:
        print('ATTENZIONE, nomi della clinica rimasti:', '; '.join(rimasti), flush=True)
A.Sessione = S; A._registro = None
viste._sessionmaker = lambda: S
dati_prova.aggiornamento_finto(ARG.dati, S)
from waitress import serve  # noqa: E402
with open(os.path.join(ARG.dati, 'demo.pid'), 'w') as f:
    f.write(str(os.getpid()))
print('Gestionale di prova: http://127.0.0.1:%d  (dati in %s)' % (ARG.porta, ARG.dati), flush=True)
serve(A.app, host='127.0.0.1', port=ARG.porta, threads=4)
