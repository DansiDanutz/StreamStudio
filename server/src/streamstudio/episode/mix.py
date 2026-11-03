"""`episode_assemble`: the composed scenes, the intro, the music bed and the SFX become
`final.mp4` (-14 LUFS, 25 fps) with `final.cues.json` beside it.

Levels (DESIGN rule 3, corrected): intro -18 LUFS, voice -16 LUFS, bed -36 LUFS, SFX -26 LUFS,
the whole mix `loudnorm` to -14 LUFS / -1.5 dBTP / LRA 11. SFX only at the special moments the
plan names; the sounds and offsets are those of `tools/compose/mix.py`. NumPy is imported inside
the functions (package rule).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from ..core.config import Settings
from . import FPS, channel_files
from .compose import probe_duration
from .contract import Scene
from .profiles import Sound

SR = 48000
LEVELS = {"intro": -18, "voice": -16, "bed": -36, "sfx": -26}
FINAL = "loudnorm=I=-14:TP=-1.5:LRA=11"

#: Cue kind → (sound file stem, offset in seconds, gain dB). Offsets are relative to the moment
#: the plan names (a scene start for `question` and `reveal`, a fraction for the others).
CUE_SOUNDS: dict[str, tuple[str, float, float]] = {
    "question_riser": ("riser-soft", -1.3, -3),
    "question_pop": ("pop-reveal", 0.3, -4),
    "whoosh": ("whoosh-soft", -0.2, -2),
    "glitch": ("glitch-zap", 0.0, -1),
    "endcard": ("warm-shimmer", 0.0, 0),
    "reveal": ("impact-deep-soft", 0.3, -2),
    # card cues (Stage 3), read from each card's cues.json
    "navigate": ("ui-click-soft", 0.0, -6),
    "counter": ("sparkle-soft", -0.1, 0),
}


EFFECT_ROLES = {
    "riser-soft": "riser", "pop-reveal": "pop", "whoosh-soft": "whoosh",
    "glitch-zap": "glitch", "warm-shimmer": "shimmer", "impact-deep-soft": "impact",
    "ui-click-soft": "page", "sparkle-soft": "sparkle",
}


def manifest(s: Settings) -> dict[str, Any]:
    p = s.assets_dir / "brand" / "manifest.json"
    return json.loads(p.read_text()) if p.exists() else {}


def sound_path(s: Settings, stem: str) -> Path | None:
    """The clip for a sound stem, if it has been copied into assets/brand."""
    for entry in manifest(s).get("sfx", []):
        if Path(entry["file"]).stem == stem:
            p = s.assets_dir / "brand" / entry["file"]
            return p if p.exists() else None
    return None


def bed_path(s: Settings) -> Path | None:
    m = manifest(s)
    for entry in m.get("music", []):
        if Path(entry["file"]).stem == m.get("bed"):
            p = s.assets_dir / "brand" / entry["file"]
            return p if p.exists() else None
    return None


def plan_cues(scenes: list[Scene], starts: list[float], durations: list[float]) -> list[dict]:
    """SFX cues from the scenes' plans, in seconds from the start of the main part (the intro is
    added later). Card cues from `cues.json` are appended by the handler in Stage 3."""
    cues: list[dict] = []

    def cue(kind: str, at: float, why: str) -> None:
        stem, off, db = CUE_SOUNDS[kind]
        cues.append({"kind": kind, "sfx": stem, "t": round(at + off, 2), "db": db, "why": why})

    from .website_demo import card_timeline

    tracks = card_timeline(scenes, durations)
    for sc, t0, d in zip(scenes, starts, durations, strict=True):
        p = sc.plan
        if sc.id in tracks:
            offset, reveal = tracks[sc.id]
            if offset == 0:
                cue("navigate", t0, f"{sc.id}: show website")
                cue("counter", t0 + reveal / FPS, f"{sc.id}: focus on {p.website_demo.focus_label}")
        if sc.question:
            cue("question_riser", t0, f"{sc.id}: question {sc.question} coming")
            cue("question_pop", t0, f"{sc.id}: question card")
        if sc.reveal:
            cue("reveal", t0, f"{sc.id}: the avatar reveal")
        if p is None:
            continue
        if p.whoosh_at is not None:
            cue("whoosh", t0 + p.whoosh_at * d, f"{sc.id}: push into the monitor")
        for gf, _gd in p.glitch:
            cue("glitch", t0 + gf * d, f"{sc.id}: glitch")
        if p.endcard:
            cue("endcard", t0 + (p.end_at or 0) * d, f"{sc.id}: end card")
    return cues


def _load(s: Settings, path: Path, lufs: float | None):
    import numpy as np

    af = f"loudnorm=I={lufs}:TP=-2:LRA=20" if lufs is not None else None
    cmd = [s.ffmpeg_bin, "-v", "error", "-i", str(path)] + (["-af", af] if af else []) + [
        "-ac", "2", "-ar", str(SR), "-f", "f32le", "-",
    ]  # fmt: skip
    a = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32)
    return a.reshape(-1, 2).copy()


def assemble(
    s: Settings,
    scenes: list[Scene],
    scene_files: list[Path],
    intro: Path | None,
    out_mp4: Path,
    extra_cues: list[dict] | None = None,
    *, sound: Sound | None = None,
) -> dict[str, Any]:
    """Concat the scene files, put the intro in front, mix the voice, the bed and the SFX."""
    import numpy as np

    levels = sound.levels.model_dump() if sound is not None else LEVELS
    durations = [probe_duration(s.ffprobe_bin, p) for p in scene_files]
    for p, d in zip(scene_files, durations, strict=True):
        frames = _frame_count(s, p)
        if abs(frames - round(d * FPS)) > 1:
            raise RuntimeError(f"{p.name}: {frames} frames for {d:.2f} s is not {FPS} fps")
    intro_d = probe_duration(s.ffprobe_bin, intro) if intro else 0.0
    starts: list[float] = []
    t = 0.0
    for d in durations:
        starts.append(t)
        t += d
    main_d = t
    total = intro_d + main_d
    mix = np.zeros((int(total * SR) + SR, 2), np.float32)

    def put(a, at: float, gain: float = 1.0) -> None:
        i = int(at * SR)
        n = min(len(a), len(mix) - i)
        if n > 0:
            mix[i : i + n] += a[:n] * gain

    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    work = out_mp4.parent / "mix"
    work.mkdir(exist_ok=True)
    # the voice: the scene files concatenated (video and audio), so timings match the picture
    concat_list = work / "scenes.txt"
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in scene_files))
    main = work / "main.mp4"
    subprocess.run(
        [s.ffmpeg_bin, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c", "copy", "-movflags", "+faststart", str(main)],
        check=True,
    )  # fmt: skip
    if intro:
        put(_load(s, intro, levels["intro"]), 0)
    put(_load(s, main, levels["voice"]), intro_d)
    notes: list[str] = []
    bed = bed_path(s) if sound is None else None
    if sound and sound.bed:
        bed = channel_files.verify(s, sound.bed)
    if bed is not None:
        m = _load(s, bed, levels["bed"])
        if not len(m):
            raise ValueError("music bed decoded to zero samples")
        xf = min(int(3 * SR), len(m) // 4)
        need = int((total - intro_d + 2) * SR)
        loop = np.empty((need, 2), dtype=np.float32)
        filled = min(need, len(m))
        loop[:filled] = m[:filled]
        ramp = np.linspace(0, 1, xf, dtype=np.float32)[:, None]
        while filled < need:
            if xf:
                loop[filled-xf:filled] *= 1 - ramp
                loop[filled-xf:filled] += m[:xf] * ramp
            count = min(need - filled, len(m) - xf)
            loop[filled:filled+count] = m[xf:xf+count]
            filled += count
        fi, fo = min(len(loop), int(2.5 * SR)), min(len(loop), int(5 * SR))
        loop[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)[:, None]
        loop[-fo:] *= np.linspace(1, 0, fo, dtype=np.float32)[:, None]
        put(loop, max(0.0, intro_d - 1.0))
    elif sound is None:
        notes.append("no music bed: assets/brand/music is empty")
    cues = plan_cues(scenes, starts, durations) + list(extra_cues or [])
    cache: dict[str, Any] = {}
    missing: set[str] = set()
    for c in cues:
        c["t"] = round(c["t"] + intro_d, 2)
        if c["sfx"] not in cache:
            if sound is None:
                p = sound_path(s, c["sfx"])
            else:
                digest = sound.sfx.get(EFFECT_ROLES.get(c["sfx"]))
                p = channel_files.verify(s, digest) if digest else None
            cache[c["sfx"]] = _load(s, p, levels["sfx"]) if p else None
        if cache[c["sfx"]] is None:
            if sound is None:
                missing.add(c["sfx"])
            continue
        put(cache[c["sfx"]], max(0.0, c["t"]), 10 ** (c["db"] / 20))
    if missing:
        notes.append("missing SFX: " + ", ".join(sorted(missing)))
    mix = mix[: int(total * SR)]
    wav = work / "mix.f32"
    mix.astype(np.float32).tofile(wav)
    (out_mp4.parent / "final.cues.json").write_text(
        json.dumps({"cues": cues, "notes": notes}, indent=1)
    )
    tmp = out_mp4.with_name(out_mp4.stem + ".tmp.mp4")
    video_inputs = ["-i", str(main)]
    graph = f"[0:v]fps={FPS},format=yuv420p,setsar=1[v];[1:a]{FINAL}[au]"
    if intro:
        video_inputs = ["-i", str(intro), *video_inputs]
        graph = (f"[0:v]fps={FPS},scale=1920:1080,format=yuv420p,setsar=1[a];"
                 f"[1:v]fps={FPS},format=yuv420p,setsar=1[b];"
                 f"[a][b]concat=n=2:v=1:a=0[v];[2:a]{FINAL}[au]")
    subprocess.run(
        [s.ffmpeg_bin, "-v", "error", "-y", *video_inputs,
         "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", str(wav), "-filter_complex", graph,
         "-map", "[v]", "-map", "[au]", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart",
         "-shortest", str(tmp)],
        check=True,
    )  # fmt: skip
    wav.unlink(missing_ok=True)
    tmp.replace(out_mp4)
    return {
        "duration_s": round(total, 2), "intro_s": round(intro_d, 2), "scenes": len(scene_files),
        "starts": [round(intro_d + x, 3) for x in starts],
        "durations": [round(d, 3) for d in durations],
        "cues": len(cues), "notes": notes,
    }  # fmt: skip


def _frame_count(s: Settings, path: Path) -> int:
    out = subprocess.run(
        [s.ffprobe_bin, "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=nb_read_frames", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return int(json.loads(out.stdout)["streams"][0]["nb_read_frames"])
