"""Render the unsaved channel look in memory using the episode compositor."""
from __future__ import annotations

import io
import re
import sqlite3
import subprocess

from ..core.config import Settings
from .compose import Compositor, H, W
from .profiles import Profile


def preview(c: sqlite3.Connection, s: Settings, profile: Profile) -> tuple[bytes, bool]:
    import numpy as np
    from PIL import Image, ImageDraw

    renderer = Compositor(s, profile.look.model_dump() if profile.look else None)
    rows = c.execute(
        "SELECT json_extract(payload,'$.key') FROM jobs WHERE kind='heygen_clip' AND status='done'"
        " AND json_extract(payload,'$.look')=? ORDER BY finished_at DESC,id DESC",
        (profile.presenter.avatar_id,),
    )
    rgba = None
    for (key,) in rows:
        if not key or not re.fullmatch(r"[0-9a-f]{16}", key):
            continue
        path = s.assets_dir / "avatar" / "clips" / f"{key}.cutout.webm"
        if path.is_file():
            raw = subprocess.run(
                [s.ffmpeg_bin, "-v", "error", "-c:v", "libvpx-vp9", "-i", str(path),
                 "-ss", "1", "-frames:v", "1", "-vf", f"scale={W}:{H}", "-pix_fmt", "rgba",
                 "-f", "rawvideo", "-"], capture_output=True, timeout=30,
            )
            if not raw.returncode and len(raw.stdout) == W * H * 4:
                rgba = np.frombuffer(raw.stdout, np.uint8).reshape(H, W, 4)
                break
    cached = rgba is not None
    if rgba is None:
        silhouette = Image.new("RGBA", (W, H))
        draw = ImageDraw.Draw(silhouette)
        draw.ellipse((W*.44, H*.06, W*.56, H*.34), fill="#91999c")
        draw.rounded_rectangle((W*.34, H*.35, W*.66, H*.97), 90, fill="#798488")
        rgba = np.asarray(silhouette)
    left = renderer.studio(rgba[..., :3].astype(np.float32), rgba[..., 3:].astype(np.float32)/255)
    title = profile.name
    font = renderer.font(64, "Bold")
    while len(title) > 1 and font.getlength(title + "…") > 1050:
        title = title[:-1]
    if title != profile.name:
        title += "…"
    lines = [(title, 64, "Bold", renderer.colors["text"]),
             ("Website demonstration", 38, "Medium", renderer.colors["accent_a"])]
    right = renderer.place_table_card(renderer.plate.copy(), "sample", lines, 1180, 270, W/2, 1, 1)
    panels = [Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8)).resize(
        (960, 540), Image.Resampling.LANCZOS) for frame in (left, right)]
    image = Image.new("RGB", (1920, 540))
    for index, panel in enumerate(panels):
        image.paste(panel, (960*index, 0))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=90)
    return buffer.getvalue(), cached
