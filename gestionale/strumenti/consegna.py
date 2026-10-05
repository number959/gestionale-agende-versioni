# -*- coding: utf-8 -*-
"""Prepara i file da mandare dove c'e' un limite di dimensione (per esempio
una chat: circa 30 MB a file). Ogni file piu' grande del massimo si divide in
pezzi (nome.parte1, nome.parte2, ...) e RICOMPONI.bat li rimette insieme su
Windows, controllando dimensione e impronta SHA-256 (con certutil, che c'e'
in ogni Windows); i file piccoli si copiano come sono.

    python strumenti/consegna.py <cartella con i file> <cartella di uscita> [--massimo 25]

Su GitHub i Setup si pubblicano interi (fino a 2 GB a file): i pezzi servono
solo per passarli a mano."""
import argparse
import hashlib
import math
import os
import shutil
import sys

BAT = r'''@echo off
setlocal
title Gestionale Agende - ricomposizione dei file
cd /d "%~dp0"
set ERRORI=0
echo.
echo   Ricompongo i file arrivati in pezzi (nella stessa cartella di questo file).
echo.
{chiamate}
echo.
if "%ERRORI%"=="0" (
    echo   Fatto. I pezzi ^(.parte1, .parte2 ...^) si possono cancellare.
) else (
    echo   Qualcosa non e' andato, vedi sopra: sistemato, rilanciare RICOMPONI.bat.
)
echo.
pause
exit /b 0

:uno
REM %1 nome, %2 impronta SHA-256, %3 dimensione, %4 numero dei pezzi
if not exist "%~1.parte1" goto :eof
set PEZZI=
for /l %%i in (1,1,%~4) do (
    if not exist "%~1.parte%%i" (
        echo   %~1: manca %~1.parte%%i, va scaricato nella stessa cartella.
        set ERRORI=1
        goto :eof
    )
)
set ELENCO="%~1.parte1"
for /l %%i in (2,1,%~4) do call set ELENCO=%%ELENCO%% + "%~1.parte%%i"
copy /b %ELENCO% "%~1" >nul
set DIM=0
for %%f in ("%~1") do set DIM=%%~zf
if not "%DIM%"=="%~3" (
    echo   %~1: la dimensione non torna. Riscaricare i pezzi.
    del "%~1"
    set ERRORI=1
    goto :eof
)
certutil -hashfile "%~1" SHA256 > "%TEMP%\ricomponi-impronta.txt" 2>nul
findstr /i /c:"SHA256" "%TEMP%\ricomponi-impronta.txt" >nul
if errorlevel 1 (
    echo   Pronto: %~1 ^(dimensione controllata^)
    goto :eof
)
findstr /i /c:"%~2" "%TEMP%\ricomponi-impronta.txt" >nul
if errorlevel 1 (
    echo   %~1: il file ricomposto non e' quello giusto. Riscaricare i pezzi.
    del "%~1"
    set ERRORI=1
    goto :eof
)
echo   Pronto e controllato: %~1
goto :eof
'''


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('sorgente')
    p.add_argument('uscita')
    p.add_argument('--massimo', type=float, default=25, help='MB al massimo per file (predefinito 25)')
    a = p.parse_args()
    massimo = int(a.massimo * 1024 * 1024)
    os.makedirs(a.uscita, exist_ok=True)
    chiamate = []
    for nome in sorted(os.listdir(a.sorgente)):
        percorso = os.path.join(a.sorgente, nome)
        if not os.path.isfile(percorso):
            continue
        dimensione = os.path.getsize(percorso)
        if dimensione <= massimo:
            shutil.copy2(percorso, os.path.join(a.uscita, nome))
            print('%-45s %8.1f MB  copiato intero' % (nome, dimensione / 1048576))
            continue
        pezzi = math.ceil(dimensione / massimo)
        passo = math.ceil(dimensione / pezzi)
        impronta = hashlib.sha256()
        with open(percorso, 'rb') as f:
            for i in range(1, pezzi + 1):
                blocco = f.read(passo)
                impronta.update(blocco)
                with open(os.path.join(a.uscita, '%s.parte%d' % (nome, i)), 'wb') as g:
                    g.write(blocco)
        chiamate.append('call :uno "%s" %s %d %d' % (nome, impronta.hexdigest(), dimensione, pezzi))
        print('%-45s %8.1f MB  in %d pezzi' % (nome, dimensione / 1048576, pezzi))
    if chiamate:
        testo = BAT.replace('{chiamate}', '\n'.join(chiamate))
        with open(os.path.join(a.uscita, 'RICOMPONI.bat'), 'wb') as f:
            f.write(testo.replace('\r\n', '\n').replace('\n', '\r\n').encode('ascii'))
        print('RICOMPONI.bat: %d file da ricomporre' % len(chiamate))
    # controllo: i pezzi rimessi insieme danno i file di partenza
    for riga in chiamate:
        nome = riga.split('"')[1]
        pezzi = int(riga.split()[-1])
        dati = b''.join(open(os.path.join(a.uscita, '%s.parte%d' % (nome, i)), 'rb').read() for i in range(1, pezzi + 1))
        assert dati == open(os.path.join(a.sorgente, nome), 'rb').read(), nome
    return 0


if __name__ == '__main__':
    sys.exit(main())
