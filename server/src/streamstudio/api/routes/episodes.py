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
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from ...core import heygen, netguard, store, youtube
from ...core.config import Settings
from ...core.db import tx
from ...core.ids import now_iso
from ...episode import ledger, preflight, profiles, record, validate
from ...episode.contract import EPISODE_ID, SCENE_ID, ConnectedCards, Script, WebsiteDemo
from ...episode.planner import settle_cancelled
from ...episode.website_demo import CATALOG
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


def _check_pinned_files(s: Settings, ep: record.Episode) -> None:
    try:
        sound = ep.channel_settings.get("sound")
        look = ep.channel_settings.get("look")
        if sound:
            profiles.verify_sound(s, profiles.Sound.model_validate(sound))
        if look:
            profiles.verify_look(s, profiles.Look.model_validate(look))
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


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
        profiles.seed(c, s)
        slug = body.profile or profiles.default(c)
        if not profiles.get(c, slug):
            raise HTTPException(409, "channel profile not found")
        ep = record.create(c, s, body)
        ep.record["profile_slug"] = slug
        record.save(c, ep)
    return record.to_out(s, ep, v)


@router.get("")
def list_episodes(c: sqlite3.Connection = Depends(conn)) -> list[dict]:
    return record.list_episodes(c)


@router.get("/workflows")
def workflows():
    return [{**CATALOG, "schema": WebsiteDemo.model_json_schema()},
            {"id": "connected-cards/v1", "choose_when": "Explain three linked steps or components.",
             "requires": ["approved narration", "three cards with titles and explanations"],
             "schema": ConnectedCards.model_json_schema()}]


@router.put("/captures/manual", status_code=201)
async def upload_manual_capture(url: str, request: Request, origin: str | None = Header(None),
                                s: Settings = Depends(settings)):
    from PIL import Image

    from ...episode import website_demo

    if not origin or not netguard.origin_allowed(origin, s.extra_hosts):
        raise HTTPException(403, "submit the capture from the studio")
    if website_demo.capture_mode(s, url) != "manual":
        raise HTTPException(422, "this URL is not on a manual capture host")
    s.sites_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=s.sites_dir) as tmp:
        source = Path(tmp) / "upload"
        size = 0
        with source.open("wb") as stream:
            async for chunk in request.stream():
                size += len(chunk)
                if size > 25 * 1024 * 1024:
                    raise HTTPException(413, "manual screenshot exceeds 25 MiB")
                stream.write(chunk)
        try:
            digest = await run_in_threadpool(website_demo.store_manual, s, url, source)
        except (OSError, Image.DecompressionBombError, ValueError) as exc:
            raise HTTPException(422, "invalid screenshot") from exc
    return {"site": url, "manual": {"sha256": digest, "focus_x": .5, "focus_y": .5}}


@router.get("/{eid}")
def get_episode(eid: str, s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)):
    """A pure read: the record without the confirm token, plus progress and validation."""
    ep = _episode(c, eid)
    result = _out(s, ep)
    latest = profiles.get(c, ep.record.get("profile_slug", "danslab"))
    if latest and ep.record.get("profile"):
        result["profile_latest_version"] = latest["version"]
    return result


# ---------------------------------------------------------------- script


def _invalidate_final(c, s, ep):
    outputs = ep.record["outputs"]
    # These jobs write shared scene/final paths. Let them finish before invalidation.
    active_outputs = [outputs.get(field) for field in
                      ("assemble_job_id", "kit_job_id", "register_job_id")]
    active_outputs.extend(st.get("compose_job_id")
                          for st in ep.record["scenes_state"].values())
    if any(_live(c, jid) for jid in active_outputs):
        raise HTTPException(409, "the current scene or Library render is finishing")
    ep.record["revision"] = ep.record.get("revision", 0) + 1
    d = record.episode_dir(s, ep.id)
    for name in ("final.mp4", "final.srt", "kit.json", "final.cues.json"):
        (d / name).unlink(missing_ok=True)
    for key in ("recording_id", "final_mp4", "final_srt", "kit"):
        ep.record["outputs"].pop(key, None)


