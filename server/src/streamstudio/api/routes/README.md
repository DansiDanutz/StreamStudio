# api/routes

## Overview

One FastAPI `APIRouter` per resource. All of them are mounted by
`create_app` in `../main.py`; none is importable as an app on its own. Request
dependencies (`settings`, `conn`, `project_or_404`) come from `../deps.py`.
Handlers take a per-request SQLite connection and the `Settings` object, call
into `streamstudio.core`, and enqueue work for the worker through
`core.store.enqueue` rather than doing long work inline.

| Module          | Prefix            | What it serves                                                         |
| --------------- | ----------------- | ---------------------------------------------------------------------- |
| `agent.py`      | `/api`            | Artifact library and the agent bus (SSE to the open editor)            |
| `episodes.py`   | `/api/episodes`   | The episode factory: script in, approve script, approve budget (paid), publish, advance, purge |
| `heygen.py`     | `/api/heygen`     | HeyGen config, credit balance, looks, and the paid render estimate/queue |
| `jobs.py`       | `/api/jobs`       | Job list, create, get, cancel                                          |
| `live.py`       | `/api/live`       | RTMP go-live config, status, and the WebSocket ingest                  |
| `projects.py`   | `/api/projects`   | Projects, EDL versions, asset import                                   |
| `recordings.py` | `/api/recordings` | Take upload, list, download, transcript, captions                      |
| `scenes.py`     | `/api/scenes`     | Saved stage sets (opaque JSON)                                         |
| `system.py`     | `/api`            | `/health` and `/edl/schema`                                            |
| `vault.py`      | `/api/vault`      | Off-machine backup: status, configure, push, sync, fetch, evict, files |
| `youtube.py`    | (none)            | `/api/youtube*` OAuth connect and `/api/recordings/{rid}/youtube` upload |

## Interface

### `agent.py`

- `router` (prefix `/api`), `Bus`, `BUS` (module-level bus: `listeners`, `pending`, `state`, `state_at`)
- `DO_TIMEOUT_S = 15.0`, `STATE_KEYS`, `GUIDE` (path to `docs/AGENT_GUIDE.md`), `GROUPS`, `GROUP_ORDER`, `MONTHS`
- Models: `WebCatalog`, `DoIn`, `ResultIn`, `MetaIn`
- Routes: `library` (GET `/api/library`, filters `kind`, `q`, `group`, `tag`), `name_artifact` (PATCH `/api/library/{aid}`), `artifact` (GET `/api/library/{aid}`), `publish` (POST `/api/library/web`, 204), `stream` (GET `/api/agent/stream`, Server-Sent Events), `do` (POST `/api/agent/do`), `result` (POST `/api/agent/result/{cid}`, 204), `state` (GET `/api/agent/state`), `timeline` (GET `/api/agent/timeline`), `guide` (GET `/api/agent/guide`), `post_state` (POST `/api/agent/state`, 204)
- Helpers: `_take_name`, `_storage`, `_server_artifacts`, `_decorate`, `_web_path`

### `episodes.py`

- `router` (prefix `/api/episodes`), `TOKEN_TTL_S = 600`
- Models: `ApproveBudgetIn` (`confirm_token`), `PublishIn` (`publish_at`, refused with 422 until Stage 2); the body of `create` and `put_script` is `episode.contract.Script`
- Routes: `create` (POST ``, 201; 503 `{missing}` when `episode.preflight.check` fails, 422 `{errors}` from the validator), `list_episodes` (GET ``), `get_episode` (GET `/{eid}`, a pure read of the `EpisodeOut` shape: the record without `budget.confirm_token` plus `progress`, `validation`, `next_action`, `last_log`), `put_script` (PUT `/{eid}/script`), `approve_script` (POST `/{eid}/approve-script`), `estimate` (GET `/{eid}/estimate`, issues the one-time token), `approve_budget` (POST `/{eid}/approve-budget`), `publish` (POST `/{eid}/publish`), `advance` (POST `/{eid}/advance`, 202), `purge` (POST `/{eid}/purge`, 202)
- Helpers: `_episode`, `_out`, `_live`, `_enqueue_planner`, `_lines` (one estimate line per distinct clip key and take), `_estimate`

### `heygen.py`

- `router` (prefix `/api/heygen`), `KEY_OK`, `ID_OK`, `GESTURE_OK`
- Models: `ConfigIn`, `Item` (`kind: "segment" | "gesture"`, `take: int = 0`), `RenderIn` (`items`, `confirm: bool = False`)
- Routes: `get_config` (GET `/config`), `put_config` (PUT `/config`), `account` (GET `/account`), `looks` (GET `/looks`), `render` (POST `/render`; the response carries `seconds`, `usd`, `clips`, `with_motion` from `core.heygen.estimate`)
- Helpers: `_public`, `_client`, `_transport` (reads `worker.handlers.HEYGEN_TRANSPORT`)

