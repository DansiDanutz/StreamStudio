# Critic Report (Stage 7, round 1)

**Target:** `daily-episode-factory.md`, FeatureRange lines 1-659 (the feature specification).

## Reviewer status

| Reviewer | Standard | Status | Raw findings |
| --- | --- | --- | --- |
| `egm-design` (design critic) | feature-spec-standard | completed | 3 Blocker, 9 Major, 9 Nit |
| `egm-structural` | feature-spec-standard + design_doc template | completed | 2 Blocker, 14 Major, 10 Nit |
| `egm-style` | persona writing standard | completed | 0 Blocker, 6 Major, 38 Nit |

All three ran in fresh contexts, dispatched directly. Findings below are deduplicated across the
three reports; each consolidated finding lists the raw findings it absorbs
(`design-1-B1` = design critic, round 1, Blocker 1, and so on) and any overlap with the Stage 5
zoom-out and Stage 6 comprehension reports, so the resolve step can close them together.

Round verdict: **not clean** (Blockers and Majors present).

---

## Blockers

### C1. The third click, "Publish", has no mechanism, and the hourly status poll has nothing to run on
- **Absorbs:** design-1-B3, design-1-M3, structural-1-B1, style-1-M3 (part); zoom-out B1; comprehension 1, 2.
- **Scope:** CUJ 1; planner rules 5-6; "Publish kit, registration, upload, publish status, purge"; Non-Goals ("no scheduler"); Alternative Q.
- **Discrepancy:** The video is uploaded private before Dan clicks Publish, yet the only publishing mechanism is `status.publishAt` passed at upload time. Nothing updates an already-uploaded video (`core/youtube.py:upload` sets `privacyStatus` once; there is no `videos.update`). "Publish now" therefore does not exist in the design, and Alternative Q says YouTube Studio was rejected. Separately, `episode_publish_status` "polls every hour", but `jobs` has no run-after column, `store.claim_job` takes the oldest queued row at once, and the worker has no timer; the poll is either a handler sleeping in one of two worker slots for days, or nothing.
- **Recommendation:** Add a "Publish" subsection: `POST /api/episodes/{id}/publish {publish_at?}` calls `PUT /youtube/v3/videos?part=status` through a new `core/youtube.py:set_status(api, video_id, privacy, publish_at)` with `public` (now) or `private` plus `publishAt` (scheduled); "now" sets `published` directly from the response. Replace the hourly poll with an on-demand check: `GET /api/episodes/{id}` and the Episode page refresh call `video_status` for a scheduled episode; `published` is set on an observed `public`. Purge becomes a planner rule that fires when a `published` episode is next advanced (page open, button, or MCP status call). Drop `publish_at` from the upload payload.

### C2. Two planners, or two worker threads, can pay HeyGen twice for one clip
- **Absorbs:** design-1-B1.
- **Scope:** "The planner"; fan-in paragraph ("two planners running at once are harmless").
- **Discrepancy:** Rule 1 enqueues a `heygen_clip` for every scene whose clip file is absent. The file appears only when the render finishes minutes later, so every `episode_advance` enqueued by a finishing handler in that window enqueues the same clip again. `BEGIN IMMEDIATE` on the `episodes` row serialises planners but does not stop the second from reaching the same conclusion. `heygen_clip` itself (`handlers.py:215-232`) reads the state file, calls `create_video`, then writes the state file; two threads for one key both see no state and both pay.
- **Recommendation:** The planner records `scenes_state[id].job_id` when it enqueues and never enqueues while that job is queued or running (`store.find_active_job(conn, "heygen_clip", key, field="key")` inside its transaction). `heygen_clip` with an `episode_id` writes a claim to the state file before `create_video`. Test: two planners, one clip, one `create_video` call.

### C3. Worker retries spend money before the planner can check the allowance
- **Absorbs:** design-1-B2.
- **Scope:** "The paid step" ("worker retries charge the allowance"); CUJ 2 ("No money was spent beyond the allowance").
- **Discrepancy:** On HeyGen `failed`, `heygen_clip` deletes its state file and raises (`handlers.py:239-243`); `main.py:run_one` calls `store.fail_job`, which requeues immediately while `attempts < 3`. The next attempt starts a new paid render with no planner involvement. A failed job has `error`, not `result`, so there is nothing for the planner to read. Up to two unbudgeted renders per scene are possible.
- **Recommendation:** A `heygen_clip` carrying an `episode_id` does not raise on HeyGen `failed`: it returns `{status: "failed", reason}` as a normal result, writes a ledger charge if HeyGen bills failed renders (Stage 0 finds out), and enqueues `episode_advance`; the planner applies rule 3. Alternatively enqueue episode clip jobs with `max_attempts = 1`.

