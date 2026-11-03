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
