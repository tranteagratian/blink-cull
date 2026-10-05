# Lightroom Classic plugin (early)

Runs Blink Cull on the photos you select and writes **colour labels, keywords and collections straight into the Lightroom catalog**.
It never deletes or rejects photos and never touches your RAW files.

## Install

1. Download the release zip (it follows `INSTALL.txt`), or build the engine yourself with `./scripts/build_engine.sh`: the plugin folder `BlinkCull.lrdevplugin` must contain it in `bin/BlinkCullEngine/`.
2. Lightroom Classic ▸ *File ▸ Plug-in Manager… ▸ Add* ▸ choose the folder `BlinkCull.lrdevplugin`.
3. If macOS blocks the unsigned engine: `xattr -dr com.apple.quarantine BlinkCull.lrdevplugin` once.

The plugin finds the engine in its own `bin/` folder. If it is missing it falls back to a path saved in the dialog, then to `~/blink-cull/dist/BlinkCullEngine/`.

## Use

Library module ▸ select photos ▸ *Library ▸ Plug-in Extras ▸ Find photos with closed eyes (selected photos)*. Pick thresholds
(0.45 red, 0.25 yellow), the options and the language (English / Română), then *Analyze*.

You get red/yellow labels, the keywords `blinkcull-closed` / `blinkcull-check`, and two collections ("Blink Cull <date> - red / yellow") to review in the grid.
Options: leave photos that already carry a colour label alone (default on), add keywords, create collections. The whole change is one undoable step.

## Why write into the catalog instead of XMP sidecars?

For photos already in a catalog, reading sidecar metadata back (*Metadata ▸ Read Metadata from Files*) can overwrite ratings and keywords with what
the sidecar holds. Writing through the Lightroom SDK avoids that.

## Known limits

- ARW only; other files in the selection are counted and skipped.
- Confirmed working on the author's Lightroom Classic setup (labels, keywords and collections); other versions and platforms are untested.
- The colour label uses `photo:setRawMetadata("label", "Red"/"Yellow")`. If your label set uses other names the call may not apply; the plugin counts
  failures and tells you, and still adds keywords and collections.
- Lightroom Classic only (the cloud-based Lightroom has no plug-in SDK). Scores are not cached: changing a threshold means analysing again.
