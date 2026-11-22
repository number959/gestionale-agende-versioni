# -*- coding: utf-8 -*-
"""Dove è caduta una prova: file e riga dell'ultima riga di una raccolta di prove nel percorso dell'errore
(l'«assert» che non è passato), non quella dentro le librerie. Lo usano le funzioni prova() delle raccolte:
«prove_15.py:812 · il testo atteso…» invece del solo «asserzione fallita» (tappa 1 della base, 21/11/2026)."""
import os
import traceback


AIUTI = {'prove_dove.py', 'prove_messaggi.py'}       # i loro messaggi d'errore dicono già la riga di chi li chiama


def dove(errore):
    passi = traceback.extract_tb(errore.__traceback__)
    nostri = [p for p in passi if os.path.basename(p.filename).startswith(('prove', 'campagna'))
              and os.path.basename(p.filename) not in AIUTI]
    if not (nostri or passi):
        return '?'
    p = (nostri or passi)[-1]
    return '%s:%d' % (os.path.basename(p.filename), p.lineno)
