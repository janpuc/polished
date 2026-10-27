#!/bin/sh
# Gives the next archive a build number that is unique and increasing: the UTC minute,
# `date -u +%Y%m%d%H%M` (12 digits). Written to app/Build.xcconfig (gitignored), which
# Config.xcconfig includes after its default of 1, so project.yml stays clean and Debug builds are
# unaffected. MARKETING_VERSION (1.0.0) is project.yml's and is bumped by hand per milestone.
#
#   app/Scripts/bump-build.sh     prints the build number it wrote
set -eu
cd "$(dirname "$0")/.."
BUILD="$(date -u +%Y%m%d%H%M)"
printf '// Written by Scripts/bump-build.sh; not committed.\nCURRENT_PROJECT_VERSION = %s\n' "$BUILD" > Build.xcconfig
echo "$BUILD"
