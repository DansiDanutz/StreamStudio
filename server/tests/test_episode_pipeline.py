"""The episode factory's worker side: planner, clip claims and charges, compose, assemble, kit,
registration, upload, purge. HeyGen and YouTube are faked; ffmpeg is real."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_episodes import CH1, ORIGIN, connect_channel, small_script
from test_heygen import KEY, FakeHeyGen

from streamstudio.api.main import create_app
from streamstudio.core import db, store, youtube
from streamstudio.core.config import Settings
from streamstudio.episode import kit, ledger, mix, planner, preflight, record
from streamstudio.episode import publish as publish_mod
from streamstudio.episode.contract import Scene, Script
from streamstudio.worker import handlers
from streamstudio.worker.main import run_one

ROOT = Path(__file__).resolve().parents[2]
SESSION = "https://upload.example/session-1"


def make_clip(path: Path, seconds: float = 1.0) -> None:
    """A real little MP4 with sound (what HeyGen 'renders')."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", f"color=c=0x203040:s=640x360:r=25:d={seconds}",
         "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000:duration={seconds}",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", str(path)],
        check=True,
    )  # fmt: skip


def make_cutout(path: Path, seconds: float = 1.0) -> None:
    """A VP9 cut-out with alpha (what rembg produces)."""
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"color=c=0xc08060@0.9:s=640x360:r=25:d={seconds},format=rgba",
         "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "200k", str(path)],
        check=True,
    )  # fmt: skip


class RealClipHeyGen(FakeHeyGen):
    """The fake HeyGen, but the download is a real MP4 so the compositor can decode it."""

    def __init__(self) -> None:
        super().__init__()
        self.videos: dict[str, int] = {}
        self.fail = False
        self.drop_once = False

    def __call__(self, req):
        url, method = req.full_url, req.get_method()
        if "files.heygen" in url:
            tmp = Path(url.split("files.heygen.ai/")[1].replace(".mp4", "")) if False else None
            del tmp
            clip = Path("/tmp") / "ss-fake-clip.mp4"
            if not clip.exists():
                make_clip(clip)
            self.calls.append((method, url))
            return 200, clip.read_bytes()
        if url.endswith("/v3/videos") and method == "POST":
            self.calls.append((method, "/v3/videos"))
            n = len(self.videos) + 1
            self.videos[f"vid_{n}"] = 0
            return 200, json.dumps({"data": {"video_id": f"vid_{n}", "status": "waiting"}}).encode()
        if "/v3/videos/vid_" in url:
            vid = url.rsplit("/", 1)[1]
            self.calls.append((method, f"/v3/videos/{vid}"))
            if self.drop_once:
                self.drop_once = False
                raise ConnectionResetError("network dropped")
            if self.fail:
                return 200, json.dumps(
                    {"data": {"status": "failed", "failure_message": "bad audio"}}
                ).encode()
            self.videos[vid] += 1
            if self.videos[vid] < 2:
                return 200, json.dumps({"data": {"status": "processing"}}).encode()
            return 200, json.dumps(
                {"data": {"status": "completed", "video_url": f"https://files.heygen.ai/{vid}.mp4"}}
            ).encode()
        return super().__call__(req)


