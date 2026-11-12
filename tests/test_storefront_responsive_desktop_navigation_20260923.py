from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / 'static' / 'index.html').read_text(encoding='utf-8')

def test_desktop_uses_new_responsive_header_and_bottom_navigation():
    assert "grid-template-areas:'brand account' 'location location' 'search search'" in HTML
    assert '.nav-action .account-label{display:none}' in HTML
    assert '.basket{display:none!important}' in HTML
    assert '.subnav .location{display:none!important}' in HTML
    assert '.whatsapp-float{display:none!important}' in HTML
    assert '.mobile-bottom-nav{position:fixed;left:50%' in HTML

def test_search_lens_and_delivery_location_are_reused_not_duplicated():
    assert 'class="search-lens"' in HTML
    assert 'class="mobile-location" id="mobileLocationBtn"' in HTML
    assert '<span>📍 Delivering to</span>' in HTML
    assert 'class="account-icon"' in HTML
