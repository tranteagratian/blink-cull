# Blink Cull

A **Lightroom Classic plugin** that finds the photos with closed eyes in your Sony ARW files, in minutes, on your own computer.

Select photos in Lightroom, run one menu command, and the suspicious ones come back with a **red or yellow colour label, a keyword and a
collection** you can review right in the grid. It is a **sorting aid for culling**, not a replacement for looking:
see [how good it is](#how-good-is-it) before you rely on it.

> Status: early / experimental. The detection was built and measured on one wedding gallery (1363 Sony a7 IV photos) labelled by one person.
> The Lightroom-side code (labels, keywords, collections) has had little real-world testing, so please report what you see.

- **Private**: nothing leaves your computer. No cloud, no account, no network access.
- **Read-only**: your RAW files are never modified or deleted. The plugin never rejects or deletes photos either; it only adds labels, keywords and collections.
- **Fast**: about 0.3 s per photo on an Apple-silicon Mac (~6 minutes for 1,400 photos), with a progress bar and a Cancel button.
- **No separate app to open**: the analysis engine ships inside the plugin folder.

## How good is it?

Measured on one wedding gallery: 1363 photos, all 594 flagged photos labelled by the photographer, recall estimated
from a random sample of 80 unflagged photos. In that gallery about **1 photo in 3** had someone with eyes closed
(the photographer counted partial blinks and downward glances too).

| Show me photos with score ≥ | Photos to review | Truly closed | Precision | Estimated recall (90% interval) | vs. picking at random |
|---|---|---|---|---|---|
| 0.55 | 97 | 93 | 96% | ~21% (18–23%) | 2.9× |
| **0.45** (red) | 197 | 171 | **87%** | ~38% (33–42%) | 2.6× |
| 0.35 | 353 | 258 | 73% | ~57% (50–63%) | 2.2× |
| **0.25** (red + yellow) | 594 | 336 | 57% | **~74% (65–82%)** | 1.7× |

Read this honestly: red is right 87% of the time, but even reviewing every flagged photo you find about three quarters of the
problems. Profile faces, hugging couples and people looking down are weak spots. Method and failure analysis:
[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).

## Install

Requires Lightroom Classic and, for now, an Apple-silicon Mac (the engine has only been built there).

1. Get the plugin folder `BlinkCull.lrdevplugin` **with the engine inside it** (`bin/BlinkCullEngine/`). Either download a release zip
   (when one is published) or build it yourself:
   ```bash
   git clone https://github.com/tranteagratian/blink-cull && cd blink-cull
   ./scripts/build_engine.sh        # needs Python 3.12 and uv; takes a couple of minutes
   ```
2. Lightroom Classic ▸ *File ▸ Plug-in Manager… ▸ Add* ▸ choose `lightroom/BlinkCull.lrdevplugin`.
3. If macOS blocks the engine (it is unsigned) run `xattr -dr com.apple.quarantine lightroom/BlinkCull.lrdevplugin` once.

## Use

In the Library module select photos (a folder, then Cmd+A) ▸ *Library ▸ Plug-in Extras ▸ Find photos with closed eyes (selected photos)*.
Choose the thresholds (default 0.45 red, 0.25 yellow) and the options, then *Analyze*. You get a summary, red/yellow labels, the keywords
`blinkcull-closed` / `blinkcull-check`, and two collections to review in the grid. The dialog is available in English and Romanian.

Options: leave photos that already carry a colour label alone (on by default), add keywords, create collections.
Only ARW files are analysed; anything else in the selection is counted and skipped.

## Limitations

- **Weak spots**: profile faces, couples hugging, people looking down; blurry or very dark faces are skipped, not judged.
- **One gallery, one labeller.** The thresholds (0.45 / 0.25) were chosen on it and may need adjusting for other events, cameras and light.
- **Sony ARW only**; **Lightroom Classic only** (the cloud-based Lightroom has no plug-in SDK); engine built for **macOS Apple silicon** only so far.
- The colour label is set through `photo:setRawMetadata("label", "Red"/"Yellow")`. If your colour-label set uses other names it may not apply;
  the plugin counts failures and tells you, and still adds keywords and collections.

## Privacy and safety

The engine reads each ARW's embedded preview and writes one line per photo to a temp file. Nothing else. It makes no network calls while scanning.
Labels, keywords and collections are written by Lightroom itself through its SDK, as one undoable step.

**Never commit or attach real photos of people, RAW files, sidecars or label files to issues or pull requests.** The repository ignores them by design.

## Repository layout

| Path | What it is |
|---|---|
| `lightroom/BlinkCull.lrdevplugin/` | the plugin (Lua) |
| `engine.py` | the headless engine the plugin runs: `--scan-list`, `--folder`, `--selftest` |
| `blink.py` | the detection pipeline (preview → faces → blink scores) |
| `scripts/build_engine.sh` | builds the engine and installs it inside the plugin folder |
| `tests/` | tests for the engine's file handling and output format |
| `learning/` | the step-by-step scripts the project grew from, plus the failed experiments (Romanian comments) |
| `docs/HOW_IT_WORKS.md` | design, evaluation, what failed and why |

The engine also works on its own: `uv run python engine.py --folder /path/to/arw --out scores.tsv`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Romanian readers: [README.ro.md](README.ro.md).

## License

Apache-2.0, see [LICENSE](LICENSE). Third-party components and models keep their own licences, see [NOTICE](NOTICE).
