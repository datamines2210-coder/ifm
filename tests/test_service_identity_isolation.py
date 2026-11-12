from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_token


def _login(service,password):
    c=TestClient(app)
    r=c.post(f'/api/{service}/auth/login',json={'email':f'{service}-admin@example.invalid','password':password})
    assert r.status_code==200
    return r.json()['token']

def test_market_token_cannot_admin_travel_or_sports():
    market=create_token('admin','administrator',role='admin')
    for svc,path,payload in [('travel','packages',{'title':'x'}),('sports','communities',{'key':'x','name':'x'})]:
        r=TestClient(app).post(f'/api/{svc}/{path}',json=payload,headers={'Authorization':'Bearer '+market})
        assert r.status_code==401

def test_travel_and_sports_tokens_are_not_interchangeable():
    travel=_login('travel','ChangeMe-Travel-Admin-123!')
    sports=_login('sports','ChangeMe-Sports-Admin-123!')
    assert TestClient(app).get('/api/sports/inquiries',headers={'Authorization':'Bearer '+travel}).status_code==401
    assert TestClient(app).get('/api/travel/inquiries',headers={'Authorization':'Bearer '+sports}).status_code==401

def test_service_password_change_is_local():
    c=TestClient(app); token=_login('travel','ChangeMe-Travel-Admin-123!')
    r=c.post('/api/travel/auth/password',json={'current_password':'ChangeMe-Travel-Admin-123!','new_password':'TravelOnlyPass123!'},headers={'Authorization':'Bearer '+token})
    assert r.status_code==200
    new_token=c.post('/api/travel/auth/login',json={'email':'travel-admin@example.invalid','password':'TravelOnlyPass123!'}).json()['token']
    assert c.post('/api/travel/auth/password',json={'current_password':'TravelOnlyPass123!','new_password':'ChangeMe-Travel-Admin-123!'},headers={'Authorization':'Bearer '+new_token}).status_code==200
    assert c.post('/api/sports/auth/login',json={'email':'sports-admin@example.invalid','password':'ChangeMe-Sports-Admin-123!'}).status_code==200
