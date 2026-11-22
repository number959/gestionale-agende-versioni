@echo off
setlocal
title Gestionale Agende - pacchetto di prova
REM Il pacchetto di prova per Giovanni (prova.py, gestionale-prova.spec): un .exe solo, con i dati
REM inventati, che non tocca il programma della clinica. Si lancia nella cartella gestionale-animata
REM (la variante della clinica). Facoltativo: il numero della tappa (CREA_PROVA.bat 2), altrimenti 1.
REM Mai un Setup per la prova: installer.iss ha lo stesso AppId del programma della clinica.
cd /d "%~dp0"
set TAPPA=%~1
if "%TAPPA%"=="" set TAPPA=1
if not exist static\animazioni.css goto :non_animata
echo.
echo   Creo il pacchetto di prova (tappa %TAPPA%). Ci vogliono un paio di minuti.
echo.

where python >nul 2>&1
if errorlevel 1 goto :senza_python
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 goto :python_vecchio

REM Versione di Python del computer e di quella con cui era stato creato .venv.
REM Se sono diverse l'ambiente isolato va rifatto: riusarlo porterebbe dentro
REM librerie compilate per un altro Python.
set PY_SISTEMA=
set PY_VENV=
for /f "usebackq delims=" %%v in (`python -c "import sys; print(sys.version_info[0], sys.version_info[1], sep='.')"`) do set PY_SISTEMA=%%v
if exist .venv\Scripts\python.exe for /f "usebackq delims=" %%v in (`.venv\Scripts\python.exe -c "import sys; print(sys.version_info[0], sys.version_info[1], sep='.')" 2^>nul`) do set PY_VENV=%%v
echo   Python in uso: %PY_SISTEMA%
if not "%PY_VENV%"=="%PY_SISTEMA%" if exist .venv (
    echo   L'ambiente isolato esistente non corrisponde a questo Python: lo rifaccio.
    rmdir /s /q .venv
)

echo   [1/3] Preparo l'ambiente isolato...
if not exist .venv\Scripts\python.exe python -m venv .venv
REM si controlla il risultato, non il codice di uscita: se un programma va in
REM crash il codice e' negativo e "if errorlevel 1" non se ne accorge
if not exist .venv\Scripts\python.exe goto :errore

echo   [2/3] Scarico le librerie...
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet --disable-pip-version-check
REM --only-binary: solo pacchetti gia' compilati. Senza, se per questo Python
REM manca un pacchetto pronto pip prova a compilarlo, e su Windows senza
REM compilatore C fallisce con un errore lungo e poco chiaro.
.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements-build.txt --quiet --disable-pip-version-check
if %errorlevel% neq 0 goto :errore_librerie

echo   [3/3] Compilo il pacchetto di prova...
.venv\Scripts\python.exe strumenti\crea_prova.py --tappa %TAPPA%
if %errorlevel% neq 0 goto :errore
if not exist dist\LEGGIMI-PROVA.txt goto :errore

echo.
echo   Pronto: in dist il file GestionaleProva-...exe e LEGGIMI-PROVA.txt.
echo   Si passano tutti e due a chi prova: niente Setup, niente installazione.
echo.
pause
exit /b 0

:senza_python
echo.
echo   Serve Python installato per costruire l'eseguibile: dalla 3.10 in su,
echo   da https://www.python.org/downloads/ spuntando "Add python.exe to PATH".
echo   Una volta creato, il .exe gira anche su computer senza Python.
echo.
pause
exit /b 1

:python_vecchio
echo.
echo   La versione di Python installata e' troppo vecchia: serve la 3.10 o successiva.
echo.
pause
exit /b 1

:non_animata
echo.
echo   Il pacchetto di prova si fa dalla cartella gestionale-animata, la variante
echo   che c'e' in clinica: lanciare CREA_PROVA.bat da li'.
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
echo   Creazione non riuscita. Dettaglio nelle righe sopra.
echo.
pause
exit /b 1
