#!/bin/bash
# Build ~/Applications/Dictate.app, a tiny launcher for the menu bar app.
# NOTE: rebuilding changes the app's signature, so macOS will ask you to
# re-grant Accessibility / Input Monitoring / Microphone to it.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
APP="$HOME/Applications/Dictate.app"
PY="$REPO/venv/bin/python"

[ -x "$PY" ] || { echo "No venv at $REPO/venv - see README (Install)."; exit 1; }
mkdir -p "$HOME/Applications"
rm -rf "$APP"

osacompile -o "$APP" -e "do shell script \"cd '$REPO' && nohup '$PY' -m holdspeak.menubar > /tmp/dictate.log 2>&1 &\""
"$PY" "$REPO/scripts/make_icon.py" "$APP/Contents/Resources/applet.icns"
plutil -insert LSUIElement -bool true "$APP/Contents/Info.plist"
codesign --force --deep --sign - "$APP"

echo "Built $APP"
echo "Grant it (and the venv's Python.app) Accessibility, Input Monitoring and Microphone."
