"""Connect the YouTube channel and upload takes. Uploads are private unless the request says
otherwise; agents (MCP) can only upload private."""

from __future__ import annotations

import html
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from ...core import store, youtube
from ...core.config import Settings
from ...core.db import tx
from ..deps import conn, settings
from .recordings import _check

router = APIRouter(tags=["youtube"])

#: Where Google Cloud's "Download JSON" lands. Tests point it elsewhere.
DOWNLOADS = Path.home() / "Downloads"


def _redirect_uri(s: Settings) -> str:
    return f"http://127.0.0.1:{s.port}/api/youtube/callback"


@router.get("/api/youtube")
def get_status(s: Settings = Depends(settings)) -> dict:
    return {**youtube.status(s.data_dir), "download_ready": bool(youtube.find_download(DOWNLOADS))}


@router.post("/api/youtube/client")
def import_client(s: Settings = Depends(settings)) -> dict:
    """Move the newest client_secret_*.json from Downloads into StreamStudio's private folder."""
    src = youtube.find_download(DOWNLOADS)
    if not src:
        raise HTTPException(404, "no client_secret_*.json in Downloads: click Download JSON first")
    try:
        return youtube.import_client(s.data_dir, src)
    except youtube.YouTubeError as e:
        raise HTTPException(422, str(e)) from e


@router.get("/api/youtube/connect")
def connect(s: Settings = Depends(settings)) -> RedirectResponse:
    try:
        return RedirectResponse(youtube.auth_url(s.data_dir, _redirect_uri(s)), status_code=302)
    except youtube.YouTubeError as e:
        raise HTTPException(409, str(e)) from e


def _page(title: str, text: str, status: int = 200) -> HTMLResponse:
    body = (f"<!doctype html><meta charset=utf-8><title>{html.escape(title)}</title>"
            f"<body style='font:16px system-ui;background:#111;color:#eee;padding:40px'>"
            f"<h2>{html.escape(title)}</h2><p>{html.escape(text)}</p>")  # fmt: skip
    return HTMLResponse(body, status_code=status)


@router.get("/api/youtube/callback")
def callback(
    state: str = "", code: str = "", error: str = "", s: Settings = Depends(settings)
) -> HTMLResponse:
    if error or not code:
        return _page("YouTube not connected", error or "Google sent no code.", 400)
    try:
        got = youtube.finish_auth(s.data_dir, state, code, expected_channel=s.youtube_channel)
    except youtube.YouTubeError as e:
        return _page("YouTube not connected", str(e), 400)
    name = (got["channel"] or {}).get("title") or "your channel"
    return _page("YouTube connected", f"StreamStudio can now upload to {name}. Close this tab.")


@router.post("/api/youtube/disconnect")
def disconnect(s: Settings = Depends(settings)) -> dict:
    youtube.disconnect(s.data_dir)
    return youtube.status(s.data_dir)


class UploadIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=20000)
    tags: list[str] = Field(default_factory=list, max_length=100)
    privacy: str = "private"


@router.post("/api/recordings/{rid}/youtube", status_code=202)
def queue_upload(
    rid: str, body: UploadIn, s: Settings = Depends(settings),
    c: sqlite3.Connection = Depends(conn),
) -> dict:  # fmt: skip
    _check(rid)
    if not (s.recordings_dir / f"{rid}.mp4").exists():
        raise HTTPException(404, "no MP4 for this take yet")
    if not youtube.status(s.data_dir)["connected"]:
        raise HTTPException(409, "YouTube is not connected: Connect the channel first")
    try:
        meta = youtube.clean_meta(body.title, body.description, body.tags, body.privacy)
    except youtube.YouTubeError as e:
        raise HTTPException(422, str(e)) from e
    with tx(c):
        job = store.find_active_job(c, "youtube_upload", rid) or store.enqueue(
            c, "youtube_upload", payload={"id": rid, "meta": meta}
        )
    return {"id": rid, "job_id": job["id"], "privacy": meta["privacy"]}
