# Offline compose: a HeyGen render → a finished StreamStudio-style video

Used for "DansLab — the AI Business Network" (docs/scripts/danslab-network.md).

1. Render the whole script in HeyGen as one video (one scene per segment).
2. `cuts.json`: segment boundaries in seconds. Found by matching HeyGen's scene changes
   (ffmpeg `scene` score) with the script's character counts, then snapping each cut to the middle of
   the nearest silence (`silencedetect`), so no word is clipped.
3. `masks.py WORKDIR`: person masks (rembg `u2net_human_seg`) for the full-frame segments, every 2nd–4th
   frame; render.py blends between them.
4. `render.py WORKDIR OUT.mp4 [--preview]`: Dan seated in the studio plate (desk in front) for talking
   segments; for site segments the page is a large card over the blurred studio and Dan is in a small
   circle (his own lip-synced voice throughout). Titles, name tags and the end card are drawn here.
   Audio is the HeyGen track, loudness-normalised to −14 LUFS.

WORKDIR holds `heygen.mp4`, `cuts.json`, `masks/` and `stills/` (16:9 captures of the sites).
