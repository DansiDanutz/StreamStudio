"""The episode record: one `episodes` row whose `record_json` holds the whole record.

The API writes `script`, `budget`, `outputs.channel` and the gate states; the planner is the only
writer of `scenes_state`, `cards`, the other `outputs` fields, `log` and the working states. Both
write inside `db.tx` (BEGIN IMMEDIATE), which is the row lock. The episode is also a `projects`
row inserted directly (no EDL version), so every job carries `project_id`.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core import heygen
from ..core.config import Settings
from ..core.db import row, rows
from ..core.ids import new_id, now_iso
from .contract import Scene, Script, script_hash

STATES = (
    "draft",
    "script_approved",
    "budget_approved",
    "in_progress",
    "needs_dan",
    "ready",
    "uploaded_private",
    "scheduled",
    "published",
    "purged",
    "cancelled",
)
#: Editing the script is allowed before the upload only.
EDITABLE = ("draft", "script_approved", "budget_approved", "in_progress", "needs_dan", "ready")
#: The planner's working states.
WORKING = ("budget_approved", "in_progress")


@dataclass
class Episode:
    id: str
    project_id: str
    status: str
    title: str
    created_at: str
    updated_at: str
    record: dict[str, Any] = field(default_factory=dict)

    @property
    def script(self) -> Script:
        raw = {k: v for k, v in self.record["script"].items() if k != "hash"}
        return Script.model_validate(raw)

    @property
    def channel_settings(self) -> dict:
        return (self.record.get("profile") or {}).get("profile", {})

    def render_script(self) -> Script:
        """Apply the presenter defaults captured at approval to the writer's script."""
        script = self.script
        pin = self.record.get("presenter_defaults")
        if pin is None:
            return script
        return script.model_copy(update={
            "look": script.look or pin["avatar_id"],
            "voice_id": script.voice_id or pin["voice_id"],
            "motion": script.motion or self.channel_settings.get("presenter", {}).get("motion"),
        })

    def scene_state(self, scene_id: str) -> dict[str, Any]:
        return self.record["scenes_state"].setdefault(scene_id, {"take": 0})


# ---------------------------------------------------------------- paths


def episode_dir(s: Settings, episode_id: str) -> Path:
    return s.episodes_dir / episode_id


def clip_paths(s: Settings, key: str) -> tuple[Path, Path]:
    """The rendered clip and its cut-out, as `heygen_clip` writes them."""
    d = s.assets_dir / "avatar" / "clips"
    return d / f"{key}.mp4", d / f"{key}.cutout.webm"


def clip_state_path(s: Settings, key: str) -> Path:
    return s.data_dir / "heygen" / f"{key}.json"


def read_clip_state(s: Settings, key: str) -> dict[str, Any]:
    p = clip_state_path(s, key)
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except json.JSONDecodeError:
        return {}


# ---------------------------------------------------------------- keys and hashes


def scene_key(s: Settings, scene: Scene, script: Script, take: int = 0) -> str:
    """The clip key for a scene's current take: what HeyGen reads, the look, the voice id and
    the motion prompt from the script, else from the saved HeyGen config."""
    cfg = heygen.load_config(s.data_dir)
    look = script.look or cfg["avatar_id"]
    voice = script.voice_id or cfg["voice_id"]
    return heygen.item_key(look, voice, scene.spoken, script.motion, None, take)


def _file_sha1(p: Path | None) -> str:
    if p is None or not p.exists():
        return ""
    h = hashlib.sha1()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def inputs_hash(
    scene: Scene, clip_mp4: Path | None, cutout_webm: Path | None, card_mp4: Path | None,
    *, degraded: bool = False, look: dict | None = None, card_track=None,
    studio_dir: Path | None = None,
) -> str:
    """What `scene_compose` depends on: the text, the clip and cut-out, the card, the plan."""
    plan = scene.plan.model_dump_json(exclude_none=True) if scene.plan else ""
    raw = "\n".join(
        [scene.text, scene.voice, scene.kind, _file_sha1(clip_mp4), _file_sha1(cutout_webm),
         _file_sha1(card_mp4), plan]
    )  # fmt: skip
    if look:
        raw += "\n" + json.dumps(look, sort_keys=True)
    elif studio_dir is not None and not (scene.plan and scene.plan.connected_cards):
        for name in (
            "plate-landscape-final.json", "plate-landscape-final.png",
            "plate-landscape-final.desk.png",
        ):
            raw += "\n" + _file_sha1(studio_dir / name)
    if card_track is not None:
        raw += "\n" + json.dumps(card_track)
    if degraded:
        raw += "\ndegraded"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------- storage


def _new_record(episode_id: str, script: Script, now: str) -> dict[str, Any]:
    return {
        "id": episode_id,
        "title": script.title,
        "status": "draft",
        "created_at": now,
        "updated_at": now,
        "last_checked_at": None,
        "script": {**script.model_dump(exclude_none=True), "hash": script_hash(script)},
        "budget": {
            "approved_at": None,
            "confirm_token": None,
            "token_expires_at": None,
            "approval_id": None,
            "clips": 0,
            "seconds": 0.0,
            "usd": 0.0,
            "allowance": {"attempts": 0, "usd": 0.0},
            "spent": {"renders": 0, "seconds": 0.0, "usd": 0.0},
        },  # fmt: skip
        "reference": None,
        "scenes_state": {sc.id: {"take": 0} for sc in script.scenes},
        "cards": {},
        "outputs": {},
        "log": [],
    }


def _from_row(r: dict[str, Any]) -> Episode:
    return Episode(
        id=r["id"], project_id=r["project_id"], status=r["status"], title=r["title"],
        created_at=r["created_at"], updated_at=r["updated_at"], record=r["record_json"],
    )  # fmt: skip


