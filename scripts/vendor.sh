#!/bin/sh
# Fetches the pinned third-party browser files into src/polished/static/vendor/ and checks
# their sha256. A developer step, not part of the build (there is no Node and no build step);
# Renovate cannot update vendored files, so a refresh means changing the versions and hashes
# below, running this, and recording the same in static/vendor/VERSIONS.txt.
#
#   scripts/vendor.sh
#
# zxing-wasm comes from the npm registry tarball. Its layout at 3.1.6 (checked, not assumed):
#   package/dist/es/reader/index.js   the reader ES module; imports "../share.js"
#   package/dist/es/share.js          code shared by the reader, writer and full builds
#   package/dist/reader/zxing_reader.wasm
# The two modules are copied unmodified with that relative layout (reader/index.js next to
# share.js), and the wasm sits at the top of the directory, so the app serves
#   /static/vendor/zxing-wasm/reader/index.js
#   /static/vendor/zxing-wasm/share.js
#   /static/vendor/zxing-wasm/zxing_reader.wasm
# scanner.js points the module at that wasm with a locateFile override; nothing loads from a CDN.
set -eu

ZXING_VERSION=3.1.6
ZXING_TARBALL_SHA256=188321a7680275ce7ab73c7c13fac9f6c4181b5da7ed65af64ba34d1fd416ea5
HTMX_VERSION=2.0.11
HTMX_SHA256=d6fdc75f204e6bdefa99b69bf1e6d4ac69b8a364f77929f45c13476b4000f717

root=$(cd "$(dirname "$0")/.." && pwd)
vendor="$root/src/polished/static/vendor"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

sha256() { shasum -a 256 "$1" | cut -d' ' -f1; }
check() { # file expected-sha256
  actual=$(sha256 "$1")
  [ "$actual" = "$2" ] || { echo "sha256 mismatch for $1: $actual (expected $2)" >&2; exit 1; }
}

curl -fsSL "https://registry.npmjs.org/zxing-wasm/-/zxing-wasm-$ZXING_VERSION.tgz" \
  -o "$work/zxing-wasm.tgz"
check "$work/zxing-wasm.tgz" "$ZXING_TARBALL_SHA256"
mkdir "$work/zxing"
tar -xzf "$work/zxing-wasm.tgz" -C "$work/zxing"
package="$work/zxing/package"
mkdir -p "$vendor/zxing-wasm/reader"
cp "$package/dist/es/reader/index.js" "$vendor/zxing-wasm/reader/index.js"
cp "$package/dist/es/share.js" "$vendor/zxing-wasm/share.js"
cp "$package/dist/reader/zxing_reader.wasm" "$vendor/zxing-wasm/zxing_reader.wasm"
cp "$package/LICENSE" "$vendor/zxing-wasm/LICENSE"

curl -fsSL "https://cdn.jsdelivr.net/npm/htmx.org@$HTMX_VERSION/dist/htmx.min.js" \
  -o "$work/htmx.min.js"
check "$work/htmx.min.js" "$HTMX_SHA256"
cp "$work/htmx.min.js" "$vendor/htmx.min.js"

for file in htmx.min.js zxing-wasm/reader/index.js zxing-wasm/share.js zxing-wasm/zxing_reader.wasm; do
  echo "$(sha256 "$vendor/$file")  $file"
done
