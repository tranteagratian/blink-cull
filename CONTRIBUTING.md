# Contributing

Thanks for looking. This is an early project; small, concrete contributions are the most useful.

## Set up

```bash
uv sync --group test
uv run python fetch_models.py
uv run --group test pytest        # 17 tests, no photos or models needed
```

## Where help is most welcome

1. **English UI strings.** The app's UI text and its error messages are in Romanian (`ui/index.html`, user-facing strings in `app.py` and `scanner.py`). A small i18n layer plus English strings would open the app to everyone.
2. **A Windows build and test.** The packaged app is macOS-only; running from source on Windows/Linux is untested.
3. **Other RAW formats** (CR3, NEF, RAF…). `rawpy` can read their previews; the orientation handling in `blink.load_preview` and the Lightroom plugin's `.arw` filter need checking.
4. **Evaluation on other galleries.** Do the thresholds (0.45 / 0.25) hold on your events? Open an issue with *numbers only*.
5. **Ideas from [docs/HOW_IT_WORKS.md §7](docs/HOW_IT_WORKS.md)**: a three-state label set, profile faces, burst grouping.

## Rules

- **Never commit or attach photos of real people, RAW files, `.xmp` sidecars or label files** (`.gitignore` blocks them on purpose). Describe a problem with scores and file *counts*, not images. If you need a picture, use one of yourself.
- Keep the safety guarantees: RAW files are read-only; nothing is written next to the user's photos unless they explicitly ask. Tests in `tests/` cover this; add one when you touch it.
- If you change anything on the path from the RAW file to the score, say how you re-measured. Earlier numbers in this project were invalidated once by a rotation bug.
- Keep it local: no network calls at scan time, no telemetry.

By contributing you agree your contribution is licensed under Apache-2.0.
