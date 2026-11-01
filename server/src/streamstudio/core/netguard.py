"""Only loopback and Tailscale peers may talk to the API, only under our own host names,
and a web page on another site may not change anything.

- Peer address: loopback, or tailnet when allowed.
- Host header: localhost, an IP literal, a Tailscale MagicDNS name (*.ts.net or a dotless short
  name), this Mac's name, or a configured extra. This defeats DNS rebinding, where an attacker's
  domain is re-pointed at 127.0.0.1 but the browser still sends the attacker's Host.
- Origin header on writes and WebSockets: when a browser sends one, it must name one of the same
  hosts. Agents, MCP and curl send no Origin and are not affected.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

LOOPBACK = [ipaddress.ip_network("127.0.0.0/8"), ipaddress.ip_network("::1/128")]
TAILNET = [ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("fd7a:115c:a1e0::/48")]
LOCAL_NAMES = {"localhost", "testserver", "testclient"}  # the last two: Starlette's TestClient
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def is_allowed(host: str | None, allow_tailnet: bool) -> bool:
    if host in (None, "testclient"):  # Starlette TestClient
        return host == "testclient"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    nets = LOOPBACK + (TAILNET if allow_tailnet else [])
    return any(ip in n for n in nets)


def _machine_names() -> set[str]:
    name = socket.gethostname().lower()
    short = name.split(".")[0]
    return {name, short, f"{short}.local"}


def _hostname(host_header: str) -> str:
    """'localhost:5173' → 'localhost', '[::1]:8787' → '::1'."""
    return (urlsplit(f"//{host_header}").hostname or "").lower()


def host_allowed(host_header: str | None, extra: list[str] | tuple[str, ...] = ()) -> bool:
    if not host_header:
        return False
    name = _hostname(host_header)
    if not name:
        return False
    try:
        ipaddress.ip_address(name)
        return True  # an IP literal cannot be a rebound attacker domain
    except ValueError:
        pass
    allowed = LOCAL_NAMES | _machine_names() | {e.lower() for e in extra}
    if name in allowed or name.endswith((".localhost", ".ts.net")):
        return True
    # A dotless name (Tailscale short name, e.g. 'mac-studio') can't be an attacker's domain.
    return "." not in name


def origin_allowed(origin: str | None, extra: list[str] | tuple[str, ...] = ()) -> bool:
    if origin is None:
        return True  # not a browser request
    netloc = urlsplit(origin).netloc
    return bool(netloc) and host_allowed(netloc, extra)


class NetGuardMiddleware:
    def __init__(
        self, app: ASGIApp, allow_tailnet: bool = True, extra_hosts: list[str] | None = None
    ) -> None:
        self.app = app
        self.allow_tailnet = allow_tailnet
        self.extra_hosts = tuple(extra_hosts or ())

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            reason = self._reject_reason(scope)
            if reason:
                if scope["type"] == "http":
                    denied = JSONResponse({"detail": f"forbidden: {reason}"}, 403)
                    await denied(scope, receive, send)
                else:
                    await send({"type": "websocket.close", "code": 1008})
                return
        await self.app(scope, receive, send)

    def _reject_reason(self, scope: Scope) -> str | None:
        client = scope.get("client")
        if not is_allowed(client[0] if client else None, self.allow_tailnet):
            return "not loopback or tailnet"
        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope.get("headers", [])}
        if not host_allowed(headers.get("host"), self.extra_hosts):
            return "unknown host name"
        writes = scope["type"] == "websocket" or scope.get("method", "GET") not in SAFE_METHODS
        if writes and not origin_allowed(headers.get("origin"), self.extra_hosts):
            return "cross-site request"
        return None
