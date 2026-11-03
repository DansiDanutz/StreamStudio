"""Website-demo/v1. Capture once; direction changes only affect the overlay."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from ..core.config import Settings
from .contract import Scene, WebsiteDemo

CATALOG = {
    "id": "website-demo/v1",
    "choose_when": "A card scene explains a visible feature on a public auto-allowed HTTPS site.",
    "requires": ["scene.site", "visible accessible label for the feature"],
    "capture": "Playwright Chromium viewport and a camera move to the labeled feature",
    "editable_without_capture": ["side", "reveal_at"],
    "reveal_at": "Fraction of narration duration when the camera starts moving.",
}


def auto_site(s: Settings, url: str) -> bool:
    try:
        u = urlsplit(url)
        port = u.port
    except ValueError:
        return False
    return (u.scheme == "https" and not u.username and not u.password and port in (None, 443)
            and any(x.host == u.hostname and x.mode == "auto" for x in s.capture_allowlist))


def asset_path(folder: Path, scene: Scene) -> Path | None:
    spec = scene.plan.website_demo if scene.plan else None
    if not spec:
        return None
    key = json.dumps([spec.workflow, scene.site, spec.focus_label], ensure_ascii=True)
    return folder / "cards" / (hashlib.sha256(key.encode()).hexdigest() + ".mp4")


def prepare(s: Settings, scene: Scene, folder: Path) -> Path:
    from playwright.sync_api import sync_playwright

    dst = asset_path(folder, scene)
    if dst is None or scene.kind != "card" or not auto_site(s, scene.site or ""):
        raise ValueError("website-demo/v1 requires a card on an auto-allowed HTTPS site")
    if dst.is_file():
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    width, height = 1200, 740
    with TemporaryDirectory(dir=dst.parent) as temp:
        image = Path(temp) / "page.png"
        movie = Path(temp) / "card.mp4"
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=s.hyperframes_browser)
            page = browser.new_page(viewport={"width": width, "height": height},
                                    reduced_motion="reduce", service_workers="block")

            def same_site(route):
                url = route.request.url
                if not auto_site(s, url) or urlsplit(url).hostname != urlsplit(scene.site).hostname:
                    return route.abort()
                response = route.fetch(max_redirects=0)
                if 300 <= response.status < 400:
                    return route.abort()
                return route.fulfill(response=response)

            page.route("**/*", same_site)
            response = page.goto(scene.site, wait_until="load")
            if not response or not response.ok:
                raise ValueError("website capture failed")
            target = page.get_by_label(scene.plan.website_demo.focus_label, exact=True)
            target.scroll_into_view_if_needed()
            page.evaluate("document.fonts.ready")
            box = target.bounding_box()
            if not box:
                raise ValueError("the capture target is not visible")
            page.screenshot(path=image, animations="disabled")
            browser.close()
        cx = (box["x"] + box["width"] / 2) / width
        cy = (box["y"] + box["height"] / 2) / height
        # Ease from the full viewport into the product detail; hold its final frame in the scene.
        zoom = "1+0.78*(1-cos(PI*min(on/35,1)))/2"
        camera = (f"zoompan=z='{zoom}':x='clip(iw*{cx}-iw/zoom/2,0,iw-iw/zoom)'"
                  f":y='clip(ih*{cy}-ih/zoom/2,0,ih-ih/zoom)':d=36:s=1200x740:fps=25")
        subprocess.run([s.ffmpeg_bin, "-loglevel", "error", "-i", str(image), "-vf", camera,
                        "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "16", str(movie)],
                       check=True)
        movie.replace(dst)
    return dst


def overlay(s: Settings, base: Path, card: Path, spec: WebsiteDemo, out: Path) -> None:
    """Render a 1920x1080 scene. Preserve the base soundtrack and hold the capture after reveal."""
    from .compose import probe_duration

    duration = probe_duration(s.ffprobe_bin, base)
    start = round(duration * spec.reveal_at * 25) / 25
    x = "60" if spec.side == "left" else "W-w-60"
    filters = (f"[1:v]scale=1180:-2,pad=iw+8:ih+8:4:4:color=0xabbfc6,"
               f"tpad=start_duration={start}:start_mode=clone[c];"
               f"[0:v][c]overlay=x={x}:y=(H-h)/2:eof_action=repeat[v]")
    out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=out.parent) as temp:
        result = Path(temp) / "scene.mp4"
        subprocess.run([s.ffmpeg_bin, "-loglevel", "error", "-i", str(base), "-i", str(card),
                        "-filter_complex", filters, "-map", "[v]", "-map", "0:a?",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "copy",
                        "-movflags", "+faststart", str(result)], check=True)
        result.replace(out)
