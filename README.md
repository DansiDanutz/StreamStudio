# StreamStudio

A browser-based recording and live-streaming studio for YouTube, built around one card layout:
**Base card** (the output frame) → **Main card** (what you capture) + **Avatar card** (you) + **Menu card**
(controls, transparent in the output unless toggled on). Runs on a Mac Studio, reachable over the tailnet.

See [PLAN.md](PLAN.md) for the milestones and [docs/DESIGN.md](docs/DESIGN.md) for the design reference.

## Run

```bash
make setup     # python venv (uv) + npm install
make dev       # api :8787, worker, web :5173
```

Production: `make build` then `make api`; FastAPI serves the built UI and `/assets` on :8787.

Config via env (`STREAMSTUDIO_*`): `DATA_DIR`, `IMPORT_ROOTS`, `PORT`, `ALLOW_TAILNET`.

## Status
S0 Foundation, S1 Stage & cards and the first S3 Director (script → cues → layout, zoom, auto-direct) are in. Next: S2 Main-card sources (screen/tab share, URL, camera) and avatar clips per segment.
