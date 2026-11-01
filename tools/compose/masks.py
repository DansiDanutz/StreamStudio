"""Pass 1: person masks for the avatar segments (every 2nd frame, 25 fps source)."""
import json, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image
from rembg import new_session, remove

W = Path(sys.argv[1])
cuts = json.load(open(W / 'cuts.json'))
AVATAR = [0, 1, 7, 8, 9, 10, 15, 16]  # segment indexes shown full frame
if (W / 'plan.json').exists():  # avatar segments, plus card segments that open with a push into the studio
    PLAN = json.load(open(W / 'plan.json'))
    AVATAR = [i for i, p in enumerate(PLAN) if p['kind'] == 'avatar' or p.get('intro_zoom')]
else:
    PLAN = None
(W / 'masks').mkdir(exist_ok=True)
FPS = 25
STEP = 4
s = new_session('u2net_human_seg')
for i in AVATAR:
    a, b = cuts[i], cuts[i + 1]
    if PLAN and PLAN[i]['kind'] == 'card':
        b = min(b, a + 1.3)  # only the push-in needs Dan cut out
    f0, f1 = round(a * FPS), round(b * FPS)
    todo = [f for f in range(f0, f1 + 2) if f % STEP == 0 and not (W / 'masks' / f'{f:05d}.png').exists()]
    if not todo:
        continue
    # decode the segment once at 960x540, every frame, then mask the even ones
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{f0 / FPS:.3f}', '-i', str(W / 'heygen.mp4'),
                          '-frames:v', str(f1 - f0 + 2), '-vf', 'scale=960:540', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         capture_output=True, check=True).stdout
    n = len(raw) // (960 * 540 * 3)
    frames = np.frombuffer(raw, np.uint8).reshape(n, 540, 960, 3)
    for k in range(n):
        f = f0 + k
        if f % STEP or (W / 'masks' / f'{f:05d}.png').exists():
            continue
        m = remove(Image.fromarray(frames[k]), session=s, only_mask=True)
        m.save(W / 'masks' / f'{f:05d}.png')
    print('segment', i, 'done', flush=True)
print('ALL DONE', flush=True)
