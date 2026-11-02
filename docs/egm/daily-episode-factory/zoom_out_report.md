# Zoom Out Report (Stage 5)

Reviewer status: completed (`egm-zoom-out`, fresh context, dispatched directly because the
synthesizer cannot nest reviewers in this harness).

Target: `daily-episode-factory.md`, full file. Standard: `zoom-out-standard.md`.

Note on line numbers: the reviewer read the document at 1,101 lines. While it ran, five
Greptile findings (recordings discovery, ledger-based ceiling, publish-before-purge, URL-keyed
captures, `card_template` in the contract) were applied, and the file is now 1,141 lines with the
Detailed Implementation Plan starting at line 660 instead of 638. Section names below are
unaffected; line numbers are approximate after line 224.

Context read by the reviewer: `concepts_brief.md`, `hypothesis.md`, `CLAUDE.md`, `PLAN.md`,
`docs/DESIGN.md`, `docs/AGENTS.md`, `docs/scripts/episode-01-v2.md`, `tools/compose/README.md`,
`tools/compose/motion/README.md`, the contract READMEs under `server/src/streamstudio` and
`web/src`, and `core/db.py`, `core/heygen.py`, `core/config.py`, `core/transcribe.py`,
`core/youtube.py`, `core/store.py`, `worker/handlers.py`, `api/routes/heygen.py`,
`api/routes/agent.py`, `render/lipsync.py`.

Context sufficiency: passes. The Overview and The Problem state what is being built and why, and
the reuse claims about `heygen_clip`, `item_key`, the worker, the YouTube upload and the agent bus
check out against the code.

---

## Blockers

### B1. The publish-status poller needs a scheduler the worker does not have, and the design lists schedulers as a non-goal
- **Where**: "Publish kit, registration, upload, publish status, purge"; planner rule 6; file 41; Non-Goals.
- **Discrepancy**: `episode_publish_status` "polls the video's privacy status every hour". `core/store.py:claim_job` claims the oldest queued row immediately; there is no delayed or recurring job in `jobs`, and `worker/main.py` has no timer. The only ways to get "hourly" are a handler that sleeps for an hour (holding one of `worker_concurrency = 2` slots) or a new scheduling mechanism, which the Non-Goals rule out. The poller exists only to trigger `episode_purge` automatically; `CLAUDE.md` says the rule is "offer to delete them", not delete unattended, and file 17 already adds `POST /{id}/purge`.
- **Recommendation**: Remove `episode_publish_status`. `POST /{id}/publish` with no `publish_at` sets `published` directly (it made the YouTube call); with `publish_at` it records the time and the status page shows "scheduled". Purge is the existing button, or a planner rule that runs when Dan next opens an episode whose `publish_at` has passed. The `published → purged` chain then needs no scheduler.

### B2. The "scenes → sets" rename is a repo-wide public-contract change bundled into the feature
- **Where**: "Vocabulary: scenes are script scenes, stage layouts are sets"; files 55a-55d; file 53.
- **Discrepancy**: Renaming `/api/scenes` to `/api/sets`, the `scene:<id>` artifact kind, the `scene.activate`/`scene.new` actions, the Library tab, `bridge.ts:EXECUTORS`, `sceneSync.ts`, the MCP guide text, plus a one-release alias and deprecation lifecycle, touches agents, the editor and the server for a reason ("so 'scene' means one thing") that no CUJ or Goal depends on. The brief's decision 11 asked for the terms to be "defined once in `docs/DESIGN.md`"; the design escalates that into an API migration. It is scope creep in a six-stage programme that already lists 57 files.
- **Recommendation**: Cut the vocabulary section and files 55a-55d from this spec. Keep a one-paragraph glossary in `docs/DESIGN.md` (file 53) that says "scene = script unit; the Library's saved layouts are called sets in prose". If the rename is wanted, it is its own small change with its own review.

