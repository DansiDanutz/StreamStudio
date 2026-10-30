"""Only loopback and Tailscale peers may talk to the API."""

from __future__ import annotations

import ipaddress

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

LOOPBACK = [ipaddress.ip_network("127.0.0.0/8"), ipaddress.ip_network("::1/128")]
TAILNET = [ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("fd7a:115c:a1e0::/48")]


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


class NetGuardMiddleware:
    def __init__(self, app: ASGIApp, allow_tailnet: bool = True) -> None:
        self.app = app
        self.allow_tailnet = allow_tailnet

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            client = scope.get("client")
            host = client[0] if client else None
            if not is_allowed(host, self.allow_tailnet):
                if scope["type"] == "http":
                    await JSONResponse({"detail": "forbidden: not loopback or tailnet"}, 403)(
                        scope, receive, send
                    )
                else:
                    await send({"type": "websocket.close", "code": 1008})
                return
        await self.app(scope, receive, send)