### C4. CUJ 3 (edit after upload) relies on transitions and rules the specification does not define
- **Absorbs:** structural-1-B2, design-1-M2 (part), style-1-M3, comprehension 9.
- **Scope:** CUJ 3; state list; reservation release rule; publish section.
- **Discrepancy:** CUJ 3 edits an `uploaded_private` episode, re-approves, shows a new cost screen and says "the upload is replaced or re-uploaded according to the YouTube rules in the Technical Plan". No such rules exist; the state list has no edge from `uploaded_private` back to `script_approved`; the reservation is released at `uploaded_private` and no second one is described. `youtube_upload` short-circuits on the saved `video_id` for the same recording id (`core/youtube.py:323-325`), so a same-id re-upload returns the old video and a new id orphans the first private one.
- **Recommendation:** Either add the re-approval cycle (edge `uploaded_private → script_approved` on `PUT /script`, a new reservation on re-approval, a new registration id, `videos.delete` of the superseded private video or an explicit statement that Dan deletes it, refusal after `published`), or narrow CUJ 3 to an edit before upload and move post-upload re-voicing to Future Improvements.

---

## Major

### C5. No Risks and Mitigations section
- **Absorbs:** design-1-M1, structural-1-10.
- **Scope:** whole document; Non-Functional Requirements is the nearest.
- **Discrepancy:** The standard requires failure modes, security, scalability and complexity risks with mitigations. Missing: a clip job in `error` (network, HeyGen concurrent cap, 30-minute timeout); YouTube upload failure, quota, OAuth expiry; disk full mid-episode; Playwright or `npx hyperframes` crash; whisper absent or wrong language; the Mac launcher killing the worker mid-planner; a silently missing cut-out (`_cutout_clip` returns `False` on `ImportError` and `heygen_clip` reports `done`).
- **Recommendation:** Add "Risks and mitigations": one row per failure mode with detection, resulting state, status-page text and recovery action. Make a missing `.cutout.webm` count as "no clip" in rule 1.

### C6. The state machine is incomplete and states are set at enqueue time
- **Absorbs:** design-1-M2, structural-1-4, structural-1-15, style-1-M2, style-1-M5; comprehension 7.
- **Scope:** states; planner rules 4-5; "The paid step" ("is cancelled"); CUJ 4 ("script ready").
- **Discrepancy:** `needs_dan` is reachable from three states but no rule sets it (allowance exhaustion degrades instead, per Alternative G); `failed` has no cause; "cancelled" is used but is not a state or a route; CUJ 4 uses "script ready", which is not a state. Rule 5 sets `uploaded_private` while enqueuing four handlers that have not run, so the status page shows a state that is not yet true, and nothing says what happens when `youtube_upload` finishes. The architecture diagram omits the publish status step.
- **Recommendation:** Any stage job in `error` → `needs_dan` with the error in `log`; `POST /{id}/advance` leaves it. Add `cancelled` with `POST /{id}/cancel` (releases the reservation, allows purge). Define `failed` or remove it. Add `assembling` and `uploading`, or set `uploaded_private` from the upload result. CUJ 4: `draft`.

### C7. Three stores for one episode; the lock protects the wrong one; the planner may read results before they exist
- **Absorbs:** design-1-M9, structural-1-5; zoom-out M2.
- **Scope:** "The episode record"; "Shape of the system" ("the planner is the only writer of `episode.json`").
- **Discrepancy:** `status` and `budget` live in both the `episodes` row and `episode.json`; the row is written under `BEGIN IMMEDIATE`, the file afterwards, so a crash leaves them disagreeing. The API also writes `episode.json` (create, approve-budget), so "only writer" is false. Handlers enqueue `episode_advance` from inside the handler while `finish_job` writes `result` only after the handler returns, so a planner can run before `jobs.result` exists.
- **Recommendation:** One canonical store. Simplest: `record_json` column on `episodes` (as `edl_versions` stores JSON), the lock then covers the record; `episode.json` on disk is an export at purge. State that the planner reads only the filesystem and the record, never `jobs.result`. Restate the invariant as "the planner is the only writer of `scenes_state`, `cards`, `outputs` and `log`; the API writes `script` and `budget`".

