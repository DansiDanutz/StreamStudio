# Goldfish Annotated Review Report

Status: resolved (2026-11-02, auto accept: 37 fixes applied, 1 escalation kept its safe assumption, 6 nits declined)

**Target:** `daily-episode-factory.md` (FeatureRange lines 1-659; where a fix must also touch the
Detailed Implementation Plan to keep the document consistent, the plan item is named)

Source findings: `critic_report.md` (Stage 7, consolidated C1-C32) plus the Stage 5 zoom-out and
Stage 6 comprehension findings that no Stage 7 reviewer raised (carried as Z- and K- items).
Categories: PROPOSE FIX (valid, edit defined), CONTEST (inaccurate, evidence cited), ESCALATE
(needs a fact only Dan has), DECLINE (nit recorded, not fixed).

Counts: 37 PROPOSE FIX, 0 CONTEST, 1 ESCALATE, 6 DECLINE (C33 added from a PR review finding
that arrived while the gate was open).

## Escalated (needs Dan's knowledge, not only approval)

### [E1] Does HeyGen bill a render that ends in `failed`? [`egm-design`, from C3]
*   **Why escalated:** The fix for C3 charges the ledger for failed renders only if HeyGen bills them. No file in the repo records HeyGen's billing rule for failed renders. Stage 0 can measure it, but the design should say which way it assumes until then.
*   **Proposed Edit if unknown:** "Until Stage 0 confirms otherwise, a render that HeyGen reports `failed` is charged to the ledger as if billed, so the ceiling errs on the safe side."

## Prioritized Findings & AI Suggestions

### [C1] Publish has no mechanism; the hourly poll has nothing to run on [`egm-design`, `egm-structural`, `egm-style`] - Severity: Blocker
*   **Affected Scope:** CUJ 1; planner rules 5-6; "Publish kit, registration, upload, publish status, purge"; Non-Goals; Alternative Q; plan items 17, 39, 41.
*   **Discrepancy:** No call makes an uploaded private video public or scheduled; the hourly poll needs a scheduler the worker lacks and the Non-Goals forbid.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Verified: `core/youtube.py:upload` sets `privacyStatus` once; `jobs` has no run-after column; `store.claim_job` claims at once. The design critic, structural, style, zoom-out and comprehension reviewers all found this independently.
*   ***Proposed Edit:***
    *   Publish section: new subsection "Publish" defining `POST /api/episodes/{id}/publish {publish_at?}` → `core/youtube.py:set_status(api, video_id, privacy, publish_at)` → `PUT /youtube/v3/videos?part=status` with `public` (now) or `private` + `publishAt` (scheduled); "now" sets `published` from the response; "scheduled" sets `scheduled` and the status page shows the time.
    *   Replace `episode_publish_status` with an on-demand check: `GET /api/episodes/{id}` (and therefore the Episode page and MCP `episode_status`) calls `video_status` for a `scheduled` episode and sets `published` on an observed `public`; a passed `publish_at` still private shows "scheduled release did not happen".
    *   Purge: planner rule 6 becomes "on the first advance after `published` (page open, status call or the Purge button), enqueue `episode_purge`". Remove `publish_at` from the upload payload (keep upload private always). Drop plan item 41's poll; rename it `episode_purge` only.

### [C2] Two planners or two threads can pay twice for one clip [`egm-design`] - Severity: Blocker
*   **Affected Scope:** "The planner" rule 1; fan-in paragraph; plan items 29, 30, 33.
*   **Discrepancy:** Clip absence persists for minutes; every planner run re-enqueues; `heygen_clip` reads state, calls `create_video`, then writes state.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Verified against `handlers.py:215-232`.
*   ***Proposed Edit:*** Rule 1: "for every scene whose clip is absent **and** whose `scenes_state[id].job_id` is not a queued or running job (`store.find_active_job`), enqueue one `heygen_clip` and record its job id in the same transaction". `heygen_clip` with an `episode_id` writes `{claimed_by: job_id}` to the state file before `create_video` and exits as a no-op if another job's claim is present. Plan item 33 test: "two planners, one clip, one `create_video`".

