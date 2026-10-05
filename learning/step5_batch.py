"""Pasul 5: ruleaza pipeline-ul pe un esantion de poze si genereaza o pagina HTML de verificat.

  1. alege N poze repartizate uniform prin folder
  2. pentru fiecare: preview -> fete -> ochi (blink.py)
  3. salveaza decupajele fetelor judecate in out/report/
  4. scrie out/report/index.html: cele mai suspecte fete primele, cu butoane Inchis/Deschis
     (raspunsurile tale devin setul de evaluare cu care calibram pragurile)

Scrie DOAR in out/report/. Folderul cu poze e citit, niciodata modificat.

Rulare:  uv run python learning/step5_batch.py --folder DIR [--n 80]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # blink.py / scanner.py sunt in radacina
import argparse
import html
import json
import time
from collections import Counter
from pathlib import Path

import cv2

import blink

ap = argparse.ArgumentParser()
ap.add_argument("--folder", required=True)
ap.add_argument("--n", type=int, default=80)
args = ap.parse_args()

report = Path("out/report")
(report / "crops").mkdir(parents=True, exist_ok=True)
(report / "photos").mkdir(parents=True, exist_ok=True)

# 1) Esantion uniform: daca sunt 1578 poze si vrem 80, luam una la ~20.
all_arw = sorted(p for p in Path(args.folder).glob("*.ARW") if p.stat().st_size > 0)
step = max(1, len(all_arw) // args.n)
sample = all_arw[::step][: args.n]
print(f"{len(all_arw)} ARW-uri in folder, analizez {len(sample)} (una la {step})")

landmarker = blink.make_landmarker()
rows = []            # o intrare per fata judecata
status_count = Counter()
errors = []
t_start = time.perf_counter()

for n, arw in enumerate(sample, 1):
    try:
        img, faces = blink.analyze_photo(arw, landmarker)
    except Exception as e:  # fisier corupt etc.: il notam si mergem mai departe
        errors.append((arw.name, f"{type(e).__name__}: {e}"))
        continue

    judged = [f for f in faces if f.status == "ok"]
    for f in faces:
        status_count[f.status] += 1

    if judged:
        # poza intreaga, micsorata, cu patratele pe fetele judecate (pentru context)
        thumb = img.copy()
        for i, f in enumerate(judged):
            x, y, w, h = map(int, f.box)
            cv2.rectangle(thumb, (x, y), (x + w, y + h), (0, 255, 0), max(4, img.shape[1] // 400))
        k = 900 / max(thumb.shape[:2])
        cv2.imwrite(str(report / "photos" / f"{arw.stem}.jpg"), cv2.resize(thumb, None, fx=k, fy=k), [cv2.IMWRITE_JPEG_QUALITY, 80])

    for i, f in enumerate(judged):
        key = f"{arw.stem}_f{i}"
        k = 360 / max(f.crop.shape[:2])
        cv2.imwrite(str(report / "crops" / f"{key}.jpg"), cv2.resize(f.crop, None, fx=k, fy=k), [cv2.IMWRITE_JPEG_QUALITY, 85])
        rows.append({
            "key": key, "photo": arw.name, "width_px": round(f.width_px),
            "sharpness": round(f.sharpness), "openness": round(f.openness, 3),
            "ear_right": round(f.ear_right, 3), "ear_left": round(f.ear_left, 3),
            "blink_right": round(f.blink_right, 3), "blink_left": round(f.blink_left, 3),
        })
    if n % 10 == 0 or n == len(sample):
        print(f"  {n}/{len(sample)}  ({time.perf_counter() - t_start:.0f}s)  fete judecate pana acum: {len(rows)}")

rows.sort(key=lambda r: r["openness"])  # cele mai inchise primele
(report / "results.json").write_text(json.dumps({"faces": rows, "skipped": dict(status_count), "errors": errors}, indent=1))

# 2) Pagina HTML
cards = "\n".join(f"""
<div class="card" data-key="{r['key']}">
  <a href="photos/{Path(r['photo']).stem}.jpg" target="_blank"><img src="crops/{r['key']}.jpg" loading="lazy"></a>
  <div class="meta">
    <b>{html.escape(r['photo'])}</b>
    <div class="big">{r['openness']:.2f}</div>
    <div>EAR dr {r['ear_right']:.2f} · st {r['ear_left']:.2f}</div>
    <div>blink dr {r['blink_right']:.2f} · st {r['blink_left']:.2f}</div>
    <div class="dim">{r['width_px']} px · claritate {r['sharpness']}</div>
    <div class="btns"><button data-v="closed">Închis</button><button data-v="open">Deschis</button></div>
  </div>
