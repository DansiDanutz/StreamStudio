"""The vault (copies off this machine) and the library's names, tags and groups."""

from __future__ import annotations

import datetime as dt
import hashlib
import urllib.parse

import pytest
from fastapi.testclient import TestClient

from streamstudio.api.main import create_app
from streamstudio.core import db, vault
from streamstudio.core.config import Settings
from streamstudio.worker.main import run_one


def work(s: Settings) -> bool:
    c = db.connect(s.db_path)
    try:
        return run_one(c, s, "t")
    finally:
        c.close()


@pytest.fixture
def env(tmp_path):
    assets = tmp_path / "assets"
    (assets / "avatar" / "clips").mkdir(parents=True)
    (assets / "avatar" / "gestures").mkdir(parents=True)
    (assets / "avatar" / "clips" / "intro-hello.mp4").write_bytes(b"clip-bytes" * 100)
    (assets / "avatar" / "gestures" / "wave.cutout.webm").write_bytes(b"wave" * 50)
    s = Settings(
        data_dir=tmp_path / "data", assets_dir=assets, allow_tailnet=False, ffmpeg_bin="ffmpeg"
    )
    rec = s.recordings_dir
    rec.mkdir(parents=True, exist_ok=True)
    (rec / "rec_20261031-234012.mp4").write_bytes(b"take" * 1000)
    return TestClient(create_app(s)), s, tmp_path


def test_sigv4_matches_the_aws_example():
    # "GET Object" example from the AWS Signature Version 4 documentation
    h = vault.sigv4_headers(
        "GET", "https://examplebucket.s3.amazonaws.com/test.txt", "us-east-1",
        "AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        hashlib.sha256(b"").hexdigest(), dt.datetime(2013, 5, 24, tzinfo=dt.UTC),
        {"range": "bytes=0-9"},
    )  # fmt: skip
    assert h["authorization"].endswith(
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
    )


def test_folder_vault_push_evict_and_fetch_back(env):
    client, s, tmp = env
    cloud = tmp / "iCloud" / "StreamStudio"
    assert client.get("/api/vault").json()["configured"] is False
    assert client.post("/api/vault/push").status_code == 409
    r = client.put("/api/vault", json={"kind": "folder", "path": str(cloud)})
    assert r.status_code == 200, r.text
    assert r.json()["not_backed_up"] == 3

    job = client.post("/api/vault/push").json()
    assert work(s) and client.get(f"/api/jobs/{job['id']}").json()["status"] == "done"
    st = client.get("/api/vault").json()
    assert st["in_vault"] == 3 and st["not_backed_up"] == 0
    assert (cloud / "streamstudio/recordings/rec_20261031-234012.mp4").exists()
    assert (cloud / "streamstudio/catalog/catalog.json").exists()

    # a second push uploads nothing
    client.post("/api/vault/push")
    work(s)
    assert client.get("/api/vault").json()["last_push"]["status"] == "done"

    # free space, then the take comes back the first time it is used
    key = "recordings/rec_20261031-234012.mp4"
    r = client.post("/api/vault/evict", json={"key": key})
    assert r.status_code == 200 and not (s.recordings_dir / key.split("/")[1]).exists()
    lib = client.get("/api/library", params={"group": "Recordings"}).json()["artifacts"]
    assert lib[0]["storage"] == {"key": key, "local": False, "vault": True}
    assert lib[0]["name"] == "Take · 31 Oct 2026 · 23:40:12"
    got = client.get("/api/recordings/rec_20261031-234012.mp4")
    assert got.status_code == 200 and got.content == b"take" * 1000

    # a changed local file can't be evicted until it is backed up again
    (s.assets_dir / "avatar/clips/intro-hello.mp4").write_bytes(b"new")
    r = client.post("/api/vault/evict", json={"key": "assets/avatar/clips/intro-hello.mp4"})
    assert r.status_code == 409
    assert client.post("/api/vault/fetch", json={"key": "../../etc/passwd"}).status_code == 422


