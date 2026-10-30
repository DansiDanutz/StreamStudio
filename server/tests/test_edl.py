import pytest

from streamstudio.edl import (
    EDL,
    EDLError,
    append_clip,
    delete_range,
    duration,
    new_edl,
    snap_to_frame,
    split,
)

US = 1_000_000


def _edl():
    e = new_edl()
    e = append_clip(e, "V1", "a", 0, 10 * US)  # 0..10s
    e = append_clip(e, "V1", "b", 5 * US, 8 * US)  # 10..13s
    return e


def test_new_edl_has_four_tracks():
    e = new_edl()
    assert [t.id for t in e.tracks] == ["V1", "V2", "A1", "C1"]
    assert e.tracks[0].magnetic


def test_append_and_duration():
    e = _edl()
    assert duration(e) == 13 * US
    assert [c.start for c in e.track("V1").clips] == [0, 10 * US]


def test_split_creates_two_clips_with_continuous_source():
    e = split(_edl(), "V1", 4 * US)
    clips = e.track("V1").clips
    assert len(clips) == 3
    assert clips[0].src_out == 4 * US and clips[1].src_in == 4 * US
    assert clips[1].start == 4 * US and clips[1].end == 10 * US


def test_split_outside_any_clip_raises():
    with pytest.raises(EDLError):
        split(_edl(), "V1", 20 * US)


def test_delete_range_ripples():
    e = delete_range(_edl(), 2 * US, 6 * US)  # remove 4s from first clip
    clips = e.track("V1").clips
    assert duration(e) == 9 * US
    assert clips[0].src_out == 2 * US
    assert clips[1].start == 2 * US and clips[1].src_in == 6 * US
    assert clips[2].start == 6 * US  # second clip moved left by 4s


def test_delete_range_across_clip_boundary():
    e = delete_range(_edl(), 8 * US, 11 * US)
    clips = e.track("V1").clips
    assert len(clips) == 2
    assert clips[0].src_out == 8 * US
    assert clips[1].start == 8 * US and clips[1].src_in == 6 * US  # b: src_in 5s + 1s


def test_locked_track_rejects_edits():
    e = _edl()
    e.track("V1").locked = True
    with pytest.raises(EDLError):
        append_clip(e, "V1", "c", 0, US)


def test_overlap_is_invalid():
    data = _edl().model_dump()
    data["tracks"][0]["clips"][1]["start"] = 5 * US
    with pytest.raises(ValueError):
        EDL.model_validate(data)


def test_snap_to_frame():
    e = new_edl()
    assert snap_to_frame(33_400, e.format) == 33_333  # 30fps frame = 33333.33µs
    assert snap_to_frame(0, e.format) == 0
