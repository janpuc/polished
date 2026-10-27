#!/bin/sh
# The TestFlight build, signed and exported to build/export/Polished.ipa; it does NOT upload
# (Scripts/upload.sh does). docs/NATIVE.md section 7.
#
#   app/Scripts/archive.sh              xcodegen, a new build number, a Release archive, an export
#   app/Scripts/archive.sh --unsigned   only the archive, CODE_SIGNING_ALLOWED=NO: proves the Release
#                                       build compiles and links for generic iOS; no key needed,
#                                       no export, nothing usable on a device
#   app/Scripts/archive.sh --account    sign with the Apple ID signed in to Xcode (Settings, Accounts)
#                                       instead of the API key. The API key in use has the App Manager
#                                       role, which can upload but which xcodebuild's automatic
#                                       provisioning rejects ("Authentication failed: Make sure a bearer
#                                       token was provided"); an Admin key or the Xcode account works.
#
# The API key comes from the environment (lib/asc.sh): ASC_KEY_ID, ASC_ISSUER_ID, ASC_KEY_PATH.
# Everything goes into app/build (gitignored). After a successful export the .xcarchive is
# deleted; the .ipa stays.
set -eu
set -o pipefail
. "$(dirname "$0")/lib/asc.sh"
cd "$(dirname "$0")/.."

UNSIGNED=0
ACCOUNT=0
case "${1:-}" in
  "") ;;
  --unsigned) UNSIGNED=1 ;;
  --account) ACCOUNT=1 ;;
  *) echo "unknown option $1" >&2; exit 2 ;;
esac
[ "$UNSIGNED" = 1 ] || [ "$ACCOUNT" = 1 ] || load_asc

xcodegen generate -q
BUILD="$(Scripts/bump-build.sh)"
echo "== Polished 1.0.0 ($BUILD)"
rm -rf build/Polished.xcarchive build/export

if [ "$UNSIGNED" = 1 ]; then
  xcodebuild -project Polished.xcodeproj -scheme Polished -configuration Release \
    -destination 'generic/platform=iOS' \
    -archivePath build/Polished.xcarchive -derivedDataPath build/DerivedData \
    CODE_SIGNING_ALLOWED=NO archive 2>&1 | grep -E "error:|warning: .*(DEBUG|deprecat)|^\*\* "
  echo "unsigned archive: build/Polished.xcarchive"
  exit 0
fi

if [ "$ACCOUNT" = 1 ]; then
  AUTH="-allowProvisioningUpdates"
else
  AUTH="-allowProvisioningUpdates -authenticationKeyPath $ASC_KEY_PATH -authenticationKeyID $ASC_KEY_ID -authenticationKeyIssuerID $ASC_ISSUER_ID"
fi
# shellcheck disable=SC2086
xcodebuild -project Polished.xcodeproj -scheme Polished -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath build/Polished.xcarchive -derivedDataPath build/DerivedData \
  archive $AUTH
# shellcheck disable=SC2086
xcodebuild -exportArchive -archivePath build/Polished.xcarchive \
  -exportOptionsPlist ExportOptions.plist -exportPath build/export $AUTH

[ -f build/export/Polished.ipa ] || { echo "the export produced no Polished.ipa" >&2; exit 1; }
rm -rf build/Polished.xcarchive
echo "exported: build/export/Polished.ipa (build $BUILD); next: Scripts/upload.sh"
