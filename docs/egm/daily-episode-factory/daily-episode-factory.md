# Daily episode factory

*   **Author:** Dan (DansiDanutz)
*   **Status:** Proposed
*   **Date:** 2026-11-02
*   **Predecessor:** [concepts_brief.md](./concepts_brief.md) (six Goldfish reviews of [hypothesis.md](./hypothesis.md))
*   **Review:** Stage 5 to 7 findings resolved on 2026-11-02; see `goldfish_review_report.md`.

--------------------------------------------------------------------------------

## Overview

StreamStudio becomes the machine that turns a finished DansLab script into a published YouTube
episode, once a day, on the Mac Studio. A writer (Dan or an agent) delivers a script in the
channel's question-and-answer shape, split into scenes of about 10 seconds. StreamStudio then
runs the pipeline:

*   validates the script against the production rules;
*   shows Dan the HeyGen cost once;
*   renders every scene as its own avatar clip and checks each clip;
*   composes the studio picture around each clip;
*   adds the logo intro, the music bed and sound effects (SFX);
*   builds the title, the description with chapters, and the captions;
*   uploads the video as private;
*   purges the workings (the intermediate files) after Dan makes the video public.

Dan touches the process three times: approve the script, approve the budget, publish.

## The Problem

Episode 1 v2 took a chain of hand steps outside the app: a HeyGen render started and downloaded in
the HeyGen web UI, captions downloaded by hand to find the scene boundaries, site captures taken
by a person in Chrome, storyboards and a 36-entry creative plan written by hand in Python and
JSON, music pulled from a folder outside the repo, scripts run one by one from a Linux box with
hard-coded paths, and a final upload by hand. One episode this way is a project. One a day is not
possible.

The hand-run scripts in `tools/compose` that produced Episode 1 v2 are the starting material for
the compositor, QA and mix, not the pipeline itself: they were built for one long HeyGen take and
have never run on the Mac Studio. The live studio (stage, Program window, go-live) stays as it is
and is not used by the factory.

The app already has most of the expensive parts: an idempotent per-scene HeyGen render with a
cost estimate and a confirm click, a job worker with retries and heartbeats, a lip-sync guard,
local transcripts, a publish kit, a resumable YouTube upload that defaults to private, and an
agent bus so an agent can prepare everything and stop before any paid step. What it lacks is the
thing that joins them: an episode. There is no server-side record that says which scenes exist,
which clips are rendered, which passed quality assurance (QA), what it cost, where the final file
is and whether it is public. The script lives in the browser's local storage; jobs are flat rows
with no grouping; the compositor, QA and mixer live outside the app with no tests.

The proposed solution is an episode record owned by the server, a script contract with a
validator, and a small set of idempotent worker jobs that take an approved episode from clips to
a private upload, with exactly three human clicks and no step that spends money without one of
them.

## Goals

Each goal names its pass/fail measure. The mechanisms that meet them are in the Technical Plan.

*   **One episode a day with three clicks.** From a finished script to a private YouTube upload
    with no action outside StreamStudio except Dan's three approvals (script, budget, publish or
    scheduled publish). Measured as: zero manual file moves, downloads or terminal commands per
    episode once the thin slice (Stage 1) ships; a wall-clock log per step on the Mac Studio.
*   **Overnight turnaround.** From approve-budget to `uploaded_private` in under 12 hours on the
    Mac Studio for a 36-scene episode. Stage 0 measurement refines the number; the status page
    records the actual time for every episode.
*   **Dan's time stays small.** Under 15 minutes of Dan's interaction per episode across the three
    clicks, measured from the status page's timestamps.
*   **Only changed scenes are re-rendered.** A faulty scene is re-rendered alone. After a script
    edit, only scenes whose words changed are rendered again. Measured by the cost ledger: a
    word change in two scenes costs two clips.
*   **No money without a click.** One confirm per episode shows the seconds to render, the cost in
    USD, the wallet balance after this render, the month's total after this render, and the
    re-render allowance. A test proves that no `heygen_clip` job for an episode is ever enqueued
    without `budget.approved_at`, and that worker retries and QA re-renders never exceed the
    allowance. HeyGen cost per episode stays within estimate plus allowance.
*   **Every production rule is enforced automatically.** Scene length, question-then-answer
    structure with the closing reveal, names written for the voice, a source on every numeric or
    ranking claim, an on-screen event at least every 8 s of avatar, the lip-sync guard on every
    composed scene, frame counts on concatenation: each has a unit test.
*   **Dan can see where an episode is from a phone.** One status page per episode: scene by
    scene, what it is blocked on, the last error in plain words, the next action, and the running
    cost. Readable through the API and the Model Context Protocol (MCP) server without the editor
    open.
*   **The toolchain is declared and checked.** A preflight refuses to start an episode when any
    tool, font or asset is missing, and nothing is hard-coded to one machine.
*   **Workings are purged once the video is public.** The final MP4, the script and the episode
    record are kept.

## Non-Goals

*   Writing or fact-checking scripts inside StreamStudio. The app validates the shape and the
    presence of sources; it does not judge truth. Writers stay outside.
*   Live streaming, the Program window, recording Dan on camera, or any change to stage rendering
    for this feature.
*   Rendering episodes with the browser stage in v1 (see Alternative D and Future Improvements).
*   A general job dependency engine or scheduler, or any cron that spends money.
*   Automatic storyboards from arbitrary pages, hand-written Python storyboards on the daily
    path, or automatic capture of logged-in pages.
*   Card templates beyond the generic site card in v1.
*   Renaming the editor's saved stage layouts ("scenes") in the Library, API or agent catalog;
    this design only fixes the vocabulary in prose (see Future Improvements).
*   Backing up episode workings to the vault.
*   Multiple channels, presenters or languages; portrait Shorts; the local-voice cost lever for
    card scenes.
*   Keeping `cuts.py`, `scenecut.py`, `splice.py`, `stitch.py` or `masks.py` in the factory.

## Open Questions

*   **Q1. Mac Studio numbers.** Wall-clock for a per-scene HeyGen render, HeyGen's
    concurrent-render cap and minimum billed seconds per clip, whether a render HeyGen reports
    `failed` is billed (the design assumes it is until shown otherwise), rembg cut-out per clip,
    whisper transcription per clip, one HyperFrames card render, compositing per scene on the
    ported code, and disk per episode. Stage 0 measures the HeyGen, rembg, whisper and HyperFrames
    numbers; Stage 1 measures compositing on the ported compositor.
*   **Q3. Which logged-in sites Dan captures by hand.** The design captures only allow-listed
    public pages automatically; a logged-in page (the JEV trading dashboard in Episode 1) is
    captured once by hand or not shown. Dan decides per site.

Q2 (allowance default), Q4 (music bed level) and Q5 (Episode 1 v2 as a fixture) from the brief are
answered in the Technical Plan and the Verification Plan.

## Critical User Journeys (CUJs)

### CUJ 1: A script becomes a private upload with three clicks

*   **Given**: The Mac Studio passes preflight (all tools, fonts and assets present), the HeyGen
    API key and a YouTube channel are connected, and a writer has posted a finished script to the
    episode API with scene ids, on-screen text, voice text, sources and site URLs.