class FakeTube:
    """Token refresh, a resumable upload, captions, and videos.update."""

    def __init__(self) -> None:
        self.received = b""
        self.size = 0
        self.inits = 0
        self.captions: list[bytes] = []
        self.meta: dict = {}
        self.updates: list[dict] = []

    def __call__(self, req):
        url, method, body = req.full_url, req.get_method(), req.data or b""
        headers = {k.lower(): v for k, v in req.header_items()}
        if url == youtube.TOKEN_URL:
            return 200, {}, json.dumps({"access_token": "at", "expires_in": 3600}).encode()
        if "uploadType=resumable" in url:
            self.inits += 1
            self.meta = json.loads(body)
            self.size = int(headers["x-upload-content-length"])
            return 200, {"Location": SESSION}, b""
        if url == SESSION:
            rng = headers["content-range"]
            if rng.startswith("bytes */"):
                have = len(self.received)
                return 308, ({"Range": f"bytes=0-{have - 1}"} if have else {}), b""
            self.received += body
            if len(self.received) < self.size:
                return 308, {"Range": f"bytes=0-{len(self.received) - 1}"}, b""
            return 200, {}, json.dumps({"id": "vidE1"}).encode()
        if "/youtube/v3/captions" in url:
            self.captions.append(body)
            return 200, {}, json.dumps({"id": "cap1"}).encode()
        if "/youtube/v3/videos" in url and method == "PUT":
            b = json.loads(body)
            self.updates.append(b)
            return 200, {}, json.dumps({"id": b["id"], "status": b["status"]}).encode()
        raise AssertionError(f"unexpected call {method} {url}")


def fake_cutout(mp4: Path, out_webm: Path, plate: Path) -> bool:
    make_cutout(out_webm, 1.0)
    return True


@pytest.fixture
def env(tmp_path, monkeypatch):
    assets = tmp_path / "assets"
    for sub in ("brand", "studio", "models"):
        shutil.copytree(ROOT / "assets" / sub, assets / sub)
    s = Settings(
        data_dir=tmp_path / "data", assets_dir=assets, import_roots=[], allow_tailnet=True,
        extra_hosts=["testclient"], heygen_month_ceiling_usd=50.0,
    )  # fmt: skip
    fake = RealClipHeyGen()
    tube = FakeTube()
    monkeypatch.setattr(handlers, "HEYGEN_TRANSPORT", fake)
    monkeypatch.setattr(handlers, "HEYGEN_POLL_S", 0)
    monkeypatch.setattr(handlers, "CUTOUT", fake_cutout)
    monkeypatch.setattr(handlers, "YOUTUBE_TRANSPORT", tube)
    monkeypatch.setattr(youtube, "CHUNK", 256 * 1024)
    monkeypatch.setattr(publish_mod, "YOUTUBE_TRANSPORT", tube)
    monkeypatch.setattr(preflight, "_pkg", lambda name: True)
    client = TestClient(create_app(s))
    client.put("/api/heygen/config", json={"api_key": KEY, "avatar_id": "look1", "voice_id": "v1"})
    connect_channel(s, CH1, "DansLab")
    youtube._write_private(
        youtube.folder(s.data_dir) / "client.json",
        {"installed": {"client_id": "cid", "client_secret": "s3cret"}},
    )
    return client, s, fake, tube


def approve(client: TestClient, eid: str) -> dict:
    assert client.post(f"/api/episodes/{eid}/approve-script").status_code == 200
    est = client.get(f"/api/episodes/{eid}/estimate").json()
    r = client.post(
        f"/api/episodes/{eid}/approve-budget",
        json={"confirm_token": est["confirm_token"]},
        headers=ORIGIN,
    )
    assert r.status_code == 200, r.text
    return r.json()


def drain(s: Settings, limit: int = 60) -> list[dict]:
    """Run jobs until the queue is empty. Returns the jobs in the order they ran."""
    c = db.connect(s.db_path)
    ran = []
    for _ in range(limit):
        before = {j["id"] for j in store.list_jobs(c, limit=500) if j["status"] in ("queued",)}
        if not before:
            break
        assert run_one(c, s, "w1")
        after = {j["id"]: j for j in store.list_jobs(c, limit=500)}
        done = [after[j] for j in before if after[j]["status"] != "queued"]
        ran.extend(done)
    return ran


def jobs_of(s: Settings, kind: str) -> list[dict]:
    c = db.connect(s.db_path)
    return [j for j in store.list_jobs(c, limit=500) if j["kind"] == kind]


