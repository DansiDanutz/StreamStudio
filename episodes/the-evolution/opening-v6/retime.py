"""Re-time the opening from Dan's real take, and refuse a take whose words don't match.

On the Mac Studio:
  whisper take.mp4 --model medium.en --word_timestamps True --output_format json --output_dir .
  # (or: mlx_whisper take.mp4 --word-timestamps True -f json)
  python3 retime.py take.json && python3 build.py --final

Writes timeline.js with source="take"; build.py then moves every card cue to Dan's spoken words.
"""
import difflib, json, re, sys
from pathlib import Path

here = Path(__file__).parent
norm = lambda s: re.sub(r"[^a-z0-9']", "", s.lower().replace("’", "'"))
lines = json.loads((here / "script.json").read_text())
script = [(li, re.sub(r"[^\w']", "", tok)) for li, line in enumerate(lines) for tok in line.split()]

wj = json.loads(Path(sys.argv[1]).read_text())
heard = [(w["word"].strip(), float(w["start"]), float(w["end"])) for seg in wj["segments"] for w in seg.get("words", [])]
a, b = [norm(w) for _, w in script], [norm(w) for w, _, _ in heard]
sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
match = {}
for blk in sm.get_matching_blocks():
    for k in range(blk.size):
        match[blk.a + k] = blk.b + k

# every line must be spoken as written (lip sync is only honest if the words are the script's)
bad = []
for li, line in enumerate(lines):
    idx = [i for i, (l, _) in enumerate(script) if l == li]
    ok = sum(i in match for i in idx) / len(idx)
    if ok < 0.9:
        bad.append(f"line {li+1} only {ok:.0%} matched: {line}")
if bad:
    sys.exit("TAKE DOES NOT MATCH SCRIPT — not using it:\n  " + "\n  ".join(bad))

words = []
for i, (li, w) in enumerate(script):
    if i in match:
        _, s, e = heard[match[i]]
    else:  # interpolate an unmatched word between its matched neighbours
        p = max([j for j in match if j < i], default=None); n = min([j for j in match if j > i], default=None)
        s = heard[match[p]][2] if p is not None else 0.0
        e = heard[match[n]][1] if n is not None else s + .3
    words.append(dict(line=li, w=w, s=round(s, 3), e=round(e, 3)))
spans = [dict(line=li, s=min(w["s"] for w in words if w["line"] == li), e=max(w["e"] for w in words if w["line"] == li)) for li in range(len(lines))]
dur = round(max(w["e"] for w in words) + 2.6, 3)
(here / "timeline.js").write_text("// MEASURED from Dan's take\nconst TIMING=" + json.dumps(dict(source="take", duration=dur, lines=spans, words=words)) + ";\n")
print(f"take matches script · {len(words)} words · duration {dur:.2f}s")
