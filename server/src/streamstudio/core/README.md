# core

## Overview

Shared, framework-free building blocks used by both the API and the worker:
settings, the SQLite schema and data access, path and network safety, media
probing, and the three external integrations (HeyGen, YouTube, the vault).
Nothing here imports FastAPI except `netguard.py`, which is a plain ASGI
middleware built on Starlette types.

| Module          | Role                                                                     |
| --------------- | ------------------------------------------------------------------------ |
| `config.py`     | `Settings` from `STREAMSTUDIO_*` env / `.env`                            |
| `db.py`         | SQLite connect, WAL, forward-only `MIGRATIONS`, `tx`, row helpers         |
| `store.py`      | Projects, EDL versions, assets, jobs                                      |
| `ids.py`        | `new_id`, `now_iso`                                                       |
| `paths.py`      | Request-path containment (`resolve_within`, `resolve_in_any`)            |
| `netguard.py`   | Loopback/tailnet peer, Host and Origin checks                            |
| `media.py`      | ffprobe/ffmpeg helpers                                                    |
| `transcribe.py` | whisper.cpp transcripts                                                   |
| `heygen.py`     | HeyGen v3 client, config file, clip keys and specs                        |
| `youtube.py`    | YouTube OAuth (PKCE), resumable upload, captions                          |
| `vault.py`      | Off-machine copies: S3 (SigV4) or synced folder                          |

## Interface

### `config.py`

