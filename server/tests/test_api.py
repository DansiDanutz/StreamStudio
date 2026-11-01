from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from streamstudio.api.main import create_app
from streamstudio.core import db
from streamstudio.core.config import Settings
from streamstudio.worker.main import run_one


@pytest.fixture
def env(tmp_path):
    settings = Settings(
        data_dir=tmp_path / "data", import_roots=[tmp_path / "media"], allow_tailnet=True
    )
    app = create_app(settings)
    return TestClient(app), settings


def test_health(env):
    client, _ = env
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] and "ffmpeg" in body["tools"]
    # the Mac app compares these with its own checkout to spot a stale server
    assert (Path(body["root"]) / "server" / "pyproject.toml").exists()
    assert body["rev"] is None or len(body["rev"]) == 40


def test_project_lifecycle_and_edl_versions(env):
    client, _ = env
    p = client.post("/api/projects", json={"name": "Episode 1"}).json()
    got = client.get(f"/api/projects/{p['id']}").json()
    assert got["edl_version"] == 1 and got["assets"] == []

    edl = client.get(f"/api/projects/{p['id']}/edl").json()
    assert edl["version"] == 1
    r = client.put(
        f"/api/projects/{p['id']}/edl",
        json={"base_version": 1, "edl": edl["edl"], "message": "no-op"},
    )
    assert r.json()["version"] == 2
    # stale base version is rejected
    r = client.put(f"/api/projects/{p['id']}/edl", json={"base_version": 1, "edl": edl["edl"]})
    assert r.status_code == 409
    assert [v["version"] for v in client.get(f"/api/projects/{p['id']}/edl/versions").json()] == [
        2,
        1,
    ]

    assert client.delete(f"/api/projects/{p['id']}").status_code == 204
    assert client.get(f"/api/projects/{p['id']}").status_code == 404


def test_import_path_is_guarded(env, tmp_path):
    client, _ = env
    p = client.post("/api/projects", json={"name": "x"}).json()
    outside = tmp_path / "elsewhere.mp4"
    outside.write_bytes(b"\0")
    r = client.post(f"/api/projects/{p['id']}/assets/import-path", json={"path": str(outside)})
    assert r.status_code == 400 and "outside" in r.json()["detail"]


def test_import_probe_job_runs(env, tmp_path):
    import shutil
    import subprocess

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    client, settings = env
    media = tmp_path / "media"
    media.mkdir()
    clip = media / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=30:duration=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-shortest",
            "-pix_fmt",
            "yuv420p",
            str(clip),
        ],
        check=True,
    )
    p = client.post("/api/projects", json={"name": "x"}).json()
    r = client.post(f"/api/projects/{p['id']}/assets/import-path", json={"path": str(clip)})
    assert r.status_code == 201, r.text
    job = r.json()["job"]
    assert job["status"] == "queued"

    conn = db.connect(settings.db_path)
    assert run_one(conn, settings, "test-worker")
    done = client.get(f"/api/jobs/{job['id']}").json()
    assert done["status"] == "done", done.get("error")
    assert abs(done["result"]["duration_us"] - 1_000_000) < 100_000
    asset = client.get(f"/api/projects/{p['id']}").json()["assets"][0]
    assert asset["status"] == "ready" and asset["probe_json"]["video"]["width"] == 320


def test_netguard_blocks_public_ip(env):
    from streamstudio.core.netguard import is_allowed

    assert is_allowed("127.0.0.1", True)
    assert is_allowed("100.101.102.103", True)
    assert not is_allowed("100.101.102.103", False)
    assert not is_allowed("8.8.8.8", True)
    assert is_allowed("::ffff:127.0.0.1", False)


def test_scenes_crud_is_idempotent_and_ordered(env):
    client, _ = env
    assert client.get("/api/scenes").json() == []
    body = {"name": "Studio desk", "collection": "Talk", "position": 2, "data": {"bezel": "studio"}}
    a = client.put("/api/scenes/scene_a", json=body)
    assert a.status_code == 200 and a.json()["bezel"] == "studio"
    assert client.put("/api/scenes/scene_a", json=body).status_code == 200  # same again: fine
    client.put(
        "/api/scenes/scene_b",
        json={"name": "World of AI", "collection": "Openers", "position": 1, "data": {}},
    )
    got = client.get("/api/scenes").json()
    assert [s["id"] for s in got] == ["scene_b", "scene_a"]
    assert got[1] == {
        "bezel": "studio",
        "id": "scene_a",
        "name": "Studio desk",
        "collection": "Talk",
        "position": 2,
        "updated_at": got[1]["updated_at"],
    }
    assert client.delete("/api/scenes/scene_a").status_code == 204
    assert client.delete("/api/scenes/scene_a").status_code == 204
    assert [s["id"] for s in client.get("/api/scenes").json()] == ["scene_b"]
    assert client.put("/api/scenes/bad id!", json=body).status_code == 422
    big = {**body, "data": {"x": "a" * 300_000}}
    assert client.put("/api/scenes/scene_c", json=big).status_code == 413


