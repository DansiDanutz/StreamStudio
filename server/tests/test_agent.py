import json

import pytest
from fastapi.testclient import TestClient

from streamstudio import mcp
from streamstudio.api.main import create_app
from streamstudio.core.config import Settings


@pytest.fixture
def client(tmp_path):
    s = Settings(
        data_dir=tmp_path / "d", import_roots=[], allow_tailnet=True, assets_dir=tmp_path / "a"
    )
    (tmp_path / "a" / "avatar" / "clips").mkdir(parents=True)
    (tmp_path / "a" / "avatar" / "clips" / "abc123.mp4").write_bytes(b"x")
    return TestClient(create_app(s))


def test_library_merges_editor_and_server_artifacts(client):
    web = {
        "artifacts": [
            {"id": "gesture:wave", "kind": "gesture", "name": "Wave", "description": "",
             "actions": [{"action": "gesture.play", "args": {"id": "wave"}}]},
        ],
        "actions": [{"action": "gesture.play", "description": "", "args": {"id": "gesture id"}}],
    }  # fmt: skip
    assert client.post("/api/library/web", json=web).status_code == 204
    client.put(
        "/api/scenes/studio-solo", json={"name": "Studio Solo", "collection": "Talk", "data": {}}
    )
    lib = client.get("/api/library").json()
    assert {"gesture", "scene", "clip"} <= set(lib["kinds"])
    assert lib["editor_online"] is False
    scene = client.get("/api/library/scene:studio-solo").json()
    assert scene["actions"] == [{"action": "scene.activate", "args": {"id": "studio-solo"}}]
    assert client.get("/api/library?kind=gesture").json()["artifacts"][0]["id"] == "gesture:wave"
    assert client.get("/api/library?q=wave").json()["artifacts"][0]["name"] == "Wave"
    assert client.get("/api/library/nope:1").status_code == 404


def test_actions_need_the_editor_and_state_is_reported(client):
    r = client.post("/api/agent/do", json={"action": "cue.apply", "args": {"cue": "pip"}})
    assert r.status_code == 409 and "editor" in r.json()["detail"]
    client.post(
        "/api/agent/state", json={"scene": {"id": "studio-solo"}, "cue": "pip", "secret": 1}
    )
    st = client.get("/api/agent/state").json()
    assert st["cue"] == "pip" and "secret" not in st


def test_mcp_speaks_json_rpc_and_never_renders(monkeypatch):
    calls = []
    monkeypatch.setattr(mcp, "_http", lambda m, p, b=None: calls.append((m, p, b)) or {"ok": True})
    init = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init["result"]["serverInfo"]["name"] == "streamstudio"
    names = [
        t["name"]
        for t in mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    ]
    assert names == ["library_list", "library_get", "studio_state", "studio_do", "heygen_estimate"]
    do = {"name": "studio_do", "arguments": {"action": "point.at", "args": {"target": "main"}}}
    out = mcp.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": do})
    assert json.loads(out["result"]["content"][0]["text"]) == {"ok": True}
    est = {"name": "heygen_estimate", "arguments": {"items": [{"kind": "segment", "script": "Hi"}]}}
    mcp.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": est})
    assert calls[-1] == (
        "POST",
        "/api/heygen/render",
        {"items": [{"kind": "segment", "script": "Hi"}], "confirm": False},
    )
    assert mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    bad = mcp.handle(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "nope", "arguments": {}},
        }
    )
    assert bad["result"]["isError"] is True
