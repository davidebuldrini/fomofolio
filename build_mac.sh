#!/usr/bin/env bash
# Build dist/InvestTrack.app and dist/InvestTrack-macos-<arch>.dmg.
# Uses the active Python if one is set up (CI), otherwise ./venv.
set -euo pipefail

# If this shell runs under Rosetta on Apple Silicon, a universal2 Python would
# build an x86_64 app. Restart natively.
if [[ "$(sysctl -n sysctl.proc_translated 2>/dev/null || echo 0)" == "1" ]]; then
  exec arch -arm64 /bin/bash "$0" "$@"
fi
cd "$(dirname "$0")"

if [[ -z "${VIRTUAL_ENV:-}" && -z "${CI:-}" ]]; then
  [[ -d venv ]] || python3 -m venv venv
  source venv/bin/activate
fi

python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt

rm -rf build dist
python -m PyInstaller --noconfirm InvestTrack.spec

# Ad-hoc signature so Gatekeeper does not report the app as damaged.
codesign --force --deep --sign - dist/InvestTrack.app

ARCH="$(uname -m)"
[[ "$ARCH" == "x86_64" ]] && ARCH="x64"
DMG="dist/InvestTrack-macos-${ARCH}.dmg"
STAGE="$(mktemp -d)"
cp -R dist/InvestTrack.app "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname InvestTrack -srcfolder "$STAGE" -ov -format UDZO "$DMG"
rm -rf "$STAGE"

echo "Built dist/InvestTrack.app and $DMG"
