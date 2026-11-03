# Motion cards (HyperFrames)

## Overview

Site cards are never still images: each is a HyperFrames composition (HTML + GSAP, rendered to MP4) in which the
real site is browsed — a browser bar with the URL, the page scrolling and zooming, a cursor that moves and
clicks, neon highlight rings with a spotlight, typed form input, and explanation callouts timed to Dan's words.

These storyboards are retained to compare existing Episode 1 work with the episode factory.
They use prepared page images and the original timing data. New captures are managed by the
episode worker and can be reviewed through the Episode page.

`cards_v2.py` is the Episode 1 v2 storyboard set: one card per group of consecutive scenes, with beats placed on
Dan's words through `T(off, scene, phrase)`. Select it with `CARDS=cards_v2` (see Interface).

Subdirectory: [intro](./intro/README.md) — the DansLab logo-reveal intro composition, built by its own script and
rendered the same way.

## Interface

### `build.py` — composition builder and renderer

- Constants: `W, H, BAR = 1400, 788, 44`; `VH = H - BAR` (viewport height below the browser bar); `CSS`
  (the card stylesheet, Inter font); `CURSOR` and `LOCK` (inline SVGs); `HERE` (this directory).
- `esc(s)`: HTML-escape `&`, `<`, `>`.
- `class Comp(cid, dur, pages_dir)`: one composition. Pages, overlays and GSAP tween strings accumulate on the
  instance; `write()` serialises them.
  - `page(src, dx=0) -> k`: register a page image from `pages_dir`; `dx` is a horizontal offset subtracted from
    every page-space coordinate for that page. Returns the page index.
  - `cam(k, t, d=1.0, focus=None, y=None, z=1.0, ease='power2.inOut')`: move the camera of page `k` at time `t`
    over `d` seconds, either to frame a `focus` rect `(x, y, w, h)` at zoom `z` or to scroll offset `y`; `d <= 0` is an
    instant `tl.set`.
  - `show(k, t, d=0.4, slide=True)`: bring page `k` in at `t`, fading the other pages out.
  - `url(t, text, typed=False)`: set the address bar text (host in bold); `typed=True` animates its width.
  - `ring(k, t, end, rect, pad=8, spot=True, r=14)`: neon highlight ring in page space, with an optional spotlight mask.
  - `typed(k, t, rect, text, d=None, size=15)`: typed text with a caret inside a form field rect.
  - `cursor(k, moves) -> id`: `moves = [(t, x, y, click)]`; the first entry places the cursor, later ones move it;
    a click adds a scale dip and a ripple. `cursor_hide(id, t)` fades it out.
  - `call(t, end, title, sub=None, top=False)`: explanation callout in card space (bottom-left, or top-right with `top=True`).
  - `chips(items, end)`: `items = [(t, text)]`; pills appear one by one and all leave at `end`.
  - `overlay(t, end, html, style, cls='ov', pop=True) -> id`: free-placed element (QR, scorecard, counter).
  - `reveal_rows(oid, times)`: reveal `.row` children of an overlay one by one.
  - `counter(oid, t, d, to, fmt, steps=24)`: count `.num` inside an overlay up to `to` using `tl.call` steps.
  - `navigate(k, t, url) -> t_ready`: blank flash, retyped address, loading bar, then page `k`; returns the time the
    page is fully in.
  - `write(out_dir)`: write `index.html` and copy its assets (see Side Effects).
  - `files`: list of extra asset names (relative to `pages_dir`) copied by `write()`; set by storyboards such as
    `cards_v2.g10` (`c.files = ['qr.png']`).
- `render(out_dir, mp4, draft=False) -> bool`: run `npx hyperframes render` on a written composition; returns
  `True` on exit code 0 and prints the last three lines of the renderer's output.
- Command line (`__main__`): `python build.py [cid ...] [--draft]`. The storyboard module is chosen by the `CARDS`
  environment variable (default `cards`); it must expose a `CARDS` dict of `cid -> function(Comp) -> Comp`. With no
  `cid` arguments every card in the dict is built.

### `cards.py` — Episode 1 storyboards

