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
        extra_hosts=["testclient"], heygen_month_ceiling_usd=50.0, episode_rerender_attempts=0,
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
    # advancing does not re-render a failed take after the approved allowance is exhausted
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

def test_cached_website_demo_reaches_library_and_serves_scene_preview(env, tmp_path):
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
    bed = tmp_path / "bed.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=330:d=0.3",
                    str(bed)], check=True)
    upload_url = "/api/channels/files?name=bed.wav&role=audio"
    assert client.put(upload_url, content=b"not wave audio", headers=ORIGIN).status_code == 422
    upload = client.put(upload_url, content=bed.read_bytes(), headers=ORIGIN)
    assert upload.status_code == 200, upload.text
    digest = upload.json()["sha256"]
    assert client.get(f"/api/channels/files/{digest}").content == bed.read_bytes()
    from PIL import Image

    photo = tmp_path / "plate.png"
    Image.new("RGB", (64, 36), (15, 230, 40)).save(photo)
    image_url = "/api/channels/files?role=image&name=plate.png"
    assert client.put(image_url, content=bed.read_bytes(), headers=ORIGIN).status_code == 422
    uploaded = client.put(image_url, content=photo.read_bytes(), headers=ORIGIN).json()
    plate = {"image": uploaded["sha256"], "seat": {"scale": .6, "hands_y": .7, "x": .47}}
    from array import array

    intro = tmp_path / "intro.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=red:s=320x180:r=30:d=1",
                    "-f", "lavfi", "-i", "sine=frequency=440:d=1", "-c:v", "libx264", "-c:a",
                    "aac", "-shortest", str(intro)], check=True)
    result = client.put("/api/channels/files?role=intro&name=intro.mp4",
                        content=intro.read_bytes(), headers=ORIGIN)
    assert result.status_code == 200, result.text
    intro_hash = result.json()["sha256"]
    normalized = tmp_path / "normalized.mp4"
    normalized.write_bytes(client.get(f"/api/channels/files/{intro_hash}").content)
    streams = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams",
                                                  "-of", "json", str(normalized)]))["streams"]
    assert streams[0]["r_frame_rate"] == "25/1" and streams[0]["width"] == 1920
    audio = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(normalized), "-vn",
                                     "-ac", "1", "-ar", "16000", "-f", "s16le", "-"])
    assert max(array("h", audio)) > 1000
    profile = client.get("/api/channels/danslab").json()
    profile["profile"]["look"] = {"plate": plate}
    profile["profile"]["sound"] = {"bed": digest, "intro": intro_hash}
    profile["profile"].update(language="en-GB", publish={
        "description_footer": "Engineering at DansLab", "default_tags": ["walkthrough"]})
    saved = client.put("/api/channels/danslab", headers=ORIGIN, json={
        "base_version": profile["version"], "profile": profile["profile"]})
    assert saved.status_code == 200
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

    original = client.get(f"/api/episodes/{eid}").json()["outputs"]["recording_id"]
    metadata = json.loads((record.episode_dir(s, eid) / "kit.json").read_text())
    assert metadata["description"].endswith("Engineering at DansLab")
    timing_file = record.episode_dir(s, eid) / "assemble.json"
    assert 0.96 <= json.loads(timing_file.read_text())["intro_s"] <= 1.08
    assert "walkthrough" in metadata["tags"]
    assert json.loads((s.recordings_dir / f"{original}.transcript.json").read_text())[
        "language"] == "en-GB"
    scene.plan.website_demo.side = "left"
    scene.plan.website_demo.reveal_at = .55
    body = small_script(scenes=[scene.model_dump()])
    edited = client.put(f"/api/episodes/{eid}/script", json=body)
    assert edited.status_code == 200 and edited.json()["status"] == "draft"
    assert client.get(preview).status_code == 404
    approve(client, eid)
    latest = client.get("/api/channels/danslab").json()
    latest["profile"]["sound"] = {}
    latest["profile"]["look"] = None
    changed = client.put("/api/channels/danslab", headers=ORIGIN, json={
        "base_version": latest["version"], "profile": latest["profile"]})
    assert changed.status_code == 200
    second_run = drain(s)
    revised = client.get(f"/api/episodes/{eid}").json()
    assert revised["status"] == "ready"
    assert revised["profile"]["profile"]["sound"]["bed"] == digest
    assert revised["profile"]["profile"]["look"]["plate"]["image"] == uploaded["sha256"]
    # The corner lies outside the foreground presenter and card in either revision.
    for content in (response.content, client.get(preview).content):
        pixel = subprocess.check_output(["ffmpeg", "-v", "error", "-i", "pipe:0", "-frames:v", "1",
                                        "-vf", "crop=4:4:0:0,scale=1:1", "-f", "rawvideo",
                                        "-pix_fmt", "rgb24", "-"], input=content)
        assert pixel[1] > max(pixel[0], pixel[2]) + 35
    assert revised["outputs"]["recording_id"] != original
    assert (s.recordings_dir / f"{original}.mp4").exists()
    assert client.get(preview).content != response.content
    assert {j["kind"] for j in second_run}.isdisjoint({"heygen_clip", "scene_qa", "youtube_upload"})
    assert asset_path(record.episode_dir(s, eid), scene) == card

    base = f"/api/episodes/{eid}"
    assert client.get(base).json()["profile_latest_version"] == changed.json()["version"]
    assert client.post(base + "/repin", json={}).status_code == 403
    draft = client.post(base + "/repin", json={}, headers=ORIGIN).json()
    assert draft["status"] == "draft" and "recording_id" not in draft["outputs"]
    assert client.post(base + "/upload", headers=ORIGIN).status_code == 409
    approve(client, eid)
    repinned_run = drain(s)
    updated = client.get(base).json()
    assert updated["status"] == "ready"
    assert json.loads(timing_file.read_text())["intro_s"] == 0
    assert updated["profile"]["version"] == changed.json()["version"]
    assert updated["outputs"]["recording_id"] != revised["outputs"]["recording_id"]
    assert not {"heygen_clip", "scene_qa", "youtube_upload"} & {j["kind"] for j in repinned_run}
    assert "scene_compose" in {j["kind"] for j in repinned_run}


