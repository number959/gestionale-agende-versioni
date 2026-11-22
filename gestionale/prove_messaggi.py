# -*- coding: utf-8 -*-
"""I messaggi per l'utente (flash()) presi da Flask, non dall'HTML (tappa 1 della base, 22/11/2026).

Prima le prove leggevano i messaggi dalla sessione e, con una pagina 200, dalle <div class="avviso…"> della
pagina con un'espressione regolare: bastava cambiare l'aspetto della zona dei messaggi per far tacere le prove
(e senza la zona restavano verdi lo stesso). Qui il messaggio si prende quando il programma lo fa, con il segnale
message_flashed di Flask, sia che la risposta rimandi (302) sia che ridisegni la pagina (200). Con una pagina 200
si controlla anche che i messaggi di quella richiesta siano scritti nella pagina, comunque sia fatta: arrivano
davvero a chi legge. Dove stanno e come si vedono lo dice la prova nel browser (prove_sicurezza_browser.py).

    import prove_messaggi as PM
    PM.segui(A.app)                  # una volta, dopo aver importato il programma
    C = PM.segna(A.app.test_client())     # ogni cliente: i messaggi di C non finiscono a C2
    assert 'Scheda salvata' in PM.avvisi(C)
    assert 'almeno 6 cifre' in PM.avvisi(C, r, 'errore')    # r 200: anche scritto nella pagina
"""
import itertools

from flask import message_flashed, request
from markupsafe import escape

_MESSAGGI = []                        # (cliente, richiesta, categoria, testo) di ogni flash(), in ordine
_NUMERO = itertools.count(1)          # non id(cliente): un numero di memoria torna dopo che il cliente sparisce


def _fatto(sender, message, category, **altro):
    """Flask la chiama a ogni flash(), dentro la richiesta che lo fa (anche se poi rimanda)."""
    _MESSAGGI.append((request.environ.get('prove.cliente'), request.environ.get('wsgi.input'), category, message))


def segui(app):
    # una funzione del modulo e non un lambda: blinker tiene i ricevitori con un riferimento debole, un lambda
    # sparirebbe alla prima pulizia della memoria e non arriverebbe più nessun messaggio (le prove con «in»
    # cadrebbero, quelle con «not in» passerebbero da sole)
    message_flashed.connect(_fatto, app)


def segna(cliente):
    """Il segno sul cliente del test_client: di chi è ogni messaggio (C, C2, C_ di mondi diversi)."""
    cliente.environ_base['prove.cliente'] = next(_NUMERO)
    return cliente


def testo(m):
    return m.striptags() if hasattr(m, '__html__') else str(m)       # Markup (un collegamento): solo le parole


def avvisi(C, r=None, categoria=None):
    """I messaggi fatti con flash() dalle richieste di C dopo l'ultima chiamata, in un testo solo; con
    categoria ('ok', 'errore', 'avviso') solo quelli. Svuota anche la coda in sessione, come prima: la pagina
    dopo non li mostra di nuovo. Con una risposta 200 i messaggi fatti in quella richiesta devono essere scritti
    nella pagina, con l'escape di Jinja."""
    io = C.environ_base.get('prove.cliente')
    assert io is not None, 'cliente senza segno: crearlo con prove_messaggi.segna()'
    miei = [x for x in _MESSAGGI if x[0] == io]
    _MESSAGGI[:] = [x for x in _MESSAGGI if x[0] != io]
    with C.session_transaction() as sess:
        sess['_flashes'] = []
    if r is not None and r.status_code == 200:
        pagina = r.get_data(as_text=True)
        richiesta = r.request.environ.get('wsgi.input')      # Werkzeug copia l'environ, lo stream è lo stesso
        for _, da, _, m in miei:      # la riga di chi chiama la dice prove_dove.dove(), che salta questo file
            assert da is not richiesta or str(escape(m)) in pagina, 'messaggio non scritto nella pagina: %s' % testo(m)
    return ' '.join(testo(m) for _, _, c, m in miei if categoria is None or c == categoria)
