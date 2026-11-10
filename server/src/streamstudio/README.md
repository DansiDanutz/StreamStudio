# streamstudio

## Overview

The `streamstudio` Python package: the API (`api/`), the job worker
(`worker/`), the shared core (`core/`), the EDL model (`edl/`), and the
offline media tools (`avatar/`, `objects/`, `render/`). Two files live at the
package root: `__init__.py` (the version string) and `mcp.py`, an MCP server
over stdio that exposes the running API to agents. Console scripts are declared
in `server/pyproject.toml`: `streamstudio-api`, `streamstudio-worker`,
`streamstudio-schema`, `streamstudio-mcp`.

## Interface

- `__init__.__version__ = "0.1.0"`
- `mcp.BASE` (from `STREAMSTUDIO_URL`, default `http://127.0.0.1:8787`), `mcp.PROTOCOL = "2025-06-18"`
- `mcp.TOOLS` — tool list served to agents: `library_list`, `library_get`, `library_name`, `vault_status`, `vault_backup`, `vault_fetch`, `studio_state`, `studio_guide`, `studio_timeline`, `studio_do`, `heygen_estimate`, `recording_transcribe`, `recording_transcript`, `youtube_status`
- `mcp.call(name, args)` — maps a tool to one HTTP call on the API; `mcp.handle(msg)` — JSON-RPC dispatch (`initialize`, `tools/list`, `tools/call`, `ping`); `mcp.main()` — stdio loop
- `mcp._http(method, path, body=None)`, `mcp._seg(value)`
- Subdirectories:
  - [api](./api/README.md) — FastAPI app and routers
  - [avatar](./avatar/README.md) — cut-out and object matte tools
  - [core](./core/README.md) — settings, SQLite, safety guards, integrations
  - [edl](./edl/README.md) — Edit Decision List model and operations
  - [episode](./episode/README.md) — the episode factory (Stage 0: constants, preflight, the HyperFrames workspace templates)
  - [objects](./objects/README.md) — particle dissolve render
  - [render](./render/README.md) — lip-sync guard, opener and preview renders
  - [worker](./worker/README.md) — job worker and handlers

## Invariants

- `[mcp.py:call]` There is no upload tool, and `heygen_estimate` always sends `confirm: False`, so no MCP tool starts a paid render or uploads a video.
- `[mcp.py:call]` Recording ids are URL-quoted with `safe=""` (`_seg`), and library ids with `safe=":"`, so an id cannot change the request path.
- `[mcp.py:handle]` Messages without an `id` (notifications) get no reply; unknown methods return JSON-RPC error `-32601`; tool failures are returned as a result with `isError: true`, not as protocol errors.
- `[mcp.py:_http]` Non-2xx API responses become `RuntimeError("StreamStudio <code>: <detail>")`; a connection failure names `BASE`.

## Side Effects

- `[mcp.py:_http]` makes HTTP requests to `BASE` (30 s timeout). `[mcp.py:main]` reads JSON lines from stdin and writes replies to stdout.

## Verification

- Run: `cd server && .venv/bin/python -m pytest`
- Lint: `cd server && .venv/bin/ruff check src tests`
