# api

## Overview

The FastAPI application. `main.py` builds the app (`create_app`), wires the
network guard, mounts every router from `routes/`, and in production serves the
built web UI from `web/dist` and the repo's `assets/` folder. `deps.py` holds
the request-scoped dependencies shared by the routers. The console script
`streamstudio-api` (see `server/pyproject.toml`) points at `main:run`.

## Interface

- `main.create_app(settings: Settings | None = None) -> FastAPI`
- `main.run()` — starts uvicorn with `get_settings()`
- `main.REPO`, `main.WEB_DIST` (`<repo>/web/dist`), `main.REPO_ASSETS` (`<repo>/assets`)
- `main.spa` — catch-all `GET /{path:path}` registered only when `WEB_DIST` is a directory
- `deps.settings(request) -> Settings` — reads `request.app.state.settings`
- `deps.conn(request) -> Iterator[sqlite3.Connection]` — one connection per request, closed afterwards
- `deps.project_or_404(c, pid) -> dict`
- Subdirectory: [routes](./routes/README.md) — one router per resource

## Invariants

- `[main.py:create_app]` runs `Settings.ensure_dirs()` and `core.db.migrate` before the app is built, so every request sees the current schema.
- `[main.py:create_app]` adds `core.netguard.NetGuardMiddleware` with `allow_tailnet=s.allow_tailnet` and `extra_hosts=s.extra_hosts`; every HTTP request and WebSocket passes through it before any router.
- `[main.py:create_app]` mounts exactly these routers: `system`, `projects`, `jobs`, `scenes`, `recordings`, `live`, `heygen`, `agent`, `vault`, `youtube`, `episodes`.
- `[deps.py:project_or_404]` answers 404 for an episode's project row (`store.is_episode_project`), so no project route reaches `latest_edl` for a project without an EDL.
- `[main.py:spa]` A path equal to `api` or starting with `api/` is 404 and never falls back to `index.html`. A file is served only when its resolved path is a regular file inside `WEB_DIST` or `REPO_ASSETS` (`root in f.parents`).
- `[main.py:run]` binds `0.0.0.0` only when `allow_tailnet` is true and `host` is the default `127.0.0.1`; otherwise it binds `s.host`.
- `[deps.py:conn]` opens with `core.db.connect` and always closes the connection after the response.

## Side Effects

- `[main.py:create_app]` creates `projects_dir` and `recordings_dir` and applies SQLite migrations on `s.db_path`.
- `[main.py:spa]` for an `avatar/…` path not on disk, when `s.assets_dir == REPO_ASSETS`, calls `core.vault.fetch` to download the clip from the vault before serving it.
- `[main.py:run]` starts a uvicorn server process on `s.port`.

## Verification

- Run: `cd server && .venv/bin/python -m pytest`
- Lint: `cd server && .venv/bin/ruff check src tests`
