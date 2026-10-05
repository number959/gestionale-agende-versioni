@echo off
REM Ferma il gestionale, se serve riavviarlo o fare un backup a freddo.
title Gestionale Agende - arresto
powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue; if ($c) { Stop-Process -Id $c.OwningProcess -Force; 'Gestionale fermato.' } else { 'Non risultava in esecuzione.' }"
pause