def create(conn: sqlite3.Connection, s: Settings, script: Script) -> Episode:
    """Insert the project row, the episode row and the episode directory. Caller holds `tx`."""
    now = now_iso()
    episode_id = new_id("ep")
    project_id = new_id("prj")
    conn.execute(
        "INSERT INTO projects (id, name, created_at, updated_at) VALUES (?,?,?,?)",
        (project_id, script.title, now, now),
    )
    record = _new_record(episode_id, script, now)
    conn.execute(
        "INSERT INTO episodes (id, project_id, status, title, created_at, updated_at, record_json)"
        " VALUES (?,?,?,?,?,?,?)",
        (episode_id, project_id, "draft", script.title, now, now, json.dumps(record)),
    )
    episode_dir(s, episode_id).mkdir(parents=True, exist_ok=True)
    return _from_row(
        {"id": episode_id, "project_id": project_id, "status": "draft", "title": script.title,
         "created_at": now, "updated_at": now, "record_json": record}
    )  # fmt: skip


def load(conn: sqlite3.Connection, episode_id: str) -> Episode | None:
    r = row(conn.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,)).fetchone())
    return _from_row(r) if r else None


def save(conn: sqlite3.Connection, episode: Episode) -> None:
    """Write the record back. Caller holds `tx`; `status` and `title` mirror the record."""
    episode.updated_at = now_iso()
    episode.record["status"] = episode.status
    episode.record["title"] = episode.title
    episode.record["updated_at"] = episode.updated_at
    conn.execute(
        "UPDATE episodes SET status = ?, title = ?, updated_at = ?, record_json = ? WHERE id = ?",
        (episode.status, episode.title, episode.updated_at, json.dumps(episode.record), episode.id),
    )
    conn.execute(
        "UPDATE projects SET name = ?, updated_at = ? WHERE id = ?",
        (episode.title, episode.updated_at, episode.project_id),
    )


def set_status(episode: Episode, status: str, message: str | None = None, **extra: Any) -> None:
    if status not in STATES:
        raise ValueError(f"unknown episode status {status}")
    episode.status = status
    episode.record["status"] = status
    if message:
        log(episode, "status", message, **extra)


def log(episode: Episode, stage: str, message: str, scene: str | None = None, **extra: Any) -> None:
    entry: dict[str, Any] = {"at": now_iso(), "stage": stage, "message": message}
    if scene:
        entry["scene"] = scene
    entry.update(extra)
    episode.record.setdefault("log", []).append(entry)
    del episode.record["log"][:-500]


def list_episodes(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    out = []
    for r in rows(conn.execute("SELECT * FROM episodes ORDER BY created_at DESC").fetchall()):
        rec = r["record_json"]
        out.append(
            {
                "id": r["id"],
                "title": r["title"],
                "status": r["status"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "scenes": len(rec.get("script", {}).get("scenes", [])),
                "youtube_video_id": rec.get("outputs", {}).get("youtube_video_id"),
            }
        )  # fmt: skip
    return out


def export(s: Settings, episode: Episode) -> Path:
    """`episode.json` in the episode directory: the archive copy written at purge."""
    d = episode_dir(s, episode.id)
    d.mkdir(parents=True, exist_ok=True)
    p = d / "episode.json"
    p.write_text(json.dumps(episode.record, indent=1))
    return p


# ---------------------------------------------------------------- the GET /{id} shape

NEXT_ACTION = {
    "draft": "Approve script",
    "script_approved": "Approve budget",
    "budget_approved": None,
    "in_progress": None,
    "needs_dan": "Advance",
    "ready": "Upload private",
    "uploaded_private": "Publish",
    "scheduled": None,
    "published": "Purge workings",
    "purged": None,
    "cancelled": "Purge workings",
}


def progress(s: Settings, episode: Episode) -> dict[str, int]:
    script = episode.render_script()
    clips = qa = composed = 0
    d = episode_dir(s, episode.id)
    for sc in script.scenes:
        st = episode.record["scenes_state"].get(sc.id, {})
        key = st.get("clip_key") or scene_key(s, sc, script, st.get("take", 0))
        mp4, webm = clip_paths(s, key)
        if mp4.exists() and webm.exists():
            clips += 1
        if st.get("qa") in ("ok", "LOOK", "degraded"):
            qa += 1
        if st.get("composed_hash") and (d / "scenes" / f"{sc.id}.mp4").exists():
            composed += 1
    return {"clips": clips, "qa": qa, "composed": composed, "total": len(script.scenes)}


def to_out(s: Settings, episode: Episode, validation: dict[str, Any]) -> dict[str, Any]:
    rec = json.loads(json.dumps(episode.record))
    from .website_demo import asset_path

    folder = episode_dir(s, episode.id)
    for scene in episode.script.scenes:
        card = asset_path(folder, scene)
        if card and (folder / "caps" / card.stem / "metadata.json").is_file():
            rec["scenes_state"].setdefault(scene.id, {})["capture_url"] = (
                f"/api/episodes/{episode.id}/scenes/{scene.id}/capture"
            )
    rec["budget"].pop("confirm_token", None)
    rec["budget"].pop("token_expires_at", None)
    rec["status"] = episode.status
    errors = validation.get("errors") or {}
    next_action = NEXT_ACTION.get(episode.status)
    if episode.status == "draft" and errors:
        n = sum(len(v) for v in errors.values())
        next_action = f"Fix {n} error{'s' if n != 1 else ''} in the script"
    log_entries = rec.get("log") or []
    return {
        **rec,
        "progress": progress(s, episode),
        "validation": validation,
        "next_action": next_action,
        "last_log": log_entries[-1]["message"] if log_entries else None,
    }