### C8. Migration 4 is one table in two places and two tables in a third; two cost ledgers
- **Absorbs:** design-1-N1, structural-1-6.
- **Scope:** "The episode record" ("adds one table"); "The paid step" (`heygen_ledger`); Rollout; "Status" (`budget.spent` is the cost ledger).
- **Recommendation:** "Migration 4 adds `episodes` and `heygen_ledger`" everywhere; `heygen_ledger` is authoritative, `budget.spent` a cached projection.

### C9. The "sets" rename contradicts the Non-Goals and falsifies the rollback statement
- **Absorbs:** design-1-M5, structural-1-7, structural-1-8; zoom-out B2.
- **Scope:** Non-Goals ("any change to the stage"); "Vocabulary"; Rollout and rollback.
- **Discrepancy:** Renaming the Library tab, the `scene:` artifact kind, two agent actions, the primary API path and the `Segment.scene` documentation is a cross-cutting change with no Goal and no CUJ, inside a spec whose rollout section says "rolling back is removing the routes". It also ignores the `item_key` signature change, the `list_recordings` extension, the `youtube_upload` payload change and the `USD_PER_S` move.
- **Recommendation:** Move the rename to its own spec, keeping a glossary sentence in `docs/DESIGN.md` ("scene = script unit; the saved layouts are called sets in prose"). Rewrite Rollout to list each touched existing surface with its rollback.

### C10. The script contract omits fields and semantics the rest of the spec uses
- **Absorbs:** structural-1-9, design-1-N2, design-1-N4, style-1-M4; comprehension 4, 5, 8, 15.
- **Scope:** script contract code block; validator table; "Compositor"; file 14 of the plan.
- **Discrepancy:** `reveal` is checked but not declared; script-level `title`, `kicker`, `tagline`, `version` are used but not declared; `question?: 1` has no type; the HeyGen look, voice and motion that `item_key` needs come from nowhere (`cfg` in `scene_key` is undefined); what a `kind: card` scene's frame contains (card video plus the presenter in the small picture-in-picture rectangle) and how one card video is sliced per scene is never stated; the guard call is under-specified (which cue per kind; the voice literal is always `"clip"`; the small card for degraded scenes comes from a rule, not the guard).
- **Recommendation:** Add a `script` block (title, kicker, tagline, version, look, voice, motion defaults from the HeyGen config, scenes) and `reveal?: true`; give `question` a type; add one paragraph to the compositor on card-scene framing and slicing; state the cue derivation (`avatar → avatar`, `card → content`, degraded → `pip`) and that the guard still runs for the shared fixture test.

### C11. The intro is keyed by per-episode text but is not a job
- **Absorbs:** design-1-M4.
- **Scope:** "Assets and toolchain"; Alternative N; Goal 1.
- **Discrepancy:** If kicker, title and tagline vary per episode, a new `intro-<hash>.mp4` must be rendered by hand before every episode, contradicting "zero terminal commands per episode" and Alternative N's reason ("they change with branding, not episodes").
- **Recommendation:** Fix the intro text to channel constants (one cached MP4; the episode title goes on a table overlay), or add a free local `intro_render` job the planner enqueues when the hash is missing. State which.

### C12. `approve-budget` is callable by any tailnet HTTP client
- **Absorbs:** design-1-M6.
- **Scope:** "The paid step"; Security NFR.
- **Discrepancy:** The MCP server is a thin HTTP client; any agent that can reach the API can POST the approval. "No MCP tool can approve" is not a control. The brief raised the same gap for `/api/heygen/render`.
- **Recommendation:** The estimate response carries a one-time `confirm_token` that only the Episode page renders into the button; `approve-budget` must echo it within a few minutes, and `Origin` must be present and allowed on that route. Say that the monthly ceiling is the backstop.

### C13. Script text reaches HyperFrames HTML unescaped; the allow-list is host-only; manual captures sit under a served folder
- **Absorbs:** design-1-M7; comprehension 12.
- **Scope:** "Cards"; Security NFR; "Assets and toolchain".
- **Discrepancy:** `card_render` fills templates with scene `text` from agent-posted scripts; `Comp` writes raw HTML, so this is script injection into a Chromium on the Mac. `site_capture` checks only host patterns, so a listed host can redirect to `127.0.0.1:8787` or a tailnet peer, and subresources are unrestricted. Hand-captured logged-in pages under `assets/sites/` are served at the web root, as would be `assets/cards/node_modules`. The allow-list is "a list of host patterns" yet file 45 says it can say `manual`.
- **Recommendation:** HTML-escape every script-derived string (test with `<script>`); `site_capture` blocks non-allow-listed hosts and private ranges with `page.route` and aborts on cross-host redirects; manual captures live under `DATA_DIR/sites/`; `assets/cards/node_modules` is excluded from the static mount; define the allow-list entry as `{host, mode: auto|manual}` with an exact-host match.

