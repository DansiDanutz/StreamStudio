# Daily episode factory

*   **Author:** Dan (DansiDanutz)
*   **Status:** Final
*   **Date:** 2026-11-02
*   **Predecessor:** [concepts_brief.md](./concepts_brief.md) (six Goldfish reviews of [hypothesis.md](./hypothesis.md))
*   **Review:** EGM Stages 5 to 9 complete; findings resolved on 2026-11-02 (see `goldfish_review_report.md`).

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
*   purges the workings (the intermediate files) when Dan asks, after the video is public.

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
    without `budget.approved_at`, that one clip is paid for at most once per take, and that
    worker retries and QA re-renders never exceed the allowance. HeyGen cost per episode stays
    within estimate plus allowance.
*   **Every production rule is enforced automatically.** Scene length, question-then-answer
    structure with the closing reveal, names written for the voice, a source on every numeric or
    ranking claim, an on-screen event at least every 8 s of avatar, the lip-sync guard on every
    composed scene, frame counts on concatenation: each has a unit test.
*   **Dan can see where an episode is from a phone.** One status page per episode: scene by
    scene, what it is blocked on, the last error in plain words, the next action, and the running
    cost. Readable through the API and the Model Context Protocol (MCP) server without the editor
    open.
*   **The toolchain is declared and checked.** A preflight refuses to start an episode when any
    tool, font or asset the shipped stage needs is missing, and nothing is hard-coded to one
    machine.
*   **Workings are purged on request once the video is public.** The final MP4, the script and
    the episode record are kept.

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
*   Re-voicing an episode after it has been uploaded (see Future Improvements).
*   Renaming the editor's saved stage layouts ("scenes") in the Library, API or agent catalog;
    this design only fixes the vocabulary in prose (see Future Improvements).
*   Backing up episode workings to the vault.
*   Multiple channels per episode, presenters or languages; portrait Shorts; the local-voice cost
    lever for card scenes.
*   Keeping `cuts.py`, `scenecut.py`, `splice.py`, `stitch.py` or `masks.py` in the factory.

## Open Questions

*   **Q1. Mac Studio numbers.** Wall-clock for a per-scene HeyGen render, HeyGen's
    concurrent-render cap and minimum billed seconds per clip, whether a render HeyGen reports
    `failed` is billed (the design assumes it is until shown otherwise), rembg cut-out per clip,
    whisper transcription per clip, one HyperFrames card render, compositing per scene on the
    ported code (and whether composites gain from worker threads), and disk per episode. Stage 0
    measures the HeyGen, rembg, whisper and HyperFrames numbers; Stage 1 measures compositing on
    the ported compositor.
*   **Q3. Which logged-in sites Dan captures by hand.** The design captures only allowlisted
    public pages automatically; a logged-in page (the JEV trading dashboard in Episode 1) is
    captured once by hand or not shown. Dan decides per site.

Q2 (allowance default), Q4 (music bed level) and Q5 (Episode 1 v2 as a fixture) from the brief are
answered in the Technical Plan and the Verification Plan.

## Critical User Journeys (CUJs)

### CUJ 1: A script becomes a private upload with three clicks

*   **Given**: The Mac Studio passes preflight (the tools, fonts and assets the shipped stage
    needs are present), the HeyGen API key and one YouTube channel are connected, and a writer has
    posted a finished script to the episode API with scene ids, on-screen text, voice text,
    sources and site URLs.
