# Blink Cull

A **Lightroom Classic plugin** that finds the photos with closed eyes in your Sony ARW files, in minutes, on your own computer.

Select photos in Lightroom, run one menu command, and the suspicious ones come back with a **red or yellow colour label, a keyword and a
collection** you can review right in the grid. It is a **sorting aid for culling**, not a replacement for looking:
see [how good it is](#how-good-is-it) before you rely on it.

> Status: early. The detection was built and measured on one wedding gallery (1363 Sony a7 IV photos) labelled by one person.
> The plugin has been used by its author in Lightroom Classic, where labels, keywords and collections were applied correctly. Other Lightroom
> versions, label sets and platforms are untested, so please report what you see.

- **Private**: nothing leaves your computer. No cloud, no account, no network access.
- **Read-only**: your RAW files are never modified or deleted. The plugin never rejects or deletes photos either; it only adds labels, keywords and collections.
- **Fast**: about 0.3 s per photo on an Apple-silicon Mac (~6 minutes for 1,400 photos), with a progress bar and a Cancel button.
- **Nothing else to install**: the analysis engine ships inside the plugin folder.

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

Requires Lightroom Classic, a Mac with **Apple silicon (M1 or newer)** and **macOS 14.5 or newer**.

1. Download `BlinkCull-0.2.0-macos-arm64.zip` from the [latest release](https://github.com/tranteagratian/blink-cull/releases/latest) and unzip it.
2. Follow `INSTALL.txt` inside (three short steps: put the `BlinkCull.lrdevplugin` folder somewhere permanent, run one `xattr` command, then
   *Lightroom ▸ File ▸ Plug-in Manager… ▸ Add*). The engine is already inside the plugin folder; there is no separate app to install.

The program is **not signed or notarized** (that needs a paid Apple Developer account), so macOS may block it; the `xattr` step in `INSTALL.txt` handles that.

**Build it yourself instead:**
```bash
git clone https://github.com/tranteagratian/blink-cull && cd blink-cull
./scripts/build_engine.sh        # needs uv; builds the engine into lightroom/BlinkCull.lrdevplugin/bin (a couple of minutes)
./scripts/make_release.sh        # optional: assemble the same zip as the release
```
Then add `lightroom/BlinkCull.lrdevplugin` in Lightroom's Plug-in Manager.

## Use

In the Library module select photos (a folder, then Cmd+A) ▸ *Library ▸ Plug-in Extras ▸ Find photos with closed eyes (selected photos)*.
Choose the thresholds (default 0.45 red, 0.25 yellow) and the options, then *Analyze*. You get a summary, red/yellow labels, the keywords
`blinkcull-closed` / `blinkcull-check`, and two collections to review in the grid. The dialog is available in English and Romanian.

Options: leave photos that already carry a colour label alone (on by default), add keywords, create collections.
Only ARW files are analysed; anything else in the selection is counted and skipped.

## Limitations

- **Weak spots**: profile faces, couples hugging, people looking down; blurry or very dark faces are skipped, not judged.
- **One gallery, one labeller.** The thresholds (0.45 / 0.25) were chosen on it and may need adjusting for other events, cameras and light.
- **Sony ARW only**; **Lightroom Classic only** (the cloud-based Lightroom has no plug-in SDK); the engine is built for **Apple-silicon Macs on macOS 14.5+** only so far; Windows and Intel Macs are not supported yet.
- The colour label is set through `photo:setRawMetadata("label", "Red"/"Yellow")`. It worked on the author's setup; if your colour-label set uses
  other names it may not apply. The plugin counts failures and tells you, and still adds keywords and collections.

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
