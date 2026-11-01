"""Job handlers. Each handler gets a JobContext and returns a JSON-able result dict.

Add a handler by decorating it with @handler("kind"). Handlers must be idempotent:
a crashed job is retried from the start.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core import media, store
from ..core.config import Settings


@dataclass
class JobContext:
    job: dict[str, Any]
    conn: sqlite3.Connection
    settings: Settings

    def progress(self, p: float, message: str | None = None) -> None:
        store.heartbeat(self.conn, self.job["id"], p, message)

    def cancelled(self) -> bool:
        j = store.get_job(self.conn, self.job["id"])
        return bool(j and j["status"] == "cancelled")


Handler = Callable[[JobContext], dict[str, Any]]
HANDLERS: dict[str, Handler] = {}


def handler(kind: str) -> Callable[[Handler], Handler]:
    def wrap(fn: Handler) -> Handler:
        HANDLERS[kind] = fn
        return fn

    return wrap


@handler("probe")
def probe_asset(ctx: JobContext) -> dict[str, Any]:
    asset = store.get_asset(ctx.conn, ctx.job["asset_id"])
    if asset is None:
        raise ValueError("asset no longer exists")
    ctx.progress(0.1, "probing")
    try:
        info = media.summarize(media.probe(Path(asset["path"]), ctx.settings.ffprobe_bin))
    except media.MediaError as e:
        store.update_asset(ctx.conn, asset["id"], status="error")
        raise ValueError(str(e)) from e
    store.update_asset(
        ctx.conn, asset["id"], status="ready", duration_us=info["duration_us"], probe_json=info
    )
    return info


@handler("noop")
def noop(ctx: JobContext) -> dict[str, Any]:
    """Used by tests and the health page to prove the worker is alive."""
    ctx.progress(0.5, "noop")
    return {"ok": True, "echo": ctx.job.get("payload")}


@handler("finish_recording")
def finish_recording(ctx: JobContext) -> dict[str, Any]:
    """Program-window take → MP4 (H.264 + AAC, -14 LUFS). Idempotent: an up-to-date MP4 is kept."""
    import subprocess

    p = ctx.job.get("payload") or {}
    if isinstance(p, str):
        import json

        p = json.loads(p)
    d = ctx.settings.recordings_dir
    src = d / p["source"]
    if not src.exists() or src.parent != d:
        raise ValueError("source recording is missing")
    dst = d / f"{p['id']}.mp4"
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return {"mp4": dst.name, "skipped": True}
    hw = "h264_videotoolbox" in media.hw_encoders(ctx.settings.ffmpeg_bin)
    venc = (
        ["-c:v", "h264_videotoolbox", "-b:v", "16M"]
        if hw
        else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"]
    )
    tmp = dst.with_suffix(".tmp.mp4")
    ctx.progress(0.1, "encoding")
    subprocess.run(
        [ctx.settings.ffmpeg_bin, "-v", "error", "-y", "-i", str(src), *venc, "-pix_fmt", "yuv420p",
         "-r", "30", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k",
         "-ar", "48000", "-movflags", "+faststart", str(tmp)],
        check=True,
    )  # fmt: skip
    tmp.replace(dst)
    queue_vault_push(ctx.conn, ctx.settings)
    return {"mp4": dst.name, "encoder": "videotoolbox" if hw else "x264"}


@handler("transcribe")
def transcribe_recording(ctx: JobContext) -> dict[str, Any]:
    """Take MP4 → <id>.transcript.json + <id>.srt (whisper.cpp, local). Idempotent: a transcript
    newer than the MP4 is kept."""
    from ..core import transcribe

    p = ctx.job.get("payload") or {}
    d = ctx.settings.recordings_dir
    mp4 = d / f"{p['id']}.mp4"
    if not mp4.exists():
        raise ValueError("the take has no MP4 yet")
    out_json, out_srt = d / f"{p['id']}.transcript.json", d / f"{p['id']}.srt"
    if out_json.exists() and out_srt.exists() and out_json.stat().st_mtime >= mp4.stat().st_mtime:
        return {"transcript": out_json.name, "skipped": True}
    ctx.progress(0.1, "transcribing")
    t = transcribe.transcribe(mp4, out_json, out_srt, ctx.settings)
    return {"transcript": out_json.name, "srt": out_srt.name, "language": t["language"],
            "words": len(t["words"]), "model": t["model"]}  # fmt: skip


#: Tests replace this with a fake Google.
YOUTUBE_TRANSPORT = None


@handler("youtube_upload")
def youtube_upload(ctx: JobContext) -> dict[str, Any]:
    """Take MP4 → a YouTube video (private unless asked otherwise), then its captions if the take
    has a transcript. Resumable and idempotent: a retried job never creates a second video."""
    import json

    from ..core import youtube

    p = ctx.job.get("payload") or {}
    d = ctx.settings.recordings_dir
    mp4 = d / f"{p['id']}.mp4"
    if not mp4.exists():
        raise ValueError("the take has no MP4 yet")
    api = youtube.Client(ctx.settings.data_dir, p["channel"], YOUTUBE_TRANSPORT)
    state = youtube.folder(ctx.settings.data_dir) / "uploads" / f"{p['channel']}-{p['id']}.json"
    ctx.progress(0.02, "uploading to YouTube")
    video_id = youtube.upload(
        api, mp4, p["meta"], state, lambda f: ctx.progress(0.02 + 0.9 * f, "uploading to YouTube")
    )
    captions = None
    srt, transcript = d / f"{p['id']}.srt", d / f"{p['id']}.transcript.json"
    done = json.loads(state.read_text())
    if srt.exists() and not done.get("captions"):
        ctx.progress(0.95, "adding captions")
        lang = json.loads(transcript.read_text()).get("language") if transcript.exists() else None
        captions = youtube.add_captions(api, video_id, srt, lang or "en")
        youtube._write_private(state, {**done, "captions": captions})
    return {
        "video_id": video_id,
        "url": f"https://youtu.be/{video_id}",
        "studio": f"https://studio.youtube.com/video/{video_id}/edit",
        "privacy": p["meta"]["privacy"],
        "channel": p["channel"],
        "captions": captions or done.get("captions"),
    }


# ---------------------------------------------------------------- HeyGen avatar clips

#: Tests replace these: the HTTP transport, the poll interval, and the cut-out step.
HEYGEN_TRANSPORT = None
HEYGEN_POLL_S = 8.0


def _cutout_clip(mp4: Path, out_webm: Path, plate: Path) -> bool:
    """Cut Dan out of a rendered clip (local rembg). False if the cut-out tools are missing."""
    import shutil

    try:
        from ..avatar.cutout import run as cutout_run
    except ImportError:
        return False
    tmp = out_webm.parent / f".work-{out_webm.stem}"
    res = cutout_run(mp4, plate, tmp, scale=0.66, hands_y=0.68, x=0.47, keep=False)
    shutil.move(res["cutout_webm"], out_webm)
    shutil.rmtree(tmp, ignore_errors=True)
    return True


CUTOUT = _cutout_clip


@handler("heygen_clip")
def heygen_clip(ctx: JobContext) -> dict[str, Any]:
    """Render one avatar clip on HeyGen (paid), download it, cut it out. Idempotent and resumable:
    the HeyGen video id is saved before polling, so a retried job never pays twice."""
    import json
    import time
    import urllib.request

    from ..core import heygen

    p = ctx.job.get("payload") or {}
    if isinstance(p, str):
        p = json.loads(p)
    s = ctx.settings
    kind = p["kind"]
    name = p["gesture"] if kind == "gesture" else p["key"]
    out_dir = s.assets_dir / "avatar" / ("gestures" if kind == "gesture" else "clips")
    out_dir.mkdir(parents=True, exist_ok=True)
    mp4 = out_dir / f"{name}.mp4"
    webm = out_dir / f"{name}.cutout.webm"
    url = f"/avatar/{out_dir.name}/{mp4.name}"
    state_dir = s.data_dir / "heygen"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / f"{p['key']}.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {}

    if not mp4.exists():
        cfg = heygen.load_config(s.data_dir)
        client = heygen.Client(cfg["api_key"], HEYGEN_TRANSPORT)
        if not state.get("video_id"):
            audio = None
            if p.get("silent_s"):
                audio = client.upload_asset(
                    "silence.wav", heygen.silence_wav(p["silent_s"]), "audio/wav"
                )
            spec = heygen.video_spec(
                p["look"], p["voice"], script=p.get("script"), audio_asset_id=audio,
                motion=p.get("motion"), title=f"StreamStudio · {name}",
            )  # fmt: skip
            ctx.progress(0.05, "sent to HeyGen")
            state["video_id"] = client.create_video(spec)
            state_file.write_text(json.dumps(state))
        deadline = time.time() + 30 * 60
        while True:
            v = client.get_video(state["video_id"])
            st = v.get("status")
            if st == "completed" and v.get("video_url"):
                break
            if st == "failed":
                state_file.unlink(missing_ok=True)  # a failed render can be retried as a new one
                raise ValueError(
                    f"HeyGen failed: {v.get('failure_message') or v.get('failure_code')}"
                )
            if time.time() > deadline:
                raise TimeoutError("HeyGen is still rendering after 30 minutes")
            if ctx.cancelled():
                return {"cancelled": True, "video_id": state["video_id"]}
            ctx.progress(0.1 + 0.6 * (st == "processing"), f"HeyGen: {st}")
            time.sleep(HEYGEN_POLL_S)
        ctx.progress(0.75, "downloading")
        part = mp4.with_suffix(".part")
        req = urllib.request.Request(v["video_url"])  # presigned: no key sent
        if HEYGEN_TRANSPORT:
            _, data = HEYGEN_TRANSPORT(req)
            part.write_bytes(data)
        else:
            with urllib.request.urlopen(req, timeout=300) as r, part.open("wb") as f:  # noqa: S310
                shutil_copy(r, f)
        part.replace(mp4)
    cut = None
    if not webm.exists() or webm.stat().st_mtime < mp4.stat().st_mtime:
        ctx.progress(0.85, "cutting out")
        plate = s.assets_dir / "studio" / "plate-landscape-final.png"
        if CUTOUT and CUTOUT(mp4, webm, plate):
            cut = f"/avatar/{out_dir.name}/{webm.name}"
    else:
        cut = f"/avatar/{out_dir.name}/{webm.name}"
    queue_vault_push(ctx.conn, s)
    return {
        "clip": url,
        "cutout": cut,
        "kind": kind,
        "name": name,
        "video_id": state.get("video_id"),
    }


def shutil_copy(src: Any, dst: Any) -> None:
    import shutil

    shutil.copyfileobj(src, dst, 1024 * 1024)


# ---------------------------------------------------------------- vault (copies off this machine)


def queue_vault_push(conn: sqlite3.Connection, s: Settings) -> dict[str, Any] | None:
    """Queue a vault backup if a vault is set up and none is already waiting."""
    from ..core import vault

    if not vault.load_config(s.data_dir).get("kind"):
        return None
    j = conn.execute(
        "SELECT id FROM jobs WHERE kind = 'vault_push' AND status IN ('queued') LIMIT 1"
    ).fetchone()
    if j:
        return store.get_job(conn, j["id"])
    return store.enqueue(conn, "vault_push")


@handler("vault_push")
def vault_push(ctx: JobContext) -> dict[str, Any]:
    """Copy new or changed clips, takes and the catalog to the vault. Idempotent by checksum."""
    from ..core import vault

    return vault.push(ctx.settings, ctx.conn, lambda p, m: ctx.progress(p, m))