- `seg04`, `seg07`, `seg08`, `seg10`, `seg12`, `seg15`, `seg16`: each takes the `Comp` class and returns a built
  composition whose duration is the segment length taken from HeyGen's captions.
- `CARDS`: dict of function name to function. `P`: the `pages/` directory next to this file.

### `cards_v2.py` — Episode 1 v2 storyboards

- Module-level data loaded at import: `SC` (the episode script's `scenes` list, from `EP_SCRIPT`, default
  `../ep1-v2.json`), `DUR` (scene number to measured seconds, from `EP_DURATIONS`, default `../ep1v2/durations.json`),
  `TEXT` (scene number to voice text).
- `group(scenes, lead=0.0) -> (off, dur)`: offsets of each scene inside a card group and the group's total length.
- `T(off, s, phrase) -> seconds`: time of `phrase` inside scene `s`, proportional to its position in the scene's text.
- `g06`, `g10`, `g15`, `g21`, `g27`: one card per scene group; `CARDS` dict as in `cards.py`.


## Invariants

- Every composition is `W x H = 1400 x 788` with a 44 px browser bar; `#root` carries `data-duration` equal to the
  `Comp` duration, and the timeline is paused and exported as `window.__timelines.root` (`build.py:Comp.write`).
  `render()` renders at 25 fps (`'-f', '25'`), which is the frame rate `../render.py:CardVideo` reads them at.
- `Comp._cam` clamps the camera so the page never shows past its own edges: `x` is clamped to
  `[W - page_w * S, 0]` and `y` to `[VH - page_h * S, 0]` (or 0 when the page is shorter than the viewport).
- Page-space coordinates passed to `ring`, `typed` and `cursor` have the page's `dx` subtracted
  (`build.py:Comp.ring`, `Comp.typed`, `Comp.cursor`); `focus` rects passed to `cam` likewise.
- `cursor()` requires at least one move; the first entry only places the cursor (`build.py:Comp.cursor`).
- `cards_v2.T` asserts that `phrase` occurs in the scene's voice text (`assert i >= 0, (s, phrase)`); a storyboard
  with a misspelled phrase fails at build time.
- `build.render` sets `HYPERFRAMES_BROWSER_PATH` to the Chromium path hard-coded in the function
  (`/opt/pw-browsers/chromium-1243/chrome-linux64/chrome`) after merging `os.environ`, so that value overrides any
  `HYPERFRAMES_BROWSER_PATH` set in the shell.
- `Comp.write` copies `node_modules/gsap/dist/gsap.min.js` from this directory; `npm i hyperframes gsap` must have
  been run here first or `write()` raises.

## Side Effects

- `Comp.write(out_dir)`: creates `out_dir` (`comps/<cid>/` when run from `__main__`), copies every registered page
  image and every name in `Comp.files` from `pages_dir`, copies `gsap.min.js`, and writes `index.html`
  (`build.py:Comp.write`). Existing files are overwritten.
- `render()`: runs `npx hyperframes render <out_dir> -o <mp4> -f 25 -q draft|delivery --video-frame-format png -w 4`
  as a subprocess with `cwd=HERE`; writes `out/<cid>.mp4` when called from `__main__` (`build.py:render`).
- `cards_v2.py`: reads `EP_SCRIPT` and `EP_DURATIONS` JSON files at import time (`json.load(open(...))`); importing
  it with those files missing raises.
- `../mix.py` reads `comps/<card>/index.html` written here with regular expressions to find tab-change and counter
  cues (`mix.py:comp_times`), so the tween strings emitted by `Comp.navigate` (`tl.to('.blank',{opacity:1,...})`)
  and `Comp.counter` (`textContent='13.5K'`) are part of this directory's output contract.

## Verification

- No automated test covers this directory; the repository-wide `make test` does not run anything under
  `tools/compose`.
- Manual check: `python build.py seg04 --draft` (or `CARDS=cards_v2 EP_SCRIPT=... EP_DURATIONS=... python build.py g06 --draft`)
  must print `seg04.mp4 OK` and leave `comps/seg04/index.html` and `out/seg04.mp4`.
