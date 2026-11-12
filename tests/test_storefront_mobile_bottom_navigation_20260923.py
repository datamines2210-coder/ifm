from pathlib import Path

HTML = (Path(__file__).parents[1] / 'static' / 'index.html').read_text(encoding='utf-8')

def test_mobile_header_is_location_search_account_first():
    assert 'grid-template-areas:\'brand account\' \'location location\' \'search search\'' in HTML
    assert 'class="search-lens"' in HTML
    assert '.nav-action .account-label{display:none}' in HTML
    assert '.basket{display:none!important}' in HTML

def test_mobile_bottom_navigation_has_requested_actions():
    assert 'class="mobile-bottom-nav"' in HTML
    for label in ('Home', 'Categories', 'Top Picks', 'WhatsApp', 'Basket'):
        assert f'<span>{label}</span>' in HTML
    assert 'onclick="openShopByCategory()"' in HTML
    assert 'id="bottomWhatsApp"' in HTML
    assert 'id="bottomCount"' in HTML

def test_mobile_moves_whatsapp_and_basket_from_floating_top_controls():
    assert '.whatsapp-float{display:none!important}' in HTML
    assert "if($('bottomCount'))$('bottomCount').textContent=$('count').textContent" in HTML
