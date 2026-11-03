"""YouTube Data API v3: connect the channel (OAuth, installed-app flow) and upload takes.

The OAuth client (Google Cloud → Desktop app JSON) and one refresh token per connected channel
(<data_dir>/youtube/channels/<UC…>.json) live in <data_dir>/youtube/ (0600). A Google sign-in
grants one channel, so each channel is connected on its own. Secrets are sent only to Google
and never logged or returned. Uploads are resumable: the session URL is saved before any bytes
go out, so a retried job continues where it stopped and never creates a second video."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com"
SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"  # upload + captions + read channel
PRIVACY = ("private", "unlisted", "public")
CHANNEL_ID = re.compile(r"^UC[0-9A-Za-z_-]{22}$")
CHUNK = 8 * 1024 * 1024  # resumable chunks must be multiples of 256 KiB
TIMEOUT_S = 120
REFRESH_MARGIN_S = 60

#: (request) → (status, headers, body). Tests replace it with a fake Google.
Transport = Callable[[urllib.request.Request], tuple[int, dict[str, str], bytes]]


class YouTubeError(RuntimeError):
    pass


def _urlopen(req: urllib.request.Request) -> tuple[int, dict[str, str], bytes]:
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:  # noqa: S310 (fixed https hosts)
            return r.status, dict(r.headers.items()), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers.items()), e.read()


# ------------------------------------------------------------------ files


def folder(data_dir: Path) -> Path:
    return data_dir / "youtube"


def _read(p: Path) -> dict[str, Any] | None:
    return json.loads(p.read_text()) if p.exists() else None


def _write_private(p: Path, obj: dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f)
    tmp.replace(p)


def _is_desktop_client(p: Path) -> bool:
    try:
        return isinstance(json.loads(p.read_text()).get("installed"), dict)
    except (OSError, json.JSONDecodeError, AttributeError):
        return False


def find_download(downloads: Path) -> Path | None:
    """The newest Desktop-app OAuth client JSON Google Cloud saved to Downloads (web clients,
    which other projects download there too, are skipped)."""
    found = sorted(downloads.glob("client_secret_*.json"), key=lambda p: p.stat().st_mtime)
    return next((p for p in reversed(found) if _is_desktop_client(p)), None)


def import_client(data_dir: Path, src: Path) -> dict[str, str]:
    """Move a Desktop-app OAuth client JSON into the private folder. Returns non-secret facts."""
    try:
        data = json.loads(src.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise YouTubeError(f"could not read {src.name}") from e
    app = data.get("installed")
    if not isinstance(app, dict) or not app.get("client_id") or not app.get("client_secret"):
        raise YouTubeError("not a Desktop app OAuth client (expected an 'installed' client JSON)")
    _write_private(folder(data_dir) / "client.json", {"installed": app})
    src.unlink()
    return {"project_id": app.get("project_id", ""), "client_id": app["client_id"]}


def _channel_file(data_dir: Path, channel_id: str) -> Path:
    if not CHANNEL_ID.match(channel_id):
        raise YouTubeError("bad channel id")
    return folder(data_dir) / "channels" / f"{channel_id}.json"


def channels(data_dir: Path) -> list[dict[str, str]]:
    """Connected channels, by title."""
    found = []
    for p in (folder(data_dir) / "channels").glob("UC*.json"):
        tok = _read(p) or {}
        if tok.get("refresh_token") and tok.get("channel"):
            found.append(tok["channel"])
    return sorted(found, key=lambda c: c["title"].lower())


def status(data_dir: Path) -> dict[str, Any]:
    connected = channels(data_dir)
    return {
        "client": (folder(data_dir) / "client.json").exists(),
        "connected": bool(connected),
        "channels": connected,
    }


def disconnect(data_dir: Path, channel_id: str) -> None:
    _channel_file(data_dir, channel_id).unlink(missing_ok=True)


def pick_channel(data_dir: Path, channel_id: str | None) -> str:
    """The channel to upload to: the one named, or the only one connected."""
    connected = [c["id"] for c in channels(data_dir)]
    if channel_id:
        if channel_id not in connected:
            raise YouTubeError(f"channel {channel_id} is not connected")
        return channel_id
    if len(connected) == 1:
        return connected[0]
    if not connected:
        raise YouTubeError("YouTube is not connected: Connect a channel first")
    raise YouTubeError("several channels are connected: say which one")


def _client(data_dir: Path) -> dict[str, str]:
    c = _read(folder(data_dir) / "client.json")
    if not c:
        raise YouTubeError("no OAuth client: download the Desktop app JSON and import it")
    return c["installed"]


# ------------------------------------------------------------------ OAuth


def auth_url(data_dir: Path, redirect_uri: str) -> str:
    """Start the consent flow (PKCE). The state and verifier wait in pending.json."""
    app = _client(data_dir)
    verifier = secrets.token_urlsafe(48)
    state = secrets.token_urlsafe(24)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    _write_private(
        folder(data_dir) / "pending.json",
        {"state": state, "verifier": verifier, "redirect_uri": redirect_uri, "at": time.time()},
    )
    q = {
        "client_id": app["client_id"], "redirect_uri": redirect_uri, "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "state": state,
        "prompt": "select_account consent",  # always show the account and channel picker
        "code_challenge": challenge.decode(), "code_challenge_method": "S256",
    }  # fmt: skip
    return f"{AUTH_URL}?{urllib.parse.urlencode(q)}"


def _post_form(send: Transport, url: str, form: dict[str, str]) -> dict[str, Any]:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(form).encode(), method="POST")
    req.add_header("content-type", "application/x-www-form-urlencoded")
    code, _, body = send(req)
    data = json.loads(body or b"{}")
    if code != 200:
        raise YouTubeError(f"Google sign-in failed: {data.get('error_description') or code}")
    return data


def finish_auth(
    data_dir: Path, state: str, code: str, transport: Transport | None = None
) -> dict[str, Any]:
    """Exchange the code for tokens, look up the channel they grant, and save them under it."""
    d = folder(data_dir)
    pending = _read(d / "pending.json")
    if not pending or not secrets.compare_digest(pending["state"], state):
        raise YouTubeError("this sign-in link is stale: start Connect again")
    app = _client(data_dir)
    send = transport or _urlopen
    tok = _post_form(send, TOKEN_URL, {
        "code": code, "client_id": app["client_id"], "client_secret": app["client_secret"],
        "redirect_uri": pending["redirect_uri"], "grant_type": "authorization_code",
        "code_verifier": pending["verifier"],
    })  # fmt: skip
    (d / "pending.json").unlink(missing_ok=True)
    if not tok.get("refresh_token"):
        raise YouTubeError("Google returned no refresh token: remove the app's access and retry")
    token = {
        "refresh_token": tok["refresh_token"],
        "access_token": tok["access_token"],
        "expires_at": time.time() + int(tok.get("expires_in", 3600)),
    }
    probe = Client(data_dir, None, transport, token=token)
    items = probe.json("GET", "/youtube/v3/channels?part=snippet&mine=true").get("items") or []
    if not items:
        raise YouTubeError("that Google account has no YouTube channel: pick a channel")
    channel = {"id": items[0]["id"], "title": items[0]["snippet"]["title"]}
    _write_private(_channel_file(data_dir, channel["id"]), {**token, "channel": channel})
    return {"channel": channel}


# ------------------------------------------------------------------ API client


class Client:
    """Calls for one connected channel. `token` is only for the sign-in probe, before the
    channel is known and saved."""

    def __init__(
        self,
        data_dir: Path,
        channel_id: str | None,
        transport: Transport | None = None,
        token: dict[str, Any] | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.channel_id = channel_id
        self.send = transport or _urlopen
        self.fixed = token

    def _token(self) -> str:
        if self.fixed:
            return self.fixed["access_token"]
        p = _channel_file(self.data_dir, self.channel_id or "")
        tok = _read(p)
        if not tok or not tok.get("refresh_token"):
            raise YouTubeError(f"channel {self.channel_id} is not connected")
        if tok.get("expires_at", 0) - REFRESH_MARGIN_S > time.time():
            return tok["access_token"]
        app = _client(self.data_dir)
        fresh = _post_form(self.send, TOKEN_URL, {
            "client_id": app["client_id"], "client_secret": app["client_secret"],
            "refresh_token": tok["refresh_token"], "grant_type": "refresh_token",
        })  # fmt: skip
        tok = {**tok, "access_token": fresh["access_token"],
               "expires_at": time.time() + int(fresh.get("expires_in", 3600))}  # fmt: skip
        _write_private(p, tok)
        return tok["access_token"]

    def call(
        self,
        method: str,
        url: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        full = url if url.startswith("https://") else f"{API}{url}"
        req = urllib.request.Request(full, data=body, method=method)
        req.add_header("authorization", f"Bearer {self._token()}")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        return self.send(req)

    def json(self, method: str, url: str, body: Any = None) -> dict[str, Any]:
        data = json.dumps(body).encode() if body is not None else None
        code, _, raw = self.call(method, url, data, {"content-type": "application/json"})
        if code >= 300:
            raise YouTubeError(f"YouTube {code}: {_reason(raw)}")
        return json.loads(raw or b"{}")


def _reason(raw: bytes) -> str:
    try:
        err = json.loads(raw).get("error", {})
        return err.get("message") or str(err)
    except (json.JSONDecodeError, AttributeError):
        return raw[:200].decode(errors="replace")


def _header(headers: dict[str, str], name: str) -> str | None:
    return next((v for k, v in headers.items() if k.lower() == name), None)


# ------------------------------------------------------------------ upload


def clean_meta(title: str, description: str, tags: list[str], privacy: str) -> dict[str, Any]:
    """YouTube's limits: title 1–100 chars, description ≤5000 bytes, tags ≤500 chars in all,
    no angle brackets in title or description."""
    if privacy not in PRIVACY:
        raise YouTubeError(f"privacy must be one of {', '.join(PRIVACY)}")
    title = " ".join(title.replace("<", "").replace(">", "").split())[:100]
    if not title:
        raise YouTubeError("a title is needed")
    description = description.replace("<", "").replace(">", "")
    description = description.encode()[:5000].decode(errors="ignore")
    kept: list[str] = []
    for t in (t.strip() for t in tags):
        if t and sum(len(x) + 1 for x in [*kept, t]) <= 500:
            kept.append(t)
    return {"title": title, "description": description, "tags": kept, "privacy": privacy}


def _offset(api: Client, session: str, size: int) -> int | None:
    """Bytes Google already has, or None when the session is gone."""
    code, headers, _ = api.call("PUT", session, b"", {"content-range": f"bytes */{size}"})
    if code in (404, 410):
        return None
    if code == 308:
        rng = _header(headers, "range")
        return int(rng.rsplit("-", 1)[1]) + 1 if rng else 0
    if code in (200, 201):
        return size
    raise YouTubeError(f"YouTube {code} while resuming the upload")


def upload(
    api: Client, mp4: Path, meta: dict[str, Any], state_file: Path,
    progress: Callable[[float], None] = lambda _p: None,
) -> str:  # fmt: skip
    """Resumable upload of `mp4`. Returns the video id. Safe to call again after a crash."""
    state = _read(state_file) or {}
    if state.get("video_id"):
        return state["video_id"]
    size = mp4.stat().st_size
    offset = _offset(api, state["session"], size) if state.get("session") else None
    if offset is None:
        body = {
            "snippet": {"title": meta["title"], "description": meta["description"],
                        "tags": meta["tags"], "categoryId": "28"},  # Science & Technology
            "status": {"privacyStatus": meta["privacy"], "selfDeclaredMadeForKids": False},
        }  # fmt: skip
        code, headers, raw = api.call(
            "POST", "/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
            json.dumps(body).encode(),
            {"content-type": "application/json", "x-upload-content-type": "video/mp4",
             "x-upload-content-length": str(size)},
        )  # fmt: skip
        session = _header(headers, "location")
        if code != 200 or not session:
            raise YouTubeError(f"YouTube {code}: {_reason(raw)}")
        state = {"session": session}
        _write_private(state_file, state)
        offset = 0
    with mp4.open("rb") as f:
        while True:
            f.seek(offset)
            chunk = f.read(CHUNK)
            end = offset + len(chunk) - 1
            code, headers, raw = api.call(
                "PUT", state["session"], chunk, {"content-range": f"bytes {offset}-{end}/{size}"}
            )
            if code in (200, 201):
                video_id = json.loads(raw)["id"]
                _write_private(state_file, {**state, "video_id": video_id})
                progress(1.0)
                return video_id
            if code != 308:
                raise YouTubeError(f"YouTube {code}: {_reason(raw)}")
            rng = _header(headers, "range")
            offset = int(rng.rsplit("-", 1)[1]) + 1 if rng else 0
            progress(offset / size)


def add_captions(api: Client, video_id: str, srt: Path, language: str) -> str:
    """Attach an SRT as a caption track. Returns the caption id."""
    boundary = secrets.token_hex(16)
    meta = {"snippet": {"videoId": video_id, "language": language, "name": "", "isDraft": False}}
    body = (
        f"--{boundary}\r\ncontent-type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(meta)}\r\n--{boundary}\r\ncontent-type: application/octet-stream\r\n\r\n"
    ).encode() + srt.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    code, _, raw = api.call(
        "POST", "/upload/youtube/v3/captions?uploadType=multipart&part=snippet", body,
        {"content-type": f"multipart/related; boundary={boundary}"},
    )  # fmt: skip
    if code >= 300:
        raise YouTubeError(f"captions: YouTube {code}: {_reason(raw)}")
    return json.loads(raw)["id"]


# ------------------------------------------------------------------ publish


def _rfc3339_future(value: str) -> str:
    """`publish_at` as YouTube wants it: RFC 3339, in the future."""
    import datetime as dt

    try:
        when = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e:
        raise YouTubeError("publish_at must be an RFC 3339 time") from e
    if when.tzinfo is None:
        raise YouTubeError("publish_at needs a time zone")
    if when <= dt.datetime.now(dt.UTC):
        raise YouTubeError("publish_at must be in the future")
    return when.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def set_status(
    api: Client, video_id: str, privacy: str, publish_at: str | None = None
) -> dict[str, Any]:
    """`videos.update` (part `status`): public now, or private with a scheduled release."""
    if privacy not in PRIVACY:
        raise YouTubeError(f"privacy must be one of {', '.join(PRIVACY)}")
    status: dict[str, Any] = {"privacyStatus": privacy}
    if publish_at:
        status = {"privacyStatus": "private", "publishAt": _rfc3339_future(publish_at)}
    out = api.json(
        "PUT", "/youtube/v3/videos?part=status", {"id": video_id, "status": status}
    )
    st = out.get("status") or status
    return {"privacy": st.get("privacyStatus"), "publish_at": st.get("publishAt")}


def video_status(api: Client, video_id: str) -> dict[str, Any]:
    """`{privacy, publish_at}` as YouTube reports them now."""
    out = api.json("GET", f"/youtube/v3/videos?part=status&id={video_id}")
    items = out.get("items") or []
    if not items:
        raise YouTubeError(f"video {video_id} not found")
    st = items[0].get("status") or {}
    return {"privacy": st.get("privacyStatus"), "publish_at": st.get("publishAt")}
