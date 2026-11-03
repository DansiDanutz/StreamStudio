# episode

## Overview

The episode factory: a script in, a private YouTube upload out (design:
`docs/egm/daily-episode-factory/daily-episode-factory.md`). Stage 0 shipped the package
skeleton, the shared constants and `preflight`; Stage 1A adds the contract, the validator, the
record, the cost ledger and the publish helper. The planner and the stage handlers (Stage 1B)
and the Episode page (Stage 1C) follow.

| Module         | Role                                                              |
| -------------- | ----------------------------------------------------------------- |
| `__init__.py`  | Package rule, `FPS`, `HYPERFRAMES_WORKERS`                        |
| `preflight.py` | Which tools the shipped stage needs, checked without importing them |
| `contract.py`  | The script contract (`Script`, `Scene`, `Plan`), `extra="forbid"` |
| `validate.py`  | The validator: errors block approval, warnings never do           |
| `record.py`    | The episode record in `episodes.record_json`; keys, hashes, the `GET /{id}` shape |
| `ledger.py`    | `heygen_ledger`: reservations, charges, releases, the month's total |
| `publish.py`   | Publish now (YouTube `videos.update`) and the purge of workings   |
| `planner.py`   | `episode_advance`: the condition table over the record and the files |
| `handlers.py`  | The factory's job handlers, registered with the worker            |
| `compose.py`   | `scene_compose`: clip + cut-out → `scenes/<scene>.mp4` on the plate, with the guard |
| `mix.py`       | `episode_assemble`: scenes + intro + bed + SFX → `final.mp4`      |
| `kit.py`       | `episode_publish_kit` and `episode_register`: kit, captions, the library take |
| `templates/`   | The HyperFrames workspace (`package.json`, `package-lock.json`) copied to `<data_dir>/cards` |

## Interface

### `__init__.py`

- `FPS = 25` — every episode render (clips, cards, intro, final) runs at this rate.
- `HYPERFRAMES_WORKERS = 4` — parallel Chrome processes for one card render.

### `preflight.py`

- `FONTS`, `INTRO`, `PLATE`, `PLATE_JSON`, `MUSIC_MANIFEST`, `HAAR_CASCADE` (relative to `assets_dir`), `WORKSPACE_MARKER`
- `playwright_chromium(s) -> Path | None`, `hyperframes_workspace(s) -> Path | None`
- `tools(s) -> dict` — `opencv`, `rembg` (flags from `find_spec`), `playwright_chromium`, `hyperframes`, `fonts`, `intro`, `plate`, `music_manifest`, `haar_cascade` (paths or `None`)
- `check(s, stage=1) -> {ok, missing}` — Stage 1: ffmpeg, ffprobe, rembg, fonts, intro, plate, music manifest; Stage 2 adds whisper and the Haar cascade; Stage 3 adds Playwright Chromium and the HyperFrames workspace

### `contract.py`

- `SCENE_ID` (`^s[0-9]{1,3}$`), `CARD_ID` (`^c[0-9]{1,3}$`), `EPISODE_ID` (`^ep_[a-z0-9]{8,40}$`)
- `Plan` — `title`, `lower`, `lowers: [[from, to, name, sub]]`, `chips`, `chip_at`, `chips_out`, `zoom`, `zoom_path: [[fraction, cx, cy, z]]`, `card_x`, `frame`, `glitch: [[fraction, seconds]]`, `endcard`, `end_at`, `end_until`, `whoosh_at`, `card_template: "generic" | None`
- `Source` (`claim`, `source`), `Scene` (`id`, `text`, `voice`, `kind: "avatar" | "card"`, `site`, `question`, `reveal`, `sources`, `plan`; property `spoken` = `voice` else `text`), `Script` (`title`, `version`, `tags`, `channel`, `look`, `voice_id`, `motion`, `scenes`)
- `script_hash(script) -> str` (16 hex)

### `validate.py`

- `MIN_S`, `MAX_S` (Stage 2), `voice_names(s)` (from `assets/brand/voice-names.json`), `estimate_seconds(script)`
- `validate(script, s) -> {errors: {scene_id: [..]}, warnings: {scene_id: [..]}}` — Stage 1 errors: duplicate scene id, a card scene without a site, both voice and text empty

