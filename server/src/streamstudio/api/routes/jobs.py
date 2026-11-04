from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...core import store
from ..deps import conn

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

#: Free, local work. Uploads and paid renders start only from their own routes, behind a click.
OPEN_KINDS = ("noop", "probe", "transcribe")


class JobIn(BaseModel):
    kind: str
    project_id: str | None = None
    asset_id: str | None = None
    payload: dict = {}


@router.get("")
def list_jobs(project_id: str | None = None, c: sqlite3.Connection = Depends(conn)) -> list[dict]:
    return store.list_jobs(c, project_id)


@router.post("", status_code=201)
def create_job(body: JobIn, c: sqlite3.Connection = Depends(conn)) -> dict:
    if body.kind not in OPEN_KINDS:
        raise HTTPException(403, f"job kind {body.kind} cannot be queued here; use its own route")
    return store.enqueue(
        c, body.kind, project_id=body.project_id, asset_id=body.asset_id, payload=body.payload
    )


@router.get("/{jid}")
def get_job(jid: str, c: sqlite3.Connection = Depends(conn)) -> dict:
    j = store.get_job(c, jid)
    if j is None:
        raise HTTPException(404, "job not found")
    return j


@router.post("/{jid}/cancel")
def cancel(jid: str, c: sqlite3.Connection = Depends(conn)) -> dict:
    if not store.cancel_job(c, jid):
        raise HTTPException(409, "job is not queued or running")
    return store.get_job(c, jid)  # type: ignore[return-value]
