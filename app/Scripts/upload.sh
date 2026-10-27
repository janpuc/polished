#!/bin/sh
# Uploads build/export/Polished.ipa to App Store Connect (TestFlight) with altool and the API key.
# Run by the orchestrator or Jan, after Scripts/archive.sh. docs/NATIVE.md section 7.
#
# `--wait` returns once App Store Connect has processed the build (5 to 20 minutes). altool finds
# the key at the path given here, so ~/.appstoreconnect/private_keys is not required.
set -eu
. "$(dirname "$0")/lib/asc.sh"
cd "$(dirname "$0")/.."
load_asc
IPA="${1:-build/export/Polished.ipa}"
[ -f "$IPA" ] || { echo "no $IPA; run Scripts/archive.sh first" >&2; exit 1; }
exec xcrun altool --upload-package "$IPA" --wait \
  --api-key "$ASC_KEY_ID" --api-issuer "$ASC_ISSUER_ID" --p8-file-path "$ASC_KEY_PATH"
