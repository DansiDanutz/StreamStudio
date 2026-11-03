"""Website-demo/v1. Capture once; direction changes only affect the overlay."""
from __future__ import annotations

import contextlib
import hashlib
import http.client
import json
import math
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit, urlunsplit

from ..core.config import Settings
from . import FPS
from .contract import Scene, WebsiteDemo

CATALOG = {
    "id": "website-demo/v1",
    "choose_when": "A card scene explains a visible feature on an allowed HTTPS site.",
    "requires": ["scene.site"],
    "focus_label": "Exact accessible label or unique visible text. Omit to select the page hero.",
    "callout": "Without an explicit label, show the page address and scene text at the reveal.",
    "manual": "For a manual host, upload a screenshot and supply its sha256 and focal point.",
    "capture": "Playwright Chromium viewport and a camera move to the labeled feature",
    "editable_without_capture": ["side", "reveal_at", "focus_cues", "page_switch.at_s"],
    "reveal_at": "Fraction of the first scene duration when the camera starts moving.",
    "focus_cues": "Timed outlines on the held opening viewport, in normalized coordinates. "
                  "Times are seconds from the start of this scene.",
    "page_switch": "Switch to another allowed automatic page at scene-local at_s seconds.",
    "direction_rules": [
        "For one feature, use focus_label and reveal_at to zoom toward it.",
        "When narration names several items already visible together, use focus_cues. "
        "Measure cue times against the actual voice take and rectangles against the opening frame.",
        "When narration moves to another page, use page_switch. Prepare both pages once. "
        "Preview timing edits from the cached cards. The second site requires automatic capture.",
        "Use separate scenes if a page switch and timed outlines are both needed.",
    ],
    "continuity": "Adjacent scenes with the same site and direction share one camera move.",
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
    if spec.page_switch:
        key += spec.page_switch.model_dump_json()
    if spec.manual:
        key += spec.manual.model_dump_json()
    return folder / "cards" / (hashlib.sha256(key.encode()).hexdigest() + ".mp4")


def automatic_hero(page):
    """Find the largest visible illustration, with the page heading as a text-only fallback."""
    return page.evaluate("""() => {
        const visible = el => {
            const r = el.getBoundingClientRect();
            const css = getComputedStyle(el);
            return { x: r.x, y: r.y, width: r.width, height: r.height,
                     area: css.visibility === 'hidden' || css.display === 'none' ||
                           Number(css.opacity) === 0 ? 0 :
                           Math.max(0, Math.min(r.right, innerWidth) - Math.max(0, r.left)) *
                           Math.max(0, Math.min(r.bottom, innerHeight) - Math.max(0, r.top)) };
        };
        const graphics = [...document.querySelectorAll('img,video,canvas,svg,[role="img"]')]
          .filter(el => !el.closest('header,nav,[aria-hidden="true"]'))
          .map(visible).filter(r => r.area >= 4096);
        const headings = [...document.querySelectorAll('main h1,h1,h2')].map(visible);
        return graphics.sort((a,b) => b.area-a.area)[0] || headings.find(r => r.area>0)
          || {x: innerWidth/4, y: innerHeight/4, width: innerWidth/2, height: innerHeight/2};
    }""")


def prepare(s: Settings, scene: Scene, folder: Path, *, cached_only: bool = False) -> Path:
    from playwright.sync_api import Error as BrowserError
    from playwright.sync_api import sync_playwright

    dst = asset_path(folder, scene)
    mode = capture_mode(s, scene.site or "")
    manual = scene.plan.website_demo.manual if dst else None
    if dst is None or scene.kind != "card" or mode != ("manual" if manual else "auto"):
        raise ValueError("capture method must match the allowed host mode")
    switch = scene.plan.website_demo.page_switch
    if switch:
        if not auto_site(s, switch.site):
            raise ValueError("the second page needs an allowed automatic capture host")
        if dst.is_file():
            return dst
        first = scene.model_copy(deep=True)
        first.plan.website_demo.page_switch = None
        second = first.model_copy(deep=True)
        second.site = switch.site
        second.plan.website_demo = WebsiteDemo(focus_label=switch.focus_label)
        sources = [prepare(s, page, folder, cached_only=cached_only) for page in (first, second)]
        frames = max(1, math.ceil(switch.at_s * FPS))
        with TemporaryDirectory(dir=dst.parent) as temp:
            movie = Path(temp) / "sequence.mp4"
            graph = (f"[0:v]tpad=stop_mode=clone:stop={frames},trim=end_frame={frames},"
                     "setpts=PTS-STARTPTS[a];[a][1:v]concat=n=2:v=1:a=0[v]")
            subprocess.run([s.ffmpeg_bin, "-loglevel", "error", "-i", str(sources[0]),
                            "-i", str(sources[1]), "-filter_complex", graph, "-map", "[v]",
                            "-c:v", "libx264", "-crf", "16", str(movie)], check=True)
            movie.replace(dst)
        return dst
    if dst.is_file():
        return dst
    if cached_only:
        raise ValueError(f"missing prepared card for {scene.site} (expected {dst.name})")
    dst.parent.mkdir(parents=True, exist_ok=True)
    width, height = 1200, 740
    with TemporaryDirectory(dir=dst.parent) as temp:
        image = Path(temp) / "page.png"
        movie = Path(temp) / "card.mp4"
        caps = folder / "caps"
        caps.mkdir(exist_ok=True)
        snapshot = caps / dst.stem
        if not snapshot.is_dir():
            scroll = 0
            evidence = {"url": scene.site, "mode": mode, "title": None, "heading": None,
                        "description": None, "focus_label": scene.plan.website_demo.focus_label}
            if manual:
                image = manual_folder(s, scene.site) / (manual.sha256 + ".png")
                with image.open("rb") as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != manual.sha256:
                        raise ValueError("manual screenshot failed its integrity check")
                cx, cy = manual.focus_x, manual.focus_y
            else:
                from .capture_network import CaptureOrigin

                origin = CaptureOrigin(urlsplit(scene.site).hostname)
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(executable_path=s.hyperframes_browser)
                    context = browser.new_context(viewport={"width": width, "height": height},
                                                  reduced_motion="reduce", service_workers="block",
                                                  offline=True)
                    context.route_web_socket("**/*", lambda ws: ws.close())

                    navigation_errors = []

                    def same_site(route):
                        req = route.request
                        try:
                            response = origin.fetch(req.url, req.method, req.headers)
                        except (ValueError, OSError, http.client.HTTPException) as exc:
                            if (req.is_navigation_request()
                                    and urlsplit(req.url).hostname == origin.host):
                                navigation_errors.append(str(exc))
                            return route.abort()
                        return route.fulfill(**response)

                    context.route("**/*", same_site)
                    page = context.new_page()
                    try:
                        response = page.goto(scene.site, wait_until="load")
                    except BrowserError:
                        if navigation_errors:
                            raise ValueError(navigation_errors[0]) from None
                        raise
                    if not response or not response.ok:
                        raise ValueError("website capture failed")
                    page.evaluate("document.fonts.ready")
                    label = scene.plan.website_demo.focus_label
                    if label:
                        target = page.get_by_label(label, exact=True)
                        if not target.count():
                            target = page.get_by_text(label, exact=True)
                            target = target.and_(page.locator(":visible"))
                        if target.count() != 1:
                            raise ValueError(f"capture target must match exactly once: {label}")
                        target.scroll_into_view_if_needed()
                        box = target.bounding_box()
                        if not box:
                            raise ValueError("the capture target is not visible")
                        page.screenshot(path=image, animations="disabled")
                    else:
                        box = automatic_hero(page)
                        extra = page.evaluate("document.documentElement.scrollHeight-740")
                        focus = box["y"] + box["height"]/2
                        scroll = max(0, min(160, extra, round(focus-height*.32)))
                        clip = {"x": 0, "y": 0, "width": width, "height": height+scroll}
                        page.screenshot(path=image, animations="disabled", clip=clip)
                    evidence.update(page.evaluate("""() => ({
                        title: document.title.slice(0, 500),
                        heading: document.querySelector('h1')?.innerText?.slice(0, 500) ?? null,
                        description: document.querySelector('meta[name="description" i]')
                            ?.content?.slice(0, 2000) ?? null
                    })"""))
                    evidence["hero_box"] = {k: box[k] for k in ("x", "y", "width", "height")}
                    context.unroute_all(behavior="wait")
                    browser.close()
                cx = (box["x"] + box["width"] / 2) / width
                cy = (box["y"] + box["height"] / 2) / height
            # Publish the image and its provenance together. Concurrent workers reuse the winner.
            bundle = Path(temp) / "snapshot"
            bundle.mkdir()
            shutil.copyfile(image, bundle / "page.png")
            with image.open("rb") as source:
                evidence["sha256"] = hashlib.file_digest(source, "sha256").hexdigest()
            evidence.update(focus_x=cx, focus_y=cy, scroll_px=scroll)
            (bundle / "metadata.json").write_text(json.dumps(evidence), encoding="utf8")
            try:
                bundle.rename(snapshot)
            except OSError:
                if not snapshot.is_dir():
                    raise
        image = snapshot / "page.png"
        evidence = json.loads((snapshot / "metadata.json").read_text(encoding="utf8"))
        with image.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() != evidence["sha256"]:
                raise ValueError("saved capture failed its integrity check")
        cx, cy, scroll = evidence["focus_x"], evidence["focus_y"], evidence["scroll_px"]
        # Ease from the full viewport into the product detail; hold its final frame in the scene.
        zoom = "1+0.78*(1-cos(PI*min(on/35,1)))/2"
        prefix = ""
        if manual:
            # Preserve aspect ratio; focal coordinates refer to the submitted image.
            from PIL import Image
            with Image.open(image) as source:
                scale = min(width/source.width, height/source.height)
                cx = .5 + (cx-.5)*source.width*scale/width
                cy = .5 + (cy-.5)*source.height*scale/height
            prefix = ("scale=1200:740:force_original_aspect_ratio=decrease,"
                      "pad=1200:740:(ow-iw)/2:(oh-ih)/2,")
        if scroll:
            prefix = f"crop=1200:740:0:'{scroll}*min(n/35,1)',"
        target_y = f"{cy}" if not scroll else f"({cy}-{scroll/height}*min(on/35,1))"
        repeats = 1 if scroll else 36
        camera = (prefix + f"zoompan=z='{zoom}':x='clip(iw*{cx}-iw/zoom/2,0,iw-iw/zoom)'"
                  f":y='clip(ih*{target_y}-ih/zoom/2,0,ih-ih/zoom)':d={repeats}:s=1200x740:fps=25")
        loop = ["-loop", "1", "-framerate", "25"] if scroll else []
        subprocess.run([s.ffmpeg_bin, "-loglevel", "error", *loop, "-i", str(image), "-vf", camera,
                        "-frames:v", "36",
                        "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "16", str(movie)],
                       check=True)
        movie.replace(dst)
    return dst


def card_timeline(scenes: list[Scene], durations: list[float]) -> dict[str, tuple[int, int]]:
    """Return (offset, reveal) in frames on the shared camera track for consecutive shots."""
    tracks = {}
    previous = None
    offset = reveal = 0
    for scene, duration in zip(scenes, durations, strict=True):
        spec = scene.plan.website_demo if scene.plan else None
        if spec is None:
            previous = None
            continue
        track = (scene.site, spec)
        length = max(1, round(duration * FPS))
        if track != previous:
            offset = 0
            reveal = min(length-1, round(length * spec.reveal_at))
        tracks[scene.id] = (offset, reveal)
        previous = track
        offset += length
    return tracks


def callout_image(renderer, text: str, site: str):
    """Render script copy as pixels, including untrusted punctuation, in the approved font."""
    from PIL import Image, ImageDraw

    font = renderer.font(32, "SemiBold")
    words = text.split()
    lines = []
    while words and len(lines) < 2:
        line = words.pop(0)
        while words and font.getlength(line + " " + words[0]) <= 1090:
            line += " " + words.pop(0)
        needs_ellipsis = font.getlength(line) > 1090 or (len(lines) == 1 and words)
        if needs_ellipsis:
            while line and font.getlength(line + "…") > 1090:
                line = line[:-1]
            line = line.rstrip() + "…"
        lines.append(line)
    image = Image.new("RGBA", (1188, 54 + 42*len(lines)))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, image.width-1, image.height-1), 14,
                           fill=renderer.colors.get("panel", (8, 14, 20, 235)),
                           outline=renderer.colors["outline"], width=2)
    draw.text((24, 8), urlsplit(site).hostname or "", font=renderer.font(22, "Medium"),
              fill=renderer.colors.get("tag_text", renderer.colors["accent_a"]))
    for i, line in enumerate(lines):
        draw.text((24, 42+42*i), line, font=font, fill=renderer.colors["text"])
    return image


