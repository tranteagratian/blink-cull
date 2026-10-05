"""Pasul 6: din imaginile publice (data/eyes/*.parquet) scoate decupaje de ochi 64x64.

Fiecare imagine are doua casete (ochi stang, drept) si o eticheta pentru ambii ochi.
Iesire: data/eyes_public.npz cu X (N,64,64,3 uint8), y (1 = inchis), group (id-ul fisierului sursa).
`group` ne lasa sa impartim train/validare pe fisiere, ca sa nu apara aceeasi persoana in ambele.

Rulare:  uv run python learning/step6_build_eyes.py
"""
import glob
import re

import cv2
import numpy as np
import pandas as pd

import eyes

X, y, group = [], [], []
files = sorted(glob.glob("data/eyes/*.parquet"), key=lambda p: int(re.findall(r"(\d+)\.parquet", p)[0]))
for p in files:
    gid = int(re.findall(r"(\d+)\.parquet", p)[0])
    df = pd.read_parquet(p)
    for _, r in df.iterrows():
        img = cv2.imdecode(np.frombuffer(r["Image_data"]["file"], np.uint8), cv2.IMREAD_COLOR)
        label = 1 if r["Label"] == "closed_eyes" else 0
        for k in ("Left_eye_react", "Right_eye_react"):
            x0, y0, w, h = [float(v) for v in r[k]]
            if w < 6:  # caseta degenerata
                continue
            X.append(eyes.eye_patch(img, x0 + w / 2, y0 + h / 2, w))
            y.append(label)
            group.append(gid)

X, y, group = np.stack(X), np.array(y), np.array(group)
np.savez_compressed("data/eyes_public.npz", X=X, y=y, group=group)
print(f"{len(X)} decupaje de ochi | inchisi: {int(y.sum())}, deschisi: {int((1 - y).sum())} | surse: {len(set(group))} fisiere")
