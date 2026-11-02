# stage

## Overview
The stage: the scene model (cards in fractions of the Base card), the zustand scene store with its localStorage and server persistence, the presets, the Base card renderer, the scene strip, media sources (files, web pages, shared tabs, camera), the studio hotspots, and the draggable library items. The director (`../director`) drives card geometry live through `useDirector.live`; this directory owns the saved layouts.

## Interface
- `types.ts`: `Orientation`, `CardKind` (`main | avatar | menu`), `Rect`, `CardLayout` (adds `z`, `visible`, `locked`, `radius`), `Bezel`, `MediaCard`, `Scene` (`menuShown`, `layouts` per orientation, optional `media`), `OUTPUT` (1920×1080 / 1080×1920), `GRID` (0.02).
- `store.ts`: `useStage` (zustand store), `orderedScenes(scenes)`, `migrateScenes(list, fromV2)`, `snap(v, grid)`, `SyncState`. Store actions: `active`, `layout`, `setOrientation`, `toggleOrientation`, `toggleMenu`, `toggleGuides`, `select`, `setRect`, `bringToFront`, `toggleVisible`, `toggleLocked`, `loadPreset`, `saveAs`, `setActive`, `deleteScene`, `setSource`, `toggleCutout`, `media`, `addMedia`, `updateMedia`, `setMediaRect`, `removeMedia`, `selectMedia`, `setSync`, `replaceScenes`, `newScene`, `duplicateScene`, `renameScene`, `moveScene`, `importScenes`, `ensureTemplate`.
- `presets.ts`: `PRESETS` (nine template scenes), `COLLECTIONS` (`Openers, Talk, Demo, Data, Social`), `Collection`, `clone`.
- `media.ts`: `tagUrl`, `isImageUrl`, `isUrlSource`, `urlOf`, `toUrlSource`, `LiveKind`, `liveStream`, `onLiveStream`, `liveKindOf`, `shareTab`, `shareCamera`.
- `hotspots.ts`: `Hotspot`, `HOTSPOTS` (`monitor`, `trading`, `table`), `hotspot(id)`.
- `sceneSync.ts`: `sceneBody(scene, position)`, `initSceneSync(fetch)`.
- `Library.tsx`: `LibraryItem`, `BRAND`, `LIBRARY`, `DRAG_MIME`, `DRAG_SRC_MIME`, `fileToItem`.
- Components: `Stage.tsx:Stage`, `Card.tsx:Card`, `MediaCardView.tsx:MediaCardView`, `SceneStrip.tsx:SceneStrip`, `Starfield.tsx:Starfield`.
- Subdirectory: [cards](./cards/README.md) (the Avatar, Main and Menu card contents).

## Invariants
- All card geometry is fractions (0..1) of the Base card (`types.ts` header, `Rect`); `Stage.tsx` sets the Base card `fontSize` to `size.w / 100` (landscape) or `size.w / 56` (portrait) so `1em` is about 1% of the long edge, and sizes cards in `%`.
- `store.ts:setRect` ignores locked layouts, snaps to `GRID` unless `snap=false`, clamps `w`/`h` to `[0.06, 1]` and keeps the card inside the frame. `setMediaRect` clamps to `[0.03, 1]` and lets a media card hang up to half off-frame.
- `Scene.menuShown` is `false` in every `PRESETS` entry except `app-menu`; `Stage.tsx` renders the menu `Card` with `card-ghost editor-only` when `!scene.menuShown`.
- `store.ts:deleteScene` does nothing when one scene remains; `importScenes` accepts only entries with a string `name` and both `layouts.landscape` and `layouts.portrait`, and gives them new ids.
- `orderedScenes` orders by `COLLECTIONS` rank (unknown collections last) and then by list order.
- `Card.tsx`: while `useDirector.live` is set the card follows the live geometry; the avatar card gets `is-circle` when `avatarShape === 'circle'` and (live) the cue is `pip`/`content` or `guarded`, or (saved) `isPipShaped(saved, orientation)`.
- `Stage.tsx` backdrop: with `bezel === 'studio'` the plate shows only while the Main card is hidden (`avatarAlone`), otherwise the `Starfield`; both stay mounted and cross-fade.
- `media.ts`: one live `MediaStream` per `LiveKind` in module state; `keep` stops the previous stream's tracks and notifies `onLiveStream` listeners; a track `ended` clears it.
- `sceneSync.ts`: the server copy wins on load (`replaceScenes(remote)` when non-empty); an empty server library is seeded from the browser; writes are debounced per scene (`DEBOUNCE_MS = 500`); `sync` goes `saving → server` or `error`.
- `Library.tsx:LIBRARY` = every `OBJECTS` entry (arrive clip, `w = 0.24`, aspect `940/750`, unframed, `once`) plus `BRAND` (`danslab-intro`, full width).

## Side Effects
- localStorage: `store.ts` reads/writes `streamstudio.scenes.v3` (`KEY`) and reads `streamstudio.scenes.v2` (`OLD_KEY`) once for migration; every mutating action calls `persist`.
- HTTP (`sceneSync.ts`): `GET /api/scenes`, `PUT /api/scenes/{id}` with `sceneBody`, `DELETE /api/scenes/{id}`; subscribes to `useStage` to push diffs.
- Browser media: `navigator.mediaDevices.getDisplayMedia` (`media.ts:shareTab`), `getUserMedia` (`media.ts:shareCamera`); `URL.createObjectURL` in `media.ts:tagUrl`, `SceneStrip.tsx:exportAll` (download of `streamstudio-scenes.json`).
- `SceneStrip.tsx` uses `alert` and `confirm`; `Stage.tsx` drop handler calls `addMedia`; `Stage.tsx` passes `tableEvent('remove:<id>')` to `ObjectLayer` when an object finishes leaving.
- `Card.tsx` and `MediaCardView.tsx` call `useDirector.getState().pointAt(...)` from the point button; `SceneStrip.tsx:go` calls `useDirector.stop()` when not playing.
- `Starfield.tsx`: `requestAnimationFrame` loop and `ResizeObserver` on a canvas; static when `prefers-reduced-motion: reduce`.

## Verification
- Run: `cd web && npx vitest run`
