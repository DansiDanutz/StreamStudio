"""`episode_publish_kit` and `episode_register`: what YouTube needs beside the video, and the
final video's place in the recordings library.

`kit.json` = `{title, description, tags, chapters, notes}`; chapters follow YouTube's rules as
`web/src/publish/kit.ts` encodes them (first at 0:00, one per question scene, chapters under 10 s
folded into the previous one, none at all when fewer than three remain). Captions come from the
on-screen text (DESIGN rule 6), timed from whisper word timings when present (Stage 2), else the
measured duration split by character count; every time is offset by the intro.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from ..core.config import Settings
from .contract import Scene, Script

LINE_CHARS = 42
LINES_PER_CAPTION = 2
MIN_CHAPTERS = 3
MIN_CHAPTER_S = 10.0
CHAPTER_TITLE_CHARS = 60


def srt_time(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    return f"{ms // 3_600_000:02d}:{ms // 60_000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def youtube_time(seconds: float) -> str:
    s = int(max(0, seconds))
    h, m = s // 3600, s // 60 % 60
    return f"{h}:{m:02d}:{s % 60:02d}" if h else f"{m}:{s % 60:02d}"


def caption_chunks(text: str) -> list[str]:
    """At most two lines of 42 characters, breaking between words."""
    lines: list[str] = []
    for word in text.split():
        if lines and len(f"{lines[-1]} {word}") <= LINE_CHARS:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    return [
        "\n".join(lines[i : i + LINES_PER_CAPTION]) for i in range(0, len(lines), LINES_PER_CAPTION)
    ]


def first_sentence(text: str) -> str:
    sentence = re.split(r"(?<=[.!?])\s", text.strip())[0].rstrip(".!?")
    if len(sentence) > CHAPTER_TITLE_CHARS:
        return sentence[: CHAPTER_TITLE_CHARS - 1].rstrip() + "…"
    return sentence


def chapters_for(
    scenes: list[Scene], starts: list[float], durations: list[float], total: float, notes: list[str]
) -> list[str]:
    """`["0:00 Intro", "<m:ss> <first sentence of the question scene>", ...]`."""
    raw: list[tuple[float, str]] = [(0.0, "Intro")]
    for sc, t0 in zip(scenes, starts, strict=True):
        if sc.question:
            raw.append((t0, first_sentence(sc.text or sc.voice) or f"Question {sc.question}"))
    merged: list[tuple[float, str]] = []
    for k, (t0, title) in enumerate(raw):
        end = raw[k + 1][0] if k + 1 < len(raw) else total
        if merged and end - t0 < MIN_CHAPTER_S:
            continue
        merged.append((t0, title))
    if len(merged) > 1 and total - merged[-1][0] < MIN_CHAPTER_S:
        merged.pop()
    if len(merged) < MIN_CHAPTERS:
        notes.append(
            "No chapters: YouTube needs at least 3 chapters of 10 s or more, and this script has"
            f" {len(merged)}. Mark more scenes with `question` to make chapters."
        )
        return []
    return [f"{youtube_time(t0)} {title}" for t0, title in merged]


def captions(
    scenes: list[Scene], starts: list[float], durations: list[float], words: dict[str, list[dict]]
) -> str:
    """SRT from the on-screen text; a scene's words timing (Stage 2) places its captions, else
    the measured duration is split by character count."""
    cues: list[str] = []
    for sc, t0, d in zip(scenes, starts, durations, strict=True):
        text = (sc.text or sc.voice).strip()
        if not text:
            continue
        chunks = caption_chunks(text)
        total = sum(len(c) for c in chunks) or 1
        timed = words.get(sc.id)
        timed = [w for w in (timed or []) if 0 <= w["start"] < w["end"] and w["start"] < d]
        bounds = []
        consumed = 0
        count = len(text.split())
        for chunk in chunks:
            if not timed:
                break
            first = min(len(timed)-1, consumed * len(timed) // count)
            consumed += len(chunk.split())
            last = min(len(timed)-1, max(first, (consumed * len(timed)-1) // count))
            start = max(bounds[-1][1] if bounds else 0, timed[first]["start"])
            end = min(d, timed[last]["end"])
            if end <= start:
                break
            bounds.append((start, end))
        if len(bounds) != len(chunks):
            bounds = []
            at = 0.0
            for chunk in chunks:
                end = at + d * len(chunk) / total
                bounds.append((at, end))
                at = end
        for chunk, (start, end) in zip(chunks, bounds, strict=True):
            cues.append(f"{len(cues) + 1}\n{srt_time(t0+start)} --> {srt_time(t0+end)}\n{chunk}\n")
    return "\n".join(cues)


def build_kit(
    script: Script,
    starts: list[float],
    durations: list[float],
    intro_s: float,
    words: dict[str, list[dict]] | None = None,
) -> tuple[dict[str, Any], str]:
    """`(kit, srt)`. `starts` are the scenes' offsets inside the main part; the intro is added."""
    offs = [intro_s + t for t in starts]
    total = intro_s + sum(durations)
    notes: list[str] = []
    chapters = chapters_for(script.scenes, offs, durations, total, notes)
    hook = next((sc.text.strip() for sc in script.scenes if sc.text.strip()), "")
    parts = [hook]
    if chapters:
        parts.append("Chapters\n" + "\n".join(chapters))
    kit = {
        "title": script.title,
        "description": "\n\n".join(p for p in parts if p),
        "tags": list(script.tags),
        "chapters": chapters,
        "notes": notes,
    }
    return kit, captions(script.scenes, offs, durations, words or {})


