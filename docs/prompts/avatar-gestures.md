# Avatar gestures: generation kit (HeyGen)

StreamStudio has 12 presenter gestures. You only generate the 8 right-hand ones and the beats; the
4 left-hand ones are the same clips mirrored on stage (the cut-out has no background, so a mirror is free).

| # | id (file name) | Used for | Generate? |
|---|---|---|---|
| 1 | `point-up-right` | the studio monitor, a card top-right | yes |
| 2 | `point-right` | a card at shoulder height on the right | yes |
| 3 | `point-down-right` | the table, a card bottom-right | yes |
| 4 | `point-up-left` | a card top-left | mirror of 1 |
| 5 | `point-left` | a card on the left | mirror of 2 |
| 6 | `point-down-left` | a card bottom-left | mirror of 3 |
| 7 | `present-right` | "this one" (open palm toward a card) | yes |
| 8 | `present-left` | same, left | mirror of 7 |
| 9 | `welcome` | opener, "let me show you" | yes |
| 10 | `thumbs-up` | wrap-ups | yes |
| 11 | `wave` | hello / goodbye | yes |
| 12 | `think` | "here's the question" | yes |

## Rules for every clip (they must cut invisibly into the base clip)
- The same avatar (Dan), the same look, framing, background, and resolution as `dan-landscape-test.mp4` (1920×1080, 25 fps).
- Start and end in the neutral seated pose: hands together on the desk, looking at camera.
- 2.5–4 s each.
- Mouth closed (silent) for the reusable set.

## In HeyGen (AI Studio)
1. Use Dan's avatar, with the Avatar IV engine. Click the avatar, then the person icon top-right, to open "Custom motion".
2. Use a script that keeps the mouth still: a pause only. If the editor needs words, use one short word and keep that clip's own audio. A clip with its own lip-synced voice is still allowed full frame.
3. Set one motion prompt per clip. Use one gesture, and end back at rest:
   - `point-up-right`: "Right arm raises and points up to the right at a screen behind, holds one beat, returns hands to the desk. Calm, confident."
   - `point-right`: "Right arm extends and points to the right at shoulder height, holds one beat, returns hands to the desk."
   - `point-down-right`: "Right hand points down and to the right at the table, holds one beat, returns hands to the desk."
   - `present-right`: "Right hand opens palm-up toward the right as if presenting something, holds one beat, returns to the desk."
   - `welcome`: "Both hands open outward, palms up, welcoming, then return together on the desk. Warm smile."
   - `thumbs-up`: "Right hand gives a thumbs-up at chest height, holds one beat, returns to the desk. Friendly."
   - `wave`: "Right hand raises and waves twice, friendly, then returns to the desk."
   - `think`: "Right hand rises to the chin, thoughtful look for one beat, then returns to the desk."
4. Export each clip as MP4 at 1080p and name it by its id (e.g. `point-up-right.mp4`).

Custom motion is capped at 10 s per scene and its timing can't be set exactly. Short clips with one gesture work best.

## Into the studio
```
python -m streamstudio.avatar.gestures ~/Downloads/gestures
```
This cuts each clip out of its background (local, free) and writes:
- `assets/avatar/gestures/<id>.cutout.webm`;
- `manifest.json`, which lists what exists.

The stage uses each clip as soon as it exists. Until then, the Director draws a pointer cue (a light sweep and a ring) toward the target.

## Better still: gestures inside the voice clip
For a segment where you point *while talking*, render that segment's clip in HeyGen with its script and a motion prompt (e.g. "points up to the right on 'this'"). The voice is the clip's own audio, so the lip-sync guard allows it full frame. Set the segment's gesture to "no gesture", because the gesture is already in the clip.

## Learned from the first HeyGen batch (31 Oct 2026)

**Rendered:** one video, "StreamStudio gestures v1": 8 scenes of 3 s each, Avatar IV, the look "Dan in his studio".

**Directions:**
- HeyGen reads "right arm" as Dan's own right, which points to the LEFT of the frame.
- Our directions are the viewer's. So in prompts, say "his left arm … toward the right side of the frame".
- `web/src/avatar/gestures.ts` `MOTION` now does this.

**Scene starts:**
- Some scenes start already mid-gesture.
- `streamstudio.avatar.gestures --rest-first` fixes that for free: it plays the clip backwards first, giving rest → gesture → rest.

**What we kept:**

| Gesture | Taken from | Note |
|---|---|---|
| `point-up-right` | scene 2 | rest-first |
| `point-right` | scene 1 | rest-first |
| `present-right` | scene 4 | |
| `welcome` | scene 5 | |
| `thumbs-up` | scene 6 | |
| `wave` | scene 7 | |
| `think` | scene 8 | |

**Dropped:** `point-down-right`. Scene 3 crossed both hands at the chest, so it still uses the pointer cue until we re-render it with the corrected prompt.
