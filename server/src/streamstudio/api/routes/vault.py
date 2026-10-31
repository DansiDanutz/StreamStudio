"""The vault: copies of clips, takes and the catalog kept off this machine (see core/vault.py)."""

from __future__ import annotations

import sqlite3
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...core import vault
from ...core.config import Settings
from ...core.db import tx
from ..deps import conn, settings

router = APIRouter(prefix="/api/vault", tags=["vault"])


class VaultIn(BaseModel):
    kind: Literal["s3", "folder", "off"]
    # s3 (Supabase Storage S3, Cloudflare R2, Backblaze B2, AWS)
    endpoint: str = Field("", max_length=300)
    region: str = Field("", max_length=40)
    bucket: str = Field("", max_length=100)
    access_key: str = Field("", max_length=200)
    secret_key: str = Field("", max_length=300)
    # folder (iCloud Drive, Google Drive for desktop, Dropbox, NAS)
    path: str = Field("", max_length=500)
    prefix: str = Field("streamstudio", max_length=80)


class KeyIn(BaseModel):
    key: str = Field(min_length=1, max_length=300)


def _status(s: Settings, c: sqlite3.Connection) -> dict[str, Any]:
    cfg = vault.load_config(s.data_dir)
    idx = vault.index(c)
    local = list(vault.local_files(s))
    local_keys = {k for k, _ in local}
    job = c.execute(
        "SELECT id, status, progress, message, error FROM jobs WHERE kind = 'vault_push'"
        " ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    return {
        "configured": bool(cfg.get("kind")),
        "config": vault.public_config(cfg),
        "local_files": len(local),
        "in_vault": len(idx),
        "not_backed_up": len(local_keys - set(idx)),
        "vault_only": len(set(idx) - local_keys),
        "bytes_in_vault": sum(o["bytes"] for o in idx.values()),
        "last_push": dict(job) if job else None,
    }


@router.get("")
def status(s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)) -> dict:
    """Where the vault is, and how much of the library is safely off this machine."""
    return _status(s, c)


@router.put("")
def configure(
    body: VaultIn, s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)
) -> dict:
    """Set where the vault lives. Blank keys keep the saved ones. The connection is checked."""
    if body.kind == "off":
        vault.save_config(s.data_dir, {})
        return _status(s, c)
    old = vault.load_config(s.data_dir)
    cfg = {k: v.strip() for k, v in body.model_dump().items() if isinstance(v, str)}
    for k in ("access_key", "secret_key"):
        if not cfg.get(k) and old.get("kind") == "s3":
            cfg[k] = old.get(k, "")
    cfg = {k: v for k, v in cfg.items() if v}
    try:
        be = vault.backend(cfg)
        if be is None:
            raise vault.VaultError("choose a folder or fill in the bucket")
        if isinstance(be, vault.FolderBackend):
            be.root.mkdir(parents=True, exist_ok=True)
        be.list(vault.prefixed(cfg, "catalog/"))  # proves the address and keys work
    except (vault.VaultError, OSError) as e:
        raise HTTPException(422, f"could not reach the vault: {e}") from e
    vault.save_config(s.data_dir, cfg)
    return _status(s, c)


@router.post("/push", status_code=202)
def push(s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)) -> dict:
    """Back up everything new or changed (runs as a job)."""
    from ...worker.handlers import queue_vault_push

    with tx(c):
        job = queue_vault_push(c, s)
    if job is None:
        raise HTTPException(409, "set up the vault first")
    return job


@router.post("/sync")
def sync(s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)) -> dict:
    """Read what the vault holds: lists cloud-only clips and takes, restores missing scenes and
    names. Use it on a new machine, or after another machine added things."""
    try:
        remote = vault.remote_files(s)
        with tx(c):
            got = vault.restore_catalog(s, c)
            known = vault.index(c)
            for o in remote:
                if vault.local_path(s, o["key"]) and o["key"] not in known:
                    vault.record(c, o["key"], o["bytes"], None)
    except vault.VaultError as e:
        raise HTTPException(422, str(e)) from e
    return {**got, "files_in_vault": len(remote), **_status(s, c)}


@router.post("/fetch")
def fetch(
    body: KeyIn, s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)
) -> dict:
    """Bring one clip or take back to this machine now."""
    if vault.local_path(s, body.key) is None:
        raise HTTPException(422, "not a vault file key")
    try:
        p = vault.fetch(s, c, body.key)
    except vault.VaultError as e:
        raise HTTPException(502, str(e)) from e
    if p is None:
        raise HTTPException(404, "the vault does not have it")
    return {"key": body.key, "bytes": p.stat().st_size, "local": True}


@router.post("/evict")
def evict(
    body: KeyIn, s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)
) -> dict:
    """Free space: remove the local copy of a file the vault holds, after checking the vault's
    copy is identical. It comes back by itself the next time it is used."""
    p = vault.local_path(s, body.key)
    if p is None or not p.exists():
        raise HTTPException(404, "no local copy")
    if body.key.endswith(".json"):
        raise HTTPException(422, "small index files stay local")
    cfg = vault.load_config(s.data_dir)
    be = vault.backend(cfg)
    if be is None:
        raise HTTPException(409, "set up the vault first")
    sha = vault.sha256_file(p)
    try:
        remote = be.head(vault.prefixed(cfg, body.key))
    except vault.VaultError as e:
        raise HTTPException(502, str(e)) from e
    if not remote or remote.get("sha256") != sha:
        raise HTTPException(409, "the vault copy is missing or different: back up first")
    p.unlink()
    with tx(c):
        vault.record(c, body.key, remote["bytes"], sha)
    return {"key": body.key, "local": False, "freed_bytes": remote["bytes"]}


@router.get("/files")
def files(s: Settings = Depends(settings)) -> list[dict]:
    try:
        return vault.remote_files(s)
    except vault.VaultError as e:
        raise HTTPException(422, str(e)) from e
