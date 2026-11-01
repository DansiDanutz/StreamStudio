"""Network guard: only loopback/tailnet peers, only our own host names, no cross-site writes."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from streamstudio.api.main import create_app
from streamstudio.core.config import Settings
from streamstudio.core.netguard import host_allowed


@pytest.fixture
def client(tmp_path):
    s = Settings(data_dir=tmp_path / "data", import_roots=[], extra_hosts=["studio.example"])
    return TestClient(create_app(s))


@pytest.mark.parametrize(
    "host",
    ["localhost", "localhost:5173", "127.0.0.1:8787", "[::1]:8787", "100.101.102.103",
     "mac-studio.tail1234.ts.net", "mac-studio", "studio.example", "testserver"],
)
def test_own_host_names_are_allowed(host):
    assert host_allowed(host, extra=["studio.example"])


@pytest.mark.parametrize(
    "host", ["evil.example", "localhost.evil.example", "ts.net.evil.example", "", None]
)
def test_other_host_names_are_rejected(host):
    # DNS rebinding: an attacker's domain re-pointed at 127.0.0.1 still carries the attacker's Host.
    assert not host_allowed(host, extra=["studio.example"])


def test_request_with_foreign_host_is_rejected(client):
    r = client.get("/api/health", headers={"host": "evil.example"})
    assert r.status_code == 403


def test_request_with_own_host_passes(client):
    assert client.get("/api/health", headers={"host": "localhost:8787"}).status_code == 200


def test_cross_site_write_is_rejected(client):
    r = client.put("/api/scenes/x", json={"name": "x", "data": {}}, headers={"origin": "https://evil.example"})
    assert r.status_code == 403


def test_null_origin_write_is_rejected(client):
    r = client.put("/api/scenes/x", json={"name": "x", "data": {}}, headers={"origin": "null"})
    assert r.status_code == 403


def test_same_site_write_passes(client):
    r = client.put("/api/scenes/x", json={"name": "x", "data": {}}, headers={"origin": "http://localhost:5173"})
    assert r.status_code < 400


def test_write_without_origin_passes(client):
    # Agents, MCP and curl send no Origin: network guard + host check still apply.
    assert client.put("/api/scenes/x", json={"name": "x", "data": {}}).status_code < 400


def test_cross_site_read_is_allowed_but_not_shared(client):
    # Reads are harmless without CORS headers: the browser will not hand the body to the page.
    r = client.get("/api/health", headers={"origin": "https://evil.example"})
    assert r.status_code == 200
    assert "access-control-allow-origin" not in r.headers


def test_cross_site_websocket_is_rejected(client):
    evil = {"origin": "https://evil.example"}
    ws_url = "/api/live/ws"
    with pytest.raises(WebSocketDisconnect), client.websocket_connect(ws_url, headers=evil) as ws:
        ws.receive_text()
