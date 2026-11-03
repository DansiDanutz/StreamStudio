# Daily episode factory

*   **Author:** Dan (DansiDanutz)
*   **Status:** Final (amended 2026-11-03: channel profiles, manual upload)
*   **Date:** 2026-11-02; amended 2026-11-03
*   **Predecessor:** [concepts_brief.md](./concepts_brief.md) (six Goldfish reviews of [hypothesis.md](./hypothesis.md))
*   **Review:** EGM Stages 5 to 9 complete; findings resolved on 2026-11-02 (see `goldfish_review_report.md`).
    The 2026-11-03 amendment (channel profiles, manual upload) was reviewed and then re-audited
    once; both are complete. Findings, their resolution and the accepted residuals are in
    `channel_profiles_review.md`.

--------------------------------------------------------------------------------

## Overview

StreamStudio becomes the machine that turns a finished script into a finished, reviewable
episode (a final MP4 with its title, description, chapters, tags and captions), once a day per
channel, on the Mac Studio. Nothing uploads to YouTube on its own: uploading is a separate click
by Dan, and making the video public is another. Nothing in the pipeline belongs to one channel: every
channel Dan builds has a **channel profile** (its presenter, voice, plate, colours, fonts, intro,
music, sound effects, production-rule thresholds, publish text, caption language and YouTube
channel), edited inside StreamStudio. DansLab is the first profile and the default: a script that
names no profile becomes a DansLab episode when it is created. A writer (Dan or an agent)
delivers a script in the shape the channel's profile sets (for DansLab, questions and answers
ending in a reveal), split into scenes of about 10 seconds. StreamStudio then runs the pipeline with that channel's
profile:

*   validates the script against the production rules;
*   shows Dan the HeyGen cost once;
*   renders every scene as its own avatar clip and checks each clip;
*   composes the studio picture around each clip;
*   adds the logo intro, the music bed and sound effects (SFX);
*   builds the title, the description with chapters, and the captions;
*   registers the final MP4 in the Library as `ready` for Dan to review;
*   uploads the video as private only when Dan clicks Upload private;
*   purges the workings (the intermediate files) when Dan asks.

Dan approves the script and the budget; the episode then builds to `ready` with no further
action. Uploading as private and publishing are two more clicks, both optional and both his.

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
a finished MP4 and kit, with two human clicks to get there, no step that spends money without
one of them, and no upload without a third.

## Goals

Each goal names its pass/fail measure. The mechanisms that meet them are in the Technical Plan.

*   **One episode a day with two clicks.** From a finished script to a `ready` episode (the
    final MP4 registered in the Library, with its kit and captions) with no action outside
    StreamStudio except Dan's two approvals (script, budget). Uploading as private and
    publishing are separate, optional clicks (Upload private, then Publish or scheduled
    publish), and nothing uploads without the first. Measured as: zero manual file moves, downloads or terminal commands per
    episode once the thin slice (Stage 1) ships; a wall-clock log per step on the Mac Studio.
*   **Overnight turnaround.** From approve-budget to `ready` in under 12 hours on the
    Mac Studio for a 36-scene episode. Stage 0 measurement refines the number; the status page
    records the actual time for every episode.
*   **Dan's time stays small.** Under 15 minutes of Dan's interaction per episode across his
    clicks (two to `ready`, up to four to a public video), measured from the status page's
    timestamps.
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
*   **Workings are purged on request once the video is public**, or from `ready` or `cancelled`
    for an episode Dan does not upload. The final MP4, the script and the episode record are kept.
*   **Any channel, no code change.** A new channel is a new profile. Dan makes it in the
    Channels page from Stage 2; in Stage 1 it is made through the channels API. No code this
    plan creates names a channel, presenter, colour, font, intro, music track or YouTube channel
    id. Those values live in profile rows and, for DansLab, in the seed folder
    `assets/channels/danslab/`. The one exception is the first-run default slug in `config.py`.
    Measured by a test that runs the Stage 1 pipeline for a second, synthetic profile and
    asserts that its plate, colours, intro, bed, caption language, description footer and
    YouTube channel are the ones in the output, and by a source scan that finds no `danslab`
    (any case) under `server/src/streamstudio/episode/`, `server/src/streamstudio/api/routes/`
    `episodes.py` and `channels.py`, `web/src/episode/` or `web/src/channels/`. The live
    studio's existing DansLab references are out of scope (see Non-Goals).
*   **DansLab stays the default.** While DansLab is the default, a script with no `profile` is
    written as a DansLab episode when it is created (a test). The DansLab seed carries the values
    Episode 1 v2 shipped with: the plate and seat, the teal-to-violet neon (`#2DE2C4` to
    `#8C64FF`), Inter, the existing logo intro with its sound, the bed at -36 LUFS, the cue
    sounds, English captions and the DansLab YouTube channel. Dan can make another profile the
    default in the Channels page.

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
*   One episode for several channels, or several presenters or languages inside one episode (each
    episode has exactly one profile, and each profile one presenter and one language); portrait
    Shorts; the local-voice cost lever for card scenes.
*   Theming the live studio (stage, Program window, overlays) from a channel profile; profiles
    drive the episode factory only in this design (see Future Improvements). The live studio's
    DansLab references stay as they are: the editor's intro media item
    (`web/src/stage/Library.tsx`, `web/src/agent/catalog.ts`, `web/src/stage/README.md` and their
    tests), the channel title in `web/src/publish/YouTubeUpload.test.tsx`, and the plate and seat
    the cut-out uses for clips rendered from the editor.
*   Quality checks in languages other than English. A profile may use any caption language, and
    captions and upload text follow it. The word-error-rate check, its number-to-words pass, the
    validator's numbers-and-rankings warning and the "Intro" chapter label are English-only in
    v1. For any other language the word-error-rate check is skipped and recorded as "not
    checked (language)", and the numbers-and-rankings warning is skipped (see Q6).
*   Deleting or cleaning up uploaded channel files. Files are kept for as long as `data_dir`
    is (see Q7).
*   Per-channel HeyGen accounts, allowances or monthly ceilings. HeyGen's key, the allowance and
    the ceiling stay global settings: one wallet pays for every channel.
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
*   **Q6. Quality checks for a non-English channel.** v1 skips the word-error-rate check and
    the numbers-and-rankings warning for any language but English (see Non-Goals). A
    non-English channel needs a number-to-words pass and claim words for its language before
    those checks can run. Dan decides when the first such channel needs them.
*   **Q7. Keeping channel files.** Uploaded channel files under `data_dir/channels/files/` are
    never deleted and are not backed up to the vault (episode workings are not either). Dan
    decides whether to vault them, and whether a "clean unused files" action is worth adding.

Q2 (allowance default), Q4 (music bed level) and Q5 (Episode 1 v2 as a fixture) from the brief are
answered in the Technical Plan and the Verification Plan. Three questions the channel-profiles
review raised are settled in "Channel profiles": the default channel is chosen in the Channels
page; several YouTube channels can be connected at once (`core/youtube.py` keeps one token file
per channel, and `pick_channel` chooses between them); and a presenter with no clip yet is
previewed as a grey silhouette.

## Critical User Journeys (CUJs)

### CUJ 1: A script becomes a finished episode with two clicks, and uploads only on a third

*   **Given**: The Mac Studio passes preflight (the tools, fonts and assets the shipped stage
    needs are present), the HeyGen API key is set, and a writer has
    posted a finished script to the episode API with scene ids, on-screen text, voice text,
    sources and site URLs.
