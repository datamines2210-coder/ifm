from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / 'static' / 'index.html').read_text(encoding='utf-8')
ADMIN = (ROOT / 'static' / 'admin.html').read_text(encoding='utf-8')

def test_shop_by_category_uses_downward_mega_menu_not_modal():
    assert 'id="shopBrowser"' in INDEX
    assert 'class="shop-mega"' in INDEX
    assert '<div class="overlay" id="shopBrowser"' not in INDEX
    assert '.shop-mega.open{display:block}' in INDEX
    assert 'grid-template-columns:minmax(190px,.8fr) minmax(240px,1fr) minmax(280px,1.4fr)' in INDEX
    assert 'Products &amp; others' in INDEX
    assert 'aria-expanded="false"' in INDEX

def test_close_buttons_render_only_one_pseudo_x():
    assert ".close{border:0;background:none;font-size:0" in INDEX
    assert ".close:before{content:'×'" in INDEX

def test_manager_hides_administrator_password_controls():
    assert "if(h.textContent.trim()==='Administrator password')" in ADMIN
    assert "if(form&&form.tagName==='FORM')form.style.display='none'" in ADMIN
