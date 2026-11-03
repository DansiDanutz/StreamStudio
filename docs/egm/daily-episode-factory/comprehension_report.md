# Comprehension Report (Stage 6)

Reviewer status: completed (`egm-comprehension`, fresh context, dispatched directly; no document
standard applies to this stage).

Target: `daily-episode-factory.md` (FeatureRange lines 1-659, DetailedRange lines 660-1141).
Read in full. Repository files consulted to check whether referenced things exist:
`core/db.py`, `core/heygen.py`, `core/store.py`, `core/config.py`, `render/lipsync.py`,
`worker/handlers.py`, `docs/DESIGN.md`, `docs/scripts/episode-01-v2.json`, `tools/compose/*`.

## Paraphrase of the Feature Specification

StreamStudio today is a live-studio app (stage, Program window, go-live) with a FastAPI server, a
SQLite job worker and a React editor; it already has per-scene HeyGen avatar rendering with a
cost confirm, a lip-sync guard, local transcription, a publish kit, a resumable private YouTube
upload and an agent/MCP bus. The one finished video (Episode 1 v2) was nevertheless produced by
hand with Linux-only scripts under `tools/compose`. The design adds one server-owned entity, the
"episode": a directory of files plus a small SQLite row, created when a writer posts a script as
JSON. The script is a list of ~10-second scenes, each with on-screen text, text as HeyGen should
read it, a kind (avatar or site card), optional sources for claims and an optional per-scene
creative "plan". A validator flags production-rule violations as warnings (length, question/reveal
structure, unsourced numbers, names not spelled for the voice, too long without an on-screen
event) and a few as errors.

Once Dan approves the script and then approves one cost screen (estimate plus a pre-authorised
re-render allowance, checked against a monthly ceiling via a ledger table), a single re-queueable
"planner" job repeatedly reads the episode record and the files on disk and enqueues the next
idempotent step: HeyGen clip per scene (clip key now includes a take number), QA per clip
(face/lip/frozen checks against the episode's first-pass medians, plus a whisper transcript whose
word error rate can fail the clip and whose word timings become the clock for captions and card
beats), re-renders within the allowance or degradation to a small presenter card beyond it,
Playwright captures of allow-listed public pages, HyperFrames card renders from JSON templates,
per-scene composites with the studio plate and overlays, concatenation with intro, music bed and
SFX at fixed loudness levels, a publish kit and SRT, registration of the final MP4 as a recording
so the existing upload/vault/library code works unchanged, and a private YouTube upload. Dan's
third click publishes (now or scheduled); a poll sets `published` only when YouTube reports
public, after which a purge job deletes the workings and keeps the final MP4, script and record.

Agents can create and inspect episodes through MCP but cannot approve budgets. A status page per
episode works at phone width and shows per-scene state, the last plain-words log line, the
blocking action and running cost. Assets (fonts, intro, music, SFX, voice-name table, Haar
cascade, card templates) move under `assets/` with a manifest; health and preflight report the
toolchain. Stage layouts are renamed "sets" so "scene" means one thing. The live studio is
untouched; browser-stage rendering, multiple channels, fact-checking, cron scheduling and a job
DAG are explicitly out of scope.

## Paraphrase of the Detailed Implementation Plan

Stage 0 packages the toolchain: an `episode` extra in `pyproject.toml`, Makefile and Mac launcher
targets that install it plus Playwright Chromium and the `assets/cards` node modules, new Settings
fields, vendored brand assets and the Haar cascade under `assets/`, a HyperFrames workspace with
four JSON card templates, the intro generator moved to `tools/brand`, `/api/health` extended with
preflight, and a measurements document recording Mac Studio wall-clocks, HeyGen limits and disk
use. Stage 1 builds the record: migration 4 (`episodes` and `heygen_ledger` tables), a new
`streamstudio.episode` package with Pydantic contract models and an Episode 1 v2 converter, the
validator, record storage helpers, the `/api/episodes` router (create, list, get, edit script,
approve script, estimate, approve budget, publish, advance, purge, contact sheet), library and MCP
exposure, a React `EpisodePage` at `?episode=<id>`, and tests plus fixtures.