def test_partial_library_registration_keeps_source_and_recovers(env, tmp_path, monkeypatch):
    client, s, _, _ = env
    movie = tmp_path / "final.mp4"
    movie.write_bytes(b"encoded scene")
    caps = tmp_path / "final.srt"
    caps.write_text("captions")
    original_replace = Path.replace

    def fail_at_visibility(path, target):
        if path.suffix == ".mp4":
            raise OSError("simulated interrupted registration")
        return original_replace(path, target)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "replace", fail_at_visibility)
        with pytest.raises(OSError, match="interrupted"):
            kit.register(s, "ep_test1234", movie, caps, {"title": "Tour"})
    assert movie.read_bytes() == b"encoded scene"
    assert kit.registered_recording(s, "ep_test1234") is None
    assert client.get("/api/recordings").json() == []
    saved = kit.register(s, "ep_test1234", movie, caps, {"title": "Tour"})
    assert Path(saved["mp4"]).read_bytes() == b"encoded scene"
    assert Path(saved["srt"]).read_text() == "captions"
    assert kit.registered_recording(s, "ep_test1234") == saved["recording_id"]


def test_connected_card_workflow_renders_motion_and_preserves_the_approved_audio(env):
    client, s, _, _ = env
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if not chrome:
        candidate = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
        chrome = str(candidate) if candidate.exists() else None
    if chrome:
        s.hyperframes_browser = Path(chrome)
    rules = client.get("/api/episodes/workflows").json()
    assert any(rule["id"] == "connected-cards/v1" for rule in rules)
    scene = {"id": "s1", "kind": "card", "text": "We capture, direct and review each scene.",
             "plan": {"connected_cards": {"title": "How a scene is made", "cards": [
                 {"title": "Capture", "body": "Record the source."},
                 {"title": "Direct", "body": "Set the reveal."},
                 {"title": "Review", "body": "Play the result."},
             ]}}}
    eid = client.post("/api/episodes", json=small_script(scenes=[scene])).json()["id"]
    approve(client, eid)
    jobs = drain(s)
    assert all(j["status"] == "done" for j in jobs), [(j["kind"], j["error"]) for j in jobs]
    ep = client.get(f"/api/episodes/{eid}").json()
    assert ep["status"] == "ready"
    movie = record.episode_dir(s, eid) / "scenes" / "s1.mp4"
    clip, _ = record.clip_paths(s, ep["scenes_state"]["s1"]["clip_key"])

    def audio_hash(path):
        return subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a",
                                        "-c", "copy", "-f", "hash", "-hash", "sha256", "-"])

    assert audio_hash(movie) == audio_hash(clip)
    frames = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(movie), "-vf",
                                      "fps=5,scale=160:90", "-an", "-f", "framemd5", "-"])
    assert len({line.split(b",")[-1] for line in frames.splitlines() if line.startswith(b"0,")}) > 2


@pytest.mark.parametrize(("attempts", "usd", "cache_only", "expected_retries"), [
    (1, 1.5, False, 1), (4, .001, False, 0), (4, 1.5, True, 0),
])
def test_retry_caps_and_cache_only(env, attempts, usd, cache_only, expected_retries):
    client, s, fake, _ = env
    s.episode_rerender_attempts = attempts
    s.episode_rerender_usd = usd
    fake.fail = True
    eid = client.post("/api/episodes", json=two_scenes()).json()["id"]
    approve(client, eid)
    # Simulate an operator turning cache-only on after approval and a submitted take failing.
    c = db.connect(s.db_path)
    assert run_one(c, s, "plan")
    first = jobs_of(s, "heygen_clip")[0]
    assert run_one(c, s, "render")
    s.heygen_cache_only = cache_only
    drain(s)
    ep = client.get(f"/api/episodes/{eid}").json()
    assert ep["status"] == "needs_dan"
    assert len(ep["budget"]["retries"]) == expected_retries
    assert len(jobs_of(s, "heygen_clip")) == 2 + expected_retries
    if expected_retries:
        retry = ep["budget"]["retries"][0]
        assert retry["take"] == 1 and retry["key"] != first["payload"]["key"]
    paid_calls = sum(call == ("POST", "/v3/videos") for call in fake.calls)
    client.post(f"/api/episodes/{eid}/advance")
    drain(s)
    assert sum(call == ("POST", "/v3/videos") for call in fake.calls) == paid_calls


