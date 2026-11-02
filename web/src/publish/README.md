# publish

## Overview
What YouTube needs next to the video: a publish kit (title, description with chapters, `.srt` captions and notes) compiled from the timeline, the panel that shows and downloads it, and the upload of a finished take to YouTube through the server.

## Interface
- `kit.ts`: `PublishKit`, `srtTime(ms)`, `youtubeTime(ms)`, `captionChunks(text)`, `buildPublishKit(script, timeline, clipMs)`.
- `PublishKitPanel.tsx`: `PublishKitPanel({ kit, onClose })`.
- `YouTubeUpload.tsx`: `YouTubeUpload({ title, description })`.

## Invariants
- `kit.ts:buildPublishKit` is pure; captions come from the script text and voice timings, not speech recognition.
- Captions are at most `LINES_PER_CAPTION = 2` lines of `LINE_CHARS = 42` characters, broken between words (`captionChunks`); only `voiced` items (voice not `none`, non-empty text) get captions; caption time is split by character count within the item's `voiceMs`, starting after `leadMs`.
- Chapters start where `sceneInEffect` changes; any chapter shorter than `MIN_CHAPTER_MS = 10_000` is folded into the previous one; fewer than `MIN_CHAPTERS = 3` chapters yields an empty list and a note; titles are the first sentence cut to `CHAPTER_TITLE_CHARS = 60`.
- `buildPublishKit` adds notes for lines timed from word count (clip not in `clipMs`) and for silent lines.
- `YouTubeUpload.tsx`: privacy starts as `private` (`PRIVACY` first entry); only takes with `mp4` are offered; the upload button is disabled while a job is running or without a take or channel.

## Side Effects
- `PublishKitPanel.tsx`: `navigator.clipboard.writeText`; Blob downloads via a temporary anchor (`download`).
- HTTP (`YouTubeUpload.tsx`): `GET /api/youtube`, `GET /api/recordings` (on mount and on window `focus`), `POST /api/youtube/client`, link to `/api/youtube/connect` in a new tab, `POST /api/recordings/{id}/youtube` with `{ title, description, privacy, channel }`, `GET /api/jobs/{id}` every 2 s until done.

## Verification
- Run: `cd web && npx vitest run`
