# StreamStudio — notes for coding agents

Read `PLAN.md` (milestones, decisions) and `docs/DESIGN.md` (visual grammar, measurements) first.

## Layout
- `server/` Python 3.12, FastAPI + SQLite + job worker. `src/streamstudio/{api,core,edl,worker}`. Tests in `server/tests`.
- `web/` React 19 + Vite + TypeScript + zustand. The stage lives in `web/src/stage/`.
- `assets/` studio plates and avatar clips, served at the web root (`/studio/...`, `/avatar/...`) by Vite (publicDir) and by FastAPI in production.
- `docs/` design reference, prompts, the HTML mock.

## Rules
- Card geometry is in fractions of the Base card; inside `.base`, `1em` = 1% of the long edge. Never hard-code pixels in stage CSS.
- The Menu card is transparent in the output by default (`scene.menuShown=false`); the editor shows it as a dashed ghost.
- **Lip-sync guard (hard rule).** Dan's face may be large (full frame, or the big card of `duo`) ONLY while the voice is the clip's own lip-synced audio (`lipsMatch(seg)`: a clip, `voice !== 'narration'`). Any other voice (cloned, dubbed, a separate narration track, or none) puts the face in the small card: `pip` (circle by default, or 3:4 portrait), ≤6% of the frame. Enforced by `guardCue` + `guardLayout` in the Director's `play()` and by `render/lipsync.py` in offline renders. Never bypass it in scripts or renders; manual cue hotkeys are previews only.
- Every job handler is idempotent. Paid APIs never run without an explicit user action and a shown cost.
- API binds to localhost + Tailscale only (`core/netguard.py`). All request paths go through `core/paths.py`.
- Run `make test` and `make lint` before committing. `make dev` runs api + worker + web.
