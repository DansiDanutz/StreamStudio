# Motion cards (HyperFrames)

Site cards are never still images: each is a HyperFrames composition (HTML + GSAP, rendered to MP4) in which the
real site is browsed — a browser bar with the URL, the page scrolling and zooming, a cursor that moves and
clicks, neon highlight rings with a spotlight, typed form input, and explanation callouts timed to Dan's words.

1. Capture the sites (Claude in Chrome, `zoom` with `scale: 1, save_to_disk: true`, a 16:9 region around the content),
   scrolling in steps with sticky/fixed elements neutralised. Never capture private dashboards, balances or P&L.
2. `stitch.py`: stitch the scroll captures into tall pages (`pages/`), from the known scroll offsets.
3. `cards.py`: one storyboard per card. Times come from HeyGen's captions (see `../cuts.py`), coordinates are page pixels.
   Building blocks (`build.py` `Comp`): `page`, `show`, `url`, `cam` (scroll / focus+zoom), `ring`, `cursor` (moves, clicks),
   `typed`, `call` (title + line), `chips`.
4. `HYPERFRAMES_BROWSER_PATH=<chromium> python build.py [seg..] [--draft]` → `out/segNN.mp4` (1400x788, 25 fps).
   Needs `npm i hyperframes gsap` next to build.py.
5. Copy the MP4s to `WORKDIR/cards/` and set `"video": "segNN.mp4"` on the plan's card segments; `render.py` plays them
   inside the neon card (frame-accurate to the segment).
