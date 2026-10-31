"""Job handlers. Each handler gets a JobContext and returns a JSON-able result dict.

Add a handler by decorating it with @handler("kind"). Handlers must be idempotent:
a crashed job is retried from the start.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core import media, store
from ..core.config import Settings


@dataclass
class JobContext:
    job: dict[str, Any]
    conn: sqlite3.Connection
    settings: Settings

    def progress(self, p: float, message: str | None = None) -> None:
        store.heartbeat(self.conn, self.job["id"], p, message)

    def cancelled(self) -> bool:
        j = store.get_job(self.conn, self.job["id"])
        return bool(j and j["status"] == "cancelled")


Handler = Callable[[JobContext], dict[str, Any]]
HANDLERS: dict[str, Handler] = {}


def handler(kind: str) -> Callable[[Handler], Handler]:
    def wrap(fn: Handler) -> Handler:
        HANDLERS[kind] = fn
        return fn

    return wrap


@handler("probe")
def probe_asset(ctx: JobContext) -> dict[str, Any]:
    asset = store.get_asset(ctx.conn, ctx.job["asset_id"])
    if asset is None:
        raise ValueError("asset no longer exists")
    ctx.progress(0.1, "probing")
    try:
        info = media.summarize(media.probe(Path(asset["path"]), ctx.settings.ffprobe_bin))
    except media.MediaError as e:
        store.update_asset(ctx.conn, asset["id"], status="error")
        raise ValueError(str(e)) from e
    store.update_asset(
        ctx.conn, asset["id"], status="ready", duration_us=info["duration_us"], probe_json=info
    )
    return info


@handler("noop")
def noop(ctx: JobContext) -> dict[str, Any]:
    """Used by tests and the health page to prove the worker is alive."""
    ctx.progress(0.5, "noop")
    return {"ok": True, "echo": ctx.job.get("payload")}


@handler("finish_recording")
def finish_recording(ctx: JobContext) -> dict[str, Any]:
    """Program-window take → MP4 (H.264 + AAC, -14 LUFS). Idempotent: an up-to-date MP4 is kept."""
    import subprocess

    p = ctx.job.get("payload") or {}
    if isinstance(p, str):
        import json

        p = json.loads(p)
    d = ctx.settings.recordings_dir
    src = d / p["source"]
    if not src.exists() or src.parent != d:
        raise ValueError("source recording is missing")
    dst = d / f"{p['id']}.mp4"
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return {"mp4": dst.name, "skipped": True}
    hw = "h264_videotoolbox" in media.hw_encoders(ctx.settings.ffmpeg_bin)
    venc = (
        ["-c:v", "h264_videotoolbox", "-b:v", "16M"]
        if hw
        else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"]
    )
    tmp = dst.with_suffix(".tmp.mp4")
    ctx.progress(0.1, "encoding")
    subprocess.run(
        [ctx.settings.ffmpeg_bin, "-v", "error", "-y", "-i", str(src), *venc, "-pix_fmt", "yuv420p",
         "-r", "30", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k",
         "-ar", "48000", "-movflags", "+faststart", str(tmp)],
        check=True,
    )  # fmt: skip
    tmp.replace(dst)
    return {"mp4": dst.name, "encoder": "videotoolbox" if hw else "x264"}
