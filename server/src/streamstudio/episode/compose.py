"""`scene_compose`: one scene's clip and cut-out become `scenes/<scene>.mp4` at 25 fps.

The compositing of `tools/compose/render.py` as functions with `Settings` injected: the studio
plate, the presenter cut-out seated at the desk, the table overlays from the scene's plan (title,
lowers, chips, end card), zoom paths, glitch moments. Stage 1 composes avatar scenes on the plate;
a card scene whose card video is not rendered yet (cards arrive in Stage 3) is composed the same
way with the site as its lower. The lip-sync guard runs for every scene before compositing.

Heavy libraries (NumPy, OpenCV, Pillow, `render.lipsync`) are imported inside the functions, never
at module level (package rule, `tests/test_episode_imports.py`).
"""

from __future__ import annotations

import json
import math
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from ..core.config import Settings
from . import FPS
from .contract import Plan, Scene

W, H = 1920, 1080
HANDS_IN_CLIP = 0.85
TABLE_BOTTOM = 1004  # where cards stand on the desk (just in front of Dan's hands)
WHITE, TEAL, MUTED = (242, 244, 250), (45, 226, 196), (170, 176, 196)
FONT_FILES = {"Bold": "inter-latin-700-normal.woff2", "SemiBold": "inter-latin-600-normal.woff2",
              "Medium": "inter-latin-500-normal.woff2"}  # fmt: skip


