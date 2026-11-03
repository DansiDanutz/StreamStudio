from __future__ import annotations

import hashlib
import sqlite3
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import Field
from starlette.concurrency import run_in_threadpool

from ...core import netguard, youtube
from ...core.config import Settings
from ...core.db import tx
from ...episode import channel_files, profiles
from ...episode.contract import Strict
from ..deps import conn, settings

router = APIRouter(prefix="/api/channels", tags=["channels"])


def owner(origin: str | None = Header(default=None), s: Settings = Depends(settings)):
    if not origin or not netguard.origin_allowed(origin, s.extra_hosts):
        raise HTTPException(403, "edit channels from the studio")


class Selection(Strict):
    slug: str = Field(pattern=r"^[a-z][a-z0-9-]{0,47}$")


class Create(Selection):
    name: str = Field(min_length=1)
    source: str | None = Field(None, alias="from")


class Save(Strict):
    base_version: int = Field(ge=1)
    profile: profiles.Profile


@router.get("")
def listing(s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)):
    with tx(c):
        profiles.seed(c, s)
        rows = c.execute("SELECT slug,MAX(version) FROM channel_profiles GROUP BY slug").fetchall()
        return [{"slug": slug, "name": profiles.get(c, slug)["profile"]["name"], "version": version,
                 "default": slug == profiles.default(c)} for slug, version in rows]


@router.post("", status_code=201, dependencies=[Depends(owner)])
def create(body: Create, s: Settings = Depends(settings), c: sqlite3.Connection = Depends(conn)):
    with tx(c):
        profiles.seed(c, s)
        if body.slug in ("default", "files", "preview"):
            raise HTTPException(422, "reserved channel name")
        if profiles.get(c, body.slug):
            raise HTTPException(409, "channel already exists")
        source = profiles.get(c, body.source or profiles.default(c))
        if not source:
            raise HTTPException(404, "source channel not found")
        data = {**source["profile"], "slug": body.slug, "name": body.name, "youtube_channel": None}
        return profiles.save(c, profiles.Profile.model_validate(data), 1)


@router.put("/default", dependencies=[Depends(owner)])
def set_default(body: Selection, s: Settings = Depends(settings),
                c: sqlite3.Connection = Depends(conn)):
    with tx(c):
        profiles.seed(c, s)
        if not profiles.get(c, body.slug):
            raise HTTPException(409, "channel not found")
        c.execute("UPDATE channel_default SET slug=? WHERE singleton=1", (body.slug,))
    return {"slug": body.slug}


@router.put("/files", dependencies=[Depends(owner)])
async def upload_file(name: str, request: Request, role: str = "audio",
                      s: Settings = Depends(settings)):
    ext = Path(name).suffix.lower()
    if ext not in channel_files.KINDS.get(role, {}):
        raise HTTPException(415, "unsupported channel file role or extension")
    root = s.data_dir / "channels" / "tmp"
    root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=root) as tmp:
        staged = Path(tmp) / ("upload" + ext)
        digest = hashlib.sha256()
        count = 0
        with staged.open("wb") as stream:
            async for chunk in request.stream():
                count += len(chunk)
                if count > 200 * 1024 * 1024:
                    raise HTTPException(413, "channel file exceeds 200 MiB")
                digest.update(chunk)
                stream.write(chunk)
        try:
            if role == "intro":
                normalized = await run_in_threadpool(channel_files.install_intro, s, staged)
                return {"sha256": normalized.stem, "kind": "video",
                        "bytes": normalized.stat().st_size, "media_type": "video/mp4"}
            if role == "audio":
                channel_files.install_audio(s, staged, ext, digest.hexdigest())
            elif role == "font":
                channel_files.install_font(s, staged, ext, digest.hexdigest())
            else:
                channel_files.install_image(s, staged, ext, digest.hexdigest())
        except (ValueError, subprocess.TimeoutExpired) as e:
            raise HTTPException(422, str(e)) from e
    return {"sha256": digest.hexdigest(), "kind": role, "bytes": count,
            "media_type": channel_files.FORMATS[ext][1]}


@router.get("/files/{digest}")
def fetch_file(digest: str, s: Settings = Depends(settings)):
    path = channel_files.resolve(s, digest)
    if path is None:
        raise HTTPException(404, "channel file not found")
    return FileResponse(path, media_type=channel_files.FORMATS[path.suffix][1],
                        headers={"X-Content-Type-Options": "nosniff"})


@router.post("/preview", dependencies=[Depends(owner)])
def preview(body: profiles.Profile, s: Settings = Depends(settings),
            c: sqlite3.Connection = Depends(conn)):
    from ...episode import channel_preview

    try:
        jpeg, cached = channel_preview.preview(c, s, body)
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(422, str(exc)) from exc
    return Response(jpeg, media_type="image/jpeg", headers={
        "Cache-Control": "no-store", "X-Presenter-Preview": "cached" if cached else "silhouette",
    })


@router.get("/{slug}")
def get(slug: str, version: int | None = None, s: Settings = Depends(settings),
        c: sqlite3.Connection = Depends(conn)):
    with tx(c):
        profiles.seed(c, s)
        result = profiles.get(c, slug, version)
    if not result:
        raise HTTPException(404, "channel version not found")
    return result


@router.put("/{slug}", dependencies=[Depends(owner)])
def save(slug: str, body: Save, s: Settings = Depends(settings),
         c: sqlite3.Connection = Depends(conn)):
    with tx(c):
        profiles.seed(c, s)
        current = profiles.get(c, slug)
        if not current:
            raise HTTPException(404, "channel not found")
        if current["version"] != body.base_version:
            raise HTTPException(409, "profile changed; reload")
        if body.profile.slug != slug:
            raise HTTPException(422, "slug differs from the channel URL")
        if not body.profile.presenter.avatar_id or not body.profile.presenter.voice_id:
            raise HTTPException(422, "choose a presenter and voice")
        try:
            profiles.verify_sound(s, body.profile.sound)
            profiles.verify_look(s, body.profile.look)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        target = body.profile.youtube_channel
        if target and target not in {ch["id"] for ch in youtube.channels(s.data_dir)}:
            raise HTTPException(422, "choose a connected YouTube channel")
        return profiles.save(c, body.profile, body.base_version + 1)


@router.delete("/{slug}", dependencies=[Depends(owner)])
def remove(slug: str, base_version: int | None = None, s: Settings = Depends(settings),
           c: sqlite3.Connection = Depends(conn)):
    with tx(c):
        profiles.seed(c, s)
        current = profiles.get(c, slug)
        if not current:
            raise HTTPException(404, "channel not found")
        if base_version is not None and base_version != current["version"]:
            raise HTTPException(409, "profile changed; reload")
        if slug == profiles.default(c):
            raise HTTPException(409, "choose another default before removing this channel")
        used = c.execute(
            "SELECT id FROM episodes WHERE COALESCE(json_extract(record_json,'$.profile_slug'),"
            "json_extract(record_json,'$.script.profile'),'danslab')=?"
            " OR json_extract(record_json,'$.script.profile')=?"
            " OR json_extract(record_json,'$.profile.slug')=? ORDER BY id",
            (slug, slug, slug),
        ).fetchall()
        if used:
            raise HTTPException(409, {"message": "channel is used by episodes",
                                      "episodes": [r["id"] for r in used]})
        c.execute("DELETE FROM channel_profiles WHERE slug=?", (slug,))
    return {"removed": slug}
