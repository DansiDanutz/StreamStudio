# avatar

## Overview
The presenter's gesture set: the twelve gesture definitions, which clip renders each one, how a pointing gesture is chosen from the presenter's position and a target, the HeyGen motion prompts used to render the clips, and the manifest of clips that exist.

## Interface
- `gestures.ts`: `GestureId`, `Gesture`, `GESTURES`, `gesture(id)`, `gestureClip(g)`, `pickGesture(presenter, target, present?)`, `SEATED`, `MOTION`, `SOURCE_GESTURES`, `motionFor(id)`, `loadGestureManifest(fetch?)`, `setMadeGestures(ids)`, `hasClip(id)`, `nearestMade(id)`, `aimAt(presenter, target)`.

## Invariants
- Left-hand gestures are `mirrorOf` a right-hand gesture; `gestureClip` returns `/avatar/gestures/<mirrorOf ?? id>.cutout.webm`; `SOURCE_GESTURES` contains only gestures without `mirrorOf` (`gestures.ts`).
- Until the manifest has loaded (`made === null`), `hasClip` returns true for every gesture; after a failed fetch it stays that way (`gestures.ts:loadGestureManifest`, `hasClip`).
- `pickGesture` picks the side from the target centre versus the presenter centre, and `up-`/`down-` when the target centre is above 42% or below 78% of the presenter height.
- `nearestMade` prefers a clip on the same side (cost 10 for a side mismatch) before height; returns null for beat gestures with no clip.
- `SEATED` is derived from the same seating numbers as `AvatarCard` (`SEAT`): landscape `x = 0.47 - 0.2`, `y = 0.68 - 0.85 * 0.66`.
- `motionFor` mirrors a prompt by swapping "right side"/"left side" and "His left"→"His right".

## Side Effects
- `loadGestureManifest`: `GET /avatar/gestures/manifest.json` with `cache: 'no-store'`; writes the module-level `made` set. `setMadeGestures` writes it directly (used by tests).

## Verification
- Run: `cd web && npx vitest run`