### [C3] Worker retries spend before the allowance check [`egm-design`] - Severity: Blocker
*   **Affected Scope:** "The paid step"; CUJ 2; plan item 29.
*   **Discrepancy:** On HeyGen `failed` the handler raises and `fail_job` requeues up to three times with no planner involvement.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Verified against `handlers.py:239-243`, `store.fail_job`, `config.job_max_attempts = 3`.
*   ***Proposed Edit:*** "A `heygen_clip` carrying an `episode_id` never raises on a HeyGen `failed`: it returns `{status: "failed", reason}` as its result, writes a ledger charge (see E1), and enqueues `episode_advance`; the planner applies rule 3. Episode clip jobs are enqueued with `max_attempts = 1` so a worker-level error (network, timeout) also returns to the planner rather than re-rendering." Plan item 29 updated; item 33 adds the test.

### [C4] CUJ 3's edit-after-upload cycle is undefined [`egm-structural`, `egm-design`, `egm-style`] - Severity: Blocker
*   **Affected Scope:** CUJ 3; state list; reservation release; publish section.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** No "YouTube rules" exist in the document; `youtube.upload` short-circuits on the saved video id. Two defensible answers (add the cycle, or narrow the CUJ); the smaller one is proposed and the other is recorded in Future Improvements, so the choice is visible.
*   ***Proposed Edit:*** CUJ 3 becomes "Only changed words are rendered again (before upload)": Given a `budget_approved` episode whose clips exist; When Dan edits scenes 6 and 12 and approves the script again, and approves the 0.75 USD estimate; Then only those two clips render, composites and concat rebuild, cards depending on their durations rebuild, the kit regenerates. Publish section adds: "After `uploaded_private`, `PUT /script` is refused with 409; re-voicing an uploaded episode is a new episode created from the old script (`POST /api/episodes?from=<id>`), and the superseded private video is deleted by Dan or left private." Future Improvements adds "in-place re-voice after upload".

### [C5] No Risks and Mitigations section [`egm-design`, `egm-structural`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** New `## Risks and mitigations` before Non-Functional Requirements, a table: failure mode / detection / episode state / status-page text / recovery. Rows: HeyGen job error or timeout; HeyGen concurrent cap; YouTube upload failure or quota; OAuth refresh failure; disk full; Playwright or `npx hyperframes` crash; whisper missing or wrong language; worker killed mid-planner (launcher update); cut-out silently missing (counts as "no clip"); capture refused by allow-list; monthly ceiling reached; scheduled release cancelled in YouTube Studio.

### [C6] State machine incomplete; states set at enqueue time [`egm-design`, `egm-structural`, `egm-style`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Also absorbs zoom-out N6 (stored status that is derivable).
*   ***Proposed Edit:*** States become the human-gate and terminal states only: `draft`, `script_approved`, `budget_approved`, `in_progress`, `needs_dan`, `uploaded_private`, `scheduled`, `published`, `purged`, `cancelled`. Progress inside `in_progress` is shown from counts ("rendering 12/36, QA 8/36, composing 3/36, uploading"). Entry rules: any stage job in `error` → `needs_dan` with the error in `log`, left by `POST /{id}/advance` after Dan acts; `POST /{id}/cancel` → `cancelled` (releases the reservation, allows purge). `uploaded_private` is set by the planner when it sees the upload result. `failed` removed. CUJ 4 uses `draft`. Diagram updated.

### [C7] Three stores; lock on the wrong one; planner may read results early [`egm-design`, `egm-structural`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Also absorbs zoom-out M2 and comprehension 3.
*   ***Proposed Edit:*** "The episode record is one JSON document in the `record_json` column of `episodes`, read and written under `BEGIN IMMEDIATE`; `episodes/<id>/episode.json` is an export written at purge for the archive. The planner reads the record and the filesystem (clip files, `qa/<scene>.json`, `cards/*/cues.json`, `final.mp4`, the registered recording) and never `jobs.result`; handlers report by writing files. The planner is the only writer of `scenes_state`, `cards`, `outputs` and `log`; the API writes `script`, `budget` and the gate states." Plan items 12, 16 updated; `CLAUDE.md` rule in item 55 reworded.