@router.put("/{eid}/script")
def put_script(
    eid: str, body: Script, expected_hash: str | None = None,
    s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn),
):
    """Replace the script; the episode returns to `draft`. Outputs downstream of the scenes go
    stale when the hash changes. Refused once the upload is live or done."""
    v = validate.validate(body, s)
    with tx(c):
        ep = _episode(c, eid)
        outputs = ep.record["outputs"]
        if (
            ep.status not in record.EDITABLE
            or outputs.get("upload_requested")
            or _live(c, outputs.get("upload_job_id"))
        ):
            raise HTTPException(409, f"the script cannot change while the episode is {ep.status}")
        if body.profile and body.profile != ep.record.get("profile_slug", "danslab"):
            raise HTTPException(409, "create a new episode to change its channel")
        previous_scenes = {sc.id: sc for sc in ep.script.scenes}
        old_hash = ep.record["script"].get("hash")
        if expected_hash is not None and expected_hash != old_hash:
            raise HTTPException(409, "the script changed; reload it before editing")
        new_hash = record.script_hash(body)
        ep.record["script"] = {**body.model_dump(exclude_none=True), "hash": new_hash}
        ep.title = body.title
        if new_hash != old_hash:
            _invalidate_final(c, s, ep)
            d = record.episode_dir(s, ep.id)
            states = ep.record["scenes_state"]
            render_script = ep.render_script()
            for sc in body.scenes:
                st = states.setdefault(sc.id, {"take": 0})
                key = record.scene_key(s, sc, render_script, st.get("take", 0))
                if st.get("clip_key") != key or previous_scenes.get(sc.id) != sc:
                    (d / "scenes" / f"{sc.id}.hash").unlink(missing_ok=True)
                    st["composed_hash"] = None
                st["clip_key"] = key
            record.log(ep, "script", "script edited; downstream outputs will be rebuilt")
        record.set_status(ep, "draft")
        record.save(c, ep)
    return record.to_out(s, ep, v)


class RepinIn(BaseModel):
    profile: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9-]{0,47}$")


@router.post("/{eid}/repin")
def repin(eid: str, body: RepinIn, origin: str | None = Header(default=None),
          s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)):
    if not origin or not netguard.origin_allowed(origin, s.extra_hosts):
        raise HTTPException(403, "change the pinned profile from the Episode page")
    with tx(c):
        ep = _episode(c, eid)
        out = ep.record["outputs"]
        if (ep.status not in record.EDITABLE or out.get("upload_requested")
                or _live(c, out.get("upload_job_id"))):
            raise HTTPException(409, f"cannot change profile while the episode is {ep.status}")
        slug = body.profile or ep.record.get("profile_slug", "danslab")
        if not profiles.get(c, slug):
            raise HTTPException(422, "channel profile not found")
        _invalidate_final(c, s, ep)
        if body.profile:
            script = ep.script.model_copy(update={"profile": slug})
            ep.record["script"] = {**script.model_dump(exclude_none=True),
                                   "hash": record.script_hash(script)}
        ep.record["profile_slug"] = slug
        ep.record.pop("profile", None)
        ep.record.pop("presenter_defaults", None)
        out.pop("channel", None)
        ep.record["budget"].update(confirm_token=None, token_expires_at=None)
        record.set_status(ep, "draft", "Repinned")
        record.save(c, ep)
    return _out(s, ep)


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
        if ep.record.get("profile") is None:
            profiles.seed(c, s)
            ep.record["profile"] = profiles.get(c, ep.record.get("profile_slug", "danslab"))
        if ep.record.get("presenter_defaults") is None:
            cfg = ep.record["profile"]["profile"]["presenter"]
            ep.record["presenter_defaults"] = {
                "avatar_id": cfg["avatar_id"] or ep.script.look,
                "voice_id": cfg["voice_id"] or ep.script.voice_id,
            }
        _check_pinned_files(s, ep)
        resolved = ep.render_script()
        if not resolved.look or not resolved.voice_id:
            raise HTTPException(409, "choose the presenter and voice before approving the script")
        reference = ep.record.get("reference")
        identity = [resolved.look, resolved.voice_id, resolved.motion]
        if reference and reference.get("presenter") != identity:
            ep.record["reference"] = None
        record.set_status(ep, "script_approved", "script approved")
        record.save(c, ep)
    return record.to_out(s, ep, v)


# ---------------------------------------------------------------- the paid step


