# director

## Overview
The script is the master clock. A `Script` is a list of `Segment`s, each with text, an optional lip-synced clip or narration track, a Main-card visual, a cue (layout), and optional scene, gesture, target, hotspot, sketch, table and media-card events. The director store plays the script: it tweens card geometry per cue, fires gestures and table events, and enforces the lip-sync guard. This directory also holds the cue layouts, the rule-based auto-direct, the pure timeline compiler, the ready-made workflows, and the Script, Timeline, Workflow and HeyGen panels.

## Interface
- `types.ts`: `Cue` (`avatar | duo | split | content | full | pip`), `AvatarShape`, `Zoom`, `Segment`, `Script`, `WORDS_PER_MIN` (150), `estimateMs(text)`, `newSegment(text?, cue?)`, `lipsMatch(seg)`, `guardCue(cue, seg)`, `MAX_UNSYNCED_AREA` (0.06), `MediaEvent`, `parseMediaEvents(src)`.
- `store.ts`: `useDirector` (zustand), `GestureOnAir`, `LiveLayouts`, `INTRO` (default script). Store actions: `setAvatarShape`, `doGesture`, `endGesture`, `markGestureMissing`, `targetRect`, `pointAt`, `pushSketch`, `tableEvent`, `setText`, `updateSegment`, `addSegment`, `insertSegments`, `removeSegment`, `runAutoDirect`, `applyCue(cue, zoom?, ms?, guard?, via?)`, `play(from?)`, `mediaEvent`, `preview(index)`, `stop`, `next`.
- `cueLayouts.ts`: `pipRect(orientation, shape?)`, `guardLayout(L, orientation, shape?)`, `layoutForCue(cue, saved, orientation, shape?)`, `isPipShaped(a, orientation)`.
- `autoDirect.ts`: `Proposal`, `propose(text, index, total)`, `autoDirect(script)`, `splitScript(text)`.
- `timeline.ts`: `TimelineItem`, `Timeline`, `clipDurations` (module-level `Map`), `compileTimeline(script, scenes, startScene?, cards?)`, `itemAt(tl, ms)`.
- `workflows.ts`: `WorkflowField`, `Workflow`, `WORKFLOWS` (`opener`, `browser`, `explain-card`, `compare`, `news`, `outro`), `workflowDefaults(w)`.
- Components: `ScriptPanel.tsx:ScriptPanel`, `TimelinePanel.tsx:Timeline`, `WorkflowPicker.tsx:WorkflowPicker`, `HeygenPanel.tsx:HeygenPanel`.

## Invariants
- Lip-sync guard (hard rule): `types.ts:lipsMatch(seg) = !!seg.clip && seg.voice !== 'narration'`. `types.ts:guardCue` degrades `avatar → pip` and `duo → content` when lips do not match. `cueLayouts.ts:guardLayout` moves any visible avatar whose area exceeds `MAX_UNSYNCED_AREA` into `pipRect`. `store.ts:play` computes `cue = guardCue(seg.cue, seg)` and `guard = !lipsMatch(seg)` and passes both to `applyCue`; `preview` and `setAvatarShape` (while playing) do the same. `applyCue` applies `guardLayout` only when its `guard` argument is true, so manual cue calls without it are previews.
- `cueLayouts.ts:layoutForCue('split')` returns the saved scene layout unchanged; the other cues are computed from it.
- `autoDirect.ts:autoDirect` leaves `pinned` segments untouched; `propose` scores by `RULES` weights, leans the first and last segments to `avatar`, and turns `avatar` into `duo` when screen content is referenced.
- `types.ts:parseMediaEvents` throws on a malformed event and when `move` has no position; `types.ts:estimateMs` is at least 1500 ms (150 words/min + 400 ms).
- `store.ts:doGesture` gives every gesture a new `seq` (never reused) and ends it after `g.ms + 2500` ms at the latest; a gesture with no clip is marked `missing` at once so the pointer cue stands in.
- `store.ts:scheduleEnd`: a voiced segment's timer is `durationMs + 30_000` (the media `ended` event advances; the timer is a safety net); an unvoiced one ends on `durationMs`.
- `store.ts:stop` resets `playing`, `current`, `live`, `zoom`, `cue` (`split`), `guarded`, `gesture`, `sketches`, `table`, `mediaLive`.
- `store.ts:tableEvent` ignores ids not in `OBJECTS`; `pushSketch` replaces the stack for ids in `RESET_ON`.
- `timeline.ts:compileTimeline` is pure; it reports a warning when `plays !== cue`, when narration has no audio, and for unknown scenes, gestures, hotspots and media cards.
- `workflows.ts:seg` marks every workflow segment `pinned: true`.
- `HeygenPanel.tsx`: a paid render runs only after the estimate (`POST /api/heygen/render` without `confirm`) is shown and the user clicks Render (`go` sends `confirm: true`); `API_USD_PER_S = 0.0385`.

## Side Effects
- localStorage: `streamstudio.script.v6` (`store.ts:KEY`, written by every `save`), `streamstudio.avatarShape` (`SHAPE_KEY`).
- Timers: module-level `requestAnimationFrame` tween (`store.ts:tween`), the segment end `setTimeout` (`timer`), gesture safety timeouts, and delayed sketch/table/media events in `play`.
- Cross-store writes: `useStage.setActive` (segment `scene`), `useStage.setSource('main', …)` (segment `visual`), `useStage.ensureTemplate` (`WorkflowPicker.tsx`).
- HTTP (`HeygenPanel.tsx`): `GET`/`PUT /api/heygen/config`, `GET /api/heygen/looks`, `GET /api/heygen/account`, `POST /api/heygen/render`, `GET /api/jobs/{id}` polled every 4 s; on completion `updateSegment(id, { clip, voice: 'clip', gesture: undefined })`.
- `TimelinePanel.tsx` creates `<video preload="metadata">` elements to learn clip lengths into `timeline.ts:clipDurations`.
- `ScriptPanel.tsx`: `URL.createObjectURL` for narration audio, `tagUrl` for clip and visual files.

## Verification
- Run: `cd web && npx vitest run`
