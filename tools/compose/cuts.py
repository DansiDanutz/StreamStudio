"""Segment cuts for a HeyGen render, from HeyGen's own captions.

    python cuts.py WORKDIR SCRIPT.json

WORKDIR holds heygen.mp4 and captions.srt (HeyGen: ⋮ → Download → Captions). SCRIPT.json is the list of
segment texts in order (strings, or objects with "text"). Captions are matched to segments by their text,
then each cut is snapped to the middle of the pause between the two segments (ffmpeg silencedetect),
so no word is clipped. Writes WORKDIR/cuts.json: [0, cut1, …, duration].

The captions are what make this reliable: HeyGen scenes of the same avatar have no visible scene change,
and frame-jump spikes inside pauses find most cuts but also give false positives.
"""

import json
import re
import subprocess
import sys
from pathlib import Path


def ts(x):
    h, m, s = x.replace(',', '.').split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def main():
    W, script = Path(sys.argv[1]), json.load(open(sys.argv[2]))
    texts = [t if isinstance(t, str) else t['text'] for t in script]
    caps = []
    for block in open(W / 'captions.srt').read().strip().split('\n\n'):
        lines = block.split('\n')
        a, b = lines[1].split(' --> ')
        caps.append((ts(a), ts(b), ' '.join(lines[2:])))

    starts, ends, seg, buf = [0.0], [], 0, ''
    for a, b, t in caps:
        if buf == '' and seg > 0 and len(starts) == seg:
            starts.append(a)
        buf += norm(t)
        target = norm(texts[seg])
        if len(buf) >= len(target) - 2:
            if buf[:20] != target[:20]:
                sys.exit(f'captions and script disagree at segment {seg + 1}: {buf[:40]!r} vs {target[:40]!r}')
            ends.append(b)
            seg, buf = seg + 1, ''
    if seg != len(texts):
        sys.exit(f'matched {seg} of {len(texts)} segments')

    log = subprocess.run(['ffmpeg', '-v', 'info', '-i', str(W / 'heygen.mp4'), '-af', 'silencedetect=n=-38dB:d=0.15',
                          '-f', 'null', '-'], capture_output=True, text=True).stderr
    marks = re.findall(r'silence_(start|end): ([0-9.]+)', log)
    sil, st = [], None
    for kind, v in marks:
        if kind == 'start':
            st = float(v)
        elif st is not None:
            sil.append((st, float(v)))
            st = None
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0',
                                str(W / 'heygen.mp4')], capture_output=True, text=True).stdout)

    cuts = [0.0]
    for i in range(1, len(texts)):
        gap = (ends[i - 1] + starts[i]) / 2
        a, b = min(sil, key=lambda q: abs((q[0] + q[1]) / 2 - gap))
        cut = round((a + b) / 2, 2)
        if abs(cut - gap) > 1.0:
            print(f'warning: cut {i} snapped {cut - gap:+.2f}s from the captions', file=sys.stderr)
        cuts.append(cut)
    cuts.append(round(dur, 2))
    json.dump(cuts, open(W / 'cuts.json', 'w'))
    print(cuts)


if __name__ == '__main__':
    main()
