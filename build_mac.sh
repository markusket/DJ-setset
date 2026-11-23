#!/bin/bash
# Rakentaa tuplaklikattavan Setinrakentaja.app-sovelluksen macOS:lle.
# Käyttö: ./build_mac.sh   (valmis sovellus: dist/Setinrakentaja.app)
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
if [ ! -d .venv ]; then
  "$PY" -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements-dev.txt

echo "== Testit =="
QT_QPA_PLATFORM=offscreen python -m pytest -q

echo "== PyInstaller =="
pyinstaller --noconfirm --clean setinrakentaja.spec

echo
echo "Valmis: dist/Setinrakentaja.app"
echo "Siirrä se Ohjelmat-kansioon (Applications). Ensimmäisellä kerralla avaa hiiren oikealla > Avaa."