*   **When**: Dan opens the Episode page, reads the validator's warnings next to the scenes, edits
    a line or two, and clicks Approve script; then reads one cost screen (36 scenes, 318 s, 12.25
    USD, wallet balance after, month's total after, allowance 4 re-renders / 1.50 USD) and clicks
    Approve budget.
*   **Then**: The worker renders every scene, runs QA, re-renders within the allowance, composes,
    concatenates, adds intro, music and SFX, builds the publish kit, uploads as private and sets
    the episode to `uploaded_private`. Dan sees the private video link and clicks Publish (now, or
    at a chosen time from Stage 2). Once the video is public the page offers "Purge workings?".
    Nothing was done outside the app, and no render ran without the budget approval.

### CUJ 2: A scene fails QA at 02:00

*   **Given**: An episode is rendering overnight; the allowance is 4 re-render attempts, shared by
    the whole episode.
*   **When**: Scene 17 fails QA (face missing); scene 23 fails QA (frozen frame).
*   **Then**: Scene 17 is re-rendered once and passes (1 attempt used). Scene 23 is re-rendered
    three times and fails QA each time (4 attempts used; the allowance is spent). Scene 23 is
    degraded: its last clip is composed with the face in the small picture-in-picture rectangle
    over its site card or the studio plate, with a note in the episode log. The episode continues
    to a private upload. In the morning the status page says: "Scene 23 degraded to the small
    picture after 3 failed re-renders (frozen frame). Keep it, or re-voice it in a new episode."
    No money was spent beyond the allowance. Had HeyGen failed to render scene 23 at all after the
    allowance, there would be no clip to degrade and the episode would stop in `needs_dan` instead.

### CUJ 3: Only changed words are rendered again

*   **Given**: An `in_progress` episode whose clips have all rendered and passed QA, not yet
    uploaded.
*   **When**: Dan edits the words of scenes 6 and 12 (the episode returns to `draft`), clicks
    Approve script again, reads the cost screen (2 scenes, 19 s, about 0.75 USD) and clicks
    Approve budget.
*   **Then**: A new reservation covers the two scenes without a clip for their new key (plus any
    render still running), and the previous one is released. Only those two clips are rendered;
    the stale `final.mp4` and `kit.json` were removed by the edit, so the two composites, the
    concatenation, cards whose scene durations changed and the publish kit's captions and
    chapters are rebuilt; the episode is registered as the next take; the upload proceeds as in
    CUJ 1. Editing an
    episode that is already `uploaded_private` is refused; re-voicing after upload is out of scope
    for v1.

### CUJ 4: An agent prepares an episode and stops before the paid step

*   **Given**: An agent with MCP access and a topic.
*   **When**: It posts the script, reads the validator's warnings, fixes them, and asks for the
    estimate.
*   **Then**: The episode stays in `draft` with the estimate on the status page. The agent cannot
    approve the budget. Dan sees one panel on his phone with two buttons: Approve budget, and
    Send back to writer (which adds a note to the episode log and leaves the episode in `draft`).

## Technical Plan (Architecture)

The work is staged in five stages (Detailed Implementation Plan): Stage 0 measures and installs
the toolchain; Stage 1 is the thin slice from script to private upload and publish; Stage 2 adds
QA, the allowance, scheduled publish, cancel and the full status page; Stage 3 adds site cards;
Stage 4 hardens, documents and removes the hand-run pipeline.

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
*   **Degraded**: a scene whose clip exists but failed QA after the allowance was spent, composed
    with the face in the small picture-in-picture (pip) rectangle instead of large.
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
 worker: episode_advance (planner) ── evaluates a condition table over the record + files on disk
   ├─ heygen_clip ×N (exists; + take, claim)   → assets/avatar/clips/<key>.mp4 (+ .cutout.webm)
   ├─ scene_qa ×N (Stage 2)                    → episodes/<id>/qa/<scene>.t<take>.words.json, .jpg
   ├─ site_capture ×K, card_render ×K (Stage 3)→ episodes/<id>/cards/<card>.mp4 + cues.json
   ├─ scene_compose ×N                         → episodes/<id>/scenes/<scene>.mp4
   ├─ episode_assemble                         → concat + intro + music + SFX → episodes/<id>/final.mp4
   ├─ episode_publish_kit                      → episodes/<id>/kit.json, final.srt
   ├─ episode_register                         → recordings/rec_<date>-ep.mp4 (moved) + .srt + .episode.json
   ├─ youtube_upload (exists; + episode_id)    → video id, private; enqueues the planner
   └─ episode_purge (Purge button)             → removes workings, keeps final, script, record
 Dan: POST /api/episodes/{id}/publish ──► YouTube videos.update (public now; scheduled from Stage 2)
```

Every box is an idempotent job keyed by what it produces; a crashed or repeated job finds its
output and returns. Handlers report by writing files; the planner reads the record and the files.
Its one permitted read of the `jobs` table is the `status` of a job id it recorded itself, to tell
queued or running from finished.

### Data flow for one scene

```text
scene s12 (voice, plan) ──clip key (text, look, voice, motion, take)──► heygen_clip ──► clip + cut-out
        │                                                                     │   (or `failed` in the clip state file)
        │                                                      scene_qa ◄─────┘  → ok | LOOK | FAIL (Stage 2)
        │                                                         │ FAIL & allowance left → take+1 → heygen_clip
        │                                                         │ FAIL & allowance spent → degraded
        │                                                         │ render failed & allowance spent → needs_dan
        └─ plan + card slice (if kind=card) ─► scene_compose (guard) ─► scenes/s12.mp4 (25 fps, clip audio)
                                                                           │
                                 episode_assemble: concat + intro + music + SFX(cues.json) ─► final.mp4
```

### The episode record

One episode is one row in a new `episodes` table whose `record_json` column holds the whole
record, read and written under a write lock, as `edl_versions` stores EDL (edit decision list)
JSON today. The episode is also a `projects` row (inserted directly, not through
`create_project`, so no EDL version is created), so `jobs.project_id` correlates every job to its
episode with no schema change to `jobs`. The project API keeps its contract by excluding
episode-owned rows: `store.list_projects` skips rows that have an `episodes` row, and
`project_or_404` answers 404 for them, so no caller reaches `latest_edl` for a project without an
EDL. The
episode's files live under `data_dir/episodes/<episode_id>/`; `episode.json` there is an export
written at purge for the archive, not a live store. Migration 4 adds two tables: `episodes` (id,
project_id, status, title, created_at, updated_at, record_json) and `heygen_ledger` (see "The
paid step").

The record:

```text
record
  id, title, status, created_at, updated_at, last_checked_at
  script: { version, hash, title, tags, channel, look, voice_id, motion, scenes: [ scene ] }
  budget: { approved_at, confirm_token, token_expires_at, clips, seconds, usd,
            allowance: {attempts, usd}, spent: {renders, seconds, usd} }      # spent is a projection of the ledger
  reference: { face: [x,y,w,h], lip_ratio }           # QA medians from the first full pass (Stage 2)
  scenes_state: { <scene_id>: { clip_key, take, job_id, video_id, duration_s,
                                qa: ok|LOOK|FAIL|degraded|null, qa_issues: [], composed_hash, card_id } }
  cards: { <card_id>: { scenes: [ids], urlkey, durations_hash, cues } }
  outputs: { channel, final_mp4, final_srt, kit, recording_id, upload_job_id, youtube_video_id, publish_at }
  log: [ { at, stage, scene?, message } ]              # plain-words events for the status page
```

Writers of the record: the API writes `script`, `budget`, `outputs.channel` and the gate states;
the planner is the only writer of `scenes_state`, `cards`, the other `outputs` fields, `log` and
the working states. Both hold the `episodes` row lock while writing.

States are the human gates and the terminal states only: `draft` → `script_approved` →
`budget_approved` → `in_progress` → `uploaded_private` → (`scheduled`) → `published` → `purged`,
plus `needs_dan` and `cancelled`. Progress inside `in_progress` is shown from counts in
`scenes_state` ("rendering 12/36, QA 8/36, composing 3/36, uploading"), not stored. Transition
rules:

*   `PUT /{id}/script` from `draft`, `script_approved`, `budget_approved` or `in_progress` returns
    the episode to `draft`. In-flight clip jobs finish and are charged to the existing
    reservation; nothing new is enqueued until the next budget approval, which reserves one line
    per distinct (clip key, take): every live render job under its own key and take, plus every
    scene that has no clip and no live job for its current key (an edited scene whose old render
    is still running is therefore reserved twice, once per key, and an unchanged scene mid-render
    once). Only then is the previous reservation released, so submitted work never leaves the
    ledger. An edit whose script hash changes makes every output downstream of the scenes stale:
    `final.mp4`, `final.srt` and `kit.json` are unlinked and `outputs.recording_id` is cleared
    (the registered recording stays in the library as an earlier take; the next registration is
    the next take), so rows 7 to 10 of the planner rebuild them. While a `youtube_upload` job is
    live, and after `uploaded_private`, the edit is refused with 409.
*   `needs_dan`: a stage job ends in `error` (network, tool crash, disk full, HeyGen cap), or a
    render fails after the allowance is spent; the reason is written to `log`.
    `POST /{id}/advance` after Dan acts returns the episode to `in_progress`.
*   `cancelled` (Stage 2): `POST /{id}/cancel` from any state before `uploaded_private`;
    releases the unsubmitted part of the reservation (see "The paid step") and allows purge.
*   `uploaded_private`: set by the planner when the upload's state file names a video id.
*   `scheduled` and `published`: set by the publish click and the refresh call (see "Publish").
*   `purged`: set by `episode_purge`, which only the Purge button enqueues.

### The script contract and validator

A script is posted as JSON and stored inside the record. Shape:

```text
script: { title, version, tags?: [str], channel?: <YouTube channel id>,
          look?, voice_id?, motion?,        # default from the saved HeyGen config
          scenes: [ scene ] }
scene:  { id: "s12", text: "...on screen...", voice: "...as HeyGen reads it...",
          kind: "avatar" | "card", site?: "https://...",
          question?: <int>,            # this scene asks question N
          reveal?: true,               # the closing scene that reveals the AI avatar
          sources?: [ { claim: "fourteen thousand subscribers", source: "Dan, 2026-11-02" } ],
          plan?: { title?: [line1, line2], lower?: [name, sub], lowers?: [[from, to, name, sub]],
                   chips?: [str], chip_at?: [fraction], chips_out?: fraction,
                   zoom?: [cx, cy, z], zoom_path?: [[fraction, cx, cy, z]], card_x?: fraction,
                   frame?: [cx, cy, z], glitch?: [[fraction, seconds]],
                   endcard?: [title, link, small], end_at?: fraction, end_until?: fraction,
                   whoosh_at?: fraction, card_template?: "generic" } }
```

`voice` is what HeyGen reads (names written for the voice); `text` is shown on screen and used
for captions when `voice` is empty. `plan` carries the per-scene creative data that
`episode-01-v2.plan.json` held positionally, with the same keys and meanings as
`tools/compose/README.md` documents them; it is optional and a scene without it still renders (an
avatar scene with `question` gets the default table overlay; a card scene gets the generic site
card). `card_template` accepts `generic` only in v1. `channel` names the connected YouTube
channel; when omitted and exactly one channel is connected, that one is used. A converter imports
the Episode 1 v2 files (script JSON, plan JSON, durations) into this shape as the first test
fixture.

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

Warnings never block approval. Errors do. Stage 1 ships the error rows; the warnings ship in
Stage 2. The table of names for the voice lives in `assets/brand/voice-names.json` (one entry per
product: on-screen spelling, voice spelling).

### The planner: `episode_advance`

One handler, re-queueable at any time, that reads the record and the filesystem and decides the
next step. It never calls HeyGen, ffmpeg or a browser itself; it enqueues the handler that does
and returns. It is enqueued by the API after each approval, by every stage handler when it
finishes (including a handler that ended in `error`, which the worker loop enqueues on the
handler's behalf), and by `POST /api/episodes/{id}/advance` for a manual resume. It runs under
the `episodes` row lock and evaluates the table below top to bottom, acting on the first row
whose predicate holds for a scene or for the episode. "Live job" means a job id recorded in
`scenes_state` whose `jobs.status` is `queued` or `running`.

| # | Predicate (record + files) | Action |
| --- | --- | --- |
| 1 | `budget_approved` or `in_progress`; a scene's clip state file says `failed` for its current take, or its recorded job ended in `error` (Stage 1) | Stage 1: set `needs_dan`, log the reason. Stage 2: see row 3. |
| 2 | A scene has no clip (`<key>.mp4` and `.cutout.webm`) for its current take, no `failed` entry for that take, and no live job | Enqueue one `heygen_clip` (payload as today plus `take`, `episode_id`, `scene_id`, one attempt); record the job id; set `in_progress`. If the scene's previous job ended in `error` with a saved `video_id`, transfer the claim to the new job id so it resumes that render. |
| 3 (Stage 2) | A scene's clip and cut-out exist for its current take, its QA result for that take is missing, and no `scene_qa` job for it is live | Enqueue `scene_qa`; after the first full pass store the medians in `reference`. (A `failed` state file means no clip exists, so rows 3a and 3c, not this row, handle a failed render.) |
| 3a (Stage 2) | A scene is `FAIL`, or its clip state file says `failed`, and the allowance has attempts and USD left | Increment `take`, charge the allowance, go to row 2. |
| 3b (Stage 2) | A scene is `FAIL` and the allowance is spent | Mark the scene `degraded` (its last clip is composed in the small rectangle); log it. |
| 3c (Stage 2) | A clip state file says `failed` and the allowance is spent | Set `needs_dan` ("Scene N could not be rendered after K attempts"). |
| 4 (Stage 3) | A card's capture is missing | Enqueue `site_capture`. |
| 5 (Stage 3) | A card's capture exists and its `durations_hash` changed | Enqueue `card_render`. |
| 6 | Every scene has a clip and cut-out (Stage 1) or a QA result of `ok`, `LOOK` or `degraded` (Stage 2), and a scene's `composed_hash` differs from its `inputs_hash` | Enqueue `scene_compose` for that scene. |
| 7 | Every `scenes/<id>.mp4` is up to date and neither `final.mp4` nor `outputs.recording_id` exists | Enqueue `episode_assemble`. |
| 8 | `final.mp4` exists and `kit.json` does not | Enqueue `episode_publish_kit`. |
| 9 | `kit.json` exists and `outputs.recording_id` is unset | Enqueue `episode_register`. |
| 10 | `outputs.recording_id` is set, the upload state file has no `video_id`, and `outputs.upload_job_id` is unset or names a job that is neither queued nor running | Enqueue `youtube_upload` with `{id, channel, key: "<channel>/<rid>", meta: clean_meta(kit.title, kit.description, kit.tags, "private"), episode_id}` and record its id in `outputs.upload_job_id`. |
| 11 | The upload state file names a `video_id` | Set `uploaded_private`; release what is left of the reservation. |

No handler waits for another: each stage handler enqueues `episode_advance` when it finishes, the
planner counts what exists, and only the last handler of a stage finds everything present. Two
planners running at once are safe because row 2 records job ids inside the lock, every handler is
idempotent, and the clip handler's claim stops a second payment (see "The paid step").

### The paid step

The confirm screen is served by `GET /api/episodes/{id}/estimate`, which uses the shared estimate
logic in `core/heygen.py` (the same numbers the editor's HeyGen panel shows) and adds: the wallet
balance after this render, the month's total after this render, the allowance, and the ceiling.
The response carries a one-time `confirm_token`, stored on the record and valid for ten minutes.

"Month after" is computed from a ledger, not from episode creation dates. The `heygen_ledger`
table holds three kinds of row, each tied to an episode, a scene, a take and a job id: a
**reservation** when a budget is approved (the estimate plus the allowance, dated when approved);
a **charge** when a render completes or fails (the billed seconds and USD, dated when the render
finished, which may fall in a later month than the approval); a **release** when unconsumed
reserved money is given back. A charge is written once per (episode, scene, take). The
unconsumed part of an episode's reservation is its latest reservation's USD minus its charges and
releases since, floored at zero. The month's total is the sum of this calendar month's charges
plus the unconsumed part of every open reservation, whatever month the episode was created in.
Seconds charged are the downloaded clip's measured duration for a completed render, and the
scene's estimated seconds for a failed one; USD is seconds times the rate. Until Stage 0 shows
otherwise, a render that HeyGen reports `failed` is charged as if billed, so the ceiling errs on
the safe side.

`POST /api/episodes/{id}/approve-budget` requires the `confirm_token` and an `Origin` header that
is present and allowed, which the Episode page sends and the MCP client does not. It runs under
the row lock: it resolves the YouTube channel (409 when several are connected and the script
names none), recomputes the month's total, refuses with 409 when the total plus this episode's
estimate and allowance would pass the monthly ceiling, and otherwise writes the reservation row,
`outputs.channel` and `budget.approved_at` in the same transaction, so two approvals cannot both
pass against the same remaining balance. An agent with raw HTTP access could still scrape the
token from the estimate response; the monthly ceiling is the backstop, and the ledger makes every
spend visible.

A `heygen_clip` carrying an `episode_id` behaves differently from today's handler in four ways.
It writes a claim (its own job id) into the clip's state file before calling HeyGen, and exits as
a no-op if the file holds another job's claim whose job is still live; a claim whose job has
finished is stale, and the planner transfers it to the replacement job together with the saved
`video_id`, so recovery after a network error resumes the submitted render instead of paying
again. It never unlinks the state file: a HeyGen `failed` is recorded there as
`{failed: reason, at}` and returned as the handler's result, with a ledger charge written and the
planner enqueued. It is enqueued with one attempt, so a worker-level error also returns to the
planner (the worker loop enqueues the planner after recording the error) instead of re-rendering
on its own; a stale-heartbeat requeue keeps the same job id and resumes from the saved
`video_id`. A `youtube_upload` carrying an `episode_id` likewise enqueues the planner when it
returns.

The planner releases what is left of a reservation when the episode reaches `uploaded_private`.
On `cancelled` (Stage 2), only the reservation for clips never submitted (no `video_id`) is
released; clips already submitted stay reserved until their render completes or fails and a
charge row is written, which the planner does on its next pass even for a cancelled episode,
because cancelling the local job does not stop HeyGen's render or its bill.

The allowance is episode-wide and counted in re-render attempts and USD; both caps must hold.
Defaults are settings: `episode_rerender_attempts` (default 4), `episode_rerender_usd` (default
1.50) and `heygen_month_ceiling_usd` (default 400). The ceiling default is deliberately tight; the
brief estimated 400 to 550 USD a month at one episode a day, and Dan sets the real ceiling.

The clip key gains the take number only when it is above zero, so every existing clip keeps its
name. Rejected takes stay in place, marked in `scenes_state`, and are vaulted like any clip.

### QA: `scene_qa` (Stage 2)

`scene_qa` runs the checks of `tools/compose/qa_avatar.py` on one clip (face present and placed,
glitch, frozen while speaking, lip motion against the voice), ported into the server package. It
compares the face box and lip ratio against `reference` when present (the medians of the first
full pass, so a single re-rendered clip still has a cohort), writes `qa/<scene>.json` and the
contact sheet `qa/<scene>.jpg`, and returns `ok`, `LOOK` or `FAIL` with the issues. The status
names are those of `qa_avatar.py`: `FAIL` for face, glitch or frozen faults, `LOOK` for lip
warnings.

Each clip is also transcribed locally with whisper and the result kept per take as
`qa/<scene>.t<take>.words.json` (with its SRT beside it), the accepted take's copy at
`qa/<scene>.words.json`; the word timings are the reference clock for captions. Transcript and
`voice` are both normalised through the voice-names table and a number-to-words pass before the
word error rate is computed. A rate above 25 % is `LOOK`; it becomes `FAIL` only when a
re-rendered take's transcript also differs from the first take's by more than 25 %, since two
matching transcripts mean the words are right and the recogniser is wrong. When whisper is
missing the transcript is recorded as unavailable and the verdict is unchanged. The lip-motion
heuristic is a quality check; it is not the lip-sync guard, which is a layout rule (see
"Compositor").

### Cards: `site_capture`, `card_render` (Stage 3)

A card covers a run of consecutive `kind: card` scenes with the same `site`. `site_capture` runs
the Playwright Chromium already used by `render/preview.py` with a fresh profile and no cookies,
takes a full-page screenshot and the bounding boxes of the first visible heading and the largest
visible image, and stores them under `episodes/<id>/caps/<urlkey>.*`. `urlkey` is the host
followed by a short hash of the whole normalised URL (host, path and query, lower-cased, trailing
slash dropped), so two pages on one site never share a file, and cards reference captures by the
same key.

Allowlist entries in `Settings.capture_allowlist` are `{host, mode: "auto" | "manual"}` matched on
the exact host. `site_capture` refuses any URL whose host is not listed, blocks requests to
non-allowlisted hosts and private address ranges while the page loads, aborts on a cross-host
redirect, and never logs in. A `manual` site is captured once by hand into
`data_dir/sites/<urlkey>/` (not under `assets/`, which is served at the web root) and reused.

`card_render` builds a HyperFrames composition from the capture with the generic card: address
bar, slow scroll, one zoom to the hero, one callout taken from the scenes' `text`, with beats at
the scene boundaries measured from the clips. The generic card is a function over the
composition builder, not a data template. Every script-derived string is HTML-escaped before it
enters the composition. The builder emits `cues.json` beside the MP4, a list of
`{kind: navigate | counter | ring | callout, t}` in seconds from the card's start; the mixer reads
that file. Rendering runs `npx hyperframes render` as a subprocess from the HyperFrames workspace
under `data_dir/cards/`, whose `package.json` and lockfile ship inside the server package and are
copied there by the launcher before `npm ci`, with the browser path from
`Settings.hyperframes_browser`. Richer templates and beats placed on words from the whisper
timings follow once the generic card has shipped a few episodes (Future Improvements).

### Compositor: `scene_compose`, `episode_assemble`

The compositing of `tools/compose/render.py` moves into the server package as functions taking
`Settings` and a scene, with every path from settings and fonts from `assets/brand/fonts/`.
`scene_compose` reads the clip and its cut-out in lock-step at 25 fps (the cut-out through the
VP9 decoder that keeps alpha), seats the presenter from the plate's seat geometry, draws the plan,
and writes `scenes/<scene>.mp4` at 25 fps with the clip's audio (the clip's timing is not
changed), via a temporary file and rename. It records an inputs hash over the scene text, the
clip and cut-out checksums, the card checksum and the plan, so "up to date" means inputs
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
against the measured durations), puts the intro in front, and runs the mix from the levels table
below, with SFX at the cues from each card's `cues.json` and from the plan (`question`,
`whoosh_at`, `glitch`, `endcard`) through a fixed cue-to-sound table carried over from `mix.py`.
One frame rate, 25 fps, for clips, cards, intro and final.

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

`episode_publish_kit` writes `kit.json` (`title`, `description`, `tags`, `chapters`, `notes`) and
`final.srt`. Chapters follow YouTube's rules as `web/src/publish/kit.ts` encodes them: the first
chapter at 0:00 (the intro), one per `question` scene, chapters shorter than 10 s folded into the
previous one, and none at all (with a note saying why) when fewer than three remain. Captions come
from the script's on-screen `text` (or `voice`), not from the transcript, because DESIGN rule 6
wants on-screen spellings such as "Zmarty" where the voice says "Smarty"; each caption's start
and end come from the whisper word timings of its scene when present, falling back to the
measured duration split by character count. Every time is offset by the intro's duration plus
the preceding scenes' measured durations.

`episode_register` moves `final.mp4` to `recordings/rec_<YYYYmmdd-HHMMSS>-ep.mp4`, writes
`rec_...-ep.srt`, a minimal `rec_...-ep.transcript.json` naming the caption language, and
`rec_...-ep.episode.json` naming the episode, and records the path in `outputs.final_mp4`.
`finish_recording` is not run: the file is already H.264, AAC, normalised. `GET /api/recordings`
today discovers takes only through their `rec_*.source.*` upload files, which a registered
episode does not have, so the listing is extended to include `rec_*.episode.json` entries, merged
and sorted by id with the takes; a contract test asserts a registered episode appears in the
listing and in the YouTube take picker. The vault, `youtube_upload` and the MCP `youtube_upload`
tool work unchanged; the upload is always private.

### Publish

`POST /api/episodes/{id}/publish {publish_at?}` is Dan's third click, available from
`uploaded_private`. It calls YouTube's video update (`videos.update`, part `status`) through a
new `set_status` in the YouTube client for the episode's channel: with no `publish_at`,
`privacyStatus: public`, and the episode is set to `published` from the response. From Stage 2,
with `publish_at`, `privacyStatus: private` plus `publishAt`, and the episode is set to
`scheduled` with the time shown on the status page.

There is no hourly poll; the worker has no scheduler and the Non-Goals rule one out.
`GET /api/episodes/{id}` is a pure read. From Stage 2, `POST /api/episodes/{id}/refresh` asks
YouTube for the video's status, records `last_checked_at` (a repeat within five minutes is a
no-op), and sets `published` on an observed `public`. The Episode page calls it once when it opens
a `scheduled` episode after `publish_at`, and MCP may call it. A passed `publish_at` with the
video still private does not count: the page shows "scheduled release did not happen" and offers
the refresh, so a release cancelled in YouTube Studio never leads to a purge.

While an upload job is live and after `uploaded_private`, `PUT /{id}/script` is refused with
409: YouTube cannot replace a video file, and a second upload is a second video. Re-voicing an uploaded episode is out of scope for
v1 (Future Improvements); a new episode from the same script reuses every unchanged clip through
the clip key.

`episode_purge` is enqueued only by `POST /{id}/purge` (the Purge button, which the page shows as
"Published. Purge workings?" once the episode is `published`, and which also works from
`cancelled`): it removes `caps/`, `cards/`, `scenes/`, `qa/` and the mix intermediates, writes
`episode.json` as the archive export, keeps `kit.json`, `final.srt` and the registered recording,
and logs the freed bytes.

### Status, observability, agents

The API, under `/api/episodes`: `POST /` (validate; 503 with the missing names when preflight
fails; 422 on errors; create), `GET /`, `GET /{id}`, `PUT /{id}/script`,
`POST /{id}/approve-script`, `GET /{id}/estimate`, `POST /{id}/approve-budget`,
`POST /{id}/publish`, `POST /{id}/advance`, `POST /{id}/purge`, and from Stage 2
`POST /{id}/refresh`, `POST /{id}/cancel`, `GET /{id}/qa/{scene}.jpg`. `GET /{id}` returns the
record without the confirm token, plus `progress` (clips, QA, composed, total), `validation`
(errors, warnings), `next_action` and `last_log`; the Episode page, the MCP tools and the tests
all read that one shape.

The editor gets an Episode page (`?episode=<id>`, usable at a 390 px wide viewport) with the
scenes, warnings, the three buttons, and a "Needs you" panel that shows the last log line and the
one action that unblocks it. In Stage 2 the MCP server gains `episode_create`, `episode_list`,
`episode_status`, `episode_estimate` and `episode_refresh`, none of which can approve, publish,
cancel or purge. Every job the planner enqueues carries `project_id` and
`payload.episode_id`; the worker log line includes it. `heygen_ledger` is the cost ledger;
`budget.spent` is a cached projection of it. `/api/health` reports the toolchain (ffmpeg, whisper,
rembg, OpenCV, Playwright Chromium, HyperFrames, fonts, intro, plate, music manifest) with cheap
existence checks only. A Library group for episodes is deferred (Future Improvements).

### Assets and toolchain

`assets/brand/` gains `fonts/` (Inter OTF, the four woff2 web fonts the intro uses), `music/`,
`sfx/`, `voice-names.json` and `manifest.json` (name, file, sha256, licence note, and which track
is the bed). The existing `assets/brand/danslab-intro.mp4`, already registered as the editor's
intro media item, is re-rendered at 25 fps and is the one intro file; the intro's kicker, title
and tagline are channel constants, and the episode title appears on the opening table overlay.
`assets/models/` holds the OpenCV Haar cascade face detector. The HyperFrames workspace lives
under `data_dir/cards/` (its `package.json` and lockfile ship in the server package; the launcher
copies them and runs `npm ci` from Stage 3), so its `node_modules` is never served.
`pyproject.toml` gains an `episode` extra (OpenCV, Pillow, NumPy, SciPy, rembg, Playwright); the
Mac launcher, the Makefile and CI install it from Stage 0, and no module in the episode package
imports any of those libraries at module level, so the API and the worker start without them.
Settings: `episodes_dir`, `cards_dir`, `sites_dir`, `capture_allowlist`, `hyperframes_browser`,
`episode_rerender_attempts`, `episode_rerender_usd`, `heygen_month_ceiling_usd`. Frame rate (25)
and the HyperFrames worker count are constants.

### The smallest version

The first episode that removes every manual step is Stage 1: a finished script posted to the API
with error-level validation, approve-script, one estimate and approve-budget with the ledger and
the channel resolved, `heygen_clip` with the take and the claim, `scene_compose` on the plate
with the guard, concatenation, the intro and the music bed, the kit with chapters, registration,
private upload, and the publish-now click, with a minimal Episode page (the scene list and three
buttons: Approve script, Approve budget, Publish). A failed render or an errored job parks the
episode in `needs_dan`. Its first episodes are ones without site mentions, since still site cards
are forbidden by the production rules. QA, the allowance, the degrade path, scheduled publish,
cancel and the full status page are Stage 2; cards are Stage 3.

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
    confirm; retries count against it; beyond it the scene degrades or the episode stops.

### Alternative G: Stall the episode when a scene fails QA after the allowance

*   **Pros**: Nothing ships with a visible fault.
*   **Cons**: The daily cadence depends on Dan's hours; a 02:00 failure costs the day.
*   **Reason for Rejection**: Rejected for the cons above for QA failures, where a clip exists.
    Chosen instead: degrade the scene to the small picture-in-picture rectangle, ship, report in
    plain words. A render that produced no clip at all still stops the episode, because there is
    nothing to show.

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
    capture in v1, richer cards over selector-found rectangles later.

### Alternative J: An agent driving a browser for captures

*   **Pros**: Handles any page, including scrolling and sticky elements.
*   **Cons**: Not idempotent; violates the private-dashboard rule by default; needs credentials.
*   **Reason for Rejection**: Rejected for the cons above. Chosen instead: Playwright full-page
    screenshots under an allowlist with a fresh profile; logged-in sites captured once by hand
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
    planner evaluating a condition table over the episode record and the files on disk; handlers
    stay idempotent.

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
    card beats once richer cards ship), with measured durations as the fallback.

### Alternative Q: Make the video public only in YouTube Studio

*   **Pros**: No new code.
*   **Cons**: Contradicts "no step outside the app" and ties the daily cadence to Dan's hours.
*   **Reason for Rejection**: Rejected for the cons above. Publish is a third in-app click that
    updates the video's status on YouTube, with `publishAt` for a scheduled release from Stage 2.

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
| HeyGen render `failed` | `failed` entry in the clip state file | `in_progress` (Stage 2) / `needs_dan` (Stage 1) | "Scene N: HeyGen failed (reason); re-rendering (allowance 3 left)" | planner rows 3a to 3c |
| HeyGen render `failed` after the allowance | same | `needs_dan` | "Scene N could not be rendered after 4 attempts" | Dan edits the line or raises the allowance; Advance |
| HeyGen network error, timeout or concurrent cap | clip job `error` | `needs_dan` | "Scene N: HeyGen unreachable / cap reached; retry when ready" | Advance transfers the claim to a new job that resumes the saved render |
| Failed render is billed by HeyGen | Stage 0 measurement | | | charged in the ledger until shown otherwise |
| Two planners enqueue the same clip | job id recorded under the row lock; claim in the state file | | | one `create_video` per (key, take) |
| YouTube upload fails or quota exceeded | upload job `error` | `needs_dan` | "Upload failed: reason" | resumable upload continues from its state file on Advance |
| YouTube OAuth refresh fails | upload, publish or refresh call `error` | `needs_dan` | "Reconnect YouTube" | Dan reconnects the channel; Advance |
| Several YouTube channels connected, none named | approve-budget 409 | `script_approved` | "Name the channel in the script" | writer adds `channel` |
| Disk full | handler `error` on write | `needs_dan` | "Disk full: N GB free; purge published episodes" | Purge button on old episodes; preflight warns under 20 GB |
| Playwright or HyperFrames crash | capture or card job `error` | `needs_dan` | "Capture of <host> failed" | fix the allowlist or capture by hand; Advance |
| Whisper missing or wrong language | preflight (Stage 2); QA result | refused at create / transcript unavailable | "whisper not installed" / "transcript unreadable" | install; captions fall back to measured durations |
| Worker killed mid-step (launcher update) | stale heartbeat | `in_progress` | progress counts unchanged | `requeue_stale` re-runs the same job id; temp-plus-rename leaves no half files |
| Cut-out silently missing (`rembg` not installed) | preflight; row 2 treats a clip without `.cutout.webm` as absent | refused at create | "rembg not installed" | install the `episode` extra |
| Capture refused by the allowlist | capture job result | `needs_dan` | "Site X is not allowlisted; add it or capture by hand" | edit settings; Advance |
| Monthly ceiling reached | approve-budget 409 | `script_approved` | "Month at 398 of 400 USD" | Dan raises the ceiling or waits |
| Scheduled release cancelled in YouTube Studio | refresh still `private` after `publish_at` | `scheduled` | "scheduled release did not happen" | Publish again; never purged |
| Script text contains HTML or script | templating | | | every script-derived string is escaped; test with `<script>` |
| Allowlisted host redirects to a private address | capture request blocking | `needs_dan` | "Capture of <host> blocked a redirect" | the page is captured by hand or dropped |

--------------------------------------------------------------------------------

## Non-Functional Requirements

*   **Security and privacy.** The episode API sits behind the existing network guard (loopback
    and tailnet only). Capture jobs run Playwright with a fresh profile, refuse any URL outside the
    allowlist, block requests to non-allowlisted hosts and private ranges, abort on cross-host
    redirects, and never hold cookies or credentials. Hand-made captures live under `data_dir`,
    not under the served `assets/`. The budget approval needs a one-time token from the estimate
    response plus a present and allowed `Origin`, and is recorded on the episode so the worker
    checks a server-side record; the monthly ceiling is the backstop against a client that scrapes
    the token. Every script-derived string is HTML-escaped before it enters a HyperFrames
    composition. HeyGen, YouTube and vault secrets are untouched (0600, masked).
*   **Cost.** One confirm per episode; retries and QA re-renders charge a visible allowance; a
    monthly ceiling refuses approval; reservations are atomic; one charge per (scene, take);
    cancelled episodes keep submitted work reserved until it is charged. No MCP tool approves.
*   **Performance.** 36 HeyGen clips at `worker_concurrency = 2` run at most two at a time,
    because each `heygen_clip` blocks while polling HeyGen; Stage 0 measures HeyGen latency and the
    account's concurrent limit, and `worker_concurrency` is raised to the measured safe value for
    the Mac Studio. Scene composites are independent jobs; whether they gain from threads (Pillow
    and NumPy share one interpreter lock) is measured in Stage 1. `episode_assemble` is a single
    ffmpeg pass. Disk per episode is measured in Stage 0; workings are purged on request after
    publish. `/api/health` is polled by the editor every minute, so its preflight entries are
    existence checks only.
*   **Rollout and rollback.** Existing surfaces touched, each additive and reverted by reverting
    the commit with no data migration: migration 4 (two new tables); the clip key (take appended
    only above zero, so every existing clip keeps its name); `heygen_clip` and `youtube_upload`
    (new behaviour only when an `episode_id` is present); the worker loop (enqueues the planner
    after an episode job's error); `GET /api/recordings` (additional entries); the YouTube client
    (a new `set_status` and `video_status`); the editor's HeyGen panel (reads the USD rate from the
    estimate instead of a local constant, Stage 4); `db.row()` (decodes one more column); the
    intro file (re-rendered at 25 fps in place). The Script panel, Program window, stage and
    recordings behave as before. Episode 1 v2 is imported as a test fixture, not migrated in place.
*   **Testability.** Every handler runs under `make test` with the fake HeyGen and YouTube
    transports that `test_heygen.py` and `test_youtube.py` already use, a fake HyperFrames
    renderer hook, and synthetic clips made with ffmpeg's `lavfi`. The package imports cleanly
    without the `episode` extra, so the existing suite never depends on it.

--------------------------------------------------------------------------------

## Additional Resources

*   `CLAUDE.md`, `PLAN.md`, `docs/DESIGN.md` ("Episode production rules", "Lip-sync guard",
    "HeyGen rendering"), `docs/AGENTS.md`, `docs/AGENT_GUIDE.md`.
*   The per-directory contract READMEs under `server/src/streamstudio/` and `web/src/`.
*   `tools/compose/README.md`, `tools/compose/motion/README.md`, `tools/compose/motion/intro/README.md`.
*   Episode 1 v2: `docs/scripts/episode-01-v2.{md,json}`, `tools/compose/episode-01-v2.plan.json`,
    `tools/compose/episode-01-v2.durations.json`.
*   `docs/egm/daily-episode-factory/hypothesis.md`, `concepts_brief.md` (six Goldfish reviews),
    `zoom_out_report.md`, `comprehension_report.md`, `critic_report.md`,
    `intermediate_zoom_out_report.md`, `implementation_readiness_report.md`,
    `goldfish_review_report.md`.

## Future Improvements

*   **One compositor.** After 10 episodes, a measured side-by-side of the ported compositor and a
    frame-by-frame Playwright render of the browser stage decides whether the stage becomes the
    only renderer (Alternative D).
*   **Local voice for card scenes.** Alternative S.
*   **Non-blocking HeyGen polling.** One "submit all, then poll all" job per episode would free
    worker slots for captures and cards while HeyGen renders.
*   **Richer cards and word-placed beats** (feature ring, comparison, counter; beats on whisper
    word timings), and agent-authored storyboards through an MCP `episode_plan` action, once the
    generic card has shipped a few episodes.
*   **Re-voice an uploaded episode**, either in place (replacing the private video) or as a new
    episode created from the old script, once YouTube's rules for that are settled.
*   **Rename the editor's saved stage layouts to "sets"** in the Library tab, `/api/scenes`, the
    `scene:` artifact kind and the agent actions, as its own small change with aliases.
*   **A Library group for episodes** with an `episode.status` action, if agents or Dan need
    episodes in the artifact library beside the Episode page and MCP tools.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

Five stages (0 to 4), each ending runnable and tested. Stage 1 is the smallest version that
produces a private upload with no manual step. Files are listed once, under the stage that first
touches them; later stages extend them. Paths are relative to the repository root; paths beginning
`data_dir/` are under the configured `Settings.data_dir`. In signatures, `s` is the `Settings`
instance and `conn` an open SQLite connection. Each code item names the contract README sections
it changes, so the READMEs never lag the code by a stage.

### Stage 0: measure and install the toolchain

#### 1. `server/pyproject.toml` (Modify)

*   **Type / Scope**: Python packaging.
*   **Proposed Changes**: Add an `episode` extra: `opencv-python-headless`, `pillow`, `numpy`,
    `scipy`, `rembg`, `playwright`. Keep `media` as a subset. Regenerate `uv.lock` (file 2).
    No new dependency for word error rate or number-to-words; both are small in-package
    functions (file 38).

#### 2. `server/uv.lock` (Modify)

*   **Type / Scope**: Lockfile.
*   **Proposed Changes**: Regenerated by `uv sync --extra episode` after file 1 changes;
    committed in the same change because CI uses `--locked`.

#### 3. `Makefile` (Modify)

*   **Type / Scope**: Developer entry points.
*   **Proposed Changes**: `setup` becomes `uv sync -p 3.12 --extra episode` and runs
    `server/.venv/bin/playwright install chromium`; `test` and `setup-media` unchanged. (The
    HyperFrames workspace install for the pipeline is added in Stage 3, file 46; Stage 0 uses the
    workspace only by hand, file 8.)

#### 4. `mac/StreamStudio.app/Contents/MacOS/StreamStudio` (Modify)

*   **Type / Scope**: Bash launcher.
*   **Proposed Changes**: The launcher's step 2 (dependency install) installs `-e ".[episode]"`
    in both of its branches (`uv pip install` and `.venv/bin/pip install`) and runs
    `playwright install chromium` once per revision. Failure messages name the missing tool.
    README: `mac/README.md` "What it does when opened" step 2 and the Side Effects entry for the
    install.

#### 5. `server/src/streamstudio/core/config.py` (Modify)

*   **Type / Scope**: Settings.
*   **Proposed Changes**: `CaptureSite(BaseModel)` with `host: str` and
    `mode: Literal["auto", "manual"]`, defined above `Settings`. Add properties `episodes_dir`
    (`data_dir / "episodes"`), `cards_dir` (`data_dir / "cards"`), `sites_dir`
    (`data_dir / "sites"`); fields `capture_allowlist: list[CaptureSite] = []`,
    `hyperframes_browser: Path | None = None` (`None` means HyperFrames uses the Playwright
    Chromium that `playwright install chromium` produces; preflight reports the resolved path),
    `episode_rerender_attempts: int = 4`, `episode_rerender_usd: float = 1.5`,
    `heygen_month_ceiling_usd: float = 400`. `ensure_dirs` creates the three directories. Frame
    rate 25 fps and the HyperFrames worker count are module constants in the episode package.
    README: `core/README.md` Interface (`config.py` field list).

#### 6. `assets/brand/fonts/`, `assets/brand/music/`, `assets/brand/sfx/`, `assets/brand/voice-names.json`, `assets/brand/manifest.json` (Create); `assets/brand/danslab-intro.mp4` (Modify)

*   **Type / Scope**: Vendored assets.
*   **Proposed Changes**: Inter OTF and the four intro woff2 files; the owned music and SFX
    clips that `tools/compose/mix.py` and the intro used; the names-for-voice table; a manifest
    with name, file, sha256 and licence note for every entry and a `"bed"` key naming the music
    loop. The existing `danslab-intro.mp4` is re-rendered at 25 fps in place (file 8), so the
    editor's intro media item, the catalog entry and `web/src/agent/agent.test.ts` keep working.
    Needed by Stage 1's assemble step.

#### 7. `assets/models/haarcascade_frontalface_default.xml` (Move from `tools/compose/models/`)

*   **Type / Scope**: QA model file.
*   **Proposed Changes**: Served from `assets_dir` so the QA module loads it from `Settings`
    (used from Stage 2). It is also served at the web root like the rest of `assets/`, which is
    harmless.

#### 8. `tools/brand/make_intro.py` (Create, ported from `tools/compose/motion/intro/make_intro.py`)

*   **Type / Scope**: One-off brand generator.
*   **Proposed Changes**: Reads fonts from `assets/brand/fonts/`, writes the composition under
    `data_dir/cards/intro/`, and runs `npx hyperframes render <dir> -o assets/brand/danslab-intro.mp4 -f 25 -q delivery`
    from the HyperFrames workspace. The workspace manifest and lockfile
    (`server/src/streamstudio/episode/templates/package.json` and `package-lock.json`, pinning
    `hyperframes` and `gsap` at the versions `tools/compose/motion/README.md` names today) are
    created in this stage by this item, so the one-off Stage 0 render is `cp` of those two files
    into `data_dir/cards/`, `npm ci` there, then the command above; file 46 later makes the
    launcher and `make setup` do that copy. The `FPS = 30` constant only scales GSAP timings and
    stays. Documented as "run when the branding changes", not part of the pipeline.

#### 9. `server/src/streamstudio/episode/__init__.py`, `server/src/streamstudio/episode/preflight.py` (Create)

*   **Type / Scope**: New package and preflight.
*   **Proposed Changes**: `__init__.py` holds a docstring only. Package rule, stated in the
    docstring and enforced by a test (file 36): no module under `episode/` imports `cv2`,
    `numpy`, `scipy`, `PIL`, `rembg` or `playwright` at module level; handlers import them inside
    the function body, as `handlers._cutout_clip` does today. `preflight.check(s, stage) -> {ok, missing}`
    uses `shutil.which`, `Path.exists` and `importlib.util.find_spec` (for the `rembg`, `cv2` and
    `playwright` packages, never importing them), and checks the tools of the shipped stage: Stage 1
    ffmpeg, ffprobe, rembg, fonts, intro, plate, music manifest; Stage 2 adds whisper and the Haar
    cascade; Stage 3 adds Playwright Chromium and the HyperFrames workspace.

#### 10. `server/src/streamstudio/api/routes/system.py` (Modify)

*   **Type / Scope**: Health route.
*   **Proposed Changes**: `tools` gains `opencv`, `rembg`, `playwright_chromium`, `hyperframes`,
    `fonts`, `intro`, `plate`, `music_manifest`, each a version or path or `None`, plus
    `preflight_ok` and `missing` from `preflight.check`. README: `api/routes/README.md`
    `system.py` entries.

#### 11. `.github/workflows/ci.yml` (Modify)

*   **Type / Scope**: CI.
*   **Proposed Changes**: The server job runs `uv sync --locked -p 3.12 --extra episode` so the
    compositor and QA tests run from Stage 1; Playwright is stubbed in tests, not installed in CI.

#### 12. `docs/egm/daily-episode-factory/stage0-measurements.md` (Create)

*   **Type / Scope**: Measurement record.
*   **Proposed Changes**: On the Mac Studio: per-scene HeyGen latency, concurrent cap, minimum
    billed seconds, whether a `failed` render is billed; rembg per clip; whisper per clip; one
    HyperFrames card render; disk per episode. Compositing is measured in Stage 1 on the ported
    code. Feeds the defaults in file 5 and the hours-per-episode target in the Goals section.

### Stage 1: the thin slice, script to private upload and publish

#### 13. `server/src/streamstudio/core/db.py` (Modify)

*   **Type / Scope**: SQLite migrations and row decoding.
*   **Proposed Changes**: Migration 4 creates `episodes` (id, project_id, status, title,
    created_at, updated_at, record_json) with an index on `status`, and `heygen_ledger` (id,
    episode_id, approval_id, scene_id, take, job_id, kind `reservation | charge | release`,
    seconds, usd, at) with an index on `at` and a partial unique index
    `UNIQUE(episode_id, scene_id, take) WHERE kind = 'charge'` so a charge is written once;
    reservation and release rows are one per estimate line and carry the approval that made them
    (`approval_id`), so the same scene and take may be reserved again by a later approval. `row()`
    also decodes `record_json`. README: `core/README.md` `db.py` tables.

#### 13a. `server/src/streamstudio/core/store.py`, `server/src/streamstudio/api/deps.py` (Modify)

*   **Type / Scope**: Project listing and lookup.
*   **Proposed Changes**: `list_projects` adds `WHERE NOT EXISTS (SELECT 1 FROM episodes e WHERE
    e.project_id = p.id)`; `project_or_404` raises 404 when the project id has an `episodes` row.
    Episode-owned project rows are therefore invisible to `/api/projects`, whose `GET /{pid}`
    unpacks `latest_edl` and would fail on a row without an EDL. README: `core/README.md`
    `store.py` ("episode-owned rows are excluded"); `api/README.md` `deps.py`.

#### 14. `server/src/streamstudio/episode/contract.py` (Create)

*   **Type / Scope**: Pydantic models.
*   **Proposed Changes**: `Plan` with every key of the script contract block, typed as there
    (`lowers: list[tuple[float, float | None, str, str | None]]`, `zoom_path:
    list[tuple[float, float, float, float]]`, `glitch: list[tuple[float, float]]`, `chips_out`,
    `card_x`, `end_at`, `end_until: float | None`, `frame: tuple[float, float, float] | None`,
    `endcard: list[str] | None`, `card_template: Literal["generic"] | None`); `Scene` (id, text,
    voice, kind, site, question: int | None, reveal: bool | None, sources, plan); `Script`
    (title, version, tags, channel, look, voice_id, motion, scenes); `extra="forbid"`;
    `script_hash(script)`. Ids: scene `^s[0-9]{1,3}$`, card `^c[0-9]{1,3}$`.

#### 15. `server/src/streamstudio/episode/validate.py` (Create)

*   **Type / Scope**: Validator.
*   **Proposed Changes**: `validate(script, s) -> {errors, warnings}` keyed by scene id. Stage 1
    ships the three error rows; the warning rows land in Stage 2 (file 40). Duration estimate
    through `heygen.estimate_seconds(scene.voice or scene.text, None)`; names table from
    `assets/brand/voice-names.json`.

#### 16. `server/src/streamstudio/episode/record.py` (Create)

*   **Type / Scope**: Episode record storage.
*   **Proposed Changes**: `create(conn, s, script) -> Episode` inserts the `projects` row
    directly (`name = script.title`, no EDL version), the `episodes` row with `record_json`
    (`outputs.upload_job_id` starts unset), and the episode directory;
    ids from `ids.new_id("ep")` (`^ep_[a-z0-9]{8,40}$`). `load(conn, id)`, `save(conn, episode)`
    (inside the caller's `BEGIN IMMEDIATE`), `set_status`, `log(event)`, `list(conn)`,
    `export(s, episode)` (writes `episode.json` at purge). Helpers: `scene_key(scene, script, take)`
    (HeyGen reads `voice`, else `text`; look, voice id and motion from the script or else
    `heygen.load_config`), `inputs_hash(scene, clip_mp4, cutout_webm, card_mp4, plan)` =
    sha1 over the scene text, the two clip file checksums, the card checksum or empty, and the
    plan JSON. `to_out(episode, validation)` builds the `GET /{id}` shape.

#### 17. `server/src/streamstudio/episode/ledger.py` (Create)

*   **Type / Scope**: Cost ledger.
*   **Proposed Changes**: `month_total(conn, now)` (this month's charges plus the unconsumed part
    of every open reservation, where an open reservation is the episode's latest approval group
    of reservation rows and unconsumed = the group's usd minus charges and releases since it,
    floored at zero); `reserve(conn, episode, lines, allowance_usd) -> approval_id` where `lines`
    is `[(scene_id, take, job_id | None, seconds, usd)]`, one row per line plus one allowance row
    with `scene_id = NULL`; `charge(conn, episode, scene, take, job_id, seconds, usd, at)`
    (idempotent through the partial unique index); `release(conn, episode, approval_id, lines)`
    (one release row per released line, the allowance row included when the whole group is
    released); `release_unsubmitted(conn, episode)` releases the latest group's lines whose
    scene has no live job and no charge; `spent(conn, episode)` for `budget.spent`. This module
    imports only `core`, so a worker handler may import it inside a function body. All called
    inside the caller's transaction.

#### 18. `server/src/streamstudio/core/heygen.py` (Modify)

*   **Type / Scope**: HeyGen client and helpers.
*   **Proposed Changes**: `item_key(look, voice, script, motion, silent_s, take=0)` appends
    `take` to the hashed list only when it is above zero, so today's keys are unchanged (tested).
    `USD_PER_S = 0.0385` and `WORDS_PER_S = 2.5` move here from the route and the panel;
    `estimate_seconds(script, silent_s) -> float` (the route's formula: `silent_s`, else
    `max(2.0, words / 2.5 + 0.6)`); `estimate(items: list[dict]) -> {seconds, usd, clips, with_motion}`
    over plain dicts with `script`, `silent_s`, `motion`. README: `core/README.md` `heygen.py`
    interface and the key invariant.

#### 19. `server/src/streamstudio/api/routes/heygen.py` (Modify)

*   **Type / Scope**: HeyGen route.
*   **Proposed Changes**: Maps `Item` to dicts and uses `core.heygen.estimate`; `Item` gains
    optional `take`; the response includes `usd`. README: `api/routes/README.md` `heygen.py`
    (`WORDS_PER_S` moves).

#### 20. `server/src/streamstudio/api/routes/episodes.py` (Create)

*   **Type / Scope**: FastAPI router, prefix `/api/episodes`.
*   **Proposed Changes**: `POST /` (preflight 503 with the missing names, validate 422, create),
    `GET /`, `GET /{id}` (pure; returns `EpisodeOut` = the record without `budget.confirm_token`
    plus `progress: {clips, qa, composed, total}`, `validation: {errors, warnings}`,
    `next_action: str | None`, `last_log: str | None`), `PUT /{id}/script` (returns the episode
    to `draft`; when the script hash changes, unlinks `final.mp4`, `final.srt` and `kit.json` and
    clears `outputs.recording_id`; 409 while `outputs.upload_job_id` names a job whose
    `jobs.status` is `queued` or `running`, and from `uploaded_private` on),
    `POST /{id}/approve-script`,
    `GET /{id}/estimate` (issues `confirm_token`, ten-minute expiry), `POST /{id}/approve-budget`
    (requires the token, and an `Origin` header that is present and passes
    `netguard.origin_allowed(origin, s.extra_hosts)`, since the middleware treats a missing
    header as a non-browser request; under the row lock resolves `youtube.pick_channel(s.data_dir, script.channel)`
    with 409 when it raises, recomputes the month's total, refuses with 409 over the ceiling,
    reserves one line per distinct (clip key, take): every live `heygen_clip` job plus every
    scene without a clip and without a live job for its current key, then releases any previous
    reservation, writes `outputs.channel` and
    `budget.approved_at`), `POST /{id}/publish` (Stage 1: publish
    now only; `publish_at` accepted from Stage 2), `POST /{id}/advance`, `POST /{id}/purge`.
    Stage 2 adds `POST /{id}/refresh`, `POST /{id}/cancel`, `GET /{id}/qa/{scene}.jpg`. Ids
    validated by the regexes in files 14 and 16. README: `api/routes/README.md` new section;
    `api/README.md` router list.

#### 21. `server/src/streamstudio/api/main.py` (Modify)

*   **Type / Scope**: App factory.
*   **Proposed Changes**: Import and mount `episodes.router`. README: `api/README.md`
    ("mounts exactly these routers").

#### 22. `server/src/streamstudio/worker/handlers.py` (Modify)

*   **Type / Scope**: Existing job handlers.
*   **Proposed Changes**: `heygen_clip` accepts `take`, `episode_id` and `scene_id`; with an
    `episode_id` it:
    *   writes a claim (its job id) into `data_dir/heygen/<key>.json` before `create_video`, and
        returns as a no-op if the file holds another job's claim whose job is queued or running;
    *   never unlinks the state file; on HeyGen `failed` it writes `{failed: reason, at}` there
        and returns the same dict;
    *   writes the ledger charge for (`episode_id`, `scene_id`, `take`) (measured duration for
        `completed`, estimated seconds for `failed`) through `streamstudio.episode.ledger`,
        imported inside the function body (the ledger imports only `core`, so there is no cycle
        and no heavy import);
    *   enqueues `episode_advance`.
    `youtube_upload` with `payload.episode_id` enqueues `episode_advance` on return.
    `store.enqueue` gains an optional `max_attempts` stored in the payload (honoured by
    `run_one`, file 23). README: `worker/README.md` Invariants for `heygen_clip` (the state file
    is no longer deleted on `failed` for episode jobs) and `youtube_upload`.

#### 23. `server/src/streamstudio/worker/main.py` (Modify)

*   **Type / Scope**: Worker loop.
*   **Proposed Changes**: `run_one` honours a per-job `max_attempts` from the payload when
    present, and after `fail_job` enqueues `episode_advance` when the payload carries
    `episode_id`. `requeue_stale` is unchanged: a stale running job is re-queued under the same
    id regardless of attempts, which is correct because the claim and the saved `video_id` belong
    to that id. Imports `streamstudio.episode.handlers` so the episode handlers register
    (file 24). README: `worker/README.md` `main.py` invariants.

#### 24. `server/src/streamstudio/episode/handlers.py`, `server/src/streamstudio/episode/planner.py` (Create)

*   **Type / Scope**: Handler registration and the `episode_advance` handler.
*   **Proposed Changes**: `episode/handlers.py` decorates the episode handlers with
    `worker.handlers.handler(...)` and imports `planner`, `compose`, `mix`, `kit`, `publish`,
    `qa`, `capture`, `cards` lazily inside each function, so importing it pulls no heavy library
    and `worker/handlers.py` never imports the episode package at module level (its one
    function-level import is `episode.ledger`, file 22, so there is no cycle). `planner.py`
    implements the condition table in the Technical Plan under the `episodes` row lock: Stage 1
    ships rows 1 (the `needs_dan` branch), 2 (with claim transfer for an errored job that saved a
    `video_id`), 6 (clip-and-cut-out predicate), 7, 8, 9, 10 and 11; Stage 2 replaces row 1 with
    3a to 3c and row 6's predicate with QA. Job ids are recorded in `scenes_state` before
    enqueueing; the only `jobs` read is `status` of a recorded id; reservation release at
    `uploaded_private`. README: `worker/README.md` handler list; `episode/README.md`.

#### 25. `server/src/streamstudio/episode/compose.py` (Create)

*   **Type / Scope**: `scene_compose` handler and compositing functions.
*   **Proposed Changes**: The compositing of `tools/compose/render.py` (plate, seated cut-out,
    table overlays, zoom, glitch, neon frame, card slice) as functions with `Settings` injected.
    Decoding: the cut-out through `ffmpeg -c:v libvpx-vp9 -i <key>.cutout.webm -vf fps=25 -f rawvideo -pix_fmt rgba -`
    (the built-in VP9 decoder drops alpha) and the clip through `ffmpeg -i <key>.mp4 -vf fps=25 -f rawvideo -pix_fmt rgb24 -`,
    consumed in lock-step; seat geometry (`scale`, `hands_y`, `x`, `HANDS_IN_CLIP = 0.85`) from
    `assets/studio/plate-landscape-final.json["seat"]`; frame count `round(duration * 25)`;
    audio mapped from the clip with `-shortest`. `render/lipsync.py:guard_cue` is called per scene
    with the cue derived from the scene kind and the voice literal `"clip"`; degraded scenes use
    `pip_rect`. `render.lipsync` imports PIL at module level, so it is imported inside the
    handler and the compositing functions, never at the top of `compose.py` (file 36 checks).
    Output `scenes/<scene>.mp4` via temp plus rename; `inputs_hash` recorded. Stage 1
    composes avatar scenes on the plate; card slices arrive in Stage 3. README:
    `render/README.md` names the compositor as a `lipsync.py` caller; `episode/README.md`.

#### 26. `server/src/streamstudio/episode/mix.py` (Create)

*   **Type / Scope**: `episode_assemble` handler.
*   **Proposed Changes**: Concat demuxer over `scenes/*.mp4` with frame-count check; the intro
    from `assets/brand/danslab-intro.mp4`; the bed named by `manifest.json`; SFX from the cue
    table (`question` → riser at -1.3 s and pop at +0.3 s, `whoosh_at` → whoosh, card `navigate`
    → page sound, `counter` → sparkle at -0.1 s, `reveal` → deep impact at +0.3 s, `glitch` →
    glitch hit, `endcard` → warm shimmer; the sounds and offsets are those of
    `tools/compose/mix.py`, with the pop no longer tied to a lower-third's start) as a module
    constant; the levels table as one
    constant dict; writes `final.mp4` and `final.cues.json`. Stage 1 ships intro, bed and the
    plan cues; card cues arrive in Stage 3.

#### 27. `server/src/streamstudio/episode/kit.py` (Create)

*   **Type / Scope**: `episode_publish_kit` and `episode_register` handlers.
*   **Proposed Changes**: `kit.json = {title, description, tags, chapters, notes}`; chapters
    `["0:00 Intro", "<m:ss> <first sentence of the question scene>", ...]`, folded under 10 s,
    emitted only when at least three remain (port of `web/src/publish/kit.ts` chapter rules),
    otherwise `notes` says why; `final.srt` with at most two lines of at most 42 characters per
    caption, timed from `qa/<scene>.words.json` when present, else measured duration split by
    characters; every time offset by the intro's ffprobe duration plus the preceding scenes'
    durations. Registration moves `final.mp4` to `recordings/rec_<stamp>-ep.mp4`, writes
    `.srt`, `rec_<stamp>-ep.transcript.json` as `{"language": "en"}` (so `youtube_upload`
    attaches captions in the right language) and `rec_<stamp>-ep.episode.json`, records the path
    in `outputs.final_mp4`, returns the recording id.

#### 28. `server/src/streamstudio/api/routes/recordings.py` (Modify)

*   **Type / Scope**: Recordings listing.
*   **Proposed Changes**: `list_recordings` also lists `rec_*.episode.json` entries (id, `mp4`,
    `mp4_bytes`, `transcript`, `source_bytes: null`, `episode: <id>`), merged with the takes and
    sorted by id descending, so the existing ordering test and the YouTube take picker keep
    working. README: `api/routes/README.md` `recordings.py` entry.

#### 29. `server/src/streamstudio/core/youtube.py` (Modify)

*   **Type / Scope**: YouTube client.
*   **Proposed Changes**: `set_status(api, video_id, privacy, publish_at=None)` calling
    `videos.update` with part `status` through `Client.json`; `video_status(api, video_id) -> {privacy, publish_at}`;
    `clean_meta` validates `publish_at` (RFC 3339, future) when given (used from Stage 2).
    README: `core/README.md` `youtube.py` interface.

#### 30. `server/src/streamstudio/episode/publish.py` (Create)

*   **Type / Scope**: Publish helper and `episode_purge` handler.
*   **Proposed Changes**: `publish(conn, s, episode, publish_at)` (called by the route; sets
    `published`, or `scheduled` from Stage 2); `episode_purge` removes `caps/`, `cards/`,
    `scenes/`, `qa/` (including per-take transcripts and SRTs) and mix intermediates, writes
    `episode.json`, keeps `kit.json`, `final.srt` and the registered recording, logs bytes freed;
    runs only from `published` or `cancelled`. `refresh_status` arrives in Stage 2 (file 42).

#### 31. `web/src/episode/EpisodePage.tsx`, `web/src/episode/api.ts`, `web/src/episode/README.md`, `web/src/index.css` (Create; Modify)

*   **Type / Scope**: React view, client and styles.
*   **Proposed Changes**: Reachable at `?episode=<id>`; Stage 1: the scene list with errors,
    the three buttons (Approve script, Approve budget with the estimate screen and the token,
    Publish now); polls `GET /api/episodes/{id}` every 5 s while `in_progress`; usable at a 390 px
    wide viewport (`index.css` gains a `.episode` breakpoint). `api.ts` exports `getEpisode`,
    `putScript`, `approveScript`, `estimate`, `approveBudget(token)`, `publish(publish_at?)`,
    `advance`, `purge`, and from Stage 2 `refresh`, `cancel`. Stage 2 adds warnings, inline edit,
    per-scene state chips, contact-sheet links, the "Needs you" panel and the schedule control.
    README: `web/src/README.md` subdirectory list.

#### 32. `web/src/App.tsx` (Modify)

*   **Type / Scope**: Routing.
*   **Proposed Changes**: `?episode=` renders `EpisodePage` before the editor branch, like
    `?render=1` and `?program=1`. README: `web/src/README.md` `App.tsx` entry.

#### 33. `server/tests/test_episodes.py` (Create)

*   **Type / Scope**: Unit and API tests.
*   **Proposed Changes**:
    *   contract round-trip including every `Plan` key and `card_template`;
    *   the converted Episode 1 v2 fixture validates under `extra="forbid"`;
    *   validator error rows;
    *   create, approve-script, estimate with token;
    *   approve-budget refused without the token, with a missing `Origin`, and with a
        disallowed `Origin` (tests send `Origin: http://testclient`);
    *   approve-budget 409 over the ceiling and 409 when two channels are connected and none is
        named;
    *   two queued approvals cannot both pass against the same remaining balance;
    *   a charge dated in the month after its approval counts in that month;
    *   a second approval reserves each (clip key, take) once: an unchanged scene mid-render is
        reserved once, an edited scene with its old render running is reserved for both keys,
        then the previous reservation is released and the month's total never drops below the
        live job's estimate in between;
    *   `PUT /script` returns an `in_progress` episode to `draft`, unlinks `final.mp4` and
        `kit.json` and clears `outputs.recording_id` when the hash changes, and is refused while
        an upload job is live and after `uploaded_private`;
    *   an episode's project row is absent from `GET /api/projects` and `GET /api/projects/{pid}`
        answers 404 for it;
    *   publish now through the fake YouTube transport sets `published`;
    *   `GET /{id}` has no side effects and returns the `EpisodeOut` shape;
    *   preflight 503 with missing names.

#### 34. `server/tests/test_episode_pipeline.py` (Create)

*   **Type / Scope**: Worker tests.
*   **Proposed Changes**:
    *   one `create_video` per (key, take) with two planners running at once;
    *   a HeyGen `failed` is recorded in the state file, charged once, parks the episode in
        `needs_dan`, and is not re-enqueued;
    *   a worker-level error enqueues the planner and parks the episode; Advance after a network
        error resumes the saved render without a second `create_video` (claim transfer);
    *   `max_attempts = 1` honoured; a stale requeue keeps the job id;
    *   compose on the plate with the guard; a frame-count mismatch fails concat;
    *   kit chapters from question markers, folding and the fewer-than-three rule, SRT timing
        fallback, intro offset;
    *   registration names, sidecar and language file; a registered episode appears in
        `GET /api/recordings` in the right order;
    *   the upload handler enqueues the planner and the planner sets `uploaded_private` and
        releases the reservation;
    *   purge keeps the right files and writes the export.

#### 35. `server/tests/fixtures/episode-01-v2/`, `server/tests/convert_episode1.py` (Create)

*   **Type / Scope**: Test fixture and its one-off converter.
*   **Proposed Changes**: Copies of `docs/scripts/episode-01-v2.json`,
    `tools/compose/episode-01-v2.plan.json`, `episode-01-v2.durations.json`, and the converted
    `script.json`. Converter rules: plan `question: true` → scene `question: n` (counted from 1);
    `kind: card` for entries with `still`/`tag`/`video`; `site` from a hand-written table of the
    storyboard groups in `cards_v2.py`; `video`, `video_at`, `cont`, `still`, `tag`, `intro_zoom`
    dropped (cards are derived from `kind: card` + `site`); the fixture's own `kind` key is
    consumed by the scene, never copied; every other key copied into `plan`. A test asserts the
    converted fixture validates against `Script` (`Plan` forbids extra keys).

#### 36. `server/tests/test_episode_imports.py` (Create)

*   **Type / Scope**: Package rule test.
*   **Proposed Changes**: Imports every module under `streamstudio.episode` with `cv2`, `numpy`,
    `scipy`, `PIL`, `rembg` and `playwright` blocked in `sys.modules` and asserts success and no
    files written; `import streamstudio.worker.handlers` succeeds the same way.

### Stage 2: QA, allowance, degrade, scheduled publish, cancel, status

#### 37. `server/src/streamstudio/episode/qa.py` (Create)

*   **Type / Scope**: `scene_qa` handler.
*   **Proposed Changes**: `check_clip(mp4, cascade) -> dict` ported from
    `tools/compose/qa_avatar.py:check`; `scene_qa` compares against `reference`, writes
    `qa/<scene>.json` and `qa/<scene>.jpg`, calls
    `transcribe.transcribe(clip, qa/<scene>.t<take>.words.json, qa/<scene>.t<take>.srt, s)`,
    copies the accepted take's words to `qa/<scene>.words.json`, catches `TranscribeError` as the
    issue "transcript unavailable" with `words: null` and the verdict unchanged, computes the word
    error rate with an in-package Levenshtein over word lists after voice-names and an in-package
    English number-to-words normalisation (integers, decimals, percentages, years) (verdict `LOOK`
    over 25 %; `FAIL` only when a re-rendered take also differs from the first take by more than
    25 %), returns `{status, issues, words}`.

#### 38. `server/src/streamstudio/episode/planner.py` (Modify)

*   **Type / Scope**: Planner rows 3, 3a to 3c and the QA predicate of row 6.
*   **Proposed Changes**: QA enqueueing, `reference` medians after the first full pass, the
    allowance (attempts and USD), `take + 1` re-renders with claim handling, `degraded` for QA
    failures, `needs_dan` for render failures after the allowance, `release_unsubmitted` on
    cancel.

#### 39. `server/src/streamstudio/episode/validate.py` (Modify)

*   **Type / Scope**: Remaining validator warnings.
*   **Proposed Changes**: Length, question and reveal presence, claim sources, voice-names
    spelling, the consecutive-avatar 8 s rule.

#### 40. `server/src/streamstudio/api/routes/episodes.py` (Modify)

*   **Type / Scope**: Stage 2 routes.
*   **Proposed Changes**: `POST /{id}/refresh` (calls `refresh_status`; a repeat within five
    minutes is a no-op), `POST /{id}/cancel`, `GET /{id}/qa/{scene}.jpg`; `publish` accepts
    `publish_at`.

#### 41. `server/src/streamstudio/mcp.py` (Modify)

*   **Type / Scope**: MCP server.
*   **Proposed Changes**: Tools `episode_create(script)`, `episode_list()`,
    `episode_status(id)`, `episode_estimate(id)`, `episode_refresh(id)`; `youtube_upload`
    unchanged. No approve, publish, cancel or purge tool; the descriptions say so. README:
    `server/src/streamstudio/README.md` `mcp.TOOLS`.

#### 42. `server/src/streamstudio/episode/publish.py` (Modify)

*   **Type / Scope**: Scheduled publish.
*   **Proposed Changes**: `publish` handles `publish_at` (sets `scheduled`);
    `refresh_status(conn, s, episode)` records `last_checked_at`, sets `published` on an
    observed `public`, logs "scheduled release did not happen" when the time has passed.

#### 43. `web/src/episode/EpisodePage.tsx` (Modify)

*   **Type / Scope**: Full status page.
*   **Proposed Changes**: Warnings beside scenes, inline edit of `text`, `voice`, `sources`,
    per-scene state chips with progress counts, contact-sheet links, the "Needs you" panel with
    Advance and Send-back-to-writer, the schedule control, a Cancel button, one refresh call when
    a `scheduled` episode is opened after `publish_at`, and "Published. Purge workings?".

#### 44. `server/tests/test_episode_qa.py` (Create)

*   **Type / Scope**: Tests.
*   **Proposed Changes**:
    *   QA on synthetic clips (ffmpeg `lavfi` frames with and without a face image, frozen frames,
        a glitch frame);
    *   the transcript check with a stubbed `transcribe`, including a name-heavy voice line that
        normalises to `ok` and a missing whisper recorded as "transcript unavailable";
    *   per-take transcript files survive a re-render;
    *   the planner never enqueues `scene_qa` for a scene whose state file says `failed` or whose
        clip is still rendering;
    *   a QA `FAIL` re-renders with `take+1` within the allowance; the next `FAIL` degrades;
    *   a render `failed` after the allowance parks in `needs_dan`;
    *   cancel releases only unsubmitted reservations;
    *   scheduled publish, refresh cooldown, a passed `publish_at` with a private video does not
        set `published`;
    *   every validator warning row on a minimal script.

### Stage 3: captures and the generic card

#### 45. `server/src/streamstudio/episode/capture.py` (Create)

*   **Type / Scope**: `site_capture` handler.
*   **Proposed Changes**: Playwright Chromium, fresh context, 1400 px wide viewport; a `route`
    handler resolves each request host with `socket.getaddrinfo` and aborts loopback, private and
    link-local addresses and any host not in the allowlist; aborts on a cross-host redirect;
    full-page screenshot to `caps/<urlkey>.png` and `caps/<urlkey>.json`
    (`{url, final_url, title, rects}`, with the first visible `h1` and the largest visible `img`
    by rendered area); `data_dir/sites/<urlkey>/` used when the allowlist entry is `manual`.

#### 46. `server/src/streamstudio/episode/hyperframes.py` (Create, ported from `tools/compose/motion/build.py`); `server/src/streamstudio/episode/templates/package.json`, `package-lock.json` (Create); `Makefile`, `mac/StreamStudio.app/Contents/MacOS/StreamStudio`, `server/src/streamstudio/episode/preflight.py` (Modify)

*   **Type / Scope**: Composition builder and workspace bootstrap.
*   **Proposed Changes**: `Comp.__init__(cid, dur, pages_dir, workspace)`; `write` copies gsap
    from `workspace / "node_modules/gsap/dist/gsap.min.js"`, escapes every string, and emits
    `cues.json` (`[{kind, t}]`) from `navigate`, `counter`, `ring` and `call`;
    `render(workspace, out_dir, mp4, browser, workers=4)` runs
    `npx hyperframes render <out_dir> -o <mp4> -f 25 -q delivery --video-frame-format png -w <workers>`
    from the workspace with `HYPERFRAMES_BROWSER_PATH=<browser>` in the subprocess environment
    (as `build.py` does today); a module attribute `RENDER = render` that tests replace (mirrors
    `handlers.CUTOUT`). The workspace manifest and lockfile, created by file 8 in Stage 0, ship
    in `episode/templates/` (hatchling includes them in the wheel); the launcher and `make setup`
    copy them to `data_dir/cards/` and run `npm ci` there once per revision; preflight's Stage 3
    set adds the workspace and the Chromium path. README: `mac/README.md` gains the step.

#### 47. `server/src/streamstudio/episode/cards.py` (Create)

*   **Type / Scope**: `card_render` handler.
*   **Proposed Changes**: Groups consecutive card scenes by `site`; `generic_card(comp, capture, scenes, beats) -> Comp`
    (address bar, slow scroll, one zoom to the hero rect, one callout from the scenes' escaped
    `text`, beats at measured scene boundaries); writes `cards/<card>.mp4` and `cues.json`;
    records `durations_hash`. `scene_compose` gains the card slice; `episode_assemble` reads card
    cues; the planner gains rows 4 and 5.

#### 48. `server/tests/test_episode_cards.py` (Create)

*   **Type / Scope**: Tests.
*   **Proposed Changes**:
    *   the generic card from a fixture capture with a `<script>` string escaped;
    *   `cues.json` emitted with the four kinds;
    *   allowlist refusal, private-range block and redirect abort;
    *   two scenes on one host with different paths produce two captures and each card reads its
        own;
    *   the renderer stubbed through `hyperframes.RENDER`;
    *   a card scene composed with the presenter in the small rectangle and the slice offset.

### Stage 4: hardening, documentation, removal of the hand-run pipeline

#### 49. `web/src/director/HeygenPanel.tsx` (Modify)

*   **Type / Scope**: Editor panel.
*   **Proposed Changes**: Reads `usd` from the estimate instead of the local `API_USD_PER_S`.
    README: `web/src/director/README.md` (`HeygenPanel.tsx` invariant and HTTP contract).

#### 50. `server/src/streamstudio/render/lipsync.py` (Modify); `server/tests/fixtures/lipsync_cases.json` (Create); `server/tests/test_lipsync.py`, `web/src/director/director.test.ts` (Modify)

*   **Type / Scope**: Shared guard fixtures.
*   **Proposed Changes**: `lipsync.py` gains only a docstring naming the compositor as a caller
    and the fixture. The fixture rows are `{cue, clip, voice, expect_cue, expect_pip}`; the Python
    test runs them through `lipsync.py` and `episode/compose.py`, the vitest test reads the same
    file with `fs.readFileSync(new URL('../../../server/tests/fixtures/lipsync_cases.json', import.meta.url))`
    and runs them through `types.ts:guardCue` and `cueLayouts.ts:guardLayout`, checking
    `expect_pip` as "area at most `MAX_UNSYNCED_AREA`" on each side, so all three
    implementations are tested against the same cases. README: `render/README.md`,
    `web/src/director/README.md`.

#### 51. Under `tools/compose/`: `cuts.py`, `scenecut.py`, `splice.py`, `masks.py`, `peek.py`, `motion/stitch.py` (Delete)

*   **Type / Scope**: Long-take tooling.
*   **Proposed Changes**: Removed; their purpose is covered by per-scene clips, cut-outs from
    `heygen_clip`, the planner and the status page's contact sheets.

#### 52. Under `tools/compose/`: `render.py`, `qa_avatar.py`, `mix.py`, `motion/build.py`, `motion/cards.py`, `motion/cards_v2.py`, `motion/intro/make_intro.py` (Delete)

*   **Type / Scope**: Replaced by the server package, `tools/brand/` or the fixture.
*   **Proposed Changes**: Deleted after files 8, 25, 26, 35, 37, 46 and 47 land; the Episode 1 v2
    storyboards survive only as the JSON fixture (file 35).

#### 53. `tools/compose/README.md`, `tools/README.md` (Modify); `tools/compose/motion/README.md`, `tools/compose/motion/intro/README.md` (Delete)

*   **Type / Scope**: Contract READMEs.
*   **Proposed Changes**: `tools/compose/README.md` keeps the two plan JSON files' description
    and points at `server/src/streamstudio/episode/README.md`; `tools/README.md` drops the
    compose and motion entries and points at the same place; the motion and intro READMEs are
    removed with their code.

#### 54. `server/src/streamstudio/episode/README.md` (Create); `server/src/streamstudio/README.md`, `web/src/README.md`, `README.md` (Modify)

*   **Type / Scope**: EGM contract READMEs not covered by the per-item lines above.
*   **Proposed Changes**: `episode/README.md` states the package contract (handlers, planner
    rows, record, ledger, invariants, side effects, verification);
    `server/src/streamstudio/README.md` adds `episode/` to its subdirectory list; `web/src/README.md`
    adds `episode/`; the root README adds the episode as a system boundary, the new global
    invariants (planner the only writer of stage data; no episode clip without an approval; one
    charge per take) and drops "Next: YouTube upload".

#### 55. `docs/DESIGN.md` (Modify)

*   **Type / Scope**: Design reference.
*   **Proposed Changes**: "Episode production rules" gains the glossary (episode, scene, set,
    card, table overlay, take, allowance, degraded, workings, kit), the -36 LUFS bed, 25 fps, the
    allowance rule and the three operator actions (approve script, approve budget, publish); one
    sentence notes that the saved stage layouts are called sets in prose; the offline compositor
    section points at the episode package.

#### 56. `docs/AGENTS.md`, `docs/AGENT_GUIDE.md` (Modify)

*   **Type / Scope**: Agent docs.
*   **Proposed Changes**: Document the five MCP episode tools (file 41) and the script contract
    (file 14); the "what agents cannot do" list gains "approve a budget, publish, cancel or purge
    an episode".

#### 57. `CLAUDE.md`, `PLAN.md` (Modify)

*   **Type / Scope**: Project instructions and plan.
*   **Proposed Changes**: `CLAUDE.md` Layout lists `episode/`; Rules add "the planner is the
    only writer of an episode's stage data; the API writes script, budget and gate states", "no
    `heygen_clip` for an episode without `budget.approved_at`", and "no module in `episode/`
    imports a heavy library at module level". `PLAN.md` gains milestone S9 (the factory) and a
    note that Decision 6 ("record and live-stream from the start") no longer drives the roadmap.

#### 58. `server/tests/test_episode_e2e.py` (Create)

*   **Type / Scope**: End-to-end test.
*   **Proposed Changes**: The three-scene fixture from script to a registered recording, a fake
    upload and a fake publish, with fake HeyGen, fake YouTube, the stubbed renderer and synthetic
    clips; asserts one paid render per key, the guard applied to every scene (cue per kind) and
    to a degraded scene, frame counts on concat, the kit, the sidecar, the recordings listing, the
    purge.

### Verification Plan

*   **Build**: `make build` (web) and `make setup` (server, with the `episode` extra) on the Mac
    Studio; `make mac-app` then a cold start of StreamStudio.app passes the Stage 1 preflight.
*   **Unit tests**: `make test` (`pytest` in `server/`, `vitest` in `web/`), including
    `test_episodes.py`, `test_episode_pipeline.py`, `test_episode_imports.py`,
    `test_episode_qa.py`, `test_episode_cards.py`, `test_episode_e2e.py` and the shared lip-sync
    fixtures.
*   **Static analysis**: `make lint` (`ruff`, `tsc -b`, `oxlint`).
*   **Coverage requirement**: every planner row, every validator rule and every ledger rule has a
    test; the guard fixtures pass in Python and TypeScript; the import test passes without the
    `episode` extra.
*   **Integration**: the Stage 0 record (file 12) exists with real numbers; one real three-scene
    episode from script to private upload and publish on the Mac Studio with no step outside the
    app, timed, is the only paid integration check. A re-render of Episode 1 v2 from the fixture
    is optional and only on Dan's approval, since it costs about 12 USD of HeyGen and compares
    against a video made from a single long take.
*   **Success measure**: the first five daily episodes each log zero manual steps, approve-budget
    to `uploaded_private` under 12 hours, Dan's interaction under 15 minutes, HeyGen cost within
    estimate plus allowance, and no scene with a `FAIL` verdict left undegraded or unresolved.

--------------------------------------------------------------------------------

*Drafted with EGM*
