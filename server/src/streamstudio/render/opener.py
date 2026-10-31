"""Frame-exact render of the reusable opener ("the world of AI").

Layers per frame: studio plate → Dan (cut-out) → desk layer → table objects → titles, then a slow camera
push-in. Dan speaks only where the real HeyGen clip has his voice (0–9.4 s). While the tools arrive he
listens: a closed-mouth stretch of the same clip (frames 234–243) played back and forth, with a natural
blink (243–247) every few seconds. Sound: his voice + a synthesized ambient bed and per-event effects.

Usage: python opener.py OUT.mp4 [--fps 25] [--seconds N (debug: stop early)] [--frames-dir DIR]
"""

from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import tempfile
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = Path(__file__).resolve().parents[4]
A = REPO / "assets"
W, H = 1920, 1080
FONT_DIR = Path("/usr/share/fonts/opentype/inter")

# ---------------------------------------------------------------- timeline (seconds)
SPEECH_END = 9.4
TOOLS = [  # id, title, line
    ("claude-code", "Claude Code", "thinks, plans and reviews my code"),
    ("codex", "Codex", "my pair programmer in the terminal"),
    ("cluster", "Grok + GrokBot", "live markets · my paper-trading agent"),
    ("hermes", "Hermes", "runs my fleet, talks to every agent"),
    ("kimi", "Kimi", "long documents and research"),
    ("glm", "GLM", "fast, cheap, local when I need it"),
]
SLOTS = [0.15, 0.29, 0.43, 0.57, 0.71, 0.85]
T0 = 9.8          # first arrival
STEP = 4.2        # seconds per tool
ARRIVE_RATE = 2.2
LEAVE_RATE = 1.6
HOLD = 3.8        # at centre after arrival start, then glide
GLIDE = 0.9
CLAW_T = T0 + STEP * len(TOOLS) + 0.4
CLAW_LEAVE = CLAW_T + 4.6
FINALE = CLAW_LEAVE + 8 / LEAVE_RATE + 0.2
END = FINALE + 5.6
HERO = (0.5, 0.88, 0.2)   # x, disc y, disc width (fraction of frame width)
SLOT_Y, SLOT_W = 0.86, 0.11

# Dan seat (matches avatar/cutout.py)
SEAT_SCALE, HANDS_Y, SEAT_X, HANDS_IN_CLIP = 0.66, 0.68, 0.47, 0.85


def ease(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def ease_io(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


# ---------------------------------------------------------------- assets
class Clip:
    """Decoded RGBA frames of an object's alpha WebM, loaded on demand."""

    def __init__(self, webm: Path, cache: Path):
        self.dir = cache
        if not any(cache.glob("f*.png")):
            cache.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", str(webm), "-pix_fmt", "rgba",
                            f"{cache}/f%05d.png"], check=True)
        self.n = len(list(cache.glob("f*.png")))

    @lru_cache(maxsize=64)
    def frame(self, i: int) -> Image.Image:
        i = min(self.n - 1, max(0, i))
        return Image.open(self.dir / f"f{i + 1:05d}.png").convert("RGBA")


@lru_cache(maxsize=48)
def dan_frame(i: int) -> Image.Image:
    im = Image.open(A / "avatar/cutout/cache/dan-landscape-test" / f"f{i + 1:05d}.png").convert("RGBA")
    th = int(H * SEAT_SCALE)
    return im.resize((int(im.width * th / im.height), th), Image.BILINEAR)


def dan_index(t: float, fps: int) -> int:
    if t < SPEECH_END:
        return int(t * fps)
    # listening loop: 234→243→234 (half speed), with a blink 243→247→243 every ~5.2 s
    u = t - SPEECH_END
    cyc = 5.2
    k = u % cyc
    if 4.6 <= k < 4.6 + 0.4:
        b = (k - 4.6) / 0.4
        return 243 + int(round(4 * (1 - abs(2 * b - 1))))
    loop = [*range(234, 244), *range(243, 233, -1)]
    return loop[int(u * fps / 2) % len(loop)]


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / name), size)


F_TITLE = font("InterDisplay-SemiBold.otf", 50)
F_LINE = font("Inter-Regular.otf", 26)
F_LABEL = font("Inter-Medium.otf", 17)
F_FINAL = font("InterDisplay-SemiBold.otf", 72)


