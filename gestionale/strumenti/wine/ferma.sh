#!/bin/bash
# Chiude il programma installato nel Windows finto (e i terminali finti rimasti).
# Si cerca per nome del processo, non per testo nella riga di comando: cosi' non
# si chiude per sbaglio la shell che lancia il comando.
for nome in Gestionale.exe; do
    for p in $(ps -eo pid=,comm= | awk -v n="$nome" '$2==n {print $1}'); do kill "$p" 2>/dev/null || true; done
done
sleep 2
for p in $(ps -eo pid=,comm=,args= | awk '$2=="sleep" && $4=="36000" {print $1}'); do kill "$p" 2>/dev/null || true; done
echo "programma chiuso"
