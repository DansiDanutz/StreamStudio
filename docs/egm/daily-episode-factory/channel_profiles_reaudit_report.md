# Goldfish Review Report: Channel Profiles Re-audit

**Target:** `docs/egm/daily-episode-factory/daily-episode-factory.md` (whole document, after 66f03ba..HEAD)
**Mode:** REVIEW. This is the single allowed re-audit. It lists only findings that still block implementation or contradict the document itself. Settled owner decisions were not reopened.

## Reviewer Status

| Reviewer | Status |
| --- | --- |
| `egm-design` (feature-spec-standard) | completed |
| `egm-implementation-readiness` (implementation-readiness-standard) | completed |
| `egm-codebase-details` (implementation-readiness-standard) | completed |

**Counts after deduplication:** 1 Blocker, 10 Major, 13 Nit.

## Check (a): original Blockers and Majors

The reviewers checked the original findings in both reports against the text:

- **Critic report:** both Blockers (B1 and B2) and all 24 Majors are fixed in place.
- **Readiness report:** all 6 Blockers and all 22 Majors are fixed in place.
- **Contested findings:** the log contests none.
- **Superseded:** critic M6 (the YouTube check at approve-script) was superseded by the manual-upload ruling. The spec follows the new ruling. The log still describes the old behaviour (Nit N12).
- **Codebase claims:** about 45 claims match the repo. Examples are `pick_channel`, the MCP tool, `netguard`, migration number 4, the DansLab intro path and the `render.py`/`mix.py` line references. The two mismatches are Nits N8 and N9.

## Check (b): the upload change

Most of the document now follows the manual-upload ruling. These parts were checked and need no change:

- the state chain (lines 412-416)
- planner rows 9a and 10, which fire only after `upload_requested_at`
- the Goals
- the Verification Plan's "zero automatic uploads"
- the tests (except the planner-loop gap)

No planner row enqueues an upload on its own, and nothing checks YouTube before Upload private. Profile save does check the channel id, but that does not gate the pipeline (N11). Three gaps remain:

- an upload can still be started without Dan's Upload private click (B1, M2)
- a failed upload loops (M1)
- the Rollout section does not list the 28a removal (M9)

---

## Prioritized Findings (Blockers -> Major -> Nits)

### B1. `POST /api/jobs` can enqueue `youtube_upload` (and paid or purge jobs) with no click and no `Origin` - Severity: Blocker
* **Reviewer Lens:** `egm-codebase-details`
* **Affected Scope:** Episode record (line 467, "only the Purge button enqueues"); Goals (lines 89-91); Risks row (line 1288, "no code path…"); NFR (lines 1330-1333, Upload private "is the only way an episode reaches YouTube… no agent can upload anything"); item 28a (lines 2002-2013).
* **Discrepancy Description:** `server/src/streamstudio/api/routes/jobs.py:26-34` `create_job` enqueues any kind found in `HANDLERS`, with any payload, and checks no `Origin`. Any HTTP client can therefore queue:
  * `youtube_upload` with `meta.privacy: "public"`;
  * `heygen_clip` with an `episode_id` and no approved budget;
  * `episode_purge`.

  This breaks the owner's rule that nothing uploads without his click, and makes the NFR and Risks claims false. No caller in the repo uses `POST /api/jobs`. Only `GET /api/jobs/{id}` is used.
* **Rationale & Recommendation:** Add to item 28a's file list and changes:
  > `server/src/streamstudio/api/routes/jobs.py` (Modify): `create_job` refuses with 403 any kind outside `API_KINDS = {"probe", "noop", "transcribe"}` (in particular `youtube_upload`, `heygen_clip`, `vault_push`, `finish_recording`, `channel_intro` and every `episode_*` kind).

  Add to item 28a's tests:
  > `POST /api/jobs` with `{kind: "youtube_upload"}` or `{kind: "heygen_clip"}` is 403.

  Extend the Risks row at line 1288 with:
  > …and `POST /api/jobs` refuses upload, paid and episode kinds.

