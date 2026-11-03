# Goldfish Review Report: Implementation Readiness (Stage 9), channel profiles amendment

**Target:** `docs/egm/daily-episode-factory/daily-episode-factory.md`. Scope: the 2026-11-03 "channel profiles" amendment only. That is "### Channel profiles" (lines 427-497) plus the related glossary, CUJ 5 and Alternatives T/U, and these Detailed Implementation Plan items: 5, 6, 8, 9, 10, 13, 13b, 14, 15, 16, 20, 21, 21a, 25, 26, 27, 31, 33, 34, 34a, 41, 41a, 43, 46a and 47.
**Repository checked:** `/Users/davidai/ZCodeProject/.worktrees/ss-channel-profiles`
**Date:** 2026-11-03
**Verdict:** Not ready to implement.

## Reviewer Status

| Reviewer | Status |
| --- | --- |
| `egm-implementation-readiness` | completed |
| `egm-codebase-details` | completed |
| `egm-style` | completed |

## Severity counts (after deduplication)

| Severity | Count |
| --- | --- |
| Blocker | 6 |
| Major | 22 |
| Nit | 24 |

The codebase reviewer found no discrepancy against the code in items 14, 15, 16, 20, 33, 34 and 43. Other lenses still raised findings on some of them, listed below. The synthesizer checked two Blocker claims directly: `server/pyproject.toml` has no `python-multipart`, and the wheel packages only `src/streamstudio`. `tools/compose/motion/intro/README.md:13-14` documents the intro's mixed-in sound.

---

## Prioritized Findings (Blockers -> Major -> Nits)

### B1. Re-rendering the intro drops its sound, and the profile cannot describe the DansLab intro - Severity: Blocker
* **Reviewer Lens:** `egm-codebase-details` (also `egm-implementation-readiness` N4, `egm-style`)
* **Affected Scope:** Item 6 (lines 1149-1164), item 8 (1173-1190), item 46a (1740-1749), item 26; profile shape (line 444)
* **Discrepancy:** Item 6 re-renders `assets/brand/danslab-intro.mp4` "at 25 fps in place" through file 8. The HyperFrames composition has no audio track. Today's sound was mixed in by hand:
  * `tools/compose/motion/intro/README.md:13-14`: "riser-soft 0.0 s, pop-reveal 0.57 s, warm-shimmer 1.3 s, whoosh-soft 3.35 s, impact-deep-soft 4.0 s; mixed to −18 LUFS, fade out from 6.4 s".
  * `web/src/agent/catalog.ts:99` describes the clip as "(7 s, with sound)".
  * The ported mix calls `load(INTRO, -18)` (`tools/compose/mix.py:57`) with `check=True`, so a silent intro makes it fail.

  The profile also cannot express the intro's look:
  * The colours are red and gold (`#e74c3c`, `#c0392b`, `#d4a017`, `#050404`, `#fafafa`, `#fffef7`, `#b9b1a4`, `#160b091a`; `make_intro.py:32-53, 57, 61`), not the teal and violet compositor palette. "Hard-coded colours become profile reads" would recolour the DansLab intro.
  * The fonts are Newsreader and JetBrains Mono woff2 (`make_intro.py:27-30`). The profile has only `fonts: {display, body}`, and with `extra="forbid"` the seed cannot name the "four intro woff2 files".
  * The logo tile, the serif `D` and the gold cursor are hard-coded (`make_intro.py:101`).
* **Proposed edit:**
  * Item 6: "The existing `danslab-intro.mp4` is converted once to 25 fps with `ffmpeg -i in.mp4 -vf fps=25 -c:a copy`. It is not re-rendered."
  * Item 8 and the profile shape: add a `look.intro` block, `{bg, accent, accent_2, text, muted, logo_letter, fonts: {serif: [sha256], mono: sha256}}`. Give a table mapping every literal listed above to its field.
  * Item 46a: after the render, mix `sfx.riser/pop/shimmer/whoosh/impact` at the cue offsets that `make_intro.py` prints, at the `intro` level, fading out from 6.4 s.
  * Item 26: if ffprobe finds no audio stream in the intro, it contributes silence instead of failing.

