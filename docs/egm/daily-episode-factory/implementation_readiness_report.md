# Implementation Readiness Report (Stage 9, round 1)

**Target:** `daily-episode-factory.md`, DetailedRange lines 834-1302 (Detailed Implementation Plan
and Verification Plan), with the specification read for context.

## Reviewer status

| Reviewer | Standard | Status | Raw findings |
| --- | --- | --- | --- |
| `egm-implementation-readiness` | implementation-readiness-standard | completed | 2 Blocker, 9 Major, 13 Nit |
| `egm-codebase-details` | implementation-readiness-standard | completed | 2 Blocker, 5 Major, 13 Nit |
| `egm-style` | persona writing standard | completed | 0 Blocker, 3 Major, 28 Nit |

All three ran in fresh contexts, dispatched directly. Every file the plan marks Modify or Delete
was confirmed to exist; every Create target is absent; the reuse claims about the test hooks,
`find_active_job`, `origin_allowed`, the guard, the transcript word timings, Playwright, the vault
globs and the recording id pattern were verified. Findings are deduplicated below; each names
the raw findings it absorbs (R = readiness, C = codebase details, S = style, Z = Stage 8).

Round verdict: **not clean** (Blockers and Majors present). The verdict of both standard
reviewers: the plan does not yet pass the zero-decision rule.

---

## Blockers

### I1. Stage 1's planner cannot advance past clips, and failure signalling never wakes it
- **Absorbs:** R-B1, R-M3; Z1, Z4, Z5, Z9.
- **Gap:** Plan item 24 ships rules 1, 4, 5 and 6 in Stage 1, but rule 4's precondition ("all scenes `ok`, `LOOK` or `degraded`") is only ever produced by `scene_qa` (Stage 2), so no scene reaches compose. Rule 5 lists four sequential jobs with no completion predicate the planner can test from files (`final.mp4` is moved by `episode_register`). A HeyGen `failed` is returned as a job result although the planner is forbidden from reading result rows, and a worker-level `error` never enqueues the planner (`worker/main.py:53-57` only calls `fail_job`), so `needs_dan` is unreachable in every stage. The claim rule blocks recovery after an `error` (Z9); `youtube_upload` never enqueues the planner (Z4); a degraded render failure has no clip to degrade (Z5).
- **Recommendation:** Replace the planner prose with a condition table evaluated top to bottom (predicate on record + files → job, deduped by the job id in `scenes_state`), with Stage 1 predicates on file presence and Stage 2 replacing the compose predicate with QA. HeyGen `failed` is written into the clip's state file (never unlinked for episodes) and read from there; `run_one` enqueues `episode_advance` after `fail_job` when the payload carries `episode_id`; the one permitted job-row read is `jobs.status` of a recorded job id. A claim is valid only while its job is queued or running and is transferred to the replacement job under the row lock. `youtube_upload` with `episode_id` enqueues the planner. Render failure after the allowance → `needs_dan`; QA failure after the allowance → `degraded`.

### I2. Module-level heavy imports break the API, the base install and CI from Stage 1
- **Absorbs:** R-B2, C-B1, C-B2.
- **Gap:** `worker/handlers.py` is imported by the API and every existing test. If any `episode/` module imports `cv2`, `numpy`, `PIL` or `playwright` at module top (as the ported `render.py` and `qa_avatar.py` do), `import streamstudio.worker.handlers` raises on any machine without the `episode` extra: the launcher's fallback install, CI (`uv sync --locked` with no extra), the `dev` dependency group. Registering handlers by importing the package at the end of `handlers.py` also creates a cycle that ruff E402 rejects. CI installing the extra (item 56) is scheduled in Stage 4.
- **Recommendation:** `episode/__init__.py` holds a docstring only; no `episode/` module imports a heavy library at module level (handlers import inside the function, as `_cutout_clip` does); registration through a thin `episode/handlers.py` imported by `worker/main.py` (not by `handlers.py`); CI and the Makefile install the `episode` extra in Stage 0; the import test asserts the package imports cleanly without the extra.

---

## Majors

### I3. `youtube_upload` cannot be enqueued as planned: channel, `meta` and `key` are unspecified
- **Absorbs:** R-M4, C-M1.
- **Recommendation:** `Script.channel?`; `approve-budget` resolves `youtube.pick_channel` (409 when several channels are connected and none named) and stores `outputs.channel`; the planner enqueues `{id, channel, key: f"{channel}/{rid}", meta: clean_meta(kit.title, kit.description, kit.tags, "private"), episode_id}` and reads `youtube/uploads/<channel>-<rid>.json`.

### I4. The `Plan` model with `extra="forbid"` rejects the Episode 1 v2 fixture; the converter mapping is unspecified
- **Absorbs:** R-M1, C-M2.
- **Recommendation:** Full `Plan` field list with types from `render.py` (adds `chips_out`, `card_x`, `end_at`, `end_until`); explicit converter rules (`question: true` → scene `question: n`; long-take card keys dropped; `site` from the storyboard groups); a test that the converted fixture validates.

### I5. The ledger is under-specified
- **Absorbs:** R-M2.
- **Recommendation:** Columns `scene_id`, `take`, `job_id`, `UNIQUE(episode_id, scene_id, take, kind)`; `unconsumed = reservation.usd − Σcharge.usd − Σrelease.usd` (floor 0) for the latest reservation not fully released; `seconds` = ffprobe duration for `completed`, the estimate's seconds for `failed`; `usd = seconds × USD_PER_S`.

### I6. `cues.json`, the "template" and the SFX mapping have no schema
- **Absorbs:** R-M5.
- **Recommendation:** `cues.json = [{kind: navigate|counter|ring|callout, t}]`; the generic card is a function over `Comp`, not a JSON interpreter; the workspace ships only `package.json` and `package-lock.json`; the cue-to-SFX table from `mix.py` becomes a module constant; `manifest.json` names the bed.

