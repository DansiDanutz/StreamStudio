# Daily episode factory

*   **Author:** Dan (DansiDanutz)
*   **Status:** Proposed
*   **Date:** 2026-11-02
*   **Predecessor:** [concepts_brief.md](./concepts_brief.md) (six Goldfish reviews of [hypothesis.md](./hypothesis.md))

--------------------------------------------------------------------------------

## Overview

StreamStudio becomes the machine that turns a finished DansLab script into a published YouTube
episode, once a day, on the Mac Studio. A writer (Dan or an agent) delivers a script in the
channel's question-and-answer shape, split into scenes of about ten seconds. StreamStudio checks
it against the production rules, shows Dan the HeyGen cost once, renders every scene as its own
avatar clip, checks each clip, composes the studio picture around it, adds the logo intro, the
music bed and sound effects, builds the title, description with chapters and captions, uploads
the video as private, and purges the workings after Dan makes it public. Dan touches the process
three times: approve the script, approve the budget, publish.

The live studio (stage, Program window, go-live) stays as it is and is not used by the factory.
The hand-run scripts in `tools/compose` that produced Episode 1 v2 are the starting material for
the compositor, QA and mix, not the pipeline itself: they were built for one long HeyGen take and
have never run on the Mac Studio.

## The Problem

Episode 1 v2 took a chain of hand steps outside the app: a HeyGen render started and downloaded in
the HeyGen web UI, captions downloaded by hand to find the scene boundaries, site captures taken
by a person in Chrome, storyboards and a 36-entry creative plan written by hand in Python and
JSON, music pulled from a folder outside the repo, scripts run one by one from a Linux box with
hard-coded paths, and a final upload by hand. One episode this way is a project. One a day is not
possible.

The app already has most of the expensive parts: an idempotent per-scene HeyGen render with a
cost estimate and a confirm click, a job worker with retries and heartbeats, a lip-sync guard,
transcripts, a publish kit, a resumable YouTube upload that defaults to private, and an agent bus
so an agent can prepare everything and stop at the money. What it lacks is the thing that joins
them: an episode. There is no server-side record that says which scenes exist, which clips are
rendered, which passed QA, what it cost, where the final file is and whether it is public. The
script lives in the browser's local storage; jobs are flat rows with no grouping; the compositor,
QA and mixer live outside the app with no tests.

The proposed solution is an episode record owned by the server, a script contract with a
validator, and a small set of idempotent worker jobs that take an approved episode from clips to
a private upload, with exactly three human clicks and no step that spends money without one of
them.

## Goals

*   **One episode a day with three clicks.** From a finished script to a private YouTube upload
    with no action outside StreamStudio except Dan's three approvals (script, budget, publish or
    scheduled publish). Measured as: a wall-clock log per stage on the Mac Studio, and zero
    manual file moves, downloads or terminal commands per episode after Stage 3.
*   **Scenes are the unit.** Every scene is its own HeyGen clip, QA verdict and composite; the
    final video is a concatenation. A faulty scene is re-rendered alone and only scenes whose
    words changed are rendered again, through the existing clip key plus a take number.
*   **Money moves only behind a click.** One confirm per episode shows seconds, USD, wallet after,
    monthly total after and a re-render allowance. Worker retries count against the allowance.
    A monthly ceiling in settings refuses to queue beyond it. No MCP tool can confirm.
*   **The production rules are tests.** Scene length 3 to 13 s (warning), question-then-answer
    structure and the closing reveal present, names written for the voice, a source or softened
    wording on every numeric or ranking claim, an on-screen event at least every 8 s of avatar,
    the lip-sync guard called for every composed scene, frame counts checked on concatenation.
    Each is a unit test run by `make test`.
*   **Dan can see where an episode is from a phone.** One status page per episode: scene by
    scene and stage by stage, what it is blocked on, the last error in plain words, the next
    action, and the running cost. Readable through the API and MCP without the editor open.
*   **Everything the pipeline needs is declared and checked.** Fonts, intro, music, SFX and the
    studio plate under `assets/` with a manifest; a dependency extra installed by the Mac launcher;
    `/api/health` lists each tool; a preflight refuses to start an episode when anything is
    missing. No path is hard-coded.
*   **Workings are kept until the video is public, then purged by a job**, with the final MP4,
    the script and the episode record kept.

## Non-Goals

*   Writing or fact-checking scripts inside StreamStudio. The app validates the shape and the
    presence of sources; it does not judge truth. Writers stay outside.
*   Live streaming, the Program window, recording Dan on camera, or any change to the stage for
    this feature.
*   Rendering episodes with the browser stage in v1. Recorded as the long-term direction, decided
    after ten episodes with a measured side-by-side.
*   A general job dependency engine or scheduler, or any cron that spends money.
*   Automatic storyboards from arbitrary pages, hand-written Python storyboards on the daily
    path, or automatic capture of logged-in pages.
*   Backing up episode workings to the vault.
*   Multiple channels, presenters or languages; portrait Shorts; the local-voice cost lever for
    card scenes.
*   Keeping `cuts.py`, `scenecut.py`, `splice.py`, `stitch.py` or `masks.py` in the factory.

## Open Questions

Carried from the brief; each is answered in a later section or by Stage 0 measurement.

*   **Q1. Mac Studio numbers.** Wall-clock for rembg cut-out, compositing, one HyperFrames card
    and one per-scene HeyGen render; HeyGen's concurrent-render cap and minimum billed seconds per
    clip; disk per episode. Stage 0 measures these before any fan-out is designed.
*   **Q2. Re-render allowance default.** How many scenes and how many USD the first confirm may
    pre-authorise before the episode parks in "needs Dan". Proposed in the Technical Plan; Dan
    sets the number in settings.
*   **Q3. Captured sites that need a login.** The JEV trading page in Episode 1 was a logged-in
    dashboard. The design captures only allow-listed public pages automatically; a logged-in page
    is captured once by hand into the library or not shown. Dan decides per site.
*   **Q4. Music bed level.** `docs/DESIGN.md` says about -28 LUFS, `mix.py` uses -36. One number
    goes into the loudness table in the Technical Plan.
*   **Q5. Episode 1 v2.** Imported into the new episode record as the first test fixture, or
    frozen as the last hand-made episode. Proposed: imported, since its script, plan and durations
    are the only real data the validator and compositor can be tested against.

## Critical User Journeys (CUJs)

### CUJ 1: A script becomes a private upload with three clicks

*   **Given**: The Mac Studio passes preflight (all tools, fonts and assets present), the HeyGen
    API key and a YouTube channel are connected, and a writer has posted a finished script to the
    episode API with scene ids, on-screen text, voice text, sources and site URLs.
*   **When**: Dan opens the episode page, reads the validator's warnings next to the scenes, edits
    a line or two, and clicks Approve script; then reads one cost screen (36 scenes, 318 s, 12.25
    USD, wallet after, month after, allowance 4 scenes / 1.50 USD) and clicks Approve budget.
*   **Then**: The worker renders every scene, runs QA, re-renders within the allowance, composes,
    concatenates, adds intro, music and SFX, builds the publish kit, uploads as private and sets
    the episode state to "uploaded private". Dan sees the private video link and clicks Publish
    (now or at a chosen time). After the video is public the workings are purged. Nothing was
    done outside the app, and no render ran without one of the two approvals.

### CUJ 2: A scene fails QA at 02:00

*   **Given**: An episode is rendering overnight; the allowance was 4 scenes.
*   **When**: Scene 17 fails QA twice (face missing), spending two of the four allowance scenes,
    and scene 23 fails three times.
*   **Then**: Scene 17 passes on the third try. Scene 23 exhausts its share and is composed in the
    small guard-compliant card over its motion card with a flag in the episode report; the episode
    continues to a private upload. In the morning the status page says: "Scene 23 degraded to the
    small card after 3 failed renders (frozen frame). Re-voice it for about 0.40 USD, or keep." No
    money was spent beyond the allowance.

### CUJ 3: Only changed words are rendered again

