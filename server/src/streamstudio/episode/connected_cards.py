"""Render the local 3D card composition with deterministic scene time and the approved audio."""
from __future__ import annotations

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from ..core.config import Settings
from .compose import FPS, probe_duration
from .contract import ConnectedCards


def render(s: Settings, spec: ConnectedCards, channel: str, clip: Path, output: Path) -> dict:
    from playwright.sync_api import sync_playwright

    frames = max(1, round(probe_duration(s.ffprobe_bin, clip) * FPS))
    template = Path(__file__).parent / "templates" / "connected-cards.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as tmp, sync_playwright() as pw:
        movie = Path(tmp) / "scene.mp4"
        browser = pw.chromium.launch(executable_path=s.hyperframes_browser)
        page = browser.new_page(viewport={"width": 1280, "height": 720}, offline=True)
        page.goto(template.resolve().as_uri())
        data = {**spec.model_dump(), "channel": channel}
        page.evaluate("spec => window.configureCards(spec)", data)
        args = [s.ffmpeg_bin, "-v", "error", "-f", "image2pipe", "-framerate", str(FPS),
                "-i", "-", "-i", str(clip), "-map", "0:v", "-map", "1:a:0", "-vf",
                "scale=1920:1080", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(movie)]
        with subprocess.Popen(args, stdin=subprocess.PIPE) as encoder:
            try:
                for frame in range(frames):
                    page.evaluate("t => window.seekScene(t)", frame / FPS)
                    encoder.stdin.write(page.screenshot(type="jpeg", quality=94))
            finally:
                encoder.stdin.close()
            if encoder.wait():
                raise RuntimeError("connected card encoding failed")
        movie.replace(output)
    return {"frames": frames, "duration_s": frames / FPS, "cue": "content"}
