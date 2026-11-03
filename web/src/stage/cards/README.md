# stage/cards

## Overview
The three core cards drawn inside the Base card by `../Stage.tsx`: the presenter (`AvatarCard`), the content (`MainCard`) and the controls (`MenuCard`). Each card reads the stage store (`../store.ts`) and the director store (`../../director/store.ts`) and renders media or controls; card geometry itself is handled by `../Card.tsx`.

## Interface
- `AvatarCard.tsx` → `AvatarCard()`: plays the avatar clip for the orientation, or the on-air segment's clip while the director plays. Selects the transparent cut-out (`CUTOUT` map, or `<clip>.cutout.webm` next to a rendered clip) when `useStage.cutout` is on and the card is full frame; shows a gesture clip (`gestureClip`) while `useDirector.gesture` is set; plays the narration `<audio>` for `voice === 'narration'` segments.
- `MainCard.tsx` → `MainCard()`: what the Main card shows, from `useStage.mainSrc`: a file (`tagUrl`), a web page (`url:` source rendered in the private `BrowserView` iframe at `VIEW_W = 1440` scaled to the card), or a live tab/camera stream (private `LiveView`, from `../media.ts`). Applies `useDirector.zoom` as a CSS transform.
- `MenuCard.tsx` → `MenuCard()`: buttons for cue (`applyCue`), scene preset (`loadPreset`), orientation (`setOrientation`), avatar visibility (`toggleVisible('avatar')`) and `toggleMenu`.

## Invariants
- The clip's own audio is heard, unlooped, only on air with matching lips: `AvatarCard.tsx:onAir = playing && !!seg && lipsMatch(seg)`; otherwise the video is `muted` and `loop`ed.
- Only the editor advances the script: `AvatarCard.tsx:advance` calls `next()` only when `!IS_PROGRAM`.
- When a Program window is connected the editor is silent: `AvatarCard.tsx:quiet` (`useProgram.connected && !IS_PROGRAM`) mutes the clip and the narration audio.
- The cut-out is used only when the card is full frame: `AvatarCard.tsx:cutout = cutoutPref && isFull`; a missing cut-out file falls back to the raw clip (`missing` state set on `onError`).
- The Menu card is a dashed ghost unless the scene shows it: `MenuCard.tsx` sets class `menu-ghost` when `scene.menuShown` is false and `menu-on` when true.
- `MainCard.tsx:BrowserView` iframes run with `sandbox="allow-scripts allow-same-origin allow-forms allow-popups"` and `referrerPolicy="no-referrer"`.
- `MainCard.tsx:LiveView` renders a prompt to share again when `liveStream(kind)` is null (a stream lives in one window).

## Side Effects
- `AvatarCard.tsx`: `URL.createObjectURL` on file pick, then `useStage.setSource('avatar', …)`; calls `useDirector.getState().next()` on clip/narration `ended`; `endGesture` / `markGestureMissing` on the gesture video's `ended` / `onError`.
- `MainCard.tsx`: `shareTab()` and `shareCamera()` (from `../media.ts`) request `getDisplayMedia` / `getUserMedia`; `setSource('main', …)`; `ResizeObserver` on the browser frame; loads a third-party URL in an iframe.
- `MenuCard.tsx`: mutates stage and director state through `applyCue`, `loadPreset`, `setOrientation`, `toggleVisible`, `toggleMenu`.

## Verification
- Run: `cd web && npx vitest run`
