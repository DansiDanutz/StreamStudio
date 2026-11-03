# tools

## Overview

Command-line production tools that sit outside the StreamStudio server and web app. They take a finished HeyGen
avatar render and turn it into a DansLab episode offline: segment cutting, person masks, the studio compositor,
HyperFrames motion cards and the logo intro, per-scene QA and re-render, and the final mix with intro, music and
SFX. Everything here is run by hand with Python 3 and ffmpeg; nothing in `tools/` is imported by `server/` or `web/`.

## Subdirectories & Boundaries

- compose: [./compose/README.md](./compose/README.md) - the offline episode pipeline (`cuts.py`, `masks.py`,
  `render.py`, `mix.py`, `scenecut.py`, `qa_avatar.py`, `splice.py`, `peek.py`) with its per-episode plan files, the
  OpenCV face model under `compose/models/`, and two code subdirectories:
  - compose/motion: [./compose/motion/README.md](./compose/motion/README.md) - HyperFrames motion-card builder
    (`build.py` `Comp`), the Episode 1 storyboards (`cards.py`, `cards_v2.py`) and capture stitching (`stitch.py`).
  - compose/motion/intro: [./compose/motion/intro/README.md](./compose/motion/intro/README.md) - generator for the
    DansLab logo-reveal intro composition (`make_intro.py`).
