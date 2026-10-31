"""SQLite storage. Plain sqlite3, WAL mode, forward-only migrations."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

MIGRATIONS: list[str] = [
    # 1 — initial schema
    """
    CREATE TABLE projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE assets (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,              -- video | audio | image
        name TEXT NOT NULL,
        path TEXT NOT NULL,              -- absolute path to the original source file
        status TEXT NOT NULL,            -- pending | ready | error
        duration_us INTEGER,
        probe_json TEXT,
        created_at TEXT NOT NULL
    );
    CREATE INDEX assets_project ON assets(project_id);
    CREATE TABLE edl_versions (
        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        version INTEGER NOT NULL,
        edl_json TEXT NOT NULL,
        message TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        PRIMARY KEY (project_id, version)
    );
    CREATE TABLE jobs (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
        asset_id TEXT REFERENCES assets(id) ON DELETE CASCADE,
        payload TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL,            -- queued | running | done | error | cancelled
        progress REAL NOT NULL DEFAULT 0,
        message TEXT NOT NULL DEFAULT '',
        result TEXT,
        error TEXT,
        attempts INTEGER NOT NULL DEFAULT 0,
        locked_by TEXT,
        heartbeat_at REAL,
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT
    );
    CREATE INDEX jobs_status ON jobs(status, created_at);
    """,
    # 2 — scenes: reusable stage sets (layout + cards + media), grouped into collections
    """
    CREATE TABLE scenes (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        collection TEXT NOT NULL DEFAULT 'Talk',
        position REAL NOT NULL DEFAULT 0,
        data_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX scenes_order ON scenes(collection, position);
    """,
]


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def migrate(conn: sqlite3.Connection) -> int:
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for i, sql in enumerate(MIGRATIONS[current:], start=current + 1):
        conn.execute("BEGIN")
        try:
            for stmt in _split(sql):
                conn.execute(stmt)
            conn.execute(f"PRAGMA user_version={i}")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    return len(MIGRATIONS)


def _split(sql: str) -> list[str]:
    out = []
    for raw in sql.split(";"):
        lines = [ln.split("--", 1)[0] for ln in raw.splitlines()]
        stmt = "\n".join(lines).strip()
        if stmt:
            out.append(stmt)
    return out


@contextmanager
def tx(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    if r is None:
        return None
    d = dict(r)
    for k in ("probe_json", "payload", "result", "edl_json"):
        if k in d and isinstance(d[k], str):
            d[k] = json.loads(d[k])
    return d


def rows(rs: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row(r) for r in rs]  # type: ignore[misc]
