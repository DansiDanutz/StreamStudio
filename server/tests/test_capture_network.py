import socket
from unittest.mock import MagicMock

import pytest

from streamstudio.episode import capture_network as network


def answer(address):
    return (socket.AF_INET6 if ":" in address else socket.AF_INET, socket.SOCK_STREAM, 6,
            "", (address, 443))


@pytest.mark.parametrize("private", ["127.0.0.1", "192.168.1.1", "169.254.169.254", "100.64.0.1",
                                     "::1", "fd00::1", "::ffff:127.0.0.1", "224.0.0.1"])
def test_mixed_dns_answers_fail_before_any_connection(monkeypatch, private):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [answer("8.8.8.8"), answer(private)])
    with pytest.raises(ValueError):
        network.CaptureOrigin("example.test")


def test_capture_pins_address_and_tls_name_across_rebinding(monkeypatch):
    dns = MagicMock(side_effect=[[answer("8.8.8.8")], [answer("127.0.0.1")]])
    monkeypatch.setattr(socket, "getaddrinfo", dns)
    origin = network.CaptureOrigin("example.test")
    sock = MagicMock()
    monkeypatch.setattr(socket, "socket", MagicMock(return_value=sock))
    origin.tls = MagicMock()
    conn = MagicMock()
    monkeypatch.setattr(network.http.client, "HTTPConnection", MagicMock(return_value=conn))
    res = conn.getresponse.return_value
    res.status = 200
    res.read.return_value = b"page"
    res.getheaders.return_value = [("Content-Type", "text/plain"), ("Set-Cookie", "private")]
    for _ in range(2):
        got = origin.fetch("https://example.test/page?id=1", "GET", {"cookie": "private"})
        assert got == {"status": 200, "body": b"page", "headers": {"Content-Type": "text/plain"}}
    assert dns.call_count == 1
    sock.__enter__.return_value.connect.assert_called_with(("8.8.8.8", 443))
    origin.tls.wrap_socket.assert_called_with(sock.__enter__.return_value,
                                               server_hostname="example.test")
    conn.request.assert_called_with("GET", "/page?id=1", headers={})
    for url in ("http://example.test", "https://example.test:444", "https://other.test",
                "https://example.test@127.0.0.1"):
        with pytest.raises(ValueError):
            origin.fetch(url, "GET", {})
    res.status = 302
    with pytest.raises(ValueError, match="redirect"):
        origin.fetch("https://example.test/go", "GET", {})
    assert dns.call_count == 1
