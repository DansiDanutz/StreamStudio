# Goldfish Review Report: channel profiles amendment (Stage 7 Critic Review)

**Target:** `docs/egm/daily-episode-factory/daily-episode-factory.md` (2026-11-03 amendment only: Overview 12-33, Goals 97-108, Non-Goals 109-132, CUJ 5 206-219, Glossary 227-258, record 305-374, contract 375-426, "Channel profiles" 427-497, paid step 555-570, Compositor 648-689, Publish kit 690-713, Status 742-763, Assets 764-784, Smallest version 785-799, Alternatives N/T/U 917-940, Risks 996-998, NFR 1012-1046, Future Improvements 1067-1090, and the plan items that touch profiles)

**Owner requirement checked:** every channel can be created and changed inside the studio without code changes, and DansLab is the default.

**Date:** 2026-11-03

## Reviewer Status

| Reviewer | Status | Standard |
| --- | --- | --- |
| `egm-design` | completed | feature-spec-standard.md |
| `egm-structural` | completed | feature-spec-standard.md |
| `egm-style` | completed | persona REVIEW vectors (no style standard supplied) |

Each reviewer ran as a single instance. The reviewers could not run `git diff`, so they found the amendment from the section list and by searching for "profile". The synthesizer re-checked the two Blockers and the code claims in findings 3 and 5 against the document and the repository.

## Summary

| Severity | Count |
| --- | --- |
| Blocker | 2 |
| Major | 24 |
| Nit | 18 |

**Verdict:** revise. The versioned, never-updated profile model and the pinning idea are sound, and so are Alternatives T and U, the cost of a presenter change flowing through the clip key, and channel resolution under the row lock. As written, though, the two core owner flows break. A channel duplicated in the studio cannot be saved. A second channel's avatar is still cut out against DansLab's plate by code the plan leaves alone.

---

## Prioritized Findings (Blockers -> Major -> Nits)

### B1. Duplicating a profile shares sha256 entries, but files are stored per slug, so the new profile's first save fails - Severity: Blocker
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** "Channel profiles" lines 431-435; file 13b lines 1251-1254 (`save` checks files under `channels_dir/<slug>/files/`; `file_path(s, slug, sha256)`); file 21a lines 1377-1379 ("sharing files by copying their sha256 entries"); CUJ 5 lines 206-218.
* **Discrepancy Description**: Files live at `data_dir/channels/<slug>/files/<sha256>.<ext>`. `POST /` with `from` copies only the sha256 references. A profile duplicated from DansLab therefore names files that exist only under `channels/danslab/files/`. Its first `PUT` fails the existence check. If the check passed, `file_path(s, newslug, sha)` would still find nothing at render time. CUJ 5 starts with exactly this step, so the owner's main flow ("create a channel in the studio") fails at the first save.
* **Rationale & Recommendation**: Use one content-addressed store for all profiles: `data_dir/channels/files/<sha256>.<ext>`, with `file_path(s, sha256)` and the slug segment dropped from `GET /api/channels/files/{sha256}`. This also removes duplicate copies. If per-slug folders must stay, change 21a to "`POST /` hard-links (or copies) every named file into the new slug's folder before inserting version 1". Add a test to file 34a: "duplicate DansLab, then `PUT` unchanged, succeeds and the composite renders".

### B2. The worker's cut-out still hard-codes DansLab's plate and seat, so a second channel needs a code change - Severity: Blocker
* **Reviewer Lens:** `egm-design` (with `egm-structural` F4)
* **Affected Scope:** Goal "Any channel, no code change" lines 97-103; file 22 lines 1387-1405; existing code `server/src/streamstudio/worker/handlers.py:182` (`cutout_run(..., scale=0.66, hands_y=0.68, x=0.47)`) and `:263` (`plate = s.assets_dir / "studio" / "plate-landscape-final.png"`); `avatar/cutout.py` (the desk is found as a sibling `<plate>.desk.png`).
* **Discrepancy Description**: `heygen_clip` makes every episode clip's cut-out against DansLab's plate, with DansLab's seat geometry hard-coded. File 22 changes `heygen_clip` but not this. The "danslab" scan in test 34a cannot catch it, because the path says `studio/plate-landscape-final.png`, not "danslab". The desk file is found by a sibling-file naming rule, which cannot work once files are stored as `<sha256>.<ext>`. A profile with a different plate, desk or seat gets DansLab's occlusion, or needs a code change. Either way the owner requirement fails.
* **Rationale & Recommendation**: Add to file 22: "With an `episode_id`, `heygen_clip` reads `look.plate.image`, `look.plate.desk` and `look.plate.seat` from the pinned profile (`profiles.pinned`) and passes them to the cut-out. With none, it keeps today's behaviour for the live studio." Give `cutout.composite`/`cutout_run` an explicit `desk: Path | None` argument instead of the sibling-file rule. Add an assertion to test 34: the synthetic profile's seat values reach `cutout_run`.

