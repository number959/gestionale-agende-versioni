#!/bin/bash
# Costruisce, dentro il Windows finto, l'eseguibile e il Setup della cartella del
# programma (questa, o quella indicata), con gli stessi CREA_EXE.bat e
# CREA_SETUP.bat che si usano su Windows. Il risultato (Setup e file delle
# versioni) torna in <cartella>/Output.
#
#   bash strumenti/wine/costruisci.sh [cartella del programma]
#   bash strumenti/wine/costruisci.sh --prova [cartella]   # il pacchetto di prova (CREA_PROVA.bat), in <cartella>/dist/windows
#
# Con --prova la firma (commit e giorno) si scrive qui, dove c'e' git (strumenti/crea_prova.py --solo-firma):
# nel Windows finto git non c'e'. La tappa e' TAPPA (di solito 1). Mai un Setup per la prova.
# Prima, una volta sola: bash strumenti/wine/prepara.sh
set -e
QUI="$(cd "$(dirname "$0")" && pwd)"
PROVA=0
if [ "${1:-}" = "--prova" ]; then PROVA=1; shift; fi
CARTELLA="$(cd "${1:-$QUI/../..}" && pwd)"
if [ "$PROVA" = 1 ]; then
    (cd "$CARTELLA" && python3 strumenti/crea_prova.py --tappa "${TAPPA:-1}" --solo-firma)
fi
NOME="$(basename "$CARTELLA")"
. "$QUI/ambiente.sh"
DEST="$WINEPREFIX/drive_c/costruzione/$NOME"
echo "== copio $CARTELLA in C:\\costruzione\\$NOME"
python3 - "$CARTELLA" "$DEST" <<'PY'
import os, shutil, sys
sorgente, dest = sys.argv[1:3]
ESCLUSE = {'__pycache__', 'build', 'dist', 'Output', '.venv', '.git', 'prove_animazioni_foto'}
TENUTE = {'.venv', 'build'}                    # nella copia: l'ambiente di costruzione si riusa
os.makedirs(dest, exist_ok=True)
voluti = set()
for radice, sotto, nomi in os.walk(sorgente):
    sotto[:] = [s for s in sotto if s not in ESCLUSE and not s.endswith('_tmp')]
    for n in nomi:
        if n.endswith(('.db', '.db-wal', '.db-shm', '.pyc', '.log')):
            continue
        rel = os.path.relpath(os.path.join(radice, n), sorgente)
        voluti.add(rel)
        a, b = os.path.join(sorgente, rel), os.path.join(dest, rel)
        os.makedirs(os.path.dirname(b), exist_ok=True)
        shutil.copy2(a, b)
for radice, sotto, nomi in os.walk(dest):
    rel_radice = os.path.relpath(radice, dest)
    if rel_radice.split(os.sep)[0] in TENUTE | {'dist', 'Output'}:
        continue
    for n in nomi:
        rel = os.path.normpath(os.path.join(rel_radice, n))
        if rel not in voluti and not n.endswith('.log'):
            os.remove(os.path.join(radice, n))         # un file tolto dai sorgenti non resta nella copia
PY
cd "$DEST"
if [ "$PROVA" = 1 ]; then
    rm -f dist/GestionaleProva-* dist/LEGGIMI-PROVA.txt
    echo "== CREA_PROVA.bat (qualche minuto)"
    printf '\r\n\r\n\r\n' | env "${ENV_CERTIFICATI[@]}" timeout 1800 script -qec "$WINE cmd /c CREA_PROVA.bat ${TAPPA:-1}" /dev/null > crea_prova.log 2>&1 || true
    if ! ls dist/GestionaleProva-*.exe >/dev/null 2>&1 || [ ! -f dist/LEGGIMI-PROVA.txt ]; then
        echo "CREA_PROVA.bat non riuscito, ultime righe di $DEST/crea_prova.log:"; senza_codici < crea_prova.log | tail -25; exit 1
    fi
    mkdir -p "$CARTELLA/dist/windows"
    rm -f "$CARTELLA"/dist/windows/GestionaleProva-*
    cp dist/GestionaleProva-*.exe dist/LEGGIMI-PROVA.txt "$CARTELLA/dist/windows/"
    echo "== pronto in $CARTELLA/dist/windows:"
    ls -la "$CARTELLA/dist/windows"
    exit 0
fi
rm -rf dist Output
echo "== CREA_EXE.bat (qualche minuto)"
printf '\r\n\r\n\r\n' | env "${ENV_CERTIFICATI[@]}" timeout 1800 script -qec "$WINE cmd /c CREA_EXE.bat" /dev/null > crea_exe.log 2>&1 || true
if [ ! -f dist/Gestionale.exe ]; then
    echo "CREA_EXE.bat non riuscito, ultime righe di $DEST/crea_exe.log:"; senza_codici < crea_exe.log | tail -25; exit 1
fi
echo "== CREA_SETUP.bat"
printf '\r\n\r\n\r\n' | timeout 900 script -qec "$WINE cmd /c CREA_SETUP.bat" /dev/null > crea_setup.log 2>&1 || true
if ! ls Output/*setup.exe >/dev/null 2>&1 || ! ls Output/*.json >/dev/null 2>&1; then
    echo "CREA_SETUP.bat non riuscito, ultime righe di $DEST/crea_setup.log:"; senza_codici < crea_setup.log | tail -25; exit 1
fi
mkdir -p "$CARTELLA/Output"
cp Output/* "$CARTELLA/Output/"
echo "== pronto in $CARTELLA/Output:"
ls -la "$CARTELLA/Output"