### `jobs.py`

- `router` (prefix `/api/jobs`), `JobIn`
- Routes: `list_jobs` (GET ``), `create_job` (POST ``, 201), `get_job` (GET `/{jid}`), `cancel` (POST `/{jid}/cancel`)

### `live.py`

- `router` (prefix `/api/live`), `YOUTUBE` (default RTMP URL), `URL_OK`, `KEY_OK`
- `LiveConfig`, `LiveState` (`proc`, `started`, `bytes`, `error`, `status()`), `STATE` (module-level `LiveState`)
- `load_config(s)`, `ffmpeg_cmd(s, target)`
- Routes: `get_config` (GET `/config`), `put_config` (PUT `/config`), `status` (GET ``), `ingest` (WebSocket `/ws`)

### `projects.py`

- `router` (prefix `/api/projects`), models `ProjectIn`, `EDLSave` (`base_version`, `edl: EDL`, `message`), `ImportPath`
- Routes: `list_projects`, `create_project` (201), `get_project`, `rename_project` (PATCH), `delete_project` (204), `get_edl` (GET `/{pid}/edl`), `save_edl` (PUT `/{pid}/edl`), `edl_versions` (GET `/{pid}/edl/versions`), `import_path` (POST `/{pid}/assets/import-path`, 201)

### `recordings.py`

- `router` (prefix `/api/recordings`), `REC_ID`, `MAX_BYTES` (16 GiB), `EXT` (content-type to extension)
- `_dir(s)`, `_check(rid)` (also imported by `youtube.py`)
- Routes: `upload` (POST ``, 201, raw body), `list_recordings` (GET ``; takes found through `rec_*.source.*` plus episodes registered by the factory found through `rec_*.episode.json`, each with `episode: <id>` and `source_bytes: null`, merged and sorted by id descending), `download` (GET `/{rid}.mp4`), `queue_transcript` (POST `/{rid}/transcribe`, 202), `get_transcript` (GET `/{rid}/transcript`), `get_captions` (GET `/{rid}.srt`)

### `scenes.py`

- `router` (prefix `/api/scenes`), `SCENE_ID`, `MAX_SCENE_BYTES = 256_000`, `SceneIn`
- Routes: `list_scenes` (GET ``), `put_scene` (PUT `/{sid}`), `delete_scene` (DELETE `/{sid}`, 204)

### `system.py`

- `router` (prefix `/api`), `ROOT` (repo checkout), `STARTUP_REV`, `_git_head`
- Routes: `health` (GET `/api/health`), `edl_schema` (GET `/api/edl/schema`)
- `health.tools` carries, besides `ffmpeg`, `ffprobe`, `ollama`, `yt-dlp` and `whisper`, the episode factory's `opencv`, `rembg`, `playwright_chromium`, `hyperframes`, `fonts`, `intro`, `plate`, `music_manifest`, `haar_cascade` (a version, a path, a flag or `null`) from `episode.preflight.tools`; `preflight_ok` and `missing` come from `episode.preflight.check(s)` (Stage 1 needs)

### `vault.py`

- `router` (prefix `/api/vault`), `VaultIn` (`kind: "s3" | "folder" | "off"`, …), `KeyIn`
- Routes: `status` (GET ``), `configure` (PUT ``), `push` (POST `/push`, 202), `sync` (POST `/sync`), `fetch` (POST `/fetch`), `evict` (POST `/evict`), `files` (GET `/files`)

### `youtube.py`

- `router` (no prefix), `DOWNLOADS` (`Path.home() / "Downloads"`), `DisconnectIn`, `UploadIn` (`privacy` defaults to `"private"`)
- Routes: `get_status` (GET `/api/youtube`), `import_client` (POST `/api/youtube/client`), `connect` (GET `/api/youtube/connect`, 302), `callback` (GET `/api/youtube/callback`, HTML), `disconnect` (POST `/api/youtube/disconnect`), `queue_upload` (POST `/api/recordings/{rid}/youtube`, 202)

## Invariants

