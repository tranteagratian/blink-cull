"""Pasul 4 (etapa B): pentru fiecare fata gasita, masoara cat de deschisi sunt ochii (EAR).

Fluxul pentru o poza:
  1. YuNet gaseste fetele (pasul 3)
  2. fiecare fata se decupeaza din poza MARE, cu margine, deci fata umple decupajul
  3. MediaPipe primeste decupajul si da cele 6 puncte per ochi
  4. EAR = distanta pe verticala dintre pleoape / distanta pe orizontala dintre colturi

        p2   p3
   p1              p4         EAR = ( |p2-p6| + |p3-p5| ) / ( 2 * |p1-p4| )
        p6   p5

  Ochi deschis ~0.25-0.35, ochi inchis < ~0.15. Valoarea nu depinde de marimea fetei,
  doar de forma ochiului.

Rulare:  uv run python learning/step4_ear.py [cale/imagine.jpg]
"""
import sys
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
from PIL import Image, ImageDraw

img_path = Path(sys.argv[1] if len(sys.argv) > 1 else "out/DSC00006.jpg")

DETECT_SIZE = 3000   # latura mare la care ruleaza YuNet
SCORE_MIN = 0.75     # scor YuNet minim (taie fals pozitivul "trandafir" de 0.63)
MIN_FACE_PX = 120    # fete mai inguste (in poza originala) nu se judeca: pleoapele nu se vad
MARGIN = 0.4         # cat extindem patratul fetei la decupare (40% pe fiecare parte)
CROP_MAX = 640       # decupajul dat lui MediaPipe nu depaseste atat

# Indecsii MediaPipe pentru p1..p6. "Right" = ochiul din dreapta PERSOANEI (stanga in imagine).
RIGHT_EYE = [33, 160, 158, 133, 153, 144]
LEFT_EYE = [362, 385, 387, 263, 373, 380]


def ear(pts):
    """pts: 6 puncte (x, y) in ordinea p1..p6."""
    p = np.array(pts)
    vertical = np.linalg.norm(p[1] - p[5]) + np.linalg.norm(p[2] - p[4])
    horizontal = np.linalg.norm(p[0] - p[3])
    return vertical / (2 * horizontal)


# --- Etapa A: YuNet pe toata poza ------------------------------------------------------
full = cv2.imread(str(img_path))
H, W = full.shape[:2]
scale = min(1.0, DETECT_SIZE / max(H, W))
small = cv2.resize(full, (round(W * scale), round(H * scale)), interpolation=cv2.INTER_AREA)
yunet = cv2.FaceDetectorYN.create(
    "models/yunet.onnx", "", (small.shape[1], small.shape[0]),
    score_threshold=SCORE_MIN, nms_threshold=0.3, top_k=100,
)
_, found = yunet.detect(small)
found = [] if found is None else sorted(found, key=lambda r: -r[2])
print(f"{img_path.name}: {len(found)} fete cu scor >= {SCORE_MIN}")

# --- Etapa B: MediaPipe pe fiecare decupaj ---------------------------------------------
landmarker = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
    base_options=mp_python.BaseOptions(
        model_asset_path="models/face_landmarker.task",
        delegate=mp_python.BaseOptions.Delegate.CPU,
    ),
    num_faces=1,
    output_face_blendshapes=True,  # a doua opinie: MediaPipe estimeaza direct "eyeBlinkLeft/Right"
))

tiles = []
for i, f in enumerate(found):
    x, y, bw, bh = (f[:4] / scale)  # inapoi la coordonatele pozei originale
    if bw < MIN_FACE_PX:
        print(f"  fata {i}: {bw:.0f}px  -> prea mica, sarita")
        continue

    # Decupaj patrat din poza mare, centrat pe fata, cu margine.
    side = max(bw, bh) * (1 + 2 * MARGIN)
    cx, cy = x + bw / 2, y + bh / 2
    x0, y0 = int(max(0, cx - side / 2)), int(max(0, cy - side / 2))
    x1, y1 = int(min(W, cx + side / 2)), int(min(H, cy + side / 2))
    crop = full[y0:y1, x0:x1]
    if max(crop.shape[:2]) > CROP_MAX:
        k = CROP_MAX / max(crop.shape[:2])
        crop = cv2.resize(crop, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    ch, cw = rgb.shape[:2]

    # Claritate: varianta Laplacianului pe fata (valoare mare = clar, mica = neclar/defocalizat).
    gray = cv2.cvtColor(cv2.resize(crop, (256, 256)), cv2.COLOR_BGR2GRAY)
    sharp = cv2.Laplacian(gray, cv2.CV_64F).var()

    res = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    if not res.face_landmarks:
        print(f"  fata {i}: {bw:.0f}px  claritate {sharp:5.0f}  -> MediaPipe nu gaseste fata in decupaj")
        continue

    lm = res.face_landmarks[0]
    pts = lambda idx: [(lm[j].x * cw, lm[j].y * ch) for j in idx]
    ear_r, ear_l = ear(pts(RIGHT_EYE)), ear(pts(LEFT_EYE))
    blend = {b.category_name: b.score for b in res.face_blendshapes[0]}
    blink_r, blink_l = blend["eyeBlinkRight"], blend["eyeBlinkLeft"]
    print(f"  fata {i}: {bw:.0f}px  claritate {sharp:5.0f}  "
          f"EAR dr={ear_r:.2f} st={ear_l:.2f}  |  blink dr={blink_r:.2f} st={blink_l:.2f}")

    # Desenam punctele ochilor + valorile pe decupaj.
    tile = Image.fromarray(rgb)
    d = ImageDraw.Draw(tile)
    for idx, color in ((RIGHT_EYE, "red"), (LEFT_EYE, "cyan")):
        for px, py in pts(idx):
            d.ellipse((px - 2, py - 2, px + 2, py + 2), fill=color)
    d.rectangle((0, 0, cw, 40), fill="black")
    d.text((6, 4), f"fata {i}  {bw:.0f}px  claritate {sharp:.0f}", fill="white")
    d.text((6, 22), f"EAR dr={ear_r:.2f} st={ear_l:.2f}  blink {blink_r:.2f}/{blink_l:.2f}", fill="white")
    tiles.append(tile)

# --- Foaia cu decupaje -----------------------------------------------------------------
if tiles:
    sheet = Image.new("RGB", (sum(t.width for t in tiles), max(t.height for t in tiles)), "black")
    xo = 0
    for t in tiles:
        sheet.paste(t, (xo, 0))
        xo += t.width
    out = Path("out") / f"{img_path.stem}_eyes.jpg"
    sheet.save(out, quality=90)
    print(f"Salvat: {out}")
