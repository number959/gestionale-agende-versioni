# -*- mode: python ; coding: utf-8 -*-
"""Ricetta PyInstaller del PACCHETTO DI PROVA (prova.py), non del programma della clinica (gestionale.spec).

Si fa dalla cartella gestionale-animata, la variante che c'e' in clinica, con
    CREA_PROVA.bat                              (su Windows)
    python strumenti/crea_prova.py --tappa 1    (su Linux, o dentro .venv)
che scrive firma_prova.json (tappa, commit, giorno, ora) e poi lancia
    pyinstaller --clean --noconfirm gestionale-prova.spec
Il risultato e' dist/GestionaleProva-tappa1-<commit>-<giorno>.exe: un file solo, da aprire con un doppio
clic, con accanto LEGGIMI-PROVA.txt. Non c'e' Setup e non ce ne deve essere uno: installer.iss ha lo stesso
AppId del programma della clinica e lo sostituirebbe. Il nome non e' mai «Gestionale.exe»: FERMA.bat e il
Setup chiudono per nome (taskkill /IM Gestionale.exe) e l'autoriparazione, senza i dati del processo,
riconosce il programma dal nome.
"""
import json
import os

from PyInstaller.utils.hooks import collect_data_files

with open(os.path.join(SPECPATH, 'firma_prova.json'), encoding='utf-8') as f:  # noqa: F821 (SPECPATH: PyInstaller)
    FIRMA = json.load(f)
if not os.path.exists(os.path.join(SPECPATH, 'static', 'animazioni.css')) and \
        os.environ.get('PROVA_VARIANTE') != 'normale':  # noqa: F821
    raise SystemExit('Il pacchetto di prova si fa dalla cartella gestionale-animata: e\' la variante della '
                     'clinica (per la normale: PROVA_VARIANTE=normale).')
NOME = 'GestionaleProva-tappa%s-%s-%s' % (FIRMA['tappa'], FIRMA['commit'].replace('+', '-'), FIRMA['giorno'])
assert NOME.lower().startswith('gestionaleprova-') and NOME.lower() != 'gestionale', NOME

analisi = Analysis(
    ['prova.py'],
    pathex=['.'],
    binaries=[],
    # come gestionale.spec (templates, static, modelli_email, dati, certifi) piu' la firma del pacchetto
    datas=[('templates', 'templates'), ('static', 'static'), ('modelli_email', 'modelli_email'), ('dati', 'dati'),
           ('firma_prova.json', '.')]
    + collect_data_files('certifi'),
    hiddenimports=[
        'waitress', 'waitress.server',
        'sqlalchemy.dialects.sqlite', 'sqlalchemy.sql.default_comparator',
        'openpyxl', 'openpyxl.drawing.image',
        'PIL.Image', 'PIL._imaging', 'PIL.ImageDraw',
        # il programma e i dati inventati: prova.py li importa dentro le funzioni, PyInstaller da solo non li vede
        'app', 'seed', 'strumenti.dati_prova', 'strumenti.catalogo_prova',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pydoc', 'doctest', 'test',
              'numpy', 'pandas', 'matplotlib', 'scipy',
              'pysqlite2', 'MySQLdb', 'psycopg2'],
    noarchive=False,
)
pyz = PYZ(analisi.pure)

esecutivo = EXE(
    pyz,
    analisi.scripts,
    analisi.binaries,
    analisi.datas,
    [],
    name=NOME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # come il programma vero: gli errori vanno in prova.log, nella cartella della prova
    disable_windowed_traceback=False,
    icon='static/icona.ico',
)