### `record.py`

- `STATES`, `EDITABLE` (`draft`, `script_approved`, `budget_approved`, `in_progress`, `needs_dan`), `WORKING` (`budget_approved`, `in_progress`), `NEXT_ACTION`
- `Episode` (dataclass: `id`, `project_id`, `status`, `title`, `created_at`, `updated_at`, `record`; property `script`, method `scene_state(scene_id)`)
- Paths: `episode_dir(s, id)`, `clip_paths(s, key) -> (mp4, cutout_webm)`, `clip_state_path(s, key)`, `read_clip_state(s, key)`
- Keys: `scene_key(s, scene, script, take=0)` (look, voice id and motion from the script, else `core.heygen.load_config`), `inputs_hash(scene, clip_mp4, cutout_webm, card_mp4)`
- Storage: `create(conn, s, script)`, `load(conn, id)`, `save(conn, episode)`, `set_status(episode, status, message=None)`, `log(episode, stage, message, scene=None)`, `list_episodes(conn)`, `export(s, episode)`
- The read shape: `progress(s, episode) -> {clips, qa, composed, total}`, `to_out(s, episode, validation)`

### `ledger.py`

- `Line = (scene_id, clip_key, take, job_id, seconds, usd)`
- `reserve(conn, episode_id, lines, allowance_usd) -> approval_id`, `charge(conn, episode_id, scene_id, clip_key, take, job_id, seconds, at=None) -> bool`, `release(conn, episode_id, approval_id, usd=None) -> float`, `release_unsubmitted(conn, episode_id, live_keys, charged_keys)`, `latest_approval(conn, episode_id)`, `unconsumed(conn, episode_id)`, `month_total(conn, now=None)`, `spent(conn, episode_id)`

### `publish.py`

- `YOUTUBE_TRANSPORT` (tests replace it; otherwise `worker.handlers.YOUTUBE_TRANSPORT`), `WORKINGS`
- `publish(conn, s, episode, publish_at)` (sets `published`, or `scheduled` from Stage 2), `purge(s, episode) -> {freed_bytes}`

### `planner.py`

