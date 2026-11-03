# episode

## Overview

The episode factory: a script in, a private YouTube upload out (design:
`docs/egm/daily-episode-factory/daily-episode-factory.md`). Stage 0 ships the package skeleton,
the shared constants and `preflight`; the contract, record, ledger, planner and handlers arrive
in Stages 1 to 4.

| Module         | Role                                                              |
| -------------- | ----------------------------------------------------------------- |
| `__init__.py`  | Package rule, `FPS`, `HYPERFRAMES_WORKERS`                        |
| `preflight.py` | Which tools the shipped stage needs, checked without importing them |
| `templates/`   | The HyperFrames workspace (`package.json`, `package-lock.json`) copied to `<data_dir>/cards` |

## Interface

### `__init__.py`

- `FPS = 25` — every episode render (clips, cards, intro, final) runs at this rate.
- `HYPERFRAMES_WORKERS = 4` — parallel Chrome processes for one card render.

### `preflight.py`

- `FONTS`, `INTRO`, `PLATE`, `PLATE_JSON`, `MUSIC_MANIFEST`, `HAAR_CASCADE` (relative to `assets_dir`), `WORKSPACE_MARKER`
- `playwright_chromium(s) -> Path | None` — `s.hyperframes_browser` when set and present, else the newest Playwright Chromium under `~/.cache/ms-playwright` or `~/Library/Caches/ms-playwright`
- `hyperframes_workspace(s) -> Path | None` — `s.cards_dir` when `node_modules/hyperframes` is installed there
- `tools(s) -> dict` — `opencv`, `rembg` (flags from `find_spec`), `playwright_chromium`, `hyperframes`, `fonts`, `intro`, `plate`, `music_manifest`, `haar_cascade` (paths or `None`)
- `check(s, stage=1) -> {ok, missing}` — Stage 1: ffmpeg, ffprobe, rembg, fonts, intro, plate, music manifest; Stage 2 adds whisper and the Haar cascade; Stage 3 adds Playwright Chromium and the HyperFrames workspace

## Invariants

- No module in this package imports `cv2`, `numpy`, `scipy`, `PIL`, `rembg` or `playwright` at module level; handlers import them inside the function body. Enforced by `tests/test_episode_imports.py`, which imports every module with those names blocked. [__init__.py:docstring]
- `preflight` looks only at paths, `PATH` and `importlib.util.find_spec`; it never imports a tool. [preflight.py:_pkg, check]
- `templates/package.json` and `package-lock.json` are the tested HyperFrames and GSAP pair (chosen in Stage 0 by rendering the intro); the launcher and `make setup` copy them, they are never edited in place. [templates/package.json]

## Side Effects

- None. `preflight` reads the filesystem only.

## Verification

- `cd server && .venv/bin/python -m pytest tests/test_episode_imports.py`