*   **When**: Dan opens the Episode page, reads the validator's warnings next to the scenes, edits
    a line or two, and clicks Approve script; then reads one cost screen (36 scenes, 318 s, 12.25
    USD, wallet balance after, month's total after, allowance 4 re-renders / 1.50 USD) and clicks
    Approve budget.
*   **Then**: The worker renders every scene, runs QA, re-renders within the allowance, composes,
    concatenates, adds intro, music and SFX, builds the publish kit, uploads as private and sets
    the episode to `uploaded_private`. Dan sees the private video link and clicks Publish (now, or
    at a chosen time). Once the video is public, the next time the episode is opened its workings
    are purged. Nothing was done outside the app, and no render ran without the budget approval.

### CUJ 2: A scene fails QA at 02:00

*   **Given**: An episode is rendering overnight; the allowance is 4 re-render attempts, shared by
    the whole episode.
*   **When**: Scene 17 fails QA (face missing); scene 23 fails QA (frozen frame).
*   **Then**: Scene 17 is re-rendered once and passes (1 attempt used). Scene 23 is re-rendered
    three times and fails each time (4 attempts used; the allowance is spent). Scene 23 is
    degraded: composed with the face in the small picture-in-picture rectangle over its site card
    or the studio plate, with a note in the episode log. The episode continues to a private
    upload. In the morning the status page says: "Scene 23 degraded to the small picture after 3
    failed re-renders (frozen frame). Keep it, or re-voice it in a new episode." No money was spent
    beyond the allowance.

### CUJ 3: Only changed words are rendered again

*   **Given**: A `budget_approved` episode whose clips have all rendered and passed QA, not yet
    uploaded.
*   **When**: Dan edits the words of scenes 6 and 12, clicks Approve script again, reads the cost
    screen (2 scenes, 19 s, about 0.75 USD) and clicks Approve budget.
*   **Then**: Only those two clips are rendered (their clip keys changed); the two composites and
    the concatenation are rebuilt; cards whose scene durations changed are rebuilt; the publish
    kit's captions and chapters are regenerated; the upload proceeds as in CUJ 1. Editing an
    episode that is already `uploaded_private` is refused; re-voicing after upload is a new
    episode (see "Publish").

### CUJ 4: An agent prepares an episode and stops before the paid step

*   **Given**: An agent with MCP access and a topic.
*   **When**: It posts the script, reads the validator's warnings, fixes them, and asks for the
    estimate.
*   **Then**: The episode stays in `draft` with the estimate on the status page. The agent cannot
    approve the budget. Dan sees one panel on his phone with two buttons: Approve budget, and
    Send back to writer (which adds a note to the episode log and leaves the episode in `draft`).

## Technical Plan (Architecture)

The work is staged in four stages (Detailed Implementation Plan): Stage 0 measures and installs
the toolchain; Stage 1 is the thin slice from script to private upload; Stage 2 adds QA, the
allowance and the full status page; Stage 3 adds site cards; Stage 4 hardens, documents and
removes the hand-run pipeline.

### Glossary

*   **Episode**: one script, one creative plan, one final MP4, one YouTube video id.
*   **Scene**: one row of the script, about 10 seconds, with its own HeyGen clip. (The editor's
    saved stage layouts are also called "scenes" in the Library and the API today; in this
    document they are called **sets**.)
*   **Card**: a HyperFrames site composition, an animated browse of a web page rendered to video,
    covering a run of consecutive card scenes about one site. HyperFrames is HeyGen's HTML-to-video
    renderer, run locally with `npx hyperframes render`.
*   **Table overlay**: the graphics drawn on an avatar scene: a **lower** (a lower-third caption
    with a name and a line), **chips** (small labels that rise one by one), a title card, the end
    card.
*   **Plate**: the studio background image behind the presenter.
*   **Take**: one rendering attempt of a scene's clip; re-renders increment the take number.
*   **Allowance**: the number of re-render attempts, and the USD, that one budget approval
    pre-authorises for the whole episode beyond the first render of each scene. Both caps hold.
*   **Degraded**: a scene whose clip failed QA after the allowance was spent, composed with the
    face in the small picture-in-picture (pip) rectangle instead of large.
*   **Workings**: the intermediate files of an episode: captures, card renders, composed scenes,
    QA output, mix intermediates.
*   **Kit**: the publish kit: title, description with chapters, tags and captions.
*   **Panel**: a user-interface element on the Episode page.
*   **rembg**: the local background-removal tool that produces the presenter cut-out.
*   **whisper**: the local speech-to-text tool (`whisper.cpp`) already used for take transcripts.
*   **Tailnet**: the Tailscale private network the API listens on.

### Shape of the system

No new process is added. The same three processes (API, worker, browser) gain one entity, the
episode, and the worker gains the handlers in the diagram below. The agent bus and MCP server
expose the episode the way they expose clips and recordings today.

```text
 writer (Dan or agent)                                    Dan (phone or Mac, over the tailnet)
   │ POST /api/episodes {script}                           │ approve script · approve budget · publish
   ▼                                                       ▼
 API ──► validator ──► episode record (SQLite) ◄──────── Episode page / MCP episode_status
   │                        ▲        │
   │ enqueue episode_advance│        │ read by every handler; stage data written only by the planner
   ▼                        │        ▼
 worker: episode_advance (planner) ── derives the next step from the record + files on disk
   ├─ heygen_clip ×N (exists; + take, claim)   → assets/avatar/clips/<key>.mp4 (+ .cutout.webm)
   ├─ scene_qa ×N                              → episodes/<id>/qa/<scene>.json, .words.json, .jpg
   ├─ site_capture ×K, card_render ×K          → episodes/<id>/cards/<card>.mp4 + cues.json
   ├─ scene_compose ×N                         → episodes/<id>/scenes/<scene>.mp4
   ├─ episode_assemble                         → concat + intro + music + SFX → episodes/<id>/final.mp4
   ├─ episode_publish_kit                      → episodes/<id>/kit.json, final.srt
   ├─ episode_register                         → recordings/rec_<date>-ep.mp4 (moved) + .srt + .episode.json
   ├─ youtube_upload (exists)                  → video id, private
   └─ episode_purge (after public)             → removes workings, keeps final, script, record
 Dan: POST /api/episodes/{id}/publish ──► YouTube videos.update (public now, or scheduled)
```

Every box is an idempotent job keyed by what it produces; a crashed or repeated job finds its
output and returns. Handlers report by writing files; the planner reads the record and the files,
never a job's result row.

### Data flow for one scene

```text
scene s12 (voice, plan) ──clip key (text, look, voice, motion, take)──► heygen_clip ──► clip + cut-out
        │                                                                     │
        │                                                      scene_qa ◄─────┘  → ok | LOOK | FAIL
        │                                                         │ FAIL & allowance left → take+1 → heygen_clip
        │                                                         │ FAIL & allowance spent → degraded
        └─ plan + card slice (if kind=card) ─► scene_compose (guard) ─► scenes/s12.mp4 (25 fps, clip audio)
                                                                           │
                                 episode_assemble: concat + intro + music + SFX(cues.json) ─► final.mp4
```

### The episode record

One episode is one row in a new `episodes` table whose `record_json` column holds the whole
record, read and written under a write lock, as `edl_versions` stores EDL (edit decision list)
JSON today. The episode is also a `projects` row, so `jobs.project_id` correlates every job to its
episode with no schema change to `jobs`. The episode's files live under
`data_dir/episodes/<episode_id>/`; `episode.json` there is an export written at purge for the
archive, not a live store. Migration 4 adds two tables: `episodes` (id, project_id, status, title,
created_at, updated_at, record_json) and `heygen_ledger` (see "The paid step").

The record:

```text
record
  id, title, status, created_at, updated_at
  script: { version, hash, title, look, voice_id, motion, scenes: [ scene ] }   # the approved contract
  budget: { approved_at, confirm_token, clips, seconds, usd, allowance: {attempts, usd},
            spent: {renders, seconds, usd} }                                     # spent is a projection of the ledger
  reference: { face: [x,y,w,h], lip_ratio }           # QA medians from the first full pass
  scenes_state: { <scene_id>: { clip_key, take, job_id, video_id, duration_s,
                                qa: ok|LOOK|FAIL|degraded, qa_issues: [], composed_hash, card_id } }
  cards: { <card_id>: { scenes: [ids], template, urlkey, durations_hash, cues } }
  outputs: { final_mp4, final_srt, kit, recording_id, youtube_video_id, publish_at }
  log: [ { at, stage, scene?, message } ]              # plain-words events for the status page
```

Writers of the record: the API writes `script`, `budget` and the gate states; the planner is the
only writer of `scenes_state`, `cards`, `outputs`, `log` and the working states. Both hold the
`episodes` row lock while writing.

States are the human gates and the terminal states only: `draft` → `script_approved` →
`budget_approved` → `in_progress` → `uploaded_private` → (`scheduled`) → `published` → `purged`,
plus `needs_dan` and `cancelled`. Progress inside `in_progress` is shown from counts in
`scenes_state` ("rendering 12/36, QA 8/36, composing 3/36, uploading"), not stored. Entry rules:

*   `needs_dan`: any stage job ends in `error` (network, tool crash, disk full, HeyGen cap); the
    error is written to `log`; `POST /{id}/advance` after Dan acts returns the episode to
    `in_progress`.
*   `cancelled`: `POST /{id}/cancel` from any state before `uploaded_private`; releases the
    unsubmitted part of the reservation (see "The paid step") and allows purge.
*   `uploaded_private`: set by the planner when it sees the upload's result file (the recording's
    upload state file names the video id).
*   `scheduled` and `published`: set by the publish click and the status check (see "Publish").
*   `purged`: set by `episode_purge`.

### The script contract and validator

A script is posted as JSON and stored inside the record. Shape:

```text
script: { title, version, look?, voice_id?, motion?,        # look/voice/motion default from the saved HeyGen config
          scenes: [ scene ] }
scene:  { id: "s12", text: "...on screen...", voice: "...as HeyGen reads it...",
          kind: "avatar" | "card", site?: "https://...",
          question?: <int>,            # this scene asks question N
          reveal?: true,               # the closing scene that reveals the AI avatar
          sources?: [ { claim: "fourteen thousand subscribers", source: "Dan, 2026-11-02" } ],
          plan?: { title?, lower?, lowers?, chips?, chip_at?, zoom?, zoom_path?, frame?,
                   glitch?, endcard?, whoosh_at?, card_template?: "generic" } }
```

`voice` is what HeyGen reads (names written for the voice); `text` is shown on screen and used
for captions when `voice` is empty. `plan` carries the per-scene creative data that
`episode-01-v2.plan.json` held positionally; it is optional and a scene without it still renders
(an avatar scene with `question` gets the default table overlay; a card scene gets the generic
site card). `card_template` accepts `generic` only in v1. A converter imports the Episode 1 v2
files (script JSON, plan JSON, durations) into this shape as the first test fixture.

The validator runs when a script is posted and on every edit, returning `{errors, warnings}` per
scene id:

| Check | Level | Rule source |
| --- | --- | --- |
| estimated length outside 3 to 13 s | warning | DESIGN rule 1 |
| no scene with `question`, or no scene with `reveal` | warning | DESIGN rule 5 |
| a number, price, date, percentage or ranking word with no `sources` entry | warning | brief F.18 |
| `voice` contains a name spelled the on-screen way (voice-names table) | warning | DESIGN rule 6 |
| consecutive avatar scenes with no `plan` element whose estimated lengths sum to more than 8 s | warning | DESIGN rule 4 |
| `kind: card` without `site` | error | cards need a page |
| duplicate scene id | error | contract |
| both `voice` and `text` empty | error | contract |

Warnings never block approval. Errors do. The table of names for the voice lives in
`assets/brand/voice-names.json` (one entry per product: on-screen spelling, voice spelling).

### The planner: `episode_advance`

