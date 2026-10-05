# How Blink Cull works

This document explains the pipeline, why it is built this way, how it was measured, and what did not work.
Numbers come from one wedding gallery (1363 Sony a7 IV ARW photos; 215 further files were 0-byte leftovers of an
interrupted card copy) labelled by one photographer. Treat them as a measurement of this tool on that gallery, not as a benchmark.

## 1. The pipeline

```
 ARW file ──► embedded JPEG ──► upright image ──► YuNet ──► face boxes ──► crop each face ──► filters ──► MediaPipe ──► score
 (35 MB)      (7008×4672,       (apply the        (any      (x,y,w,h,      (+40% margin,      (≥120 px,    Face         mean of
              ~1 ms to read)    camera's          size)     score ≥0.75)   from the BIG        sharp enough) Landmarker   eyeBlinkLeft/
                                orientation)                                image)                          blendshapes  eyeBlinkRight
                                                                                                                         per face
 photo score = the highest face score in the photo ──► ≥ 0.45 red ("closed")   0.25–0.45 yellow ("to check")   below: not shown
```

**1. Read the embedded JPEG, not the RAW.** An ARW contains a full-size JPEG preview. `rawpy` returns it in about a
millisecond; developing the RAW would take seconds per photo and add nothing for this task. The camera does not rotate
the preview; it stores the orientation in metadata (`flip`), so we rotate it ourselves.

**2. Find faces with YuNet** (a small OpenCV detector) on the image shrunk to 3000 px. It finds faces of any size.
Detections below 0.75 confidence are dropped (this removed, for example, an orange flower in a bouquet that scored 0.63).

**3. Crop each face from the big image and give the crop to MediaPipe.** This is the key design decision.
MediaPipe's own face detector shrinks its input to roughly 128×128, so a small face inside a large photo is invisible
to it. We tested the same photo at 2000, 3500 and 7008 px: MediaPipe found the same single face every time, while YuNet
found four. What matters is how much of the *frame* a face fills, not how many pixels it has. Cropping makes the face fill the frame.

**4. Skip faces that cannot be judged**, instead of guessing: narrower than 120 px (the eyelids are not visible), or
blurry/dark (variance of the Laplacian < 100), or no landmarks found (typically profiles). A blurry face makes the model
invent landmarks, and a guess here causes false alarms.

**5. Score the eyes with MediaPipe's `eyeBlinkLeft` / `eyeBlinkRight` blendshapes** (0 = open, 1 = closed), averaged.
**6. A photo's score is the score of its most "closed" face**, then two thresholds split the photos into red / yellow / hidden.

### Why blendshapes and not the classic eye aspect ratio (EAR)?
EAR (lid opening ÷ eye width from 6 landmarks) is the textbook method. On 153 labelled faces from this gallery it separated
closed from open worse (AUC 0.74 for the more-open eye, 0.83 for the less-open eye) than the blendshapes (AUC 0.89). EAR
assumes a frontal face; on profiles and three-quarter views the far eye is foreshortened or hidden and the landmarks drift.
The blendshapes degraded more gracefully on those views in our tests (we did not investigate why).

## 2. How it was measured

1. Run the tool; save every score.
2. The photographer labelled **all 594 photos the tool flagged** as "closed" / "open" in the app (precision is therefore measured directly).
3. To estimate recall, 80 photos the tool did **not** flag were drawn at random and labelled the same way (11 of 71 still-unflagged ones were closed → about 117 missed in ~758, 90% interval 74–180).
4. Recall = found / (found + estimated missed), with the interval propagated from that sample.

| Threshold | Photos | Truly closed | Precision | Est. recall (90%) | Lift |
|---|---|---|---|---|---|
| ≥ 0.55 | 97 | 93 | 96% | ~21% (18–23%) | 2.9× |
| ≥ 0.45 | 197 | 171 | 87% | ~38% (33–42%) | 2.6× |
| ≥ 0.35 | 353 | 258 | 73% | ~57% (50–63%) | 2.2× |
| ≥ 0.25 | 594 | 336 | 57% | ~74% (65–82%) | 1.7× |

"Lift" is recall ÷ share of photos reviewed, i.e. how much better than reviewing at random. Because roughly a third of
the gallery was "closed" by the photographer's (generous) definition, a rule that makes you review most of the folder is
nearly useless even if its recall looks high. That is why thresholds are reported as a trade-off, not a single accuracy number.

**What the misses look like** (11 closed photos the tool did not flag): borderline scores just under the threshold (3),
profile/hugging faces where MediaPipe finds no landmarks (2), people looking down with small faces (2), faces judged but
scored low (2), a crowd of blurry guests (1), and one photo with no face at all that was probably not an eye problem (1).

