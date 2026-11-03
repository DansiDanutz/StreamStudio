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

## System Overview

Three processes and one browser app, all local to the Mac Studio:

```
 Browser: web/ (React editor, Program window, render view)
   │  HTTP + WebSocket /api, SSE /api/agent/stream
   ▼
 server/ FastAPI (streamstudio.api)  ──SQLite jobs table──▶  server/ worker (streamstudio.worker)
   │  reads/writes DATA_DIR, assets/, recordings                │  ffmpeg, whisper-cli, rembg
   │  ffmpeg RTMP push for live                                 │  HeyGen API (paid, confirmed first)
   └── serves web/dist and assets/ in production                └── YouTube upload, vault push
 server/ MCP server (streamstudio.mcp, stdio) ──▶ the API above, for agents
 server episode worker: script approval → per-scene QA and composition → Library
 mac/: launcher app that clones, builds, starts and opens the studio
```

The editor keeps the script as the master clock: the director store in `web/src/director` tweens the
cards per cue and enforces the lip-sync guard; the same guard exists server-side in
`server/src/streamstudio/render/lipsync.py` for offline renders. Long jobs (recording finish, transcripts,
HeyGen renders, YouTube uploads, vault pushes) are queued and only the worker executes them. Some work still
runs inside an API request: a vault fetch (`POST /api/vault/fetch`, or a missing recording or avatar asset
fetched on download) transfers the whole file before responding, and the live WebSocket feeds ffmpeg for
the length of the broadcast. Agents reach the editor through the server's agent bus
(`/api/agent/*`) and the MCP server.

## Subdirectories & System Boundaries

- server: [./server/README.md](./server/README.md) - Python 3.12 backend: FastAPI API, SQLite, job worker,
  EDL model, offline media tools, MCP server. Package contract in
  [./server/src/streamstudio/README.md](./server/src/streamstudio/README.md).
- web: [./web/README.md](./web/README.md) - React 19 + Vite + TypeScript editor, Program window and render
  view; module contracts under [./web/src/README.md](./web/src/README.md).
- [Production utilities](./tools/README.md) support independent card previews, the DansLab tour, and brand generation. The episode worker assembles videos for the Library.
- mac: [./mac/README.md](./mac/README.md) - the StreamStudio.app launcher and its icon script.
- assets: studio plates, brand files, avatar and object clips served at the web root (`/studio`, `/avatar`,
  `/objects`, `/brand`). No code.
- docs: design reference (`DESIGN.md`), agent guides (`AGENTS.md`, `AGENT_GUIDE.md`), prompts, scripts, the
  HTML mock, and [./docs/egm/README.md](./docs/egm/README.md) for EGM design briefs and reviews. No code.

## Global Invariants

- **Lip-sync guard.** The presenter's face may be large only while the voice is the clip's own lip-synced
  audio. Editor: `web/src/director/types.ts:lipsMatch` / `guardCue` and `cueLayouts.ts:guardLayout`,
  applied in `store.ts:play`; agents go through `web/src/agent/bridge.ts:'cue.apply'` with the guard on.
  Offline: `server/src/streamstudio/render/lipsync.py:lips_match` / `guard_cue`, `MAX_UNSYNCED_AREA = 0.06`
  in both copies.
- **Card geometry is fractional.** Every card rect is a fraction of the Base card
  (`web/src/stage/types.ts`); `Stage.tsx` sizes cards in `%` and sets `1em` to about 1% of the long edge.
- **The Menu card is transparent in the output by default** (`Scene.menuShown` false in every preset but
  `app-menu`; `Stage.tsx` renders it as a ghost in the editor).
- **Network guard.** The API answers only loopback and, when `ALLOW_TAILNET`, the Tailscale ranges, and
  checks `Host` and `Origin` (`server/src/streamstudio/core/netguard.py:NetGuardMiddleware`).
- **Path safety.** User-supplied paths resolve through `core/paths.py` (`resolve_within`, `resolve_in_any`)
  and the SPA handler only serves files inside `web/dist` or `assets/`.
- **Jobs are idempotent and worker-only.** Queued jobs run only in the worker; `worker/handlers.py` handlers
  check their own output before working, and `store.find_active_job` prevents duplicate transcript and
  upload jobs. Vault fetches and the live ingest are the request-time exceptions named above.
- **Paid APIs need an explicit confirm.** HeyGen renders run only with `confirm: true` after the estimate
  (`api/routes/heygen.py:render`, `HeygenPanel.tsx`); the MCP server never sends `confirm` and always
  uploads to YouTube as `private` (`streamstudio/mcp.py:call`).
- **Secrets stay masked.** HeyGen, live and vault configs are written `0600` and returned masked.

## Global Side Effects

- SQLite database and `projects/`, `recordings/` under `DATA_DIR` (`core/config.py`, `core/db.py`).
- Files written beside the repo: `assets/avatar/{clips,gestures}` (HeyGen downloads and cut-outs),
  `<data_dir>/{heygen,live,vault,youtube}.json` and `youtube/` tokens, `library-web.json`, `catalog.json`.
- Subprocesses: `ffmpeg`/`ffprobe` (API health, live push, worker, offline tools), `whisper-cli`, `git`
  (health rev), Playwright Chromium (`render/preview.py`), `npx hyperframes` (`tools/compose/motion`).
- External services: HeyGen (`api.heygen.com`, spends credits), Google OAuth and YouTube upload, an S3
  endpoint or a synced folder for the vault, RTMP to YouTube Live. Browser-side: `getDisplayMedia`,
  `getUserMedia`, `localStorage` keys `streamstudio.*`.

## System Verification

- Run: `make test` (server pytest + web vitest)
- Lint: `make lint` (ruff, tsc, oxlint)
