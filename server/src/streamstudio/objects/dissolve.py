#!/usr/bin/env python3
"""Particle dissolve for a table object (generalised from Dan's ChatGPT lobster outro project).

The object still (emblem floating over a lit disc, on black) breaks into particles in its own
colour, which drift up and fade; the disc dims out; the last second is black.
Reversed, it is the arrival.
Deterministic (fixed seed), local, no model calls. Object bounds, disc line and particle colour are
detected from the image instead of being hard-coded.

Usage: python dissolve.py STILL.png OUT.mp4 [--seed N] [--particles 16000] [--preview SHEET.jpg]
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter

ROOT = Path("/tmp/objects-dissolve")
FPS = 30
DURATION = 8.0
BLACK_START = 7.0
SEED = 7312026
PARTICLE_COUNT = 16000
SOURCE: Path = ROOT
OUTPUT: Path = ROOT


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def srgb_to_linear(a):
    a = a.astype(np.float32) / 255.0
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(a):
    a = np.clip(a, 0.0, 1.0)
    s = np.where(a <= 0.0031308, a * 12.92, 1.055 * np.maximum(a, 0.0031308) ** (1.0 / 2.4) - 0.055)
    return np.clip(s * 255.0 + 0.5, 0, 255).astype(np.uint8)


class Outro:
    def __init__(self):
        self.original = np.array(Image.open(SOURCE).convert("RGB"))
        self.h, self.w = self.original.shape[:2]
        if self.w % 2 or self.h % 2:
            # A black row/column makes H.264 4:2:0 valid without resampling.
            padded = np.zeros((self.h + self.h % 2, self.w + self.w % 2, 3), np.uint8)
            padded[: self.h, : self.w] = self.original
            self.original = padded
            self.h, self.w = padded.shape[:2]

        # Remove only imperceptible background noise; retain illuminated glass/wood.
        self.clean = self.original.copy()
        self.clean[self.clean.max(axis=2) <= 6] = 0
        self.base = srgb_to_linear(self.clean)

        # Detect the light disc (brightest warm row in the lower part) and the emblem above it.
        lum = self.clean.max(axis=2).astype(np.float32)
        r, g = self.clean[..., 0].astype(np.float32), self.clean[..., 1].astype(np.float32)
        hot = ((lum > 200) & (r >= g)).sum(axis=1)
        hot[: int(self.h * 0.35)] = 0
        disc_y = int(hot.argmax())
        rows = (lum > 18).sum(axis=1)
        # the stage starts at the gap between emblem and disc (or ~3% above the disc if they touch)
        stage_y = disc_y - int(self.h * 0.03)
        for y in range(
            disc_y - 6, disc_y - int(self.h * 0.12), -1
        ):  # only look just above the disc
            if rows[y] < 3:
                stage_y = y
                break
        self.stage_y = stage_y
        ys, xs = np.where(lum[:stage_y] > 18)
        self.x0, self.x1 = max(0, xs.min() - 6), min(self.w, xs.max() + 7)
        self.y0, self.y1 = max(0, ys.min() - 6), self.stage_y
        # particle colour = the emblem's own glow colour
        sel = lum[self.y0 : self.y1, self.x0 : self.x1] > 120
        rgb = self.clean[self.y0 : self.y1, self.x0 : self.x1][sel].astype(np.float32)
        c = rgb.mean(axis=0) if len(rgb) else np.array([80, 140, 255], np.float32)
        self.tint = (c / max(1.0, c.max())).astype(np.float32)
        self.obj = self.base[self.y0 : self.y1, self.x0 : self.x1].copy()
        self.oh, self.ow = self.obj.shape[:2]
        self.stage = self.base[self.stage_y :].copy()
        rgb_stage = self.clean[self.stage_y :].astype(np.float32)
        red, blue = rgb_stage[..., 0], rgb_stage[..., 2]
        self.blue_reflection = np.clip((blue - red) / (blue + red + 1.0) * 1.7, 0, 1)
        self.rng = np.random.default_rng(SEED)

        # Coherent micro-regions dissolve at different times. A modest top-to-bottom
        # bias makes the antennae and claw tips begin to release their particles first.
        coarse = self.rng.random((math.ceil(self.oh / 3), math.ceil(self.ow / 3)))
        grains = np.repeat(np.repeat(coarse, 3, axis=0), 3, axis=1)[: self.oh, : self.ow]
        grains = gaussian_filter(grains, 0.55).astype(np.float32)
        lo, hi = np.percentile(grains, [1.5, 98.5])
        grains = np.clip((grains - lo) / (hi - lo), 0, 1)
        # Histogram equalization distributes releases over the full dissolve interval.
        order = np.argsort(grains, axis=None)
        ranks = np.empty(grains.size, np.float32)
        ranks[order] = np.linspace(0, 1, grains.size, dtype=np.float32)
        grains = ranks.reshape(grains.shape)
        ynorm = np.clip(np.arange(self.oh, dtype=np.float32)[:, None] / max(1, self.oh), 0, 1)
        self.birth_map = (0.72 + 3.92 * (0.72 * grains + 0.28 * ynorm)).astype(np.float32)

        self.init_particles()

    def init_particles(self):
        signal = self.clean[self.y0 : self.y1, self.x0 : self.x1].max(axis=2)
        yy, xx = np.where(signal > 10)
        weight = 0.12 + (signal[yy, xx].astype(np.float64) / 255.0) ** 0.7
        weight /= weight.sum()
        pick = self.rng.choice(
            len(xx), size=PARTICLE_COUNT, replace=len(xx) < PARTICLE_COUNT, p=weight
        )
        px, py = xx[pick], yy[pick]
        self.px = px.astype(np.float32) + self.x0 + self.rng.uniform(-0.4, 0.4, PARTICLE_COUNT)
        self.py = py.astype(np.float32) + self.y0 + self.rng.uniform(-0.4, 0.4, PARTICLE_COUNT)
        self.birth = self.birth_map[py, px].astype(np.float32)
        self.life = self.rng.uniform(1.5, 2.55, PARTICLE_COUNT).astype(np.float32)
        self.vy = self.rng.uniform(30, 73, PARTICLE_COUNT).astype(np.float32)
        self.ay = self.rng.uniform(8, 21, PARTICLE_COUNT).astype(np.float32)
        self.vx = self.rng.normal(0, 9, PARTICLE_COUNT).astype(np.float32)
        self.sway = self.rng.uniform(3, 13, PARTICLE_COUNT).astype(np.float32)
        self.freq = self.rng.uniform(1.4, 2.8, PARTICLE_COUNT).astype(np.float32)
        self.phase = self.rng.uniform(0, 2 * np.pi, PARTICLE_COUNT).astype(np.float32)
        signal_sample = signal[py, px].astype(np.float32) / 255.0
        self.power = (0.09 + 0.38 * np.sqrt(signal_sample)) * self.rng.uniform(
            0.65, 1.35, PARTICLE_COUNT
        )
        jitter = self.rng.uniform(0.75, 1.15, (PARTICLE_COUNT, 3)).astype(np.float32)
        lin = srgb_to_linear((self.tint * 255).astype(np.uint8)[None, :])[0]
        self.color = np.clip(lin[None, :] / max(1e-3, lin.max()) * jitter, 0, 1).astype(np.float32)
        # A few particles are brighter, but all remain very small, blue and understated.
        self.power[self.rng.random(PARTICLE_COUNT) < 0.04] *= 1.75

        # All particle motion is upward, and this fixed processing area comfortably
        # contains every trajectory without changing the source/camera transform.
        self.fx0, self.fx1 = max(0, self.x0 - 160), min(self.w, self.x1 + 160)
        self.fy0, self.fy1 = max(0, self.y0 - 340), self.stage_y
        self.fw, self.fh = self.fx1 - self.fx0, self.fy1 - self.fy0

    def particles(self, t):
        age = t - self.birth
        valid = (age > 0) & (age < self.life)
        if not valid.any() or t >= BLACK_START:
            return None, 0
        idx = np.where(valid)[0]
        a = age[idx]
        ramp = 1 - np.exp(-a / 0.20)
        x = (
            self.px[idx]
            + self.vx[idx] * a
            + self.sway[idx]
            * (np.sin(self.freq[idx] * a + self.phase[idx]) - np.sin(self.phase[idx]))
            * ramp
        )
        y = self.py[idx] - self.vy[idx] * a * ramp - 0.5 * self.ay[idx] * a * a
        opacity = smoothstep(a / 0.13) * (1 - smoothstep(a / self.life[idx]))
        opacity *= 1 - smoothstep((t - 6.25) / 0.7)
        energy = self.power[idx] * opacity

        x = x - self.fx0
        y = y - self.fy0
        inside = (x >= 2) & (x < self.fw - 3) & (y >= 2) & (y < self.fh - 3)
        x, y, idx, energy = x[inside], y[inside], idx[inside], energy[inside]
        xi, yi = np.floor(x).astype(np.int32), np.floor(y).astype(np.int32)
        dx, dy = x - xi, y - yi
        field = np.zeros((self.fh, self.fw, 3), np.float32)
        colors = self.color[idx] * energy[:, None]
        for ox, oy, frac in (
            (0, 0, (1 - dx) * (1 - dy)),
            (1, 0, dx * (1 - dy)),
            (0, 1, (1 - dx) * dy),
            (1, 1, dx * dy),
        ):
            for c in range(3):
                np.add.at(field[..., c], (yi + oy, xi + ox), colors[:, c] * frac)

        # Small cores + restrained local bloom; no smoke or background fog.
        core = gaussian_filter(field, sigma=(0.40, 0.40, 0), truncate=2.5)
        glow = gaussian_filter(field, sigma=(1.35, 1.35, 0), truncate=3.0)
        halo = gaussian_filter(field, sigma=(3.4, 3.4, 0), truncate=3.0)
        return core * 1.8 + glow * 1.8 + halo * 0.55, len(idx)

    def frame(self, frame_index):
        t = frame_index / FPS
        if t >= BLACK_START:
            return np.zeros((self.h, self.w, 3), np.uint8)
        canvas = np.zeros_like(self.base)

        if t < 0.54:
            return self.clean.copy()

        # Each original region disappears precisely as particles are released there.
        remain = 1 - smoothstep((t - self.birth_map + 0.08) / 0.24)
        canvas[self.y0 : self.y1, self.x0 : self.x1] = self.obj * remain[..., None]
        live_energy = float((self.obj * remain[..., None]).sum() / max(self.obj.sum(), 1e-8))

        disc_gain = 1 - smoothstep((t - 2.35) / 3.75)
        reflected_emblem = min(1.0, live_energy + 0.12 * (1 - smoothstep((t - 3.9) / 1.8)))
        stage_gain = disc_gain * (1 - self.blue_reflection * (1 - reflected_emblem))
        canvas[self.stage_y :] = self.stage * stage_gain[..., None]

        light, _ = self.particles(t)
        if light is not None:
            canvas[self.fy0 : self.fy1, self.fx0 : self.fx1] += light
        # Everything has a controlled, smooth endpoint; no residual ambient pixels.
        canvas *= 1 - smoothstep((t - 6.65) / 0.35)
        return linear_to_srgb(canvas)

    def preview(self):
        checks = ROOT / "checks"
        checks.mkdir(exist_ok=True)
        times = [0, 1.0, 2.0, 2.8, 3.6, 4.5, 5.4, 6.2, 7.0]
        thumb_w = 558
        thumb_h = round(self.h * thumb_w / self.w)
        sheet = Image.new("RGB", (thumb_w * 3, (thumb_h + 25) * 3), (17, 19, 23))
        draw = ImageDraw.Draw(sheet)
        for k, t in enumerate(times):
            a = self.frame(round(t * FPS))
            image = Image.fromarray(a)
            image.save(checks / f"frame_{t:04.1f}.png")
            thumb = image.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            sx, sy = (k % 3) * thumb_w, (k // 3) * (thumb_h + 25)
            sheet.paste(thumb, (sx, sy))
            draw.text((sx + 10, sy + thumb_h + 5), f"{t:.1f} s", fill=(225, 230, 238))
        sheet.save(checks / "contact_sheet.jpg", quality=94)
        print(
            json.dumps(
                {
                    "preview": str(checks / "contact_sheet.jpg"),
                    "dimensions": [self.w, self.h],
                    "particles": PARTICLE_COUNT,
                }
            ),
            flush=True,
        )

    def render(self):
        if OUTPUT.exists():
            raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-n",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{self.w}x{self.h}",
            "-r",
            str(FPS),
            "-i",
            "pipe:0",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "16",
            "-pix_fmt",
            "yuv420p",
            "-force_key_frames",
            str(BLACK_START),
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-colorspace",
            "bt709",
            "-movflags",
            "+faststart",
            str(OUTPUT),
        ]
        log_path = ROOT / "checks" / "encode.log"
        with log_path.open("wb") as log:
            process = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log
            )
            try:
                for n in range(round(DURATION * FPS)):
                    process.stdin.write(self.frame(n).tobytes())
                    if n % 30 == 0:
                        print(f"Rendered {n}/{round(DURATION * FPS)} frames", flush=True)
            finally:
                process.stdin.close()
            result = process.wait()
        if result != 0:
            raise RuntimeError(f"FFmpeg failed; see {log_path}")
        metadata = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(OUTPUT)],
            check=True,
            capture_output=True,
            text=True,
        )
        (ROOT / "checks" / "ffprobe.json").write_text(metadata.stdout)
        print(
            json.dumps(
                {
                    "video": str(OUTPUT),
                    "bytes": OUTPUT.stat().st_size,
                    "duration_seconds": DURATION,
                    "fps": FPS,
                    "dimensions": [self.w, self.h],
                }
            ),
            flush=True,
        )


def main():
    global SOURCE, OUTPUT, SEED, PARTICLE_COUNT
    parser = argparse.ArgumentParser()
    parser.add_argument("still", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--particles", type=int, default=PARTICLE_COUNT)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()
    SOURCE, OUTPUT, SEED, PARTICLE_COUNT = args.still, args.out, args.seed, args.particles
    outro = Outro()
    if args.preview:
        global ROOT
        ROOT = args.preview.parent
        outro.preview()
    if OUTPUT.exists():
        OUTPUT.unlink()
    (ROOT / "checks").mkdir(parents=True, exist_ok=True)
    outro.render()


if __name__ == "__main__":
    main()