def overlay(s: Settings, base: Path, card: Path, spec: WebsiteDemo, out: Path,
            *, outline: tuple = (171, 191, 198, 255), track: tuple[int, int] | None = None,
            callout=None) -> None:
    """Render a 1920x1080 scene. Preserve the base soundtrack and hold the capture after reveal."""
    from .compose import probe_duration

    duration = probe_duration(s.ffprobe_bin, base)
    length = max(1, round(duration * FPS))
    offset, reveal = track or (0, min(length-1, round(length * spec.reveal_at)))
    if spec.page_switch:
        offset = reveal = 0
    x = "60" if spec.side == "left" else "W-w-60"
    color = bytes(outline).hex()
    motion = (f"tpad=start={reveal}:start_mode=clone:stop_mode=clone:stop=-1,"
              f"trim=start_frame={offset}:end_frame={offset+length},setpts=PTS-STARTPTS")
    if spec.focus_cues:
        # Cue coordinates refer to the opening viewport, before the prepared camera zoom.
        motion = f"trim=end_frame=1,tpad=stop_mode=clone:stop={length-1},setpts=PTS-STARTPTS"
        for cue in spec.focus_cues:
            motion += (f",drawbox=x=iw*{cue.x}:y=ih*{cue.y}:w=iw*{cue.width}:h=ih*{cue.height}"
                       f":color=0x76efd2:t=5:enable='gte(t,{cue.start_s})*lt(t,{cue.end_s})'")
    filters = (f"[1:v]{motion},scale=1180:-2,format=yuva420p,"
               f"pad=iw+8:ih+8:4:4:color=0x{color}[c];"
               f"[0:v][c]overlay=x={x}:y=(H-h)/2:eof_action=repeat[v]")
    out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=out.parent) as temp:
        result = Path(temp) / "scene.mp4"
        inputs = ["-i", str(base), "-i", str(card)]
        if callout is not None:
            label = Path(temp) / "callout.png"
            callout.save(label)
            inputs += ["-i", str(label)]
            at = max(0, reveal-offset) / FPS
            filters = filters.removesuffix("[v]") + (
                f"[scene];[scene][2:v]overlay=x={x}:y=H-h-32:enable='gte(t,{at})'[v]")
        subprocess.run([s.ffmpeg_bin, "-loglevel", "error", *inputs,
                        "-filter_complex", filters, "-map", "[v]", "-map", "0:a?",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "copy",
                        "-movflags", "+faststart", str(result)], check=True)
        result.replace(out)