### B2. The server cannot import the intro builder in `tools/brand/make_intro.py` - Severity: Blocker
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details` (also `egm-style`)
* **Affected Scope:** Item 8 (1173-1190), item 46a (line 1745)
* **Discrepancy:**
  * Item 46a's `channel_intro` handler uses "file 8's function, imported lazily". But `server/pyproject.toml:35-36` packages only `src/streamstudio`, so `tools/brand/` is not on the worker's path.
  * Item 8's signature takes `<out.mp4>`, but its command hard-codes `-o assets/brand/danslab-intro.mp4`, relative to the workspace cwd.
  * Item 8 does not say how sha256 file fields become paths. The seed uses relative paths; stored profiles use sha256.
* **Proposed edit:**
  * In Stage 0, create `server/src/streamstudio/episode/intro.py` with `build_intro(s, profile: Profile, resolve: Callable[[str], Path], out_dir: Path) -> Path`.
  * Make `tools/brand/make_intro.py <profile.json> <seed_dir> <out.mp4>` a thin CLI over it, run with `uv run python -m streamstudio.episode.intro`.
  * Render with `-o <out.mp4>`.
  * Item 46a extends `intro.py` rather than creating it.

### B3. A profile duplicated from another can never be saved - Severity: Blocker
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-style`
* **Affected Scope:** Item 21a (lines 1377-1379), item 13b (1251-1254), Technical Plan line 433
* **Discrepancy:** Item 21a's `POST /` "shar[es] files by copying their sha256 entries". But item 13b's `save` "checks every named file exists under `channels_dir/<slug>/files/`", and `file_path(s, slug, sha256)` looks inside the slug's own directory. A copy made for CUJ 5 fails its first save, and its handlers cannot resolve its files.
* **Proposed edit:**
  * Item 21a: "copies the latest version of `from` under the new slug and name. For every sha256 it names, it hard-links the file (copying if linking fails) from `channels_dir/<from>/files/` into `channels_dir/<slug>/files/`, then calls `profiles.save`."
  * Item 34a test: "a profile created from `danslab` saves unchanged and `file_path` resolves every file."

### B4. The "no `danslab` in source" scan in item 34a fails against today's repository - Severity: Blocker
* **Reviewer Lens:** all three
* **Affected Scope:** Item 34a (lines 1571-1572), item 6 (1162-1164), item 13b (1255)
* **Discrepancy:** The scan allows `danslab` only in `config.py`'s `default_profile`. The literal already appears in:
  * `web/src/stage/Library.tsx:17,19`
  * `web/src/agent/catalog.ts:99`
  * `web/src/agent/agent.test.ts:20-24`
  * `web/src/publish/YouTubeUpload.test.tsx:38`
  * `web/src/stage/README.md:27`

  Item 6 says those references "keep working". Item 13b's `ensure_seed` would also add the literal to `episode/profiles.py`.
* **Proposed edit:**
  * Limit the scan to `server/src/streamstudio/episode/`, `server/src/streamstudio/api/routes/{episodes,channels}.py` and `web/src/{episode,channels}/`.
  * Make `ensure_seed` slug-agnostic: "for every `assets_dir/channels/<slug>/profile.json`, insert version 1 of `<slug>` if no row for that slug exists". At minimum, seed from `s.default_profile`.

