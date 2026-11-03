"""The HeyGen cost ledger: reservations when a budget is approved, charges when a render ends,
releases when reserved money is given back. Imports only `core`, so a worker handler may import
it inside a function body. Every function runs inside the caller's transaction.

Rows are one per estimate line. A reservation group is every row that shares an `approval_id`;
the allowance is one extra line in the group with `scene_id` NULL. A charge is unique per
(episode, clip key): the key encodes words and take, so an edited scene's old and new renders are
distinct charges, and a repeated handler run never charges twice.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from ..core.heygen import USD_PER_S
from ..core.ids import new_id, now_iso

Line = tuple[str | None, str | None, int, str | None, float, float]
"""(scene_id, clip_key, take, job_id, seconds, usd)"""


def _insert(
    conn: sqlite3.Connection,
    episode_id: str,
    kind: str,
    *,
    approval_id: str | None,
    scene_id: str | None,
    clip_key: str | None,
    take: int | None,
    job_id: str | None,
    seconds: float,
    usd: float,
    at: str,
) -> None:
    conn.execute(
        "INSERT INTO heygen_ledger (id, episode_id, approval_id, scene_id, clip_key, take, job_id,"
        " kind, seconds, usd, at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (new_id("led"), episode_id, approval_id, scene_id, clip_key, take, job_id, kind,
         round(seconds, 3), round(usd, 4), at),
    )  # fmt: skip


def reserve(
    conn: sqlite3.Connection, episode_id: str, lines: list[Line], allowance_usd: float
) -> str:
    """One reservation row per line plus the allowance line. Returns the approval id."""
    approval_id = new_id("apr")
    at = now_iso()
    for scene_id, clip_key, take, job_id, seconds, usd in lines:
        _insert(
            conn, episode_id, "reservation", approval_id=approval_id, scene_id=scene_id,
            clip_key=clip_key, take=take, job_id=job_id, seconds=seconds, usd=usd, at=at,
        )  # fmt: skip
    _insert(
        conn, episode_id, "reservation", approval_id=approval_id, scene_id=None,
        clip_key=None, take=None, job_id=None, seconds=0.0, usd=allowance_usd, at=at,
    )  # fmt: skip
    return approval_id


def charge(
    conn: sqlite3.Connection,
    episode_id: str,
    scene_id: str,
    clip_key: str,
    take: int,
    job_id: str | None,
    seconds: float,
    at: str | None = None,
) -> bool:
    """Record what a render cost. False when this clip key was already charged."""
    try:
        _insert(conn, episode_id, "charge", approval_id=None, scene_id=scene_id,
                clip_key=clip_key, take=take, job_id=job_id, seconds=seconds,
                usd=seconds * USD_PER_S, at=at or now_iso())  # fmt: skip
    except sqlite3.IntegrityError:
        return False
    return True


def latest_approval(conn: sqlite3.Connection, episode_id: str) -> dict[str, Any] | None:
    """The newest reservation group: `{approval_id, at, usd}` or None."""
    r = conn.execute(
        "SELECT approval_id, MIN(at) AS at, SUM(usd) AS usd FROM heygen_ledger"
        " WHERE episode_id = ? AND kind = 'reservation' GROUP BY approval_id"
        " ORDER BY at DESC, approval_id DESC LIMIT 1",
        (episode_id,),
    ).fetchone()
    return dict(r) if r else None


def _sum(conn: sqlite3.Connection, sql: str, args: tuple) -> float:
    return float(conn.execute(sql, args).fetchone()[0] or 0.0)


def unconsumed(conn: sqlite3.Connection, episode_id: str) -> float:
    """What is left of the episode's latest reservation: its USD minus the charges dated since
    it and the releases made against it, floored at zero."""
    group = latest_approval(conn, episode_id)
    if group is None:
        return 0.0
    charged = _sum(
        conn,
        "SELECT SUM(usd) FROM heygen_ledger WHERE episode_id = ? AND kind = 'charge' AND at >= ?",
        (episode_id, group["at"]),
    )
    released = _sum(
        conn,
        "SELECT SUM(usd) FROM heygen_ledger WHERE kind = 'release' AND approval_id = ?",
        (group["approval_id"],),
    )
    return max(0.0, group["usd"] - charged - released)


def release(
    conn: sqlite3.Connection, episode_id: str, approval_id: str, usd: float | None = None
) -> float:
    """Give back what is left of a reservation group (or `usd` of it). Returns the USD released."""
    group = conn.execute(
        "SELECT MIN(at) AS at, SUM(usd) AS usd FROM heygen_ledger"
        " WHERE episode_id = ? AND approval_id = ? AND kind = 'reservation'",
        (episode_id, approval_id),
    ).fetchone()
    if not group or group["usd"] is None:
        return 0.0
    charged = _sum(
        conn,
        "SELECT SUM(usd) FROM heygen_ledger WHERE episode_id = ? AND kind = 'charge' AND at >= ?",
        (episode_id, group["at"]),
    )
    released = _sum(
        conn,
        "SELECT SUM(usd) FROM heygen_ledger WHERE kind = 'release' AND approval_id = ?",
        (approval_id,),
    )
    left = max(0.0, group["usd"] - charged - released)
    amount = left if usd is None else max(0.0, min(usd, left))
    if amount <= 0:
        return 0.0
    _insert(conn, episode_id, "release", approval_id=approval_id, scene_id=None, clip_key=None,
            take=None, job_id=None, seconds=0.0, usd=amount, at=now_iso())  # fmt: skip
    return amount


def release_unsubmitted(
    conn: sqlite3.Connection, episode_id: str, live_keys: set[str], charged_keys: set[str]
) -> float:
    """Cancel (Stage 2): release the latest group's lines whose clip was never submitted (no live
    job and no charge). The allowance line goes with them."""
    group = latest_approval(conn, episode_id)
    if group is None:
        return 0.0
    rows = conn.execute(
        "SELECT scene_id, clip_key, usd FROM heygen_ledger WHERE approval_id = ?"
        " AND kind = 'reservation'",
        (group["approval_id"],),
    ).fetchall()
    free = sum(
        r["usd"]
        for r in rows
        if r["scene_id"] is None
        or (r["clip_key"] not in live_keys and r["clip_key"] not in charged_keys)
    )
    return release(conn, episode_id, group["approval_id"], free)


def month_total(conn: sqlite3.Connection, now: str | None = None) -> float:
    """This calendar month's charges plus the unconsumed part of every open reservation,
    whatever month each episode was created in."""
    month = (now or now_iso())[:7]
    charged = _sum(
        conn,
        "SELECT SUM(usd) FROM heygen_ledger WHERE kind = 'charge' AND substr(at, 1, 7) = ?",
        (month,),
    )
    episodes = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT episode_id FROM heygen_ledger WHERE kind = 'reservation'"
        ).fetchall()
    ]
    return round(charged + sum(unconsumed(conn, e) for e in episodes), 4)


def spent(conn: sqlite3.Connection, episode_id: str) -> dict[str, float | int]:
    """`budget.spent`: what the episode's renders have cost so far."""
    r = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(seconds), 0), COALESCE(SUM(usd), 0) FROM heygen_ledger"
        " WHERE episode_id = ? AND kind = 'charge'",
        (episode_id,),
    ).fetchone()
    return {"renders": int(r[0]), "seconds": round(r[1], 1), "usd": round(r[2], 2)}
