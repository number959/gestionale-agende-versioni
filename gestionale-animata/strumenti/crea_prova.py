# -*- coding: utf-8 -*-
"""Costruisce il pacchetto di prova per Giovanni (prova.py, gestionale-prova.spec), dalla cartella
gestionale-animata, la variante della clinica: scrive firma_prova.json (tappa, commit, giorno e ora) e lancia
PyInstaller. Alla fine in dist/ ci sono GestionaleProva-tappa<N>-<commit>-<giorno>.exe e LEGGIMI-PROVA.txt
con il nome vero del file.

    CREA_PROVA.bat [tappa]                                  (su Windows: prepara .venv e lancia questo)
    python strumenti/crea_prova.py --tappa 1                (su Linux, o con il Python di .venv)
    python strumenti/crea_prova.py --tappa 1 --solo-firma   (solo firma_prova.json: per costruire in Wine)

Con file cambiati e non salvati nel git il commit diventa «<commit>+modifiche»: il pacchetto non deve dire di
essere un commit che non e'. Senza git (la copia nel Windows finto di strumenti/wine) si tiene la firma gia'
scritta, e lo si dice. Mai un Setup per la prova: installer.iss ha lo stesso AppId del programma della clinica."""
import argparse
import glob
import json
import os
import subprocess
import sys
from datetime import datetime

QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIRMA = os.path.join(QUI, 'firma_prova.json')


def git(*a):
    return subprocess.run(['git'] + list(a), cwd=QUI, capture_output=True, text=True, check=True).stdout.strip()


def scrivi_firma(tappa):
    try:
        commit = git('rev-parse', '--short', 'HEAD')
        if git('status', '--porcelain', '--', '.'):
            commit += '+modifiche'
    except (OSError, subprocess.CalledProcessError):
        try:
            with open(FIRMA, encoding='utf-8') as f:
                firma = json.load(f)
        except (OSError, ValueError):
            raise SystemExit('Qui non c\'e\' git e manca firma_prova.json: scriverla prima con --solo-firma '
                             'dove c\'e\' il repository.')
        print('git non c\'e\': tengo la firma gia\' scritta', firma, flush=True)
        return firma
    adesso = datetime.now()
    firma = {'tappa': str(tappa), 'commit': commit, 'giorno': adesso.date().isoformat(),
             'costruito': adesso.isoformat(timespec='seconds')}
    with open(FIRMA, 'w', encoding='utf-8') as f:
        json.dump(firma, f)
    print('firma del pacchetto:', firma, flush=True)
    return firma


def leggimi(nome_file, firma):
    """LEGGIMI-PROVA.txt accanto all'eseguibile, con il nome vero del file (le righe con # sono per chi lo
    scrive), a capo di Windows e con il segno UTF-8 per il Blocco note."""
    with open(os.path.join(QUI, 'LEGGIMI-PROVA.txt'), encoding='utf-8') as f:
        righe = [r for r in f.read().splitlines() if not r.startswith('#')]
    testo = '\r\n'.join(righe).strip() + '\r\n'
    for chiave, valore in (('{file}', nome_file), ('{tappa}', firma['tappa']), ('{commit}', firma['commit']),
                           ('{giorno}', datetime.strptime(firma['giorno'], '%Y-%m-%d').strftime('%d/%m/%Y'))):
        testo = testo.replace(chiave, valore)
    with open(os.path.join(QUI, 'dist', 'LEGGIMI-PROVA.txt'), 'w', encoding='utf-8-sig', newline='') as f:
        f.write(testo)


def main():
    p = argparse.ArgumentParser(description='Costruisce il pacchetto di prova.')
    p.add_argument('--tappa', required=True)
    p.add_argument('--solo-firma', action='store_true', help='scrive solo firma_prova.json')
    arg = p.parse_args()
    firma = scrivi_firma(arg.tappa)
    if arg.solo_firma:
        return 0
    nome = 'GestionaleProva-tappa%s-%s-%s' % (firma['tappa'], firma['commit'].replace('+', '-'), firma['giorno'])
    for vecchio in glob.glob(os.path.join(QUI, 'dist', 'GestionaleProva-*')) + \
            glob.glob(os.path.join(QUI, 'dist', 'LEGGIMI-PROVA.txt')):
        os.remove(vecchio)
    r = subprocess.run([sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', '--log-level', 'WARN',
                        'gestionale-prova.spec'], cwd=QUI)
    fatti = glob.glob(os.path.join(QUI, 'dist', nome + '*'))
    if r.returncode or not fatti:
        print('Costruzione non riuscita (PyInstaller: %s).' % r.returncode)
        return 1
    nome_file = os.path.basename(fatti[0])
    assert nome_file.lower() not in ('gestionale.exe', 'gestionale'), nome_file
    leggimi(nome_file, firma)
    print('Pronto: dist%s%s (%.0f MB) e dist%sLEGGIMI-PROVA.txt'
          % (os.sep, nome_file, os.path.getsize(fatti[0]) / 1e6, os.sep), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
