"""Assemble The Evolution opening (v2).

Inputs : script.json, cues.json, timeline.js (word timings: estimated, or from retime.py)
         take.mp4 (optional) — Dan's continuous lip-synced take of script.json
Outputs: cues.js, index.html (HyperFrames composition), sound.wav (original SFX bed)

  python3 build.py            # review build: presenter slot + guide captions if no take.mp4
  python3 build.py --final    # requires take.mp4 and measured timings; no guide captions
"""
import json, re, sys
from pathlib import Path
import sound

here = Path(__file__).parent
TIMING = json.loads(re.search(r"const TIMING=(.*);", (here / "timeline.js").read_text()).group(1))
words, D = TIMING["words"], TIMING["duration"]
final = "--final" in sys.argv
take = here / "take.mp4"
if final:
    assert take.exists(), "final build needs take.mp4 (Dan's continuous take)"
    assert TIMING["source"] == "take", "final build needs timings measured from the take (run retime.py)"


def at(line, word, off):
    for w in words:
        if w["line"] == line and w["w"].lower() == word.lower():
            return round(w["s"] + off, 3)
    raise KeyError(f"cue word {word!r} not in line {line}")


cues = {k: at(*v) for k, v in json.loads((here / "cues.json").read_text()).items() if not k.startswith("_")}
(here / "cues.js").write_text("const CUE=" + json.dumps(cues) + ";\n")

if take.exists():
    presenter = '<video id="dan-take" src="take.mp4" muted playsinline></video>'
    media = (f'<video id="dan-take-clip" class="clip" src="take.mp4" data-start="0" data-duration="{D:.3f}" '
             f'data-track-index="1" style="display:none"></video>\n'
             f'<audio id="voice" class="clip" src="take.mp4" data-start="0" data-duration="{D:.3f}" data-track-index="2"></audio>')
else:
    presenter = ('<div class="slot"><div class="frame"></div><div class="lbl">DAN · CONTINUOUS TAKE<small>SLOT — RECORD THE OPENING LINES</small></div>'
                 '<div class="meter">' + "<i></i>" * 9 + "</div></div>")
    media = ""
media += f'\n<audio id="sound-design" class="clip" src="sound.wav" data-start="0" data-duration="{D:.3f}" data-track-index="3"></audio>'

html = (here / "composition.html.in").read_text()
for svgf in sorted((here / "art").glob("*.svg")):
    html = html.replace(f"<!--ART:{svgf.stem}-->", svgf.read_text())
html = html.replace("__DURATION__", f"{D:.3f}").replace("__PRESENTER__", presenter).replace("__MEDIA__", media)
if take.exists():
    html = html.replace('<div id="guide"></div>', '<div id="guide" data-off="1"></div>')
(here / "index.html").write_text(html)

sound.render(cues, D, here / "sound.wav")
print(f"duration {D:.2f}s · timing source: {TIMING['source']} · take: {'yes' if take.exists() else 'NO (slot)'}")
for k in ("shrink", "letterIn", "radioIn", "moonIn", "recordIn", "present", "absorb", "danBig", "danBack", "wallIn", "title"):
    print(f"  {k:9s} {cues[k]:6.2f}s")
