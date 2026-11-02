# Daily episode factory

* **Author:** Dan (DansiDanutz)
* **Date:** 2026-11-02
* **Hypothesis reviewed:** [hypothesis.md](./hypothesis.md)

## Overview

Turn StreamStudio into a factory that produces one scripted DansLab episode a day. There is no
live streaming. A finished script in a question-and-answer structure, split into scenes of about
10 seconds, goes in; a private YouTube upload with intro, music, sound effects, motion site cards
and the avatar's closing reveal comes out. Dan's time is limited to approving the script, approving
the HeyGen cost, and making the video public. Free, local tools are preferred; HeyGen is the one
paid step. The pipeline that made Episode 1 v2 exists as hand-run scripts in `tools/compose`; the
hypothesis proposed running it as StreamStudio jobs.

### Reviewer status

Six fresh Goldfish reviewers, each in its own context with no conversation history, read the
hypothesis and the repository and reported independently. The EGM synthesizer could not spawn
them in this harness, so the Elephant dispatched them directly and merged the reports.

| Reviewer | Status |
| --- | --- |
| `egm-design` (Skeptical Architect) | completed |
| `egm-codebase-details` (Technical accuracy and reuse) | completed |
| `egm-zoom-out` (Simplicity, scope, cost) | completed |
| `egm-comprehension` (Naive reader, UX) | completed |
| `egm-implementation-readiness` (Operability, migration) | completed |
| `egm-structural` (Structure, long-term maintenance) | completed |

## Analysis

Critique first. Each point names the file or fact it rests on and the lenses that raised it.
Where all six agreed it says so; those are the decisions the design cannot avoid.

### A. The hypothesis proposed porting the wrong pipeline (all six lenses)

1. **`tools/compose` was built for one long HeyGen take; the app already renders per scene.**
   `render.py` opens `WORKDIR/heygen.mp4` and `cuts.json`; `cuts.py` and `scenecut.py` exist only
   to recover scene boundaries from a captions file downloaded by hand from the HeyGen web UI
   (`tools/compose/README.md` step 2); `masks.py` redoes the rembg cut-out that
   `avatar/cutout.py:run` already does for the app; `splice.py` swaps video frames into a
   fixed-length take and copies the original audio (`-c:a copy`), so its README invariant is "a
   patch must have the same frame count as the range it replaces". A HeyGen re-render of a scene
   never has the same length or audio. Meanwhile `worker/handlers.py:heygen_clip` already renders
   one idempotent clip per segment, keyed by `core/heygen.py:item_key(look, voice, script, motion,
   silent_s)`, which gives "only scenes whose words changed are rendered again" for free.
   Consequence: the unit of the factory is the per-scene clip, the final video is a concatenation
   of per-scene composites, and `cuts.py`, `scenecut.py`, `splice.py`, `stitch.py` and `masks.py`
   are not part of it.

2. **Nothing in `tools/compose` has run on the Mac Studio.** Every hard-coded path is Linux:
   `render.py:25 STUDIO = /home/claude/streamstudio/assets/studio`, `render.py:26` Inter fonts at
   `/usr/share/fonts/opentype/inter/`, `mix.py:22 LIB` default under `/home/claude/dansidanutz/`,
   `motion/build.py:render` forcing `HYPERFRAMES_BROWSER_PATH` to a `chrome-linux64` binary and
   overriding the shell. `render/opener.py` fails at import without the same font directory.
   OpenCV is imported by four scripts and is in no `pyproject.toml` extra; `rembg` is only in the
   optional `media` extra, which the Mac launcher does not install (`mac/StreamStudio.app/...`
   step 2 runs `pip install -e .`), so `heygen_clip` reports `done` with `cutout: None` and no one
   notices. HyperFrames needs `npm i hyperframes gsap` in a folder with no `package.json`. The
   fonts, music and SFX are outside the repo. Render time, rembg throughput and HyperFrames on
   macOS are unmeasured. The constraint is Mac Studio only.