*   **Given**: An uploaded private episode; Dan changes the words of scenes 6 and 12 and approves
    the script again.
*   **When**: The cost screen shows 2 scenes, 19 s, about 0.75 USD.
*   **Then**: Only those two clips are rendered (the clip key changed), the two composites and the
    concatenation are rebuilt, cards that depended on the old durations are rebuilt, the publish
    kit's captions and chapters are regenerated, and the upload is replaced or re-uploaded
    according to the YouTube rules in the Technical Plan.

### CUJ 4: An agent prepares an episode and stops at the money

*   **Given**: An agent with MCP access and a topic.
*   **When**: It posts the script, reads the validator's warnings, fixes them, and asks for the
    estimate.
*   **Then**: The episode sits in "script ready" with the estimate on the status page. The agent
    cannot approve the budget; Dan sees one card on his phone with two buttons.

## Technical Plan (Architecture)

### Shape of the system

Nothing new runs. The same three processes (API, worker, browser) gain one entity, the episode,
and the worker gains a handful of handlers. The agent bus and MCP server expose the episode the
way they expose clips and recordings today.

```text
 writer (Dan or agent)                                    Dan (phone or Mac, over the tailnet)
   │ POST /api/episodes {script}                           │ approve script · approve budget · publish
   ▼                                                       ▼
 API ──► validator ──► episodes/<id>/episode.json ◄──── episode page (editor) / MCP episode_status
   │                        ▲        │
   │ enqueue episode_advance│        │ read by every handler, written only by the planner
   ▼                        │        ▼
 worker: episode_advance (planner) ── derives the next step from episode.json + files on disk
   ├─ heygen_clip ×N (exists; + take)     → assets/avatar/clips/<key>.mp4 (+ .cutout.webm)
   ├─ scene_qa ×N                         → episodes/<id>/qa/<scene>.json, qa-<scene>.jpg
   ├─ site_capture ×K, card_render ×K     → episodes/<id>/cards/<card>.mp4 + cues.json
   ├─ scene_compose ×N                    → episodes/<id>/scenes/<scene>.mp4
   ├─ episode_assemble                    → concat + intro + music + SFX → episodes/<id>/final.mp4
   ├─ episode_publish_kit                 → episodes/<id>/kit.json, final.srt
   ├─ episode_register                    → recordings/rec_<date>-ep.mp4 (+ .srt, .episode.json)
   ├─ youtube_upload (exists)             → video id, private
   └─ episode_purge (after public)        → removes workings, keeps final, script, record
```

Every box is an idempotent job keyed by what it produces; a crashed or repeated job finds its
output and returns. The planner is the only writer of `episode.json`; handlers write their own
files and a small result the planner reads back from `jobs.result`.

### The episode record

One directory per episode under `DATA_DIR/episodes/<episode_id>/`, created by `POST /api/episodes`.
The episode is also a `projects` row (the existing table), so `jobs.project_id` correlates every
job to its episode with no schema change to `jobs`. Migration 4 adds one table:

```text
episodes(id TEXT PK, project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
         status TEXT, title TEXT, created_at TEXT, updated_at TEXT,
         script_hash TEXT, budget_json TEXT, youtube_video_id TEXT, published_at TEXT)
```

The table holds what lists and status pages need. The full record is `episode.json`:

```text
episode.json
  id, title, status, created_at, updated_at
  script: { version, hash, scenes: [ scene ] }        # the approved contract (below)
  budget: { approved_at, approved_by, clips, seconds, usd, allowance: {scenes, usd},
            spent: {renders, seconds, usd}, ceiling_month_usd }
  reference: { face: [x,y,w,h], lip_ratio }           # QA cohort medians, first full pass
  scenes_state: { <scene_id>: { clip_key, take, video_id, duration_s, qa: ok|LOOK|FAIL|degraded,
                                qa_issues: [], composed_sha, card_id } }
  cards: { <card_id>: { scenes: [ids], template, url, durations_hash, mp4_sha, cues } }
  outputs: { final_mp4, final_srt, kit, recording_id, youtube_video_id, privacy, publish_at }
  log: [ { at, stage, scene?, message } ]              # plain-words events for the status page
```

States: `draft` → `script_approved` → `budget_approved` → `rendering` → `qa` → `composing` →
`uploaded_private` → `published` → `purged`, plus `needs_dan` (reachable from `rendering`, `qa`,
`composing`) and `failed`. Every transition appends to `log`.

### The script contract and validator

A script is posted as JSON and stored verbatim inside `episode.json`. One scene:

```text
scene: { id: "s12", text: "...on screen...", voice: "...as HeyGen reads it...",
         kind: "avatar" | "card", site?: "https://...", question?: 1,
         sources?: [ { claim: "fourteen thousand subscribers", source: "Dan, 2026-11-02" } ],
         plan?: { title?, lower?, lowers?, chips?, chip_at?, zoom?, zoom_path?, frame?,
                  glitch?, endcard?, whoosh_at? } }
```

`voice` is what HeyGen reads (names written for the voice); `text` is shown on screen and used
for captions when `voice` is empty. `plan` carries the per-scene creative data that
`episode-01-v2.plan.json` held positionally; it is optional and a scene without it still renders
(avatar scenes get the default table card on `question`, card scenes get the generic site card).
A converter imports the Episode 1 v2 files (script JSON, plan JSON, durations) into this shape
as the first fixture.

The validator runs on post and on every edit, returning `{errors, warnings}` per scene id:

| Check | Level | Rule source |
| --- | --- | --- |
| estimated length outside 3 to 13 s (`WORDS_PER_S = 2.5`) | warning | DESIGN rule 1 |
| no `question` marker, or no closing reveal scene (`reveal: true`) | warning | DESIGN rule 5 |
| a number, price, date, percentage or ranking word with no `sources` entry | warning | brief F.18 |
| `voice` contains a name in the names-for-voice table spelled the on-screen way | warning | DESIGN rule 6 |
| avatar scene with no `plan` element and estimated length over 8 s | warning | DESIGN rule 4 |
| `kind: card` without `site` | error | cards need a page |
| duplicate scene id, empty `voice` and `text` | error | |

Warnings never block approval. Errors do. The table of names for the voice lives in
`assets/brand/voice-names.json` (one entry per product: on-screen spelling, voice spelling).

### The planner: `episode_advance`

One handler, re-queueable at any time, that reads `episode.json` and the filesystem and decides
the next step. It never calls HeyGen, ffmpeg or a browser itself; it enqueues the handler that
does and returns. It is enqueued by the API after each approval, by every stage handler when it
finishes (via the existing `store.enqueue`), and by a `POST /api/episodes/{id}/advance` for a
manual resume. Rules, in order:

1. `budget_approved` and some scene has no clip for its current `(key, take)`: enqueue one
   `heygen_clip` per missing clip (payload as today plus `take`, `episode_id`), set
   `rendering`.
2. All clips present and some scene has no QA result for its current clip: enqueue `scene_qa`
   per scene; set `qa`. On the first full pass, store the cohort medians in `reference`.
3. A scene is `FAIL`: if `budget.allowance` has room, increment `take`, charge the allowance,
   enqueue `heygen_clip`; otherwise mark the scene `degraded` (composed in the small card) and
   log it. `LOOK` is recorded and continues.
4. All scenes `ok`, `LOOK` or `degraded`: enqueue `site_capture` for each card whose capture is
   missing or stale, then `card_render` for each card whose `durations_hash` changed, then
   `scene_compose` per scene whose inputs hash changed; set `composing`.
5. All composites present: enqueue `episode_assemble`, then `episode_publish_kit`, then
   `episode_register`, then `youtube_upload` (private, with the kit's title and description, and
   `publish_at` if Dan set one); set `uploaded_private`.
6. `published` (seen by `episode_publish_status`, below): enqueue `episode_purge`.

Fan-in is implicit: a stage handler enqueues `episode_advance` when it finishes, the planner
counts what exists, and only the last one of a stage finds everything present. Two planners running
at once are harmless because every handler is idempotent and the planner's own work is
`BEGIN IMMEDIATE` on the `episodes` row.

