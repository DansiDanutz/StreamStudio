"""FastAPI app. In production it also serves the built web UI from web/dist."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..core import db, vault
from ..core.config import Settings, get_settings
from ..core.netguard import NetGuardMiddleware
from .routes import agent, heygen, jobs, live, projects, recordings, scenes, system
from .routes import vault as vault_routes

REPO = Path(__file__).resolve().parents[4]
WEB_DIST = REPO / "web" / "dist"
REPO_ASSETS = (
    REPO / "assets"
)  # studio plates, avatar clips: served at the web root like Vite's publicDir


def create_app(settings: Settings | None = None) -> FastAPI:
    s = settings or get_settings()
    s.ensure_dirs()
    c = db.connect(s.db_path)
    db.migrate(c)
    c.close()

    app = FastAPI(title="StreamStudio", version=__version__)
    app.state.settings = s
    app.add_middleware(NetGuardMiddleware, allow_tailnet=s.allow_tailnet, extra_hosts=s.extra_hosts)
    app.include_router(system.router)
    app.include_router(projects.router)
    app.include_router(jobs.router)
    app.include_router(scenes.router)
    app.include_router(recordings.router)
    app.include_router(live.router)
    app.include_router(heygen.router)
    app.include_router(agent.router)
    app.include_router(vault_routes.router)

    if WEB_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="web-assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            if path == "api" or path.startswith("api/"):
                # unknown API paths never fall back to the app
                raise HTTPException(404, "not found")
            for root in (WEB_DIST, REPO_ASSETS):
                f = (root / path).resolve()
                if path and f.is_file() and root in f.parents:
                    return FileResponse(f)
            if path.startswith("avatar/") and s.assets_dir == REPO_ASSETS:
                # a clip kept only in the vault: bring it back, then serve it
                try:
                    got = vault.fetch(s, None, f"assets/{path}")
                except vault.VaultError:
                    got = None
                if got is not None:
                    return FileResponse(got)
            return FileResponse(WEB_DIST / "index.html")

    return app


def run() -> None:
    import uvicorn

    s = get_settings()
    host = "0.0.0.0" if s.allow_tailnet and s.host == "127.0.0.1" else s.host
    uvicorn.run(create_app(s), host=host, port=s.port, log_level="info")


if __name__ == "__main__":
    run()
