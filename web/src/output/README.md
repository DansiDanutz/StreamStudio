# output

## Overview
The Program window and its link to the editor. The editor is the controller: it runs the director and posts its state over a `BroadcastChannel`; the Program window (`/?program=1`) mirrors that state into its own stores, renders a clean `Stage`, plays the sound, records itself (tab capture cropped to the Base card) and can stream the recording to the server for a YouTube live.

## Interface
- `link.ts`: `IS_PROGRAM`, `useProgram` (connected, recording, seconds, live), `startController()`, `startProgram(status)`, `openProgram(orientation)`.
- `recorder.ts`: `pickMime(can?, streamable?)`, `Take`, `Recorder` (`start(target, timeslice?, streamable?)`, `stop()`, `setTap(fn)`, `recording`, `seconds`, `cropped`), `uploadTake(take)`, `LiveLink` (`open()`, `send(blob)`, `close()`, `on`, `onEnd`).
- `ProgramView.tsx`: `ProgramView()`.
- `TakeTranscript.tsx`: `TakeTranscript({ id, ready? })`.

## Invariants
- Only the keys in `link.ts:STAGE_KEYS` and `DIRECTOR_KEYS` are mirrored; `startProgram` applies `state` messages with `useStage.setState` / `useDirector.setState` and never drives the director itself.
- `link.ts:startController` marks the Program disconnected after 5 s without a `hello` or `status` message, and on `bye`.
- `link.ts:IS_PROGRAM` is true only when the query string has `program=1`.
- `recorder.ts:pickMime` prefers WebM when `streamable` (needed for live and for the server's MP4 job) and MP4 otherwise.
- `recorder.ts:Recorder.setTap` replays the header chunk to a tap that joins mid-take; the first non-empty chunk is kept as the header.
- `ProgramView.tsx:goLive` always records too (starts the recorder with a 500 ms timeslice) and taps the chunks into `LiveLink`; `LiveLink.close` resolves on socket close or after 20 s.
- `LiveLink.onEnd` maps close codes: `4400` no stream key, `4409` already live elsewhere, `1000`/`1005` clean.

## Side Effects
- `BroadcastChannel('streamstudio.program')` messages (`hello`, `state`, `status` every 1 s, `bye` on `beforeunload`); `window.open('/?program=1', …)` in `openProgram`.
- `Recorder.start`: `navigator.mediaDevices.getDisplayMedia` with `preferCurrentTab`, `CropTarget.fromElement` + `track.cropTo` when available, `MediaRecorder` at 16 Mbps video / 192 kbps audio.
- HTTP: `POST /api/recordings` (`uploadTake`), `GET /api/recordings` polled every 2 s until the MP4 exists, `GET`/`PUT /api/live/config`, WebSocket `/api/live/ws` (`LiveLink`), `POST /api/recordings/{id}/transcribe` and `GET /api/jobs/{id}` every 2 s (`TakeTranscript`); links to `/api/recordings/{id}.mp4` and `.srt`.
- `ProgramView.tsx` adds `render-mode program-mode` to the document element, sets `document.title`, calls `requestFullscreen`, creates object URLs for the last take, and calls `loadGestureManifest()`.

## Verification
- Run: `cd web && npx vitest run`
