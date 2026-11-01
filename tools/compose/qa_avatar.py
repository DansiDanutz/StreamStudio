"""Avatar QA for scene clips: find avatar faults before a scene goes into the video.

    python qa_avatar.py SCENES_DIR [--sheet]

For every scene-NN.mp4 it checks, on frames sampled at 12.5 fps:
- face: present in every sampled frame, same size and place as the other scenes (no drift or jump);
- glitches: a sudden whole-frame change inside the scene (a pop, a smear, a cut in the avatar render);
- frozen: the picture not changing for more than 0.6 s while the voice is speaking;
- lips: the mouth area must move while the voice speaks (silent lips = lip-sync fault),
  and must not chatter during long silences;
- seams: the jump between the end of one scene and the start of the next (pose/position), so the
  compositor can cover a big one with a card, a zoom or a cut-away.
Writes SCENES_DIR/qa.json and, with --sheet, qa-NN.jpg contact sheets (start, middle, end, worst frame).
FAIL = face/glitch/frozen fault (re-render the scene). LOOK = a lip warning: look at that moment by eye
(a head tilt or a smile can trip it). Exit code 1 if any scene FAILS.
"""
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

FPS_S = 12.5
CASCADE = cv2.CascadeClassifier(str(Path(__file__).parent / 'models' / 'haarcascade_frontalface_default.xml'))


def frames(path, w=480):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-vf', f'fps={FPS_S},scale={w}:-2', '-f', 'rawvideo',
                          '-pix_fmt', 'gray', '-'], capture_output=True, check=True).stdout
    h = int(round(w * 9 / 16 / 2) * 2)
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w)


def audio_rms(path, n):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-ac', '1', '-ar', '16000', '-f', 's16le', '-'],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    hop = int(16000 / FPS_S)
    r = np.array([np.sqrt(np.mean(a[i * hop:(i + 1) * hop] ** 2)) if i * hop < len(a) else 0 for i in range(n)])
    return r


def face_box(g):
    f = CASCADE.detectMultiScale(g, 1.1, 5, minSize=(40, 40))
    return max(f, key=lambda b: b[2] * b[3]) if len(f) else None


