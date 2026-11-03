"""The episode factory's API: a script in, three clicks (approve script, approve budget, publish).

Paid: `approve-budget` is the only call that leads to HeyGen spending. It needs the one-time
`confirm_token` from the estimate screen and a browser `Origin`, runs under the row lock, and
refuses when the month would pass the ceiling. Nothing here calls HeyGen or ffmpeg; the planner
job (`episode_advance`) does the work in the worker.
"""

from __future__ import annotations

import secrets
import sqlite3
import time
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from ...core import heygen, netguard, store, youtube
from ...core.config import Settings
from ...core.db import tx
from ...core.ids import now_iso
from ...episode import ledger, preflight, record, validate
from ...episode.contract import EPISODE_ID, Script
from ..deps import conn, settings

router = APIRouter(prefix="/api/episodes", tags=["episodes"])

TOKEN_TTL_S = 10 * 60


class ApproveBudgetIn(BaseModel):
    confirm_token: str = Field(min_length=16, max_length=128)


class PublishIn(BaseModel):
    publish_at: str | None = Field(default=None, max_length=40)


def _episode(c: sqlite3.Connection, eid: str) -> record.Episode:
    if not EPISODE_ID.match(eid):
        raise HTTPException(404, "episode not found")
    ep = record.load(c, eid)
    if ep is None:
        raise HTTPException(404, "episode not found")
    return ep


def _out(s: Settings, ep: record.Episode) -> dict[str, Any]:
    return record.to_out(s, ep, validate.validate(ep.script, s))


def _live(c: sqlite3.Connection, job_id: str | None) -> bool:
    if not job_id:
        return False
    j = store.get_job(c, job_id)
    return bool(j and j["status"] in ("queued", "running"))


def _enqueue_planner(c: sqlite3.Connection, ep: record.Episode) -> dict[str, Any]:
    return store.enqueue(
        c, "episode_advance", project_id=ep.project_id, payload={"episode_id": ep.id}
    )


# ---------------------------------------------------------------- create, list, read


@router.post("", status_code=201)
def create(body: Script, s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)):
    pre = preflight.check(s, stage=1)
    if not pre["ok"]:
        raise HTTPException(503, {"missing": pre["missing"]})
    v = validate.validate(body, s)
    if v["errors"]:
        raise HTTPException(422, {"errors": v["errors"]})
    with tx(c):
        ep = record.create(c, s, body)
    return record.to_out(s, ep, v)


@router.get("")
def list_episodes(c: sqlite3.Connection = Depends(conn)) -> list[dict]:
    return record.list_episodes(c)


@router.get("/{eid}")
def get_episode(eid: str, s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)):
    """A pure read: the record without the confirm token, plus progress and validation."""
    return _out(s, _episode(c, eid))


# ---------------------------------------------------------------- script


@router.put("/{eid}/script")
def put_script(
    eid: str, body: Script, s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)
):
    """Replace the script; the episode returns to `draft`. Outputs downstream of the scenes go
    stale when the hash changes. Refused once the upload is live or done."""
    v = validate.validate(body, s)
    with tx(c):
        ep = _episode(c, eid)
        if ep.status not in record.EDITABLE or _live(c, ep.record["outputs"].get("upload_job_id")):
            raise HTTPException(409, f"the script cannot change while the episode is {ep.status}")
        old_hash = ep.record["script"].get("hash")
        new_hash = record.script_hash(body)
        ep.record["script"] = {**body.model_dump(exclude_none=True), "hash": new_hash}
        ep.title = body.title
        if new_hash != old_hash:
            d = record.episode_dir(s, ep.id)
            for name in ("final.mp4", "final.srt", "kit.json", "final.cues.json"):
                (d / name).unlink(missing_ok=True)
            for key in ("recording_id", "final_mp4", "final_srt", "kit"):
                ep.record["outputs"].pop(key, None)
            states = ep.record["scenes_state"]
            for sc in body.scenes:
                st = states.setdefault(sc.id, {"take": 0})
                st["clip_key"] = record.scene_key(s, sc, body, st.get("take", 0))
            record.log(ep, "script", "script edited; downstream outputs will be rebuilt")
        record.set_status(ep, "draft")
        record.save(c, ep)
    return record.to_out(s, ep, v)


