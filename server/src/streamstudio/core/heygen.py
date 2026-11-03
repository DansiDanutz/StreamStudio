"""HeyGen API (v3) client for avatar clips: one script line (or a silent gesture) → an MP4 of Dan.

Paid: every create call spends HeyGen credits, so callers must only reach `create_video` from a job
the user started after seeing the cost (see api/routes/heygen.py). The API key lives in
<data_dir>/heygen.json (0600), is sent only to api.heygen.com, and is never logged or returned."""

from __future__ import annotations

import hashlib
import json
import os
import struct
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

API = "https://api.heygen.com"
TIMEOUT_S = 60

Transport = Callable[[urllib.request.Request], tuple[int, bytes]]


class HeyGenError(RuntimeError):
    pass


def _urlopen(req: urllib.request.Request) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:  # noqa: S310 (fixed https host)
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


# ------------------------------------------------------------------ config


def config_path(data_dir: Path) -> Path:
    return data_dir / "heygen.json"


def load_config(data_dir: Path) -> dict[str, str]:
    p = config_path(data_dir)
    base = {"api_key": "", "avatar_id": "", "voice_id": "", "look_name": ""}
    return {**base, **json.loads(p.read_text())} if p.exists() else base


def save_config(data_dir: Path, cfg: dict[str, str]) -> None:
    p = config_path(data_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(cfg, f)
    tmp.replace(p)


def mask(key: str) -> str:
    return f"••••{key[-4:]}" if key else ""


# ------------------------------------------------------------------ client


class Client:
    def __init__(self, api_key: str, transport: Transport | None = None) -> None:
        if not api_key:
            raise HeyGenError("no HeyGen API key saved")
        self.key = api_key
        self.send = transport or _urlopen

    def _call(
        self, method: str, path: str, body: bytes | None = None, ctype: str | None = None
    ) -> Any:
        req = urllib.request.Request(f"{API}{path}", data=body, method=method)
        req.add_header("x-api-key", self.key)
        req.add_header("accept", "application/json")
        if ctype:
            req.add_header("content-type", ctype)
        status, raw = self.send(req)
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            payload = {}
        if status >= 400:
            err = payload.get("error") or {}
            msg = err.get("message") or f"HTTP {status}"
            raise HeyGenError(f"HeyGen: {msg}".replace(self.key, "••••"))
        return payload.get("data", payload)

    def me(self) -> dict[str, Any]:
        return self._call("GET", "/v3/users/me")

    def looks(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        token = ""
        for _ in range(10):
            q = "?ownership=private&limit=50" + (f"&token={token}" if token else "")
            req = urllib.request.Request(f"{API}/v3/avatars/looks{q}", method="GET")
            req.add_header("x-api-key", self.key)
            status, raw = self.send(req)
            if status >= 400:
                raise HeyGenError(f"HeyGen: HTTP {status}")
            page = json.loads(raw)
            out += page.get("data", [])
            if not page.get("has_more"):
                break
            token = page.get("next_token") or ""
        return out

    def upload_asset(self, name: str, content: bytes, ctype: str) -> str:
        boundary = uuid.uuid4().hex
        body = (
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
                f"Content-Type: {ctype}\r\n\r\n"
            ).encode()
            + content
            + f"\r\n--{boundary}--\r\n".encode()
        )
        data = self._call("POST", "/v3/assets", body, f"multipart/form-data; boundary={boundary}")
        return data["asset_id"]

    def create_video(self, spec: dict[str, Any]) -> str:
        data = self._call("POST", "/v3/videos", json.dumps(spec).encode(), "application/json")
        return data["video_id"]

    def get_video(self, video_id: str) -> dict[str, Any]:
        return self._call("GET", f"/v3/videos/{video_id}")


# ------------------------------------------------------------------ specs


def silence_wav(seconds: float, rate: int = 24000) -> bytes:
    """A silent mono WAV: the audio track for a gesture clip, so the mouth stays closed."""
    n = int(seconds * rate)
    data = b"\x00\x00" * n
    return (
        b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
        + b"data" + struct.pack("<I", len(data)) + data
    )  # fmt: skip


#: HeyGen API pricing per rendered second (the number the editor's HeyGen panel shows).
USD_PER_S = 0.0385
#: About 150 words a minute, for the length estimate.
WORDS_PER_S = 2.5


def item_key(
    look: str,
    voice: str,
    script: str | None,
    motion: str | None,
    silent_s: float | None,
    take: int = 0,
) -> str:
    """Stable id for a clip: the same request never renders (or bills) twice. A re-render is a
    new take, hashed in only when above zero so every existing clip keeps its name."""
    parts: list[Any] = [look, voice, script or "", motion or "", silent_s or 0]
    if take > 0:
        parts.append(take)
    raw = json.dumps(parts, ensure_ascii=False)
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def estimate_seconds(script: str | None, silent_s: float | None) -> float:
    """Expected clip length: a silent gesture's seconds, else the words at WORDS_PER_S plus a
    lead-in, never under two seconds."""
    if silent_s:
        return float(silent_s)
    return max(2.0, len((script or "").split()) / WORDS_PER_S + 0.6)


def estimate(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Cost of rendering `items` (dicts with `script`, `silent_s`, `motion`)."""
    seconds = round(sum(estimate_seconds(i.get("script"), i.get("silent_s")) for i in items), 1)
    return {
        "seconds": seconds,
        "usd": round(seconds * USD_PER_S, 2),
        "clips": len(items),
        "with_motion": sum(1 for i in items if i.get("motion")),
    }


def video_spec(
    look: str,
    voice: str,
    *,
    script: str | None = None,
    audio_asset_id: str | None = None,
    motion: str | None = None,
    title: str = "StreamStudio",
) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "type": "avatar", "avatar_id": look, "resolution": "1080p", "aspect_ratio": "16:9",
        "title": title[:80],
    }  # fmt: skip
    if audio_asset_id:
        spec["audio_asset_id"] = audio_asset_id
    else:
        spec["script"] = script
        if voice:
            spec["voice_id"] = voice
    if motion:
        spec["motion_prompt"] = motion
    return spec
