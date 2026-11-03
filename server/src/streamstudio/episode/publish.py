"""Publish: the private YouTube video goes public (now, or scheduled from Stage 2), and the
Purge button's handler. Stage 2 adds `refresh_status`."""

from __future__ import annotations

import datetime as dt
import shutil
import sqlite3
from typing import Any

from ..core import youtube
from ..core.config import Settings
from . import record

#: Tests replace this; the worker's `handlers.YOUTUBE_TRANSPORT` is used otherwise.
YOUTUBE_TRANSPORT = None


def _transport():
    if YOUTUBE_TRANSPORT is not None:
        return YOUTUBE_TRANSPORT
    from ..worker import handlers

    return handlers.YOUTUBE_TRANSPORT


def publish(
    conn: sqlite3.Connection, s: Settings, ep: record.Episode, publish_at: str | None
) -> dict[str, Any]:
    """Called by the route inside its transaction, from `uploaded_private`."""
    out = ep.record["outputs"]
    video_id = out.get("youtube_video_id")
    if not video_id:
        raise youtube.YouTubeError("the episode has no YouTube video id yet")
    api = youtube.Client(s.data_dir, out["channel"], _transport())
    st = youtube.set_status(api, video_id, "public", publish_at)
    ep.record["last_checked_at"] = None
    if publish_at:
        out["publish_at"] = st.get("publish_at") or publish_at
        record.set_status(ep, "scheduled", f"scheduled for {out['publish_at']}")
    else:
        out["publish_at"] = None
        record.set_status(ep, "published", f"published: https://youtu.be/{video_id}")
    return st


def refresh_status(s: Settings, ep: record.Episode) -> bool:
    """Check the remote state at most once per five minutes while holding the episode lock."""
    now = dt.datetime.now(dt.UTC)
    last = ep.record.get("last_checked_at")
    if last and (now - dt.datetime.fromisoformat(last)).total_seconds() < 300:
        return False
    out = ep.record["outputs"]
    api = youtube.Client(s.data_dir, out["channel"], _transport())
    observed = youtube.video_status(api, out["youtube_video_id"])
    ep.record["last_checked_at"] = now.isoformat()
    if observed["privacy"] == "public":
        record.set_status(ep, "published", "YouTube confirms the video is public")
    elif observed["publish_at"]:
        out["publish_at"] = observed["publish_at"]
        if ep.status != "scheduled":
            record.set_status(ep, "scheduled", "YouTube reports a scheduled release")
    if ep.status == "scheduled" and now >= dt.datetime.fromisoformat(out["publish_at"]):
        record.log(ep, "refresh", "scheduled release did not happen")
    return True


#: Directories the purge removes; the final video, kit and captions stay.
WORKINGS = ("caps", "cards", "scenes", "qa", "mix")


def purge(s: Settings, ep: record.Episode) -> dict[str, Any]:
    """Remove the workings, write the archive export, keep what matters. Idempotent."""
    d = record.episode_dir(s, ep.id)
    freed = 0
    for name in WORKINGS:
        p = d / name
        if p.is_dir():
            freed += sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
            shutil.rmtree(p, ignore_errors=True)
    for f in d.glob("*.tmp*"):
        freed += f.stat().st_size
        f.unlink(missing_ok=True)
    record.export(s, ep)
    return {"freed_bytes": freed}
