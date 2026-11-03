# DansLab logo-reveal intro (HyperFrames)

## Overview

Ported 1:1 from the channel's existing intro (DansiDanutz/Claude-Youtube, `remotion/src/lib/danslab.tsx`
`DlLogoAnimated` + `SiteBg`, `shots/danslab-ep03/TIntro.tsx`): starfield, the red tile with the serif D and the
blinking gold cursor, ring pulse, sparks, shine sweep, then the title card (kicker, title, red→gold rule, tagline).

    python make_intro.py "DANSLAB" 'Build it. Show it. <em>Sell it.</em>' "Tagline"
    npx hyperframes render comps/intro -o out/intro.mp4 -f 30 -q delivery

Fonts: @fontsource Newsreader 500/600/500-italic, JetBrains Mono 500 (copied next to index.html).
Sound (from Claude-Youtube `media/library/sfx`, ElevenLabs-generated, owned): riser-soft 0.0 s, pop-reveal 0.57 s,
warm-shimmer 1.3 s, whoosh-soft 3.35 s, impact-deep-soft 4.0 s; mixed to −18 LUFS, fade out from 6.4 s.

`make_intro.py` is a one-shot generator: it builds the HyperFrames composition (HTML, CSS and a GSAP timeline)
as a single file. Rendering it to MP4 is a separate `npx hyperframes render` step, and the finished MP4 is what
`../../mix.py` puts in front of the episode.

## Interface

- `make_intro.py` (script, no importable functions besides `rnd`):
  - Positional arguments (`sys.argv[1..3]`): `KICKER` (default `DANSLAB`), `TITLE_HTML` (default
    `Build it. Show it. <em>Sell it.</em>`; inserted as raw HTML, `<em>` renders gold italic), `TAG` (tagline).
  - Timing constants: `FPS = 30`, `S0 = 0.5` (logo starts), `TITLE = 3.6` (title card starts), `DUR = 7.2`
    (composition length in seconds), `f(n)` converts a frame count to seconds.
  - `OUT`: `comps/intro/index.html` next to the script (`Path(__file__).parent / 'comps' / 'intro' / 'index.html'`).
  - `rnd(seed)`: deterministic pseudo-random in `[0, 1)` used for the 92 stars and 14 sparks, so every run
    produces the same layout.
- Printed on success: `ok <OUT>` and the SFX cue times (`riser`, `pop`, `shimmer`, `whoosh`, `impact`) derived
  from `S0` and `TITLE`; these are the numbers quoted in the Sound line above.

## Invariants

- The composition is `1920x1080` with `data-duration="{DUR}"` on `#root` and a paused GSAP timeline exported as
  `window.__timelines = {root: tl}` (`make_intro.py:html`); HyperFrames drives the timeline from there.
- The cursor blink is a `tl.set` every 14 frames from `S0 + f(22)` until `TITLE` (`make_intro.py` while loop), and
  `#root` fades out over the last 0.6 s (`tl.to('#root', {opacity: 0, duration: 0.6}, DUR - 0.6)`).
- The generated HTML references `gsap.min.js` and four `.woff2` font files by relative path; the script does not
  copy them. They must be placed next to `index.html` by hand before rendering (see Fonts above).
- Star and spark positions depend only on `rnd(seed)`, never on time or the environment.

## Side Effects

- Writes `comps/intro/index.html` relative to the script, overwriting any previous file
  (`make_intro.py:OUT.write_text`). The parent directory must already exist; the script does not create it.
- Prints the output path and cue times to stdout. No network, no subprocesses.

## Verification

- No automated test covers this directory; the repository-wide `make test` does not run anything under
  `tools/compose`.
- Manual check: run `python make_intro.py` and confirm `comps/intro/index.html` is written and the printed cue
  times match the Sound line in this file, then render with `npx hyperframes render comps/intro -o out/intro.mp4 -f 30 -q delivery`.
