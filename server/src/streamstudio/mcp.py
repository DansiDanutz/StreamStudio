"""StreamStudio as an MCP server (stdio, JSON-RPC 2.0, no extra dependencies).

Lets any agent (Claude Code, Paperclip agents, Hermes…) read the artifact library and drive the
stage through the running StreamStudio API:

    claude mcp add streamstudio -- python -m streamstudio.mcp
    (STREAMSTUDIO_URL defaults to http://127.0.0.1:8787)

Tools: library_list, library_get, studio_state, studio_do, heygen_estimate. Nothing here spends
money or starts a capture: HeyGen renders and record / go live stay a human click in the editor.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BASE = os.environ.get("STREAMSTUDIO_URL", "http://127.0.0.1:8787").rstrip("/")
PROTOCOL = "2025-06-18"

TOOLS: list[dict[str, Any]] = [
    {
        "name": "library_list",
        "description": (
            "List StreamStudio artifacts: scenes, gestures, table objects, media, workflows, "
            "hotspots, cues, rendered clips, recordings. Each has an id and the actions that "
            "use it."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "description": "Only this kind, e.g. 'gesture', 'scene'.",
                },
                "query": {"type": "string", "description": "Free-text filter."},
            },
        },
    },
    {
        "name": "library_get",
        "description": "One artifact by id (e.g. 'gesture:point-up-right', 'scene:studio-solo').",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    },
    {
        "name": "studio_state",
        "description": "What is on stage now: scene, cue, segment, gesture, table, program.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "studio_do",
        "description": (
            "Run a stage action in the open editor. Use the 'actions' listed by library_list "
            "(e.g. scene.activate, cue.apply, point.at, gesture.play, table.event, media.add, "
            "main.source, workflow.insert, script.play, script.stop). Needs the editor open."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"action": {"type": "string"}, "args": {"type": "object"}},
            "required": ["action"],
        },
    },
    {
        "name": "heygen_estimate",
        "description": (
            "Estimate a HeyGen render (seconds, clips) WITHOUT rendering. Rendering costs money "
            "and is only started by Dan in the editor (Script → HeyGen)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"items": {"type": "array", "items": {"type": "object"}}},
            "required": ["items"],
        },
    },
]


def _http(method: str, path: str, body: Any = None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    req.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 (local API)
            raw = r.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        with contextlib.suppress(json.JSONDecodeError):
            detail = json.loads(detail).get("detail", detail)
        raise RuntimeError(f"StreamStudio {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"StreamStudio is not running at {BASE} ({e.reason})") from e
    return json.loads(raw) if raw else None


def call(name: str, args: dict[str, Any]) -> Any:
    if name == "library_list":
        q = {k: v for k, v in {"kind": args.get("kind"), "q": args.get("query")}.items() if v}
        return _http("GET", "/api/library" + (f"?{urllib.parse.urlencode(q)}" if q else ""))
    if name == "library_get":
        return _http("GET", f"/api/library/{urllib.parse.quote(args['id'], safe=':')}")
    if name == "studio_state":
        return _http("GET", "/api/agent/state")
    if name == "studio_do":
        return _http(
            "POST", "/api/agent/do", {"action": args["action"], "args": args.get("args") or {}}
        )
    if name == "heygen_estimate":
        return _http("POST", "/api/heygen/render", {"items": args["items"], "confirm": False})
    raise ValueError(f"unknown tool {name}")


def handle(msg: dict[str, Any]) -> dict[str, Any] | None:
    mid, method = msg.get("id"), msg.get("method")
    if mid is None:  # notification
        return None
    if method == "initialize":
        result: Any = {
            "protocolVersion": PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "streamstudio", "version": "0.1.0"},
        }
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        p = msg.get("params") or {}
        try:
            out = call(p.get("name", ""), p.get("arguments") or {})
            result = {"content": [{"type": "text", "text": json.dumps(out, indent=1)}]}
        except Exception as e:  # tool errors go back to the agent, not as protocol errors
            result = {"content": [{"type": "text", "text": str(e)}], "isError": True}
    elif method == "ping":
        result = {}
    else:
        return {
            "jsonrpc": "2.0",
            "id": mid,
            "error": {"code": -32601, "message": f"no method {method}"},
        }
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        reply = handle(msg)
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
