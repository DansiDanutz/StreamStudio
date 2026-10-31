"""Scenes: reusable stage sets saved on the Mac Studio (the browser keeps a local copy).

A scene is opaque JSON for the server (the web app owns its shape); the server stores it
with its name, collection and order so every device sees the same scene library."""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...core.db import rows, tx
from ...core.ids import now_iso
from ..deps import conn

router = APIRouter(prefix="/api/scenes", tags=["scenes"])

SCENE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAX_SCENE_BYTES = 256_000


class SceneIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    collection: str = Field(default="Talk", min_length=1, max_length=40)
    position: float = 0
    data: dict[str, Any]


def _out(r: dict[str, Any]) -> dict[str, Any]:
    data = json.loads(r.pop("data_json"))
    return {**data, **r}


def _check_id(sid: str) -> None:
    if not SCENE_ID.match(sid):
        raise HTTPException(422, "bad scene id")


@router.get("")
def list_scenes(c: sqlite3.Connection = Depends(conn)) -> list[dict[str, Any]]:
    rs = rows(c.execute("SELECT * FROM scenes ORDER BY position, name").fetchall())
    return [_out(r) for r in rs]


@router.put("/{sid}")
def put_scene(sid: str, body: SceneIn, c: sqlite3.Connection = Depends(conn)) -> dict[str, Any]:
    """Create or replace a scene (idempotent)."""
    _check_id(sid)
    data = {k: v for k, v in body.data.items() if k not in {"id", "name", "collection", "position"}}
    blob = json.dumps(data, separators=(",", ":"))
    if len(blob) > MAX_SCENE_BYTES:
        raise HTTPException(413, "scene too large (media must be URLs, not inline data)")
    with tx(c):
        c.execute(
            "INSERT INTO scenes (id, name, collection, position, data_json, updated_at)"
            " VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,"
            " collection=excluded.collection, position=excluded.position,"
            " data_json=excluded.data_json, updated_at=excluded.updated_at",
            (sid, body.name.strip(), body.collection.strip(), body.position, blob, now_iso()),
        )
    r = c.execute("SELECT * FROM scenes WHERE id = ?", (sid,)).fetchone()
    return _out(dict(r))


@router.delete("/{sid}", status_code=204)
def delete_scene(sid: str, c: sqlite3.Connection = Depends(conn)) -> None:
    _check_id(sid)
    with tx(c):
        c.execute("DELETE FROM scenes WHERE id = ?", (sid,))  # idempotent: 204 even if absent
