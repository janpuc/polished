#!/bin/sh
# The web's tips against the app's, for twelve fixture recipes at tip-xl, light and dark:
# ~/.cache/polished/native/parity.png (web light, swift light, web dark, swift dark).
# Needs Chromium for Playwright (see the README's Testing section) and a built app.
#
#   app/Scripts/parity.sh
set -eu
cd "$(dirname "$0")/.."
ROOT="$(cd .. && pwd)"
WORK="${TMPDIR:-/tmp}/polished-parity"
mkdir -p "$WORK" "$HOME/.cache/polished/native"

xcodegen generate -q
UDID=$(xcrun simctl list devices available -j | python3 -c '
import json, sys
for runtime, devices in json.load(sys.stdin)["devices"].items():
    if runtime.endswith("iOS-27-0"):
        for d in devices:
            if d["name"] == "iPhone 18 Pro":
                print(d["udid"])
' | head -1)
xcodebuild build -project Polished.xcodeproj -scheme Polished \
  -destination "platform=iOS Simulator,id=$UDID" -derivedDataPath build/DerivedData \
  CODE_SIGNING_ALLOWED=NO 2>&1 | grep -E "error:|BUILD"
xcrun simctl boot "$UDID" 2>/dev/null || true
xcrun simctl bootstatus "$UDID" -b >/dev/null
xcrun simctl install "$UDID" build/DerivedData/Build/Products/Debug-iphonesimulator/Polished.app
for scheme in light dark; do
  xcrun simctl ui "$UDID" appearance "$scheme"
  xcrun simctl terminate "$UDID" com.janpuc.polished >/dev/null 2>&1 || true
  xcrun simctl launch "$UDID" com.janpuc.polished -screen parity >/dev/null
  sleep 3
  xcrun simctl io "$UDID" screenshot "$WORK/sim-$scheme.png" >/dev/null 2>&1
done
xcrun simctl ui "$UDID" appearance light

(cd "$ROOT" && uvx --from playwright --with-editable . python -I app/Scripts/parity/web_tips.py "$WORK")
uvx --from pillow python -I Scripts/parity/montage.py "$WORK" "$HOME/.cache/polished/native/parity.png"
