"""One-off converter: the Episode 1 v2 files (script JSON, plan JSON, durations) into the script
contract, as the first test fixture.

    python server/tests/convert_episode1.py

Rules: plan `question: true` becomes scene `question: n` (counted from 1); a plan entry with
`still`, `tag` or `video` is a `kind: card` scene whose `site` comes from the storyboard groups
in `tools/compose/motion/cards_v2.py`; `video`, `video_at`, `cont`, `still`, `tag` and
`intro_zoom` are dropped (cards are derived from `kind: card` + `site`); the plan's own `kind`
is consumed by the scene, never copied; every other key is copied into `plan`.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).resolve().parent / "fixtures" / "episode-01-v2"

#: The storyboard groups of cards_v2.py: the scenes each card covers and its site.
SITES = {
    (6,): "https://www.fake-real.live",
    (10, 11, 12, 13): "https://nervixpay.live",
    (15, 16, 17, 18): "https://worldcup26.world",
    (21, 22, 23, 24): "https://danslab-jev.vercel.app",
    (27,): "https://nervix.space/list",
    (28,): "https://nervix.space",
    (29,): "https://nervix.space/#directory",
}
DROP = ("video", "video_at", "cont", "still", "tag", "intro_zoom", "kind", "question")


def site_for(n: int) -> str:
    for scenes, site in SITES.items():
        if n in scenes:
            return site
    raise KeyError(f"scene {n} is a card with no storyboard group")


def convert() -> dict:
    src = json.loads((FIX / "episode-01-v2.json").read_text(encoding="utf8"))
    plans = json.loads((FIX / "episode-01-v2.plan.json").read_text(encoding="utf8"))
    scenes = []
    question = 0
    for row, plan in zip(src["scenes"], plans, strict=True):
        n = row["scene"]
        is_card = plan.get("kind") == "card" or any(k in plan for k in ("still", "tag", "video"))
        kind = "card" if is_card else "avatar"
        sc: dict = {"id": f"s{n}", "text": row["text"], "voice": row["voice"], "kind": kind}
        if kind == "card":
            sc["site"] = site_for(n)
        if plan.get("question"):
            question += 1
            sc["question"] = question
        if any("AI avatar" in (lw[2] or "") for lw in plan.get("lowers", [])):
            sc["reveal"] = True
        rest = {k: v for k, v in plan.items() if k not in DROP}
        if kind == "card":
            rest.setdefault("card_template", "generic")
        if rest:
            sc["plan"] = rest
        scenes.append(sc)
    return {
        "title": "In Love With AI, Episode 1: Build it. Show it. Sell it.",
        "version": "2",
        "tags": ["AI", "DansLab", "builders"],
        "scenes": scenes,
    }


if __name__ == "__main__":
    out = convert()
    (FIX / "script.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf8"
    )
    print(FIX / "script.json", len(out["scenes"]), "scenes")
