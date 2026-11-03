import pytest

from streamstudio.core.config import Settings
from streamstudio.episode import validate, website_demo
from streamstudio.episode.contract import Scene, Script


def test_website_card_direction_reuses_capture(tmp_path):
    scene = Scene.model_validate({
        "id": "s10", "kind": "card", "site": "https://nervixpay.live",
        "text": "See the product QR code.",
        "plan": {"website_demo": {"focus_label": "Scannable NervixPay product preview"}},
    })
    original = website_demo.asset_path(tmp_path, scene)
    revised = scene.model_copy(deep=True)
    revised.plan.website_demo.side = "left"
    revised.plan.website_demo.reveal_at = .55
    assert website_demo.asset_path(tmp_path, revised) == original
    revised.plan.website_demo.focus_label = "Another feature"
    assert website_demo.asset_path(tmp_path, revised) != original
    s = Settings(capture_allowlist=[{"host": "nervixpay.live", "mode": "auto"}])
    script = Script(title="Checkout", scenes=[scene])
    assert not validate.validate(script, s)["errors"]
    for url in ("https://other.test", "http://nervixpay.live", "https://nervixpay.live:bad"):
        scene.site = url
        assert validate.validate(script, s)["errors"]["s10"]


def test_focus_cues_reuse_capture_and_reset_the_next_camera_track(tmp_path):
    base = Scene(id="s1", kind="card", site="https://nervix.space/#directory",
                 text="Explore our projects.", plan={"website_demo": {}})
    data = base.model_dump()
    data["id"] = "s2"
    data["plan"]["website_demo"]["focus_cues"] = [
        {"start_s": 1.2, "end_s": 2.4, "x": 0.1, "y": 0.25, "width": 0.3, "height": 0.2}
    ]
    focus = Scene.model_validate(data)
    after = base.model_copy(update={"id": "s3"})
    continued = base.model_copy(update={"id": "s4"})
    assert website_demo.asset_path(tmp_path, focus) == website_demo.asset_path(tmp_path, base)
    assert website_demo.card_timeline([base, focus, after, continued], [4, 3, 2, 5]) == {
        "s1": (0, 30), "s2": (0, 22), "s3": (0, 15), "s4": (50, 15),
    }


def test_page_switch_retiming_reuses_pages_and_checks_second_host(tmp_path):
    settings = Settings(capture_allowlist=[{"host": "nervix.space", "mode": "auto"}])
    scene = Scene(id="s28", kind="card", site="https://nervix.space",
                  text="Every project gets its own page.", plan={"website_demo": {
                      "focus_label": "10 USD a month",
                      "page_switch": {"at_s": 2.94, "site": "https://nervix.space/l/nervixpay"},
                  }})
    first = scene.model_copy(deep=True)
    first.plan.website_demo.page_switch = None
    first_path = website_demo.asset_path(tmp_path, first)
    sequence_path = website_demo.asset_path(tmp_path, scene)
    assert first_path != sequence_path
    scene.plan.website_demo.page_switch.at_s = 3.5
    assert website_demo.asset_path(tmp_path, scene) != sequence_path
    assert website_demo.asset_path(tmp_path, first) == first_path
    script = Script(title="Directory", scenes=[scene])
    assert not validate.validate(script, settings)["errors"]
    script.scenes[0].plan.website_demo.page_switch.site = "https://other.test"
    assert validate.validate(script, settings)["errors"]["s28"]


def test_offline_sequence_reports_the_missing_second_page(tmp_path):
    settings = Settings(capture_allowlist=[{"host": "nervix.space", "mode": "auto"}])
    first = Scene(id="s28", kind="card", text="Every project gets its own page.",
                  site="https://nervix.space", plan={"website_demo": {}})
    prepared = website_demo.asset_path(tmp_path, first)
    prepared.parent.mkdir()
    prepared.touch()
    data = first.model_dump()
    second = "https://nervix.space/l/nervixpay"
    data["plan"]["website_demo"]["page_switch"] = {"at_s": 2.94, "site": second}
    scene = Scene.model_validate(data)
    with pytest.raises(ValueError, match="missing prepared card") as exc:
        website_demo.prepare(settings, scene, tmp_path, cached_only=True)
    assert second in str(exc.value)
    assert not website_demo.asset_path(tmp_path, scene).exists()
    assert not (tmp_path / "caps").exists()
