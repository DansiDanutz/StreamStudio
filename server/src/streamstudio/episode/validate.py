"""The script validator: errors block approval, warnings never do.

Stage 1 ships the error rows of the design's table (`kind: card` without a site, a duplicate
scene id, a scene with nothing to say). The warning rows (length, question and reveal structure,
unsourced numbers, names spelled for the screen, long runs of plain avatar scenes) ship in Stage 2.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..core import heygen
from ..core.config import Settings
from .contract import Script
from .website_demo import capture_mode, manual_folder

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

    def warn(sid: str, message: str) -> None:
        warnings.setdefault(sid, []).append(message)

    if not any(sc.question for sc in script.scenes):
        warn("*", "no scene introduces a question")
    if not any(sc.reveal for sc in script.scenes):
        warn("*", "no scene marks the reveal")
    names = [n for n in voice_names(s) if n["screen"] != n["voice"]]
    plain_seconds = 0.0
    plain_count = 0
    seen: set[str] = set()
    for sc in script.scenes:
        seconds = heygen.estimate_seconds(sc.spoken, None)
        if not MIN_S <= seconds <= MAX_S:
            warn(sc.id, f"estimated {seconds:.1f}s falls outside the 3–13s scene range")
        if not sc.sources and re.search(
            r"\d|[$€£%]|\b(first|largest|fastest|cheapest|best|top[- ]ranked)\b",
            sc.text + " " + sc.spoken, re.I,
        ):
            warn(sc.id, "add a source for the numerical or ranking claim")
        for name in names:
            if re.search(r"(?<!\w)" + re.escape(name["screen"]) + r"(?!\w)", sc.spoken, re.I):
                warn(sc.id, f"use {name['voice']} in the spoken line for {name['screen']}")
        if sc.kind == "avatar" and not (sc.plan and sc.plan.model_dump(exclude_defaults=True)):
            plain_seconds += seconds
            plain_count += 1
            if plain_count >= 2 and plain_seconds > 8:
                warn(sc.id, "consecutive plain presenter scenes exceed 8s")
        else:
            plain_seconds = 0.0
            plain_count = 0
        if sc.id in seen:
            err(sc.id, "duplicate scene id")
        seen.add(sc.id)
        connected = sc.plan and sc.plan.connected_cards
        if connected and (sc.kind != "card" or sc.plan.website_demo):
            err(sc.id, "connected cards need a card scene with one visual workflow")
        if sc.kind == "card" and not connected and not (sc.site or "").strip():
            err(sc.id, "a card scene needs a site")
        if sc.plan and sc.plan.website_demo:
            manual = sc.plan.website_demo.manual
            mode = capture_mode(s, sc.site or "")
            if sc.kind != "card" or mode != ("manual" if manual else "auto"):
                err(sc.id, "website demo needs an allowed HTTPS site and matching capture method")
            elif manual and not (manual_folder(s, sc.site) / (manual.sha256 + ".png")).is_file():
                err(sc.id, "upload the manual screenshot for this page first")
        if not sc.spoken:
            err(sc.id, "both voice and text are empty")
    return {"errors": errors, "warnings": warnings}
