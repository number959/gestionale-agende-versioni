# -*- coding: utf-8 -*-
"""I controlli «non c'è» con il loro gemello (tappa 1 della base, 22/11/2026).

Un controllo come
    assert '<form method="post">' not in pagina
passa anche quando la pagina cambia forma e quella stringa non la scrive più nessuno: è successo
(prove_anagrafiche.py, il modulo oggi è <form method="post" id="modulo-appuntamento" …>). Il gemello cerca la
STESSA cosa, letta nello STESSO modo, in una pagina dove deve esserci: se non la trova nemmeno lì, la prova cade
invece di passare da sola.

    from prove_gemelli import manca, protetto
    manca(testo(r), 'Fittizi', dove_ce=lambda: testo(C.get('/sala/…')), perche='mai pazienti nella matrice')
    protetto(html(r), '<script>alert(1)</script>')      # sull'HTML grezzo, mai su un testo() che toglie i tag

Nel browser (Playwright): sparisce() per «Esc chiude», «un clic fuori chiude»; manca_nel_browser() per un
selettore che non c'è qui e c'è in un'altra pagina.
"""
from markupsafe import escape as _escape            # come Jinja: " diventa &#34;, ' diventa &#39;


def _trova(ago, testo):
    if hasattr(ago, 'search'):                       # un re.compile(...)
        return ago.search(testo) is not None
    return ago in testo


def _leggi(posto):
    return posto() if callable(posto) else posto


def _nome(ago):
    return getattr(ago, 'pattern', ago)


def manca(testo, ago, dove_ce, perche=''):
    """`ago` (stringa o re.compile) NON deve stare in `testo`, e DEVE stare in `dove_ce`.

    dove_ce: il testo di una pagina dove c'è davvero, letto con la stessa funzione (html() con html(), testo() con
    testo()), oppure una funzione senza argomenti che lo legge, oppure una lista di questi (basta uno).
    Prima il gemello: se cade lui, il messaggio dice che il controllo è diventato cieco."""
    posti = dove_ce if isinstance(dove_ce, (list, tuple)) else [dove_ce]
    coda = ': ' + perche if perche else ''
    if not any(_trova(ago, _leggi(p)) for p in posti):
        raise AssertionError("gemello: %r non c'è nemmeno dove deve esserci (il controllo «non c'è» non vedrebbe "
                             "niente)%s" % (_nome(ago), coda))
    if _trova(ago, testo):
        raise AssertionError("%r c'è e non deve esserci%s" % (_nome(ago), coda))


def protetto(html, pezzo, perche=''):
    """Testo pericoloso salvato dall'utente: nella pagina (HTML grezzo) non c'è vivo, e c'è nella forma protetta
    da Jinja. Il gemello è la forma protetta nella stessa pagina: dice che il testo è davvero arrivato fin lì."""
    sicuro = str(_escape(pezzo))
    coda = ': ' + perche if perche else ''
    if sicuro not in html:
        raise AssertionError("gemello: %r non c'è nemmeno protetto (%r): la pagina non lo mostra, il controllo "
                             "passerebbe da solo%s" % (pezzo, sicuro, coda))
    if pezzo in html:
        raise AssertionError('%r arriva vivo nella pagina%s' % (pezzo, coda))


# ---------------------------------------------------------------- nel browser (Playwright)
def sparisce(pg, selettore, azione, aspetta=150, **filtro):
    """Prima c'è (almeno uno, visibile), dopo azione() non c'è più (o non si vede). Il gemello è lo stesso
    selettore un attimo prima. Torna (va bene, (prima, dopo)) per ok()/controlla()."""
    loc = pg.locator(selettore, **filtro)
    prima = loc.count() >= 1 and loc.first.is_visible()
    azione()
    pg.wait_for_timeout(aspetta)
    dopo = loc.count() == 0 or not loc.first.is_visible()
    return prima and dopo, (prima, dopo)


def manca_nel_browser(pg, selettore, dove_ce, **filtro):
    """Il selettore non c'è in questa pagina e c'è in quella che apre dove_ce() (una funzione che fa pg.goto(…));
    poi si torna alla pagina di prima. Torna (va bene, dettaglio) per ok()/controlla()."""
    qui = pg.locator(selettore, **filtro).count()
    torna = pg.url
    dove_ce()
    li = pg.locator(selettore, **filtro).count()
    pg.goto(torna)
    return qui == 0 and li >= 1, {'qui': qui, 'dove deve esserci': li}
