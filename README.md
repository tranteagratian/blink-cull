# Blink Cull

Find the photos with closed eyes in a folder of Sony ARW files, in minutes, on your own computer.

Blink Cull reads the full-size JPEG that every ARW carries, finds the faces, measures how closed each person's eyes are
and shows you the suspicious photos first. It is a **sorting aid for culling**, not a replacement for looking:
see [how good it is](#how-good-is-it) before you rely on it.

> Status: early / experimental. Built and measured on one wedding gallery (1363 Sony a7 IV photos) and labelled by one person.

- **Private**: nothing leaves your computer. No cloud, no account.
- **Read-only**: your RAW files are never modified or deleted. Sidecar files are only written when you ask, and never next to your photos by default.
- **Fast**: about 0.3 s per photo on an Apple-silicon Mac (~6 minutes for 1,400 photos).
- Three ways to use it: a **desktop app**, a **Lightroom Classic plugin**, and a **command line**.

## How good is it?

Measured on one wedding gallery: 1363 photos, all 594 flagged photos labelled by the photographer, recall estimated
from a random sample of 80 unflagged photos. In that gallery about **1 photo in 3** had someone with eyes closed
(the photographer counted partial blinks and downward glances too).

| Show me photos with score ≥ | Photos to review | Truly closed | Precision | Estimated recall (90% interval) | vs. picking at random |
|---|---|---|---|---|---|
| 0.55 | 97 | 93 | 96% | ~21% (18–23%) | 2.9× |
| **0.45** (red group) | 197 | 171 | **87%** | ~38% (33–42%) | 2.6× |
| 0.35 | 353 | 258 | 73% | ~57% (50–63%) | 2.2× |
| **0.25** (red + yellow) | 594 | 336 | 57% | **~74% (65–82%)** | 1.7× |

Read this honestly: the red group is right 87% of the time, but even reviewing all 594 flagged photos you find about
three quarters of the problems. Profile faces, hugging couples and people looking down are weak spots. Details,
method and failure analysis: [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).

## Quick start (from source)

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/tranteagratian/blink-cull
cd blink-cull
uv sync
uv run python fetch_models.py          # downloads two small model files into ./models
uv run python app.py                   # the desktop app
```

In the app: choose a folder of ARW files → wait for the scan → review the red and yellow photos (click one to enlarge,
keys `1` closed / `2` fine, `←` `→` to move) → optionally export Lightroom labels.

### Command line

```bash
uv run python blinkcull.py /path/to/photos                      # scan and print a summary
uv run python blinkcull.py /path/to/photos --xmp-dir out/xmp    # also write Lightroom label sidecars (red / yellow)
uv run python blinkcull.py /path/to/photos --out out/scan --rebuild --check-min 0.2   # other thresholds, no rescan
```

### Lightroom Classic plugin (experimental)

Select photos → *Library ▸ Plug-in Extras ▸ Find photos with closed eyes*. Labels, keywords and collections are
written straight into the catalog, which also works for photos already in the catalog. See [lightroom/README.md](lightroom/README.md).

### Building the macOS app

See [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md#packaging). The unsigned app is blocked by Gatekeeper on other
people's Macs (right-click ▸ Open); proper distribution needs signing and notarization.

## Limitations

- **Weak spots**: profile faces, couples hugging, people looking down, blurry or very dark faces (skipped, not judged).
- **One gallery, one labeller.** The thresholds (0.45 / 0.25) were chosen on it and may need adjusting for other events, cameras and light.
- **Sony ARW only** for now. Other RAW formats are readable by the underlying library but untested.
- **UI text is in Romanian** (the author's language); English strings are a welcome contribution.
- Packaged app: macOS (Apple silicon) only. Windows and Linux from source are untested.

## Privacy and safety

Photos are only read. The desktop app serves its UI from a local server bound to `127.0.0.1`; every request needs a
random per-run token and a matching `Host` header, so web pages in your browser cannot talk to it. Exporting `.xmp`
files refuses to write into your photo folder unless you explicitly choose "next to the photos", and even then never
overwrites an existing `.xmp`. These rules are covered by tests (`uv run --group test pytest`).

**Never commit or attach real photos of people to issues or pull requests.** The repository ignores RAW files,
sidecars and label files by design.

## Repository layout

| Path | What it is |
|---|---|
| `blink.py` | the detection pipeline (preview → faces → blink scores) |
| `scanner.py` | folder scan, verdicts, XMP export |
| `app.py`, `ui/` | desktop app (pywebview window + local server + single-file UI) |
| `blinkcull.py` | command line |
| `lightroom/` | Lightroom Classic plugin (Lua) |
| `learning/` | the step-by-step scripts the project grew from, plus the failed experiments (Romanian comments) |
| `tests/` | unit and security tests |
| `docs/HOW_IT_WORKS.md` | design, evaluation, what failed and why |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Romanian readers: [README.ro.md](README.ro.md).

## License

Apache-2.0, see [LICENSE](LICENSE). Third-party components and models keep their own licences, see [NOTICE](NOTICE).
