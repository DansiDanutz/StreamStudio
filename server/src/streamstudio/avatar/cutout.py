"""Avatar cut-out: remove the background from an avatar clip and composite it onto a studio plate.

Pipeline (all local, free):
  clip.mp4 → frames → human segmentation (rembg u2net_human_seg) → alpha matte (temporally smoothed)
           → cutout.webm (VP9 + alpha, for the browser)            [Chrome/Edge/Firefox]
           → composite.mp4 (cutout placed on the plate)             [preview + Safari fallback]

Usage: python -m streamstudio.avatar.cutout CLIP PLATE OUT_DIR [--scale 0.92] [--anchor-y 0.86] [--x 0.5]
`anchor-y` is where the bottom of the cut-out lands on the plate (fraction of plate height);
`scale` is cut-out height relative to plate height. Audio is carried over from the clip.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate,nb_frames", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    s = json.loads(out)["streams"][0]
    num, _, den = s["r_frame_rate"].partition("/")
    return {"w": s["width"], "h": s["height"], "fps": int(num) / int(den or 1)}


def extract_frames(clip: Path, out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), f"{out}/f%05d.png"], check=True)
    return sorted(out.glob("f*.png"))


def segment(frames: list[Path], out: Path, model: str = "u2net_human_seg") -> list[Path]:
    """Write RGBA PNGs with a smoothed alpha matte. Temporal smoothing (3-frame EMA) kills flicker."""
    from rembg import new_session, remove

    out.mkdir(parents=True, exist_ok=True)
    session = new_session(model)
    prev: np.ndarray | None = None
    results: list[Path] = []
    for i, f in enumerate(frames):
        img = Image.open(f).convert("RGB")
        rgba = remove(img, session=session, alpha_matting=False, post_process_mask=True)
        a = np.asarray(rgba.split()[-1], dtype=np.float32)
        if prev is not None:
            a = 0.65 * a + 0.35 * prev
        prev = a
        alpha = Image.fromarray(a.astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
        rgba.putalpha(alpha)
        p = out / f.name
        rgba.save(p)
        results.append(p)
        if i % 25 == 0:
            print(f"  segmented {i + 1}/{len(frames)}", flush=True)
    return results


def fit_cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Resize + centre-crop to `size` (like CSS object-fit: cover)."""
    w, h = img.size
    k = max(size[0] / w, size[1] / h)
    img = img.resize((round(w * k), round(h * k)), Image.LANCZOS)
    left = (img.width - size[0]) // 2
    top = (img.height - size[1]) // 2
    return img.crop((left, top, left + size[0], top + size[1]))


def composite(
    cutouts: list[Path], plate: Path, out: Path, *, scale: float, anchor_y: float, x: float,
    size: tuple[int, int] = (1920, 1080),
) -> None:
    """Place each RGBA cut-out on the plate at output size: height = scale*H, bottom at anchor_y, centred at x."""
    out.mkdir(parents=True, exist_ok=True)
    bg = fit_cover(Image.open(plate).convert("RGB"), size)
    pw, ph = bg.size
    for p in cutouts:
        fg = Image.open(p).convert("RGBA")
        fw, fh = fg.size
        th = int(ph * scale)
        tw = int(fw * th / fh)
        fg = fg.resize((tw, th), Image.LANCZOS)
        canvas = bg.convert("RGBA")
        canvas.alpha_composite(fg, (int(pw * x - tw / 2), int(ph * anchor_y - th)))
        canvas.convert("RGB").save(out / p.name)


def encode_alpha_webm(cutouts_dir: Path, fps: float, clip: Path, out: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-framerate", f"{fps}", "-i", f"{cutouts_dir}/f%05d.png",
         "-i", str(clip), "-map", "0:v", "-map", "1:a?", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
         "-b:v", "0", "-crf", "30", "-row-mt", "1", "-auto-alt-ref", "0", "-c:a", "libopus", "-shortest", str(out)],
        check=True,
    )  # fmt: skip


def encode_mp4(frames_dir: Path, fps: float, clip: Path, out: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-framerate", f"{fps}", "-i", f"{frames_dir}/f%05d.png",
         "-i", str(clip), "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)],
        check=True,
    )  # fmt: skip


def run(clip: Path, plate: Path, out_dir: Path, *, scale: float, anchor_y: float, x: float, keep: bool) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    info = probe(clip)
    work = Path(tempfile.mkdtemp(prefix="cutout_"))
    cache = out_dir / "cache" / clip.stem  # segmented RGBA frames: the slow part, kept between runs
    try:
        print(f"frames…  ({info['w']}x{info['h']} @ {info['fps']:.3g} fps)", flush=True)
        frames = extract_frames(clip, work / "frames")
        cached = sorted(cache.glob("f*.png"))
        if len(cached) == len(frames):
            print(f"using {len(cached)} cached segmented frames", flush=True)
            cut = cached
        else:
            print(f"segmenting {len(frames)} frames…", flush=True)
            cut = segment(frames, cache)
        print("compositing…", flush=True)
        size = (1920, 1080) if info["w"] >= info["h"] else (1080, 1920)
        composite(cut, plate, work / "comp", scale=scale, anchor_y=anchor_y, x=x, size=size)
        stem = clip.stem
        webm = out_dir / f"{stem}.cutout.webm"
        mp4 = out_dir / f"{stem}.on-plate.mp4"
        still = out_dir / f"{stem}.on-plate.jpg"
        print("encoding…", flush=True)
        encode_alpha_webm(cache, info["fps"], clip, webm)
        encode_mp4(work / "comp", info["fps"], clip, mp4)
        Image.open(sorted((work / "comp").glob("*.png"))[len(frames) // 3]).save(still, quality=92)
        return {"cutout_webm": str(webm), "composite_mp4": str(mp4), "still": str(still), **info}
    finally:
        if not keep:
            shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("clip", type=Path)
    ap.add_argument("plate", type=Path)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--scale", type=float, default=0.78)
    ap.add_argument("--anchor-y", type=float, default=0.88)
    ap.add_argument("--x", type=float, default=0.46)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    print(json.dumps(run(a.clip, a.plate, a.out_dir, scale=a.scale, anchor_y=a.anchor_y, x=a.x, keep=a.keep), indent=2))


if __name__ == "__main__":
    main()
