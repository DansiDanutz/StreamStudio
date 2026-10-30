# Intro — "I'm in love with AI" (desk sketch)

Format: Avatar cue throughout (Dan full-frame in the 3D studio). Each segment draws something on the desk.
Avatar clips: generate one per segment from the text below; ask for **hand gestures toward the desk**
(pointing, sketching motion) so the drawings read as his.

| # | Dan says | Desk sketch |
|---|---|---|
| 1 | Welcome to Dan's Lab. I'll say it straight: I'm in love with AI. Not the hype, the work. The part where an idea becomes a thing that runs. | `heart` — a heart with a small circuit trace, drawn near his hands |
| 2 | This table is big for a reason. Everything I build starts here, with the tools and the agents I trust. So let me draw you the team. | `grid` — a faint grid fans out across the desk |
| 3 | Codex writes the code with me. Claude thinks with me, plans with me, and tells me when I'm wrong. | `codex` + `claude` — a terminal window with a blinking prompt; a speech bubble with three dots |
| 4 | GrokBot trades for me, on paper for now, learning every day. Hermes runs my fleet, the messenger between all my machines. | `grokbot` + `hermes` — a robot head with a candlestick chart; a winged envelope |
| 5 | And this one… the OpenClaw lobster. The most exciting, most attractive thing I saw this year. And I gave up on it. | `lobster` — a lobster, drawn slowly, with a glow |
| 6 | Not because it was bad. Because that's how fast AI moves: what made me fall in love in the first place got replaced in months. That's the lesson, and that's the fun. | `lobster-crossout` — a soft X over the lobster, then a tiny "→ next" arrow |
| 7 | So together, with all of these, we're going to try to make money, in the open, on this table. Let's go. | `team` — all glyphs pulse once, a line connects them to a coin |

## Direction
- Cue: `avatar` for every segment (room + desk visible). Content cards stay hidden.
- Sketch style: neon chalk on the dark wood: 2.5 px stroke, teal `#5eead4` with warm accents `#f3c27a`, 60 % opacity,
  soft glow, drawn on with stroke animation (≈1.2 s per glyph), labels in a handwritten face (Caveat).
- Perspective: the sketch plane is mapped to the desk (far edge at 66 % of frame height), so lines foreshorten
  like they're really on the table.
- Timing: a sketch starts 300 ms after its segment starts; the cross-out in #6 starts 1.5 s in, on "gave up".
- Audio: the avatar clip is the voice. A faint chalk "scratch" SFX under each draw-on is optional (S5 audio mixer).