---

### M1. Any script edit silently repins to the latest profile, and "repin" is never defined - Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-style`
* **Affected Scope:** transition rules lines 350-368; Pinning lines 470-478; Risks row 997 ("or keep the pinned version"); file 20 lines 1350-1352; Alternative U line 939.
* **Discrepancy Description**: `approve-script` always pins the latest version, and `PUT /script` sends the episode back to `draft`. So fixing one typo moves the episode to the newest profile. That can bring a new presenter and repaid clips. The **Use latest profile** button then does nothing new, and the risk row's "keep the pinned version" cannot be done. File 20 says `repin` "clears `record.profile`", but the prose never says so. The action is called "Use latest profile", "repin", "re-pinned" and "Re-pinning", and none of these is defined.
* **Rationale & Recommendation**: In Pinning: "approve-script pins the latest version only when `record.profile` is empty or its slug differs from the script's slug; otherwise it keeps the existing pin. Only `POST /{id}/repin` clears `record.profile`." Add a Glossary entry: "**Repin**: replace an episode's pinned profile with the latest version, through the **Use latest profile** button (`POST /api/episodes/{id}/repin`). The episode returns to `draft`." Add a test to file 33: a script edit after a profile save keeps the old pin.

### M2. A script with no `profile` is resolved to the default late, so changing the default can switch an episode's channel - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** contract lines 380, 401-402; file 20 lines 1350-1351.
* **Discrepancy Description**: `s.default_profile` is resolved at each approve-script, not when the episode is created. If the default changes, or Dan repins a waiting DansLab draft, the episode becomes another channel, with a different presenter and a different YouTube channel.
* **Rationale & Recommendation**: "At `POST /api/episodes`, a script with no `profile` gets the current default slug written into `script.profile`, and the response shows it. From then on the slug changes only through `PUT /script`." In the fixture test, assert that the slug was filled in at create.

### M3. Changing the default needs an environment variable and a restart, and the seed loader is hard-wired to `danslab` - Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-structural` (F12a), `egm-style` (22)
* **Affected Scope:** "The default" lines 460-468; Settings line 780; file 5 line 1140; file 13b lines 1255-1256.
* **Discrepancy Description**: `Settings` is a pydantic `BaseSettings` read from `STREAMSTUDIO_*` or `.env` (`core/config.py:12-13`, confirmed), and there is no settings API or UI. "Another profile can be made the default by changing the setting" therefore cannot be done in the studio. A default that names a missing slug fails every script that has no `profile`. `ensure_seed` names `danslab` and `assets/channels/danslab/` directly, which is a second literal in `server/src/` beside `config.py`.
* **Rationale & Recommendation**: Store the default in the database (an `is_default` flag or a `channel_settings` row). Set it with a "Make default" action on the Channels page through `PUT /api/channels/{slug}/default`, with the same Origin rule as other writes. `Settings.default_profile` becomes only the value used on first start. Refuse to make a profile without its required files the default. At startup, fail or warn in health when the stored default has no row. `ensure_seed` loads every folder under `assets/channels/*/` by its `profile.json` slug, so the loader names no slug. Rewrite line 468 with an actor: "Dan makes another profile the default with **Make default** on the Channels page."

### M4. The upload check refuses fonts, lets ffprobe follow links inside files, and never says how the served type is set - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** "Editing" line 492; NFR Security lines 1022-1025; file 13b line 1253; file 21a line 1382.
* **Discrepancy Description**: "ffprobe or Pillow must open it": neither opens OTF or TTF, so `look.fonts` cannot be set in the studio. Given untrusted input, ffprobe will follow HLS and `concat` lists, which can read local files or make network requests. `GET /files/{sha256}` serves "the stored type", but nothing records that type.
* **Rationale & Recommendation**: Check each field against its own formats:
  * images: Pillow, PNG, JPEG or WebP only;
  * fonts: `fontTools.ttLib.TTFont`, OTF or TTF only;
  * audio and video: `ffprobe -protocol_whitelist file`, with `format_name` in an allowlist (mov/mp4, wav, mp3, m4a, flac, ogg).

  Store the detected MIME type in a `<sha256>.json` sidecar. Serve files with that type and `X-Content-Type-Options: nosniff`. Add `fontTools` to the `episode` extra.

