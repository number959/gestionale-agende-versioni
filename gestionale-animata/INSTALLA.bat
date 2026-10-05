@echo off
setlocal
title Gestionale Agende - installazione
cd /d "%~dp0"
echo.
echo   GESTIONALE AGENDE
echo   Installazione sul computer della segreteria
echo.

where python >nul 2>&1
if errorlevel 1 goto :senza_python
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 goto :python_vecchio

REM Se .venv e' stato creato con un altro Python va rifatto: le librerie
REM compilate dentro non funzionerebbero con quello attuale.
set PY_SISTEMA=
set PY_VENV=
for /f "usebackq delims=" %%v in (`python -c "import sys; print(sys.version_info[0], sys.version_info[1], sep='.')"`) do set PY_SISTEMA=%%v
if exist .venv\Scripts\python.exe for /f "usebackq delims=" %%v in (`.venv\Scripts\python.exe -c "import sys; print(sys.version_info[0], sys.version_info[1], sep='.')" 2^>nul`) do set PY_VENV=%%v
echo   Python in uso: %PY_SISTEMA%
if not "%PY_VENV%"=="%PY_SISTEMA%" if exist .venv (
    echo   L'ambiente isolato esistente non corrisponde a questo Python: lo rifaccio.
    rmdir /s /q .venv
)

echo   [1/4] Preparo l'ambiente isolato...
if not exist .venv\Scripts\python.exe python -m venv .venv
REM si controlla il risultato, non il codice di uscita: se un programma va in
REM crash il codice e' negativo e "if errorlevel 1" non se ne accorge
if not exist .venv\Scripts\python.exe goto :errore
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet --disable-pip-version-check
REM --only-binary: solo pacchetti gia' compilati, mai compilazione da sorgente
.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt --quiet --disable-pip-version-check
if %errorlevel% neq 0 goto :errore_librerie

echo   [2/4] Collegamento sul desktop...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$w = New-Object -ComObject WScript.Shell; $l = $w.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Agende.lnk'); $l.TargetPath = '%~dp0AVVIA.bat'; $l.WorkingDirectory = '%~dp0'; $l.IconLocation = '%~dp0static\icona.ico'; $l.WindowStyle = 7; $l.Description = 'Agenda delle stanze'; $l.Save()"
if errorlevel 1 echo   ATTENZIONE: collegamento non creato, si puo' fare a mano.

echo   [3/4] Avvio automatico all'accesso...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$w = New-Object -ComObject WScript.Shell; $l = $w.CreateShortcut([Environment]::GetFolderPath('Startup') + '\Agende.lnk'); $l.TargetPath = '%~dp0AVVIA.bat'; $l.WorkingDirectory = '%~dp0'; $l.IconLocation = '%~dp0static\icona.ico'; $l.WindowStyle = 7; $l.Save()"
if errorlevel 1 echo   ATTENZIONE: avvio automatico non registrato.

echo   [4/4] Primo avvio...
echo.
call "%~dp0AVVIA.bat"
echo.
echo   Fatto. Sul desktop c'e' l'icona "Agende".
echo   Il programma parte da solo a ogni accesso al computer.
echo.
pause
exit /b 0

:senza_python
echo.
echo   Python non risulta installato.
echo   Due strade:
echo     a) installare Python 3 da https://www.python.org/downloads/
echo        spuntando "Add python.exe to PATH", poi rilanciare questo file;
echo     b) oppure usare l'eseguibile: lanciare CREA_EXE.bat su un computer
echo        con Python, e copiare dist\Gestionale.exe su questo.
echo.
pause
exit /b 1

:python_vecchio
echo.
echo   La versione di Python installata e' troppo vecchia: serve la 3.10 o successiva.
echo.
pause
exit /b 1

:errore_librerie
echo.
echo   Non e' stato possibile scaricare le librerie. Le cause possibili:
echo     1. manca la connessione a internet, oppure un proxy o un firewall la blocca;
echo     2. una libreria non esiste ancora gia' pronta per Python %PY_SISTEMA%.
echo        Succede con le versioni di Python appena uscite. In questo caso
echo        installare la versione precedente da https://www.python.org/downloads/
echo        e rilanciare questo file: l'ambiente isolato si rifa' da solo.
echo.
pause
exit /b 1

:errore
echo.
echo   Installazione interrotta. Il dettaglio e' nelle righe sopra.
echo.
pause
exit /b 1
