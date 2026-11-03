"""The script validator: errors block approval, warnings never do.

Stage 1 ships the error rows of the design's table (`kind: card` without a site, a duplicate
scene id, a scene with nothing to say). The warning rows (length, question and reveal structure,
unsourced numbers, names spelled for the screen, long runs of plain avatar scenes) ship in Stage 2.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..core import heygen
from ..core.config import Settings
from .contract import Script
from .website_demo import auto_site

#: Scenes shorter or longer than this are flagged (DESIGN rule 1), from Stage 2.
MIN_S, MAX_S = 3.0, 13.0


def voice_names(s: Settings) -> list[dict[str, str]]:
    """The names-for-voice table (`assets/brand/voice-names.json`), or empty when absent."""
    p = Path(s.assets_dir) / "brand" / "voice-names.json"
    if not p.exists():
        return []
    return json.loads(p.read_text()).get("names", [])


def estimate_seconds(script: Script) -> dict[str, float]:
    return {sc.id: round(heygen.estimate_seconds(sc.spoken, None), 1) for sc in script.scenes}


def validate(script: Script, s: Settings) -> dict[str, dict[str, list[str]]]:
    """`{errors: {scene_id: [..]}, warnings: {scene_id: [..]}}`; episode-level notes use `"*"`."""
    errors: dict[str, list[str]] = {}
    warnings: dict[str, list[str]] = {}

    def err(sid: str, msg: str) -> None:
        errors.setdefault(sid, []).append(msg)

    seen: set[str] = set()
    for sc in script.scenes:
        if sc.id in seen:
            err(sc.id, "duplicate scene id")
        seen.add(sc.id)
        if sc.kind == "card" and not (sc.site or "").strip():
            err(sc.id, "a card scene needs a site")
        if (sc.plan and sc.plan.website_demo
                and (sc.kind != "card" or not auto_site(s, sc.site or ""))):
            err(sc.id, "website demo needs a card on an auto-allowed HTTPS site")
        if not sc.spoken:
            err(sc.id, "both voice and text are empty")
    return {"errors": errors, "warnings": warnings}