### I7. The compositor's decode path is unspecified and has a trap (VP9 alpha)
- **Absorbs:** R-M6.
- **Recommendation:** Decode the cut-out with `-c:v libvpx-vp9` to `rgba` and the clip to `rgb24`, both at `fps=25`, in lock-step; seat geometry from `plate-landscape-final.json["seat"]`; frame count `round(duration × 25)`; `inputs_hash` defined.

### I8. Publish kit decisions left open
- **Absorbs:** R-M7.
- **Recommendation:** `kit.json` keys; chapters only when at least three after folding those under 10 s, first at 0:00 (port `kit.ts`); `Script.tags`; times offset by the intro duration.

### I9. `GET /api/episodes/{id}` has no response shape
- **Absorbs:** R-M8.
- **Recommendation:** `EpisodeOut` = record minus the token plus `progress`, `validation`, `next_action`, `last_log`; `api.ts` exports listed.

### I10. Word error rate and number-to-words have no implementation; per-take transcripts overwrite each other
- **Absorbs:** R-M9.
- **Recommendation:** In-package Levenshtein and number-to-words; `qa/<scene>.t<take>.words.json` per take, `qa/<scene>.words.json` the accepted copy.

### I11. Contract READMEs are updated only in Stage 4; four READMEs are missing from the plan
- **Absorbs:** C-M3.
- **Recommendation:** Each code item names the README sections it changes; add `api/README.md`, `web/src/director/README.md`, `render/README.md`, `mac/README.md`.

### I12. A second intro file beside the one that already ships, and a 30 fps generator
- **Absorbs:** C-M4.
- **Recommendation:** One file: re-render `assets/brand/danslab-intro.mp4` at 25 fps (the stage media card and catalog keep working); `make_intro.py` renders with `-f 25`.

### I13. `transcribe.transcribe` always writes an SRT and raises without whisper
- **Absorbs:** C-M5.
- **Recommendation:** Pass `qa/<scene>.t<take>.srt`; purge it; catch `TranscribeError` as issue "transcript unavailable" with `words: null`.

### I14. Stage 1 scope, pure GET, mid-pipeline edits, release triggers, workspace bootstrap
- **Absorbs:** Z2, Z3, Z6, Z7, Z8, Z10; S-M2.
- **Recommendation:** Stage 1 publishes now only; scheduled publish, refresh, cancel and the shared fixture move later; `?from=` dropped to Future Improvements. `GET /{id}` pure; `POST /{id}/refresh` with `last_checked_at`; purge via the button only (rule 6 removed; items 24 and 32 agree). `PUT /{id}/script` from any pre-upload state returns to `draft`; a second approve-budget releases the previous reservation and reserves only scenes without a clip. Release at `uploaded_private` and `cancelled` only. The HyperFrames workspace files ship in the package and `npm ci` moves to Stage 3. Preflight checks only the shipped stage's tools.

### I15. Cross-reference and naming errors that change meaning
- **Absorbs:** S-M1, S-M3, C-N6, R-N5.
- **Recommendation:** Item 49's "deleted after" list names the card builder's replacement and is sorted; the contact sheet is `qa/<scene>.jpg` everywhere.

---

## Nits

### I16. Small decisions to pin down
- **Absorbs:** C-N1, C-N2, C-N3, C-N4, C-N5, C-N7, C-N8, C-N9, C-N10, C-N11, C-N12, C-N13, R-N1, R-N2, R-N3, R-N4, R-N6, R-N7, R-N8, R-N9, R-N10, R-N11, R-N12, R-N13.
- Includes: `estimate_seconds` signature; `item_key` appends `take` only when non-zero; `db.row()` decodes `record_json`; the `projects` row is inserted directly, not through `create_project`; the launcher's two install branches; `Comp` takes a workspace path; the shared fixture's import path and row format; `hyperframes_browser` `None` semantics; `CaptureSite` placement; recordings list ordering; `Origin` must be present (the middleware treats absence as a non-browser request); id regexes; the render hook lives in `episode/hyperframes.py`; capture rect definitions; a page stylesheet; the registered episode's caption language; the intro render command; `requeue_stale` and one attempt.

### I17. Style nits on the plan
- **Absorbs:** S-N1 to S-N28.
- Includes: `s` expanded as `Settings`; `fps` unit; `tools/compose/mix.py` disambiguated; route notation without empty strings; the item 22 run-on as bullets; `max_attempts` stated once; fragments; "two lines of 42" as "at most"; vague verbs in items 50, 51, 53; "three clicks" named; delete headings with full paths; moved files not re-listed as deletions; `data_dir/` paths explained in the intro; "allowlist" in prose; the viewport dimension; the phone width in px; test lists as bullets; the success measure's QA item made a pass condition; verdict names defined.

---

## Traceability

| Source | Covered by |
| --- | --- |
| Z1, Z4, Z5, Z9 | I1 |
| Z2, Z3, Z6, Z7, Z8, Z10 | I14 |
| R-B1, R-M3 | I1 |
| R-B2, C-B1, C-B2 | I2 |
| R-M1, C-M2 | I4 |
| R-M2 | I5 |
| R-M4, C-M1 | I3 |
| R-M5 | I6 |
| R-M6 | I7 |
| R-M7 | I8 |
| R-M8 | I9 |
| R-M9 | I10 |
| C-M3 | I11 |
| C-M4 | I12 |
| C-M5 | I13 |
| S-M1, S-M3, C-N6, R-N5 | I15 |
| S-M2 | I14 |
| all C-N, R-N | I16 |
| all S-N | I17 |
