"""Cut a table object (rendered on black) into an RGBA cut-out that sits on the studio desk.

- Emblem body (above the light disc): solid, so the smoked glass stays dark and opaque.
- Glow around it: soft luminance key.
- Below the disc: only the bright reflections survive, the source wood patch is dropped.
Output is cropped to the object and normalised so the light disc is the same width for every tool.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage


def disc_row(lum: np.ndarray, r: np.ndarray, g: np.ndarray) -> int:
    hot = (lum > 200) & (r >= g)
    rows = hot.sum(axis=1)
    lower = rows.copy()
    lower[: int(len(rows) * 0.35)] = 0
    return int(lower.argmax())


def cut(src: Path, dst: Path, disc_width_px: int = 520) -> Image.Image:
    im = Image.open(src).convert("RGB")
    a = np.asarray(im).astype(np.float32)
    lum = a.max(axis=2)
    y_disc = disc_row(lum, a[..., 0], a[..., 1])
    yy = np.arange(lum.shape[0])[:, None]
    above = yy < y_disc - 4

    body = ndimage.binary_closing(lum > 28, iterations=3) & above
    body = ndimage.binary_fill_holes(body)
    lab, n = ndimage.label(body)
    if n:
        sizes = ndimage.sum(body, lab, range(1, n + 1))
        body = np.isin(lab, 1 + np.where(sizes > 1500)[0])
    body = ndimage.binary_erosion(body, iterations=2)

    glow = np.clip((lum - 14) / 45, 0, 1)
    refl = np.clip((lum - 70) / 90, 0, 1)
    alpha = np.where(above, glow, refl)
    alpha = np.where(body, 1.0, alpha)
    A = Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))

    rgba = im.convert("RGBA")
    rgba.putalpha(A)
    # crop to the meaningful object (bright parts), with a margin for the glow
    ys, xs = np.where((lum > 60) | body)
    pad = 24
    box = (max(0, xs.min() - pad), max(0, ys.min() - pad), min(im.width, xs.max() + pad), min(im.height, ys.max() + pad))
    rgba = rgba.crop(box)
    # normalise: the disc spans the bright ring's width on its row
    ring = np.where(lum[y_disc] > 150)[0]
    ring_w = max(1, ring.max() - ring.min()) if ring.size else rgba.width
    k = disc_width_px / ring_w
    rgba = rgba.resize((max(1, round(rgba.width * k)), max(1, round(rgba.height * k))), Image.LANCZOS)
    rgba.info["disc_y"] = round((y_disc - box[1]) * k)
    rgba.save(dst)
    return rgba


if __name__ == "__main__":
    for p in sys.argv[1:]:
        src = Path(p)
        out = cut(src, src.with_name("cutout.png"))
        print(src.parent.name, out.size)