def test_recording_upload_becomes_mp4(env, tmp_path):
    import subprocess

    client, settings = env
    take = tmp_path / "take.webm"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=30:duration=1",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:v", "libvpx-vp9", "-b:v", "200k",
         "-c:a", "libopus", "-shortest", str(take)],
        check=True,
    )  # fmt: skip
    r = client.post(
        "/api/recordings", content=take.read_bytes(), headers={"content-type": "video/webm"}
    )
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    assert client.get(f"/api/recordings/{rid}.mp4").status_code == 404  # not encoded yet
    c = db.connect(settings.db_path)
    assert run_one(c, settings, "w1")
    rec = client.get("/api/recordings").json()[0]
    assert rec["id"] == rid and rec["mp4"]
    got = client.get(f"/api/recordings/{rid}.mp4")
    assert got.status_code == 200 and got.content[4:8] == b"ftyp"
    assert run_one(c, settings, "w1") is False  # nothing left; the job is done
    assert (
        client.post(
            "/api/recordings", content=b"", headers={"content-type": "video/webm"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/recordings", content=b"x", headers={"content-type": "text/plain"}
        ).status_code
        == 415
    )
    bad = client.get("/api/recordings/..%2Fsecret.mp4")
    assert bad.status_code in (404, 422)
    assert client.get("/api/recordings/rec_bad.mp4").status_code == 422


def test_live_config_keeps_the_key_secret(env):
    client, settings = env
    assert client.get("/api/live/config").json()["has_key"] is False
    r = client.put("/api/live/config", json={"stream_key": "abcd-efgh-ijkl-mnop-1234"})
    assert r.status_code == 200 and r.json()["stream_key"] == "••••1234"
    assert "abcd" not in r.text
    assert oct((settings.data_dir / "live.json").stat().st_mode)[-3:] == "600"
    # changing the server keeps the saved key
    r = client.put("/api/live/config", json={"rtmp_url": "rtmps://live.example.com/app"})
    assert r.json() == {
        "rtmp_url": "rtmps://live.example.com/app",
        "stream_key": "••••1234",
        "has_key": True,
    }
    assert client.put("/api/live/config", json={"rtmp_url": "http://evil"}).status_code == 422
    assert client.put("/api/live/config", json={"stream_key": "bad key!"}).status_code == 422


def test_live_ingest_pushes_through_ffmpeg(env, tmp_path):
    import subprocess

    client, settings = env
    with client.websocket_connect("/api/live/ws") as ws:  # no key yet: refused
        msg = ws.receive()
        assert msg["type"] == "websocket.close" and msg["code"] == 4400
    client.put("/api/live/config", json={"stream_key": "test-key-0001"})
    take = tmp_path / "in.webm"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=30:duration=2",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libvpx-vp9", "-b:v", "300k",
         "-c:a", "libopus", "-shortest", str(take)],
        check=True,
    )  # fmt: skip
    out = tmp_path / "out.flv"
    client.app.state.live_target_override = str(out)
    data = take.read_bytes()
    with client.websocket_connect("/api/live/ws") as ws:
        for i in range(0, len(data), 16384):
            ws.send_bytes(data[i : i + 16384])
        ws.send_text("stop")
        assert ws.receive()["type"] == "websocket.close"  # the server closes once ffmpeg is done
    import time

    for _ in range(100):  # ffmpeg flushes after the socket closes
        st = client.get("/api/live").json()
        if not st["live"]:
            break
        time.sleep(0.1)
    assert st["live"] is False and st["bytes_in"] == len(data) and st["error"] is None
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name", "-of", "csv=p=0",
         str(out)],
        capture_output=True, text=True, check=True,
    ).stdout.split()  # fmt: skip
    assert probe == ["h264", "aac"]


def test_health_reports_the_revision_the_server_started_with(env, monkeypatch):
    # A `git pull` after start must not make an old server look current.
    from streamstudio.api.routes import system

    client, _ = env
    started = client.get("/api/health").json()
    monkeypatch.setattr(system, "_git_head", lambda: "f" * 40)
    after_pull = client.get("/api/health").json()
    assert after_pull["rev"] == started["rev"] == system.STARTUP_REV
    assert after_pull["head"] == "f" * 40
    assert after_pull["stale"] is (started["rev"] is not None)


def test_health_is_not_stale_when_code_matches_checkout(env, monkeypatch):
    from streamstudio.api.routes import system

    client, _ = env
    monkeypatch.setattr(system, "_git_head", lambda: system.STARTUP_REV)
    assert client.get("/api/health").json()["stale"] is False
