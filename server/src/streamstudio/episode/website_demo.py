"""Website-demo/v1. Capture once; direction changes only affect the overlay."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit, urlunsplit

from ..core.config import Settings
from .contract import Scene, WebsiteDemo

CATALOG = {
    "id": "website-demo/v1",
    "choose_when": "A card scene explains a visible feature on an allowed HTTPS site.",
    "requires": ["scene.site", "visible accessible label for the feature"],
    "manual": "For a manual host, upload a screenshot and supply its sha256 and focal point.",
    "capture": "Playwright Chromium viewport and a camera move to the labeled feature",
    "editable_without_capture": ["side", "reveal_at"],
    "reveal_at": "Fraction of narration duration when the camera starts moving.",
}


def capture_mode(s: Settings, url: str) -> str | None:
    try:
        u = urlsplit(url)
        if u.scheme != "https" or u.username or u.password or u.port not in (None, 443):
            return None
        return next((x.mode for x in s.capture_allowlist if x.host == u.hostname), None)
    except ValueError:
        return None


def auto_site(s: Settings, url: str) -> bool:
    return capture_mode(s, url) == "auto"


def manual_folder(s: Settings, url: str) -> Path:
    if capture_mode(s, url) != "manual":
        raise ValueError("the site must be configured for manual capture")
    u = urlsplit(url)
    normalized = urlunsplit(("https", u.hostname, u.path.rstrip("/"), u.query, ""))
    return s.sites_dir / hashlib.sha256(normalized.encode()).hexdigest()


def store_manual(s: Settings, url: str, source: Path) -> str:
    from PIL import Image

    folder = manual_folder(s, url)
    folder.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=folder) as tmp:
        png = Path(tmp) / "capture.png"
        with Image.open(source) as image:
            if (image.format not in ("PNG", "JPEG", "WEBP")
                    or image.width * image.height > 20_000_000):
                raise ValueError("expected a PNG, JPEG or WebP screenshot under 20 megapixels")
            # Strip ancillary metadata and preserve the entire viewport and its coordinates.
            image.convert("RGB").save(png, "PNG")
        with png.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        target = folder / (digest + ".png")
        with contextlib.suppress(FileExistsError):
            os.link(png, target)
    return digest


def asset_path(folder: Path, scene: Scene) -> Path | None:
    spec = scene.plan.website_demo if scene.plan else None
    if not spec:
        return None
    key = json.dumps([spec.workflow, scene.site, spec.focus_label], ensure_ascii=True)
    if spec.manual:
        key += spec.manual.model_dump_json()
    return folder / "cards" / (hashlib.sha256(key.encode()).hexdigest() + ".mp4")


def prepare(s: Settings, scene: Scene, folder: Path) -> Path:
    from playwright.sync_api import sync_playwright

    dst = asset_path(folder, scene)
    mode = capture_mode(s, scene.site or "")
    manual = scene.plan.website_demo.manual if dst else None
    if dst is None or scene.kind != "card" or mode != ("manual" if manual else "auto"):
        raise ValueError("capture method must match the allowed host mode")
    if dst.is_file():
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    width, height = 1200, 740
    with TemporaryDirectory(dir=dst.parent) as temp:
        image = Path(temp) / "page.png"
        movie = Path(temp) / "card.mp4"
        if manual:
            image = manual_folder(s, scene.site) / (manual.sha256 + ".png")
            with image.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != manual.sha256:
                    raise ValueError("manual screenshot failed its integrity check")
            cx, cy = manual.focus_x, manual.focus_y
        else:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(executable_path=s.hyperframes_browser)
                page = browser.new_page(viewport={"width": width, "height": height},
                                        reduced_motion="reduce", service_workers="block")

                def same_site(route):
                    url = route.request.url
                    if (not auto_site(s, url)
                            or urlsplit(url).hostname != urlsplit(scene.site).hostname):
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
        if manual:
            # Preserve aspect ratio; focal coordinates refer to the submitted image.
            from PIL import Image
            with Image.open(image) as source:
                scale = min(width/source.width, height/source.height)
                cx = .5 + (cx-.5)*source.width*scale/width
                cy = .5 + (cy-.5)*source.height*scale/height
            camera = ("scale=1200:740:force_original_aspect_ratio=decrease,"
                      "pad=1200:740:(ow-iw)/2:(oh-ih)/2," + camera)
        subprocess.run([s.ffmpeg_bin, "-loglevel", "error", "-i", str(image), "-vf", camera,
                        "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "16", str(movie)],
                       check=True)
        movie.replace(dst)
    return dst


def overlay(s: Settings, base: Path, card: Path, spec: WebsiteDemo, out: Path,
            *, outline: tuple = (171, 191, 198, 255)) -> None:
    """Render a 1920x1080 scene. Preserve the base soundtrack and hold the capture after reveal."""
    from .compose import probe_duration

    duration = probe_duration(s.ffprobe_bin, base)
    start = round(duration * spec.reveal_at * 25) / 25
    x = "60" if spec.side == "left" else "W-w-60"
    color = bytes(outline).hex()
    filters = (f"[1:v]scale=1180:-2,format=yuva420p,pad=iw+8:ih+8:4:4:color=0x{color},"
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