def _lines(s: Settings, c: sqlite3.Connection, ep: record.Episode) -> list[dict[str, Any]]:
    """One estimate line per distinct (clip key, take) that still costs money: every live render
    job under its own key, plus every scene with no clip and no live job for its current key."""
    script = ep.render_script()
    lines: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sc in script.scenes:
        st = ep.scene_state(sc.id)
        take = int(st.get("take", 0))
        key = record.scene_key(s, sc, script, take)
        st["clip_key"] = key
        mp4, _ = record.clip_paths(s, key)
        live_key = st.get("job_key")  # the key the live job renders (may be an old one)
        live = _live(c, st.get("job_id"))
        seconds = heygen.estimate_seconds(sc.spoken, None)
        if (live and live_key and live_key not in seen
                and not record.clip_paths(s, live_key)[0].is_file()):
            seen.add(live_key)
            lines.append(
                {"scene_id": sc.id, "clip_key": live_key, "take": int(st.get("job_take", take)),
                 "job_id": st["job_id"], "script": sc.spoken, "silent_s": None,
                 "motion": script.motion, "seconds": seconds, "live": True}
            )  # fmt: skip
        if key in seen or mp4.is_file():
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
    if s.heygen_cache_only:
        allowance = {"attempts": 0, "usd": 0.0}
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


@router.get("/{eid}/cost")
def projected_cost(
    eid: str, s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)
):
    """Agent estimate. Never rotates Dan's browser token or contacts a provider."""
    with tx(c):
        ep = _episode(c, eid)
        estimate = _estimate(s, c, ep)
        estimate.pop("_lines")
        return estimate


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
        _check_pinned_files(s, ep)
        est = _estimate(s, c, ep)
        if s.heygen_cache_only and any(
            not record.clip_paths(s, line["clip_key"])[0].exists() for line in est["_lines"]
        ):
            raise HTTPException(409, "cache-only production: matching avatar footage is missing")
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
        b["retries"] = []
        b.update(
            {"approved_at": now_iso(), "confirm_token": None, "token_expires_at": None,
             "approval_id": approval_id, "clips": est["clips"], "seconds": est["seconds"],
             "usd": est["usd"], "allowance": est["allowance"], "spent": ledger.spent(c, ep.id)}
        )  # fmt: skip
        record.set_status(
            ep, "budget_approved", f"budget approved: {est['usd']} USD for {est['clips']} clips"
        )
        record.save(c, ep)
        job = _enqueue_planner(c, ep)
    return {**_out(s, ep), "job_id": job["id"]}


# ---------------------------------------------------------------- publish, advance, purge


@router.post("/{eid}/upload", status_code=202)
def upload_private(
    eid: str,
    origin: str | None = Header(default=None),
    s: Settings = Depends(settings),
    c: sqlite3.Connection = Depends(conn),
):
    if origin is None or not netguard.origin_allowed(origin, s.extra_hosts):
        raise HTTPException(403, "upload from the Episode page")
    with tx(c):
        ep = _episode(c, eid)
        if ep.status != "ready":
            raise HTTPException(409, f"the episode is {ep.status}")
        try:
            requested = ep.script.channel or ep.channel_settings.get("youtube_channel")
            channel = youtube.pick_channel(s.data_dir, requested)
        except youtube.YouTubeError as e:
            raise HTTPException(409, str(e)) from e
        ep.record["outputs"].update(channel=channel, upload_requested=True)
        record.set_status(ep, "in_progress", "private upload requested")
        record.save(c, ep)
        _enqueue_planner(c, ep)
    return _out(s, ep)


@router.post("/{eid}/publish")
def publish(
    eid: str,
    body: PublishIn,
    s: Settings = Depends(settings),
    c: sqlite3.Connection = Depends(conn),
):
    """Dan's third click: the private video goes public now (scheduling arrives in Stage 2)."""
    if body.publish_at is not None:
        try:
            youtube.rfc3339_future(body.publish_at)
        except youtube.YouTubeError as e:
            raise HTTPException(422, str(e)) from e
    from ...episode import publish as publish_mod

    with tx(c):
        ep = _episode(c, eid)
        if ep.status not in ("uploaded_private", "scheduled"):
            raise HTTPException(409, f"nothing to publish: the episode is {ep.status}")
        try:
            publish_mod.publish(c, s, ep, body.publish_at)
        except youtube.YouTubeError as e:
            raise HTTPException(502, str(e)) from e
        record.save(c, ep)
    return _out(s, ep)