Stage 2 adds the paid path: `item_key` gains `take`, the USD rate and estimate move into
`core/heygen.py`, `heygen_clip` learns `take`/`episode_id` and enqueues the planner, the planner
implements the six rules under `BEGIN IMMEDIATE`, the vault mirrors `assets/brand`, and `scene_qa`
ports the QA checks and adds transcription; tests cover the state machine, allowance, ceiling,
concurrency and synthetic clips. Stage 3 ports the compositor and mixer into `episode/compose.py`
and `episode/mix.py`, shares lip-sync guard fixtures between Python and TypeScript, writes the
publish kit and registration handler, extends the recordings listing to see episode sidecars, adds
`publish_at` and `video_status` to the YouTube client and route, and adds publish-status and purge
handlers. Stage 4 adds Playwright capture, the HyperFrames builder moved into
`episode/hyperframes.py`, and `card_render`, with tests. Stage 5 deletes the old `tools/compose`
scripts, rewrites READMEs, DESIGN, AGENTS, CLAUDE and PLAN docs, carries out the scenes-to-sets
rename across routes, catalog and tests, adds an end-to-end test and makes CI install the
`episode` extra. Verification is `make build`/`make test`/`make lint`, a re-render of Episode 1 v2
on the Mac Studio compared side by side, one real three-scene episode end to end, and the first
five daily episodes logged.

## Findings

### 1. The third click, "Publish", has no described mechanism
- Severity: Blocker
- Scope: Overview; CUJ 1; planner rules 5-6; "Publish kit, registration, upload, publish status, purge"; plan files 17, 39, 40, 41
- Gap: The video is uploaded private *before* Dan clicks Publish (rule 5 sets `uploaded_private`). `publish_at` is sent only at upload time. The YouTube client changes are limited to `publish_at` on upload and a `video_status` read (file 39). Nothing says what `POST /api/episodes/{id}/publish` does to an already-uploaded video: there is no `videos.update` call to flip `privacyStatus` to public ("now") or to set `publishAt` after the fact ("at a chosen time"). A fresh reader cannot tell whether "Publish now" is implemented at all or whether Dan is expected to do it in YouTube Studio, which Alternative Q says was rejected.
- Recommendation: State, in the publish section and in files 39/41, the exact YouTube call made by `POST /{id}/publish` for both "now" and "scheduled", and whether `publish_at` can be set before upload, after upload, or both.

### 2. Who enqueues `episode_publish_status`, and how does an hourly poll run on a worker with no scheduler?
- Severity: Major
- Scope: publish section; planner rule 6; Non-Goals; file 41
- Gap: The planner's rules jump from `uploaded_private` (rule 5) to `published` (rule 6). `episode_publish_status` "polls every hour", but the `jobs` table has no run-at/delay column and the design rules out any scheduler. The reader cannot tell whether the handler sleeps for an hour holding a worker slot, re-enqueues itself, or is triggered by something else, nor who enqueues it first.
- Recommendation: Add a planner rule or a sentence naming the trigger and the repeat mechanism, and reconcile it with the "no scheduler" non-goal.

### 3. How the planner learns that `youtube_upload` finished
- Severity: Major
- Scope: "Shape of the system"; fan-in paragraph; publish section; file 29
- Gap: Fan-in relies on "a stage handler enqueues `episode_advance` when it finishes". `heygen_clip` is modified to do so (file 29), but `youtube_upload` is stated to "work unchanged" and is not listed among modified handlers. The record's `outputs.youtube_video_id` must come from somewhere; the doc hints at `jobs.result` but never says the planner scans job rows by `project_id` for the upload result.
- Recommendation: State explicitly how the planner picks up results of unmodified handlers (poll `jobs` by `project_id`/kind, or add the enqueue to `youtube_upload`).