def two_scenes() -> dict:
    return small_script(scenes=[
        {"id": "s1", "text": "Welcome to the lab. What can one agent build in a day?",
         "question": 1, "plan": {"chips": ["An app", "A game"], "chip_at": [0.1, 0.4]}},
        {"id": "s2", "text": "The end, and yes: this was my AI avatar.", "reveal": True,
         "plan": {"endcard": ["Subscribe", "DansLab", "new episodes"], "end_at": 0.1,
                  "end_until": 1.0}},
    ])  # fmt: skip


# ---------------------------------------------------------------- the thin slice


def test_the_thin_slice_runs_from_approval_to_a_private_upload(env):
    client, s, fake, tube = env
    eid = client.post("/api/episodes", json=two_scenes()).json()["id"]
    youtube._channel_file(s.data_dir, CH1).unlink()
    approve(client, eid)
    ran = drain(s)
    assert client.get(f"/api/episodes/{eid}").json()["status"] == "ready"
    assert all(j["kind"] != "youtube_upload" for j in ran)
    assert client.post(f"/api/episodes/{eid}/advance").status_code == 409
    assert client.post(f"/api/episodes/{eid}/upload").status_code == 403
    assert client.post(f"/api/episodes/{eid}/upload", headers=ORIGIN).status_code == 409
    assert tube.inits == 0
    connect_channel(s, CH1, "DansLab")
    assert client.post(f"/api/episodes/{eid}/upload", headers=ORIGIN).status_code == 202
    assert client.post(f"/api/episodes/{eid}/upload", headers=ORIGIN).status_code == 409
    ran += drain(s)
    kinds = [j["kind"] for j in ran]
    assert kinds.count("heygen_clip") == 2 and kinds.count("scene_compose") == 2
    for k in ("episode_assemble", "episode_publish_kit", "episode_register", "youtube_upload"):
        assert kinds.count(k) == 1, kinds
    assert all(j["status"] == "done" for j in ran), [
        (j["kind"], j["error"]) for j in ran if j["status"] != "done"
    ]
    assert [c for c in fake.calls if c == ("POST", "/v3/videos")] == [("POST", "/v3/videos")] * 2
    ep = client.get(f"/api/episodes/{eid}").json()
    assert ep["status"] == "uploaded_private", ep["log"]
    assert ep["outputs"]["youtube_video_id"] == "vidE1" and ep["next_action"] == "Publish"
    assert kinds.count("scene_qa") == 2
    assert ep["scenes_state"]["s1"]["qa"] == "degraded"  # synthetic solid-color presenter
    sheet = client.get(f"/api/episodes/{eid}/qa/s1.jpg")
    assert sheet.status_code == 200 and sheet.content.startswith(b"\xff\xd8")
    assert ep["progress"] == {"clips": 2, "qa": 2, "composed": 2, "total": 2}
    rid = ep["outputs"]["recording_id"]
    assert rid.endswith("-ep") and (s.recordings_dir / f"{rid}.mp4").exists()
    assert (s.recordings_dir / f"{rid}.srt").exists()
    assert json.loads((s.recordings_dir / f"{rid}.transcript.json").read_text())["language"] == "en"
    # composed scenes: 25 fps, one frame per 40 ms, the clip's audio
    d = record.episode_dir(s, eid)
    for sid in ("s1", "s2"):
        assert mix._frame_count(s, d / "scenes" / f"{sid}.mp4") == 25
    assert not (d / "final.mp4").exists()  # moved into the library
    k = json.loads((d / "kit.json").read_text())
    assert k["title"] == "Test episode" and k["chapters"] == [] and k["notes"]
    assert "Welcome to the lab" in (d / "final.srt").read_text()
    cues = json.loads((d / "final.cues.json").read_text())
    assert {c["kind"] for c in cues["cues"]} == {
        "question_riser",
        "question_pop",
        "reveal",
        "endcard",
    }
    assert tube.meta["status"]["privacyStatus"] == "private" and tube.inits == 1
    assert tube.captions and b"Welcome" in tube.captions[0]
    # the ledger: two charges, the reservation released
    c = db.connect(s.db_path)
    kinds_l = [r["kind"] for r in c.execute("SELECT kind FROM heygen_ledger ORDER BY at, kind")]
    assert kinds_l.count("charge") == 2 and kinds_l.count("release") == 1
    assert ep["budget"]["spent"]["renders"] == 2
    assert ledger.unconsumed(c, eid) == 0
    # the library lists the episode as a take, newest first
    listing = client.get("/api/recordings").json()
    assert listing[0]["id"] == rid and listing[0]["episode"] == eid and listing[0]["mp4"]
    # a second planner pass is a no-op
    assert planner.advance(c, s, eid)["skipped"] == "episode is uploaded_private"
    # publish, then purge
    assert client.post(f"/api/episodes/{eid}/publish", json={}).json()["status"] == "published"
    assert tube.updates[-1]["status"] == {"privacyStatus": "public"}
    client.post(f"/api/episodes/{eid}/purge")
    drain(s)
    ep = client.get(f"/api/episodes/{eid}").json()
    assert ep["status"] == "purged" and "freed" in ep["last_log"]
    assert not (d / "scenes").exists() and not (d / "mix").exists()
    assert (
        (d / "kit.json").exists() and (d / "final.srt").exists() and (d / "episode.json").exists()
    )
    assert (s.recordings_dir / f"{rid}.mp4").exists()


