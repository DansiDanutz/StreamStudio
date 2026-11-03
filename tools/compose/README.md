# Offline compose: a HeyGen render → a finished StreamStudio-style video

## Overview

Used for "DansLab — the AI Business Network" (docs/scripts/danslab-network.md).

1. Render the whole script in HeyGen as one video (one scene per segment).
2. `cuts.py WORKDIR SCRIPT.json` → `cuts.json`: segment boundaries in seconds. Download HeyGen's captions
   too (⋮ → Download → Captions) as `WORKDIR/captions.srt`; captions are matched to the script's segments
   and each cut is snapped to the middle of the pause between them (`silencedetect`), so no word is clipped.
   (Scenes of the same avatar have no visible scene change, so the captions are what make this exact.)
3. `masks.py WORKDIR`: person masks (rembg `u2net_human_seg`) for the full-frame segments, every 4th
   frame; render.py blends between them.
4. `render.py WORKDIR OUT.mp4 [--preview]`: Dan seated in the studio plate (desk in front) for talking
   segments; for site segments the page is a large card over the blurred studio and Dan is in a small
   circle (his own lip-synced voice throughout). Titles, name tags and the end card are drawn here.
   Audio is the HeyGen track, loudness-normalised to −14 LUFS.

WORKDIR holds `heygen.mp4`, `cuts.json`, `masks/` and `stills/` (16:9 captures of the sites).

Subdirectories:

- [motion](./motion/README.md): the HyperFrames motion cards (`build.py`, storyboards, `stitch.py`) and, under
  [motion/intro](./motion/intro/README.md), the logo-reveal intro composition.
- The OpenCV face detector `qa_avatar.py` loads lives in `assets/models/haarcascade_frontalface_default.xml` (moved there so the server can serve it from `assets_dir`).

Data files in this directory: `episode-01.plan.json` and `episode-01-v2.plan.json` (per-episode plans, see below),
`episode-01-v2.durations.json` (measured scene lengths for `motion/cards_v2.py`), `danslab-network.cuts.json`.

### Per-episode plans

