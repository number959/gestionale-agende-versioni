# -*- coding: utf-8 -*-
"""Tutte le prove automatiche di questa cartella, una dopo l'altra, con il
riepilogo alla fine. Va su Windows e su Linux, con il Python da cui si lancia
(quello con le librerie del programma; per il browser anche Playwright):

    python strumenti/tutte_le_prove.py                     prove senza browser
    python strumenti/tutte_le_prove.py --browser URL       anche quelle nel browser
    python strumenti/tutte_le_prove.py --solo prove_17,campagna

Le prove nel browser girano su un gestionale di prova gia' avviato con i dati
finti (per esempio: python strumenti/demo.py --porta 5001), MAI su quello
vero: salvano pazienti e prenotazioni. prove_16_browser.py cambia l'indirizzo
degli aggiornamenti del gestionale su cui gira, per questo va per ultima.

Una prova e' andata se esce senza errori e la sua riga finale lo dice
(«0 da sistemare», «N prove nel browser, N superate», «N / N», «Nessun
guasto»): alcune delle prove piu' vecchie escono con 0 anche quando qualcosa
non va, per questo si guarda la riga finale. I registri restano in una
cartella temporanea, detta alla fine. Ogni giro ha la sua cartella per i file
temporanei: le due versioni si possono provare anche nello stesso momento."""
import argparse
import os
import re
import subprocess
import sys
import tempfile
import time

QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SENZA_BROWSER = ['prove.py', 'prove2.py', 'prove100.py', 'prove200.py', 'prove_14.py', 'prove_143.py',
                 'prove_145.py', 'prove_146.py', 'prove_anagrafiche.py', 'prove_funzioni.py', 'prove_guida.py',
                 'prove_personalizzazione.py', 'prove_15.py', 'prove_16.py', 'prove_17.py', 'prove_18.py',
                 'prove_19.py', 'prove_191.py', 'prove_110.py', 'prove_autoriparazione.py', 'prove_111.py', 'prove_111_importa.py', 'prove_111_turni.py',
                 'prove_112.py', 'prove_112_excel.py', 'campagna.py']
# in quest'ordine: prima quelle che non cambiano niente, per ultima quella che cambia l'indirizzo degli aggiornamenti
NEL_BROWSER = ['prove_guida_browser.py', 'prove_sicurezza_browser.py', 'prove_animazioni.py', 'prove_icone_animate.py',
               'prove_tendine_browser.py', 'prove_15_browser.py', 'prove_17_browser.py', 'prove_18_browser.py',
               'prove_19_browser.py', 'prove_191_browser.py', 'prove_110_browser.py', 'prove_112_browser.py',
               'prove_16_browser.py']


def giudica(nome, codice, uscita):
    """(andata, riga da mostrare) dalla riga finale della prova e dal codice d'uscita."""
    righe = [r.strip() for r in uscita.splitlines() if r.strip()]
    if nome == 'campagna.py':
        casi = next((r for r in righe if r.startswith('totale casi eseguiti')), '')
        casi = ' '.join(casi.split()[-1:]) + ' casi' if casi else ''
        if 'Nessun guasto' in uscita and 'raggiunte' not in uscita:
            nota = ' (tempo finito prima di tutti i casi)' if 'budget di tempo esaurito' in uscita else ''
            return codice == 0, ('%s, nessun guasto%s' % (casi, nota)).strip(', ')
        guasti = next((r for r in righe if 'cause distinte di guasto' in r), 'guasti trovati')
        return False, ('%s, %s' % (casi, guasti.rstrip(':'))).strip(', ')
    for r in reversed(righe):
        m = re.match(r'^(\d+) prove(?: totali)?, (?:\d+ superate, )?(\d+) da sistemare$', r)
        if m:
            return codice == 0 and m.group(2) == '0', r
        m = re.match(r'^(\d+) prove nel browser, (\d+) superate$', r)
        if m:
            return codice == 0 and m.group(1) == m.group(2), r
        m = re.match(r'^(\d+) / (\d+)$', r)
        if m:
            return codice == 0 and m.group(1) == m.group(2), '%s / %s prove' % (m.group(1), m.group(2))
    return False, 'nessun riepilogo (uscita %s): %s' % (codice, righe[-1][:120] if righe else 'nessun testo')


def main():
    try:
        sys.stdout.reconfigure(errors='replace')
    except AttributeError:
        pass
    p = argparse.ArgumentParser(description='Tutte le prove automatiche, con il riepilogo.')
    p.add_argument('--browser', metavar='URL', help='anche le prove nel browser, su questo gestionale DI PROVA')
    p.add_argument('--solo', metavar='NOMI', help='solo queste prove, separate da virgole (anche senza .py)')
    p.add_argument('--limite', type=int, default=1800, help='secondi al massimo per una prova (predefinito 1800)')
    a = p.parse_args()

    elenco = [(n, []) for n in SENZA_BROWSER]
    if a.browser:
        elenco += [(n, [a.browser.rstrip('/')]) for n in NEL_BROWSER]
    elenco = [(n, x) for n, x in elenco if os.path.exists(os.path.join(QUI, n))]
    if a.solo:
        voluti = {s.strip() if s.strip().endswith('.py') else s.strip() + '.py' for s in a.solo.split(',') if s.strip()}
        sconosciuti = voluti - {n for n, _ in elenco}
        if sconosciuti:
            print('Prove sconosciute in questa cartella%s: %s' % (
                '' if a.browser else ' (per quelle nel browser serve --browser URL)', ', '.join(sorted(sconosciuti))))
            return 2
        elenco = [(n, x) for n, x in elenco if n in voluti]

    giro = tempfile.mkdtemp(prefix='gestionale-prove-%s-' % os.path.basename(QUI))
    temporanei = os.path.join(giro, 'temporanei')
    os.makedirs(temporanei)
    ambiente = dict(os.environ, TMPDIR=temporanei, TEMP=temporanei, TMP=temporanei,
                    PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    print('Prove di %s con Python %s (registri in %s)\n' % (QUI, sys.version.split()[0], giro), flush=True)
    risultati = []
    inizio_tutto = time.monotonic()
    for nome, argomenti in elenco:
        inizio = time.monotonic()
        registro = os.path.join(giro, nome.replace('.py', '.log'))
        try:
            r = subprocess.run([sys.executable, nome] + argomenti, cwd=QUI, env=ambiente, timeout=a.limite,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            codice, uscita = r.returncode, r.stdout.decode('utf-8', 'replace')
        except subprocess.TimeoutExpired as e:
            codice, uscita = 'tempo scaduto', (e.stdout or b'').decode('utf-8', 'replace')
        with open(registro, 'w', encoding='utf-8') as f:
            f.write(uscita)
        andata, riga = giudica(nome, codice if codice != 'tempo scaduto' else -1, uscita)
        if codice == 'tempo scaduto':
            andata, riga = False, 'oltre %d secondi, fermata' % a.limite
        secondi = time.monotonic() - inizio
        risultati.append((andata, nome))
        print('%s %-28s %5.0f s  %s' % ('OK' if andata else 'KO', nome, secondi, riga), flush=True)
    rotte = [n for ok, n in risultati if not ok]
    print('\n%d prove lanciate in %.0f s: %s' % (len(risultati), time.monotonic() - inizio_tutto,
                                                'tutte andate.' if not rotte else 'da guardare ' + ', '.join(rotte)))
    if rotte:
        print('I registri delle prove sono in %s' % giro)
    return 1 if rotte else 0


if __name__ == '__main__':
    sys.exit(main())