- `[episodes.py:approve_budget]` is the only route that leads to HeyGen spending. It needs the one-time `confirm_token` from `[episodes.py:estimate]` (ten-minute expiry, cleared on use), an `Origin` header that is present and passes `core.netguard.origin_allowed(origin, s.extra_hosts)` (403 otherwise), the episode in `script_approved` (409), one resolvable YouTube channel (`core.youtube.pick_channel`, 409), and the month's total after this episode's estimate and allowance at or under `heygen_month_ceiling_usd` (409). The check, the ledger reservation, the release of any previous reservation and the status change share one `tx`, so two approvals cannot both pass against the same balance.
- `[episodes.py:_lines]` reserves one line per distinct (clip key, take): every live `heygen_clip` job under its own key, plus every scene with no clip and no live job for its current key.
- `[episodes.py:put_script]` is refused (409) outside `episode.record.EDITABLE` or while `outputs.upload_job_id` is queued or running; when the script hash changes it unlinks `final.mp4`, `final.srt`, `kit.json` and `final.cues.json` and clears `outputs.recording_id`, `final_mp4`, `final_srt`, `kit`.
- `[episodes.py:get_episode]` has no side effects. `[episodes.py:publish]` works from `uploaded_private` only and rejects `publish_at` with 422 until Stage 2. `[episodes.py:purge]` works from `published` or `cancelled` and reuses a queued `episode_purge` job.
- `[heygen.py:render]` Without `confirm: true` the response is an estimate only (`seconds`, `clips`, `with_motion`, `ready`, empty `jobs`); nothing is queued. With `confirm`, one `heygen_clip` job is enqueued per item whose MP4 does not already exist at `<assets_dir>/avatar/<clips|gestures>/<name>.mp4`; the item key comes from `core.heygen.item_key`. Requires a saved API key and `avatar_id` (400 otherwise).
- `[heygen.py:_public]` The API key is only ever returned masked (`core.heygen.mask`). `[heygen.py:put_config]` validates keys with `KEY_OK` and ids with `ID_OK` (422 on mismatch).
- `[agent.py:do]` 409 when no editor is connected (`BUS.listeners` empty); only the first listener receives the action; 504 after `DO_TIMEOUT_S`; a result with `ok: false` becomes 422. The pending future is always removed from `BUS.pending`.
- `[agent.py:post_state]` Only keys in `STATE_KEYS` are stored; `[agent.py:state]` omits `timeline`; `[agent.py:timeline]` is 404 until the editor has posted one.
- `[agent.py:library]` Scene artifacts in `library-web.json` are dropped in favour of the server's `scenes` table; `[agent.py:name_artifact]` returns 404 for unknown ids and an empty title restores the default name.
- `[live.py:ingest]` One broadcast at a time: the socket is closed with code 4409 when `STATE.proc` is still running, and 4400 when no stream key is saved. `[live.py:LiveState]` is module-level state. The stream key is replaced by `••••` in any stored ffmpeg error, and `[live.py:get_config]` returns it masked.
- `[live.py:put_config]` The URL must match `URL_OK` (`rtmp://` or `rtmps://`) and a non-empty key must match `KEY_OK`; a missing `stream_key` keeps the saved one.
- `[recordings.py:_check]` Recording ids must match `REC_ID`. `[recordings.py:upload]` rejects content types outside `EXT` (415), bodies above `MAX_BYTES` (413, partial file removed) and empty bodies (400); the id is `rec_YYYYmmdd-HHMMSS` with a hex suffix on collision.
- `[recordings.py:queue_transcript]` and `[youtube.py:queue_upload]` reuse a queued or running job (`core.store.find_active_job`) instead of enqueueing a duplicate; both require `<rid>.mp4` to exist (404). `queue_transcript` returns 503 when whisper is not installed.
- `[scenes.py:put_scene]` is an idempotent upsert on `scenes.id`; `id`, `name`, `collection`, `position` are stripped from `data`; a blob over `MAX_SCENE_BYTES` is 413. `[scenes.py:delete_scene]` returns 204 whether or not the scene existed.
- `[projects.py:import_path]` The path must resolve inside `Settings.allowed_import_roots()` via `core.paths.resolve_in_any` (400 otherwise), be a file, and have a kind from `core.media.kind_for`. `[projects.py:save_edl]` maps `core.store.VersionConflict` to 409.
- `[jobs.py:create_job]` The kind must be registered in `worker.handlers.HANDLERS` (400). `[jobs.py:cancel]` is 409 unless the job is queued or running.
- `[vault.py:configure]` The backend is probed (`be.list` on the `catalog/` prefix) before the config is saved (422 on failure); blank s3 keys keep the previously saved ones; `kind: "off"` clears the config. `[vault.py:evict]` refuses `.json` keys (422) and removes the local file only after `be.head` reports the same sha256 (409 otherwise). `[vault.py:fetch]` accepts only keys that `core.vault.local_path` recognises (422).
- `[youtube.py:_redirect_uri]` The OAuth redirect is fixed to `http://127.0.0.1:{port}/api/youtube/callback`. `[youtube.py:queue_upload]` is 409 when no channel is connected and resolves the channel with `core.youtube.pick_channel`; metadata is normalised by `core.youtube.clean_meta` (422 on error).
- `[system.py:STARTUP_REV]` is read once at import; `[system.py:health]` reports `stale: true` when the checkout's current `HEAD` differs from it.

