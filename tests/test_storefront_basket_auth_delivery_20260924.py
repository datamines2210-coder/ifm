from pathlib import Path

HTML = Path('static/index.html').read_text(encoding='utf-8')

def test_basket_requires_successful_login_and_is_user_scoped_for_24_hours():
    assert 'const CART_TTL_MS=24*60*60*1000' in HTML
    assert "function openCart(){if(!requireBasketLogin())return;" in HTML
    assert "return owner?'ifm_cart_user_'+owner:''" in HTML
    assert "updated_at:Date.now(),items:cart" in HTML
    assert "Date.now()-saved.updated_at<=CART_TTL_MS" in HTML

def test_login_and_basket_clear_fixed_bottom_navigation():
    assert '--bottom-nav-clearance:76px' in HTML
    assert "bottom:var(--bottom-nav-clearance,76px)" in HTML
    assert "max-height:calc(100dvh - var(--bottom-nav-clearance) - 40px)" in HTML

def test_delivery_uses_date_and_selectable_office_hour_windows():
    assert 'id="deliveryDate" type="date"' in HTML
    assert 'id="deliverySlot"' in HTML
    assert 'Office operating hours: 9:00 AM – 8:00 PM IST' in HTML
    assert 'value="09:00-10:00"' in HTML
    assert 'value="19:00-20:00"' in HTML
    assert 'Today<br>' not in HTML
    assert "delivery_date:$('deliveryDate').value" in HTML
    assert "delivery_slot:$('deliverySlot').value" in HTML