### M1. A failed upload (or any failed stage job) re-enqueues forever, and Advance never resumes the upload - Severity: Major
* **Reviewer Lens:** all three (merged)
* **Affected Scope:** Planner intro (lines 747-757); rows 6-10 (lines 769-774); `needs_dan` rule (lines 434-436); Risks rows (lines 1285-1286); item 23/24 (lines 1864-1888).
* **Discrepancy Description:**
  * **The loop:** row 10 fires when `upload_job_id` "names a job that is neither queued nor running". A job in `error` qualifies. The worker enqueues the planner after every error (line 748), and `store.fail_job` (`core/store.py:217-226`) has already retried that job 3 times. So a quota error loops without end: 3 attempts, error, re-enqueue. Rows 6-9 behave the same way for compose, assemble, kit and register jobs.
  * **No path to `needs_dan`:** only row 1 sets `needs_dan`, and only for clips. This contradicts line 434 ("a stage job ends in `error`" gives `needs_dan`) and the Risks row "Upload failed … `needs_dan` … continues on Advance".
  * **Advance cannot resume an upload:** even if the episode reached `needs_dan`, Advance returns it to `in_progress` (line 436). Row 9a then sets `ready` and stops, so the upload never resumes.
* **Rationale & Recommendation:** Insert a row 0 before row 1:
  > A job id recorded in `compose_job_id`, `outputs.assemble_job_id`, `kit_job_id`, `register_job_id` or `upload_job_id` (from Stage 2/3 also `qa_job_id`, `capture_job_id`, `card_job_id`) names a job in `error` | Set `needs_dan`; log the job's error in plain words (for the upload: "Upload failed: <reason>").

  Change row 10's last clause to:
  > …and `outputs.upload_job_id` is unset.

  Replace line 436 with:
  > `POST /{id}/advance` clears the recorded job ids whose jobs ended in `error`, then sets `uploaded_private` when the upload state file names a `video_id`, else `ready` when `outputs.upload_requested_at` or `outputs.recording_id` is set, else `in_progress`; then enqueues the planner.

  Add row 0 to item 24's Stage 1 row list. Add an item 34 test:
  > An upload job ending in `error` parks the episode in `needs_dan` with no new upload job; Advance returns it to `ready` and enqueues one upload that resumes from the state file.

  State in the Risks row (line 1286) that a failed Publish is synchronous: it returns 502 and leaves the state unchanged.

### M2. The YouTube take picker can upload a registered episode outside the episode gate, including as public - Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-codebase-details` (merged; codebase rated it Blocker)
* **Affected Scope:** Publish kit (lines 976-985; line 979 says "appears… in the YouTube take picker"); item 28 (lines 1994-2000); test at lines 2131-2132; CUJ 3 (lines 234-236); NFR (lines 1330-1333).
* **Discrepancy Description:** `web/src/publish/YouTubeUpload.tsx:31-32, 97-103` lists every take, offers any channel and offers `public` privacy. `api/routes/youtube.py:101-121` accepts all of them. Item 28 deliberately adds episode recordings to that picker. An upload from the picker never sets `outputs.upload_requested_at`. As a result:
  * script edits and repins stay allowed after the video is on YouTube, which contradicts CUJ 3 and the 409-after-upload rule;
  * the episode can go public, or to a channel the profile does not name;
  * the NFR's "only way an episode reaches YouTube" is false.

  Severity is Major, not Blocker: this path still needs Dan's click, so the owner rule holds. What fails is the document's own invariants.
* **Rationale & Recommendation:** In item 28 add:
  > `queue_upload` in `api/routes/youtube.py` refuses with 409 ("upload this episode from its Episode page") a `rid` that has `rec_<rid>.episode.json`; `YouTubeUpload.tsx` leaves out entries whose `episode` is set.

  Add `web/src/publish/YouTubeUpload.tsx` (Modify) to item 28's file list.

  At line 979, replace "and in the YouTube take picker" with:
  > and is absent from the YouTube take picker

  In the test at lines 2131-2132, replace the take-picker assertion with:
  > appears in `GET /api/recordings` with `episode` set, and `POST /api/recordings/{rid}/youtube` for it is 409