### B3. The feature specification and the implementation plan disagree on what will be built
- **Where**: Technical Plan vs Detailed Implementation Plan.
- **Discrepancy**: Because the spec is written at code level (see M1), it contradicts the plan in several places a builder would have to resolve alone:
  - Allowance settings: the spec defines `episode_rerender_scenes = max(2, ceil(0.1 * scenes))` as one setting; file 5 splits it into `episode_rerender_scenes_min` and `episode_rerender_fraction`.
  - Card builder location: the spec says `episode/cards.py` imports `tools/compose/motion/build.py:Comp`; file 46 moves it to `server/src/streamstudio/episode/hyperframes.py`, and file 50 deletes `build.py`.
  - Intro generator: the spec keeps the intro as a cached asset only; file 9 moves `make_intro.py` to `tools/brand/`, a path mentioned nowhere in the spec.
  - Scene contract: the validator table checks `reveal: true`, but the scene shape has no `reveal` field; file 14 adds it silently.
  - Settings: the spec's list has seven settings; file 5 adds `episode_fps` and the two allowance settings above (nine).
  - `episode/__init__.py` (file 13) exposes `contract, validate, planner, qa, compose, mix, cards, capture, kit, preflight` but not `hyperframes` or `publish`, both of which files 41 and 46 create.
- **Recommendation**: Lift the spec back to interfaces and data flow (M1) so there is one place where concrete names live, then reconcile the plan against it. At minimum fix the six items above before anyone codes from this document.

---

## Major

### M1. The Technical Plan is written at implementation altitude
- **Where**: the whole Technical Plan, especially the paid step, QA, compositor, cards and publish sections.
- **Discrepancy**: The standard asks high-level sections to carry architecture, interfaces and data flow. The spec instead carries: the full function list to be moved from `render.py`; the `item_key(..., take=0)` signature and the `<key>.a<take>.mp4` rename; `BEGIN IMMEDIATE`; `loudnorm=I=-14:TP=-1.5:LRA=11` and four LUFS numbers; `page.screenshot(full_page=True)`, `document.querySelector`, a 1400 px viewport; the `-w` flag to `npx hyperframes render`; 42-character caption lines; `WORDS_PER_S = 2.5`; the `HeygenPanel.tsx` → `core/heygen.py:USD_PER_S` move; the 25 % word-error threshold. The Detailed Implementation Plan then repeats most of it, which is how B3 happened.
- **Recommendation**: Keep in the spec: the episode record's fields and states, the job list with inputs and outputs, the planner's six rules in prose, the three human gates, the security boundary for captures, and the decision table for QA outcomes. Move every file path, function name, constant, CLI flag and threshold into the plan, once.

