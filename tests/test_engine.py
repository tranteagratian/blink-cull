"""Tests for the engine's file handling and output format. They need no photos and no model files:
missing, empty and corrupt files are handled before any model is loaded."""
import io
import sys

import pytest

import engine


def rows(buf):
    return [line.split("\t") for line in buf.getvalue().splitlines()]


def test_missing_and_empty_files(tmp_path):
    empty = tmp_path / "empty.ARW"
    empty.write_bytes(b"")
    buf = io.StringIO()
    n = engine.run([str(tmp_path / "nope.ARW"), str(empty)], buf)
    assert n == 2
    assert [r[1:] for r in rows(buf)] == [["", "0", "missing"], ["", "0", "missing"]]


def test_corrupt_file_is_an_error_not_a_crash(tmp_path, capsys):
    junk = tmp_path / "junk.ARW"
    junk.write_bytes(b"this is not a raw file" * 100)
    buf = io.StringIO()
    engine.run([str(junk)], buf)
    assert rows(buf)[0][1:] == ["", "0", "error"]
    assert "junk.ARW" in capsys.readouterr().err         # the reason goes to stderr, for debugging


def test_one_bad_photo_does_not_stop_the_rest(tmp_path):
    junk = tmp_path / "junk.ARW"
    junk.write_bytes(b"x" * 500)
    buf = io.StringIO()
    engine.run([str(junk), str(tmp_path / "nope.ARW"), str(junk)], buf)
    assert [r[3] for r in rows(buf)] == ["error", "missing", "error"]


def test_output_is_tab_separated_with_four_columns(tmp_path):
    buf = io.StringIO()
    engine.run([str(tmp_path / "a b/c d.ARW")], buf)       # spaces in the path are fine
    (row,) = rows(buf)
    assert len(row) == 4 and row[0].endswith("c d.ARW")


def test_progress_file_reports_done_and_total(tmp_path):
    prog = tmp_path / "progress.txt"
    engine.run([str(tmp_path / "1.ARW"), str(tmp_path / "2.ARW"), str(tmp_path / "3.ARW")], io.StringIO(), progress=prog)
    assert prog.read_text() == "3 3"


def test_cancel_file_stops_cleanly(tmp_path):
    cancel = tmp_path / "cancel.flag"
    cancel.write_text("1")
    buf = io.StringIO()
    done = engine.run([str(tmp_path / "1.ARW"), str(tmp_path / "2.ARW")], buf, cancel=cancel)
    assert done == 0 and buf.getvalue() == ""            # nothing processed, nothing written


def test_list_arw_ignores_hidden_empty_and_other_files(tmp_path):
    (tmp_path / "A.ARW").write_bytes(b"x")
    (tmp_path / "b.arw").write_bytes(b"x")               # extension is case-insensitive
    (tmp_path / "empty.ARW").write_bytes(b"")             # interrupted card copy
    (tmp_path / "._A.ARW").write_bytes(b"x")              # macOS resource fork, not a photo
    (tmp_path / "c.JPG").write_bytes(b"x")
    assert [p.name for p in engine.list_arw(tmp_path)] == ["A.ARW", "b.arw"]


def test_cli_scan_list_roundtrip(tmp_path):
    listing, out = tmp_path / "list.txt", tmp_path / "out.tsv"
    listing.write_text(f"{tmp_path / 'x.ARW'}\n\n{tmp_path / 'y.ARW'}\n", encoding="utf-8")   # blank lines are ignored
    assert engine.main(["--scan-list", str(listing), "--out", str(out)]) == 0
    assert [r[3] for r in (line.split("\t") for line in out.read_text().splitlines())] == ["missing", "missing"]


def test_cli_requires_exactly_one_source():
    with pytest.raises(SystemExit):
        engine.main(["--out", "x.tsv"])
