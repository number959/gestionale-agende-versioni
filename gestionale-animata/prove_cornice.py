# -*- coding: utf-8 -*-
"""Leggere la cornice nell'HTML, per le prove senza browser (tappa 2 della base, 22/11/2026). Non è una raccolta: non
scrive la riga finale e non sta nell'elenco di strumenti/tutte_le_prove.py; la importano le raccolte che guardano il
menu, come prove_gemelli.py.

Dalla tappa 2 il menu sta a sinistra (templates/_menu.html, <nav class="menu v-menu">), le pagine di un'area sono
linguette in cima alla pagina (_linguette.html, dentro data-cornice="linguette") e la voce accesa ha aria-current (page;
true sul pulsante della tendina Aiuto). Le prove leggono la cornice da qui: se il disegno cambia, si cambia qui.

    from prove_cornice import CON_MENU, linguetta_accesa, voce_accesa
    assert voce_accesa(t, 'menu-ambulatori') and linguetta_accesa(t) == 'Riepilogo live'
    assert not CON_MENU.search(t)                         # la pagina è senza menu (il modo schermo, un foglio)
"""
import re
from html import unescape

CON_MENU = re.compile(r'<nav class="menu[ "]')          # il menu, anche con altre classi dopo («menu v-menu»)


def menu_html(t):
    """Il pezzo di HTML del menu (dentro <nav class="menu …">), '' se non c'è."""
    m = CON_MENU.search(t)
    return t[m.start():t.index('</nav>', m.start())] if m else ''


def linguette_html(t):
    """Il pezzo di HTML delle linguette (data-cornice="linguette"), '' se la pagina non ne ha."""
    i = t.find('data-cornice="linguette"')
    return t[i:t.index('</nav>', i)] if i >= 0 else ''


def voce_accesa(t, guida):
    """La voce del menu con quel data-guida è accesa: aria-current="page" sul suo collegamento, o "true" sul pulsante
    della tendina (Aiuto)."""
    return bool(re.search(r'<a [^>]*aria-current="page"[^>]*data-guida="%s"' % re.escape(guida), t) or
                re.search(r'data-guida="%s">\s*<button[^>]*aria-current="true"' % re.escape(guida), t))


def linguette(t):
    """Le linguette della pagina: [(parola, indirizzo, accesa)], senza il contatore."""
    uscita = []
    for m in re.finditer(r'<a class="v-linguetta" href="([^"]*)"([^>]*)>(.*?)</a>', linguette_html(t), re.S):
        parola = re.sub(r'<span class="v-conta".*?</span>|<[^>]+>', '', m.group(3), flags=re.S)
        uscita.append((' '.join(unescape(parola).split()), unescape(m.group(1)), 'aria-current="page"' in m.group(2)))
    return uscita


def linguetta_accesa(t):
    """La parola della linguetta accesa (None se nessuna; più d'una separate da virgole)."""
    return ', '.join(p for p, _, accesa in linguette(t) if accesa) or None


def contatore_della_voce(t, guida):
    """Il numero accanto alla voce del menu con quel data-guida (Segreteria: quelli da confermare), None se non c'è."""
    m = re.search(r'<a [^>]*data-guida="%s"[^>]*>(.*?)</a>' % re.escape(guida), menu_html(t), re.S)
    n = re.search(r'<span class="v-conta[^"]*"[^>]*>(\d+)</span>', m.group(1)) if m else None
    return int(n.group(1)) if n else None