## Side Effects

- `[agent.py:publish]` writes `<data_dir>/library-web.json` (creating `data_dir`). `[agent.py:name_artifact]` upserts `artifact_meta`. `[agent.py:stream]` keeps an SSE response open (keep-alive comment every 15 s) and adds/removes a queue in `BUS.listeners`. `[agent.py:do]` puts a message on one listener's queue. `[agent.py:post_state]` replaces `BUS.state`. `[agent.py:guide]` reads `docs/AGENT_GUIDE.md`.
- `[episodes.py:create]` inserts a `projects` row and an `episodes` row and creates `<episodes_dir>/<id>/`. `[episodes.py:approve_budget]` writes `heygen_ledger` rows and enqueues `episode_advance`; `[episodes.py:advance]` enqueues `episode_advance`; `[episodes.py:purge]` enqueues `episode_purge`. `[episodes.py:estimate]` calls HeyGen's `/v3/users/me` for the wallet balance when a key is saved (free; `null` on failure). `[episodes.py:publish]` calls YouTube `videos.update` through `episode.publish.publish` (502 on `YouTubeError`).
- `[heygen.py:put_config]` writes `<data_dir>/heygen.json` through `core.heygen.save_config`. `[heygen.py:account]` and `[heygen.py:looks]` call `api.heygen.com` through `core.heygen.Client` (502 on `HeyGenError`). `[heygen.py:render]` inserts `heygen_clip` rows in `jobs` inside one transaction; the paid call itself happens in the worker.
- `[live.py:put_config]` writes `<data_dir>/live.json` with mode `0600` via a temp file and rename. `[live.py:ingest]` starts an `ffmpeg` subprocess (`ffmpeg_cmd`, VideoToolbox when `core.media.hw_encoders` lists it) that pushes RTMP to `<rtmp_url>/<stream_key>` (or `app.state.live_target_override`), pipes WebSocket bytes into it, and kills it after 15 s if it does not exit.
- `[recordings.py:upload]` streams the body to `<recordings_dir>/<rid>.source.<ext>.part`, renames it, opens its own `sqlite3` connection and enqueues `finish_recording`. `[recordings.py:download]` calls `core.vault.fetch` to pull a missing MP4 from the vault (502 on `VaultError`). `[recordings.py:_dir]` creates `recordings_dir`.
- `[projects.py:import_path]` inserts an `assets` row and a `probe` job. `[projects.py:create_project]`, `rename_project`, `delete_project` write `projects` (and, by schema cascade, `assets`, `edl_versions`, `jobs`).
- `[scenes.py:put_scene]` and `[scenes.py:delete_scene]` write the `scenes` table.
- `[system.py:_git_head]` runs `git -C <ROOT> rev-parse HEAD` (3 s timeout). `[system.py:health]` runs `ffmpeg`/`ffprobe -version`, `ffmpeg -encoders`, `shutil.which`, `shutil.disk_usage(data_dir)`, two `COUNT(*)` queries on `jobs`, and `episode.preflight` (path checks and `importlib.util.find_spec`; nothing heavy is imported).
- `[vault.py:configure]` writes `<data_dir>/vault.json`, may `mkdir` the folder backend root, and performs one network or filesystem list. `[vault.py:push]` enqueues `vault_push` via `worker.handlers.queue_vault_push`. `[vault.py:sync]` lists the remote, pulls `catalog/catalog.json`, and inserts missing `scenes`, `artifact_meta` and `vault_objects` rows. `[vault.py:fetch]` downloads a file into `assets_dir` or `recordings_dir`. `[vault.py:evict]` unlinks a local file and updates `vault_objects`. `[vault.py:files]` lists the remote.
- `[youtube.py:import_client]` moves the newest `client_secret_*.json` out of `DOWNLOADS` into `<data_dir>/youtube/client.json`. `[youtube.py:connect]` writes `<data_dir>/youtube/pending.json` and redirects to Google. `[youtube.py:callback]` exchanges the code with Google and writes `<data_dir>/youtube/channels/<UC…>.json`. `[youtube.py:disconnect]` unlinks a channel file. `[youtube.py:queue_upload]` enqueues `youtube_upload`.

## Verification

- Run: `cd server && .venv/bin/python -m pytest`
- Lint: `cd server && .venv/bin/ruff check src tests`
