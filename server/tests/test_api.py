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
        "bezel": "studio", "id": "scene_a", "name": "Studio desk", "collection": "Talk",
        "position": 2, "updated_at": got[1]["updated_at"],
    }
    assert client.delete("/api/scenes/scene_a").status_code == 204
    assert client.delete("/api/scenes/scene_a").status_code == 204
    assert [s["id"] for s in client.get("/api/scenes").json()] == ["scene_b"]
    assert client.put("/api/scenes/bad id!", json=body).status_code == 422
    big = {**body, "data": {"x": "a" * 300_000}}
    assert client.put("/api/scenes/scene_c", json=big).status_code == 413
