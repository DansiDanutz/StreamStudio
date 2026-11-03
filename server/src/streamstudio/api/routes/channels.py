from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import Field

from ...core import netguard, youtube
from ...core.config import Settings
from ...core.db import tx
from ...episode import profiles
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
        target = body.profile.youtube_channel
        if target and target not in {ch["id"] for ch in youtube.channels(s.data_dir)}:
            raise HTTPException(422, "choose a connected YouTube channel")
        return profiles.save(c, body.profile, body.base_version + 1)