## 3. What did not work (kept in `learning/` so you can reproduce it)

- **A classifier trained by us.** A MobileNetV3-small (1.53 M parameters, ImageNet-pretrained) fine-tuned on ~12,000 eye crops from
  a public *synthetic* open/closed-eyes dataset reached 99.7% validation accuracy on synthetic data, and **AUC 0.905 vs 0.892 for
  MediaPipe on the real photos**, a difference whose bootstrap 95% interval was [−0.032, +0.064], i.e. no demonstrated gain. Combining
  the two did not help either (0.894 vs 0.890). So the shipped tool uses MediaPipe alone and does not depend on PyTorch.
  The synthetic faces are frontal with cleanly closed or open eyes, which is exactly what real wedding photos are not.
- **A sharpness gate that looked great and was an artefact.** Gating on eye-patch sharpness raised AUC to 0.95 but silently
  removed 43% of the closed faces: closed lids are smooth surfaces with few edges, so "sharpness" was partly predicting the label.
  Gating on whole-face sharpness showed no gain. The result was discarded.
- **A bug that invalidated earlier numbers.** OpenCV applies EXIF orientation when decoding a JPEG, and the code applied the
  camera's rotation again, so every portrait-orientation photo (38% of the gallery) was analysed sideways. Fixing it cut the
  number of photos with no judged face from 494 to 192. Lesson: re-measure after any change to the input path.
- **Ambiguity is in the data.** Smiling squints, downward gazes and profiles are neither clearly open nor clearly closed; a binary
  label cannot represent them. A three-state label (open / lowered or squinting / closed) would be the right next dataset.

## 4. The pieces around the pipeline

**Desktop app** (`app.py`, `ui/index.html`). A pywebview window shows a single-file UI served by a tiny HTTP server on
`127.0.0.1`. Every request needs a random per-run token and a matching `Host` header (defence against other web pages
reaching the server and against DNS rebinding). The folder dialog is opened by Python on the server side, not through
a JavaScript bridge, which did not initialise in the packaged build. Results and thumbnails live in the app's data folder,
so reopening a folder is instant and your "closed / fine" marks persist.

**Lightroom Classic plugin** (`lightroom/`, Lua). It writes the selected photos' paths to a temp file, runs the app in
headless mode (`--scan-list`), reads a small TSV of scores and then writes colour labels, keywords and collections *into
the catalog*. This is deliberately not XMP: reading sidecar metadata back into a catalog for photos that already have ratings
or keywords can overwrite them. The least certain part is the label call (`photo:setRawMetadata("label", ...)`); the plugin counts
failures and tells you, and still applies keywords and collections.

**Packaging.** `pyinstaller` builds the macOS app (about 255 MB). The first build was 1.2 GB because PyTorch, jaxlib, pandas and
pyarrow were pulled in; excluding the modules the app does not use fixed that (see Packaging below).

## 5. Packaging

```bash
uv sync --group build
uv run python fetch_models.py
uv run --group build pyinstaller --noconfirm --windowed --name "Blink Cull" \
  --add-data "models/yunet.onnx:models" --add-data "models/face_landmarker.task:models" --add-data "ui:ui" \
  --collect-all mediapipe --collect-all rawpy --collect-submodules webview \
  --exclude-module torch --exclude-module torchvision --exclude-module jax --exclude-module jaxlib \
  --exclude-module pandas --exclude-module pyarrow --exclude-module scipy --exclude-module sklearn \
  app.py
"dist/Blink Cull.app/Contents/MacOS/Blink Cull" --selftest /path/to/arw/folder   # headless check of the packaged build
```
Pins in `pyproject.toml` (`mediapipe==0.10.21`, `numpy<2`, `opencv-python==4.10`) are deliberate: MediaPipe 1.0.x crashes on
start-up on macOS 26 while initialising its Metal GPU helper, and 0.10.21 requires NumPy 1.x.
PyTorch is only needed for the failed experiment: `uv sync --group experiments`.

## 6. Reproducing the experiments

All scripts run from the repository root and write into `out/` and `data/` (git-ignored):
`learning/step1_extract.py` … `step5_batch.py` are the pipeline built up step by step; `step6`–`step8` are the classifier experiment.
Their comments are in Romanian (the project began as a learning log).

## 7. Ideas that would actually move the numbers

1. A **three-state** labelled set (open / lowered or squinting / closed) with a "cannot tell" option, from several events and cameras.
2. A model for **profile and three-quarter faces**, which MediaPipe's blendshapes handle poorly.
3. A local vision-language model (e.g. through Ollama) to judge only the uncertain yellow zone, evaluated against the same labels.
4. Burst grouping: pick the best frame of a burst (eyes open + sharp) instead of judging frames in isolation.