One handler, re-queueable at any time, that reads the record and the filesystem and decides the
next step. It never calls HeyGen, ffmpeg or a browser itself; it enqueues the handler that does
and returns. It is enqueued by the API after each approval, by every stage handler when it
finishes, and by `POST /api/episodes/{id}/advance` for a manual resume. Rules, in order, all run
under the `episodes` row lock:

1. `budget_approved` or `in_progress`, and some scene has no clip for its current (key, take)
   **and** no queued or running `heygen_clip` job recorded in `scenes_state[id].job_id`: enqueue
   one `heygen_clip` per such scene (payload as today plus `take`, `episode_id`, and
   `max_attempts = 1`) and record each job id in the same transaction; set `in_progress`.
2. All clips present and some scene has no QA result for its current clip: enqueue `scene_qa` per
   scene. After the first full pass, store the cohort medians in `reference`.
3. A clip job reported `failed` (as a result, see "The paid step") or a scene is `FAIL`: if the
   allowance has attempts and USD left, increment `take`, charge the allowance and go to rule 1;
   otherwise mark the scene `degraded` and log it. A `LOOK` result is recorded and the scene
   continues.
4. All scenes `ok`, `LOOK` or `degraded`: enqueue `site_capture` for each card whose capture is
   missing, then `card_render` for each card whose `durations_hash` changed, then `scene_compose`
   per scene whose inputs hash changed.
5. All composites present: enqueue `episode_assemble`, then `episode_publish_kit`, then
   `episode_register`, then `youtube_upload` (private; title and description from the kit). When
   the upload's state file names a video id, set `uploaded_private`.
6. `published`, on the first advance after it (page open, status call or the Purge button):
   enqueue `episode_purge`. A passed `publish_at` with the video still private never advances this
   rule.

No handler waits for another: each stage handler enqueues `episode_advance` when it finishes, the
planner counts what exists, and only the last handler of a stage finds everything present. Two
planners running at once are safe because rule 1 records job ids inside the lock and every
handler is idempotent.

### The paid step

The confirm screen is served by `GET /api/episodes/{id}/estimate`, which uses the shared estimate
logic in `core/heygen.py` (the same numbers the editor's HeyGen panel shows) and adds: the wallet
balance after this render, the month's total after this render, the allowance, and the ceiling.
The response carries a one-time `confirm_token`, stored on the record and valid for ten minutes.

"Month after" is computed from a ledger, not from episode creation dates. The `heygen_ledger`
table holds three kinds of row: a **reservation** when a budget is approved (the estimate plus the
allowance, dated when approved); a **charge** when a render completes or fails (the billed seconds
and USD, dated when the render finished, which may fall in a later month than the approval); a
**release** when unconsumed reserved money is given back. The month's total is the sum of this
calendar month's charges plus the unconsumed part of every open reservation, whatever month the
episode was created in. Until Stage 0 shows otherwise, a render that HeyGen reports `failed` is
charged as if billed, so the ceiling errs on the safe side.

`POST /api/episodes/{id}/approve-budget` requires the `confirm_token` and an allowed `Origin`
header, which the Episode page sends and the MCP client does not. It runs under the row lock: it
recomputes the month's total, refuses with 409 when the total plus this episode's estimate and
allowance would pass the monthly ceiling, and otherwise writes the reservation row and
`budget.approved_at` in the same transaction, so two approvals cannot both pass against the same
remaining balance. An agent with raw HTTP access could still scrape the token from the estimate
response; the monthly ceiling is the backstop, and the ledger makes every spend visible.

Each completed or failed `heygen_clip` writes a charge row and consumes its seconds from the
episode's reservation. The planner releases what is left of a reservation when the episode reaches
`uploaded_private`, or when it degrades its last failing scene. On `cancelled`, only the
reservation for clips never submitted (no `video_id`) is released; clips already submitted stay
reserved until their render completes or fails and a charge row is written, which the planner does
on its next pass even for a cancelled episode, because cancelling the local job does not stop
HeyGen's render or its bill.

A `heygen_clip` carrying an `episode_id` never raises on a HeyGen `failed`: it returns
`{status: "failed", reason}` as its normal result, writes the charge row and enqueues the
planner, so rule 3 applies the allowance. It also writes a claim (its job id) to the clip's state
file before calling HeyGen and exits as a no-op if another job's claim is present, so two jobs for
one key cannot both pay. Episode clip jobs are enqueued with one attempt, so a worker-level error
also returns to the planner instead of re-rendering on its own.

The allowance is episode-wide and counted in re-render attempts and USD; both caps must hold.
Defaults are settings: `episode_rerender_attempts` (default 4), `episode_rerender_usd` (default
1.50) and `heygen_month_ceiling_usd` (default 400). The ceiling default is deliberately tight; the
brief estimated 400 to 550 USD a month at one episode a day, and Dan sets the real ceiling.

The clip key gains the take number; take 0 reproduces today's key so every existing clip keeps
its name. Rejected takes stay in place, marked in `scenes_state`, and are vaulted like any clip.

### QA: `scene_qa`

`scene_qa` runs the checks of `tools/compose/qa_avatar.py` on one clip (face present and placed,
glitch, frozen while speaking, lip motion against the voice), ported into the server package. It
compares the face box and lip ratio against `reference` when present (the medians of the first
full pass, so a single re-rendered clip still has a cohort), writes `qa/<scene>.json` and a
contact-sheet image, and returns `ok`, `LOOK` or `FAIL` with the issues. The status names are
those of `qa_avatar.py`: `FAIL` for face, glitch or frozen faults, `LOOK` for lip warnings.

Each clip is also transcribed locally with whisper and the result kept as
`qa/<scene>.words.json`; the word timings are the reference clock for captions and card beats.
Transcript and `voice` are both normalised through the voice-names table and a number-to-words
pass before the word error rate is computed. A rate above 25 % is `LOOK`; it becomes `FAIL` only
when a re-rendered take's transcript also differs from the first take's by more than 25 %, since
two matching transcripts mean the words are right and the recogniser is wrong. The lip-motion
heuristic is a quality check; it is not the lip-sync guard, which is a layout rule (see
"Compositor").

### Cards: `site_capture`, `card_render`

A card covers a run of consecutive `kind: card` scenes with the same `site`. `site_capture` runs
the Playwright Chromium already used by `render/preview.py` with a fresh profile and no cookies,
takes a full-page screenshot and the bounding boxes of the first heading and the main image, and
stores them under `episodes/<id>/caps/<urlkey>.*`. `urlkey` is the host followed by a short hash
of the whole normalised URL (host, path and query, lower-cased, trailing slash dropped), so two
pages on one site never share a file, and cards reference captures by the same key.

Allow-list entries in `Settings.capture_allowlist` are `{host, mode: "auto" | "manual"}` matched on
the exact host. `site_capture` refuses any URL whose host is not listed, blocks requests to
non-allow-listed hosts and private address ranges while the page loads, aborts on a cross-host
redirect, and never logs in. A `manual` site is captured once by hand into
`data_dir/sites/<urlkey>/` (not under `assets/`, which is served at the web root) and reused.

`card_render` builds a HyperFrames composition from the capture and the `generic` template:
address bar, slow scroll, one zoom to the hero, one callout taken from the scenes' `text`, with
beats at the scene boundaries measured from the clips. Every script-derived string is HTML-escaped
before it enters the template. The builder emits `cues.json` (tab changes, counter landings)
beside the MP4; the mixer reads that file. Rendering runs `npx hyperframes render` as a subprocess
from the HyperFrames workspace, with the browser path from `Settings.hyperframes_browser`.
Richer templates (`feature-ring`, `compare`, `counter`) and beats placed on words from the
whisper timings follow once the generic card has shipped a few episodes (Future Improvements).

### Compositor: `scene_compose`, `episode_assemble`

The compositing of `tools/compose/render.py` moves into the server package as functions taking
`Settings` and a scene, with every path from settings and fonts from `assets/brand/fonts/`.
`scene_compose` renders one scene's frames from its clip (the clip's timing is not changed), its
cut-out mask (`<key>.cutout.webm`, already produced by `heygen_clip`) and its plan, and writes
`scenes/<scene>.mp4` at 25 fps with the clip's audio, via a temporary file and rename, recording
an inputs hash (text hash, clip checksum, card checksum, plan) so "up to date" means inputs
unchanged.

An avatar scene's frame is the plate, the presenter cut-out seated at the desk, and the table
overlays from its plan. A card scene's frame is the card video slice for that scene (offset by
the scene's start inside the card run, measured from clip durations; a card shorter than its run
holds its last frame, a longer one is cut) under the presenter in the small picture-in-picture
rectangle, plus the scene's overlays. The lip-sync guard runs for every scene before compositing:
the cue is `avatar` for avatar scenes, `content` for card scenes and `pip` for degraded scenes,
and the voice is always the clip's own, so the guard leaves these unchanged; it still runs so the
shared guard fixtures exercise the compositor and the editor's guard alike.

`episode_assemble` concatenates the scene files (identical encode settings, frame counts checked
against the measured durations), puts the cached intro in front, and runs the mix from the
levels table below, with SFX at the cues from each card's `cues.json` and from the plan
(`question`, `whoosh_at`, `glitch`, `endcard`). One frame rate, 25 fps, for clips, cards, intro
and final.

| Track | Level |
| --- | --- |
| intro | -18 LUFS (loudness units relative to full scale) |
| voice | -16 LUFS |
| music bed (looped under everything from the end of the intro) | -36 LUFS |
| SFX | -26 LUFS |
| final | `loudnorm` to -14 LUFS, true peak -1.5 dB, loudness range 11 |