</div>""" for r in rows)

skipped = ", ".join(f"{v} {k}" for k, v in status_count.items() if k != "ok") or "niciuna"
page = f"""<!doctype html>
<html lang="ro"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Blink report</title>
<style>
:root {{ --bg:#f6f6f4; --fg:#1b1b1b; --card:#fff; --line:#ddd; --dim:#777; --closed:#c0392b; --open:#2e7d32; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#161616; --fg:#eee; --card:#222; --line:#383838; --dim:#999; }} }}
body {{ margin:0; padding:16px; background:var(--bg); color:var(--fg); font:15px/1.4 -apple-system, system-ui, sans-serif; }}
h1 {{ margin:0 0 4px; font-size:20px; }}
.sub {{ color:var(--dim); margin-bottom:12px; }}
.bar {{ position:sticky; top:0; background:var(--bg); padding:8px 0; display:flex; gap:12px; align-items:center; border-bottom:1px solid var(--line); margin-bottom:12px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:12px; }}
.card {{ background:var(--card); border:2px solid var(--line); border-radius:8px; overflow:hidden; display:flex; flex-direction:column; }}
.card img {{ width:100%; display:block; }}
.meta {{ padding:8px 10px 10px; }}
.big {{ font-size:28px; font-weight:600; }}
.dim {{ color:var(--dim); font-size:13px; }}
.btns {{ display:flex; gap:8px; margin-top:8px; }}
button {{ flex:1; padding:8px; border:1px solid var(--line); border-radius:6px; background:transparent; color:var(--fg); font:inherit; cursor:pointer; }}
.card.closed {{ border-color:var(--closed); }} .card.closed button[data-v=closed] {{ background:var(--closed); color:#fff; }}
.card.open {{ border-color:var(--open); }} .card.open button[data-v=open] {{ background:var(--open); color:#fff; }}
.export {{ margin-left:auto; flex:none; padding:8px 14px; }}
</style></head><body>
<h1>Raport ochi închiși</h1>
<div class="sub">{len(sample)} poze analizate · {len(rows)} fețe judecate · sărite: {skipped} · erori: {len(errors)}<br>
Ordonate după cât de deschis e ochiul mai deschis (mic = ambii ochi închiși). Click pe imagine = poza întreagă.</div>
<div class="bar"><span id="count">0 marcate</span><button class="export" id="export">Export răspunsuri (JSON)</button></div>
<div class="grid">{cards}</div>
<script>
const rows = {json.dumps(rows)};
const K = "blink-labels";
let labels = {{}};
try {{ labels = JSON.parse(localStorage.getItem(K) || "{{}}"); }} catch (e) {{}}
const save = () => {{ try {{ localStorage.setItem(K, JSON.stringify(labels)); }} catch (e) {{}} }};
const paint = () => {{
  document.querySelectorAll(".card").forEach(c => {{ c.classList.remove("open", "closed"); const v = labels[c.dataset.key]; if (v) c.classList.add(v); }});
  document.getElementById("count").textContent = Object.keys(labels).length + " marcate din " + rows.length;
}};
document.querySelectorAll(".card button").forEach(b => b.addEventListener("click", () => {{
  const key = b.closest(".card").dataset.key, v = b.dataset.v;
  if (labels[key] === v) delete labels[key]; else labels[key] = v;
  save(); paint();
}}));
document.getElementById("export").addEventListener("click", () => {{
  const out = rows.filter(r => labels[r.key]).map(r => ({{...r, label: labels[r.key]}}));
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 1)], {{type: "application/json"}}));
  a.download = "labels.json"; a.click();
}});
paint();
</script></body></html>"""
(report / "index.html").write_text(page)

total = time.perf_counter() - t_start
print(f"\nGata in {total:.0f}s ({total / len(sample):.2f}s/poza)")
print(f"Fete judecate: {len(rows)} | sarite: {dict(status_count)} | erori: {len(errors)}")
for name, err in errors:
    print(f"  EROARE {name}: {err}")
print(f"Raport: {report / 'index.html'}")