### M5. The "browser-only" write check lets requests without an Origin header through - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** NFR Security lines 1025-1026; file 21a lines 1382-1383; file 34a line 1570.
* **Discrepancy Description**: `netguard.origin_allowed(None)` returns `True` ("not a browser request", `core/netguard.py:69-71`, confirmed). Approve-budget is protected only because file 20 also requires the header to be present. As 21a is written, curl or an agent can rewrite a profile's presenter, footer or `youtube_channel` without an Origin header. Even with the header required, the check blocks cross-site requests only. It does not authorise anyone.
* **Rationale & Recommendation**: In 21a: "Every write requires an `Origin` header that is present and passes `origin_allowed`." Add a test to 34a: a write with no Origin returns 403. Add one sentence to the NFR: the check stops cross-site requests, not tailnet clients; pinning, the budget screen and private upload are the backstop.

### M6. A copied or missing YouTube channel is only caught after the money is spent - Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-structural` (F12c)
* **Affected Scope:** profile shape line 440; paid step lines 561-567; CUJ 1 cost screen lines 158-160; CUJ 5 lines 208-211; Risks row 996.
* **Discrepancy Description**: Duplicating DansLab copies `UCCPMUreEqO1x11YiAhzLusA`. If Dan forgets to change it, the new channel's episodes upload to DansLab. A profile with no `youtube_channel` falls back to "the one connected channel", which is DansLab's channel today. The channel is resolved inside approve-budget, but the cost screen does not show it.
* **Rationale & Recommendation**:
  * Duplicating clears `youtube_channel`.
  * Only the seed may leave it out; for any other profile, saving without it returns 422.
  * `GET /estimate` resolves the channel and shows its title on the confirm screen, with the same 409 conditions.
  * The Channels page warns when two profiles name the same channel.

### M7. Recovery from a missing profile file cannot be reached, and the check runs against the wrong version - Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-structural` (F15)
* **Affected Scope:** Risks row 998; transition rules lines 350 and 365 (repin and `PUT /script` are not allowed from `needs_dan`); Status lines 760-762; file 9 line 1201; file 20 line 1343.
* **Discrepancy Description**: The recovery "re-upload, save, Use latest profile" needs repin from `needs_dan`, which is not an allowed state. The create-time check reads the latest version, not the pinned one, and nothing checks again before money is spent. Because files are stored by content, re-uploading the same file already repairs the pinned version without a repin. File 20's `POST /` does not include the profile check that line 761 promises.
* **Rationale & Recommendation**: Run `profiles.missing(pinned)` at approve-script and at approve-budget, before any reservation, and return 409 naming the fields. Add the same check to file 20's `POST /` sequence. Rewrite row 998's recovery: "re-upload the same file (the same sha256 restores the pinned version), then Advance; or repin". Either allow repin from `needs_dan` or say why not.

### M8. Deleting a profile breaks history, and `ensure_seed` brings back a deleted DansLab - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** "The default" line 467; "Editing" lines 493-494; file 13b line 1255.
* **Discrepancy Description**: A hard delete leaves published, purged and cancelled episodes pinned to a `{slug, version}` that no longer exists, so their archive and status views break. If the slug is reused, version 1 comes back with different content. Drafts that name the slug but have no pin are not protected. If Dan makes another profile the default and deletes DansLab, the next start re-seeds it.
* **Rationale & Recommendation**: `DELETE` archives the profile (an `archived_at` column): it is hidden from lists and refused in new scripts, its rows and files are kept, and its slug is never reused. Also refuse deletion while any episode's `script.profile` names the slug. `ensure_seed` skips any slug that has ever had a row.

### M9. The API and the worker race when seeding at first start - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** file 13b lines 1255-1257.
* **Discrepancy Description**: Both processes call `ensure_seed` on a fresh database. Two plain inserts of `(danslab, 1)` hit the primary key, and one process crashes on first launch.
* **Rationale & Recommendation**: "`ensure_seed` runs inside `BEGIN IMMEDIATE` with `INSERT OR IGNORE`. Files are written to a temporary name and renamed, and existing files are skipped." Add a test: two concurrent `ensure_seed` calls give one row and no error.

