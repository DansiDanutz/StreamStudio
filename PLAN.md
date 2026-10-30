# StreamStudio — Build Plan (v2, stage-first)

> A browser-based recording and live-streaming studio for YouTube, built around one card layout.
> It runs on the Mac Studio and is reachable from other devices on the tailnet.
> Everything that happens inside the Base card is recorded to MP4 and streamed live to YouTube.
> The recordings then flow into AI editing: transcript, rough cut, captions, Shorts and upload.

## 1. The structure

```
LANDSCAPE 16:9 (default)                      PORTRAIT 9:16 (toggle)
┌────────────────────────────────────────┐    ┌──────────────────┐
│ BASE CARD  = the video frame + margins │    │ BASE CARD        │
│ ┌───────────────────────────┐ ┌──────┐ │    │ ┌──────────────┐ │
│ │                           │ │ MENU │ │    │ │  MAIN CARD   │ │
│ │        MAIN CARD          │ │ ▸ A  │ │    │ │              │ │
│ │  screen · window · tab    │ │ ▸ B  │ │    │ └──────────────┘ │
│ │  file · URL · camera      │ │  ├ b1│ │    │ ┌──────┐ ┌─────┐ │
│ │                           │ ├──────┤ │    │ │AVATAR│ │MENU │ │
│ │                           │ │AVATAR│ │    │ └──────┘ └─────┘ │
│ └───────────────────────────┘ └──────┘ │    └──────────────────┘
└────────────────────────────────────────┘
```

| Card | What it is |
|---|---|
| **Base card** | The output frame: 1920×1080 by default, or 1080×1920 in portrait. It has margins and safe-area guides, plus a background (color, gradient or image). Everything inside it is recorded and streamed; nothing outside it is. |
| **Main card** | What we capture. Sources: screen, window or tab share; video or image file; web page URL; second camera. It can switch between sources live. |
| **Avatar card** | Dan's AI avatar, driven by his live voice. The mic moves the mouth, it blinks and idles, and the background is transparent. |
| **Menu card** | Options with submenus that control the stage. It is **transparent by default**: it takes up space and responds to clicks and hotkeys, but is not drawn into the output. **Toggle on** and it is drawn into the video for viewers. |

The cards can be dragged and resized with snap-to-grid, and z-order can be changed. Layouts are saved per orientation and switched live as **scenes**, with animated transitions.

## 2. How it works

```
 Browser (stage UI)                                   Mac Studio
 ┌──────────────────────────────────────┐            ┌────────────────────────────┐
 │ Sources ─► Compositor (WebGL canvas) │  WebSocket │ FastAPI ─► ffmpeg          │
 │ screen/cam/file/URL  draws cards at  │ ─────────► │  h264_videotoolbox + AAC   │
 │ avatar renderer      30/60 fps       │  media     │  tee ─► MP4 file (archive) │
 │ menu (when ON)       + WebAudio mix  │  chunks    │      └► RTMP ► YouTube Live│
 └──────────────────────────────────────┘            └────────────────────────────┘
```