def ease(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def probe_duration(ffprobe_bin: str, path: Path) -> float:
    out = subprocess.run(
        [ffprobe_bin, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
         str(path)],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return float(out.stdout.strip() or 0)


def guard(scene: Scene, clip_url: str, degraded: bool) -> str:
    """The lip-sync guard: the cue the compositor may draw. The voice is always the clip's own,
    so the cue comes back unchanged; it runs so the shared guard fixtures exercise this path."""
    from ..render import lipsync

    cue = "pip" if degraded else ("content" if scene.kind == "card" else "avatar")
    return lipsync.guard_cue(cue, clip_url, "clip")


class Compositor:
    """Plate, desk, fonts and caches, built once per process. Call `frame(...)` per frame."""

    def __init__(self, s: Settings) -> None:
        import cv2
        import numpy as np
        from PIL import Image

        self.s = s
        self.np, self.cv2 = np, cv2
        studio = s.assets_dir / "studio"
        self.plate = np.asarray(
            self._cover(Image.open(studio / "plate-landscape-final.png").convert("RGB"))
        ).astype(np.float32)
        desk = np.asarray(
            self._cover(Image.open(studio / "plate-landscape-final.desk.png").convert("RGBA"))
        ).astype(np.float32)
        self.desk, self.desk_a = desk, desk[..., 3:4] / 255.0
        seat = json.loads((studio / "plate-landscape-final.json").read_text())["seat"]
        self.scale, self.hands_y, self.sx = seat["scale"], seat["hands_y"], seat["x"]
        self.blurred = (
            cv2.GaussianBlur(self.plate, (0, 0), 18) * 0.38
            + np.array([6, 6, 12], np.float32) * 0.62
        )
        self._fonts: dict[tuple[int, str], Any] = {}
        self._cards: dict[str, Any] = {}

    @staticmethod
    def _cover(img):
        from PIL import Image

        k = max(W / img.width, H / img.height)
        img = img.resize((round(img.width * k), round(img.height * k)), Image.LANCZOS)
        x, y = (img.width - W) // 2, (img.height - H) // 2
        return img.crop((x, y, x + W, y + H))

    def font(self, size: int, weight: str = "SemiBold"):
        from PIL import ImageFont

        key = (size, weight)
        if key not in self._fonts:
            path = self.s.assets_dir / "brand" / "fonts" / FONT_FILES[weight]
            self._fonts[key] = ImageFont.truetype(str(path), size)
        return self._fonts[key]

    # ------------------------------------------------------------ layers

    def studio(self, frame, alpha):
        """Dan seated in the plate, desk in front. `frame` RGB float, `alpha` 0..1 (H, W, 1)."""
        cv2 = self.cv2
        out = self.plate.copy()
        if alpha is not None:
            ph = round(H * self.scale)
            pw = round(W * ph / H)
            fg = cv2.resize(frame, (pw, ph), interpolation=cv2.INTER_AREA)
            ma = cv2.resize(alpha, (pw, ph), interpolation=cv2.INTER_AREA)[..., None]
            bottom = (self.hands_y + (1 - HANDS_IN_CLIP) * self.scale) * H
            x0, y0 = round(W * self.sx - pw / 2), round(bottom - ph)
            xs, ys = max(0, x0), max(0, y0)
            xe, ye = min(W, x0 + pw), min(H, y0 + ph)
            sub_fg = fg[ys - y0 : ye - y0, xs - x0 : xe - x0]
            sub_m = ma[ys - y0 : ye - y0, xs - x0 : xe - x0]
            out[ys:ye, xs:xe] = out[ys:ye, xs:xe] * (1 - sub_m) + sub_fg * sub_m
        return out * (1 - self.desk_a) + self.desk[..., :3] * self.desk_a

    def zoom(self, img, cx: float, cy: float, z: float):
        if z <= 1.001:
            return img
        np, cv2 = self.np, self.cv2
        w, h = W / z, H / z
        x0 = min(max(cx * W - w / 2, 0), W - w)
        y0 = min(max(cy * H - h / 2, 0), H - h)
        m = np.array([[z, 0, -x0 * z], [0, z, -y0 * z]], np.float32)
        return cv2.warpAffine(img, m, (W, H), flags=cv2.INTER_LINEAR)

    def table_card(self, key: str, lines, w: int, h: int):
        """A glass mini card with a neon rim and its reflection. Cached per key."""
        if key in self._cards:
            return self._cards[key]
        np, cv2 = self.np, self.cv2
        from PIL import Image, ImageDraw

        pad = 40
        w2, h2 = w + pad * 2, h + pad * 2
        im = Image.new("RGBA", (w2, h2), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((pad, pad, pad + w, pad + h), 18, fill=(8, 10, 18, 205))
        rim = Image.new("L", (w2, h2), 0)
        ImageDraw.Draw(rim).rounded_rectangle(
            (pad, pad, pad + w, pad + h), 18, outline=255, width=3
        )
        rim_a = np.asarray(rim).astype(np.float32) / 255.0
        total = sum(sz for _, sz, _, _ in lines) + 14 * (len(lines) - 1)
        y = pad + (h - total) / 2 - 4
        for text, sz, wt, rgb in lines:
            f = self.font(sz, wt)
            tw = d.textlength(text, font=f)
            d.text((pad + (w - tw) / 2, y), text, font=f, fill=(*rgb, 255))
            y += sz + 14
        base = np.asarray(im).astype(np.float32)
        grad = np.linspace(0, 1, w2, dtype=np.float32)[None, :, None]
        col = (
            np.array([45, 226, 196], np.float32) * (1 - grad)
            + np.array([140, 100, 255], np.float32) * grad
        )
        glow = np.clip(cv2.GaussianBlur(rim_a, (0, 0), 10) * 2.4, 0, 1)[..., None]
        rgb = base[..., :3] * (base[..., 3:4] / 255.0)
        a = base[..., 3:4] / 255.0
        rgb = rgb * (1 - glow * (1 - a)) + col * glow * (1 - a)
        a = np.clip(a + glow * 0.85, 0, 1)
        rgb = rgb * (1 - rim_a[..., None]) + col * 1.1 * rim_a[..., None]
        a = np.maximum(a, rim_a[..., None])
        fade = np.linspace(0.32, 0, h2, dtype=np.float32)[:, None, None]
        out_rgb = np.concatenate([rgb, rgb[::-1]], 0)
        out_a = np.concatenate([a, a[::-1] * fade], 0)
        self._cards[key] = (out_rgb, out_a, pad)
        return self._cards[key]

    def place_table_card(self, out, key, lines, w, h, cx, alpha, rise=0.0):
        if alpha <= 0.01:
            return out
        np = self.np
        rgb, a, pad = self.table_card(key, lines, w, h)
        h2 = h + pad * 2
        lift = int((1 - rise) * 46)
        x0 = int(cx - (w + pad * 2) / 2)
        y0 = TABLE_BOTTOM - h - pad + lift
        hh, ww = rgb.shape[:2]
        vis = np.ones((hh, 1, 1), np.float32)
        cut = h2 - pad - lift
        if lift > 0:
            vis[max(cut, 0) : h2] = 0
        ys, xs = max(0, y0), max(0, x0)
        ye, xe = min(H, y0 + hh), min(W, x0 + ww)
        if ye <= ys or xe <= xs:
            return out
        sa = a[ys - y0 : ye - y0, xs - x0 : xe - x0] * vis[ys - y0 : ye - y0] * alpha
        sr = rgb[ys - y0 : ye - y0, xs - x0 : xe - x0]
        out[ys:ye, xs:xe] = out[ys:ye, xs:xe] * (1 - sa) + sr * sa
        return out

    def table_glow(self, out, cx, w, alpha):
        if alpha <= 0.01:
            return out
        np, cv2 = self.np, self.cv2
        g = np.zeros((H, W), np.float32)
        cv2.ellipse(g, (int(cx), TABLE_BOTTOM), (int(w * 0.62), 26), 0, 0, 360, 1.0, -1)
        g = cv2.GaussianBlur(g, (0, 0), 22)[..., None] * 0.5 * alpha
        return out + np.array([60, 200, 190], np.float32) * g

    def glitch(self, img, u: float, f: int):
        np = self.np
        k = math.sin(math.pi * min(max(u, 0), 1))
        rng = np.random.default_rng(f)
        sh = int(6 + 22 * k)
        out = img.copy()
        out[..., 0] = np.roll(img[..., 0], sh, axis=1)
        out[..., 2] = np.roll(img[..., 2], -sh, axis=1)
        for _ in range(int(3 + 7 * k)):
            y = int(rng.integers(0, H - 40))
            h = int(rng.integers(8, 60))
            out[y : y + h] = np.roll(out[y : y + h], int(rng.integers(-80, 80) * k), axis=1)
        if rng.random() < 0.35 * k:
            out = out * 0.85 + np.array([20, 40, 60], np.float32) * 0.15
        return out

    def pip(self, frame, alpha):
        """The degraded layout: the blurred studio with the presenter in the small circle."""
        from PIL import Image

        from ..render import lipsync

        np = self.np
        base = Image.fromarray(np.clip(self.blurred, 0, 255).astype(np.uint8))
        face = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
        out = lipsync.composite_pip(base, face, "circle").convert("RGB")
        return np.asarray(out).astype(np.float32)

    # ------------------------------------------------------------ one frame

    def frame(
        self, scene: Scene, plan: Plan, frame, alpha, tl: float, dur: float, f: int, cue: str
    ):
        if cue == "pip":
            return self.pip(frame, alpha)
        p = plan
        out = self.studio(frame, alpha)
        if p.frame and not p.zoom and not p.zoom_path:
            out = self.zoom(out, *p.frame)
        if p.title:
            t1, t2 = (p.title + [""])[:2]
            al = ease(tl / 0.5) * (1 - ease((tl - 2.6) / 0.6))
            out = self.table_glow(out, W / 2, 820, al)
            w = max(820, int(self.font(64, "Bold").getlength(t1)) + 140)
            lines = [(t1, 64, "Bold", WHITE)] + ([(t2, 30, "Medium", TEAL)] if t2 else [])
            out = self.place_table_card(
                out, "title:" + t1, lines, w, 170, W / 2, al, ease(tl / 0.6)
            )
        lowers = list(p.lowers) or ([(0.0, None, p.lower[0], p.lower[1])] if p.lower else [])
        zoomed = bool(p.zoom or p.zoom_path)
        for fa, fb, name, sub in lowers:
            t_in = 0.3 + fa * dur
            t_out = fb * dur - 0.5 if fb is not None else min(dur - 0.6, 7.0 + t_in)
            al = ease((tl - t_in) / 0.4) * (1 - ease((tl - t_out) / 0.5))
            lines = [(name, 44, "Bold", WHITE)] + ([(sub, 26, "Medium", TEAL)] if sub else [])
            w = max(460, int(self.font(44, "Bold").getlength(name)) + 120)
            cx = W * 0.47 if not zoomed else W * (p.card_x if p.card_x is not None else 0.30)
            out = self.table_glow(out, cx, w, al)
            out = self.place_table_card(
                out, "lower:" + name, lines, w, 150 if sub else 112, cx, al, ease((tl - t_in) / 0.5)
            )
        if p.chips:
            names = p.chips
            co = p.chips_out * dur if p.chips_out else dur - 0.8
            al_out = 1 - ease((tl - co) / 0.6)
            cw = [max(300, int(self.font(36, "Bold").getlength(n)) + 70) for n in names]
            gap = max(30, min(90, (W * 0.92 - sum(cw)) / max(len(names) - 1, 1)))
            span = sum(cw) + gap * (len(names) - 1)
            x = (W - span) / 2
            xs = []
            for wk in cw:
                xs.append(x + wk / 2)
                x += wk + gap
            times = p.chip_at or [k * 1.3 / max(dur, 1) for k in range(len(names))]
            for k, name in enumerate(names):
                t_in = times[k] * dur if k < len(times) else k * 1.3
                al = ease((tl - t_in) / 0.35) * al_out
                out = self.table_glow(out, xs[k], cw[k], al)
                out = self.place_table_card(
                    out,
                    "chip:" + name,
                    [(name, 36, "Bold", WHITE)],
                    cw[k],
                    96,
                    xs[k],
                    al,
                    ease((tl - t_in) / 0.45),
                )
        if p.endcard:
            e_in = p.end_at * dur if p.end_at is not None else dur - 6.5
            e_out = p.end_until * dur if p.end_until is not None else dur + 1
            if e_in < tl < e_out + 0.6:
                fades_out = p.end_until is not None and p.end_until < 0.999
                al = ease((tl - e_in) / 0.6) * (
                    (1 - ease((tl - (e_out - 0.5)) / 0.5)) if fades_out else 1
                )
                out = self.table_glow(out, W / 2, 1100, al)
                e = (list(p.endcard) + ["", ""])[:3]
                lines = (
                    [(e[0], 56, "Bold", WHITE)]
                    + ([(e[1], 36, "SemiBold", TEAL)] if e[1] else [])
                    + ([(e[2], 24, "Medium", MUTED)] if e[2] else [])
                )
                out = self.place_table_card(
                    out, "end:" + e[0], lines, 1100, 230, W / 2, al, ease((tl - e_in) / 0.7)
                )
        if p.zoom_path:
            ks = p.zoom_path
            fr = tl / dur
            k0 = max((k for k in ks if k[0] <= fr), key=lambda k: k[0], default=ks[0])
            k1 = min((k for k in ks if k[0] > fr), key=lambda k: k[0], default=k0)
            u = 0 if k1 is k0 else ease((fr - k0[0]) / (k1[0] - k0[0]))
            out = self.zoom(out, *(k0[j] + (k1[j] - k0[j]) * u for j in (1, 2, 3)))
        elif p.zoom:
            cx, cy, z = p.zoom
            out = self.zoom(out, cx, cy, 1 + (z - 1) * ease(tl / min(dur, 2.2)))
        for gf, gd in p.glitch:
            g0 = gf * dur
            if g0 <= tl < g0 + gd:
                out = self.glitch(out, (tl - g0) / gd, f)
        return out


def effective_plan(scene: Scene) -> Plan:
    """The plan to draw: the scene's own, with the defaults a plain scene gets (a card scene
    without its card shows the site as a lower; a question scene gets a question lower)."""
    plan = scene.plan or Plan()
    if scene.kind == "card" and scene.site and not plan.lowers and not plan.lower:
        host = urlsplit(scene.site).netloc or scene.site
        plan = plan.model_copy(update={"lower": (host, None)})
    elif scene.question and not plan.lowers and not plan.lower and not plan.title:
        first = scene.text.split(".")[0].strip()[:60] or scene.voice[:60]
        plan = plan.model_copy(update={"lower": (f"{scene.question} · {first}", None)})
    return plan


def compose_scene(
    s: Settings,
    scene: Scene,
    clip_mp4: Path,
    cutout_webm: Path,
    out_mp4: Path,
    *,
    card_mp4: Path | None = None,
    degraded: bool = False,
    progress: Callable[[float, str], None] | None = None,
    compositor: Compositor | None = None,
) -> dict[str, Any]:
    """Compose one scene to `out_mp4` (temp file plus rename). Returns frames and duration."""
    import numpy as np

    cue = guard(scene, f"/avatar/clips/{clip_mp4.name}", degraded)
    comp = compositor or Compositor(s)
    plan = effective_plan(scene)
    dur = probe_duration(s.ffprobe_bin, clip_mp4)
    n = max(1, round(dur * FPS))
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_mp4.with_name(out_mp4.stem + ".tmp.mp4")
    dec = subprocess.Popen(
        [s.ffmpeg_bin, "-v", "error", "-i", str(clip_mp4), "-vf", f"fps={FPS},scale={W}:{H}",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE,
    )  # fmt: skip
    cut = (
        subprocess.Popen(
            [
                s.ffmpeg_bin,
                "-v",
                "error",
                "-c:v",
                "libvpx-vp9",
                "-i",
                str(cutout_webm),
                "-vf",
                f"fps={FPS},scale={W}:{H}",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgba",
                "-",
            ],
            stdout=subprocess.PIPE,
        )  # fmt: skip
        if cutout_webm.exists()
        else None
    )
    enc = subprocess.Popen(
        [s.ffmpeg_bin, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-i", str(clip_mp4), "-map", "0:v", "-map", "1:a?",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-movflags", "+faststart", "-shortest", str(tmp)],
        stdin=subprocess.PIPE,
    )  # fmt: skip
    size_rgb, size_rgba = W * H * 3, W * H * 4
    frames = 0
    last_alpha = None
    try:
        for f in range(n):
            buf = dec.stdout.read(size_rgb)
            if len(buf) < size_rgb:
                break
            frame = np.frombuffer(buf, np.uint8).reshape(H, W, 3).astype(np.float32)
            alpha = None
            if cut is not None:
                abuf = cut.stdout.read(size_rgba)
                if len(abuf) == size_rgba:
                    rgba = np.frombuffer(abuf, np.uint8).reshape(H, W, 4)
                    alpha = rgba[..., 3:4].astype(np.float32) / 255.0
                    frame = rgba[..., :3].astype(np.float32)
                    last_alpha = alpha
                else:
                    alpha = last_alpha
            out = comp.frame(scene, plan, frame, alpha, f / FPS, dur, f, cue)
            enc.stdin.write(np.clip(out, 0, 255).astype(np.uint8).tobytes())
            frames += 1
            if progress and f % 25 == 0:
                progress(f / n, f"composing {scene.id}")
    finally:
        enc.stdin.close()
        enc.wait()
        dec.kill()
        dec.wait()
        if cut is not None:
            cut.kill()
            cut.wait()
    if frames == 0 or enc.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"compose of {scene.id} produced no frames")
    if plan.website_demo:
        from .website_demo import overlay

        try:
            if not card_mp4:
                raise ValueError("website demo capture missing")
            overlay(s, tmp, card_mp4, plan.website_demo, out_mp4)
        finally:
            tmp.unlink(missing_ok=True)
    else:
        tmp.replace(out_mp4)
    return {"frames": frames, "duration_s": round(frames / FPS, 3), "cue": cue}
