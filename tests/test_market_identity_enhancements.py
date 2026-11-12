import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
import app.main as main


def test_required_signup_fields_username_email_phone():
    c=TestClient(app)
    r=c.post('/api/auth/signup',json={'name':'Required Fields','email':'req@example.com','phone':'9876543210','password':'Password123'})
    assert r.status_code==422
    r=c.post('/api/auth/signup',json={'name':'Required Fields','username':'requiredx','email':'req2@example.com','phone':'','password':'Password123'})
    assert r.status_code==422


def test_username_and_email_login_and_admin_password_reset():
    c=TestClient(app); suffix=uuid.uuid4().hex[:10]; username='buyer'+suffix; email=f'{username}@example.com'
    r=c.post('/api/auth/signup',json={'name':'Buyer','username':username,'email':email,'phone':'9876543210','password':'Password123'}); assert r.status_code==200,r.text
    assert c.post('/api/auth/login',json={'email':username,'password':'Password123'}).status_code==200
    assert c.post('/api/auth/login',json={'email':email,'password':'Password123'}).status_code==200
    a=c.post('/api/auth/login',json={'email':settings.admin_username,'password':settings.admin_password}); assert a.status_code==200,a.text
    h={'Authorization':'Bearer '+a.json()['token']}
    users=c.get('/api/admin/users',headers=h); assert users.status_code==200
    row=next(x for x in users.json()['items'] if x['username']==username)
    r=c.post(f"/api/admin/users/{row['id']}/password",headers=h,json={'new_password':'NewPassword456'}); assert r.status_code==200,r.text
    assert c.post('/api/auth/login',json={'email':username,'password':'Password123'}).status_code==401
    assert c.post('/api/auth/login',json={'email':username,'password':'NewPassword456'}).status_code==200


def test_customer_can_update_bank_details():
    c=TestClient(app); suffix=uuid.uuid4().hex[:10]; username='bank'+suffix
    r=c.post('/api/auth/signup',json={'name':'Bank User','username':username,'email':f'{username}@example.com','phone':'9876543210','password':'Password123'}); c.headers.update({'Authorization':'Bearer '+r.json()['token']})
    r=c.put('/api/account/bank',json={'bank_name':'Example Bank','bank_account_masked':'XXXX1234','ifsc':'EXAM0001234'}); assert r.status_code==200,r.text
    p=c.get('/api/account/profile').json()['profile']; assert p['bank_name']=='Example Bank'; assert p['ifsc']=='EXAM0001234'


def test_otp_login_sends_to_both_channels(monkeypatch):
    c=TestClient(app); suffix=uuid.uuid4().hex[:10]; username='otp'+suffix; email=f'{username}@example.com'
    r=c.post('/api/auth/signup',json={'name':'OTP User','username':username,'email':email,'phone':'9876543210','password':'Password123'}); assert r.status_code==200
    delivered={}
    def fake_deliver(e,p,code): delivered.update(email=e,phone=p,code=code)
    monkeypatch.setattr(main,'_deliver_otp',fake_deliver)
    r=c.post('/api/auth/otp/request',json={'identity':username}); assert r.status_code==200,r.text
    assert delivered['email']==email and delivered['phone']=='9876543210'
    r=c.post('/api/auth/otp/verify',json={'identity':username,'code':delivered['code']}); assert r.status_code==200,r.text
    assert r.json()['user']['username']==username
