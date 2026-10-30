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