### B5. File upload names multipart, but no parser is installed, and the size cap does not match the signature - Severity: Blocker
* **Reviewer Lens:** `egm-codebase-details` (also `egm-implementation-readiness` M9)
* **Affected Scope:** Item 21a (lines 1380-1381), item 13b (1253), item 34a (1568-1569)
* **Discrepancy:**
  * FastAPI's `UploadFile`/`Form` needs `python-multipart`. It is not in `server/pyproject.toml:6-11`, and item 1 does not add it. The existing upload streams a raw body instead (`api/routes/recordings.py:38-56`: `request.stream()`, `MAX_BYTES`, 413).
  * `store_file(s, slug, path)` takes a path, but the test requires the size to be "checked from the stream".
  * No status codes are given for oversize or unreadable files, and the stored extension and media type are unspecified.
* **Proposed edit:** "`POST /{slug}/files?name=<filename>` takes a raw body, streamed as in `recordings.py:upload` to `channels_dir/<slug>/tmp/<uuid>`. It returns 413 at 200 MB + 1. The extension is checked against an allowlist (png, jpg, otf, ttf, woff2, mp4, mp3, wav, m4a). `store_file` then probes the file and returns 422 if it cannot be opened (see M7 for fonts). It renames the file to `<sha256>.<ext>`. `GET /files/{sha256}` sets the media type from `<ext>`."

### B6. The `render.py` literal list in item 25 is incomplete, so DansLab and Nervix values survive the port - Severity: Blocker
* **Reviewer Lens:** `egm-codebase-details`, `egm-implementation-readiness` (M7)
* **Affected Scope:** Item 25 (lines 1436-1444), profile shape (444, 456-458), line 463
* **Discrepancy:** Item 25 lists six literals and maps none of them explicitly. It misses these values in `tools/compose/render.py`:
  * `[6, 6, 12]` (:50)
  * `[60, 200, 190]` (:377)
  * `WHITE, TEAL, MUTED = (242,244,250), (45,226,196), (170,176,196)` (:380)
  * `[20, 40, 60]` (:479)
  * Chip outline `(124,92,255,170)`; it is not `accent_b` (140,100,255), and alpha 170 would be lost.
  * Table-card fill `(8,10,18,205)`, which is not `panel` (10,12,20,220).
  * The hard-coded Nervix endcard text (:441-442: "List your AI business", "nervix-market.vercel.app", ...).
  * Three Inter weights, `Bold`, `SemiBold` and `Medium`, loaded from a Linux path (:26, 294, 406-443), while the profile has only `{display, body}`.

  `RING_RGB` and `ring` (:184-187) are unused. So "the seed carries Episode 1 v2's values" (line 463) is not pixel-true.
* **Proposed edit:**
  * Add a mapping table to item 25: `text` = WHITE and (236,238,246); a new `muted` = MUTED; `accent_a` = TEAL and the table glow; `panel` = the tag fill; a new `panel_2` = the table-card fill; a new `outline` = the chip outline with alpha.
  * Keep `[6,6,12]` and `[20,40,60]` as neutral module constants.
  * Fonts: `display` = Bold; `body` = SemiBold and Medium. Alternatively, use `fonts: {bold, semibold, medium}`.
  * The endcard comes only from `profile.publish.endcard`.
  * Drop "the card ring".
  * Add the new fields to the profile shape (line 444).

---

### M1. The preview route is specified as both GET and POST - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** Technical Plan lines 487-488 vs 493; item 41a (line 1672)
* **Discrepancy:** Line 488 has `GET /api/channels/{slug}/preview.jpg` "rendered ... from the unsaved form". A GET cannot carry that form. Line 493 and item 41a have `POST /{slug}/preview`. Item 41a "returns a JPEG", but there are two frames (avatar and card).
* **Proposed edit:** Line 488 becomes `POST /api/channels/{slug}/preview`. Fix the response: one 1280x360 JPEG with the avatar frame on the left and the card frame on the right, or `?frame=avatar|card`.

