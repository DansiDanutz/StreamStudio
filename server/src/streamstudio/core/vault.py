"""The vault: a copy of every StreamStudio artifact kept outside the Mac Studio.

Two kinds of storage:
  * ``s3``     any S3-compatible bucket: Supabase Storage (its S3 endpoint), Cloudflare R2,
               Backblaze B2, AWS S3. Requests are signed here (SigV4), no SDK needed.
  * ``folder`` a folder another service syncs off the machine: iCloud Drive, Google Drive
               for desktop, Dropbox, a NAS share.

What goes in: rendered avatar clips and gesture clips (assets/avatar/**), finished takes
(recordings/rec_*.mp4) and ``catalog/catalog.json`` (scenes, artifact names and tags).
Every object carries its sha256, so a push only uploads what changed and a pull is checked.
Files come back on demand: a clip or take that is missing locally is fetched from the vault the
first time something asks for it (see ``fetch``), so local copies can be removed to save space.

Credentials live in <data_dir>/vault.json (0600) and are only ever shown masked.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
import shutil
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, BinaryIO, Protocol

from .config import Settings

TIMEOUT_S = 120
#: Local areas that are mirrored, as (vault key prefix, folder, file patterns).
CLIP_GLOBS = ("*.mp4", "*.webm", "*.json")
REC_GLOBS = ("rec_*.mp4",)


class VaultError(RuntimeError):
    pass


# ------------------------------------------------------------------ config


def config_path(data_dir: Path) -> Path:
    return data_dir / "vault.json"


def load_config(data_dir: Path) -> dict[str, str]:
    p = config_path(data_dir)
    return json.loads(p.read_text()) if p.exists() else {}


def save_config(data_dir: Path, cfg: dict[str, str]) -> None:
    p = config_path(data_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(cfg, f)
    tmp.replace(p)


def mask(v: str) -> str:
    return f"••••{v[-4:]}" if v else ""


def public_config(cfg: dict[str, str]) -> dict[str, Any]:
    """The config without secrets, for the UI and agents."""
    out = {k: v for k, v in cfg.items() if k not in ("secret_key", "access_key")}
    if cfg.get("kind") == "s3":
        out["access_key"] = mask(cfg.get("access_key", ""))
        out["secret_key"] = mask(cfg.get("secret_key", ""))
    return out


# ------------------------------------------------------------------ backends


class Backend(Protocol):
    label: str

    def put(self, key: str, src: Path, sha256: str) -> None: ...
    def get(self, key: str, dst: BinaryIO) -> None: ...
    def head(self, key: str) -> dict[str, Any] | None: ...
    def list(self, prefix: str) -> list[dict[str, Any]]: ...


class FolderBackend:
    """A synced folder (iCloud Drive, Google Drive for desktop, Dropbox, NAS)."""

    def __init__(self, path: str) -> None:
        self.root = Path(path).expanduser()
        self.label = f"folder {self.root}"

    def _p(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents:
            raise VaultError("bad key")
        return p

    def put(self, key: str, src: Path, sha256: str) -> None:
        dst = self._p(key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + ".part")
        shutil.copyfile(src, tmp)
        tmp.replace(dst)
        dst.with_name(dst.name + ".sha256").write_text(sha256)

    def get(self, key: str, dst: BinaryIO) -> None:
        with self._p(key).open("rb") as f:
            shutil.copyfileobj(f, dst, 1024 * 1024)

    def head(self, key: str) -> dict[str, Any] | None:
        p = self._p(key)
        if not p.is_file():
            return None
        sha = p.with_name(p.name + ".sha256")
        return {
            "bytes": p.stat().st_size,
            "sha256": sha.read_text().strip() if sha.exists() else None,
        }

    def list(self, prefix: str) -> list[dict[str, Any]]:
        base = self.root / prefix
        if not base.exists():
            return []
        out = []
        for p in sorted(base.rglob("*")):
            if p.is_file() and not p.name.endswith((".sha256", ".part")):
                out.append({"key": p.relative_to(self.root).as_posix(), "bytes": p.stat().st_size})
        return out


Transport = Callable[[urllib.request.Request], tuple[int, dict[str, str], bytes]]


def _urlopen(req: urllib.request.Request) -> tuple[int, dict[str, str], bytes]:
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:  # noqa: S310 (configured endpoint)
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


def sigv4_headers(
    method: str, url: str, region: str, access_key: str, secret_key: str,
    payload_hash: str, now: dt.datetime, extra: dict[str, str] | None = None, service: str = "s3",
) -> dict[str, str]:  # fmt: skip
    """AWS Signature Version 4 headers for one request (checked against AWS's own example)."""
    u = urllib.parse.urlsplit(url)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    day = amz_date[:8]
    headers = {"host": u.netloc, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date}
    headers.update({k.lower(): v.strip() for k, v in (extra or {}).items()})
    names = sorted(headers)
    query = "&".join(
        f"{urllib.parse.quote(k, safe='-_.~')}={urllib.parse.quote(v, safe='-_.~')}"
        for k, v in sorted(urllib.parse.parse_qsl(u.query, keep_blank_values=True))
    )
    canonical = "\n".join([
        method, urllib.parse.quote(u.path or "/", safe="/-_.~%"), query,
        "".join(f"{n}:{headers[n]}\n" for n in names), ";".join(names), payload_hash,
    ])  # fmt: skip
    scope = f"{day}/{region}/{service}/aws4_request"
    to_sign = "\n".join(
        ["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()]
    )
    k = ("AWS4" + secret_key).encode()
    for part in (day, region, service, "aws4_request"):
        k = hmac.new(k, part.encode(), hashlib.sha256).digest()
    sig = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    headers["authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
        f"SignedHeaders={';'.join(names)}, Signature={sig}"
    )
    return headers


class S3Backend:
    """Any S3-compatible bucket, path-style requests (works for Supabase, R2, B2 and AWS)."""

    def __init__(self, cfg: dict[str, str], transport: Transport | None = None) -> None:
        for k in ("endpoint", "bucket", "access_key", "secret_key"):
            if not cfg.get(k):
                raise VaultError(f"vault: {k} is missing")
        self.endpoint = cfg["endpoint"].rstrip("/")
        if not self.endpoint.startswith("https://"):
            raise VaultError("vault: the endpoint must be https://")
        self.bucket = cfg["bucket"]
        self.region = cfg.get("region") or "auto"
        self.ak, self.sk = cfg["access_key"], cfg["secret_key"]
        self.send = transport or _urlopen
        self.label = f"s3 {urllib.parse.urlsplit(self.endpoint).netloc}/{self.bucket}"

    def _url(self, key: str = "", query: str = "") -> str:
        path = f"/{self.bucket}" + (f"/{urllib.parse.quote(key, safe='/-_.~')}" if key else "")
        return f"{self.endpoint}{path}" + (f"?{query}" if query else "")

    def _req(
        self, method: str, url: str, body: Any = None, payload_hash: str = "UNSIGNED-PAYLOAD",
        extra: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:  # fmt: skip
        h = sigv4_headers(
            method, url, self.region, self.ak, self.sk, payload_hash, dt.datetime.now(dt.UTC), extra
        )
        h.pop("host")
        req = urllib.request.Request(url, data=body, method=method, headers=h)
        return self.send(req)

    def put(self, key: str, src: Path, sha256: str) -> None:
        size = src.stat().st_size
        with src.open("rb") as f:
            st, _, body = self._req(
                "PUT", self._url(key), f, sha256,
                {"content-length": str(size), "x-amz-meta-sha256": sha256},
            )  # fmt: skip
        if st not in (200, 201):
            raise VaultError(f"upload {key}: HTTP {st} {body[:200]!r}")

    def get(self, key: str, dst: BinaryIO) -> None:
        st, _, body = self._req("GET", self._url(key))
        if st != 200:
            raise VaultError(f"download {key}: HTTP {st}")
        dst.write(body)

    def head(self, key: str) -> dict[str, Any] | None:
        st, h, _ = self._req("HEAD", self._url(key))
        if st == 404:
            return None
        if st != 200:
            raise VaultError(f"check {key}: HTTP {st}")
        return {"bytes": int(h.get("content-length", 0)), "sha256": h.get("x-amz-meta-sha256")}

    def list(self, prefix: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        token = ""
        while True:
            q = {"list-type": "2", "prefix": prefix}
            if token:
                q["continuation-token"] = token
            st, _, body = self._req("GET", self._url(query=urllib.parse.urlencode(q)))
            if st != 200:
                raise VaultError(f"list: HTTP {st} {body[:200]!r}")
            root = ET.fromstring(body)  # noqa: S314 (our own bucket's listing)
            ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
            for c in root.iter(f"{ns}Contents"):
                out.append({
                    "key": c.findtext(f"{ns}Key"), "bytes": int(c.findtext(f"{ns}Size") or 0),
                })  # fmt: skip
            token = root.findtext(f"{ns}NextContinuationToken") or ""
            if root.findtext(f"{ns}IsTruncated") != "true" or not token:
                return out


#: Tests replace this to talk to a fake bucket.
S3_TRANSPORT: Transport | None = None


def backend(cfg: dict[str, str]) -> Backend | None:
    kind = cfg.get("kind")
    if kind == "s3":
        return S3Backend(cfg, S3_TRANSPORT)
    if kind == "folder" and cfg.get("path"):
        return FolderBackend(cfg["path"])
    return None


def prefixed(cfg: dict[str, str], key: str) -> str:
    p = (cfg.get("prefix") or "streamstudio").strip("/")
    return f"{p}/{key}" if p else key


# ------------------------------------------------------------------ what is mirrored


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def local_files(s: Settings) -> Iterator[tuple[str, Path]]:
    """(vault key, local path) for every file the vault keeps."""
    av = s.assets_dir / "avatar"
    for sub in ("clips", "gestures"):
        d = av / sub
        for pat in CLIP_GLOBS:
            for f in sorted(d.glob(pat)) if d.exists() else []:
                yield f"assets/avatar/{sub}/{f.name}", f
    for pat in REC_GLOBS:
        d = s.recordings_dir
        for f in sorted(d.glob(pat)) if d.exists() else []:
            yield f"recordings/{f.name}", f


def local_path(s: Settings, key: str) -> Path | None:
    """Where a vault key lives on this machine (None for keys that are not files we mirror)."""
    parts = key.split("/")
    if len(parts) == 4 and parts[:2] == ["assets", "avatar"] and parts[2] in ("clips", "gestures"):
        base = s.assets_dir / "avatar" / parts[2]
    elif len(parts) == 2 and parts[0] == "recordings" and parts[1].startswith("rec_"):
        base = s.recordings_dir
    else:
        return None
    name = parts[-1]
    if "/" in name or name.startswith(".") or not name.endswith((".mp4", ".webm", ".json")):
        return None
    return base / name


def catalog(c: sqlite3.Connection) -> dict[str, Any]:
    """Scenes plus every artifact's name and tags: what a fresh machine needs to restore."""
    scenes = [dict(r) for r in c.execute("SELECT * FROM scenes ORDER BY collection, position")]
    meta = [dict(r) for r in c.execute("SELECT * FROM artifact_meta ORDER BY id")]
    return {"version": 1, "scenes": scenes, "meta": meta}


# ------------------------------------------------------------------ index (what is where)


def index(c: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    return {r["key"]: dict(r) for r in c.execute("SELECT * FROM vault_objects")}


def record(c: sqlite3.Connection, key: str, size: int, sha: str | None) -> None:
    c.execute(
        "INSERT INTO vault_objects (key, bytes, sha256, pushed_at) VALUES (?,?,?,?)"
        " ON CONFLICT(key) DO UPDATE SET bytes=excluded.bytes, sha256=excluded.sha256,"
        " pushed_at=excluded.pushed_at",
        (key, size, sha, dt.datetime.now(dt.UTC).isoformat(timespec="seconds")),
    )


def push(
    s: Settings, c: sqlite3.Connection, progress: Callable[[float, str], None] | None = None
) -> dict[str, Any]:
    """Upload what the vault does not have yet. Idempotent: unchanged files are skipped."""
    cfg = load_config(s.data_dir)
    be = backend(cfg)
    if be is None:
        raise VaultError("no vault is set up")
    files = list(local_files(s))
    known = index(c)
    sent = skipped = 0
    for i, (key, f) in enumerate(files):
        sha = sha256_file(f)
        k = known.get(key)
        if k and k["sha256"] == sha:
            skipped += 1
            continue
        remote = be.head(prefixed(cfg, key))
        if not (remote and remote.get("sha256") == sha):
            if progress:
                progress(i / max(1, len(files)), f"uploading {key}")
            be.put(prefixed(cfg, key), f, sha)
            sent += 1
        else:
            skipped += 1
        record(c, key, f.stat().st_size, sha)
    cat = s.data_dir / "catalog.json"
    cat.write_text(json.dumps(catalog(c), indent=1))
    be.put(prefixed(cfg, "catalog/catalog.json"), cat, sha256_file(cat))
    return {"uploaded": sent, "unchanged": skipped, "files": len(files), "where": be.label}


def fetch(s: Settings, c: sqlite3.Connection | None, key: str) -> Path | None:
    """Bring one file back from the vault to where it belongs. None if the vault lacks it."""
    dst = local_path(s, key)
    if dst is None:
        return None
    if dst.exists():
        return dst
    cfg = load_config(s.data_dir)
    be = backend(cfg)
    if be is None:
        return None
    remote = be.head(prefixed(cfg, key))
    if remote is None:
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(f".{dst.name}.part")
    with part.open("wb") as f:
        be.get(prefixed(cfg, key), f)
    if remote.get("sha256") and sha256_file(part) != remote["sha256"]:
        part.unlink(missing_ok=True)
        raise VaultError(f"{key}: the downloaded copy does not match its checksum")
    part.replace(dst)
    if c is not None:
        record(c, key, dst.stat().st_size, remote.get("sha256"))
    return dst


def remote_files(s: Settings) -> list[dict[str, Any]]:
    """Everything the vault holds (keys without the prefix)."""
    cfg = load_config(s.data_dir)
    be = backend(cfg)
    if be is None:
        return []
    pre = prefixed(cfg, "")
    return [{**o, "key": o["key"][len(pre) :]} for o in be.list(pre) if o["key"].startswith(pre)]


def restore_catalog(s: Settings, c: sqlite3.Connection) -> dict[str, int]:
    """Pull catalog.json and add the scenes and names this machine does not have yet."""
    cfg = load_config(s.data_dir)
    be = backend(cfg)
    if be is None:
        raise VaultError("no vault is set up")
    import io

    buf = io.BytesIO()
    try:
        be.get(prefixed(cfg, "catalog/catalog.json"), buf)
    except (VaultError, FileNotFoundError):
        return {"scenes": 0, "names": 0}
    data = json.loads(buf.getvalue() or b"{}")
    have = {r[0] for r in c.execute("SELECT id FROM scenes")}
    n_sc = 0
    for sc in data.get("scenes", []):
        if sc["id"] in have:
            continue
        c.execute(
            "INSERT INTO scenes (id, name, collection, position, data_json, updated_at)"
            " VALUES (?,?,?,?,?,?)",
            (sc["id"], sc["name"], sc["collection"], sc["position"], sc["data_json"],
             sc["updated_at"]),
        )  # fmt: skip
        n_sc += 1
    have_m = {r[0] for r in c.execute("SELECT id FROM artifact_meta")}
    n_m = 0
    for m in data.get("meta", []):
        if m["id"] in have_m:
            continue
        c.execute(
            "INSERT INTO artifact_meta (id, title, tags, updated_at) VALUES (?,?,?,?)",
            (m["id"], m.get("title"), m.get("tags") or "[]", m["updated_at"]),
        )
        n_m += 1
    return {"scenes": n_sc, "names": n_m}
