from __future__ import annotations

import platform
import shutil
import sqlite3
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends

from ... import __version__
from ...core import media, transcribe
from ...core.config import Settings
from ...edl.model import EDL
from ...episode import preflight
from ..deps import conn, settings

router = APIRouter(prefix="/api", tags=["system"])

#: The checkout this server runs from (server/src/streamstudio/api/routes → repo root).
ROOT = Path(__file__).resolve().parents[5]


def _git_head() -> str | None:
    """The checkout's current git revision (changes on pull)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=3
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() or None


#: The revision this server process started with: the code it is actually running. Captured at
#: import, so a `git pull` after start can't make an old server look current.
STARTUP_REV = _git_head()


@router.get("/health")
def health(s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)) -> dict:
    queued = c.execute("SELECT COUNT(*) FROM jobs WHERE status = 'queued'").fetchone()[0]
    running = c.execute("SELECT COUNT(*) FROM jobs WHERE status = 'running'").fetchone()[0]
    disk = shutil.disk_usage(s.data_dir)
    head = _git_head()
    pre = preflight.check(s)
    return {
        "ok": True,
        "version": __version__,
        # rev: the code running; head: the checkout on disk. They differ after a pull: restart.
        "rev": STARTUP_REV,
        "head": head,
        "stale": bool(STARTUP_REV and head and head != STARTUP_REV),
        "root": str(ROOT),
        "platform": f"{platform.system()} {platform.machine()}",
        "python": platform.python_version(),
        "data_dir": str(s.data_dir),
        "disk_free_gb": round(disk.free / 1e9, 1),
        "tools": {
            "ffmpeg": media.tool_version(s.ffmpeg_bin),
            "ffprobe": media.tool_version(s.ffprobe_bin),
            "ollama": shutil.which("ollama"),
            "yt-dlp": shutil.which("yt-dlp"),
            "whisper": transcribe.whisper_status(s),
            # episode factory (Stage 1 needs; see episode.preflight.check)
            **preflight.tools(s),
        },
        "preflight_ok": pre["ok"],
        "missing": pre["missing"],
        "hw_encoders": media.hw_encoders(s.ffmpeg_bin),
        "jobs": {"queued": queued, "running": running},
        "import_roots": [str(p) for p in s.allowed_import_roots()],
    }


@router.get("/edl/schema")
def edl_schema() -> dict:
    return EDL.model_json_schema()
