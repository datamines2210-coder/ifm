from pathlib import Path


def _html():
    return (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")


def test_mobile_header_uses_grid_and_keeps_account_visible():
    html = _html()
    mobile = html.split("@media(max-width:620px){", 1)[1].split("</style>", 1)[0]
    assert ".nav-in{display:grid" in mobile
    assert "grid-template-areas:'brand account basket' 'search search search'" in mobile
    assert ".account-wrap{grid-area:account" in mobile
    assert ".nav-admin{grid-area:admin" not in mobile
    assert ".basket{grid-area:basket" in mobile
    assert ".search{grid-area:search" in mobile
    assert "flex-wrap:wrap" not in mobile


def test_account_login_is_not_hidden_on_tablet_or_mobile():
    html = _html()
    responsive = html.split("@media(max-width:900px){", 1)[1].split("</style>", 1)[0]
    assert ".nav-action{display:none}" not in responsive
    assert ".nav-action{display:block}" in responsive
    assert '<span class="account-label">Login / Sign up</span>' in html


def test_mobile_header_has_compact_overflow_guards():
    html = _html()
    mobile = html.split("@media(max-width:620px){", 1)[1].split("</style>", 1)[0]
    assert ".brand{grid-area:brand;min-width:0" in mobile
    assert ".nav-action{display:flex;flex-direction:column" in mobile
    assert "width:64px;height:56px" in mobile
    assert ".mobile-location{grid-area:location;display:flex" in mobile
    assert ".search{grid-area:search;width:100%;max-width:none;min-width:0" in mobile
