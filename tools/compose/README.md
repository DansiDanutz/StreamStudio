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
- `endcard` [title, link, small print].

`peek.py WORKDIR t1 t2 …` renders single frames at those seconds into `WORKDIR/peek.jpg` for checking.
