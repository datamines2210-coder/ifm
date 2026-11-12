import importlib
from fastapi.testclient import TestClient


def test_scorer_admin_can_change_identity_and_manage_sessions(tmp_path, monkeypatch):
    monkeypatch.setenv('SCORER_DB_PATH', str(tmp_path/'scorer.db'))
    monkeypatch.setenv('SCORER_ADMIN_EMAIL', 'old-admin@example.com')
    monkeypatch.setenv('SCORER_ADMIN_PASSWORD', 'AdminPass123!')
    import app.scorer.database as db
    import app.scorer.auth as auth
    import app.scorer.router as router
    importlib.reload(db); importlib.reload(auth); importlib.reload(router)
    db.init_db()
    from fastapi import FastAPI
    app=FastAPI(); app.include_router(router.router)
    c=TestClient(app)
    login=c.post('/api/scorer/auth/admin-login',json={'email':'old-admin@example.com','password':'AdminPass123!'})
    assert login.status_code==200
    token=login.json()['token']; h={'Authorization':f'Bearer {token}'}
    r=c.put('/api/scorer/admin/identity',headers=h,json={'name':'Club Scorer Admin','username':'clubadmin','email':'new-admin@example.com'})
    assert r.status_code==200 and r.json()['email']=='new-admin@example.com'
    assert c.post('/api/scorer/auth/admin-login',json={'email':'old-admin@example.com','password':'AdminPass123!'}).status_code==401
    assert c.post('/api/scorer/auth/admin-login',json={'login':'new-admin@example.com','password':'AdminPass123!'}).status_code==200
    assert c.post('/api/scorer/auth/admin-login',json={'login':'clubadmin','password':'AdminPass123!'}).status_code==200
    assert c.get('/api/scorer/admin/overview',headers=h).status_code==200