### 4. Card scenes: does the avatar appear, and how is a multi-scene card split per scene?
- Severity: Major
- Scope: script contract; planner rule 1; compositor; cards; data flow; Alternative S
- Gap: Rule 1 renders a HeyGen clip for every scene including `kind: card`, and CUJ 2 speaks of a degraded scene "over its motion card". Only Alternative S ("the guard already keeps the face small in those scenes") lets the reader infer that in a card scene the avatar is shown as the small presenter card over the site card. This is never said in the compositor section. Separately, a card "covers a run of consecutive card scenes" and produces one `cards/<card>.mp4`, while `scene_compose` writes one file per scene; how the card video is cut at scene boundaries (offsets, what happens if the card is shorter or longer than the sum of clips) is not described.
- Recommendation: One paragraph in the compositor section: what a card scene's frame contains (card video, presenter pip, overlays), and how `scene_compose` addresses its slice of the card.

### 5. When does the lip-sync guard ever say `pip` in the factory?
- Severity: Major
- Scope: compositor; CUJ 2; verification
- Gap: The guard returns `pip` when the voice heard is not the clip's own audio. In this pipeline every scene is a HeyGen clip with its own audio, so a reader expects "as scripted" always; yet the e2e test asserts "the guard applied to a narration scene", and the script contract has no narration concept. The reader cannot tell what `cue`, `clip` and `voice` are passed per scene, or whether card scenes are forced to `pip` by a rule rather than by the guard.
- Recommendation: Define, in the compositor section, the guard inputs for avatar and card scenes and the resulting placement; drop or explain "narration scene".

### 6. Allowance semantics: episode-wide or per scene, and what "its share" means
- Severity: Major
- Scope: Goals; CUJ 2; paid step; plan file 5
- Gap: The allowance is "4 scenes / 1.50 USD" (two caps; which one binds is not stated). CUJ 2 then says scene 23 "exhausts its share", implying a per-scene share, while the planner (rule 3) treats it as one episode pool. The CUJ arithmetic only works if "fails N times" counts the original render, which the text does not say. The Settings default in the feature (`episode_rerender_scenes = max(2, ceil(0.1 * scenes))`) does not match the plan's two fields `episode_rerender_scenes_min` and `episode_rerender_fraction`.
- Recommendation: Define "allowance" once (unit = re-render attempts, episode-wide, both caps must hold), rewrite CUJ 2's numbers to match, and use the same setting names in both ranges.

### 7. `needs_dan` is a state with no rule that reaches it
- Severity: Major
- Scope: states; Q2; planner rules
- Gap: `needs_dan` is "reachable from rendering, qa, composing" and Q2 says the episode "parks in needs Dan" when the allowance is exhausted, but rule 3 degrades and continues instead (Alternative G confirms). No rule sets `needs_dan` or `failed`, and nothing says what clears them.
- Recommendation: List the conditions that enter `needs_dan` and `failed` (for example ffmpeg failure, capture refused, every scene degraded) and the exit action.

### 8. Which HeyGen avatar and voice an episode renders with
- Severity: Major
- Scope: script contract; clip key; file 16 `scene_key(scene, cfg, take)`
- Gap: `item_key(look, voice, script, motion, silent_s, take)` needs a look (avatar id), a voice id and a motion, but the script contract has none of these fields and no setting is named for them. `cfg` in `scene_key` is undefined.
- Recommendation: Add the fields to the `Script` model or name the Settings keys, and define `cfg`.

### 9. "The YouTube rules in the Technical Plan" do not exist
- Severity: Major
- Scope: CUJ 3
- Gap: CUJ 3 defers to rules for replacing versus re-uploading an already-uploaded video after a word change. The Technical Plan contains no such rules; YouTube does not allow replacing a video file, which makes the choice consequential (new video id, lost link).
- Recommendation: Write the rule (likely: re-upload as a new private video while the episode is unpublished; refuse or warn after publish) in the publish section.

