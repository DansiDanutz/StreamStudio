from streamstudio.episode import qa


def test_first_pass_reference_identifies_framing_and_lip_outliers():
    normal = {"face": [100, 20, 80, 80], "lip_ratio": 1.0, "status": "ok", "issues": []}
    shifted = {**normal, "face": [124, 20, 80, 80], "lip_ratio": .45}
    ref = qa.cohort_reference([normal, normal, shifted])
    assert ref == {"face": normal["face"], "lip_ratio": 1.0}
    verdict, issues = qa.compare(shifted, ref)
    assert verdict == "FAIL" and len(issues) == 2
    assert shifted["issues"] == []
    assert qa.compare({**normal, "lip_ratio": 0}, ref)[0] == "LOOK"
    assert qa.compare(normal, ref) == ("ok", [])
    assert qa.compare({**normal, "face": [100, 20, 95, 95]}, ref)[0] == "FAIL"
    assert qa.cohort_reference([{"face": None}]) == {"face": None, "lip_ratio": None}

def test_transcript_review_normalizes_names_and_scopes_repeat_failures():
    names = [{"screen": "StreamStudio", "voice": "Stream Studio"}]
    expected = "StreamStudio grew 3.5%."
    heard = "Stream Studio grew three point five percent."
    assert qa.word_error(qa.spoken_tokens(expected, names), qa.spoken_tokens(heard, names)) == 0
    for first, verdict in ((None, "LOOK"), ("different line", "LOOK"), (heard, "FAIL")):
        report = {"status": "ok", "issues": []}
        qa.review_speech(report, expected, "different line", first, names)
        assert report["status"] == verdict and report["word_error_rate"] > .25


def test_transcript_retry_follows_whisper_availability(monkeypatch):
    status = {"bin": None, "model": None}
    monkeypatch.setattr(qa.transcribe, "whisper_status", lambda settings: status)
    report = {"transcript_available": False, "whisper_status": status.copy()}
    assert qa.reusable_report(report, None)
    status.update(bin="whisper-cli", model="dan-local.bin")
    assert not qa.reusable_report(report, None)
    assert not qa.reusable_report({"transcript_available": False}, None)
    assert qa.reusable_report({**report, "whisper_status": status.copy()}, None)
    assert qa.reusable_report({"transcript_available": True}, None)
