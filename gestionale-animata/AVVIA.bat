@echo off
REM Avvia il gestionale senza finestre e apre il browser.
REM Se e' gia' in esecuzione apre solo il browser: cliccare due volte non fa danni.
cd /d "%~dp0"
if exist "%~dp0Gestionale.exe" (
    start "" "%~dp0Gestionale.exe"
) else if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0app.py"
) else (
    start "" pythonw "%~dp0app.py"
)
exit /b 0
