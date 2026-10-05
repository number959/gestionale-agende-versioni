@echo off
title Gestionale Agende - creazione installatore
cd /d "%~dp0"
echo.
echo   Creo GestionaleAgende-setup.exe
echo.

if not exist dist\Gestionale.exe (
    echo   Manca dist\Gestionale.exe: lanciare prima CREA_EXE.bat
    pause
    exit /b 1
)

set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
    echo   Inno Setup non trovato.
    echo   Si scarica gratis da https://jrsoftware.org/isdl.php
    echo   Installarlo e rilanciare questo file.
    pause
    exit /b 1
)

if exist Output\GestionaleAgende-setup.exe del /q Output\GestionaleAgende-setup.exe
%ISCC% installer.iss
if %errorlevel% neq 0 goto :errore
if not exist Output\GestionaleAgende-setup.exe goto :errore

REM il file delle versioni per "Aggiorna adesso": si pubblica insieme al Setup
set PY=python
if exist .venv\Scripts\python.exe set PY=.venv\Scripts\python.exe
%PY% strumenti\prepara_aggiornamento.py
if %errorlevel% neq 0 echo   Attenzione: Output\aggiornamento.json non creato. Serve Python: rilanciare questo file dopo CREA_EXE.bat.

echo.
echo   Pronto: Output\GestionaleAgende-setup.exe
echo   E' l'unico file da portare sul PC della segreteria.
echo   Per l'aggiornamento dal programma si pubblicano insieme, nella stessa versione
echo   su GitHub: Output\GestionaleAgende-setup.exe e Output\aggiornamento.json
echo   (vedi LEGGIMI, "Pubblicare un aggiornamento").
echo.
pause
exit /b 0

:errore
echo.
echo   Creazione non riuscita. Dettaglio nelle righe sopra.
echo.
pause
exit /b 1
