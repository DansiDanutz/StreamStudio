"""Go live: the Program window streams its encoded output over a WebSocket; ffmpeg on the Mac Studio
re-encodes it (VideoToolbox when available) and pushes RTMP to YouTube (or any RTMP/RTMPS server).

The stream key is stored in <data_dir>/live.json (0600), never logged, and only shown masked."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ...core import media
from ...core.config import Settings
from ..deps import settings

router = APIRouter(prefix="/api/live", tags=["live"])

YOUTUBE = "rtmp://a.rtmp.youtube.com/live2"
URL_OK = re.compile(r"^rtmps?://[A-Za-z0-9.-]+(:\d+)?(/[\w./-]*)?$")
KEY_OK = re.compile(r"^[A-Za-z0-9_-]{4,128}$")


class LiveConfig(BaseModel):
    rtmp_url: str = Field(default=YOUTUBE, max_length=300)
    stream_key: str | None = Field(
        default=None, max_length=128, description="Leave out to keep the saved key"
    )


class LiveState:
    """One broadcast at a time (module-level: one API process per Mac Studio)."""

    def __init__(self) -> None:
        self.proc: asyncio.subprocess.Process | None = None
        self.started: float | None = None
        self.bytes = 0
        self.error: str | None = None

    def status(self) -> dict[str, Any]:
        on = self.proc is not None and self.proc.returncode is None
        return {
            "live": on,
            "seconds": int(time.time() - self.started) if on and self.started else 0,
            "bytes_in": self.bytes,
            "error": self.error,
        }


STATE = LiveState()


def _cfg_path(s: Settings) -> Path:
    return s.data_dir / "live.json"


def load_config(s: Settings) -> dict[str, str]:
    p = _cfg_path(s)
    return json.loads(p.read_text()) if p.exists() else {"rtmp_url": YOUTUBE, "stream_key": ""}


def _mask(key: str) -> str:
    return f"••••{key[-4:]}" if key else ""


def ffmpeg_cmd(s: Settings, target: str) -> list[str]:
    hw = "h264_videotoolbox" in media.hw_encoders(s.ffmpeg_bin)
    venc = (
        ["-c:v", "h264_videotoolbox", "-b:v", "6M", "-maxrate", "6M", "-bufsize", "12M",
         "-realtime", "1"]
        if hw
        else ["-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency", "-b:v", "6M",
              "-maxrate", "6M", "-bufsize", "12M"]
    )  # fmt: skip
    return [
        s.ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-fflags", "+genpts", "-i", "pipe:0",
        *venc, "-pix_fmt", "yuv420p", "-r", "30", "-g", "60", "-keyint_min", "60",
        "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2", "-f", "flv", target,
    ]  # fmt: skip


@router.get("/config")
def get_config(s: Settings = Depends(settings)) -> dict[str, Any]:
    c = load_config(s)
    return {
        "rtmp_url": c["rtmp_url"],
        "stream_key": _mask(c.get("stream_key", "")),
        "has_key": bool(c.get("stream_key")),
    }


@router.put("/config")
def put_config(body: LiveConfig, s: Settings = Depends(settings)) -> dict[str, Any]:
    url = body.rtmp_url.strip().rstrip("/")
    if not URL_OK.match(url):
        raise HTTPException(422, "the server address must be rtmp:// or rtmps://")
    c = load_config(s)
    if body.stream_key is not None:
        key = body.stream_key.strip()
        if key and not KEY_OK.match(key):
            raise HTTPException(422, "that does not look like a stream key")
        c["stream_key"] = key
    c["rtmp_url"] = url
    p = _cfg_path(s)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(c, f)
    tmp.replace(p)
    return get_config(s)


@router.get("")
def status() -> dict[str, Any]:
    return STATE.status()


@router.websocket("/ws")
async def ingest(ws: WebSocket) -> None:
    """Binary messages: the encoded stream from MediaRecorder. Closing the socket ends it."""
    s: Settings = ws.app.state.settings
    await ws.accept()
    c = load_config(s)
    if not c.get("stream_key"):
        await ws.close(code=4400, reason="no stream key saved")
        return
    if STATE.proc is not None and STATE.proc.returncode is None:
        await ws.close(code=4409, reason="already live")
        return
    target = (
        getattr(ws.app.state, "live_target_override", None) or f"{c['rtmp_url']}/{c['stream_key']}"
    )
    STATE.error, STATE.bytes, STATE.started = None, 0, time.time()
    proc = await asyncio.create_subprocess_exec(
        *ffmpeg_cmd(s, target), stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    STATE.proc = proc
    assert proc.stdin is not None
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            data = msg.get("bytes")
            if data:
                STATE.bytes += len(data)
                proc.stdin.write(data)
                await proc.stdin.drain()
            elif msg.get("text") == "stop":
                break
    except (WebSocketDisconnect, ConnectionResetError, BrokenPipeError):
        pass
    finally:
        with contextlib.suppress(Exception):
            proc.stdin.close()
            await proc.stdin.wait_closed()
        try:
            err = await asyncio.wait_for(proc.stderr.read(), timeout=15) if proc.stderr else b""
            await asyncio.wait_for(proc.wait(), timeout=15)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            err = b"ffmpeg did not stop in time"
        if proc.returncode not in (0, None) and err:
            # never echo the target URL (it contains the key)
            STATE.error = err.decode(errors="replace").replace(
                c.get("stream_key", "") or "\0", "••••"
            )[-400:]
        STATE.proc = None
        with contextlib.suppress(Exception):
            await ws.close()
