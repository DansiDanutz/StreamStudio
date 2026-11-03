# Goldfish Annotated Review Report: channel profiles amendment

Status: resolved and re-audited (2026-11-03: review 94 fixes applied, 0 contested, 2 nits
declined; re-audit 23 fixes applied, 0 contested, 1 nit declined, residuals accepted below)

**Target:** `daily-episode-factory.md`, the 2026-11-03 channel-profiles amendment (Overview,
Goals, Non-Goals, Open Questions, CUJ 5, Glossary, the record, the script contract, "Channel
profiles", the paid step, QA, Compositor, Publish kit, Status, Assets, The smallest version,
Alternatives N/T/U, Risks, NFR, Additional Resources, Future Improvements, and plan items 1, 5,
6, 8, 9, 10, 13, 13a-13c, 14-16, 20-27, 31, 33, 34, 34a, 37-39, 41, 41a, 43, 44, 44a, 46a, 47,
48, 52, 54-57 and the Verification Plan).

Source findings: `channel_profiles_critic_report.md` (Stage 7: 2 Blockers, 24 Majors, 18 Nits)
and `channel_profiles_readiness_report.md` (Stage 9: 6 Blockers, 22 Majors, 24 Nits).
Categories: PROPOSE FIX (valid, edit applied), CONTEST (inaccurate, evidence cited), DECLINE
(nit recorded, not fixed). Each finding was checked against the repository before editing.
Where the owner had already decided how a finding is fixed, that decision was applied even when
the report proposed another fix; the row says so.

Counts:

| Report | Severity | PROPOSE FIX | CONTEST | DECLINE |
| --- | --- | --- | --- | --- |
| Critic | Blocker | 2 | 0 | 0 |
| Critic | Major | 24 | 0 | 0 |
| Critic | Nit | 17 | 0 | 1 |
| Readiness | Blocker | 6 | 0 | 0 |
| Readiness | Major | 22 | 0 | 0 |
| Readiness | Nit | 23 | 0 | 1 |
| **Total** | | **94** | **0** | **2** |

One premise was corrected while fixing: critic B2 and readiness M21 say a second channel's clips
get DansLab's occlusion. They do not. The kept `.cutout.webm` is encoded from the segmented
frames alone (`server/src/streamstudio/avatar/cutout.py:150`); the plate and seat only feed the
on-plate composite, which `_cutout_clip` writes into a work folder and deletes
(`worker/handlers.py:180-184`). The fix was still applied, as the owner decided, because the
episode path should not read DansLab's plate file at all.

## Critic report (`channel_profiles_critic_report.md`)