- `LIVE`, `clip_payload(s, episode, scene, script, key, take)` (the `heygen_clip` payload: as the editor's plus `take`, `episode_id`, `scene_id`, `seconds`, `max_attempts: 1`)
- `advance(conn, s, episode_id) -> dict` — one pass under `db.tx`; skipped outside `record.WORKING`. Stage 1 rows: sync (current keys, clip presence, measured durations, composed hashes from `scenes/<id>.hash`); row 1 (a `failed` state file or an errored recorded job → `needs_dan`); row 2 (`heygen_clip` per scene without a clip, claim transfer when the previous job errored with a saved `video_id`); row 6 (`scene_compose` when `composed_hash != inputs_hash`); rows 7 to 9 (`episode_assemble`, `episode_publish_kit`, `episode_register`, the recording id discovered from `rec_*-ep.episode.json`); rows 10 and 11 (`youtube_upload` with `clean_meta` from `kit.json`, then `uploaded_private` from the upload state file and the release of the reservation)

### `handlers.py`

- `episode_advance`, `scene_compose`, `episode_assemble`, `episode_publish_kit`, `episode_register`, `episode_purge` — each imports its module inside the function and enqueues `episode_advance` when done (purge sets `purged` itself)

### `compose.py`

- `W, H = 1920, 1080`, `HANDS_IN_CLIP = 0.85`, `TABLE_BOTTOM`, `FONT_FILES`, `ease`, `probe_duration(ffprobe_bin, path)`
- `guard(scene, clip_url, degraded) -> cue` (`avatar`, `content` or `pip` through `render.lipsync.guard_cue` with the voice `"clip"`)
- `Compositor(s)` — `studio`, `zoom`, `table_card`, `place_table_card`, `table_glow`, `glitch`, `pip`, `frame(scene, plan, frame, alpha, tl, dur, f, cue)`
- `effective_plan(scene)` (a card scene without its card gets the site as a lower; a question scene without overlays gets a question lower)
- `compose_scene(s, scene, clip_mp4, cutout_webm, out_mp4, *, card_mp4=None, degraded=False, progress=None, compositor=None) -> {frames, duration_s, cue}` — decodes the cut-out with `libvpx-vp9` (alpha kept) and the clip at 25 fps in lock-step, encodes H.264 with the clip's audio, temp file plus rename

### `mix.py`

- `SR`, `LEVELS` (intro -18, voice -16, bed -36, SFX -26 LUFS), `FINAL` (`loudnorm` -14 / -1.5 / 11), `CUE_SOUNDS` (cue kind → sound, offset, dB)
- `manifest(s)`, `sound_path(s, stem)`, `bed_path(s)`, `plan_cues(scenes, starts, durations)`
- `assemble(s, scenes, scene_files, intro, out_mp4, extra_cues=None) -> {duration_s, intro_s, scenes, starts, durations, cues, notes}` — refuses a scene file whose frame count is not 25 fps; writes `final.cues.json`

### `kit.py`

- `LINE_CHARS = 42`, `LINES_PER_CAPTION = 2`, `MIN_CHAPTERS = 3`, `MIN_CHAPTER_S = 10`
- `srt_time`, `youtube_time`, `caption_chunks`, `first_sentence`, `chapters_for`, `captions`, `build_kit(script, starts, durations, intro_s, words=None) -> (kit, srt)`
- `register(s, episode_id, final_mp4, final_srt, kit) -> {recording_id, mp4, srt}` (`rec_<stamp>-ep`, with `.srt`, `.transcript.json` naming the language, `.episode.json`), `registered_recording(s, episode_id)`

## Invariants

- No module in this package imports `cv2`, `numpy`, `scipy`, `PIL`, `rembg` or `playwright` at module level; handlers import them inside the function body. Enforced by `tests/test_episode_imports.py`. [__init__.py:docstring]
- `preflight` looks only at paths, `PATH` and `importlib.util.find_spec`; it never imports a tool. [preflight.py:_pkg, check]
- Every contract model forbids unknown keys, so a typo in a plan key is a 422. [contract.py:Strict]
- `record.save` runs inside the caller's `db.tx`; the API writes `script`, `budget`, `outputs.channel` and the gate states, the planner everything else. [record.py:save]
- A charge is written once per (episode, clip key); a second `charge` for the same key returns False. `month_total` is this month's charges plus the unconsumed part of every episode's latest reservation group, floored at zero per episode. [ledger.py:charge, unconsumed, month_total]
- `templates/package.json` and `package-lock.json` are the tested HyperFrames and GSAP pair; the launcher and `make setup` copy them, they are never edited in place. [templates/package.json]
- The planner is the only writer of `scenes_state`, `cards`, the non-channel `outputs` fields, `log` and the working states; stage handlers report by writing files (`scenes/<id>.mp4` and `.hash`, `final.mp4`, `kit.json`, `rec_*-ep.episode.json`, the upload state file). Every row records the job id it enqueues and skips while that job is queued or running; its one `jobs` read is the status of a recorded id. [planner.py:_pass]
- Every episode render runs at 25 fps; `mix.assemble` refuses a scene file whose frame count disagrees. The lip-sync guard runs for every scene before compositing. [compose.py:compose_scene, guard; mix.py:assemble]

## Side Effects

- `record.create` inserts `projects` and `episodes` rows and creates `<episodes_dir>/<id>/`; `record.export` writes `episode.json` there. `ledger.*` insert `heygen_ledger` rows. `publish.publish` calls YouTube; `publish.purge` deletes the workings directories. [record.py:create, export; ledger.py:_insert; publish.py:publish, purge]
- `planner.advance` enqueues jobs and rewrites the record; `compose_scene`, `assemble` run ffmpeg subprocesses and write under `<episodes_dir>/<id>/scenes` and `/mix`; `kit.register` moves `final.mp4` into `recordings_dir`. [planner.py:_enqueue; compose.py:compose_scene; mix.py:assemble; kit.py:register]

## Verification

- `cd server && .venv/bin/python -m pytest tests/test_episode_imports.py tests/test_episodes.py tests/test_episode_pipeline.py` (the pipeline tests need the `episode` extra and ffmpeg with libx264 and libvpx-vp9)
- The Episode 1 v2 fixture: `tests/fixtures/episode-01-v2/script.json`, regenerated by `python tests/convert_episode1.py`.
