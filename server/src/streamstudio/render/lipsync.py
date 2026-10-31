"""Lip-sync guard for offline renders (mirror of web/src/director/types.ts).

Hard rule: Dan's face may fill the frame ONLY while the voice heard is the clip's own lip-synced
audio. Any other voice (cloned, dubbed, a separate narration track, or none) puts the face in a
small circle (or portrait) card, bottom-left, where a lip/voice mismatch is too small to notice.
"""

from __future__ import annotations

from typing import Literal

from PIL import Image, ImageDraw, ImageFilter

Voice = Literal["clip", "narration"]
Shape = Literal["circle", "portrait"]

MAX_UNSYNCED_AREA = 0.06  # largest share of the frame the face may take when lips do not match


def lips_match(clip: str | None, voice: Voice | None = None) -> bool:
    return bool(clip) and voice != "narration"


def guard_cue(cue: str, clip: str | None, voice: Voice | None = None) -> str:
    if lips_match(clip, voice):
        return cue
    return {"avatar": "pip", "duo": "content"}.get(cue, cue)


def pip_rect(width: int, height: int, shape: Shape = "circle") -> tuple[int, int, int, int]:
    """(x, y, w, h) in pixels of the small presenter card, matching cueLayouts.pipRect."""
    land = width >= height
    w = round(width * (0.15 if land else 0.3))
    h = round(w * (4 / 3 if shape == "portrait" else 1))
    x = round(width * (0.045 if land else 0.06))
    y = height - h - round(height * (0.07 if land else 0.05))
    return x, y, w, h


def pip_card(
    face: Image.Image, frame_size: tuple[int, int], shape: Shape = "circle", face_y: float = 0.36
) -> tuple[Image.Image, tuple[int, int]]:
    """Crop `face` (a raw clip frame) to the small card, face-centred.

    Returns (RGBA card, top-left position in the frame)."""
    x, y, w, h = pip_rect(*frame_size, shape=shape)
    fw, fh = face.size
    k = max(w / fw, h / fh)
    scaled = face.convert("RGB").resize((round(fw * k), round(fh * k)), Image.LANCZOS)
    sx = (scaled.width - w) // 2
    sy = min(max(0, round(scaled.height * face_y - h / 2)), scaled.height - h)
    card = scaled.crop((sx, sy, sx + w, sy + h)).convert("RGBA")
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    if shape == "circle":
        d.ellipse((0, 0, w - 1, h - 1), fill=255)
    else:
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=w // 10, fill=255)
    card.putalpha(mask)
    return card, (x, y)


def composite_pip(frame: Image.Image, face: Image.Image, shape: Shape = "circle") -> Image.Image:
    """Draw the small presenter card (with a soft shadow) onto `frame`."""
    out = frame.convert("RGBA")
    card, (x, y) = pip_card(face, out.size, shape)
    shadow = Image.new("RGBA", out.size, (0, 0, 0, 0))
    sh = Image.new("RGBA", card.size, (0, 0, 0, 150))
    sh.putalpha(card.getchannel("A").point(lambda a: a * 150 // 255))
    shadow.alpha_composite(sh, (x, y + card.height // 25))
    out.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(card.width // 20)))
    out.alpha_composite(card, (x, y))
    return out