### C14. The 25 % word-error rule will fail correct renders on names and numbers
- **Absorbs:** design-1-M8.
- **Scope:** "QA"; DESIGN rule 6.
- **Discrepancy:** Voice-spelled names ("Smarty", "WorldCup twenty-six dot world"), product names and numbers are what whisper transcribes inconsistently; a 10 s scene has about 25 words, so 6 wrong words trips the rule on a perfect render, then the paid re-render gets the same result.
- **Recommendation:** Normalise both sides through the voice-names table and a number-to-words pass; treat high WER as `LOOK` unless face or glitch checks also fail; `FAIL` only when the re-rendered take's transcript differs from the first.

### C15. The specification and the implementation plan disagree in named places
- **Absorbs:** design-1-N8, structural-1-11, structural-1-16; zoom-out B3; comprehension 14, 16.
- **Scope:** settings names (spec `episode_rerender_scenes` vs plan `_min`/`_fraction`, plus `episode_fps`); compose function list (`table_glow`, `neon_frame`); `check_clip(mp4)` vs `check_clip(mp4, cascade)`; MCP tools (three vs four); routes the CUJs click but the spec never names (`PUT /script`, `approve-script`, `publish`, `purge`, `qa/{scene}.jpg`); card builder location (`tools/compose/motion/build.py` vs `episode/hyperframes.py`); `episode/__init__` exports missing `hyperframes` and `publish`.
- **Recommendation:** Make the spec the source of truth for routes, settings and module locations at interface level, strip function-level detail from it (zoom-out M1), and align the plan.

### C16. Open Questions contains questions the document already answers
- **Absorbs:** structural-1-3.
- **Recommendation:** Keep Q1 (Stage 0 numbers) and the open part of Q3 (Dan decides per logged-in site); delete Q2, Q4, Q5 and leave their resolutions where they live.

### C17. Undefined terms, "card" with three meanings, acronyms at first use
- **Absorbs:** style-1-M1, style-1-N1, style-1-N2, structural-1-12; comprehension 10, 11.
- **Scope:** Overview onward; "Vocabulary".
- **Discrepancy:** "card" means the HyperFrames site composition, the table overlay on avatar scenes and two UI elements. "workings", "plate", "take", "allowance", "degraded", "LOOK", "kit", "set", "lower", "chips", "kicker" are used before or without definition. HyperFrames, rembg, QA, MCP, LUFS, tailnet, pip, DAG, EDL, Haar cascade and whisper are not expanded at first use. The "Vocabulary" section defines none of them.
- **Recommendation:** A glossary at the top of the Technical Plan (episode, scene, set, card = site composition, table overlay, panel for UI, take, allowance, degraded, workings, kit, plate, lower, chips, kicker) and a one-clause expansion at each acronym's first use.

### C18. Forward references to stages before they are defined
- **Absorbs:** structural-1-13.
- **Recommendation:** One sentence at the top of the Technical Plan naming the six stages, or "see Detailed Implementation Plan, Stage N" at each use.

### C19. CUJs misuse states and allowance semantics
- **Absorbs:** structural-1-14, style-1-M2; comprehension 6; structural-1-26.
- **Scope:** CUJ 2 ("exhausts its share"), CUJ 3 (Given contains actions, When is an outcome, the approval click is missing), CUJ 4 ("script ready", "two buttons" undefined).
- **Recommendation:** Episode-wide allowance in re-render attempts, both caps must hold; rewrite CUJ 2's arithmetic to match; rewrite CUJ 3 as Given/When/Then with the approval click; CUJ 4 in `draft` with the two buttons named (Approve budget, Send back to writer) and the reject path defined.

### C20. The Overview's pipeline sentence is one 80-word sentence
- **Absorbs:** style-1-M6.
- **Recommendation:** A bulleted list of the pipeline stages.

---

## Nit

