"""Edit Decision List v1 — the single source of truth for a project's edit.

All times are integer microseconds (µs). Integers keep cuts exact; frame snapping
happens in ops, not in storage. The UI edits this document, the renderer compiles it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TrackKind = Literal["video", "audio", "caption", "overlay"]


class Format(BaseModel):
    model_config = ConfigDict(extra="forbid")
    width: int = Field(1920, ge=16, le=8192)
    height: int = Field(1080, ge=16, le=8192)
    fps_num: int = Field(30, ge=1)
    fps_den: int = Field(1, ge=1)
    sample_rate: int = Field(48000, ge=8000)


class Clip(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    asset_id: str
    start: int = Field(ge=0, description="Position on the timeline, µs")
    src_in: int = Field(ge=0, description="In-point in the source asset, µs")
    src_out: int = Field(gt=0, description="Out-point in the source asset, µs")
    speed: float = Field(1.0, gt=0.0, le=16.0)
    volume: float = Field(1.0, ge=0.0, le=4.0)
    muted: bool = False

    @model_validator(mode="after")
    def _in_before_out(self) -> Clip:
        if self.src_out <= self.src_in:
            raise ValueError(f"clip {self.id}: src_out must be greater than src_in")
        return self

    @property
    def duration(self) -> int:
        return round((self.src_out - self.src_in) / self.speed)

    @property
    def end(self) -> int:
        return self.start + self.duration

    def src_at(self, t: int) -> int:
        """Source time that plays at timeline time t."""
        return self.src_in + round((t - self.start) * self.speed)


class Track(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: TrackKind
    name: str = ""
    magnetic: bool = Field(False, description="Main storyline: deletes ripple, no gaps")
    muted: bool = False
    hidden: bool = False
    locked: bool = False
    clips: list[Clip] = Field(default_factory=list)

    @model_validator(mode="after")
    def _no_overlaps(self) -> Track:
        ordered = sorted(self.clips, key=lambda c: c.start)
        for a, b in zip(ordered, ordered[1:], strict=False):
            if b.start < a.end:
                raise ValueError(f"track {self.id}: clips {a.id} and {b.id} overlap")
        self.clips = ordered
        return self


class Marker(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    at: int = Field(ge=0)
    label: str = ""
    kind: Literal["chapter", "note", "short"] = "note"


class EDL(BaseModel):
    model_config = ConfigDict(extra="forbid", title="StreamStudioEDL")
    schema_version: Literal[1] = 1
    format: Format = Field(default_factory=Format)
    tracks: list[Track] = Field(default_factory=list)
    markers: list[Marker] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> EDL:
        seen: set[str] = set()
        for t in self.tracks:
            for i in (t.id, *(c.id for c in t.clips)):
                if i in seen:
                    raise ValueError(f"duplicate id: {i}")
                seen.add(i)
        return self

    def track(self, track_id: str) -> Track:
        for t in self.tracks:
            if t.id == track_id:
                return t
        raise KeyError(track_id)
