"""Legge gettoni.css (chiaro in :root, scuro in html.scuro) e calcola i contrasti delle coppie testo/fondo.
È la bozza della prova della 1-bis: python contrasti_gettoni.py percorso/gettoni.css"""
import importlib.util, os, re, sys
R = '/home/user/gestionale-agende-versioni/gestionale'
sys.path.insert(0, R)
import marchio  # noqa: E402
spec = importlib.util.spec_from_file_location('gts', os.path.join(R, 'strumenti', 'genera_tema_scuro.py'))
gts = importlib.util.module_from_spec(spec); spec.loader.exec_module(gts)

css = re.sub(r'/\*.*?\*/', '', open(sys.argv[1], encoding='utf-8').read(), flags=re.S)
chiaro_blocco = css[css.index(':root'):css.index('@media screen')]
scuro_blocco = css[css.index('html.scuro'):]
leggi = lambda b: dict(re.findall(r'--v-([\w-]+):\s*(#[0-9A-Fa-f]{6})\s*;', b))
C = leggi(chiaro_blocco); S = dict(C); S.update(leggi(scuro_blocco))
COPPIE = [('testo', 'fondo'), ('testo', 'superficie'), ('testo', 'superficie-tenue'), ('testo', 'incasso'),
          ('testo-medio', 'superficie'), ('testo-medio', 'incasso'), ('testo-medio', 'fondo'),
          ('testo-tenue', 'superficie'), ('testo-tenue', 'fondo'), ('testo-tenue', 'incasso'),
          ('testo-tenue', 'superficie-tenue'), ('testo-tenue', 'chiuso'),
          ('verde-testo', 'occupato'), ('verde-testo', 'arrivato'), ('verde', 'superficie'), ('verde-testo', 'superficie'),
          ('confermato-testo', 'confermato'), ('rosso', 'rosso-fondo'), ('rosso', 'superficie'), ('rosso-forte', 'rosso-fondo'),
          ('avviso-testo', 'avviso-fondo'), ('avviso-testo', 'sabbia'), ('ok-testo', 'ok-fondo'), ('sala-testo', 'sala-fondo'),
          ('testo', 'disponibile'), ('testo', 'occupato'), ('testo', 'arrivato'), ('testo-su-pieno', 'verde-pieno'), ('testo-su-pieno', 'rosso-pieno'), ('testo-su-pieno', 'sala-pieno')]
NON_TESTO = [('riga-campo', 'superficie'), ('segno-grigio', 'superficie'), ('riga', 'superficie')]
ruolo = {}
for n in C:
    ruolo[n] = 'testo' if n.startswith('testo') or n.endswith('-testo') or n in ('verde', 'rosso', 'rosso-forte') else \
        'bordo' if n.startswith('riga') or n.endswith('-riga') or n in ('azzurro', 'sala', 'segno-grigio') else 'fondo'
print('%-18s %-8s %-8s %-8s' % ('gettone', 'chiaro', 'scuro', 'converti()'))
for n in C:
    conv = gts.converti(C[n], ruolo[n])
    print('%-18s %-8s %-8s %-8s%s' % (n, C[n], S[n], conv, '' if conv.upper() == S[n].upper() else '  ritoccato'))
male = []
print('\n%-32s %6s %6s' % ('testo / fondo', 'chiaro', 'scuro'))
for t, f in COPPIE:
    a, b = marchio.contrasto(C[t], C[f]), marchio.contrasto(S[t], S[f])
    if min(a, b) < 4.5:
        male.append((t, f, a, b))
    print('%-32s %6.2f %6.2f%s' % (t + ' / ' + f, a, b, '' if min(a, b) >= 4.5 else '   <-- sotto 4,5'))
print('\nbordi (non testo; WCAG 1.4.11 chiede 3:1, oggi i campi hanno 1,85:1)')
for t, f in NON_TESTO:
    print('%-32s %6.2f %6.2f' % (t + ' / ' + f, marchio.contrasto(C[t], C[f]), marchio.contrasto(S[t], S[f])))
print('\nCOPPIE SOTTO 4,5:', male or 'nessuna')
