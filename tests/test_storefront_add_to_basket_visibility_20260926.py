from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / 'static' / 'index.html').read_text(encoding='utf-8')

def test_product_action_zone_is_bottom_anchored_and_reserved():
    assert 'padding:13px 14px 68px' in HTML
    assert 'position:relative' in HTML
    assert '.add-row{display:flex!important' in HTML
    assert 'position:absolute' in HTML
    assert 'bottom:15px' in HTML
    assert 'visibility:visible!important' in HTML

def test_live_products_render_add_to_basket_and_coming_soon_does_not():
    assert "p.status==='coming_soon'" in HTML
    assert '>Coming Soon</button>' in HTML
    assert '>Add to basket</button>' in HTML
    assert 'onclick="add(' in HTML

def test_mobile_cards_reserve_action_space():
    assert '.card-body{padding-bottom:62px}.add-row{left:10px;right:10px;bottom:10px}' in HTML
