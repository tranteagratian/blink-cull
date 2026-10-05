"""Blink Cull desktop app.

A native window (pywebview) showing a UI served by a tiny local HTTP server bound to 127.0.0.1 only.
Every request must carry a random per-run token and a matching Host header, so web pages open in a browser
cannot call it (CSRF / DNS rebinding). Photos are only read; the app's work folder receives thumbnails and
results. .xmp files are written only when the user explicitly asks.

Run from source:     uv run python app.py
Headless self-test:  uv run python app.py --selftest FOLDER_WITH_ARW
Lightroom engine:    uv run python app.py --scan-list LIST.txt --out RESULTS.tsv [--progress F] [--cancel F]

User-facing strings (UI text, error messages) are Romanian for now.
"""
import json
import hashlib
import mimetypes
import os
import secrets
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import blink
import scanner

TOKEN = secrets.token_urlsafe(16)
PORT = 0
WINDOW = None  # native window (None when running in a browser or in tests)


def data_dir():
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".local" / "share"
    d = base / "BlinkCull"
    d.mkdir(parents=True, exist_ok=True)
    return d


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.folder = None
        self.workdir = None
        self.status = "idle"   # idle | scanning | done | error
        self.done = self.total = 0
        self.t0 = 0.0
        self.error = ""
        self.cancel = threading.Event()
        self.data = None
        self.labels = {}       # stem -> "closed" (confirmed by the user) | "open" (false alarm)
        self.cached = False


S = State()


def workdir_for(folder):
    return data_dir() / hashlib.sha1(str(folder).encode()).hexdigest()[:12]


def _scan_job(folder, workdir):
    def progress(done, total):
        S.done, S.total = done, total

    try:
        data = scanner.scan_folder(folder, workdir, progress=progress, cancel=S.cancel)
        S.data = data
        S.status = "done"
    except scanner.Cancelled:
        S.status = "idle"
    except Exception as e:  # noqa: BLE001: any error is reported to the user instead of killing the app
        S.status, S.error = "error", f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------- API routes (return a dict or raise ValueError)
def api_state(_):
    with S.lock:
        elapsed = time.perf_counter() - S.t0 if S.t0 else 0
        eta = (S.total - S.done) * elapsed / S.done if S.done else None
        return {"status": S.status, "folder": S.folder, "done": S.done, "total": S.total,
                "eta_s": eta, "error": S.error, "cached": S.cached}


def api_scan(body):
    folder = Path(body.get("folder", "")).expanduser()
    if not folder.is_dir():
        raise ValueError("Folderul ales nu există.")
    with S.lock:
        if S.status == "scanning":
            raise ValueError("O scanare este deja în curs.")
        files, empty = scanner.list_arw(folder)
        if not files:
            raise ValueError("Nu am găsit fișiere ARW (Sony RAW) în acest folder.")
        S.reset()
        S.folder, S.workdir = str(folder), workdir_for(folder)
        lab = S.workdir / "labels.json"
        S.labels = json.loads(lab.read_text()) if lab.exists() else {}
        scores = S.workdir / "scores.json"
        if scores.exists() and not body.get("rescan"):
            S.data, S.status, S.cached = json.loads(scores.read_text()), "done", True
            return {"status": "done", "cached": True}
        S.status, S.total, S.t0 = "scanning", len(files), time.perf_counter()
        threading.Thread(target=_scan_job, args=(folder, S.workdir), daemon=True).start()
    return {"status": "scanning", "total": len(files)}


def api_cancel(_):
    S.cancel.set()
    return {"ok": True}


def api_reset(_):
    S.cancel.set()
    with S.lock:
        S.reset()
    return {"ok": True}


def _labelled(closed_min, check_min):
    items = scanner.flagged(S.data, closed_min, check_min)
    for it in items:
        it["label"] = S.labels.get(it["stem"])
    return items


def api_results(q):
    if S.status != "done" or not S.data:
        raise ValueError("Nu există rezultate.")
    closed = float(q.get("closed", [scanner.CLOSED_MIN])[0])
    check = float(q.get("check", [scanner.CHECK_MIN])[0])
    d = S.data
    return {"items": _labelled(closed, check),
            "meta": {"folder": S.folder, "total": len(d["photos"]), "errors": len(d["errors"]),
                     "empty_files": d["empty_files"], "seconds": d.get("seconds"), "cached": S.cached}}


def api_label(body):
    stem, value = body.get("stem", ""), body.get("value")
    if Path(stem).name != stem or value not in ("closed", "open", None):
        raise ValueError("Cerere invalidă.")
    if S.workdir is None:
        raise ValueError("Nu există rezultate.")
    if value is None:
        S.labels.pop(stem, None)
    else:
        S.labels[stem] = value
    (S.workdir / "labels.json").write_text(json.dumps(S.labels))
    return {"ok": True}


def api_export(body):
    if S.status != "done":
        raise ValueError("Nu există rezultate de exportat.")
    closed, check = float(body.get("closed", scanner.CLOSED_MIN)), float(body.get("check", scanner.CHECK_MIN))
    items = []
    for it in _labelled(closed, check):
        if it["label"] == "open":      # the user marked it as a false alarm: no label
            continue
        items.append({"stem": it["stem"], "verdict": "inchis" if it["label"] == "closed" else it["verdict"]})
    if body.get("mode") == "beside":
        dest = S.folder
        res = scanner.write_xmp(items, dest, S.folder, beside=True)
    else:
        dest = body.get("dest", "")
        if not dest:
            raise ValueError("Alege un folder de destinație.")
        res = scanner.write_xmp(items, dest, S.folder)
    return {**res, "dest": str(dest), "total": len(items)}