### [C8] Migration 4 counts; two ledgers [`egm-design`, `egm-structural`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "Migration 4 adds `episodes` and `heygen_ledger`" in the record section and Rollout; "`heygen_ledger` is the cost ledger; `budget.spent` is a cached projection of it".

### [C9] "Sets" rename contradicts Non-Goals and the rollback claim [`egm-design`, `egm-structural`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Also zoom-out B2. The brief's decision 11 asked for the terms to be defined once in `docs/DESIGN.md`; the API rename was added during reconciliation at Dan's request, so this fix reverses a decision Dan made. Flagged in chat.
*   ***Proposed Edit:*** Remove the "Vocabulary" subsection's rename mechanics and plan items 55a-55d; keep a glossary (C17) and a `docs/DESIGN.md` sentence in item 53; add Future Improvements "rename stage sets to 'sets' in the Library, API and catalog as its own change". Rollout rewritten to list every touched existing surface: `item_key` (take defaults to 0), `list_recordings` (additive), `youtube_upload` payload (optional field), `USD_PER_S` move (editor reads it from the estimate), `heygen_clip` (`episode_id` branch only), migration 4 (additive), each with "rollback: revert the commit; no data migration".

### [C10] Script contract omits fields and card-scene semantics [`egm-structural`, `egm-design`, `egm-style`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Contract block gains a `script` wrapper: `{ title, kicker?, tagline?, version, look?, voice_id?, motion?, scenes }` with look/voice/motion defaulting from the saved HeyGen config (`heygen.load_config`); scene gains `reveal?: true`; `question?: <int>` glossed as the question number. Compositor gains a paragraph: "A card scene's frame is the card video slice for that scene (offset by the scene's start inside the card run, measured from clip durations; a card shorter than its run holds its last frame, longer is cut) under the presenter in the picture-in-picture rectangle (`pip_rect`), with the scene's plan overlays. Cue derivation: `avatar` scenes → `avatar`, `card` scenes → `content`, degraded scenes → `pip`; the voice literal passed to `guard_cue` is always `"clip"`, so the guard leaves these unchanged, and it still runs so the shared fixture test exercises the compositor."

### [C11] Intro keyed by per-episode text but not a job [`egm-design`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Two defensible answers; the one consistent with Alternative N is proposed.
*   ***Proposed Edit:*** "The intro's kicker, title and tagline are channel constants ('DANSLAB', 'Build it. Show it. Sell it.', the tagline); one cached `assets/brand/intro/intro.mp4` serves every episode. The episode title appears on the opening table overlay, not in the intro." Remove `kicker`/`tagline` from the script contract; plan item 6 and 9 updated.

### [C12] `approve-budget` callable by any tailnet client [`egm-design`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "`GET /{id}/estimate` returns a one-time `confirm_token` (random, stored on the record, valid 10 minutes). `POST /{id}/approve-budget` requires the token and an allowed `Origin` header, which the editor sends and the MCP client does not. An agent with raw HTTP could still scrape the token; the monthly ceiling is the backstop." Security NFR updated; plan items 17, 24 updated.

### [C13] Unescaped script text in HTML; host-only allow-list; captures under a served folder [`egm-design`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Security NFR and Cards: every script-derived string is HTML-escaped before templating (test with `<script>`); `site_capture` blocks requests to non-allow-listed hosts and private address ranges with `page.route` and aborts on cross-host redirects; allow-list entries are `{host, mode: "auto" | "manual"}` matched on the exact host; manual captures live under `DATA_DIR/sites/<urlkey>/`; `assets/cards/node_modules` is excluded from the static mount (or the HyperFrames workspace moves to `DATA_DIR/cards/`); the launcher runs `npm ci` there. Plan items 5, 45 updated.

### [C14] 25 % WER fails correct renders on names [`egm-design`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** QA: "Both transcript and `voice` are normalised through the voice-names table and a number-to-words pass before the word error rate is computed. A rate above 25 % is `LOOK`; it is `FAIL` only when a re-rendered take's transcript differs from the first take's by more than 25 % as well (two matching transcripts mean the words are right and the recogniser is wrong)."

