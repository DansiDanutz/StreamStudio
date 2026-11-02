# objects

## Overview

`dissolve.py` is a standalone script that renders the particle dissolve of a
table object: a still (emblem over a lit disc, on black) breaks into particles
in its own colour, drifts up and fades, and the last second is black. Played in
reverse it is the object's arrival. It is deterministic and local (numpy,
scipy, Pillow, ffmpeg); no model calls. Run as
`python dissolve.py STILL.png OUT.mp4 [--seed N] [--particles 16000] [--preview SHEET.jpg]`.

## Interface

- Module constants: `ROOT` (default `/tmp/objects-dissolve`), `FPS = 30`, `DURATION = 8.0`, `BLACK_START = 7.0`, `SEED`, `PARTICLE_COUNT = 16000`, `SOURCE`, `OUTPUT`
- `smoothstep(x)`, `srgb_to_linear(a)`, `linear_to_srgb(a)`
- `Outro` — `__init__()` (reads `SOURCE`, detects disc row, stage, object bounds and tint), `init_particles()`, `particles(t)`, `frame(frame_index) -> ndarray`, `preview()`, `render()`
- `main()` — parses args and assigns the module globals `SOURCE`, `OUTPUT`, `SEED`, `PARTICLE_COUNT` (and `ROOT` when `--preview` is given) before constructing `Outro`

## Invariants

- `[dissolve.py:Outro.__init__]` Randomness comes only from `np.random.default_rng(SEED)`, so the same still and seed give the same frames. Odd image dimensions are padded by one black row/column so the H.264 4:2:0 output needs no resampling.
- `[dissolve.py:Outro.frame]` Frames at `t >= BLACK_START` are all black; frames before 0.54 s are the cleaned source unchanged.
- `[dissolve.py:Outro.render]` Refuses to overwrite an existing `OUTPUT` (`FileExistsError`); `[dissolve.py:main]` unlinks `OUTPUT` first, so the CLI always replaces it. The encode forces a key frame at `BLACK_START` and tags bt709.
- `[dissolve.py:Outro]` reads configuration from module globals, so `Outro()` must be constructed after `main` has set them (or after assigning them directly).

## Side Effects

- `[dissolve.py:Outro.render]` runs `ffmpeg` (reads raw frames on stdin) and `ffprobe` as subprocesses, writes `OUTPUT`, `ROOT/checks/encode.log` and `ROOT/checks/ffprobe.json`, and prints progress and a JSON summary to stdout.
- `[dissolve.py:Outro.preview]` writes `ROOT/checks/frame_<t>.png` for nine sample times and `ROOT/checks/contact_sheet.jpg`.
- `[dissolve.py:main]` creates `ROOT/checks`.

## Verification

- Run: `cd server && .venv/bin/python -m pytest`
- Lint: `cd server && .venv/bin/ruff check src tests`