def test_two_planners_at_once_pay_once_per_key(env):
    client, s, fake, _ = env
    eid = client.post("/api/episodes", json=two_scenes()).json()["id"]
    approve(client, eid)
    c = db.connect(s.db_path)
    assert run_one(c, s, "w1")  # the first planner: two clip jobs
    planner.advance(c, s, eid)  # a second planner sees the live jobs
    assert len(jobs_of(s, "heygen_clip")) == 2
    drain(s)
    assert [x for x in fake.calls if x == ("POST", "/v3/videos")] == [("POST", "/v3/videos")] * 2
    assert client.get(f"/api/episodes/{eid}").json()["status"] == "ready"


def test_a_failed_render_is_recorded_charged_once_and_parks_the_episode(env):
    client, s, fake, _ = env
    fake.fail = True
    eid = client.post("/api/episodes", json=two_scenes()).json()["id"]
    approve(client, eid)
    drain(s)
    ep = client.get(f"/api/episodes/{eid}").json()
    assert ep["status"] == "needs_dan" and "bad audio" in ep["last_log"]
    key = ep["scenes_state"]["s1"]["clip_key"]
    state = record.read_clip_state(s, key)
    assert state["failed"] == "bad audio" and state["video_id"]
    c = db.connect(s.db_path)
    charges = c.execute(
        "SELECT clip_key, seconds FROM heygen_ledger WHERE kind = 'charge'"
    ).fetchall()
    assert len(charges) == 2 and all(r["seconds"] > 0 for r in charges)  # estimated seconds
    clip_jobs = jobs_of(s, "heygen_clip")
    assert len(clip_jobs) == 2 and all(j["status"] == "done" for j in clip_jobs)
    assert all(j["result"]["failed"] == "bad audio" for j in clip_jobs)
    # advancing does not re-render a failed take by itself (the allowance arrives in Stage 2)
    client.post(f"/api/episodes/{eid}/advance")
    drain(s)
    assert len(jobs_of(s, "heygen_clip")) == 2
    assert client.get(f"/api/episodes/{eid}").json()["status"] == "needs_dan"