def check(path):
    F = frames(path)
    n = len(F)
    rms = audio_rms(path, n)
    voiced = rms > max(0.02, np.percentile(rms, 60) * 0.35)
    boxes = [face_box(F[i]) for i in range(n)]
    found = [b is not None for b in boxes]
    ref = np.median(np.array([b for b in boxes if b is not None]), axis=0) if any(found) else None
    issues = []
    if sum(found) < 0.97 * n:
        issues.append(f'face missing in {n - sum(found)} of {n} frames')
    # glitches: whole-frame jumps (ignoring the very first frames)
    d = np.abs(np.diff(F.astype(np.float32), axis=0)).mean((1, 2))
    med = np.median(d) + 0.3
    spikes = [i + 1 for i in range(2, len(d)) if d[i] > 6 * med and d[i] > 4]
    if spikes:
        issues.append('glitch at ' + ', '.join(f'{s / FPS_S:.1f}s' for s in spikes[:6]))
    # frozen while speaking
    still = d < 0.15
    run = best = 0
    for i, s in enumerate(still):
        run = run + 1 if (s and voiced[i + 1]) else 0
        best = max(best, run)
    if best / FPS_S > 0.6:
        issues.append(f'picture frozen {best / FPS_S:.1f}s while speaking')
    # lips: motion in the mouth area (lower third of the face box)
    mouth = np.zeros(n)
    if ref is not None:
        x, y, w, h = [int(v) for v in ref]
        y0, y1, x0, x1 = y + int(h * 0.62), y + int(h * 0.98), x + int(w * 0.25), x + int(w * 0.75)
        m = F[:, y0:y1, x0:x1].astype(np.float32)
        u = F[:, y + int(h * 0.2):y + int(h * 0.5), x0:x1].astype(np.float32)  # eyes/brow: head motion only
        mouth[1:] = np.clip(np.abs(np.diff(m, axis=0)).mean((1, 2)) - np.abs(np.diff(u, axis=0)).mean((1, 2)), 0, None)
        talk = mouth[voiced].mean() if voiced.any() else 0
        quiet = mouth[~voiced].mean() if (~voiced).sum() > 5 else 0
        # windows of 1.2 s with voice but no lip motion
        win = int(1.2 * FPS_S)
        dead = [i for i in range(0, n - win, win // 2)
                if voiced[i:i + win].mean() > 0.8 and mouth[i:i + win].mean() < 0.35 * max(talk, 1e-3)]
        if dead:
            issues.append('lips still while speaking at ' + ', '.join(f'{i / FPS_S:.1f}s' for i in dead[:5]))
        lip_ratio = talk / max(quiet, 1e-3) if quiet > 0 else None
    worst = max(range(1, n), key=lambda i: d[i - 1]) if n > 1 else 0
    if ref is None:
        lip_ratio = None
    return {
        'lip_ratio': round(float(lip_ratio), 2) if lip_ratio else None,
        'frames': n, 'seconds': round(n / FPS_S, 2), 'face_found': round(sum(found) / max(n, 1), 3),
        'face': [round(float(v), 1) for v in ref] if ref is not None else None,
        'issues': issues, 'worst_frame': worst,
        'first': F[0], 'last': F[-1], 'all': F,
    }


def main():
    D = Path(sys.argv[1])
    clips = sorted(D.glob('scene-*.mp4'))
    res = {c.stem: check(c) for c in clips}
    faces = np.array([r['face'] for r in res.values() if r['face']])
    ref = np.median(faces, axis=0) if len(faces) else None
    names = list(res)
    ratios = [r['lip_ratio'] for r in res.values() if r['lip_ratio']]
    lip_ref = float(np.median(ratios)) if ratios else None
    for i, k in enumerate(names):
        r = res[k]
        # lips are judged against the other scenes of the same avatar: an outlier is a lip-sync fault
        if lip_ref and r['lip_ratio'] and r['lip_ratio'] < 0.7 * lip_ref:
            r['issues'].append(f"lips follow the voice much less than in the other scenes ({r['lip_ratio']} vs {lip_ref:.2f})")
        if ref is not None and r['face']:
            dx = abs(r['face'][0] + r['face'][2] / 2 - (ref[0] + ref[2] / 2)) / ref[2]
            ds = abs(r['face'][2] / ref[2] - 1)
            if dx > 0.15 or ds > 0.12:
                r['issues'].append(f'face placed differently from the other scenes (shift {dx:.0%}, size {ds:.0%})')
        if i + 1 < len(names):
            nxt = res[names[i + 1]]
            r['seam_next'] = round(float(np.abs(r['last'].astype(np.float32) - nxt['first'].astype(np.float32)).mean()), 2)
    out = {}
    for k, r in res.items():
        if '--sheet' in sys.argv:
            F = r['all']
            idx = [0, len(F) // 2, len(F) - 1, r['worst_frame']]
            tiles = [cv2.cvtColor(F[j], cv2.COLOR_GRAY2BGR) for j in idx]
            for t, j in zip(tiles, idx):
                cv2.putText(t, f'{j / FPS_S:.1f}s', (8, 24), 0, 0.7, (0, 255, 255), 2)
            cv2.imwrite(str(D / f'qa-{k[6:]}.jpg'), np.hstack(tiles))
        out[k] = {kk: vv for kk, vv in r.items() if kk not in ('first', 'last', 'all')}
        hard = [x for x in r['issues'] if not x.startswith('lips')]
        out[k]['status'] = 'FAIL' if hard else ('LOOK' if r['issues'] else 'ok')
    (D / 'qa.json').write_text(json.dumps(out, indent=1))
    bad = 0
    for k, r in out.items():
        seam = f"  seam→next {r['seam_next']}" if 'seam_next' in r else ''
        print(f"{k}  {r['status']:4}  {r['seconds']:5.1f}s  face {r['face_found']:.0%}  lips {r['lip_ratio']}{seam}  {'; '.join(r['issues'])}")
        bad += r['status'] == 'FAIL'
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
