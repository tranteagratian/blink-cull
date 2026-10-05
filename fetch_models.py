"""Download the two model files into ./models (they are not stored in the repository).

    python fetch_models.py
"""
import sys
import urllib.request
from pathlib import Path

MODELS = {
    "yunet.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "face_landmarker.task": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
}
MIN_BYTES = 100_000  # a real model is far larger; guards against saving an HTML error page

dest = Path(__file__).resolve().parent / "models"
dest.mkdir(exist_ok=True)
for name, url in MODELS.items():
    target = dest / name
    if target.exists() and target.stat().st_size > MIN_BYTES:
        print(f"{name}: already present")
        continue
    print(f"{name}: downloading ...")
    try:
        data = urllib.request.urlopen(url, timeout=60).read()
    except Exception as e:  # noqa: BLE001
        sys.exit(f"could not download {name}: {e}")
    if len(data) < MIN_BYTES:
        sys.exit(f"{name}: unexpectedly small download ({len(data)} bytes); aborting")
    target.write_bytes(data)
    print(f"{name}: {len(data) / 1e6:.1f} MB")