### M10. A repin that changes the presenter leaves the QA reference stale and uses up paid re-renders - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** Pinning lines 474-478; record `reference` line 329; QA lines 603-604; planner row 3 line 518.
* **Discrepancy Description**: `reference` holds the face-box and lip-ratio medians from the first full pass, and nothing resets it. After a repin that changes the avatar or motion, new clips are measured against the old presenter. They fail QA, and each failure spends a paid re-render from the allowance.
* **Rationale & Recommendation**: "When a repin or a script edit changes the resolved `avatar_id`, `motion` or script `look`, `reference` is cleared; planner row 3 rebuilds it from the next full pass."

### M11. Three places disagree on where the one allowed `danslab` literal lives, and the scan fails on files the plan keeps - Severity: Major
* **Reviewer Lens:** `egm-structural` (F4), `egm-design` (12), `egm-style` (10)
* **Affected Scope:** Goal lines 97-103; Assets lines 768-771; file 5 line 1140; file 6 lines 1162-1164; file 8 line 1179; file 34a lines 1571-1572.
* **Discrepancy Description**: The Goal allows one constant in "the seed loader". File 5 and test 34a put it in `config.py`. The Goal says "no file in the repository", but the test scans only `server/src/` and `web/src/`. The scan would already fail on `web/src/stage/Library.tsx:17-19`, `web/src/agent/catalog.ts:99`, `web/src/agent/agent.test.ts:20-24` and `web/src/publish/YouTubeUpload.test.tsx:38`, which file 6 keeps working on purpose. File 8 hard-codes `-o assets/brand/danslab-intro.mp4`.
* **Rationale & Recommendation**: Goal: "No file under `server/src/streamstudio/episode/`, `api/routes/{episodes,channels}.py` or `web/src/{episode,channels}/` names a channel, except the first-boot default in `config.py`." Make test 34a scan the same paths. List the live-studio intro item as an allowed exception, tied to the live-studio Non-Goal. File 8 writes to its `<out.mp4>` argument. Assets line 769: "Apart from the first-boot default, the seed is the only place a channel's values live in the repository."

### M12. Non-English profiles are accepted, but QA, the validator and chapters work only in English - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** Glossary lines 240-243; Non-Goals lines 124-126; profile `language` line 439; QA lines 612-615; file 37 line 1630; file 27 line 1470; `core/transcribe.py:96` (`-l auto`).
* **Discrepancy Description**: The parts that depend on language are English-only:
  * The word-error-rate normaliser converts numbers to English words.
  * The sources check matches English claim words.
  * Chapters are hard-coded as `"0:00 Intro"`.
  * whisper ignores the profile's language.
  * The synthetic `ro` test checks only the caption-language file.

  A non-English channel would get false QA failures, which spend money, and fixing them needs code.
* **Rationale & Recommendation**: Either:
  * (a) limit `language` to `en` in v1, with any other value refused with 422, and add a Non-Goal: "non-English channels need per-language QA normalisers and validator word lists"; or
  * (b) add `publish.intro_chapter_label` and `rules.claim_words`, pick the QA normaliser by language (and skip the word-error check when the language has none), and pass `-l <language>` to whisper.

### M13. What ships in Stage 1 contradicts itself, and the owner requirement is first met in Stage 2 without saying so - Severity: Major
* **Reviewer Lens:** `egm-design` (14), `egm-structural` (F6, F17), `egm-style` (2, 4, 15)
* **Affected Scope:** Smallest version lines 787 and 795-796; "Editing" lines 486-496; file 21a lines 1376-1384; CUJ 5 lines 206-218; file 34a line 1570.
* **Discrepancy Description**:
  * Line 787 says Stage 1 has a profile "read API", while line 795 lets Stage 1 save profiles through the API.
  * Line 796 puts file upload in Stage 2, but 21a ships `POST /{slug}/files` in Stage 1.
  * "Editing" marks only `/intro` with its stage.
  * CUJ 5 uses the Channels page and preview (Stage 2) but has no stage tag.
  * Test 34a (Stage 1) asserts that MCP has no write tool, but the MCP channel tools only arrive in Stage 2.
  * Saving through the API with an Origin header is not "inside the studio". The owner requirement is therefore met only in Stage 2.
* **Rationale & Recommendation**: Lines 787 and 795-796: "Stage 1: the profiles table, the DansLab seed and the channels API (list, create, read, save, file upload). Stage 2: the Channels page, preview and delete. The owner requirement (create and change channels in the studio) is met at Stage 2; in Stage 1 a second channel exists only as a test fixture." Alternatively, move a minimal Channels page (list, duplicate, form, file pickers, save) into Stage 1. Replace the "Editing" route list with a table that has a Stage column. Tag CUJ 5 "(Channels page and preview from Stage 2)". Move the MCP assertion to a Stage 2 test.