def test_names_tags_groups_and_restore_on_a_new_machine(env, tmp_path):
    client, s, tmp = env
    cloud = tmp / "cloud"
    client.put("/api/vault", json={"kind": "folder", "path": str(cloud)})
    client.put("/api/scenes/sc1", json={"name": "Desk intro", "collection": "Openers", "data": {}})
    r = client.patch(
        "/api/library/clip:intro-hello", json={"title": "Hello opener", "tags": ["intro", "ep12"]}
    )
    assert r.status_code == 200 and r.json()["name"] == "Hello opener"
    lib = client.get("/api/library").json()
    assert {"Scenes", "Avatar", "Recordings"} <= set(lib["groups"]) and lib["tags"] == [
        "ep12",
        "intro",
    ]
    found = client.get("/api/library", params={"q": "hello opener", "tag": "ep12"}).json()
    assert [a["id"] for a in found["artifacts"]] == ["clip:intro-hello"]
    assert client.patch("/api/library/clip:nope", json={"title": "x"}).status_code == 404
    client.post("/api/vault/push")
    work(s)

    # another machine: empty data and assets, same vault
    s2 = Settings(data_dir=tmp_path / "data2", assets_dir=tmp_path / "assets2", allow_tailnet=False)
    c2 = TestClient(create_app(s2))
    c2.put("/api/vault", json={"kind": "folder", "path": str(cloud)})
    r = c2.post("/api/vault/sync").json()
    assert r["scenes"] == 1 and r["names"] == 1 and r["vault_only"] == 3
    clip = c2.get("/api/library/clip:intro-hello").json()
    assert clip["name"] == "Hello opener" and clip["storage"]["local"] is False
    assert c2.post("/api/vault/fetch", json={"key": clip["storage"]["key"]}).json()["local"]
    assert (s2.assets_dir / "avatar/clips/intro-hello.mp4").read_bytes() == b"clip-bytes" * 100


class FakeBucket:
    """Just enough S3 for the backend: PUT, GET, HEAD and ListObjectsV2, checking signatures."""

    def __init__(self):
        self.objects: dict[str, tuple[bytes, str]] = {}

    def __call__(self, req):
        assert req.get_header("Authorization").startswith("AWS4-HMAC-SHA256 Credential=AK/")
        u = urllib.parse.urlsplit(req.full_url)
        path = u.path.removeprefix("/storage/v1/s3")
        _, bucket, *key = path.split("/", 2)
        key = urllib.parse.unquote(key[0]) if key else ""
        m = req.get_method()
        if m == "PUT":
            data = req.data.read()
            self.objects[key] = (data, req.get_header("X-amz-meta-sha256"))
            return 200, {}, b""
        if m in ("GET", "HEAD") and key:
            if key not in self.objects:
                return 404, {}, b""
            data, sha = self.objects[key]
            h = {"content-length": str(len(data)), "x-amz-meta-sha256": sha}
            return 200, h, (data if m == "GET" else b"")
        q = dict(urllib.parse.parse_qsl(u.query))
        items = "".join(
            f"<Contents><Key>{k}</Key><Size>{len(v[0])}</Size></Contents>"
            for k, v in sorted(self.objects.items()) if k.startswith(q.get("prefix", ""))
        )  # fmt: skip
        ns = "http://s3.amazonaws.com/doc/2006-03-01/"
        return (
            200,
            {},
            (
                f'<ListBucketResult xmlns="{ns}"><IsTruncated>false</IsTruncated>'
                f"{items}</ListBucketResult>"
            ).encode(),
        )


def test_s3_vault_keeps_secrets_masked(env, monkeypatch):
    client, s, _ = env
    bucket = FakeBucket()
    monkeypatch.setattr(vault, "S3_TRANSPORT", bucket)
    cfg = {
        "kind": "s3", "endpoint": "https://abc.supabase.co/storage/v1/s3", "region": "eu-central-1",
        "bucket": "studio", "access_key": "AK", "secret_key": "SECRET-123456",
    }  # fmt: skip
    r = client.put("/api/vault", json=cfg)
    assert r.status_code == 200, r.text
    assert r.json()["config"]["secret_key"] == "••••3456" and "SECRET" not in r.text
    # re-saving with blank keys keeps the saved ones
    r = client.put("/api/vault", json={**cfg, "access_key": "", "secret_key": ""})
    assert r.status_code == 200
    client.post("/api/vault/push")
    work(s)
    assert "streamstudio/assets/avatar/gestures/wave.cutout.webm" in bucket.objects
    gest = client.get("/api/vault").json()
    assert gest["in_vault"] == 3
    r = client.put("/api/vault", json={**cfg, "endpoint": "http://plain.example"})
    assert r.status_code == 422
