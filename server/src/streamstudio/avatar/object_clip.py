"""Turn a generated object clip (on black) into transparent clips for the stage.

Per frame: optional hue shift, then the same matte as object_matte (solid body above the disc,
soft glow, only bright reflections below). Crop box and scale are fixed from the FIRST frame so
nothing jitters.
Writes VP9+alpha WebM: <out>/<name>.webm, plus <out>/<name>-reversed.webm when --reverse.

Usage: python object_clip.py SRC.mp4 OUT_DIR NAME [--hue-shift 108] [--reverse NAME2] [--disc 520]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from object_matte import disc_row  # type: ignore
from PIL import Image, ImageFilter
from scipy import ndimage


def hue(im: Image.Image, shift: int) -> Image.Image:
    if not shift:
        return im
    hsv = np.asarray(im.convert("HSV")).astype(np.int16)
    h, s = hsv[..., 0], hsv[..., 1]
    m = (h > 120) & (h < 200) & (s > 50)
    hsv[..., 0] = np.where(m, (h + shift) % 256, h)
    return Image.fromarray(hsv.clip(0, 255).astype(np.uint8), "HSV").convert("RGB")


def alpha_for(a: np.ndarray, y_disc: int, body_ref: np.ndarray | None) -> np.ndarray:
    lum = a.max(axis=2)
    yy = np.arange(lum.shape[0])[:, None]
    above = yy < y_disc - 4
    body = ndimage.binary_fill_holes(ndimage.binary_closing(lum > 28, iterations=3) & above)
    lab, n = ndimage.label(body)
    if n:
        sizes = ndimage.sum(body, lab, range(1, n + 1))
        body = np.isin(lab, 1 + np.where(sizes > 1500)[0])
    body = ndimage.binary_erosion(body, iterations=2)
    glow = np.clip((lum - 14) / 45, 0, 1)
    refl = np.clip((lum - 70) / 90, 0, 1)
    al = np.where(above, glow, refl)
    return np.where(body, 1.0, al)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("name")
    ap.add_argument("--hue-shift", type=int, default=0)
    ap.add_argument("--reverse")
    ap.add_argument("--disc", type=int, default=520)
    ap.add_argument("--fps", type=int, default=30)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="objclip_"))
    try:
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(a.src), f"{work}/s%05d.png"], check=True
        )
        frames = sorted(work.glob("s*.png"))
        first = np.asarray(hue(Image.open(frames[0]).convert("RGB"), a.hue_shift)).astype(
            np.float32
        )
        lum0 = first.max(axis=2)
        y_disc = disc_row(lum0, first[..., 0], first[..., 1])
        ys, xs = np.where(lum0 > 60)
        pad = 60
        box = (
            max(0, xs.min() - pad),
            max(0, ys.min() - 140),
            min(lum0.shape[1], xs.max() + pad),
            min(lum0.shape[0], ys.max() + pad),
        )
        ring = np.where(lum0[y_disc] > 150)[0]
        k = a.disc / max(1, ring.max() - ring.min())
        size = (round((box[2] - box[0]) * k) // 2 * 2, round((box[3] - box[1]) * k) // 2 * 2)
        outdir = work / "o"
        outdir.mkdir()
        for i, f in enumerate(frames):
            im = hue(Image.open(f).convert("RGB"), a.hue_shift)
            arr = np.asarray(im).astype(np.float32)
            al = alpha_for(arr, y_disc, None)
            A = Image.fromarray((al * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))
            rgba = im.convert("RGBA")
            rgba.putalpha(A)
            rgba.crop(box).resize(size, Image.LANCZOS).save(outdir / f"o{i:05d}.png")

        def enc(pattern: str, dst: Path, extra: list[str]) -> None:
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-framerate",
                    str(a.fps),
                    "-i",
                    pattern,
                    *extra,
                    "-c:v",
                    "libvpx-vp9",
                    "-pix_fmt",
                    "yuva420p",
                    "-b:v",
                    "0",
                    "-crf",
                    "28",
                    "-row-mt",
                    "1",
                    "-auto-alt-ref",
                    "0",
                    str(dst),
                ],
                check=True,
            )

        enc(f"{outdir}/o%05d.png", a.out / f"{a.name}.webm", [])
        if a.reverse:
            enc(f"{outdir}/o%05d.png", a.out / f"{a.reverse}.webm", ["-vf", "reverse"])
        print(a.out / f"{a.name}.webm", size, f"disc_y={round((y_disc - box[1]) * k)}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
