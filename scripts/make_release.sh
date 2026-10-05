#!/usr/bin/env bash
# Assemble the release zip: the plugin folder (with the engine inside it), install notes and licences. macOS Apple silicon.
# Run scripts/build_engine.sh first. Output: dist/release/BlinkCull-<version>-macos-arm64.zip and SHA256SUMS.txt
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=$(grep -E '^version' pyproject.toml | head -1 | sed -E 's/.*"(.*)".*/\1/')
NAME="BlinkCull-${VERSION}-macos-arm64"
PLUGIN=lightroom/BlinkCull.lrdevplugin
[ -x "$PLUGIN/bin/BlinkCullEngine/BlinkCullEngine" ] || { echo "engine missing: run scripts/build_engine.sh first" >&2; exit 1; }

rm -rf dist/release && mkdir -p "dist/release/$NAME"
cp -R "$PLUGIN" "dist/release/$NAME/"
cp LICENSE NOTICE "dist/release/$NAME/"
sed "s/@VERSION@/$VERSION/g" scripts/INSTALL.txt > "dist/release/$NAME/INSTALL.txt"
uv run python scripts/third_party_licenses.py > "dist/release/$NAME/THIRD_PARTY_LICENSES.txt"

# ditto (not zip) keeps the symlinks and executable bits that the PyInstaller bundle relies on
(cd dist/release && ditto -c -k --norsrc --noextattr --noacl --keepParent "$NAME" "$NAME.zip" && shasum -a 256 "$NAME.zip" > SHA256SUMS.txt && cat SHA256SUMS.txt)
