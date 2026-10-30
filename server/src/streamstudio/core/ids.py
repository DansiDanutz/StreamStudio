from __future__ import annotations

import secrets
import time


def new_id(prefix: str) -> str:
    """Sortable, URL-safe id: <prefix>_<ms-timestamp-base36><random>."""
    ts = _b36(int(time.time() * 1000))
    return f"{prefix}_{ts}{secrets.token_hex(4)}"


def _b36(n: int) -> str:
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while n:
        n, r = divmod(n, 36)
        out = chars[r] + out
    return out or "0"


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
