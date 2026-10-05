"""Verificare de recall: cate poze cu ochi inchisi NU marcheaza programul?

Alege la intamplare poze pe care blinkcull NU le-a marcat (nu sunt in out/scan/results.json) si le
pune intr-o pagina, ca omul sa spuna care ar fi trebuit marcate. Doua grupe, evaluate separat:
  A  poze cu cel putin o fata judecata, dar cu scor sub pragul de verificare
  B  poze fara nicio fata judecata (fete neclare, mici, intoarse sau lipsa)

Scrie DOAR in out/recall/. Citeste ARW-urile doar pentru citire.

Rulare:  uv run python learning/recall_check.py FOLDER [--per-group 40]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # blink.py / scanner.py sunt in radacina
import argparse
import html
import json
import random
from pathlib import Path

import cv2

import blink

ap = argparse.ArgumentParser()
ap.add_argument("folder")
ap.add_argument("--per-group", type=int, default=40)
ap.add_argument("--seed", type=int, default=0)
args = ap.parse_args()

out = Path("out/recall")
(out / "photos").mkdir(parents=True, exist_ok=True)

import scanner
flagged = {p["stem"] for p in scanner.flagged(json.load(open("out/scan/scores.json")))}
files = sorted(p for p in Path(args.folder).glob("*.ARW") if p.stat().st_size > 0 and p.stem not in flagged)
random.Random(args.seed).shuffle(files)  # ordine aleatoare reproductibila: esantionul nu e ales de mine
print(f"{len(files)} poze nemarcate; caut {args.per_group} per grupa", flush=True)

landmarker = blink.make_landmarker()
samples = {"A": [], "B": []}
tried = 0
for arw in files:
    if all(len(v) >= args.per_group for v in samples.values()):
        break
    try:
        img, faces = blink.analyze_photo(arw, landmarker)
    except Exception:
        continue
    tried += 1
    judged = [f for f in faces if f.status == "ok"]
    group = "A" if judged else "B"
    if len(samples[group]) >= args.per_group:
        continue

    thumb = img.copy()
    lw = max(4, img.shape[1] // 400)
    for f in faces:
        x, y, w, h = map(int, f.box)
        cv2.rectangle(thumb, (x, y), (x + w, y + h), (0, 200, 0) if f.status == "ok" else (160, 160, 160), lw)
    k = 1000 / max(thumb.shape[:2])
    cv2.imwrite(str(out / "photos" / f"{arw.stem}.jpg"), cv2.resize(thumb, None, fx=k, fy=k), [cv2.IMWRITE_JPEG_QUALITY, 82])
    score = max(((f.blink_right + f.blink_left) / 2 for f in judged), default=None)
    why = sorted({f.status for f in faces if f.status != "ok"})
    samples[group].append({"photo": arw.name, "stem": arw.stem, "group": group,
                           "score": None if score is None else round(score, 3),
                           "faces_found": len(faces), "faces_judged": len(judged), "skipped_reasons": why})
    print(f"  A {len(samples['A'])}/{args.per_group}  B {len(samples['B'])}/{args.per_group}  (analizate {tried})", flush=True)

json.dump(samples, open(out / "samples.json", "w"), indent=1)

ORDER = random.Random(1)
cards = []
for g in ("A", "B"):
    for s in samples[g]:
        cards.append(s)
ORDER.shuffle(cards)  # amestecate: nu stii din ce grupa e fiecare poza cand o judeci

card_html = "\n".join(f"""<div class="card" data-key="{s['stem']}">
  <a href="photos/{s['stem']}.jpg" target="_blank"><img src="photos/{s['stem']}.jpg" loading="lazy"></a>
  <div class="meta"><b>{html.escape(s['photo'])}</b>
  <div class="btns"><button data-v="closed">Are ochi închiși</button><button data-v="open">Ochi deschiși (ok)</button></div></div></div>""" for s in cards)

page = f"""<!doctype html>
<html lang="ro"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>blinkcull recall</title>
<style>
:root {{ --bg:#f6f6f4; --fg:#1b1b1b; --card:#fff; --line:#ddd; --dim:#777; --closed:#c0392b; --open:#2e7d32; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#161616; --fg:#eee; --card:#222; --line:#383838; --dim:#999; }} }}
body {{ margin:0; padding:16px; background:var(--bg); color:var(--fg); font:15px/1.4 -apple-system, system-ui, sans-serif; }}
h1 {{ margin:0 0 4px; font-size:20px; }} .dim {{ color:var(--dim); font-size:13px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(340px,1fr)); gap:12px; margin-top:10px; }}
.card {{ background:var(--card); border:2px solid var(--line); border-radius:8px; overflow:hidden; }}
.card img {{ width:100%; display:block; }} .meta {{ padding:8px 10px 10px; }}
.btns {{ display:flex; gap:8px; margin-top:8px; }}
button {{ flex:1; padding:8px; border:1px solid var(--line); border-radius:6px; background:transparent; color:var(--fg); font:inherit; cursor:pointer; }}
.card.closed {{ border-color:var(--closed); }} .card.closed button[data-v=closed] {{ background:var(--closed); color:#fff; }}
.card.open {{ border-color:var(--open); }} .card.open button[data-v=open] {{ background:var(--open); color:#fff; }}
.bar {{ position:sticky; top:0; background:var(--bg); padding:8px 0; display:flex; gap:12px; align-items:center; border-bottom:1px solid var(--line); }}
.export {{ margin-left:auto; flex:none; padding:7px 14px; }}
</style></head><body>
<h1>Pozele pe care programul NU le-a marcat</h1>
<div class="dim">{len(cards)} poze alese la întâmplare. Pentru fiecare: are o persoană care contează ochii închiși? Dacă da, apasă „Are ochi închiși"; dacă poza e bună, apasă „Ochi deschiși (ok)". Chenarele verzi = fețe judecate de program, gri = fețe găsite dar sărite. Clic pe imagine = mărit.</div>
<div class="bar"><span id="count"></span><button class="export" id="export">Export răspunsuri (JSON)</button></div>
<div class="grid">{card_html}</div>
<script>
const K = "blinkcull-recall-labels-v2"; let labels = {{}};
try {{ labels = JSON.parse(localStorage.getItem(K) || "{{}}"); }} catch (e) {{}}
const paint = () => {{ document.querySelectorAll(".card").forEach(c => {{ c.classList.remove("open","closed"); const v = labels[c.dataset.key]; if (v) c.classList.add(v); }});
  document.getElementById("count").textContent = Object.keys(labels).length + " marcate din {len(cards)}"; }};
document.querySelectorAll(".card button").forEach(b => b.addEventListener("click", () => {{
  const k = b.closest(".card").dataset.key, v = b.dataset.v; if (labels[k] === v) delete labels[k]; else labels[k] = v;
  try {{ localStorage.setItem(K, JSON.stringify(labels)); }} catch (e) {{}} paint(); }}));
document.getElementById("export").addEventListener("click", () => {{
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(labels, null, 1)], {{type: "application/json"}}));
  a.download = "recall-labels.json"; a.click(); }});
paint();
</script></body></html>"""
(out / "index.html").write_text(page)
print(f"\nGata: grupa A {len(samples['A'])} poze, grupa B {len(samples['B'])} poze | {out / 'index.html'}")
