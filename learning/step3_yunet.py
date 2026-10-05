"""Pasul 3 (etapa A): gaseste TOATE fetele dintr-o poza cu YuNet, inclusiv cele mici.

YuNet e un detector mic (230 KB) care cauta fete la mai multe scari. Spre deosebire de
MediaPipe (care redimensioneaza totul la ~128x128 si pierde fetele mici), YuNet primeste
imaginea mare si le gaseste si cand ocupa doar cateva zeci de pixeli.

Pentru fiecare fata intoarce: patratul (x, y, latime, inaltime), 5 puncte (ochi, nas, gura)
si un scor de incredere 0..1. NU da cele 6 puncte per ochi: pentru ele vine etapa B.

Rulare:  uv run python learning/step3_yunet.py [cale/imagine.jpg]
"""
import sys
import time
from pathlib import Path

import cv2
from PIL import Image, ImageDraw

img_path = Path(sys.argv[1] if len(sys.argv) > 1 else "out/DSC00006.jpg")

# Latura mare la care rulam detectia. 3000 px = compromis intre viteza si fetele mici.
DETECT_SIZE = 3000
SCORE_MIN = 0.6  # sub acest scor, ignoram "fata" (probabil fals pozitiv)

# 1) Citim imaginea (OpenCV o tine in ordine BGR, nu RGB) si o micsoram.
full = cv2.imread(str(img_path))
H, W = full.shape[:2]
scale = min(1.0, DETECT_SIZE / max(H, W))
small = cv2.resize(full, (round(W * scale), round(H * scale)), interpolation=cv2.INTER_AREA)
h, w = small.shape[:2]
print(f"Imagine: {W}x{H} -> detectie la {w}x{h}")

# 2) Cream detectorul. Trebuie sa-i spunem dimensiunea imaginii pe care o va primi.
detector = cv2.FaceDetectorYN.create(
    "models/yunet.onnx", "", (w, h),
    score_threshold=SCORE_MIN, nms_threshold=0.3, top_k=100,
)

# 3) Detectia. `faces` e None daca nu gaseste nimic, altfel o matrice N x 15.
t0 = time.perf_counter()
_, faces = detector.detect(small)
ms = (time.perf_counter() - t0) * 1000
faces = [] if faces is None else faces
print(f"Detectie: {ms:.0f} ms  |  fete gasite: {len(faces)}")

# 4) Desenam pe poza mica, ca sa vezi ce a gasit. Culoare dupa scor: verde = sigur, galben = nesigur.
canvas = Image.fromarray(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
draw = ImageDraw.Draw(canvas)
for i, f in enumerate(sorted(faces, key=lambda r: -r[2])):
    x, y, bw, bh = f[:4]
    score = f[14]
    color = "lime" if score >= 0.85 else "yellow"
    draw.rectangle((x, y, x + bw, y + bh), outline=color, width=4)
    draw.text((x + 4, y + 4), f"{i} {score:.2f}", fill=color)
    # latimea feței ca % din latimea cadrului: asta conteaza pentru MediaPipe (etapa B)
    print(f"  fata {i}: {bw / scale:4.0f}px in poza originala ({bw / w * 100:4.1f}% din latime), scor {score:.2f}")

out = Path("out") / f"{img_path.stem}_yunet.jpg"
canvas.save(out, quality=90)
print(f"Salvat: {out}")
