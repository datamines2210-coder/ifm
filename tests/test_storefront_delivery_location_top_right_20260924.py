from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")

def test_delivery_location_is_in_header_actions_before_account():
    actions = HTML.split('<div class="header-actions">', 1)[1].split('</div><form class="search"', 1)[0]
    assert 'id="mobileLocationBtn"' in actions
    assert 'id="accountBtn"' in actions
    assert actions.index('id="mobileLocationBtn"') < actions.index('id="accountBtn"')
    assert 'class="mobile-location"' in actions

def test_delivery_location_is_top_right_on_desktop_and_mobile():
    assert ".nav-in{grid-template-columns:minmax(0,1fr) auto;grid-template-areas:'brand actions' 'search search'}" in HTML
    assert '.header-actions{grid-area:actions;display:flex' in HTML
    mobile_rule = "@media(max-width:768px){.nav-in{grid-template-columns:minmax(0,1fr) auto;grid-template-areas:'brand actions' 'search search'"
    assert mobile_rule in HTML
    assert '.subnav .location{display:none!important}' in HTML

def test_location_keeps_existing_modal_and_state_sync():
    assert 'onclick="openLocation()"' in HTML
    assert 'id="mobileLocationText"' in HTML
    assert "$('mobileLocationText').textContent=locationLabel" in HTML
