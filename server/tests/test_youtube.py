"""YouTube: import the OAuth client, connect, resumable upload, captions. Google is faked."""

import json
import os
import urllib.parse
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from streamstudio.api.main import create_app
from streamstudio.api.routes import youtube as yt_routes
from streamstudio.core import db, youtube
from streamstudio.core.config import Settings
from streamstudio.worker import handlers
from streamstudio.worker.main import run_one

RID = "rec_20261101-020000"
CLIENT = {"installed": {"client_id": "cid.apps.googleusercontent.com", "client_secret": "s3cret",
                        "project_id": "streamstudio-test"}}  # fmt: skip
SESSION = "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=abc"
DANSLAB = {"id": "UCCPMUreEqO1x11YiAhzLusA", "title": "DansLab"}
DYKT = {"id": "UC7j29XhArv5tlRqQj2qAb4Q", "title": "Did You Know That?"}
#: sign-in code → (access token, refresh token, channel)
GRANTS = {"the-code": ("at-1", "rt-1", DANSLAB), "code-2": ("at-2", "rt-2", DYKT)}


class FakeGoogle:
    """Just enough of Google: tokens, channels.list, resumable videos.insert, captions.insert."""

    def __init__(self, drop_after_first_chunk: bool = False) -> None:
        self.calls: list[tuple[str, str]] = []
        self.received = b""
        self.size = 0
        self.inits = 0
        self.drop = drop_after_first_chunk
        self.captions: list[bytes] = []
        self.meta: dict = {}
        self.tokens: list[str] = []

    def __call__(self, req):
        url, method, body = req.full_url, req.get_method(), req.data or b""
        headers = {k.lower(): v for k, v in req.header_items()}
        self.calls.append((method, url.split("?")[0]))
        if url == youtube.TOKEN_URL:
            form = dict(urllib.parse.parse_qsl(body.decode()))
            assert form["client_secret"] == "s3cret"
            if form["grant_type"] == "authorization_code":
                assert form["code_verifier"]
                at, rt, _ = GRANTS[form["code"]]
                out = {"access_token": at, "refresh_token": rt, "expires_in": 3600}
            else:
                at = next(a for a, r, _ in GRANTS.values() if r == form["refresh_token"])
                out = {"access_token": at, "expires_in": 3600}
            return 200, {}, json.dumps(out).encode()
        token = headers["authorization"].removeprefix("Bearer ")
        self.tokens.append(token)
        if "/youtube/v3/channels" in url:
            ch = next(c for a, _, c in GRANTS.values() if a == token)
            items = [{"id": ch["id"], "snippet": {"title": ch["title"]}}]
            return 200, {}, json.dumps({"items": items}).encode()
        if "uploadType=resumable" in url:
            self.inits += 1
            self.meta = json.loads(body)
            self.size = int(headers["x-upload-content-length"])
            return 200, {"Location": SESSION}, b""
        if url == SESSION:
            rng = headers["content-range"]
            if rng.startswith("bytes */"):
                have = len(self.received)
                return 308, ({"Range": f"bytes=0-{have - 1}"} if have else {}), b""
            start = int(rng.split()[1].split("-")[0])
            assert start == len(self.received), "chunk must continue where Google stopped"
            self.received += body
            if self.drop:
                self.drop = False
                raise ConnectionResetError("network dropped")
            if len(self.received) < self.size:
                return 308, {"Range": f"bytes=0-{len(self.received) - 1}"}, b""
            return 200, {}, json.dumps({"id": "vid123"}).encode()
        if "/youtube/v3/captions" in url:
            self.captions.append(body)
            return 200, {}, json.dumps({"id": "cap1"}).encode()
        raise AssertionError(f"unexpected call {method} {url}")


@pytest.fixture
def env(tmp_path, monkeypatch):
    s = Settings(data_dir=tmp_path / "data", import_roots=[])
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    monkeypatch.setattr(yt_routes, "DOWNLOADS", downloads)
    google = FakeGoogle()
    monkeypatch.setattr(youtube, "_urlopen", google)
    monkeypatch.setattr(handlers, "YOUTUBE_TRANSPORT", google)
    monkeypatch.setattr(youtube, "CHUNK", 256 * 1024)
    client = TestClient(create_app(s))
    return client, s, downloads, google


def _connect(client: TestClient, downloads: Path, code: str = "the-code") -> None:
    if not client.get("/api/youtube").json()["client"]:
        (downloads / "client_secret_web.json").write_text(json.dumps({"web": {"client_id": "w"}}))
        (downloads / "client_secret_cid.json").write_text(json.dumps(CLIENT))
        assert client.post("/api/youtube/client").json()["project_id"] == "streamstudio-test"
    r = client.get("/api/youtube/connect", follow_redirects=False)
    assert r.status_code == 302
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(r.headers["location"]).query))
    assert q["code_challenge_method"] == "S256" and q["access_type"] == "offline"
    assert q["prompt"] == "select_account consent"  # always offer the channel picker
    assert q["redirect_uri"].startswith("http://127.0.0.1:")
    done = client.get(f"/api/youtube/callback?state={q['state']}&code={code}")
    assert done.status_code == 200 and GRANTS[code][2]["title"] in done.text


def test_import_moves_the_desktop_client_and_keeps_it_private(env):
    client, s, downloads, _ = env
    assert client.get("/api/youtube").json() == {
        "client": False, "connected": False, "channels": [], "download_ready": False,
    }  # fmt: skip
    assert client.post("/api/youtube/client").status_code == 404
    (downloads / "client_secret_web.json").write_text(json.dumps({"web": {"client_id": "w"}}))
    assert client.post("/api/youtube/client").status_code == 404  # web clients are skipped
    (downloads / "client_secret_cid.json").write_text(json.dumps(CLIENT))
    r = client.post("/api/youtube/client").json()
    assert r == {"project_id": "streamstudio-test", "client_id": CLIENT["installed"]["client_id"]}
    assert not (downloads / "client_secret_cid.json").exists()  # moved, not copied
    saved = youtube.folder(s.data_dir) / "client.json"
    assert oct(os.stat(saved).st_mode & 0o777) == "0o600"
    assert "s3cret" not in client.get("/api/youtube").text


