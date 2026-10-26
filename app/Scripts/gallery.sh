#!/bin/sh
# The tip gallery (-screen gallery) scrolled top to bottom on three simulators, in light and dark
# appearance, one XCUITest run each; the screenshots land in ~/.cache/polished/native/gallery/
# <device>-<light|dark>/. The iPhone 18 Pro and iPad Pro are on iOS 27.0, the iPhone Duo on 27.1.
#
#   app/Scripts/gallery.sh
set -eu
set -o pipefail
cd "$(dirname "$0")/.."

OUT="${POLISHED_GALLERY_OUT:-$HOME/.cache/polished/native/gallery}"
rm -rf "$OUT"
mkdir -p "$OUT"
xcodegen generate -q

run() { # name, os, slug
  name="$1"; os="$2"; slug="$3"
  udid=$(xcrun simctl list devices available -j | python3 -c '
import json, sys
name, os = sys.argv[1:3]
for runtime, devices in json.load(sys.stdin)["devices"].items():
    if runtime.endswith("iOS-" + os.replace(".", "-")):
        for d in devices:
            if d["name"] == name:
                print(d["udid"])
' "$name" "$os" | head -1)
  [ -n "$udid" ] || { echo "no simulator $name on iOS $os" >&2; return 1; }
  xcrun simctl boot "$udid" 2>/dev/null || true
  xcrun simctl bootstatus "$udid" -b >/dev/null
  for scheme in light dark; do
    xcrun simctl ui "$udid" appearance "$scheme"
    dir="$OUT/$slug-$scheme"
    rm -rf "$dir.xcresult" "$dir"
    xcodebuild test \
      -project Polished.xcodeproj -scheme Polished \
      -destination "platform=iOS Simulator,id=$udid" \
      -derivedDataPath build/DerivedData \
      -only-testing:PolishedUITests/PolishedUITests/testGalleryScreenshots \
      -resultBundlePath "$dir.xcresult" \
      CODE_SIGNING_ALLOWED=NO 2>&1 | grep -E "\*\* TEST|error:" || true
    mkdir -p "$dir"
    xcrun xcresulttool export attachments --path "$dir.xcresult" --output-path "$dir" >/dev/null
    python3 Scripts/rename_attachments.py "$dir"
    rm -rf "$dir.xcresult"
    echo "$slug $scheme: $(ls "$dir" | grep -c png) screenshots"
  done
  xcrun simctl ui "$udid" appearance light
}

run "iPhone 18 Pro" 27.0 iphone-18-pro
run "iPad Pro 13-inch (M5)" 27.0 ipad-pro-13
run "iPhone Duo" 27.1 iphone-duo
echo "gallery: $OUT"
