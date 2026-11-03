"""Validate and store local channel audio by SHA-256."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from ..core.config import Settings

FORMATS = {
    ".wav": ("wav", "audio/wav"), ".mp3": ("mp3", "audio/mpeg"),
    ".flac": ("flac", "audio/flac"), ".ogg": ("ogg", "audio/ogg"),
    ".aac": ("aac", "audio/aac"), ".m4a": ("mov", "audio/mp4"),
}


def resolve(s: Settings, digest: str) -> Path | None:
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        return None
    root = s.data_dir / "channels" / "files"
    return next((p for ext in FORMATS if (p := root / (digest + ext)).is_file()), None)


def install_audio(s: Settings, staged: Path, ext: str, digest: str) -> Path:
    probe = subprocess.run(
        [s.ffprobe_bin, "-v", "error", "-protocol_whitelist", "file", "-show_format",
         "-show_streams", "-of", "json", str(staged)], capture_output=True, timeout=30,
    )
    if probe.returncode:
        raise ValueError("unreadable audio")
    info = json.loads(probe.stdout)
    streams = info.get("streams", [])
    if (FORMATS[ext][0] not in info["format"]["format_name"].split(",") or not streams
            or not all(stream["codec_type"] == "audio" for stream in streams)
            or float(info["format"].get("duration", 0)) <= 0):
        raise ValueError("audio contents do not match the selected format")
    root = s.data_dir / "channels" / "files"
    root.mkdir(parents=True, exist_ok=True)
    target = root / (digest + ext)
    with contextlib.suppress(FileExistsError):
        os.link(staged, target)
    return target


def verify(s: Settings, digest: str) -> Path:
    path = resolve(s, digest)
    if path is None:
        raise ValueError(f"channel audio is missing: {digest}")
    with path.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != digest:
            raise ValueError(f"channel audio failed its integrity check: {digest}")
    return path
