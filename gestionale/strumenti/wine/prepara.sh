#!/bin/bash
# Prepara una volta sola il Windows finto (Wine) con Python e Inno Setup, per
# costruire e provare eseguibile e Setup su Linux (Ubuntu/Debian). Si puo'
# rilanciare: salta quello che c'e' gia'.
#
#   bash strumenti/wine/prepara.sh
#
# Scarica: i pacchetti di Wine (64 e 32 bit: ISCC di Inno Setup e' a 32 bit),
# Python per Windows dal pacchetto NuGet "python" (la cartella tools, senza
# installatore) e Inno Setup 6 dalla sua pagina delle versioni su GitHub.
set -e
cd "$(dirname "$0")"
PYTHON_VERSIONE="${PYTHON_VERSIONE:-3.14.8}"
INNO_VERSIONE="${INNO_VERSIONE:-6.7.3}"

if ! dpkg -s wine64 >/dev/null 2>&1 || ! dpkg -s wine32:i386 >/dev/null 2>&1 || ! command -v Xvfb >/dev/null; then
    echo "== pacchetti: wine64, wine32, xvfb"
    SUDO=""; [ "$(id -u)" = 0 ] || SUDO=sudo
    $SUDO dpkg --add-architecture i386
    $SUDO apt-get update -q
    DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y -q wine64 wine32:i386 xvfb x11-utils unzip curl
fi
. ./ambiente.sh
avvia_schermo
if [ ! -f "$WINEPREFIX/system.reg" ]; then
    echo "== Windows finto in $WINEPREFIX"
    "$WINE" wineboot -i >/dev/null 2>&1 || true
    sleep 3
fi
PYDIR="$WINEPREFIX/drive_c/Python314"
if [ ! -f "$PYDIR/python.exe" ]; then
    echo "== Python $PYTHON_VERSIONE per Windows"
    TMP="$(mktemp -d)"
    curl -fsSL -o "$TMP/python.nupkg" "https://api.nuget.org/v3-flatcontainer/python/$PYTHON_VERSIONE/python.$PYTHON_VERSIONE.nupkg"
    unzip -q "$TMP/python.nupkg" 'tools/*' -d "$TMP"
    mkdir -p "$PYDIR"
    cp -r "$TMP/tools/." "$PYDIR/"
    rm -rf "$TMP"
fi
# Wine 9 non ha KERNEL32.CopyFile2 (su Windows 10/11 c'e'): Python 3.14 lo usa in
# shutil.copy2 e senza questo si ferma gia' creando l'ambiente isolato di CREA_EXE.bat.
# Tolto, shutil fa la copia normale. Vale solo per il Python del Windows finto: il
# programma non usa shutil.copy2 e sul PC della clinica non cambia niente.
if [ ! -f "$PYDIR/Lib/sitecustomize.py" ]; then
    cat > "$PYDIR/Lib/sitecustomize.py" <<'PY'
# SOLO NEL WINDOWS FINTO (Wine): Wine 9 non implementa KERNEL32.CopyFile2, che su
# Windows 10/11 esiste. Togliendolo, shutil usa la copia generica.
try:
    import _winapi
    del _winapi.CopyFile2
except (ImportError, AttributeError):
    pass
PY
fi
ISCC="$WINEPREFIX/drive_c/Program Files (x86)/Inno Setup 6/ISCC.exe"
if [ ! -f "$ISCC" ]; then
    echo "== Inno Setup $INNO_VERSIONE"
    TMP="$(mktemp -d)"
    curl -fsSL -o "$TMP/innosetup.exe" \
        "https://github.com/jrsoftware/issrc/releases/download/is-${INNO_VERSIONE//./_}/innosetup-$INNO_VERSIONE.exe"
    cp "$TMP/innosetup.exe" "$WINEPREFIX/drive_c/innosetup.exe"
    (cd "$WINEPREFIX/drive_c" && timeout 300 bash -c "script -qec '$WINE C:\\\\innosetup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /ALLUSERS' /dev/null" >/dev/null 2>&1 || true)
    rm -rf "$TMP" "$WINEPREFIX/drive_c/innosetup.exe"
fi
echo "== controllo"
(cd "$WINEPREFIX/drive_c" && in_terminale "$WINE C:\\\\Python314\\\\python.exe -c \"import os, shutil, ssl, sys, tempfile; d = tempfile.mkdtemp(); open(os.path.join(d, 'a'), 'w').close(); shutil.copy2(os.path.join(d, 'a'), os.path.join(d, 'b')); shutil.rmtree(d); print('Python', sys.version.split()[0], 'pronto')\"" 2>/dev/null | senza_codici | tail -1)
[ -f "$ISCC" ] && echo "Inno Setup pronto: $ISCC" || { echo "Inno Setup NON installato"; exit 1; }
echo "Windows finto pronto in $WINEPREFIX"
