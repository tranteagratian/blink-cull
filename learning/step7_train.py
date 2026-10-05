"""Pasul 7: antreneaza un clasificator mic ochi inchis / deschis pe decupajele publice.

Model: MobileNetV3-small preantrenat pe ImageNet, cap nou cu 1 iesire (logit "inchis").
Validare: fisiere sursa separate de cele de antrenare (aceeasi persoana nu apare in ambele).
Augmentari: rotatie, scalare, lumina/contrast, blur, zgomot, oglindire: pozele reale au ochi inclinati,
neclari, in lumini diferite fata de portretele sintetice.

Rulare:  uv run python learning/step7_train.py [--epochs 8]
"""
import argparse
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision
from sklearn.metrics import roc_auc_score
from torchvision.transforms import v2

ap = argparse.ArgumentParser()
ap.add_argument("--epochs", type=int, default=8)
args = ap.parse_args()

torch.manual_seed(0)
np.random.seed(0)
# GPU Apple (MPS): ~13x mai rapid decat CPU aici. CPU-ul devine MAI lent cu mai multe fire, deci cade pe 1 fir.
device = "mps" if torch.backends.mps.is_available() else "cpu"
if device == "cpu":
    torch.set_num_threads(1)
print("device:", device)

d = np.load("data/eyes_public.npz")
X, y, group = d["X"], d["y"], d["group"]

# Validare: fiecare al 5-lea fisier sursa, din closed si din open separat (sa ramana echilibrat).
gids = sorted(set(group))
val_g = set(gids[::5])
val = np.array([g in val_g for g in group])
print(f"train {int((~val).sum())} | val {int(val.sum())} decupaje  (val = {len(val_g)} fisiere sursa)")

MEAN, STD = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1), torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
aug = v2.Compose([
    v2.RandomAffine(degrees=25, translate=(0.08, 0.08), scale=(0.85, 1.2)),
    v2.RandomHorizontalFlip(),
    v2.ColorJitter(brightness=0.4, contrast=0.4, saturation=0.3),
    v2.RandomApply([v2.GaussianBlur(5, sigma=(0.3, 2.0))], p=0.4),
])


def to_tensor(batch_uint8, train):
    t = torch.from_numpy(batch_uint8).permute(0, 3, 1, 2).contiguous()  # N,3,64,64 uint8
    if train:
        t = torch.stack([aug(x) for x in t])
    t = t.float() / 255
    if train:
        t = (t + torch.randn_like(t) * 0.02 * torch.rand(len(t), 1, 1, 1)).clamp(0, 1)  # zgomot usor
    t = F.interpolate(t, size=96, mode="bilinear", align_corners=False)  # MobileNet merge mai bine la >= 96 px
    return ((t - MEAN) / STD).to(device)


model = torchvision.models.mobilenet_v3_small(weights=torchvision.models.MobileNet_V3_Small_Weights.DEFAULT)
model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, 1)
model.to(device)
opt = torch.optim.AdamW(model.parameters(), lr=5e-4, weight_decay=1e-4)
sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=1e-3, total_steps=args.epochs * (int((~val).sum()) // 64 + 1))

Xtr, ytr, Xva, yva = X[~val], y[~val], X[val], y[val]


@torch.no_grad()
def predict(Xs):
    model.eval()
    out = [torch.sigmoid(model(to_tensor(Xs[i:i + 256], False))).squeeze(1) for i in range(0, len(Xs), 256)]
    return torch.cat(out).cpu().numpy()


for ep in range(1, args.epochs + 1):
    model.train()
    t0 = time.perf_counter()
    perm = np.random.permutation(len(Xtr))
    loss_sum = 0
    for i in range(0, len(perm), 64):
        idx = perm[i:i + 64]
        loss = F.binary_cross_entropy_with_logits(model(to_tensor(Xtr[idx], True)).squeeze(1), torch.from_numpy(ytr[idx]).float().to(device))
        opt.zero_grad(); loss.backward(); opt.step(); sched.step()
        loss_sum += loss.item() * len(idx)
    p = predict(Xva)
    print(f"epoca {ep}/{args.epochs}  loss {loss_sum / len(perm):.4f}  val acc {((p > 0.5) == yva).mean():.4f}  "
          f"val AUC {roc_auc_score(yva, p):.4f}  ({time.perf_counter() - t0:.0f}s)", flush=True)

torch.save(model.cpu().state_dict(), "models/eye_state.pt")
print("Salvat: models/eye_state.pt")
