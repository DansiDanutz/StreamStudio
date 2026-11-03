# src

## Overview
The StreamStudio web app entry: `main.tsx` mounts `App`, and `App.tsx` picks one of three views from the query string: the headless render view (`?render=1`), the Program window (`?program=1`, see [output](./output/README.md)) or the editor. The editor composes the stage, the scene strip or timeline, and the Library or Script side panel, wires the hotkeys, and starts scene sync, the Program link and the agent bridge.

## Interface
- `App.tsx`: default export `App()`; private `RenderView` and `Editor`; `RENDER` and `AUTOPLAY` flags from the query string.
- `health.ts`: `staleServerWarning(health)` → message or null.
- `main.tsx`: mounts `<App />` in `StrictMode` into `#root` and imports `index.css`.
- Subdirectories:
  - [stage](./stage/README.md): scene model, stage store, Base card and cards.
  - [director](./director/README.md): script, cues, lip-sync guard, timeline, workflows, HeyGen panel.
  - [agent](./agent/README.md): artifact catalog and action bridge for agents.
  - [avatar](./avatar/README.md): gesture definitions and clip manifest.
  - [library](./library/README.md): Library and Vault panels.
  - [output](./output/README.md): Program window link, recorder, live link.
  - [overlays](./overlays/README.md): table objects, desk sketches, pointer cue.
  - [publish](./publish/README.md): publish kit and YouTube upload.

## Invariants
- `App.tsx:RenderView` opens on the first segment's cue through `guardCue(first.cue, first)` with `guard = !lipsMatch(first)` and no tween (`ms = 0`); with `?autoplay=1` it calls `play(0)` after 800 ms; it exposes `window.__director` for the renderer.
- `App.tsx:Editor` hotkeys are ignored when the event target is an `INPUT`. Cue hotkeys (`A D S C F P`, `Z`) call `applyCue` without the `guard` argument, so they are previews; the guard is enforced in `useDirector.play`.
- `health.ts:staleServerWarning` warns when the health payload has no `rev` or when `stale === true`.
- Scene hotkeys `1–9` call `useDirector.stop()` first unless a script is playing (`App.tsx:onKey`).

## Side Effects
- `App.tsx:Editor` on mount: `initSceneSync()`, `loadGestureManifest()`, `startController()`, `startAgentBridge()`; `GET /api/health` on mount and every 60 s; a `window` `keydown` listener.
- `App.tsx:RenderView` adds `render-mode` to the document element and turns guides off.
- Hotkeys mutate stage and director state (`toggleOrientation`, `toggleMenu`, `toggleGuides`, `toggleLocked`, `toggleVisible`, `setActive`, `applyCue`, `stop`, `pushSketch`, `pointAt`, `removeMedia`).

## Verification
- Run: `cd web && npx vitest run`