### [C15] Spec and plan disagree in named places [`egm-design`, `egm-structural`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Also zoom-out B3 and M1, comprehension 14 and 16. The spec is made the source of truth at interface level and loses function-level detail.
*   ***Proposed Edit:*** Spec: list the routes the CUJs use (`POST /api/episodes`, `GET`, `PUT /{id}/script`, `approve-script`, `estimate`, `approve-budget`, `publish`, `cancel`, `advance`, `purge`, `qa/{scene}.jpg`); settings reduced to `episodes_dir`, `capture_allowlist`, `hyperframes_browser`, `episode_rerender_scenes`, `episode_rerender_usd`, `heygen_month_ceiling_usd` (fps 25 and HyperFrames workers become constants; zoom-out M5); card builder named as `episode/hyperframes.py`; MCP tools four; remove the function list from the compositor paragraph and the `item_key` signature, `BEGIN IMMEDIATE`, the 1400 px viewport, the `-w` flag and the 42-character line from the spec (they stay in the plan). Plan items 5, 13, 32, 34, 46 aligned (`check_clip(mp4, cascade)`, exports include `hyperframes` and `publish`).

### [C16] Open Questions already answered [`egm-structural`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Keep Q1 (extended with whisper per clip and compose time per scene) and Q3 narrowed to "which logged-in sites Dan captures by hand"; delete Q2, Q4, Q5.

### [C17] Undefined terms; "card" with three meanings; acronyms [`egm-style`, `egm-structural`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** New "Glossary" subsection at the top of the Technical Plan: episode, scene, set, card (a HyperFrames site composition only), table overlay (the lower-third and chip graphics on avatar scenes), panel (a UI element), take, allowance, degraded, workings, kit, plate, lower, chips. Replace "table card", "small card", "motion card", "'Needs you' card" and "one card on his phone" accordingly. Expand at first use: QA, MCP, SFX, LUFS, tailnet, HyperFrames, rembg, whisper, pip, DAG, EDL, Haar cascade.

### [C18] Forward references to stages [`egm-structural`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** One sentence at the top of the Technical Plan naming the stages (see Z-M4 for the new staging).

### [C19] CUJs misuse states and allowance semantics [`egm-structural`, `egm-style`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "Allowance" defined once: episode-wide, counted in re-render attempts and USD, both caps must hold. CUJ 2 rewritten: allowance 4 attempts; scene 17 fails once and passes on its re-render (1 used); scene 23 fails and its three re-renders fail (3 used, allowance spent); scene 23 degrades. CUJ 3 as in C4. CUJ 4: `draft`; the panel has "Approve budget" and "Send back to writer" (sets a `log` note and leaves `draft`).

### [C20] Overview pipeline sentence [`egm-style`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** The style report's bulleted list.

### [C21] Rejected-clip rename [`egm-design`] - Severity: Nit
*   ***AI Suggestion:*** PROPOSE FIX (cheap, removes a hazard)
*   ***Proposed Edit:*** Drop the rename; rejected takes stay in place, marked in `scenes_state`, and are vaulted like any clip.

### [C22] 8-second rule per scene not per run [`egm-design`] - Severity: Nit
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Validator row: "consecutive avatar scenes with no plan element whose estimated lengths sum to more than 8 s".

### [C23] Compositing parallelism asserted [`egm-design`] - Severity: Nit
*   ***AI Suggestion:*** PROPOSE FIX (one clause in Q1 and Performance NFR).

### [C24] `episode_register` copies the MP4 [`egm-design`] - Severity: Nit
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "moves `final.mp4` into `recordings/` and records the path in `outputs.final_mp4`" (also closes zoom-out N4 and C30).

### [C25] Ceiling default at the cost floor [`egm-design`] - Severity: Nit
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "The default is deliberately tight; Dan sets the real ceiling in settings."

### [C26] Duplicated content [`egm-structural`] - Severity: Nit
*   ***AI Suggestion:*** DECLINE. Each repetition serves its section (non-goal, rejected alternative, future direction).

