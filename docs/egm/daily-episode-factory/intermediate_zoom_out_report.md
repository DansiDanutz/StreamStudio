# Intermediate Zoom Out Report (Stage 8)

Reviewer status: completed (`egm-zoom-out`, fresh context, dispatched directly).

Target: `daily-episode-factory.md` after the Stage 7 resolution (1302 lines; specification
1-833, Detailed Implementation Plan 834-1302). Standard: `zoom-out-standard.md`. Prior reports
read: `zoom_out_report.md` (Stage 5), `comprehension_report.md` (Stage 6), `critic_report.md`
(Stage 7), `goldfish_review_report.md` (resolution).

Code checked for the claims below: `core/store.py` (`enqueue`, `claim_job`, `fail_job`,
`find_active_job`, `requeue_stale`), `worker/handlers.py` (`heygen_clip`, `youtube_upload`,
`CUTOUT`, `HANDLERS`), `worker/main.py` (`run_one`), `core/youtube.py` (`upload`, `clean_meta`;
no `set_status` today), `core/heygen.py` (`item_key`, `load_config`), `core/db.py`,
`core/config.py`, `core/netguard.py` (`origin_allowed`), `core/transcribe.py`,
`api/routes/heygen.py`, `api/routes/recordings.py`, `render/lipsync.py`, `render/preview.py`,
`web/src/director/HeygenPanel.tsx`, `tools/compose/qa_avatar.py`, `tools/compose/motion/build.py`,
`CLAUDE.md`, `docs/DESIGN.md`, `PLAN.md`.

Context sufficiency: passes. Overview, The Problem and Goals say what is built and why; the
Glossary lets a fresh reader follow the Technical Plan without `docs/DESIGN.md` open.

---

## Stage 5 disposition

| Stage 5 finding | Status | Reason |
| --- | --- | --- |
| B1 Publish poller needs a scheduler | Closed | `episode_publish_status` is gone. Publish is `POST /{id}/publish` → `set_status`; the scheduled check runs inside `GET /{id}`; purge is planner rule 6 on the next advance. No scheduler. The replacement has its own problems (new findings 3 and 4). |
| B2 "scenes → sets" rename bundled in | Closed | Rename is a Non-Goal, a Future Improvement, a glossary note and one sentence in `docs/DESIGN.md`. Plan items 55a-55d are gone. |
| B3 Spec and plan disagree | Closed | All six named items reconciled. Three small new disagreements appear below (finding 7). |
| M1 Technical Plan at implementation altitude | Partly closed | Function lists, signatures, `BEGIN IMMEDIATE`, viewport px, `-w`, 42-character lines and the `WORDS_PER_S` constant are out of the spec. Remaining: the LUFS table and the 25 % threshold (production decisions rather than code) and the YouTube endpoint path. Acceptable residue. |
| M2 Three stores, lock on the wrong one | Closed | `record_json` on `episodes`, `episode.json` as an export at purge, planner the only writer of stage data. Matches the `edl_versions` pattern. |
| M3 Four card templates in v1 | Closed | `generic` only; others in Future Improvements. |
| M4 Smallest version not identified | Partly closed | "The smallest version" names the slice and Stage 1 delivers it; the first video now comes after 37 files instead of 44. Stage 1 still carries items the slice does not need (finding 2). |
| M5 Knobs for fixed things | Closed | 25 fps and HyperFrames workers are constants; the allowance is two plain settings. |
| M6 Goals without measures | Closed | 12 hours, 15 minutes, a test for no `heygen_clip` without `budget.approved_at`, cost within estimate plus allowance. |
| M7 Four status surfaces | Closed | Library group and `episode.status` deferred. |
| N1 Converter in production code | Closed | `server/tests/convert_episode1.py`. |
| N2 Whisper unmeasured | Closed | Q1 and the Stage 0 record include whisper per clip; captions fall back to measured durations. |
| N3 Script-text captions duplicate the transcript | Closed | Reason stated; the `kit.ts` change is gone. |
| N4 `episode_register` copies | Closed | Moves. |
| N5 Episode 1 v2 re-render costs money | Closed | Optional, Dan-approved. |
| N6 `status` stored and derived | Closed | Gate and terminal states only; progress from counts. |
| N7 Stage 0 not only measurement | Closed | Templates moved to Stage 3; brand assets stay in Stage 0 with a stated reason. |
| N8 Goals carry mechanism | Closed | Goals are outcomes. |

---

## New findings

