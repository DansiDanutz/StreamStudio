"""Runtime configuration, read from STREAMSTUDIO_* environment variables or a .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STREAMSTUDIO_", env_file=".env", extra="ignore")

    # Where projects, proxies, caches and renders live.
    data_dir: Path = Field(default_factory=lambda: Path.home() / "StreamStudioData")

    # The repo's assets/ folder (served at the web root): generated avatar clips land here.
    assets_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[4] / "assets")

    # Folders the importer may read source footage from (colon-separated in env).
    # The data_dir is always allowed.
    import_roots: list[Path] = Field(default_factory=lambda: [Path.home() / "Movies"])

    host: str = "127.0.0.1"
    port: int = 8787

    # Accept requests from Tailscale peers (100.64.0.0/10, fd7a:115c:a1e0::/48).
    # When true, run with host=0.0.0.0; the network guard still rejects everything
    # that is not loopback or tailnet.
    allow_tailnet: bool = True

    # Extra host names the API answers to, on top of localhost, IP literals, *.ts.net and this
    # Mac's name (env: a JSON list). Anything else is rejected (DNS-rebinding guard).
    extra_hosts: list[str] = []

    # Worker
    worker_concurrency: int = 2
    job_heartbeat_timeout_s: int = 120
    job_max_attempts: int = 3

    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "streamstudio.db"

    @property
    def projects_dir(self) -> Path:
        return self.data_dir / "projects"

    @property
    def recordings_dir(self) -> Path:
        return self.data_dir / "recordings"

    def allowed_import_roots(self) -> list[Path]:
        return [self.data_dir, *self.import_roots]

    def ensure_dirs(self) -> None:
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
