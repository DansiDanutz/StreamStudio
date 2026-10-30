from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from fastapi import HTTPException, Request

from ..core import db, store
from ..core.config import Settings


def settings(request: Request) -> Settings:
    return request.app.state.settings


def conn(request: Request) -> Iterator[sqlite3.Connection]:
    c = db.connect(request.app.state.settings.db_path)
    try:
        yield c
    finally:
        c.close()


def project_or_404(c: sqlite3.Connection, pid: str) -> dict:
    p = store.get_project(c, pid)
    if p is None:
        raise HTTPException(404, "project not found")
    return p