@router.post("/{eid}/approve-script")
def approve_script(
    eid: str, s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)
):
    with tx(c):
        ep = _episode(c, eid)
        if ep.status != "draft":
            raise HTTPException(409, f"the episode is {ep.status}, not a draft")
        v = validate.validate(ep.script, s)
        if v["errors"]:
            raise HTTPException(422, {"errors": v["errors"]})
        record.set_status(ep, "script_approved", "script approved")
        record.save(c, ep)
    return record.to_out(s, ep, v)


# ---------------------------------------------------------------- the paid step


def _lines(s: Settings, c: sqlite3.Connection, ep: record.Episode) -> list[dict[str, Any]]:
    """One estimate line per distinct (clip key, take) that still costs money: every live render
    job under its own key, plus every scene with no clip and no live job for its current key."""
    script = ep.script
    lines: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sc in script.scenes:
        st = ep.scene_state(sc.id)
        take = int(st.get("take", 0))
        key = record.scene_key(s, sc, script, take)
        st["clip_key"] = key
        mp4, webm = record.clip_paths(s, key)
        live_key = st.get("job_key")  # the key the live job renders (may be an old one)
        live = _live(c, st.get("job_id"))
        seconds = heygen.estimate_seconds(sc.spoken, None)
        if live and live_key and live_key not in seen:
            seen.add(live_key)
            lines.append(
                {"scene_id": sc.id, "clip_key": live_key, "take": int(st.get("job_take", take)),
                 "job_id": st["job_id"], "script": sc.spoken, "silent_s": None,
                 "motion": script.motion, "seconds": seconds, "live": True}
            )  # fmt: skip
        if key in seen or (mp4.exists() and webm.exists()):
            continue
        if live and live_key == key:
            continue
        seen.add(key)
        lines.append({"scene_id": sc.id, "clip_key": key, "take": take, "job_id": None,
                      "script": sc.spoken, "silent_s": None, "motion": script.motion,
                      "seconds": seconds, "live": False})  # fmt: skip
    return lines


def _estimate(s: Settings, c: sqlite3.Connection, ep: record.Episode) -> dict[str, Any]:
    lines = _lines(s, c, ep)
    est = heygen.estimate(lines)
    allowance = {"attempts": s.episode_rerender_attempts, "usd": s.episode_rerender_usd}
    before = ledger.month_total(c)
    previous = ledger.unconsumed(c, ep.id)
    after = round(before - previous + est["usd"] + allowance["usd"], 2)
    return {
        **est,
        "ready": len(ep.script.scenes) - len([ln for ln in lines if not ln["live"]]),
        "lines": [
            {k: ln[k] for k in ("scene_id", "clip_key", "take", "seconds", "live")} for ln in lines
        ],
        "allowance": allowance,
        "ceiling_usd": s.heygen_month_ceiling_usd,
        "month_total_before_usd": round(before, 2),
        "month_total_after_usd": after,
        "over_ceiling": after > s.heygen_month_ceiling_usd,
        "_lines": lines,
    }


@router.get("/{eid}/estimate")
def estimate(eid: str, s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)):
    """The confirm screen: cost of what still has to render, the month after, the allowance, the
    ceiling, and a one-time token valid for ten minutes."""
    with tx(c):
        ep = _episode(c, eid)
        if ep.status != "script_approved":
            raise HTTPException(409, f"approve the script first (episode is {ep.status})")
        est = _estimate(s, c, ep)
        est.pop("_lines")
        token = secrets.token_urlsafe(24)
        ep.record["budget"]["confirm_token"] = token
        ep.record["budget"]["token_expires_at"] = time.time() + TOKEN_TTL_S
        record.save(c, ep)
    wallet = None
    cfg = heygen.load_config(s.data_dir)
    if cfg["api_key"]:
        try:
            from ...worker import handlers

            me = heygen.Client(cfg["api_key"], handlers.HEYGEN_TRANSPORT).me()
            wallet = (me.get("wallet") or {}).get("remaining_balance")
        except heygen.HeyGenError:
            wallet = None
    return {
        **est,
        "wallet_remaining_usd": wallet,
        "confirm_token": token,
        "expires_in_s": TOKEN_TTL_S,
    }


