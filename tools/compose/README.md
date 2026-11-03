# Episode composition utilities

The episode worker handles per-scene avatar clips, cut-outs, QA contact sheets, composition,
mixing, and Library registration. The Episode page exposes the scene preview and QA sheet.
Use the worker for new productions. [Episode package](../../server/src/streamstudio/episode/README.md)

The original plans in `episode-01.plan.json` and `episode-01-v2.plan.json` describe segment
framing, timed overlays, entrances, and sound cues. The worker's executable Episode 1 script
is the [36-scene fixture](../../server/tests/fixtures/episode-01-v2/script.json).
The legacy renderer, mixer and custom motion storyboards remain available for parity checks
with existing production material. [Historical tool reference](https://github.com/DansiDanutz/StreamStudio/blob/412a0e6/tools/compose/README.md)

The standalone tour renderer uses the same connected-card animation template as the worker.
It accepts a local Dan opener, local narration and two rendered website scenes.

## Website demonstration card (v1)

Discover the rules and JSON Schema through `GET /api/episodes/workflows` or run
`python tools/compose/website_demo.py catalog` in the server's episode environment.
Choose this workflow when the narration refers to a visible, specifically labeled feature on a
public website configured for automatic capture. Use an avatar scene for narration without a
visual reference. Check the label against the actual page before committing the direction.

Episode 1 scene s10 says “you set up your own product QR code”. Its source is
https://nervixpay.live. Keep its existing text, voice and site, and add:

    "plan": {"website_demo": {"workflow": "website-demo/v1",
      "focus_label": "Scannable NervixPay product preview", "side": "right", "reveal_at": 0.30}}

The worker captures the real browser viewport and creates a camera move toward that label.
This demonstrates the site's visible product preview. Set the site's capture mode to `auto`
only on hosts approved for unattended capture. Capture uses a fresh Chromium session.
The Episode page serves the composed scene from `GET /api/episodes/{eid}/scenes/{sid}/preview`.

For independent harnesses, export one scene object as scene.json. With the episode environment's
Python, run these commands from the repo root. The base MP4 is a narrated 1920×1080, 25 fps scene.

    python tools/compose/website_demo.py prepare scene.json workspace
    python tools/compose/website_demo.py preview scene.json workspace base.mp4 first.mp4

A second harness can read the catalog and save a new scene JSON with `side: "left"` and
`reveal_at: 0.55`. Run only `preview` with the edited JSON. It reads the existing card and base
from disk and copies the audio stream. The reveal is a fraction of scene duration. Missing capture
assets fail explicitly. The workflow version, URL and target label identify the capture.