### [C27] Reasons for rejection [`egm-structural`, `egm-style`] - Severity: Nit
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Prefix the seven entries with a one-line reason before "Chosen instead".

### [C28] Section placement and splitting [`egm-structural`, `egm-style`] - Severity: Nit
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Promote Additional Resources and Future Improvements to `##`; add the missing rule; move "Data flow for one scene" after "Shape of the system"; move Cards before Compositor; one paragraph per handler in the publish section; Overview paragraph 2 moved to The Problem.

### [C29] Validator table details [`egm-structural`, `egm-style`] - Severity: Nit
*   ***AI Suggestion:*** PROPOSE FIX (fill the cell, split the error row, align the 8 s check with Goal 4 via C22).

### [C30] Purge keep-list [`egm-structural`] - Severity: Nit
*   ***AI Suggestion:*** PROPOSE FIX (covered by C24: the registered recording is the only final MP4).

### [C31] `PLAN.md` in Additional Resources [`egm-structural`] - Severity: Nit
*   ***AI Suggestion:*** DECLINE. The plan's item 55 edits `PLAN.md`; the reference is useful to the implementer.

### [C32] Style nits [`egm-style`] - Severity: Nit
*   ***AI Suggestion:*** PROPOSE FIX for the ones that change meaning: N3 (status names as code identifiers), N4 (digits), N5 (`data_dir`), N6 (QA status case: keep `qa_avatar.py`'s names and say so), N14 ("wallet balance after this render"), N37 ("roughly 45 %" gets its basis: the card-scene share of Episode 1 v2's seconds), N38 ("run at most two at a time"). DECLINE the rest (heading case, sentence splits, idiom swaps) as pure style; the style report holds the replacements for a later pass.

### [C33] Cancelling an episode releases money already committed to HeyGen [Greptile, PR review] - Severity: Major
*   **Affected Scope:** "The paid step" (reservation release rule); C6's new `cancelled` state.
*   **Discrepancy:** Cancelling a local `heygen_clip` only stops polling and returns the saved `video_id` (`handlers.py:246-247`); HeyGen keeps rendering and bills. Releasing the whole reservation on cancel lets another episode pass the ceiling with that money.
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** "On `cancelled`, the planner releases only the part of the reservation for clips that were never submitted (no `video_id`). Clips already submitted stay reserved until their render completes or fails and a charge row is written, which the planner does on its next pass even for a cancelled episode." Test added to the ledger tests: cancel with two submitted clips keeps their seconds reserved.

## Carried from Stage 5 (zoom-out) and Stage 6 (comprehension)

### [Z-M1] Technical Plan at implementation altitude [`egm-zoom-out`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX (as part of C15: remove function lists, signatures, flags and constants from the spec; keep interfaces, data flow, rules and gates).

### [Z-M3] Four card templates in v1 [`egm-zoom-out`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Cards: "v1 ships the `generic` template only (address bar, slow scroll, one zoom to the hero, one callout from the scene text), with beats at scene boundaries; `feature-ring`, `compare`, `counter` and word-placed beats follow once the generic card has shipped (Future Improvements)." `card_template` stays in the contract as an optional field accepting `generic` only in v1. Plan items 8, 47, 48 reduced.

### [Z-M4] Smallest version not identified; first video after ~44 files [`egm-zoom-out`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Justification:*** Also zoom-out N7 and comprehension 13.
*   ***Proposed Edit:*** New Technical Plan paragraph "The smallest version" and restaged plan: Stage 0 measurement and dependencies only (HeyGen latency and cap, rembg, whisper per clip, HyperFrames on the Mac; compositing measured in Stage 1 on the ported code; brand assets moved here because Stage 1 needs them); Stage 1 thin slice to a private upload (record, error-level validation, approve-script, estimate and approve-budget with the ledger, `heygen_clip` with take and claim, `scene_compose` on the plate with the guard, concat, cached intro and music bed, kit with chapters, register, upload, publish click, a minimal Episode page with the list and three buttons); Stage 2 QA, allowance, degrade, `needs_dan`, full validator warnings, status detail, MCP tools; Stage 3 generic cards and captures, SFX from cues; Stage 4 hardening, docs, removal of `tools/compose`, e2e test, CI. Four stages instead of six; file items renumbered.

