# The Evolution — Episode 01 (DansLab · Then & Now series)

`opening-v6/` is the 85-second opening, built as one HyperFrames composition.

- **Series rule — Then & Now:** every episode and chapter hooks with something from the past (photo paper, sepia, film grain, projector sound), then a one-frame hard cut on "Now" to the present (night sky, orange + green, crisp).
- **Presenter:** the teal card is a slot for Dan's lip-synced take. The opening was designed around **one continuous take** that moves from full frame → portrait card lower-left → side panel and back. Note: `docs/DESIGN.md` asks for ~10 s scenes; the take can be rendered as ~10 s clips and joined, as long as it stays continuous in the edit.
- **Status:** motion, art and sound are final for review; the take is not yet made (HeyGen "Brian" voice is out of ElevenLabs quota).

## Files
| file | what |
| --- | --- |
| `The-Evolution-Opening-v6-sky-3d.mp4` | review render (guide captions, presenter slot) |
| `script.json` | the 9 spoken lines |
| `cues.json` | every animation cue as `[line, word, offset]` |
| `composition.head` + `composition.body` → `composition.html.in` | the HyperFrames composition source |
| `make_art.py` → `art/*.svg` | original vector artifacts with moving parts (phone dial, letter, radio, Moon, turntable, smartphone) |
| `sound.py` → `sound.wav` | original synthesized sound design (no samples) |
| `estimate_timing.py` | estimated word timings until the take exists |
| `make_take.py` | makes the take with StreamStudio's HeyGen client (paid, `--confirm` only) |
| `retime.py` | re-times every cue to the take's Whisper word timings; refuses a take whose words don't match |
| `build.py` | builds `index.html`, `cues.js`, `sound.wav` (`--final` once the take exists) |
| `render.py` | frame-exact Playwright render |
| `TAKE-NEEDED.md` | what to record / generate |

## Rebuild
```
python3 make_art.py && python3 build.py && python3 render.py out.mp4
# with Dan's take:
python3 make_take.py --confirm
whisper take.mp4 --model medium.en --word_timestamps True --output_format json --output_dir .
python3 retime.py take.json && python3 build.py --final && python3 render.py final.mp4
```
