"""ffmpeg / ffprobe helpers."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".flv", ".ts", ".mts"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


class MediaError(RuntimeError):
    pass


def kind_for(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext in VIDEO_EXT:
        return "video"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in IMAGE_EXT:
        return "image"
    return None


def probe(path: Path, ffprobe_bin: str = "ffprobe") -> dict[str, Any]:
    cmd = [
        ffprobe_bin, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]  # fmt: skip
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=120)
    except FileNotFoundError as e:
        raise MediaError(f"{ffprobe_bin} not found — install ffmpeg") from e
    except subprocess.CalledProcessError as e:
        raise MediaError(f"ffprobe failed: {e.stderr.strip()[-500:]}") from e
    return json.loads(out.stdout)


def summarize(info: dict[str, Any]) -> dict[str, Any]:
    """The handful of fields the app actually uses."""
    fmt = info.get("format", {})
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    dur = float(fmt.get("duration") or (v or a or {}).get("duration") or 0)
    out: dict[str, Any] = {
        "duration_us": round(dur * 1_000_000),
        "container": fmt.get("format_name"),
        "size_bytes": int(fmt.get("size") or 0),
        "bit_rate": int(fmt.get("bit_rate") or 0),
    }
    if v:
        num, _, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/1").partition("/")
        out["video"] = {
            "codec": v.get("codec_name"),
            "width": v.get("width"),
            "height": v.get("height"),
            "fps_num": int(num or 0),
            "fps_den": int(den or 1) or 1,
            "pix_fmt": v.get("pix_fmt"),
        }
    if a:
        out["audio"] = {
            "codec": a.get("codec_name"),
            "sample_rate": int(a.get("sample_rate") or 0),
            "channels": a.get("channels"),
        }
    return out


def tool_version(binary: str) -> str | None:
    if not shutil.which(binary):
        return None
    try:
        out = subprocess.run([binary, "-version"], capture_output=True, text=True, timeout=10)
        return out.stdout.splitlines()[0] if out.stdout else None
    except Exception:
        return None


def hw_encoders(ffmpeg_bin: str = "ffmpeg") -> list[str]:
    """Hardware encoders available (VideoToolbox on the Mac Studio)."""
    if not shutil.which(ffmpeg_bin):
        return []
    try:
        out = subprocess.run(
            [ffmpeg_bin, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=10
        ).stdout
    except Exception:
        return []
    return sorted(
        w for line in out.splitlines() for w in line.split()[1:2]
        if any(h in w for h in ("videotoolbox", "nvenc", "qsv", "vaapi"))
    )  # fmt: skip
