@echo off
REM Ferma il gestionale, se serve riavviarlo o fare un backup a freddo.
title Gestionale Agende - arresto
REM per nome e non per porta (1.11): il gestionale puo' essere su una porta di riserva, e sulla
REM 5000 puo' esserci un altro programma, che non va chiuso
taskkill /F /IM Gestionale.exe >nul 2>&1 && echo Gestionale fermato. || echo Non risultava in esecuzione.
pause
