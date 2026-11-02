# overlays

## Overview
Layers drawn over the studio plate: the 3D objects on the table (`ObjectLayer`), the neon-chalk desk sketches (`DeskSketch`), and the pointer cue that stands in for a gesture clip (`PointerCue`). The director store (`../director/store.ts`) owns the table and sketch state; these components only render it.

## Interface
- `objects.ts`: `ObjectPhase`, `ObjectDef`, `OBJECTS` (seven objects), `HERO`, `objectStill(o)`, `objectClip(o, 'arrive' | 'leave')`, `TableEvent`.
- `sketches.ts`: `Stroke`, `Glyph`, `Sketch`, `SKETCHES` (`heart`, `grid`, `codex`, `grokbot`, `lobster`, `lobster-crossout`, `team`), `RESET_ON`.
- `ObjectLayer.tsx`: `ObjectLayer({ table, onGone? })`, `TableState`.
- `DeskSketch.tsx`: `DeskSketch({ stack, edgeY? })`.
- `PointerCue.tsx`: `PointerCue()`.

## Invariants
- `ObjectLayer.tsx`: only the most recent `arrive` (`latest`, by `arrivedAt`) owns the hero spot; objects in phase `gone` are not rendered; an arrive clip plays once and holds its last frame; `idle`/`react` without an arrival seek to the end of the clip.
- `ObjectLayer.tsx` constants: `HOLD_MS = 2600` (still-only objects at the hero spot), `ARRIVE_RATE = 2.2`, `LEAVE_RATE = 1.6`, `SETTLE_DELAY_MS = 700`, `DISC_PX = 520` (clips and stills are normalised to this disc width).
- A clip error falls back to `objectStill` and, in phase `leave`, calls `onGone` so the object is removed.
- `sketches.ts` coordinates are a 1000×400 desk space; `DeskSketch.tsx` draws glyphs at `(scale ?? 1) * 0.58` and animates each stroke by its measured `getTotalLength()`.
- `sketches.ts:RESET_ON` = `heart`, `grid`: these replace the sketch stack instead of adding to it (used by `useDirector.pushSketch`).
- `PointerCue.tsx` renders nothing without `gesture.to`; a soft ring while a real clip plays, a sweep line plus ring when `gesture.missing`.

## Side Effects
- DOM and SVG rendering only; `ObjectLayer` sets `playbackRate` and `currentTime` on its videos and calls `onGone`. No network or storage access.

## Verification
- Run: `cd web && npx vitest run`
