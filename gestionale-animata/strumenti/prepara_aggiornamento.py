# -*- coding: utf-8 -*-
"""Scrive il file delle versioni accanto al Setup appena creato:
Output/aggiornamento.json (nella versione animata aggiornamento-animata.json).

Dentro: versione (da comune.py), nome del Setup, dimensione, impronta SHA-256,
data e novita' (da novita.py). Il programma installato lo legge per «Aggiorna
adesso»: va pubblicato insieme al Setup, nella stessa versione su GitHub o
nella stessa cartella (vedi LEGGIMI, «Pubblicare un aggiornamento»).

Lo lancia CREA_SETUP.bat dopo Inno Setup; a mano:
    python strumenti/prepara_aggiornamento.py [cartella del Setup]
Usa solo la libreria standard."""
import hashlib
import json
import os
import re
import sys
from datetime import date

QUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, QUI)
import novita  # noqa: E402


def versione_programma():
    with open(os.path.join(QUI, 'comune.py'), encoding='utf-8') as f:
        m = re.search(r"^VERSIONE = '([0-9.]+)'", f.read(), re.M)
    if not m:
        raise SystemExit('VERSIONE non trovata in comune.py')
    return m.group(1)


def principale(argomenti):
    animata = os.path.exists(os.path.join(QUI, 'static', 'animazioni.css'))
    setup = 'GestionaleAgende-animata-setup.exe' if animata else 'GestionaleAgende-setup.exe'
    nome = 'aggiornamento-animata.json' if animata else 'aggiornamento.json'
    cartella = argomenti[0] if argomenti else os.path.join(QUI, 'Output')
    percorso = os.path.join(cartella, setup)
    if not os.path.exists(percorso):
        print('  Manca %s: creare prima il Setup.' % percorso)
        return 1
    h, n = hashlib.sha256(), 0
    with open(percorso, 'rb') as f:
        if f.read(2) != b'MZ':
            print('  %s non è un programma Windows.' % percorso)
            return 1
        f.seek(0)
        for blocco in iter(lambda: f.read(1024 * 1024), b''):
            h.update(blocco)
            n += len(blocco)
    versione = versione_programma()
    if novita.confronta(novita.NOVITA[0][0], versione) != 0:
        print('  Attenzione: in novita.py la prima versione è la %s, il programma è la %s.' % (novita.NOVITA[0][0], versione))
    dati = {'programma': 'Gestionale Agende', 'variante': 'animata' if animata else 'normale', 'versione': versione,
            'file': setup, 'byte': n, 'sha256': h.hexdigest(), 'pubblicata': date.today().isoformat(),
            'novita': novita.per_manifesto()}
    uscita = os.path.join(cartella, nome)
    with open(uscita, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(dati, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print('  Pronto: %s (versione %s, %.1f MB)' % (uscita, versione, n / 1048576))
    return 0


if __name__ == '__main__':
    sys.exit(principale(sys.argv[1:]))