### 1. Stage 1 ships planner rule 1 without rule 3, and rule 1 as written re-enqueues a failed scene for ever
- **Severity**: Blocker
- **Where**: planner rules 1 and 3; "The paid step"; plan file 24 ("Stage 1 ships rules 1, 4, 5 and 6; rules 2 and 3 land in Stage 2"); plan file 39 (`needs_dan` on job `error` also in Stage 2).
- **Discrepancy**: The C3 fix made a HeyGen `failed` a normal `done` result with a charge row, and `max_attempts = 1` stops the worker from retrying. The only thing that now stops a re-render is rule 3's allowance check. Rule 1 fires for "some scene has no clip for its current (key, take) and no queued or running `heygen_clip` job". After a `failed`, the clip is absent and the job is finished, so rule 1 re-enqueues the same (key, take). Either the old claim is still in the state file and the planner loops (enqueue, no-op, advance, enqueue), or the claim is cleared and the scene is paid again with no allowance check. The rules "run in order" and rule 1 precedes rule 3, so rule 1 re-enqueues the same take before rule 3 increments it. In Stage 1 rule 3 does not exist at all, nor does `needs_dan` on `error`, yet Stage 1 runs real episodes with real money. The Risks table promises `needs_dan` and allowance behaviour that Stage 1 cannot deliver.
- **Recommendation**: Make rule 1 explicit: it skips a scene whose last result for the current take is `failed` or whose job ended in `error`. Put the two-line safety rule in Stage 1 with rule 1: "a `failed` result or an `error` on any stage job → `needs_dan`, with the reason in `log`". Stage 2 then replaces the `failed` branch with the allowance (rule 3) and leaves `error → needs_dan` alone. Evaluate rule 3 before rule 1 re-enqueues. Add "a `failed` clip in Stage 1 parks the episode and is charged once" to the Stage 1 tests.

### 2. Stage 1 still carries features no Stage 1 journey needs
- **Severity**: Major
- **Where**: "The smallest version"; Stage 1 files 19, 20 (`?from=<id>`, `cancel`, `scheduled`), 27, 31 (`publish_at`), 32 (`refresh_status`), 33 (Cancel button).
- **Discrepancy**: The slice is "script to private upload and the publish click". Stage 1 nevertheless includes scheduled publishing and the `scheduled` state with its status check; `POST /api/episodes?from=<id>` for re-voicing after upload, which no v1 CUJ exercises; `cancel` with partial reservation release; the shared Python/TypeScript lip-sync fixture with a vitest change (file 27); and the editor `HeygenPanel.tsx` change (file 19). Each is a code path and a test before the first video exists. The `?from=` route serves a flow the document itself moved to Future Improvements.
- **Recommendation**: Stage 1 publishes now only; `publish_at`, `scheduled` and the status refresh move to Stage 2 with the full status page. `?from=<id>` moves to Stage 2 or Future Improvements. Files 27 and 19 move to Stage 4 hardening. Keep `cancel` only if Dan asks for it before Stage 2; otherwise the Stage 1 escape hatch is `needs_dan` plus the Purge button.

### 3. `GET /api/episodes/{id}` has side effects, and one of them will exhaust the YouTube quota
- **Severity**: Major
- **Where**: Publish; planner rule 6; plan file 20 (`GET /{id}` runs the YouTube status check); file 33 (the page polls `GET /api/episodes/{id}` every 5 s); file 32 (`refresh_status`).
- **Discrepancy**: The B1 fix moved the poll from the worker into the read endpoint. A `scheduled` episode left open on Dan's phone issues a `videos.list` call every 5 seconds: 17,280 calls a day against the Data API's default 10,000-unit daily quota, before the 1,600 units an upload costs. The same GET is also, by rule 6, the trigger that enqueues `episode_purge`, so a status read from MCP can delete files. A read endpoint that calls a third party and starts destructive jobs is an architectural dead end: every future consumer of the status API inherits both behaviours. It also stretches `CLAUDE.md`'s "offer to delete them" into "delete on first open".
- **Recommendation**: Keep `GET /{id}` pure. The status check becomes an explicit `POST /{id}/refresh` that the Episode page calls once when it opens a `scheduled` episode after `publish_at` (and that MCP may call), with a `last_checked_at` on the record so repeated calls within a few minutes are no-ops. Purge becomes the button only (`POST /{id}/purge`), with the page showing "Published. Purge workings?" so the rule is literally "offer". Rule 6 then disappears.

