"""Data access for projects, assets, EDL versions and jobs."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from ..edl import EDL, new_edl
from .db import row, rows, tx
from .ids import new_id, now_iso

# ---------------------------------------------------------------- projects


def create_project(conn: sqlite3.Connection, name: str) -> dict[str, Any]:
    pid = new_id("prj")
    ts = now_iso()
    with tx(conn):
        conn.execute(
            "INSERT INTO projects (id, name, created_at, updated_at) VALUES (?,?,?,?)",
            (pid, name, ts, ts),
        )
        conn.execute(
            "INSERT INTO edl_versions (project_id, version, edl_json, message, created_at)"
            " VALUES (?,?,?,?,?)",
            (pid, 1, new_edl().model_dump_json(), "created", ts),
        )
    return get_project(conn, pid)  # type: ignore[return-value]


def list_projects(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Projects the editor owns. An episode's project row (no EDL) is excluded."""
    return rows(
        conn.execute(
            "SELECT p.*, (SELECT COUNT(*) FROM assets a WHERE a.project_id = p.id) AS asset_count"
            " FROM projects p"
            " WHERE NOT EXISTS (SELECT 1 FROM episodes e WHERE e.project_id = p.id)"
            " ORDER BY updated_at DESC"
        ).fetchall()
    )


def is_episode_project(conn: sqlite3.Connection, pid: str) -> bool:
    r = conn.execute("SELECT 1 FROM episodes WHERE project_id = ?", (pid,)).fetchone()
    return r is not None


def get_project(conn: sqlite3.Connection, pid: str) -> dict[str, Any] | None:
    return row(conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone())


def rename_project(conn: sqlite3.Connection, pid: str, name: str) -> dict[str, Any] | None:
    conn.execute(
        "UPDATE projects SET name = ?, updated_at = ? WHERE id = ?", (name, now_iso(), pid)
    )
    return get_project(conn, pid)


def delete_project(conn: sqlite3.Connection, pid: str) -> bool:
    return conn.execute("DELETE FROM projects WHERE id = ?", (pid,)).rowcount > 0


def touch_project(conn: sqlite3.Connection, pid: str) -> None:
    conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now_iso(), pid))


# ---------------------------------------------------------------- EDL


def latest_edl(conn: sqlite3.Connection, pid: str) -> tuple[int, EDL] | None:
    r = conn.execute(
        "SELECT version, edl_json FROM edl_versions WHERE project_id = ?"
        " ORDER BY version DESC LIMIT 1",
        (pid,),
    ).fetchone()
    if r is None:
        return None
    return r["version"], EDL.model_validate_json(r["edl_json"])


class VersionConflict(Exception):
    pass


def save_edl(
    conn: sqlite3.Connection, pid: str, edl: EDL, base_version: int, message: str = ""
) -> int:
    """Optimistic concurrency: the save only lands if base_version is still the latest."""
    with tx(conn):
        cur = conn.execute(
            "SELECT MAX(version) FROM edl_versions WHERE project_id = ?", (pid,)
        ).fetchone()[0]
        if cur != base_version:
            raise VersionConflict(f"latest version is {cur}, you edited {base_version}")
        v = cur + 1
        conn.execute(
            "INSERT INTO edl_versions (project_id, version, edl_json, message, created_at)"
            " VALUES (?,?,?,?,?)",
            (pid, v, edl.model_dump_json(), message, now_iso()),
        )
        conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now_iso(), pid))
    return v


def list_edl_versions(conn: sqlite3.Connection, pid: str) -> list[dict[str, Any]]:
    return rows(
        conn.execute(
            "SELECT version, message, created_at FROM edl_versions WHERE project_id = ?"
            " ORDER BY version DESC",
            (pid,),
        ).fetchall()
    )


# ---------------------------------------------------------------- assets


def create_asset(
    conn: sqlite3.Connection, pid: str, *, kind: str, name: str, path: str
) -> dict[str, Any]:
    aid = new_id("ast")
    conn.execute(
        "INSERT INTO assets (id, project_id, kind, name, path, status, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (aid, pid, kind, name, path, "pending", now_iso()),
    )
    touch_project(conn, pid)
    return get_asset(conn, aid)  # type: ignore[return-value]


def get_asset(conn: sqlite3.Connection, aid: str) -> dict[str, Any] | None:
    return row(conn.execute("SELECT * FROM assets WHERE id = ?", (aid,)).fetchone())


def list_assets(conn: sqlite3.Connection, pid: str) -> list[dict[str, Any]]:
    return rows(
        conn.execute(
            "SELECT * FROM assets WHERE project_id = ? ORDER BY created_at", (pid,)
        ).fetchall()
    )


