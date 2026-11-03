"""`episode_advance`: the planner. Reads the record and the files, decides the next step, enqueues
the handler that does it, returns. Re-queueable at any time; never calls HeyGen, ffmpeg or a
browser itself.

The condition table of the design, evaluated top to bottom under the `episodes` row lock. Every
row records the job id it enqueues in the record and skips while that job is live, so two
planners running at once never enqueue the same work twice. Its one read of the `jobs` table is
the status of a job id it recorded itself.

Stage 1 ships rows 1 (the `needs_dan` branch), 2, 6 (clip-and-cut-out predicate), 7, 8, 9, 10
and 11; Stage 2 replaces row 1 with the QA rows and row 6's predicate with the QA verdict.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..core import heygen, store, youtube
from ..core.config import Settings
from ..core.db import tx
from . import kit, ledger, record
from .contract import Scene, Script

LIVE = ("queued", "running")


def _job_status(conn: sqlite3.Connection, job_id: str | None) -> str | None:
    if not job_id:
        return None
    r = conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return r["status"] if r else None


def _live(conn: sqlite3.Connection, job_id: str | None) -> bool:
    return _job_status(conn, job_id) in LIVE


def _enqueue(conn, ep: record.Episode, kind: str, payload: dict[str, Any]) -> str:
    job = store.enqueue(
        conn, kind, project_id=ep.project_id, payload={**payload, "episode_id": ep.id}
    )
    return job["id"]


def clip_payload(
    s: Settings, ep: record.Episode, scene: Scene, script: Script, key: str, take: int
) -> dict:
    cfg = heygen.load_config(s.data_dir)
    return {
        "key": key, "kind": "segment", "gesture": None, "segment_id": scene.id,
        "clip": f"/avatar/clips/{key}.mp4", "script": scene.spoken, "silent_s": None,
        "motion": script.motion, "look": script.look or cfg["avatar_id"],
        "voice": script.voice_id or cfg["voice_id"], "take": take, "scene_id": scene.id,
        "seconds": round(heygen.estimate_seconds(scene.spoken, None), 1), "max_attempts": 1,
    }  # fmt: skip


def advance(conn: sqlite3.Connection, s: Settings, episode_id: str) -> dict[str, Any]:
    """One planner pass. Returns what it did, for the job result and the tests."""
    with tx(conn):
        ep = record.load(conn, episode_id)
        if ep is None:
            return {"skipped": "no such episode"}
        if ep.status not in record.WORKING:
            return {"skipped": f"episode is {ep.status}"}
        did = _pass(conn, s, ep)
        record.save(conn, ep)
    return did


def _pass(conn: sqlite3.Connection, s: Settings, ep: record.Episode) -> dict[str, Any]:
    script = ep.script
    d = record.episode_dir(s, ep.id)
    out = ep.record["outputs"]
    states = ep.record["scenes_state"]
    done: dict[str, Any] = {"enqueued": [], "episode": ep.id}

    # ---- sync: current keys, files, finished jobs
    clips_ready = True
    for sc in script.scenes:
        st = ep.scene_state(sc.id)
        take = int(st.get("take", 0))
        key = record.scene_key(s, sc, script, take)
        st["clip_key"] = key
        mp4, webm = record.clip_paths(s, key)
        has_clip = mp4.exists() and webm.exists()
        st["clip"] = has_clip
        if has_clip and not st.get("duration_s"):
            from .compose import probe_duration  # ffprobe only

            st["duration_s"] = round(probe_duration(s.ffprobe_bin, mp4), 3)
        if not has_clip:
            clips_ready = False
        hash_file = d / "scenes" / f"{sc.id}.hash"
        if (d / "scenes" / f"{sc.id}.mp4").exists() and hash_file.exists():
            st["composed_hash"] = hash_file.read_text().strip()
        elif not (d / "scenes" / f"{sc.id}.mp4").exists():
            st["composed_hash"] = None

    # ---- row 1: a failed render or an errored job parks the episode
    for sc in script.scenes:
        st = states[sc.id]
        state = record.read_clip_state(s, st["clip_key"])
        if state.get("failed") and not st.get("clip"):
            record.set_status(
                ep, "needs_dan", f"Scene {sc.id} failed on HeyGen: {state['failed']}", scene=sc.id
            )
            return {**done, "needs_dan": sc.id}
        for field in ("job_id", "compose_job_id"):
            if _job_status(conn, st.get(field)) == "error" and not st.get(f"{field}_seen_error"):
                st[f"{field}_seen_error"] = True
                job = store.get_job(conn, st[field])
                reason = (job or {}).get("error") or "unknown error"
                record.set_status(
                    ep,
                    "needs_dan",
                    f"Scene {sc.id}: {field.replace('_', ' ')} ended in error:"
                    f" {reason.splitlines()[0][:200]}",
                    scene=sc.id,
                )
                return {**done, "needs_dan": sc.id}
    for field in ("assemble_job_id", "kit_job_id", "register_job_id", "upload_job_id"):
        if _job_status(conn, out.get(field)) == "error" and not out.get(f"{field}_seen_error"):
            out[f"{field}_seen_error"] = True
            job = store.get_job(conn, out[field])
            reason = (job or {}).get("error") or "unknown error"
            record.set_status(
                ep,
                "needs_dan",
                f"{field.replace('_job_id', '')} ended in error: {reason.splitlines()[0][:200]}",
            )
            return {**done, "needs_dan": field}

    # ---- row 2: render what has no clip
    for sc in script.scenes:
        st = states[sc.id]
        if st.get("clip") or _live(conn, st.get("job_id")):
            continue
        key, take = st["clip_key"], int(st.get("take", 0))
        state = record.read_clip_state(s, key)
        if state.get("failed"):
            continue  # row 1 handled it
        payload = clip_payload(s, ep, sc, script, key, take)
        job_id = _enqueue(conn, ep, "heygen_clip", payload)
        previous = st.get("job_id")
        if previous and _job_status(conn, previous) == "error" and state.get("video_id"):
            # claim transfer: the replacement job resumes the submitted render, no second payment
            state["claim"] = job_id
            record.clip_state_path(s, key).write_text(json.dumps(state))
            record.log(
                ep, "render", f"{sc.id}: resuming HeyGen render {state['video_id']}", scene=sc.id
            )
        st.update({"job_id": job_id, "job_key": key, "job_take": take, "job_id_seen_error": False})
        record.log(ep, "render", f"{sc.id}: clip queued (take {take})", scene=sc.id)
        done["enqueued"].append(("heygen_clip", sc.id))
    if done["enqueued"]:
        record.set_status(ep, "in_progress")
        return done
    if not clips_ready:
        return {**done, "waiting": "clips"}
    if ep.status == "budget_approved":
        record.set_status(ep, "in_progress")

    # ---- row 6: compose scenes whose inputs changed
    composed_ready = True
    for sc in script.scenes:
        st = states[sc.id]
        mp4, webm = record.clip_paths(s, st["clip_key"])
        card = d / "cards" / f"{st['card_id']}.mp4" if st.get("card_id") else None
        current = record.inputs_hash(sc, mp4, webm, card)
        st["inputs_hash"] = current
        if st.get("composed_hash") == current:
            continue
        composed_ready = False
        if _live(conn, st.get("compose_job_id")):
            continue
        job_id = _enqueue(conn, ep, "scene_compose", {"scene_id": sc.id, "inputs_hash": current})
        st.update({"compose_job_id": job_id, "compose_job_id_seen_error": False})
        done["enqueued"].append(("scene_compose", sc.id))
    if done["enqueued"] or not composed_ready:
        return done if done["enqueued"] else {**done, "waiting": "compose"}

    # ---- rows 7 to 9: assemble, kit, register
    final = d / "final.mp4"
    kit_json = d / "kit.json"
    rid = out.get("recording_id") or kit.registered_recording(s, ep.id)
    if rid and not out.get("recording_id"):
        out["recording_id"] = rid
        out["final_mp4"] = str(s.recordings_dir / f"{rid}.mp4")
        out["final_srt"] = str(s.recordings_dir / f"{rid}.srt")
        record.log(ep, "register", f"registered as {rid}")
    if not final.exists() and not rid:
        if not _live(conn, out.get("assemble_job_id")):
            out["assemble_job_id"] = _enqueue(conn, ep, "episode_assemble", {})
            out["assemble_job_id_seen_error"] = False
            done["enqueued"].append(("episode_assemble", None))
        return done
    if not kit_json.exists():
        if not _live(conn, out.get("kit_job_id")):
            out["kit_job_id"] = _enqueue(conn, ep, "episode_publish_kit", {})
            out["kit_job_id_seen_error"] = False
            done["enqueued"].append(("episode_publish_kit", None))
        return done
    out["kit"] = str(kit_json)
    if not rid:
        if not _live(conn, out.get("register_job_id")):
            out["register_job_id"] = _enqueue(conn, ep, "episode_register", {})
            out["register_job_id_seen_error"] = False
            done["enqueued"].append(("episode_register", None))
        return done

    # ---- rows 10 and 11: upload, then uploaded_private
    if not out.get("upload_requested") and not out.get("upload_job_id"):
        record.set_status(ep, "ready", "ready in the Library")
        approval = ep.record["budget"].get("approval_id")
        if approval:
            ledger.release(conn, ep.id, approval)
            ep.record["budget"]["spent"] = ledger.spent(conn, ep.id)
        return done
    channel = out.get("channel")
    state_file = youtube.folder(s.data_dir) / "uploads" / f"{channel}-{rid}.json"
    state = {}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
        except json.JSONDecodeError:
            state = {}
    if state.get("video_id"):
        out["youtube_video_id"] = state["video_id"]
        record.set_status(
            ep, "uploaded_private", f"uploaded privately: https://youtu.be/{state['video_id']}"
        )
        if ep.record["budget"].get("approval_id"):
            freed = ledger.release(conn, ep.id, ep.record["budget"]["approval_id"])
            ep.record["budget"]["spent"] = ledger.spent(conn, ep.id)
            if freed:
                record.log(ep, "budget", f"released {freed:.2f} USD of the reservation")
        return {**done, "uploaded": state["video_id"]}
    if not _live(conn, out.get("upload_job_id")):
        k = json.loads(kit_json.read_text())
        meta = youtube.clean_meta(k["title"], k["description"], k.get("tags", []), "private")
        out["upload_job_id"] = _enqueue(
            conn,
            ep,
            "youtube_upload",
            {"id": rid, "channel": channel, "key": f"{channel}/{rid}", "meta": meta},
        )
        out["upload_job_id_seen_error"] = False
        done["enqueued"].append(("youtube_upload", rid))
    return done