### M2. Repin does not invalidate built outputs - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** Item 20 (1350-1352); Technical Plan 357-368, 476
* **Discrepancy:** Repin has "the same ... effects as `PUT /script`", and `PUT /script` unlinks outputs only when the script hash changes. Repin never changes the script hash. So `final.mp4` and `recording_id` survive, planner rows 7 and 9 skip, and the old look is uploaded. This contradicts line 476.
* **Proposed edit:**
  * Item 20: "`repin` always unlinks `final.mp4`, `final.srt` and `kit.json`, clears `outputs.recording_id`, and clears `record.profile`."
  * Item 34 test: after repinning a palette change, `final.mp4` is rebuilt and a sampled rim pixel shows the new colour.

### M3. When approve-script pins the profile is undecided - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** Technical Plan line 470; item 20 (1350-1351)
* **Discrepancy:** As written, every approve-script copies the profile's latest version. That makes the repin button redundant, and the look changes silently, without unlinking outputs.
* **Proposed edit:** "approve-script pins only when `record.profile` is unset. It is cleared by `repin`, and by a `PUT /script` whose `profile` slug differs from the pinned slug." Add a matching test to item 33.

### M4. `EpisodeOut` has no fields for the channel name or a changed profile - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** Item 20 (1344-1346); items 31 (1510), 33 (1553-1555), 43 (1691-1693)
* **Discrepancy:** Item 33 asserts that `GET /{id}` reports the profile as "changed", and item 31 shows the channel's name. `EpisodeOut` adds only `progress, validation, next_action, last_log`.
* **Proposed edit:** Add `profile_name: str | None` and `profile_latest_version: int | None`. "Changed" means `profile_latest_version > record.profile.version`.

### M5. Creating an episode does not check the profile's files - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** Item 20 (line 1343); Technical Plan 761-762; risk row 998
* **Discrepancy:** The Technical Plan says creation "refuses with 503 naming the missing ones". Item 20's `POST /` mentions only preflight and validation, and no test covers the refusal.
* **Proposed edit:** In item 20, "`POST /` resolves the named or default profile and returns 503 with `profiles.missing(s, profile)` when that list is not empty." Add a test to item 33.

### M6. Fonts are both required and optional, and most defaults are missing - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** Line 453 vs lines 761 and 1201; item 13b (1247)
* **Discrepancy:** Line 453 does not list fonts as required, but preflight and creation treat "plate, fonts" as required. Only `levels` has a default table. Palette, rules, publish, language, sfx and fonts have none, and nothing says what the compositor does without fonts.
* **Proposed edit:**
  * Add `look.fonts` to the required list.
  * In item 13b, list every default, for example palette = the seed values; `rules = {scene_s:[3,13], event_gap_s:8, question_hooks:false, reveal:false}`; `publish = {description_footer:"", default_tags:[], endcard:null}`; a null sfx slot means silent.

### M7. Uploaded intros are never converted to 25 fps, and `store_file` rejects fonts - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** Technical Plan 674-675; items 13b (1253), 21a
* **Discrepancy:** The plan converts "an uploaded intro at another rate ... once, when it is uploaded". But `store_file` and `POST /{slug}/files` do not know which file is an intro. Neither ffprobe nor `PIL.Image.open` opens OTF or woff2, so fonts would be rejected.
* **Proposed edit:**
  * Add `?role=intro`, which re-encodes with `-vf fps=25` (audio copied) before hashing. Alternatively, `PUT` returns 422 when `sound.intro` is not 25 fps.
  * Validate fonts with `PIL.ImageFont.truetype(path, 12)`.
  * Add tests to item 34a.

### M8. DELETE behaviour is underspecified - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-style`
* **Affected Scope:** Technical Plan 467, 493-494; item 41a (line 1675)
* **Discrepancy:** The plan does not say:
  * whether all versions and the `files/` directory are removed;
  * the status code for "pinned by an episode";
  * how pinned episodes are found;
  * what published or purged episodes show after their profile is deleted.
