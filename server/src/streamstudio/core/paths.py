"""Path safety. Every filesystem path that comes from a request goes through here."""

from __future__ import annotations

from pathlib import Path


class UnsafePathError(ValueError):
    pass


def resolve_within(root: Path, candidate: str | Path) -> Path:
    """Resolve `candidate` (absolute, or relative to root) and require it to stay inside `root`.

    Symlinks are resolved before the check, so a link pointing outside root is rejected.
    """
    root_r = Path(root).expanduser().resolve()
    p = Path(candidate).expanduser()
    if not p.is_absolute():
        p = root_r / p
    p = p.resolve()
    if p != root_r and root_r not in p.parents:
        raise UnsafePathError(f"path escapes allowed root: {candidate}")
    return p


def resolve_in_any(roots: list[Path], candidate: str | Path) -> Path:
    """Resolve an absolute path and require it to sit inside one of `roots`."""
    p = Path(candidate).expanduser()
    if not p.is_absolute():
        raise UnsafePathError("import path must be absolute")
    for root in roots:
        try:
            return resolve_within(root, p)
        except UnsafePathError:
            continue
    raise UnsafePathError(f"path is outside the allowed import folders: {candidate}")


def safe_filename(name: str, max_len: int = 120) -> str:
    keep = "".join(c if c.isalnum() or c in "-_. " else "_" for c in name).strip(" .")
    return (keep or "file")[:max_len]
