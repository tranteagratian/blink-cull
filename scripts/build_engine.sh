#!/usr/bin/env bash
# Build the Blink Cull engine as a standalone program and install it inside the Lightroom plugin folder
# (lightroom/BlinkCull.lrdevplugin/bin/BlinkCullEngine). macOS / Linux. On Windows run the same pyinstaller
# command from PowerShell, with ";" instead of ":" in --add-data.
set -euo pipefail
cd "$(dirname "$0")/.."

# Build with uv's standalone Python, NOT a Homebrew/system one: a Python compiled on macOS 26 makes every extension module
# in the bundle require macOS 26, so the engine would refuse to start on older systems.
export UV_PYTHON_PREFERENCE=only-managed
uv python install 3.12
rm -rf .venv
uv sync --group build
uv run python fetch_models.py

rm -rf build dist/BlinkCullEngine
uv run --group build pyinstaller --noconfirm --name BlinkCullEngine --onedir --console \
  --add-data "models/yunet.onnx:models" --add-data "models/face_landmarker.task:models" \
  --collect-all mediapipe --collect-all rawpy \
  --exclude-module torch --exclude-module torchvision --exclude-module jax --exclude-module jaxlib \
  --exclude-module pandas --exclude-module pyarrow --exclude-module scipy --exclude-module sklearn \
  --exclude-module tensorflow --exclude-module IPython --exclude-module notebook --exclude-module webview \
  engine.py

PLUGIN=lightroom/BlinkCull.lrdevplugin
rm -rf "$PLUGIN/bin"
mkdir -p "$PLUGIN/bin"
cp -R dist/BlinkCullEngine "$PLUGIN/bin/"
echo "engine installed in $PLUGIN/bin/BlinkCullEngine ($(du -sh "$PLUGIN/bin/BlinkCullEngine" | cut -f1))"
