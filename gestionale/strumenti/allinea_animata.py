# -*- coding: utf-8 -*-
"""Tiene allineate le due versioni del programma: la normale (questa
cartella) e quella con le animazioni (la cartella gestionale-animata accanto).

Tutti i file devono essere uguali byte per byte, tranne:
- quelli che ogni versione ha suoi (PROPRI), da adattare a mano;
- quelli che esistono solo nell'animata (SOLO_ANIMATA);
- immagini e video della guida, che si rigenerano in ciascuna versione
  (RIGENERATI);
- quello che non e' sorgente (database delle prove, cartelle di costruzione).

    python strumenti/allinea_animata.py            # dice cosa e' diverso
    python strumenti/allinea_animata.py --copia    # copia nell'animata i file comuni cambiati

Esce con 1 se resta qualcosa di diverso (dopo --copia: solo se qualcosa non
si e' potuto allineare, per esempio un file che c'e' solo nell'animata)."""
import filecmp
import os
import shutil
import sys

QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NORMALE = QUI
ANIMATA = os.path.join(os.path.dirname(QUI), 'gestionale-animata')

PROPRI = {'CREA_SETUP.bat', 'LEGGIMI.md', 'installer.iss', 'templates/base.html', 'templates/griglia.html',
          'templates/impostazioni.html'}
SOLO_ANIMATA = ('static/animazioni.css', 'static/animazioni.js', 'static/animazioni/', 'prove_animazioni.py',
                'prove_icone_animate.py')
RIGENERATI = ('static/guida/', 'static/video/')
CARTELLE_ESCLUSE = {'__pycache__', 'build', 'dist', 'Output', '.venv', '.git', 'prove_animazioni_foto'}
ESTENSIONI_ESCLUSE = ('.db', '.db-wal', '.db-shm', '.pyc', '.log', '.conflitto')
FILE_ESCLUSI = {'campagna-progresso.txt'}


def file_di(radice):
    uscita = set()
    for cartella, sotto, nomi in os.walk(radice):
        sotto[:] = [s for s in sotto if s not in CARTELLE_ESCLUSE and not s.endswith('_tmp')]
        for nome in nomi:
            if nome.endswith(ESTENSIONI_ESCLUSE) or nome in FILE_ESCLUSI:
                continue
            uscita.add(os.path.relpath(os.path.join(cartella, nome), radice).replace(os.sep, '/'))
    return uscita


def escluso(percorso):
    return percorso in PROPRI or percorso.startswith(SOLO_ANIMATA) or percorso.startswith(RIGENERATI)


def main():
    copia = '--copia' in sys.argv[1:]
    if not os.path.isdir(ANIMATA):
        print('Manca la cartella della versione animata: %s' % ANIMATA)
        return 1
    normale, animata = file_di(NORMALE), file_di(ANIMATA)
    diversi, mancanti, in_piu = [], [], []
    for f in sorted(normale):
        if escluso(f):
            continue
        if f not in animata:
            mancanti.append(f)
        elif not filecmp.cmp(os.path.join(NORMALE, f), os.path.join(ANIMATA, f), shallow=False):
            diversi.append(f)
    for f in sorted(animata - normale):
        if not escluso(f):
            in_piu.append(f)
    for f in (diversi + mancanti) if copia else []:
        destinazione = os.path.join(ANIMATA, f)
        os.makedirs(os.path.dirname(destinazione), exist_ok=True)
        shutil.copy2(os.path.join(NORMALE, f), destinazione)
    for nome, elenco in (('copiati' if copia else 'diversi', diversi), ('nuovi' if copia else 'mancano nell\'animata', mancanti),
                         ('solo nell\'animata (da togliere o da portare nella normale)', in_piu)):
        for f in elenco:
            print('%-12s %s' % (nome.split(' ')[0], f))
    restano = in_piu if copia else diversi + mancanti + in_piu
    print('%d file comuni, %s' % (len([f for f in normale if not escluso(f)]),
                                  'tutti uguali' if not restano else '%d da sistemare' % len(restano)))
    return 1 if restano else 0


if __name__ == '__main__':
    sys.exit(main())
