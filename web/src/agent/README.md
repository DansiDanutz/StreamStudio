# agent

## Overview
The editor's side of the agent bus. `catalog.ts` builds the artifact library the editor owns (gestures, targets, hotspots, objects, media, workflows, cues, templates) and the list of actions agents may call. `bridge.ts` publishes that catalog to the server, executes incoming actions on the stage and director stores, and reports the editor's state. A new artifact kind or action is added here (`catalog.ts` + `bridge.ts`) with a test.

## Interface
- `catalog.ts`: `Artifact`, `ActionSpec`, `ACTIONS` (the action specs), `buildCatalog()` → `{ artifacts, actions }`.
- `bridge.ts`: `EXECUTORS` (action name → function), `timelineNow()`, `snapshot()`, `startAgentBridge()` → stop function.
- Actions (`catalog.ts:ACTIONS`, implemented in `bridge.ts:EXECUTORS`): `scene.activate`, `scene.new`, `cue.apply`, `point.at`, `gesture.play`, `table.event`, `media.add`, `media.event`, `media.remove`, `main.source`, `workflow.insert`, `timeline.get`, `publish.kit`, `segment.preview`, `segment.update`, `segment.add`, `segment.remove`, `script.set`, `script.play`, `script.stop`, `avatar.shape`, `orientation.set`.

## Invariants
- `bridge.ts:'cue.apply'` always calls `applyCue(cue, zoom, 600, true)`: the lip-sync guard is never bypassed for agents.
- `bridge.ts:cleanPatch` keeps only the keys in `FIELDS`, rejects a `cue` outside `CUES`, validates `media` with `parseMediaEvents`, converts an `http(s)` `visual` with `toUrlSource`, and recomputes `durationMs` from the text.
- `segment.update`, `segment.add` and `script.set` mark segments `pinned: true` (`bridge.ts`).
- `bridge.ts:segIndex` accepts a number, a numeric string or a segment id and throws when out of range.
- Id prefixes are stripped before lookup (`scene:`, `template:`, `target:`, `gesture:`, `object:`/`media:`, `workflow:`) in the respective executors.
- The catalog is published only after `loadGestureManifest()` resolves, so `clip_ready` is true only for clips that exist (`bridge.ts:startAgentBridge`).
- `buildCatalog` lists a `media:` artifact only for `LIBRARY` items that are not `OBJECTS` (`catalog.ts`).

## Side Effects
- `bridge.ts:startAgentBridge`: `POST /api/library/web` with `buildCatalog()`; dispatches `window` event `streamstudio:library` on success; opens `EventSource('/api/agent/stream')` and answers each `do` event with `POST /api/agent/result/{id}`; posts `snapshot()` to `POST /api/agent/state`, debounced 500 ms, on every `useStage`, `useDirector` or `useProgram` change.
- Executors mutate `useStage` and `useDirector` state (scene switch, media cards, cues, gestures, table, script).

## Verification
- Run: `cd web && npx vitest run`