### [Z-M5] Configuration knobs for fixed things [`egm-zoom-out`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX (folded into C15).

### [Z-M6] Goals without measures [`egm-zoom-out`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Goals rewritten as outcomes with numbers: approve-budget to `uploaded_private` overnight (under 12 hours on the Mac Studio; Stage 0 refines); Dan's total interaction under 15 minutes per episode; HeyGen cost per episode within estimate plus allowance; a test proves zero `heygen_clip` jobs without `budget.approved_at`; every production rule enforced automatically (mechanism moved to the Technical Plan). Also absorbs zoom-out N8.

### [Z-M7] Four status surfaces [`egm-zoom-out`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX
*   ***Proposed Edit:*** Defer the Library group and `episode.status` action to Future Improvements; keep API, Episode page, MCP. Plan items 19, 23 reduced.

### [Z-N1] One-off converter in production code [`egm-zoom-out`] - Severity: Nit
*   ***AI Suggestion:*** PROPOSE FIX (converter lives under `server/tests/`; the converted `script.json` is the fixture).

### [Z-N2] Whisper per clip unmeasured [`egm-zoom-out`] - Severity: Nit
*   ***AI Suggestion:*** PROPOSE FIX (Q1 and Stage 0; fallback "one pass on `final.mp4` with scene offsets" named in Risks).

### [Z-N3] Script-text captions duplicate the transcript [`egm-zoom-out`] - Severity: Nit
*   ***AI Suggestion:*** PROPOSE FIX (state the reason: on-screen spellings per DESIGN rule 6; drop plan item 42).

### [Z-N5] Episode 1 v2 re-render costs money [`egm-zoom-out`] - Severity: Nit
*   ***AI Suggestion:*** PROPOSE FIX (Verification: the three-scene real episode is the paid integration check; the Episode 1 v2 re-render is optional and Dan-approved).

### [K-13] Stage 0 measures a compositor ported later [`egm-comprehension`] - Severity: Major
*   ***AI Suggestion:*** PROPOSE FIX (folded into Z-M4).

### [Z-N6, Z-N7, Z-N8] [`egm-zoom-out`] - Severity: Nit
*   ***AI Suggestion:*** PROPOSE FIX (folded into C6, Z-M4, Z-M6).

### [Carried but declined]
*   zoom-out M1 items that are style only, structural 17 and 25, style nits other than those in C32: DECLINE as above.

---

# Stage 9 resolution (Implementation Readiness)