The bed level is the one Episode 1 v2 shipped with; `docs/DESIGN.md` rule 3 said about -28 LUFS
and is corrected to -36.

### Publish kit, registration, upload

`episode_publish_kit` writes `kit.json` (title from the script title, description with chapters
at the `question` scenes' start times, tags) and `final.srt`. Captions come from the script's
on-screen `text` (or `voice`), not from the transcript, because DESIGN rule 6 wants on-screen
spellings such as "Zmarty" where the voice says "Smarty"; each caption's start and end come from
the whisper word timings of its scene offset by the scene's start in the final video, falling
back to the measured duration split by character count when a transcript is missing.

`episode_register` moves `final.mp4` to `recordings/rec_<YYYYmmdd-HHMMSS>-ep.mp4`, writes
`rec_...-ep.srt` and `rec_...-ep.episode.json` naming the episode, and records the path in
`outputs.final_mp4`. `finish_recording` is not run: the file is already H.264, AAC, normalised.
`GET /api/recordings` today discovers takes only through their `rec_*.source.*` upload files,
which a registered episode does not have, so the listing is extended to include
`rec_*.episode.json` entries; a contract test asserts a registered episode appears in the listing
and in the YouTube take picker. The vault, `youtube_upload` and the MCP `youtube_upload` tool work
unchanged; the upload is always private.

### Publish

`POST /api/episodes/{id}/publish {publish_at?}` is Dan's third click, available from
`uploaded_private`. It calls YouTube's video update (`PUT /youtube/v3/videos?part=status`) through
a new `set_status` in the YouTube client: with no `publish_at`, `privacyStatus: public`, and the
episode is set to `published` from the response; with `publish_at`, `privacyStatus: private` plus
`publishAt`, and the episode is set to `scheduled` with the time shown on the status page.

There is no hourly poll; the worker has no scheduler and the Non-Goals rule one out. Instead,
`GET /api/episodes/{id}` (and therefore the Episode page and MCP `episode_status`) calls YouTube's
video status for a `scheduled` episode and sets `published` on an observed `public`. A passed
`publish_at` with the video still private does not count: the page shows "scheduled release did
not happen" and keeps checking on each open, so a release cancelled in YouTube Studio never
triggers a purge.

After `uploaded_private`, `PUT /{id}/script` is refused with 409: YouTube cannot replace a video
file, and a second upload is a second video. Re-voicing an uploaded episode is a new episode
created from the old script (`POST /api/episodes?from=<id>`), which reuses every unchanged clip
through the clip key; the superseded private video is left private for Dan to delete.

`episode_purge` runs only from `published` (or `cancelled`): it removes `caps/`, `cards/`,
`scenes/`, `qa/` and the mix intermediates, writes `episode.json` as the archive export, keeps
`kit.json`, `final.srt` and the registered recording, and logs the freed bytes.

### Status, observability, agents

The API: `POST /api/episodes` (validate; 503 with the missing names when preflight fails; 422 on
errors), `POST /api/episodes?from=<id>`, `GET /api/episodes`, `GET /{id}`, `PUT /{id}/script`,
`POST /{id}/approve-script`, `GET /{id}/estimate`, `POST /{id}/approve-budget`,
`POST /{id}/publish`, `POST /{id}/cancel`, `POST /{id}/advance`, `POST /{id}/purge`,
`GET /{id}/qa/{scene}.jpg`.

The editor gets an Episode page (`?episode=<id>`, usable at phone width) with the scenes,
warnings, the three buttons, and a "Needs you" panel that shows the last log line and the one
action that unblocks it. The MCP server gains `episode_create`, `episode_list`, `episode_status`
and `episode_estimate`, none of which can approve, publish or purge. Every job the planner
enqueues carries `project_id` and `payload.episode_id`; the worker log line includes it.
`heygen_ledger` is the cost ledger; `budget.spent` is a cached projection of it. `/api/health`
reports the toolchain (ffmpeg, whisper, rembg, OpenCV, Playwright Chromium, HyperFrames, fonts,
intro, plate, music manifest). A Library group for episodes is deferred (Future Improvements).

### Assets and toolchain

`assets/brand/` gains `fonts/` (Inter OTF, the four woff2 web fonts the intro uses), `intro/`
(one rendered `intro.mp4` at 25 fps; the intro's kicker, title and tagline are channel constants,
so one file serves every episode and the episode title appears on the opening table overlay),
`music/`, `sfx/`, `voice-names.json` and `manifest.json` (name, file, sha256, licence note).
`assets/models/` holds the OpenCV Haar cascade face detector. The HyperFrames workspace
(`package.json`, templates) lives under `data_dir/cards/` so its `node_modules` is never served;
the launcher runs `npm ci` there. `pyproject.toml` gains an `episode` extra (OpenCV, Pillow,
NumPy, SciPy, rembg, Playwright); the Mac launcher installs it and runs
`playwright install chromium` once per revision. Settings: `episodes_dir`, `capture_allowlist`,
`hyperframes_browser`, `episode_rerender_attempts`, `episode_rerender_usd`,
`heygen_month_ceiling_usd`. Frame rate (25) and HyperFrames worker count are constants.

### The smallest version

The first episode that removes every manual step is Stage 1: a finished script posted to the API
with error-level validation only, approve-script, one estimate and approve-budget with the
ledger, `heygen_clip` with the take and the claim, `scene_compose` on the plate with the guard,
concatenation, the cached intro and the music bed, the kit with chapters, registration, private
upload, and the publish click, with a minimal Episode page (the scene list and three buttons).
Its first episodes are ones without site mentions, since still site cards are forbidden by the
production rules. QA, the allowance, the degrade path and the full status page are Stage 2; cards
are Stage 3.

## Alternatives Considered

Taken from the brief's "Alternatives Weighed", which recorded every option the six reviewers
rejected and why. After each, the option chosen in this design is stated.

### Alternative A: Write and fact-check the script inside StreamStudio

*   **Pros**: One tool for the whole day; the validator and the writer share a schema.
*   **Cons**: Ties the server to a model API that would need the same click-and-cost gate as
    HeyGen; duplicates the writing agents and skills Dan already runs; "fact-checked" cannot be
    implemented as truth verification, only as "a source is present".
*   **Reason for Rejection**: Rejected by all six reviews for the cons above. Chosen instead: a
    script contract plus validator; writers deliver through `POST /api/episodes` or MCP.

### Alternative B: Port `tools/compose` as it stands, one job per script

*   **Pros**: Smallest change on paper; the scripts produced one real episode.
*   **Cons**: Built for one long HeyGen take; Linux-only paths; work executed at import; no tests;
    `masks.py` duplicates `avatar/cutout.py`; `mix.py` reads cues by regex over HTML.
*   **Reason for Rejection**: Cannot run on the Mac Studio and cannot be tested. Chosen instead:
    the compositing, QA and mix functions are rewritten under the server package with injected
    paths; `ffmpeg` and `npx hyperframes render` stay subprocesses.

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
    reuses sets, cues, table objects and media cards.
*   **Cons**: Real-time capture is not frame-exact and drops frames non-deterministically; the
    25 versus 30 fps question is open; the table-overlay and zoom-path grammar of Episode 1 exists
    only in `render.py`; `preview.py` is a script, not a job.
*   **Reason for Rejection**: It has not yet produced an episode, and v1 does not accept lower
    output quality for a simpler compositor. Recorded as the long-term direction: after 10
    episodes, a side-by-side of the ported compositor and a frame-by-frame Playwright render of the
    stage decides whether the stage becomes the only renderer.

### Alternative E: HyperFrames for the whole episode

*   **Pros**: Intro, cards, chips and framing in one composition sharing CSS with the stage.
*   **Cons**: Long renders; the avatar cut-out would have to be handled inside HTML video
    elements; untested at episode length.
*   **Reason for Rejection**: Too large a change for v1; noted as a way to share CSS later.

### Alternative F: Automatic re-render on QA fail with no click

*   **Pros**: No overnight stall.
*   **Cons**: Violates the rule that paid APIs never run without an explicit action and a shown
    cost; the worker already retries a failed HeyGen render as a new paid one.
*   **Reason for Rejection**: The rule in `CLAUDE.md` that paid APIs run only after an explicit
    action with a shown cost. Chosen instead: a re-render allowance shown and approved on the one
    confirm; retries count against it; beyond it the scene degrades.

### Alternative G: Stall the episode when a scene fails QA after the allowance

*   **Pros**: Nothing ships with a visible fault.
*   **Cons**: The daily cadence depends on Dan's hours; a 02:00 failure costs the day.
*   **Reason for Rejection**: Rejected for the cons above. Chosen instead: degrade the scene to the
    small picture-in-picture rectangle, ship, report in plain words, re-voice later in a new
    episode if Dan wants.

### Alternative H: A daily cron that starts the pipeline

*   **Pros**: Hands-off start.
*   **Cons**: Either spends money unattended or stops at the gate anyway.
*   **Reason for Rejection**: Rejected for the cons above. Replaced by a queue of episodes in
    flight, each waiting for Dan's approval whenever he gives it.

### Alternative I: Agent-written Python storyboards per episode (today's `cards_v2.py`)

*   **Pros**: Full creative control per card.
*   **Cons**: Unverifiable until rendered; page-pixel coordinates break when a site changes; a
    bug stops the mix; nothing produces one from a script.
*   **Reason for Rejection**: Not a daily process. Chosen instead: a generic site card from the
    capture in v1, JSON templates over selector-found rectangles later.

### Alternative J: An agent driving a browser for captures

*   **Pros**: Handles any page, including scrolling and sticky elements.
*   **Cons**: Not idempotent; violates the private-dashboard rule by default; needs credentials.
*   **Reason for Rejection**: Rejected for the cons above. Chosen instead: Playwright full-page
    screenshots under an allow-list with a fresh profile; logged-in sites captured once by hand
    into `data_dir/sites/`.

### Alternative K: Keep the episode in the Director's localStorage and drive it over the agent bus

*   **Pros**: No new storage.
*   **Cons**: `POST /api/agent/do` is 409 without an open editor; localStorage is per browser;
    the worker cannot read it.
*   **Reason for Rejection**: An unattended pipeline cannot depend on an open tab.

### Alternative L: A job dependency (DAG) layer in the worker

*   **Pros**: Explicit ordering.
*   **Cons**: New claim rules, new schema on `jobs`, more code than the feature needs.
*   **Reason for Rejection**: Rejected for the cons above. Chosen instead: one re-queueable
    planner deriving the next step from the episode record and the files on disk; handlers stay
    idempotent.

### Alternative M: Store the plan as an EDL in `edl_versions`

*   **Pros**: Reuses versioning and optimistic concurrency.
*   **Cons**: The EDL holds cuts on tracks, not chips, lowers, zoom paths or sound cues.
*   **Reason for Rejection**: Rejected for the con above. The `projects` row and
    `jobs.project_id` are reused for correlation; the record lives in `episodes.record_json`; an
    EDL may be derived for the editor.

### Alternative N: Intro, music and SFX as per-episode render steps

*   **Pros**: Always current.
*   **Cons**: They change with branding, not episodes; the intro needs fonts copied by hand.
*   **Reason for Rejection**: Rejected for the cons above. Rendered once and kept under
    `assets/brand/`; the intro text is a channel constant.

### Alternative O: External fact-checking APIs

*   **Pros**: Independent verification.
*   **Cons**: Paid or rate-limited; Episode 1's claims are mostly Dan's own business facts.
*   **Reason for Rejection**: Rejected for the cons above. The validator checks that a source or
    softened wording is present.

### Alternative P: Word timings from HeyGen captions, from text proportion, or from measured clip durations only

*   **Pros**: HeyGen captions are exact; text proportion needs no tool; measured durations alone
    need no transcript.
*   **Cons**: HeyGen captions require a manual download; proportion (`cards_v2.T`) guesses;
    measured durations time scene boundaries but not words inside a scene.
*   **Reason for Rejection**: Whisper is local, free and already a dependency, and the same pass
    powers the wrong-words QA check, so word timings cost nothing extra. Dan confirmed the brief's
    choice during reconciliation: whisper word timings are the reference for captions (and for
    card beats once richer templates ship), with measured durations as the fallback.

### Alternative Q: Make the video public only in YouTube Studio

*   **Pros**: No new code.
*   **Cons**: Contradicts "no step outside the app" and ties the daily cadence to Dan's hours.
*   **Reason for Rejection**: Rejected for the cons above. Publish is a third in-app click that
    updates the video's status on YouTube, with `publishAt` for a scheduled release.

### Alternative R: A new `episode` artifact kind for the final MP4 (and a shared deliverable lookup)

*   **Pros**: A separate kind; episodes are never listed as takes.
*   **Cons**: With a new kind, four files and the MCP tool must learn a second location. With a
    shared lookup, every consumer of recordings must be refactored.
*   **Reason for Rejection**: Dan chose to register the final MP4 as a take
    (`recordings/rec_<date>-ep.mp4` with an episode sidecar) so upload, vault, library and MCP
    work unchanged, with the recordings listing extended to see the sidecar.

### Alternative S: A free local voice for the card scenes

*   **Pros**: Cuts HeyGen spend by roughly 45 % (the card-scene share of Episode 1 v2's seconds);
    the guard already keeps the face small in those scenes.
*   **Cons**: Voice continuity between HeyGen's cloned voice and a local one.
*   **Reason for Rejection**: Not adopted; recorded as the only lever that lowers the minimum
    monthly HeyGen cost, for Dan to revisit.

--------------------------------------------------------------------------------

## Risks and mitigations

| Failure mode | Detection | Episode state | Status page says | Recovery |
| --- | --- | --- | --- | --- |
| HeyGen render `failed` | clip job result | `in_progress` | "Scene N: HeyGen failed (reason); re-rendering (allowance 3 left)" | planner rule 3 (allowance or degrade) |
| HeyGen network error, timeout or concurrent cap | clip job `error` | `needs_dan` | "Scene N: HeyGen unreachable / cap reached; retry when ready" | Advance button re-enqueues; Stage 0 sizes concurrency |
| Failed render is billed by HeyGen | Stage 0 measurement | | | charged in the ledger until shown otherwise |
| Two planners enqueue the same clip | job id recorded under the row lock | | | one `create_video` per (key, take); claim in the state file |
| YouTube upload fails or quota exceeded | upload job `error` | `needs_dan` | "Upload failed: reason" | resumable upload continues from its state file on Advance |
| YouTube OAuth refresh fails | upload or status call `error` | `needs_dan` | "Reconnect YouTube" | Dan reconnects the channel; Advance |
| Disk full | handler `error` on write | `needs_dan` | "Disk full: N GB free; purge published episodes" | Purge button on old episodes; preflight warns under 20 GB |
| Playwright or HyperFrames crash | capture or card job `error` | `needs_dan` | "Capture of <host> failed" | fix the allow-list or capture by hand; Advance |
| Whisper missing or wrong language | preflight; QA result | refused at create / `LOOK` | "whisper not installed" / "transcript unreadable" | install; captions fall back to measured durations |
| Worker killed mid-step (launcher update) | stale heartbeat | `in_progress` | progress counts unchanged | `requeue_stale` re-runs the idempotent step; temp-plus-rename leaves no half files |
| Cut-out silently missing (`rembg` not installed) | preflight; rule 1 treats a clip without `.cutout.webm` as absent | refused at create | "rembg not installed" | install the `episode` extra |
| Capture refused by the allow-list | capture job result | `needs_dan` | "Site X is not allow-listed; add it or capture by hand" | edit settings; Advance |
| Monthly ceiling reached | approve-budget 409 | `script_approved` | "Month at 398 of 400 USD" | Dan raises the ceiling or waits |
| Scheduled release cancelled in YouTube Studio | status check still `private` after `publish_at` | `scheduled` | "scheduled release did not happen" | Publish again; never purged |
| Script text contains HTML or script | templating | | | every script-derived string is escaped; test with `<script>` |
| Allow-listed host redirects to a private address | capture request blocking | `needs_dan` | "Capture of <host> blocked a redirect" | the page is captured by hand or dropped |

--------------------------------------------------------------------------------

## Non-Functional Requirements

*   **Security and privacy.** The episode API sits behind the existing network guard (loopback
    and tailnet only). Capture jobs run Playwright with a fresh profile, refuse any URL outside the
    allow-list, block requests to non-allow-listed hosts and private ranges, abort on cross-host
    redirects, and never hold cookies or credentials. Hand-made captures live under `data_dir`,
    not under the served `assets/`. The budget approval needs a one-time token from the estimate
    response plus an allowed `Origin`, and is recorded on the episode so the worker checks a
    server-side record; the monthly ceiling is the backstop against a client that scrapes the
    token. Every script-derived string is HTML-escaped before it enters a HyperFrames template.
    HeyGen, YouTube and vault secrets are untouched (0600, masked).
*   **Cost.** One confirm per episode; retries and QA re-renders charge a visible allowance; a
    monthly ceiling refuses approval; reservations are atomic; cancelled episodes keep submitted
    work reserved until it is charged. Every paid render writes a ledger row. No MCP tool approves.
*   **Performance.** 36 HeyGen clips at `worker_concurrency = 2` run at most two at a time,
    because each `heygen_clip` blocks while polling HeyGen; Stage 0 measures HeyGen latency and the
    account's concurrent limit, and `worker_concurrency` is raised to the measured safe value for
    the Mac Studio. Scene composites are independent jobs; whether they gain from threads (Pillow
    and NumPy share one interpreter lock) is measured in Stage 1. `episode_assemble` is a single
    ffmpeg pass. Disk per episode is measured in Stage 0; workings are purged after publish.
*   **Rollout and rollback.** Existing surfaces touched, each additive and reverted by reverting
    the commit with no data migration: migration 4 (two new tables); the clip key (take defaults to
    0, so every existing clip keeps its name); `heygen_clip` (new behaviour only when an
    `episode_id` is present); `GET /api/recordings` (additional entries); `youtube_upload` (an
    optional field); the YouTube client (a new `set_status` and `video_status`); the editor's
    HeyGen panel (reads the USD rate from the estimate instead of a local constant). The Script
    panel, Program window, stage and recordings behave as before. Episode 1 v2 is imported as a
    test fixture, not migrated in place.
*   **Testability.** Every handler runs under `make test` with the fake HeyGen and YouTube
    transports that `test_heygen.py` and `test_youtube.py` already use, a fake HyperFrames
    renderer hook like `handlers.CUTOUT`, and synthetic clips made with ffmpeg's `lavfi`.

--------------------------------------------------------------------------------

## Additional Resources

*   `CLAUDE.md`, `PLAN.md`, `docs/DESIGN.md` ("Episode production rules", "Lip-sync guard",
    "HeyGen rendering"), `docs/AGENTS.md`, `docs/AGENT_GUIDE.md`.
*   The per-directory contract READMEs under `server/src/streamstudio/` and `web/src/`.
*   `tools/compose/README.md`, `tools/compose/motion/README.md`, `tools/compose/motion/intro/README.md`.
*   Episode 1 v2: `docs/scripts/episode-01-v2.{md,json}`, `tools/compose/episode-01-v2.plan.json`,
    `tools/compose/episode-01-v2.durations.json`.
*   `docs/egm/daily-episode-factory/hypothesis.md`, `concepts_brief.md` (six Goldfish reviews),
    `zoom_out_report.md`, `comprehension_report.md`, `critic_report.md`, `goldfish_review_report.md`.

## Future Improvements

*   **One compositor.** After 10 episodes, a measured side-by-side of the ported compositor and a
    frame-by-frame Playwright render of the browser stage decides whether the stage becomes the
    only renderer (Alternative D).
*   **Local voice for card scenes.** Alternative S.
*   **Non-blocking HeyGen polling.** One "submit all, then poll all" job per episode would free
    worker slots for captures and cards while HeyGen renders.
*   **Richer card templates and word-placed beats** (`feature-ring`, `compare`, `counter`; beats
    on whisper word timings), and agent-authored storyboards through an MCP `episode_plan` action,
    once the generic card has shipped a few episodes.
*   **Re-voice an uploaded episode in place**, replacing the private video, once YouTube's rules
    for that are settled; v1 creates a new episode instead.
*   **Rename the editor's saved stage layouts to "sets"** in the Library tab, `/api/scenes`, the
    `scene:` artifact kind and the agent actions, as its own small change with aliases.
*   **A Library group for episodes** with an `episode.status` action, if agents or Dan need
    episodes in the artifact library beside the Episode page and MCP tools.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

Five stages (0 to 4), each ending runnable and tested. Stage 1 is the smallest version that
produces a private upload with no manual step. Files are listed once, under the stage that first
touches them; later stages extend them. Paths are relative to the repository root.

### Stage 0: measure and install the toolchain

#### 1. `server/pyproject.toml` (Modify)

*   **Type / Scope**: Python packaging.
*   **Proposed Changes**: Add an `episode` extra: `opencv-python-headless`, `pillow`, `numpy`,
    `scipy`, `rembg`, `playwright`. Keep `media` as a subset. Regenerate `uv.lock`.

#### 2. `server/uv.lock` (Modify)

*   **Type / Scope**: Lockfile.
*   **Proposed Changes**: Locked by `uv sync --extra episode`.

#### 3. `Makefile` (Modify)

*   **Type / Scope**: Developer entry points.
*   **Proposed Changes**: `setup-episode` target (`uv sync -p 3.12 --extra episode`, then
    `.venv/bin/playwright install chromium`, then `npm ci` in the HyperFrames workspace under
    `data_dir/cards/`); `test` unchanged.

#### 4. `mac/StreamStudio.app/Contents/MacOS/StreamStudio` (Modify)

*   **Type / Scope**: Bash launcher.
*   **Proposed Changes**: Step 2 installs `-e ".[episode]"` and runs `playwright install
    chromium` once per revision; a new step runs `npm ci` in the HyperFrames workspace once per
    revision. Failure messages name the missing tool.

#### 5. `server/src/streamstudio/core/config.py` (Modify)

*   **Type / Scope**: Settings.
*   **Proposed Changes**: Add `episodes_dir` property (`data_dir / "episodes"`), `cards_dir`
    property (`data_dir / "cards"`, the HyperFrames workspace), `sites_dir` property
    (`data_dir / "sites"`), `capture_allowlist: list[CaptureSite]` (`host`, `mode`),
    `hyperframes_browser: Path | None`, `episode_rerender_attempts: int = 4`,
    `episode_rerender_usd: float = 1.5`, `heygen_month_ceiling_usd: float = 400`. `ensure_dirs`
    creates the three directories. Frame rate 25 and the HyperFrames worker count are module
    constants in the episode package, not settings.

#### 6. `assets/brand/fonts/`, `assets/brand/music/`, `assets/brand/sfx/`, `assets/brand/intro/intro.mp4`, `assets/brand/voice-names.json`, `assets/brand/manifest.json` (Create)

*   **Type / Scope**: Vendored assets.
*   **Proposed Changes**: Inter OTF and the four intro woff2 files; the owned music and SFX
    clips that `mix.py` and the intro used; the rendered intro MP4 at 25 fps with the channel's
    constant kicker, title and tagline; the names-for-voice table; a manifest with name, file,
    sha256 and licence note for every entry. Needed by Stage 1's assemble step.

#### 7. `assets/models/haarcascade_frontalface_default.xml` (Move from `tools/compose/models/`)

*   **Type / Scope**: QA model file.
*   **Proposed Changes**: Served from `assets_dir` so the QA module loads it from `Settings`
    (used from Stage 2).

#### 8. `tools/brand/make_intro.py` (Move from `tools/compose/motion/intro/make_intro.py`)

*   **Type / Scope**: One-off brand generator.
*   **Proposed Changes**: Reads fonts from `assets/brand/fonts/`, writes `assets/brand/intro/`
    at 25 fps with the constant text; documented as "run when the branding changes", not part of
    the pipeline.

#### 9. `server/src/streamstudio/episode/__init__.py`, `server/src/streamstudio/episode/preflight.py` (Create)

*   **Type / Scope**: New package and preflight.
*   **Proposed Changes**: The package exposes `contract`, `validate`, `record`, `ledger`,
    `planner`, `qa`, `compose`, `mix`, `cards`, `capture`, `hyperframes`, `kit`, `publish`,
    `preflight`. `preflight.check(s) -> {ok, missing}` tests each tool, font, asset and the
    HyperFrames workspace.

#### 10. `server/src/streamstudio/api/routes/system.py` (Modify)

*   **Type / Scope**: Health route.
*   **Proposed Changes**: `tools` gains `opencv`, `rembg`, `playwright_chromium`, `hyperframes`,
    `fonts`, `intro`, `plate`, `music_manifest`, each a version or path or `None`, plus
    `preflight_ok` and `missing` from `preflight.check`.

#### 11. `docs/egm/daily-episode-factory/stage0-measurements.md` (Create)

*   **Type / Scope**: Measurement record.
*   **Proposed Changes**: On the Mac Studio: per-scene HeyGen latency, concurrent cap, minimum
    billed seconds, whether a `failed` render is billed; rembg per clip; whisper per clip; one
    HyperFrames card render; disk per episode. Compositing is measured in Stage 1 on the ported
    code. Feeds the defaults in file 5 and the Goals' hour figure.

### Stage 1: the thin slice, script to private upload

#### 12. `server/src/streamstudio/core/db.py` (Modify)

*   **Type / Scope**: SQLite migrations.
*   **Proposed Changes**: Migration 4 creates `episodes` (id, project_id, status, title,
    created_at, updated_at, record_json) with an index on `status`, and `heygen_ledger` (id,
    episode_id, kind `reservation | charge | release`, seconds, usd, at) with an index on `at`.

#### 13. `server/src/streamstudio/episode/contract.py` (Create)

*   **Type / Scope**: Pydantic models.
*   **Proposed Changes**: `Scene` (id, text, voice, kind, site, question, reveal, sources,
    plan), `Plan` (title, lower, lowers, chips, chip_at, zoom, zoom_path, frame, glitch,
    endcard, whoosh_at, card_template as `Literal["generic"]`), `Script` (title, version, look,
    voice_id, motion, scenes), `extra="forbid"`; `script_hash(script)`.

#### 14. `server/src/streamstudio/episode/validate.py` (Create)

*   **Type / Scope**: Validator.
*   **Proposed Changes**: `validate(script, s) -> {errors, warnings}` keyed by scene id
    implementing the table in the Technical Plan (Stage 1 ships the error rows and the length
    warning; the other warnings land in Stage 2); duration estimate shared with
    `core/heygen.py:estimate`; names table from `assets/brand/voice-names.json`.

#### 15. `server/src/streamstudio/episode/record.py` (Create)

*   **Type / Scope**: Episode record storage.
*   **Proposed Changes**: `create(conn, s, script) -> Episode` (creates the `projects` row and
    the `episodes` row with `record_json`, and the episode directory); `load(conn, id)`,
    `save(conn, episode)` (inside the caller's `BEGIN IMMEDIATE`), `set_status`, `log(event)`,
    `list(conn)`, `export(s, episode)` (writes `episode.json` at purge); per-scene helpers
    (`scene_key(scene, script, take)` using the script's look, voice and motion,
    `inputs_hash(scene, clip, card)`).

#### 16. `server/src/streamstudio/episode/ledger.py` (Create)

*   **Type / Scope**: Cost ledger.
*   **Proposed Changes**: `month_total(conn, now)` (this month's charges plus open reservations),
    `reserve(conn, episode, seconds, usd)`, `charge(conn, episode, scene, seconds, usd, at)`,
    `release(conn, episode, seconds, usd)`, `release_unsubmitted(conn, episode)`; all called
    inside the caller's transaction.

#### 17. `server/src/streamstudio/core/heygen.py` (Modify)

*   **Type / Scope**: HeyGen client and helpers.
*   **Proposed Changes**: `item_key(..., take: int = 0)` (take 0 reproduces today's key);
    `USD_PER_S = 0.0385` and `WORDS_PER_S = 2.5` moved here; `estimate(items) -> {seconds, usd,
    clips, with_motion}` used by the HeyGen route, the episode API and MCP.

#### 18. `server/src/streamstudio/api/routes/heygen.py` (Modify)

*   **Type / Scope**: HeyGen route.
*   **Proposed Changes**: Use `core.heygen.estimate`; `Item` gains optional `take`; the response
    includes `usd`.

#### 19. `web/src/director/HeygenPanel.tsx` (Modify)

*   **Type / Scope**: Editor panel.
*   **Proposed Changes**: Reads `usd` from the estimate instead of the local `API_USD_PER_S`.

#### 20. `server/src/streamstudio/api/routes/episodes.py` (Create)

*   **Type / Scope**: FastAPI router, prefix `/api/episodes`.
*   **Proposed Changes**: `POST ""` (preflight 503, validate 422, create), `POST "?from=<id>"`,
    `GET ""`, `GET /{id}` (runs the YouTube status check for `scheduled` episodes),
    `PUT /{id}/script` (409 after `uploaded_private`), `POST /{id}/approve-script`,
    `GET /{id}/estimate` (issues `confirm_token`), `POST /{id}/approve-budget` (token and
    `Origin` required; row lock; ceiling 409; reservation), `POST /{id}/publish` (`set_status`;
    `published` or `scheduled`), `POST /{id}/cancel`, `POST /{id}/advance`, `POST /{id}/purge`,
    `GET /{id}/qa/{scene}.jpg` (Stage 2). Ids validated by regex.

#### 21. `server/src/streamstudio/api/main.py` (Modify)

*   **Type / Scope**: App factory.
*   **Proposed Changes**: Import and mount `episodes.router`.

#### 22. `server/src/streamstudio/worker/handlers.py` (Modify)

*   **Type / Scope**: Job handlers.
*   **Proposed Changes**: `heygen_clip` accepts `take` and `episode_id`; with an `episode_id` it
    writes a claim (its job id) to the clip's state file before `create_video` and exits as a no-op
    if another job's claim is present, returns `{status: "failed", reason}` instead of raising on
    HeyGen `failed`, writes the ledger charge, and enqueues `episode_advance`. `store.enqueue`
    gains an optional `max_attempts` stored in the payload and honoured by `run_one`. New handlers
    registered from the episode package (imported at module end so `HANDLERS` sees them). A
    `HYPERFRAMES_RENDER` hook for tests.

#### 23. `server/src/streamstudio/worker/main.py` (Modify)

*   **Type / Scope**: Worker loop.
*   **Proposed Changes**: `run_one` honours a per-job `max_attempts` from the payload when
    present.

#### 24. `server/src/streamstudio/episode/planner.py` (Create)

*   **Type / Scope**: `episode_advance` handler.
*   **Proposed Changes**: The six rules in the Technical Plan under the `episodes` row lock; job
    ids recorded in `scenes_state` before enqueueing; reads the filesystem and the record only;
    reservation release and `release_unsubmitted` on cancel; sets `uploaded_private` from the
    upload state file; purge rule from `published`. Stage 1 ships rules 1, 4 (compose only), 5 and
    6; rules 2 and 3 land in Stage 2.

#### 25. `server/src/streamstudio/episode/compose.py` (Create)

*   **Type / Scope**: `scene_compose` handler and compositing functions.
*   **Proposed Changes**: The compositing of `tools/compose/render.py` (plate, seated cut-out,
    table overlays, zoom, glitch, neon frame, card slice) as functions with `Settings` injected;
    `render/lipsync.py:guard_cue` called per scene with the cue derived from the scene kind and
    the voice literal `"clip"`; degraded scenes in `pip_rect`; `scenes/<scene>.mp4` at 25 fps with
    the clip's audio, temp plus rename, `inputs_hash` recorded. Stage 1 composes avatar scenes on
    the plate; card slices arrive in Stage 3.

#### 26. `server/src/streamstudio/render/lipsync.py` (Modify)

*   **Type / Scope**: Guard.
*   **Proposed Changes**: No behaviour change; docstring names the compositor as a caller and the
    fixture file below.

#### 27. `server/tests/fixtures/lipsync_cases.json` (Create), `server/tests/test_lipsync.py` (Modify), `web/src/director/director.test.ts` (Modify)

*   **Type / Scope**: Shared guard fixtures.
*   **Proposed Changes**: Cases of (cue, clip, voice) to expected cue and small-rectangle
    placement; the Python test runs them through `lipsync.py` and `compose.py`, the vitest test
    through `types.ts:guardCue` and `cueLayouts.ts:guardLayout`, so the three copies cannot drift.

#### 28. `server/src/streamstudio/episode/mix.py` (Create)

*   **Type / Scope**: `episode_assemble` handler.
*   **Proposed Changes**: Concat demuxer over `scenes/*.mp4` with frame-count check; intro from
    `assets/brand/intro/intro.mp4`; music bed and SFX from the manifest; cues from each card's
    `cues.json` and the plan; the levels table as one constant dict; writes `final.mp4` and
    `final.cues.json`. Stage 1 ships intro and bed; SFX cues from cards arrive in Stage 3.

#### 29. `server/src/streamstudio/episode/kit.py` (Create)

*   **Type / Scope**: `episode_publish_kit` and `episode_register` handlers.
*   **Proposed Changes**: `kit.json` (title, description with chapters at `question` scenes,
    tags) and `final.srt` (two lines of 42 characters per caption, timed from each scene's
    `qa/<scene>.words.json` when present, else measured duration split by characters);
    registration moves `final.mp4` to `recordings/rec_<stamp>-ep.mp4`, writes `.srt` and
    `rec_<stamp>-ep.episode.json`, records the path in `outputs.final_mp4`, returns the recording
    id.

#### 30. `server/src/streamstudio/api/routes/recordings.py` (Modify)

*   **Type / Scope**: Recordings listing.
*   **Proposed Changes**: `list_recordings` also lists `rec_*.episode.json` entries (id, `mp4`,
    `mp4_bytes`, `transcript`, `source_bytes: null`, `episode: <id>`), so registered episodes
    appear in the Recordings tab and the YouTube take picker.

#### 31. `server/src/streamstudio/core/youtube.py` (Modify)

*   **Type / Scope**: YouTube client.
*   **Proposed Changes**: `set_status(api, video_id, privacy, publish_at=None)` calling
    `PUT /youtube/v3/videos?part=status`; `video_status(api, video_id) -> {privacy, publish_at}`;
    `clean_meta` validates `publish_at` (RFC 3339, future) when given.

#### 32. `server/src/streamstudio/episode/publish.py` (Create)

*   **Type / Scope**: Publish helpers and `episode_purge` handler.
*   **Proposed Changes**: `publish(conn, s, episode, publish_at)` (called by the route; sets
    `published` or `scheduled`); `refresh_status(conn, s, episode)` (called by `GET /{id}` for
    `scheduled` episodes; sets `published` on an observed `public`, logs "scheduled release did
    not happen" when the time has passed); `episode_purge` removes `caps/`, `cards/`, `scenes/`,
    `qa/` and mix intermediates, writes `episode.json`, keeps `kit.json`, `final.srt` and the
    registered recording, logs bytes freed; runs only from `published` or `cancelled`.

#### 33. `web/src/episode/EpisodePage.tsx`, `web/src/episode/api.ts`, `web/src/episode/README.md` (Create)

*   **Type / Scope**: React view and client.
*   **Proposed Changes**: Reachable at `?episode=<id>`; Stage 1: the scene list with errors,
    Approve script, Approve budget (shows the estimate screen and sends the token), Publish (now or
    at a time), Cancel; polls `GET /api/episodes/{id}` every 5 s; works at phone width. Stage 2
    adds warnings, inline edit, per-scene state chips, contact-sheet links and the "Needs you"
    panel.

#### 34. `web/src/App.tsx` (Modify)

*   **Type / Scope**: Routing.
*   **Proposed Changes**: `?episode=` renders `EpisodePage` before the editor branch, like
    `?render=1` and `?program=1`.

#### 35. `server/tests/test_episodes.py` (Create)

*   **Type / Scope**: Unit and API tests.
*   **Proposed Changes**: Contract round-trip including `card_template`; validator error rows and
    the length warning; create, approve-script, estimate with token, approve-budget refused
    without the token or `Origin`, refused over the ceiling, two queued approvals cannot both pass
    against the same balance, a charge dated in the month after its approval counts in that month,
    a release frees the ceiling; publish now and scheduled through the fake YouTube transport; a
    passed `publish_at` with a private video does not set `published`; cancel releases only
    unsubmitted reservations; preflight 503 with missing names.

#### 36. `server/tests/test_episode_pipeline.py` (Create)

*   **Type / Scope**: Worker tests.
*   **Proposed Changes**: Planner on a three-scene fixture with the fake HeyGen transport: one
    `create_video` per (key, take) with two planners running at once; a HeyGen `failed` returned as
    a result and charged; `max_attempts = 1` honoured; compose on the plate with the guard;
    concat frame counts; kit chapters and SRT timing fallback; registration names and sidecar; a
    registered episode appears in `GET /api/recordings`; the upload sets `uploaded_private`;
    purge keeps the right files and writes the export.

#### 37. `server/tests/fixtures/episode-01-v2/` and `server/tests/convert_episode1.py` (Create)

*   **Type / Scope**: Test fixture and its one-off converter.
*   **Proposed Changes**: Copies of `docs/scripts/episode-01-v2.json`,
    `tools/compose/episode-01-v2.plan.json`, `episode-01-v2.durations.json`, and the converted
    `script.json` produced by the converter, which lives in `server/tests/`, not in the package.

### Stage 2: QA, allowance, degrade, status

#### 38. `server/src/streamstudio/episode/qa.py` (Create)

*   **Type / Scope**: `scene_qa` handler.
*   **Proposed Changes**: `check_clip(mp4, cascade) -> dict` ported from
    `tools/compose/qa_avatar.py:check`; `scene_qa` compares against `reference`, writes
    `qa/<scene>.json` and `qa-<scene>.jpg`, runs `core.transcribe.transcribe` on the clip,
    writes `qa/<scene>.words.json`, computes the word error rate after voice-names and
    number-to-words normalisation (`LOOK` over 25 %; `FAIL` only when a re-rendered take also
    differs by more than 25 %), returns `{status, issues, words}`.

#### 39. `server/src/streamstudio/episode/planner.py` (Modify)

*   **Type / Scope**: Planner rules 2 and 3.
*   **Proposed Changes**: QA enqueueing, `reference` medians after the first full pass, the
    allowance (attempts and USD), `take + 1` re-renders, degrade, `needs_dan` on job `error`.

#### 40. `server/src/streamstudio/episode/validate.py` (Modify)

*   **Type / Scope**: Remaining validator warnings.
*   **Proposed Changes**: Question and reveal presence, claim sources, voice-names spelling,
    the consecutive-avatar 8 s rule.

#### 41. `server/src/streamstudio/mcp.py` (Modify)

*   **Type / Scope**: MCP server.
*   **Proposed Changes**: Tools `episode_create(script)`, `episode_list()`,
    `episode_status(id)`, `episode_estimate(id)`; `youtube_upload` unchanged. No approve, publish
    or purge tool; the descriptions say so.

#### 42. `web/src/episode/EpisodePage.tsx` (Modify)

*   **Type / Scope**: Full status page.
*   **Proposed Changes**: Warnings beside scenes, inline edit of `text`, `voice`, `sources`,
    per-scene state chips with progress counts, contact-sheet links, the "Needs you" panel and
    the Advance and Send-back-to-writer actions.

#### 43. `server/tests/test_episode_qa.py` (Create)

*   **Type / Scope**: Tests.
*   **Proposed Changes**: QA on synthetic clips (ffmpeg `lavfi` frames with and without a face
    image, frozen frames, a glitch frame); the transcript check with a stubbed `transcribe`,
    including a name-heavy voice line that normalises to `ok`; a FAIL re-renders with `take+1`
    within the allowance; the next FAIL degrades; retries charge the allowance; a job `error` sets
    `needs_dan` and Advance clears it; every validator warning row on a minimal script.

### Stage 3: captures and generic cards

#### 44. `server/src/streamstudio/episode/capture.py` (Create)

*   **Type / Scope**: `site_capture` handler.
*   **Proposed Changes**: Playwright Chromium, fresh context, 1400 px viewport, request blocking
    for non-allow-listed hosts and private ranges, abort on cross-host redirect, full-page
    screenshot and selector rectangles to `caps/<urlkey>.*`; `urlkey` from the normalised URL;
    `data_dir/sites/<urlkey>/` used when the allow-list entry is `manual`.

#### 45. `server/src/streamstudio/episode/hyperframes.py` (Move from `tools/compose/motion/build.py`)

*   **Type / Scope**: Composition builder.
*   **Proposed Changes**: `Comp` unchanged in API; no import-time work; every string escaped;
    `write` emits `cues.json`; `render` takes the browser path from `Settings` and runs from
    `data_dir/cards/` with a constant worker count.

#### 46. `server/src/streamstudio/episode/cards.py` (Create), `data_dir/cards/package.json`, `data_dir/cards/templates/generic.json` (Created by the launcher's `npm ci` step and shipped from `server/src/streamstudio/episode/templates/`)

*   **Type / Scope**: `card_render` handler and the generic template.
*   **Proposed Changes**: Groups consecutive card scenes by `site`; fills the `generic` template
    from the capture and the scenes' escaped `text`; beats at measured scene boundaries; writes
    `cards/<card>.mp4` and `cues.json`; records `durations_hash`. `scene_compose` gains the card
    slice; `episode_assemble` reads card cues.

#### 47. `server/tests/test_episode_cards.py` (Create)

*   **Type / Scope**: Tests.
*   **Proposed Changes**: Template fill from a fixture capture with a `<script>` string escaped;
    `cues.json` emitted; allow-list refusal and redirect abort; two scenes on one host with
    different paths produce two captures and each card reads its own; the renderer stubbed through
    the `HYPERFRAMES_RENDER` hook; a card scene composed with the presenter in the small
    rectangle.

### Stage 4: hardening, documentation, removal of the hand-run pipeline

#### 48. `tools/compose/cuts.py`, `scenecut.py`, `splice.py`, `masks.py`, `peek.py`, `motion/stitch.py` (Delete)

*   **Type / Scope**: Long-take tooling.
*   **Proposed Changes**: Removed; their purpose is covered by per-scene clips, cut-outs from
    `heygen_clip`, the planner and the status page's contact sheets.

#### 49. `tools/compose/render.py`, `qa_avatar.py`, `mix.py`, `motion/build.py`, `motion/cards.py`, `motion/cards_v2.py`, `motion/intro/make_intro.py` (Delete)

*   **Type / Scope**: Moved into the server package or fixtures.
*   **Proposed Changes**: Deleted after files 25, 28, 38, 45 and 8 land; the Episode 1 v2
    storyboards survive only as the JSON fixture (file 37).

#### 50. `tools/compose/README.md`, `tools/compose/motion/README.md`, `tools/compose/motion/intro/README.md`, `tools/README.md` (Modify or Delete)

*   **Type / Scope**: Contract READMEs.
*   **Proposed Changes**: `tools/compose/` keeps the two plan JSON files and a README pointing at
    `server/src/streamstudio/episode/README.md`; the motion and intro READMEs are removed with
    their code; `tools/README.md` updated.

#### 51. `server/src/streamstudio/episode/README.md` (Create), `server/src/streamstudio/README.md`, `server/src/streamstudio/api/routes/README.md`, `server/src/streamstudio/worker/README.md`, `server/src/streamstudio/core/README.md`, `web/src/README.md`, `README.md` (Modify)

*   **Type / Scope**: EGM contract READMEs.
*   **Proposed Changes**: The new package's contract; the parents list it; the route, worker,
    core, web and root READMEs gain the new routes, handlers, settings, tools and the episode as a
    system boundary; the root README's Status drops "Next: YouTube upload".

#### 52. `docs/DESIGN.md` (Modify)

*   **Type / Scope**: Design reference.
*   **Proposed Changes**: "Episode production rules" gains the glossary (episode, scene, set,
    card, table overlay, take, allowance, degraded, workings, kit), the -36 LUFS bed, 25 fps, the
    allowance rule and the three clicks; one sentence notes that the saved stage layouts are
    called sets in prose; the offline compositor section points at the episode package.

#### 53. `docs/AGENTS.md`, `docs/AGENT_GUIDE.md` (Modify)

*   **Type / Scope**: Agent docs.
*   **Proposed Changes**: The episode tools, the script contract, "what agents cannot do" gains
    "approve a budget, publish or purge".

#### 54. `CLAUDE.md`, `PLAN.md` (Modify)

*   **Type / Scope**: Project instructions and plan.
*   **Proposed Changes**: `CLAUDE.md` Layout lists `episode/`; Rules add "the planner is the
    only writer of an episode's stage data; the API writes script, budget and gate states" and
    "no `heygen_clip` for an episode without `budget.approved_at`". `PLAN.md` gains milestone S9
    (the factory) and a note that Decision 6 ("record and live-stream from the start") no longer
    drives the roadmap.

#### 55. `server/tests/test_episode_e2e.py` (Create)

*   **Type / Scope**: End-to-end test.
*   **Proposed Changes**: The three-scene fixture from script to a registered recording, a fake
    upload and a fake publish, with fake HeyGen, fake YouTube, stubbed HyperFrames and synthetic
    clips; asserts one paid render per key, the guard applied to every scene (cue per kind) and
    to a degraded scene, frame counts on concat, the kit, the sidecar, the recordings listing, the
    purge.

#### 56. `.github/workflows/ci.yml` (Modify)

*   **Type / Scope**: CI.
*   **Proposed Changes**: Server job installs the `episode` extra (headless OpenCV) so the
    compositor and QA tests run; Playwright is stubbed in tests, not installed in CI.

### Verification Plan

*   **Build**: `make build` (web) and `uv sync --extra episode` (server) on the Mac Studio;
    `make mac-app` then a cold start of StreamStudio.app passes preflight.
*   **Unit tests**: `make test` (`pytest` in `server/`, `vitest` in `web/`), including
    `test_episodes.py`, `test_episode_pipeline.py`, `test_episode_qa.py`, `test_episode_cards.py`,
    `test_episode_e2e.py` and the shared lip-sync fixtures.
*   **Static analysis**: `make lint` (`ruff`, `tsc -b`, `oxlint`); a test imports every module in
    the episode package and asserts no files are written at import.
*   **Coverage requirement**: every planner rule, every validator rule and every ledger rule has a
    test; the guard fixtures pass in Python and TypeScript.
*   **Integration**: the Stage 0 record (file 11) exists with real numbers; one real three-scene
    episode from script to private upload and publish on the Mac Studio with no step outside the
    app, timed, is the only paid integration check. A re-render of Episode 1 v2 from the fixture
    is optional and only on Dan's approval, since it costs about 12 USD of HeyGen and compares
    against a video made from a single long take.
*   **Success measure**: the first five daily episodes each log zero manual steps, approve-budget
    to `uploaded_private` under 12 hours, Dan's interaction under 15 minutes, HeyGen cost within
    estimate plus allowance, and their QA verdicts.

--------------------------------------------------------------------------------

*Drafted with EGM*