def title_layer(title: str, line: str, alpha: float, label: str | None = None) -> Image.Image | None:
    if alpha <= 0.01:
        return None
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    a = int(255 * alpha)
    y = int(H * 0.905)
    if label:
        d.text((W // 2, y - 64), label.upper(), font=F_LABEL, fill=(243, 194, 122, int(a * 0.9)), anchor="mm")
    d.text((W // 2, y - 22), title, font=F_TITLE, fill=(255, 255, 255, a), anchor="mm")
    d.text((W // 2, y + 24), line, font=F_LINE, fill=(214, 220, 230, int(a * 0.85)), anchor="mm")
    shadow = lay.filter(ImageFilter.GaussianBlur(10))
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh.paste((0, 0, 0, 255), mask=shadow.split()[3].point(lambda p: int(p * 0.7)))
    sh.alpha_composite(lay)
    return sh


# ---------------------------------------------------------------- objects
def place(canvas: Image.Image, clip: Clip, idx: int, x: float, y: float, disc_w: float, gain: float = 1.0,
          lift: float = 0.0) -> None:
    fr = clip.frame(idx)
    w = int(disc_w * W * fr.width / 520)
    h = int(fr.height * w / fr.width)
    if w < 4:
        return
    im = fr.resize((w, h), Image.BILINEAR)
    if gain != 1.0:
        r, g, b, al = im.split()
        r, g, b = (ch.point(lambda p, k=gain: min(255, int(p * k))) for ch in (r, g, b))
        im = Image.merge("RGBA", (r, g, b, al))
    canvas.alpha_composite(im, (int(x * W - w / 2), int(y * H - 0.75 * h - lift * H)))


def tool_state(i: int, t: float):
    """→ (clip_index, x, y, disc_w, visible) for tool i at time t."""
    t0 = T0 + i * STEP
    if t < t0:
        return None
    ci = int((t - t0) * 30 * ARRIVE_RATE)  # clips are 30 fps
    g = ease_io((t - t0 - HOLD) / GLIDE)
    hx, hy, hw = HERO
    x = hx + (SLOTS[i] - hx) * g
    y = hy + (SLOT_Y - hy) * g
    w = hw + (SLOT_W - hw) * g
    return ci, x, y, w


def render_frame(t: float, fps: int, clips: dict[str, Clip], plate: Image.Image, desk: Image.Image) -> Image.Image:
    c = plate.copy()
    # Dan
    df = dan_frame(dan_index(t, fps))
    bottom = HANDS_Y + (1 - HANDS_IN_CLIP) * SEAT_SCALE
    c.alpha_composite(df, (int(SEAT_X * W - df.width / 2), int(bottom * H - df.height)))
    c.alpha_composite(desk)
    # tools
    for i, (tid, _, _) in enumerate(TOOLS):
        st = tool_state(i, t)
        if not st:
            continue
        ci, x, y, w = st
        gain, lift = 1.0, 0.0
        if t >= FINALE:  # sequential pulse
            k = (t - FINALE - 0.28 * i) / 0.7
            if 0 <= k <= 1:
                p = math.sin(k * math.pi)
                gain, lift = 1 + 0.75 * p, 0.012 * p
        bob = 0.003 * math.sin((t + i * 0.7) * 1.4) if ci >= 240 else 0.0
        place(c, clips[tid], min(ci, 239), x, y + bob, w, gain, lift)
    # OpenClaw
    if CLAW_T <= t < CLAW_LEAVE + 8 / LEAVE_RATE:
        if t < CLAW_LEAVE:
            ci = int((t - CLAW_T) * 30 * ARRIVE_RATE)
            place(c, clips["openclaw-arrive"], min(ci, 239), HERO[0], HERO[1] + (0.003 * math.sin(t * 1.4) if ci >= 240 else 0), HERO[2])
        else:
            ci = int((t - CLAW_LEAVE) * 30 * LEAVE_RATE)
            place(c, clips["openclaw-leave"], min(ci, 239), HERO[0], HERO[1], HERO[2])
    # titles
    for i, (tid, title, line) in enumerate(TOOLS):
        t0 = T0 + i * STEP
        a = ease((t - t0 - 1.3) / 0.35) * (1 - ease((t - t0 - HOLD - 0.1) / 0.35))
        lay = title_layer(title, line, a, f"{i + 1:02d} / the team")
        if lay:
            c.alpha_composite(lay)
    a1 = ease((t - CLAW_T - 1.3) / 0.35) * (1 - ease((t - CLAW_LEAVE + 0.2) / 0.3))
    lay = title_layer("OpenClaw", "the most exciting thing I saw this year", a1, "and one more")
    if lay:
        c.alpha_composite(lay)
    a2 = ease((t - CLAW_LEAVE - 0.2) / 0.35) * (1 - ease((t - CLAW_LEAVE - 3.4) / 0.4))
    lay = title_layer("…and I gave it up.", "that's how fast AI moves", a2, "openclaw")
    if lay:
        c.alpha_composite(lay)
    af = ease((t - FINALE - 1.6) / 0.5)
    if af > 0.01:
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        d.text((W // 2, int(H * 0.935)), "Six minds. One table.", font=F_FINAL, fill=(255, 255, 255, int(255 * af)), anchor="mm")
        sh = lay.filter(ImageFilter.GaussianBlur(12))
        base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        base.paste((0, 0, 0, 255), mask=sh.split()[3].point(lambda p: int(p * 0.75)))
        base.alpha_composite(lay)
        c.alpha_composite(base)
    # camera: slow push-in after the speech, toward the table
    s = 1 + 0.045 * ease((t - SPEECH_END) / (FINALE - SPEECH_END))
    out = c.convert("RGB")
    if s > 1.0005:
        cx, cy = W * 0.5, H * 0.62
        cw, ch = W / s, H / s
        out = out.resize((W, H), Image.BILINEAR, box=(cx - cw * 0.5, cy - ch * 0.62, cx + cw * 0.5, cy + ch * 0.38))
    # fades
    fade = ease(t / 0.6) * (1 - ease((t - (END - 1.0)) / 1.0))
    if fade < 0.999:
        out = Image.eval(out, lambda p, f=fade: int(p * f))
    return out


# ---------------------------------------------------------------- sound
SR = 48000


def synth_audio(path: Path) -> None:
    n = int(END * SR)
    t = np.arange(n) / SR
    mix = np.zeros(n, np.float32)
    rng = np.random.default_rng(7)

    def env(start, attack, hold, release):
        xs = [start, start + attack, start + attack + hold, start + attack + hold + release]
        return np.interp(t, xs, [0, 1, 1, 0], left=0, right=0).astype(np.float32)

    # ambient bed: slow chord pad (A minor 9 → F maj7 → C maj → G), soft detuned sines + sub
    chords = [[110, 164.81, 220, 261.63, 329.63, 493.88], [87.31, 174.61, 220, 261.63, 329.63, 440],
              [65.41, 130.81, 196, 261.63, 329.63, 392], [98, 146.83, 196, 246.94, 293.66, 392]]
    seg = 8.0
    pad = np.zeros(n, np.float32)
    for k in range(int(END // seg) + 1):
        ch = chords[k % 4]
        e = env(k * seg - 1.0, 2.5, seg - 1.0, 2.5)
        for j, f in enumerate(ch):
            for det in (-0.12, 0.12):
                pad += e * (0.05 if j else 0.07) * np.sin(2 * np.pi * (f * (1 + det / 100)) * t + j)
    swell = 0.55 + 0.45 * np.clip((t - SPEECH_END) / 4, 0, 1)      # rises after the voice
    swell *= 1 - np.clip((t - (END - 2.0)) / 2.0, 0, 1)
    swell *= np.clip(t / 1.2, 0, 1)
    mix += pad * swell * 0.55

    def chime(at, base, gain=0.18, dur=2.4):
        i0 = int(at * SR)
        m = int(dur * SR)
        if i0 >= n:
            return
        m = min(m, n - i0)
        tt = np.arange(m) / SR
        sig = sum(np.sin(2 * np.pi * base * r * tt) * a for r, a in ((1, 1), (2.01, 0.45), (3.02, 0.22), (4.2, 0.1)))
        mix[i0:i0 + m] += (gain * sig * np.exp(-tt * 2.2)).astype(np.float32)

    def shimmer(at, dur, gain=0.11, up=True):
        i0 = int(at * SR)
        m = min(int(dur * SR), n - i0)
        if m <= 0:
            return
        noise = rng.standard_normal(m).astype(np.float32)
        tt = np.arange(m) / SR
        # resonant sweep: sum of narrow sines following a rising pitch, modulated by noise
        f0, f1 = (900, 4200) if up else (3500, 500)
        f = f0 + (f1 - f0) * (tt / dur) ** 1.5
        ph = 2 * np.pi * np.cumsum(f) / SR
        sig = np.sin(ph) * 0.4 + np.sin(ph * 1.5) * 0.25
        sig *= 0.5 + 0.5 * np.convolve(np.abs(noise), np.ones(200) / 200, mode="same")
        e = np.sin(np.pi * np.clip(tt / dur, 0, 1)) ** 2
        mix[i0:i0 + m] += (gain * sig * e).astype(np.float32)

    def whoosh(at, dur=0.9, gain=0.08):
        i0 = int(at * SR)
        m = min(int(dur * SR), n - i0)
        if m <= 0:
            return
        noise = rng.standard_normal(m).astype(np.float32)
        k = np.ones(60) / 60
        lp = np.convolve(noise, k, mode="same")
        tt = np.arange(m) / SR
        e = np.sin(np.pi * tt / dur) ** 2
        mix[i0:i0 + m] += (gain * lp * e * 3).astype(np.float32)

    notes = [523.25, 587.33, 659.25, 783.99, 880, 987.77]
    for i in range(len(TOOLS)):
        t0 = T0 + i * STEP
        shimmer(t0 + 0.3, 3.0)
        chime(t0 + 3.4, notes[i])
        whoosh(t0 + HOLD)
    shimmer(CLAW_T + 0.3, 3.0, gain=0.1)
    chime(CLAW_T + 3.4, 440, gain=0.16)
    # lobster dissolve: crackle + falling tone
    i0 = int(CLAW_LEAVE * SR)
    m = min(int(5 * SR), n - i0)
    tt = np.arange(m) / SR
    clicks = (rng.random(m) < 0.004 * np.exp(-tt / 2.2)).astype(np.float32) * rng.uniform(-1, 1, m)
    crack = np.convolve(clicks, np.exp(-np.arange(80) / 12), mode="same")
    mix[i0:i0 + m] += (0.22 * crack).astype(np.float32)
    shimmer(CLAW_LEAVE, 3.5, gain=0.08, up=False)
    # finale: ascending pulses + low swell
    for i in range(len(TOOLS)):
        chime(FINALE + 0.28 * i, notes[i] * 2, gain=0.1, dur=1.6)
    i0 = int((FINALE + 1.6) * SR)
    m = min(int(4 * SR), n - i0)
    tt = np.arange(m) / SR
    mix[i0:i0 + m] += (0.22 * np.sin(2 * np.pi * 55 * tt) * np.exp(-tt * 0.9) * np.clip(tt / 0.05, 0, 1)).astype(np.float32)

    # voice: Dan's real clip audio, 0 → SPEECH_END, ducking the bed
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(A / "avatar/dan-landscape-test.mp4"), "-ac", "1", "-ar",
                          str(SR), "-f", "s16le", "-"], capture_output=True, check=True).stdout
    v = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    vm = min(len(v), int((SPEECH_END + 0.05) * SR))
    vv = v[:vm].copy()
    vv[-int(0.04 * SR):] *= np.linspace(1, 0, int(0.04 * SR))
    mix[:vm] += vv * 1.0

    peak = float(np.abs(mix).max()) or 1.0
    mix = (mix / peak * 0.89).astype(np.float32)
    stereo = np.stack([mix, mix], axis=1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((stereo * 32767).astype(np.int16).tobytes())


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--fps", type=int, default=25)
    ap.add_argument("--seconds", type=float)
    ap.add_argument("--stills", type=str, help="comma-separated times: write PNG stills instead of a video")
    a = ap.parse_args()
    cache = Path(tempfile.gettempdir()) / "opener-cache"
    clips = {tid: Clip(A / f"objects/{tid}/arrive.webm", cache / tid) for tid, _, _ in TOOLS}
    clips["openclaw-arrive"] = Clip(A / "objects/openclaw/arrive.webm", cache / "openclaw-arrive")
    clips["openclaw-leave"] = Clip(A / "objects/openclaw/leave.webm", cache / "openclaw-leave")
    plate = Image.open(A / "studio/plate-landscape-final.png").convert("RGBA").resize((W, H), Image.LANCZOS)
    desk = Image.open(A / "studio/plate-landscape-final.desk.png").convert("RGBA").resize((W, H), Image.LANCZOS)

    if a.stills:
        a.out.mkdir(parents=True, exist_ok=True)
        for s in a.stills.split(","):
            render_frame(float(s), a.fps, clips, plate, desk).save(a.out / f"t{float(s):05.1f}.jpg", quality=90)
        print("stills", a.out)
        return

    end = min(END, a.seconds or END)
    tmp = Path(tempfile.mkdtemp(prefix="opener_"))
    try:
        wav = tmp / "mix.wav"
        synth_audio(wav)
        vid = tmp / "video.mp4"
        p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                              "-r", str(a.fps), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                              "-pix_fmt", "yuv420p", str(vid)], stdin=subprocess.PIPE)
        total = int(end * a.fps)
        for f in range(total):
            p.stdin.write(render_frame(f / a.fps, a.fps, clips, plate, desk).tobytes())
            if f % 100 == 0:
                print(f"frame {f}/{total}", flush=True)
        p.stdin.close()
        p.wait()
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(vid), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "256k",
                        "-ar", "48000", "-shortest", "-movflags", "+faststart", str(a.out)], check=True)
        print(a.out, f"{end:.1f}s")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
