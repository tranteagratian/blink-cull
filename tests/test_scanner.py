"""Tests for the pure logic: verdict thresholds, folder listing and the XMP export safety rules.
No photos or model files are needed."""
import xml.etree.ElementTree as ET

import pytest

import scanner

NS = {"xmp": "http://ns.adobe.com/xap/1.0/", "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#"}


def photo(stem, score):
    return {"stem": stem, "photo": f"{stem}.ARW", "score": score}


def test_verdict_boundaries():
    assert scanner.verdict(photo("a", None)) == "ok"          # no judged face
    assert scanner.verdict(photo("a", 0.45)) == "inchis"       # >= closed_min
    assert scanner.verdict(photo("a", 0.449)) == "verifica"
    assert scanner.verdict(photo("a", 0.25)) == "verifica"     # >= check_min
    assert scanner.verdict(photo("a", 0.249)) == "ok"


def test_verdict_custom_thresholds():
    assert scanner.verdict(photo("a", 0.30), closed_min=0.30, check_min=0.10) == "inchis"
    assert scanner.verdict(photo("a", 0.12), closed_min=0.30, check_min=0.10) == "verifica"


def test_flagged_sorted_and_filtered():
    data = {"photos": [photo("low", 0.10), photo("mid", 0.30), photo("high", 0.80), photo("none", None)]}
    out = scanner.flagged(data)
    assert [p["stem"] for p in out] == ["high", "mid"]         # most suspicious first, "ok" photos dropped
    assert [p["verdict"] for p in out] == ["inchis", "verifica"]


def test_list_arw_counts_empty_and_ignores_hidden(tmp_path):
    (tmp_path / "A.ARW").write_bytes(b"x" * 10)
    (tmp_path / "b.arw").write_bytes(b"x" * 10)                # case-insensitive
    (tmp_path / "EMPTY.ARW").write_bytes(b"")                  # interrupted card copy
    (tmp_path / "._A.ARW").write_bytes(b"x" * 10)              # macOS resource-fork file, not a photo
    (tmp_path / "other.JPG").write_bytes(b"x" * 10)
    files, empty = scanner.list_arw(tmp_path)
    assert sorted(f.name for f in files) == ["A.ARW", "b.arw"]
    assert empty == 1


def test_write_xmp_valid_and_labelled(tmp_path):
    photos, dest = tmp_path / "photos", tmp_path / "xmp"
    photos.mkdir()
    res = scanner.write_xmp([{"stem": "r", "verdict": "inchis"}, {"stem": "y", "verdict": "verifica"}], dest, photos)
    assert res == {"written": 2, "skipped_existing": []}
    label = lambda stem: ET.parse(dest / f"{stem}.xmp").getroot().find(".//rdf:Description", NS).get(f"{{{NS['xmp']}}}Label")
    assert label("r") == "Red" and label("y") == "Yellow"


def test_write_xmp_refuses_destination_inside_photo_folder(tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    for dest in (photos, photos / "sub"):
        with pytest.raises(ValueError):
            scanner.write_xmp([{"stem": "r", "verdict": "inchis"}], dest, photos)
    assert not list(photos.rglob("*.xmp"))                      # nothing was written


def test_write_xmp_beside_never_overwrites_existing(tmp_path):
    photos = tmp_path / "photos"
    photos.mkdir()
    edited = photos / "r.xmp"
    edited.write_text("<existing-edits/>")                      # a sidecar that may hold the user's edits
    res = scanner.write_xmp([{"stem": "r", "verdict": "inchis"}, {"stem": "n", "verdict": "verifica"}], photos, photos, beside=True)
    assert res == {"written": 1, "skipped_existing": ["r"]}
    assert edited.read_text() == "<existing-edits/>"           # untouched
    assert (photos / "n.xmp").exists()


def test_write_xmp_separate_folder_can_be_refreshed(tmp_path):
    photos, dest = tmp_path / "photos", tmp_path / "xmp"
    photos.mkdir()
    scanner.write_xmp([{"stem": "r", "verdict": "verifica"}], dest, photos)
    scanner.write_xmp([{"stem": "r", "verdict": "inchis"}], dest, photos)    # threshold changed, label must follow
    assert "Red" in (dest / "r.xmp").read_text()
