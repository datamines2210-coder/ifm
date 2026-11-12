from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

def test_catalog_search_includes_category_name():
    c=TestClient(app)
    all_items=c.get('/api/catalog').json()['items']
    if not all_items: return
    category=all_items[0]['category']
    r=c.get('/api/catalog',params={'q':category})
    assert r.status_code==200
    assert any(x['category'].lower()==category.lower() for x in r.json()['items'])

def test_storefront_shop_modal_and_manager_password_hooks():
    html=(Path(__file__).parents[1]/'static'/'index.html').read_text(encoding='utf-8')
    assert 'id="shopAllToggle"' in html
    assert 'Shop by category <span class="shop-arrow">▼</span>' in html
    assert 'id="shopBrowser"' in html
    assert 'class="shop-mega"' in html
    assert "user.role==='manager'" in html
    assert '<span class="account-label">Login / Sign up</span><span>Account</span>' not in html

def test_manager_customers_tab_is_allowed_but_read_only_ui():
    html=(Path(__file__).parents[1]/'static'/'admin.html').read_text(encoding='utf-8')
    assert "['catalog','orders','customers','offers','support']" in html
    assert 'Customer view — read only' in html