def api_pick(_):
    """Open the native folder dialog from Python (no JS bridge needed); returns the chosen path or None if cancelled."""
    if WINDOW is None:
        raise ValueError("no_native")
    import webview
    kind = webview.FileDialog.FOLDER if hasattr(webview, "FileDialog") else webview.FOLDER_DIALOG
    try:
        r = WINDOW.create_file_dialog(kind)
    except Exception as e:  # noqa: BLE001: surface the error on screen instead of losing it
        raise ValueError(f"Dialogul nativ a eșuat: {type(e).__name__}: {e}")
    return {"path": r[0] if r else None}


def api_reveal(body):
    path = body.get("path", "")
    if not Path(path).is_dir():
        raise ValueError("Folderul nu există.")
    if sys.platform == "darwin":
        subprocess.run(["open", path])
    elif sys.platform == "win32":
        os.startfile(path)  # noqa: S606
    else:
        subprocess.run(["xdg-open", path])
    return {"ok": True}


ROUTES = {
    ("POST", "/api/pick"): api_pick, ("POST", "/api/reveal"): api_reveal,
    ("GET", "/api/state"): api_state, ("GET", "/api/results"): api_results,
    ("POST", "/api/scan"): api_scan, ("POST", "/api/cancel"): api_cancel, ("POST", "/api/reset"): api_reset,
    ("POST", "/api/label"): api_label, ("POST", "/api/export"): api_export,
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _allowed(self, query):
        if self.headers.get("Host", "") not in (f"127.0.0.1:{PORT}", f"localhost:{PORT}"):
            return False  # against DNS rebinding
        return self.path == "/" or self.headers.get("X-Token") == TOKEN or query.get("t", [None])[0] == TOKEN

    def _handle(self, method):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if not self._allowed(query):
            return self._send(403, {"error": "interzis"})
        if method == "GET" and url.path == "/":
            html = Path(blink.resource("ui", "index.html")).read_text(encoding="utf-8").replace("__TOKEN__", TOKEN)
            return self._send(200, html, "text/html; charset=utf-8")
        if method == "GET" and url.path.startswith("/img/"):
            parts = url.path.split("/")  # ['', 'img', 'photos|crops', 'STEM.jpg']
            if len(parts) != 4 or parts[2] not in ("photos", "crops") or Path(parts[3]).name != parts[3] or not S.workdir:
                return self._send(404, {"error": "nu exista"})
            f = S.workdir / parts[2] / parts[3]
            if not f.is_file():
                return self._send(404, {"error": "nu exista"})
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(f.name)[0] or "image/jpeg")
            self.send_header("Content-Length", str(f.stat().st_size))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(f.read_bytes())
            return
        fn = ROUTES.get((method, url.path))
        if not fn:
            return self._send(404, {"error": "nu exista"})
        try:
            body = {}
            if method == "POST":
                n = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(n) or b"{}")
            return self._send(200, fn(body if method == "POST" else query))
        except ValueError as e:
            return self._send(400, {"error": str(e)})
        except Exception as e:  # noqa: BLE001
            return self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")


def start_server():
    global PORT
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    PORT = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{PORT}/"


def _arg(name):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else None


def scan_list_mode():
    """Headless mode used by the Lightroom plugin: read ARW paths (one per line), write a TSV:
    path <TAB> score <TAB> faces_judged <TAB> status      (status: ok | nojudged | missing | error)
    Optional: --progress FILE (writes "done total") and --cancel FILE (stops cleanly if it exists).
    """
    list_file, out_file = _arg("--scan-list"), _arg("--out")
    progress_file, cancel_file = _arg("--progress"), _arg("--cancel")
    paths = [ln.strip() for ln in open(list_file, encoding="utf-8") if ln.strip()]
    landmarker = blink.make_landmarker()
    with open(out_file, "w", encoding="utf-8") as out:
        for i, p in enumerate(paths, 1):
            if cancel_file and Path(cancel_file).exists():
                break
            score, judged, status = "", 0, "ok"
            try:
                if not Path(p).is_file() or Path(p).stat().st_size == 0:
                    status = "missing"
                else:
                    _, faces = blink.analyze_photo(p, landmarker)
                    good = [f for f in faces if f.status == "ok"]
                    judged = len(good)
                    if good:
                        score = round(max((f.blink_right + f.blink_left) / 2 for f in good), 3)
                    else:
                        status = "nojudged"
            except Exception as e:  # noqa: BLE001: one bad photo must not stop the rest
                status = "error"
            out.write(f"{p}\t{score}\t{judged}\t{status}\n")
            out.flush()
            if progress_file:
                Path(progress_file).write_text(f"{i} {len(paths)}")


def main():
    if "--scan-list" in sys.argv:
        return scan_list_mode()
    if "--selftest" in sys.argv:  # headless check (also usable on the packaged app)
        folder = sys.argv[sys.argv.index("--selftest") + 1]
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            data = scanner.scan_folder(folder, tmp, limit=3)
        print(f"selftest ok: {len(data['photos'])} poze analizate, {len(data['errors'])} erori")
        return

    url = start_server()
    try:
        import webview
    except ImportError:
        import webbrowser
        print("pywebview lipseste: deschid in browser:", url)
        webbrowser.open(url)
        threading.Event().wait()
        return
    global WINDOW
    WINDOW = webview.create_window("Blink Cull", url, width=1280, height=860, min_size=(900, 600))
    webview.start()


if __name__ == "__main__":
    main()
