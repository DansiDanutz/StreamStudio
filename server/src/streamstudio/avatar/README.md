# avatar

## Overview

Local, offline image tools that turn rendered avatar clips and table-object
renders into stage-ready assets with alpha. `cutout.py` removes the background
from a presenter clip (rembg) and composites it on a studio plate;
`gestures.py` batches that over the fixed set of gesture clips;
`object_matte.py` and `object_clip.py` matte a table object rendered on black
into an RGBA still or a VP9+alpha WebM. All four are also command-line scripts
(`python -m streamstudio.avatar.cutout`, `python -m streamstudio.avatar.gestures`;
`object_clip.py` and `object_matte.py` are run as plain scripts from this
directory because `object_clip.py` imports `object_matte` as a top-level
module). They need the `media` optional dependencies from
`server/pyproject.toml` (pillow, numpy, scipy, rembg) and `ffmpeg`/`ffprobe`.

## Interface

### `cutout.py`

- `probe(path) -> dict` (`w`, `h`, `fps`), `extract_frames(clip, out) -> list[Path]`
- `segment(frames, out, model="u2net_human_seg") -> list[Path]`
- `fit_cover(img, size)`, `HANDS_IN_CLIP = 0.85`, `desk_layer_for(plate) -> Path | None`
- `composite(cutouts, plate, out, *, scale, hands_y, x, size=(1920, 1080))`
- `encode_alpha_webm(cutouts_dir, fps, clip, out)`, `encode_mp4(frames_dir, fps, clip, out)`
- `run(clip, plate, out_dir, *, scale, hands_y, x, keep) -> dict` (keys `cutout_webm`, `composite_mp4`, `still`, plus probe info)
- `main()` — CLI: `CLIP PLATE OUT_DIR [--scale 0.66] [--hands-y 0.68] [--x 0.47] [--keep]`

### `gestures.py`

- `VIDEO`, `ROOT` (repo root), `OUT` (`<repo>/assets/avatar/gestures`), `NEEDED` (the eight gesture ids)
- `duration(p) -> float`, `split(video, out_dir, seconds=3.0, ffmpeg="ffmpeg") -> list[Path]`, `rest_first(clip, ffmpeg="ffmpeg")`
- `process(src_dir, plate, out=OUT) -> dict` (manifest: `gestures`, `missing`)
- `main()` — CLI: `SRC_DIR [--split HEYGEN.mp4] [--seconds 3] [--rest-first ids] [--plate PLATE.png]`

### `object_clip.py`

- `hue(im, shift)`, `alpha_for(a, y_disc, body_ref)`, `main()` — CLI: `SRC.mp4 OUT_DIR NAME [--hue-shift N] [--reverse NAME2] [--disc 520] [--fps 30]`

### `object_matte.py`

- `disc_row(lum, r, g) -> int`, `cut(src, dst, disc_width_px=520) -> Image`

## Invariants

- `[gestures.py:process]` Idempotent: a `<id>.cutout.webm` whose mtime is newer than its source is not re-rendered. Only ids in `NEEDED` are processed; the manifest lists what exists and what is missing.
- `[gestures.py:split]` Scenes in the HeyGen video are cut in `NEEDED` order, `seconds` each, starting at `i * seconds`.
- `[cutout.py:run]` Output size is `1920x1080` for landscape sources and `1080x1920` for portrait. Segmented RGBA frames are cached in `<out_dir>/cache/<clip stem>` and reused only when the cached frame count equals the extracted frame count. Outputs are named `<stem>.cutout.webm`, `<stem>.on-plate.mp4`, `<stem>.on-plate.jpg`.
- `[cutout.py:segment]` Alpha is smoothed with a 0.65/0.35 EMA over consecutive frames and a 0.8 px Gaussian blur; the rembg model is `u2net_human_seg`.
- `[cutout.py:composite]` Presenter height is `scale * H`, hands land at `hands_y` (hands assumed at `HANDS_IN_CLIP` of clip height), centred at `x`; a `<plate>.desk.png` layer, when present, is composited over the presenter.
- `[object_clip.py:main]` The crop box, scale and disc row are computed from the first frame only and applied to every frame; output dimensions are rounded to even numbers.
- `[object_matte.py:cut]` The output is resized so the disc ring spans `disc_width_px`; `disc_y` is stored in `rgba.info`.

## Side Effects

- All modules run `ffmpeg` and/or `ffprobe` as subprocesses with `check=True`.
- `[cutout.py:run]` creates a `tempfile.mkdtemp(prefix="cutout_")` work dir (removed unless `keep`), writes the cache under `out_dir`, and prints progress to stdout. `[cutout.py:segment]` imports `rembg` lazily and creates a model session.
- `[gestures.py:process]` writes `<out>/<id>.cutout.webm` and `<out>/manifest.json`, creating `out`; `[gestures.py:rest_first]` rewrites the clip in place via a `.tmp.mp4`; `[gestures.py:split]` writes `<out_dir>/<id>.mp4`.
- `[object_clip.py:main]` creates a `tempfile.mkdtemp(prefix="objclip_")` work dir (always removed) and writes `<out>/<name>.webm` (and `<reverse>.webm`).
- `[object_matte.py:cut]` writes `dst`; the `__main__` block writes `cutout.png` next to each input.

## Verification

- Run: `cd server && .venv/bin/python -m pytest`
- Lint: `cd server && .venv/bin/ruff check src tests`
