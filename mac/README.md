# StreamStudio for macOS

`StreamStudio.app` is a small launcher that shows up with your other apps (Launchpad, Spotlight, the Dock).

**Install:** `make mac-app` copies it to `~/Applications`. You can also drag it to the Dock.

**What it does when opened:**

1. The first time, it downloads StreamStudio into `~/StreamStudio/app`. Every time after, it updates it with `git pull`.
2. It sets up the server once per version: Python 3.12 via `uv`, which fetches Python itself, or via a Homebrew `python3.12`.
3. It builds the web app once per version, which needs `node`.
4. It starts the API and the worker in the background (`127.0.0.1:8787`, logs in `~/StreamStudioData/logs`).
5. It opens the studio in its own window: Chrome, Brave or Edge in app mode. Recording and going live need a Chromium browser.

**The server keeps running** when the window closes. Open the app again to get the window back. To stop the server, run `pkill -f streamstudio`.

**If something's missing,** the app says so in a dialog. The fixes:
- `brew install uv`
- `brew install node`

**The icon** is drawn by `mac/make_icon.py`.
