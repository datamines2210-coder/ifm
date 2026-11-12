from pathlib import Path

def html(): return (Path(__file__).parents[1]/'static'/'index.html').read_text(encoding='utf-8')

def test_product_card_anchors_action_row_below_images():
    s=html(); assert '.card-body{padding:13px 14px 68px;display:flex;flex-direction:column;flex:1;min-height:0;position:relative}' in s; assert '.add-row{display:flex!important;gap:8px;position:absolute' in s

def test_live_and_coming_soon_action_logic_preserved():
    s=html(); assert "p.status==='coming_soon'?'<button class=\"add\" disabled" in s; assert 'Add to basket' in s

def test_cashfree_primary_ui_replaces_au():
    s=html(); assert 'Cashfree Payment Gateway' in s; assert 'value="cashfree" checked' in s; assert 'AU Finance Payment Gateway' not in s

def test_server_checkout_contains_live_status_guard():
    s=(Path(__file__).parents[1]/'app'/'main.py').read_text(encoding='utf-8')
    assert "getattr(p, 'status', 'live') != 'live'" in s

def test_provider_neutral_payment_transaction_schema_present():
    s=(Path(__file__).parents[1]/'app'/'db.py').read_text(encoding='utf-8')
    assert 'CREATE TABLE IF NOT EXISTS payment_transactions' in s
    assert 'provider_order_id' in s and 'payment_session_id' in s and 'is_test' in s
