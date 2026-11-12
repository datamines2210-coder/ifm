"""Legacy filename retained so hot-patch overlays replace the obsolete AU Bank tests."""
import base64, hashlib, hmac, uuid
from fastapi.testclient import TestClient
from app.main import app, cashfree
from app.auth import create_token
from app.config import settings
from app.payments.cashfree import CashfreeGateway

client=TestClient(app)

def admin_client():
    c=TestClient(app); c.headers.update({'Authorization':'Bearer '+create_token('admin','administrator',role='admin')}); return c

def set_provider(provider):
    c=admin_client(); r=c.put('/api/admin/payment-settings',json={'provider':provider,'razorpay_checkout_url':'https://pages.razorpay.com/tifa','upi_id':'','upi_name':'','upi_redirect_url':''}); assert r.status_code==200,r.text; return r

def customer_client():
    c=TestClient(app); u='buyer'+uuid.uuid4().hex[:10]; r=c.post('/api/auth/signup',json={'name':'Test Buyer','username':u,'email':u+'@example.com','phone':'9876543210','password':'Passw0rd123'}); assert r.status_code==200,r.text; c.headers.update({'Authorization':'Bearer '+r.json()['token']}); return c

def live_product():
    return next(x for x in client.get('/api/catalog').json()['items'] if x.get('active') and x.get('status','live')=='live')

def test_cashfree_is_valid_primary_provider():
    r=set_provider('cashfree'); assert r.json()['settings']['provider']=='cashfree'

def test_gateway_health_has_cashfree_and_razorpay():
    d=client.get('/api/payments/gateways/health').json(); assert set(d['gateways'])=={'cashfree','razorpay'}; assert d['gateways']['cashfree']['primary'] is True

def test_unconfigured_cashfree_falls_back_to_razorpay():
    set_provider('cashfree'); c=customer_client(); p=live_product(); r=c.post('/api/checkout',json={'customer_name':'Test Buyer','email':'buyer@example.com','phone':'9876543210','pincode':'560001','address':'1 MG Road','delivery_date':'2099-01-01','delivery_slot':'09:00-10:00','items':[{'product_id':p['id'],'quantity':1}]}); assert r.status_code==200,r.text; assert r.json()['payment']['provider']=='razorpay_redirect'; assert r.json()['payment']['gateway_failover']=='cashfree_unavailable'

def test_explicit_razorpay_choice_is_honoured():
    set_provider('cashfree'); c=customer_client(); p=live_product(); r=c.post('/api/checkout',json={'customer_name':'Test Buyer','email':'buyer@example.com','phone':'9876543210','pincode':'560001','address':'1 MG Road','delivery_date':'2099-01-01','delivery_slot':'09:00-10:00','items':[{'product_id':p['id'],'quantity':1}],'payment_method':'razorpay'}); assert r.status_code==200,r.text; assert r.json()['payment']['gateway_choice']=='customer_selected_razorpay'

def test_cashfree_webhook_missing_signature_rejected():
    assert client.post('/api/payments/cashfree/webhook',content=b'{}').status_code==401

def test_cashfree_signature_uses_timestamp_plus_raw_body(monkeypatch):
    monkeypatch.setattr(settings,'cashfree_app_id','app'); monkeypatch.setattr(settings,'cashfree_secret_key','secret')
    body=b'{"data":{}}'; ts='1700000000'; sig=base64.b64encode(hmac.new(b'secret',ts.encode()+body,hashlib.sha256).digest()).decode()
    assert CashfreeGateway().verify_webhook_signature(body,ts,sig)

def test_payment_testing_requires_admin():
    assert client.get('/api/admin/payment-testing').status_code in (401,403)