### 4. Nothing enqueues the planner when the upload finishes, so `uploaded_private` depends on a page open
- **Severity**: Major
- **Where**: fan-in paragraph ("each stage handler enqueues `episode_advance` when it finishes"); `uploaded_private` entry rule; "`youtube_upload` ... work unchanged"; Rollout ("`youtube_upload` (an optional field)").
- **Discrepancy**: The planner reads the upload's state file (it does contain `video_id`; verified in `handlers.py:143` and `youtube.py:356`). But `youtube_upload` is the one stage handler that is "unchanged", so it never enqueues `episode_advance`, and comprehension finding 3 stays open. The episode shows "uploading" until something else advances it. The Rollout section still lists an "optional field" on `youtube_upload` that the specification no longer describes.
- **Recommendation**: One sentence: "`youtube_upload` with `payload.episode_id` enqueues `episode_advance` on return". That is the optional field Rollout already names; align the publish section with it.

### 5. The degrade path assumes a clip exists; a HeyGen `failed` after the allowance has none
- **Severity**: Major
- **Where**: rule 3; Glossary "Degraded"; Compositor (degraded → `pip`); Risks row.
- **Discrepancy**: Degrade means "composed with the face in the small picture-in-picture rectangle", which works for a QA `FAIL` (the clip and its audio exist). The C3 fix folded HeyGen `failed` into the same branch, but a `failed` render has no MP4, no cut-out and no voice audio; `scene_compose` has nothing to put in the small rectangle and no audio for the scene.
- **Recommendation**: Split the branch: QA `FAIL` with the allowance spent → `degraded`; HeyGen `failed` with the allowance spent → `needs_dan` ("Scene N could not be rendered after K attempts"). This reuses the `needs_dan` path from finding 1.

### 6. CUJ 3's starting state does not exist, and editing a script mid-pipeline has no defined edge
- **Severity**: Major
- **Where**: CUJ 3 Given ("A `budget_approved` episode whose clips have all rendered and passed QA"); states; rule 1 ("set `in_progress`"); `PUT /{id}/script` (refused only after `uploaded_private`).
- **Discrepancy**: Rule 1 moves the episode to `in_progress` when clips are enqueued, so an episode whose clips have rendered is `in_progress`, not `budget_approved`. `PUT /script` is allowed in `in_progress`, yet no edge says what state follows, whether the planner keeps enqueueing for the old script while the new one is unapproved, what happens to the partially consumed reservation when a second approve-budget writes a second one, and whether in-flight clip jobs for changed scenes are cancelled. This is the C4 gap moved one state earlier.
- **Recommendation**: Add the edge: "`PUT /{id}/script` from `script_approved`, `budget_approved` or `in_progress` returns the episode to `draft`; the planner only acts on `budget_approved` and `in_progress`; in-flight clip jobs finish and are charged to the existing reservation; `approve-budget` releases the previous reservation and writes a new one covering only scenes without a clip for their key." Fix CUJ 3's Given to `in_progress`.

### 7. Small spec-versus-plan disagreements introduced by the restaging
- **Severity**: Nit
- **Where**: "The smallest version" vs file 14; "the scene list and three buttons" vs file 33; preflight (file 9) vs `POST /api/episodes` 503.
- **Discrepancy**: The spec's Stage 1 has "error-level validation only"; file 14 also ships the length warning. The spec's Stage 1 page has three buttons; file 33 has four plus the estimate screen. Preflight tests every tool and the HyperFrames workspace, so in Stage 1 a missing Playwright, HyperFrames or whisper (Stage 2 or 3 tools) blocks creating an episode the slice can fully produce.
- **Recommendation**: Pick one in each case. For preflight: check only what the shipped stage uses, and say so in file 9.

### 8. Reservation release has two triggers where one would do
- **Severity**: Nit
- **Where**: "The paid step" ("when the episode reaches `uploaded_private`, or when it degrades its last failing scene").
- **Recommendation**: Release at `uploaded_private` and `cancelled` only.

---

## What passes

- The additions kept their altitude. The Glossary, the Risks table, the ledger's three row kinds, the claim-in-state-file rule and the gate-only state list are described as behaviour and invariants, not code.
- Reuse claims verified against the code: `item_key` with `take = 0` reproducing today's hash; `find_active_job` for the queued-or-running check; `youtube_upload` attaching `<id>.srt` automatically, so writing `rec_*-ep.srt` gets captions for free; `transcribe.transcribe` already emitting word timings; `netguard.origin_allowed` for the `Origin` check; Playwright already in `render/preview.py`; `record_json` following `edl_versions`; the two cost-rate copies the `estimate` consolidation removes.
- The planner-instead-of-DAG, allowance-instead-of-stall and register-as-a-take decisions remain the simplest options that keep the `CLAUDE.md` money rule and leave upload, vault and MCP unchanged.
- Non-Goals are concrete and honoured by the body of the document, including the scheduler and the rename.
