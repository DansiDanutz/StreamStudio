from PIL import Image

from streamstudio.render.lipsync import (
    MAX_UNSYNCED_AREA,
    composite_pip,
    guard_cue,
    lips_match,
    pip_rect,
)


def test_lips_match_only_with_the_clips_own_voice():
    assert lips_match("/avatar/a.mp4")
    assert lips_match("/avatar/a.mp4", "clip")
    assert not lips_match("/avatar/a.mp4", "narration")
    assert not lips_match(None)


def test_guard_cue_degrades_big_face_cues():
    assert guard_cue("avatar", "/a.mp4") == "avatar"
    assert guard_cue("avatar", "/a.mp4", "narration") == "pip"
    assert guard_cue("duo", None) == "content"
    assert guard_cue("full", None) == "full"


def test_pip_is_small_and_square():
    for size in [(1920, 1080), (1080, 1920)]:
        x, y, w, h = pip_rect(*size)
        assert w == h
        assert (w * h) / (size[0] * size[1]) <= MAX_UNSYNCED_AREA
        assert x + w < size[0] / 2 and y + h < size[1]


def test_composite_pip_keeps_frame_size_and_draws_bottom_left():
    frame = Image.new("RGB", (1920, 1080), (0, 0, 0))
    face = Image.new("RGB", (1280, 720), (200, 50, 50))
    out = composite_pip(frame, face)
    assert out.size == frame.size
    x, y, w, h = pip_rect(1920, 1080)
    assert out.getpixel((x + w // 2, y + h // 2))[0] > 150  # face inside the circle
    assert out.getpixel((x + 2, y + 2))[0] < 60  # corner outside the circle stays the frame
    assert out.getpixel((1800, 100))[:3] == (0, 0, 0)