### C21. Rejected-clip rename is unnecessary and may break editor references
- **Absorbs:** design-1-N3. With `take` in the hash the new render has a new name; renaming `<key>.mp4` breaks Director segments pointing at it, and `vault.local_files` backs up every rejected take. Keep rejected takes in place, mark them in `scenes_state`, say whether they are vaulted.

### C22. The 8-second rule is checked per scene, not per run
- **Absorbs:** design-1-N5. Three consecutive 6 s avatar scenes with no plan element pass. Validate across consecutive avatar scenes.

### C23. Compositing parallelism is asserted, not shown
- **Absorbs:** design-1-N6. Pillow/numpy on worker threads shares one GIL. Add compose time per scene to Q1.

### C24. `episode_register` copies the final MP4
- **Absorbs:** design-1-N7; zoom-out N4. Hard-link or move.

### C25. Monthly ceiling default sits at the brief's cost floor
- **Absorbs:** design-1-N9. The brief estimated 400 to 550 USD a month; a 400 default refuses late-month approvals. Raise it or say it is deliberately tight.

### C26. Duplicated content across Non-Goals, Alternatives and Future Improvements
- **Absorbs:** structural-1-17. The compositor side-by-side and the local-voice lever each appear three times. State once, cross-reference.

### C27. "Reason for Rejection" entries that give no reason
- **Absorbs:** structural-1-18, style-1-N32. Alternatives G, J, L, N, O, Q start with "Chosen instead"; P bundles three options. Add a one-line reason first.

### C28. Section placement and splitting
- **Absorbs:** structural-1-19, structural-1-20, structural-1-21, structural-1-24, style-1-N8, style-1-N28. Overview paragraph 2 is scope; the publish paragraph covers five handlers; "Data flow for one scene" belongs beside "Shape of the system"; Cards should precede Compositor; Additional Resources and Future Improvements are nested under NFR; missing horizontal rule.

### C29. Validator table details
- **Absorbs:** structural-1-22, style-1-N18. Empty rule-source cell; the error row bundles two checks; the 8 s check is weaker than Goal 4.

### C30. Purge keep-list ambiguity
- **Absorbs:** structural-1-23. Say whether `episodes/<id>/final.mp4` stays after registration.

### C31. Additional Resources cites `PLAN.md`, which the specification never uses
- **Absorbs:** structural-1-25.

### C32. Style nits
- **Absorbs:** style-1-N3 to N7, N9 to N17, N19 to N31, N33 to N38. Status names spelled three ways; numbers in words and digits; `DATA_DIR` vs `data_dir`; QA status case; heading case; the loudness "table" that is prose; Goal 7's bold pattern; two ideas per sentence in Goal 2; "stop at the money"; "after" without object; "a handful of handlers"; "Nothing new runs"; "runs on post"; "`LOOK` is recorded and continues"; "fan-in"; the two 60-word ledger sentences; "cohort", "canonical clock"; "untouched in time"; unclear subjects; "goes"; the `cards_v2.T` aside; "named after each"; "All six lenses"; "quality is not traded"; "asynchronous gates"; "Cleaner model"; the compressed Alternative R con; "roughly 45 %" without basis; "serialise" misstating concurrency 2. The style report has the exact replacement for each.

---

## Traceability to earlier stages

| Earlier finding | Covered by |
| --- | --- |
| zoom-out B1 (poller needs scheduler) | C1 |
| zoom-out B2 (sets rename is scope creep) | C9 |
| zoom-out B3 (spec and plan disagree) | C15 |
| zoom-out M1 (spec at implementation altitude) | C15, C17 (resolve step) |
| zoom-out M2 (three stores) | C7 |
| zoom-out M3 (four templates in v1), M4 (thin slice), M5 (knobs), M6 (goals without numbers), M7 (four status surfaces), N1-N8 | not raised by Stage 7 reviewers; carried as open zoom-out findings for the resolve step |
| comprehension 1, 2 | C1 |
| comprehension 3 (how the planner learns upload finished) | C6, C7 |
| comprehension 4, 5, 8, 15 | C10 |
| comprehension 6 | C19 |
| comprehension 7 | C6 |
| comprehension 9 | C4 |
| comprehension 10, 11 | C17 |
| comprehension 12 | C13 |
| comprehension 13 (Stage 0 measures a compositor ported in Stage 3) | not raised by Stage 7 reviewers; carried |
| comprehension 14, 16 | C15 |
| comprehension 17, 18 | C32 |
