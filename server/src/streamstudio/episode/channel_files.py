"""Validate and store channel media by SHA-256."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from ..core.config import Settings

AUDIO = {
    ".wav": ("wav", "audio/wav"), ".mp3": ("mp3", "audio/mpeg"),
    ".flac": ("flac", "audio/flac"), ".ogg": ("ogg", "audio/ogg"),
    ".aac": ("aac", "audio/aac"), ".m4a": ("mov", "audio/mp4"),
}


IMAGE = {".png": ("PNG", "image/png"), ".jpg": ("JPEG", "image/jpeg"),
         ".jpeg": ("JPEG", "image/jpeg"), ".webp": ("WEBP", "image/webp")}
FONT = {".otf": (b"OTTO", "font/otf"), ".ttf": (b"\x00\x01\x00\x00", "font/ttf")}
INTRO_FONT = {**FONT, ".woff2": (b"wOF2", "font/woff2")}
VIDEO = {".mp4": ("mov", "video/mp4"), ".mov": ("mov", "video/quicktime")}
KINDS = {"audio": AUDIO, "image": IMAGE, "font": FONT, "intro_font": INTRO_FONT, "intro": VIDEO}
FORMATS = {**AUDIO, **IMAGE, **INTRO_FONT, **VIDEO}


def install_font(s: Settings, staged: Path, ext: str, digest: str) -> Path:
    from PIL import ImageFont

    with staged.open("rb") as stream:
        if stream.read(4) != INTRO_FONT[ext][0]:
            raise ValueError("font does not match its extension")
    try:
        ImageFont.truetype(str(staged), 32).getmask("DansLab")
    except OSError as e:
        raise ValueError("unreadable channel font") from e
    return _store(s, staged, ext, digest)


def install_image(s: Settings, staged: Path, ext: str, digest: str) -> Path:
    from PIL import Image

    try:
        with Image.open(staged) as img:
            if img.format != IMAGE[ext][0] or img.width * img.height > 40_000_000:
                raise ValueError("unsupported image format or dimensions")
            img.verify()
        with Image.open(staged) as img:
            img.load()
    except (OSError, Image.DecompressionBombError, SyntaxError) as e:
        raise ValueError("unreadable channel image") from e
    return _store(s, staged, ext, digest)


def resolve(s: Settings, digest: str) -> Path | None:
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        return None
    root = s.data_dir / "channels" / "files"
    return next((p for ext in FORMATS if (p := root / (digest + ext)).is_file()), None)


def install_intro(s: Settings, staged: Path) -> Path:
    probe = subprocess.run(
        [s.ffprobe_bin, "-v", "error", "-protocol_whitelist", "file", "-show_format",
         "-show_streams", "-of", "json", str(staged)], capture_output=True, timeout=30,
    )
    if probe.returncode:
        raise ValueError("unreadable intro video")
    info = json.loads(probe.stdout)
    streams = info.get("streams", [])
    if ("mov" not in info["format"]["format_name"].split(",")
            or not any(st["codec_type"] == "video" and not st["disposition"]["attached_pic"]
                       for st in streams)):
        raise ValueError("expected a QuickTime or MP4 movie with a video track")
    silent = not any(st["codec_type"] == "audio" for st in streams)
    generated = staged.parent / "normalized.mp4"
    args = [s.ffmpeg_bin, "-v", "error", "-nostdin", "-protocol_whitelist", "file",
            "-i", str(staged)]
    if silent:
        args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    args += ["-map", "0:V:0", "-map", "1:a:0" if silent else "0:a:0", "-vf",
             "fps=25,scale=1920:1080:force_original_aspect_ratio=decrease,"
             "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1", "-c:v", "libx264", "-crf", "18",
             "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000",
             "-ac", "2", "-af", "apad", "-shortest", "-movflags", "+faststart", str(generated)]
    if subprocess.run(args, capture_output=True, timeout=300).returncode:
        raise ValueError("could not normalize the channel intro")
    with generated.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return _store(s, generated, ".mp4", digest)


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
    return _store(s, staged, ext, digest)


def _store(s: Settings, staged: Path, ext: str, digest: str) -> Path:
    root = s.data_dir / "channels" / "files"
    root.mkdir(parents=True, exist_ok=True)
    target = root / (digest + ext)
    with contextlib.suppress(FileExistsError):
        os.link(staged, target)
    return target


def verify(s: Settings, digest: str, *, kind: str = "audio") -> Path:
    path = resolve(s, digest)
    if path is None or path.suffix not in KINDS[kind]:
        raise ValueError(f"missing channel {kind}: {digest}")
    with path.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != digest:
            raise ValueError(f"channel file failed its integrity check: {digest}")
    return path