### M2. One episode lives in three stores, and the lock does not cover the one that matters
- **Where**: "The episode record"; the planner's concurrency argument; file 16.
- **Discrepancy**: An episode is a `projects` row (correlation only), an `episodes` SQLite row (status, title, budget_json, youtube_video_id) and `episode.json` on disk ("the full record"). `status` and `budget` exist in two of them. The planner's concurrency argument is "`BEGIN IMMEDIATE` on the `episodes` row", but the state it protects is written to a file via temp-plus-rename after the transaction; a crash between the two leaves the row and the file disagreeing, and two planners can still both pass the row check and both write the file. Minimalist data flow asks for one source of truth.
- **Recommendation**: Pick one. Simplest that keeps the lock honest: put the record JSON in a `record_json` column of `episodes` (SQLite is already the worker's coordination point, and `edl_versions` stores JSON blobs the same way). `episode.json` on disk then becomes an export written at purge time for the archive, not a live store. The `projects` row stays only because `jobs.project_id` needs it.

### M3. Four card templates are built in v1 while the design itself says to ship only the generic card first
- **Where**: cards section; file 8; file 47; Future Improvements.
- **Discrepancy**: Stage 4 creates `generic`, `feature-ring`, `compare`, `counter` templates plus word-placed beats. Future Improvements says "Richer card templates ... once the generic card has shipped a few episodes." The brief's decision 7 and Alternative I named the generic card as the default and the template set as the replacement for hand storyboards, not as a v1 deliverable. Three of the four templates and the phrase-to-word beat placement serve no CUJ in this document.
- **Recommendation**: Stage 4 ships `generic` only (address bar, scroll, one zoom, one callout), with beats at scene boundaries. Add the other templates and word-placed beats after the first cards have shipped, as the document already proposes.

### M4. The smallest version is not identified and the first video arrives after roughly 44 files
- **Where**: Goals; staging; `hypothesis.md` open question 5 ("What is the smallest version that still removes every manual step?").
- **Discrepancy**: The brief's last open question is not answered anywhere in the design. Stage 0 (11 files, including card templates and the intro generator), Stage 1 (14 files: full seven-rule validator, EpisodePage, MCP tools, library group, converter, fixtures) and Stage 2 (8 files: Haar-cascade QA, cohort medians, whisper WER, contact sheets, degrade path, cost ledger) all land before the first private upload in Stage 3. Stage 1 delivers a status page and MCP tools for episodes that cannot yet be produced. Dan's problem ("One a day is not possible") is not touched until Stage 3.
- **Recommendation**: Name the thin slice explicitly and build it first: `POST /api/episodes` with error-level validation only, approve-script, one estimate and approve-budget, `heygen_clip` with `take`, `scene_compose` in the plate (guard applied), concat, cached intro, music bed, kit with chapters, register, private upload, publish click. No cards, no QA beyond "clip exists and has a face", no warnings, no EpisodePage beyond a list and three buttons. Then QA and the allowance, then cards, then the rest. Stage 0 stays measurement and dependencies only; move file 8 and file 9 to the stages that need them.

### M5. Configuration knobs for things the design fixes
- **Where**: settings list; file 5.
- **Discrepancy**: `episode_fps` is configurable while the spec says "One frame rate, 25 fps, for clips, cards, intro and final" and the intro and HeyGen clips are already 25 fps assets, so changing it would break them. `hyperframes_workers` exposes a renderer CLI flag nobody has asked to tune. `episode_rerender_fraction` plus `episode_rerender_scenes_min` encode a formula where the brief's Q2 said "Dan sets the number in settings". Each knob is a code path and a test.
- **Recommendation**: Constants, not settings, for fps and workers. One `episode_rerender_scenes` integer and one `episode_rerender_usd`, with the formula used only to pick the default once Stage 0 numbers exist. Keep `capture_allowlist`, `hyperframes_browser`, `heygen_month_ceiling_usd`.

### M6. Goals are requirements, not measures
- **Where**: Goals; Verification "Success measure".
- **Discrepancy**: Only Goal 1 has a measure. "Dan can see where an episode is from a phone", "Money moves only behind a click", "Everything the pipeline needs is declared and checked" have no pass/fail. The success measure logs wall-clock and cost but sets no target, so an episode that takes 30 hours or costs 40 USD would pass. Given the 02:00 CUJ, overnight completion is the implicit target but is unstated.
- **Recommendation**: Add numbers: episode from approve-budget to `uploaded_private` in under N hours on the Mac Studio (N from Stage 0); Dan's total interaction under M minutes; HeyGen cost per episode within estimate plus allowance; zero `POST /api/heygen/render` calls without `budget.approved_at` (a test). Drop goals that are really architecture to the Technical Plan.

### M7. Four status surfaces for one status
- **Where**: "Status, observability, agents"; files 17, 19, 20, 21, 23.
- **Discrepancy**: The same episode state is exposed through `GET /api/episodes/{id}`, a new React `EpisodePage` polling every 5 s, a new Library group "Episodes" with `episode:<id>` artifacts and an `episode.status` action, and three MCP tools. The Goal asks for "one status page per episode" readable from the API and MCP. The Library group adds server and web code and a `GROUPS` entry on both sides for a second view of the same list.
- **Recommendation**: Ship the API, the EpisodePage and the MCP tools. Defer the Library group and `episode.status` action until an agent or Dan actually needs episodes in the artifact library.

---

## Nit

### N1. A one-off converter in production code
- **Where**: the contract section; file 14 (`from_episode1_v2`), file 25.
- **Recommendation**: Put the converter under `server/tests/` next to the fixture, or in `tools/`, and store the converted `script.json` as the fixture.

### N2. Whisper per clip is unmeasured and missing from Stage 0
- **Where**: Q1; QA section; file 32.
- **Discrepancy**: Q1 lists rembg, compositing, HyperFrames and HeyGen for measurement but not whisper; the design adds 36 whisper runs per episode and makes their word timings the canonical clock for captions and cards.
- **Recommendation**: Add whisper per clip to Stage 0's measurements. If it is slow, run it once on `final.mp4` after concat (one pass, scene offsets known from measured durations) instead of 36 times.

### N3. Script-text captions re-implement what the existing transcript already produces
- **Where**: publish kit section; file 38; file 42.
- **Discrepancy**: `core/transcribe.transcribe` already writes an SRT, and `youtube_upload` already attaches `<rid>.srt`. The design builds a Python port of `web/src/publish/kit.ts` and modifies the TypeScript to export constants a Python module cannot import. The legitimate reason (on-screen spellings such as "Zmarty" per DESIGN rule 6) is not stated.
- **Recommendation**: State the reason in one sentence. Drop file 42; the two kits serve different inputs and do not need to be byte-identical.

### N4. `episode_register` copies the final MP4
- **Where**: publish section; file 38.
- **Recommendation**: Move or hard-link; `final.mp4` becomes the registered recording and `outputs.final_mp4` points at it.

### N5. The Episode 1 v2 side-by-side costs real money and has no tolerance
- **Where**: Verification "Integration"; Q5.
- **Discrepancy**: Episode 1 v2 was one long HeyGen take; no per-scene clips exist for it. "Re-rendered on the Mac Studio from the fixture" means paying for 36 clips (about 12 to 15 USD, more with motion) to compare against a video made from a different source, with "visual tolerance" undefined.
- **Recommendation**: Replace with "one real three-scene episode" (already listed) as the only paid integration check, and drop the Episode 1 v2 re-render or make it a Dan-approved optional.

### N6. `status` is stored but also derived
- **Where**: episode record; planner rules.
- **Recommendation**: Keep only the human-gate states (`draft`, `script_approved`, `budget_approved`, `uploaded_private`, `published`, `purged`, `needs_dan`, `failed`); show "rendering 12/36, QA 8/36" from counts.

### N7. Stage 0 is not only measurement
- **Where**: files 6, 8, 9.
- **Recommendation**: Keep Stage 0 to the `episode` extra, launcher, settings, health, the Haar cascade move and the measurement record. Fonts, music, SFX and the intro MP4 are needed by Stage 3; templates by Stage 4.

### N8. Goals carry mechanism
- **Where**: Goals.
- **Recommendation**: Keep the outcome in Goals ("only changed scenes are re-rendered"; "every production rule is enforced automatically"); the mechanism belongs in the Technical Plan.

---

## What passes

- Root problem focus: the design attacks the missing episode entity and the hand-run chain, not a symptom, and it records the PLAN.md Decision 6 conflict (file 55).
- Reuse is real: `heygen_clip` and its `.cutout.webm`, `item_key`, `jobs.project_id`, `core.transcribe`, `youtube.upload` resumable state, Playwright already in `render/preview.py`, the fake transports in tests, `find_active_job` for dedupe. Dropping `cuts.py`, `scenecut.py`, `splice.py`, `stitch.py`, `masks.py` is the right call.
- The planner-instead-of-DAG decision (Alternative L) and the allowance-instead-of-stall decisions (Alternatives F, G) are the simplest options that keep the `CLAUDE.md` money rule.
- Non-goals are concrete and mostly honoured; the one exception is the scheduler (B1).
