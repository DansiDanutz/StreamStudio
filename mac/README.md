# StreamStudio for macOS

## Overview

`StreamStudio.app` is a small launcher that shows up with your other apps (Launchpad, Spotlight, the Dock). The bundle holds one bash script (`StreamStudio.app/Contents/MacOS/StreamStudio`), an `Info.plist`, and the app icon. The icon is drawn by `mac/make_icon.py`.

**Install:** `make mac-app` copies it to `~/Applications`. You can also drag it to the Dock.

**What it does when opened:**

1. The first time, it downloads StreamStudio into `~/StreamStudio/app`. Every time after, it updates it with `git pull`.
2. It sets up the server once per version: Python 3.12 via `uv`, which fetches Python itself, or via a system `python3.12`, `python3.13` or `python3.14` (for example from Homebrew), installed with the `episode` extra (OpenCV, rembg, Playwright), then Playwright's Chromium (`playwright install chromium`, needed for site cards).
3. It builds the web app once per version, which needs `node`.
4. It starts the API and the worker in the background (`127.0.0.1:8787`, logs in `~/StreamStudioData/logs`).
5. It opens the studio in its own window: Chrome, Brave, Edge, Chromium or Arc in app mode. Recording and going live need a Chromium browser.

**The server keeps running** when the window closes. Open the app again to get the window back. To stop the server, run `pkill -f streamstudio`.

**Always the latest version.** Each start pulls the newest code. If a server is already running but is an older version, or was started from somewhere else (for example `make dev`), the app stops it and starts the current one from `~/StreamStudio/app`. `/api/health` reports `rev` and `root` so you can check which code is answering.

**If something's missing,** the app says so in a dialog. The fixes:
- `brew install uv`
- `brew install node`

**The icon** is drawn by `mac/make_icon.py`.

## Interface

- `StreamStudio.app/Contents/MacOS/StreamStudio` — the launcher. No arguments. Steps 1 to 5 above are numbered comments in the script. [MacOS/StreamStudio:top-level]
  - `STREAMSTUDIO_HOME` (environment, optional) — the checkout the launcher clones, pulls and runs from. Default `$HOME/StreamStudio/app`. [MacOS/StreamStudio:APPDIR]
  - Internal helpers: `say` (notification), `fail` (critical alert, then `exit 1`), `up` (health probe), `field <key>` (reads one key from `/api/health`), `stop_server`. [MacOS/StreamStudio:say, fail, up, field, stop_server]
- `make_icon.py` — `main()` draws the 1024 px icon and writes `AppIcon.png` and `AppIcon.icns` into `StreamStudio.app/Contents/Resources`. Helper `gradient(size, c1, c2, diagonal=True)`. Run: `python3 mac/make_icon.py`. Needs Pillow (`PIL`). [make_icon.py:main, gradient, OUT]
- `StreamStudio.app/Contents/Info.plist` — bundle identifier `live.danslab.streamstudio`, version `0.1.0`, executable `StreamStudio`, icon `AppIcon`, minimum macOS `12.0`. [Info.plist:CFBundleIdentifier, CFBundleExecutable, LSMinimumSystemVersion]
- Makefile target `mac-app` — copies the bundle to `~/Applications` and marks the launcher executable. [Makefile:mac-app]

## Invariants

- A server that already answers `/api/health` is kept only if its `root` equals `APPDIR` and its `rev` equals the checkout's `git rev-parse HEAD`; otherwise it is stopped and replaced. [MacOS/StreamStudio:CURRENT, stop_server]
- The Python venv is rebuilt when `server/.venv/.rev` differs from the current revision; the web build is redone when `web/dist/.rev` differs. Both files are written only after their step succeeds. [MacOS/StreamStudio:.venv/.rev, web/dist/.rev]
- `git pull --ff-only` failure is ignored, so an offline start runs the code already on disk. A failed first clone aborts the launcher. [MacOS/StreamStudio:git pull, git clone]
- The launcher polls up to 30 s (60 × 0.5 s) for the API to answer after starting it, and aborts if it does not. [MacOS/StreamStudio:up]
- The health values the launcher compares against are produced by the server's `health` route. [server/src/streamstudio/api/routes/system.py:health]

## Side Effects

- Clones or pulls `https://github.com/DansiDanutz/StreamStudio.git` into `APPDIR`. [MacOS/StreamStudio:REPO]
- Creates `~/StreamStudioData/logs` and `~/StreamStudioData/run`; appends to `setup.log`, `api.log`, `worker.log`; writes `api.pid` and `worker.pid`. [MacOS/StreamStudio:LOG, RUN]
- Creates `server/.venv` (via `uv` or `python -m venv` + `pip install -e ".[episode]"`), downloads Playwright's Chromium into `~/Library/Caches/ms-playwright`, and runs `npm ci` + `npm run build` in `web/`. [MacOS/StreamStudio:step 2, step 3]
- Kills processes: pids in `run/*.pid`, any listener on TCP 8787 whose command line contains `streamstudio`, and any `streamstudio.worker.main`. [MacOS/StreamStudio:stop_server]
- Starts `streamstudio.api.main` and `streamstudio.worker.main` with `nohup` in the background. [MacOS/StreamStudio:step 4]
- Prepends `/opt/homebrew/bin`, `/usr/local/bin`, `~/.local/bin`, `~/.cargo/bin` to `PATH` for the launcher's own process. [MacOS/StreamStudio:PATH]
- Shows macOS notifications and alerts through `osascript`. [MacOS/StreamStudio:say, fail]
- Opens a browser: a Chromium-based app in `--app` mode with its own profile under `~/StreamStudioData/window`, or the default browser. [MacOS/StreamStudio:step 5]
- `make_icon.py` writes `AppIcon.png` and `AppIcon.icns` into the bundle's `Resources` folder. [make_icon.py:OUT]

## Verification

- Run: `make test` (repository-wide; there are no tests specific to `mac/`)
- Install check: `make mac-app`, then open `~/Applications/StreamStudio.app`