### The paid step

The confirm screen is served by `GET /api/episodes/{id}/estimate`, which reuses the estimate
logic of `routes/heygen.py:render` (moved into `core/heygen.py:estimate(items)` so the route,
the episode API and MCP share it) and adds: wallet after (`heygen.Client.me`), month after (sum
of `budget.spent.usd` over episodes created this month), the allowance, and the ceiling. The USD
rate moves from `HeygenPanel.tsx` into `core/heygen.py:USD_PER_S`, served to the editor.

`POST /api/episodes/{id}/approve-budget` records `budget.approved_at`, writes the allowance and
enqueues the planner. It is refused with 409 when month-after would pass
`Settings.heygen_month_ceiling_usd`. The MCP server has no tool for it. Worker retries of a
`failed` HeyGen render (the existing behaviour in `heygen_clip`) and QA re-renders both charge the
allowance; when it is spent the planner degrades instead of rendering. Defaults, all in
`Settings`: `episode_rerender_scenes = max(2, ceil(0.1 * scenes))`, `episode_rerender_usd = 1.50`,
`heygen_month_ceiling_usd = 400`.

The clip key gains `take`: `item_key(look, voice, script, motion, silent_s, take=0)`; `take=0`
reproduces today's key so every existing clip keeps its name. A rejected clip is renamed
`<key>.a<take>.mp4` before the next render so nothing is lost.

### QA: `scene_qa`

`tools/compose/qa_avatar.py:check` becomes `episode/qa.py:check_clip(mp4) -> dict` (same
measurements, the Haar cascade loaded from `assets/models/`). `scene_qa` runs it on one clip,
compares face box and lip ratio against `episode.reference` when present (the median of the
first full pass is stored by the planner; a lone re-render therefore has a cohort), writes
`qa/<scene>.json` and the contact sheet, and returns `{status, issues}`. Status is `FAIL` for
face, glitch or frozen faults, `LOOK` for lip warnings, `ok` otherwise, exactly the current
rule. Each clip is also transcribed locally (`core/transcribe`), and the result is kept as
`qa/<scene>.words.json`: a word error rate over 25 % against `scene.voice` is a `FAIL` (HeyGen
read the wrong words), and the word timings are the canonical clock for captions and card beats
(below). One whisper pass per clip serves both.

### Compositor: `scene_compose`, `episode_assemble`

The frame functions of `tools/compose/render.py` (`compose`, `mask_for`, `studio`, `zoom`,
`card_layer`, `table_card`, `place_table_card`, `glitch`, `CardVideo`) move to
`server/src/streamstudio/episode/compose.py` as functions taking a `Settings` and a scene; every
constant that was a path becomes `s.assets_dir / ...`; fonts come from `assets/brand/fonts/`.
`scene_compose` renders one scene's frames from its clip (video and audio untouched in time),
its cut-out mask (`<key>.cutout.webm`, already produced by `heygen_clip`; `masks.py` is dropped)
and its plan, and writes `scenes/<scene>.mp4` at 25 fps with the clip's audio, via a temp file
and rename. Before composing it calls `render/lipsync.py:guard_cue(cue, clip, voice)` with the
scene's clip and voice; an avatar scene whose guard says `pip`, and every `degraded` scene, is
composed with the face in `pip_rect` over the plate or its card. A unit test feeds the shared
guard fixtures through both `lipsync.py` and `compose.py` so they cannot disagree.

`episode_assemble` concatenates the scene files with ffmpeg's concat demuxer (identical encode
settings, frame counts checked against the measured durations), puts the cached intro in front,
and runs the mix: voice at -16 LUFS, music bed looped under everything from the end of the intro
at -36 LUFS (the level Episode 1 v2 shipped with; `docs/DESIGN.md` rule 3 is corrected to say
so), SFX at -26 LUFS at the cues from each card's `cues.json` and from the plan (`question`,
`whoosh_at`, `glitch`, `endcard`), final `loudnorm=I=-14:TP=-1.5:LRA=11`. One frame rate, 25 fps,
for clips, cards, intro and final. The logic comes from `mix.py`, rewritten as
`episode/mix.py:assemble(...)` with the library at `s.assets_dir / "brand" / "music"` and
`"sfx"`.

### Cards: `site_capture`, `card_render`

A card covers a run of consecutive `kind: card` scenes with the same `site`. `site_capture` runs
Playwright Chromium (already a dependency of `render/preview.py`) with a fresh profile, no
cookies, a 1400 px viewport, and takes `page.screenshot(full_page=True)` into
`episodes/<id>/caps/<host>.png`, plus the bounding boxes of the first heading and the main image
(`document.querySelector`) into `caps/<host>.json`. It refuses any URL not matching
`Settings.capture_allowlist` (a list of host patterns) and never logs in. A site that needs a
login is captured once by hand into `assets/sites/<host>/` and reused.