### M3. An episode that needs no new clips never reaches `ready` - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** Planner rows 2 and 9a (lines 762, 773); transition rules (lines 412-417, 430); item 34 palette-repin test (lines 2148-2150).
* **Discrepancy Description:** Only row 2 (and Advance) sets `in_progress`, and row 9a requires `in_progress`. A palette-only repin, or an edit that changes no spoken line, approves a zero-line budget. Row 2 never fires, so the episode stays `budget_approved`. Rows 6-9 rebuild the video, but row 9a never sets `ready`, and Upload private (allowed only from `ready`) is refused. This contradicts line 430 ("the episode returns to `ready`"). The palette test does not assert the final state.
* **Rationale & Recommendation:** Change row 9a's predicate to:
  > …and the episode is `budget_approved` or `in_progress`

  Add to the item 34 palette-repin bullet:
  > …and the episode ends in `ready`.

### M4. The planner does not say which states it acts in - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** Planner intro (lines 745-757); rows 6-9 (lines 769-772); `PUT /script` and repin rules (lines 419-447).
* **Discrepancy Description:** After an edit or repin the episode is in `draft`, in-flight clip jobs finish, and each one enqueues the planner. Rows 6-9 have no state condition. Two things go wrong:
  * After a repin `record.profile` is cleared, so row 6 would enqueue `scene_compose` with no pin.
  * After an edit, rows 7-9 could assemble and register a recording before Dan re-approves.

  An implementer has to guess which states the planner acts in.
* **Rationale & Recommendation:** Add after line 757:
  > The planner acts only in `budget_approved` and `in_progress` (rows 0 to 9a) and in `ready` (rows 0, 10 and 11). In every other state it returns without action; Advance changes the state first. `heygen_clip` writes its ledger charge in any state.

### M5. The Risks recovery "Dan edits the line" is refused from `needs_dan` - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** Transition rules (lines 419-420); Risks row (line 1281); item 20 `PUT /script` bullet.
* **Discrepancy Description:** `PUT /{id}/script` is allowed from `draft`, `script_approved`, `budget_approved`, `in_progress` or `ready`. That list leaves out `needs_dan`. The Risks row's recovery for a render that fails after the allowance is spent is "Dan edits the line or raises the allowance; Advance". Repin is allowed from `needs_dan`; edit is not.
* **Rationale & Recommendation:** At lines 419-420, write:
  > from `draft`, `script_approved`, `budget_approved`, `in_progress`, `ready` or `needs_dan`

  Add the same to item 20's `PUT /script` bullet.

### M6. CUJ 5's estimate text contradicts the `youtube_channel` default - Severity: Major
* **Reviewer Lens:** `egm-design`
* **Affected Scope:** CUJ 5 (lines 249-258) and the defaults table (line 576).
* **Discrepancy Description:** CUJ 5 says "No second YouTube channel is connected", so only DansLab's channel is connected. The new profile leaves `youtube_channel` empty. Under the line 576 default, that resolves at upload to "the only connected YouTube channel", which is DansLab's. So the estimate should say "Upload channel: DansLab", not "not connected". As written, the CUJ implies a safety stop that does not exist: an upload would land on the DansLab channel.
* **Rationale & Recommendation:** Replace the CUJ 5 sentence with:
  > the estimate screen said "Upload channel: DansLab (the only connected channel; this profile names none)", so Dan knows to connect and name the new channel before he clicks Upload private.

### M7. Create with a missing default profile gives three different answers - Severity: Major
* **Reviewer Lens:** `egm-implementation-readiness`
* **Affected Scope:** Item 9 (lines 1543-1546); item 20 `POST /` (lines 1745-1748); Status section (line 1042); Risks row (line 1292).
* **Discrepancy Description:**
  * The Stage 1 preflight includes the default profile.
  * `POST /` runs preflight first and returns 503, even for a script that names a different, valid profile.
  * The Risks row says 409.
  * Validation would give 422 under `_script`.
