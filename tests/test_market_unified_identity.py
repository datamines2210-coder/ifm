import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.auth import create_token


def test_storefront_has_no_admin_top_button_and_has_account_icon():
    html=TestClient(app).get('/').text
    assert 'href="/admin">Admin</a>' not in html
    assert '👤 Login / Sign up' in html
    assert 'Username or email address' in html


def test_customer_can_login_by_username_and_edit_address_and_bank():
    c=TestClient(app); suffix=uuid.uuid4().hex[:8]; username='buyer'+suffix
    r=c.post('/api/auth/signup',json={'name':'Buyer Name','username':username,'email':f'{username}@example.com','phone':'9876543210','password':'Passw0rd123'})
    assert r.status_code==200,r.text
    r=c.post('/api/auth/login',json={'email':username,'password':'Passw0rd123'})
    assert r.status_code==200,r.text
    c.headers.update({'Authorization':'Bearer '+r.json()['token']})
    r=c.put('/api/account/address',json={'address_line1':'1 Test Road','address_line2':'','city':'Bengaluru','state':'Karnataka','pincode':'560001'})
    assert r.status_code==200
    profile=c.get('/api/account/profile').json()
    assert profile['profile']['address_line1']=='1 Test Road'
    assert profile['bank_details_editable'] is True
    r=c.put('/api/account/bank',json={'bank_name':'Test Bank','bank_account_masked':'****4321','ifsc':'TEST0001'})
    assert r.status_code==200,r.text
    profile=c.get('/api/account/profile').json()
    assert profile['profile']['bank_name']=='Test Bank'
    assert profile['profile']['bank_account_masked']=='****4321'


def test_builtin_admin_uses_unified_login_and_can_manage_sessions():
    c=TestClient(app)
    r=c.post('/api/auth/login',json={'email':settings.admin_username,'password':settings.admin_password})
    assert r.status_code==200,r.text
    assert r.json()['user']['role']=='admin'
    c.headers.update({'Authorization':'Bearer '+r.json()['token']})
    sessions=c.get('/api/admin/sessions')
    assert sessions.status_code==200
    assert any(x['user_id']=='admin' for x in sessions.json()['items'])


def test_extended_services_remain_mounted_but_are_separate_from_market_identity():
    paths={r.path for r in app.routes}
    assert {'/scorer', '/travel', '/sports'} <= paths
    assert any(p.startswith('/api/scorer') for p in paths)
    assert any(p.startswith('/api/travel') for p in paths)
    assert any(p.startswith('/api/sports') for p in paths)

    # Each extended service keeps its own authentication namespace rather than
    # reusing the Market /api/auth endpoints.
    assert '/api/scorer/auth/login' in paths
    assert '/api/travel/auth/login' in paths
    assert '/api/sports/auth/login' in paths


def test_legacy_customer_without_username_gets_readable_username_and_can_login(tmp_path, monkeypatch):
    import sqlite3, time
    from app import db as market_db
    from app.auth import hash_password
    old_url=settings.database_url
    dbfile=tmp_path/'legacy.db'
    monkeypatch.setattr(settings,'database_url',f'sqlite:///{dbfile}')
    try:
        market_db.init_db()
        with market_db.connect() as con:
            con.execute("INSERT INTO users(id,name,email,username,phone,password_hash,role,must_change_password,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                        ('legacy_kalyan','Kalyan','kalyan@example.com',None,'',hash_password('Passw0rd123'),'customer',0,int(time.time())))
        market_db.init_db()
        u=market_db.find_user_by_login('kalyan')
        assert u is not None and u['id']=='legacy_kalyan'
    finally:
        monkeypatch.setattr(settings,'database_url',old_url)


def test_customer_can_update_account_details_and_change_password():
    c=TestClient(app); suffix=uuid.uuid4().hex[:8]; username='edit'+suffix
    email=f'{username}@example.com'
    r=c.post('/api/auth/signup',json={'name':'Edit User','username':username,'email':email,'phone':'9876543210','password':'Passw0rd123'})
    assert r.status_code==200,r.text
    token=r.json()['token']; c.headers.update({'Authorization':'Bearer '+token})
    r=c.put('/api/account/details',json={'name':'Updated User','username':username+'x','email':email,'phone':'9999999999'})
    assert r.status_code==200,r.text
    assert r.json()['name']=='Updated User'
    r=c.post('/api/auth/password',json={'current_password':'Passw0rd123','new_password':'NewPassw0rd456'})
    assert r.status_code==200,r.text
    c.headers.pop('Authorization',None)
    r=c.post('/api/auth/login',json={'email':username+'x','password':'NewPassw0rd456'})
    assert r.status_code==200,r.text
