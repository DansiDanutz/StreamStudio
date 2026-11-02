# library

## Overview
The Library panel: every artifact (scenes, templates, gestures, clips, objects, media, recordings, workflows, layouts) in tabs with search and filters, merged from the editor's own catalog (`../agent/catalog.ts`) and the server's copy (`/api/library`, which adds names, tags and storage). The Vault panel configures where copies are kept off the machine.

## Interface
- `groups.ts`: `GROUPS` (kind → tab), `TABS`, `KIND_LABEL`, `Storage`, `LibItem`, `StatusFilter`, `StoreFilter`, `Sort`, `Filters`, `NO_FILTERS`, `asItem(a)`, `matches(a, q)`, `needsClip(a)`, `storeOf(a)`, `filterItems(items, f)`, `countBy(items, key)`, `fmtBytes(n)`.
- `LibraryPanel.tsx`: `LibraryPanel({ onAddFile })`.
- `VaultPanel.tsx`: `VaultPanel({ onClose })`.

## Invariants
- `groups.ts:GROUPS` is written to match the server's grouping (`api/routes/agent.py GROUPS`, per the file comment) so agents and the editor see the same tabs.
- `groups.ts:matches` requires every search word to appear in name, default name, id, description, tags or kind label.
- `LibraryPanel.tsx:all`: when the server answers, its items take precedence over editor items with the same id; `stage-media` items (cards on the current scene) always come from the editor.
- `groups.ts:needsClip` is true only for a `gesture` without `clip_ready`.
- `VaultPanel.tsx`: `access_key` and `secret_key` are blanked after a save and never shown unmasked (the server's masked values are used as placeholders).
- `VaultPanel.tsx` re-polls `/api/vault` every 1.5 s only while `last_push.status` is `queued` or `running`.

## Side Effects
- HTTP (`LibraryPanel.tsx`): `GET /api/library` on mount, every 15 s, and on the `streamstudio:library` window event; `PATCH /api/library/{id}` (title, tags); `POST /api/vault/fetch` and `POST /api/vault/evict` with a storage key.
- HTTP (`VaultPanel.tsx`): `GET /api/vault`, `PUT /api/vault`, `POST /api/vault/push`, `POST /api/vault/sync`.
- localStorage `streamstudio.library.filters` (filters without the search text).
- `navigator.clipboard.writeText` for the copied agent call; drag data under `DRAG_MIME` / `DRAG_SRC_MIME`.
- The ▶ button runs `EXECUTORS[action]` from `../agent/bridge.ts` locally, mutating stage and director state.

## Verification
- Run: `cd web && npx vitest run`
