#!/usr/bin/env bash
# Builds galaxyxr-vrlink-<version>-linux-x64.zip: a single-file GUI binary plus the driver folder.
# Linux counterpart of build-release.ps1. Requires Python 3.11+ with tkinter (Arch: `tk`,
# Debian/Ubuntu: `python3-tk`). Installs PyInstaller into a local venv on first run.
# Usage: build/build-release.sh [--skip-venv]
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="$(tr -d '[:space:]' < "$root/VERSION")"
dist="$root/dist"
venv="$root/.venv-linux"   # separate from the Windows .venv when the checkout is shared
name="galaxyxr-vrlink-$version-linux-x64"

py="${PYTHON:-python3}"
if [[ "${1:-}" != "--skip-venv" ]]; then
    [[ -x "$venv/bin/python" ]] || "$py" -m venv "$venv"
    "$venv/bin/python" -m pip install --upgrade pip pyinstaller
    py="$venv/bin/python"
fi
"$py" -c 'import tkinter' || { echo "tkinter is missing for $py (install tk / python3-tk)" >&2; exit 1; }
"$py" -m PyInstaller --version

rm -rf "$dist/exe-linux" "$dist/$name" "$dist/$name.zip" "$dist/$name.zip.sha256"
mkdir -p "$dist"
"$py" -m PyInstaller --noconfirm --clean --onefile --windowed \
    --name GalaxyXR-VRLink-Setup \
    --distpath "$dist/exe-linux" --workpath "$root/build/pyi-linux" --specpath "$root/build/pyi-linux" \
    --add-data "$root/driver:driver" \
    --add-data "$root/VERSION:." \
    --add-data "$root/app/galaxyxr_vrlink/icon.png:galaxyxr_vrlink" \
    --paths "$root/app" \
    "$root/app/launcher.py"
exe="$dist/exe-linux/GalaxyXR-VRLink-Setup"
[[ -x "$exe" ]] || { echo "PyInstaller did not produce $exe" >&2; exit 1; }

stage="$dist/$name"
mkdir -p "$stage"
cp "$exe" "$stage/"
cp -r "$root/driver" "$stage/driver"
cp "$root/VERSION" "$root/README.md" "$stage/"
# Python's zipfile keeps the exec bit in the archive (restored by `unzip`), and needs no zip tool.
(cd "$stage" && "$py" -m zipfile -c "../$name.zip" GalaxyXR-VRLink-Setup driver VERSION README.md)
(cd "$dist" && sha256sum "$name.zip" > "$name.zip.sha256")
echo "built $dist/$name.zip"
cat "$dist/$name.zip.sha256"