def test_a_worker_error_parks_the_episode_and_advance_resumes_the_render(env):
    client, s, fake, _ = env
    fake.drop_once = True
    eid = client.post("/api/episodes", json=two_scenes()).json()["id"]
    approve(client, eid)
    c = db.connect(s.db_path)
    assert run_one(c, s, "w1")  # planner
    assert run_one(c, s, "w1")  # the first clip job: network drops after create_video
    first = (
        jobs_of(s, "heygen_clip")[-1]
        if jobs_of(s, "heygen_clip")[-1]["status"] == "error"
        else jobs_of(s, "heygen_clip")[0]
    )
    assert (
        first["status"] == "error" and first["attempts"] == 1
    )  # max_attempts 1: no retry on its own
    drain(s)
    ep = client.get(f"/api/episodes/{eid}").json()
    assert ep["status"] == "needs_dan" and "ended in error" in ep["last_log"]
    creates = [x for x in fake.calls if x == ("POST", "/v3/videos")]
    assert len(creates) == 2  # both scenes were submitted once
    r = client.post(f"/api/episodes/{eid}/advance")
    assert r.status_code == 202
    drain(s)
    assert [
        x for x in fake.calls if x == ("POST", "/v3/videos")
    ] == creates  # resumed, not paid again
    replacement = [j for j in jobs_of(s, "heygen_clip") if j["id"] != first["id"]]
    assert all(j["status"] == "done" for j in replacement)
    assert client.get(f"/api/episodes/{eid}").json()["status"] == "ready"


def test_a_stale_requeue_keeps_the_job_id_and_claim(env):
    client, s, fake, _ = env
    eid = client.post("/api/episodes", json=two_scenes()).json()["id"]
    approve(client, eid)
    c = db.connect(s.db_path)
    assert run_one(c, s, "w1")
    job = jobs_of(s, "heygen_clip")[0]
    c.execute("UPDATE jobs SET status = 'running', heartbeat_at = 0 WHERE id = ?", (job["id"],))
    assert store.requeue_stale(c, 60) == 1
    again = store.get_job(c, job["id"])
    assert again["status"] == "queued" and again["payload"]["max_attempts"] == 1
    drain(s)
    assert client.get(f"/api/episodes/{eid}").json()["status"] == "ready"


# ---------------------------------------------------------------- the pieces


def test_compose_on_the_plate_with_the_guard(env, tmp_path):
    from streamstudio.episode import compose

    _, s, _, _ = env
    clip, cut = tmp_path / "c.mp4", tmp_path / "c.cutout.webm"
    make_clip(clip, 0.6)
    make_cutout(cut, 0.6)
    sc = Scene(
        id="s1",
        text="Hello",
        question=1,
        plan={"title": ["DansLab", "the lab"], "glitch": [[0.5, 0.2]]},
    )
    out = tmp_path / "out.mp4"
    r = compose.compose_scene(s, sc, clip, cut, out)
    assert r["frames"] == 15 and r["cue"] == "avatar" and out.exists()
    assert mix._frame_count(s, out) == 15
    card = Scene(id="s2", text="x", kind="card", site="https://nervix.space/list")
    assert compose.guard(card, "/avatar/clips/c.mp4", False) == "content"
    assert compose.guard(card, "/avatar/clips/c.mp4", True) == "pip"
    assert compose.effective_plan(card).lower == ("nervix.space", None)
    r = compose.compose_scene(s, card, clip, cut, tmp_path / "pip.mp4", degraded=True)
    assert r["cue"] == "pip"


def test_assemble_refuses_a_frame_count_mismatch(env, tmp_path):
    _, s, _, _ = env
    bad = tmp_path / "s1.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x180:r=30:d=1",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(bad)], check=True,
    )  # fmt: skip
    with pytest.raises(RuntimeError, match="not 25 fps"):
        mix.assemble(
            s,
            [Scene(id="s1", text="x")],
            [bad],
            s.assets_dir / "brand" / "danslab-intro.mp4",
            tmp_path / "f.mp4",
        )


