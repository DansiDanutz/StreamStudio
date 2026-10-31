import json

import pytest
from fastapi.testclient import TestClient

from streamstudio.api.main import create_app
from streamstudio.core import db, heygen
from streamstudio.core.config import Settings
from streamstudio.worker import handlers
from streamstudio.worker.main import run_one

KEY = "sk_test_ABCDEFGHIJKLMNOP1234"


class FakeHeyGen:
    """Stands in for api.heygen.com and the presigned download host."""

    def __init__(self):
        self.calls = []
        self.polls = 0

    def __call__(self, req):
        url, method = req.full_url, req.get_method()
        self.calls.append((method, url.replace("https://api.heygen.com", "")))
        if "files.heygen" in url:
            assert req.get_header("X-api-key") is None  # never send the key to the CDN
            return 200, b"\x00\x00\x00\x18ftypmp42fake-mp4"
        assert req.get_header("X-api-key") == KEY
        if url.endswith("/v3/users/me"):
            body = {
                "billing_type": "subscription",
                "subscription": {"credits": {"premium_credits": {"remaining": 200}}},
            }
            return 200, json.dumps({"data": body}).encode()
        if "/v3/avatars/looks" in url:
            return 200, json.dumps(
                {
                    "data": [
                        {
                            "id": "look1",
                            "name": "Dan in his studio",
                            "avatar_type": "photo_avatar",
                            "default_voice_id": "v1",
                        }
                    ],
                    "has_more": False,
                }
            ).encode()
        if url.endswith("/v3/assets"):
            assert b"RIFF" in req.data
            return 200, json.dumps({"data": {"asset_id": "asset_silence"}}).encode()
        if url.endswith("/v3/videos") and method == "POST":
            self.spec = json.loads(req.data)
            return 200, json.dumps({"data": {"video_id": "vid_1", "status": "waiting"}}).encode()
        if url.endswith("/v3/videos/vid_1"):
            self.polls += 1
            if self.polls < 2:
                return 200, json.dumps({"data": {"status": "processing"}}).encode()
            return 200, json.dumps(
                {"data": {"status": "completed", "video_url": "https://files.heygen.ai/x.mp4"}}
            ).encode()
        return 404, b"{}"


@pytest.fixture
def env(tmp_path, monkeypatch):
    fake = FakeHeyGen()
    monkeypatch.setattr(handlers, "HEYGEN_TRANSPORT", fake)
    monkeypatch.setattr(handlers, "HEYGEN_POLL_S", 0)
    monkeypatch.setattr(handlers, "CUTOUT", None)
    s = Settings(
        data_dir=tmp_path / "data",
        import_roots=[],
        allow_tailnet=True,
        assets_dir=tmp_path / "assets",
    )
    return TestClient(create_app(s)), s, fake


def test_key_is_saved_privately_and_masked(env):
    client, s, _ = env
    r = client.put("/api/heygen/config", json={"api_key": KEY})
    assert r.json()["api_key"] == "••••1234" and KEY not in r.text
    assert oct(heygen.config_path(s.data_dir).stat().st_mode)[-3:] == "600"
    assert client.put("/api/heygen/config", json={"api_key": "bad key"}).status_code == 422
    looks = client.get("/api/heygen/looks").json()
    assert looks[0]["id"] == "look1"
    assert client.get("/api/heygen/account").json()["premium_remaining"] == 200


def test_render_needs_confirmation_then_runs_once(env):
    client, s, fake = env
    client.put("/api/heygen/config", json={"api_key": KEY, "avatar_id": "look1", "voice_id": "v1"})
    items = [
        {
            "kind": "gesture",
            "gesture": "point-up-right",
            "silent_s": 3,
            "motion": "points up-right",
        },
        {"kind": "segment", "script": "Let me show you Fake-Real, live.", "segment_id": "seg_1"},
    ]
    est = client.post("/api/heygen/render", json={"items": items}).json()
    assert est["clips"] == 2 and est["jobs"] == [] and est["seconds"] > 3
    assert not [c for c in fake.calls if c[0] == "POST"]  # nothing paid for yet
    got = client.post("/api/heygen/render", json={"items": items[:1], "confirm": True}).json()
    assert len(got["jobs"]) == 1
    c = db.connect(s.db_path)
    assert run_one(c, s, "w")
    clip = s.assets_dir / "avatar" / "gestures" / "point-up-right.mp4"
    assert clip.exists()
    assert (
        fake.spec["audio_asset_id"] == "asset_silence"
        and fake.spec["motion_prompt"] == "points up-right"
    )
    creates = [x for x in fake.calls if x == ("POST", "/v3/videos")]
    assert len(creates) == 1
    # asking again: already rendered, nothing queued, nothing paid
    again = client.post("/api/heygen/render", json={"items": items[:1], "confirm": True}).json()
    assert (
        again["jobs"] == [] and again["ready"][0]["clip"] == "/avatar/gestures/point-up-right.mp4"
    )


def test_a_retried_job_resumes_instead_of_paying_twice(env):
    client, s, fake = env
    client.put("/api/heygen/config", json={"api_key": KEY, "avatar_id": "look1", "voice_id": "v1"})
    key = heygen.item_key("look1", "v1", "Hello.", None, None)
    (s.data_dir / "heygen").mkdir(parents=True)
    (s.data_dir / "heygen" / f"{key}.json").write_text(json.dumps({"video_id": "vid_1"}))
    client.post(
        "/api/heygen/render",
        json={"items": [{"kind": "segment", "script": "Hello."}], "confirm": True},
    )
    assert run_one(db.connect(s.db_path), s, "w")
    assert ("POST", "/v3/videos") not in fake.calls
    assert (s.assets_dir / "avatar" / "clips" / f"{key}.mp4").exists()
