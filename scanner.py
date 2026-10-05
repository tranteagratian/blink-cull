"""UI-independent logic: scanning a folder, turning scores into verdicts, and exporting XMP sidecars.

Used by the command line (blinkcull.py) and the desktop app (app.py).
RAW files are only ever read. Scanning writes into `workdir`; .xmp files are written only on explicit request.

Verdict values (plain strings, they appear in saved files, the UI and the Lightroom plugin):
  "inchis"    closed, the red group    (score >= CLOSED_MIN)
  "verifica"  to check, the yellow group (CHECK_MIN <= score < CLOSED_MIN)
  "ok"        nothing to show
"""
import json
import time
from pathlib import Path

import cv2

import blink

CLOSED_MIN = 0.45  # score at/above which a photo is "inchis" (red)
CHECK_MIN = 0.25   # score at/above which a photo is "verifica" (yellow)


class Cancelled(Exception):
    pass


def list_arw(folder):
    """(non-empty ARW files, number of empty 0-byte ARW files; interrupted card copies leave these behind)"""
    all_arw = [p for p in Path(folder).iterdir() if p.suffix.lower() == ".arw" and not p.name.startswith(".")]
    files = sorted(p for p in all_arw if p.stat().st_size > 0)
    return files, len(all_arw) - len(files)


def scan_folder(folder, workdir, progress=None, cancel=None, limit=0):
    """Analyze every photo. Writes scores.json plus thumbnails into `workdir` and returns the scores dict.

    progress(done, total) is called after each photo; cancel is a threading.Event.
    """
    workdir = Path(workdir)
    (workdir / "photos").mkdir(parents=True, exist_ok=True)
    (workdir / "crops").mkdir(parents=True, exist_ok=True)
    files, empty = list_arw(folder)
    if limit:
        files = files[:limit]

    landmarker = blink.make_landmarker()
    scores, errors = [], []
    t0 = time.perf_counter()
    for n, arw in enumerate(files, 1):
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        try:
            img, faces = blink.analyze_photo(arw, landmarker)
        except Exception as e:  # corrupt file, no embedded preview, ...
            errors.append({"photo": arw.name, "error": f"{type(e).__name__}: {e}"})
            if progress:
                progress(n, len(files))
            continue

        judged = [f for f in faces if f.status == "ok"]
        for f in judged:
            f.score = (f.blink_right + f.blink_left) / 2   # mean of the two eyeBlink blendshapes
        worst = max(judged, key=lambda f: f.score) if judged else None  # the most "closed" face decides the photo
        skipped = [f for f in faces if f.status in ("neclara", "fara_puncte")]
        scores.append({
            "photo": arw.name, "stem": arw.stem,
            "score": None if worst is None else round(worst.score, 3),
            "faces_found": len(faces), "faces_judged": len(judged),
            "face_px": 0 if worst is None else round(worst.width_px),
            "skipped": {s: sum(f.status == s for f in skipped) for s in ("neclara", "fara_puncte")},
            "skipped_max_px": max((round(f.width_px) for f in skipped), default=0),
        })

        if faces:  # annotated thumbnail; box colours do not depend on thresholds, so they stay valid when those change
            thumb = img.copy()
            lw = max(4, img.shape[1] // 400)
            for f in faces:
                x, y, w, h = map(int, f.box)
                if f is worst:
                    color, width = (0, 0, 255), lw * 2          # most suspicious face: thick red
                elif f.status == "ok":
                    color, width = (0, 200, 0), lw              # judged: green
                else:
                    color, width = (160, 160, 160), lw          # skipped: grey
                cv2.rectangle(thumb, (x, y), (x + w, y + h), color, width)
            k = 1100 / max(thumb.shape[:2])
            cv2.imwrite(str(workdir / "photos" / f"{arw.stem}.jpg"), cv2.resize(thumb, None, fx=k, fy=k), [cv2.IMWRITE_JPEG_QUALITY, 82])
        if worst is not None:
            k = 360 / max(worst.crop.shape[:2])
            cv2.imwrite(str(workdir / "crops" / f"{arw.stem}.jpg"), cv2.resize(worst.crop, None, fx=k, fy=k), [cv2.IMWRITE_JPEG_QUALITY, 85])
        if progress:
            progress(n, len(files))

    data = {"folder": str(folder), "photos": scores, "errors": errors, "empty_files": empty,
            "seconds": round(time.perf_counter() - t0, 1)}
    (workdir / "scores.json").write_text(json.dumps(data, indent=1))
    return data


def verdict(p, closed_min=CLOSED_MIN, check_min=CHECK_MIN):
    s = p["score"]
    if s is None:
        return "ok"
    if s >= closed_min:
        return "inchis"
    if s >= check_min:
        return "verifica"
    return "ok"


def flagged(data, closed_min=CLOSED_MIN, check_min=CHECK_MIN):
    """The photos worth showing, with their verdict, most suspicious first."""
    out = []
    for p in data["photos"]:
        v = verdict(p, closed_min, check_min)
        if v != "ok":
            out.append({**p, "verdict": v})
    out.sort(key=lambda r: -r["score"])
    return out


XMP = """<?xpacket begin="\\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmp:Label="{label}">
   <dc:subject><rdf:Bag><rdf:li>{keyword}</rdf:li></rdf:Bag></dc:subject>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>
"""
LABELS = {"inchis": ("Red", "blinkcull-inchis"), "verifica": ("Yellow", "blinkcull-verifica")}


def write_xmp(items, dest, photo_folder, beside=False):
    """Write one .xmp sidecar per photo into `dest`. items = [{"stem": ..., "verdict": ...}, ...].

    beside=False: `dest` must be OUTSIDE the photo folder, otherwise this refuses.
    beside=True:  `dest` is the photo folder itself; an existing .xmp is NEVER overwritten (it may hold edits).
    Returns {"written": n, "skipped_existing": [stem, ...]}.
    """
    dest, photo_folder = Path(dest).resolve(), Path(photo_folder).resolve()
    inside = dest == photo_folder or photo_folder in dest.parents
    if inside and not beside:
        raise ValueError("Destinatia e in folderul cu poze. Alege alt folder, sau confirma explicit scrierea langa poze.")
    dest.mkdir(parents=True, exist_ok=True)
    written, skipped = 0, []
    for it in items:
        target = dest / f"{it['stem']}.xmp"
        if beside and target.exists():
            skipped.append(it["stem"])
            continue
        label, keyword = LABELS[it["verdict"]]
        target.write_text(XMP.format(label=label, keyword=keyword), encoding="utf-8")
        written += 1
    return {"written": written, "skipped_existing": skipped}