def test_kit_chapters_captions_and_the_intro_offset():
    script = Script.model_validate({"title": "T", "tags": ["a"], "scenes": [
        {"id": "s1", "text": "Intro words here."},
        {"id": "s2", "text": "First question. More words.", "question": 1},
        {"id": "s3", "text": "Short one.", "question": 2},
        {"id": "s4", "text": "Third question! Again.", "question": 3},
        {"id": "s5", "text": "Fourth question? Yes.", "question": 4},
    ]})  # fmt: skip
    durations = [12.0, 15.0, 4.0, 20.0, 14.0]
    starts = [0.0, 12.0, 27.0, 31.0, 51.0]
    k, srt = kit.build_kit(script, starts, durations, 7.2)
    # s3 (4 s) folds into s2; everything is offset by the 7.2 s intro
    assert k["chapters"] == [
        "0:00 Intro",
        "0:19 First question",
        "0:38 Third question",
        "0:58 Fourth question",
    ]
    assert (
        k["description"].startswith("Intro words here.")
        and "Chapters\n0:00 Intro" in k["description"]
    )
    assert k["tags"] == ["a"] and k["notes"] == []
    assert srt.startswith("1\n00:00:07,200 --> 00:00:19,200\nIntro words here.")
    # fewer than three chapters: none, with a note
    few, _ = kit.build_kit(
        Script.model_validate({"title": "T", "scenes": [{"id": "s1", "text": "a", "question": 1}]}),
        [0.0],
        [30.0],
        7.2,
    )
    assert few["chapters"] == [] and "at least 3 chapters" in few["notes"][0]
    assert kit.caption_chunks("one two " * 30)[0].count("\n") == 1
    assert all(
        len(line) <= 42 for chunk in kit.caption_chunks("word " * 40) for line in chunk.split("\n")
    )
    # whisper word timings (Stage 2) place the captions inside the scene
    _, timed = kit.build_kit(
        script,
        starts,
        durations,
        0.0,
        {"s1": [{"start": 1.0, "end": 1.5}, {"start": 3.0, "end": 4.0}]},
    )
    assert timed.startswith("1\n00:00:01,000 --> 00:00:04,000")


def test_registration_names_and_the_library_listing(env, tmp_path):
    client, s, _, _ = env
    final, srt = tmp_path / "final.mp4", tmp_path / "final.srt"
    make_clip(final, 0.5)
    srt.write_text("1\n00:00:00,000 --> 00:00:00,500\nhi\n")
    r = kit.register(s, "ep_test1234", final, srt, {"title": "T"})
    rid = r["recording_id"]
    assert rid.startswith("rec_") and rid.endswith("-ep") and not final.exists()
    assert kit.registered_recording(s, "ep_test1234") == rid
    assert kit.registered_recording(s, "ep_other") is None
    # an ordinary take uploaded earlier sorts after a newer episode and before an older one
    (s.recordings_dir / "rec_20200101-000000.source.webm").write_bytes(b"x")
    ids = [x["id"] for x in client.get("/api/recordings").json()]
    assert ids == sorted(ids, reverse=True) and rid in ids and "rec_20200101-000000" in ids
    time.sleep(0)

def test_cached_website_demo_reaches_library_and_serves_scene_preview(env):
    from streamstudio.core.config import CaptureSite
    from streamstudio.episode.website_demo import asset_path

    client, s, _, tube = env
    s.capture_allowlist = [CaptureSite(host="nervixpay.live")]
    scene = Scene.model_validate({
        "id": "s10", "kind": "card", "site": "https://nervixpay.live",
        "text": "Look at the product QR code.",
        "plan": {"website_demo": {"focus_label": "Scannable NervixPay product preview"}},
    })
    rules = client.get("/api/episodes/workflows").json()
    assert rules[0]["id"] == "website-demo/v1"
    eid = client.post("/api/episodes", json=small_script(scenes=[scene.model_dump()])).json()["id"]
    card = asset_path(record.episode_dir(s, eid), scene)
    make_clip(card)
    preview = f"/api/episodes/{eid}/scenes/s10/preview"
    assert client.get(preview).status_code == 404
    approve(client, eid)
    ran = drain(s)
    assert all(j["status"] == "done" for j in ran), [(j["kind"], j["error"]) for j in ran]
    assert client.get(f"/api/episodes/{eid}").json()["status"] == "ready"
    response = client.get(preview)
    assert response.headers["content-type"] == "video/mp4" and b"ftyp" in response.content[:32]
    assert tube.inits == 0
