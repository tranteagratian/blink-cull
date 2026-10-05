"""Pasul 8: testeaza clasificatorul pe fetele REALE etichetate de tine (modelul nu le-a vazut niciodata).

Pentru fiecare fata din labels.json:
  1. luam decupajul fetei salvat la pasul 5 (out/report/crops/)
  2. MediaPipe da punctele ochilor -> centru, latime, unghi pentru fiecare ochi
  3. eyes.eye_patch face decupajul 64x64, modelul da P(inchis) pentru fiecare ochi
  4. scorul fetei = combinatie a celor doi ochi (mean / max / min)
Comparam cu `blink` din MediaPipe, pe aceleasi fete.

Rulare:  uv run python learning/step8_eval_real.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # blink.py / scanner.py sunt in radacina
import json

import cv2
import mediapipe as mp
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision
from sklearn.metrics import precision_recall_curve, roc_auc_score

import blink
import eyes

labels = json.load(open("out/report/labels.json"))

# --- model ---------------------------------------------------------------------------------
model = torchvision.models.mobilenet_v3_small(weights=None)
model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, 1)
model.load_state_dict(torch.load("models/eye_state.pt"))
model.eval()
MEAN, STD = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1), torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)


@torch.no_grad()
def p_closed(patches):
    t = torch.from_numpy(np.stack(patches)).permute(0, 3, 1, 2).float() / 255
    t = (F.interpolate(t, size=96, mode="bilinear", align_corners=False) - MEAN) / STD
    return torch.sigmoid(model(t)).squeeze(1).numpy()


# --- punctele ochilor ----------------------------------------------------------------------
landmarker = blink.make_landmarker()
EYES = {"dr": blink.RIGHT_EYE, "st": blink.LEFT_EYE}


def eye_geometry(lm, idx, w, h):
    pts = np.array([(lm[j].x * w, lm[j].y * h) for j in idx])
    c = pts.mean(axis=0)
    left, right = (pts[0], pts[3]) if pts[0][0] < pts[3][0] else (pts[3], pts[0])
    width = np.linalg.norm(right - left)
    angle = np.degrees(np.arctan2(right[1] - left[1], right[0] - left[0]))
    return c[0], c[1], width, angle


rows, failed = [], 0
for r in labels:
    img = cv2.imread(f"out/report/crops/{r['key']}.jpg")
    h, w = img.shape[:2]
    res = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
    if not res.face_landmarks:
        failed += 1
        continue
    lm = res.face_landmarks[0]
    geo = {k: eye_geometry(lm, idx, w, h) for k, idx in EYES.items()}
    row = {"key": r["key"], "y": int(r["label"] == "closed"),
           "blink_mean": (r["blink_right"] + r["blink_left"]) / 2}
    for align in (False, True):
        ps = p_closed([eyes.eye_patch(img, cx, cy, wd, angle if align else 0.0) for cx, cy, wd, angle in geo.values()])
        tag = "al" if align else "na"
        row[f"mean_{tag}"], row[f"max_{tag}"], row[f"min_{tag}"] = float(ps.mean()), float(ps.max()), float(ps.min())
    rows.append(row)

y = np.array([r["y"] for r in rows])
print(f"{len(rows)} fete evaluate ({failed} pierdute: MediaPipe nu mai gaseste punctele pe decupajul salvat) | "
      f"inchise: {int(y.sum())}, deschise: {int((1 - y).sum())}\n")


def report(name, score):
    s = np.array(score)
    prec, rec, thr = precision_recall_curve(y, s)
    line = f"{name:34s} AUC {roc_auc_score(y, s):.3f} |"
    for target in (0.9, 0.8, 0.7):
        i = np.where(rec[:-1] >= target)[0].max()
        line += f"  recall>={target:.1f}: precizie {prec[i]:.2f}"
    print(line)


report("blink_mean (MediaPipe)", [r["blink_mean"] for r in rows])
for tag, name in (("na", "fara aliniere"), ("al", "cu aliniere (rotit)")):
    for agg in ("mean", "max", "min"):
        report(f"clasificator {agg:4s} {name}", [r[f"{agg}_{tag}"] for r in rows])

json.dump(rows, open("out/report/eval_scores.json", "w"), indent=1)
