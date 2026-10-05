@echo off
REM Copia il database con la data nel nome e tiene gli ultimi 30 giorni.
REM Da impostare nell'Utilita' di pianificazione, una volta al giorno.
REM Modificare DESTINAZIONE con il percorso del NAS o della cartella Drive.
set DESTINAZIONE=D:\Backup\Agende

set ORIGINE=%LOCALAPPDATA%\GestionaleAgende\agende.db
if not exist "%ORIGINE%" echo Database non trovato in %ORIGINE% & exit /b 1
if not exist "%DESTINAZIONE%" mkdir "%DESTINAZIONE%"

for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set OGGI=%%d
copy /y "%ORIGINE%" "%DESTINAZIONE%\agende-%OGGI%.db" >nul
powershell -NoProfile -Command "Get-ChildItem '%DESTINAZIONE%\agende-*.db' | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item -Force"
exit /b 0
