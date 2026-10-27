#!/bin/sh
# The XCUITest flows of docs/NATIVE.md 6.2 against the real server, locally: the iPhone 18 Pro and
# the iPad Pro 13-inch (iOS 27.0) and the iPhone Duo (iOS 27.1, the only device its runtime has),
# each in light and dark appearance. Writes ~/.cache/polished/native-flows/<timestamp>/index.html
# (flow x device x scheme, steps, pass/fail, screenshots) and exits 1 when any flow failed.
#
#   app/Scripts/flows.sh                          every flow, three devices, two schemes
#   app/Scripts/flows.sh --devices iphone         iphone, ipad, duo (comma separated)
#   app/Scripts/flows.sh --schemes light
#   app/Scripts/flows.sh --flows SearchFlow,TabsFlow
#   app/Scripts/flows.sh --flows A,B --duo-also C,D   C and D run on the Duo only (a device whose
#                                                      earlier runs were checked elsewhere)
#
# The server is started and stopped here (Scripts/native_server.py): sign-in off, a development
# token, POLISHED_TEST_RESET_FROM for /__test/reset, no sync. Nothing here reaches holotaco.com;
# the photos come from cdn.shopify.com.
set -eu
set -o pipefail
. "$(dirname "$0")/lib/server.sh"
. "$(dirname "$0")/lib/sim.sh"
cd "$ROOT/app"

DEVICES="iphone,ipad,duo"
SCHEMES="light,dark"
DUO_ALSO=""
FLOWS="SearchFlow,TabsFlow,HistoryFlow,DeepLinkFlow,ShadeDetailFlow,WheelFlow,WishlistFlow,SignInFlow,AddBottleFlow,BottleLevelFlow,WishlistWritesFlow,WheelDeleteFlow,WheelTagFlow,WearFlow,TipColourFlow,BuilderFlow,BuilderCopyFlow,BuilderResumeFlow"
while [ $# -gt 0 ]; do
  case "$1" in
    --devices) DEVICES="$2"; shift 2 ;;
    --schemes) SCHEMES="$2"; shift 2 ;;
    --flows) FLOWS="$2"; shift 2 ;;
    --duo-also) DUO_ALSO="$2"; shift 2 ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$HOME/.cache/polished/native-flows/$STAMP"
mkdir -p "$OUT/runs"
trap stop_server EXIT

xcodegen generate -q
echo "== build for testing"
xcodebuild build-for-testing \
  -project Polished.xcodeproj -scheme Polished \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath build/DerivedData \
  CODE_SIGNING_ALLOWED=NO 2>&1 | grep -E "error:|^\*\* " || true
XCTESTRUN="$(ls build/DerivedData/Build/Products/*.xctestrun | head -1)"

start_server

run_device() { # slug, name, os, flows
  slug="$1"; name="$2"; os="$3"; flows="$4"
  only=""
  for flow in $(echo "$flows" | tr ',' ' '); do only="$only -only-testing:PolishedUITests/$flow"; done
  udid="$(udid_for "$name" "$os")"
  [ -n "$udid" ] || { echo "no simulator $name on iOS $os" >&2; return 1; }
  boot_sim "$udid"
  for scheme in $(echo "$SCHEMES" | tr ',' ' '); do
    xcrun simctl ui "$udid" appearance "$scheme"
    run="$OUT/runs/$slug-$scheme"
    echo "== $name, $scheme"
    # shellcheck disable=SC2086
    TEST_RUNNER_POLISHED_SERVER="$SERVER_BASE" xcodebuild test-without-building \
      -xctestrun "$XCTESTRUN" \
      -destination "platform=iOS Simulator,id=$udid" \
      $only \
      -test-timeouts-enabled YES -default-test-execution-time-allowance 150 -maximum-test-execution-time-allowance 240 \
      -resultBundlePath "$run.xcresult" 2>&1 | tee "$run.log" | grep -E "Test Case.*(passed|failed)|error:|\*\* TEST" | grep -v IDESchemeAction || true
    printf '{"device": "%s", "os": "%s", "scheme": "%s", "slug": "%s", "flows": "%s"}\n' "$name" "$os" "$scheme" "$slug" "$flows" >"$run.json"
  done
  xcrun simctl ui "$udid" appearance light
}

for device in $(echo "$DEVICES" | tr ',' ' '); do
  case "$device" in
    iphone) run_device iphone-18-pro "iPhone 18 Pro" 27.0 "$FLOWS" ;;
    ipad) run_device ipad-pro-13 "iPad Pro 13-inch (M5)" 27.0 "$FLOWS" ;;
    duo) run_device iphone-duo "iPhone Duo" 27.1 "${FLOWS}${DUO_ALSO:+,$DUO_ALSO}" ;;
    *) echo "unknown device $device" >&2; exit 2 ;;
  esac
done

echo "== report"
status=0
python3 Scripts/report.py "$OUT" --flows "${FLOWS}${DUO_ALSO:+,$DUO_ALSO}" || status=$?

# Disk is short: the report keeps its screenshots, the result bundles (hundreds of MB) go, and
# only the newest report stays.
rm -rf "$OUT"/runs/*.xcresult
for old in "$HOME"/.cache/polished/native-flows/*/; do
  [ "${old%/}" = "$OUT" ] || rm -rf "$old"
done
exit "$status"
