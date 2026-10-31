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
| `library_list(kind?, query?)` | `GET /api/library` | All artifacts, or one kind |
| `library_get(id)` | `GET /api/library/{id}` | One artifact |
| `studio_state()` | `GET /api/agent/state` | What is on stage now |
| `studio_do(action, args)` | `POST /api/agent/do` | Run an action in the open editor |
| `heygen_estimate(items)` | `POST /api/heygen/render` with `confirm:false` | Cost estimate only |

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