### M14. Field defaults would put DansLab's values in code, and the required fields disagree - Severity: Major
* **Reviewer Lens:** `egm-structural` (F5), `egm-design` (18), `egm-style` (11)
* **Affected Scope:** lines 448 and 453-455; Compositor line 677; Status line 761; file 9 line 1201; file 13b lines 1247-1249.
* **Discrepancy Description**: "Every field has a default except ..." makes the pydantic `Profile` carry DansLab's palette, fonts, levels and rules as code constants. That breaks the Goal. A font cannot have a default without a font file in code. Line 761 and file 9 also treat fonts as required, while line 453 does not.
* **Rationale & Recommendation**: "A new profile takes its values from the profile it duplicates (`POST /` with `from`). The `Profile` model has no channel defaults except `language: "en"` and the LUFS levels." Add `look.fonts` to the required list on line 453 so it agrees with lines 761 and 1201.

### M15. The preview endpoint has two names in one section - Severity: Major
* **Reviewer Lens:** `egm-structural` (F7), `egm-style` (3)
* **Affected Scope:** line 488 against lines 493, 1384 and file 41a line 1672.
* **Discrepancy Description**: The section names both `GET /api/channels/{slug}/preview.jpg` and `POST /{slug}/preview`. A GET cannot carry the unsaved form.
* **Rationale & Recommendation**: Line 488: "(`POST /api/channels/{slug}/preview`, which the compositor renders from the unsaved form and returns as a JPEG)".

### M16. Converting an uploaded intro to 25 fps has no owner in the plan - Severity: Major
* **Reviewer Lens:** `egm-structural` (F8), `egm-design` (17)
* **Affected Scope:** Compositor lines 674-675; files 13b and 21a; CUJ 5 line 211.
* **Discrepancy Description**: The design converts an intro "once, when it is uploaded". But `POST /files` does not know that a file is an intro, and no file or test does the conversion.
* **Rationale & Recommendation**: Convert at `PUT /{slug}` when `sound.intro` changes: store the 25 fps file and replace the sha256. Alternatively, convert once in `episode_assemble`, cached by the source sha256. Add a test to 34a: a 30 fps intro ends up at 25 fps.

### M17. The validator plan has a wrong cross-reference and a hard-coded threshold - Severity: Major
* **Reviewer Lens:** `egm-structural` (F9)
* **Affected Scope:** file 15 line 1286; file 39 lines 1645-1646.
* **Discrepancy Description**: File 15 points to "(file 40)", but the validator change is file 39. File 39 keeps "the consecutive-avatar 8 s rule", which contradicts `rules.event_gap_s` (lines 416 and 449).
* **Rationale & Recommendation**: Change "(file 40)" to "(file 39)". In file 39, write "the consecutive-avatar rule over `profile.rules.event_gap_s`" and "length against `profile.rules.scene_s`".

### M18. The new Goals are not fully traced to tests and the Verification Plan - Severity: Major
* **Reviewer Lens:** `egm-structural` (F10)
* **Affected Scope:** Goals lines 99-107; file 34 lines 1592-1595; file 34a lines 1564-1565; Verification Plan lines 1864-1871.
* **Discrepancy Description**: The "Any channel" Goal names plate, colours, intro, bed, caption language, footer and YouTube channel. Test 34 checks neither the plate nor the intro, and the synthetic profile has no intro. The "DansLab default" Goal names plate, seat, Inter, the logo intro and the cue sounds. Test 34a checks only palette, levels, rules, language and channel. The Verification Plan leaves out `test_channels.py`.
* **Rationale & Recommendation**: Test 34: give the synthetic profile an intro, and assert a sampled plate pixel and the intro's offset in the output. Test 34a: "the seed's plate, seat, font and intro sha256s equal `manifest.json`". Add `test_channels.py` to lines 1865-1867. Add to line 1869: "every profile field reaches its output (composite, mix, kit, upload)".