# ---------------------------------------------------------------- registration


def register(
    s: Settings, episode_id: str, final_mp4: Path, final_srt: Path, kit: dict[str, Any],
    *, revision: int = 0, language: str = "en",
) -> dict[str, str]:
    """Move the final video into the recordings library as a take named `rec_<stamp>-ep`, with
    its captions, a minimal transcript file naming the language, and the episode sidecar."""
    d = s.recordings_dir
    d.mkdir(parents=True, exist_ok=True)
    stamp = int(time.time())
    while True:
        rid = time.strftime("rec_%Y%m%d-%H%M%S", time.localtime(stamp)) + "-ep"
        if not any(d.glob(f"{rid}.*")):
            break
        stamp += 1
    with TemporaryDirectory(dir=d, prefix=".register-") as staging:
        staged = Path(staging)
        movie = staged / f"{rid}.mp4"
        try:
            os.link(final_mp4, movie)
        except OSError:
            shutil.copy2(final_mp4, movie)
        if final_srt.exists():
            shutil.copy2(final_srt, staged / f"{rid}.srt")
        (staged / f"{rid}.transcript.json").write_text(
            json.dumps({"language": language, "source": "script"})
        )
        (staged / f"{rid}.episode.json").write_text(json.dumps({
            "episode": episode_id, "revision": revision, "title": kit.get("title"),
            "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }))
        # The Library discovers the MP4. Expose it only after every companion is in place.
        for companion in staged.iterdir():
            if companion != movie:
                companion.replace(d / companion.name)
        movie.replace(d / movie.name)
    final_mp4.unlink()
    return {"recording_id": rid, "mp4": str(d / f"{rid}.mp4"), "srt": str(d / f"{rid}.srt")}


def registered_recording(s: Settings, episode_id: str, revision: int = 0) -> str | None:
    """The recording id an episode was registered under, found from the sidecar files."""
    best = None
    for p in sorted(s.recordings_dir.glob("rec_*-ep.episode.json")):
        try:
            sidecar = json.loads(p.read_text())
            if sidecar.get("episode") == episode_id and sidecar.get("revision", 0) == revision:
                rid = p.name[: -len(".episode.json")]
                if (s.recordings_dir / f"{rid}.mp4").is_file():
                    best = rid
        except (json.JSONDecodeError, OSError):
            continue
    return best
