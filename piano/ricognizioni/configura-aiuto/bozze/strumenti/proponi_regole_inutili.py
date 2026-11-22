# -*- coding: utf-8 -*-
"""BOZZA tappa 9 (non è nel repository): le regole di static/stile.css che nessuno usa più, da PROPORRE.
Decide una persona: lo script non cambia nessun file.

    python strumenti/proponi_regole_inutili.py            # nella cartella del programma
    python strumenti/proponi_regole_inutili.py --tutte     # anche quelle usate, con dove

Una classe (o un id) è «usata» se compare in un modello (templates/*.html), in uno script (static/*.js), in un file
Python del programma (*.py, senza le prove) o in strumenti/*.py: scritta intera, oppure con un nome composto
(«stato-{{ x }}», 'stato-' + x, "esito-%s"): allora vale ogni classe che comincia così. Le prove non contano: una
classe che cercano solo le prove è proprio una di quelle da guardare. Una regola si propone quando nessuno dei suoi
selettori può più colpire: un selettore è morto se una delle sue classi o dei suoi id non è usata.
Le regole dentro @media restano legate al loro blocco; @font-face, :root, html, body e i soli tag non si propongono.
tema-scuro.css non si guarda: lo rifà il suo generatore da stile.css (strumenti/genera_tema_scuro.py)."""
import glob
import os
import re
import sys

QUI = os.getcwd()
CLASSE = re.compile(r'\.(-?[A-Za-z_][\w-]*)')
ID = re.compile(r'#([A-Za-z_][\w-]*)')


def corpus():
    file = glob.glob(os.path.join(QUI, 'templates', '*.html')) + glob.glob(os.path.join(QUI, 'static', '*.js')) + \
        [f for f in glob.glob(os.path.join(QUI, '*.py')) if not os.path.basename(f).startswith('prove')] + \
        glob.glob(os.path.join(QUI, 'strumenti', '*.py'))
    testi = {}
    for f in file:
        with open(f, encoding='utf-8', errors='replace') as h:
            testi[os.path.relpath(f, QUI)] = h.read()
    return testi


def parole_e_prefissi(testi):
    parole, prefissi = {}, set()
    for nome, t in testi.items():
        for w in set(re.findall(r'[A-Za-z_][\w-]*', t)):
            parole.setdefault(w, nome)
        # nomi composti: «xxx-{{», «xxx-{%», 'xxx-' +, "xxx-%s", `xxx-${`. Negli script ogni riga (turni.js:119
        # scrive 'avviso-turni livello-' + livello senza la parola class); nei modelli e nel Python solo le righe
        # che parlano di classi, perché «novita-%s» di aggiornamenti.py:724 è una chiave, non una classe
        for riga in t.splitlines():
            if not nome.endswith('.js') and 'class' not in riga:
                continue
            for m in re.finditer(r'([A-Za-z_][\w-]*-)(?:\{\{|\{%|\'\s*\+|"\s*\+|%s|\$\{)', riga):
                prefissi.add(m.group(1))
    return parole, prefissi


def regole(css):
    """[(riga, selettore, dentro_media)] con i commenti tolti."""
    senza = re.sub(r'/\*.*?\*/', lambda m: '\n' * m.group(0).count('\n'), css, flags=re.S)
    out, pila, i, riga = [], [], 0, 1
    testa = ''
    for ch in senza:
        if ch == '{':
            sel = ' '.join(testa.split())
            out.append((riga - testa.count('\n'), sel, bool(pila)))
            pila.append(sel)
            testa = ''
        elif ch == '}':
            if pila:
                pila.pop()
            testa = ''
        else:
            testa += ch
        if ch == '\n':
            riga += 1
    return [(r, s, m) for r, s, m in out if not s.startswith('@')]


def usata(nome, parole, prefissi):
    return nome in parole or any(nome.startswith(p) for p in prefissi)


def main():
    tutte = '--tutte' in sys.argv
    testi = corpus()
    parole, prefissi = parole_e_prefissi(testi)
    with open(os.path.join(QUI, 'static', 'stile.css'), encoding='utf-8') as f:
        css = f.read()
    proposte = 0
    for riga, sel, in_media in regole(css):
        selettori = [s.strip() for s in sel.split(',') if s.strip()]
        vivi = []
        for s in selettori:
            nomi = CLASSE.findall(re.sub(r'\[[^\]]*\]|:[\w-]+\([^)]*\)', '', s)) + ID.findall(s)
            morti = [n for n in nomi if not usata(n, parole, prefissi)]
            if not morti:
                vivi.append(s)
        if not vivi:
            proposte += 1
            print('stile.css:%d  %s%s' % (riga, sel[:150], '   (dentro @media)' if in_media else ''))
        elif tutte:
            print('  usata   stile.css:%d  %s' % (riga, sel[:150]))
    print('%d regole proposte (nessuna toccata: decide una persona)' % proposte)


if __name__ == '__main__':
    main()
