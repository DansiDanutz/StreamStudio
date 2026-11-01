"""Finish an episode: logo intro + composed video, with voice, a very quiet music bed and a few SFX.

    python mix.py EPISODE_DIR MAIN.mp4 INTRO.mp4 OUT.mp4 [--music ambient-pad]

EPISODE_DIR has cuts.json + plan.json (scene timing and cues) and heygen.mp4 (the voice).
Levels (production rules): voice -16 LUFS, music bed -36 LUFS (about 20 dB under the voice),
SFX about -26 LUFS, only at special moments; the whole mix is normalised to -14 LUFS / -1.5 dBTP.
SFX cues come from the plan: question scenes (riser into the scene + pop on the card), whoosh_at,
glitch, end cards, plus card moments read from the motion cards (tab changes, the counter landing).
Writes OUT.mp4 and OUT.cues.json (every cue, for checking).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 48000
import os
LIB = Path(os.environ.get('MEDIA_LIB', '/home/claude/dansidanutz/claude-youtube/media/library'))  # music/ and sfx/
COMPS = Path(os.environ.get('CARD_COMPS', Path(__file__).resolve().parent / 'motion' / 'comps'))  # built motion cards

W, MAIN, INTRO, OUT = (Path(a) for a in sys.argv[1:5])
MUSIC = next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == '--music'), 'ambient-pad')
cuts = json.load(open(W / 'cuts.json'))
plan = json.load(open(W / 'plan.json'))


def load(path, lufs=None, extra=''):
    af = ','.join(x for x in [extra, f'loudnorm=I={lufs}:TP=-2:LRA=20' if lufs is not None else ''] if x)
    cmd = ['ffmpeg', '-v', 'error', '-i', str(path)] + (['-af', af] if af else []) + \
          ['-ac', '2', '-ar', str(SR), '-f', 'f32le', '-']
    a = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32)
    return a.reshape(-1, 2).copy()


def dur(path):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)],
                                capture_output=True, text=True, check=True).stdout)


INTRO_D = dur(INTRO)
total = INTRO_D + dur(MAIN)
mix = np.zeros((int(total * SR) + SR, 2), np.float32)


def put(a, t, gain=1.0):
    i = int(t * SR)
    n = min(len(a), len(mix) - i)
    if n > 0:
        mix[i:i + n] += a[:n] * gain


# intro (logo reveal with its own SFX), then the voice
put(load(INTRO, -18), 0)
put(load(W / 'heygen.mp4', -16), INTRO_D)

# music bed: loop with crossfades, fade in after the logo, fade out at the end
m = load(LIB / 'music' / 'clips' / f'{MUSIC}.mp3', -36)
xf = int(3 * SR)
need = int((total - INTRO_D + 2) * SR)
bed = m.copy()
ramp = np.linspace(0, 1, xf, dtype=np.float32)[:, None]
while len(bed) < need:
    bed[-xf:] = bed[-xf:] * (1 - ramp) + m[:xf] * ramp
    bed = np.concatenate([bed, m[xf:]])
bed = bed[:need]
fi, fo = int(2.5 * SR), int(5 * SR)
bed[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)[:, None]
bed[-fo:] *= np.linspace(1, 0, fo, dtype=np.float32)[:, None]
put(bed, INTRO_D - 1.0)

# ------------------------------------------------------------------ SFX cues
cues = []


def cue(name, t, db=0.0, why=''):
    cues.append({'sfx': name, 't': round(t, 2), 'db': db, 'why': why})


def comp_times(card, pattern):
    f = COMPS / card / 'index.html'
    return [float(x) for x in re.findall(pattern, f.read_text())] if f.exists() else []


seen_cards = set()
for i, p in enumerate(plan):
    t0, d = cuts[i] + INTRO_D, cuts[i + 1] - cuts[i]
    if p.get('question'):
        cue('riser-soft', t0 - 1.3, -3, f'scene {i + 1}: question coming')
        fa = p['lowers'][0][0] if p.get('lowers') else 0
        cue('pop-reveal', t0 + 0.3 + fa * d, -4, f'scene {i + 1}: question card')
    if p.get('whoosh_at') is not None:
        cue('whoosh-soft', t0 + p['whoosh_at'] * d - 0.2, -2, f'scene {i + 1}: push into the monitor')
    for gf, gd in p.get('glitch', []):
        cue('glitch-zap', t0 + gf * d, -1, f'scene {i + 1}: glitch')
    if p.get('endcard'):
        cue('warm-shimmer', t0 + p.get('end_at', 0) * d, 0, f'scene {i + 1}: end card')
    for fa, fb, name, sub in p.get('lowers', []):
        if 'AI avatar' in name:
            cue('impact-deep-soft', t0 + 0.3 + fa * d, -2, f'scene {i + 1}: the avatar reveal')
    v = p.get('video')
    if v and not p.get('cont'):  # card moments, read from the motion card itself
        card = v.rsplit('.', 1)[0]
        for tb in comp_times(card, r"tl\.to\('\.blank',\{opacity:1,duration:[.0-9]+\},([0-9.]+)"):
            cue('ui-click-soft', t0 + tb, -6, f'{card}: new page opened')
        land = comp_times(card, r"textContent='13\.5K'\},null,([0-9.]+)")
        if land:
            cue('sparkle-soft', t0 + land[0] - 0.1, 0, f'{card}: 13.5K subscribers')

sfx_cache = {}
for c in cues:
    if c['sfx'] not in sfx_cache:
        sfx_cache[c['sfx']] = load(LIB / 'sfx' / 'clips' / f"{c['sfx']}.mp3", -26)
    put(sfx_cache[c['sfx']], c['t'], 10 ** (c['db'] / 20))

mix = mix[:int(total * SR)]
wav = OUT.with_suffix('.mix.f32')
mix.astype(np.float32).tofile(wav)
Path(str(OUT) + '.cues.json').write_text(json.dumps(cues, indent=1))

# picture: intro (to 25 fps) + main, audio: the mix, normalised for YouTube
subprocess.run([
    'ffmpeg', '-v', 'error', '-y', '-i', str(INTRO), '-i', str(MAIN),
    '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', str(wav),
    '-filter_complex', '[0:v]fps=25,format=yuv420p,setsar=1[a];[1:v]format=yuv420p,setsar=1[b];[a][b]concat=n=2:v=1:a=0[v];'
                       '[2:a]loudnorm=I=-14:TP=-1.5:LRA=11[au]',
    '-map', '[v]', '-map', '[au]', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-r', '25',
    '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', '-shortest', str(OUT)], check=True)
wav.unlink()
print('done', OUT, f'{total:.1f}s', len(cues), 'cues')