| ID | Category | Justification |
| --- | --- | --- |
| B1 | PROPOSE FIX | Verified: per-slug folders break a duplicate's first save. Owner decision applied: one shared store `data_dir/channels/files/<sha256>.<ext>`; duplicating copies only the JSON; `GET /api/channels/files/{sha256}` has no slug; test in 34a (duplicate, save unchanged, every path resolves). |
| B2 | PROPOSE FIX | Verified the literals (`worker/handlers.py:182`, `:263`) and the sibling desk rule (`avatar/cutout.py:83-85`); premise corrected above. Item 22: with an `episode_id`, plate, desk and seat come from the pinned profile; without one, `EDITOR_SEAT` keeps the editor unchanged. New item 22a adds `desk=` to `cutout.run`/`composite`; test in 34. |
| M1 | PROPOSE FIX | Pin only when `record.profile` is unset; `PUT /script` keeps the pin; only repin clears it. Glossary entry for Repin; repin fully defined in the transition rules and item 20; tests in 33. |
| M2 | PROPOSE FIX | `POST /api/episodes` writes the default slug into `script.profile`; test that changing the default leaves the episode unchanged. |
| M3 | PROPOSE FIX | Verified `core/config.py:12-13` (env-only settings). Default stored in `app_settings`, changed by `PUT /api/channels/default` and **Make default**; `Settings.default_profile` is the first-run value; `ensure_seed` reads every seed folder's slug, so it names none. |
| M4 | PROPOSE FIX | Owner decision applied instead of fontTools: fonts by magic bytes (OTF, TTF, WOFF2), images by Pillow, media by `ffprobe -protocol_whitelist file` with a format allowlist; sidecar records the media type; served with `nosniff`. |
| M5 | PROPOSE FIX | Verified `core/netguard.py:69-71` returns true for `None`. Every channel write needs a present and allowed `Origin`; 403 tests; NFR states the check stops cross-site requests only and names the backstops. |
| M6 | PROPOSE FIX | Duplicating clears `youtube_channel`; save refuses a channel that is not connected; approve-script checks it before money is spent; the estimate shows the channel title; the page warns on shared or empty channels. Per the owner's decision an empty channel stays allowed (not 422). **Superseded** by the manual-upload ruling: approve-script no longer checks YouTube; the channel is resolved only at Upload private. |
| M7 | PROPOSE FIX | `profiles.missing(pinned)` runs at approve-script and approve-budget before any reservation, and at create (409); recovery row rewritten (same sha256 restores the pinned version); repin allowed from `needs_dan`. |
| M8 | PROPOSE FIX | Owner decision applied: delete refused (409 with ids) while any episode in any state names the slug in the script or the pin; files never deleted; `seeded:<slug>` flag stops a deleted DansLab being seeded again; default cannot be deleted. |
| M9 | PROPOSE FIX | `ensure_seed` inside `BEGIN IMMEDIATE`, `INSERT OR IGNORE`, temp-plus-rename files; concurrency test in 34a. |
| M10 | PROPOSE FIX | `reference.presenter` recorded with the medians; approve-script clears `reference` when the resolved presenter changes; tests in 33 and 44. |
| M11 | PROPOSE FIX | Verified the existing references (`web/src/stage/Library.tsx:17,19`, `web/src/agent/catalog.ts:99`, `agent.test.ts:20-24`, `YouTubeUpload.test.tsx:38`). Goal, scan and Assets agree: the scan covers only the new code; the live studio's references are a Non-Goal; item 8 no longer writes to a DansLab path. |
| M12 | PROPOSE FIX | Verified `core/transcribe.py:96` (`-l auto`) and the English-only normaliser. Owner decision applied: any caption language, but the word-error-rate check, number-to-words, the numbers-and-rankings warning and the "Intro" label are English-only; other languages record "not checked (language)". Non-Goal, Q6 and a test in 44. |
| M13 | PROPOSE FIX | Stage 1: storage, seed, read API, save, make default, raw-body upload. Stage 2: Channels page, preview, delete, MCP read tools, each tested (item 44a). "The smallest version" states the owner requirement is fully met at the end of Stage 2; CUJ 5 tagged; route table has a Stage column. |
| M14 | PROPOSE FIX | Neutral defaults listed in a table in the doc (white/black/grey palette, no intro, no bed, silent cues, 3-13 s, 8 s, questions and reveal off, `en`); DansLab's values only in the seed; fonts required as "at least one" everywhere. |
| M15 | PROPOSE FIX | One method: `POST /api/channels/preview` with the unsaved profile as the body; returns one JPEG. |
| M16 | PROPOSE FIX | Owner decision applied: `channel_files.normalise_intro` converts an intro uploaded with `role=intro` to 25 fps keeping audio, in new item 13c; save refuses a non-25 fps intro; test in 34a. |
| M17 | PROPOSE FIX | File 15 now points to file 39; file 39 uses `rules.event_gap_s` and `rules.scene_s`. |
| M18 | PROPOSE FIX | Test 34's synthetic profile has an intro; plate pixel and intro offset asserted; 34a checks seed sha256s against `manifest.json`; `test_channels.py` in the Verification Plan; coverage line "every profile field reaches its output". |
| M19 | PROPOSE FIX | Items 54-57 amended: README contract (profiles, store, seed, pinning), glossary terms, two read-only channel tools, "create, edit, delete or make default a channel profile" in the cannot-do list, record writers, "no channel value in code" rule. |
| M20 | PROPOSE FIX | Q6 (non-English QA) and Q7 (keeping channel files) added; the default, several YouTube channels (verified `core/youtube.py:99-115`, `:128-139`) and the presenter preview are settled in "Channel profiles" and said so. |
| M21 | PROPOSE FIX | Five rows added: mistyped presenter ids (avatar checked against `heygen.Client.looks()`, `core/heygen.py:97`; no voice list exists, so ids are shown on the estimate), missing default, shared wallet (per-channel month total), unvaulted files, unlicensed music. |
| M22 | PROPOSE FIX | Migration 4 now adds four tables (with `app_settings`) in the record section, item 13 and NFR Rollout. |
| M23 | PROPOSE FIX | Glossary entries for Channel, YouTube channel and Look (script vs profile); `script.profile` is the slug and `record.profile` the pin, both stated; "fresh browser profile" in QA, Alternative J and NFR. The profile's `look` was annotated rather than renamed, to keep `look_hash` as decided. |
| M24 | PROPOSE FIX | Owner decision applied: `canonical()` defined; `look_hash` (look and presenter name) in `inputs_hash` and `durations_hash`; `sound_hash` with the assembly; publish fields reach only the kit; `latest` returns `(version, hash, Profile)`; footer-only repin test in 34. |
| N1 | PROPOSE FIX | Header line 8 points to this file; both reports and this log added to Additional Resources. |
| N2 | PROPOSE FIX | T and U moved after S; Alternative N and U texts corrected. |
| N3 | PROPOSE FIX | 13a now precedes 13b (and new 13c); 34 precedes 34a. |
| N4 | PROPOSE FIX | Builder moved into the server package (`episode/intro_comp.py`, item 46a); own work folder per job; result discarded and logged when intro inputs changed. |
| N5 | PROPOSE FIX | `PUT` carries `base_version`; 409 "profile changed; reload"; tested. |
| N6 | DECLINE | Cleaning unused files is new scope; recorded as Q7, a Non-Goal and a Future Improvement instead. |
| N7 | PROPOSE FIX | Missing profile files are 409 with the fields; 503 stays for the toolchain. |
| N8 | PROPOSE FIX | Verified `core/youtube.py:128-139`; item 20 says `pick_channel` exists and is unchanged. |
| N9 | PROPOSE FIX | Glossary gains Seed, Default profile, Channels page, SFX slot (and Repin, Channel, YouTube channel, Look). |
| N10 | PROPOSE FIX | NFR Rollout lists the router, the startup seed, health's `default_profile`, `?channels=1`, `data_dir/channels/`, the cut-out's `desk` argument, and that a revert leaves rows and files harmlessly. |
| N11 | PROPOSE FIX | Validator prose names `presenter.voice_names` and the latest-before / pinned-after rule. |
| N12 | PROPOSE FIX | Test wording: approve-budget writes `outputs.channel`; the upload uses it. |
| N13 | PROPOSE FIX | CUJ 5 defines the slug and says "new YouTube channel" and "the episode with no `profile`". |
| N14 | PROPOSE FIX | Overview: the script shape is the profile's (DansLab: questions ending in a reveal); one list of profile contents in Overview and Glossary. |
| N15 | PROPOSE FIX | Question and reveal checks are two rows. |
| N16 | PROPOSE FIX | "Channel profiles" rewritten as one rule per paragraph with a palette table. |
| N17 | PROPOSE FIX | Compositor text: a fixed table maps each cue to a slot and offset; the profile chooses the file; levels sentence reworded with its meaning. |
| N18 | PROPOSE FIX | Voice-names table removed from the seed file list (it is in `profile.json`); upload wording names the API and the Stage 2 page; paid-step sentence split; route named `GET /api/channels/files/{sha256}`; Library sentence on its own line. |

