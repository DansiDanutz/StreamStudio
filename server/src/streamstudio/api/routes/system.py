from __future__ import annotations

import platform
import shutil
import sqlite3

from fastapi import APIRouter, Depends

from ... import __version__
from ...core import media
from ...core.config import Settings
from ...edl.model import EDL
from ..deps import conn, settings

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health(s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)) -> dict:
    queued = c.execute("SELECT COUNT(*) FROM jobs WHERE status = 'queued'").fetchone()[0]
    running = c.execute("SELECT COUNT(*) FROM jobs WHERE status = 'running'").fetchone()[0]
    disk = shutil.disk_usage(s.data_dir)
    return {
        "ok": True,
        "version": __version__,
        "platform": f"{platform.system()} {platform.machine()}",
        "python": platform.python_version(),
        "data_dir": str(s.data_dir),
        "disk_free_gb": round(disk.free / 1e9, 1),
        "tools": {
            "ffmpeg": media.tool_version(s.ffmpeg_bin),
            "ffprobe": media.tool_version(s.ffprobe_bin),
            "ollama": shutil.which("ollama"),
            "yt-dlp": shutil.which("yt-dlp"),
        },
        "hw_encoders": media.hw_encoders(s.ffmpeg_bin),
        "jobs": {"queued": queued, "running": running},
        "import_roots": [str(p) for p in s.allowed_import_roots()],
    }


@router.get("/edl/schema")
def edl_schema() -> dict:
    return EDL.model_json_schema()
