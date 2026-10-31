# Intro — "Let me introduce you to the world of AI" (3D objects on the table)

The reusable opener (and, reversed, the closer) for every DansLab video. First part of the video, highest quality bar.
Replaces the chalk-sketch idea (rejected: looked cheap).

## The idea
The table stays empty and real. Dan presses a button on the desk; a **3D object materialises on the table** for
each tool, hologram-like, with real reflections on the wood. He introduces each one in a few words. By the end,
six objects stand on the table and Dan orchestrates them (they light up / turn toward him as he names them).

Objects (in order): **Claude → Codex → Grok (with GrokBot) → Hermes → Kimi → GLM**.

## How it is built (layers, bottom to top)
1. **Plate** — the 3D studio (`assets/studio/plate-landscape-final.png`, 4K upscale when available).
2. **Dan** — HeyGen avatar clip per segment, cut out (`avatar/cutout.py`), seated behind the desk.
3. **Object clips** — one generated video per tool: the 3D emblem rising out of the table, rendered **on pure
   black** so it composites with *screen/add* blend and keeps its own glow and reflection. Each clip has three
   parts: `arrive` (1.5–2 s), `idle` (loopable 4 s), `react` (0.8 s pulse/turn, used when Dan names it).
4. **Desk layer** — the desk cut from the plate (`plate-landscape-final.desk.png`) on top of Dan only (not above
   the objects: the objects stand ON the desk, so they sit above the desk layer).
5. **Light wrap** — a soft teal/amber glow on the wood under each object (generated with the clip, or a radial
   gradient in the compositor).

Everything is composited in StreamStudio's stage (render mode) or, for the final deterministic render, Remotion.

## Shot list (segments → Director)
| # | Dan says (HeyGen, with a gesture) | Table | Cue |
|---|---|---|---|
| 0 | *(no words, 2 s)* A slow push-in on the empty studio. The button on the desk glows. | empty | avatar |
| 1 | Let me introduce you to the world of AI. The technology of the future, on this table, today. | button press → spark | avatar |
| 2 | First: Claude. This is where I think, plan and write. When I'm wrong, it says so. Best at reasoning, long context, and code review. | Claude object arrives, left | avatar |
| 3 | Codex. My pair programmer in the terminal. Fastest way from an idea to running code. | Codex arrives | avatar |
| 4 | Grok, with GrokBot on top: real-time market data, and my paper-trading agent that learns every day. | Grok + small GrokBot | avatar |
| 5 | Hermes. The messenger of my fleet; it runs the machines and talks to every other agent. | Hermes arrives | avatar |
| 6 | Kimi. Long documents, research, the reader of the team. | Kimi arrives | avatar |
| 7 | And GLM. Fast, cheap, local when I need it. | GLM arrives, right | avatar |
| 7b | And one more. OpenClaw, the lobster. The most exciting, most attractive thing I saw this year. And I gave up on it. | OpenClaw (red glass lobster) arrives centre and stays there | avatar |
| 7c | Not because it was bad. That is how fast AI moves: the thing that made me fall in love got replaced in months. | OpenClaw dims | avatar |
| 8 | Six minds, one table. I'm the conductor. Let's make something. | all `react` in sequence, then together | avatar |
| end | *(closer, reused)* Thanks for watching. Same table, next time. | objects dim, button light off | avatar |

Dan's "press": ask HeyGen for a hand gesture (tap on the desk / point) on segments 1–7. The object `arrive`
starts 400 ms after the gesture.

## Object design brief (one look for all six)
Hologram-solid: a **glass-and-light 3D emblem**, 25–30 cm tall on the desk scale, floating 2 cm above the wood on
a thin disc of light. Material: dark smoked glass with an inner volumetric glow in the tool's colour, fine edge
highlights in warm amber from the studio lamps, subtle teal rim light from the LED strips. A soft reflection on
the wood. Camera: locked, matches the plate (35 mm, desk-height, slight diagonal). Background: **pure black**.

Per-tool colour: Claude warm coral/terracotta · Codex white/mint · Grok black/silver with a red core · Hermes
deep violet · Kimi blue · GLM green-teal.

For the emblem shapes: use each tool's **official logo as the reference image** (Dan supplies the PNGs); the
prompt only describes material and motion, never redraws the mark. Keep marks proportionate, no wordmarks.

## Generation route
- **Image first, then video**: generate one still per object with the brief (image-to-image from the logo),
  approve the six stills for consistency, then animate each still with image-to-video (arrive / idle / react).
- Tools: Higgsfield (image + video, available through StreamStudio), or Kling / Veo / Runway in Dan's accounts.
- Output: 1920×1080 (object centred, black background), 25 or 30 fps, 2 + 4 + 1 s. Named
  `assets/objects/<tool>/{arrive,idle,react}.mp4`.
- Compositing positions on the desk (fractions of frame): Claude (0.18, 0.80) · Codex (0.31, 0.78) ·
  Grok (0.44, 0.77) · Hermes (0.56, 0.77) · Kimi (0.69, 0.78) · GLM (0.82, 0.80), scale 0.22 of frame height.

## Prompts (image, per object)
> Studio product render, pure black background, a single 3D emblem based on the attached logo, built as dark
> smoked glass with an inner volumetric glow in {COLOUR}, thin warm amber edge highlights and a subtle teal rim
> light, floating 2 cm above a dark walnut desk surface on a thin disc of light, soft reflection on the wood,
> 35 mm lens at desk height, slight three-quarter angle, cinematic, photoreal, 8k, no text, no wordmark.

## Prompts (video, from the approved still)
- **arrive**: "The emblem materialises from a point of light on the desk: particles gather, the glass forms, the
  inner glow ignites, a soft pulse of light spreads across the wood. 2 seconds. Camera locked. Black background."
- **idle**: "The emblem hovers and slowly rotates 10 degrees back and forth, the inner glow breathes gently, light
  disc shimmers. Seamless loop, 4 seconds. Camera locked. Black background."
- **react**: "The emblem brightens sharply, lifts 1 cm and settles, a ring of light expands across the desk.
  1 second. Camera locked. Black background."