* **Rationale & Recommendation:** Item 20, `POST /`:
  > preflight 503 for missing toolchain parts only (`preflight.check(s, conn, stage, profiles=False)`); a script with no `profile` whose stored default has no row is 422 under `_script` ("default profile X missing").

  Risks row at line 1292: change 409 to 422.

  Item 9:
  > default-profile entries are reported by health and by `check(..., profiles=True)`, never by create.

### M8. Item 28a does not say how to change `test_agent.py`'s exact tool list, and Stage 2 does not list the file - Severity: Major
* **Reviewer Lens:** `egm-codebase-details`
* **Affected Scope:** Item 28a (line 2009); item 41 (lines 2255-2262); item 44a (lines 2327-2341).
* **Discrepancy Description:** `server/tests/test_agent.py:62-67` asserts the exact tool list, including `"youtube_upload"`, and lines 84-89 call `youtube_upload`. Item 28a says only that the test "asserts no tool name contains `upload`". Stage 2 adds seven MCP tools, which will break the exact-list test, but `test_agent.py` is not in Stage 2's file list.
* **Rationale & Recommendation:** Item 28a:
  > `test_agent.py`: drop `"youtube_upload"` from the expected list (lines 62-67), delete the `youtube_upload` call block (lines 84-89), add the "no tool name contains `upload`" assertion.

  Item 44a: add `server/tests/test_agent.py` (Modify), with the change:
  > expected tool list gains `episode_create`, `episode_list`, `episode_status`, `episode_estimate`, `episode_refresh`, `channel_list`, `channel_get`.

### M9. The Rollout section calls every change additive but leaves out item 28a, which is not - Severity: Major
* **Reviewer Lens:** `egm-design`, `egm-codebase-details` (merged)
* **Affected Scope:** NFR "Rollout and rollback" (lines 1346-1358).
* **Discrepancy Description:** The section says every change is "additive and reverted by reverting the commit". Item 28a is not additive:
  * it removes the MCP `youtube_upload` tool, which `docs/AGENTS.md:30` documents;
  * it adds a 403 without `Origin` on the take upload route.

  Agents lose take upload, and a revert brings agent uploads back.
* **Rationale & Recommendation:** Add:
  > Two Stage 1 changes are not additive (item 28a): the MCP `youtube_upload` tool is removed, and `POST /api/recordings/{rid}/youtube` requires a present, allowed `Origin`; with B1 adopted, `POST /api/jobs` also refuses upload, paid and episode kinds. Agents lose take upload; reverting restores it.

### M10. Item 28a leaves READMEs and a docstring saying MCP uploads, against the doc's own "READMEs never lag" rule - Severity: Major
* **Reviewer Lens:** `egm-codebase-details`
* **Affected Scope:** Item 28a (lines 2012-2013) and the README rule at lines 1419-1420.
* **Discrepancy Description:** These still say MCP uploads:
  * root `README.md:99-101` ("the MCP server … always uploads to YouTube as `private`");
  * `server/src/streamstudio/README.md:31` (the `youtube_upload` invariant);
  * the module docstring of `api/routes/youtube.py:1-2` ("agents (MCP) can only upload private").

  Item 28a updates only `docs/AGENTS.md`.
* **Rationale & Recommendation:** Add these to item 28a's file list and changes:
  > root `README.md` (drop the MCP-upload clause; add "no MCP tool uploads; every upload starts from a browser click with an allowed `Origin`"); `server/src/streamstudio/README.md` line 31 (remove the `youtube_upload` invariant); `youtube.py` module docstring.

---

### Nits

