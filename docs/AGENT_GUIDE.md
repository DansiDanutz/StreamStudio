# StreamStudio: how a video is made (guide for agents)

Read this once, then use `studio_timeline` to see the current video and `studio_do` to change it.

## The model, in four levels
1. **Show.** The channel: Dan's studio, his avatar, the opener and closer.
2. **Script.** An ordered list of **segments**. The video is the segments played in order.
3. **Scene.** A saved stage set: the backdrop, where the cards sit, and the media cards on it. A segment can switch the scene.
4. **Cue.** How the cards move inside the scene for one segment: the layout.

## A segment (all fields except `text` and `cue` are optional)

| field | meaning | values |
|---|---|---|
| `text` | what Dan says | the line; it sets the length when there is no clip (~150 words/min) |
| `cue` | the layout | `avatar` (Dan fills the frame), `duo` (Dan big, content small), `split` (the scene as laid out), `content` (content big, Dan small), `full` (content only), `pip` (Dan small over the studio) |
| `scene` | switch to this scene first | a scene id from `library_list kind=scene` |
| `gesture` | Dan moves first; then the layout follows his hand; then he talks | `auto` (aims at `target`) or a gesture id |
| `target` | what he points at | `main`, `menu`, `media:<id>`, `hotspot:monitor`, `hotspot:trading`, `hotspot:table` |
| `via` | the Main card opens out of / closes into this studio place | `monitor`, `trading` |
| `visual` | what the Main card shows from now on | a web page (`https://…`), or a file path |
| `table` | 3D objects on the desk | `arrive:<id>`, `leave:<id>`, `react:all`, `clear`; chain with `;` |
| `media` | media cards (dragged in from the Library) | `show:Codex`, `hide:Codex`, `move:Codex@x,y,w` (centre and width, as fractions of the frame), `focus:Codex` (big, centred), `reset:Codex`; chain with `;`. A card is named by its label or id. |
| `zoom` | zoom into the Main card | `{x, y, scale}` with x, y in 0..1 and a scale of about 1.6 |
| `voice` | where the voice comes from | `clip` (the clip's own lip-synced audio) or `narration` |
| `clip` | Dan's rendered clip for this line | set by Script → HeyGen |

## The rules that change what plays (the timeline shows them)
- **Lip-sync guard:**
  - Dan's face can only be large (`avatar`, `duo`) while the voice is the clip's own audio.
  - Otherwise `avatar` plays as `pip` and `duo` plays as `content`.
  - The timeline marks these: asked → plays.
- **Gestures:**
  - The movement used is the closest one that has a real clip.
  - With no clip, a pointer cue (a light sweep and a ring) stands in.
- **The scene carries over:** a segment with no `scene` stays in the last one set.
- **The Main card's source carries over:** a segment with no `visual` keeps showing the last one set.
- **Media card moves are temporary:**
  - They apply while the script plays and reset when it stops.
  - They never change the saved scene.
  - Pointing at a moved card aims at where it now is.

## Typical moves

| You want | Do |
|---|---|
| Point at the monitor, then open the browser | Segment A: `{cue:'avatar', gesture:'auto', target:'hotspot:monitor'}`. Segment B: `{cue:'content', via:'monitor', visual:'https://fake-real.live'}` |
| Two cards, left and right | Segment A: `{media:'move:Claude Code@0.17,0.32,0.22; hide:Codex', gesture:'auto', target:'media:Claude Code'}`. Segment B: `{media:'move:Codex@0.83,0.32,0.22', gesture:'auto', target:'media:Codex'}` |
| Explain a card | `{gesture:'auto', target:'media:<id>', cue:'duo'}`, then `{cue:'content'}` |
| A tool appears on the table | `{table:'arrive:codex', gesture:'present-right'}` |
| Back to Dan alone | `{cue:'avatar', via:'monitor'}`; the browser closes back into the monitor |
| Start from a ready-made shape | `workflow.insert {id, fields}` (see `library_list kind=workflow`) |

## Working loop
1. Run `studio_timeline` and read `items[i].plays`, `voice`, `gesture` and `warnings`.
2. Fix things with `segment.update {index, patch}`, `segment.add`, `segment.remove` or `script.set`.
3. Run `segment.preview {index}` to put that moment on stage, then `script.play`.
4. Leave paid and capture steps to Dan:
   - HeyGen renders: use `heygen_estimate` to tell him the cost.
   - Record and Go live.
