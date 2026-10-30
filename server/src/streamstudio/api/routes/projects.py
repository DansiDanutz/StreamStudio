from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...core import media, store
from ...core.config import Settings
from ...core.paths import UnsafePathError, resolve_in_any
from ...edl import EDL
from ..deps import conn, project_or_404, settings

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class EDLSave(BaseModel):
    base_version: int
    edl: EDL
    message: str = ""


class ImportPath(BaseModel):
    path: str = Field(description="Absolute path on the Mac Studio, inside an allowed import root")


@router.get("")
def list_projects(c: sqlite3.Connection = Depends(conn)) -> list[dict]:
    return store.list_projects(c)


@router.post("", status_code=201)
def create_project(body: ProjectIn, c: sqlite3.Connection = Depends(conn)) -> dict:
    return store.create_project(c, body.name.strip())


@router.get("/{pid}")
def get_project(pid: str, c: sqlite3.Connection = Depends(conn)) -> dict:
    p = project_or_404(c, pid)
    version, _ = store.latest_edl(c, pid)  # type: ignore[misc]
    return {**p, "edl_version": version, "assets": store.list_assets(c, pid)}


@router.patch("/{pid}")
def rename_project(pid: str, body: ProjectIn, c: sqlite3.Connection = Depends(conn)) -> dict:
    project_or_404(c, pid)
    return store.rename_project(c, pid, body.name.strip())  # type: ignore[return-value]


@router.delete("/{pid}", status_code=204)
def delete_project(pid: str, c: sqlite3.Connection = Depends(conn)) -> None:
    if not store.delete_project(c, pid):
        raise HTTPException(404, "project not found")


# --------------------------------------------------------------- EDL


@router.get("/{pid}/edl")
def get_edl(pid: str, c: sqlite3.Connection = Depends(conn)) -> dict:
    project_or_404(c, pid)
    version, edl = store.latest_edl(c, pid)  # type: ignore[misc]
    return {"version": version, "edl": edl.model_dump()}


@router.put("/{pid}/edl")
def save_edl(pid: str, body: EDLSave, c: sqlite3.Connection = Depends(conn)) -> dict:
    project_or_404(c, pid)
    try:
        v = store.save_edl(c, pid, body.edl, body.base_version, body.message)
    except store.VersionConflict as e:
        raise HTTPException(409, str(e)) from e
    return {"version": v}


@router.get("/{pid}/edl/versions")
def edl_versions(pid: str, c: sqlite3.Connection = Depends(conn)) -> list[dict]:
    project_or_404(c, pid)
    return store.list_edl_versions(c, pid)


# --------------------------------------------------------------- assets


@router.post("/{pid}/assets/import-path", status_code=201)
def import_path(
    pid: str,
    body: ImportPath,
    c: sqlite3.Connection = Depends(conn),
    s: Settings = Depends(settings),
) -> dict:
    """Register a file that already lives on the Mac Studio (no copy) and probe it."""
    project_or_404(c, pid)
    try:
        p = resolve_in_any(s.allowed_import_roots(), body.path)
    except UnsafePathError as e:
        raise HTTPException(400, str(e)) from e
    if not p.is_file():
        raise HTTPException(400, f"not a file: {p}")
    kind = media.kind_for(p)
    if kind is None:
        raise HTTPException(400, f"unsupported file type: {p.suffix}")
    asset = store.create_asset(c, pid, kind=kind, name=Path(p).name, path=str(p))
    job = store.enqueue(c, "probe", project_id=pid, asset_id=asset["id"])
    return {"asset": asset, "job": job}
