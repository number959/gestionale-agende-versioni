# -*- mode: python ; coding: utf-8 -*-
"""Ricetta PyInstaller. Un solo file, niente finestra nera, icona della clinica.

Si usa cosi, sul PC dove deve girare:
    pyinstaller --clean --noconfirm gestionale.spec
Il risultato e' dist/Gestionale.exe (dist/Gestionale su Linux).
"""

analisi = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    # templates e static vanno portati dentro: Flask li cerca in sys._MEIPASS.
    # modelli_email: le informative della regola gia' pronta (preparazione endoscopie);
    # dati: comuni e stati esteri per il codice fiscale (codice_fiscale.py)
    datas=[('templates', 'templates'), ('static', 'static'), ('modelli_email', 'modelli_email'), ('dati', 'dati')],
    # PyInstaller non li trova da solo, sono importati a runtime
    hiddenimports=[
        'waitress', 'waitress.server',
        'sqlalchemy.dialects.sqlite', 'sqlalchemy.sql.default_comparator',
        'openpyxl', 'openpyxl.drawing.image',
        'PIL.Image', 'PIL._imaging',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pydoc', 'doctest', 'test',
              'numpy', 'pandas', 'matplotlib', 'scipy',
              # driver di altri database che SQLAlchemy elenca: non servono,
              # e senza escluderli la compilazione stampa avvisi che sembrano errori
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
    name='Gestionale',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # nessuna finestra: gli errori vanno su gestionale.log
    disable_windowed_traceback=False,
    icon='static/icona.ico',
)