* **Proposed edit:** "DELETE removes every `channel_profiles` row for the slug and `channels_dir/<slug>/`. It returns 409 for `s.default_profile`. It returns 409 with the episode ids when `SELECT id FROM episodes WHERE json_extract(record_json,'$.profile.slug') = ? AND status NOT IN ('published','purged','cancelled')` is not empty. For a deleted slug, `pinned()` returns `None` and `EpisodeOut.profile_name` is null."

### M9. The Stage 2 Channels work has no tests - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** Items 41, 41a, 44, 34a
* **Discrepancy:** Item 41a ships preview and DELETE in Stage 2, and item 41 adds `channel_list` and `channel_get`. Item 44 covers none of them. Item 34a's "MCP has no write tool" check is vacuous in Stage 1.
* **Proposed edit:** Add a Stage 2 test block covering:
  * DELETE returns 409 for the default profile and for a slug pinned by an `in_progress` episode, and succeeds when only `published` episodes pin it;
  * preview returns `image/jpeg` for an unsaved form and 422 for an invalid one, and writes no row;
  * `channel_list` and `channel_get` return the latest version, and `TOOLS` has no channel write tool.

### M10. The preview's "if a clip exists for the presenter" has no lookup rule - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** Item 41a (1672-1674)
* **Discrepancy:** Clips are keyed by an `item_key` hash under `assets/avatar/clips/` (`worker/handlers.py:206-209`). Nothing maps an `avatar_id` to a clip. In Stage 2 the card frame can only be the compositor's layout, because the HyperFrames card (item 47) lands in Stage 3.
* **Proposed edit:**
  * "Use the newest `jobs` row with `kind='heygen_clip'`, `status='done'` and `payload.look == avatar_id` whose `cutout` file exists, at 1.0 s. Otherwise use the grey silhouette."
  * State that the Stage 2 card frame is the compositor card scene.

### M11. Preflight cannot read the default profile with its signature - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** Item 9 (1198-1202), item 10, item 20 (1343)
* **Discrepancy:** `preflight.check(s, stage)` has no connection. It still has to check "the default profile's seed files", which are now sha256 files stored in the database.
* **Proposed edit:**
  * Change the signature to `preflight.check(s, conn, stage, profile: Profile | None = None) -> {ok, missing}`. It reads `profiles.latest(conn, s.default_profile)`, and a missing row is itself an entry in `missing`.
  * Health (item 10) passes its connection.
  * Test: `default_profile.missing` is not empty after the plate file is deleted.

### M12. `ensure_seed` has no real startup hook in either process - Severity: Major
* **Reviewer Lens:** all three
* **Affected Scope:** Item 13b (1256-1257), item 21 (1370-1371), item 23
* **Discrepancy:** Neither process has a startup hook to call:
  * `create_app` runs `db.migrate(c)` inline (`api/main.py:28-30`).
  * The worker migrates once per thread (`worker/main.py:64-65`), and item 23 does not mention seeding.
  * The sentence in item 13b reads as if `pinned` is what gets called at startup.
* **Proposed edit:**
  * Item 21: "call `profiles.ensure_seed(c, s)` after `db.migrate(c)` in `create_app`."
  * Item 23: "call it after `db.migrate(conn)` in `loop`."
  * Item 13b: "`ensure_seed` runs inside `db.tx` and is idempotent across `worker_concurrency` threads."

### M13. `profiles.latest` does not return a hash, and the hash is not canonical - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** Item 13b (1250-1252)
* **Discrepancy:** `latest(conn, slug) -> (version, Profile)` does not return the hash, but pinning stores `{slug, version, hash}`. `sha1(profile_json)` has no fixed serialisation, so equal profiles can hash differently.
* **Proposed edit:** Return `ProfileRow(slug, version, hash, profile)`. Define `profile_json = json.dumps(profile.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))`.

