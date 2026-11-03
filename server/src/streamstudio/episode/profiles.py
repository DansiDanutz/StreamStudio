"""Immutable channel settings selected at episode creation and pinned at approval."""
from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import Field

from ..core import heygen
from . import channel_files
from .contract import Strict


class Presenter(Strict):
    name: str = Field(min_length=1)
    avatar_id: str
    voice_id: str
    motion: str | None = None


class Publish(Strict):
    description_footer: str = ""
    default_tags: list[str] = []


Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Effect = Literal["riser", "pop", "whoosh", "glitch", "shimmer", "impact", "page", "sparkle"]
Level = Annotated[float, Field(ge=-70, le=-5)]


class Levels(Strict):
    intro: Level = -18
    voice: Level = -16
    bed: Level = -36
    sfx: Level = -26


class Sound(Strict):
    intro: Digest | None = None
    bed: Digest | None = None
    sfx: dict[Effect, Digest] = {}
    levels: Levels = Field(default_factory=Levels)


def verify_sound(s, sound: Sound | None):
    if sound:
        if sound.intro:
            channel_files.verify(s, sound.intro, kind="intro")
        digests = set(sound.sfx.values())
        if sound.bed:
            digests.add(sound.bed)
        for digest in digests:
            channel_files.verify(s, digest)


class Seat(Strict):
    scale: float = Field(gt=.01, le=2)
    hands_y: float = Field(ge=0, le=1)
    x: float = Field(ge=0, le=1)


class Plate(Strict):
    image: Digest
    desk: Digest | None = None
    seat: Seat


Color = Annotated[str, Field(pattern=r"^#[A-Fa-f0-9]{6}([A-Fa-f0-9]{2})?$")]


class Palette(Strict):
    accent_a: Color = "#FFFFFF"
    accent_b: Color = "#FFFFFF"
    glow: Color = "#FFFFFF"
    panel: Color = "#000000DC"
    panel_2: Color = "#000000CD"
    outline: Color = "#FFFFFFAA"
    text: Color = "#FFFFFF"
    tag_text: Color = "#FFFFFF"
    muted: Color = "#AAAAAA"


class Look(Strict):
    plate: Plate
    palette: Palette | None = None
    fonts: dict[Literal["display", "body", "small"], Digest] = {}


def verify_look(s, look: Look | None):
    if look:
        channel_files.verify(s, look.plate.image, kind="image")
        for digest in set(look.fonts.values()):
            channel_files.verify(s, digest, kind="font")
        if look.plate.desk:
            channel_files.verify(s, look.plate.desk, kind="image")


class IntroColours(Strict):
    bg: Color = "#050404"
    glow: Color = "#160b091a"
    accent: Color = "#e74c3c"
    accent_dark: Color = "#c0392b"
    highlight: Color = "#d4a017"
    letter: Color = "#fffef7"
    title: Color = "#fafafa"
    muted: Color = "#b9b1a4"


class Intro(Strict):
    fonts: dict[Literal["serif", "serif_bold", "serif_italic", "mono"], Digest] = {}
    kicker: str = Field(default="", max_length=40)
    title: str = Field(default="", max_length=64)
    title_em: str = Field(default="", max_length=40)
    tagline: str = Field(default="", max_length=120)
    logo_letter: str = Field(default="", max_length=1)
    colours: IntroColours = Field(default_factory=IntroColours)


class Profile(Strict):
    slug: str = Field(pattern=r"^[a-z][a-z0-9-]{0,47}$")
    name: str = Field(min_length=1)
    language: str = Field(default="en", pattern=r"^[A-Za-z]{2,8}(-[A-Za-z0-9]{1,8})*$")
    youtube_channel: str | None = Field(default=None, pattern=r"^UC[0-9A-Za-z_-]{22}$")
    presenter: Presenter
    intro: Intro = Field(default_factory=Intro)
    look: Look | None = None
    sound: Sound | None = None
    publish: Publish = Field(default_factory=Publish)


def save(c, profile: Profile, version: int):
    raw = json.dumps(profile.model_dump(), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode()).hexdigest()
    c.execute("INSERT INTO channel_profiles VALUES(?,?,?,?)", (profile.slug, version, digest, raw))
    return {"slug": profile.slug, "version": version, "hash": digest, "profile": json.loads(raw)}


def seed(c, s):
    current = get(c, "danslab")
    if not current and c.execute("SELECT 1 FROM channel_seeds WHERE slug='danslab'").fetchone():
        return
    if current:
        identity = current["profile"]["presenter"]
        if current["version"] != 1 or (identity["avatar_id"] and identity["voice_id"]):
            return
    cfg = heygen.load_config(s.data_dir)
    if current and not (cfg["avatar_id"] and cfg["voice_id"]):
        return
    save(c, Profile(slug="danslab", name="DansLab", presenter=Presenter(
        name="Dan", avatar_id=cfg["avatar_id"], voice_id=cfg["voice_id"])), 2 if current else 1)
    c.execute("INSERT OR IGNORE INTO channel_seeds VALUES ('danslab')")


def default(c):
    return c.execute("SELECT slug FROM channel_default WHERE singleton=1").fetchone()[0]


def get(c, slug: str, version: int | None = None):
    row = c.execute("SELECT * FROM channel_profiles WHERE slug=? AND (? IS NULL OR version=?)"
                    " ORDER BY version DESC LIMIT 1", (slug, version, version)).fetchone()
    if row is None:
        return None
    return {"slug": slug, "version": row["version"], "hash": row["hash"],
            "profile": json.loads(row["profile_json"])}
