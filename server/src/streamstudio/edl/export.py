"""Export the EDL JSON Schema so the web app can generate matching TypeScript types."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .model import EDL


def schema_json() -> str:
    return json.dumps(EDL.model_json_schema(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    text = schema_json()
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