### M14. A non-English profile is only half-specified - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** CUJ 5 (line 215); items 34 (1592-1595), 37
* **Discrepancy:** The `ro` test profile covers captions only. Whisper's language, the English number-to-words step in QA and the English validator warnings all ignore `profile.language`. From Stage 2, a Romanian episode would get false `LOOK` verdicts.
* **Proposed edit:**
  * Item 37 passes `profile.language` to `transcribe`.
  * Number normalisation and the number/ranking validator rows apply only when `language` starts with `en`.
  * Add a test to item 44.

### M15. Skipped optional files are not logged consistently or tested - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** Technical Plan 454-455; items 25, 26
* **Discrepancy:** "the status page names what was skipped", but only item 26 logs a skip (intro, bed). A missing desk in item 25 and a null SFX slot do not log.
* **Proposed edit:** Every skipped optional file writes the log line "Profile X has no <field>; skipped". Add an item 34 test with a profile that has no intro, no bed and one empty sfx slot.

### M16. Item 6 does not name the sources of the seed files - Severity: Major
* **Reviewer Lens:** `egm-codebase-details`
* **Affected Scope:** Item 6 (1155-1157)
* **Discrepancy:** None of the seed files exist in the repository; `assets/` holds only `studio/`, `brand/`, `avatar/` and `objects/`. The audio comes from `MEDIA_LIB` (default `/home/claude/dansidanutz/claude-youtube/media/library`, `mix.py:22`):
  * `music/clips/ambient-pad.mp3` (:26, 61)
  * `sfx/clips/{riser-soft, pop-reveal, whoosh-soft, ui-click-soft, sparkle-soft, impact-deep-soft, glitch-zap, warm-shimmer}.mp3` (:94-118)

  The fonts are a Linux system Inter (`render.py:26`) and @fontsource woff2 (`intro/README.md:12`).
* **Proposed edit:** Add a table to item 6 listing each source path, its destination under `assets/channels/danslab/` and its profile slot (for example `sfx.riser` = `riser-soft.mp3`).

### M17. Item 26 drops `mix.py` details that shape the DansLab sound - Severity: Major
* **Reviewer Lens:** `egm-codebase-details`
* **Affected Scope:** Item 26 (1456-1462)
* **Discrepancy:** These `mix.py` details are missing from item 26:
  * per-cue gains: riser -3 dB, pop -4, whoosh -2, glitch -1, shimmer 0, impact -2, page -6, sparkle 0 (`mix.py:94-113`);
  * the whoosh offset of -0.2 s (:98);
  * the bed timing (:62-73): it starts at `INTRO_D - 1.0`, loops with a 3 s crossfade, fades in over 2.5 s and fades out over 5 s;
  * per-track `loudnorm=I=<lvl>:TP=-2:LRA=20` (:32).
* **Proposed edit:** Add these values to item 26's table of module constants.

### M18. The `build.py` literal list in item 47 is incomplete, and the font is never loaded - Severity: Major
* **Reviewer Lens:** `egm-codebase-details`, `egm-implementation-readiness` (N7)
* **Affected Scope:** Item 47 (1757-1760)
* **Discrepancy:** Item 47 misses these colours in `tools/compose/motion/build.py`:
  * `#8c64ff` (:43, 50)
  * `rgba(124,92,255,…)` (:34, 41, 53)
  * `rgba(45,226,196,…)` (:34, 42, 48, 53, 57)
  * `#161925` (:25), `#eef0f7` (:36), `#0a0b10` (:51)
  * `rgba(10,12,22,.92)` and `rgba(16,14,34,.92)` (:41, 48)
  * `rgba(9,11,20,.94)` (:53), `#06231e` (:56)
  * The two dark tones `#07080d` and `#0c0e15` both map to one `panel`.

  Every rule names `Inter` with no `@font-face` (:21-58).
* **Proposed edit:**
  * Map every literal to a CSS variable.
  * Require the builder to emit `@font-face{font-family:Body;src:url(body.<ext>)}` and add the font file to `Comp.files`, which `Comp.write` already copies (:236-237).

