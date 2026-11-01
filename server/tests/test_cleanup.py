"""Cut suggestions from a transcript: silences and fillers."""

import json

from fastapi.testclient import TestClient

from streamstudio.api.main import create_app
from streamstudio.core.cleanup import saved_ms, suggest_cuts
from streamstudio.core.config import Settings

W = lambda s, e, w: {"start_ms": s, "end_ms": e, "word": w}  # noqa: E731


def test_long_silence_is_trimmed_not_removed():
    cuts = suggest_cuts([W(0, 500, "Hello"), W(2500, 3000, "world")], silence_ms=700, keep_ms=250)
    assert cuts == [{"start_ms": 625, "end_ms": 2375, "kind": "silence", "text": ""}]


def test_short_gap_is_kept():
    assert suggest_cuts([W(0, 500, "a"), W(900, 1200, "b")]) == []


def test_fillers_en_and_ro_with_punctuation():
    words = [W(0, 300, "So,"), W(300, 600, "Um,"), W(600, 900, "ăă"), W(900, 1200, "yes")]
    cuts = suggest_cuts(words)
    assert cuts == [{"start_ms": 300, "end_ms": 900, "kind": "filler", "text": "Um, ăă"}]
    assert suggest_cuts(words, langs=("en",))[0]["end_ms"] == 600
    assert suggest_cuts(words, fillers=False) == []


def test_filler_next_to_silence_merges_into_one_cut():
    words = [W(0, 500, "ok"), W(2000, 2300, "uh"), W(2300, 2800, "go")]
    cuts = suggest_cuts(words, silence_ms=700, keep_ms=0)
    assert len(cuts) == 1 and cuts[0]["kind"] == "mixed"
    assert saved_ms(cuts) == 2300 - 500


def test_cuts_endpoint(tmp_path):
    s = Settings(data_dir=tmp_path)
    s.recordings_dir.mkdir(parents=True)
    rid = "rec_20261101-020000"
    words = [W(0, 500, "Hi"), W(600, 900, "uh"), W(900, 1200, "there")]
    (s.recordings_dir / f"{rid}.transcript.json").write_text(json.dumps({"words": words}))
    c = TestClient(create_app(s), base_url="http://127.0.0.1:8787")
    r = c.get(f"/api/recordings/{rid}/cuts")
    assert r.status_code == 200 and r.json()["saved_ms"] == 300
    assert c.get("/api/recordings/rec_20261101-020001/cuts").status_code == 404
    assert c.get("/api/recordings/bad/cuts").status_code == 422
