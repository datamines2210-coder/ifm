from pathlib import Path

def test_account_icon_matches_bottom_navigation_icon_size():
    html = (Path(__file__).parents[1] / "static" / "index.html").read_text(encoding="utf-8")
    assert ".nav-action .account-icon{display:inline-flex;align-items:center;justify-content:center;font-size:20px;line-height:1}" in html
    assert ".nav-action .account-icon{font-size:20px;line-height:1}" in html
    assert ".mobile-bottom-nav .bottom-icon{font-size:20px;line-height:1.1;color:var(--forest)}" in html
    assert ".nav-action .account-icon{font-size:22px" not in html
