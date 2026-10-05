#!/bin/bash
# Impostazioni comuni degli script di strumenti/wine (si legge con ". ambiente.sh").
# Un Windows finto (Wine) per costruire e provare eseguibile e Setup su Linux, per
# esempio in una sessione di Claude Code nel cloud. Sul PC con Windows non serve:
# bastano CREA_EXE.bat e CREA_SETUP.bat (vedi LEGGIMI, «Ricostruire l'installatore»).
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine-gestionale}"
export WINEDEBUG=-all
export WINEPATH='C:\Python314;C:\Python314\Scripts'
WINE="$(command -v wine64 || command -v wine || true)"
[ -n "$WINE" ] || WINE=/usr/lib/wine/wine64
# il Python di Windows non deve leggere la configurazione di pip di Linux
unset PIP_CONFIG_FILE
# dietro un proxy che controlla i certificati (come nelle sessioni nel cloud) pip dentro
# Wine deve conoscere lo stesso certificato: lo stesso file, visto da Windows (Z: e' la radice)
ENV_CERTIFICATI=()
if [ -n "${SSL_CERT_FILE:-}" ] && [ -f "$SSL_CERT_FILE" ]; then
    CERT_WIN="Z:$(printf '%s' "$SSL_CERT_FILE" | sed 's#/#\\#g')"
    ENV_CERTIFICATI=(PIP_CERT="$CERT_WIN" SSL_CERT_FILE="$CERT_WIN" REQUESTS_CA_BUNDLE="$CERT_WIN")
fi
# lo schermo finto per le finestre di Windows (il Setup mostra la sua barra)
schermo_pronto() {
    if command -v xdpyinfo >/dev/null 2>&1; then
        xdpyinfo -display "$DISPLAY" >/dev/null 2>&1
    else
        # senza xdpyinfo: qualcuno risponde sul file dello schermo? (puo' esserne rimasto uno vecchio)
        local n="${DISPLAY#*:}"
        python3 -c 'import socket, sys; socket.socket(socket.AF_UNIX).connect(sys.argv[1])' \
            "/tmp/.X11-unix/X${n%%.*}" 2>/dev/null
    fi
}
avvia_schermo() {
    export DISPLAY="${DISPLAY:-:93}"
    schermo_pronto && return 0
    (Xvfb "$DISPLAY" -screen 0 1366x900x24 >/dev/null 2>&1 &)
    for i in $(seq 1 20); do
        schermo_pronto && return 0
        sleep 0.5
    done
    echo "lo schermo finto non parte (Xvfb $DISPLAY)" >&2
    return 1
}
# la cartella dei dati del programma installato nel Windows finto
CARTELLA_DATI="$WINEPREFIX/drive_c/users/$(id -un)/AppData/Local/GestionaleAgende"
# i programmi dentro Wine vogliono un terminale vero: senza, il Python dell'eseguibile non
# trova i suoi stdin e stdout ("can't initialize sys standard streams"). "script" glielo da'
in_terminale() {
    script -qec "$1" /dev/null
}
# il terminale di Wine scrive codici di controllo (anche gli spazi diventano "sposta a destra"): via
senza_codici() {
    sed -e 's/\x1b\[[0-9]*C/ /g' -e 's/\x1b\[[0-9;?]*[A-Za-z]//g' -e 's/\r//g'
}
