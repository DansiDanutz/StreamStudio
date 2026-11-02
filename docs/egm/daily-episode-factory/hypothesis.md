# Daily episode factory: anchored hypothesis for Goldfish review

* **Author:** Dan (DansiDanutz)
* **Date:** 2026-11-02
* **Mode:** BRAINSTORM (concept, not a design yet)

## Hypothesis

Turn StreamStudio into a daily episode factory for scripted DansLab videos. There is no live
streaming. Two stages:

1. **Script stage.** From a topic, produce a fact-checked script in a question-and-answer
   structure (a mysterious question, then the answer, repeated; a light reveal at the end that the
   presenter is Dan's AI avatar), split into scenes of about 10 seconds (3 to 13 s), names written
   for the voice, every factual claim carrying a source or a softer wording.
2. **Production stage.** Run the pipeline that today lives as hand-operated scripts in
   `tools/compose` as StreamStudio jobs, in order: per-scene HeyGen avatar render (the only paid
   step; cost shown and confirmed first), site captures and HyperFrames motion cards for every site
   mention, per-scene QA (face present and placed, glitches, frozen frames, lips versus voice) with
   single-scene re-render and splice, the DansLab logo intro plus music bed and sound effects at
   named moments, the publish kit (title, description with chapters, captions) and the YouTube
   upload (private by default).

Dan's time is limited to writing or approving the script and approving the HeyGen cost. Free,
local tools are preferred; quality is not traded away for cost. Success: one episode a day with no
step performed outside the app.

## What exists today (ground truth for reviewers)

* The live studio (stage, Program window, go-live) is built and will not be used for this.
* The editor already has: the Director (script as master clock, cues, lip-sync guard), HeyGen panel
  (estimate then confirmed render), per-segment clips, timeline, publish kit, YouTube upload of a
  take, library and vault, agent bus and MCP server. See `README.md` and the per-directory
  `README.md` contracts under `web/src/` and `server/src/streamstudio/`.
* The offline pipeline that made Episode 1 v2 is in `tools/compose` (see its `README.md`):
  `cuts.py`, `masks.py`, `render.py`, `scenecut.py`, `qa_avatar.py`, `splice.py`, `mix.py`,
  `motion/build.py` with storyboards, `motion/intro/make_intro.py`. It is run by hand, hard-codes
  machine paths (`render.py:STUDIO`, `motion/build.py:render`), reads music from a folder outside
  the repo (`mix.py:LIB`), and nothing in it is imported by the server or the web app.
* Episode 1 v2: 36 scenes, 293.6 s, 20 avatar scenes and 16 motion cards; script in
  `docs/scripts/episode-01-v2.md` and `.json`, plan in `tools/compose/episode-01-v2.plan.json`,
  measured durations in `tools/compose/episode-01-v2.durations.json`. Two scenes exceed 13 s,
  three are under 4 s. Site captures were taken by hand in Chrome; the HeyGen take was rendered
  and downloaded by hand; the final MP4 was uploaded by hand.
* The production rules are in `docs/DESIGN.md` under "Episode production rules" and summarised in
  `CLAUDE.md`. The lip-sync guard is a hard rule: Dan's face is large only while the voice is the
  clip's own lip-synced audio.
* Cost reference: `web/src/director/HeygenPanel.tsx:API_USD_PER_S = 0.0385`; a 300 s episode is
  about 11.5 USD of HeyGen at that rate, about 350 USD a month at one episode a day.
* Hard constraints: Mac Studio, localhost plus Tailscale only (`core/netguard.py`); paid APIs never
  run without an explicit click and a shown cost; every job handler is idempotent; all request
  paths go through `core/paths.py`.

## Open questions the reviewers should weigh

* Is a "script stage" inside StreamStudio the right boundary, or should script writing stay with
  the writing skills and agents that already exist, with StreamStudio only accepting a finished
  script?
* Which pieces of `tools/compose` should become worker jobs, which should stay command-line tools
  called by a job, and which should be dropped?
* How are site captures produced without a person driving a browser?
* What does one-episode-a-day do to HeyGen credits, disk (workings are kept until the video is
  posted), and render time on one Mac Studio?
* What is the smallest version that still removes every manual step?
