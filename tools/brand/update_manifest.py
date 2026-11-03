"""Refresh assets/brand/manifest.json: the sha256 of every listed file that is present.

    python tools/brand/update_manifest.py

Entries are kept as written (name, file, licence, note); only `sha256` is recomputed, and it is
null for a file that is not in the checkout yet (the owned music and SFX clips are copied in by
hand). Run after `make_intro.py` and after adding a clip.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

BRAND = Path(__file__).resolve().parents[2] / "assets" / "brand"
MANIFEST = BRAND / "manifest.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    m = json.loads(MANIFEST.read_text())
    present = missing = 0
    for group in ("fonts", "intro", "music", "sfx"):
        for entry in m[group]:
            path = BRAND / entry["file"]
            if path.exists():
                entry["sha256"] = sha256(path)
                present += 1
            else:
                entry["sha256"] = None
                missing += 1
    MANIFEST.write_text(json.dumps(m, indent=2) + "\n")
    print(f"{MANIFEST}: {present} present, {missing} missing")


if __name__ == "__main__":
    main()
