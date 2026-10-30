# StreamStudio — Build Plan

> The YouTube video editing studio. Local-first, AI-assisted, built for the Mac Studio.
> Raw footage or stream VODs go in. Edited long-forms, Shorts, captions, thumbnails and an uploaded YouTube video come out.

## 1. What it is (and isn't)

**Is:** an *editing* studio. It takes footage you already have (camera recordings, OBS captures, Twitch/YouTube live VODs, AI clips from YouTubePipeline), then cuts, captions, reframes, renders and publishes it.

**Isn't:** a generator. Script, voice and image/video *generation* stay in YouTubePipeline. StreamStudio can import that pipeline's output as its source footage.

**Core idea:** edit video by editing text. Every source is transcribed with word-level timestamps, so deleting words in the transcript deletes them from the video. A timeline is there for precise work, and AI does the boring cuts.

## 2. Architecture

```
apps/web      React + Vite + TypeScript: library, transcript editor, timeline, player, publish
apps/api      FastAPI (Python 3.12): projects, media, jobs, EDL, YouTube OAuth
apps/worker   Python job worker: ffmpeg, transcription, analysis, render
packages/edl  The Edit Decision List schema (JSON Schema → TS types + Pydantic models)
data/         Projects on disk: sources/, proxies/, cache/, renders/ (git-ignored)
```

- **Single source of truth = EDL JSON.** The UI edits the EDL, and the renderer compiles the EDL into one ffmpeg filtergraph. There are no hidden states, so every edit can be diffed, undone and versioned.
- **Storage:** SQLite (projects, assets, jobs, versions) plus plain folders. No Docker and no cloud required.
- **Jobs:** a SQLite-backed queue with a worker pool, progress over WebSocket, and jobs that resume after a crash.
- **Hardware:** VideoToolbox encode (`h264_videotoolbox`/`hevc_videotoolbox`), MLX for Whisper on Apple Silicon.
- **Remote access (optional):** the API binds to the Tailscale interface, so the UI works from a laptop or phone on the tailnet.

### AI / media stack (all local unless noted)
| Job | Tool |
|---|---|
| Transcription + word timestamps | `mlx-whisper` (large-v3-turbo), with a `faster-whisper` fallback |
| Speaker labels | `pyannote` (optional) |
| Silence / VAD | Silero VAD + ffmpeg `silencedetect` |
| Filler words ("um", "deci", "păi") | transcript rules, EN + RO |
| Highlight / clip scoring | Ollama (qwen/llama) over transcript + audio energy + chat spikes |
| Titles, description, chapters, tags | Ollama |
| Face tracking for 9:16 reframe | MediaPipe face detection + smoothed crop path |
| Loudness | ffmpeg `loudnorm` two-pass → −14 LUFS |
| Thumbnails | frame picker + text templates; Higgsfield optional (paid, opt-in) |
| Upload | YouTube Data API v3 (OAuth, resumable upload) |

**Paid-API rule:** nothing paid runs without an explicit click and a cost estimate shown first.

## 3. Milestones

Each milestone ends runnable, tested and committed.

**M0 — Foundation**
Monorepo layout, `make dev` (api + worker + web), CLAUDE.md, EDL schema v1, lint/format, pytest + vitest, GitHub Actions CI, and a tiny fixture clip set for golden tests.

**M1 — Ingest & media library**
Drag-drop or local-path import, plus URL import for your own VODs (yt-dlp). ffprobe metadata, 720p proxy generation, waveform peaks, thumbnail filmstrip, project and library pages.

**M2 — Transcript & text-based editing**
Word-level transcription job and a transcript editor. Select words, delete, and the cut appears in the EDL. Search the transcript, add speaker labels, play from the clicked word.

**M3 — Auto rough cut**
Silence removal with a tightness slider, filler-word removal (EN/RO), and retake detection that keeps the last take of repeated sentences. Every auto-cut is reviewable and reversible.

**M4 — Timeline editor & preview**
Multi-track timeline (main video, B-roll, overlays, music, captions), trim/split/ripple/J-L cuts, snapping, undo/redo, keyboard shortcuts (J/K/L, I/O), and a frame-accurate proxy preview player that plays the EDL.

**M5 — Captions & branding**
Animated word-level captions (ASS: karaoke highlight, pop, bounce), style presets, a brand kit (fonts, colors, logo, intro/outro, lower thirds), SRT/VTT export.

**M6 — Clips & Shorts factory**
Highlight detection that ranks the best 20–60 s moments from a long VOD, optionally weighted by stream chat activity. Auto 9:16 reframe with face tracking, hook-title overlay, and batch export of N Shorts in one click.

**M7 — Render engine**
EDL → ffmpeg compiler, render queue, presets (YouTube 4K/1080p, Shorts 1080×1920), VideoToolbox encode, two-pass loudnorm, chapter-marker embed. Golden-file tests compare rendered frames and audio.

**M8 — Publish**
Thumbnail studio, AI title/description/chapters/tags (editable), YouTube OAuth, upload, schedule, playlist, publish-history log.

**M9 — Integrations & agents**
REST API + MCP server so your agents (Paperclip) can drive edits: "cut last night's stream into 5 Shorts". Import from YouTubePipeline. Watch-folder auto-ingest for OBS recordings.

## 4. Quality bar
- Every job is idempotent and resumable, and every edit is versioned.
- Unit tests for EDL ops and the ffmpeg compiler, plus golden render tests on fixture clips.
- Path-safety on all file access, and the API is localhost/tailnet only by default.
- A 2-hour VOD should transcribe and produce clip candidates in about 10 minutes on the Mac Studio (target; to be measured).

## 5. Decisions (locked 2026-10-30)
1. **Focus:** long-form and Shorts equally. Build M0 → M9 in order.
2. **Hosting:** runs on the Mac Studio; the API/UI binds to localhost and the Tailscale interface, so it is reachable from other tailnet devices. No public exposure.
3. **YouTubePipeline:** StreamStudio is standalone. Import from YouTubePipeline arrives in M9.