## Readiness report (`channel_profiles_readiness_report.md`)

| ID | Category | Justification |
| --- | --- | --- |
| B1 | PROPOSE FIX | Verified: `make_intro.py` has no audio (`:97-110`), the README's hand mix (`intro/README.md:13-14`), `mix.py:57` fails on a silent intro, and the red/gold palette (`make_intro.py:32-61`). Owner decision applied: DansLab's intro is not re-rendered; the seed ships the existing file converted to 25 fps with its audio; the editor's file is unchanged; an intro with no audio contributes silence. |
| B2 | PROPOSE FIX | Verified `server/pyproject.toml:35-36` packages only `src/streamstudio`. The template moves to `server/src/streamstudio/episode/intro_comp.py` (item 46a); `tools/brand/make_intro.py` is dropped; item 8 renders to a scratch path as a check only. |
| B3 | PROPOSE FIX | Same defect as critic B1; fixed by the shared store (owner decision), not by hard links. |
| B4 | PROPOSE FIX | Verified the five existing references. Scan scoped to `episode/`, `api/routes/episodes.py`, `api/routes/channels.py`, `web/src/episode/`, `web/src/channels/`; `ensure_seed` is slug-agnostic. |
| B5 | PROPOSE FIX | Verified no `python-multipart` (`server/pyproject.toml:6-11`) and the raw-body pattern (`api/routes/recordings.py:38-56`). `PUT /api/channels/files?name=` streams the body, counts 200 MB while streaming (413), 415 for the extension, 422 for the kind; type recorded in a sidecar. |
| B6 | PROPOSE FIX | Grepped `render.py`; item 25 maps every colour, font weight and channel text literal with its line. New palette fields `glow`, `panel_2`, `outline`, `muted`; fonts `display`, `body`, `small`; the Nervix end card belongs to `plan.endcard`, and `publish.endcard` was removed from the profile (owner decision). |
| M1 | PROPOSE FIX | One method, `POST /api/channels/preview`; one 1920x540 JPEG with both frames. |
| M2 | PROPOSE FIX | Repin always unlinks `final.mp4`, `final.srt`, `kit.json` and clears `outputs.recording_id` and `outputs.channel`; palette-repin test checks a rebuilt rim pixel. |
| M3 | PROPOSE FIX | Same as critic M1. |
| M4 | PROPOSE FIX | `EpisodeOut` gains `profile_name` and `profile_latest_version`; "changed" defined from them. |
| M5 | PROPOSE FIX | `POST /` checks `profiles.missing` (409, per critic N7 rather than 503); test in 33. |
| M6 | PROPOSE FIX | Same as critic M14: fonts "at least one"; every default listed. |
| M7 | PROPOSE FIX | `role=intro` conversion at upload; fonts checked by magic bytes (Pillow cannot open WOFF2, which the intro needs); tests in 34a. |
| M8 | PROPOSE FIX | Owner decision applied instead of the proposed "status not in published, purged, cancelled": delete refused while any episode in any state names the slug, found by `json_extract` on the script slug and the pin; 409 codes stated; files kept. |
| M9 | PROPOSE FIX | New item 44a: delete, preview and MCP tests, plus a vitest file; the MCP check moved there from Stage 1. |
| M10 | PROPOSE FIX | Verified clip keys are hashes (`worker/handlers.py:206-209`). Lookup rule: newest `done` `heygen_clip` job with `payload.look == avatar_id` whose cut-out exists, else a silhouette; Stage 2 card frame is the compositor card scene. |
| M11 | PROPOSE FIX | `preflight.check(s, conn, stage)` reads the stored default; a missing row is a `missing` entry; health passes its connection. |
| M12 | PROPOSE FIX | Verified `api/main.py:28-30` and `worker/main.py:64-65`. Seed after `db.migrate(c)` in `create_app`, and once in the worker's `run()` before threads start (once per process, not per thread). |
| M13 | PROPOSE FIX | Same as critic M24: `latest` returns `(version, hash, Profile)`; canonical JSON defined. |
| M14 | PROPOSE FIX | Same as critic M12, by the owner's decision. Passing the language to whisper was not adopted: `-l auto` already detects it (`core/transcribe.py:96`), and captions take their words from the script. |
| M15 | PROPOSE FIX | Every skipped optional file logs "Profile X has no <field>; skipped" (compose and mix); test with no intro, no bed and one empty slot. |
| M16 | PROPOSE FIX | Verified `mix.py:22, 26, 61, 94-118` and `render.py:26`. Item 6 has a source table: each seed file, its source path and its profile field. |
| M17 | PROPOSE FIX | Verified against `mix.py:31-133`. Item 26 carries the per-track loudnorm, bed loop, crossfade, fades and start, cue gains and offsets (whoosh -0.2 s) and the final encode exactly. |
| M18 | PROPOSE FIX | Grepped `build.py`; item 47 maps every literal and weight; CSS variables keep each alpha; the builder writes `@font-face` and adds the files to `Comp.files` (`build.py:236-237`). |
| M19 | PROPOSE FIX | Verified `db._split` (`core/db.py:139-146`). The index is its own `CREATE UNIQUE INDEX ... WHERE kind = 'charge'` statement; no `;` or `--` in literals. |
| M20 | PROPOSE FIX | Verified `avatar/cutout.py:70-108`. Item 25 imports `HANDS_IN_CLIP` and `fit_cover` inside the functions and takes the desk from the profile, never `desk_layer_for`. |
| M21 | PROPOSE FIX | Same as critic B2. The 0.66/0.68 against 0.60/0.70 seat mismatch only reaches the discarded on-plate composite; the episode path now uses the pinned seat. |
| M22 | PROPOSE FIX | Same as critic M13. |
| N1 | PROPOSE FIX | Same as critic N3. |
| N2 | PROPOSE FIX | Same as critic M17. |
| N3 | PROPOSE FIX | Unknown-profile error keyed `_script`; signature `validate(script, profile: Profile \| None)`; row named, not counted. |
| N4 | PROPOSE FIX | 34a says the seed validates once its paths are replaced by sha256s. |
| N5 | PROPOSE FIX | Body slug mismatch 422, unknown slug 404, bad or reserved slug 422, preview needs `Origin`; all tested. |
| N6 | PROPOSE FIX | Script overrides stated in the contract and item 14. "Default set by env only" is superseded by the stored default (critic M3). |
| N7 | PROPOSE FIX | Verified `make_intro.py:6`. `title` and `title_em` are escaped and the template adds the `<em>`; `build` copies gsap and the fonts. |
| N8 | PROPOSE FIX | `default_profile` is top-level in health; HyperFrames checked at `data_dir/cards/node_modules/hyperframes/package.json`; versions through `media.tool_version` (`core/media.py:76`, called at `system.py:58`). |
| N9 | PROPOSE FIX | Item 6 names `data_dir/heygen.json` keys `avatar_id` and `voice_id` (`core/heygen.py:45-48`) and notes the editor keeps reading them. |
| N10 | PROPOSE FIX | Verified `api/main.py:20-22, 54-57`; Assets states the seed served at the web root is accepted. |
| N11 | PROPOSE FIX | `youtube_channel` validated with `youtube.CHANNEL_ID` (`core/youtube.py:30`). |
| N12 | PROPOSE FIX | Verified `core/youtube.py:288-301`. The kit shortens the body, never the footer, and lists dropped tags in `notes`; tested. |
| N13 | PROPOSE FIX | Item 31 labels `index.css` Modify; item 41a adds the `.channels` breakpoint. |
| N14 | PROPOSE FIX | Verified `mcp.py:208`; `channel_get` uses `_seg(slug)`; tested in 44a. |
| N15 | PROPOSE FIX | Item 56 says five episode tools and two channel tools; `test_channels.py` in the Verification Plan. |
| N16 | PROPOSE FIX | `reveal` added to the Compositor cue list and the item 26 cue table. |
| N17 | PROPOSE FIX | Added: `channel_intro` tests in item 48; no-channel upload test in 33; palette repin through approve-script and a zero-line approve-budget in 34; `<script>` escape tests for intro and card. |
| N18 | PROPOSE FIX | "repin" throughout; the button is named once with its route. |
| N19 | PROPOSE FIX | The 70-word pinning sentence is now separate paragraphs and a list. |
| N20 | PROPOSE FIX | "A profile has this shape:"; defaults point to the "Default levels" table by name. |
| N21 | PROPOSE FIX | The route table has a Stage column. |
| N22 | PROPOSE FIX | Applied with critic N2, since the same sentences were rewritten ("adding a channel is a pull request", "from his phone", no quoted rule). |
| N23 | DECLINE | Pure wording. Line 8 was rewritten for this log anyway; the Overview and CUJ phrasings are kept. |
| N24 | PROPOSE FIX | Partial: approve-budget split into sub-bullets, the cue mapping is a table, the debounce clause rewritten. Rewrapping long lines declined as wording. |