- `CaptureSite(BaseModel)` — `host: str`, `mode: "auto" | "manual"` (a site the episode factory may capture for a card)
- `Settings(BaseSettings)` — fields `data_dir`, `assets_dir`, `import_roots`, `host`, `port`, `allow_tailnet`, `extra_hosts`, `worker_concurrency`, `job_heartbeat_timeout_s`, `job_max_attempts`, `ffmpeg_bin`, `ffprobe_bin`, `whisper_bin`, `whisper_model`, `capture_allowlist: list[CaptureSite]`, `hyperframes_browser: Path | None` (`None`: Playwright's Chromium), `episode_rerender_attempts` (4), `episode_rerender_usd` (1.5), `heygen_month_ceiling_usd` (400); properties `db_path`, `projects_dir`, `recordings_dir`, `episodes_dir`, `cards_dir`, `sites_dir`; methods `allowed_import_roots()`, `ensure_dirs()` (creates the five directories)
- `get_settings()` (lru-cached)

### `db.py`

- `MIGRATIONS: list[str]` — 4 migrations creating tables `projects`, `assets`, `edl_versions`, `jobs`, `scenes`, `artifact_meta`, `vault_objects`, `episodes` (id, project_id, status, title, created_at, updated_at, record_json), `heygen_ledger` (id, episode_id, approval_id, scene_id, clip_key, take, job_id, kind `reservation | charge | release`, seconds, usd, at; a charge is unique per (episode_id, clip_key))
- `connect(path) -> sqlite3.Connection`, `migrate(conn) -> int`, `tx(conn)` (context manager), `row(r)` (decodes `probe_json`, `payload`, `result`, `edl_json`, `record_json`), `rows(rs)`, `WAL_RETRIES`, `WAL_RETRY_S`

### `store.py`

- Projects: `create_project`, `list_projects` (episode-owned rows are excluded), `is_episode_project`, `get_project`, `rename_project`, `delete_project`, `touch_project`
- EDL: `latest_edl`, `save_edl`, `list_edl_versions`, `VersionConflict`
- Assets: `create_asset`, `get_asset`, `list_assets`, `update_asset`
- Jobs: `enqueue`, `get_job`, `list_jobs`, `claim_job`, `heartbeat`, `finish_job`, `fail_job`, `find_active_job`, `cancel_job`, `requeue_stale`

### `ids.py`

- `new_id(prefix) -> str`, `now_iso() -> str`

### `paths.py`

- `UnsafePathError(ValueError)`, `resolve_within(root, candidate)`, `resolve_in_any(roots, candidate)`, `safe_filename(name, max_len=120)`

### `netguard.py`

- `LOOPBACK`, `TAILNET`, `LOCAL_NAMES`, `SAFE_METHODS`
- `is_allowed(host, allow_tailnet)`, `host_allowed(host_header, extra=())`, `origin_allowed(origin, extra=())`
- `NetGuardMiddleware(app, allow_tailnet=True, extra_hosts=None)`

### `media.py`

- `VIDEO_EXT`, `AUDIO_EXT`, `IMAGE_EXT`, `MediaError`
- `kind_for(path)`, `probe(path, ffprobe_bin="ffprobe")`, `summarize(info)`, `tool_version(binary)`, `hw_encoders(ffmpeg_bin="ffmpeg")`

### `transcribe.py`

- `MODEL_CANDIDATES`, `WHISPER_TIMEOUT_S`, `TranscribeError`
- `whisper_model(s)`, `whisper_status(s)`, `require_whisper(s)`, `parse_whisper_json(data)`, `transcribe(mp4, out_json, out_srt, s)`

### `heygen.py`

- `API`, `TIMEOUT_S`, `Transport`, `HeyGenError`
- `config_path`, `load_config`, `save_config`, `mask`
- `Client(api_key, transport=None)` — `me()`, `looks()`, `upload_asset(name, content, ctype)`, `create_video(spec)`, `get_video(video_id)`
- `USD_PER_S = 0.0385`, `WORDS_PER_S = 2.5`
- `silence_wav(seconds, rate=24000)`, `item_key(look, voice, script, motion, silent_s, take=0)`, `estimate_seconds(script, silent_s)`, `estimate(items) -> {seconds, usd, clips, with_motion}`, `video_spec(look, voice, *, script, audio_asset_id, motion, title)`

### `youtube.py`

- `AUTH_URL`, `TOKEN_URL`, `API`, `SCOPE`, `PRIVACY`, `CHANNEL_ID`, `CHUNK`, `TIMEOUT_S`, `REFRESH_MARGIN_S`, `Transport`, `YouTubeError`
- Files: `folder`, `find_download`, `import_client`, `channels`, `status`, `disconnect`, `pick_channel`
- OAuth: `auth_url(data_dir, redirect_uri)`, `finish_auth(data_dir, state, code, transport=None)`
- `Client(data_dir, channel_id, transport=None, token=None)` — `call()`, `json()`
- Upload: `clean_meta`, `upload(api, mp4, meta, state_file, progress)`, `add_captions(api, video_id, srt, language)`
- Publish: `set_status(api, video_id, privacy, publish_at=None)` (`videos.update`, part `status`; a `publish_at` makes it private with a scheduled release), `video_status(api, video_id) -> {privacy, publish_at}`

### `vault.py`

- `TIMEOUT_S`, `CLIP_GLOBS`, `REC_GLOBS`, `VaultError`, `S3_TRANSPORT`
- Config: `config_path`, `load_config`, `save_config`, `mask`, `public_config`
- `Backend` (Protocol), `FolderBackend`, `S3Backend`, `sigv4_headers`, `backend(cfg)`, `prefixed(cfg, key)`
- `sha256_file`, `local_files(s)`, `local_path(s, key)`, `catalog(c)`, `index(c)`, `record(c, key, size, sha)`
- `push(s, c, progress=None)`, `fetch(s, c, key)`, `remote_files(s)`, `restore_catalog(s, c)`

## Invariants

- `[netguard.py:NetGuardMiddleware._reject_reason]` A request is rejected (HTTP 403, or WebSocket close 1008) unless the peer address is in `LOOPBACK` or, when `allow_tailnet`, in `TAILNET` (`is_allowed`); the `Host` header passes `host_allowed` (localhost, an IP literal, `*.localhost`, `*.ts.net`, this machine's names, a dotless name, or a configured extra); and, for non-`SAFE_METHODS` requests and all WebSockets, any `Origin` header passes `origin_allowed`. Requests without an `Origin` are not subject to the origin check.
- `[paths.py:resolve_within]` resolves symlinks before checking containment; `[paths.py:resolve_in_any]` requires an absolute path and raises `UnsafePathError` when it is outside every root.
- `[config.py:Settings.allowed_import_roots]` always includes `data_dir` first; `[config.py:Settings]` reads env with prefix `STREAMSTUDIO_` and ignores unknown keys.
- `[db.py:connect]` sets `isolation_level=None`, `busy_timeout=30000`, `journal_mode=WAL` (retried up to `WAL_RETRIES`) and `foreign_keys=ON`. `[db.py:migrate]` is forward-only, runs under `BEGIN IMMEDIATE`, re-reads `user_version` inside the lock, and sets `user_version` after each migration. `[db.py:tx]` is `BEGIN IMMEDIATE` … `COMMIT`/`ROLLBACK`.
- `[store.py:save_edl]` Optimistic concurrency: the insert happens only when `base_version` equals `MAX(version)`; otherwise `VersionConflict`. `[store.py:claim_job]` claims the oldest queued job inside `tx` and increments `attempts`. `[store.py:fail_job]` requeues while `attempts < max_attempts`, else sets `error`. `[store.py:requeue_stale]` returns running jobs with a stale `heartbeat_at` to the queue. `[store.py:cancel_job]` only affects queued or running jobs. `[store.py:heartbeat]` clamps progress to `[0, 1]`.
- `[ids.py:new_id]` ids are `<prefix>_<base36 ms timestamp><8 hex>`, sortable by creation time.
- `[heygen.py:item_key]` The same `(look, voice, script, motion, silent_s)` always yields the same 16-hex key; `take` is hashed in only when above zero, so every existing clip keeps its name. `[heygen.py:Client.__init__]` raises `HeyGenError` without a key. `[heygen.py:Client._call]` sends the key only in `x-api-key` to `API` and replaces it with `••••` in error messages. `[heygen.py:save_config]` writes with mode `0600`. `[heygen.py:silence_wav]` is 16-bit mono PCM.
- `[youtube.py:upload]` Resumable: the session URL is written to `state_file` before any media bytes are sent; a saved `video_id` short-circuits the call; chunks are `CHUNK` (8 MiB) and resume from Google's reported `range`. `[youtube.py:clean_meta]` enforces title 1–100 chars, description ≤ 5000 bytes, tags ≤ 500 chars total, `privacy` in `PRIVACY`, and strips `<`/`>`. `[youtube.py:finish_auth]` compares `state` with `secrets.compare_digest` and requires a refresh token. `[youtube.py:_channel_file]` validates ids with `CHANNEL_ID`. `[youtube.py:_write_private]` writes with mode `0600`. `[youtube.py:Client._token]` refreshes the access token when within `REFRESH_MARGIN_S` of expiry.
- `[vault.py:S3Backend.__init__]` requires `endpoint`, `bucket`, `access_key`, `secret_key` and an `https://` endpoint. `[vault.py:FolderBackend._p]` rejects keys that resolve outside the folder root. `[vault.py:local_path]` only maps `assets/avatar/{clips,gestures}/<name>.{mp4,webm,json}` and `recordings/rec_*`; everything else is `None`. `[vault.py:push]` skips files whose sha256 matches the local index or the remote `head`. `[vault.py:fetch]` verifies the downloaded sha256 when the remote reports one and raises `VaultError` on mismatch. `[vault.py:public_config]` masks `access_key` and `secret_key`. `[vault.py:save_config]` writes with mode `0600`.
- `[transcribe.py:transcribe]` writes the JSON and SRT through temp files and `replace`, so a partial transcript is never visible. `[transcribe.py:require_whisper]` raises `TranscribeError` when the binary or model is missing.
- `[media.py:probe]` raises `MediaError` when ffprobe is missing or fails (120 s timeout).

## Side Effects

- `[db.py:connect]` creates the database's parent directory and the file. `[db.py:migrate]` alters the schema. All `store.py` functions read or write SQLite; `create_project`, `save_edl`, `claim_job` open their own transactions, the rest run in autocommit or inside a caller's `tx`.
- `[config.py:Settings.ensure_dirs]` and `[config.py:get_settings]` create `projects_dir` and `recordings_dir`.
- `[netguard.py:_machine_names]` calls `socket.gethostname()` on every request.
- `[media.py:probe]`, `[media.py:tool_version]`, `[media.py:hw_encoders]` run `ffprobe`/`ffmpeg` subprocesses.
- `[transcribe.py:transcribe]` runs `ffmpeg` and `whisper-cli` subprocesses in a temporary directory and writes `<rid>.transcript.json` and `<rid>.srt`.
- `[heygen.py:Client]` makes HTTPS calls to `https://api.heygen.com` (`/v3/users/me`, `/v3/avatars/looks`, `/v3/assets`, `/v3/videos`); `create_video` spends HeyGen credits. `[heygen.py:save_config]` writes `<data_dir>/heygen.json`.
- `[youtube.py:auth_url]` writes `<data_dir>/youtube/pending.json`; `[youtube.py:finish_auth]` posts to `TOKEN_URL`, calls the channels API, deletes `pending.json` and writes `<data_dir>/youtube/channels/<id>.json`; `[youtube.py:import_client]` writes `client.json` and unlinks the source; `[youtube.py:disconnect]` unlinks a channel file; `[youtube.py:Client._token]` may rewrite the channel file; `[youtube.py:upload]` and `[youtube.py:add_captions]` call `https://www.googleapis.com` and write `state_file`.
- `[vault.py:S3Backend]` sends signed HTTPS requests to the configured endpoint; `[vault.py:FolderBackend]` copies files under its root and writes `<name>.sha256` sidecars. `[vault.py:push]` writes `<data_dir>/catalog.json` and uploads it; `[vault.py:fetch]` writes into `assets_dir` or `recordings_dir` via a `.part` file; `[vault.py:record]` and `[vault.py:restore_catalog]` write `vault_objects`, `scenes` and `artifact_meta`.

## Verification

- Run: `cd server && .venv/bin/python -m pytest`
- Lint: `cd server && .venv/bin/ruff check src tests`
