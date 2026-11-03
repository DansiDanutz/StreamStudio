# worker

## Overview

The job worker process (console script `streamstudio-worker`, `main:run`). It
claims queued rows from the `jobs` table in SQLite, runs the handler registered
for the job's `kind`, keeps a heartbeat while it runs, and records the result
or failure. `handlers.py` holds the registry and the seven built-in handlers
(media probe, recording finish, transcript, YouTube upload, HeyGen clip, vault
push, noop). The API enqueues jobs; only this process executes them.

## Interface

### `handlers.py`

- `JobContext` — `job`, `conn`, `settings`; `progress(p, message=None)`, `cancelled() -> bool`
- `Handler = Callable[[JobContext], dict]`, `HANDLERS: dict[str, Handler]`, `handler(kind)` decorator
- Registered kinds: `probe` (`probe_asset`), `noop`, `finish_recording`, `transcribe` (`transcribe_recording`), `youtube_upload`, `heygen_clip`, `vault_push`
- `queue_vault_push(conn, s) -> dict | None`
- Test hooks: `YOUTUBE_TRANSPORT`, `HEYGEN_TRANSPORT`, `HEYGEN_POLL_S = 8.0`, `CUTOUT` (defaults to `_cutout_clip`)
- `_cutout_clip(mp4, out_webm, plate) -> bool`, `shutil_copy(src, dst)`

### `main.py`

- `run_one(conn, settings, worker_id) -> bool`
- `loop(settings, worker_id, stop, poll_s=0.5)`
- `run()`

## Invariants

- `[handlers.py:handler]` Handlers are keyed by kind; `[main.py:run_one]` fails a job with no handler immediately (`max_attempts=0`).
- Handlers are idempotent (module docstring) and each one checks its own output before working: `[handlers.py:finish_recording]` keeps an MP4 whose mtime is not older than the source; `[handlers.py:transcribe_recording]` keeps a transcript newer than the MP4; `[handlers.py:youtube_upload]` resumes from `<data_dir>/youtube/uploads/<channel>-<id>.json` through `core.youtube.upload` and never creates a second video; `[handlers.py:heygen_clip]` writes the HeyGen `video_id` to `<data_dir>/heygen/<key>.json` before polling, so a retry resumes the same paid render, and skips the render entirely when the MP4 exists; `[handlers.py:vault_push]` is idempotent by checksum (`core.vault.push`).
- `[handlers.py:heygen_clip]` gives up after 30 minutes (`TimeoutError`), deletes the state file on a `failed` status so the next attempt starts a new render, returns `{"cancelled": True}` when the job is cancelled mid-poll, and re-cuts the clip only when the `.cutout.webm` is older than the MP4. The downloaded URL is presigned; the API key is not sent to it.
- `[handlers.py:queue_vault_push]` returns `None` when no vault is configured and reuses an already queued `vault_push` job instead of adding another.
- `[handlers.py:finish_recording]` rejects a source outside `recordings_dir`; output is H.264 (`h264_videotoolbox` when `core.media.hw_encoders` lists it, else `libx264`), AAC 192k, 48 kHz, 30 fps, `loudnorm=I=-14:TP=-1.5:LRA=11`.
- `[main.py:run_one]` A job whose status became `cancelled` while running is not marked done. Any exception is recorded with `core.store.fail_job`, which requeues until `Settings.job_max_attempts`.
- `[main.py:loop]` Each thread migrates the schema on start and calls `core.store.requeue_stale` every 30 s with `Settings.job_heartbeat_timeout_s`. `[main.py:run_one]` runs a daemon heartbeat thread (every 15 s, own connection) for the life of the job.
- `[main.py:run]` starts `Settings.worker_concurrency` loop threads; worker ids are `<hostname>:<pid>:<n>`.

## Side Effects

- `[handlers.py:probe_asset]` runs `ffprobe` and updates the `assets` row (`status`, `duration_us`, `probe_json`).
- `[handlers.py:finish_recording]` runs `ffmpeg`, writes `<recordings_dir>/<id>.mp4` via `.tmp.mp4`, then enqueues `vault_push`.
- `[handlers.py:transcribe_recording]` runs `ffmpeg` and `whisper-cli` (`core.transcribe.transcribe`) and writes `<id>.transcript.json` and `<id>.srt`.
- `[handlers.py:youtube_upload]` sends the MP4 and, when an SRT exists, the captions to Google (`core.youtube`), and writes the upload state file.
- `[handlers.py:heygen_clip]` uploads a silence WAV (gesture items), calls `create_video` (spends HeyGen credits), polls `get_video`, downloads the MP4 to `<assets_dir>/avatar/<clips|gestures>/<name>.mp4` via `.part`, runs the local cut-out (rembg + ffmpeg) to `<name>.cutout.webm`, and enqueues `vault_push`.
- `[handlers.py:vault_push]` uploads to the configured vault and writes `vault_objects` and `<data_dir>/catalog.json`.
- `[main.py:run_one]` writes `jobs` (claim, heartbeat, finish, fail) and logs to `streamstudio.worker`. `[main.py:run]` installs `SIGINT`/`SIGTERM` handlers that stop the loops.

## Verification

- Run: `cd server && .venv/bin/python -m pytest`
- Lint: `cd server && .venv/bin/ruff check src tests`
