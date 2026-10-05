"""Pasul 1: scoate JPEG-ul incorporat dintr-un fisier ARW.

Un ARW e un container (format TIFF) care contine:
  - datele RAW (senzorul, ~33 MP, necomprimat/slab comprimat, nu se poate afisa direct)
  - unul sau mai multe JPEG-uri "preview" generate de aparat la momentul pozei
Noi citim doar JPEG-ul, fara sa dezvoltam RAW-ul.

Rulare:  uv run python learning/step1_extract.py cale/poza.ARW
"""
import io
import sys
import time
from pathlib import Path

import rawpy
from PIL import Image

if len(sys.argv) < 2:
    sys.exit("usage: uv run python learning/step1_extract.py PATH/TO/photo.ARW")
arw_path = Path(sys.argv[1])

out_dir = Path("out")
out_dir.mkdir(exist_ok=True)

t0 = time.perf_counter()

# 1) Deschidem fisierul ARW. `rawpy` e un wrapper peste LibRaw.
with rawpy.imread(str(arw_path)) as raw:
    # 2) Cerem preview-ul incorporat. Primim octetii JPEG-ului si formatul.
    thumb = raw.extract_thumb()
    # Aparatul nu roteste preview-ul; doar noteaza orientarea in metadate.
    # LibRaw o expune ca `flip`: 0 = normal, 3 = 180 grade, 5 = 90 antiorar, 6 = 90 orar.
    flip = raw.sizes.flip

# 3) Daca preview-ul e deja JPEG, octetii sunt chiar continutul unui fisier .jpg.
#    Il salvam asa cum e, fara re-encodare (fara pierdere de calitate).
assert thumb.format == rawpy.ThumbFormat.JPEG, f"format neasteptat: {thumb.format}"
jpg_path = out_dir / f"{arw_path.stem}.jpg"
img = Image.open(io.BytesIO(thumb.data))

# 4) Aplicam orientarea. PIL roteste antiorar, deci "6 = 90 orar" devine rotate(-90).
# Daca poza trebuie rotita, JPEG-ul se re-encodeaza (calitate 95, pierdere neglijabila).
# Daca e deja normala, pastram octetii originali neatinsi.
ROTATE = {3: 180, 5: 90, 6: -90}
if flip in ROTATE:
    img = img.rotate(ROTATE[flip], expand=True)
    img.save(jpg_path, quality=95)
else:
    jpg_path.write_bytes(thumb.data)

elapsed_ms = (time.perf_counter() - t0) * 1000

print(f"ARW sursa     : {arw_path.name}  ({arw_path.stat().st_size / 1e6:.1f} MB)")
print(f"JPEG extras   : {jpg_path}  ({len(thumb.data) / 1e6:.1f} MB)")
print(f"Orientare     : flip={flip} ({'rotit ' + str(ROTATE[flip]) + ' grade' if flip in ROTATE else 'neschimbat'})")
print(f"Rezolutie     : {img.size[0]} x {img.size[1]} px")
print(f"Timp          : {elapsed_ms:.0f} ms")
