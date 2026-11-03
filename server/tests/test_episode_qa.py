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