## Left for the owner

*   **Q6 and Q7** stay open in the design: when a non-English channel needs its own QA
    normalisers, and whether channel files are vaulted or cleaned.
*   **Empty `youtube_channel`.** As decided, a profile may leave it empty. With only DansLab's
    YouTube channel connected, such a profile's episodes would upload to DansLab; the estimate
    screen says "Upload channel: DansLab (the only connected channel; this profile names
    none)". Since the manual-upload ruling nothing uploads before Dan clicks Upload private, so
    this is information, not a gate (superseded part: the approve-script check).
*   **Tag text colour.** Settled after review: a ninth palette field, `tag_text`, keeps it
    exact (see the manual-upload section).
*   **Seed sources.** The bed, the eight SFX and the Inter OTFs are on the Linux box
    (`MEDIA_LIB`, `/usr/share/fonts/opentype/inter/`); someone copies them into
    `assets/channels/danslab/` and fills each licence note in `manifest.json`.

## Owner change after review: upload is a manual click (2026-11-03)

The owner's words: "I don't want anything to upload automatically yet." He is also not
connecting more YouTube channels for now. Applied throughout `daily-episode-factory.md`:

*   **New end state `ready`.** Once the final MP4 is registered with its kit and SRT, planner
    row 9a sets `ready`, releases the reservation and stops. Row 10 enqueues `youtube_upload`
    only when `outputs.upload_requested_at` is set; row 11 is unchanged.
