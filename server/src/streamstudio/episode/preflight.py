"""What the episode factory needs on this machine, checked without importing any of it.

``check(s, stage)`` looks only at paths, ``PATH`` and importable package names
(``importlib.util.find_spec``), never importing OpenCV, rembg or Playwright, so it is safe to call
from the API's health route on a base install.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

from ..core.config import Settings

#: Font files every card and the intro reference, under ``assets/brand/fonts``.
FONTS = (
    "newsreader-latin-500-normal.woff2",
    "newsreader-latin-600-normal.woff2",
    "newsreader-latin-500-italic.woff2",
    "jetbrains-mono-latin-500-normal.woff2",
    "inter-latin-400-normal.woff2",
    "inter-latin-500-normal.woff2",
    "inter-latin-600-normal.woff2",
    "inter-latin-700-normal.woff2",
)

#: Relative to ``assets_dir``.
INTRO = "brand/danslab-intro.mp4"
PLATE = "studio/plate-landscape-final.png"
PLATE_JSON = "studio/plate-landscape-final.json"
MUSIC_MANIFEST = "brand/manifest.json"
HAAR_CASCADE = "models/haarcascade_frontalface_default.xml"

#: The HyperFrames workspace (``package.json`` plus ``node_modules``) lives under ``cards_dir``.
WORKSPACE_MARKER = "node_modules/hyperframes/package.json"


def _pkg(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def playwright_chromium(s: Settings) -> Path | None:
    """The Chromium HyperFrames and the capture use: the configured path, else Playwright's own."""
    if s.hyperframes_browser is not None:
        return s.hyperframes_browser if s.hyperframes_browser.exists() else None
    if not _pkg("playwright"):
        return None
    # Playwright's download folder; it does not have to be imported to be found.
    home = Path.home()
    roots = [home / ".cache" / "ms-playwright", home / "Library" / "Caches" / "ms-playwright"]
    for root in roots:
        for d in sorted(root.glob("chromium-*"), reverse=True):
            for exe in (
                d / "chrome-mac-arm64" / "Chromium.app" / "Contents" / "MacOS" / "Chromium",
                d / "chrome-mac" / "Chromium.app" / "Contents" / "MacOS" / "Chromium",
                d / "chrome-linux" / "chrome",
                d / "chrome-linux64" / "chrome",
            ):
                if exe.exists():
                    return exe
    return None


def hyperframes_workspace(s: Settings) -> Path | None:
    marker = s.cards_dir / WORKSPACE_MARKER
    return s.cards_dir if marker.exists() else None


def tools(s: Settings) -> dict[str, str | bool | None]:
    """Every tool the factory may need, as a version, a path, a flag or ``None`` when absent."""
    a = s.assets_dir
    fonts_ok = all((a / "brand" / "fonts" / f).exists() for f in FONTS)
    chromium = playwright_chromium(s)
    workspace = hyperframes_workspace(s)
    return {
        "opencv": _pkg("cv2"),
        "rembg": _pkg("rembg"),
        "playwright_chromium": str(chromium) if chromium else None,
        "hyperframes": str(workspace) if workspace else None,
        "fonts": str(a / "brand" / "fonts") if fonts_ok else None,
        "intro": str(a / INTRO) if (a / INTRO).exists() else None,
        "plate": str(a / PLATE) if (a / PLATE).exists() and (a / PLATE_JSON).exists() else None,
        "music_manifest": str(a / MUSIC_MANIFEST) if (a / MUSIC_MANIFEST).exists() else None,
        "haar_cascade": str(a / HAAR_CASCADE) if (a / HAAR_CASCADE).exists() else None,
    }


def check(s: Settings, stage: int = 1) -> dict:
    """``{ok, missing}`` for the tools the shipped stage needs.

    Stage 1: ffmpeg, ffprobe, rembg, fonts, intro, plate, music manifest.
    Stage 2 adds whisper and the Haar cascade. Stage 3 adds Playwright Chromium and the
    HyperFrames workspace. ``missing`` names tools, not files, so the health page can show it.
    """
    t = tools(s)
    missing: list[str] = []
    if not shutil.which(s.ffmpeg_bin):
        missing.append("ffmpeg")
    if not shutil.which(s.ffprobe_bin):
        missing.append("ffprobe")
    for name in ("rembg", "fonts", "intro", "plate", "music_manifest"):
        if not t[name]:
            missing.append(name)
    if stage >= 2:
        if not shutil.which(s.whisper_bin):
            missing.append("whisper")
        if not t["haar_cascade"]:
            missing.append("haar_cascade")
    if stage >= 3:
        if not t["playwright_chromium"]:
            missing.append("playwright_chromium")
        if not t["hyperframes"]:
            missing.append("hyperframes")
    return {"ok": not missing, "missing": missing}
