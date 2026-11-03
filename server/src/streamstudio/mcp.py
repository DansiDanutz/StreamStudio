"""StreamStudio as an MCP server (stdio, JSON-RPC 2.0, no extra dependencies).

Lets any agent (Claude Code, Paperclip agents, Hermes…) read the artifact library and drive the
stage through the running StreamStudio API:

    claude mcp add streamstudio -- python -m streamstudio.mcp
    (STREAMSTUDIO_URL defaults to http://127.0.0.1:8787)

Tools: library_list, library_get, library_name, studio_state, studio_guide, studio_timeline,
studio_do, heygen_estimate, vault_status, vault_backup, vault_fetch. Nothing here spends
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

from .episode.contract import EPISODE_ID, Script

BASE = os.environ.get("STREAMSTUDIO_URL", "http://127.0.0.1:8787").rstrip("/")
PROTOCOL = "2025-06-18"

SCRIPT_SCHEMA = Script.model_json_schema()
SCRIPT_DEFINITIONS = SCRIPT_SCHEMA.pop("$defs", {})

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
                "group": {
                    "type": "string",
                    "description": "Library tab: Scenes, Avatar, Media, Recordings, Workflows, "
                    "Layouts.",
                },
                "kind": {
                    "type": "string",
                    "description": "Only this kind, e.g. 'gesture', 'scene'.",
                },
                "tag": {"type": "string", "description": "Only artifacts with this tag."},
                "query": {"type": "string", "description": "Words that must all appear."},
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
        "name": "library_name",
        "description": "Give an artifact its own name and/or tags (empty title = default name).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "title": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["id"],
        },
    },
    {
        "name": "vault_status",
        "description": "Where the off-machine copies live, and how many artifacts are not "
        "backed up yet. Each artifact's 'storage' says {local, vault}.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "vault_backup",
        "description": "Copy new or changed clips, takes and the catalog to the vault (a job).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "vault_fetch",
        "description": "Bring a vault-only clip or take back to this machine before using it. "
        "Pass the artifact's storage.key.",
        "inputSchema": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
        },
    },
    {
        "name": "studio_state",
        "description": "What is on stage now: scene, cue, segment, gesture, table, program.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "studio_guide",
        "description": "Read first: how a StreamStudio video is built (segments, cues, gestures, "
        "the lip-sync rule) and the typical moves.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "studio_timeline",
        "description": "The current video as a timeline: each segment's start/end, the layout that "
        "really plays, voice, gesture, table, Main card, and warnings to fix.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "studio_do",
        "description": (
            "Run a stage action in the open editor. Use the 'actions' listed by library_list "
            "(e.g. timeline.get, publish.kit, segment.update, segment.add, segment.preview, "
            "scene.activate, cue.apply, point.at, table.event, media.add, workflow.insert, "
            "script.play). Needs the editor open."
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
    {
        "name": "recording_transcribe",
        "description": (
            "Transcribe a recorded take locally with whisper.cpp (free, offline). Queues a job and "
            "returns its id; poll the job, then read recording_transcript."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "recording id (rec_...)"}},
            "required": ["id"],
        },
    },
    {
        "name": "recording_transcript",
        "description": "A take's transcript: language, full text, segments and word timings (ms).",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "recording id (rec_...)"}},
            "required": ["id"],
        },
    },
    {
        "name": "youtube_status",
        "description": "Which YouTube channels are connected (id and title).",
        "inputSchema": {"type": "object", "properties": {}},
    },

    {
        "name": "episode_create",
        "description": "Create a draft script. Dan reviews and approves it on the Episode page.",
        "inputSchema": {"type": "object", "$defs": SCRIPT_DEFINITIONS,
                        "properties": {"script": SCRIPT_SCHEMA},
                        "required": ["script"]},
    },
    {
        "name": "episode_edit",
        "description": "Revise a pre-upload episode. Use the script hash from episode_status.",
        "inputSchema": {"type": "object", "$defs": SCRIPT_DEFINITIONS,
                        "properties": {"script": SCRIPT_SCHEMA, "expected_hash": {"type": "string"},
                                       "id": {"type": "string", "pattern": EPISODE_ID.pattern}},
                        "required": ["id", "script", "expected_hash"]},
    },
    {
        "name": "episode_list",
        "description": "List episodes and their production status.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "episode_workflows",
        "description": "Discover supported episode workflows, selection rules and parameters.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    *[
        {
            "name": name, "description": description,
            "inputSchema": {"type": "object", "properties": {
                "id": {"type": "string", "pattern": EPISODE_ID.pattern}}, "required": ["id"]},
        }
        for name, description in (
            ("episode_status", "Read a saved episode, scene progress, warnings and next action."),
            ("episode_estimate", "Read projected costs without starting or approving a render."),
            ("episode_refresh", "Check an uploaded video's status once per five minutes."),
        )
    ],
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


def _seg(value: str) -> str:
    """One URL path segment: slashes and dots cannot climb out of it."""
    return urllib.parse.quote(value, safe="")


def call(name: str, args: dict[str, Any]) -> Any:
    if name == "library_list":
        q = {
            k: v
            for k, v in {
                "group": args.get("group"), "kind": args.get("kind"),
                "tag": args.get("tag"), "q": args.get("query"),
            }.items()
            if v
        }  # fmt: skip
        return _http("GET", "/api/library" + (f"?{urllib.parse.urlencode(q)}" if q else ""))
    if name == "library_get":
        return _http("GET", f"/api/library/{urllib.parse.quote(args['id'], safe=':')}")
    if name == "library_name":
        body = {k: args[k] for k in ("title", "tags") if k in args}
        return _http("PATCH", f"/api/library/{urllib.parse.quote(args['id'], safe=':')}", body)
    if name == "vault_status":
        return _http("GET", "/api/vault")
    if name == "vault_backup":
        return _http("POST", "/api/vault/push")
    if name == "vault_fetch":
        return _http("POST", "/api/vault/fetch", {"key": args["key"]})
    if name == "studio_state":
        return _http("GET", "/api/agent/state")
    if name == "studio_guide":
        return _http("GET", "/api/agent/guide")["guide"]
    if name == "studio_timeline":
        return _http("GET", "/api/agent/timeline")
    if name == "studio_do":
        return _http(
            "POST", "/api/agent/do", {"action": args["action"], "args": args.get("args") or {}}
        )
    if name == "heygen_estimate":
        return _http("POST", "/api/heygen/render", {"items": args["items"], "confirm": False})
    if name == "recording_transcribe":
        return _http("POST", f"/api/recordings/{_seg(args['id'])}/transcribe")
    if name == "recording_transcript":
        return _http("GET", f"/api/recordings/{_seg(args['id'])}/transcript")
    if name == "youtube_status":
        return _http("GET", "/api/youtube")
    if name == "episode_create":
        return _http("POST", "/api/episodes", args["script"])
    if name == "episode_edit":
        if not EPISODE_ID.fullmatch(args["id"]):
            raise ValueError("invalid episode id")
        query = urllib.parse.urlencode({"expected_hash": args["expected_hash"]})
        return _http("PUT", f"/api/episodes/{args['id']}/script?{query}", args["script"])
    if name == "episode_list":
        return _http("GET", "/api/episodes")
    if name == "episode_workflows":
        return _http("GET", "/api/episodes/workflows")
    if name in ("episode_status", "episode_estimate", "episode_refresh"):
        eid = args["id"]
        if not EPISODE_ID.fullmatch(eid):
            raise ValueError("invalid episode id")
        path = f"/api/episodes/{eid}"
        if name == "episode_estimate":
            return _http("GET", path + "/cost")
        if name == "episode_refresh":
            return _http("POST", path + "/refresh")
        return _http("GET", path)
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
            text = out if isinstance(out, str) else json.dumps(out, indent=1)
            result = {"content": [{"type": "text", "text": text}]}
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
