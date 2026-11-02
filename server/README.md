# server

## Overview

The Python 3.12 backend of StreamStudio: a FastAPI API, a SQLite-backed job
worker, and the offline media tools, packaged as `streamstudio` from
`src/streamstudio`. `pyproject.toml` declares the runtime dependencies
(fastapi, uvicorn, pydantic, pydantic-settings), the optional `media` extras
(pillow, numpy, scipy, rembg) for the cut-out, dissolve and opener tools, the
`dev` group (pytest, httpx, ruff, pillow), and four console scripts:
`streamstudio-api` (`streamstudio.api.main:run`), `streamstudio-worker`
(`streamstudio.worker.main:run`), `streamstudio-schema`
(`streamstudio.edl.export:main`) and `streamstudio-mcp` (`streamstudio.mcp:main`).
Tests live in `tests/` (pytest, `testpaths = ["tests"]`); ruff runs with
line length 100 and rules `E, F, I, UP, B, SIM`.

Verification for this subtree: `cd server && .venv/bin/python -m pytest`
(repo-wide `make test`); lint with `cd server && .venv/bin/ruff check src tests`.

## Subdirectories & Boundaries

- src: [./src/README.md](./src/README.md) — the `streamstudio` package source
- tests: test suite (pytest), no contract file