*   **New click, `POST /api/episodes/{id}/upload` (Upload private).** Only from `ready`; needs a
    present and allowed `Origin`; no MCP tool. It resolves the YouTube channel with
    `pick_channel` (409 when not connected or ambiguous), writes `outputs.channel` and
    `outputs.upload_requested_at`, and enqueues the planner. The upload stays private; Publish
    follows `uploaded_private` as before.
*   **YouTube gates nothing before the upload.** Channel resolution and its 409s are removed
    from approve-script and approve-budget; the estimate shows "Upload channel: <title>, or not
    connected (connect before uploading)" as information. Profile save still checks a changed,
    non-empty `youtube_channel`. Episodes build to `ready` with zero connected channels.
*   **Transitions.** Script edit and repin are allowed in `ready` and refused once an upload is
    requested; cancel up to `ready`; purge from `ready`, `published` and `cancelled`.
*   **Clicks counted honestly.** Two clicks to `ready` (approve script, approve budget), then
    optional Upload private and Publish. Overview, Goals, CUJs 1, 2, 3 and 5, the smallest
    version, Stage 1's title, the planner table, items 20, 24, 30, 31, 33, 34, 41, 43, 55-58,
    Risks, NFR and the Verification Plan are updated. No auto-upload setting; it is one line in
    Future Improvements.
