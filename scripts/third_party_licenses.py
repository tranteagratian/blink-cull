"""Print the licence texts of the third-party packages bundled in the engine (to stdout).

The engine is built with PyInstaller from the project's runtime dependencies. Packages that are in the dependency tree
but NOT in the bundle (jax and its friends are excluded in build_engine.sh) are skipped. Verified against the executable's
PYZ listing: `uv run --group build pyi-archive_viewer -l -r <engine>`.
"""
import re
from importlib import metadata
from pathlib import Path

EXCLUDED = {"jax", "jaxlib", "scipy", "ml-dtypes", "opt-einsum"}
ROOTS = ["mediapipe", "numpy", "opencv-python", "pillow", "rawpy"]
norm = lambda n: re.sub(r"[-_.]+", "-", n).lower()


def license_files(d):
    out = []
    for f in d.files or []:
        low, s = f.name.lower(), str(f).lower()
        if any(low.startswith(p) for p in ("license", "licence", "copying", "notice")) or "licenses/" in s or "license_files/" in s:
            p = Path(d.locate_file(f))
            if p.is_file() and p.stat().st_size < 200_000:
                out.append((f.name, p.read_text(errors="replace").strip()))
    return out


seen, todo = {}, list(ROOTS)
while todo:
    n = todo.pop()
    k = norm(n)
    if k in seen or k in EXCLUDED:
        continue
    try:
        d = metadata.distribution(n)
    except metadata.PackageNotFoundError:
        seen[k] = None
        continue
    seen[k] = d
    todo += [re.split(r"[ ;<>=!~\[(]", r.strip(), 1)[0] for r in (d.requires or []) if "extra ==" not in r]

print("Licences of the third-party packages bundled in the Blink Cull engine.\n"
      "The engine is built with PyInstaller; each package below keeps its own licence.\n"
      "LibRaw (inside rawpy) is shipped as a separate shared library that can be replaced (LGPL-2.1 / CDDL-1.0).\n"
      "The YuNet face detector model (OpenCV Zoo) is MIT-licensed; the MediaPipe Face Landmarker model is Apache-2.0 (see its model card).\n")
for k, d in sorted(seen.items()):
    if d is None:
        continue
    lic = d.metadata.get("License-Expression") or d.metadata.get("License") or ""
    lic = lic.splitlines()[0][:90] if lic else "see below"
    print(f"{'=' * 78}\n{d.metadata['Name']} {d.version}   [{lic}]\n{'=' * 78}")
    texts = license_files(d)
    if not texts:
        print("(no licence file is shipped inside this package; see its project page)\n")
    for fn, t in texts:
        print(f"--- {fn} ---\n{t}\n")
