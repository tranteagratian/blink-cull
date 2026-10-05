"""Blink Cull engine: the headless closed-eye scorer used by the Lightroom plugin.

    BlinkCullEngine --scan-list LIST.txt --out RESULTS.tsv [--progress FILE] [--cancel FILE]
    BlinkCullEngine --folder DIR [--out RESULTS.tsv]          # convenience: score every ARW in a folder
    BlinkCullEngine --selftest DIR                            # score the first 3 ARW files, print a one-line summary

Output (UTF-8 TSV, one line per photo, written as it goes):

    path <TAB> score <TAB> faces_judged <TAB> status

  score         0..1, higher = more closed, for the most closed judged face in the photo; empty if no face was judged
  faces_judged  how many faces were sharp and large enough to measure
  status        ok | nojudged (faces found but none judged) | missing (file absent or empty) | error

--progress FILE  is rewritten after every photo with "done total"
--cancel FILE    if this file appears, the engine stops cleanly after the current photo (results so far are kept)

RAW files are only read. Nothing is ever written next to them.
"""
import argparse
import sys
from pathlib import Path

import blink


class LazyLandmarker:
    """Loads the MediaPipe model only when a face actually needs it, so missing/empty/corrupt files cost nothing."""

    def __init__(self):
        self._lm = None

    def detect(self, image):
        if self._lm is None:
            self._lm = blink.make_landmarker()
        return self._lm.detect(image)


def list_arw(folder):
    """Non-empty .arw files of a folder, sorted (hidden files such as macOS '._' resource forks are ignored)."""
    files = [p for p in Path(folder).iterdir() if p.suffix.lower() == ".arw" and not p.name.startswith(".")]
    return sorted(p for p in files if p.stat().st_size > 0)


def score_photo(path, landmarker):
    """(score or None, faces_judged, status) for one photo."""
    p = Path(path)
    if not p.is_file() or p.stat().st_size == 0:
        return None, 0, "missing"
    try:
        img = blink.load_preview(p)
        faces = [blink.analyze_face(img, landmarker, *box) for box in blink.find_faces(img)]
    except Exception as e:  # noqa: BLE001: one bad photo must not stop the rest
        print(f"error: {p.name}: {type(e).__name__}: {e}", file=sys.stderr)
        return None, 0, "error"
    judged = [f for f in faces if f.status == "ok"]
    if not judged:
        return None, 0, "nojudged"
    # the photo is as suspicious as its most "closed" face; a face's score is the mean of its two eyeBlink values
    return round(max((f.blink_right + f.blink_left) / 2 for f in judged), 3), len(judged), "ok"


def run(paths, out, progress=None, cancel=None):
    """Score `paths` and write TSV lines to the open text file `out`. Returns the number of photos processed."""
    landmarker = LazyLandmarker()
    done = 0
    for done, path in enumerate(paths, 1):
        if cancel and Path(cancel).exists():
            return done - 1
        score, judged, status = score_photo(path, landmarker)
        out.write(f"{path}\t{'' if score is None else score}\t{judged}\t{status}\n")
        out.flush()
        if progress:
            Path(progress).write_text(f"{done} {len(paths)}")
    return done


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--scan-list", help="text file with one photo path per line")
    src.add_argument("--folder", help="score every ARW file in this folder")
    src.add_argument("--selftest", metavar="DIR", help="score the first 3 ARW files of DIR and print a summary")
    ap.add_argument("--out", help="TSV output file (default: standard output)")
    ap.add_argument("--progress", help="file rewritten after every photo with 'done total'")
    ap.add_argument("--cancel", help="stop cleanly if this file exists")
    args = ap.parse_args(argv)

    if args.selftest:
        paths = [str(p) for p in list_arw(args.selftest)[:3]]
        if not paths:
            sys.exit("selftest: no non-empty ARW files found")
        import io
        buf = io.StringIO()
        run(paths, buf)
        rows = [line.split("\t") for line in buf.getvalue().splitlines()]
        bad = [r for r in rows if r[3] == "error"]
        print(f"selftest ok: {len(rows)} photos scored, {len(bad)} errors")
        return 1 if bad else 0

    if args.scan_list:
        paths = [ln.strip() for ln in open(args.scan_list, encoding="utf-8") if ln.strip()]
    else:
        paths = [str(p) for p in list_arw(args.folder)]
    if args.out:
        with open(args.out, "w", encoding="utf-8") as out:
            run(paths, out, args.progress, args.cancel)
    else:
        run(paths, sys.stdout, args.progress, args.cancel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
