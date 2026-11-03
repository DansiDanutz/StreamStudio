"""The script contract: what a writer posts to `POST /api/episodes` and what the record stores.

Every model forbids unknown keys, so a typo in a plan key is a 422, not a silently ignored
creative instruction. The `Plan` keys carry the meanings `tools/compose/README.md` documents for
the hand-run pipeline's `plan.json`; fractions are of the scene's measured length.
"""

from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCENE_ID = re.compile(r"^s[0-9]{1,3}$")
CARD_ID = re.compile(r"^c[0-9]{1,3}$")
EPISODE_ID = re.compile(r"^ep_[a-z0-9]{8,40}$")

Fraction = float


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WebsiteDemo(Strict):
    """website-demo/v1: immutable capture inputs and editable scene direction."""

    workflow: Literal["website-demo/v1"] = "website-demo/v1"
    focus_label: str = Field(min_length=1, max_length=160)
    side: Literal["left", "right"] = "right"
    reveal_at: float = Field(default=0.30, ge=0, lt=1)


class Plan(Strict):
    """Per-scene creative data: table overlays, framing, cues."""

    title: list[str] | None = Field(default=None, max_length=2)
    lower: tuple[str, str | None] | None = None
    lowers: list[tuple[Fraction, Fraction | None, str, str | None]] = []
    chips: list[str] = []
    chip_at: list[Fraction] = []
    chips_out: Fraction | None = None
    zoom: tuple[float, float, float] | None = None
    zoom_path: list[tuple[Fraction, float, float, float]] = []
    card_x: float | None = None
    frame: tuple[float, float, float] | None = None
    glitch: list[tuple[Fraction, float]] = []
    endcard: list[str] | None = Field(default=None, min_length=1, max_length=3)
    end_at: Fraction | None = None
    end_until: Fraction | None = None
    whoosh_at: Fraction | None = None
    website_demo: WebsiteDemo | None = None
    card_template: Literal["generic"] | None = None


class Source(Strict):
    claim: str
    source: str


class Scene(Strict):
    id: str = Field(pattern=SCENE_ID.pattern)
    text: str = Field(default="", max_length=1500)
    voice: str = Field(default="", max_length=1500)
    kind: Literal["avatar", "card"] = "avatar"
    site: str | None = Field(default=None, max_length=500)
    question: int | None = Field(default=None, ge=1, le=99)
    reveal: bool | None = None
    sources: list[Source] = []
    plan: Plan | None = None

    @property
    def spoken(self) -> str:
        """What HeyGen reads: the voice line, else the on-screen text."""
        return (self.voice or self.text).strip()


class Script(Strict):
    title: str = Field(min_length=1, max_length=100)
    version: str = Field(default="1", max_length=40)
    tags: list[str] = []
    channel: str | None = Field(default=None, pattern=r"^UC[0-9A-Za-z_-]{22}$")
    look: str | None = Field(default=None, max_length=80)
    voice_id: str | None = Field(default=None, max_length=80)
    motion: str | None = Field(default=None, max_length=400)
    scenes: list[Scene] = Field(min_length=1, max_length=200)

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        return [t.strip() for t in v if t.strip()]


def script_hash(script: Script) -> str:
    """Stable over the script's content; the record stores it and edits compare against it."""
    raw = script.model_dump_json(exclude_none=True)
    return hashlib.sha1(raw.encode()).hexdigest()[:16]