### 10. `plan` fields and brand vocabulary are listed without meaning
- Severity: Major
- Scope: script contract (`title, lower, lowers, chips, chip_at, zoom, zoom_path, frame, glitch, endcard, whoosh_at`; "default table card", "generic site card"); "plate"; "motion card"; "kicker", "tagline"
- Gap: A fresh reader does not know what a lower, chip, table card, plate, or motion card is, or what "the default table card on `question`" shows. These are project-specific terms defined only in `docs/DESIGN.md` and `tools/compose/README.md`.
- Recommendation: A short glossary (one line each) under the script contract, or a pointer to the exact DESIGN.md section for each.

### 11. HyperFrames and rembg are never introduced
- Severity: Major
- Scope: Q1 (first use); cards; assets; Future Improvements
- Gap: "HyperFrames" is used from the first page as if known; only `npx hyperframes render` hints it is an npm-based HTML-to-video renderer. "rembg" is never explained as the background-removal tool behind the cut-outs.
- Recommendation: One clause at first use for each.

### 12. Capture allow-list format contradicts itself
- Severity: Major
- Scope: cards section; file 5; file 45
- Gap: `capture_allowlist` is "a list of host patterns" and `list[str]`, yet file 45 says a site is used from `assets/sites/` "when the allow-list says `manual`". A flat list of host patterns cannot "say manual". The pattern syntax is also unstated.
- Recommendation: Define the entry shape (for example `{"host": "...", "mode": "auto|manual"}`) and the match rule.

### 13. Stage 0 measures a compositor that is only ported in Stage 3
- Severity: Major
- Scope: Q1; file 11; Overview
- Gap: File 11 records "wall-clock per step for Episode 1 v2 on the Mac Studio", but the Overview says the `tools/compose` scripts "have never run on the Mac Studio" and have hard-coded Linux paths, and the port lands in Stage 3. The reader cannot tell what is actually run in Stage 0 to obtain compositing and card numbers.
- Recommendation: Say which tool is run for each measurement in Stage 0 (old scripts with paths patched, a spike, or only the HeyGen/rembg measurements), or move the compositing measurement to Stage 3.

### 14. Feature and plan disagree on where the HyperFrames builder lives
- Severity: Major
- Scope: cards section ("`tools/compose/motion/build.py:Comp`, imported from `episode/cards.py`") versus file 46 (moved to `episode/hyperframes.py`) and file 50 (`build.py` deleted)
- Recommendation: Align the feature text with the plan.

### 15. `reveal` and `question` are used by the validator but not shown in the scene schema
- Severity: Nit
- Scope: scene schema versus validator table; file 14
- Recommendation: Add `reveal?: true` to the schema block and gloss `question` (number or boolean).

### 16. `episode_publish_status` and `hyperframes` missing from the package listing
- Severity: Nit
- Scope: file 13 versus files 41, 46
- Recommendation: Add `publish` and `hyperframes` to the `__init__` exports.

### 17. Undefined references in Stage 5 docs changes
- Severity: Nit
- Scope: file 55 ("milestone S9", "Decision 6"); vocabulary section (`Segment.scene`)
- Recommendation: One clause each ("Decision 6, record and live-stream from the start").

### 18. Minor terms assumed
- Severity: Nit
- Scope: "tailnet"; "measured durations"; "within visual tolerance"; "as `cards_v2.T` tried to do by guessing"
- Recommendation: Gloss or quantify; drop the `cards_v2.T` aside or move it to Alternatives.

### Checked and found adequate
- Migration numbering: three migrations exist in `db.py`; "Migration 4" is correct.
- `item_key`, `guard_cue`, `pip_rect`, `handlers.CUTOUT`, `store.enqueue(project_id=...)`, `jobs.result`, `jobs.project_id`, `worker_concurrency = 2`, `list_recordings`, `finish_recording`, `comp_times`, `cards_v2.T` all exist as named.
- Open questions Q1-Q5 are each answered or assigned to Stage 0 as the section promises; the -36 LUFS decision matches `tools/compose/mix.py` and the DESIGN.md -28 discrepancy is real.
- The planner/fan-in model, ledger-based monthly total, `take=0` key compatibility and the purge-only-after-public rule are explained well enough to paraphrase without outside reading.
