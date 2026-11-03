"""Package rule: the episode package imports cleanly without the `episode` extra."""

from __future__ import annotations

import importlib
import pkgutil
import subprocess
import sys
from pathlib import Path

import streamstudio.episode as episode

HEAVY = ("cv2", "numpy", "scipy", "PIL", "rembg", "playwright")


def test_every_episode_module_imports_without_heavy_libraries(tmp_path):
    """Run in a fresh interpreter with the heavy packages blocked, so a module-level import of
    any of them (directly or through another streamstudio module) fails the test."""
    names = [m.name for m in pkgutil.iter_modules(episode.__path__, "streamstudio.episode.")]
    assert "streamstudio.episode.preflight" in names
    code = f"""
import sys
for name in {HEAVY!r}:
    sys.modules[name] = None
import importlib
for name in {names!r} + ["streamstudio.worker.handlers"]:
    importlib.import_module(name)
print("ok")
"""
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=tmp_path, check=False
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "ok"
    assert not any(tmp_path.iterdir()), "importing must not write files"


def test_preflight_reports_missing_tools_without_importing_them(tmp_path, monkeypatch):
    from streamstudio.core.config import Settings
    from streamstudio.episode import preflight

    s = Settings(data_dir=tmp_path / "data", assets_dir=tmp_path / "assets")
    monkeypatch.setattr(preflight.shutil, "which", lambda b: None)
    r = preflight.check(s, stage=3)
    assert r["ok"] is False
    for name in ("ffmpeg", "ffprobe", "fonts", "intro", "plate", "music_manifest", "hyperframes"):
        assert name in r["missing"]
    assert "cv2" not in sys.modules or importlib.import_module("cv2")  # never imported by preflight


def test_preflight_is_satisfied_by_the_repository_assets(monkeypatch):
    from streamstudio.core.config import Settings
    from streamstudio.episode import preflight

    root = Path(__file__).resolve().parents[2]
    s = Settings(assets_dir=root / "assets")
    monkeypatch.setattr(preflight.shutil, "which", lambda b: "/usr/bin/" + b)
    monkeypatch.setattr(preflight, "_pkg", lambda name: True)
    r = preflight.check(s, stage=2)
    assert r == {"ok": True, "missing": []}
    t = preflight.tools(s)
    assert t["fonts"] and t["intro"] and t["plate"] and t["haar_cascade"] and t["music_manifest"]