3. **The scripts run their work at import** (`tools/compose/README.md` Interface: "importing them
   executes them"; `cards_v2.py` loads two JSON files at import from paths that do not exist in the
   repo). They cannot become handlers without being rewritten as functions, and there are no tests
   (`make test` does not touch `tools/compose`).

### B. The unstated architectural decision: which compositor (design, structural, zoom-out, codebase, readiness)

4. **Two compositors, no shared code.** The browser stage with the Director (`web/src/stage`,
   `web/src/director`; `PLAN.md` S3 calls it "the core") and `tools/compose/render.py` (Pillow and
   OpenCV, its own grammar: `CARD_W/H 1400x788`, `CIRCLE = 300`, `TABLE_BOTTOM = 1004`, table
   cards, chips, zoom paths, glitch). `render/opener.py` is a third frame-exact renderer. The
   hypothesis silently chose `render.py`, which makes the stage, cues, timeline and publish kit
   dead for the product the app is now for. Every visual change would be made twice or drift.
   `README.md` already lists `tools/compose` as "not imported by the app".

5. **The lip-sync guard is not called by the compositor that made the video.** Three states exist:
   `web/src/director/types.ts:guardCue` plus `cueLayouts.ts:guardLayout`;
   `render/lipsync.py:guard_cue` and `pip_rect` (`MAX_UNSYNCED_AREA = 0.06` mirrored in both);
   and `render.py`, which enforces nothing (`tools/compose/README.md`: "the rule itself is enforced
   in the server, not here"). Episode 1 obeys the rule only because `CIRCLE = 300` px is 4.3 % of
   the frame and every scene carries Dan's own HeyGen audio. A narration scene or a music-only
   moment would break it. `CLAUDE.md` makes it a hard rule for offline renders.

6. **Two direction grammars.** `plan.json` (`kind`, `chips`, `lowers`, `zoom_path`, `frame`,
   `glitch`, `question`, `whoosh_at`, `video_at`, `cont`) and the Director `Segment` (`cue`,
   `table`, `media`, `zoom`, `gesture`). Agents, the guard, the timeline compiler and the publish
   kit all speak `Segment`; anything built on `plan.json` is invisible to `studio_timeline`,
   `segment.update` and `render/lipsync.py`.

### C. Scene identity and the episode record (structural, readiness, codebase, comprehension)

7. **Four descriptions of one episode joined only by array position.** `docs/scripts/episode-01-v2.json`
   (rows, scenes, voice, est_s, changed), `episode-01-v2.plan.json` (36 positional entries, no
   ids), `episode-01-v2.durations.json` (scene number to seconds), `cards_v2.py` (storyboards with
   hard-coded scene numbers; `video_at` values are cumulative durations copied by hand:
   `12.956 = 8.876 + 4.08`). `render.py` asserts `len(PLAN) == len(cuts) - 1`. The editor's
   `Segment` is a fifth model, in `localStorage streamstudio.script.v6`, which the worker cannot
   read. Inserting one scene misaligns everything downstream. No format has a field for a claim's
   source.

8. **No episode entity, no ordering, no fan-in.** `core/db.py` `jobs` has `kind, payload, status,
   progress, message, result, error, attempts`; no parent, dependency or group.
   `store.claim_job` takes the oldest queued row of any kind. An episode is N clip renders, N QA
   checks, K captures and card renders, then compose, mix, publish kit, upload: fan-out then
   fan-in then linear. `agent.py:do` returns 409 without an open editor, so the agent bus cannot
   host it. Nothing today can answer "where is episode N" or "resume from step 7".

9. **"Done" is judged by file existence and the scripts write in place.** Existing handlers use
   `.part`/`.tmp` and rename; `render.py`, `mix.py`, `splice.py` and `build.py:render` write the
   output path directly. The launcher kills the worker on every update (`stop_server`), and
   `requeue_stale` returns the job after the heartbeat timeout; the retry would find a half-written
   MP4 and skip it. Every step needs temp plus rename and an input manifest (text hash, clip
   sha256, card inputs) so "up to date" means inputs unchanged.

### D. The paid step: re-renders, retries, budget, throughput (all six)

10. **Re-rendering a failed scene with the same words is impossible under the current key.**
    `api/routes/heygen.py:render` returns an item whose MP4 exists as `ready` and never queues it;
    `heygen_clip` skips when the MP4 exists. `item_key` has no take or attempt component. A QA
    `FAIL` on unchanged text yields the same key and the same bad file. One line fixes it (a `take`
    integer in the key, keeping the rejected clip as `<key>.a1.mp4` so a worse re-render can be
    rolled back), but it must be designed, not discovered.

11. **Automatic re-render spends money without a click.** `CLAUDE.md`: paid APIs never run without
    an explicit user action and a shown cost. The hypothesis's "single-scene re-render" after QA
    implies the pipeline re-spends on its own. The worker already does: `store.fail_job` requeues up
    to `job_max_attempts = 3`, and `heygen_clip` deletes its state file on a HeyGen `failed` so the
    next attempt is a new paid render (`handlers.py:239-243`). The job status enum has no "waiting
    for approval". The USD rate lives only in the browser (`HeygenPanel.tsx:API_USD_PER_S =
    0.0385`), so the server, the MCP `heygen_estimate` and any job cannot show the same number.
    `POST /api/heygen/render` with `confirm: true` is callable by any tailnet client; the "click"
    exists only in the panel and in the MCP refusal.

12. **The cost figure is a floor.** 293.6 s x 0.0385 = 11.3 USD for Episode 1 v2 is right for
    voiced seconds. Missing: `heygen.py:_seconds` adds 0.6 s per clip and floors at 2 s (about
    +22 s for 36 clips), custom motion "about 2x" (`docs/DESIGN.md` line 302), QA re-renders, and
    the 16 of 36 scenes re-rendered in v2 for word changes. Realistic: 400 to 550 USD a month at one
    a day, before any re-render policy. Roughly 45 % of paid lip-sync seconds are shown at a 300 px
    circle (the 16 card scenes).

13. **Throughput.** `worker_concurrency = 2` (`core/config.py`); `heygen_clip` holds its slot while
    polling every 8 s for up to 30 minutes. Thirty-six clips, two at a time, serialise into many
    rounds of HeyGen latency, and captures, card renders and QA wait behind them. HeyGen's
    concurrent-render cap per account and its minimum billed seconds per clip are not recorded
    anywhere in the repo. Measure before designing fan-out.

### E. The hidden manual work: storyboards, plan, captures (all six)

14. **Storyboards and the creative plan were written by hand and nothing produces them.**
    `motion/cards_v2.py` is one Python function per card group with page-pixel rectangles for
    rings, cursor paths and typed fields, beats placed by `T(off, scene, phrase)` proportionally to
    character position (not real word timing), asserting the phrase exists. `episode-01-v2.plan.json`
    is about 580 lines of hand-tuned fractions (`chip_at: 0.451`, `zoom_path`, `glitch`). Dan's
    time is script and cost; the hypothesis names no author for either. Without one, "one episode a
    day with no step outside the app" is false on day one.

15. **Site capture is a tooling gap and a security boundary.** Captures were taken by a person in
    Chrome in viewport steps, which is the only reason `stitch.py` exists. Playwright is already a
    dependency (`render/preview.py:22`); `page.screenshot(full_page=True)` replaces capture plus
    stitch. The rule "never capture private dashboards, balances or P&L"
    (`motion/README.md` step 1) has no enforcer once no person drives the browser; the JEV card
    (`cards_v2.py:g21`) is a logged-in trading dashboard. A capture job needs a URL allow-list, a
    fresh browser profile with no stored sessions unless a recipe says so, and a redaction rule.

16. **The mixer reads sound cues by regex over generated HTML.** `mix.py:comp_times` scrapes GSAP
    tween strings out of `comps/<card>/index.html` (`motion/README.md` Side Effects), coupling the
    mixer to `build.py`'s emitted JavaScript. The card builder should emit `cues.json`.

17. **The intro is not a per-episode job.** `make_intro.py` is deterministic (`rnd(seed)`), needs
    four `.woff2` files copied by hand, and only kicker, title and tagline vary. Render once per
    distinct text and cache the MP4 as an asset.

### F. Script stage, fact-checking and the contract (all six)

18. **The script stage does not belong inside StreamStudio.** Writing, fact-checking, the
    question structure and voice spellings are editorial and already live with the writing agents
    and skills; StreamStudio's entire text knowledge is `estimateMs`, `splitScript` and
    `WORDS_PER_S = 2.5`. "Fact-checked" has no operational meaning in the repo and cannot be
    implemented as truth verification; Episode 1 v2's claims are mostly Dan's own business facts
    ("fourteen thousand subscribers", "ten dollars a month", rows 18 and 28). What the app can own
    is the contract: a script format with scene ids, on-screen text, voice text, per-claim
    `source` (URL or "Dan, 2026-11-02") or softened wording, site URL, and a validator with
    line-level warnings. The validator checks presence, not truth.

19. **The 3 to 13 s rule is a wish today.** `autoDirect.ts:splitScript` splits by paragraph or
    sentence pairs, not by duration. Episode 1 v2 breaks the rule in two of 36 scenes (13.12 s and
    13.93 s) even with hand splitting; three more sit just above the 3 s floor (3.2, 3.44, 3.64 s)
    and are within the rule. A hard gate would make v2 unimportable;
    it must be a warning the splitter tries to satisfy.

20. **Vocabulary collides.** "Scene" is a saved stage set in the editor (`/api/scenes`, Library tab
    "Scenes", `docs/AGENT_GUIDE.md` line 8) and a ~10 s script unit in the production rules; the
    Director calls the latter a "segment". "Card" means Base/Main/Avatar/Menu cards, table cards,
    HyperFrames site cards and Library media cards. The plan's "16 motion cards" are 16 card
    scenes sharing five HyperFrames renders (`g06`, `g10`, `g15`, `g21`, `g27`).

### G. Output, publishing and the success criterion (design, comprehension, structural, codebase, readiness)

21. **"No step performed outside the app" is unachievable as written.** `mcp.py:call` forces
    `privacy: "private"`; `docs/AGENTS.md`: "Dan publishes it"; making the video public happens in
    YouTube Studio. The HeyGen click is in the middle of the pipeline, so a nightly unattended run
    is impossible by design. The criterion must name the clicks (approve script, approve budget,
    publish) and where the pipeline parks between them.

22. **The final MP4 has no path into upload, vault or library.** `youtube.py:queue_upload`
    requires `recordings_dir/<rid>.mp4` with a `rec_*` id; `handlers.py:youtube_upload` attaches
    `<rid>.srt` from whisper; `core/vault.py:local_path` maps only avatar clips and recordings;
    `agent.py:_server_artifacts` lists scenes, clips, recordings. A composed episode is not a take.
    If it is registered as one, `finish_recording` would re-encode and apply `loudnorm` a second
    time on an already normalised mix.

23. **The publish kit is browser-only.** `web/src/publish/kit.ts:buildPublishKit` runs in the
    editor; its only server route is the agent action `publish.kit`, which is 409 without an open
    editor. With per-scene clips, captions are the scene voice text over measured clip durations
    and chapters fall out of the "Question N" markers: about thirty lines of Python, not a port.

24. **"Workings stay until posted" has no observer and no home.** Nothing polls YouTube privacy
    status; `Settings.projects_dir` is unused by any handler; there is no episode directory under
    `DATA_DIR` and no purge job. Several GB per episode (36 clips, cut-outs, card frames, mixes);
    tens of GB per month of backlog. Fine on a Mac Studio, not vaulted, and not evictable through
    the Library.

### H. QA (design, zoom-out, codebase, readiness, structural)

25. **QA judges against the median of the other scenes.** `qa_avatar.py:main` derives `lip_ref`
    and the face-placement reference from the batch; a single re-rendered scene has no cohort. The
    episode record must store the medians from the full pass. `LOOK` means "a human should look"
    and nobody is named to look; `FAIL`/`LOOK` live in a print loop and an exit code, not a data
    contract.

26. **The lip-ratio heuristic is not the lip-sync guard.** `qa_avatar.py:check` compares mouth
    motion to audio RMS; `render/lipsync.py:lips_match` is a layout rule about whose voice is
    playing. Name them separately. Whisper word timings (`core/transcribe.py:parse_whisper_json`)
    can give a stronger check: transcribed words against the scene's voice text.

### I. Smaller disagreements between rules and code (several lenses)

27. Frame rates: `render.py` and cards at 25 fps, `make_intro.py:FPS = 30`, `finish_recording`
    at 30 fps; `mix.py` concatenates them. Pick one.
28. Music level: `docs/DESIGN.md` rule 3 says about -28 LUFS for the bed; `mix.py` uses -36.
29. `README.md:38` says "Next: YouTube upload" while `youtube_upload` exists.
30. `PLAN.md` still locks "record and live-stream from the start" (Decision 6) and describes a
    live studio. The brief should say it supersedes that direction for product focus.
31. Observability: no correlation id on jobs, no cost ledger (`<data_dir>/heygen/<key>.json` holds
    only `video_id`), QA results on disk and unindexed, `fail_job` keeps only the last error, MCP
    has no `job_get`, and `/api/health` reports counts only.

### What survives scrutiny

Per-scene paid rendering with a cost gate and idempotent resume (`heygen_clip`, `item_key`); the
job worker with heartbeat, retries and cancel; YouTube resumable upload with captions and private
default; the vault; the agent bus and MCP server that let an agent prepare everything and stop at
the money; Playwright already present; the production rules as tests waiting to be written; and a
compositor, QA and mix that produced one real episode. The hypothesis is feasible as a staged
programme once four things are settled: the compositor, the episode record, the plan author, and
the re-render budget rule.

### Optional cost lever, Dan's call

Under the lip-sync guard a non-clip voice forces the face into the small card, which is already
where Dan is during the 16 card scenes. Those scenes could use a free local text-to-speech of the
same lines and cut HeyGen spend by roughly 45 %. The cost is voice continuity between HeyGen's
cloned voice and a local one. Flagged because it is the only lever that moves the monthly floor;
not recommended by the reviewers.

## Goals vs. Non-Goals

* **In-Scope Goals:**
  * One server-owned episode record with stable scene ids: script rows (on-screen text, voice
    text, sources, site URL), per-scene state (clip key and take, HeyGen video id, measured
    duration, QA verdict, card id), costs, and the YouTube id. Stored under `DATA_DIR/episodes/<id>/`,
    exposed as a library artifact and through MCP, readable without the editor open.
  * A script contract and validator: scene length 3 to 13 s as a warning, question-then-answer
    and closing reveal present, names-for-voice applied, a source or softened wording present on
    every numeric or ranking claim, an on-screen event at least every 8 s of avatar. Writers stay
    outside; `POST /api/episodes` accepts the finished script.
  * Per-scene HeyGen rendering through the existing `heygen_clip` and `item_key` plus a `take`
    component; one confirm per episode showing seconds, USD, wallet after, monthly total after,
    and a bounded re-render allowance that automatic retries count against; a configurable monthly
    ceiling; the rate moved to `core/heygen.py`.
  * Per-scene QA as a job with a JSON result, compared against the episode's stored reference, a
    contact-sheet image per failing scene, and a decision table for `ok`, `LOOK`, `FAIL`.
  * Compose per scene with `render/lipsync.py:guard_cue` called for every scene, concatenate,
    intro from a cached asset, music bed and SFX from `cues.json`, one loudness table; temp plus
    rename and an input manifest on every step.
  * Site capture by Playwright full-page screenshots under a URL allow-list with no stored
    sessions by default; motion cards from a small template set parameterised by captures and
    scene phrases; the card builder emits `cues.json`.
  * A server-side publish kit (captions from voice text over measured durations; chapters from
    the question markers) and private upload, with the final MP4 registered so upload, vault and
    library accept it without a second `loudnorm`.
  * An episode status page (per scene, per stage, blocked-on, last error, next action), usable
    from a phone over Tailscale; a cost ledger per episode; correlation ids on jobs.
  * Workings kept under the episode directory until the YouTube id is recorded and the video is
    public, then purged by a job; not vaulted.
  * Every path from `Settings`; fonts, music, SFX, intro and studio plate under `assets/` with a
    manifest; an `episode` dependency extra installed by the launcher; `/api/health` lists each
    tool; a preflight refuses to start an episode when anything is missing.
* **Out-of-Scope Non-Goals:**
  * An in-app script writer or an automatic truth-checker.
  * Live streaming, the Program window, recording Dan on camera.
  * A general job dependency engine or scheduler; any cron that spends money.
  * Rendering episodes with the browser stage in v1 (recorded as the long-term direction).
  * Automatic storyboard authoring from arbitrary pages; hand-written Python storyboards on the
    daily path; capturing logged-in pages automatically.
  * Backing up episode workings to the vault.
  * Multiple channels, presenters or languages; portrait Shorts.
  * Keeping `cuts.py`, `scenecut.py`, `splice.py`, `stitch.py`, `masks.py` in the factory.

## Alternatives Weighed

1. **Script stage inside StreamStudio (in-app writer and fact-checker).** Rejected by all lenses.
   Ties the server to a model API, duplicates the writing agents, and "fact-checked" cannot be
   implemented as truth verification. Kept: a script contract and validator; the writer acts from
   outside, through `POST /api/episodes` or the MCP `script.set`.
2. **Port `tools/compose` as it is, wrapping each script as a job.** Rejected. Built for one long
   take, Linux-only paths, import-time execution, no tests, duplicates `avatar/cutout.py`.
   Accepted in part: `render.py`'s compositing functions, `qa_avatar.py` and `mix.py` are rewritten
   as importable functions under `server/src/streamstudio/episode/` with paths injected;
   `npx hyperframes render` and `ffmpeg` stay subprocesses.
3. **One long HeyGen take cut by captions (how Episode 1 v2 was made).** Rejected. Needs a
   captions download from the HeyGen UI by hand; a single-scene fix means re-rendering the take or
   a splice that cannot survive a length change; per-scene jobs exist and give changed-words-only
   re-rendering for free. Risk accepted: per-scene framing drift, caught by QA against a stored
   reference.
4. **Browser stage recorded headlessly as the compositor (`render/preview.py`).** Rejected for v1,
   recorded as the direction. Real-time capture is not frame-exact, the 25 versus 30 fps question
   is open (`docs/DESIGN.md` line 142), and the table-card and zoom-path grammar exists only in
   `render.py`. Revisit after the first ten episodes with a side-by-side of `render.py` output and
   a headless recording; two compositors is a maintenance trap. A frame-by-frame Playwright
   screenshot render of the stage is the deterministic variant to test then.
5. **HyperFrames for the whole episode.** Rejected for v1: long renders, mask handling inside HTML.
   Noted as a way to share CSS with the stage.
6. **Automatic re-render on QA fail with no click.** Rejected: violates `CLAUDE.md`. Replaced by a
   re-render allowance shown and approved on the first confirm; beyond it the episode parks in
   "needs Dan" with the extra cost shown.
7. **Stall on a scene that fails QA after the allowance.** Rejected in favour of degrade: place
   the scene in the small guard-compliant card over its motion card or the plate, list it in the
   episode report, ship the day's episode, re-voice later.
8. **A daily cron that starts the pipeline.** Rejected: it either spends money unattended or stops
   at the gate anyway. Replaced by a queue of episodes in flight (write day N+1 while day N
   renders) with asynchronous gates.
9. **Agent-written Python storyboards per episode (today's `cards_v2.py`).** Rejected for v1:
   unverifiable until rendered, page-pixel coordinates break when the site changes, a bug stops the
   mix. Replaced by templates (hero scroll, feature ring, compare table, QR/counter) parameterised
   by URL, selector-found rectangles and scene phrases; storyboards become JSON. A generic card
   (URL bar, slow scroll, one zoom, one callout from the scene text) is the default when no
   storyboard exists.
10. **Agent-driven browser capture.** Rejected: not idempotent, and it violates the private-page
    rule by default. Replaced by capture recipes per site (URL, viewport, steps, elements to
    blank) run by Playwright with a fresh profile; a new site means writing a recipe once.
    Captures are reusable library media across episodes until stale.
11. **Keep the episode in the Director's localStorage and drive it through the agent bus.**
    Rejected: `POST /api/agent/do` is 409 without an open editor, and localStorage is per browser.
12. **A job dependency (DAG) layer in the worker.** Rejected as unnecessary: one episode document
    plus idempotent stage handlers that derive the next step from what exists on disk, and a
    re-queueable `episode_advance`, cover fan-out and fan-in.
13. **Store the plan as an EDL in `edl_versions`.** Rejected: the EDL holds cuts on tracks, not
    chips, lowers, zoom paths or sound cues. The `projects` row and `jobs.project_id` are reused as
    the episode's correlation key; the EDL may be derived for the editor.
14. **Intro, music and SFX as per-episode render steps.** Rejected: they change with branding, not
    episodes. Build once, version as assets.
15. **External fact-checking APIs.** Rejected for v1: paid or rate-limited, and the claims are
    mostly Dan's own. The validator enforces that a source or softened wording is present.
16. **Whisper versus HeyGen captions versus text proportion for word timing.** Whisper (local,
    free, already a dependency) is the canonical source for card beats and captions; HeyGen
    captions require a manual download; the proportional guess in `cards_v2.T` is dropped.
17. **Make the video public from the app.** Accepted as a third named click, with YouTube's
    `publishAt` as the option that keeps the daily cadence independent of Dan's hours.

## Key Decisions & Staging for Next Steps

**Decisions to carry into `/egm:egm-draft`:**

1. **Boundary.** "Inside the app" means the API, worker, MCP server and editor. Writers deliver a
   finished script through the API; StreamStudio owns the contract, the validator and everything
   after approval. Three named clicks remain: approve script, approve budget, publish (or schedule
   publish). The success criterion is restated to say so.
2. **Scenes are the unit.** One `heygen_clip` per scene with a `take` component in the key; the
   final video is a concatenation of per-scene composites; a re-voiced scene re-times everything
   after it and cards record the durations they were built from. `cuts`, `scenecut`, `splice`,
   `stitch` and `masks` are out.
3. **Episode record.** One server-owned JSON per episode under `DATA_DIR/episodes/<id>/` with
   stable scene ids, correlated to a `projects` row and `jobs.project_id`; explicit states (draft,
   script approved, budget approved, rendering, QA, needs Dan, composed, uploaded private,
   published, workings purged); a single idempotent planner derives the next step from what exists
   on disk; every step writes temp plus rename with an input manifest. The Director format is a
   view of it for previewing; `plan.json` is replaced by plan data nested under each scene.
4. **Compositor.** v1 productionises the compositing functions of `render.py` as
   `server/src/streamstudio/episode/`, paths from `Settings`, `render/lipsync.py:guard_cue` called
   per scene with tests on a shared fixture of guard cases, one frame rate and one loudness table.
   The stage stays for editing and preview. Revisit after ten episodes with a measured
   side-by-side.
5. **Paid step.** One confirm per episode through the existing `/api/heygen/render` gate, showing
   seconds, USD, wallet after, monthly total after, and a re-render allowance; worker retries count
   against it; a configurable monthly ceiling refuses to queue beyond it; the rate lives in
   `core/heygen.py`; the persisted approval is recorded on the episode so an unattended worker
   can check it. No MCP tool can confirm.
6. **QA.** JSON verdict per scene against the episode's stored reference; `ok` continues, `LOOK`
   continues with a flag in the report, `FAIL` re-renders within the allowance, then degrades to
   the small card and reports. Whisper word timings feed captions, card beats and a text-match
   check.
7. **Cards and captures.** Playwright full-page captures under an allow-list with a fresh
   profile; JSON storyboards over a template set with a generic default; `cues.json` emitted by
   the builder and read by the mixer; HyperFrames as a subprocess with its browser path from
   `Settings`.
8. **Assets and toolchain.** Intro MP4 cached per text, music, SFX, fonts and plate under
   `assets/` with a manifest; an `episode` extra (opencv, pillow, numpy, rembg, playwright)
   installed by the launcher; `/api/health` lists each tool; preflight before any episode.
9. **Output.** Final MP4 registered so `youtube_upload`, the vault and the library accept it
   without re-encoding; server-side publish kit; private upload with optional `publishAt`; purge
   job after the video is public.
10. **Rules as tests.** Scene length warning, question structure and reveal present,
    names-for-voice table, claim-source presence, an on-screen event every 8 s of avatar, guard
    honoured per scene, frame counts on concat: each a unit test on the validator or the
    compositor, run by `make test`.
11. **Vocabulary.** The script unit is a "scene" in everything Dan sees and the stage sets are
    renamed "sets"; "motion card" is one HyperFrames render covering a run of scenes about one
    site; the terms episode, scene, set, card, take, workings and publish kit are defined once in
    `docs/DESIGN.md`.
12. **PLAN.md.** This brief supersedes Decision 6 (live from the start) for product focus; the
    live studio is kept but no longer drives the roadmap.

**Suggested staging (each stage ends runnable and tested):**

* **Stage 0, measure and port.** Run Episode 1 v2 end to end on the Mac Studio with injected
  paths and record wall-clock per step (rembg, compose, one HyperFrames card, one per-scene HeyGen
  render, HeyGen concurrent limit and minimum billed seconds, disk per episode). Move intro, music,
  SFX, fonts into `assets/` with a manifest; add the `episode` extra and the health entries. No
  product surface yet.
* **Stage 1, episode and validator.** Episode record, `POST /api/episodes`, validator with
  warnings, MCP `episode_create` and `episode_status`, library artifact, status page in the
  editor. No paid step.
* **Stage 2, avatar batch and QA.** One confirm with allowance and ceiling, `take` in the key, N
  `heygen_clip` jobs, QA job with stored reference and contact sheets, cost ledger, morning
  summary, degrade path.
* **Stage 3, compose and publish, no site cards.** Compose per scene with the guard, concat,
  cached intro, music, server-side publish kit, registration as a recording, private upload,
  `publishAt`, purge job. The first daily episodes are ones without site mentions, since still
  site cards are forbidden by the production rules.
* **Stage 4, cards.** Capture recipes and allow-list, template storyboards with the generic
  default, `cues.json`, SFX from cues, plan generation from the question structure and site
  mentions (an agent through MCP may enrich it).
* **Stage 5, hardening.** End-to-end test with stubbed HeyGen (`HEYGEN_TRANSPORT`) and YouTube
  transports and synthetic clips from ffmpeg `lavfi`; the side-by-side that decides the
  compositor's future; the optional local-TTS lever for card scenes if Dan wants it.
