# episode

## Overview

The Episode page of the episode factory: `?episode=<id>` shows one episode's scenes with their
validation errors, the three buttons (Approve script, Approve budget with the cost screen and its
one-time token, Publish now), Advance when the factory needs Dan, and Purge once published. It
reads the server's `EpisodeOut` shape (`GET /api/episodes/{id}`) and nothing else; while the
worker is busy it polls every 5 s. Usable at a 390 px wide viewport over the tailnet. Stage 2
adds warnings, inline edit, per-scene state chips, contact-sheet links, the "Needs you" detail
and the schedule control.

## Interface

- `api.ts`: types `EpisodeStatus`, `SceneIn`, `Episode`, `Estimate`, `ApiError`; one function per route: `getEpisode`, `listEpisodes`, `createEpisode`, `putScript`, `approveScript`, `estimate`, `approveBudget(id, token)`, `publish(id, publishAt?)`, `advance`, `purge`; pure helpers `progressLabel(ep)`, `primaryAction(status)`, `usd(n)`.
- `EpisodePage.tsx`: `EpisodePage({ id })`.
- `App.tsx` renders it when the query string has `episode=<id>`, before the editor branch.

## Invariants

- `progressLabel` derives "rendering n/m, composing n/m, assembling, uploading" from `progress` and `outputs`; nothing is stored. [api.ts:progressLabel]
- `primaryAction` maps each gate state to exactly one click; working states have none. [api.ts:primaryAction]
- Approve budget is two steps: the estimate (with `confirm_token`) is shown first, and the token is sent only on the second click; the browser's `Origin` header is what the server requires. Nothing is paid until that click. [EpisodePage.tsx:est]
- Approve script is disabled while the validator reports errors. [EpisodePage.tsx:errorCount]

## Side Effects

- `fetch` to `/api/episodes*`; a 5 s interval while the status is `budget_approved` or `in_progress`. [EpisodePage.tsx:load]

## Verification

- `cd web && npx vitest run src/episode`
