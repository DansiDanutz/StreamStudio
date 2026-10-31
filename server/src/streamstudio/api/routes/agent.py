"""The artifact library and the agent bus.

Library: every artifact StreamStudio has (scenes, gestures, table objects, media, workflows,
hotspots, cues, rendered clips, recordings), each with the actions an agent can call on it.
The editor publishes the parts it owns (gestures, workflows, objects…) on load; the server adds
what it owns (scenes, clips, recordings) and keeps the last copy so the library is readable even
with the editor closed.

Bus: an agent POSTs an action to /api/agent/do; the open editor receives it over
Server-Sent Events, runs it on the stage, and posts the result back. Paid or capture actions
are never on the bus: HeyGen renders keep their confirm gate, and record / go live need a
click in the Program window.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ...core.config import Settings
from ..deps import conn, settings

router = APIRouter(prefix="/api", tags=["agent"])

DO_TIMEOUT_S = 15.0
STATE_KEYS = {
    "scene",
    "cue",
    "playing",
    "segment",
    "orientation",
    "gesture",
    "table",
    "program",
    "timeline",
}
GUIDE = Path(__file__).resolve().parents[5] / "docs" / "AGENT_GUIDE.md"


class Bus:
    def __init__(self) -> None:
        self.listeners: set[asyncio.Queue[dict]] = set()
        self.pending: dict[str, asyncio.Future[dict]] = {}
        self.state: dict[str, Any] = {}
        self.state_at: float | None = None


BUS = Bus()


class WebCatalog(BaseModel):
    artifacts: list[dict[str, Any]] = Field(max_length=2000)
    actions: list[dict[str, Any]] = Field(default_factory=list, max_length=200)


class DoIn(BaseModel):
    action: str = Field(min_length=1, max_length=64)
    args: dict[str, Any] = Field(default_factory=dict)


class ResultIn(BaseModel):
    ok: bool
    result: Any = None
    error: str | None = None


def _web_path(s: Settings) -> Path:
    return s.data_dir / "library-web.json"


def _server_artifacts(s: Settings, c) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in c.execute(
        "SELECT id, name, collection FROM scenes ORDER BY position, name"
    ).fetchall():
        out.append({
            "id": f"scene:{r['id']}", "kind": "scene", "name": r["name"],
            "description": f"Scene in {r['collection']}: a saved stage layout.",
            "actions": [{"action": "scene.activate", "args": {"id": r["id"]}}],
        })  # fmt: skip
    clips = s.assets_dir / "avatar" / "clips"
    for f in sorted(clips.glob("*.mp4")) if clips.exists() else []:
        url = f"/avatar/clips/{f.name}"
        out.append({
            "id": f"clip:{f.stem}", "kind": "clip", "name": f.stem,
            "description": "A rendered avatar clip (Dan's own lip-synced voice).",
            "url": url,
            "actions": [{"action": "segment.attach_clip", "args": {"clip": url}}],
        })  # fmt: skip
    rec = s.recordings_dir
    for f in sorted(rec.glob("rec_*.mp4"), reverse=True) if rec.exists() else []:
        out.append({
            "id": f"recording:{f.stem}", "kind": "recording", "name": f.stem,
            "description": "A finished take from the Program window (H.264/AAC MP4).",
            "url": f"/api/recordings/{f.name}", "bytes": f.stat().st_size, "actions": [],
        })  # fmt: skip
    return out


@router.get("/library")
def library(
    kind: str | None = None, q: str | None = None, s: Settings = Depends(settings), c=Depends(conn)
) -> dict[str, Any]:
    p = _web_path(s)
    web = json.loads(p.read_text()) if p.exists() else {"artifacts": [], "actions": []}
    items = [a for a in web["artifacts"] if a.get("kind") != "scene"] + _server_artifacts(s, c)
    if kind:
        items = [a for a in items if a.get("kind") == kind]
    if q:
        ql = q.lower()
        items = [a for a in items if ql in json.dumps(a).lower()]
    return {
        "editor_online": bool(BUS.listeners),
        "kinds": sorted({a["kind"] for a in items}),
        "artifacts": items,
        "actions": web.get("actions", []),
    }


@router.get("/library/{aid:path}")
def artifact(aid: str, s: Settings = Depends(settings), c=Depends(conn)) -> dict[str, Any]:
    for a in library(None, None, s, c)["artifacts"]:
        if a["id"] == aid:
            return a
    raise HTTPException(404, "no such artifact")


@router.post("/library/web", status_code=204)
def publish(body: WebCatalog, s: Settings = Depends(settings)) -> None:
    """The editor publishes what it owns: gestures, workflows, objects, hotspots, cues…"""
    p = _web_path(s)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(body.model_dump()))


# ---------------------------------------------------------------- bus


@router.get("/agent/stream")
async def stream(request: Request) -> StreamingResponse:
    """The editor listens here for agent actions (Server-Sent Events)."""
    q: asyncio.Queue[dict] = asyncio.Queue()
    BUS.listeners.add(q)

    async def gen():
        try:
            yield "event: hello\ndata: {}\n\n"
            while not await request.is_disconnected():
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"event: do\ndata: {json.dumps(msg)}\n\n"
                except TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            BUS.listeners.discard(q)

    return StreamingResponse(
        gen(), media_type="text/event-stream", headers={"cache-control": "no-cache"}
    )


@router.post("/agent/do")
async def do(body: DoIn) -> dict[str, Any]:
    """Run an action on the open editor and wait for its result."""
    if not BUS.listeners:
        raise HTTPException(
            409, "the StreamStudio editor is not open: open it to run stage actions"
        )
    cid = uuid.uuid4().hex[:12]
    fut: asyncio.Future[dict] = asyncio.get_running_loop().create_future()
    BUS.pending[cid] = fut
    msg = {"id": cid, "action": body.action, "args": body.args}
    for q in list(BUS.listeners)[:1]:  # one controller runs it
        q.put_nowait(msg)
    try:
        res = await asyncio.wait_for(fut, timeout=DO_TIMEOUT_S)
    except TimeoutError as e:
        raise HTTPException(504, "the editor did not answer in time") from e
    finally:
        BUS.pending.pop(cid, None)
    if not res.get("ok"):
        raise HTTPException(422, res.get("error") or "the action failed")
    return {"id": cid, "result": res.get("result")}


@router.post("/agent/result/{cid}", status_code=204)
def result(cid: str, body: ResultIn) -> None:
    fut = BUS.pending.get(cid)
    if fut and not fut.done():
        fut.set_result(body.model_dump())


@router.get("/agent/state")
def state() -> dict[str, Any]:
    rest = {k: v for k, v in BUS.state.items() if k != "timeline"}
    return {"editor_online": bool(BUS.listeners), "updated": BUS.state_at, **rest}


@router.get("/agent/timeline")
def timeline() -> dict[str, Any]:
    """The script as a timeline (last posted by the editor): what plays when, after the rules."""
    tl = BUS.state.get("timeline")
    if tl is None:
        raise HTTPException(404, "no timeline yet: open the StreamStudio editor once")
    return {"editor_online": bool(BUS.listeners), **tl}


@router.get("/agent/guide")
def guide() -> dict[str, str]:
    """How a StreamStudio video is put together: segments, cues, rules, typical moves."""
    return {"guide": GUIDE.read_text() if GUIDE.exists() else "docs/AGENT_GUIDE.md is missing"}


@router.post("/agent/state", status_code=204)
def post_state(body: dict[str, Any]) -> None:
    BUS.state = {k: v for k, v in body.items() if k in STATE_KEYS}
    BUS.state_at = time.time()
