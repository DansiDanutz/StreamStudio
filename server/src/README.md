# src

## Overview

The source layout for the `streamstudio` distribution. This directory holds
only the package itself; `server/pyproject.toml` builds the wheel from
`src/streamstudio` (hatchling, `packages = ["src/streamstudio"]`).

## Subdirectories & Boundaries

- streamstudio: [./streamstudio/README.md](./streamstudio/README.md) — the API, worker, core, EDL, media tools and MCP server
