# Stage 0 measurements

Plan item 12 of `daily-episode-factory.md`. The numbers feed the defaults in `core/config.py`
(`episode_rerender_attempts`, `episode_rerender_usd`, `heygen_month_ceiling_usd`) and the
hours-per-episode target in the Goals section. Rows marked **Mac Studio** can only be measured on
Dan's machine; this file records the procedure and the result, and is updated as they come in.

## Measured in the Stage 0 build (cloud container, x86_64, software Chromium)

| Measurement | Result |
| --- | --- |
| HyperFrames and GSAP version pair | `hyperframes@0.9.6`, `gsap@3.15.0` (`episode/templates/package-lock.json`); `npm ci` 79 packages, about 10 s |
| Intro render, 7.2 s at 25 fps, 1920x1080, quality `delivery` | 35 s wall clock (180 frames), one worker, software rendering; `tools/brand/make_intro.py` |
| Intro file | 619 KB, h264 25 fps + the original AAC track |
| Base install (`uv sync`, no extra) | unchanged; the `episode` package imports with `cv2`, `numpy`, `scipy`, `PIL`, `rembg`, `playwright` blocked (`tests/test_episode_imports.py`) |
| Lock resolution with the `episode` extra | adds `opencv-python-headless 5.0.0.93`, `playwright 1.64.1`, `pyee 14.0.0` |

## To measure on the Mac Studio (fill in)

| Measurement | How | Result |
| --- | --- | --- |
| HeyGen latency per 10 s scene | time from `create_video` to `completed` for three scenes rendered one after another, from the `jobs` rows' timestamps | |
| HeyGen concurrent cap | submit six scene renders at once; count how many run before HeyGen answers 429 or queues | |
| HeyGen minimum billed seconds | the credit delta on the account page after one 3 s scene and after one 10 s scene | |
| **Does HeyGen bill a `failed` render?** | a paid test: submit one render with an input that fails (an empty audio asset), compare the credit balance before and after. Until measured the ledger charges a failed render as if billed (the safe assumption kept at escalation E1) | |
| rembg per clip | `time` of the existing `cutout` job on one 10 s clip (the worker log shows the duration) | |
| whisper per clip | `time` of `whisper-cli` on one 10 s clip with the model `transcribe.whisper_model` picks | |
| One HyperFrames card render | `npx hyperframes render` of one 10 s card from the Episode 1 v2 storyboard at 25 fps, `-w 4` | |
| Disk per episode | `du -sh <data_dir>/episodes/<id>` after one full run (clips, cut-outs, cards, composites, final) | |
| Playwright Chromium path | `/api/health` → `tools.playwright_chromium` after `playwright install chromium` | |

The HeyGen rows cost real money and run only on Dan's explicit go, from his API key; nothing in
the repository runs them.
