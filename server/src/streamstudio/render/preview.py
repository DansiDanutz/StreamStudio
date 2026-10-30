"""Headless preview render: play the current script in render mode and record the Base card.

Uses Playwright's built-in recorder (VP8 WebM at the viewport size), then ffmpeg re-encodes to H.264
and muxes the given audio (e.g. the avatar clip's voice). This is the *preview* path; the production
path (S6) encodes the compositor stream live on the Mac Studio with VideoToolbox.

Usage: python -m streamstudio.render.preview OUT.mp4 [--url http://127.0.0.1:8787] [--audio clip.mp4]
       [--width 1920 --height 1080] [--max-seconds 120]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


def record(url: str, out_dir: Path, w: int, h: int, max_s: float) -> Path:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        ctx = browser.new_context(
            viewport={"width": w, "height": h},
            device_scale_factor=1,
            record_video_dir=str(out_dir),
            record_video_size={"width": w, "height": h},
        )
        page = ctx.new_page()
        page.goto(f"{url}/?render=1&autoplay=1")
        page.wait_for_selector(".base")
        t0 = time.time()
        # wait for the director to start, then to stop
        page.wait_for_function("() => window.__director && window.__director.getState().playing", timeout=15_000)
        while time.time() - t0 < max_s:
            if not page.evaluate("() => window.__director.getState().playing"):
                break
            time.sleep(0.25)
        time.sleep(0.6)  # let the last sketch settle
        path = page.video.path()
        ctx.close()
        browser.close()
    return Path(path)


def encode(webm: Path, out: Path, audio: Path | None, lead_in_s: float = 0.8) -> None:
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(webm)]
    if audio:
        cmd += ["-itsoffset", f"{lead_in_s}", "-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    cmd += [str(out)]
    subprocess.run(cmd, check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--url", default="http://127.0.0.1:8787")
    ap.add_argument("--audio", type=Path)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--max-seconds", type=float, default=120)
    a = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="render_"))
    try:
        webm = record(a.url, tmp, a.width, a.height, a.max_seconds)
        encode(webm, a.out, a.audio)
        print(a.out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
