from pathlib import Path
H=(Path(__file__).resolve().parents[1]/'static'/'index.html').read_text(encoding='utf-8')
def test_card_has_strict_image_viewport():
    assert 'storefront product-card layout v3' in H
    assert 'aspect-ratio:4/3!important' in H
    assert 'object-fit:contain!important' in H
    assert 'overflow:hidden!important' in H
def test_details_and_actions_are_normal_flow():
    assert '.card .card-body{position:relative!important' in H
    assert '.card .add-row{position:static!important' in H
    assert 'margin-top:auto!important' in H
def test_compact_card_hides_external_link():
    assert '.card .parent-link{display:none!important}' in H
def test_responsive_columns():
    assert '@media(max-width:1050px){.grid{grid-template-columns:repeat(3' in H
    assert '.grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:11px}' in H
    assert '@media(max-width:350px){.grid{grid-template-columns:1fr}' in H
def test_quickview_and_purchase_behavior_preserved():
    assert 'id="productQuickView"' in H
    assert 'openProductQuickView' in H
    assert 'Add to basket' in H
    assert 'Coming Soon' in H