### M19. The partial unique index in item 13 is written in a form SQLite rejects - Severity: Major
* **Reviewer Lens:** `egm-codebase-details`
* **Affected Scope:** Item 13 (1235-1236)
* **Discrepancy:** SQLite has no table-level `UNIQUE … WHERE`. Also, `db._split` splits on `;` and strips `--` (`db.py:139-146`).
* **Proposed edit:** Use `CREATE UNIQUE INDEX heygen_ledger_charge ON heygen_ledger(episode_id, clip_key) WHERE kind = 'charge'`, with no `;` or `--` inside string literals.

### M20. Item 25 should reuse the existing cut-out helpers - Severity: Major
* **Reviewer Lens:** `egm-codebase-details`
* **Affected Scope:** Item 25 (1443-1444)
* **Discrepancy:** `HANDS_IN_CLIP = 0.85`, `fit_cover` and the seat maths already exist in `server/src/streamstudio/avatar/cutout.py:70-108`. `desk_layer_for` (:83-85) must not be reused, because it derives the desk from the plate filename, which fails for `<sha256>.png`.
* **Proposed edit:** "Import `HANDS_IN_CLIP`, `fit_cover` and the seat helpers from `avatar/cutout.py` inside the function, because that module imports numpy and PIL at top level. The desk comes from `look.plate.desk`."

### M21. `_cutout_clip` hard-codes the DansLab plate with a different seat - Severity: Major
* **Reviewer Lens:** `egm-codebase-details`
* **Affected Scope:** Items 22 and 25
* **Discrepancy:** `worker/handlers.py:182, 263` uses `s.assets_dir / "studio" / "plate-landscape-final.png"` with `scale=0.66, hands_y=0.68`. The seed uses 0.60 / 0.70 from `plate-landscape-final.json`. This affects the `.on-plate` preview.
* **Proposed edit:** Either pass the pinned profile's plate and seat for episode jobs, or state explicitly that the preview stays DansLab-only.

### M22. Stage 1 and Stage 2 both claim file upload - Severity: Major
* **Reviewer Lens:** `egm-style`, `egm-implementation-readiness` (N9)
* **Affected Scope:** Lines 795-796 vs item 21a (1376-1384)
* **Discrepancy:** Line 796 says "the Channels page, file upload and preview are Stage 2". Item 21a ships `POST /{slug}/files` in Stage 1, and item 34's second profile needs it there.
* **Proposed edit:** "A second channel can run in Stage 1 by saving a profile and uploading its files through the API; the Channels page and preview are Stage 2."

---

### Nits

