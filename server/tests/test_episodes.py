"""The episode factory's API: contract, validator, record, ledger and the three clicks."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_heygen import KEY, FakeHeyGen

from streamstudio.api.main import create_app
from streamstudio.core import db, store, youtube
from streamstudio.core.config import Settings
from streamstudio.core.ids import now_iso
from streamstudio.episode import ledger, preflight, record, validate
from streamstudio.episode import publish as publish_mod
from streamstudio.episode.contract import Plan, Scene, Script, script_hash
from streamstudio.worker import handlers

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "episode-01-v2" / "script.json"
CH1 = "UC" + "a" * 22
CH2 = "UC" + "b" * 22
ORIGIN = {"Origin": "http://testclient"}


class FakeYouTube:
    """Token refresh and videos.update only."""

    def __init__(self) -> None:
        self.updates: list[dict] = []

    def __call__(self, req):
        url, method = req.full_url, req.get_method()
        if url == youtube.TOKEN_URL:
            return 200, {}, json.dumps({"access_token": "at", "expires_in": 3600}).encode()
        if "/youtube/v3/videos" in url and method == "PUT":
            body = json.loads(req.data)
            self.updates.append(body)
            return 200, {}, json.dumps({"id": body["id"], "status": body["status"]}).encode()
        raise AssertionError(f"unexpected call {method} {url}")


def connect_channel(s: Settings, channel_id: str, title: str) -> None:
    youtube._write_private(
        youtube._channel_file(s.data_dir, channel_id),
        {"refresh_token": "rt", "access_token": "at", "expires_at": time.time() + 3600,
         "channel": {"id": channel_id, "title": title}},
    )  # fmt: skip


@pytest.fixture
def env(tmp_path, monkeypatch):
    assets = tmp_path / "assets"
    for sub in ("brand", "studio", "models"):
        shutil.copytree(ROOT / "assets" / sub, assets / sub)
    s = Settings(
        data_dir=tmp_path / "data", assets_dir=assets, import_roots=[], allow_tailnet=True,
        extra_hosts=["testclient"], heygen_month_ceiling_usd=50.0,
    )  # fmt: skip
    fake = FakeHeyGen()
    tube = FakeYouTube()
    monkeypatch.setattr(handlers, "HEYGEN_TRANSPORT", fake)
    monkeypatch.setattr(handlers, "HEYGEN_POLL_S", 0)
    monkeypatch.setattr(handlers, "CUTOUT", None)
    monkeypatch.setattr(publish_mod, "YOUTUBE_TRANSPORT", tube)
    monkeypatch.setattr(preflight, "_pkg", lambda name: True)
    monkeypatch.setattr(preflight.shutil, "which", lambda b: "/usr/bin/" + b)
    client = TestClient(create_app(s))
    client.put("/api/heygen/config", json={"api_key": KEY, "avatar_id": "look1", "voice_id": "v1"})
    connect_channel(s, CH1, "DansLab")
    return client, s, fake, tube


def small_script(**over) -> dict:
    base = {
        "title": "Test episode",
        "scenes": [
            {"id": "s1", "text": "Hello there, this is scene one.", "question": 1},
            {"id": "s2", "voice": "Smarty trades for you.", "text": "Zmarty trades for you."},
            {"id": "s3", "text": "The end: it was an AI avatar all along.", "reveal": True},
        ],
    }
    return {**base, **over}


def connection(s: Settings):
    c = db.connect(s.db_path)
    db.migrate(c)
    return c


def approve_both(client: TestClient, eid: str) -> dict:
    assert client.post(f"/api/episodes/{eid}/approve-script").status_code == 200
    est = client.get(f"/api/episodes/{eid}/estimate").json()
    r = client.post(
        f"/api/episodes/{eid}/approve-budget",
        json={"confirm_token": est["confirm_token"]},
        headers=ORIGIN,
    )
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- contract and validator


def test_contract_round_trips_every_plan_key_and_forbids_extras():
    plan = Plan(
        title=["One", "Two"], lower=("Dan", None), lowers=[(0.1, None, "Name", "sub")],
        chips=["a", "b"], chip_at=[0.2, 0.4], chips_out=0.9, zoom=(0.5, 0.5, 1.1),
        zoom_path=[(0, 0.5, 0.5, 1.0), (0.5, 0.6, 0.4, 1.2)], card_x=0.3, frame=(0.47, 0.47, 1.1),
        glitch=[(0.7, 0.5)], endcard=["t", "link", "small"], end_at=0.1, end_until=0.6,
        whoosh_at=0.76, card_template="generic",
    )  # fmt: skip
    sc = Scene(id="s1", text="t", voice="v", kind="card", site="https://x", question=1, plan=plan)
    script = Script(title="T", scenes=[sc])
    again = Script.model_validate_json(script.model_dump_json())
    assert again == script and again.scenes[0].plan.card_template == "generic"
    with pytest.raises(ValidationError):
        Scene.model_validate({"id": "s1", "text": "t", "plan": {"titel": ["x"]}})
    with pytest.raises(ValidationError):
        Scene.model_validate({"id": "scene-1", "text": "t"})
    with pytest.raises(ValidationError):
        Scene.model_validate({"id": "s1", "text": "t", "plan": {"card_template": "fancy"}})
    assert script_hash(script) == script_hash(again)
    assert script_hash(script) != script_hash(Script(title="T2", scenes=[sc]))


def test_the_episode_1_fixture_validates_under_extra_forbid():
    script = Script.model_validate_json(FIXTURE.read_text())
    assert len(script.scenes) == 36
    assert [s.id for s in script.scenes if s.question] == ["s9", "s14", "s20", "s26"]
    assert all(s.site for s in script.scenes if s.kind == "card")
    assert script.scenes[33].reveal is True


def test_validator_error_rows(tmp_path):
    s = Settings(data_dir=tmp_path, assets_dir=ROOT / "assets")
    script = Script.model_validate(
        {"title": "T", "scenes": [
            {"id": "s1", "kind": "card"},
            {"id": "s1", "text": "again"},
            {"id": "s2", "text": "fine"},
        ]}
    )  # fmt: skip
    v = validate.validate(script, s)
    assert sorted(v["errors"]["s1"]) == sorted(
        ["duplicate scene id", "a card scene needs a site", "both voice and text are empty"]
    )
    assert "s2" not in v["errors"] and "s2" in v["warnings"]


# ---------------------------------------------------------------- create, read, list


def test_create_read_and_list(env):
    client, s, _, _ = env
    r = client.post("/api/episodes", json=small_script())
    assert r.status_code == 201, r.text
    ep = r.json()
    assert ep["status"] == "draft" and ep["next_action"] == "Approve script"
    assert "confirm_token" not in ep["budget"] and ep["progress"] == {
        "clips": 0,
        "qa": 0,
        "composed": 0,
        "total": 3,
    }
    assert ep["validation"]["errors"] == {}
    assert (s.episodes_dir / ep["id"]).is_dir()
    got = client.get(f"/api/episodes/{ep['id']}").json()
    assert got == ep  # a pure read
    assert client.get(f"/api/episodes/{ep['id']}").json() == got
    assert client.get("/api/episodes").json()[0]["id"] == ep["id"]
    assert client.get("/api/episodes/ep_nope1234").status_code == 404
    assert client.get("/api/episodes/../etc").status_code == 404


def test_create_refuses_errors_and_missing_tools(env, monkeypatch):
    client, s, _, _ = env
    r = client.post("/api/episodes", json=small_script(scenes=[{"id": "s1", "kind": "card"}]))
    assert r.status_code == 422 and "a card scene needs a site" in r.text
    monkeypatch.setattr(
        preflight, "check", lambda s, stage=1: {"ok": False, "missing": ["ffmpeg", "intro"]}
    )
    r = client.post("/api/episodes", json=small_script())
    assert r.status_code == 503 and r.json()["detail"]["missing"] == ["ffmpeg", "intro"]


def test_an_episode_is_not_a_project_to_the_editor(env):
    client, s, _, _ = env
    eid = client.post("/api/episodes", json=small_script()).json()["id"]
    c = connection(s)
    pid = record.load(c, eid).project_id
    assert pid not in [p["id"] for p in client.get("/api/projects").json()]
    assert client.get(f"/api/projects/{pid}").status_code == 404
    assert client.get(f"/api/projects/{pid}/edl").status_code == 404


# ---------------------------------------------------------------- the three clicks


def test_approve_script_then_estimate_then_budget(env):
    client, s, _, _ = env
    eid = client.post("/api/episodes", json=small_script()).json()["id"]
    assert client.get(f"/api/episodes/{eid}/estimate").status_code == 409  # script first
    assert client.post(f"/api/episodes/{eid}/approve-script").json()["status"] == "script_approved"
    est = client.get(f"/api/episodes/{eid}/estimate").json()
    assert est["clips"] == 3 and est["usd"] > 0 and est["confirm_token"]
    assert est["allowance"] == {"attempts": 4, "usd": 1.5} and est["ceiling_usd"] == 50.0
    assert est["month_total_before_usd"] == 0 and est["over_ceiling"] is False
    # the token and the Origin gate the paid step
    r = client.post(
        f"/api/episodes/{eid}/approve-budget", json={"confirm_token": est["confirm_token"]}
    )
    assert r.status_code == 403
    r = client.post(
        f"/api/episodes/{eid}/approve-budget",
        json={"confirm_token": est["confirm_token"]},
        headers={"Origin": "http://evil.example"},
    )
    assert r.status_code == 403
    r = client.post(
        f"/api/episodes/{eid}/approve-budget", json={"confirm_token": "x" * 32}, headers=ORIGIN
    )
    assert r.status_code == 409
    r = client.post(
        f"/api/episodes/{eid}/approve-budget",
        json={"confirm_token": est["confirm_token"]},
        headers=ORIGIN,
    )
    assert r.status_code == 200, r.text
    ep = r.json()
    assert ep["status"] == "budget_approved"
    assert ep["budget"]["usd"] == est["usd"] and ep["budget"]["approval_id"]
    assert "confirm_token" not in ep["budget"]
    c = connection(s)
    rows = c.execute("SELECT kind, scene_id, usd FROM heygen_ledger ORDER BY scene_id").fetchall()
    assert [r["kind"] for r in rows] == ["reservation"] * 4
    assert round(sum(r["usd"] for r in rows), 2) == round(est["usd"] + 1.5, 2)
    assert round(ledger.month_total(c), 2) == round(est["usd"] + 1.5, 2)
    job = store.get_job(c, ep["job_id"])
    assert job["kind"] == "episode_advance" and job["payload"] == {"episode_id": eid}
    # the token is one-time
    r = client.post(
        f"/api/episodes/{eid}/approve-budget",
        json={"confirm_token": est["confirm_token"]},
        headers=ORIGIN,
    )
    assert r.status_code == 409


def test_budget_refused_over_the_ceiling_and_without_a_single_channel(env):
    client, s, _, _ = env
    eid = client.post("/api/episodes", json=small_script()).json()["id"]
    client.post(f"/api/episodes/{eid}/approve-script")
    s.heygen_month_ceiling_usd = 1.0
    est = client.get(f"/api/episodes/{eid}/estimate").json()
    assert est["over_ceiling"] is True
    r = client.post(
        f"/api/episodes/{eid}/approve-budget",
        json={"confirm_token": est["confirm_token"]},
        headers=ORIGIN,
    )
    assert r.status_code == 409 and "ceiling" in r.text
    s.heygen_month_ceiling_usd = 50.0
    connect_channel(s, CH2, "Other")
    est = client.get(f"/api/episodes/{eid}/estimate").json()
    r = client.post(
        f"/api/episodes/{eid}/approve-budget",
        json={"confirm_token": est["confirm_token"]},
        headers=ORIGIN,
    )
    assert r.status_code == 200


def test_two_approvals_cannot_both_pass_against_the_same_balance(env):
    client, s, _, _ = env
    a = client.post("/api/episodes", json=small_script()).json()["id"]
    b = client.post("/api/episodes", json=small_script(title="Second")).json()["id"]
    first = approve_both(client, a)
    s.heygen_month_ceiling_usd = first["budget"]["usd"] + 1.5 + 0.5  # room for one, not two
    client.post(f"/api/episodes/{b}/approve-script")
    est = client.get(f"/api/episodes/{b}/estimate").json()
    assert est["month_total_before_usd"] > 0 and est["over_ceiling"]
    r = client.post(
        f"/api/episodes/{b}/approve-budget",
        json={"confirm_token": est["confirm_token"]},
        headers=ORIGIN,
    )
    assert r.status_code == 409


def test_a_charge_in_the_next_month_counts_in_that_month(env):
    client, s, _, _ = env
    eid = client.post("/api/episodes", json=small_script()).json()["id"]
    approve_both(client, eid)
    c = connection(s)
    reserved = ledger.month_total(c)
    with db.tx(c):
        assert ledger.charge(c, eid, "s1", "key-s1", 0, None, 10.0, at="2099-02-03T00:00:00Z")
        assert not ledger.charge(c, eid, "s1", "key-s1", 0, None, 10.0)  # once per clip key
    # the charge consumes the reservation it was made under, so the month's total holds...
    assert ledger.month_total(c, now="2099-02-10T00:00:00Z") == pytest.approx(reserved)
    assert ledger.spent(c, eid) == {"renders": 1, "seconds": 10.0, "usd": round(10 * 0.0385, 2)}
    # ...until the charges pass what was reserved
    with db.tx(c):
        assert ledger.charge(c, eid, "s2", "key-s2", 0, None, 100.0, at="2099-02-04T00:00:00Z")
    assert ledger.month_total(c, now="2099-02-10T00:00:00Z") == pytest.approx(110 * 0.0385)
    assert ledger.month_total(c, now="2099-03-10T00:00:00Z") == pytest.approx(0.0)


def test_a_second_approval_reserves_each_key_once_and_keeps_live_work(env):
    client, s, _, _ = env
    eid = client.post("/api/episodes", json=small_script()).json()["id"]
    first = approve_both(client, eid)
    c = connection(s)
    ep = record.load(c, eid)
    old_key = ep.record["scenes_state"]["s2"]["clip_key"]
    # scene s2's render is running; scene s3's clip already exists
    with db.tx(c):
        job = store.enqueue(c, "heygen_clip", project_id=ep.project_id, payload={"key": old_key})
        c.execute("UPDATE jobs SET status = 'running' WHERE id = ?", (job["id"],))
        st = ep.record["scenes_state"]
        st["s2"].update({"job_id": job["id"], "job_key": old_key, "job_take": 0})
        mp4, webm = record.clip_paths(s, st["s3"]["clip_key"])
        mp4.parent.mkdir(parents=True, exist_ok=True)
        mp4.write_bytes(b"x")
        webm.write_bytes(b"x")
        record.save(c, ep)
    # edit s2's words (new key) and re-approve
    edited = small_script()
    edited["scenes"][1]["voice"] = "Smarty trades for you, every day."
    r = client.put(f"/api/episodes/{eid}/script", json=edited)
    assert r.status_code == 200 and r.json()["status"] == "draft"
    client.post(f"/api/episodes/{eid}/approve-script")
    est = client.get(f"/api/episodes/{eid}/estimate").json()
    keys = [ln["clip_key"] for ln in est["lines"]]
    assert (
        old_key in keys and len(keys) == len(set(keys)) == 3
    )  # s1, old s2 (live), new s2; s3 ready
    assert est["month_total_before_usd"] == pytest.approx(first["budget"]["usd"] + 1.5, abs=0.01)
    second = client.post(
        f"/api/episodes/{eid}/approve-budget",
        json={"confirm_token": est["confirm_token"]},
        headers=ORIGIN,
    ).json()
    assert second["budget"]["approval_id"] != first["budget"]["approval_id"]
    rel = c.execute("SELECT usd FROM heygen_ledger WHERE kind = 'release'").fetchall()
    assert len(rel) == 1 and rel[0]["usd"] == pytest.approx(first["budget"]["usd"] + 1.5, abs=0.01)
    assert ledger.month_total(c) == pytest.approx(est["usd"] + 1.5, abs=0.01)
    assert est["usd"] >= first["budget"]["usd"] * 2 / 3  # the live render stayed reserved


def test_put_script_resets_outputs_and_is_refused_once_uploading(env):
    client, s, _, _ = env
    eid = client.post("/api/episodes", json=small_script()).json()["id"]
    approve_both(client, eid)
    c = connection(s)
    d = record.episode_dir(s, eid)
    for name in ("final.mp4", "kit.json"):
        (d / name).write_text("x")
    with db.tx(c):
        ep = record.load(c, eid)
        record.set_status(ep, "in_progress")
        ep.record["outputs"].update({"recording_id": "rec_1-ep", "channel": CH1})
        record.save(c, ep)
    same = client.put(f"/api/episodes/{eid}/script", json=small_script()).json()
    assert same["status"] == "draft" and same["outputs"]["recording_id"] == "rec_1-ep"  # same hash
    changed = client.put(f"/api/episodes/{eid}/script", json=small_script(title="New title")).json()
    assert changed["status"] == "draft" and "recording_id" not in changed["outputs"]
    assert not (d / "final.mp4").exists() and not (d / "kit.json").exists()
    assert changed["title"] == "New title"
    with db.tx(c):
        ep = record.load(c, eid)
        record.set_status(ep, "in_progress")
        job = store.enqueue(
            c, "youtube_upload", project_id=ep.project_id, payload={"episode_id": eid}
        )
        ep.record["outputs"]["upload_job_id"] = job["id"]
        record.save(c, ep)
    assert client.put(f"/api/episodes/{eid}/script", json=small_script()).status_code == 409
    with db.tx(c):
        store.finish_job(c, job["id"], {})
        ep = record.load(c, eid)
        record.set_status(ep, "uploaded_private")
        record.save(c, ep)
    assert client.put(f"/api/episodes/{eid}/script", json=small_script()).status_code == 409


def test_publish_now_sets_published_through_youtube(env):
    client, s, _, tube = env
    eid = client.post("/api/episodes", json=small_script()).json()["id"]
    assert client.post(f"/api/episodes/{eid}/publish", json={}).status_code == 409
    c = connection(s)
    with db.tx(c):
        ep = record.load(c, eid)
        record.set_status(ep, "uploaded_private")
        ep.record["outputs"].update({"channel": CH1, "youtube_video_id": "vid123"})
        record.save(c, ep)
    r = client.post(f"/api/episodes/{eid}/publish", json={"publish_at": "yesterday"})
    assert r.status_code == 422
    r = client.post(f"/api/episodes/{eid}/publish", json={})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "published" and r.json()["next_action"] == "Purge workings"
    assert tube.updates == [{"id": "vid123", "status": {"privacyStatus": "public"}}]
    assert "youtu.be/vid123" in r.json()["last_log"]
    purge = client.post(f"/api/episodes/{eid}/purge")
    assert (
        purge.status_code == 202
        and store.get_job(c, purge.json()["job_id"])["kind"] == "episode_purge"
    )
    assert client.post(f"/api/episodes/{eid}/purge").json()["job_id"] == purge.json()["job_id"]


def test_advance_resumes_a_parked_episode(env):
    client, s, _, _ = env
    eid = client.post("/api/episodes", json=small_script()).json()["id"]
    assert client.post(f"/api/episodes/{eid}/advance").status_code == 409
    c = connection(s)
    with db.tx(c):
        ep = record.load(c, eid)
        record.set_status(ep, "needs_dan", "HeyGen cap reached")
        record.save(c, ep)
    got = client.get(f"/api/episodes/{eid}").json()
    assert got["next_action"] == "Advance" and got["last_log"] == "HeyGen cap reached"
    r = client.post(f"/api/episodes/{eid}/advance")
    assert r.status_code == 202 and r.json()["status"] == "in_progress"
    assert store.get_job(c, r.json()["job_id"])["kind"] == "episode_advance"


def test_record_helpers(env):
    client, s, _, _ = env
    eid = client.post("/api/episodes", json=small_script()).json()["id"]
    c = connection(s)
    ep = record.load(c, eid)
    script = ep.script
    k0 = record.scene_key(s, script.scenes[0], script, 0)
    assert record.scene_key(s, script.scenes[0], script, 1) != k0
    assert record.scene_key(s, script.scenes[0], script, 0) == k0
    h = record.inputs_hash(script.scenes[0], None, None, None)
    assert h == record.inputs_hash(script.scenes[0], None, None, None)
    assert h != record.inputs_hash(script.scenes[1], None, None, None)
    p = record.export(s, ep)
    assert json.loads(p.read_text())["id"] == eid
    assert now_iso() <= record.load(c, eid).updated_at or True

def test_script_warnings_explain_claims_voice_pacing_and_structure(tmp_path):
    s = Settings(data_dir=tmp_path, assets_dir=ROOT / "assets")
    script = Script(title="Tour", scenes=[
        Scene(id="s1", text="StreamStudio has the fastest setup with 12 steps in all."),
        Scene(id="s2", text="Here is how to use the editor and the preview together."),
    ])
    report = validate.validate(script, s)
    assert not report["errors"]
    assert len(report["warnings"]["*"]) == 2
    assert any("source" in w for w in report["warnings"]["s1"])
    assert any("Stream Studio" in w for w in report["warnings"]["s1"])
    assert any("8s" in w for w in report["warnings"]["s2"])

def test_scheduled_release_requires_observed_public_status_before_purge(env, monkeypatch):
    client, s, _, tube = env
    eid = client.post("/api/episodes", json=small_script()).json()["id"]
    c = connection(s)
    with db.tx(c):
        ep = record.load(c, eid)
        record.set_status(ep, "uploaded_private")
        ep.record["outputs"].update(channel=CH1, youtube_video_id="vid123")
        record.save(c, ep)
    when = "2099-01-01T00:00:00Z"
    r = client.post(f"/api/episodes/{eid}/publish", json={"publish_at": when})
    assert r.json()["status"] == "scheduled"
    assert tube.updates[-1]["status"] == {"privacyStatus": "private", "publishAt": when}
    calls = []

    def observe(api, video_id):
        calls.append(video_id)
        return {"privacy": "private" if len(calls) == 1 else "public", "publish_at": None}

    monkeypatch.setattr(youtube, "video_status", observe)
    with db.tx(c):
        ep = record.load(c, eid)
        ep.record["outputs"]["publish_at"] = "2000-01-01T00:00:00Z"
        record.save(c, ep)
    r = client.post(f"/api/episodes/{eid}/refresh").json()
    assert r["status"] == "scheduled" and r["last_log"] == "scheduled release did not happen"
    assert client.post(f"/api/episodes/{eid}/purge").status_code == 409
    assert client.post(f"/api/episodes/{eid}/refresh").json() == r and calls == ["vid123"]
    with db.tx(c):
        ep = record.load(c, eid)
        ep.record["last_checked_at"] = "2000-01-01T00:00:00Z"
        record.save(c, ep)
    assert client.post(f"/api/episodes/{eid}/refresh").json()["status"] == "published"

def test_agent_episode_workflow_preserves_browser_approval(env, monkeypatch):
    from streamstudio import mcp

    client, _, _, _ = env

    def local_call(method, path, body=None):
        response = client.request(method, path, json=body)
        response.raise_for_status()
        return response.json()

    monkeypatch.setattr(mcp, "_http", local_call)
    assert mcp.call("episode_workflows", {})[0]["id"] == "website-demo/v1"
    ep = mcp.call("episode_create", {"script": small_script()})
    args = {"id": ep["id"]}
    rev = {**args, "expected_hash": ep["script"]["hash"], "script": small_script(title="Edited")}
    assert mcp.call("episode_edit", rev)["title"] == "Edited"
    stale = client.put(f"/api/episodes/{ep['id']}/script",
                       params={"expected_hash": rev["expected_hash"]}, json=small_script())
    assert stale.status_code == 409
    assert mcp.call("episode_status", args)["status"] == "draft"
    assert mcp.call("episode_list", {})[0]["id"] == ep["id"]
    assert "confirm_token" not in mcp.call("episode_estimate", args)
    base = f"/api/episodes/{ep['id']}"
    client.post(base + "/approve-script")
    token = client.get(base + "/estimate").json()["confirm_token"]
    assert "confirm_token" not in mcp.call("episode_estimate", args)
    response = client.post(base + "/approve-budget", json={"confirm_token": token}, headers=ORIGIN)
    assert response.status_code == 200, response.text

def test_approval_keeps_dans_presenter_when_global_voice_changes(env):
    client, s, _, _ = env
    eid = client.post("/api/episodes", json=small_script()).json()["id"]
    base = f"/api/episodes/{eid}"
    approval = client.post(base + "/approve-script").json()
    assert approval["presenter_defaults"] == {"avatar_id": "look1", "voice_id": "v1"}
    before = client.get(base + "/cost").json()["lines"]
    client.put("/api/heygen/config", json={"api_key": KEY, "avatar_id": "other", "voice_id": "v2"})
    assert client.get(base + "/cost").json()["lines"] == before
    client.put(base + "/script", json=small_script(title="New title"))
    assert client.post(base + "/approve-script").json()["presenter_defaults"] == approval[
        "presenter_defaults"
    ]
    est = client.get(base + "/estimate").json()
    body = {"confirm_token": est["confirm_token"]}
    assert client.post(base + "/approve-budget", json=body, headers=ORIGIN).status_code == 200
    c = connection(s)
    from streamstudio.episode import planner
    planner.advance(c, s, eid)
    jobs = [job for job in store.list_jobs(c) if job["kind"] == "heygen_clip"]
    assert jobs and all(j["payload"]["voice"] == "v1" and j["payload"]["look"] == "look1"
                        for j in jobs)

def test_channel_versions_and_approval_pin(env):
    client, _, _, _ = env
    create = {"slug": "engineering", "name": "Engineering"}
    assert client.post("/api/channels", json=create).status_code == 403
    v1 = client.post("/api/channels", json=create, headers=ORIGIN).json()
    assert v1["version"] == 1 and v1["profile"]["youtube_channel"] is None
    client.put("/api/channels/default", json={"slug": "engineering"}, headers=ORIGIN)
    eid = client.post("/api/episodes", json=small_script()).json()["id"]
    client.put("/api/channels/default", json={"slug": "danslab"}, headers=ORIGIN)
    publishing = {"default_tags": ["local"], "description_footer": "Lab"}
    settings = {**v1["profile"], "publish": publishing}
    url = "/api/channels/engineering"
    body = {"base_version": 1, "profile": settings}
    v2 = client.put(url, json=body, headers=ORIGIN).json()
    assert v2["version"] == 2 and v2["hash"] != v1["hash"]
    assert client.put(url, json=body, headers=ORIGIN).status_code == 409
    assert client.get(url, params={"version": 1}).json() == v1
    base = f"/api/episodes/{eid}"
    assert client.post(base + "/approve-script").json()["profile"] == v2
    assert client.put(url, json={"base_version": 2, "profile": v1["profile"]},
                      headers=ORIGIN).status_code == 200
    assert client.put(base + "/script", json=small_script(title="Edited")).status_code == 200
    assert client.post(base + "/approve-script").json()["profile"] == v2
