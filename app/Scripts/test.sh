#!/bin/sh
# Generates the project, runs the PolishedCore tests on the Mac (`swift test`) and the app's
# tests on the iPhone 18 Pro simulator (PolishedTests hosts the same sources; PolishedUITests runs
# the flows against the local server of lib/server.sh, which this script starts and stops), then
# exports the screenshot attachments to ~/.cache/polished/native/<timestamp>/.
#
#   app/Scripts/test.sh
#
# The iPhone 18 Pro and the iPad Pro exist only on the iOS 27.0 runtime; the iOS 27.1 runtime
# has just the iPhone Duo (see docs/NATIVE.md 6.2). Exit status is xcodebuild's.
set -eu
set -o pipefail
. "$(dirname "$0")/lib/server.sh"
cd "$ROOT/app"

DEVICE="${POLISHED_TEST_DEVICE:-iPhone 18 Pro}"
OS="${POLISHED_TEST_OS:-27.0}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$HOME/.cache/polished/native/$STAMP"
mkdir -p "$OUT"

xcodegen generate -q
trap stop_server EXIT
start_server

echo "== swift test (PolishedCore, on the Mac)"
(cd PolishedCore && swift test 2>&1 | tail -3)

echo "== xcodebuild test ($DEVICE, iOS $OS)"
status=0
TEST_RUNNER_POLISHED_SERVER="$SERVER_BASE" xcodebuild test \
  -project Polished.xcodeproj -scheme Polished \
  -destination "platform=iOS Simulator,name=$DEVICE,OS=$OS" \
  -derivedDataPath build/DerivedData \
  -resultBundlePath "$OUT/result.xcresult" \
  CODE_SIGNING_ALLOWED=NO 2>&1 | tee "$OUT/xcodebuild.log" | grep -E "✔ Suite|✘|Test run with|Executed [0-9]+ tests, with .* in .* \(.*\) seconds$|\*\* TEST|error:" || status=$?

xcrun xcresulttool get test-results summary --path "$OUT/result.xcresult" --compact 2>/dev/null \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print({k: d.get(k) for k in ("result","passedTests","failedTests","skippedTests","totalTestCount")})' || true

mkdir -p "$OUT/shots"
xcrun xcresulttool export attachments --path "$OUT/result.xcresult" --output-path "$OUT/shots" >/dev/null
python3 Scripts/rename_attachments.py "$OUT/shots"
# Disk is short: the screenshots stay, the result bundle goes, and only the newest run is kept.
rm -rf "$OUT/result.xcresult"
for old in "$HOME"/.cache/polished/native/2*/; do
  [ "${old%/}" = "$OUT" ] || rm -rf "$old"
done
echo "screenshots: $OUT/shots"
echo "$OUT" > build/last-test-run.txt
exit "$status"