@router.post("/{eid}/approve-budget")
def approve_budget(
    eid: str,
    body: ApproveBudgetIn,
    origin: str | None = Header(default=None),
    s: Settings = Depends(settings),
    c: sqlite3.Connection = Depends(conn),
):
    """Dan's second click. Needs the token and a browser Origin; reserves the money in the ledger
    and starts the planner. Two approvals cannot both pass against the same balance: the check
    and the reservation share one transaction."""
    if origin is None or not netguard.origin_allowed(origin, s.extra_hosts):
        raise HTTPException(403, "approve the budget from the Episode page")
    with tx(c):
        ep = _episode(c, eid)
        if ep.status != "script_approved":
            raise HTTPException(409, f"approve the script first (episode is {ep.status})")
        b = ep.record["budget"]
        if (
            not b.get("confirm_token")
            or not secrets.compare_digest(b["confirm_token"], body.confirm_token)
            or (b.get("token_expires_at") or 0) < time.time()
        ):
            raise HTTPException(409, "the estimate expired: open the cost screen again")
        script = ep.script
        try:
            channel = youtube.pick_channel(s.data_dir, script.channel)
        except youtube.YouTubeError as e:
            raise HTTPException(409, str(e)) from e
        est = _estimate(s, c, ep)
        if est["over_ceiling"]:
            raise HTTPException(
                409,
                f"this episode would take the month to {est['month_total_after_usd']} USD,"
                f" over the ceiling of {s.heygen_month_ceiling_usd} USD",
            )
        lines = est.pop("_lines")
        previous = b.get("approval_id")
        approval_id = ledger.reserve(
            c, ep.id,
            [(ln["scene_id"], ln["clip_key"], ln["take"], ln["job_id"], ln["seconds"],
              round(ln["seconds"] * heygen.USD_PER_S, 4)) for ln in lines],
            est["allowance"]["usd"],
        )  # fmt: skip
        if previous:
            ledger.release(c, ep.id, previous)
        b.update(
            {"approved_at": now_iso(), "confirm_token": None, "token_expires_at": None,
             "approval_id": approval_id, "clips": est["clips"], "seconds": est["seconds"],
             "usd": est["usd"], "allowance": est["allowance"], "spent": ledger.spent(c, ep.id)}
        )  # fmt: skip
        ep.record["outputs"]["channel"] = channel
        record.set_status(
            ep, "budget_approved", f"budget approved: {est['usd']} USD for {est['clips']} clips"
        )
        record.save(c, ep)
        job = _enqueue_planner(c, ep)
    return {**_out(s, ep), "job_id": job["id"]}


# ---------------------------------------------------------------- publish, advance, purge


@router.post("/{eid}/publish")
def publish(
    eid: str,
    body: PublishIn,
    s: Settings = Depends(settings),
    c: sqlite3.Connection = Depends(conn),
):
    """Dan's third click: the private video goes public now (scheduling arrives in Stage 2)."""
    if body.publish_at:
        raise HTTPException(422, "scheduled publishing arrives in Stage 2: publish now only")
    from ...episode import publish as publish_mod

    with tx(c):
        ep = _episode(c, eid)
        if ep.status != "uploaded_private":
            raise HTTPException(409, f"nothing to publish: the episode is {ep.status}")
        try:
            publish_mod.publish(c, s, ep, None)
        except youtube.YouTubeError as e:
            raise HTTPException(502, str(e)) from e
        record.save(c, ep)
    return _out(s, ep)


@router.post("/{eid}/advance", status_code=202)
def advance(eid: str, s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)):
    """Resume after Dan acted on a `needs_dan`, or poke the planner."""
    with tx(c):
        ep = _episode(c, eid)
        if ep.status not in (*record.WORKING, "needs_dan"):
            raise HTTPException(409, f"nothing to advance: the episode is {ep.status}")
        if ep.status == "needs_dan":
            record.set_status(ep, "in_progress", "resumed by Dan")
            record.save(c, ep)
        job = _enqueue_planner(c, ep)
    return {**_out(s, ep), "job_id": job["id"]}


@router.post("/{eid}/purge", status_code=202)
def purge(eid: str, s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)):
    """The Purge button: remove the workings once the video is on YouTube (or the episode is
    cancelled). The final video, the kit and the record stay."""
    with tx(c):
        ep = _episode(c, eid)
        if ep.status not in ("published", "cancelled"):
            raise HTTPException(
                409, f"purge is for published or cancelled episodes, not {ep.status}"
            )
        existing = store.find_active_job(c, "episode_purge", ep.id, "episode_id")
        job = existing or store.enqueue(
            c, "episode_purge", project_id=ep.project_id, payload={"episode_id": ep.id}
        )
    return {**_out(s, ep), "job_id": job["id"]}
