"""DansLab logo-reveal intro: build the HyperFrames composition and render it at 25 fps.

Run when the branding changes, not as part of the pipeline:

    python tools/brand/make_intro.py                  # build + render assets/brand/danslab-intro.mp4
    python tools/brand/make_intro.py --no-render      # only write the composition
    python tools/brand/make_intro.py "DANSLAB" 'Build it. Show it. <em>Sell it.</em>' "Tagline"

Fonts come from assets/brand/fonts; the composition is written under <data_dir>/cards/intro
(STREAMSTUDIO_DATA_DIR, default ~/StreamStudioData) and rendered from the HyperFrames workspace in
<data_dir>/cards (package.json and package-lock.json from server/src/streamstudio/episode/templates,
then `npm ci`). The existing intro's sound track (its own SFX, mixed to -18 LUFS) is kept: the new
video is muxed with the old audio, so the composition does not need audio.

Ported 1:1 from Claude-Youtube remotion (lib/danslab.tsx DlLogoAnimated + SiteBg, ep03 TIntro).
The FPS constant below only scales the GSAP frame timings; the render frame rate is RENDER_FPS.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / "assets" / "brand" / "fonts"
INTRO_MP4 = ROOT / "assets" / "brand" / "danslab-intro.mp4"
TEMPLATES = ROOT / "server" / "src" / "streamstudio" / "episode" / "templates"
DATA_DIR = Path(os.environ.get("STREAMSTUDIO_DATA_DIR", Path.home() / "StreamStudioData"))
WORKSPACE = DATA_DIR / "cards"
OUT = WORKSPACE / "intro" / "index.html"

#: The frame rate every episode render uses (streamstudio.episode.FPS).
RENDER_FPS = 25

args = [a for a in sys.argv[1:] if not a.startswith("--")]
RENDER = "--no-render" not in sys.argv
KICKER = args[0] if len(args) > 0 else "DANSLAB"
TITLE_HTML = args[1] if len(args) > 1 else "Build it. Show it. <em>Sell it.</em>"
TAG = (
    args[2]
    if len(args) > 2
    else "Four questions every builder asks, answered with things we have already built."
)
sys.path.insert(0, str(ROOT / "server" / "src"))
from streamstudio.episode.intro_template import DUR, FONT_FILES, S0, TITLE, composition, f  # noqa: E402

html = composition(KICKER, TITLE_HTML, TAG, "D", {
    "bg": "#050404", "glow": "#160b091a", "accent": "#e74c3c", "accent_dark": "#c0392b",
    "highlight": "#d4a017", "letter": "#fffef7", "title": "#fafafa", "muted": "#b9b1a4",
})


def ensure_workspace() -> None:
    """The HyperFrames workspace in <data_dir>/cards: templates copied, `npm ci` once."""
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    for name in ("package.json", "package-lock.json"):
        src, dst = TEMPLATES / name, WORKSPACE / name
        if not dst.exists() or dst.read_bytes() != src.read_bytes():
            shutil.copy2(src, dst)
    if not (WORKSPACE / "node_modules" / "hyperframes" / "package.json").exists():
        subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=WORKSPACE, check=True)


def render() -> None:
    gsap = WORKSPACE / "node_modules" / "gsap" / "dist" / "gsap.min.js"
    shutil.copy2(gsap, OUT.parent / "gsap.min.js")
    video = OUT.parent / "intro-video.mp4"
    env = dict(os.environ)
    browser = os.environ.get("STREAMSTUDIO_HYPERFRAMES_BROWSER")
    if browser:
        env["HYPERFRAMES_BROWSER_PATH"] = browser
    cmd = [
        "npx", "hyperframes", "render", str(OUT.parent), "-o", str(video),
        "-f", str(RENDER_FPS), "-q", "delivery", "--quiet",
    ]  # fmt: skip
    subprocess.run(cmd, cwd=WORKSPACE, env=env, check=True)
    # keep the intro's own sound (SFX mixed in the original) on the new 25 fps picture
    if INTRO_MP4.exists():
        tmp = INTRO_MP4.with_suffix(".tmp.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(INTRO_MP4),
                "-map", "0:v:0", "-map", "1:a:0?", "-c:v", "copy", "-c:a", "copy",
                "-movflags", "+faststart", "-shortest", str(tmp),
            ],  # fmt: skip
            check=True,
        )
        tmp.replace(INTRO_MP4)
    else:
        shutil.copy2(video, INTRO_MP4)
    print("rendered", INTRO_MP4, f"{RENDER_FPS} fps")


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    for name in FONT_FILES:
        shutil.copy2(FONTS / name, OUT.parent / name)
    OUT.write_text(html)
    print(
        "ok", OUT, "SFX cues (s): riser 0.0, pop", S0 + f(2), "shimmer", S0 + f(24),
        "whoosh", TITLE - 0.25, "impact", TITLE + f(12),
    )  # fmt: skip
    if RENDER:
        ensure_workspace()
        render()
