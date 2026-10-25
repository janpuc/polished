#!/usr/bin/env bash
# Rebuilds src/polished/static/fonts/fraunces-latin.woff2 from the pinned upstream file and checks
# the input hashes recorded in static/vendor/VERSIONS.txt. Needs curl and uv; run from the repo root.
#
#     scripts/make_fonts.sh
set -euo pipefail

SHA=4024282d9b0cffcdb8e3024560862746178d741f
BASE="https://raw.githubusercontent.com/google/fonts/$SHA/ofl/fraunces"
TTF_SHA256=177ff6c0f14e5550a3c624247cd1189611d4eb65d000b14944c63d967958abbb
OFL_SHA256=bdf4c22802eaf804f998195871c6b8938aac2ac14b2d78a8bd66a6f1eced833b
UNICODES="U+0020-007E,U+00A0-00FF,U+0131,U+0152-0153,U+02C6,U+02DA,U+02DC,U+2013-2014,U+2018-201A,U+201C-201E,U+2022,U+2026,U+2039-203A,U+20AC,U+2212,U+00D7"
OUT=src/polished/static/fonts

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$OUT"

curl -sSfL -o "$work/fraunces.ttf" "$BASE/Fraunces%5BSOFT%2CWONK%2Copsz%2Cwght%5D.ttf"
curl -sSfL -o "$work/OFL.txt" "$BASE/OFL.txt"
echo "$TTF_SHA256  $work/fraunces.ttf" | shasum -a 256 -c -
echo "$OFL_SHA256  $work/OFL.txt" | shasum -a 256 -c -

# Keep the axes the stylesheet uses (SOFT, opsz, wght 500 to 600), pin WONK off, then subset.
uv run --with fonttools --with brotli fonttools varLib.instancer "$work/fraunces.ttf" \
  WONK=0 wght=500:600 opsz=18:40 SOFT=0:100 -o "$work/instance.ttf"
uv run --with fonttools --with brotli pyftsubset "$work/instance.ttf" --unicodes="$UNICODES" \
  --layout-features='kern,liga,calt,ccmp,locl,mark,mkmk,lnum,tnum,pnum' --flavor=woff2 \
  --output-file="$OUT/fraunces-latin.woff2"
cp "$work/OFL.txt" "$OUT/OFL.txt"
shasum -a 256 "$OUT/fraunces-latin.woff2"
