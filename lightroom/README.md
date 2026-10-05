# Lightroom Classic plugin (experimental)

Runs Blink Cull on the photos you select and writes **colour labels, keywords and collections straight into the
Lightroom catalog**. It never deletes or rejects photos and never touches your RAW files.

## Install

1. Install and build the Blink Cull app (see the main README); the plugin uses it as a headless engine.
2. Lightroom Classic ▸ *File ▸ Plug-in Manager… ▸ Add* ▸ choose the folder `BlinkCull.lrdevplugin`.
   The engine is looked up in `/Applications`, `~/Applications` and `~/blink-cull/dist`; otherwise type its path in the dialog.

## Use

Select photos (or a folder, then Cmd+A) in the Library module ▸ *Library ▸ Plug-in Extras ▸ Find photos with closed eyes*.
Choose thresholds (default 0.45 red, 0.25 yellow), then *Analyse*. When done you get a summary, red/yellow labels, the keywords
`blinkcull-inchis` / `blinkcull-verifica`, and two new collections to review in the grid.

Options: leave photos that already carry a colour label alone (default on), add keywords, create collections.

## Why not just write XMP files?

For photos already in a catalog, reading sidecar metadata back (*Metadata ▸ Read Metadata from Files*) can overwrite ratings and
keywords with what the sidecar holds. Writing through the Lightroom SDK avoids that.

## Known limits

- ARW only; other files in the selection are counted and skipped.
- Setting the colour label uses `photo:setRawMetadata("label", "Red"/"Yellow")`. If your label set uses other names the call may
  not apply; the plugin counts failures and tells you, and still adds keywords and collections.
- Lightroom Classic only (the cloud-based Lightroom has no plug-in SDK). Experimental: report what you see.
