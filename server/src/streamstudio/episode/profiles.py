"""Immutable channel settings selected at episode creation and pinned at approval."""
from __future__ import annotations

import hashlib
import json

from pydantic import Field

from ..core import heygen
from .contract import Strict


class Presenter(Strict):
    name: str = Field(min_length=1)
    avatar_id: str
    voice_id: str
    motion: str | None = None


class Publish(Strict):
    description_footer: str = ""
    default_tags: list[str] = []


class Profile(Strict):
    slug: str = Field(pattern=r"^[a-z][a-z0-9-]{0,47}$")
    name: str = Field(min_length=1)
    language: str = Field(default="en", pattern=r"^[A-Za-z]{2,8}(-[A-Za-z0-9]{1,8})*$")
    youtube_channel: str | None = Field(default=None, pattern=r"^UC[0-9A-Za-z_-]{22}$")
    presenter: Presenter
    publish: Publish = Field(default_factory=Publish)


def save(c, profile: Profile, version: int):
    raw = json.dumps(profile.model_dump(), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode()).hexdigest()
    c.execute("INSERT INTO channel_profiles VALUES(?,?,?,?)", (profile.slug, version, digest, raw))
    return {"slug": profile.slug, "version": version, "hash": digest, "profile": json.loads(raw)}


def seed(c, s):
    current = get(c, "danslab")
    if current:
        identity = current["profile"]["presenter"]
        if current["version"] != 1 or (identity["avatar_id"] and identity["voice_id"]):
            return
    cfg = heygen.load_config(s.data_dir)
    if current and not (cfg["avatar_id"] and cfg["voice_id"]):
        return
    save(c, Profile(slug="danslab", name="DansLab", presenter=Presenter(
        name="Dan", avatar_id=cfg["avatar_id"], voice_id=cfg["voice_id"])), 2 if current else 1)



def default(c):
    return c.execute("SELECT slug FROM channel_default WHERE singleton=1").fetchone()[0]


def get(c, slug: str, version: int | None = None):
    row = c.execute("SELECT * FROM channel_profiles WHERE slug=? AND (? IS NULL OR version=?)"
                    " ORDER BY version DESC LIMIT 1", (slug, version, version)).fetchone()
    if row is None:
        return None
    return {"slug": slug, "version": row["version"], "hash": row["hash"],
            "profile": json.loads(row["profile_json"])}
