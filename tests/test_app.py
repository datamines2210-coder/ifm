import hashlib, hmac, json, os, uuid
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)

def test_health():
    r = client.get('/api/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'

def test_travel_page():
    r = client.get('/travel')
    assert r.status_code == 200
    assert 'Travel services' in r.text
    assert 'Holiday Packages' in r.text
    assert 'href="https://pages.razorpay.com/ssbglr" target="_blank"' in r.text

def test_travel_link_from_market():
    r = client.get('/')
    assert r.status_code == 200
    assert '<a href="/travel">Travel</a>' in r.text
    assert '<a href="#why">Contact us</a>' in r.text

def test_ready():
    r = client.get('/api/ready')
    assert r.status_code == 200
    assert r.json()['catalog_count'] > 0

def test_catalog_search():
    r = client.get('/api/catalog?q=pickle')
    assert r.status_code == 200
    assert all('pickle' in x['name'].lower() for x in r.json()['items'])

def test_catalog_filter():
    r = client.get('/api/catalog?category=Tea&state=Assam')
    assert r.status_code == 200
    assert all(x['category'] == 'Tea' and x['state'] == 'Assam' for x in r.json()['items'])

def test_signup_login_me():
    email = 'test-auth@example.com'
    client.post('/api/auth/signup', json={'name':'Test Buyer','username':'testbuyer','email':email,'phone':'9876543210','password':'StrongPass123'})
    r = client.post('/api/auth/login', json={'email':email,'password':'StrongPass123'})
    assert r.status_code == 200
    token = r.json()['token']
    r = client.get('/api/auth/me', headers={'Authorization':f'Bearer {token}'})
    assert r.status_code == 200
    assert r.json()['email'] == email

def _authed_client(prefix):
    c = TestClient(app)
    email = f'{prefix}.{uuid.uuid4().hex[:10]}@example.com'
    username = 'test' + uuid.uuid4().hex[:12]
    r = c.post('/api/auth/signup', json={'name':'Test User','username':username,'email':email,'phone':'9876543210','password':'StrongPass123'})
    c.headers.update({'Authorization': 'Bearer ' + r.json()['token']})
    return c

def test_checkout_requires_login():
    r = client.post('/api/checkout', json={
        'customer_name':'Test User','email':'test@example.com','phone':'9876543210','pincode':'560078',
        'address':'Test street, Bengaluru','delivery_date':'2099-01-01','delivery_slot':'09:00-10:00','delivery_date':'2099-01-01','delivery_slot':'09:00-10:00','items':[{'product_id':'demo-up-001','quantity':2}]
    })
    assert r.status_code == 401

def test_checkout():
    c = _authed_client('checkout.basic')
    r = c.post('/api/checkout', json={
        'customer_name':'Test User','email':'test@example.com','phone':'9876543210','pincode':'560078',
        'address':'Test street, Bengaluru','delivery_date':'2099-01-01','delivery_slot':'09:00-10:00','delivery_date':'2099-01-01','delivery_slot':'09:00-10:00','items':[{'product_id':'demo-up-001','quantity':2}]
    })
    assert r.status_code == 200
    assert r.json()['amount'] == 1078
    assert r.json()['order_id'].startswith('ord_')

def test_invalid_product():
    c = _authed_client('checkout.invalid')
    r = c.post('/api/checkout', json={
        'customer_name':'Test User','email':'test@example.com','phone':'9876543210','pincode':'560078',
        'address':'Test street','delivery_date':'2099-01-01','delivery_slot':'09:00-10:00','delivery_date':'2099-01-01','delivery_slot':'09:00-10:00','items':[{'product_id':'bad','quantity':1}]
    })
    assert r.status_code == 400

def test_security_request_id():
    r = client.get('/api/health')
    assert r.headers.get('x-request-id')

def test_metrics():
    client.get('/api/catalog')
    r = client.get('/metrics')
    assert r.status_code == 200
    assert 'app_requests_total' in r.text

def test_payment_signature_helper():
    secret = 'ifm-synthetic-signature-test-only-not-a-real-key'
    original = settings.razorpay_key_secret
    settings.razorpay_key_secret = secret
    try:
        from app.services import PaymentService
        order_id, payment_id = 'order_test', 'pay_test'
        signature = hmac.new(secret.encode(), f'{order_id}|{payment_id}'.encode(), hashlib.sha256).hexdigest()
        assert PaymentService().verify_signature(order_id, payment_id, signature)
        assert not PaymentService().verify_signature(order_id, payment_id, 'bad')
    finally:
        settings.razorpay_key_secret = original


def test_signup_duplicate_email():
    email = f'duplicate-auth-{uuid.uuid4().hex}@example.com'
    payload = {'name':'Duplicate Buyer','username':'dup'+uuid.uuid4().hex[:12],'email':email,'phone':'9876543210','password':'StrongPass123'}
    assert client.post('/api/auth/signup', json=payload).status_code == 200
    r = client.post('/api/auth/signup', json=payload)
    assert r.status_code == 409


def test_login_invalid_password():
    email = 'invalid-password@example.com'
    client.post('/api/auth/signup', json={'name':'Password Buyer','username':'passwordbuyer','email':email,'phone':'9876543210','password':'StrongPass123'})
    r = client.post('/api/auth/login', json={'email':email,'password':'WrongPass123'})
    assert r.status_code == 401


def test_auth_me_requires_login():
    r = client.get('/api/auth/me')
    assert r.status_code == 401