def update_asset(conn: sqlite3.Connection, aid: str, **fields: Any) -> None:
    if "probe_json" in fields and not isinstance(fields["probe_json"], str):
        fields["probe_json"] = json.dumps(fields["probe_json"])
    cols = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE assets SET {cols} WHERE id = ?", (*fields.values(), aid))


# ---------------------------------------------------------------- jobs


def enqueue(
    conn: sqlite3.Connection,
    kind: str,
    *,
    project_id: str | None = None,
    asset_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    jid = new_id("job")
    conn.execute(
        "INSERT INTO jobs (id, kind, project_id, asset_id, payload, status, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (jid, kind, project_id, asset_id, json.dumps(payload or {}), "queued", now_iso()),
    )
    return get_job(conn, jid)  # type: ignore[return-value]


def get_job(conn: sqlite3.Connection, jid: str) -> dict[str, Any] | None:
    return row(conn.execute("SELECT * FROM jobs WHERE id = ?", (jid,)).fetchone())


def list_jobs(
    conn: sqlite3.Connection, project_id: str | None = None, limit: int = 100
) -> list[dict[str, Any]]:
    if project_id:
        rs = conn.execute(
            "SELECT * FROM jobs WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
            (project_id, limit),
        )
    else:
        rs = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
    return rows(rs.fetchall())


def claim_job(conn: sqlite3.Connection, worker_id: str) -> dict[str, Any] | None:
    with tx(conn):
        r = conn.execute(
            "SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at LIMIT 1"
        ).fetchone()
        if r is None:
            return None
        conn.execute(
            "UPDATE jobs SET status = 'running', locked_by = ?, heartbeat_at = ?,"
            " started_at = ?, attempts = attempts + 1, error = NULL WHERE id = ?",
            (worker_id, time.time(), now_iso(), r["id"]),
        )
    return get_job(conn, r["id"])


def heartbeat(
    conn: sqlite3.Connection, jid: str, progress: float | None = None, message: str | None = None
) -> None:
    sets, vals = ["heartbeat_at = ?"], [time.time()]
    if progress is not None:
        sets.append("progress = ?")
        vals.append(max(0.0, min(1.0, progress)))
    if message is not None:
        sets.append("message = ?")
        vals.append(message)
    conn.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id = ?", (*vals, jid))


def finish_job(conn: sqlite3.Connection, jid: str, result: dict[str, Any] | None = None) -> None:
    conn.execute(
        "UPDATE jobs SET status = 'done', progress = 1, result = ?, finished_at = ?,"
        " locked_by = NULL WHERE id = ?",
        (json.dumps(result or {}), now_iso(), jid),
    )


def fail_job(conn: sqlite3.Connection, jid: str, error: str, max_attempts: int) -> str:
    """Requeue if attempts remain, else mark error. Returns the new status."""
    j = get_job(conn, jid)
    status = "queued" if j and j["attempts"] < max_attempts else "error"
    conn.execute(
        "UPDATE jobs SET status = ?, error = ?, locked_by = NULL,"
        " finished_at = CASE WHEN ? = 'error' THEN ? ELSE NULL END WHERE id = ?",
        (status, error[-4000:], status, now_iso(), jid),
    )
    return status


def find_active_job(
    conn: sqlite3.Connection, kind: str, payload_id: str, field: str = "id"
) -> dict[str, Any] | None:
    """A queued or running job of `kind` whose payload `field` matches: lets a repeated request
    reuse the job instead of queueing duplicate work."""
    return row(
        conn.execute(
            "SELECT * FROM jobs WHERE kind = ? AND json_extract(payload, ?) = ?"
            " AND status IN ('queued', 'running') ORDER BY created_at LIMIT 1",
            (kind, f"$.{field}", payload_id),
        ).fetchone()
    )


def cancel_job(conn: sqlite3.Connection, jid: str) -> bool:
    return (
        conn.execute(
            "UPDATE jobs SET status = 'cancelled', finished_at = ? WHERE id = ?"
            " AND status IN ('queued', 'running')",
            (now_iso(), jid),
        ).rowcount
        > 0
    )


def requeue_stale(conn: sqlite3.Connection, timeout_s: int) -> int:
    """Jobs whose worker stopped heartbeating (crash, sleep) go back to the queue."""
    return conn.execute(
        "UPDATE jobs SET status = 'queued', locked_by = NULL"
        " WHERE status = 'running' AND heartbeat_at < ?",
        (time.time() - timeout_s,),
    ).rowcount