*   **When**: Dan opens the Episode page, reads the validator's warnings next to the scenes, edits
    a line or two, and clicks Approve script; then reads one cost screen (36 scenes, 318 s, 12.25
    USD, wallet balance after, month's total after, allowance 4 re-renders / 1.50 USD) and clicks
    Approve budget.
*   **Then**: The worker renders every scene, runs QA, re-renders within the allowance, composes,
    concatenates, adds intro, music and SFX, builds the publish kit, registers the final MP4 in
    the Library and sets the episode to `ready`. Nothing is uploaded. In the morning the status
    page says "Ready: final MP4 in Library. Upload private?". Dan watches the MP4 and reads the
    kit. If he wants it on YouTube, he clicks Upload private (a YouTube channel must be connected
    by then); the episode becomes `uploaded_private`, he sees the private video link and clicks
    Publish (now, or at a chosen time from Stage 2). The page offers "Purge workings?" once the
    video is public, or from `ready` if he decides not to upload. Nothing was done outside the
    app, no render ran without the budget approval, and no upload ran without Upload private.

### CUJ 2: A scene fails QA at 02:00

*   **Given**: An episode is rendering overnight; the allowance is 4 re-render attempts, shared by
    the whole episode.
*   **When**: Scene 17 fails QA (face missing); scene 23 fails QA (frozen frame).
*   **Then**: Scene 17 is re-rendered once and passes (1 attempt used). Scene 23 is re-rendered
    three times and fails QA each time (4 attempts used; the allowance is spent). Scene 23 is
    degraded: its last clip is composed with the face in the small picture-in-picture rectangle
    over its site card or the studio plate, with a note in the episode log. The episode continues
    to `ready`. In the morning the status page says: "Scene 23 degraded to the small
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
    chapters are rebuilt; the episode is registered as the next take and returns to `ready`, as
    in CUJ 1. The same holds for an episode already `ready`, since nothing was uploaded. Editing
    an episode once Dan has clicked Upload private is refused; re-voicing after upload is out of
    scope for v1.

### CUJ 4: An agent prepares an episode and stops before the paid step

*   **Given**: An agent with MCP access and a topic.
*   **When**: It posts the script, reads the validator's warnings, fixes them, and asks for the
    estimate.
*   **Then**: The episode stays in `draft` with the estimate on the status page. The agent cannot
    approve the budget. Dan sees one panel on his phone with two buttons: Approve budget, and
    Send back to writer (which adds a note to the episode log and leaves the episode in `draft`).

### CUJ 5: Dan starts a second channel without a code change (Channels page and preview from Stage 2)

*   **Given**: DansLab is the only profile and the default; Dan has a HeyGen avatar and voice
    for the new presenter. No second YouTube channel is connected.
*   **When**: Dan opens the Channels page and duplicates DansLab under the slug (short id)
    `didyouknow`. He changes the name, presenter, voice, colours, plate and music, uploads the
    intro MP4, leaves the YouTube channel empty, and saves. A writer posts a script with
    `"profile": "didyouknow"`; another script with no `profile` arrives the same day.
*   **Then**: The preview frame shows the new look before saving. The `didyouknow` episode is
    composed on the new plate with the new colours, intro and bed, captioned in the profile's
    language, and reaches `ready`; nothing is uploaded, and the estimate screen said "Upload channel: DansLab
    (the only connected channel; this profile names none)", so Dan knows to connect and name
    the new channel before he clicks Upload private. The episode with no `profile`
    is a DansLab episode. Both share one HeyGen wallet, one allowance setting and one monthly
    ceiling. No file in the repository changed.

## Technical Plan (Architecture)

The work is staged in five stages (Detailed Implementation Plan): Stage 0 measures and installs
the toolchain; Stage 1 is the thin slice from script to a `ready` episode, with the manual
private upload and publish; Stage 2 adds
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
*   **Channel**: a show, defined by one channel profile (DansLab is one channel).
*   **YouTube channel**: the connected YouTube account an episode uploads to when Dan clicks
    Upload private. A channel's profile may name one; none needs to be connected to build.
*   **Ready**: the state of an episode whose final MP4 is registered in the Library with its
    kit and SRT, and which has not been uploaded. The pipeline stops there.
*   **Channel profile** (or **profile**): everything that makes an episode belong to one channel:
    presenter, voice, plate, colours, fonts, intro, music, SFX, production-rule thresholds, publish
    text, caption language and YouTube channel. Saved as numbered, read-only versions; editing a
    profile writes a new version. Named by a **slug**, a short id (`^[a-z0-9-]{2,32}$`).
*   **Seed**: a profile shipped in the repository under `assets/channels/<slug>/` and stored as
    version 1 on first start. DansLab is the only seed.
*   **Default profile**: the profile a script with no `profile` gets when it is created. It is
    stored in the database and changed in the Channels page; DansLab is the default on first
    start.
*   **Pinned profile**: the profile version an episode uses (`record.profile`), fixed at the
    episode's first approve-script and changed only by a repin. `script.profile` is only the slug.
*   **Repin**: replacing an episode's pinned profile with the latest version, through the **Use
    latest profile** button (`POST /api/episodes/{id}/repin`). The episode returns to `draft`.
*   **Channels page**: the editor view at `?channels=1` that lists, creates and edits profiles
    (Stage 2).
*   **SFX slot**: one of the eight named sounds in a profile (`riser`, `pop`, `whoosh`, `page`,
    `sparkle`, `impact`, `glitch`, `shimmer`). A fixed table in code says which cue plays which
    slot; the profile says which file is in each slot.
*   **Look**: in a script, `look` is a HeyGen avatar look id. In a profile, `look` is the studio
    visuals (plate, palette, fonts).
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
   │ POST /api/episodes {script}                           │ approve script · approve budget · upload private · publish
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
   │   (planner sets `ready` and stops; nothing below runs without Dan's click)
   ├─ youtube_upload (exists; + episode_id)    → video id, private; only after Upload private
   └─ episode_purge (Purge button)             → removes workings, keeps final, script, record
 Dan: POST /api/episodes/{id}/upload ──► planner enqueues youtube_upload (always private)
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
written at purge for the archive, not a live store. Migration 4 adds four tables: `episodes` (id,
project_id, status, title, created_at, updated_at, record_json), `heygen_ledger` (see "The
paid step"), and `channel_profiles` and `app_settings` (see "Channel profiles").

The record:

```text
record
  id, title, status, created_at, updated_at, last_checked_at
  script: { version, hash, title, tags, profile, look, voice_id, motion, scenes: [ scene ] }
                                                      # profile: a slug, filled in at create
  profile: { slug, version, hash, look_hash, sound_hash }   # the pin: set at the first approve-script
  budget: { approved_at, confirm_token, token_expires_at, clips, seconds, usd,
            allowance: {attempts, usd}, spent: {renders, seconds, usd} }      # spent is a projection of the ledger
  reference: { face: [x,y,w,h], lip_ratio,            # QA medians from the first full pass (Stage 2)
               presenter: [avatar_id, voice_id, motion] }   # the presenter the medians were taken with
  scenes_state: { <scene_id>: { clip_key, take, job_id, video_id, duration_s,
                                qa: ok|LOOK|FAIL|degraded|null, qa_issues: [], composed_hash, card_id,
                                qa_job_id, capture_job_id, card_job_id, compose_job_id } }
  cards: { <card_id>: { scenes: [ids], urlkey, durations_hash, cues } }
  outputs: { channel, final_mp4, final_srt, kit, recording_id, upload_requested_at,
             youtube_video_id, publish_at,
             assemble_job_id, kit_job_id, register_job_id, upload_job_id }
  log: [ { at, stage, scene?, message } ]              # plain-words events for the status page
```

Writers of the record: the API writes `script` (including the `script.profile` slug), the pinned
`profile`, `budget`, `outputs.channel`, `outputs.upload_requested_at`, the clearing of
`reference` and the gate states;
the planner is the only writer of `scenes_state`, `cards`, the other `outputs` fields, `log` and
the working states. Both hold the `episodes` row lock while writing.

States are the human gates and the terminal states only: `draft` → `script_approved` →
`budget_approved` → `in_progress` → `ready` → (`uploaded_private` → (`scheduled`) →
`published`) → `purged`, plus `needs_dan` and `cancelled`. `ready` is where the pipeline stops;
the states in brackets follow only Dan's Upload private and Publish clicks. Progress inside
`in_progress` is shown from counts in `scenes_state` ("rendering 12/36, QA 8/36, composing
3/36, assembling"), not stored. Transition rules:

*   `PUT /{id}/script` from `draft`, `script_approved`, `budget_approved`, `in_progress`,
    `ready` or `needs_dan` returns the episode to `draft`. In-flight clip jobs finish and are charged to the existing
    reservation; nothing new is enqueued until the next budget approval, which reserves one line
    per distinct (clip key, take): every live render job under its own key and take, plus every
    scene that has no clip and no live job for its current key (an edited scene whose old render
    is still running is therefore reserved twice, once per key, and an unchanged scene mid-render
    once). Only then is the previous reservation released, so submitted work never leaves the
    ledger. An edit whose script hash changes makes every output downstream of the scenes stale:
    `final.mp4`, `final.srt` and `kit.json` are unlinked and `outputs.recording_id` is cleared
    (the registered recording stays in the library as an earlier take; the next registration is
    the next take), so rows 7 to 9 of the planner rebuild them and the episode returns to `ready`.
    Once `outputs.upload_requested_at` is set, the edit is refused with 409. An edit keeps the pinned
    profile. An edit that changes `script.profile` while a pin exists is refused with 409
    ("change the channel with Use latest profile").
*   `needs_dan`: a stage job ends in `error` after its last attempt (network, tool crash, disk
    full, HeyGen cap, YouTube quota), or a render fails after the allowance is spent; planner
    rows 0, 1 and 3c set it and write the reason to `log`.
*   `POST /{id}/advance` (from `needs_dan`, after Dan acts) moves each recorded job id whose job
    ended in `error` to `prev_job_id` beside it and clears it, so the planner enqueues that job
    once more (another error parks the episode again). It then sets `uploaded_private` when the
    upload state file names a `video_id`; else `ready` when `outputs.upload_requested_at` is
    set, so row 10 enqueues the upload again and it resumes from its state file; else
    `in_progress`. Then it enqueues the planner.
*   `POST /{id}/repin {profile?}` (the **Use latest profile** button) is allowed from the same
    states as `PUT /{id}/script` (so from `ready` and `needs_dan` too). It is refused with
    409 once `outputs.upload_requested_at` is set. Under the row lock it:
    *   sets `script.profile` to `profile` when one is given (422 when no such profile exists);
    *   clears `record.profile` and `outputs.channel`;
    *   unlinks `final.mp4`, `final.srt` and `kit.json` and clears `outputs.recording_id`, always,
        so the planner rebuilds the mix, the kit and the registration;
    *   returns the episode to `draft`, with in-flight clip jobs handled as for `PUT /script`;
    *   logs "Repinned".

    The next approve-script pins the latest version. Composed scenes and card renders are kept;
    each is rebuilt only if the new pin's `look_hash` differs, because that hash is in their
    inputs. A changed presenter changes the clip keys, so new clips go through the budget screen.
    The QA `reference` is cleared at that approve-script when the presenter changes (see
    "Channel profiles").
*   `ready`: set by the planner when the final MP4 is registered with its kit and SRT; it
    releases what is left of the reservation. The status page shows "Ready: final MP4 in
    Library. Upload private?".
*   `POST /{id}/upload` (the **Upload private** button) is allowed only from `ready` and needs
    the same present-and-allowed `Origin` as approve-budget; MCP has no tool for it. Under the
    row lock it resolves the YouTube channel with
    `youtube.pick_channel(s.data_dir, pinned.youtube_channel)` (409 when that channel is not
    connected, or when the profile names none and none or several are connected), writes
    `outputs.channel` and `outputs.upload_requested_at`, and enqueues the planner. The episode
    stays `ready` until the upload lands. A second click is 409 once
    `outputs.upload_requested_at` is set, so a changed channel cannot start a second video.
*   `cancelled` (Stage 2): `POST /{id}/cancel` from any state up to and including `ready`, but
    not once `outputs.upload_requested_at` is set; releases the unsubmitted part of the
    reservation (see "The paid step") and allows purge.
*   `uploaded_private`: set by the planner when the upload's state file names a video id.
*   `scheduled` and `published`: set by the publish click and the refresh call (see "Publish").
*   `purged`: set by `episode_purge`, which only the Purge button enqueues, from `ready` (before any
    upload request), `published` or `cancelled`.

### The script contract and validator

A script is posted as JSON and stored inside the record. Shape:

```text
script: { title, version, tags?: [str], profile?: <slug>,   # omitted: the default profile's slug, written in at create
          look?, voice_id?, motion?,        # HeyGen avatar look id, voice, motion: override the profile's presenter
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
card). `card_template` accepts `generic` only in v1. `profile` names the channel profile. When it
is omitted, `POST /api/episodes` writes the current default profile's slug into
`script.profile`, and the response shows it. From then on the slug changes only through
`PUT /script` before the first pin, or through a repin after it, so changing the default never
moves an existing episode to another channel. `look`, `voice_id`
and `motion`, when present, override the profile's `presenter.avatar_id`, `presenter.voice_id`
and `presenter.motion`. The YouTube channel comes from the profile, not the script (see "Channel
profiles"). A converter imports the Episode 1 v2 files (script JSON, plan JSON, durations) into
this shape as the first test fixture, with no `profile`, so the fixture also proves the default.

The validator runs when a script is posted and on every edit, returning `{errors, warnings}` per
scene id:

| Check | Level | Rule source |
| --- | --- | --- |
| estimated length outside the profile's `rules.scene_s` (DansLab: 3 to 13 s) | warning | DESIGN rule 1 |
| the profile requires questions (`rules.question_hooks`) and no scene has `question` | warning | DESIGN rule 5 |
| the profile requires a reveal (`rules.reveal`) and no scene has `reveal` | warning | DESIGN rule 5 |
| a number, price, date, percentage or ranking word with no `sources` entry (English profiles only) | warning | brief F.18 |
| `voice` contains a name spelled the on-screen way (`presenter.voice_names`) | warning | DESIGN rule 6 |
| consecutive avatar scenes with no `plan` element whose estimated lengths sum to more than the profile's `rules.event_gap_s` (DansLab: 8 s) | warning | DESIGN rule 4 |
| `kind: card` without `site` | error | cards need a page |
| duplicate scene id | error | contract |
| both `voice` and `text` empty | error | contract |
| `profile` names no saved profile (keyed `_script`, not by scene) | error | contract |

Warnings never block approval. Errors do. Stage 1 ships the error rows; the warnings ship in
Stage 2. The thresholds and the voice-names table (`presenter.voice_names`: one entry per
product, on-screen spelling and voice spelling) come from the script's profile: its latest
version before the first approve-script, and the pinned version after. The DansLab seed carries
the values above.

### Channel profiles

A profile is a JSON document plus the files it names.

**Storage.** Profiles live in a `channel_profiles` table (slug, version, created_at, hash,
profile_json). A save inserts version N+1 and never updates a row, so an episode pinned to
version N keeps rendering with N while Dan edits.

Profile files (plate, desk, fonts, intro, music, SFX) live in one content-addressed store shared
by every profile: `data_dir/channels/files/<sha256>.<ext>`, with a `<sha256>.json` sidecar that
records the detected media type, extension, kind, size, original name and an optional licence
note. The JSON names each file by sha256. Duplicating a profile therefore copies only the JSON,
and old versions keep their files. Deleting a profile never deletes a file. `data_dir/channels/`
is not under the served `assets/`; files are read back only through
`GET /api/channels/files/{sha256}`, served with the sidecar's media type and
`X-Content-Type-Options: nosniff`.

A profile has this shape:

```text
profile:
  slug, name, language: "en",                       # caption language, BCP 47
  youtube_channel?: <UC… id>                        # a connected YouTube channel, or empty
  presenter: { name, avatar_id, voice_id, motion?, voice_names: [[on_screen, voice]] }
  look: { plate: {image, desk?, seat: {scale, hands_y, x}},                 # image files by sha256
          palette: {accent_a, accent_b, glow, panel, panel_2, outline, text, tag_text, muted},  # "#RRGGBB" or "#RRGGBBAA"
          fonts: {display?, body?, small?} }                                # OTF or TTF by sha256; at least one
  intro: { kicker, title, title_em?, tagline, logo_letter,                  # inputs of the intro template (Stage 3)
           colours: {bg, glow, accent, accent_dark, highlight, letter, title, muted},
           fonts: {serif?, serif_bold?, serif_italic?, mono?} }             # OTF, TTF or WOFF2 by sha256
  sound: { intro?: <mp4 sha256, 25 fps>, bed?: <audio sha256>,
           sfx: { riser?, pop?, whoosh?, page?, sparkle?, impact?, glitch?, shimmer? },  # audio sha256s
           levels: { intro, voice, bed, sfx } }                             # LUFS
  rules: { scene_s: [min, max], event_gap_s, question_hooks: bool, reveal: bool }
  publish: { description_footer, default_tags: [str] }
```

The end card's text is not a profile field. It belongs to the scene that shows it
(`plan.endcard` in the script).

**Required fields and defaults.** A profile must have `slug`, `name`, `presenter.name`,
`presenter.avatar_id`, `presenter.voice_id`, `look.plate.image`, `look.plate.seat` and at least
one of `look.fonts`. Every other field has a neutral default. No default is a DansLab value;
DansLab's values live only in `assets/channels/danslab/profile.json`.

| Field | Default when absent |
| --- | --- |
| `language` | `"en"` |
| `youtube_channel` | empty: at Upload private, the only connected YouTube channel; 409 there when none or several are connected |
| `presenter.motion`, `presenter.voice_names` | none, `[]` |
| `look.plate.desk` | none: no desk layer in front of the presenter |
| `look.palette` | `accent_a`, `accent_b`, `glow`, `text` and `tag_text` `#FFFFFF`; `panel` `#000000DC`; `panel_2` `#000000CD`; `outline` `#FFFFFFAA`; `muted` `#AAAAAA` |
| a missing `look.fonts` slot | the first present of `body`, `display`, `small` |
| `intro` (template inputs) | `kicker` and `tagline` empty, `title` the profile's `name`, no `title_em`, `logo_letter` the first letter of `name`; colours `bg` `#000000`, `glow` `#00000000`, `accent`, `highlight` and `title` `#FFFFFF`, `accent_dark` and `muted` `#AAAAAA`, `letter` `#000000`; fonts from `look.fonts` |
| `sound.intro`, `sound.bed` | none: no intro, no bed |
| a `sound.sfx` slot | none: that cue is silent |
| `sound.levels` | the "Default levels" table (see "Compositor") |
| `rules` | `scene_s` `[3, 13]`, `event_gap_s` 8, `question_hooks` false, `reveal` false |
| `publish` | `description_footer` `""`, `default_tags` `[]` |

A pinned profile that lacks an optional file is produced without it. Every skip writes the log
line "Profile X has no <field>; skipped", which the status page shows. All strings that reach a
composition or a caption are escaped like script strings.

**Palette.** The palette replaces every colour the compositor and the card builder carry from
`render.py` and `build.py`. Items 25 and 47 list every literal and its field.

| Field | Used for |
| --- | --- |
| `accent_a` | the start of the neon rim, the tag dot, card rings, carets and highlights |
| `accent_b` | the end of the neon rim and of the card's loading bar |
| `glow` | the pool of light under a table card |
| `panel` | the site tag's fill, the card's browser chrome and callouts |
| `panel_2` | the table card's glass fill, the card's address box |
| `outline` | the site tag's outline, the card's callout and score borders |
| `text` | every title and name |
| `tag_text` | the site tag's text |
| `muted` | the end card's small line, the card's URL |

**Hashes.** `canonical(x)` is `json.dumps(x, sort_keys=True, separators=(",", ":"),
ensure_ascii=False)`. Each version stores `hash = sha1(canonical(profile))`, which identifies the
version. Two partial hashes decide what a change rebuilds:

*   `look_hash = sha1(canonical({look, presenter.name}))`. It enters each scene's `inputs_hash`
    and each card's `durations_hash`, so a plate, seat, palette, font or presenter-name change
    recomposes scenes and re-renders cards.
*   `sound_hash = sha1(canonical(sound))`. It is recorded with the assembly inputs, so an intro,
    bed, SFX or level change rebuilds the mix.

The publish fields and `language` reach only the kit and the registration. A change to them
recomposes nothing. `profiles.latest` returns `(version, hash, Profile)`; the pin stores
`{slug, version, hash, look_hash, sound_hash}`.

**The default.** The default profile's slug is stored in the `app_settings` table under the
key `default_profile`. On first start it is `Settings.default_profile` (`danslab`). Dan makes
another profile the default with **Make default** on the Channels page
(`PUT /api/channels/default {slug}`). That is refused with 409 when the slug has no row or its
latest version lacks a required file. The default profile cannot be deleted. Health and
preflight report "default profile X missing" when the stored slug has no row.

**The seed.** On start, the API and the worker each call `profiles.ensure_seed(conn, s)`. For
every `assets_dir/channels/<folder>/profile.json` it reads the profile's slug. If
`app_settings` has no `seeded:<slug>` flag, it stores the folder's files in the shared store,
inserts version 1, and writes the flag. The flag stays when the profile is later deleted, so a
deleted DansLab is never seeded again. `ensure_seed` never overwrites a saved version, so Dan's
edits to DansLab win over the seed. It runs inside `BEGIN IMMEDIATE`, inserts with
`INSERT OR IGNORE`, writes each file to a temporary name and renames it, and skips files that
already exist. Two processes starting at once therefore give one row and no error. The loader
names no slug.

**Pinning.** The first `approve-script` copies `{slug, version, hash, look_hash, sound_hash}` of
the profile's latest version into `record.profile`. A later approve-script keeps that pin. A
`PUT /script` keeps it, and only a repin clears it. So fixing a typo never moves an episode to a
newer profile version. Every handler reads the pinned version, never the latest. A profile edit
does not touch pinned episodes. The Episode page shows "Profile changed since approval" with
the **Use latest profile** button when a newer version exists.

At approve-script, after pinning, the API also:

*   returns 409 naming the fields when `profiles.missing(s, pinned)` is not empty;
*   clears `reference` when the resolved presenter (`avatar_id`, `voice_id` and `motion` after
    the script's overrides) differs from `reference.presenter`, so planner row 3 rebuilds the QA
    medians from the next full pass instead of failing new clips against the old presenter.

The clip key is unchanged in shape. It takes the presenter's `avatar_id`, `voice_id` and
`motion` from the pinned profile unless the script overrides them. A presenter change therefore
changes the clip keys and goes back through the budget screen before any money is spent. A
colour change does not touch the clips; it only recomposes scenes, through `look_hash`.

**The YouTube channel.** `PUT /api/channels/{slug}` refuses with 422 a `youtube_channel` that
fails `youtube.CHANNEL_ID` or, when it changed from the previous version, is not among
`youtube.channels(s.data_dir)`. An empty value is allowed. Duplicating a profile clears
`youtube_channel`. YouTube gates nothing before the upload: approve-script and approve-budget
do not look at it, and an episode builds to `ready` with no YouTube channel connected. The
estimate screen shows, as information only, the channel Upload private would use: "Upload
channel: <title>" for the profile's channel; when the profile names none, the channel
`pick_channel` would choose ("Upload channel: <title> (the only connected channel; this profile
names none)"); otherwise "Upload channel: not connected (connect before uploading)", or, with
several connected and none named, "Upload channel: several connected; name one in the
profile". The channel is resolved, with its 409s, only when Dan
clicks Upload private (`POST /api/episodes/{id}/upload`). The Channels page warns when two
profiles name the same YouTube channel, or when a profile names none.

**The presenter.** When `presenter.avatar_id` changes and the HeyGen key is set, `PUT` checks
the id against `heygen.Client.looks()` and returns 422 when HeyGen answers without it. When HeyGen
cannot be reached the save goes through with a warning in the response. The HeyGen client has no
voice list, so `voice_id` is not checked; the estimate screen shows the presenter's name,
avatar id and voice id.

**The intro.** A profile's `sound.intro` is an MP4 at 25 fps. It is uploaded, or, from Stage 3,
rendered from the profile's `intro` block by `channel_intro`. The template is the composition of
`tools/compose/motion/intro/make_intro.py`, moved into the server package as
`server/src/streamstudio/episode/intro_comp.py`; the `intro` block covers everything that file
varies (eight colours, four fonts, the logo letter, kicker, title, emphasised title and tagline).
The template renders a silent video, so `channel_intro` mixes the profile's `riser`, `pop`,
`shimmer`, `whoosh` and `impact` slots at the offsets `make_intro.py` prints. DansLab's intro is
not rendered from its profile. Its sound was mixed by hand
(`tools/compose/motion/intro/README.md`), so the seed ships the existing
`assets/brand/danslab-intro.mp4`, converted to 25 fps with its audio kept.

**Editing.** The Channels page lists profiles. It creates one by duplicating another (the
default, unless Dan picks one), edits every field, uploads files, previews the result, and saves
a new version. The API, under `/api/channels`:

| Route | Does | Stage |
| --- | --- | --- |
| `GET /` | slug, name, latest version, default flag of every profile | 1 |
| `POST /` | create from `{slug, name, from?}`: copies the latest JSON of `from` (default: the default profile) under the new slug and name, with `youtube_channel` cleared; 409 if the slug exists; 422 for a bad slug | 1 |
| `GET /{slug}` | the latest version, or `?version=N`; 404 for an unknown slug | 1 |
| `PUT /{slug}` | save `{base_version, profile}` as a new version; 422 with the field errors (including a body slug that differs from the path); 409 "profile changed; reload" when `base_version` is not the latest | 1 |
| `PUT /default` | make `{slug}` the default | 1 |
| `PUT /files?name=<file>&role=<intro>` | upload one file as the raw request body; returns `{sha256, media_type, kind, bytes}` | 1 |
| `GET /files/{sha256}` | read a stored file | 1 |
| `POST /preview` | render an unsaved profile from the request body; returns one JPEG | 2 |
| `DELETE /{slug}` | delete a profile (rules below) | 2 |
| `POST /{slug}/intro` | render the intro from the `intro` block | 3 |

The slugs `default`, `files` and `preview` are reserved (422), and the router declares those
routes before `/{slug}`.

So a second channel can run in Stage 1 by saving a profile and uploading its files through the
API. The owner's requirement, creating and changing a channel inside the studio, is met at the
end of Stage 2, when the Channels page ships.

Every `POST`, `PUT` and `DELETE` needs an `Origin` header that is present and passes
`netguard.origin_allowed`. The guard returns true for a missing header (`core/netguard.py:69-71`),
so the route checks presence itself, as approve-budget does. MCP gains `channel_list` and
`channel_get` in Stage 2, both read-only; agents name a profile in a script but cannot edit one.

**Uploads.** `PUT /api/channels/files` avoids a multipart parser. It streams the raw body to
`data_dir/channels/tmp/<uuid>` as `api/routes/recordings.py:upload` does, hashing as it goes. It
returns 413 when the count passes 200 MB, 415 when the name's extension is not allowed, and 422
when the file is not what its extension says:

| Kind | Extensions | Check |
| --- | --- | --- |
| image | png, jpg, jpeg, webp | Pillow opens and verifies it, format PNG, JPEG or WEBP |
| font | otf, ttf, woff2 | magic bytes: `OTTO` (OTF), `00 01 00 00` or `true` (TTF), `wOF2` (WOFF2) |
| audio, video | mp3, wav, m4a, aac, flac, ogg, mp4, mov | `ffprobe -protocol_whitelist file` with no network, and `format_name` in an allowlist (mov/mp4 family, wav, mp3, aac, flac, ogg) |

The file is renamed to `<sha256>.<ext>`, or dropped when that file already exists. With
`role=intro`, `channel_files.normalise_intro` first re-encodes the video to 25 fps, keeping its
audio, and the stored sha256 is that of the result. `PUT /{slug}` checks each field against its
kind: a plate must be an image, `look.fonts` must be OTF or TTF (the compositor draws with
Pillow), `intro.fonts` may also be WOFF2, `sound.intro` must be a video at 25 fps, and the bed and
SFX must be audio.

**Preview.** `POST /api/channels/preview` takes the unsaved profile as its body and writes
nothing. It returns one 1920x540 JPEG: an avatar frame on the left and a card frame on the right.
The presenter is a still at 1.0 s from the cut-out of the newest `heygen_clip` job that is
`done`, has `payload.look` equal to the form's `avatar_id`, and whose cut-out file exists.
Without one, the presenter is a neutral grey silhouette. In Stage 2 the card frame is the
compositor's card scene with a plain page, because the HyperFrames card arrives in Stage 3.

**Delete.** `DELETE /{slug}` is refused with 409 for the default profile, and with 409 listing
the episode ids when any episode in any state names the slug in `script.profile` or
`record.profile`. Otherwise it removes the slug's `channel_profiles` rows and keeps every file.
Published and purged episodes therefore always keep a readable profile.

### The planner: `episode_advance`

One handler, re-queueable at any time, that reads the record and the filesystem and decides the
next step. It never calls HeyGen, ffmpeg or a browser itself; it enqueues the handler that does
and returns. It is enqueued by the API after each approval, by every stage handler when it
finishes (including a handler that ended in `error`, which the worker loop enqueues on the
handler's behalf), and by `POST /api/episodes/{id}/advance` for a manual resume. It runs under
the `episodes` row lock and evaluates the table below top to bottom, acting on the first row
whose predicate holds for a scene or for the episode. "Live job" means a job id recorded in the
record whose `jobs.status` is `queued` or `running`. Every row that enqueues a job records the
job id in the record inside the lock (per scene: `job_id` for the clip, `qa_job_id`,
`capture_job_id`, `card_job_id`, `compose_job_id`; per episode: `outputs.assemble_job_id`,
`kit_job_id`, `register_job_id`, `upload_job_id`), and no row fires while the job it last recorded
for that scene or episode is live, so a planner run during a capture, a card render, a composite
or an assembly never enqueues the same work twice.

The planner acts only in `budget_approved` and `in_progress` (rows 0 to 9a) and in `ready` with
`outputs.upload_requested_at` set (rows 0, 10 and 11). In every other state, `draft` and
`needs_dan` included, it returns without action; Advance changes the state first. A clip job
that finishes after an edit or a repin therefore enqueues a planner that does nothing, and
`heygen_clip` still writes its ledger charge in any state.

| # | Predicate (record + files) | Action |
| --- | --- | --- |
| 0 | A job id recorded in a scene's `compose_job_id` (from Stage 2 also `qa_job_id`, from Stage 3 `capture_job_id` and `card_job_id`) or in `outputs.assemble_job_id`, `kit_job_id`, `register_job_id` or `upload_job_id` names a job in `error` (the worker has already spent its attempts) | Set `needs_dan`; log the job's error in plain words ("Upload failed: <reason>", "Scene N: compose failed: <reason>"). Nothing is re-enqueued until Advance. |
| 1 | `budget_approved` or `in_progress`; a scene's clip state file says `failed` for its current take, or its recorded job ended in `error` (Stage 1) | Stage 1: set `needs_dan`, log the reason. Stage 2: see row 3. |
| 2 | A scene has no clip (`<key>.mp4` and `.cutout.webm`) for its current take, no `failed` entry for that take, and no live job | Enqueue one `heygen_clip` (payload as today plus `take`, `episode_id`, `scene_id`, one attempt); record the job id; set `in_progress`. If the scene's `prev_job_id` (set by Advance) ended in `error` with a saved `video_id`, transfer the claim to the new job id so it resumes that render. |
| 3 (Stage 2) | A scene's clip and cut-out exist for its current take, its QA result for that take is missing, and no `scene_qa` job for it is live | Enqueue `scene_qa`; after the first full pass store the medians in `reference`, with the resolved presenter they were taken with. (A `failed` state file means no clip exists, so rows 3a and 3c, not this row, handle a failed render.) |
| 3a (Stage 2) | A scene is `FAIL`, or its clip state file says `failed`, and the allowance has attempts and USD left | Increment `take`, charge the allowance, go to row 2. |
| 3b (Stage 2) | A scene is `FAIL` and the allowance is spent | Mark the scene `degraded` (its last clip is composed in the small rectangle); log it. |
| 3c (Stage 2) | A clip state file says `failed` and the allowance is spent | Set `needs_dan` ("Scene N could not be rendered after K attempts"). |
| 4 (Stage 3) | A card's capture is missing | Enqueue `site_capture`. |
| 5 (Stage 3) | A card's capture exists and its `durations_hash` changed | Enqueue `card_render`. |
| 6 | Every scene has a clip and cut-out (Stage 1) or a QA result of `ok`, `LOOK` or `degraded` (Stage 2), and a scene's `composed_hash` differs from its `inputs_hash` | Enqueue `scene_compose` for that scene. |
| 7 | Every `scenes/<id>.mp4` is up to date and neither `final.mp4` nor `outputs.recording_id` exists | Enqueue `episode_assemble`. |
| 8 | `final.mp4` exists and `kit.json` does not | Enqueue `episode_publish_kit`. |
| 9 | `kit.json` exists and `outputs.recording_id` is unset | Enqueue `episode_register`. |
| 9a | `outputs.recording_id` is set, `kit.json` and `final.srt` exist, and the episode is `budget_approved` or `in_progress` (an approval with no new clips never passes through `in_progress`) | Set `ready`; release what is left of the reservation; log "Ready: final MP4 in Library". The planner stops here; it never enqueues `youtube_upload` on its own. |
| 10 | `outputs.upload_requested_at` is set (only `POST /{id}/upload` sets it), `outputs.recording_id` is set, the upload state file has no `video_id`, and `outputs.upload_job_id` is unset | Enqueue `youtube_upload` with `{id, channel, key: "<channel>/<rid>", meta: clean_meta(kit.title, kit.description, kit.tags, "private"), episode_id}` and record its id in `outputs.upload_job_id`. |
| 11 | The upload state file names a `video_id` | Set `uploaded_private`. |

No handler waits for another: each stage handler enqueues `episode_advance` when it finishes, the
planner counts what exists, and only the last handler of a stage finds everything present. Two
planners running at once are safe because every row records its job id inside the lock and skips
while that job is live, every handler is idempotent, and the clip handler's claim stops a second
payment (see "The paid step").

### The paid step

The confirm screen is served by `GET /api/episodes/{id}/estimate`, which uses the shared estimate
logic in `core/heygen.py` (the same numbers the editor's HeyGen panel shows) and adds: the wallet
balance after this render, the month's total after this render (with the share of each
channel), the allowance, the ceiling, the "Upload channel" line described in "The YouTube channel"
(information only, never a refusal), and the presenter's
name, avatar id and voice id. The response carries a one-time `confirm_token`, stored on the
record and valid for ten minutes.

"Month after" is computed from a ledger, not from episode creation dates. The `heygen_ledger`
table holds three kinds of row, each tied to an episode, a scene, a take and a job id: a
**reservation** when a budget is approved (the estimate plus the allowance, dated when approved);
a **charge** when a render completes or fails (the billed seconds and USD, dated when the render
finished, which may fall in a later month than the approval); a **release** when unconsumed
reserved money is given back. A charge is written once per (episode, clip key): the clip key
already encodes the words and the take, so an edit that changes the words and a QA re-render that
raises the take each get their own charge, and a render still running when its scene is edited is
charged under its old key. The
unconsumed part of an episode's reservation is its latest reservation's USD minus its charges and
releases since, floored at zero. The month's total is the sum of this calendar month's charges
plus the unconsumed part of every open reservation, whatever month the episode was created in.
Seconds charged are the downloaded clip's measured duration for a completed render, and the
scene's estimated seconds for a failed one; USD is seconds times the rate. Until Stage 0 shows
otherwise, a render that HeyGen reports `failed` is charged as if billed, so the ceiling errs on
the safe side.

`POST /api/episodes/{id}/approve-budget` requires the `confirm_token` and an `Origin` header that
is present and allowed, which the Episode page sends and the MCP client does not. It runs under
the row lock, and before any reservation it checks the pinned profile again: 409 naming the
fields when `profiles.missing(s, pinned)` is not empty. It does not look at YouTube. It then
recomputes the month's total and refuses with 409 when the total plus this episode's estimate
and allowance would pass the monthly ceiling. Otherwise it writes the reservation row and
`budget.approved_at` in the same
transaction, so two approvals cannot both pass against the same remaining balance. An agent with raw HTTP access could still scrape the
token from the estimate response; the monthly ceiling is the backstop, and the ledger makes every
spend visible.

A `heygen_clip` carrying an `episode_id` behaves differently from today's handler in five ways.
It takes the plate, desk and seat it passes to the cut-out from the pinned profile, not from
`assets/studio/` and the seat literals in `worker/handlers.py:182` and `:263`; without an
`episode_id` (the editor) nothing changes. The kept `.cutout.webm` is encoded from the segmented
frames alone (`avatar/cutout.py:153`), so it does not depend on the plate; the plate only feeds
the on-plate composite that `_cutout_clip` throws away. The change stops every channel's clips
from reading DansLab's plate file, and a clip shared by two channels with the same presenter
and words stays correct for both.
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

The planner releases what is left of a reservation when the episode reaches `ready`.
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
missing the transcript is recorded as unavailable and the verdict is unchanged. The
number-to-words pass is English-only, so when the pinned profile's `language` does not start
with `en` the word-error-rate check is skipped, the issue "not checked (language)" is recorded,
and the verdict is unchanged; the transcript is still kept for caption timings. The lip-motion
heuristic is a quality check; it is not the lip-sync guard, which is a layout rule (see
"Compositor").

### Cards: `site_capture`, `card_render` (Stage 3)

A card covers a run of consecutive `kind: card` scenes with the same `site`. `site_capture` runs
the Playwright Chromium already used by `render/preview.py` with a fresh browser profile and no cookies,
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
the scene boundaries measured from the clips, drawn in the pinned profile's palette and fonts.
The pinned profile's `look_hash` is part of the card's `durations_hash`.
The generic card is a function over the composition builder, not a data template. Every script-derived string is HTML-escaped before it
enters the composition. The builder emits `cues.json` beside the MP4, a list of
`{kind: navigate | counter | ring | callout, t}` in seconds from the card's start; the mixer reads
that file. Rendering runs `npx hyperframes render` as a subprocess from the HyperFrames workspace
under `data_dir/cards/`, whose `package.json` and lockfile ship inside the server package and are
copied there by the launcher before `npm ci`, with the browser path from
`Settings.hyperframes_browser`. Richer templates and beats placed on words from the whisper
timings follow once the generic card has shipped a few episodes (Future Improvements).

### Compositor: `scene_compose`, `episode_assemble`

The compositing of `tools/compose/render.py` moves into the server package as functions taking
`Settings`, the pinned profile and a scene, with every path from settings, and the plate, seat,
fonts and colours from the profile; no channel constant remains in the code.
`scene_compose` reads the clip and its cut-out in lock-step at 25 fps (the cut-out through the
VP9 decoder that keeps alpha), seats the presenter from the profile's seat geometry, draws the plan,
and writes `scenes/<scene>.mp4` at 25 fps with the clip's audio (the clip's timing is not
changed), via a temporary file and rename. It records an inputs hash over the scene text, the
clip and cut-out checksums, the card checksum, the plan and the pinned profile's `look_hash`, so
"up to date" means inputs unchanged, and a change to a profile's sound or publish text
recomposes nothing. The seating reuses `HANDS_IN_CLIP` and `fit_cover` from `avatar/cutout.py`;
the desk comes from `look.plate.desk`, never from the sibling-file rule of `desk_layer_for`,
which cannot find a desk stored as `<sha256>.png`.

An avatar scene's frame is the plate, the presenter cut-out seated at the desk, and the table
overlays from its plan. A card scene's frame is the card video slice for that scene (offset by
the scene's start inside the card run, measured from clip durations; a card shorter than its run
holds its last frame, a longer one is cut) under the presenter in the small picture-in-picture
rectangle, plus the scene's overlays. The lip-sync guard runs for every scene before compositing:
the cue is `avatar` for avatar scenes, `content` for card scenes and `pip` for degraded scenes,
and the voice is always the clip's own, so the guard leaves these unchanged; it still runs so the
shared guard fixtures exercise the compositor and the editor's guard alike.

`episode_assemble` concatenates the scene files (identical encode settings, frame counts checked
against the measured durations), puts the profile's intro in front, and runs the mix from the
profile's levels. SFX play at the cues from each card's `cues.json` and from the plan
(`question`, `whoosh_at`, `glitch`, `endcard`, `reveal`). A fixed table, carried over from
`mix.py` with its gains, offsets and bed timing (item 26), maps each cue to one of the eight
`sound.sfx` slots and an offset; the profile chooses the file in each slot. An intro with no
audio stream contributes silence. The pinned profile's `sound_hash` is recorded with the
assembly inputs. One frame rate, 25 fps, for clips, cards, intro and final; an uploaded intro at
another rate is converted to 25 fps when it is uploaded (`channel_files.normalise_intro`).

Default levels (the defaults for every profile, and the DansLab seed's values). A profile may
change the intro, voice, bed and SFX levels; the final loudness target is fixed:

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
`final.srt`. The description ends with the profile's `publish.description_footer`; tags are the
script's plus the profile's `default_tags`, deduplicated; the caption language is the profile's
`language`. `clean_meta` cuts descriptions at 5000 bytes and tags at 500 characters
(`core/youtube.py:288-301`), so the kit shortens the body, never the footer, and writes any
dropped tag to `notes`. Chapters follow YouTube's rules as `web/src/publish/kit.ts` encodes them:
the first chapter at 0:00 ("Intro" when the profile has an intro, else the first scene's first
sentence), one per `question` scene, chapters shorter than 10 s folded into the
previous one, and none at all (with a note saying why) when fewer than three remain. Captions come
from the script's on-screen `text` (or `voice`), not from the transcript, because DESIGN rule 6
wants on-screen spellings such as "Zmarty" where the voice says "Smarty"; each caption's start
and end come from the whisper word timings of its scene when present, falling back to the
measured duration split by character count. Every time is offset by the intro's duration plus
the preceding scenes' measured durations.

`episode_register` moves `final.mp4` to `recordings/rec_<YYYYmmdd-HHMMSS>-ep.mp4`, writes
`rec_...-ep.srt`, a minimal `rec_...-ep.transcript.json` naming the profile's caption language, and
`rec_...-ep.episode.json` naming the episode, and records the path in `outputs.final_mp4`.
`finish_recording` is not run: the file is already H.264, AAC, normalised. `GET /api/recordings`
today discovers takes only through their `rec_*.source.*` upload files, which a registered
episode does not have, so the listing is extended to include `rec_*.episode.json` entries, merged
and sorted by id with the takes; a contract test asserts a registered episode appears in the
listing with `episode` set and is absent from the YouTube take picker, and the take upload
route refuses it (409, "use the episode's Upload private"), so an episode reaches YouTube only
through `POST /{id}/upload`. The vault and the `youtube_upload` job work unchanged.
The MCP `youtube_upload` tool is removed in Stage 1, and `POST /api/recordings/{rid}/youtube`
requires a present and allowed `Origin` (item 28a), and `POST /api/jobs` refuses upload, paid
and episode kinds (item 28a), so every upload, of an episode or of any other take, starts from
Dan's click in the browser. The planner sets `ready` once the recording is registered and stops. The
episode uploads only after Dan clicks **Upload private** (`POST /{id}/upload`, see "The episode
record"), and the upload is always private.

### Publish

`POST /api/episodes/{id}/publish {publish_at?}` is Dan's fourth click, after Upload private,
available from `uploaded_private`. It calls YouTube's video update (`videos.update`, part `status`) through a
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

Once Dan has clicked Upload private (`outputs.upload_requested_at` is set), `PUT /{id}/script`
and repin are refused with 409: YouTube cannot replace a video file, and a second upload is a
second video. Before that, in `ready`, both are allowed, since nothing has been uploaded. Re-voicing an uploaded episode is out of scope for
v1 (Future Improvements); a new episode from the same script reuses every unchanged clip through
the clip key.

`episode_purge` is enqueued only by `POST /{id}/purge` (the Purge button, which the page shows as
"Published. Purge workings?" once the episode is `published`, and which also works from
`cancelled` and from `ready` before any upload request, for an episode Dan decides not to
upload): it removes `caps/`, `cards/`, `scenes/`, `qa/` and the mix intermediates, writes
`episode.json` as the archive export, keeps `kit.json`, `final.srt` and the registered recording,
and logs the freed bytes.

### Status, observability, agents

The API, under `/api/episodes`: `POST /` (validate; 503 with the missing names when preflight
fails; 422 on errors; 409 naming the fields when the profile lacks a required file; create),
`GET /`, `GET /{id}`, `PUT /{id}/script`, `POST /{id}/approve-script`, `POST /{id}/repin`,
`GET /{id}/estimate`, `POST /{id}/approve-budget`, `POST /{id}/upload`, `POST /{id}/publish`,
`POST /{id}/advance`,
`POST /{id}/purge`, and from Stage 2 `POST /{id}/refresh`, `POST /{id}/cancel`,
`GET /{id}/qa/{scene}.jpg`. `GET /{id}` returns the record without the confirm token, plus
`progress` (clips, QA, composed, total), `validation` (errors, warnings), `next_action`,
`last_log`, `profile_name` and `profile_latest_version` ("Profile changed since approval" means
`profile_latest_version` is above `record.profile.version`); the Episode page, the MCP tools and
the tests all read that one shape.

The editor gets an Episode page (`?episode=<id>`, usable at a 390 px wide viewport) with the
scenes, warnings, the four buttons (Approve script, Approve budget, Upload private, Publish),
"Ready: final MP4 in Library. Upload private?" when the episode is `ready`, and a "Needs you" panel that shows the last log line and the
one action that unblocks it. In Stage 2 the MCP server gains `episode_create`, `episode_list`,
`episode_status`, `episode_estimate` and `episode_refresh`, none of which can approve, upload,
publish, cancel or purge, and the read-only `channel_list` and `channel_get`. Every job the planner enqueues carries `project_id` and
`payload.episode_id`; the worker log line includes it. `heygen_ledger` is the cost ledger;
`budget.spent` is a cached projection of it. `/api/health` reports the toolchain (ffmpeg, whisper,
rembg, OpenCV, Playwright Chromium, HyperFrames) and, as a top-level `default_profile`, whether
the default profile exists and has its required files, with cheap existence checks only.
Creating an episode also checks the named profile's required files (plate, seat, at least one
font) and refuses with 409 naming the missing ones, and a script with no `profile` while the
stored default has no row is refused with the same 409 ("default profile X missing"); 503 stays
for missing toolchain parts only.

A Library group for episodes is deferred (Future Improvements).

### Assets and toolchain

`assets/channels/danslab/` is the DansLab seed: `profile.json` (which holds the voice-names
table as `presenter.voice_names`), the plate and desk, three Inter OTF weights, the four woff2
fonts of the intro template, the owned music bed and cue sounds, a 25 fps copy of the intro and a
`manifest.json` (name, file, sha256, licence note for every file); item 6 lists each source.
Apart from the first-run default slug in `config.py`, the seed is the only place a channel's
values live in the new code. The existing `assets/brand/danslab-intro.mp4`, registered as the
editor's intro media item, stays unchanged at 30 fps for the editor; the seed's copy is that file
converted to 25 fps with its audio kept. The episode title appears on the opening table overlay.
Like the rest of `assets/`, the seed is served at the web root (`api/main.py:20-22, 54-57`);
that is accepted, because its files are already in the repository. Other channels' files are
uploaded through `/api/channels` (the Channels page from Stage 2) and never enter the repository.
`assets/models/` holds the OpenCV Haar cascade face detector. The HyperFrames workspace lives
under `data_dir/cards/` (its `package.json` and lockfile ship in the server package; the launcher
copies them and runs `npm ci` from Stage 3), so its `node_modules` is never served.
`pyproject.toml` gains an `episode` extra (OpenCV, Pillow, NumPy, SciPy, rembg, Playwright); the
Mac launcher, the Makefile and CI install it from Stage 0, and no module in the episode package
imports any of those libraries at module level, so the API and the worker start without them.
Settings: `episodes_dir`, `cards_dir`, `sites_dir`, `channels_dir`, `default_profile`
(`danslab`, the first-run value only; the live default is in `app_settings`), `capture_allowlist`, `hyperframes_browser`, `episode_rerender_attempts`,
`episode_rerender_usd`, `heygen_month_ceiling_usd`. Frame rate (25)
and the HyperFrames worker count are constants.

### The smallest version

The first episode that removes every manual step is Stage 1: the profiles table with the DansLab
seed, the channels API (list, create, read, save, make default, raw-body file upload and read), a
finished script posted to the API with error-level validation, approve-script (pinning the
profile), one estimate and approve-budget with the ledger, `heygen_clip` with the take and the
claim, `scene_compose` on the plate with the guard, concatenation, the intro and the music bed,
the kit with chapters, registration, and the stop at `ready`. Then the manual Upload private
click (private upload) and the publish-now click, with a minimal Episode page (the scene list
and four buttons: Approve script, Approve budget, Upload private, Publish). Stage 1 builds
episodes with no YouTube channel connected. A failed render or an errored job parks the
episode in `needs_dan`. Its first episodes are ones without site mentions, since still site cards
are forbidden by the production rules. A second channel can run in Stage 1 by saving a profile
and uploading its files through the API. Stage 2 adds the Channels page, preview, delete and the
MCP channel tools. The owner's requirement, that any channel is created and changed inside the
studio with no code change, is fully met at the end of Stage 2. QA, the allowance, the degrade
path, scheduled publish, cancel and the full status page are also Stage 2; cards and the intro
render are Stage 3.

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
    screenshots under an allowlist with a fresh browser profile; logged-in sites captured once by hand
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
*   **Reason for Rejection**: Rejected for the cons above. Chosen instead: profile files (an
    uploaded or once-rendered intro, the bed, the SFX) stored by sha256 and shared across
    versions; the intro texts are profile fields.

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
*   **Reason for Rejection**: Rejected for the cons above. Publish is an in-app click, after
    Upload private, that updates the video's status on YouTube, with `publishAt` for a scheduled release from Stage 2.

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

### Alternative T: Channel values in code or in one repository folder per channel

*   **Pros**: No new table, API or page; adding a channel is a pull request.
*   **Cons**: A new channel, a colour or a music change needs a commit and a release; an agent or
    Dan cannot change a channel from his phone; channel files (presenter cut-outs, licensed music)
    end up in a public repository.
*   **Reason for Rejection**: Dan asked for every channel to be changeable inside the studio.
    Profiles are data in the app; only the DansLab seed lives in the repository.

### Alternative U: Episodes follow the latest profile instead of a pinned version

*   **Pros**: An edit reaches every running episode at once.
*   **Cons**: A presenter or voice edit would change clip keys under an approved budget and render
    clips no one approved; a colour edit mid-run would give one episode two looks.
*   **Reason for Rejection**: The goal "No money without a click", and the rule that one episode
    has one look, both need the version fixed at approval. A repin is one button and goes back
    through the budget screen.

--------------------------------------------------------------------------------

## Risks and mitigations

| Failure mode | Detection | Episode state | Status page says | Recovery |
| --- | --- | --- | --- | --- |
| HeyGen render `failed` | `failed` entry in the clip state file | `in_progress` (Stage 2) / `needs_dan` (Stage 1) | "Scene N: HeyGen failed (reason); re-rendering (allowance 3 left)" | planner rows 3a to 3c |
| HeyGen render `failed` after the allowance | same | `needs_dan` | "Scene N could not be rendered after 4 attempts" | Dan edits the line or raises the allowance; Advance |
| HeyGen network error, timeout or concurrent cap | clip job `error` | `needs_dan` | "Scene N: HeyGen unreachable / cap reached; retry when ready" | Advance transfers the claim to a new job that resumes the saved render |
| Failed render is billed by HeyGen | Stage 0 measurement | | | charged in the ledger until shown otherwise |
| Two planners enqueue the same clip | job id recorded under the row lock; claim in the state file | | | one `create_video` per (key, take) |
| YouTube upload fails or quota exceeded (only after Upload private) | upload job `error` after its last attempt (planner row 0) | `needs_dan`; no new upload job until Advance | "Upload failed: reason" | Advance returns the episode to `ready` with the request kept; row 10 enqueues one upload that resumes from its state file |
| A compose, assemble, kit or register job fails | job `error` after its last attempt (planner row 0) | `needs_dan` | "Scene N: compose failed: reason" | Dan fixes the cause; Advance enqueues the job once more |
| YouTube OAuth refresh fails | upload job `error`; Publish and Refresh are synchronous and return 502 | `needs_dan` for the upload; unchanged for Publish and Refresh | "Reconnect YouTube" | Dan reconnects the channel; Advance for the upload, or clicks Publish or Refresh again |
| No YouTube channel connected, profile names none and several are connected, or its channel is not connected | profile save 422 (a changed, unconnected channel); Upload private 409 | `ready` (building is never blocked) | "Upload channel: not connected (connect before uploading)" / "Connect channel Y" | Dan connects the channel, or edits the profile and repins, then clicks Upload private again |
| An episode uploads without Dan asking | none needed: no code path sets `outputs.upload_requested_at` except `POST /{id}/upload`, which needs a browser `Origin`; MCP has no upload tool of any kind, the take upload route also needs a browser `Origin` and refuses an episode's recording, and `POST /api/jobs` refuses upload, paid and episode kinds (items 28 and 28a) | `ready` | | tests assert the planner never enqueues `youtube_upload` without `upload_requested_at`, that `mcp.TOOLS` has no upload tool, that the take upload route refuses a request with no `Origin` and an episode's recording, and that `POST /api/jobs` is 403 for `youtube_upload`, `heygen_clip` and `episode_purge` |
| Profile edited after approval | `profile_latest_version` above the pinned version | unchanged | "Profile changed since approval" | repin (back to `draft`), or do nothing: the episode keeps its pinned version, and script edits keep it too |
| Profile file missing on disk (deleted by hand) | create 409; approve-script and approve-budget 409 before any reservation; handler `error` | refused / `draft` / `needs_dan` | "Profile X is missing its plate" | upload the same file again (the same sha256 restores the pinned version), then approve again or Advance; or save a new file and repin |
| Mistyped `avatar_id` or `voice_id` | avatar id checked against HeyGen's looks on save (422); the estimate screen shows the presenter's name and ids; QA (Stage 2) finds a face that does not match `reference` | `draft` / `script_approved` | "Avatar X is not in your HeyGen account" | fix the profile and repin before approving the budget |
| The stored default names no profile | health and preflight report "default profile X missing" | creating a script with no `profile` refused with 409 | "Default profile X missing" | Dan makes another profile the default |
| One channel uses up the shared wallet or ceiling | approve-budget 409 over the ceiling | `script_approved` | "Month at 398 of 400 USD (DansLab 310, didyouknow 88)" | Dan raises the ceiling, waits, or holds one channel's episodes |
| Channel files lost with `data_dir` | none: `data_dir/channels/` is not vaulted (Q7) | episodes of that channel go to `needs_dan` | "Profile X is missing its plate" | accepted risk until Q7 is settled; the seed restores DansLab's files on a new machine |
| Uploaded music or SFX with no licence | the licence note per file, shown on the Channels page | `ready`, then `uploaded_private` | YouTube shows a copyright claim on the private video | Dan reviews the MP4 at `ready`, and the upload is private, so he sees the claim before publishing; he replaces the file and repins |
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
    and tailnet only). Capture jobs run Playwright with a fresh browser profile, refuse any URL outside the
    allowlist, block requests to non-allowlisted hosts and private ranges, abort on cross-host
    redirects, and never hold cookies or credentials. Hand-made captures live under `data_dir`,
    not under the served `assets/`. The budget approval needs a one-time token from the estimate
    response plus a present and allowed `Origin`, and is recorded on the episode so the worker
    checks a server-side record; the monthly ceiling is the backstop against a client that scrapes
    the token. Every script-derived string is HTML-escaped before it enters a HyperFrames
    composition. HeyGen, YouTube and vault secrets are untouched (0600, masked).
    Profile uploads arrive as a raw body (no multipart parser), are capped at 200 MB counted
    while streaming, and are stored by sha256 under `data_dir` (never under the served
    `assets/`). Each is accepted only when its kind checks out: Pillow for images, magic bytes for
    fonts, and `ffprobe -protocol_whitelist file` with a format allowlist for audio and video, so
    a playlist or concat file cannot make ffprobe read other files or the network. Files are
    served back only through the channels route, with the recorded media type and `nosniff`.
    Profile strings are escaped like script strings. Every profile write needs a present and
    allowed `Origin`, as approve-budget does; MCP can read profiles, not write them. The `Origin`
    check stops cross-site browser requests, not a client on the tailnet; for those, pinning, the
    budget screen (which shows the presenter), the stop at `ready` and the private upload are the
    backstop. `POST /{id}/upload` needs the same present-and-allowed `Origin` and is the only
    way an episode reaches YouTube: the take upload route
    (`POST /api/recordings/{rid}/youtube`) needs the same `Origin` and refuses an episode's
    recording, and `POST /api/jobs` accepts only free, local, non-episode kinds (403 for
    `youtube_upload`, `heygen_clip`, every episode, scene, card, site and channel kind). So no
    MCP tool and no cross-site page can upload, spend or purge; a local client that forges
    `Origin` is the accepted residual risk.
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
    existence checks only. A change to a profile's publish text or sound recomposes no scene,
    because only `look_hash` enters the scene and card hashes.
*   **Rollout and rollback.** Existing surfaces touched, each additive and reverted by reverting
    the commit with no data migration: migration 4 (four new tables: `episodes`, `heygen_ledger`,
    `channel_profiles`, `app_settings`); the clip key (take appended
    only above zero, so every existing clip keeps its name); `heygen_clip` and `youtube_upload`
    (new behaviour only when an `episode_id` is present); the worker loop (enqueues the planner
    after an episode job's error); `GET /api/recordings` (additional entries); the YouTube client
    (a new `set_status` and `video_status`); the editor's HeyGen panel (reads the USD rate from the
    estimate instead of a local constant, Stage 4); `db.row()` (decodes two more columns); the
    `/api/channels` router; `profiles.ensure_seed` at API and worker startup; `default_profile` in
    `/api/health`; the `?channels=1` view; `data_dir/channels/`; the cut-out's optional `desk`
    argument. The editor's intro file is unchanged. A revert leaves the profile rows, the settings
    row and the channel files in place, where nothing reads them. The Script panel, Program window, stage and
    recordings behave as before. Two Stage 1 changes are not additive (items 28 and 28a): the
    MCP `youtube_upload` tool is removed, and `POST /api/recordings/{rid}/youtube` requires a
    present, allowed `Origin` and refuses an episode's recording; `POST /api/jobs` also refuses
    every kind outside its allowlist with 403. Agents lose take upload and generic job
    creation; reverting the commit restores both. Episode 1 v2 is imported as a test fixture, not migrated in place.
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
*   The channel-profiles amendment's reviews: `channel_profiles_critic_report.md`,
    `channel_profiles_readiness_report.md`, and their resolution, `channel_profiles_review.md`.

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
*   **An automatic upload setting**: a per-profile or global switch that lets the planner
    enqueue the private upload on reaching `ready`, if Dan asks for it later. v1 has none.
*   **Re-voice an uploaded episode**, either in place (replacing the private video) or as a new
    episode created from the old script, once YouTube's rules for that are settled.
*   **Rename the editor's saved stage layouts to "sets"** in the Library tab, `/api/scenes`, the
    `scene:` artifact kind and the agent actions, as its own small change with aliases.
*   **A Library group for episodes** with an `episode.status` action, if agents or Dan need
    episodes in the artifact library beside the Episode page and MCP tools.
*   **The live studio themed by a profile**: the stage, Program window and overlays read the same
    palette, fonts, plate and intro, so going live on a channel looks like its episodes.
*   **Per-channel card templates and SFX cue tables**, once a second channel needs a different
    card or different cue timing rather than different sounds.
*   **Quality checks per language**: a number-to-words pass and claim words for each caption
    language a channel uses, so the word-error-rate check and the sources warning run beyond
    English (Q6).
*   **Clean unused channel files**: remove files no profile version names, and report the size of
    `data_dir/channels/` in health (Q7).

--------------------------------------------------------------------------------

## Detailed Implementation Plan

Five stages (0 to 4), each ending runnable and tested. Stage 1 is the smallest version that
produces a finished, reviewable episode (`ready`) with no manual step, and uploads it as private
only on Dan's click. Files are listed once, under the stage that first
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
    functions (file 38). No `python-multipart` either: channel uploads take a raw request body
    (item 21a), as recording uploads already do.

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
    (`data_dir / "sites"`), `channels_dir` (`data_dir / "channels"`); fields
    `default_profile: str = "danslab"` (the first-run default only; the live default is the
    `app_settings` row, item 13b; this is the one place the new code names DansLab),
    `capture_allowlist: list[CaptureSite] = []`,
    `hyperframes_browser: Path | None = None` (`None` means HyperFrames uses the Playwright
    Chromium that `playwright install chromium` produces; preflight reports the resolved path),
    `episode_rerender_attempts: int = 4`, `episode_rerender_usd: float = 1.5`,
    `heygen_month_ceiling_usd: float = 400`. `ensure_dirs` creates the four directories and
    `channels_dir / "files"` and `channels_dir / "tmp"`. Frame rate 25 fps and the HyperFrames
    worker count are module constants in the episode package.
    README: `core/README.md` Interface (`config.py` field list).

#### 6. `assets/channels/danslab/` (Create): `profile.json`, `plate.png`, `plate.desk.png`, `intro.mp4`, `fonts/`, `music/`, `sfx/`, `manifest.json`

*   **Type / Scope**: The DansLab seed profile.
*   **Proposed Changes**: `profile.json` in the shape of "Channel profiles", naming files by
    path relative to the seed folder; `ensure_seed` replaces each path with its sha256 when it
    stores the file. Every file and its source:

    | Seed file | Source | Profile field |
    | --- | --- | --- |
    | `plate.png`, `plate.desk.png` | copies of `assets/studio/plate-landscape-final.png` and `.desk.png` (the editor still serves the originals) | `look.plate.image`, `look.plate.desk` |
    | (values) | `assets/studio/plate-landscape-final.json`: scale 0.60, hands_y 0.70, x 0.47 | `look.plate.seat` |
    | `fonts/Inter-Bold.otf`, `Inter-SemiBold.otf`, `Inter-Medium.otf` | the Inter OTF release that `render.py:26` loaded from `/usr/share/fonts/opentype/inter/` on the Linux box; SIL Open Font License | `look.fonts.display`, `.body`, `.small` |
    | `fonts/newsreader-latin-500-normal.woff2`, `-600-normal`, `-500-italic`, `fonts/jetbrains-mono-latin-500-normal.woff2` | the @fontsource packages named in `tools/compose/motion/intro/README.md`; SIL Open Font License | `intro.fonts.serif`, `.serif_bold`, `.serif_italic`, `.mono` |
    | `music/ambient-pad.mp3` | `$MEDIA_LIB/music/clips/ambient-pad.mp3` (`mix.py:22, 26, 61`; `MEDIA_LIB` defaults to `/home/claude/dansidanutz/claude-youtube/media/library` on the Linux box) | `sound.bed` |
    | `sfx/riser-soft.mp3`, `pop-reveal.mp3`, `whoosh-soft.mp3`, `ui-click-soft.mp3`, `sparkle-soft.mp3`, `impact-deep-soft.mp3`, `glitch-zap.mp3`, `warm-shimmer.mp3` | `$MEDIA_LIB/sfx/clips/<name>.mp3` (`mix.py:94-118`) | `sound.sfx.riser`, `.pop`, `.whoosh`, `.page`, `.sparkle`, `.impact`, `.glitch`, `.shimmer` |
    | `intro.mp4` | `assets/brand/danslab-intro.mp4` (30 fps, AAC, 7.2 s) converted once with the settings of `channel_files.normalise_intro` (item 13c): 25 fps, audio kept | `sound.intro` |

    The values in `profile.json`: the palette `accent_a` `#2DE2C4`, `accent_b` `#8C64FF`, `glow`
    `#3CC8BE`, `panel` `#0A0C14DC`, `panel_2` `#080A12CD`, `outline` `#7C5CFFAA`, `text` `#F2F4FA`,
    `tag_text` `#ECEEF6`,
    `muted` `#AAB0C4` (item 25 maps each to its `render.py` literal); the intro block from
    `make_intro.py` (kicker `DANSLAB`, title `Build it. Show it.`, `title_em` `Sell it.`, its
    tagline, logo letter `D`, and the colours `#050404`, `#160B091A`, `#E74C3C`, `#C0392B`,
    `#D4A017`, `#FFFEF7`, `#FAFAFA`, `#B9B1A4`); the "Default levels" table; rules 3 to 13 s,
    8 s, questions and reveal on; `language: "en"`;
    `youtube_channel: "UCCPMUreEqO1x11YiAhzLusA"`; the presenter's name, voice-names table, and
    HeyGen `avatar_id` and `voice_id` copied from the keys of the same names in
    `data_dir/heygen.json` on the Mac Studio (`core/heygen.py:45-48`; ids, not secrets). The
    editor's `/api/heygen/render` still reads those keys from `heygen.json`; the two copies are
    independent from then on. `manifest.json` lists name, file, sha256 and licence note for
    every file. `assets/brand/danslab-intro.mp4` itself is not changed, so the editor's intro
    media item, the catalog entry and `web/src/agent/agent.test.ts` keep working.

    Copying the files from the Linux box is a Stage 0 task: Dan, or an agent running on the
    Linux box, copies the bed, the eight SFX and the three Inter OTFs from the source paths
    above into the seed folder. Every licence note in `manifest.json` must be filled in before
    Stage 1 starts; test 34a fails on an empty note. Needed by Stage 1.

#### 7. `assets/models/haarcascade_frontalface_default.xml` (Move from `tools/compose/models/`)

*   **Type / Scope**: QA model file.
*   **Proposed Changes**: Served from `assets_dir` so the QA module loads it from `Settings`
    (used from Stage 2). It is also served at the web root like the rest of `assets/`, which is
    harmless.

#### 8. `server/src/streamstudio/episode/templates/package.json`, `package-lock.json` (Create)

*   **Type / Scope**: The HyperFrames workspace manifest and lockfile.
*   **Proposed Changes**: No recorded version pair exists (`tools/compose/motion/README.md`
    says only `npm i hyperframes gsap`), so choosing one is a Stage 0 task. Run
    `npm i hyperframes@latest gsap@latest` in an empty `data_dir/cards/`. Build the existing
    intro composition with `tools/compose/motion/intro/make_intro.py` unchanged, copy gsap and the
    four woff2 fonts next to it as its README says, and render it with
    `npx hyperframes render <dir> -o <scratch>/intro-check.mp4 -f 25 -q delivery`. Check it plays
    at 25 fps for its full length, then commit the resulting `package.json` and
    `package-lock.json` as the templates. The render is a check only and is not shipped: the
    DansLab seed ships the existing intro (item 6). Those two files are the tested pair from then
    on; item 46 makes the launcher and `make setup` copy them and run `npm ci`, and item 46a moves
    the intro template into the server package for new channels.

#### 9. `server/src/streamstudio/episode/__init__.py`, `server/src/streamstudio/episode/preflight.py` (Create)

*   **Type / Scope**: New package and preflight.
*   **Proposed Changes**: `__init__.py` holds a docstring only. Package rule, stated in the
    docstring and enforced by a test (file 36): no module under `episode/` imports `cv2`,
    `numpy`, `scipy`, `PIL`, `rembg` or `playwright` at module level; handlers import them inside
    the function body, as `handlers._cutout_clip` does today.
    `preflight.check(s, conn, stage) -> {ok, missing}` uses `shutil.which`, `Path.exists` and
    `importlib.util.find_spec` (for the `rembg`, `cv2` and `playwright` packages, never importing
    them), and checks the tools of the shipped stage: Stage 1 ffmpeg, ffprobe, rembg, and, when
    called as `check(s, conn, stage, profiles=True)` (health only), the default profile, read with `profiles.default_slug(conn, s)` and `profiles.latest`; a missing
    row is itself an entry ("default profile X missing"), and so is each missing required file
    (plate, seat, at least one font). Stage 2 adds whisper and the Haar cascade; Stage 3 adds
    Playwright Chromium and the HyperFrames workspace
    (`data_dir/cards/node_modules/hyperframes/package.json`). Create calls it with
    `profiles=False`, so a missing default profile is never a 503; create reports it as a 409
    (item 20).

#### 10. `server/src/streamstudio/api/routes/system.py` (Modify)

*   **Type / Scope**: Health route.
*   **Proposed Changes**: `tools` gains `opencv`, `rembg`, `playwright_chromium`, `hyperframes`,
    each a version or path or `None` (versions through the existing `media.tool_version`).
    The response gains a top-level `default_profile` (`{slug, version, missing: [...]}`), plus
    `preflight_ok` and `missing` from `preflight.check(..., profiles=True)`, which health calls
    with its own connection. README: `api/routes/README.md` `system.py` entries.

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

### Stage 1: the thin slice, script to a ready episode, with manual upload and publish

#### 13. `server/src/streamstudio/core/db.py` (Modify)

*   **Type / Scope**: SQLite migrations and row decoding.
*   **Proposed Changes**: Migration 4 creates four tables:
    *   `episodes` (id, project_id, status, title, created_at, updated_at, record_json) with an
        index on `status`;
    *   `heygen_ledger` (id, episode_id, approval_id, scene_id, clip_key, take, job_id, kind
        `reservation | charge | release`, seconds, usd, at) with an index on `at`, and a partial
        unique index created as its own statement,
        `CREATE UNIQUE INDEX heygen_ledger_charge ON heygen_ledger(episode_id, clip_key) WHERE kind = 'charge'`
        (SQLite has no table-level `UNIQUE ... WHERE`), so a charge is written once per paid
        render (the key encodes words and take, so an edited scene's old and new renders are
        distinct charges); reservation and release rows are one per estimate line and carry the
        approval that made them (`approval_id`), so the same scene and take may be reserved again
        by a later approval;
    *   `channel_profiles` (slug, version, created_at, hash, profile_json) with primary key
        `(slug, version)`;
    *   `app_settings` (key primary key, value) for the default profile and the seed flags.

    `db._split` splits on `;` and strips `--` (`db.py:139-146`), so no string literal in the
    migration contains either. `row()` also decodes `record_json` and `profile_json`. README:
    `core/README.md` `db.py` tables.

#### 13a. `server/src/streamstudio/core/store.py`, `server/src/streamstudio/api/deps.py` (Modify)

*   **Type / Scope**: Project listing and lookup.
*   **Proposed Changes**: `list_projects` adds `WHERE NOT EXISTS (SELECT 1 FROM episodes e WHERE
    e.project_id = p.id)`; `project_or_404` raises 404 when the project id has an `episodes` row.
    Episode-owned project rows are therefore invisible to `/api/projects`, whose `GET /{pid}`
    unpacks `latest_edl` and would fail on a row without an EDL. README: `core/README.md`
    `store.py` ("episode-owned rows are excluded"); `api/README.md` `deps.py`.

#### 13b. `server/src/streamstudio/episode/profiles.py` (Create)

*   **Type / Scope**: Channel profile model and storage.
*   **Proposed Changes**: Pydantic `Profile` with the fields of "Channel profiles"
    (`extra="forbid"`; colours `^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$`; slug `^[a-z0-9-]{2,32}$`
    and not `default`, `files` or `preview`; file fields `^[0-9a-f]{64}$`; `youtube_channel`
    through the existing `youtube.CHANNEL_ID`; `rules.scene_s` min below max; at least one
    `look.fonts` slot). Every default is the neutral one in the "Required fields and defaults"
    table; the model holds no channel's values. Functions:
    *   `canonical(obj) -> str` (`json.dumps(obj, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False)`), `look_hash(profile)`, `sound_hash(profile)`;
    *   `latest(conn, slug) -> (version, hash, Profile) | None`, `get(conn, slug, version)`;
    *   `save(conn, s, profile, base_version) -> version`, inside `BEGIN IMMEDIATE`: 409 when
        `base_version` is not the latest; checks every named file exists in
        `channels_dir/files/` and is of its field's kind (item 13c's sidecar); checks
        `youtube_channel` and `presenter.avatar_id` as "Channel profiles" says; inserts version
        max+1 with `hash = sha1(canonical(profile))`;
    *   `duplicate(conn, s, from_slug, slug, name) -> version`: copies the JSON only, clears
        `youtube_channel`, inserts version 1;
    *   `missing(s, profile) -> [field]`: required fields whose file is absent;
    *   `default_slug(conn, s)` (the `app_settings` row, else `s.default_profile`) and
        `set_default(conn, s, slug)` (409 for no row or missing required files);
    *   `delete(conn, s, slug)`: 409 for the default; 409 with the episode ids when any
        `episodes` row names the slug in `$.script.profile` or `$.profile.slug` (by
        `json_extract`, any status); otherwise deletes the slug's rows and keeps the files;
    *   `ensure_seed(conn, s)`: for every `assets_dir/channels/*/profile.json`, inside
        `BEGIN IMMEDIATE`, skips a slug whose `seeded:<slug>` flag exists; otherwise stores the
        folder's files through `channel_files.store_path`, inserts version 1 with
        `INSERT OR IGNORE`, and writes the flag with `INSERT OR IGNORE`. It names no slug;
    *   `pinned(conn, episode) -> Profile`: the version in `record.profile`.

    `ensure_seed` is called in `create_app` after `db.migrate(c)` (item 21) and once in the
    worker's `run()` before its threads start (item 23). README: `episode/README.md`.

#### 13c. `server/src/streamstudio/episode/channel_files.py` (Create)

*   **Type / Scope**: The shared, content-addressed store of channel files.
*   **Proposed Changes**: Imports only the standard library and `core` at module level; Pillow
    is imported inside `check_image`.
    *   `store_stream(s, name, chunks, role=None) -> FileInfo`: writes the chunks to
        `channels_dir/tmp/<uuid>` while counting bytes and hashing (413 past 200 MB), checks the
        extension against the allowlist (415), checks the kind (422), and renames the file to
        `files/<sha256>.<ext>`, or drops it when that file exists. With `role="intro"` it first
        calls `normalise_intro`. It writes the sidecar `files/<sha256>.json`
        (`{media_type, ext, kind, bytes, name, note, fps, has_audio}`);
    *   `store_path(s, path) -> FileInfo`: the same for a file on disk (the seed);
    *   `check_image(path)` (Pillow verify, PNG, JPEG or WEBP), `check_font(path)` (magic bytes
        `OTTO`, `00 01 00 00`, `true`, `wOF2`), `probe_media(s, path)` (`ffprobe -v error
        -protocol_whitelist file -show_entries format=format_name:stream=codec_type,r_frame_rate
        -of json`, with `format_name` in the allowlist);
    *   `normalise_intro(s, src, dst)`: `ffmpeg -i src -map 0:v -map 0:a? -vf fps=25 -c:v libx264
        -crf 18 -pix_fmt yuv420p -c:a aac -b:a 192k dst`, so an intro at any rate is stored at
        25 fps with its audio;
    *   `path(s, sha256) -> Path`, `info(s, sha256) -> FileInfo`.

    README: `episode/README.md`.

#### 14. `server/src/streamstudio/episode/contract.py` (Create)

*   **Type / Scope**: Pydantic models.
*   **Proposed Changes**: `Plan` with every key of the script contract block, typed as there
    (`lowers: list[tuple[float, float | None, str, str | None]]`, `zoom_path:
    list[tuple[float, float, float, float]]`, `glitch: list[tuple[float, float]]`, `chips_out`,
    `card_x`, `end_at`, `end_until: float | None`, `frame: tuple[float, float, float] | None`,
    `endcard: list[str] | None`, `card_template: Literal["generic"] | None`); `Scene` (id, text,
    voice, kind, site, question: int | None, reveal: bool | None, sources, plan); `Script`
    (title, version, tags, profile: slug | None, look, voice_id, motion, scenes); `extra="forbid"`;
    `script_hash(script)`. `look`, `voice_id` and `motion`, when set, override the profile's
    presenter. Ids: scene `^s[0-9]{1,3}$`, card `^c[0-9]{1,3}$`.

#### 15. `server/src/streamstudio/episode/validate.py` (Create)

*   **Type / Scope**: Validator.
*   **Proposed Changes**: `validate(script, profile: Profile | None) -> {errors, warnings}`
    keyed by scene id, where `profile` is the pinned version after the first approve-script and
    the named profile's latest version before it; the route resolves it and passes `None` for an
    unknown slug, which gives the "names no saved profile" error under the key `"_script"`.
    Stage 1 ships the four error rows; the warning rows land in Stage 2 (file 39) with their
    thresholds and the voice-names table from `profile.rules` and `profile.presenter.voice_names`.
    Duration estimate through `heygen.estimate_seconds(scene.voice or scene.text, None)`.

#### 16. `server/src/streamstudio/episode/record.py` (Create)

*   **Type / Scope**: Episode record storage.
*   **Proposed Changes**: `create(conn, s, script) -> Episode` writes
    `profiles.default_slug(conn, s)` into `script.profile` when it is empty, then inserts the
    `projects` row directly (`name = script.title`, no EDL version), the `episodes` row with
    `record_json` (`outputs.upload_job_id` starts unset), and the episode directory;
    ids from `ids.new_id("ep")` (`^ep_[a-z0-9]{8,40}$`). `load(conn, id)`, `save(conn, episode)`
    (inside the caller's `BEGIN IMMEDIATE`), `set_status`, `log(event)`, `list(conn)`,
    `export(s, episode)` (writes `episode.json` at purge). Helpers:
    `scene_key(scene, script, profile, take)` (HeyGen reads `voice`, else `text`; look, voice id
    and motion from the script, else from `profile.presenter`; `heygen.load_config` supplies only
    the API key), `presenter(script, profile) -> [avatar_id, voice_id, motion]` (for the
    `reference` check), `inputs_hash(scene, clip_mp4, cutout_webm, card_mp4, plan, look_hash)` =
    sha1 over the scene text, the two clip file checksums, the card checksum or empty, the plan
    JSON and the pinned profile's `look_hash`. `to_out(episode, validation, latest)` builds the
    `GET /{id}` shape.

#### 17. `server/src/streamstudio/episode/ledger.py` (Create)

*   **Type / Scope**: Cost ledger.
*   **Proposed Changes**: `month_total(conn, now)` (this month's charges plus the unconsumed part
    of every open reservation, where an open reservation is the episode's latest approval group
    of reservation rows and unconsumed = the group's usd minus charges and releases since it,
    floored at zero); `reserve(conn, episode, lines, allowance_usd) -> approval_id` where `lines`
    is `[(scene_id, clip_key, take, job_id | None, seconds, usd)]`, one row per line plus one
    allowance row with `scene_id = NULL`;
    `charge(conn, episode, scene, clip_key, take, job_id, seconds, usd, at)` (idempotent through
    the partial unique index on the clip key); `release(conn, episode, approval_id, lines)`
    (one release row per released line, the allowance row included when the whole group is
    released); `release_unsubmitted(conn, episode)` releases the latest group's lines whose
    scene has no live job and no charge; `spent(conn, episode)` for `budget.spent`. This module
    imports only `core`, so a worker handler may import it inside a function body. All called
    inside the caller's transaction.

#### 18. `server/src/streamstudio/core/heygen.py` (Modify)

*   **Type / Scope**: HeyGen client and helpers.
*   **Proposed Changes**: `item_key(look, voice, script, motion, silent_s, take=0)` appends
    `take` to the hashed list only when it is above zero, so today's keys are unchanged (tested).
    `WORDS_PER_S = 2.5` moves here from the route (`api/routes/heygen.py:26`), and
    `USD_PER_S = 0.0385` mirrors the panel's `API_USD_PER_S` (`HeygenPanel.tsx:7`, removed from
    the panel in item 49);
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
*   **Proposed Changes**:
    *   `POST /`: preflight (`profiles=False`) 503 with the missing toolchain names only;
        resolves the script's slug, or writes `profiles.default_slug` into `script.profile`,
        and refuses with 409 ("default profile X missing") when that default has no row;
        validate 422 (an unknown slug the script names is the `_script` error); 409 with the
        fields of `profiles.missing(s, latest)` when not empty; create. These are the only
        create answers for a missing profile; health and the Risks table use the same 409.
    *   `GET /`; `GET /{id}` (pure; returns `EpisodeOut` = the record without
        `budget.confirm_token` plus `progress: {clips, qa, composed, total}`,
        `validation: {errors, warnings}`, `next_action: str | None`, `last_log: str | None`,
        `profile_name: str | None`, `profile_latest_version: int | None`).
    *   `PUT /{id}/script`: returns the episode to `draft`; when the script hash changes, unlinks
        `final.mp4`, `final.srt` and `kit.json` and clears `outputs.recording_id`; keeps the pin;
        allowed from `ready` and `needs_dan`; 409 when it changes `script.profile` while a pin exists; 409 once
        `outputs.upload_requested_at` is set.
    *   `POST /{id}/approve-script`: pins the latest version of `script.profile` only when
        `record.profile` is unset; then 409 when `profiles.missing(s, pinned)` is not empty, and
        clears
        `reference` when `record.presenter(script, pinned)` differs from `reference.presenter`.
    *   `POST /{id}/repin {profile?}`: the states, refusals and effects in the transition rules
        (sets `script.profile` when given, clears `record.profile` and `outputs.channel`, always
        unlinks `final.mp4`, `final.srt` and `kit.json`, clears `outputs.recording_id`, returns to
        `draft`; allowed from `ready`, refused once `outputs.upload_requested_at` is set).
    *   `GET /{id}/estimate`: issues `confirm_token` with a ten-minute expiry, and adds
        the "Upload channel" line of "The YouTube channel" (the profile's channel, or the one
        `pick_channel` would choose when the profile names none, or "not connected"; from
        `youtube.channels`; information only, never a 409), the presenter's name and ids, and
        the month's total per channel.
    *   `POST /{id}/approve-budget`:
        *   requires the token, and an `Origin` header that is present and passes
            `netguard.origin_allowed(origin, s.extra_hosts)`, since the middleware treats a
            missing header as a non-browser request;
        *   under the row lock, 409 naming the fields when `profiles.missing(s, pinned)` is not
            empty, before any reservation;
        *   recomputes the month's total and refuses with 409 over the ceiling;
        *   reserves one line per distinct (clip key, take): every live `heygen_clip` job plus
            every scene without a clip and without a live job for its current key;
        *   releases any previous reservation;
        *   writes `budget.approved_at`; it does not look at YouTube.
    *   `POST /{id}/upload` (Upload private): only from `ready`, 409 otherwise; requires a
        present and allowed `Origin` as approve-budget does (403 without); under the row lock
        resolves `youtube.pick_channel(s.data_dir, pinned.youtube_channel)` (exists,
        `core/youtube.py:128-139`), 409 when it raises; writes `outputs.channel` and
        `outputs.upload_requested_at`; enqueues `episode_advance`; 409 when
        `outputs.upload_requested_at` is already set.
    *   `POST /{id}/publish` (Stage 1: publish now only; `publish_at` accepted from Stage 2),
        `POST /{id}/advance` (the state rule in "The episode record": clears errored job ids
        into `prev_job_id`, then `uploaded_private`, `ready` or `in_progress`),
        `POST /{id}/purge`.

    Stage 2 adds `POST /{id}/refresh`, `POST /{id}/cancel`, `GET /{id}/qa/{scene}.jpg`. Ids
    validated by the regexes in files 14 and 16. README: `api/routes/README.md` new section;
    `api/README.md` router list.

#### 21. `server/src/streamstudio/api/main.py` (Modify)

*   **Type / Scope**: App factory.
*   **Proposed Changes**: Import and mount `episodes.router` and `channels.router`. In
    `create_app`, call `profiles.ensure_seed(c, s)` right after `db.migrate(c)` on the same
    connection (`api/main.py:28-30`). README: `api/README.md` ("mounts exactly these routers",
    and the seed at startup).

#### 21a. `server/src/streamstudio/api/routes/channels.py` (Create)

*   **Type / Scope**: FastAPI router, prefix `/api/channels`.
*   **Proposed Changes**: Stage 1 ships the Stage 1 rows of the route table in "Channel
    profiles". The fixed routes (`/default`, `/files`, `/preview`) are declared before `/{slug}`.
    *   `GET /`: slug, name, latest version, `default` flag.
    *   `POST /` (`{slug, name, from?}`): `profiles.duplicate`; 409 if the slug exists; 422 for a
        bad or reserved slug.
    *   `GET /{slug}` (latest, or `?version=N`; 404 for an unknown slug).
    *   `PUT /{slug}` (`{base_version, profile}`): 404 for an unknown slug; 422 with field errors,
        including a body slug that differs from the path; 409 from `profiles.save` when
        `base_version` is stale; returns the new version and any warning (HeyGen unreachable).
    *   `PUT /default` (`{slug}`): `profiles.set_default`.
    *   `PUT /files?name=<file>&role=intro`: streams `request.stream()` into
        `channel_files.store_stream`, as `api/routes/recordings.py:38-56` streams a take; returns
        `{sha256, media_type, kind, bytes}`; 413, 415 and 422 as in "Uploads".
    *   `GET /files/{sha256}`: `FileResponse` with the sidecar's media type and
        `X-Content-Type-Options: nosniff`; 404 for an unknown or malformed sha256.

    Every `POST`, `PUT` and `DELETE` requires an `Origin` header that is present and passes
    `netguard.origin_allowed`, else 403. Stage 2 adds `POST /preview` and `DELETE /{slug}`
    (item 41a); Stage 3 adds `POST /{slug}/intro` (item 46a). README: `api/routes/README.md` new
    section.

#### 22. `server/src/streamstudio/worker/handlers.py` (Modify)

*   **Type / Scope**: Existing job handlers.
*   **Proposed Changes**: `heygen_clip` accepts `take`, `episode_id` and `scene_id`; with an
    `episode_id` it:
    *   writes a claim (its job id) into `data_dir/heygen/<key>.json` before `create_video`, and
        returns as a no-op if the file holds another job's claim whose job is queued or running;
    *   never unlinks the state file; on HeyGen `failed` it writes `{failed: reason, at}` there
        and returns the same dict;
    *   writes the ledger charge for (`episode_id`, its clip key, with `scene_id` and `take` as
        attributes) (measured duration for
        `completed`, estimated seconds for `failed`) through `streamstudio.episode.ledger`,
        imported inside the function body (the ledger imports only `core`, so there is no cycle
        and no heavy import);
    *   reads the pinned profile with `streamstudio.episode.profiles.pinned`, imported inside the
        function body, and passes its plate, desk and seat to the cut-out:
        `CUTOUT(mp4, webm, plate, seat=..., desk=...)`. Without an `episode_id` the call keeps
        today's plate (`assets/studio/plate-landscape-final.png`, `handlers.py:263`) and seat
        (0.66, 0.68, 0.47, `handlers.py:182`), now named `EDITOR_SEAT`, so the editor is
        unchanged;
    *   enqueues `episode_advance`.
    `_cutout_clip(mp4, out_webm, plate, seat=EDITOR_SEAT, desk=None)` passes `desk` on to
    `cutout.run`. `youtube_upload` with `payload.episode_id` enqueues `episode_advance` on return.
    `store.enqueue` gains an optional `max_attempts` stored in the payload (honoured by
    `run_one`, file 23). README: `worker/README.md` Invariants for `heygen_clip` (the state file
    is no longer deleted on `failed` for episode jobs; the cut-out's plate comes from the pinned
    profile) and `youtube_upload`.

#### 22a. `server/src/streamstudio/avatar/cutout.py` (Modify)

*   **Type / Scope**: The cut-out helpers.
*   **Proposed Changes**: `composite` and `run` gain an optional keyword `desk: Path | None`.
    When it is given, it is the desk layer; when it is `None`, `desk_layer_for(plate)` is used
    as today, so the editor and the CLI are unchanged. `HANDS_IN_CLIP` and `fit_cover` stay
    where they are and are imported by the episode compositor (item 25). README:
    `avatar/README.md` `cutout.py` interface.

#### 23. `server/src/streamstudio/worker/main.py` (Modify)

*   **Type / Scope**: Worker loop.
*   **Proposed Changes**: `run_one` honours a per-job `max_attempts` from the payload when
    present, and after `fail_job` enqueues `episode_advance` when the payload carries
    `episode_id`. `requeue_stale` is unchanged: a stale running job is re-queued under the same
    id regardless of attempts, which is correct because the claim and the saved `video_id` belong
    to that id. `run()` opens one connection, runs `db.migrate` and `profiles.ensure_seed`, and
    closes it before it starts the worker threads, so the seed runs once per process rather than
    once per thread. Imports `streamstudio.episode.handlers` so the episode handlers register
    (file 24). README: `worker/README.md` `main.py` invariants.

#### 24. `server/src/streamstudio/episode/handlers.py`, `server/src/streamstudio/episode/planner.py` (Create)

*   **Type / Scope**: Handler registration and the `episode_advance` handler.
*   **Proposed Changes**: `episode/handlers.py` decorates the episode handlers with
    `worker.handlers.handler(...)` and imports `planner`, `compose`, `mix`, `kit`, `publish`,
    `qa`, `capture`, `cards` lazily inside each function, so importing it pulls no heavy library
    and `worker/handlers.py` never imports the episode package at module level (its two
    function-level imports are `episode.ledger` and `episode.profiles`, file 22; both import only
    `core` and pydantic, so there is no cycle). `planner.py`
    implements the condition table in the Technical Plan under the `episodes` row lock, acting
    only in the states the table names: Stage 1
    ships rows 0, 1 (the `needs_dan` branch), 2 (with claim transfer from `prev_job_id` for an
    errored job that saved a `video_id`), 6 (clip-and-cut-out predicate), 7, 8, 9, 9a, 10 and 11; Stage 2 replaces row 1
    with 3a to 3c and row 6's predicate with QA. Job ids are recorded in `scenes_state` before
    enqueueing; the only `jobs` read is `status` of a recorded id; reservation release at
    `ready`; `youtube_upload` is enqueued only by row 10, which needs
    `outputs.upload_requested_at`. README: `worker/README.md` handler list; `episode/README.md`.

#### 25. `server/src/streamstudio/episode/compose.py` (Create)

*   **Type / Scope**: `scene_compose` handler and compositing functions.
*   **Proposed Changes**: The compositing of `tools/compose/render.py` (plate, seated cut-out,
    table overlays, zoom, glitch, neon frame, card slice) as functions with `Settings` and the
    pinned `Profile` injected. Every colour, font and channel text literal in `render.py` is
    mapped below; layout numbers (sizes, `CARD_*`, `CIRCLE`, `TABLE_BOTTOM`, timings) stay as
    module constants because they are not channel values.

    | `render.py` literal | Line | Becomes |
    | --- | --- | --- |
    | `[45, 226, 196]` (rim and table-card gradient start), `(45, 226, 196, 255)` (tag dot), `TEAL` | 196, 297, 328, 380 | `palette.accent_a` |
    | `[140, 100, 255]` (rim and table-card gradient end) | 196, 328 | `palette.accent_b` |
    | `[60, 200, 190]` (table glow) | 377 | `palette.glow` |
    | `(10, 12, 20, 220)` (tag fill) | 296 | `palette.panel` |
    | `(8, 10, 18, 205)` (table-card fill) | 315 | `palette.panel_2` |
    | `(124, 92, 255, 170)` (tag outline, alpha kept) | 296 | `palette.outline` |
    | `WHITE = (242, 244, 250)` | 380 | `palette.text` |
    | `(236, 238, 246, 255)` (tag text) | 298 | `palette.tag_text`, so Episode 1 v2's tag stays exact |
    | `MUTED = (170, 176, 196)` | 380 | `palette.muted` |
    | `[6, 6, 12]` (blurred-plate tint), `[20, 40, 60]` (glitch tint) | 50, 479 | neutral module constants |
    | `RING_RGB`, `ring` | 184-187 | dropped: unused |
    | Inter `Bold` (titles, names, chips, end-card title) | 406-407, 413-414, 422, 435, 443 | `look.fonts.display` |
    | Inter `SemiBold` (tag, end-card link) | 32, 294, 443 | `look.fonts.body` |
    | Inter `Medium` (title and lower subtitles, end-card small line) | 406, 413, 443 | `look.fonts.small` |
    | `FONT = '/usr/share/fonts/opentype/inter/Inter-{}.otf'` | 26 | the profile's font files |
    | `STUDIO` plate, desk and `plate-landscape-final.json` seat | 25, 45-49 | `look.plate.image`, `.desk`, `.seat` |
    | end-card fallback text ("List your AI business", `nervix-market.vercel.app`, the NervixPay line) | 441-442 | the scene's `plan.endcard`; a plan without one shows no end card |
    | `PLAN` titles, lowers, chips and tags ("DansLab", "Dan", Nervix and site names) | 54-70 | the script's scene plans (the Episode 1 v2 fixture carries them) |

    The lower's default name is `profile.presenter.name`.
    Decoding: the cut-out through `ffmpeg -c:v libvpx-vp9 -i <key>.cutout.webm -vf fps=25 -f rawvideo -pix_fmt rgba -`
    (the built-in VP9 decoder drops alpha) and the clip through `ffmpeg -i <key>.mp4 -vf fps=25 -f rawvideo -pix_fmt rgb24 -`,
    consumed in lock-step. Seat geometry (`scale`, `hands_y`, `x`) comes from
    `profile.look.plate.seat`. `HANDS_IN_CLIP` and `fit_cover` are imported from
    `avatar/cutout.py` inside the functions, because that module imports NumPy and Pillow at
    module level; `desk_layer_for` is not used, and the desk comes from `look.plate.desk`. A
    profile with no desk composes without one and logs the skip. Frame count
    `round(duration * 25)`; audio mapped from the clip with `-shortest`.
    `render/lipsync.py:guard_cue` is called per scene with the cue derived from the scene kind
    and the voice literal `"clip"`; degraded scenes use `pip_rect`. `render.lipsync` imports PIL
    at module level, so it is imported inside the handler and the compositing functions, never
    at the top of `compose.py` (file 36 checks). Output `scenes/<scene>.mp4` via temp plus
    rename; `inputs_hash` (with `look_hash`) recorded. Stage 1 composes avatar scenes on the
    plate; card slices arrive in Stage 3. Stage 2 adds `preview_frames(s, conn, profile)` (item 41a).
    README: `render/README.md` names the compositor as a `lipsync.py` caller; `episode/README.md`.

#### 26. `server/src/streamstudio/episode/mix.py` (Create)

*   **Type / Scope**: `episode_assemble` handler.
*   **Proposed Changes**: Concat demuxer over `scenes/*.mp4` with a frame-count check. The intro,
    bed, SFX and levels come from the pinned profile (`sound.intro`, `sound.bed`, `sound.sfx`,
    `sound.levels`); each absent file is skipped with the log line "Profile X has no <field>;
    skipped". An intro with no audio stream contributes silence instead of failing. The mix
    carries over `tools/compose/mix.py` exactly, as module constants:

    | What | `mix.py` | Value |
    | --- | --- | --- |
    | sample format | 20, 34 | 48 kHz, stereo, float32 |
    | per-track loudness | 31-32 | each input through `loudnorm=I=<level>:TP=-2:LRA=20`, at the profile's level for its track |
    | intro and voice placement | 57-58 | intro at 0 s; the concatenated scenes at the intro's duration |
    | bed loop | 61-69 | looped with a 3 s linear crossfade, to the length of the main part plus 2 s |
    | bed fades | 70-72 | linear fade in over 2.5 s, linear fade out over the last 5 s |
    | bed start | 73 | 1.0 s before the intro ends |
    | SFX loudness | 118 | each SFX file at the profile's `sfx` level, then the cue's gain |
    | final | 127-133 | `loudnorm=I=-14:TP=-1.5:LRA=11`; H.264 `-preset medium -crf 18`, `-r 25`; AAC 192k at 48 kHz; `+faststart`; `-shortest` |

    The cue table (`t0` is the scene's start in the final video, `d` its duration):

    | Cue | Slot | Time | Gain | `mix.py` |
    | --- | --- | --- | --- | --- |
    | `question` scene | `riser` | `t0 - 1.3` | -3 dB | 94 |
    | `question` scene | `pop` | `t0 + 0.3` (no longer tied to a lower's start) | -4 dB | 95-96 |
    | `whoosh_at` | `whoosh` | `t0 + whoosh_at * d - 0.2` | -2 dB | 98 |
    | each `glitch` | `glitch` | `t0 + start * d` | -1 dB | 100 |
    | `endcard` | `shimmer` | `t0 + end_at * d` (`end_at` 0 when absent) | 0 dB | 102 |
    | `reveal` scene | `impact` | `t0 + 0.3` (replaces the match on "AI avatar" in a lower) | -2 dB | 104-105 |
    | card `navigate` | `page` | the cue's time | -6 dB | 110 |
    | card `counter` | `sparkle` | the cue's time - 0.1 | 0 dB | 113 |

    An empty slot is silent and logged once. Writes `final.mp4` and `final.cues.json`, and
    records `sound_hash` with the assembly inputs. Stage 1 ships intro, bed and the plan cues;
    card cues arrive in Stage 3.

#### 27. `server/src/streamstudio/episode/kit.py` (Create)

*   **Type / Scope**: `episode_publish_kit` and `episode_register` handlers.
*   **Proposed Changes**: `kit.json = {title, description, tags, chapters, notes}`; chapters
    `["0:00 Intro", "<m:ss> <first sentence of the question scene>", ...]` when the profile has
    an intro, else the first chapter is the first scene's first sentence at 0:00; folded under
    10 s, emitted only when at least three remain (port of `web/src/publish/kit.ts` chapter
    rules), otherwise `notes` says why; `final.srt` with at most two lines of at most 42
    characters per caption, timed from `qa/<scene>.words.json` when present, else measured
    duration split by characters; every time offset by the intro's ffprobe duration (0 without
    an intro) plus the preceding scenes' durations. The description ends with
    `profile.publish.description_footer`; the body is shortened so the whole stays within
    `clean_meta`'s 5000 bytes and the footer is never cut. The tags are the script's plus
    `profile.publish.default_tags`, deduplicated, in that order; tags past `clean_meta`'s 500
    characters are listed in `notes`. Registration moves `final.mp4` to
    `recordings/rec_<stamp>-ep.mp4`, writes `.srt`, `rec_<stamp>-ep.transcript.json` as
    `{"language": profile.language}` (so `youtube_upload` attaches captions in the right
    language) and `rec_<stamp>-ep.episode.json`, records the path in `outputs.final_mp4`,
    returns the recording id.

#### 28. `server/src/streamstudio/api/routes/recordings.py`, `server/src/streamstudio/api/routes/youtube.py`, `web/src/publish/YouTubeUpload.tsx`, `web/src/publish/YouTubeUpload.test.tsx` (Modify)

*   **Type / Scope**: Recordings listing; an episode uploads only through its own route.
*   **Proposed Changes**: `list_recordings` also lists `rec_*.episode.json` entries (id, `mp4`,
    `mp4_bytes`, `transcript`, `source_bytes: null`, `episode: <id>`), merged with the takes and
    sorted by id descending, so the existing ordering test keeps working. `queue_upload` in
    `api/routes/youtube.py` refuses with 409 ("use the episode's Upload private") a `rid` whose
    `<rid>.episode.json` sidecar names an episode, so an episode goes to YouTube only through
    `POST /api/episodes/{id}/upload`, private, on the profile's channel, with
    `upload_requested_at` set. `YouTubeUpload.tsx` leaves out entries whose `episode` is set;
    its vitest asserts an episode entry is not offered. README: `api/routes/README.md`
    `recordings.py` and `youtube.py` entries; `web/src/publish/README.md`.

#### 28a. `server/src/streamstudio/mcp.py`, `server/src/streamstudio/api/routes/youtube.py`, `server/src/streamstudio/api/routes/jobs.py`, `server/tests/test_agent.py`, `server/tests/test_youtube.py`, `server/tests/test_api.py`, `docs/AGENTS.md`, `README.md`, `server/src/streamstudio/README.md` (Modify)

*   **Type / Scope**: No upload without Dan's click (owner decision, 2026-11-03).
*   **Proposed Changes**: Remove the `youtube_upload` tool from `mcp.TOOLS` and its handler;
    `youtube_status` stays (read-only). `POST /api/recordings/{rid}/youtube` refuses with 403
    a request whose `Origin` is missing or not allowed (`netguard.origin_allowed` plus an
    explicit presence check, since it returns `True` for `None`); the editor's YouTube panel
    sends one already; the module docstring drops "agents (MCP) can only upload private" and
    says every upload starts from a browser click.
    `create_job` in `api/routes/jobs.py` (today it enqueues any registered kind with any payload
    and no `Origin`, `jobs.py:26-34`) accepts only `API_KINDS = {"noop", "probe",
    "transcribe"}`: free, local and never tied to an episode. Nothing in `web/src` posts to
    `/api/jobs` today (the editor only polls `GET /api/jobs/{id}`), so no caller changes. Every
    other kind is 403 naming the route to use: `youtube_upload` (Upload private, or
    `POST /api/recordings/{rid}/youtube`), `heygen_clip` (`POST /api/heygen/render`),
    `vault_push` (`POST /api/vault/push`), `finish_recording` (`POST /api/recordings`), every
    `episode_*`, `scene_*`, `card_*` and `site_*` kind (`/api/episodes`) and every `channel_*`
    kind (`/api/channels`). An unknown kind stays 400.
    Tests: `test_agent.py` drops `"youtube_upload"` from the exact expected tool list
    (lines 62-67), deletes the `youtube_upload` call block (lines 84-89) and asserts no tool
    name contains `upload`; `test_youtube.py` sends `Origin: http://testclient` on its upload
    calls and adds a 403 case with no `Origin`; `test_api.py` asserts `POST /api/jobs` is 403
    for `youtube_upload`, `heygen_clip`, `vault_push` and `episode_purge` (no job row written)
    and 201 for `noop`. `docs/AGENTS.md` drops the `youtube_upload` row and says uploads are
    the owner's click. The root `README.md` (lines 99-101) drops the clause that the MCP server
    uploads as `private` and says "no MCP tool uploads; every upload starts from a browser
    click with an allowed `Origin`". README: `server/src/streamstudio/README.md` `mcp.TOOLS`,
    and its `[mcp.py:call]` `youtube_upload` invariant (line 31) is removed;
    `api/routes/README.md` `youtube.py` and `jobs.py` (`create_job` allowlist).

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
    runs only from `ready` (before any upload request), `published` or `cancelled`.
    `refresh_status` arrives in Stage 2 (file 42).

#### 31. `web/src/episode/EpisodePage.tsx`, `web/src/episode/api.ts`, `web/src/episode/README.md` (Create); `web/src/index.css` (Modify)

*   **Type / Scope**: React view, client and styles.
*   **Proposed Changes**: Reachable at `?episode=<id>`; Stage 1: the channel's name
    (`profile_name`) and pinned profile version in the header, the scene list with errors,
    four buttons (Approve script; Approve budget with the estimate screen and the token;
    Upload private, shown only in `ready` before an upload is requested, and replaced by
    "Uploading…" in `ready` with `outputs.upload_requested_at` set; Publish now, shown only in
    `uploaded_private`); in
    `ready` the page shows "Ready: final MP4 in Library. Upload private?" with a link to the MP4
    and the kit. The estimate screen shows the "Upload channel" line of "The YouTube channel", and the
    presenter's name and ids. Polls `GET /api/episodes/{id}` every 5 s while `in_progress`, or
    while `ready` with `outputs.upload_requested_at` set;
    usable at a 390 px wide viewport (`index.css` gains a `.episode` breakpoint). `api.ts` exports
    `getEpisode`, `putScript`, `approveScript`, `repin(profile?)`, `estimate`,
    `approveBudget(token)`, `upload()`, `publish(publish_at?)`, `advance`, `purge`, and from
    Stage 2
    `refresh`, `cancel`. Stage 2 adds warnings, inline edit, per-scene state chips, contact-sheet
    links, the "Needs you" panel and the schedule control. README: `web/src/README.md`
    subdirectory list.

#### 32. `web/src/App.tsx` (Modify)

*   **Type / Scope**: Routing.
*   **Proposed Changes**: `?episode=` renders `EpisodePage` before the editor branch, like
    `?render=1` and `?program=1`. README: `web/src/README.md` `App.tsx` entry.

#### 33. `server/tests/test_episodes.py` (Create)

*   **Type / Scope**: Unit and API tests.
*   **Proposed Changes**:
    *   contract round-trip including every `Plan` key and `card_template`;
    *   the converted Episode 1 v2 fixture validates under `extra="forbid"`;
    *   validator error rows, with the unknown-profile error under `_script`;
    *   create, approve-script, estimate with token;
    *   approve-budget refused without the token, with a missing `Origin`, and with a
        disallowed `Origin` (tests send `Origin: http://testclient`);
    *   approve-budget 409 over the ceiling; approve-script and approve-budget pass with zero
        connected YouTube channels, and with two connected and none named;
    *   two queued approvals cannot both pass against the same remaining balance;
    *   a charge dated in the month after its approval counts in that month;
    *   a second approval reserves each (clip key, take) once: an unchanged scene mid-render is
        reserved once, an edited scene with its old render running is reserved for both keys,
        then the previous reservation is released and the month's total never drops below the
        live job's estimate in between;
    *   `PUT /script` returns an `in_progress`, `ready` or `needs_dan` episode to `draft`, unlinks
        `final.mp4` and `kit.json` and clears `outputs.recording_id` when the hash changes, and
        is refused (409) once `outputs.upload_requested_at` is set;
    *   `POST /{id}/upload` is 409 from every state but `ready`, 403 without `Origin` and with a
        disallowed one; from `ready` it writes `outputs.channel` and `upload_requested_at`; it is
        409 when the profile's YouTube channel is not connected, when none is connected, and
        when the profile names none and two are connected; a second click is 409 and enqueues
        nothing;
    *   repin is allowed in `ready` and refused once an upload is requested; purge works from
        `ready` and is refused once an upload is requested;
    *   an episode's project row is absent from `GET /api/projects` and `GET /api/projects/{pid}`
        answers 404 for it;
    *   publish now through the fake YouTube transport sets `published`;
    *   `GET /{id}` has no side effects and returns the `EpisodeOut` shape, including
        `profile_name` and `profile_latest_version`;
    *   preflight 503 names only missing toolchain parts; create 409 naming the field when the
        profile's plate file is missing; a script with no `profile` while the stored default
        has no row is 409 ("default profile X missing"), never 503 or 422;
    *   a script with no `profile` gets `danslab` written into `script.profile` at create (the
        response shows it); one naming an unknown profile is a 422 error;
    *   after create, making another profile the default leaves the episode's slug and its pin
        unchanged;
    *   approve-script pins the latest version; a profile saved afterwards leaves the pin
        unchanged and makes `profile_latest_version` exceed the pinned version;
    *   a script edit after a profile save keeps the old pin, and the next approve-script keeps
        it too; a `PUT /script` that changes `profile` while pinned is 409;
    *   `repin` returns the episode to `draft`, unlinks `final.mp4`, `final.srt` and `kit.json`,
        clears `outputs.recording_id` and the pin even when the script hash is unchanged, is
        allowed from `needs_dan`, and the next approve-script pins the new version; `repin`
        with `{profile}` changes `script.profile`;
    *   approve-script 409 when the pinned profile misses a required file, with no reservation
        written;
    *   approve-budget 409 when a pinned file was deleted after approve-script, with no ledger
        row written;
    *   `reference` is cleared at approve-script when the repinned profile changes `avatar_id`,
        `voice_id` or `motion`, and kept when only the palette changes;
    *   Upload private writes the pinned profile's `youtube_channel` to `outputs.channel` (the
        upload uses it);
    *   a profile with no `youtube_channel` and one connected YouTube channel uploads to that
        channel on Upload private; the estimate response names its title ("the only connected
        channel; this profile names none"), with none connected says "not connected (connect
        before uploading)", and with two connected and none named says "several connected".

#### 34. `server/tests/test_episode_pipeline.py` (Create)

*   **Type / Scope**: Worker tests.
*   **Proposed Changes**:
    *   one `create_video` per (key, take) with two planners running at once;
    *   a HeyGen `failed` is recorded in the state file, charged once, parks the episode in
        `needs_dan`, and is not re-enqueued;
    *   a worker-level error enqueues the planner and parks the episode; Advance after a network
        error resumes the saved render without a second `create_video` (claim transfer);
    *   `max_attempts = 1` honoured; a stale requeue keeps the job id;
    *   `heygen_clip` with an `episode_id` passes the synthetic profile's plate path, seat and
        desk to `CUTOUT` (stubbed); without one it passes today's plate and `EDITOR_SEAT`;
    *   compose on the plate with the guard; a frame-count mismatch fails concat;
    *   kit chapters from question markers, folding and the fewer-than-three rule, SRT timing
        fallback, intro offset; a footer that would pass 5000 bytes is kept whole and the body
        shortened;
    *   registration names, sidecar and language file; a registered episode appears in
        `GET /api/recordings` in the right order with `episode` set, and
        `POST /api/recordings/{rid}/youtube` for it is 409;
    *   after registration the planner sets `ready`, releases the reservation, and never
        enqueues `youtube_upload` without `outputs.upload_requested_at` (run the planner
        repeatedly in `ready`: no upload job);
    *   with zero connected YouTube channels, an episode still reaches `ready`;
    *   after Upload private, row 10 enqueues one private `youtube_upload`; the upload handler
        enqueues the planner and the planner sets `uploaded_private`;
    *   an upload job ending in `error` parks the episode in `needs_dan`, and further planner
        runs enqueue no upload; Advance returns it to `ready` and row 10 enqueues one upload
        that resumes from the state file;
    *   a `scene_compose` job ending in `error` parks the episode in `needs_dan` with no new
        compose job; Advance enqueues it once more;
    *   a clip job that finishes while the episode is in `draft` (after an edit or a repin)
        enqueues a planner that enqueues nothing and writes the charge;
    *   purge keeps the right files and writes the export;
    *   a second, synthetic profile (a red-and-yellow palette, a one-colour plate, a 2 s intro
        uploaded at 30 fps with a tone, a sine-tone bed, `language: "ro"`, its own footer and
        YouTube channel) runs the Stage 1 pipeline end to end: a sampled plate pixel, a sampled
        pixel of the neon rim, the intro's tone in the first 2 s and the scenes' start offset
        by the intro, the bed's frequency in the mix, the SRT language file, the description
        footer and, after Upload private, the upload's channel are all the profile's;
    *   a profile with no intro, no bed and one empty SFX slot assembles, chapters start at
        0:00 without "Intro", and the log has one "has no <field>; skipped" line for each;
    *   changing only the palette, then repin, approve-script and a zero-line approve-budget,
        re-composes every scene, enqueues no `heygen_clip`, rebuilds `final.mp4`, a sampled
        rim pixel shows the new colour, and the episode ends in `ready`;
    *   changing only the description footer, then repin, re-composes nothing and enqueues no
        `heygen_clip`; the rebuilt kit has the new footer;
    *   changing `presenter.voice_id` changes every clip key.

#### 34a. `server/tests/test_channels.py` (Create)

*   **Type / Scope**: Profile storage and API tests.
*   **Proposed Changes**:
    *   `ensure_seed` inserts `danslab` version 1 once and never overwrites a saved version; two
        concurrent `ensure_seed` calls on a fresh database give one row and no error; after
        DansLab is made non-default and deleted, a restart does not seed it again;
    *   once its paths are replaced by sha256s, the seed validates against `Profile`; every file
        it names exists; its plate, desk, seat, font and intro sha256s equal `manifest.json`;
        its palette, levels, rules, language and YouTube channel equal the values listed in
        item 6; its intro is 25 fps and has an audio stream; every licence note in
        `manifest.json` is filled in;
    *   a `Profile` built with only the required fields has the neutral defaults of the
        "Required fields and defaults" table and none of the seed's values;
    *   `PUT` saves version N+1 and never changes version N; `GET ?version=N` returns N; a `PUT`
        with a stale `base_version` is 409; a body slug that differs from the path is 422; a
        `PUT` on an unknown slug is 404;
    *   `POST /` from `danslab` copies its latest version and clears `youtube_channel`; a
        duplicate slug is 409; a bad or reserved slug (`files`) is 422; the copy saves unchanged
        with `PUT` and `channel_files.path` resolves every file it names;
    *   a `youtube_channel` that is not connected is 422 on save; an unchanged one is accepted
        while disconnected; an `avatar_id` HeyGen does not list is 422 (fake transport), and an
        unreachable HeyGen saves with a warning;
    *   upload: a body of 200 MB + 1 byte of zeros sent through a generator is 413 and leaves no
        file (size counted from the stream); an extension outside the allowlist is 415; a
        `.png` that Pillow cannot open is 422; an OTF, a TTF and a WOFF2 are accepted by magic
        bytes and a renamed text file is not; an HLS playlist renamed `.mp4` is refused and
        ffprobe was called with `-protocol_whitelist file`; the same file uploaded twice is
        stored once; `GET /files/{sha256}` serves the sidecar's media type with `nosniff`;
    *   a 30 fps intro uploaded with `role=intro` is stored at 25 fps with its audio; a 30 fps
        video named in `sound.intro` without that role is 422 on save; a WOFF2 in `look.fonts`
        is 422;
    *   `PUT /default` makes another profile the default, refuses a slug with no row (409), and
        `GET /` marks the new default;
    *   every write with no `Origin` is 403, and with a disallowed `Origin` is 403;
    *   no `danslab` (any case) in a `*.py`, `*.ts` or `*.tsx` file under
        `server/src/streamstudio/episode/`,
        `server/src/streamstudio/api/routes/episodes.py`, `server/src/streamstudio/api/routes/channels.py`,
        `web/src/episode/` or `web/src/channels/` (a source scan in the test; the live studio's
        existing references are out of its scope, see Non-Goals).

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
    25 %), returns `{status, issues, words}`. When the pinned profile's `language` does not start
    with `en`, the word-error-rate step is skipped with the issue "not checked (language)" and the
    verdict unchanged.

#### 38. `server/src/streamstudio/episode/planner.py` (Modify)

*   **Type / Scope**: Planner rows 3, 3a to 3c and the QA predicate of row 6.
*   **Proposed Changes**: QA enqueueing, `reference` medians (with `reference.presenter`) after the first full pass, the
    allowance (attempts and USD), `take + 1` re-renders with claim handling, `degraded` for QA
    failures, `needs_dan` for render failures after the allowance, `release_unsubmitted` on
    cancel.

#### 39. `server/src/streamstudio/episode/validate.py` (Modify)

*   **Type / Scope**: Remaining validator warnings.
*   **Proposed Changes**: Length against `profile.rules.scene_s`; question presence when
    `rules.question_hooks` and reveal presence when `rules.reveal`; claim sources (only when the
    profile's `language` starts with `en`); voice-names spelling from
    `profile.presenter.voice_names`; the consecutive-avatar rule over `profile.rules.event_gap_s`.

#### 40. `server/src/streamstudio/api/routes/episodes.py` (Modify)

*   **Type / Scope**: Stage 2 routes.
*   **Proposed Changes**: `POST /{id}/refresh` (calls `refresh_status`; a repeat within five
    minutes is a no-op), `POST /{id}/cancel`, `GET /{id}/qa/{scene}.jpg`; `publish` accepts
    `publish_at`.

#### 41. `server/src/streamstudio/mcp.py` (Modify)

*   **Type / Scope**: MCP server.
*   **Proposed Changes**: Tools `episode_create(script)`, `episode_list()`,
    `episode_status(id)`, `episode_estimate(id)`, `episode_refresh(id)`, `channel_list()`,
    `channel_get(slug)`; `channel_get` builds its path with `_seg(slug)` (`mcp.py:208-210`);
    no upload tool (`youtube_upload` was removed in Stage 1, item 28a). No approve, upload,
    publish, cancel, purge or profile-write tool; the descriptions say so. README: `server/src/streamstudio/README.md` `mcp.TOOLS`.

#### 41a. `web/src/channels/ChannelsPage.tsx`, `web/src/channels/api.ts`, `web/src/channels/README.md` (Create); `web/src/App.tsx`, `web/src/index.css`, `server/src/streamstudio/api/routes/channels.py`, `server/src/streamstudio/episode/compose.py`, `server/src/streamstudio/episode/profiles.py` (Modify)

*   **Type / Scope**: The Channels page, preview and delete.
*   **Proposed Changes**: `?channels=1` renders `ChannelsPage` before the editor branch:
    *   the profile list, with the default marked, **Make default** (`PUT /default`) and
        **Delete** (shows the 409's episode ids when refused);
    *   **New**: duplicate from a chosen profile, the default preselected;
    *   a form for every field grouped as Identity, Presenter, Look, Intro, Sound, Rules,
        Publish, with colour inputs and file pickers that upload each file as a raw body through
        `PUT /files?name=` (with `role=intro` for the intro) and show the licence note field;
    *   warnings when two profiles name the same YouTube channel or a profile names none;
    *   **Save**, which `PUT`s `{base_version, profile}`, shows the new version number, and on
        409 asks Dan to reload.

    A preview pane posts the unsaved form to `POST /api/channels/preview`, which validates it
    (422 with field errors), calls `compose.preview_frames(s, conn, profile)` and returns the
    JPEG described in "Channel profiles"; it writes nothing. The pane sends at most one request
    per second. `DELETE /{slug}` calls `profiles.delete`. Usable at a 390 px viewport
    (`index.css` gains a `.channels` breakpoint). README: `web/src/README.md` subdirectory list;
    `api/routes/README.md`.

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
    a `scheduled` episode is opened after `publish_at`, "Ready: final MP4 in Library. Upload
    private?" with Purge beside it, "Published. Purge workings?", and, when
    `profile_latest_version` is above the pinned version, "Profile changed since approval" with
    the **Use latest profile** button (`POST /{id}/repin`).

#### 44. `server/tests/test_episode_qa.py` (Create)

*   **Type / Scope**: Tests.
*   **Proposed Changes**:
    *   QA on synthetic clips (ffmpeg `lavfi` frames with and without a face image, frozen frames,
        a glitch frame);
    *   the transcript check with a stubbed `transcribe`, including a name-heavy voice line that
        normalises to `ok` and a missing whisper recorded as "transcript unavailable";
    *   with a profile whose `language` is `ro`, the word-error-rate check records "not checked
        (language)" and the verdict is unchanged, and the numbers-and-rankings warning is not
        raised;
    *   per-take transcript files survive a re-render;
    *   the planner never enqueues `scene_qa` for a scene whose state file says `failed` or whose
        clip is still rendering;
    *   a QA `FAIL` re-renders with `take+1` within the allowance; the next `FAIL` degrades;
    *   after a repin that changes `avatar_id`, `reference` is rebuilt from the next full pass
        and the new clips are not measured against the old medians;
    *   a render `failed` after the allowance parks in `needs_dan`;
    *   cancel releases only unsubmitted reservations, is allowed in `ready`, and is refused
        once an upload is requested;
    *   scheduled publish, refresh cooldown, a passed `publish_at` with a private video does not
        set `published`;
    *   every validator warning row on a minimal script, with thresholds from a non-default
        profile (`scene_s`, `event_gap_s`).

#### 44a. `server/tests/test_channels.py`, `server/tests/test_agent.py` (Modify); `web/src/channels/channels.test.tsx` (Create)

*   **Type / Scope**: Stage 2 channel tests.
*   **Proposed Changes**:
    *   `DELETE` is 409 for the default profile; 409 with the ids when an episode in any state,
        `published` included, names the slug in `script.profile` or the pin; it succeeds when no
        episode names it, keeps every file, and the seed flag stays;
    *   `POST /preview` returns `image/jpeg` for an unsaved form, 422 for an invalid one, 403
        without `Origin`, and writes no row and no file;
    *   the preview uses the newest `done` `heygen_clip` job whose `payload.look` is the form's
        `avatar_id` and whose cut-out exists, and the grey silhouette when there is none;
    *   `channel_list` and `channel_get` return the latest version; a slug with `/` is escaped by
        `_seg`; `mcp.TOOLS` has no channel write tool;
    *   `test_agent.py`: the exact expected tool list gains `episode_create`, `episode_list`,
        `episode_status`, `episode_estimate`, `episode_refresh`, `channel_list` and
        `channel_get`;
    *   vitest: the page duplicates a profile, uploads a picked file as a raw body, saves with
        `base_version`, shows the reload message on 409, and shows the shared-channel warning.

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

#### 46a. `server/src/streamstudio/episode/intro_comp.py` (Create, moved from `tools/compose/motion/intro/make_intro.py`); `server/src/streamstudio/api/routes/channels.py` (Modify)

*   **Type / Scope**: The intro template, the `channel_intro` handler and its route.
*   **Proposed Changes**: `intro_comp.build(profile, resolve, out_dir) -> Path` writes the
    composition of `make_intro.py` to `out_dir`, where `resolve(sha256) -> Path` turns a font
    field into a file. Every value `make_intro.py` varies becomes a read of the profile's `intro`
    block; the stars, sparks and timings (`S0`, `TITLE`, `DUR`, `FPS = 30` for GSAP timings) stay
    as constants:

    | `make_intro.py` literal | Line | Becomes |
    | --- | --- | --- |
    | `#050404` | 32, 33 | `intro.colours.bg` |
    | `#160b091a` | 34 | `intro.colours.glow` |
    | `#e74c3c` (ring, tile, kicker, rule start, red sparks) | 40, 43, 48, 52, 61 | `intro.colours.accent` |
    | `#c0392b` (tile gradient end) | 43 | `intro.colours.accent_dark` |
    | `#d4a017` (cursor, emphasised title, rule end, warm stars, gold sparks) | 46, 50, 52, 57, 58, 61 | `intro.colours.highlight` |
    | `#fffef7` (the logo letter) | 45 | `intro.colours.letter` |
    | `#fafafa` (title) | 49 | `intro.colours.title` |
    | `#b9b1a4` (tagline) | 53 | `intro.colours.muted` |
    | `#ffffff08`, `#ffffff24`, `#ffffff88`, `#ffffff10`, `#fff` (grid, borders, shine, track, stars) | 35, 43, 44, 51, 57 | neutral constants |
    | Newsreader 500, 600, 500 italic; JetBrains Mono 500 | 27-30 | `intro.fonts.serif`, `.serif_bold`, `.serif_italic`, `.mono` |
    | the letter `D` | 101 | `intro.logo_letter` |
    | `KICKER`, `TITLE_HTML`, `TAG` | 5-7 | `intro.kicker`, `intro.title` plus `intro.title_em`, `intro.tagline` |

    `TITLE_HTML` held raw HTML with `<em>`. The template instead escapes `title` and `title_em`
    and wraps the escaped `title_em` in `<em>` itself, so no profile string is inserted as HTML.
    `build` copies gsap from the workspace and each font file next to `index.html`.

    `POST /api/channels/{slug}/intro` enqueues `channel_intro` with the slug and the latest
    version. The handler builds the composition in its own folder,
    `data_dir/cards/intro-<slug>-<version>/`, renders it through `hyperframes.RENDER` with
    `-f 25`, and mixes the profile's `riser`, `pop`, `shimmer`, `whoosh` and `impact` slots at the
    offsets `make_intro.py` prints (0.0, 0.567, 1.3, 3.35 and 4.0 s), at the profile's `intro`
    level, fading out from 6.4 s. It stores the MP4 with `channel_files.store_path` and saves
    version N+1 naming it in `sound.intro`. If a newer version was saved meanwhile and its
    `intro` block or SFX slots differ from the ones rendered, it discards the result and logs
    "intro inputs changed; render again"; otherwise it saves on top of the newest version,
    changing only `sound.intro`. The DansLab seed never runs this job. README:
    `episode/README.md`.

#### 47. `server/src/streamstudio/episode/cards.py` (Create)

*   **Type / Scope**: `card_render` handler.
*   **Proposed Changes**: Groups consecutive card scenes by `site`; `generic_card(comp, capture, scenes, beats) -> Comp`
    (address bar, slow scroll, one zoom to the hero rect, one callout from the scenes' escaped
    `text`, beats at measured scene boundaries); writes `cards/<card>.mp4` and `cues.json`;
    records `durations_hash`, which includes the pinned profile's `look_hash`. The builder writes
    CSS variables from the palette as RGB triplets, so each literal's alpha stays a constant
    (`rgba(var(--accent-a), .55)`), and maps every literal of `tools/compose/motion/build.py`:

    | `build.py` literal | Line | Becomes |
    | --- | --- | --- |
    | `#2de2c4` (ring, caret, ripple, callout text, chip border, score heading, tick, number subtitle, lock icon) | 33, 37, 39, 43, 45, 48, 50, 54, 56, 58, 63-64 | `accent_a` |
    | `rgba(45,226,196,…)` glows | 34, 42, 48, 53, 57 | `accent_a`, alpha kept |
    | `#8c64ff` (callout bar end, loading bar end) | 43, 50 | `accent_b` |
    | `rgba(124,92,255,…)` (ring halo, callout and score borders) | 34, 41, 53 | `outline`, alpha kept |
    | `#07080d` (page), `#0c0e15` (browser bar), `#0a0b10` (blank page) | 21, 22, 23, 51 | `panel` |
    | `#161925` (address box) | 25 | `panel_2` |
    | `rgba(10,12,22,.92)`, `rgba(16,14,34,.92)` (callout gradient, chip fill), `rgba(9,11,20,.94)` (score fill) | 41, 48, 53 | `panel` and `panel_2`, alpha kept |
    | `#06231e` (tick mark on the accent) | 56 | `panel` |
    | `#c9cde0` (URL) | 27 | `muted` |
    | `#fff` (URL host, callout and chip text, score rows, number), `#eef0f7` (typed text) | 28, 36, 44, 47, 55, 57 | `text` |
    | `#fff` (flash, cursor fill), `#0b0d14` (cursor stroke), `rgba(255,255,255,.07/.06)` (hairlines), `rgba(4,5,10,.55)` (spotlight), `rgba(0,0,0,…)` (shadows), `#ff5f57`, `#febc2e`, `#28c840` (window dots) | 23, 25, 35, 42, 48-49, 53, 62, 244 | neutral constants |
    | `Inter` at weights 500, 600, 700, 800, with no `@font-face` | 21-58 | `@font-face` rules the builder writes: `small` for 500, `body` for 600, `display` for 700 and 800; each font file is added to `Comp.files`, which `Comp.write` already copies (`build.py:236-237`) |

    `build.py` holds no channel text. `scene_compose` gains the card slice; `episode_assemble`
    reads card cues; the planner gains rows 4 and 5.

#### 48. `server/tests/test_episode_cards.py` (Create)

*   **Type / Scope**: Tests.
*   **Proposed Changes**:
    *   the generic card from a fixture capture with a `<script>` string escaped;
    *   `cues.json` emitted with the four kinds;
    *   the card's CSS carries the profile's colours and `@font-face` rules, and no `build.py`
        palette literal;
    *   allowlist refusal, private-range block and redirect abort;
    *   two scenes on one host with different paths produce two captures and each card reads its
        own;
    *   the renderer stubbed through `hyperframes.RENDER`;
    *   a card scene composed with the presenter in the small rectangle and the slice offset;
    *   `channel_intro` with the fake renderer stores a 25 fps intro and saves a new version
        naming it; `<script>` in `intro.title` is escaped; the SFX land at the five offsets; a
        newer version with a changed `intro` block makes the job discard its result and log.

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

*   **Type / Scope**: Replaced by the server package or the fixture.
*   **Proposed Changes**: Deleted after files 25, 26, 35, 37, 46, 46a and 47 land; the Episode 1
    v2 storyboards survive only as the JSON fixture (file 35).

#### 53. `tools/compose/README.md`, `tools/README.md` (Modify); `tools/compose/motion/README.md`, `tools/compose/motion/intro/README.md` (Delete)

*   **Type / Scope**: Contract READMEs.
*   **Proposed Changes**: `tools/compose/README.md` keeps the two plan JSON files' description
    and points at `server/src/streamstudio/episode/README.md`; `tools/README.md` drops the
    compose and motion entries and points at the same place; the motion and intro READMEs are
    removed with their code.

#### 54. `server/src/streamstudio/episode/README.md` (Create); `server/src/streamstudio/README.md`, `web/src/README.md`, `README.md` (Modify)

*   **Type / Scope**: EGM contract READMEs not covered by the per-item lines above.
*   **Proposed Changes**: `episode/README.md` states the package contract (handlers, planner
    rows, record, ledger, profiles, the shared file store, the seed, pinning and repin,
    invariants, side effects, verification); `server/src/streamstudio/README.md` adds `episode/`
    to its subdirectory list; `web/src/README.md` adds `episode/` and `channels/`; the root
    README adds the episode and channel profiles as system boundaries, the new global invariants
    (planner the only writer of stage data; no episode clip without an approval; no upload
    without Dan's Upload private click; one charge per take; every handler reads the pinned profile; no channel value in code, channels are
    profiles) and drops "Next: YouTube upload".

#### 55. `docs/DESIGN.md` (Modify)

*   **Type / Scope**: Design reference.
*   **Proposed Changes**: "Episode production rules" gains the glossary (episode, scene, set,
    card, table overlay, take, allowance, degraded, workings, kit, channel, YouTube channel,
    channel profile, pinned profile, repin, seed, default profile, SFX slot), the -36 LUFS bed,
    25 fps, the allowance rule and the operator actions (approve script and approve budget to
    `ready`; then, optionally, Upload private and publish), and the rule that nothing uploads
    automatically; it states that the production-rule thresholds are per profile, with DansLab's as
    the seed values; one sentence notes that the saved stage layouts are called sets in prose;
    the offline compositor section points at the episode package. Rule 2 ("Workings stay until
    the video is on YouTube", `docs/DESIGN.md:354`) becomes "Workings stay until Dan purges
    them", since purge is allowed from `ready` and `cancelled` too.

#### 56. `docs/AGENTS.md`, `docs/AGENT_GUIDE.md` (Modify)

*   **Type / Scope**: Agent docs.
*   **Proposed Changes**: Document the five MCP episode tools and the two read-only channel
    tools (file 41), the script contract (file 14) and how a script names a channel
    (`profile`, or the default); the "what agents cannot do" list gains "approve a budget,
    upload, publish, cancel or purge an episode" and "create, edit, delete or make default a channel
    profile".

#### 57. `CLAUDE.md`, `PLAN.md` (Modify)

*   **Type / Scope**: Project instructions and plan.
*   **Proposed Changes**: `CLAUDE.md` Layout lists `episode/` and `web/src/channels/`; Rules add
    "the planner is the only writer of an episode's stage data; the API writes script, the
    profile pin, budget, `outputs.channel`, `outputs.upload_requested_at` and gate states", "no
    `heygen_clip` for an episode without `budget.approved_at`", "no `youtube_upload` for an
    episode without `outputs.upload_requested_at`; the pipeline stops at `ready`", "no module in `episode/` imports a heavy library at module
    level", and "no channel value in code: channels are profiles, and only the seed folder
    holds DansLab's values". `PLAN.md` gains milestone S9 (the factory) and a note that
    Decision 6 ("record and live-stream from the start") no longer drives the roadmap.

#### 58. `server/tests/test_episode_e2e.py` (Create)

*   **Type / Scope**: End-to-end test.
*   **Proposed Changes**: The three-scene fixture from script to a registered recording and
    `ready` (asserting no upload job exists), then Upload private, a fake upload and a fake
    publish, with fake HeyGen, fake YouTube, the stubbed renderer and synthetic
    clips; asserts one paid render per key, the guard applied to every scene (cue per kind) and
    to a degraded scene, frame counts on concat, the kit, the sidecar, the recordings listing, the
    purge.

### Verification Plan

*   **Build**: `make build` (web) and `make setup` (server, with the `episode` extra) on the Mac
    Studio; `make mac-app` then a cold start of StreamStudio.app passes the Stage 1 preflight.
*   **Unit tests**: `make test` (`pytest` in `server/`, `vitest` in `web/`), including
    `test_episodes.py`, `test_episode_pipeline.py`, `test_channels.py`,
    `test_episode_imports.py`, `test_episode_qa.py`, `test_episode_cards.py`,
    `test_episode_e2e.py`, `web/src/channels/channels.test.tsx` and the shared lip-sync
    fixtures.
*   **Static analysis**: `make lint` (`ruff`, `tsc -b`, `oxlint`).
*   **Coverage requirement**: every planner row, every validator rule and every ledger rule has a
    test; every profile field reaches its output (composite, mix, kit, upload) in a test, and
    every profile route has a test for its refusals; the guard fixtures pass in Python and
    TypeScript; the import test passes without the `episode` extra; the `danslab` source scan
    passes.
*   **Integration**: the Stage 0 record (file 12) exists with real numbers; one real three-scene
    episode from script to `ready` on the Mac Studio with no step outside the app, timed, then
    Dan's Upload private and Publish, is the only paid integration check. A re-render of Episode 1 v2 from the fixture
    is optional and only on Dan's approval, since it costs about 12 USD of HeyGen and compares
    against a video made from a single long take. At the end of Stage 2, Dan creates a test
    channel in the Channels page (duplicate, change the colours, plate and music, leave the
    YouTube channel empty, upload an intro, save), and one real three-scene episode for it
    reaches `ready` with no YouTube channel of its own and nothing uploaded, with no file in the
    repository changed.
*   **Success measure**: the first five daily episodes each log zero manual steps and zero
    automatic uploads, approve-budget to `ready` under 12 hours, Dan's interaction under 15 minutes, HeyGen cost within
    estimate plus allowance, and no scene with a `FAIL` verdict left undegraded or unresolved.

--------------------------------------------------------------------------------

*Drafted with EGM*