`card_render` builds a HyperFrames composition from a template and the capture: `generic`
(address bar, slow scroll, one zoom to the hero, one callout taken from the scenes' `text`),
`feature-ring` (ring on a selector-found rectangle), `compare`, `counter`. Templates are JSON
under `assets/cards/templates/`; the builder is `tools/compose/motion/build.py:Comp`, imported
from `episode/cards.py` after `build.py` stops executing at import. `Comp.write` also emits
`cues.json` (tab changes, counter landings); the mixer reads that file and the regex in
`mix.py:comp_times` goes. Rendering runs `npx hyperframes render` as a subprocess from
`assets/cards/` (which holds the `package.json`), with the browser path from
`Settings.hyperframes_browser` and a `-w` from `Settings.hyperframes_workers`. Beats inside a
card are placed on words: a template beat names a phrase from the scene's `voice`, and its time
comes from that scene's `qa/<scene>.words.json` offset by the scene's start in the card, so a
ring or a callout lands when Dan says the words, as `cards_v2.T` tried to do by guessing.

### Publish kit, registration, upload, publish status, purge

`episode_publish_kit` writes `kit.json` (title from the script title, description with chapters
at the `question` scenes' start times, tags) and `final.srt` from each scene's `text` or `voice`,
split into two lines of 42 characters as `publish/kit.ts` does, with each caption's start and end
taken from the whisper word timings of that scene (`qa/<scene>.words.json`) offset by the scene's
start in the final video. A scene whose transcript is missing falls back to splitting its measured
duration by character count.
`episode_register` copies `final.mp4` to `recordings/rec_<YYYYmmdd-HHMMSS>-ep.mp4`, `final.srt`
to `rec_...-ep.srt`, and writes `rec_...-ep.episode.json` naming the episode. `finish_recording`
is not run: the file is already H.264, AAC, normalised. The Recordings tab, the vault
(`local_path` matches `recordings/rec_*`), `youtube_upload` and the MCP `youtube_upload` tool
work unchanged. `youtube_upload`'s payload gains an optional `publish_at`, passed as
`status.publishAt` with `privacyStatus: private`, which is how YouTube schedules a public
release. `episode_publish_status` polls the video's privacy status every hour until it is
`public` (or `publish_at` has passed), then sets `published`. `episode_purge` removes
`caps/`, `cards/`, `scenes/`, `qa/` and the mix intermediates, keeps `episode.json`, `kit.json`,
`final.srt` and the registered recording, and logs the freed bytes.

### Status, observability, agents

`GET /api/episodes` and `GET /api/episodes/{id}` return the record with per-scene state, the
log, costs and the active job ids. The editor gets an Episode page (`?episode=<id>`, usable at
phone width) with the scenes, warnings, the three buttons, and a "Needs you" card that shows the
last log line and the one action that unblocks it. The library lists `episode:<id>` artifacts
with `episode.status` actions; the MCP server gains `episode_create`, `episode_status` and
`episode_estimate`, none of which can approve. Every job the planner enqueues carries
`project_id` and `payload.episode_id`; the worker log line includes it. `budget.spent` is the
cost ledger; `/api/health` reports the toolchain (ffmpeg, whisper, rembg, OpenCV, Playwright
Chromium, HyperFrames, fonts, intro, plate, music manifest) and `POST /api/episodes` returns 503
with the missing names when preflight fails.

### Vocabulary: scenes are script scenes, stage layouts are sets

So that "scene" means one thing to Dan and to agents, the saved stage layouts are renamed
"sets". The Library tab becomes "Sets", the artifact kind becomes `set` with ids `set:<id>`
(`scene:<id>` ids and the `scene.activate` and `scene.new` actions keep working as aliases for
one release, with a deprecation note in the catalog), the API gains `/api/sets` as the primary
path with `/api/scenes` kept as an alias, and the `Segment.scene` field is documented as "set".
`docs/AGENT_GUIDE.md`, `docs/AGENTS.md` and `docs/DESIGN.md` use the new words. The SQLite table
`scenes` is not renamed (no data migration; the name is internal).

### Assets and toolchain

`assets/brand/` gains `fonts/` (Inter OTF, the four intro woff2), `intro/` (the rendered
`intro-<hash>.mp4` per kicker, title and tagline), `music/`, `sfx/`, `voice-names.json` and
`manifest.json` (name, file, sha256, licence note). `assets/models/` holds the Haar cascade.
`assets/cards/` holds `package.json` and the templates. `pyproject.toml` gains an `episode`
extra (opencv-python-headless, pillow, numpy, scipy, rembg, playwright); the Mac launcher
installs `-e ".[episode]"` and runs `playwright install chromium` once per revision. New settings:
`episodes_dir` (default `data_dir/episodes`), `capture_allowlist`, `hyperframes_browser`,
`hyperframes_workers`, `episode_rerender_scenes`, `episode_rerender_usd`,
`heygen_month_ceiling_usd`.

### Data flow for one scene

```text
scene s12 (voice, plan) ──item_key(…, take)──► heygen_clip ──► clips/<key>.mp4 + .cutout.webm
        │                                                            │
        │                                              scene_qa ◄────┘  → qa/s12.json (ok|LOOK|FAIL)
        │                                                  │ FAIL & allowance → take+1 → heygen_clip
        │                                                  │ FAIL & no allowance → degraded
        └─ plan + card (if kind=card) ─► scene_compose(guard_cue) ─► scenes/s12.mp4 (25 fps, clip audio)
                                                                          │
                                       episode_assemble: concat + intro + music + SFX(cues.json) ─► final.mp4
```

## Alternatives Considered

Taken from the brief's "Alternatives Weighed", which recorded every option the six reviewers
rejected and why. The option chosen in this design is named after each.

### Alternative A: Write and fact-check the script inside StreamStudio

*   **Pros**: One tool for the whole day; the validator and the writer share a schema.
*   **Cons**: Ties the server to a model API that would need the same click-and-cost gate as
    HeyGen; duplicates the writing agents and skills Dan already runs; "fact-checked" cannot be
    implemented as truth verification, only as "a source is present".
*   **Reason for Rejection**: All six lenses. Chosen instead: a script contract plus validator;
    writers deliver through `POST /api/episodes` or MCP.

### Alternative B: Port `tools/compose` as it stands, one job per script

*   **Pros**: Smallest change on paper; the scripts produced one real episode.
*   **Cons**: Built for one long HeyGen take; Linux-only paths; work executed at import; no tests;
    `masks.py` duplicates `avatar/cutout.py`; `mix.py` reads cues by regex over HTML.
*   **Reason for Rejection**: Cannot run on the Mac Studio and cannot be tested. Chosen instead:
    the compositing, QA and mix functions are rewritten under `server/src/streamstudio/episode/`
    with injected paths; `ffmpeg` and `npx hyperframes render` stay subprocesses.

### Alternative C: One long HeyGen take cut by captions (how Episode 1 v2 was made)

*   **Pros**: One `create_video` call; continuous framing across scenes; HeyGen's captions give
    scene boundaries.
*   **Cons**: The captions file is downloaded by hand in the HeyGen UI; fixing one scene means
    re-rendering the whole take or a splice that cannot survive a length change; per-scene jobs
    already exist and give changed-words-only re-rendering for free.
*   **Reason for Rejection**: Blocks the per-scene re-render that the production rules require.
    Chosen instead: per-scene clips and concatenation; framing drift is caught by QA against a
    stored reference.

### Alternative D: The browser stage recorded headlessly as the compositor

*   **Pros**: One compositor, one guard, one CSS brand grammar; editor preview equals output;
    reuses scenes, cues, table objects and media cards.
*   **Cons**: Real-time capture is not frame-exact and drops frames non-deterministically; the
    25 versus 30 fps question is open; the table-card and zoom-path grammar of Episode 1 exists
    only in `render.py`; `preview.py` is a script, not a job.
*   **Reason for Rejection**: Not proven to produce an episode; quality is not traded. Recorded
    as the long-term direction: after ten episodes, a side-by-side of `render.py` output and a
    frame-by-frame Playwright render of the stage decides whether `render.py` is retired.

### Alternative E: HyperFrames for the whole episode

*   **Pros**: Intro, cards, chips and framing in one composition sharing CSS with the stage.
*   **Cons**: Long renders; the avatar cut-out would have to be handled inside HTML video
    elements; untested at episode length.
*   **Reason for Rejection**: Too large a change for v1; noted as a way to share CSS later.

### Alternative F: Automatic re-render on QA fail with no click

*   **Pros**: No overnight stall.
*   **Cons**: Violates the rule that paid APIs never run without an explicit action and a shown
    cost; the worker already retries a failed HeyGen render as a new paid one.
*   **Reason for Rejection**: `CLAUDE.md`. Chosen instead: a re-render allowance shown and
    approved on the one confirm; retries count against it; beyond it the scene degrades.

### Alternative G: Stall the episode when a scene fails QA after the allowance

*   **Pros**: Nothing ships with a visible fault.
*   **Cons**: The daily cadence depends on Dan's hours; a 02:00 failure costs the day.
*   **Reason for Rejection**: Chosen instead: degrade the scene to the small guard-compliant
    card, ship, report in plain words, re-voice later if Dan wants.

### Alternative H: A daily cron that starts the pipeline

*   **Pros**: Hands-off start.
*   **Cons**: Either spends money unattended or stops at the gate anyway.
*   **Reason for Rejection**: Replaced by a queue of episodes in flight with asynchronous gates.

### Alternative I: Agent-written Python storyboards per episode (today's `cards_v2.py`)

*   **Pros**: Full creative control per card.
*   **Cons**: Unverifiable until rendered; page-pixel coordinates break when a site changes; a
    bug stops the mix; nothing produces one from a script.
*   **Reason for Rejection**: Not a daily process. Chosen instead: JSON storyboards over a
    template set, a generic card as the default, selector-found rectangles.

### Alternative J: An agent driving a browser for captures

*   **Pros**: Handles any page, including scrolling and sticky elements.
*   **Cons**: Not idempotent; violates the private-dashboard rule by default; needs credentials.
*   **Reason for Rejection**: Chosen instead: Playwright full-page screenshots under an
    allow-list with a fresh profile; logged-in sites captured once by hand into `assets/sites/`.

### Alternative K: Keep the episode in the Director's localStorage and drive it over the agent bus

*   **Pros**: No new storage.
*   **Cons**: `POST /api/agent/do` is 409 without an open editor; localStorage is per browser;
    the worker cannot read it.
*   **Reason for Rejection**: An unattended pipeline cannot depend on an open tab.

### Alternative L: A job dependency (DAG) layer in the worker

*   **Pros**: Explicit ordering.
*   **Cons**: New claim rules, new schema on `jobs`, more code than the feature needs.
*   **Reason for Rejection**: Chosen instead: one re-queueable planner deriving the next step
    from the episode record and the files on disk; handlers stay idempotent.

### Alternative M: Store the plan as an EDL in `edl_versions`

*   **Pros**: Reuses versioning and optimistic concurrency.
*   **Cons**: The EDL holds cuts on tracks, not chips, lowers, zoom paths or sound cues.
*   **Reason for Rejection**: The `projects` row and `jobs.project_id` are reused for
    correlation; the plan lives inside the episode record; an EDL may be derived for the editor.

### Alternative N: Intro, music and SFX as per-episode render steps

*   **Pros**: Always current.
*   **Cons**: They change with branding, not episodes; the intro needs fonts copied by hand.
*   **Reason for Rejection**: Rendered once per text and cached under `assets/brand/`.

### Alternative O: External fact-checking APIs

*   **Pros**: Independent verification.
*   **Cons**: Paid or rate-limited; Episode 1's claims are mostly Dan's own business facts.
*   **Reason for Rejection**: The validator checks that a source or softened wording is present.

### Alternative P: Word timings from HeyGen captions, from text proportion, or from measured clip durations only

*   **Pros**: HeyGen captions are exact; text proportion needs no tool; measured durations alone
    need no transcript.
*   **Cons**: HeyGen captions require a manual download; proportion (`cards_v2.T`) guesses;
    measured durations time scene boundaries but not words inside a scene.
*   **Reason for Rejection**: Whisper is local, free and already a dependency, and the same pass
    powers the wrong-words QA check, so word timings cost nothing extra. Dan confirmed the brief's
    choice during reconciliation: whisper word timings are canonical for captions and card beats,
    with measured durations as the fallback.

### Alternative Q: Make the video public only in YouTube Studio

*   **Pros**: No new code.
*   **Cons**: Contradicts "no step outside the app" and ties the daily cadence to Dan's hours.
*   **Reason for Rejection**: Publish is a third in-app click, with YouTube's `publishAt` for a
    scheduled release.

### Alternative R: A new `episode` artifact kind for the final MP4 (and a shared deliverable lookup)

*   **Pros**: Cleaner model; episodes never masquerade as takes.
*   **Cons**: Four files and the MCP tool learn a second location (kind); or a refactor of every
    consumer of recordings (lookup).
*   **Reason for Rejection**: Dan chose to register the final MP4 as a take
    (`recordings/rec_<date>-ep.mp4` with an episode sidecar) so upload, vault, library and MCP
    work unchanged.

### Alternative S: A free local voice for the card scenes

*   **Pros**: Cuts HeyGen spend by roughly 45 %; the guard already keeps the face small in those
    scenes.
*   **Cons**: Voice continuity between HeyGen's cloned voice and a local one.
*   **Reason for Rejection**: Not adopted; recorded as the only lever that moves the monthly
    floor, for Dan to revisit.

--------------------------------------------------------------------------------

## Non-Functional Requirements

*   **Security and privacy.** The episode API sits behind the existing network guard (loopback
    and tailnet only). Capture jobs run Playwright with a fresh profile and refuse any URL outside
    `Settings.capture_allowlist`; they never hold cookies or credentials. The budget approval is a
    server-side record, so an unattended worker checks it rather than trusting the caller;
    `POST /api/heygen/render` keeps working for the editor, and the episode path never calls it
    without `budget.approved_at`. HeyGen, YouTube and vault secrets are untouched (0600, masked).
    Captions and publish kits contain only script text.
*   **Cost.** One confirm per episode; retries and QA re-renders charge a visible allowance; a
    monthly ceiling refuses approval. Every paid render writes to the episode's cost ledger. No
    MCP tool approves.
*   **Performance.** Thirty-six HeyGen clips at `worker_concurrency = 2` with a blocking poll
    serialise; Stage 0 measures HeyGen latency and the account's concurrent limit, and
    `Settings.worker_concurrency` is raised to the measured safe value for the Mac Studio. Scene
    composites are independent and run on the worker's threads; `episode_assemble` is a single
    ffmpeg pass. Disk per episode is measured in Stage 0; workings are purged after publish.
*   **Rollout and rollback.** Migration 4 adds the `episodes` table and touches nothing else;
    `take=0` keeps every existing clip name; the editor's Script panel, HeyGen panel, Program
    window and recordings are unchanged. The feature is reachable only through the new routes and
    the Episode page, so rolling back is removing the routes; existing data is unaffected.
    Episode 1 v2 is imported as a fixture, not migrated in place.
*   **Testability.** Every handler runs under `make test` with the fake HeyGen and YouTube
    transports that `test_heygen.py` and `test_youtube.py` already use, a fake HyperFrames
    renderer hook like `handlers.CUTOUT`, and synthetic clips made with ffmpeg's `lavfi`.

### Additional Resources

*   `CLAUDE.md`, `PLAN.md`, `docs/DESIGN.md` ("Episode production rules", "Lip-sync guard",
    "HeyGen rendering"), `docs/AGENTS.md`, `docs/AGENT_GUIDE.md`.
*   The per-directory contract READMEs under `server/src/streamstudio/` and `web/src/`.
*   `tools/compose/README.md`, `tools/compose/motion/README.md`, `tools/compose/motion/intro/README.md`.
*   Episode 1 v2: `docs/scripts/episode-01-v2.{md,json}`, `tools/compose/episode-01-v2.plan.json`,
    `tools/compose/episode-01-v2.durations.json`.
*   `docs/egm/daily-episode-factory/hypothesis.md` and `concepts_brief.md` (six Goldfish reviews).

### Future Improvements

*   **One compositor.** After ten episodes, a measured side-by-side of `episode/compose.py` and a
    frame-by-frame Playwright render of the browser stage decides whether the stage becomes the
    only renderer.
*   **Local voice for card scenes.** The guard already keeps the face small there; a free local
    voice would cut HeyGen spend by roughly 45 % at the cost of voice continuity.
*   **Non-blocking HeyGen polling.** One "submit all, then poll all" job per episode would free
    worker slots for captures and cards while HeyGen renders.
*   **Richer card templates and agent-authored storyboards** through an MCP `episode_plan`
    action, once the generic card has shipped a few episodes.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

Six stages, each ending runnable and tested. Files are listed once, under the stage that first
touches them; later stages extend them. Paths are relative to the repository root.

### Stage 0: measure and port the toolchain

#### 1. `server/pyproject.toml` (Modify)

*   **Type / Scope**: Python packaging.
*   **Proposed Changes**: Add an `episode` extra: `opencv-python-headless`, `pillow`, `numpy`,
    `scipy`, `rembg`, `playwright`. Keep `media` as a subset. Regenerate `uv.lock`.

#### 2. `server/uv.lock` (Modify)

*   **Type / Scope**: Lockfile.
*   **Proposed Changes**: Locked by `uv sync --extra episode`.

#### 3. `Makefile` (Modify)

*   **Type / Scope**: Developer entry points.
*   **Proposed Changes**: `setup-episode` target (`uv sync -p 3.12 --extra episode` then
    `.venv/bin/playwright install chromium`, and `npm ci` in `assets/cards/`); `test` unchanged.

#### 4. `mac/StreamStudio.app/Contents/MacOS/StreamStudio` (Modify)

*   **Type / Scope**: Bash launcher.
*   **Proposed Changes**: Step 2 installs `-e ".[episode]"` and runs `playwright install
    chromium` once per revision; a new step installs `assets/cards/` node modules once per
    revision. Failure messages name the missing tool.

#### 5. `server/src/streamstudio/core/config.py` (Modify)

*   **Type / Scope**: Settings.
*   **Proposed Changes**: Add `episodes_dir` property (`data_dir / "episodes"`),
    `capture_allowlist: list[str]`, `hyperframes_browser: Path | None`,
    `hyperframes_workers: int = 4`, `episode_rerender_scenes_min: int = 2`,
    `episode_rerender_fraction: float = 0.1`, `episode_rerender_usd: float = 1.5`,
    `heygen_month_ceiling_usd: float = 400`, `episode_fps: int = 25`. `ensure_dirs` creates
    `episodes_dir`.

#### 6. `assets/brand/fonts/` (Create), `assets/brand/music/`, `assets/brand/sfx/`, `assets/brand/intro/`, `assets/brand/voice-names.json`, `assets/brand/manifest.json` (Create)

*   **Type / Scope**: Vendored assets.
*   **Proposed Changes**: Inter OTF and the four intro woff2 files; the owned music and SFX
    clips that `mix.py` and the intro used; the rendered intro MP4 at 25 fps named by a hash of
    kicker, title and tagline; the names-for-voice table; a manifest with name, file, sha256 and
    licence note for every entry. Large binaries follow the repo's existing policy for
    `assets/avatar` (vault-eligible; see file 31).

#### 7. `assets/models/haarcascade_frontalface_default.xml` (Move from `tools/compose/models/`)

*   **Type / Scope**: QA model file.
*   **Proposed Changes**: Served from `assets_dir` so `episode/qa.py` loads it from `Settings`.

#### 8. `assets/cards/package.json`, `assets/cards/templates/{generic,feature-ring,compare,counter}.json` (Create)

*   **Type / Scope**: HyperFrames workspace and card templates.
*   **Proposed Changes**: `hyperframes` and `gsap` as dependencies; one JSON template per card
    type describing the `Comp` calls (page, cam, ring, call, chips, counter) with placeholders for
    the capture, selector rectangles and scene phrases.

#### 9. `tools/brand/make_intro.py` (Move from `tools/compose/motion/intro/make_intro.py`)

*   **Type / Scope**: One-off brand generator.
*   **Proposed Changes**: Reads fonts from `assets/brand/fonts/`, writes to `assets/brand/intro/`,
    at 25 fps; documented as "run when the branding changes", not part of the pipeline.

#### 10. `server/src/streamstudio/api/routes/system.py` (Modify)

*   **Type / Scope**: Health route.
*   **Proposed Changes**: `tools` gains `opencv`, `rembg`, `playwright_chromium`, `hyperframes`,
    `fonts`, `intro`, `plate`, `music_manifest`, each a version or path or `None`; a
    `preflight_ok` boolean and `missing` list computed by a shared `episode.preflight.check(s)`.

#### 11. `docs/egm/daily-episode-factory/stage0-measurements.md` (Create)

*   **Type / Scope**: Measurement record.
*   **Proposed Changes**: Wall-clock per step for Episode 1 v2 on the Mac Studio, HeyGen latency
    and concurrent limit, minimum billed seconds, disk per episode. Feeds the defaults in file 5.

### Stage 1: episode record, contract, validator, status

#### 12. `server/src/streamstudio/core/db.py` (Modify)

*   **Type / Scope**: SQLite migrations.
*   **Proposed Changes**: Migration 4 creates `episodes` (id, project_id, status, title,
    created_at, updated_at, script_hash, budget_json, youtube_video_id, published_at) with an
    index on `status`.

#### 13. `server/src/streamstudio/episode/__init__.py` (Create)

*   **Type / Scope**: New package.
*   **Proposed Changes**: Exposes `record`, `contract`, `validate`, `planner`, `qa`, `compose`,
    `mix`, `cards`, `capture`, `kit`, `preflight`.

#### 14. `server/src/streamstudio/episode/contract.py` (Create)

*   **Type / Scope**: Pydantic models.
*   **Proposed Changes**: `Scene` (id, text, voice, kind, site, question, reveal, sources,
    plan), `Plan` (title, lower, lowers, chips, chip_at, zoom, zoom_path, frame, glitch,
    endcard, whoosh_at), `Script` (title, kicker, tagline, scenes), `extra="forbid"`; a
    `script_hash(script)`; `from_episode1_v2(script_json, plan_json, durations_json)` converter.

#### 15. `server/src/streamstudio/episode/validate.py` (Create)

*   **Type / Scope**: Validator.
*   **Proposed Changes**: `validate(script, s) -> {errors, warnings}` keyed by scene id
    implementing the table in the Technical Plan; duration estimate shared with
    `core/heygen.py:estimate`; claim detection by a number, currency, percent, date and ranking
    regex; names table from `assets/brand/voice-names.json`.

#### 16. `server/src/streamstudio/episode/record.py` (Create)

*   **Type / Scope**: Episode record storage.
*   **Proposed Changes**: `create(conn, s, script) -> Episode` (creates the `projects` row, the
    `episodes` row, the directory, writes `episode.json`); `load(s, id)`, `save(s, episode)`
    (temp plus rename), `set_status`, `log(event)`, `list(conn)`; the per-scene state helpers
    (`scene_key(scene, cfg, take)`, `inputs_hash(scene, clip, card)`).

#### 17. `server/src/streamstudio/api/routes/episodes.py` (Create)

*   **Type / Scope**: FastAPI router, prefix `/api/episodes`.
*   **Proposed Changes**: `POST ""` (validate, 503 on preflight failure, 422 on errors, create),
    `GET ""`, `GET /{id}`, `PUT /{id}/script` (re-validate, bump version, mark changed scenes),
    `POST /{id}/approve-script`, `GET /{id}/estimate`, `POST /{id}/approve-budget` (409 over the
    ceiling), `POST /{id}/publish` (`publish_at` optional), `POST /{id}/advance`,
    `POST /{id}/purge`, `GET /{id}/qa/{scene}.jpg` (contact sheet). Ids validated by regex.

#### 18. `server/src/streamstudio/api/main.py` (Modify)

*   **Type / Scope**: App factory.
*   **Proposed Changes**: Import and mount `episodes.router`.

#### 19. `server/src/streamstudio/api/routes/agent.py` (Modify)

*   **Type / Scope**: Library and agent bus.
*   **Proposed Changes**: `GROUPS` gains `"episode": "Episodes"`, `GROUP_ORDER` gains
    "Episodes"; `_server_artifacts` lists `episode:<id>` with status, cost and a
    `episode.status` action.

#### 20. `server/src/streamstudio/mcp.py` (Modify)

*   **Type / Scope**: MCP server.
*   **Proposed Changes**: Tools `episode_create(script)`, `episode_status(id)`,
    `episode_estimate(id)`, `episode_list()`; `youtube_upload` unchanged. No approve tool; the
    tool descriptions say so.

#### 21. `web/src/episode/EpisodePage.tsx`, `web/src/episode/api.ts`, `web/src/episode/README.md` (Create)

*   **Type / Scope**: React view and client.
*   **Proposed Changes**: Reachable at `?episode=<id>`; lists scenes with validator warnings and
    inline edit of `text`, `voice`, `sources`; buttons Approve script, Approve budget (shows the
    estimate screen), Publish (now or at a time); per-scene state chips and contact-sheet links;
    a "Needs you" card from the last log line; polls `GET /api/episodes/{id}` every 5 s; works at
    phone width (no stage).

#### 22. `web/src/App.tsx` (Modify)

*   **Type / Scope**: Routing.
*   **Proposed Changes**: `?episode=` renders `EpisodePage` before the editor branch, like
    `?render=1` and `?program=1`.

#### 23. `web/src/library/groups.ts` (Modify)

*   **Type / Scope**: Library grouping.
*   **Proposed Changes**: `GROUPS.episode = 'Episodes'`, `TABS` gains 'Episodes',
    `KIND_LABEL.episode`.

#### 24. `server/tests/test_episodes.py` (Create)

*   **Type / Scope**: Unit and API tests.
*   **Proposed Changes**: Contract round-trip; the Episode 1 v2 converter reproduces 36 scenes
    with the known durations; each validator rule on a minimal script (warning versus error);
    create, approve-script, estimate, approve-budget refused over the ceiling, status; preflight
    503 with missing names.

#### 25. `server/tests/fixtures/episode-01-v2/` (Create)

*   **Type / Scope**: Test fixture.
*   **Proposed Changes**: Copies of `docs/scripts/episode-01-v2.json`,
    `tools/compose/episode-01-v2.plan.json`, `episode-01-v2.durations.json`, and the converted
    `script.json`.

### Stage 2: avatar batch, QA, cost

#### 26. `server/src/streamstudio/core/heygen.py` (Modify)

*   **Type / Scope**: HeyGen client and helpers.
*   **Proposed Changes**: `item_key(..., take: int = 0)` (take 0 reproduces today's key);
    `USD_PER_S = 0.0385`, `WORDS_PER_S = 2.5` moved here; `estimate(items) -> {seconds, usd,
    clips, with_motion}` used by the route, the episode API and MCP.

#### 27. `server/src/streamstudio/api/routes/heygen.py` (Modify)

*   **Type / Scope**: HeyGen route.
*   **Proposed Changes**: Use `core.heygen.estimate`; `Item` gains optional `take`; the
    response includes `usd`.

#### 28. `web/src/director/HeygenPanel.tsx` (Modify)

*   **Type / Scope**: Editor panel.
*   **Proposed Changes**: Reads `usd` from the estimate instead of the local `API_USD_PER_S`.

#### 29. `server/src/streamstudio/worker/handlers.py` (Modify)

*   **Type / Scope**: Job handlers.
*   **Proposed Changes**: `heygen_clip` accepts `take` and `episode_id`, renames a rejected clip
    to `<key>.a<take>.mp4` before re-rendering, and enqueues `episode_advance` when it carries an
    `episode_id`. New handlers registered from `episode/planner.py`, `episode/qa.py`,
    `episode/compose.py`, `episode/cards.py`, `episode/capture.py`, `episode/kit.py` (imported at
    module end so `HANDLERS` sees them). A `HYPERFRAMES_RENDER` hook for tests.

#### 30. `server/src/streamstudio/episode/planner.py` (Create)

*   **Type / Scope**: `episode_advance` handler.
*   **Proposed Changes**: The six rules in the Technical Plan; charges the allowance; writes
    `reference` after the first full QA pass; `BEGIN IMMEDIATE` on the `episodes` row; every
    enqueue carries `project_id` and `payload.episode_id`.

#### 31. `server/src/streamstudio/core/vault.py` (Modify)

*   **Type / Scope**: Vault mapping.
*   **Proposed Changes**: `local_path` and `CLIP_GLOBS` also mirror `assets/brand/**` (fonts,
    intro, music, sfx, manifest) so a fresh Mac can fetch them; episode workings stay unmapped.

#### 32. `server/src/streamstudio/episode/qa.py` (Create)

*   **Type / Scope**: `scene_qa` handler.
*   **Proposed Changes**: `check_clip(mp4, cascade) -> dict` ported from
    `tools/compose/qa_avatar.py:check`; `scene_qa` compares against `episode.reference`, writes
    `qa/<scene>.json` and `qa-<scene>.jpg`, runs `core.transcribe.transcribe` on the clip,
    writes the word timings to `qa/<scene>.words.json`, computes word error rate against
    `scene.voice` (FAIL over 25 %), returns `{status, issues, words}`.

#### 33. `server/tests/test_episode_pipeline.py` (Create)

*   **Type / Scope**: Worker tests.
*   **Proposed Changes**: Planner state machine on a three-scene fixture with the fake HeyGen
    transport: renders once per key, a FAIL re-renders with `take+1` within the allowance, the
    next FAIL degrades, retries charge the allowance, approval over the ceiling refused, two
    planners running at once produce one set of jobs; QA on synthetic clips (ffmpeg `lavfi`
    frames with and without a face image, frozen frames, a glitch frame); the transcript check
    with a stubbed `transcribe`.

### Stage 3: compose and publish (no site cards)

#### 34. `server/src/streamstudio/episode/compose.py` (Create)

*   **Type / Scope**: `scene_compose` handler and compositing functions.
*   **Proposed Changes**: The frame functions of `tools/compose/render.py` (`compose`,
    `mask_for`, `studio`, `zoom`, `card_layer`, `table_card`, `place_table_card`, `table_glow`,
    `glitch`, `neon_frame`, `CardVideo`) with `Settings` injected; the cut-out mask read from the
    clip's `.cutout.webm`; `guard_cue` from `render/lipsync.py` called per scene; `degraded` and
    guarded scenes composed in `pip_rect`; output `scenes/<scene>.mp4` at `episode_fps` with the
    clip's audio, temp plus rename, `inputs_hash` recorded.

#### 35. `server/src/streamstudio/render/lipsync.py` (Modify)

*   **Type / Scope**: Guard.
*   **Proposed Changes**: No behaviour change; `guard_cue` gains a docstring naming
    `episode/compose.py` as a caller, and the fixture file below is referenced.

#### 36. `server/tests/fixtures/lipsync_cases.json` (Create), `server/tests/test_lipsync.py` (Modify), `web/src/director/director.test.ts` (Modify)

*   **Type / Scope**: Shared guard fixtures.
*   **Proposed Changes**: Cases of (cue, clip, voice) to expected cue and small-card placement;
    the Python test runs them through `lipsync.py` and `compose.py`, the vitest test through
    `types.ts:guardCue` and `cueLayouts.ts:guardLayout`, so the three copies cannot drift.

#### 37. `server/src/streamstudio/episode/mix.py` (Create)

*   **Type / Scope**: `episode_assemble` handler.
*   **Proposed Changes**: Concat demuxer over `scenes/*.mp4` with frame-count check; intro from
    `assets/brand/intro/`; music bed and SFX from the manifest; cues from each card's `cues.json`
    and the plan; the loudness table (`-16`, `-36`, `-26`, final `-14/-1.5/11`) as one constant
    dict; writes `final.mp4` and `final.cues.json`.

#### 38. `server/src/streamstudio/episode/kit.py` (Create)

*   **Type / Scope**: `episode_publish_kit` and `episode_register` handlers.
*   **Proposed Changes**: `kit.json` (title, description with chapters at `question` scenes,
    tags) and `final.srt` (two lines of 42 characters per caption, timed from each scene's
    `qa/<scene>.words.json`, falling back to measured duration split by characters), mirroring
    `web/src/publish/kit.ts`; registration copies to `recordings/rec_<stamp>-ep.mp4`,
    `.srt` and writes `rec_<stamp>-ep.episode.json`; returns the recording id.

#### 39. `server/src/streamstudio/core/youtube.py` (Modify)

*   **Type / Scope**: YouTube client.
*   **Proposed Changes**: `clean_meta` accepts `publish_at` (RFC 3339, future); `upload` sends
    `status.publishAt` when present; `video_status(api, video_id) -> privacy` for the publish
    poll.

#### 40. `server/src/streamstudio/api/routes/youtube.py` (Modify)

*   **Type / Scope**: Upload route.
*   **Proposed Changes**: `UploadIn.publish_at: str | None`; passed through to the payload.

#### 41. `server/src/streamstudio/episode/publish.py` (Create)

*   **Type / Scope**: `episode_publish_status` and `episode_purge` handlers.
*   **Proposed Changes**: Hourly poll of the video's privacy until public or past `publish_at`;
    sets `published`; purge removes `caps/`, `cards/`, `scenes/`, `qa/`, mix intermediates, keeps
    `episode.json`, `kit.json`, `final.srt`; logs bytes freed.

#### 42. `web/src/publish/kit.ts` (Modify)

*   **Type / Scope**: Editor publish kit.
*   **Proposed Changes**: Export the caption-splitting constants and the chapter rule so the
    Python port and the TypeScript stay in one documented place; no behaviour change.

#### 43. `server/tests/test_episode_publish.py` (Create)

*   **Type / Scope**: Tests.
*   **Proposed Changes**: Kit chapters from question markers; SRT line splitting equals the
    TypeScript fixtures from `web/src/publish/kit.test.ts`; registration names and sidecar;
    upload with `publishAt` through the fake transport; purge keeps the right files.

#### 44. `server/tests/test_youtube.py` (Modify)

*   **Type / Scope**: Tests.
*   **Proposed Changes**: `clean_meta` with `publish_at`; `video_status`.

### Stage 4: captures and cards

#### 45. `server/src/streamstudio/episode/capture.py` (Create)

*   **Type / Scope**: `site_capture` handler.
*   **Proposed Changes**: Playwright Chromium, fresh context, 1400 px viewport,
    `page.screenshot(full_page=True)` to `caps/<host>.png`, selector rectangles to
    `caps/<host>.json`; allow-list check; `assets/sites/<host>/` used when present and the
    allow-list says `manual`.

#### 46. `server/src/streamstudio/episode/hyperframes.py` (Move from `tools/compose/motion/build.py`)

*   **Type / Scope**: Composition builder.
*   **Proposed Changes**: `Comp` unchanged in API; no import-time work; `write` emits
    `cues.json`; `render` takes the browser path and worker count from `Settings` and runs from
    `assets/cards/`.

#### 47. `server/src/streamstudio/episode/cards.py` (Create)

*   **Type / Scope**: `card_render` handler.
*   **Proposed Changes**: Groups consecutive card scenes by `site`; picks the template (plan
    `card_template` or `generic`); fills placeholders from the capture and scene phrases; places
    beats on the words named by the template using each scene's `qa/<scene>.words.json` offset by
    the scene's start in the card (scene boundary when a phrase is not found); writes
    `cards/<card>.mp4` and `cues.json`; records `durations_hash` over the word files it used.

#### 48. `server/tests/test_episode_cards.py` (Create)

*   **Type / Scope**: Tests.
*   **Proposed Changes**: Template fill from a fixture capture; `cues.json` emitted; allow-list
    refusal; the renderer stubbed through the `HYPERFRAMES_RENDER` hook.

### Stage 5: hardening, documentation, removal of the hand-run pipeline

#### 49. `tools/compose/cuts.py`, `scenecut.py`, `splice.py`, `masks.py`, `peek.py`, `motion/stitch.py` (Delete)

*   **Type / Scope**: Long-take tooling.
*   **Proposed Changes**: Removed; their purpose is covered by per-scene clips, cut-outs from
    `heygen_clip`, the planner and the status page's contact sheets.

#### 50. `tools/compose/render.py`, `qa_avatar.py`, `mix.py`, `motion/build.py`, `motion/cards.py`, `motion/cards_v2.py`, `motion/intro/make_intro.py` (Delete)

*   **Type / Scope**: Moved into the server package or fixtures.
*   **Proposed Changes**: Deleted after files 34, 32, 37, 46, 9 land; the Episode 1 v2
    storyboards are kept only as the JSON fixture (file 25).

#### 51. `tools/compose/README.md`, `tools/compose/motion/README.md`, `tools/compose/motion/intro/README.md`, `tools/README.md` (Modify or Delete)

*   **Type / Scope**: Contract READMEs.
*   **Proposed Changes**: `tools/compose/` keeps the two plan JSON files and a README pointing at
    `server/src/streamstudio/episode/README.md`; the motion and intro READMEs are removed with
    their code; `tools/README.md` updated.

#### 52. `server/src/streamstudio/episode/README.md` (Create), `server/src/streamstudio/README.md`, `server/src/streamstudio/api/routes/README.md`, `server/src/streamstudio/worker/README.md`, `server/src/streamstudio/core/README.md`, `web/src/README.md`, `web/src/library/README.md`, `README.md` (Modify)

*   **Type / Scope**: EGM contract READMEs.
*   **Proposed Changes**: The new package's contract; the parents list it; the route, worker,
    core, web and root READMEs gain the new routes, handlers, settings, tools, group and the
    episode as a system boundary; the root README's Status drops "Next: YouTube upload".

#### 53. `docs/DESIGN.md` (Modify)

*   **Type / Scope**: Design reference.
*   **Proposed Changes**: "Episode production rules" gains the vocabulary (episode, scene, set,
    card, take, workings, kit), the -36 LUFS bed, 25 fps, the allowance rule and the three clicks;
    the "Scenes" section is retitled "Sets"; the offline compositor section points at
    `episode/compose.py`.

#### 54. `docs/AGENTS.md`, `docs/AGENT_GUIDE.md` (Modify)

*   **Type / Scope**: Agent docs.
*   **Proposed Changes**: The episode tools, the script contract, "what agents cannot do" gains
    "approve a budget".

#### 55. `CLAUDE.md`, `PLAN.md` (Modify)

*   **Type / Scope**: Project instructions and plan.
*   **Proposed Changes**: `CLAUDE.md` Layout lists `episode/`; Rules add "the episode planner is
    the only writer of `episode.json`" and "no handler calls HeyGen without `budget.approved_at`".
    `PLAN.md` gains milestone S9 (the factory) and a note that Decision 6 no longer drives the
    roadmap.

#### 55a. `server/src/streamstudio/api/routes/scenes.py` (Modify)

*   **Type / Scope**: Stage sets route.
*   **Proposed Changes**: The router is mounted at both `/api/sets` (primary) and `/api/scenes`
    (alias); handler names and the `scenes` table unchanged.

#### 55b. `web/src/library/groups.ts`, `web/src/agent/catalog.ts`, `web/src/agent/bridge.ts`, `web/src/stage/sceneSync.ts` (Modify)

*   **Type / Scope**: Editor vocabulary.
*   **Proposed Changes**: Library tab "Sets" and `KIND_LABEL.set`; the catalog publishes
    `set:<id>` artifacts with `set.activate` and `set.new` actions, and `scene:<id>`,
    `scene.activate`, `scene.new` as aliases marked deprecated; `bridge.ts:EXECUTORS` accepts both
    names; `sceneSync.ts` calls `/api/sets`.

#### 55c. `server/src/streamstudio/api/routes/agent.py`, `server/src/streamstudio/mcp.py` (Modify, continued)

*   **Type / Scope**: Server-side artifacts and MCP docs.
*   **Proposed Changes**: `_server_artifacts` emits `set:<id>` (kind `set`, group "Sets") and
    accepts `scene:` ids in `library_get` and `library_name` as aliases; the `studio_guide` text
    and tool descriptions use "set".

#### 55d. `web/src/library/groups.test.ts`, `web/src/agent/agent.test.ts`, `server/tests/test_agent.py`, `server/tests/test_api.py` (Modify)

*   **Type / Scope**: Tests.
*   **Proposed Changes**: Both the new and the alias names resolve; the alias is flagged
    deprecated in the catalog.

#### 56. `server/tests/test_episode_e2e.py` (Create)

*   **Type / Scope**: End-to-end test.
*   **Proposed Changes**: The three-scene fixture from script to a registered recording and a
    fake upload with fake HeyGen, fake YouTube, stubbed HyperFrames and synthetic clips; asserts
    one paid render per key, the guard applied to a narration scene, frame counts on concat, the
    kit, the sidecar, the purge.

#### 57. `.github/workflows/ci.yml` (Modify)

*   **Type / Scope**: CI.
*   **Proposed Changes**: Server job installs the `episode` extra (headless OpenCV) so the
    compositor and QA tests run; Playwright is stubbed in tests, not installed in CI.

### Verification Plan

*   **Build**: `make build` (web) and `uv sync --extra episode` (server) on the Mac Studio;
    `make mac-app` then a cold start of StreamStudio.app passes preflight.
*   **Unit tests**: `make test` (`pytest` in `server/`, `vitest` in `web/`), including the new
    `test_episodes.py`, `test_episode_pipeline.py`, `test_episode_publish.py`,
    `test_episode_cards.py`, `test_episode_e2e.py` and the shared lip-sync fixtures.
*   **Static analysis**: `make lint` (`ruff`, `tsc -b`, `oxlint`); no import-time side effects
    (a test imports every module in `streamstudio.episode` and asserts no files are written).
*   **Coverage requirement**: every planner rule and every validator rule has a test; the guard
    fixtures pass in Python and TypeScript.
*   **Integration**: Stage 0 record (file 11) exists with real numbers; Episode 1 v2 re-rendered
    on the Mac Studio from the fixture with the compositor within visual tolerance of the shipped
    video (side-by-side contact sheet checked by Dan); one real three-scene episode from script to
    private upload with no step outside the app, timed.
*   **Success measure**: the first five daily episodes each log zero manual steps, their
    wall-clock, their HeyGen cost against the allowance, and their QA verdicts.
