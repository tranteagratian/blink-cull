"""Core detection pipeline: RAW preview -> faces -> per-eye blink scores.

  load_preview(arw)     the full-size JPEG embedded in an ARW, correctly oriented, as an OpenCV (BGR) array
  find_faces(img)       YuNet face boxes (any size) with score >= SCORE_MIN
  analyze_photo(arw)    everything: for each face, a crop, a sharpness value and MediaPipe blink scores

Reads RAW files read-only and never writes anything to disk.

Face status values (kept as plain strings because they end up in saved files and the UI):
  "ok"           judged: the eyes were measured
  "mica"         too small (narrower than MIN_FACE_PX), skipped
  "neclara"      too blurry/dark (sharpness < SHARP_MIN), skipped
  "fara_puncte"  MediaPipe found no landmarks (typically profile views, hugging, heads turned away), skipped
"""
import sys
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import rawpy
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision


def resource(*parts):
    """Path of a bundled file, both when running from source and when frozen into an app (PyInstaller)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return str(base.joinpath(*parts))


DETECT_SIZE = 3000   # long side (px) the image is shrunk to for face detection
SCORE_MIN = 0.75     # minimum YuNet confidence (removes false positives such as a flower scoring 0.63)
MIN_FACE_PX = 120    # faces narrower than this (in the original photo) are not judged: eyelids are not visible
SHARP_MIN = 100      # minimum face sharpness (variance of the Laplacian); provisional, calibrate on your own data
MARGIN = 0.4         # how much the face box is expanded on each side when cropping
CROP_MAX = 640       # longest side of the crop handed to MediaPipe

# MediaPipe face-mesh indices of the 6 landmarks per eye (corner, 2 upper lid, corner, 2 lower lid).
# "Right" is the person's right eye (the left one in the image).
RIGHT_EYE = [33, 160, 158, 133, 153, 144]
LEFT_EYE = [362, 385, 387, 263, 373, 380]

# LibRaw `flip` value -> OpenCV rotation that makes the preview upright
_ROTATE = {
    3: cv2.ROTATE_180,
    5: cv2.ROTATE_90_COUNTERCLOCKWISE,
    6: cv2.ROTATE_90_CLOCKWISE,
}


@dataclass
class Face:
    box: tuple            # x, y, width, height in the original photo
    yunet_score: float
    width_px: float
    sharpness: float = 0.0
    status: str = "ok"    # see the module docstring
    ear_right: float = None
    ear_left: float = None
    blink_right: float = None   # MediaPipe `eyeBlink*` blendshapes, 0 = open, 1 = closed
    blink_left: float = None
    crop: np.ndarray = field(default=None, repr=False)  # BGR crop, only kept for judged faces

    @property
    def openness(self):
        """Eye aspect ratio of the MORE open eye. Small = both eyes closed."""
        return max(self.ear_right, self.ear_left)


def load_preview(arw_path):
    """The embedded JPEG, decoded and rotated upright. Returns a BGR image."""
    with rawpy.imread(str(arw_path)) as raw:
        thumb = raw.extract_thumb()
        flip = raw.sizes.flip
    # IGNORE_ORIENTATION: otherwise OpenCV applies the EXIF orientation itself and we would rotate twice.
    img = cv2.imdecode(np.frombuffer(thumb.data, np.uint8), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    return cv2.rotate(img, _ROTATE[flip]) if flip in _ROTATE else img


def make_yunet(width, height):
    return cv2.FaceDetectorYN.create(
        resource("models", "yunet.onnx"), "", (width, height),
        score_threshold=SCORE_MIN, nms_threshold=0.3, top_k=100,
    )


def make_landmarker():
    return vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(
            model_asset_path=resource("models", "face_landmarker.task"),
            delegate=mp_python.BaseOptions.Delegate.CPU,  # the GPU path crashes MediaPipe 1.0 on macOS 26
        ),
        num_faces=1,
        output_face_blendshapes=True,
    ))


def _ear(pts):
    """Eye aspect ratio from 6 landmark points: lid opening divided by eye width."""
    p = np.array(pts)
    vertical = np.linalg.norm(p[1] - p[5]) + np.linalg.norm(p[2] - p[4])
    return vertical / (2 * np.linalg.norm(p[0] - p[3]))


def find_faces(img):
    """List of (x, y, w, h, score) in the coordinates of the original image."""
    H, W = img.shape[:2]
    scale = min(1.0, DETECT_SIZE / max(H, W))
    small = cv2.resize(img, (round(W * scale), round(H * scale)), interpolation=cv2.INTER_AREA)
    det = make_yunet(small.shape[1], small.shape[0])  # YuNet needs the exact input size up front
    _, found = det.detect(small)
    if found is None:
        return []
    found = sorted(found, key=lambda r: -r[2])
    return [(*(r[:4] / scale), r[14]) for r in found]


def analyze_face(img, landmarker, x, y, bw, bh, score):
    """Crop one face from the full-size image, filter by size and sharpness, then measure the eyes.

    The crop matters: MediaPipe's own detector shrinks its input to ~128x128, so a small face in a large photo
    is invisible to it. Feeding it a crop where the face fills the frame is what makes it work.
    """
    H, W = img.shape[:2]
    face = Face(box=(x, y, bw, bh), yunet_score=float(score), width_px=float(bw))
    if bw < MIN_FACE_PX:
        face.status = "mica"
        return face

    side = max(bw, bh) * (1 + 2 * MARGIN)
    cx, cy = x + bw / 2, y + bh / 2
    x0, y0 = int(max(0, cx - side / 2)), int(max(0, cy - side / 2))
    x1, y1 = int(min(W, cx + side / 2)), int(min(H, cy + side / 2))
    crop = img[y0:y1, x0:x1]
    if max(crop.shape[:2]) > CROP_MAX:
        k = CROP_MAX / max(crop.shape[:2])
        crop = cv2.resize(crop, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(cv2.resize(crop, (256, 256)), cv2.COLOR_BGR2GRAY)
    face.sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if face.sharpness < SHARP_MIN:
        face.status = "neclara"
        return face

    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    res = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    if not res.face_landmarks:
        face.status = "fara_puncte"
        return face

    ch, cw = rgb.shape[:2]
    lm = res.face_landmarks[0]
    pts = lambda idx: [(lm[j].x * cw, lm[j].y * ch) for j in idx]
    blend = {b.category_name: b.score for b in res.face_blendshapes[0]}
    face.ear_right, face.ear_left = float(_ear(pts(RIGHT_EYE))), float(_ear(pts(LEFT_EYE)))
    face.blink_right, face.blink_left = float(blend["eyeBlinkRight"]), float(blend["eyeBlinkLeft"])
    face.crop = crop
    return face


def analyze_photo(arw_path, landmarker):
    """Run the whole pipeline on one photo. Returns (image, [Face, ...])."""
    img = load_preview(arw_path)
    faces = [analyze_face(img, landmarker, *f) for f in find_faces(img)]
    return img, faces