def test_each_sign_in_connects_one_more_channel(env):
    client, s, downloads, _ = env
    _connect(client, downloads)
    _connect(client, downloads, "code-2")
    st = client.get("/api/youtube").json()
    assert st["connected"] and st["channels"] == [DANSLAB, DYKT]
    tok = youtube.folder(s.data_dir) / "channels" / f"{DANSLAB['id']}.json"
    assert oct(os.stat(tok).st_mode & 0o777) == "0o600"
    assert "rt-1" not in client.get("/api/youtube").text
    left = client.post("/api/youtube/disconnect", json={"channel": DYKT["id"]}).json()
    assert left["channels"] == [DANSLAB]
    bad = client.post("/api/youtube/disconnect", json={"channel": "../client"})
    assert bad.status_code == 422


def test_callback_rejects_a_forged_state(env):
    client, _, downloads, _ = env
    (downloads / "client_secret_cid.json").write_text(json.dumps(CLIENT))
    client.post("/api/youtube/client")
    client.get("/api/youtube/connect", follow_redirects=False)
    r = client.get("/api/youtube/callback?state=forged&code=the-code")
    assert r.status_code == 400 and not client.get("/api/youtube").json()["connected"]


def _take(s: Settings, size: int = 700 * 1024) -> None:
    d = s.recordings_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{RID}.mp4").write_bytes(os.urandom(size))
    (d / f"{RID}.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nSalut\n")
    (d / f"{RID}.transcript.json").write_text(json.dumps({"language": "ro"}))


def test_upload_is_private_by_default_and_adds_captions(env):
    client, s, downloads, google = env
    _connect(client, downloads)
    _take(s)
    r = client.post(f"/api/recordings/{RID}/youtube", json={"title": "My <first> take"})
    assert r.status_code == 202 and r.json()["privacy"] == "private"
    assert run_one(db.connect(s.db_path), s, "w1")
    job = client.get(f"/api/jobs/{r.json()['job_id']}").json()
    assert job["status"] == "done", job
    assert job["result"]["video_id"] == "vid123" and job["result"]["captions"] == "cap1"
    assert google.meta["status"]["privacyStatus"] == "private"
    assert google.meta["snippet"]["title"] == "My first take"
    assert google.received == (s.recordings_dir / f"{RID}.mp4").read_bytes()
    assert b'"language": "ro"' in google.captions[0] and b"Salut" in google.captions[0]


def test_a_dropped_upload_resumes_without_a_second_video(env):
    client, s, downloads, google = env
    _connect(client, downloads)
    _take(s)
    google.drop = True
    jid = client.post(f"/api/recordings/{RID}/youtube", json={"title": "Take"}).json()["job_id"]
    c = db.connect(s.db_path)
    assert run_one(c, s, "w1")  # fails mid-upload and is requeued
    assert client.get(f"/api/jobs/{jid}").json()["status"] == "queued"
    assert run_one(c, s, "w1")
    assert client.get(f"/api/jobs/{jid}").json()["status"] == "done"
    assert google.inits == 1  # one video, resumed
    assert google.received == (s.recordings_dir / f"{RID}.mp4").read_bytes()


def test_with_several_channels_the_upload_names_one(env):
    client, s, downloads, google = env
    _connect(client, downloads)
    _connect(client, downloads, "code-2")
    _take(s)
    url = f"/api/recordings/{RID}/youtube"
    assert client.post(url, json={"title": "T"}).status_code == 422  # which channel?
    other = {"title": "T", "channel": "UCxxxxxxxxxxxxxxxxxxxxxx"}
    assert client.post(url, json=other).status_code == 422  # not connected
    r = client.post(url, json={"title": "T", "channel": DYKT["id"]})
    assert r.status_code == 202 and r.json()["channel"] == DYKT["id"]
    # the same take can go to the other channel too: a separate job, not a duplicate
    r2 = client.post(url, json={"title": "T", "channel": DANSLAB["id"]})
    assert r2.json()["job_id"] != r.json()["job_id"]
    c = db.connect(s.db_path)
    assert run_one(c, s, "w1")
    done = client.get(f"/api/jobs/{r.json()['job_id']}").json()
    assert done["status"] == "done" and done["result"]["channel"] == DYKT["id"]
    assert "at-2" in google.tokens and "at-1" not in google.tokens[2:]


def test_upload_needs_a_connection_an_mp4_and_a_known_privacy(env):
    client, s, downloads, _ = env
    _take(s)
    assert client.post(f"/api/recordings/{RID}/youtube", json={"title": "x"}).status_code == 409
    _connect(client, downloads)
    bad = client.post(f"/api/recordings/{RID}/youtube", json={"title": "x", "privacy": "secret"})
    assert bad.status_code == 422
    other = "rec_20261101-030000"
    assert client.post(f"/api/recordings/{other}/youtube", json={"title": "x"}).status_code == 404


def test_clean_meta_respects_youtube_limits():
    m = youtube.clean_meta("a" * 150, "d" * 6000, ["t" * 300, "u" * 300, "v"], "unlisted")
    assert len(m["title"]) == 100 and len(m["description"].encode()) == 5000
    assert m["tags"] == ["t" * 300, "v"]
    with pytest.raises(youtube.YouTubeError):
        youtube.clean_meta("  ", "", [], "private")