A WORKDIR may also hold `plan.json`: one entry per segment, replacing the built-in plan
(`episode-01.plan.json` is Episode 1's). Keys:

- `kind`: `avatar` (Dan in the studio) or `card` (`still`, `tag`, optional `intro_zoom` [cx, cy] = push into the studio monitor first).
- `title` [line 1, line 2]: title card rising on the table.
- `lower` [name, sub]: one table card; `lowers` [[from, to, name, sub], …] several, timed as fractions of the segment.
- `chips` [names] with optional `chip_at` [fractions]: small cards rising one by one, e.g. on the words that name them.
- `zoom` [cx, cy, z] or `zoom_path` [[fraction, cx, cy, z], …]; `card_x` places table cards while zoomed.
- `endcard` [title, link, small print], shown from `end_at` to `end_until` (fractions; default: the last 6.5 s).
- Motion cards: `video` (a HyperFrames render in `WORKDIR/cards/`), `video_at` (seconds into that card where this
  segment starts) and `cont: true` when a segment continues the same card (no fade between them).
- `chips_out` (fraction): when the chips leave. `frame` [cx, cy, z]: a slightly tighter framing for the whole
  segment (table cards stay in screen space). `glitch` [[fraction, seconds], …]: RGB-split glitch moments.
- Sound cues for `mix.py`: `question: true` (riser into the segment, pop on its card), `whoosh_at` (fraction).

`episode-01-v2.plan.json` is Episode 1 v2's plan; its motion cards are `motion/cards_v2.py`
(`CARDS=cards_v2 EP_SCRIPT=… EP_DURATIONS=episode-01-v2.durations.json python3 motion/build.py`).

### Finishing: intro, music, SFX

`mix.py WORKDIR MAIN.mp4 INTRO.mp4 OUT.mp4 [--music ambient-pad]` puts the DansLab logo intro in front and mixes
the voice (−16 LUFS), a very quiet music bed (−36 LUFS, looped, fading in after the logo) and SFX only at the
special moments the plan names (plus the card's own page changes and counter landing), then normalises the
whole thing to −14 LUFS. Every cue is written to `OUT.mp4.cues.json`. Music and SFX come from the media library
(`MEDIA_LIB`, ElevenLabs-generated on Dan's account).

### Scenes of ~10 s

Fixing one scene after the full render: `render.py WORKDIR x --scenes=4,31` composes only those scenes into
`WORKDIR/patches/`, then `splice.py WORKDIR main.mp4 main-fixed.mp4` swaps them in frame-exact and `mix.py` remixes.

`scenecut.py` cuts a long take into scene clips by caption text, so each scene is checked
(`qa_avatar.py`) and, if faulty, re-rendered alone and swapped in.

`peek.py WORKDIR t1 t2 …` renders single frames at those seconds into `WORKDIR/peek.jpg` for checking.

## Interface

All scripts are command-line tools driven by `sys.argv`; most run their work at module level, so importing them
executes them. Only `render.py` exposes functions that another script reuses (`peek.py` loads it with
`importlib` and calls `render.compose`).

### `cuts.py` — segment boundaries from captions

- Usage: `python cuts.py WORKDIR SCRIPT.json`. `SCRIPT.json` is a list of segment texts (strings or objects with `text`).
- `ts(x)`: SRT timestamp to seconds. `norm(s)`: lower-case alphanumerics only, used to compare captions to script.
- `main()`: match captions to segments, snap each boundary to the nearest pause from `ffmpeg silencedetect`
  (`n=-38dB:d=0.15`), write `WORKDIR/cuts.json` as `[0, cut1, …, duration]`.

### `masks.py` — person masks for the avatar segments

- Usage: `python masks.py WORKDIR`. Constants `FPS = 25`, `STEP = 4`; rembg session `u2net_human_seg`.
- `AVATAR`: the segment indexes to mask. Default list `[0, 1, 7, 8, 9, 10, 15, 16]`; when `WORKDIR/plan.json`
  exists it is every entry with `kind == 'avatar'` or an `intro_zoom`.

### `mix.py` — final mix

- Usage: `python mix.py EPISODE_DIR MAIN.mp4 INTRO.mp4 OUT.mp4 [--music NAME]` (default music `ambient-pad`).
- Environment: `MEDIA_LIB` (music/SFX library root, default `/home/claude/dansidanutz/claude-youtube/media/library`),
  `CARD_COMPS` (built motion-card compositions, default `motion/comps` next to this file).
- `SR = 48000`. `load(path, lufs=None, extra='')`: decode to stereo float32 at `SR`, optionally `loudnorm` to
  `lufs`. `dur(path)`: duration via ffprobe. `put(a, t, gain)`: add audio into the mix at `t` seconds.
- `cue(name, t, db, why)`: register an SFX cue. `comp_times(card, pattern)`: regex-extract times from a card's
  `index.html` under `CARD_COMPS`.
- Plan keys read for cues: `question`, `lowers` (first start fraction; a name containing `AI avatar` adds the
  reveal impact), `whoosh_at`, `glitch`, `endcard`/`end_at`, `video`/`cont`.

### `peek.py` — single-frame previews

- Usage: `python peek.py WORKDIR t1 [t2 …]`; renders `render.compose` at each second into a 2-column contact sheet
  `WORKDIR/peek.jpg`.

### `qa_avatar.py` — avatar QA for scene clips

- Usage: `python qa_avatar.py SCENES_DIR [--sheet]`; checks every `scene-NN.mp4` in the directory.
- `FPS_S = 12.5` (sampling rate); `CASCADE`: Haar face detector from `assets/models/`.
- `frames(path, w=480)`: grey frames at `FPS_S`. `audio_rms(path, n)`: per-frame RMS at 16 kHz mono.
  `face_box(g)`: largest detected face or `None`. `check(path)`: one clip's measurements and issue list.
- `main()`: judges every clip against the median of the others (face placement and lip ratio), writes `qa.json`,
  prints one line per scene with status `FAIL`, `LOOK` or `ok`, and exits 1 if any scene is `FAIL`.
- Status rule (`qa_avatar.py:main`): any issue not starting with `lips` is `FAIL`; issues that are only lip
  warnings give `LOOK`.

### `render.py` — the compositor

- Usage: `python render.py WORKDIR [OUT.mp4] [--preview] [--scenes=4,31] [--until=SECONDS]`.
  - `--preview`: every 5th second only (`PREVIEW_EVERY = 5`), video only.
  - `--scenes=`: 1-based scene numbers composed into `WORKDIR/patches/scene-NN.mp4` (video only) by `render_scenes`.
  - `--until=`: compose only the first N seconds (video only).
- Constants: `WW, HH, FPS = 1920, 1080, 25`; `STUDIO` (studio plate directory, hard-coded
  `/home/claude/streamstudio/assets/studio`); `FONT` (Inter OTF path pattern); `CARD_W, CARD_H, CARD_X, CARD_Y =
  1400, 788, 440, 150`; `CIRCLE = 300` with its top-left at `(92, HH - 92 - CIRCLE)`; `TABLE_BOTTOM = 1004`.
- `PLAN`: built-in Episode 1 plan, replaced by `WORKDIR/plan.json` when present.
- Frame functions: `compose(frame, f)` (one output frame for source frame `f`), `seg_at(t)`, `ease(x)`,
  `mask_for(f)` (person alpha, blended between the nearest saved masks), `studio(frame, f)`, `zoom(img, cx, cy, z)`,
  `card_img(name)`, `card_layer(...)`, `glitch(img, u, f)`.
- Overlay helpers: `rounded_mask`, `neon_frame`, `text_rgba`, `overlay`, `tag_draw`, `table_card`,
  `place_table_card`, `table_glow`.
- `class CardVideo`: forward-only reader of a motion card MP4 from `WORKDIR/cards/`; `CardVideo.get(name)` caches
  one reader per file, `frame(i)` returns frame `i` resized to `CARD_W x CARD_H` if needed.
- `main()`: full render; `render_scenes(dec)`: the `--scenes` path.

### `scenecut.py` — scene clips from a long take

- Usage: `python scenecut.py TAKE.mp4 CAPTIONS.srt SCRIPT.json SCENES OUTDIR`, where `SCRIPT.json` has a `scenes`
  list of `{scene, voice}` and `SCENES` is a comma-separated list of scene numbers.
- `ts`, `norm` (as in `cuts.py`), `caps(srt)`, `silences(mp4)`, `locate(C, text) -> (start, end)` (first caption
  run whose normalised text equals the scene's voice text), `snap(sil, t, side)`, `cut(mp4, a, b, out)`.

### `splice.py` — swap re-rendered scenes into the main video

- Usage: `python splice.py WORKDIR MAIN.mp4 OUT.mp4`; uses `WORKDIR/patches/scene-NN.mp4` and `WORKDIR/cuts.json`.

## Invariants

- `render.py` asserts `len(PLAN) == len(cuts) - 1`: the plan must have exactly one entry per segment in `cuts.json`
  (`render.py:assert len(PLAN) == len(cuts) - 1`).
- `cuts.py` exits with an error if the captions and the script disagree at the start of a segment
  (`buf[:20] != target[:20]`) or if fewer segments were matched than the script has; it prints a warning when a
  cut is snapped more than 1.0 s from the caption boundary (`cuts.py:main`).
- Card segments in `render.py` keep Dan's own HeyGen frame on screen: `card_layer` crops the centre of the source
  frame (`side = 0.60 * HH` around `(WW/2, 0.37 * HH)`) into the `CIRCLE = 300` px circle at the bottom left, and the
  audio is the HeyGen track mapped unchanged in time (`main`: `-map 1:a`). The module docstring states this is how
  the lip-sync rule holds for offline renders; the rule itself is enforced in the server (`render/lipsync.py`), not here.
- `CardVideo.frame` raises `FileNotFoundError` when the motion card MP4 is missing or empty (`render.py:CardVideo.frame`),
  so a plan that names a `video` not present in `WORKDIR/cards/` stops the render.
- `mix.py` exits if a plan segment's `video` has no built composition under `CARD_COMPS`
  (`mix.py:comp_times`, `sys.exit('motion card comp not found ...')`), rather than mixing without its cues.
- Loudness targets (`mix.py`): intro `-18` LUFS, voice `-16`, music bed `-36`, SFX `-26`, final `loudnorm=I=-14:TP=-1.5:LRA=11`.
  `render.py`'s own full render applies the same final `loudnorm` to the HeyGen audio.
- `masks.py` masks every `STEP = 4` th frame and skips frames whose mask file already exists; card segments with an
  `intro_zoom` are masked only for their first 1.3 s (`b = min(b, a + 1.3)`). `render.mask_for` searches up to 4 frames
  either side for a saved mask and interpolates, so `STEP` must stay at most 4.
- `qa_avatar.py` thresholds (`check`): face must be found in at least 97% of sampled frames; a glitch is a frame
  difference above `6 * (median + 0.3)` and above 4; frozen is more than 0.6 s of no change while voiced; lips are
  compared to the median lip ratio across scenes (`< 0.7 * lip_ref` is flagged) and face placement to the median box
  (shift `> 15%` of width or size `> 12%`).
- `splice.py` replaces only the video frames of the patched ranges; audio is copied from `MAIN.mp4` (`-c:a copy`),
  so a patch must have the same frame count as the range it replaces.
- `render.py` reads the studio plate, desk layer and seat geometry from `STUDIO/plate-landscape-final.{png,desk.png,json}`;
  the path is hard-coded and must exist on the machine running the script.

## Side Effects

- `cuts.py`: runs `ffmpeg` (silencedetect) and `ffprobe` on `WORKDIR/heygen.mp4`; writes `WORKDIR/cuts.json`.
- `masks.py`: creates `WORKDIR/masks/`; decodes segments with `ffmpeg` at 960x540; runs rembg (CPU/GPU model
  `u2net_human_seg`, downloaded by rembg on first use); writes `WORKDIR/masks/NNNNN.png`.
- `render.py`: spawns an `ffmpeg` decoder on `WORKDIR/heygen.mp4` and an `ffmpeg` encoder; writes `OUT.mp4`
  (default `WORKDIR/danslab-network.mp4`) or, with `--scenes`, creates `WORKDIR/patches/` and writes
  `scene-NN.mp4` files. Reads `WORKDIR/stills/`, `WORKDIR/cards/`, `WORKDIR/masks/`, `WORKDIR/plan.json` and the
  `STUDIO` plate files; loads Inter fonts from `/usr/share/fonts/opentype/inter/`.
- `mix.py`: reads `MEDIA_LIB/music/clips/<name>.mp3` and `MEDIA_LIB/sfx/clips/<name>.mp3`, and
  `CARD_COMPS/<card>/index.html`; runs `ffmpeg`/`ffprobe` several times; writes a temporary `OUT.mix.f32` (deleted
  afterwards), `OUT.mp4` and `OUT.mp4.cues.json`.
- `qa_avatar.py`: runs `ffmpeg` per clip; writes `SCENES_DIR/qa.json` and, with `--sheet`, `SCENES_DIR/qa-NN.jpg`;
  exit code 1 on any `FAIL`.
- `scenecut.py`: runs `ffmpeg` silencedetect on the take and one `ffmpeg` encode per requested scene into
  `OUTDIR/scene-NN.mp4`; prints `NOT FOUND` and skips a scene whose text is not in the captions.
- `splice.py`: spawns `ffmpeg` readers for `MAIN.mp4` and each patch and one encoder; writes `OUT.mp4`.
- `peek.py`: runs `ffmpeg` once per requested second; writes `WORKDIR/peek.jpg`.
- No script in this directory calls a network API or a paid service; HeyGen rendering and site capture happen
  before these tools run.

## Verification

- No automated test covers this directory; the repository-wide `make test` (server pytest + web vitest) and
  `make lint` (ruff on `server/`) do not touch `tools/compose`.
- Manual checks the scripts provide: `render.py WORKDIR out.mp4 --preview` for a quick pass, `peek.py` for single
  frames, `qa_avatar.py SCENES_DIR --sheet` for per-scene faults (exit code 0 means no `FAIL`), and
  `OUT.mp4.cues.json` from `mix.py` to confirm every SFX cue.
