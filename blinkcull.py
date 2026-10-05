"""blinkcull command line: scan a folder of ARW files and print a summary. The graphical app is app.py.

Usage:   uv run python blinkcull.py FOLDER [--out out/scan] [--limit N] [--xmp-dir DIR]
         uv run python blinkcull.py FOLDER --out out/scan --rebuild --check-min 0.2
"""
import argparse
import json
import time
from pathlib import Path

import scanner

ap = argparse.ArgumentParser()
ap.add_argument("folder")
ap.add_argument("--out", default="out/scan")
ap.add_argument("--limit", type=int, default=0, help="only process the first N photos (for testing)")
ap.add_argument("--rebuild", action="store_true", help="do not scan again: reuse the existing scores.json")
ap.add_argument("--closed-min", type=float, default=scanner.CLOSED_MIN)
ap.add_argument("--check-min", type=float, default=scanner.CHECK_MIN)
ap.add_argument("--xmp-dir", default="", help="write .xmp sidecars (Lightroom labels) into this folder, which must be SEPARATE from the photos")
args = ap.parse_args()

out = Path(args.out)
if args.rebuild:
    data = json.loads((out / "scores.json").read_text())
else:
    t0 = time.perf_counter()
    last = [0]

    def progress(done, total):
        if done - last[0] >= 100 or done == total:
            last[0] = done
            print(f"  {done}/{total}  ({time.perf_counter() - t0:.0f}s)", flush=True)

    data = scanner.scan_folder(args.folder, out, progress=progress, limit=args.limit)

items = scanner.flagged(data, args.closed_min, args.check_min)
n_closed = sum(i["verdict"] == "inchis" for i in items)
print(f"{len(data['photos'])} photos analysed | closed (>= {args.closed_min}): {n_closed} | "
      f"to check (>= {args.check_min}): {len(items) - n_closed} | errors: {len(data['errors'])} | "
      f"empty ARW files skipped: {data['empty_files']}")

if args.xmp_dir:
    res = scanner.write_xmp(items, args.xmp_dir, args.folder)
    print(f"XMP: {res['written']} sidecars written to {args.xmp_dir} (red = closed, yellow = to check). Photo folder untouched.")