### M19. The plan's docs and agent-instruction items were not amended - Severity: Major
* **Reviewer Lens:** `egm-structural` (F11)
* **Affected Scope:** files 54 (1819-1824), 55 (1829-1833), 56 (1838-1840), 57 (1845-1847).
* **Discrepancy Description**: These items predate the amendment:
  * File 56 still says "the five MCP episode tools" and does not list editing a profile among the things agents cannot do.
  * File 55's glossary list leaves out the profile terms.
  * File 57's list of record writers leaves out `profile` and `outputs.channel`.
  * File 54's README contract does not mention `profiles.py`, the seed or pinning.

  As a result, no rule tells future code changes to keep channel values out of code.
* **Rationale & Recommendation**: Make these edits:
  * File 56: "five episode tools and two read-only channel tools"; add "create or edit a channel profile" to the cannot-do list.
  * File 55: add "channel profile, pinned profile, seed".
  * File 57: "the API writes script, profile pin, budget, `outputs.channel` and gate states", plus the rule "no channel value in code; channels are profiles".
  * File 54: add profiles, the seed and pinning to the README contract.

### M20. Open Questions has no profile items, though several profile decisions are open - Severity: Major
* **Reviewer Lens:** `egm-structural` (F12)
* **Affected Scope:** Open Questions lines 133-147; related lines 208, 440, 468, 1673.
* **Discrepancy Description**: The design does not settle these points:
  * whether the default can be changed in the studio (see M3);
  * whether the existing YouTube connect flow supports several channels, which CUJ 5 assumes;
  * whether profile files are kept forever;
  * how a new presenter is previewed before any paid clip exists (file 41a's preview needs "a clip for the presenter").
* **Rationale & Recommendation**: Add Q6 "Choosing the default channel in the studio", Q7 "Several YouTube channels connected" and Q8 "Previewing a presenter with no clip". Alternatively, settle each one in "Channel profiles" and say so.

### M21. The Risks table is missing profile failure modes - Severity: Major
* **Reviewer Lens:** `egm-structural` (F13)
* **Affected Scope:** Risks lines 996-998.
* **Discrepancy Description**: These failure modes have no row:
  * a mistyped `avatar_id` or `voice_id`, which fails or renders the wrong person after money is approved;
  * a `default_profile` that names no row;
  * several channels sharing one wallet and ceiling, so one channel can block another;
  * profile files that are not backed up (Non-Goal line 123);
  * uploaded music with no licence, which leads to a copyright claim on the new channel.
* **Rationale & Recommendation**: Add five rows with these mitigations:
  * check avatar and voice ids against HeyGen's lists on save (422);
  * health and preflight report "default profile X missing";
  * the status page shows the month's spend by channel;
  * back up `data_dir/channels/` to the vault, or record it as an accepted risk;
  * a licence note per uploaded file, shown on the Channels page.

### M22. Migration 4's table count contradicts itself - Severity: Major
* **Reviewer Lens:** `egm-style` (1)
* **Affected Scope:** record line 316 (unchanged text) against NFR Rollout line 1039.
* **Discrepancy Description**: Line 316 says migration 4 adds two tables. Line 1039 says three, including `channel_profiles`.
* **Rationale & Recommendation**: Line 316: "Migration 4 adds three tables: `episodes` (...), `heygen_ledger` (see "The paid step") and `channel_profiles` (see "Channel profiles")."

### M23. "Channel", `look` and `profile` each mean two things - Severity: Major
* **Reviewer Lens:** `egm-style` (5, 6, 7, 8)
* **Affected Scope:** Overview lines 15-20; `outputs.channel` lines 334 and 339; line 402; line 790; test line 1536; contract lines 380-381; profile shape line 442; Pinning line 475; record lines 325-326 and 339; Playwright text lines 623, 891 and 1015.
* **Discrepancy Description**: Each term is used for two different things:
  * "Channel" means both a show (a profile) and a YouTube account.
  * The script's `look` is the HeyGen avatar look, while the profile's `look` is the studio visuals.
  * `script.profile` is a slug, while `record.profile` is the pinned `{slug, version, hash}`.
  * "A fresh profile" in the unchanged Playwright text now reads as a channel profile.
* **Rationale & Recommendation**: Make these edits:
  * Add Glossary entries for **Channel** (a show defined by one profile) and **YouTube channel** (the connected account an episode uploads to). Write "YouTube channel" at lines 790 and 1536.
  * Rename the profile's `look` to `studio` throughout, or annotate line 381: "`look` is the HeyGen avatar look, not the profile's studio look".
  * Line 339: "the API writes `script` (including the requested `script.profile` slug), the pinned `profile`, ...".
  * Write "fresh browser profile" at lines 623, 891 and 1015.

### M24. The text misstates what the profile hash covers, and the whole-profile hash recomposes every scene for any edit - Severity: Major
* **Reviewer Lens:** `egm-style` (9), `egm-design` (15)
* **Affected Scope:** Pinning lines 474-478; Compositor lines 656-658; file 16 lines 1301-1303; file 47 line 1761.
* **Discrepancy Description**: The text "(look, fonts, palette, plate)" implies that only visual fields enter `inputs_hash`. The plan hashes the whole profile. A change to the footer, tags or YouTube channel therefore recomposes 36 scenes and re-renders every card: hours of work for a text edit. `sha1(profile_json)` is also not canonical unless the keys are sorted.
* **Rationale & Recommendation**: Hash parts of the profile, each feeding only what it affects:
  * `look_hash = sha1(canonical(look) + presenter.name)` in `inputs_hash`;
  * `card_hash = sha1(palette, fonts)` in `durations_hash`;
  * `sound_hash` in the mix inputs.

  Define `hash = sha1(json.dumps(profile, sort_keys=True, separators=(",", ":")))`. Rewrite lines 474-478 to say exactly what each change recomputes. In test 34, add: a repin that changes only the footer re-composes nothing.

---

### N1. The header names the wrong review file - Severity: Nit
* **Reviewer Lens:** `egm-structural` (F1), `egm-style` (26)
* **Affected Scope:** line 8; Additional Resources lines 1062-1065.
* **Recommendation**: Line 8: "The 2026-11-03 amendment (channel profiles) was reviewed separately (see `channel_profiles_critic_report.md`)." Add that file to Additional Resources.

### N2. Alternatives are out of order, and the texts of N and U are inaccurate - Severity: Nit
* **Reviewer Lens:** `egm-structural` (F2, F19), `egm-style` (25), `egm-design` (16)
* **Affected Scope:** lines 917-981.
* **Recommendation**: Move T and U after S. Alternative N: "Chosen instead: profile files (an uploaded or once-rendered intro, the bed, the SFX) stored by sha256 and shared across versions; the intro texts are profile fields." Alternative U: "The goal "No money without a click", and the rule that one episode has one look, both need ...".

### N3. Plan item numbers are out of reading order - Severity: Nit
* **Reviewer Lens:** `egm-structural` (F3)
* **Affected Scope:** lines 1244/1259 (13b before 13a) and 1559/1574 (34a before 34).
* **Recommendation**: Put 13a before 13b, and move 34a after 34.

### N4. The intro job can save over newer intro settings, cannot import its builder, and shares a work folder - Severity: Nit
* **Reviewer Lens:** `egm-design` (16)
* **Affected Scope:** file 46a lines 1743-1748; file 8 lines 1176-1190.
* **Recommendation**: Move the builder to `episode/intro.py`, with `tools/brand/make_intro.py` as a thin wrapper. Give each job its own output path and work folder (`cards/intro-<slug>-<version>/`). If the newest version's intro inputs differ from the ones rendered, discard the result and log "intro inputs changed; render again".

### N5. Two tabs saving the same profile: the later save silently wins - Severity: Nit
* **Reviewer Lens:** `egm-design` (20)
* **Affected Scope:** `PUT /{slug}` line 491; file 13b `save`.
* **Recommendation**: `PUT` carries `base_version`; if it does not match the latest version, return 409 "profile changed; reload".

### N6. Uploaded files are never cleaned up - Severity: Nit
* **Reviewer Lens:** `egm-design` (21)
* **Affected Scope:** lines 431-434; NFR Performance.
* **Recommendation**: Add a "Clean unused channel files" action that removes files no version names and that are older than 7 days. Report the size of `channels/` in health.

### N7. A missing profile file returns 503 - Severity: Nit
* **Reviewer Lens:** `egm-design` (19)
* **Affected Scope:** Status lines 761-762.
* **Recommendation**: Return 409 with the missing fields, and keep 503 for missing toolchain parts.

### N8. The plan does not say whether `youtube.pick_channel` exists - Severity: Nit
* **Reviewer Lens:** `egm-structural` (F14); `egm-design` confirmed the function exists at `core/youtube.py:128-139`.
* **Affected Scope:** file 20 line 1357; file 29 lines 1493-1496.
* **Recommendation**: In file 29, add "`pick_channel(data_dir, channel_id | None)` (exists; unchanged)".

### N9. The Glossary is missing new terms - Severity: Nit
* **Reviewer Lens:** `egm-structural` (F16), `egm-style` (18, 19, 23)
* **Affected Scope:** Glossary lines 240-245.
* **Recommendation**: Add entries for **seed** (the only profile shipped in the repository, `assets/channels/danslab/`, loaded on first start), **default profile**, **Channels page** (`?channels=1`, Stage 2) and **SFX slot**. Define "seed" before line 243 uses it.

### N10. NFR Rollout lists too few touched surfaces - Severity: Nit
* **Reviewer Lens:** `egm-structural` (F18)
* **Affected Scope:** lines 1038-1046.
* **Recommendation**: Add the `/api/channels` router, the `ensure_seed` write at startup, `default_profile` in `/api/health`, `?channels=1` and `data_dir/channels/`. Note that a revert leaves the profile rows and files in place, harmlessly.

### N11. The validator prose leaves out the pinned/latest rule and names the voice table differently - Severity: Nit
* **Reviewer Lens:** `egm-style` (12)
* **Affected Scope:** lines 423-425.
* **Recommendation**: "The thresholds and the voice-names table (`presenter.voice_names`) come from the script's profile, or the default: its latest version before approve-script, and the pinned version after."

### N12. The test wording says approve-budget uploads - Severity: Nit
* **Reviewer Lens:** `egm-style` (14)
* **Affected Scope:** line 1556.
* **Recommendation**: "approve-budget writes the pinned profile's `youtube_channel` to `outputs.channel` (the upload uses it), and answers 409 when that channel is not connected."

### N13. CUJ 5 uses "second" for two things and uses "slug" before defining it - Severity: Nit
* **Reviewer Lens:** `egm-style` (15)
* **Affected Scope:** lines 206-218.
* **Recommendation**: Write "duplicates DansLab under the slug (short id) `didyouknow`", "the `didyouknow` episode ... uploaded as private to the new YouTube channel" and "the episode with no `profile` is a DansLab episode".

### N14. The Overview assumes every channel uses questions and answers, and lists profile contents differently from the Glossary - Severity: Nit
* **Reviewer Lens:** `egm-style` (16, 17)
* **Affected Scope:** Overview lines 15-20; Glossary lines 240-242.
* **Recommendation**: "delivers a script in the shape the channel's profile sets (for DansLab, questions and answers ending in a reveal)". Use one list of profile contents in both places, including the caption language.

### N15. One validator table row holds two checks - Severity: Nit
* **Reviewer Lens:** `egm-style` (20)
* **Affected Scope:** line 413.
* **Recommendation**: Split it into one row for `question_hooks` and one for `reveal`.

### N16. Two paragraphs in "Channel profiles" each pack several rules - Severity: Nit
* **Reviewer Lens:** `egm-style` (21)
* **Affected Scope:** lines 429-435 and 453-458.
* **Recommendation**: Give each rule its own paragraph, and put the palette mapping in a table. "When the pinned profile lacks an optional file, the episode is produced without it."

### N17. The SFX slot and levels wording is vague - Severity: Nit
* **Reviewer Lens:** `egm-style` (23)
* **Affected Scope:** lines 672-673 and 677.
* **Recommendation**: "a fixed table maps each cue to one of the eight `sound.sfx` slots and an offset; the profile chooses the file in each slot", and "a profile may change the intro, voice, bed and SFX levels; the final loudness target is fixed".

### N18. The Assets section lists a voice-names file the profile shape does not have, and the paid step and NFR have long sentences - Severity: Nit
* **Reviewer Lens:** `egm-style` (24, 26)
* **Affected Scope:** Assets lines 766-772; paid step lines 561-568; NFR line 1024; line 762.
* **Recommendation**: Remove "the voice-names table" from the seed's file list, because it is `presenter.voice_names` inside `profile.json`. Write "uploaded through `/api/channels` (the Channels page from Stage 2)". Split the paid-step sentence at "It resolves the YouTube channel". Name the route `GET /api/channels/files/{sha256}` (see B1). Start "A Library group for episodes is deferred" on its own line.

---

## Checked and found sound

* A save inserts a new version and never updates an old one.
* A presenter change flows through the clip key, and a colour change does not.
* A repin goes back through the budget screen.
* The YouTube channel is resolved under the row lock with the existing `pick_channel`.
* There is one wallet and one ceiling across channels.
* Card templates and SFX cues stay in code, and the Non-Goals list this honestly as a limit of "no code change".
* Alternatives T and U meet the Alternatives Rule.
* "Channel profiles" sits in a sound place, as an H3 under Technical Plan.
* The amendment has no hype or filler.
