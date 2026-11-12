from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app, cashfree
from app.auth import create_token
from app.config import settings

ROOT=Path(__file__).parents[1]

def html(): return (ROOT/'static'/'index.html').read_text(encoding='utf-8')
def admin_html(): return (ROOT/'static'/'admin.html').read_text(encoding='utf-8')

def admin_client():
    c=TestClient(app)
    c.headers.update({'Authorization':'Bearer '+create_token('admin','administrator',role='admin')})
    return c

def test_basket_has_inline_product_search_without_closing():
    s=html()
    assert 'Add another product' in s
    assert 'basketProductSearch' in s
    assert 'searchBasketProducts' in s
    assert 'addFromBasket' in s
    assert "closeCart();document.getElementById('products')" not in s

def test_basket_search_respects_live_and_coming_soon():
    s=html()
    assert "String(p.status||'live').toLowerCase()==='live'" in s
    assert 'Add to basket' in s and 'Coming Soon' in s

def test_basket_add_preserves_checkout_form_state():
    s=html()
    assert 'captureCartFormState' in s and 'restoreCartFormState' in s

def test_admin_ui_supports_sandbox_and_guarded_production_one_rupee():
    s=admin_html()
    assert "env==='production'" in s
    assert 'LIVE CASHFREE TEST' in s
    assert 'Final confirmation' in s
    assert 'confirm_live:live' in s

def test_production_one_rupee_requires_explicit_confirmation(monkeypatch):
    monkeypatch.setattr(settings,'cashfree_environment','production')
    monkeypatch.setattr(settings,'cashfree_app_id','live-app')
    monkeypatch.setattr(settings,'cashfree_secret_key','live-secret')
    r=admin_client().post('/api/admin/payment-testing/cashfree/one-rupee',json={'confirm_live':False})
    assert r.status_code==400
    assert 'explicit production confirmation' in r.text

def test_sandbox_one_rupee_path_creates_test_transaction(monkeypatch):
    monkeypatch.setattr(settings,'cashfree_environment','sandbox')
    monkeypatch.setattr(settings,'cashfree_app_id','sandbox-app')
    monkeypatch.setattr(settings,'cashfree_secret_key','sandbox-secret')
    monkeypatch.setattr(cashfree,'create_order',lambda **kw:{'provider':'cashfree','id':kw['order_id'],'payment_session_id':'sandbox-session','amount':100,'currency':'INR','environment':'sandbox'})
    r=admin_client().post('/api/admin/payment-testing/cashfree/one-rupee',json={'confirm_live':False})
    assert r.status_code==200,r.text
    d=r.json(); assert d['environment']=='sandbox' and d['live_money'] is False and d['amount']==1.0

def test_production_one_rupee_path_is_fixed_and_marked_live(monkeypatch):
    monkeypatch.setattr(settings,'cashfree_environment','production')
    monkeypatch.setattr(settings,'cashfree_app_id','live-app')
    monkeypatch.setattr(settings,'cashfree_secret_key','live-secret')
    monkeypatch.setattr(cashfree,'create_order',lambda **kw:{'provider':'cashfree','id':kw['order_id'],'payment_session_id':'live-session','amount':100,'currency':'INR','environment':'production'})
    r=admin_client().post('/api/admin/payment-testing/cashfree/one-rupee',json={'confirm_live':True})
    assert r.status_code==200,r.text
    d=r.json(); assert d['environment']=='production' and d['live_money'] is True and d['amount']==1.0
