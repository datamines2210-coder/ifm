from pathlib import Path


def test_storefront_mobile_header_and_close_controls_present():
    html = (Path(__file__).parents[1] / "static" / "index.html").read_text(encoding="utf-8")
    assert ".close:before{content:'×'" in html
    assert 'class="mobile-location"' in html
    assert 'id="mobileLocationText"' in html
    assert 'class="account-icon"' in html
    assert 'class="basket-icon"' in html
    assert ".subnav .location{display:none}" in html
    assert "$('mobileLocationText').textContent=locationLabel" in html
