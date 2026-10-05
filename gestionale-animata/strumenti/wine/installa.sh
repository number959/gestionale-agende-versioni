#!/bin/bash
# Installa un Setup nel Windows finto senza domande (/SILENT, come «Aggiorna
# adesso»): alla fine il Setup riapre il programma, che risponde su
# http://127.0.0.1:5000. Se c'e' gia' un programma installato, il Setup lo
# chiude e lo aggiorna: i dati restano.
#
#   bash strumenti/wine/installa.sh Output/GestionaleAgende-setup.exe
#
# I dati del programma installato: $CARTELLA_DATI (vedi ambiente.sh).
set -e
QUI="$(cd "$(dirname "$0")" && pwd)"
SETUP="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
[ -f "$SETUP" ] || { echo "uso: installa.sh <Setup.exe>"; exit 1; }
. "$QUI/ambiente.sh"
avvia_schermo
NOME="$(basename "$SETUP")"
cp "$SETUP" "$WINEPREFIX/drive_c/$NOME"
prima="$(curl -s --max-time 3 http://127.0.0.1:5000/aggiornamenti/stato.json | python3 -c 'import sys,json; print(json.load(sys.stdin)["avviato"])' 2>/dev/null || true)"
cd "$WINEPREFIX/drive_c"
# il terminale finto resta aperto (sleep): ci gira il programma che il Setup riapre
(nohup script -qec "$WINE C:\\\\$NOME /SILENT /SUPPRESSMSGBOXES /NORESTART /LOG=C:\\\\setup-installa.log; sleep 36000" /dev/null \
    > "$WINEPREFIX/drive_c/installa.out" 2>&1 &)
for i in $(seq 1 120); do
    sleep 2
    adesso="$(curl -s --max-time 3 http://127.0.0.1:5000/aggiornamenti/stato.json | python3 -c 'import sys,json; print(json.load(sys.stdin)["avviato"])' 2>/dev/null || true)"
    if [ -n "$adesso" ] && [ "$adesso" != "$prima" ]; then
        versione="$(curl -s http://127.0.0.1:5000/aggiornamenti/stato.json | python3 -c 'import sys,json; print(json.load(sys.stdin)["versione"])')"
        echo "installato e aperto: versione $versione su http://127.0.0.1:5000 (dati in $CARTELLA_DATI)"
        exit 0
    fi
done
echo "il programma non risponde dopo 4 minuti: registro del Setup in $WINEPREFIX/drive_c/setup-installa.log"
exit 1
