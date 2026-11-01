# StreamStudio

A browser-based recording and live-streaming studio for YouTube, built around one card layout:
**Base card** (the output frame) → **Main card** (what you capture) + **Avatar card** (you) + **Menu card**
(controls, transparent in the output unless toggled on). Runs on a Mac Studio, reachable over the tailnet.

See [PLAN.md](PLAN.md) for the milestones and [docs/DESIGN.md](docs/DESIGN.md) for the design reference.

## Run

```bash
make setup         # python venv from server/uv.lock + npm install
make setup-media   # optional: offline media tools (cut-out, dissolve, opener renders)
make dev           # api :8787, worker, web :5173
make test          # pytest + vitest
make lint          # ruff, tsc, oxlint
```

Production: `make build` then `make api`; FastAPI serves the built UI and `/assets` on :8787.
On the Mac, `make mac-app` installs StreamStudio.app, which starts everything and opens the editor.

Config via env (`STREAMSTUDIO_*`): `DATA_DIR`, `IMPORT_ROOTS`, `PORT`, `ALLOW_TAILNET`,
`EXTRA_HOSTS` (JSON list of extra host names the API answers to), `FFMPEG_BIN`, `WHISPER_BIN`,
`WHISPER_MODEL` (defaults to the best ggml model in `~/.local/share/whisper-models`).

Transcripts need whisper.cpp (`brew install whisper-cpp`) and a ggml model; `/api/health` shows
what was found.

## Status
Shipped: foundation, stage and cards, the Director (script → cues → layout, zoom, auto-direct),
media cards and scenes, avatar cut-out and gestures, HeyGen clips (cost estimate first, paid
renders only from the editor), the timeline, the library and vault, the Program window with
clean recording and Go live to YouTube, local transcripts and captions for takes, the publish
kit (title, description with chapters, SRT), and agent control over HTTP and MCP
([docs/AGENTS.md](docs/AGENTS.md)). The API only answers on loopback and the tailnet, checks
Host and Origin, and the editor warns when the running server is older than the checkout.

Next: YouTube upload (needs a Google OAuth client), per-agent permission scopes, a phone layout.
