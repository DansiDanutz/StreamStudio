"""HeyGen: render Dan's avatar clips (script lines and silent gestures) from the Director.

Paid. `POST /api/heygen/render` without `confirm: true` only returns the estimate; with it, one
idempotent job per clip is queued. The API key is pasted by Dan in the editor, stored in
<data_dir>/heygen.json (0600), and only ever returned masked."""

from __future__ import annotations

import re
import sqlite3
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...core import heygen, store
from ...core.config import Settings
from ...core.db import tx
from ..deps import conn, settings

router = APIRouter(prefix="/api/heygen", tags=["heygen"])

KEY_OK = re.compile(r"^[A-Za-z0-9_\-=.]{16,256}$")
ID_OK = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
GESTURE_OK = re.compile(r"^[a-z-]{3,32}$")
WORDS_PER_S = 2.5  # ~150 wpm, for the estimate


class ConfigIn(BaseModel):
    api_key: str | None = Field(default=None, max_length=256)
    avatar_id: str | None = Field(default=None, max_length=80)
    voice_id: str | None = Field(default=None, max_length=80)
    look_name: str | None = Field(default=None, max_length=120)


class Item(BaseModel):
    kind: Literal["segment", "gesture"]
    script: str | None = Field(default=None, max_length=1500)
    silent_s: float | None = Field(default=None, ge=1, le=10)
    motion: str | None = Field(default=None, max_length=400)
    gesture: str | None = None
    segment_id: str | None = Field(default=None, max_length=80)


class RenderIn(BaseModel):
    items: list[Item] = Field(min_length=1, max_length=60)
    confirm: bool = False


def _public(cfg: dict[str, str]) -> dict[str, Any]:
    return {
        "has_key": bool(cfg["api_key"]),
        "api_key": heygen.mask(cfg["api_key"]),
        "avatar_id": cfg["avatar_id"],
        "voice_id": cfg["voice_id"],
        "look_name": cfg["look_name"],
    }


def _client(s: Settings) -> heygen.Client:
    try:
        return heygen.Client(heygen.load_config(s.data_dir)["api_key"], _transport())
    except heygen.HeyGenError as e:
        raise HTTPException(400, str(e)) from e


def _transport():  # tests swap the network
    from ...worker import handlers

    return handlers.HEYGEN_TRANSPORT


@router.get("/config")
def get_config(s: Settings = Depends(settings)) -> dict[str, Any]:
    return _public(heygen.load_config(s.data_dir))


@router.put("/config")
def put_config(body: ConfigIn, s: Settings = Depends(settings)) -> dict[str, Any]:
    cfg = heygen.load_config(s.data_dir)
    if body.api_key is not None:
        k = body.api_key.strip()
        if k and not KEY_OK.match(k):
            raise HTTPException(422, "that does not look like a HeyGen API key")
        cfg["api_key"] = k
    for f in ("avatar_id", "voice_id"):
        v = getattr(body, f)
        if v is not None:
            if v and not ID_OK.match(v):
                raise HTTPException(422, f"bad {f}")
            cfg[f] = v
    if body.look_name is not None:
        cfg["look_name"] = body.look_name.strip()
    heygen.save_config(s.data_dir, cfg)
    return _public(cfg)


@router.get("/account")
def account(s: Settings = Depends(settings)) -> dict[str, Any]:
    """Credit balance, so the editor can show it next to every render button."""
    try:
        me = _client(s).me()
    except heygen.HeyGenError as e:
        raise HTTPException(502, str(e)) from e
    bt = me.get("billing_type")
    sub = (me.get("subscription") or {}).get("credits") or {}
    return {
        "billing_type": bt,
        "premium_remaining": (sub.get("premium_credits") or {}).get("remaining"),
        "resets_at": (sub.get("premium_credits") or {}).get("resets_at"),
        "wallet_remaining": (me.get("wallet") or {}).get("remaining_balance"),
        "spending_usd": (me.get("usage_based") or {}).get("spending_current_usd"),
    }


@router.get("/looks")
def looks(s: Settings = Depends(settings)) -> list[dict[str, Any]]:
    try:
        return [
            {
                k: x.get(k)
                for k in ("id", "name", "avatar_type", "default_voice_id", "preview_image_url")
            }
            for x in _client(s).looks()
        ]
    except heygen.HeyGenError as e:
        raise HTTPException(502, str(e)) from e


def _seconds(it: Item) -> float:
    if it.silent_s:
        return it.silent_s
    return max(2.0, len((it.script or "").split()) / WORDS_PER_S + 0.6)


@router.post("/render")
def render(
    body: RenderIn, s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)
) -> dict:
    cfg = heygen.load_config(s.data_dir)
    if not cfg["api_key"] or not cfg["avatar_id"]:
        raise HTTPException(400, "save the HeyGen API key and pick a look first")
    planned, ready = [], []
    for it in body.items:
        if it.kind == "gesture" and not (it.gesture and GESTURE_OK.match(it.gesture)):
            raise HTTPException(422, "a gesture item needs a gesture id")
        if it.kind == "segment" and not (it.script or "").strip():
            raise HTTPException(422, "a segment item needs a script")
        silent = it.silent_s if it.kind == "gesture" else None
        script = None if silent else (it.script or "").strip()
        key = heygen.item_key(cfg["avatar_id"], cfg["voice_id"], script, it.motion, silent)
        name = it.gesture if it.kind == "gesture" else key
        folder = "gestures" if it.kind == "gesture" else "clips"
        entry = {
            "key": key, "kind": it.kind, "gesture": it.gesture, "segment_id": it.segment_id,
            "clip": f"/avatar/{folder}/{name}.mp4", "seconds": round(_seconds(it), 1),
        }  # fmt: skip
        if (s.assets_dir / "avatar" / folder / f"{name}.mp4").exists():
            ready.append(entry)
        else:
            payload = {
                **entry, "script": script, "silent_s": silent, "motion": it.motion,
                "look": cfg["avatar_id"], "voice": cfg["voice_id"],
            }  # fmt: skip
            planned.append((entry, payload))
    seconds = round(sum(e["seconds"] for e, _ in planned), 1)
    out: dict[str, Any] = {
        "seconds": seconds,
        "clips": len(planned),
        "with_motion": sum(1 for _, p in planned if p["motion"]),
        "ready": ready,
        "jobs": [],
    }
    if not body.confirm or not planned:
        return out
    with tx(c):
        for entry, payload in planned:
            job = store.enqueue(c, "heygen_clip", payload=payload)
            out["jobs"].append({**entry, "job_id": job["id"]})
    return out
