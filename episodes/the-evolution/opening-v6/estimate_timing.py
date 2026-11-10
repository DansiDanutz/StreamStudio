"""Estimated word timings for the motion review (no take yet).
retime.py replaces timeline.js with the real take's word timings."""
import json, re, sys
lines = json.load(open("script.json"))
LEAD, GAP, TAIL = 0.45, 0.45, 2.4
t = LEAD; words = []; spans = []
for li, line in enumerate(lines):
    toks = line.split()
    s0 = t
    for tok in toks:
        core = re.sub(r"[^\w']", "", tok)
        syl = max(1, len(re.findall(r"[aeiouy]+", core.lower())))
        d = 0.13 + 0.115 * syl
        if core in ("AI",): d = 0.42
        words.append(dict(line=li, w=core, s=round(t, 3), e=round(t + d, 3)))
        t += d
        if tok.endswith((".", "?")): t += 0.42
        elif tok.endswith(","): t += 0.16
    spans.append(dict(line=li, s=round(s0, 3), e=round(words[-1]["e"], 3)))
    t += GAP
dur = round(words[-1]["e"] + TAIL, 3)
open("timeline.js", "w").write("// ESTIMATED timings (no take yet)\nconst TIMING=" + json.dumps(dict(source="estimate", duration=dur, lines=spans, words=words)) + ";\n")
print("duration", dur); [print(s, lines[s['line']][:40]) for s in spans]
