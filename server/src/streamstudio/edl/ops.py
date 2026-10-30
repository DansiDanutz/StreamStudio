"""Pure EDL operations. Each takes an EDL and returns a new, validated EDL."""

from __future__ import annotations

from collections.abc import Iterable

from ..core.ids import new_id
from .model import EDL, Clip, Format, Track


class EDLError(ValueError):
    pass


def new_edl(fmt: Format | None = None) -> EDL:
    return EDL(
        format=fmt or Format(),
        tracks=[
            Track(id="V1", kind="video", name="Main", magnetic=True),
            Track(id="V2", kind="overlay", name="B-roll"),
            Track(id="A1", kind="audio", name="Music"),
            Track(id="C1", kind="caption", name="Captions"),
        ],
    )


def duration(edl: EDL) -> int:
    return max((c.end for t in edl.tracks for c in t.clips), default=0)


def snap_to_frame(t: int, fmt: Format) -> int:
    """Round a µs time to the nearest frame boundary."""
    frame_us = 1_000_000 * fmt.fps_den / fmt.fps_num
    return round(round(t / frame_us) * frame_us)


def _rebuild(edl: EDL, track_id: str, clips: list[Clip]) -> EDL:
    data = edl.model_dump()
    for t in data["tracks"]:
        if t["id"] == track_id:
            t["clips"] = [c.model_dump() for c in clips]
    return EDL.model_validate(data)


def _editable(edl: EDL, track_id: str) -> Track:
    try:
        t = edl.track(track_id)
    except KeyError:
        raise EDLError(f"no such track: {track_id}") from None
    if t.locked:
        raise EDLError(f"track {track_id} is locked")
    return t


def append_clip(
    edl: EDL, track_id: str, asset_id: str, src_in: int, src_out: int, *, at: int | None = None
) -> EDL:
    t = _editable(edl, track_id)
    start = max((c.end for c in t.clips), default=0) if at is None else at
    clip = Clip(id=new_id("clip"), asset_id=asset_id, start=start, src_in=src_in, src_out=src_out)
    return _rebuild(edl, track_id, [*t.clips, clip])


def split(edl: EDL, track_id: str, at: int) -> EDL:
    """Split the clip under timeline time `at` into two clips."""
    t = _editable(edl, track_id)
    out: list[Clip] = []
    did = False
    for c in t.clips:
        if c.start < at < c.end:
            cut = c.src_at(at)
            out.append(c.model_copy(update={"src_out": cut}))
            out.append(c.model_copy(update={"id": new_id("clip"), "start": at, "src_in": cut}))
            did = True
        else:
            out.append(c)
    if not did:
        raise EDLError(f"no clip under {at}µs on {track_id}")
    return _rebuild(edl, track_id, out)


def delete_range(
    edl: EDL, start: int, end: int, *, track_ids: Iterable[str] | None = None, ripple: bool = True
) -> EDL:
    """Remove [start, end) from the given tracks (default: every unlocked track).

    Clips straddling the range are trimmed or split. With ripple, everything after
    `end` moves left by (end - start) so no gap is left behind.
    """
    if end <= start:
        raise EDLError("delete_range: end must be greater than start")
    ids = list(track_ids) if track_ids is not None else [t.id for t in edl.tracks if not t.locked]
    gap = end - start
    for tid in ids:
        t = _editable(edl, tid)
        out: list[Clip] = []
        for c in t.clips:
            if c.end <= start:  # entirely before
                out.append(c)
            elif c.start >= end:  # entirely after
                out.append(c.model_copy(update={"start": c.start - gap}) if ripple else c)
            else:
                if c.start < start:  # keep head
                    out.append(c.model_copy(update={"src_out": c.src_at(start)}))
                if c.end > end:  # keep tail
                    tail_start = start if ripple else end
                    tail = c.model_copy(update={"start": tail_start, "src_in": c.src_at(end)})
                    if c.start < start:
                        tail = tail.model_copy(update={"id": new_id("clip")})
                    out.append(tail)
        edl = _rebuild(edl, tid, out)
    return edl
