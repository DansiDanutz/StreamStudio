"""Local transcripts of recorded takes (whisper.cpp): parse, job, API."""

import json
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from streamstudio.api.main import create_app
from streamstudio.core import db
from streamstudio.core.config import Settings
from streamstudio.core.transcribe import parse_whisper_json
from streamstudio.worker.main import run_one

RID = "rec_20261101-020000"

WHISPER_JSON = {
    "result": {"language": "en"},
    "transcription": [
        {
            "offsets": {"from": 0, "to": 2500},
            "text": " Hello there, friends.",
            "tokens": [
                {"text": "[_BEG_]", "offsets": {"from": 0, "to": 0}},
                {"text": " Hello", "offsets": {"from": 100, "to": 600}},
                {"text": " there", "offsets": {"from": 600, "to": 1000}},
                {"text": ",", "offsets": {"from": 1000, "to": 1050}},
                {"text": " friend", "offsets": {"from": 1100, "to": 1800}},
                {"text": "s.", "offsets": {"from": 1800, "to": 2400}},
                {"text": "[_TT_125]", "offsets": {"from": 2500, "to": 2500}},
            ],
        },
        {"offsets": {"from": 2500, "to": 4000}, "text": " Bye.", "tokens": []},
    ],
}


def test_parse_whisper_json_into_segments_and_words():
    t = parse_whisper_json(WHISPER_JSON)
    assert t["language"] == "en"
    assert t["text"] == "Hello there, friends. Bye."
    assert t["segments"] == [
        {"start_ms": 0, "end_ms": 2500, "text": "Hello there, friends."},
        {"start_ms": 2500, "end_ms": 4000, "text": "Bye."},
    ]
    # sub-word tokens join into words; special tokens are dropped
    assert t["words"] == [
        {"start_ms": 100, "end_ms": 600, "word": "Hello"},
        {"start_ms": 600, "end_ms": 1050, "word": "there,"},
        {"start_ms": 1100, "end_ms": 2400, "word": "friends."},
    ]


def _fake_tools(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Stand-ins for ffmpeg and whisper-cli that write the files the real ones would."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    ffmpeg = bin_dir / "ffmpeg"
    # only "writes" the WAV: probes like `ffmpeg -encoders` must not leave files behind
    ffmpeg.write_text(
        '#!/bin/sh\nfor a; do last="$a"; done\ncase "$last" in *.wav) : > "$last";; esac\n'
    )
    whisper = bin_dir / "whisper-cli"
    whisper.write_text(
        "#!/bin/sh\n"
        'while [ $# -gt 0 ]; do [ "$1" = "-of" ] && out="$2"; shift; done\n'
        f"cat > \"$out.json\" <<'EOF'\n{json.dumps(WHISPER_JSON)}\nEOF\n"
        'printf "1\\n00:00:00,000 --> 00:00:02,500\\n Hello there, friends.\\n\\n" > "$out.srt"\n'
        'echo run >> "$out.calls"\n'
    )
    for f in (ffmpeg, whisper):
        f.chmod(f.stat().st_mode | stat.S_IEXEC)
    model = tmp_path / "ggml-test.bin"
    model.write_bytes(b"model")
    return ffmpeg, whisper, model


@pytest.fixture
def env(tmp_path):
    ffmpeg, whisper, model = _fake_tools(tmp_path)
    s = Settings(
        data_dir=tmp_path / "data", import_roots=[], ffmpeg_bin=str(ffmpeg),
        whisper_bin=str(whisper), whisper_model=model,
    )  # fmt: skip
    client = TestClient(create_app(s))
    (s.recordings_dir / f"{RID}.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
    return client, s


def test_transcript_job_writes_json_and_srt_and_is_idempotent(env):
    client, s = env
    r = client.post(f"/api/recordings/{RID}/transcribe")
    assert r.status_code == 202, r.text
    c = db.connect(s.db_path)
    assert run_one(c, s, "w1")
    job = client.get(f"/api/jobs/{r.json()['job_id']}").json()
    assert job["status"] == "done", job
    t = client.get(f"/api/recordings/{RID}/transcript").json()
    assert t["text"] == "Hello there, friends. Bye." and t["language"] == "en"
    srt = client.get(f"/api/recordings/{RID}.srt")
    assert srt.status_code == 200 and "Hello there, friends." in srt.text
    # a second request does no work: the transcript is newer than the MP4
    r2 = client.post(f"/api/recordings/{RID}/transcribe")
    assert run_one(c, s, "w1")
    assert client.get(f"/api/jobs/{r2.json()['job_id']}").json()["result"]["skipped"] is True
    calls = list(s.recordings_dir.glob("*.calls"))
    assert not calls or calls[0].read_text().count("run") == 1


def test_transcribe_requests_are_deduplicated_while_queued(env):
    client, _ = env
    first = client.post(f"/api/recordings/{RID}/transcribe").json()["job_id"]
    second = client.post(f"/api/recordings/{RID}/transcribe").json()["job_id"]
    assert first == second


def test_transcribe_needs_a_finished_mp4(env):
    client, _ = env
    assert client.post("/api/recordings/rec_20261101-030000/transcribe").status_code == 404
    assert client.get(f"/api/recordings/{RID}/transcript").status_code == 404
    assert client.get(f"/api/recordings/{RID}.srt").status_code == 404
    assert client.post("/api/recordings/..%2Fx/transcribe").status_code in (404, 405, 422)


def test_transcribe_reports_missing_whisper(tmp_path):
    s = Settings(data_dir=tmp_path / "d", import_roots=[], whisper_bin="no-such-whisper")
    client = TestClient(create_app(s))
    (s.recordings_dir / f"{RID}.mp4").write_bytes(b"x")
    r = client.post(f"/api/recordings/{RID}/transcribe")
    assert r.status_code == 503 and "whisper" in r.json()["detail"]


def test_health_reports_whisper(env):
    client, _ = env
    tools = client.get("/api/health").json()["tools"]
    assert tools["whisper"]["bin"] and tools["whisper"]["model"].endswith("ggml-test.bin")


REAL_MODEL = Path.home() / ".local/share/whisper-models/ggml-base.bin"
SAMPLE = next(Path("/opt/homebrew/Cellar").glob("whisper.cpp/*/share/whisper.cpp/jfk.wav"), None) \
    if Path("/opt/homebrew/Cellar").exists() else None


@pytest.mark.skipif(
    not (shutil.which("whisper-cli") and shutil.which("ffmpeg") and REAL_MODEL.exists() and SAMPLE),
    reason="needs whisper-cli, ffmpeg, the base model and the bundled sample",
)
def test_real_whisper_transcribes_a_take(tmp_path):
    s = Settings(data_dir=tmp_path / "d", import_roots=[], whisper_model=REAL_MODEL)
    client = TestClient(create_app(s))
    mp4 = s.recordings_dir / f"{RID}.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=320x180:r=30:d=11",
         "-i", str(SAMPLE), "-c:v", "libx264", "-c:a", "aac", "-shortest", str(mp4)],
        check=True,
    )  # fmt: skip
    client.post(f"/api/recordings/{RID}/transcribe")
    assert run_one(db.connect(s.db_path), s, "w1")
    t = client.get(f"/api/recordings/{RID}/transcript").json()
    assert "fellow Americans" in t["text"]
    assert t["words"] and t["words"][0]["start_ms"] < 1000
