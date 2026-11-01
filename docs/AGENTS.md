# StreamStudio for agents

Every artifact in StreamStudio is in one **library**, and every artifact names the **actions** that use it. Any agent (Claude Code, Paperclip agents, Hermes…) can read the library and drive the stage.

## Connect

```
claude mcp add streamstudio -- python -m streamstudio.mcp     # from server/, with its venv
# or point it elsewhere:
STREAMSTUDIO_URL=http://<mac-studio-tailnet-name>:8787 python -m streamstudio.mcp
```

The connection is plain HTTP on the same API, so it's open to localhost and the tailnet only.

| MCP tool | HTTP | What it does |
|---|---|---|
| `library_list(group?, kind?, tag?, query?)` | `GET /api/library` | All artifacts, or one tab / kind / tag; every query word must match |
| `library_get(id)` | `GET /api/library/{id}` | One artifact |
| `library_name(id, title?, tags?)` | `PATCH /api/library/{id}` | Give an artifact its own name and tags (empty title = default) |
| `vault_status()` | `GET /api/vault` | Where the off-machine copies live; how much is not backed up |
| `vault_backup()` | `POST /api/vault/push` | Back up new or changed clips, takes and the catalog (a job) |
| `vault_fetch(key)` | `POST /api/vault/fetch` | Bring a vault-only file back (pass the artifact's `storage.key`) |
| `studio_guide()` | `GET /api/agent/guide` | **Read first:** how a video is built (`docs/AGENT_GUIDE.md`) |
| `studio_timeline()` | `GET /api/agent/timeline` | The video as a timeline: what plays when, after the rules, with warnings |
| `studio_state()` | `GET /api/agent/state` | What is on stage now |
| `studio_do(action, args)` | `POST /api/agent/do` | Run an action in the open editor |
| `heygen_estimate(items)` | `POST /api/heygen/render` with `confirm:false` | Cost estimate only |
| `recording_transcribe(id)` | `POST /api/recordings/{id}/transcribe` | Transcribe a take locally (whisper.cpp, a job) |
| `youtube_status()` | `GET /api/youtube` | Which channels are connected |
| `youtube_upload(id, title, description?, tags?, channel?)` | `POST /api/recordings/{id}/youtube` | Upload a take as a **private** video (a job) to a connected channel; Dan publishes it |
| `recording_transcript(id)` | `GET /api/recordings/{id}/transcript` | Text, segments and word timings; captions at `/api/recordings/{id}.srt` |

## Library tabs, names, storage

Every artifact has a `group` (the Library tab: Scenes, Avatar, Media, Recordings, Workflows,
Layouts), a specific `name` (renamed ones keep `default_name`), `tags`, and for files a
`storage: {key, local, vault}`. A file that is only in the vault (`local:false`) still works:
the server fetches it the first time it is played or downloaded; call `vault_fetch` first to avoid
the wait.

## Artifact kinds

| kind | id example | main action |
|---|---|---|
| scene | `scene:studio-solo` | `scene.activate {id}` |
| template | `template:studio-circle` | `scene.new {template, collection?}` |
| cue | `cue:content` | `cue.apply {cue, zoom?}` (the lip-sync guard always applies) |
| gesture | `gesture:point-up-right` | `gesture.play {id}` |
| target | `target:main` | `point.at {target}` |
| hotspot | `hotspot:monitor` | `point.at {target:'hotspot:monitor'}` |
| object | `object:codex` | `table.event {event:'arrive:codex'}`, `media.add {item:'codex'}` |
| media | `media:<id>` | `media.add {item}` |
| workflow | `workflow:browser` | `workflow.insert {id, fields?, mode}` |
| clip | `clip:<key>` | a rendered HeyGen clip (Dan's own voice) |
| recording | `recording:rec_…` | a finished MP4 at its `url` |

**Script and timeline actions:**
- `timeline.get`;
- `publish.kit` (title, description with chapters, captions as .srt);
- `segment.preview {index}`;
- `segment.update {index, patch}`;
- `segment.add {after?, segment}`;
- `segment.remove {index}`;
- `script.set {segments}`.

**More actions:**
- `media.remove {id}`;
- `main.source {src}`, where `src` is a web page, a file path, or null;
- `script.play {from?}` and `script.stop`;
- `avatar.shape {shape}`;
- `orientation.set {orientation}`.

`library_list` returns the full argument list for each action.

## Pointing at anything
`point.at` aims from where Dan is: seated at the desk, or in his small card.
- It picks up, level or down, and left or right, toward the target's position.
- It uses the closest movement that has a real clip.
- If no clip exists, a pointer cue stands in.

## What agents cannot do (by design)
- **Spend money.** HeyGen renders only start from a click in Script → HeyGen, after the cost is shown.
- **Start a capture.** Record and Go live need a click in the Program window: browsers only allow screen capture from a person's click.
- **Bypass the lip-sync guard.** `cue.apply` always enforces it.

## How it works
1. The open editor publishes the artifacts it owns (`POST /api/library/web`) and listens on `/api/agent/stream` (Server-Sent Events).
2. `POST /api/agent/do` sends the action to the editor and waits up to 15 s for the result.
3. The server adds what it owns (scenes, clips, recordings) and keeps the editor's last catalog, so `library_list` works with the editor closed.
4. Stage actions need the editor open; without it they return 409.
