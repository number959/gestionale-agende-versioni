#!/bin/bash
# Costruisce, dentro il Windows finto, l'eseguibile e il Setup della cartella del
# programma (questa, o quella indicata), con gli stessi CREA_EXE.bat e
# CREA_SETUP.bat che si usano su Windows. Il risultato (Setup e file delle
# versioni) torna in <cartella>/Output.
#
#   bash strumenti/wine/costruisci.sh [cartella del programma]
#
# Prima, una volta sola: bash strumenti/wine/prepara.sh
set -e
QUI="$(cd "$(dirname "$0")" && pwd)"
CARTELLA="$(cd "${1:-$QUI/../..}" && pwd)"
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
