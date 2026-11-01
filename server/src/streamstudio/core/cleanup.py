"""Suggest cuts for a take from its word-level transcript: long silences and filler words (EN/RO).

Pure functions, non-destructive: they return ranges (ms) that a caller may apply to an EDL
(`edl.ops.delete_range`) or show to the user first."""

from __future__ import annotations

import re
from typing import Any

FILLERS: dict[str, frozenset[str]] = {
    "en": frozenset({"um", "uh", "uhm", "umm", "er", "erm", "hmm", "ah"}),
    "ro": frozenset({"ăă", "ăăă", "ee", "eee", "hm", "mm", "mmm", "aaa", "îî", "îîî"}),
}

_STRIP = re.compile(r"^[^\w]+|[^\w]+$")


def _norm(word: str) -> str:
    return _STRIP.sub("", word.lower())


def suggest_cuts(
    words: list[dict[str, Any]],
    *,
    silence_ms: int = 700,
    keep_ms: int = 250,
    langs: tuple[str, ...] = ("en", "ro"),
    fillers: bool = True,
) -> list[dict[str, Any]]:
    """Return [{start_ms, end_ms, kind, text}] sorted, non-overlapping.

    - `silence`: a gap between two words longer than `silence_ms` is trimmed down to `keep_ms`
      (the pause stays natural; only the excess is cut).
    - `filler`: a word in the filler list for `langs` is cut whole.
    """
    stop = frozenset().union(*(FILLERS.get(lang, frozenset()) for lang in langs))
    cuts: list[dict[str, Any]] = []
    prev_end: int | None = None
    for w in words:
        s, e = int(w["start_ms"]), int(w["end_ms"])
        if prev_end is not None and s - prev_end > silence_ms:
            half = keep_ms // 2
            a, b = prev_end + half, s - (keep_ms - half)
            if b > a:
                cuts.append({"start_ms": a, "end_ms": b, "kind": "silence", "text": ""})
        if fillers and _norm(w["word"]) in stop and e > s:
            cuts.append({"start_ms": s, "end_ms": e, "kind": "filler", "text": w["word"]})
        prev_end = max(e, prev_end or 0)
    return _merge(cuts)


def _merge(cuts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Join touching or overlapping ranges so they can be applied in one pass."""
    out: list[dict[str, Any]] = []
    for c in sorted(cuts, key=lambda c: c["start_ms"]):
        if out and c["start_ms"] <= out[-1]["end_ms"]:
            last = out[-1]
            last["end_ms"] = max(last["end_ms"], c["end_ms"])
            if c["kind"] != last["kind"]:
                last["kind"] = "mixed"
            last["text"] = " ".join(t for t in (last["text"], c["text"]) if t)
        else:
            out.append(dict(c))
    return out


def saved_ms(cuts: list[dict[str, Any]]) -> int:
    return sum(c["end_ms"] - c["start_ms"] for c in cuts)
