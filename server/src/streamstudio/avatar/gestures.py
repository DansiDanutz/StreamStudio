"""Turn raw gesture clips into stage-ready cut-outs.

Input: a folder of clips named by gesture id (point-up-right.mp4, point-right.mp4, ...; see
web/src/avatar/gestures.ts and docs/prompts/avatar-gestures.md). Left-hand gestures are mirrored
on stage, so only the right-hand versions are needed.
Output: assets/avatar/gestures/<id>.cutout.webm (VP9 + alpha) and manifest.json listing what exists.
Idempotent: a clip whose cut-out is newer than the source is skipped.

Usage: python -m streamstudio.avatar.gestures SRC_DIR [--plate PLATE.png]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from .cutout import run

VIDEO = {".mp4", ".mov", ".webm"}
ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "assets" / "avatar" / "gestures"
NEEDED = [
    "point-up-right", "point-right", "point-down-right", "present-right",
    "welcome", "thumbs-up", "wave", "think",
]  # fmt: skip


def duration(p: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return round(float(out.stdout.strip() or 0), 2)


def process(src_dir: Path, plate: Path, out: Path = OUT) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    done: dict[str, float] = {}
    for gid in NEEDED:
        clips = [p for p in src_dir.glob(f"{gid}.*") if p.suffix.lower() in VIDEO]
        src = clips[0] if clips else None
        dst = out / f"{gid}.cutout.webm"
        if src and (not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime):
            tmp = out / f".work-{gid}"
            res = run(src, plate, tmp, scale=0.66, hands_y=0.68, x=0.47, keep=False)
            shutil.move(res["cutout_webm"], dst)
            shutil.rmtree(tmp, ignore_errors=True)
        if dst.exists():
            done[gid] = duration(dst)
    manifest = {"gestures": done, "missing": [g for g in NEEDED if g not in done]}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src_dir", type=Path)
    ap.add_argument("--plate", type=Path, default=ROOT / "assets/studio/plate-landscape-final.png")
    a = ap.parse_args()
    print(json.dumps(process(a.src_dir, a.plate), indent=2))


if __name__ == "__main__":
    main()