| # | Location | Discrepancy | Proposed edit |
| --- | --- | --- | --- |
| N1 | Items 13b/13a (1244/1259), 34a/34 (1559/1574) | Items are out of order. | Swap them (store = 13a, profiles = 13b; 34 before 34a). No cross-references break. |
| N2 | Item 15 (1286) | "warning rows land in Stage 2 (file 40)". The validator is file 39. | Change to "file 39". |
| N3 | Item 15 (1285) | The unknown-profile error is script-level, but errors are keyed by scene. "fourth error row" depends on table order. | Key it as `"_script"`. Signature: `validate(..., profile: Profile \| None)`. Name the row instead of counting. |
| N4 | Item 34a | "the seed validates against `Profile`" only holds after paths are replaced by sha256. | Say so. |
| N5 | Item 21a | Edge cases are unstated. | `PUT` with a body slug different from the path: 422. `PUT` on an unknown slug: 404. `POST /` with a slug that fails `^[a-z0-9-]{2,32}$`: 422. State whether preview needs `Origin`. |
| N6 | Items 14/16 | It is not stated that `script.look` overrides `presenter.avatar_id`, or how `default_profile` is changed. | "`script.look` overrides `presenter.avatar_id`. `default_profile` is set by env or config only. A default with no row fails preflight." |
| N7 | Item 8 | `TITLE_HTML` contains `<em>` (`make_intro.py:6`), which conflicts with "all strings escaped" (line 455). The script does not copy gsap or fonts next to `index.html` (`intro/README.md:39-40`). | Allow exactly one tag, `<em>`, and say the script copies gsap and the fonts. |
| N8 | Item 10 (1207-1209) | `default_profile` is not a tool. The hyperframes check is unspecified. | Make `default_profile` a top-level key. Check `data_dir/cards/node_modules/hyperframes/package.json`. Reuse `media.tool_version` (`system.py:58`). |
| N9 | Item 6 (1160) | The source of the ids is vague, and there are two sources of truth. | Name `data_dir/heygen.json` keys `avatar_id` and `voice_id` (`core/heygen.py:41-48`). Note that `/api/heygen/render` still reads them (`api/routes/heygen.py:140-163`). |
| N10 | Item 6, line 766 | `assets/channels/` is served at the web root (`api/main.py:20-22, 54-57`). | State that this is accepted for the seed. |
| N11 | Item 13b | A new regex for `youtube_channel`. | Reuse `youtube.CHANNEL_ID` (`core/youtube.py:30`). |
| N12 | Item 27 (1475-1476) | `clean_meta` truncates descriptions at 5000 bytes and tags at 500 chars (`youtube.py:296-301`), which can silently drop the footer and tags. | Reserve room for the footer and record any drop in `notes`. |
| N13 | Items 31 (1507), 41a | `index.css` is labelled Create. The Channels page has no CSS file for its 390 px layout. | Label `index.css` as Modify. Add `index.css` (`.channels` breakpoint) to item 41a. |
| N14 | Item 41 | The `channel_get` path is not escaped. | Build it with `_seg(slug)` (`mcp.py:208-210`). |
| N15 | Item 56 (1838), Verification Plan (1865-1867) | Item 56 says "five MCP episode tools", but there are now seven. `test_channels.py` is not in the Verification Plan's test list. | Update both. |
| N16 | Item 26, Technical Plan line 672 | Item 26 adds a `reveal → impact` cue that the Technical Plan's cue list omits. | Add `reveal` to line 672. |
| N17 | Tests | Several small gaps. | 46a: add tests in `test_episode_cards.py`. 33: a profile without `youtube_channel` and one connected channel uploads to that channel. 34: the palette-repin test goes through approve-script and a zero-line approve-budget. Add a test that `<script>` in profile strings is escaped in intro and card HTML. |
| N18 | Repin naming (365, 472-475, 939, 1351, 1554, 1596) | The action is called "repin", "re-pinned", "Re-pinning" and "Use latest profile". | Use "repin" throughout. Name the button once: "**Use latest profile** (`POST /{id}/repin`)". |
| N19 | Lines 474-478 | One 70-word sentence. | Split it: the inputs-hash effect, then the clip-key effect, then the cost consequence. |
| N20 | Lines 435, 448, 465 | "Shape:" is attached to the preview sentence. "defaults below" and "the levels table below" point about 230 lines down. | Write "A profile has this shape:". Point to the "Default levels" table (Mix section). |
| N21 | API list (489-495) | Only `/intro` has a stage tag. | Tag preview and DELETE "(from Stage 2)". |
| N22 | Alternatives T and U (926-939) | "a channel is a pull request" is a metaphor. "from the phone" has no referent. "one look per episode" is quoted as if it were a goal. | "adding a channel is a pull request"; "from his phone"; drop the quotes. |
| N23 | Lines 8, 15, 216 | Phrasing. | "reviewed separately"; "No pipeline code is specific to one channel."; "intro and music bed". |
| N24 | Items 9, 20 (1353-1361), 26 (1458-1462), 41a (1672-1675) | Lines are over 100 characters, the approve-budget entry is one 90-word sentence, item 26 has a 60-word parenthetical, and a clause in 41a dangles. | Rewrap. Split approve-budget into sub-bullets. Put the cue-to-slot mapping in a table. "The pane debounces to one request per second." |
