"""Swap re-rendered scenes into a finished main video (frame-exact), keeping everything else.

    python splice.py WORKDIR MAIN.mp4 OUT.mp4   (uses WORKDIR/patches/scene-NN.mp4 + cuts.json)
"""
import json
import subprocess
import sys
from pathlib import Path

W, MAIN, OUT = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
FPS, WW, HH = 25, 1920, 1080
cuts = json.load(open(W / 'cuts.json'))
patches = {int(p.stem.split('-')[1]): p for p in sorted((W / 'patches').glob('scene-*.mp4'))}
starts = {round(cuts[s - 1] * FPS): (s, round(cuts[s] * FPS)) for s in patches}
rd = lambda src: subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(src), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                                  stdout=subprocess.PIPE)
main = rd(MAIN)
enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{WW}x{HH}', '-r', str(FPS),
                        '-i', '-', '-i', str(MAIN), '-map', '0:v', '-map', '1:a?', '-c:v', 'libx264', '-preset', 'medium',
                        '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', OUT],
                       stdin=subprocess.PIPE)
size, f, patch, end = WW * HH * 3, 0, None, -1
while True:
    buf = main.stdout.read(size)
    if len(buf) < size:
        break
    if f in starts:
        s, end = starts[f]
        patch = rd(patches[s])
    if patch and f < end:
        pb = patch.stdout.read(size)
        buf = pb if len(pb) == size else buf
    elif patch:
        patch.kill(); patch = None
    enc.stdin.write(buf)
    f += 1
enc.stdin.close(); enc.wait()
print('spliced', sorted(patches), 'into', OUT)
