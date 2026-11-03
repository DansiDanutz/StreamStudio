# tools/brand

## Overview

One-off generators for the brand assets under `assets/brand/`. They run by hand when the branding
changes; the episode factory (`server/src/streamstudio/episode`) only reads their output. Nothing
here is imported by `server/` or `web/`.

- `make_intro.py` builds the DansLab logo-reveal composition (HTML, CSS, a GSAP timeline) and
  renders it with HyperFrames at 25 fps into `assets/brand/danslab-intro.mp4`, keeping the intro's
  own sound track. Ported from `tools/compose/motion/intro/make_intro.py`.
- `update_manifest.py` recomputes the sha256 of every file listed in `assets/brand/manifest.json`.

## Interface

- `make_intro.py [KICKER] [TITLE_HTML] [TAG] [--no-render]` — positional texts as before
  (`DANSLAB`, `Build it. Show it. <em>Sell it.</em>`, the tagline); `--no-render` only writes the
  composition. [make_intro.py:args, RENDER]
  - Reads fonts from `assets/brand/fonts/` (`FONT_FILES`), writes `<data_dir>/cards/intro/index.html`
    (`OUT`; `STREAMSTUDIO_DATA_DIR`, default `~/StreamStudioData`), copies `gsap.min.js` from the
    workspace, renders `intro-video.mp4` beside it and muxes the existing intro's audio onto it.
    [make_intro.py:FONTS, OUT, render]
  - `ensure_workspace()` copies `server/src/streamstudio/episode/templates/{package.json,package-lock.json}`
    into `<data_dir>/cards/` and runs `npm ci` there when `node_modules/hyperframes` is missing.
    [make_intro.py:ensure_workspace]
  - `STREAMSTUDIO_HYPERFRAMES_BROWSER` (environment, optional) is passed to HyperFrames as
    `HYPERFRAMES_BROWSER_PATH`; otherwise HyperFrames finds a Chromium itself. [make_intro.py:render]
  - Constants: `RENDER_FPS = 25` (the render rate, matches `streamstudio.episode.FPS`), `FPS = 30`
    (only scales the ported GSAP frame timings), `S0 = 0.5`, `TITLE = 3.6`, `DUR = 7.2`.
  - Prints the output path and the SFX cue times (`riser 0.0, pop 0.57, shimmer 1.3, whoosh 3.35,
    impact 4.0`), then `rendered <mp4> 25 fps`.
- `update_manifest.py` — no arguments; `sha256(path)`, `main()`. [update_manifest.py:main]

## Invariants

- The composition is `1920x1080`, `data-fps="25"`, `data-duration="7.2"`, with a paused GSAP timeline
  exported as `window.__timelines = {root: tl}`. Star and spark positions depend only on `rnd(seed)`.
  [make_intro.py:html, rnd]
- The rendered intro is 180 frames at 25 fps with the original AAC track copied (`-c:a copy`), so
  `web/src/stage/Library.tsx`'s media item and the agent catalog keep working. [make_intro.py:render]
- `update_manifest.py` never adds or removes entries; a file not in the checkout gets `sha256: null`.
  [update_manifest.py:main]

## Side Effects

- `make_intro.py` writes under `<data_dir>/cards/` (workspace files, `node_modules` via `npm ci`,
  `intro/`), replaces `assets/brand/danslab-intro.mp4` through a temp file and rename, and runs
  `npm`, `npx hyperframes render` (launches Chromium) and `ffmpeg` as subprocesses.
- `update_manifest.py` rewrites `assets/brand/manifest.json`.

## Verification

- No automated test; the repository-wide `make test` does not run `tools/`.
- Manual: `python tools/brand/make_intro.py`, then `ffprobe assets/brand/danslab-intro.mp4` shows
  `r_frame_rate=25/1`, `nb_frames=180`, an `aac` stream; `python tools/brand/update_manifest.py`
  prints how many listed files are present.