- **N1. Test 33 (Stage 1) tests the Stage 2 cancel route.** Line 2082 says "repin and cancel are allowed in `ready`". Cancel arrives in item 40. **Edit:** "repin is allowed in `ready` and refused once an upload is requested; purge works from `ready`". Move the cancel case to item 44. *(design, codebase)*
- **N2. A second Upload private click is not specified.** The episode stays `ready` after the first click (lines 455-461). A second click rewrites `outputs.channel`, and a changed channel gives a new key `<channel>/<rid>`, which uploads a second video. **Edit:** in item 20, add "409 when `outputs.upload_requested_at` is already set". In item 31, add "in `ready` with `upload_requested_at` set, the button is replaced by 'Uploading…'". *(design, readiness)*
- **N3. The page stops polling before the upload lands.** Item 31 (line 2042) polls only while `in_progress`, so the page never sees `ready` turn into `uploaded_private`. **Edit:** "while `in_progress`, or while `ready` with `outputs.upload_requested_at` set". *(codebase)*
- **N4. The purge states disagree in three places.**
  - Line 467 is missing "before any upload request". **Edit:** "from `ready` (before any upload request), `published` or `cancelled`".
  - The Goal at line 104 says "once the video is public". **Edit:** add "or from `ready` or `cancelled` for an episode Dan does not upload".
  - The diagram at line 329 leaves out a click. **Edit:** "approve script · approve budget · upload private · publish".

  *(design)*
- **N5. The NFR claim at lines 1330-1333 is too strong.** "No agent can upload anything" overstates what the `Origin` check does (lines 1327-1330). **Edit:** "no MCP tool and no cross-site page can upload; a local client that forges `Origin` is the accepted residual risk". *(codebase)*
- **N6. The MCP tool-list sentence at line 1036 leaves out upload.** **Edit:** "none of which can approve, upload, publish, cancel or purge". *(readiness)*
- **N7. Row 11 (line 775) releases the reservation a second time.** Row 9a already released it. **Edit:** "Set `uploaded_private`." *(readiness)*
- **N8. Wrong line reference at line 825.** `avatar/cutout.py:150` should be `:153`. Line 153 is the `encode_alpha_webm` call; line 150 is the MP4 path. *(codebase)*
- **N9. Wrong constant location at line 1728.** `api/routes/heygen.py:26` has only `WORDS_PER_S`. The rate is `API_USD_PER_S` in `web/src/director/HeygenPanel.tsx:7`. **Edit:** "`WORDS_PER_S = 2.5` moves here from the route, and `USD_PER_S = 0.0385` mirrors the panel's `API_USD_PER_S` (removed from the panel in item 49)". *(codebase)*
- **N10. `preview_frames` has two signatures.** Item 25 (line 1934) has `(s, profile)`; item 41a (line 2279) has `(s, conn, profile)`. **Edit:** item 25 uses `preview_frames(s, conn, profile)`. *(readiness)*
- **N11. Profile save checks that the YouTube channel is connected.** Lines 657-660 return 422 on save for an unconnected `youtube_channel`. This does not gate the pipeline, so it is consistent with the ruling, but Dan cannot save a channel he has not connected yet. **Edit, only if unintended:** "an unconnected id is saved with a warning". Otherwise leave it. *(design)*
- **N12. The resolution log is out of date.** The spec itself is correct. In `channel_profiles_review.md`:
  - lines 191-193 say the MCP `youtube_upload` tool is "unchanged by this design". **Edit:** "Settled: item 28a removes the MCP tool and requires `Origin` on the take route".
  - the M6 row (line 49) and lines 148-150 still describe the approve-script YouTube check. **Edit:** mark them superseded by the manual-upload ruling.

  *(design)*
- **N13. Two smaller issues in item 55 and the hardening rules.**
  - **`docs/DESIGN.md:354` rule 2** ("Workings stay until the video is on YouTube") contradicts purge from `ready` and `cancelled`. Item 55 should rewrite it to "until Dan purges them".
  - **The `danslab` source scan** (lines 2190-2193) would match the READMEs that item 54 asks to describe the seed. Limit the scan to `*.py`, `*.ts` and `*.tsx`.
  - **Optional hardening:** publish, purge, repin and cancel could require a present `Origin`, as approve-budget and upload do.

  *(codebase)*