def test_visual_failure_retries_once_then_uses_degraded_layout(env):
    client, s, _, _ = env
    s.episode_rerender_attempts = 1
    scene = {"id": "s1", "text": "The factory verifies every scene before assembly."}
    eid = client.post("/api/episodes", json=small_script(scenes=[scene])).json()["id"]
    approve(client, eid)
    drain(s)
    ep = client.get(f"/api/episodes/{eid}").json()
    assert ep["status"] == "ready"
    state = ep["scenes_state"]["s1"]
    assert state["qa"] == "degraded" and state["take"] == 1
    assert len(state["rejected_takes"]) == 1 and len(ep["budget"]["retries"]) == 1
    assert ep["budget"]["spent"]["renders"] == 2


def test_manual_capture_is_scoped_to_page_and_worker_uses_it_offline(env, tmp_path, monkeypatch):
    from PIL import Image, ImageDraw

    from streamstudio.core.config import CaptureSite
    from streamstudio.episode import website_demo

    client, s, _, _ = env
    s.capture_allowlist = [CaptureSite(host="private.example", mode="manual")]
    site = "https://private.example/dashboard"
    endpoint = "/api/episodes/captures/manual"
    pic = tmp_path / "screen.png"
    shot = Image.new("RGB", (900, 600), "navy")
    ImageDraw.Draw(shot).rectangle((620, 140, 840, 320), fill="orange")
    shot.save(pic)
    image = pic.read_bytes()
    assert client.put(endpoint, params={"url": site}, content=image).status_code == 403
    saved = client.put(endpoint, params={"url": site}, content=image, headers=ORIGIN)
    assert saved.status_code == 201
    manual = {**saved.json()["manual"], "focus_x": .8, "focus_y": .4}
    scene = Scene.model_validate({"id": "s1", "kind": "card", "text": "Inspect the new report.",
                                  "site": site, "plan": {"website_demo": {
                                      "manual": manual}}})
    import playwright.sync_api as pw
    monkeypatch.setattr(pw, "sync_playwright", lambda: pytest.fail("unexpected browser"))
    invalid = {**scene.model_dump(), "site": site + "/other"}
    assert client.post("/api/episodes", json=small_script(scenes=[invalid])).status_code == 422
    eid = client.post("/api/episodes", json=small_script(scenes=[scene.model_dump()])).json()["id"]
    approve(client, eid)
    jobs = drain(s)
    assert all(j["status"] == "done" for j in jobs), [(j["kind"], j["error"]) for j in jobs]
    assert client.get(f"/api/episodes/{eid}").json()["status"] == "ready"
    assert website_demo.asset_path(record.episode_dir(s, eid), scene).is_file()


def test_adjacent_card_slices_continue_the_same_camera_move(env, tmp_path):
    from streamstudio.episode.website_demo import card_timeline, overlay

    _, s, _, _ = env
    scene = Scene.model_validate({"id": "s1", "kind": "card", "site": "https://example.org",
                                  "text": "Inspect the graphic.", "plan": {"website_demo": {
                                      "focus_label": "Chart", "reveal_at": .80}}})
    second = scene.model_copy(update={"id": "s2"})
    tracks = card_timeline([scene, second], [1, 1])
    assert tracks == {"s1": (0, 20), "s2": (25, 20)}
    cues = mix.plan_cues([scene, second], [0, 1], [1, 1])
    assert [c["kind"] for c in cues] == ["navigate", "counter"]
    base = tmp_path / "base.mp4"
    card = tmp_path / "motion.mp4"
    make_clip(base)
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=400x240:rate=25:duration=1.44", "-c:v", "libx264", str(card)],
                   check=True)
    # Match the episode compositor's output geometry.
    wide = tmp_path / "wide.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(base), "-vf", "scale=1920:1080",
                    "-c:a", "copy", str(wide)], check=True)
    starts = []
    for sid, timing in tracks.items():
        out = tmp_path / f"{sid}.mp4"
        overlay(s, wide, card, scene.plan.website_demo, out, track=timing)
        starts.append(subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(out),
                      "-frames:v", "1", "-vf", "scale=160:90", "-f", "rawvideo", "-pix_fmt",
                      "rgb24", "-"]))
        assert mix._frame_count(s, out) == 25
    assert starts[0] != starts[1]
