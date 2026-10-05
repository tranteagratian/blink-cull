"""Security and basic behaviour of the local HTTP server. No photos or model files are needed."""
import json
import urllib.error
import urllib.request

import pytest

import app


@pytest.fixture(scope="module")
def base():
    return app.start_server().rstrip("/")


def call(base, path, body=None, token=True, host=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Token"] = app.TOKEN
    if host:
        headers["Host"] = host
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                 headers=headers, method="GET" if body is None else "POST")
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if r.headers["Content-Type"].startswith("application/json") else raw)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_index_is_served_with_token_injected(base):
    code, page = call(base, "/", token=False)
    assert code == 200 and app.TOKEN.encode() in page and b"__TOKEN__" not in page


def test_api_requires_token(base):
    assert call(base, "/api/state", token=False)[0] == 403
    assert call(base, "/api/scan", {"folder": "/"}, token=False)[0] == 403


def test_wrong_host_header_is_rejected(base):
    assert call(base, "/api/state", host="evil.example.com")[0] == 403          # DNS rebinding


def test_initial_state_is_idle(base):
    code, state = call(base, "/api/state")
    assert code == 200 and state["status"] == "idle"


def test_scan_rejects_missing_or_empty_folder(base, tmp_path):
    assert call(base, "/api/scan", {"folder": "/does/not/exist"})[0] == 400
    assert call(base, "/api/scan", {"folder": str(tmp_path)})[0] == 400          # no ARW inside


def test_endpoints_need_results_first(base):
    assert call(base, "/api/results")[0] == 400
    assert call(base, "/api/export", {"mode": "beside"})[0] == 400
    assert call(base, "/api/label", {"stem": "DSC0001", "value": "closed"})[0] == 400


def test_label_input_is_validated(base):
    assert call(base, "/api/label", {"stem": "../x", "value": "closed"})[0] == 400
    assert call(base, "/api/label", {"stem": "ok", "value": "banana"})[0] == 400


def test_images_need_token_and_block_path_traversal(base):
    assert call(base, "/img/crops/x.jpg", token=False)[0] == 403
    assert call(base, f"/img/crops/..%2Fscores.json?t={app.TOKEN}", token=False)[0] == 404


def test_native_dialog_unavailable_without_window(base):
    code, r = call(base, "/api/pick", {})
    assert code == 400 and r["error"] == "no_native"                             # UI falls back to a typed path
