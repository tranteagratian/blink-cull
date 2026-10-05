"""Pasul 2: gaseste fete si ochi intr-un JPEG si deseneaza ce a gasit.

MediaPipe Face Landmarker primeste o imagine si intoarce, pentru fiecare fata,
478 de puncte 3D (landmarks) normalizate 0..1 (x, y relativ la latimea/inaltimea imaginii).
Din cele 478 ne intereseaza 6 puncte per ochi:

        p2   p3          p1 = colt exterior, p4 = colt interior
   p1              p4    p2,p3 = pleoapa de sus
        p6   p5          p5,p6 = pleoapa de jos

Pasul 3 va masura cat de departe sunt pleoapele (sus vs jos) ca sa decida ochi deschis/inchis.

Rulare:  uv run python learning/step2_faces.py [cale/imagine.jpg]
"""
import sys
import time
from pathlib import Path

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
from PIL import Image, ImageDraw

MODEL = "models/face_landmarker.task"
img_path = Path(sys.argv[1] if len(sys.argv) > 1 else "out/DSC00544.jpg")

# Indecsii celor 6 puncte per ochi in mesh-ul MediaPipe, in ordinea p1..p6 din schema de sus.
# "Right/Left" sunt din perspectiva persoanei din poza, nu a ta.
RIGHT_EYE = [33, 160, 158, 133, 153, 144]
LEFT_EYE = [362, 385, 387, 263, 373, 380]

# 1) Incarcam imaginea si o micsoram la max 2000 px pe latura mare.
#    Modelul nu are nevoie de 33 MP, iar o imagine mai mica e mult mai rapida.
#    Coordonatele rezultate sunt normalizate 0..1, deci le putem desena si pe originalul mare.
full = Image.open(img_path).convert("RGB")
small = full.copy()
small.thumbnail((2000, 2000))
print(f"Imagine: {full.size} -> procesata la {small.size}")

# 2) Cream detectorul. num_faces = cate fete cautam maxim.
options = vision.FaceLandmarkerOptions(
    # delegate=CPU: fara asta MediaPipe incearca GPU (Metal) si poate crapa
    base_options=mp_python.BaseOptions(
        model_asset_path=MODEL, delegate=mp_python.BaseOptions.Delegate.CPU
    ),
    num_faces=10,
    min_face_detection_confidence=0.3,  # mai mic = prinde si fete mici/neclare, dar mai multe false pozitive
)
detector = vision.FaceLandmarker.create_from_options(options)

# 3) Rulam detectia.
mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=__import__("numpy").asarray(small))
t0 = time.perf_counter()
result = detector.detect(mp_image)
print(f"Detectie: {(time.perf_counter() - t0) * 1000:.0f} ms")
print(f"Fete gasite: {len(result.face_landmarks)}")

# 4) Desenam pe imaginea mica: patrat pe fata + puncte pe ochi.
draw = ImageDraw.Draw(small)
W, H = small.size
for i, landmarks in enumerate(result.face_landmarks):
    xs = [p.x * W for p in landmarks]
    ys = [p.y * H for p in landmarks]
    box = (min(xs), min(ys), max(xs), max(ys))
    draw.rectangle(box, outline="lime", width=3)
    draw.text((box[0], box[1] - 14), f"fata {i}", fill="lime")
    for eye, color in ((RIGHT_EYE, "red"), (LEFT_EYE, "cyan")):
        for idx in eye:
            x, y = landmarks[idx].x * W, landmarks[idx].y * H
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=color)
    print(f"  fata {i}: latime ~{box[2] - box[0]:.0f}px (din {W}px), "
          f"ochi dreapta p1=({landmarks[33].x:.3f},{landmarks[33].y:.3f})")

out = Path("out") / f"{img_path.stem}_faces.jpg"
small.save(out, quality=90)
print(f"Salvat: {out}")