@router.post("/{eid}/refresh")
def refresh(eid: str, s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)):
    from ...episode.publish import refresh_status

    with tx(c):
        ep = _episode(c, eid)
        if ep.status not in ("uploaded_private", "scheduled", "published"):
            raise HTTPException(409, "no uploaded video to check")
        if ep.status != "published":
            try:
                if refresh_status(s, ep):
                    record.save(c, ep)
            except youtube.YouTubeError as e:
                raise HTTPException(502, str(e)) from e
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


@router.post("/{eid}/cancel")
def cancel(eid: str, origin: str | None = Header(default=None), s: Settings = Depends(settings),
           c: sqlite3.Connection = Depends(conn)):
    if not origin or not netguard.origin_allowed(origin, s.extra_hosts):
        raise HTTPException(403, "cancel from the Episode page")
    with tx(c):
        ep = _episode(c, eid)
        if ep.status != "cancelled":
            if (ep.status not in record.EDITABLE or ep.record["outputs"].get("upload_requested")
                    or ep.record["outputs"].get("upload_job_id")):
                raise HTTPException(409, f"cannot cancel an episode while it is {ep.status}")
            record.set_status(ep, "cancelled", "cancelled before upload")
        settle_cancelled(c, s, ep)
        record.save(c, ep)
    return _out(s, ep)


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
        if ep.status == "cancelled":
            settle_cancelled(c, s, ep)
            active = c.execute("SELECT 1 FROM jobs WHERE project_id=? AND status IN"
                               " ('queued','running') AND kind NOT IN ('episode_advance',"
                               " 'episode_purge') LIMIT 1", (ep.project_id,)).fetchone()
            if active or ledger.unconsumed(c, eid) > 0:
                raise HTTPException(409, "wait for outstanding work to settle before purging")
        existing = store.find_active_job(c, "episode_purge", ep.id, "episode_id")
        job = existing or store.enqueue(
            c, "episode_purge", project_id=ep.project_id, payload={"episode_id": ep.id}
        )
    return {**_out(s, ep), "job_id": job["id"]}

@router.get("/{eid}/scenes/{sid}/preview")
def scene_preview(eid: str, sid: str, s: Settings = Depends(settings),
                  c: sqlite3.Connection = Depends(conn)):
    ep = _episode(c, eid)
    if not SCENE_ID.fullmatch(sid) or not any(sc.id == sid for sc in ep.script.scenes):
        raise HTTPException(404, "scene not found")
    path = record.episode_dir(s, eid) / "scenes" / f"{sid}.mp4"
    if not path.is_file() or not path.with_suffix(".hash").is_file():
        raise HTTPException(404, "scene preview is not ready")
    return FileResponse(path, media_type="video/mp4", headers={"Cache-Control": "no-store"})

@router.get("/{eid}/qa/{sid}.jpg")
def scene_qa_sheet(eid: str, sid: str, s: Settings = Depends(settings),
                   c: sqlite3.Connection = Depends(conn)):
    ep = _episode(c, eid)
    scene = next((sc for sc in ep.script.scenes if sc.id == sid), None)
    if scene is None or not SCENE_ID.fullmatch(sid):
        raise HTTPException(404, "scene not found")
    st = ep.record["scenes_state"].get(sid, {})
    key = record.scene_key(s, scene, ep.render_script(), int(st.get("take", 0)))
    sheet = record.episode_dir(s, eid) / "qa" / sid / f"{key}.jpg"
    if not sheet.is_file():
        raise HTTPException(404, "review sheet is not ready for this take")
    return FileResponse(sheet, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/{eid}/scenes/{sid}/capture")
def scene_capture(eid: str, sid: str, image: bool = False, s: Settings = Depends(settings),
                  c: sqlite3.Connection = Depends(conn)):
    from ...episode.website_demo import asset_path

    ep = _episode(c, eid)
    scene = next((sc for sc in ep.script.scenes if sc.id == sid), None)
    if scene is None:
        raise HTTPException(404, "scene not found")
    folder = record.episode_dir(s, eid)
    card = asset_path(folder, scene)
    if not card:
        raise HTTPException(404, "scene has no website capture")
    snapshot = folder / "caps" / card.stem
    path = snapshot / ("page.png" if image else "metadata.json")
    if not path.is_file():
        raise HTTPException(404, "capture evidence unavailable for this render")
    return FileResponse(path, media_type="image/png" if image else "application/json",
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