*   **Open item 2 settled.** A ninth palette field, `tag_text` (DansLab `#ECEEF6`), keeps
    Episode 1 v2's tag text exact.
*   **Open item 3.** Copying the seed files from the Linux box is a Stage 0 task in item 6, by
    Dan or an agent on the Linux box; every licence note is filled in before Stage 1, and test
    34a checks it.
*   **Open item 1 stands.** With uploads manual, the estimate screen and the Upload private click
    both show the YouTube channel before anything is uploaded.

Settled after this section was written: item 28a removes the MCP `youtube_upload` tool and
requires a present, allowed `Origin` on the take upload route; the re-audit below adds the
`POST /api/jobs` allowlist and keeps episode recordings out of the take upload route.

## Re-audit (2026-11-03)

Source: `channel_profiles_reaudit_report.md`, the single allowed re-audit (1 Blocker, 10
Majors, 13 Nits after deduplication). It found every original Blocker and Major fixed and
contested none. Each claim below was checked against the repository before editing.

| Severity | PROPOSE FIX | CONTEST | DECLINE |
| --- | --- | --- | --- |
| Blocker | 1 | 0 | 0 |
| Major | 10 | 0 | 0 |
| Nit | 12 | 0 | 1 |
| **Total** | **23** | **0** | **1** |