Status: resolved (2026-11-02, applied under Dan's prior "approve" for the batch)

**Target:** `daily-episode-factory.md` (DetailedRange 834-1302, plus the specification passages
the plan fixes depend on). Source: `implementation_readiness_report.md` (I1-I17, which absorb the
Stage 8 findings Z1-Z10).

Counts: 17 PROPOSE FIX, 0 CONTEST, 0 ESCALATE, 0 DECLINE (the style nits in I17 that change
meaning are applied; pure wording nits are applied where the sentence was rewritten anyway and
otherwise left, recorded as accepted).

| Finding | Suggestion | Justification and edit |
| --- | --- | --- |
| I1 | PROPOSE FIX | Verified against `worker/main.py:53-57`, `handlers.py:214-247`. Planner rewritten as a condition table with Stage 1 and Stage 2 predicates; HeyGen `failed` recorded in the clip state file; `run_one` enqueues the planner on error for episode jobs; claim valid only while its job is live and transferred on recovery; `youtube_upload` enqueues the planner; render failure after the allowance → `needs_dan`, QA failure → `degraded`. |
| I2 | PROPOSE FIX | Verified against `api/routes/jobs.py`, `heygen.py:68`, `ci.yml:10`, `pyproject.toml`. Package import rule; `episode/handlers.py` registration via `worker/main.py`; CI and Makefile install the extra in Stage 0; import test without the extra. |
| I3 | PROPOSE FIX | Verified against `handlers.py:137-146`, `youtube.py:139`. `Script.channel`, resolution at approve-budget, payload spelled out. |
| I4 | PROPOSE FIX | Verified against `episode-01-v2.plan.json`, `render.py`. Full `Plan` fields; converter rules; validation test. |
| I5 | PROPOSE FIX | Ledger columns, uniqueness, unconsumed formula, seconds source. |
| I6 | PROPOSE FIX | `cues.json` schema; generic card as a function; SFX table constant; bed in manifest; workspace ships `package.json` + lockfile. |
| I7 | PROPOSE FIX | Decode path with `libvpx-vp9`, seat from the plate JSON, frame count, `inputs_hash`. |
| I8 | PROPOSE FIX | `kit.json` keys, chapter rules ported from `kit.ts`, `Script.tags`, intro offset. |
| I9 | PROPOSE FIX | `EpisodeOut` shape; `api.ts` exports. |
| I10 | PROPOSE FIX | In-package WER and number-to-words; per-take transcript files. |
| I11 | PROPOSE FIX | README lines per item; four READMEs added. |
| I12 | PROPOSE FIX | One intro file, re-rendered at 25 fps; generator renders with `-f 25`. |
| I13 | PROPOSE FIX | SRT path passed and purged; `TranscribeError` caught. |
| I14 | PROPOSE FIX | Stage 1 trimmed to publish-now; `GET /{id}` pure with `POST /{id}/refresh`; purge button only; `PUT /script` edge; single release trigger; workspace bootstrap in Stage 3; per-stage preflight. |
| I15 | PROPOSE FIX | Item 49 list; `qa/<scene>.jpg` everywhere. |
| I16 | PROPOSE FIX | All listed decisions pinned in the relevant items. |
| I17 | PROPOSE FIX (partial) | Meaning-changing style items applied; remaining wording nits accepted as is. |

### PR review corrections after Stage 9

Five findings from the automated PR review of the Stage 9 head, each verified against the source
and applied to the final design and the mirror:

| # | Finding | Fix |
| --- | --- | --- |
| P1 | Planner row 3 queued `scene_qa` for a scene whose render failed or is still rendering | Row 3 requires the clip and cut-out to exist, the QA result to be missing and no live `scene_qa` job; rows 3a and 3c own failed renders |
| P2 | `PUT /{id}/script` left `final.mp4`, `kit.json` and `outputs.recording_id` in place, so rows 7 to 9 kept the old video | An edit that changes the hash unlinks the final outputs and clears the recording id (the registered recording stays as an earlier take); 409 while an upload job is live |
| P3 | The fixture converter copied `kind` into `Plan`, which forbids extra keys | `kind` is consumed by the scene; a test validates the converted fixture |
| P4 | Re-approval released the previous reservation while a render was still running | The new reservation includes every live render job's estimate before the previous one is released |
| P5 | An episode's `projects` row was listed by `/api/projects` and its detail route would fail on `latest_edl` | `list_projects` excludes rows with an `episodes` row; `project_or_404` answers 404 for them (new plan item 13a) |
| P6 | The P4 wording counted an unchanged scene twice while its render was running | The reservation has one line per distinct (clip key, take): live jobs under their own key, plus scenes with no clip and no live job for their current key |

### Stage 9 re-audit resolution (round 2)

The confirming re-audit (`implementation_readiness_report.md`, round 2) returned five Majors and
nine Nits, J1 to J13, all contradictions between plan items or against the source. Each was
applied under the standing auto-accept decision; no finding was contested or escalated. The
review then concluded and the design's status moved to Final.

### PR review corrections after conclusion (Codex)

| # | Finding | Fix |
| --- | --- | --- |
| P7 | Planner rows 4 to 9 had no live-job exclusion, so a planner run during a capture, card render, composite or assembly enqueued the work twice | Every row records its job id in the record (`qa_job_id`, `capture_job_id`, `card_job_id`, `compose_job_id` per scene; `assemble_job_id`, `kit_job_id`, `register_job_id`, `upload_job_id` per episode) and skips while that job is live |
| P8 | The charge index on (episode, scene, take) collided when an edit changed the clip key without a new take | Ledger rows carry `clip_key`; charges are unique per (episode, clip key) |
