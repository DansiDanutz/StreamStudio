"""Recordings from the Program window: the browser uploads the take, the worker turns it into an
MP4 (VideoToolbox on the Mac Studio, x264 elsewhere). Files live in <data_dir>/recordings."""

from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from ...core import store, transcribe, vault
from ...core.config import Settings
from ...core.db import tx
from ..deps import conn, settings

router = APIRouter(prefix="/api/recordings", tags=["recordings"])

REC_ID = re.compile(r"^rec_[0-9]{8}-[0-9]{6}(-[a-z0-9]{1,8})?$")
MAX_BYTES = 16 * 1024**3  # 16 GB per take
EXT = {"video/webm": ".webm", "video/mp4": ".mp4", "video/x-matroska": ".mkv"}


def _dir(s: Settings) -> Path:
    d = s.recordings_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


def _check(rid: str) -> None:
    if not REC_ID.match(rid):
        raise HTTPException(422, "bad recording id")


@router.post("", status_code=201)
async def upload(request: Request, s: Settings = Depends(settings)) -> dict:
    """Body: the raw take (video/webm or video/mp4). Streams to disk, then queues the MP4 job."""
    ctype = (request.headers.get("content-type") or "video/webm").split(";")[0].strip()
    if ctype not in EXT:
        raise HTTPException(415, f"unsupported type {ctype}")
    rid = time.strftime("rec_%Y%m%d-%H%M%S")
    d = _dir(s)
    if any(d.glob(f"{rid}.*")):
        rid += f"-{int(time.time() * 1000) % 100000:x}"
    raw = d / f"{rid}.source{EXT[ctype]}"
    part = raw.with_suffix(raw.suffix + ".part")
    size = 0
    with part.open("wb") as f:
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_BYTES:
                f.close()
                part.unlink(missing_ok=True)
                raise HTTPException(413, "recording too large")
            f.write(chunk)
    if size == 0:
        part.unlink(missing_ok=True)
        raise HTTPException(400, "empty recording")
    part.rename(raw)
    c = sqlite3.connect(s.db_path)
    c.row_factory = sqlite3.Row
    try:
        with tx(c):
            job = store.enqueue(c, "finish_recording", payload={"id": rid, "source": raw.name})
    finally:
        c.close()
    return {"id": rid, "bytes": size, "job_id": job["id"]}


@router.get("")
def list_recordings(
    s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)
) -> list[dict]:
    out = []
    for src in sorted(_dir(s).glob("rec_*.source.*"), reverse=True):
        if src.name.endswith(".part"):
            continue
        rid = src.name.split(".source")[0]
        mp4 = src.parent / f"{rid}.mp4"
        out.append({
            "id": rid,
            "source_bytes": src.stat().st_size,
            "mp4": mp4.exists(),
            "mp4_bytes": mp4.stat().st_size if mp4.exists() else None,
            "transcript": (src.parent / f"{rid}.transcript.json").exists(),
        })  # fmt: skip
    return out


@router.get("/{rid}.mp4")
def download(rid: str, s: Settings = Depends(settings)) -> FileResponse:
    _check(rid)
    f = _dir(s) / f"{rid}.mp4"
    if not f.exists():
        # only in the vault (local copy removed, or another machine): bring it back first
        try:
            got = vault.fetch(s, None, f"recordings/{rid}.mp4")
        except vault.VaultError as e:
            raise HTTPException(502, str(e)) from e
        if got is None:
            raise HTTPException(404, "not ready yet")
    return FileResponse(f, media_type="video/mp4", filename=f"streamstudio-{rid[4:]}.mp4")


@router.post("/{rid}/transcribe", status_code=202)
def queue_transcript(
    rid: str, s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)
) -> dict:
    """Transcribe a finished take locally (whisper.cpp). A repeat request reuses the queued job."""
    _check(rid)
    if not (_dir(s) / f"{rid}.mp4").exists():
        raise HTTPException(404, "no MP4 for this take yet")
    try:
        transcribe.require_whisper(s)
    except transcribe.TranscribeError as e:
        raise HTTPException(503, str(e)) from e
    with tx(c):
        job = store.find_active_job(c, "transcribe", rid) or store.enqueue(
            c, "transcribe", payload={"id": rid}
        )
    return {"id": rid, "job_id": job["id"]}


@router.get("/{rid}/transcript")
def get_transcript(rid: str, s: Settings = Depends(settings)) -> FileResponse:
    _check(rid)
    f = _dir(s) / f"{rid}.transcript.json"
    if not f.exists():
        raise HTTPException(404, "no transcript yet: POST /api/recordings/{id}/transcribe")
    return FileResponse(f, media_type="application/json")


@router.get("/{rid}.srt")
def get_captions(rid: str, s: Settings = Depends(settings)) -> FileResponse:
    _check(rid)
    f = _dir(s) / f"{rid}.srt"
    if not f.exists():
        raise HTTPException(404, "no captions yet: POST /api/recordings/{id}/transcribe")
    name = f"streamstudio-{rid[4:]}.srt"
    return FileResponse(f, media_type="application/x-subrip", filename=name)
