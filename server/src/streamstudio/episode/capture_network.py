"""Capture HTTPS resources through a socket pinned to a validated public DNS answer."""
from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit

LIMIT = 16 * 1024 * 1024


def addresses(host: str) -> list:
    answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not answers:
        raise ValueError("capture host has no addresses")
    for _, _, _, _, addr in answers:
        ip = ipaddress.ip_address(addr[0])
        if isinstance(ip, ipaddress.IPv6Address):
            if ip.ipv4_mapped:
                ip = ip.ipv4_mapped
            elif ip.sixtofour or ip.teredo or ip in ipaddress.ip_network("64:ff9b::/96"):
                raise ValueError("capture does not accept IPv6 transition addresses")
        if not ip.is_global or ip.is_multicast or ip.is_reserved:
            raise ValueError("capture host resolves to a non-public address")
    return answers


class CaptureOrigin:
    def __init__(self, host: str):
        self.host = host
        self.answers = addresses(host)
        self.tls = ssl.create_default_context()
        self.remaining = 64 * 1024 * 1024

    def fetch(self, url: str, method: str, headers: dict) -> dict:
        u = urlsplit(url)
        if (method not in ("GET", "HEAD") or u.scheme != "https" or u.hostname != self.host
                or u.username is not None or u.password is not None or u.port not in (None, 443)):
            raise ValueError("capture request outside the selected HTTPS origin")
        path = (u.path or "/") + ("?" + u.query if u.query else "")
        for i, (family, kind, proto, _, addr) in enumerate(self.answers):
            with socket.socket(family, kind, proto) as sock:
                sock.settimeout(12)
                try:
                    sock.connect(addr)
                except OSError:
                    if i + 1 == len(self.answers):
                        raise
                    continue
                # Dial only the numeric address above. SNI, Host and certificate validation
                # still use the original hostname. HTTPConnection must never resolve it again.
                with self.tls.wrap_socket(sock, server_hostname=self.host) as secure:
                    conn = http.client.HTTPConnection(self.host, 443)
                    conn.sock = secure
                    try:
                        safe = {k: v for k, v in headers.items()
                                if k.lower() in ("accept", "accept-language", "user-agent")}
                        conn.request(method, path, headers=safe)
                        res = conn.getresponse()
                        if 300 <= res.status < 400:
                            raise ValueError("capture redirects are disabled")
                        cap = min(LIMIT, self.remaining)
                        body = res.read(cap+1)
                        if len(body) > cap:
                            raise ValueError("capture response exceeds size limit")
                        self.remaining -= len(body)
                        response_headers = {k: v for k, v in res.getheaders() if k.lower() in
                                            ("content-type", "content-encoding", "content-language",
                                             "content-security-policy", "x-content-type-options")}
                        return {"status": res.status, "headers": response_headers, "body": body}
                    finally:
                        conn.close()
        raise OSError("capture connection failed")
