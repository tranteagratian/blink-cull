# Contributing

Thanks for looking. This is an early project; small, concrete contributions are the most useful.

## Set up

```bash
uv sync --group test
uv run python fetch_models.py
uv run --group test pytest                      # 9 tests, no photos or models needed
uv run python engine.py --folder /path/to/arw   # score a folder from the command line
./scripts/build_engine.sh                       # build the engine into the plugin folder
```

## Where help is most welcome

1. **Test the plugin in real catalogs** (different Lightroom Classic versions, label sets, localised UIs) and report exactly what happens.
   The colour-label call is the least certain part.
2. **A Windows build.** The engine has only been built on macOS (Apple silicon); the plugin has Windows branches (`WIN_ENV`) that are untested.
3. **Other RAW formats** (CR3, NEF, RAF…). `rawpy` can read their previews; the orientation handling in `blink.load_preview` and the plugin's `.arw` filter need checking.
4. **Evaluation on other galleries.** Do the thresholds (0.45 / 0.25) hold on your events? Open an issue with *numbers only*.
5. **More dialog languages.** All texts are in one `STRINGS` table in `lightroom/BlinkCull.lrdevplugin/FindBlinks.lua`; add a block.
6. **A score cache**, so changing a threshold does not need a new analysis.
7. **Ideas from [docs/HOW_IT_WORKS.md §7](docs/HOW_IT_WORKS.md)**: a three-state label set, profile faces, burst grouping.

## Rules

- **Never commit or attach photos of real people, RAW files, sidecars or label files** (`.gitignore` blocks them on purpose). Describe a problem with scores and file *counts*, not images. If you need a picture, use one of yourself.
- Keep the safety guarantees: RAW files are read-only; the plugin never deletes or rejects photos.
- If you change anything on the path from the RAW file to the score, say how you re-measured. Earlier numbers in this project were invalidated once by a rotation bug.
- Keep it local: no network calls at scan time, no telemetry.

By contributing you agree your contribution is licensed under Apache-2.0.