| ID | Category | Resolution |
| --- | --- | --- |
| B1 | PROPOSE FIX | Verified `api/routes/jobs.py:26-34` enqueues any registered kind with no `Origin`, and that nothing in `web/src` posts to `/api/jobs`. Item 28a: `create_job` accepts only `API_KINDS = {"noop", "probe", "transcribe"}`; every other kind is 403 naming its dedicated route; tests in `test_api.py`. Risks, NFR Security and Rollout updated. |
| M1 | PROPOSE FIX | New planner row 0: a recorded stage job in `error` (attempts spent) sets `needs_dan` with the reason. Row 10 needs `upload_job_id` unset. Advance moves errored job ids to `prev_job_id` (row 2 transfers the clip claim from it), then sets `uploaded_private`, `ready` (upload requested, so row 10 resumes the upload) or `in_progress`. Publish and Refresh are synchronous (502, state unchanged). Tests in item 34. |
| M2 | PROPOSE FIX | Verified `api/routes/youtube.py:101-121` and `YouTubeUpload.tsx` accept any take and public privacy. Item 28: the take upload route refuses an episode's recording with 409 ("use the episode's Upload private"); the picker leaves episode entries out. Publish kit text and tests updated. |
| M3 | PROPOSE FIX | Row 9a fires from `budget_approved` or `in_progress`; the palette-repin test ends in `ready`. |
| M4 | PROPOSE FIX | The planner acts only in `budget_approved`, `in_progress` and `ready` with an upload requested; elsewhere it returns. Test: a clip finishing in `draft` enqueues nothing. |
| M5 | PROPOSE FIX | `PUT /script` allowed from `needs_dan` (transition rule, item 20, test 33). |
| M6 | PROPOSE FIX | With an empty profile channel the estimate names the channel Upload private would use, or "not connected", or "several connected". CUJ 5, "The YouTube channel", the paid step, items 20 and 31 and test 33 updated. |
| M7 | PROPOSE FIX | Owner decision applied instead of the report's 422: one answer, 409 "default profile X missing", at create. Preflight runs with `profiles=False` at create (503 for toolchain only); health uses `profiles=True`. Items 9, 10, 20, the Status section and test 33 updated; the Risks row already said 409. |
| M8 | PROPOSE FIX | Verified `test_agent.py:62-67` and `:84-89`. Item 28a drops `youtube_upload` from the exact list and its call block; item 44a adds `test_agent.py` with the seven new tools. |
| M9 | PROPOSE FIX | Rollout names the two non-additive Stage 1 changes (items 28, 28a) and the `/api/jobs` allowlist; reverting restores agent take upload. |
| M10 | PROPOSE FIX | Verified root `README.md:99-101`, `server/src/streamstudio/README.md:31` and the `youtube.py` docstring. All three are in item 28a. |
| N1 | PROPOSE FIX | Cancel moved from test 33 to test 44. |
| N2 | PROPOSE FIX | A second Upload private is 409; the page shows "Uploading…". |
| N3 | PROPOSE FIX | The page polls while `ready` with an upload requested. |
| N4 | PROPOSE FIX | Purge states aligned in the Goal, the record and the diagram. |
| N5 | PROPOSE FIX | NFR now says no MCP tool and no cross-site page can upload; a forged local `Origin` is the accepted residual. |
| N6 | PROPOSE FIX | MCP sentence lists upload. |
| N7 | PROPOSE FIX | Row 11 only sets `uploaded_private`. |
| N8 | PROPOSE FIX | `avatar/cutout.py:153` (the `encode_alpha_webm` call). |
| N9 | PROPOSE FIX | Verified `api/routes/heygen.py:26` and `HeygenPanel.tsx:7`; item 18 reworded. |
| N10 | PROPOSE FIX | Item 25 uses `preview_frames(s, conn, profile)`. |
| N11 | DECLINE | Intended: saving a changed `youtube_channel` that is not connected stays 422, so a typo is caught on save. It gates nothing in the pipeline. |
| N12 | PROPOSE FIX | This log: M6 row and the empty-channel bullet marked superseded; the MCP `youtube_upload` paragraph marked settled; tag text marked settled. |
| N13 | PROPOSE FIX | Item 55 rewrites `docs/DESIGN.md` rule 2; the `danslab` scan covers only `*.py`, `*.ts`, `*.tsx`. The optional `Origin` on publish, purge, repin and cancel is not applied (residual 2). |

### Accepted residuals

1.  **A local client that forges `Origin`.** The `Origin` check stops cross-site browser
    requests and MCP, not a process on the tailnet that sets the header. The backstops are the
    budget screen, the stop at `ready`, the private upload and the `/api/jobs` allowlist.
2.  **No presence check on publish, purge, repin and cancel.** The middleware already refuses a
    disallowed `Origin`, so cross-site pages cannot reach them; a presence check would only stop
    non-browser clients, which can forge it (residual 1). MCP has no tool for any of them.
3.  **Profile save checks the YouTube channel** (N11, declined above).
4.  **Q6 and Q7** stay open in the design.
