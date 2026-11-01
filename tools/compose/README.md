# Offline compose: a HeyGen render → a finished StreamStudio-style video

Used for "DansLab — the AI Business Network" (docs/scripts/danslab-network.md).

1. Render the whole script in HeyGen as one video (one scene per segment).
2. `cuts.py WORKDIR SCRIPT.json` → `cuts.json`: segment boundaries in seconds. Download HeyGen's captions
   too (⋮ → Download → Captions) as `WORKDIR/captions.srt`; captions are matched to the script's segments
   and each cut is snapped to the middle of the pause between them (`silencedetect`), so no word is clipped.
   (Scenes of the same avatar have no visible scene change, so the captions are what make this exact.)
3. `masks.py WORKDIR`: person masks (rembg `u2net_human_seg`) for the full-frame segments, every 2nd–4th
   frame; render.py blends between them.
4. `render.py WORKDIR OUT.mp4 [--preview]`: Dan seated in the studio plate (desk in front) for talking
   segments; for site segments the page is a large card over the blurred studio and Dan is in a small
   circle (his own lip-synced voice throughout). Titles, name tags and the end card are drawn here.
   Audio is the HeyGen track, loudness-normalised to −14 LUFS.

WORKDIR holds `heygen.mp4`, `cuts.json`, `masks/` and `stills/` (16:9 captures of the sites).

## Per-episode plans
A WORKDIR may also hold `plan.json`: one entry per segment, replacing the built-in plan
(`episode-01.plan.json` is Episode 1's). Keys:
- `kind`: `avatar` (Dan in the studio) or `card` (`still`, `tag`, optional `intro_zoom` [cx, cy] = push into the studio monitor first).
- `title` [line 1, line 2]: title card rising on the table.
- `lower` [name, sub]: one table card; `lowers` [[from, to, name, sub], …] several, timed as fractions of the segment.
- `chips` [names] with optional `chip_at` [fractions]: small cards rising one by one, e.g. on the words that name them.
- `zoom` [cx, cy, z] or `zoom_path` [[fraction, cx, cy, z], …]; `card_x` places table cards while zoomed.
- `endcard` [title, link, small print], shown from `end_at` to `end_until` (fractions; default: the last 6.5 s).
- Motion cards: `video` (a HyperFrames render in `WORKDIR/cards/`), `video_at` (seconds into that card where this
  segment starts) and `cont: true` when a segment continues the same card (no fade between them).
- `chips_out` (fraction): when the chips leave. `frame` [cx, cy, z]: a slightly tighter framing for the whole
  segment (table cards stay in screen space). `glitch` [[fraction, seconds], …]: RGB-split glitch moments.
- Sound cues for `mix.py`: `question: true` (riser into the segment, pop on its card), `whoosh_at` (fraction).

`episode-01-v2.plan.json` is Episode 1 v2's plan; its motion cards are `motion/cards_v2.py`
(`CARDS=cards_v2 EP_SCRIPT=… EP_DURATIONS=episode-01-v2.durations.json python3 motion/build.py`).

## Finishing: intro, music, SFX
`mix.py WORKDIR MAIN.mp4 INTRO.mp4 OUT.mp4 [--music ambient-pad]` puts the DansLab logo intro in front and mixes
the voice (−16 LUFS), a very quiet music bed (−36 LUFS, looped, fading in after the logo) and SFX only at the
special moments the plan names (plus the card's own page changes and counter landing), then normalises the
whole thing to −14 LUFS. Every cue is written to `OUT.mp4.cues.json`. Music and SFX come from the media library
(`MEDIA_LIB`, ElevenLabs-generated on Dan's account).

## Scenes of ~10 s
`scenecut.py` cuts a long take into scene clips by caption text, so each scene is checked
(`qa_avatar.py`) and, if faulty, re-rendered alone and swapped in.

`peek.py WORKDIR t1 t2 …` renders single frames at those seconds into `WORKDIR/peek.jpg` for checking.