- **Compositor:** a single canvas at output resolution. Each card is drawn from its source every frame. The editable DOM cards sit on top of the canvas at the same positions. That is how the Menu can be clickable while invisible in the output.
- **Audio:** a WebAudio mixer combines the mic (with noise suppression), tab or system audio, and file audio. It has per-source gain, meters, and music ducking under the voice.
- **Output:** `canvas.captureStream()` plus the mixed audio go to MediaRecorder. Chunks travel over WebSocket to the backend, where one ffmpeg process encodes on VideoToolbox and **tees** the stream: an MP4 recording and an RTMP push to YouTube at the same time. A local backup recording also runs in the browser, so a network blip doesn't lose the take.
- **YouTube Live:** the Live Streaming API creates the broadcast and stream key, sets the title and description, then goes live and ends the broadcast from the Menu.
- **Web page URL source:** browsers can't paint a cross-origin iframe into a canvas. A URL therefore opens in a headless Chromium (Playwright) on the Mac Studio, which is streamed into the Main card. Tab-share is the quick fallback.
- **Avatar:** rendered in the browser in real time, locally and free.
  - Stage 1: a layered 2D avatar (Dan's artwork) with mouth shapes (visemes) driven by mic audio, plus blinking and idle motion.
  - Stage 2: an optional 3D VRM avatar, with webcam face tracking (MediaPipe) driving head, eyes and expressions while the mic drives the mouth.
  - A photoreal AI avatar (Higgsfield/HeyGen) can replace the avatar in post-production. It is opt-in, paid, and the cost is shown first.
- **Backend:** FastAPI + SQLite + a job worker (already started on branch `m0-foundation`). It stores projects, layouts, scenes, recordings and jobs, and runs ffmpeg and the post-production jobs.

## 3. Milestones

Each milestone ends runnable, tested and committed.

**S0 — Foundation**
Monorepo (`server/` Python, `web/` React + Vite + TS) and `make dev`, which runs the API, worker and web together. CI, tests, and the net guard so only localhost and tailnet can reach the app.

**S1 — Stage & cards**
Base card with a landscape/portrait toggle, margins and safe-area guides, and a background. Main, Avatar and Menu cards with drag, resize, snap and z-order. Layouts saved per orientation, scenes, and hotkeys.

**S2 — Main card sources**
Screen, window and tab share; camera; video and image files; web page URL (headless Chromium on the Mac). Live source switching, crop/fit/fill, and rounded corners and borders.

**S3 — Director (script-driven stage)** ← the core
The script is the master clock. It is split into segments; each segment carries the spoken text, its avatar clip (voice), the visual to show in the Main card, and a **cue**: `avatar` (presenter full), `split` (presenter + content), `content` (content maximized, presenter minimized), `full` (content fills the frame, presenter hidden), with an optional **zoom** target inside the Main card. **Auto-direct** proposes the cues from the text (rules first, Ollama later): talking to the audience → avatar; "look at this / on screen / here" → content; "this button / in the corner" → zoom; intro and outro → avatar full. Playback tweens the cards between layouts, switches and zooms the Main source, and plays the avatar clip with its audio as the voice; a segment ends when its clip ends, so image, voice and layout never drift. Dan can override any cue live, and the Menu card exposes the same cues as buttons and hotkeys.

**S3b — Menu card**
Transparent by default, with a toggle to show it in the output (button and hotkey, with fade). Submenus control sources, scenes, orientation, avatar, record and live, and mic. The menu's look when it is visible is styled to match the brand.

**S4 — Avatar card**
A mic-driven 2D avatar: visemes, blink, idle and emotion presets. Then a VRM 3D avatar with webcam face tracking. Transparent background and an avatar asset manager.

**S5 — Audio mixer**
Mic with noise suppression, tab or system audio, and file audio. Per-source gain and mute, level meters, ducking, and a loudness target.

**S6 — Record + Live**
Compositor → MediaRecorder → WebSocket → ffmpeg tee (MP4 + RTMP), with a local backup recording. YouTube OAuth and the Live API to create, go live and end broadcasts. A live health panel shows bitrate, dropped frames and stream status.

**S7 — Post-production**
Every recording becomes a project: word-level transcript, text-based editing, silence and filler removal (EN/RO), animated captions, Shorts (highlight ranking + 9:16 export), thumbnails, AI title, description and chapters, and upload.

**S8 — Agents**
REST + MCP API so Paperclip agents can switch scenes, start and stop recording, and run post-production.

## 4. Quality bar
- Recording must survive network or tab hiccups: chunked uploads, a local backup copy, and a reconnecting stream.
- 1080p30 composite at a steady frame rate on the Mac Studio, with the 60 fps option measured in S1.
- Paid APIs only run on an explicit click, with the cost shown first. The avatar, recording and streaming are all local.
- Only localhost and tailnet can reach the app; path-safety applies to all file access.

## 5. Decisions (locked 2026-10-30)
1. **Stage-first:** card layout of Base → Main + Avatar + Menu, landscape by default and portrait optional.
2. **Menu card:** transparent by default; when toggled on it is drawn into the output.
3. **Main card sources:** screen/window/tab, file, URL, second camera — all of them.
4. **Avatar:** an AI avatar driven by Dan's live voice.
5. **Layout:** drag and resize, saved layouts and scenes.
6. **Output:** record and live-stream to YouTube at the same time, from the start.
7. **Hosting:** Mac Studio; localhost and tailnet only.
8. **YouTubePipeline:** StreamStudio is standalone, and import arrives later.
