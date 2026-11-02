# render

## Overview

Offline rendering. `lipsync.py` is the server-side copy of the lip-sync guard
(mirror of `web/src/director/types.ts`) and the compositor for the small
presenter card. `opener.py` is a frame-exact render of the reusable opener
(plate, Dan cut-out, desk layer, table objects, titles, synthesized sound).
`preview.py` records the web app's render mode with Playwright and re-encodes
it with ffmpeg. `opener.py` and `preview.py` are command-line scripts;
`lipsync.py` is a library used by them and by tests.

## Interface

### `lipsync.py`

- `Voice = Literal["clip", "narration"]`, `Shape = Literal["circle", "portrait"]`, `MAX_UNSYNCED_AREA = 0.06`
- `lips_match(clip, voice=None) -> bool`
- `guard_cue(cue, clip, voice=None) -> str`
- `pip_rect(width, height, shape="circle") -> (x, y, w, h)`
- `pip_card(face, frame_size, shape="circle", face_y=0.36) -> (RGBA card, (x, y))`
- `composite_pip(frame, face, shape="circle") -> Image`

### `opener.py`

- Constants: `REPO`, `A` (`<repo>/assets`), `W, H = 1920, 1080`, `FONT_DIR`, `SPEECH_END = 9.4`, `TOOLS`, `SLOTS`, `T0`, `STEP`, `ARRIVE_RATE`, `LEAVE_RATE`, `HOLD`, `GLIDE`, `CLAW_T`, `CLAW_LEAVE`, `FINALE`, `END`, `HERO`, `SLOT_Y`, `SLOT_W`, `SEAT_SCALE`, `HANDS_Y`, `SEAT_X`, `HANDS_IN_CLIP`, `SR = 48000`
- `ease(t)`, `ease_io(t)`, `Clip(webm, cache)` with `frame(i)`, `dan_frame(i)`, `dan_index(t, fps)`, `font(name, size)`, `title_layer(title, line, alpha, label=None)`, `place(...)`, `tool_state(i, t)`, `render_frame(t, fps, clips, plate, desk)`, `synth_audio(path)`, `main()`
- CLI: `OUT.mp4 [--fps 25] [--seconds N] [--stills t1,t2,…]`

### `preview.py`

- `record(url, out_dir, w, h, max_s) -> Path`, `encode(webm, out, audio, lead_in_s=0.8)`, `main()`
- CLI: `OUT.mp4 [--url http://127.0.0.1:8787] [--audio clip.mp4] [--width 1920 --height 1080] [--max-seconds 120]`

## Invariants

- `[lipsync.py:lips_match]` is true only when a clip is set and `voice != "narration"`. `[lipsync.py:guard_cue]` leaves the cue unchanged when lips match; otherwise `avatar` becomes `pip` and `duo` becomes `content`, so the face is never full-frame or the big card of `duo` with any other voice. `[lipsync.py:MAX_UNSYNCED_AREA]` is the largest share of the frame (0.06) the face may take when lips do not match.
- `[lipsync.py:pip_rect]` The small card is 15 % of the width in landscape and 30 % in portrait, bottom-left, square for `circle` and 4:3 for `portrait`; `[lipsync.py:pip_card]` applies an elliptical or rounded-rectangle alpha mask.
- `[opener.py:dan_index]` Dan's real clip frames play only for `t < SPEECH_END`; afterwards a closed-mouth loop over frames 234–243 with a blink (243–247) every 5.2 s is used.
- `[opener.py]` `F_TITLE`, `F_LINE`, `F_LABEL`, `F_FINAL` are loaded at import from `FONT_DIR` (`/usr/share/fonts/opentype/inter`); importing the module fails when those font files are absent.
- `[opener.py:main]` Audio is normalised with `loudnorm=I=-14:TP=-1.5:LRA=11`; video is `libx264` crf 17 at `--fps`.
- `[preview.py:record]` Waits for `.base` and for `window.__director.getState().playing` to become true (15 s timeout), then stops when it turns false or after `max_s`.

## Side Effects

- `[opener.py:Clip.__init__]` decodes object WebMs with `ffmpeg` into `tempfile.gettempdir()/opener-cache/<id>/f*.png` and reuses them on later runs. `[opener.py:dan_frame]` reads `<assets>/avatar/cutout/cache/dan-landscape-test/`. `[opener.py:synth_audio]` decodes `<assets>/avatar/dan-landscape-test.mp4` with `ffmpeg` and writes a WAV. `[opener.py:main]` runs `ffmpeg` twice (raw frames to video, then mux), writes `OUT.mp4` or still JPEGs, uses a `tempfile.mkdtemp(prefix="opener_")` directory that is removed afterwards, and prints progress.
- `[preview.py:record]` launches Playwright Chromium, navigates to `<url>/?render=1&autoplay=1`, and records a WebM into `out_dir`. `[preview.py:encode]` runs `ffmpeg`. `[preview.py:main]` creates and removes a `tempfile.mkdtemp(prefix="render_")` directory.
- `[lipsync.py]` has no side effects beyond allocating Pillow images.

## Verification

- Run: `cd server && .venv/bin/python -m pytest`
- Lint: `cd server && .venv/bin/ruff check src tests`
