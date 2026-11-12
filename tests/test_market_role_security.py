from fastapi.testclient import TestClient
from app.main import app
from app.config import settings


def _admin(c):
    r=c.post('/api/auth/login',json={'email':settings.admin_username,'password':settings.admin_password}); assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['token']}

def test_market_allows_only_one_active_session_per_identity():
    c=TestClient(app)
    s=c.post('/api/auth/signup',json={'name':'One Session','username':'onesession','email':'onesession@example.com','phone':'9876543291','password':'Password123'}); assert s.status_code==200,s.text
    first={'Authorization':'Bearer '+s.json()['token']}
    assert c.get('/api/auth/me',headers=first).status_code==200
    second_login=c.post('/api/auth/login',json={'email':'onesession','password':'Password123'}); assert second_login.status_code==200
    second={'Authorization':'Bearer '+second_login.json()['token']}
    assert c.get('/api/auth/me',headers=second).status_code==200
    assert c.get('/api/auth/me',headers=first).status_code==401


def test_manager_power_user_permissions_are_server_enforced():
    c=TestClient(app); ah=_admin(c)
    create=c.post('/api/admin/users',headers=ah,json={'name':'Catalog Manager','username':'catalogmanager','email':'manager@example.com','phone':'9876543292','password':'Password123','role':'manager'}); assert create.status_code==200,create.text
    mlogin=c.post('/api/admin/login',json={'email':'catalogmanager','password':'Password123'}); assert mlogin.status_code==200,mlogin.text
    mh={'Authorization':'Bearer '+mlogin.json()['token']}
    product={'id':'mgr-product','name':'Manager Product','category':'Manager Category','state':'Karnataka','price':10,'mrp':12,'unit':'100 g','description':'manager test','image':'','parent_url':'','active':True,'status':'live'}
    assert c.post('/api/admin/catalog',headers=mh,json=product).status_code==200
    product['name']='Manager Product Edited'; assert c.put('/api/admin/catalog/mgr-product',headers=mh,json=product).status_code==200
    assert c.delete('/api/admin/catalog/mgr-product',headers=mh).status_code==403
    cat={'display_name':'Manager Category','description':'','active':True,'sort_order':100,'new_category':'Manager Category'}
    assert c.post('/api/admin/catalog/categories',headers=mh,json=cat).status_code==200
    assert c.delete('/api/admin/catalog/categories/Manager%20Category',headers=mh).status_code==403
    assert c.get('/api/admin/orders',headers=mh).status_code==200
    assert c.put('/api/admin/orders/not-real/status',headers=mh,json={'status':'paid'}).status_code==403
    offer={'id':'mgr-offer','title':'Manager Offer','slogan':'','description':'','offer_type':'informational','value':0,'code':'','scope':'site','target':'','image':'','cta_text':'','cta_link':'','placement':'offers','priority':100,'status':'draft'}
    assert c.post('/api/admin/offers',headers=mh,json=offer).status_code==200
    assert c.get('/api/admin/offers/recommendations',headers=mh).status_code==200
    assert c.put('/api/admin/offers/mgr-offer',headers=mh,json=offer).status_code==403
    assert c.delete('/api/admin/offers/mgr-offer',headers=mh).status_code==403
    users=c.get('/api/admin/users',headers=mh); assert users.status_code==200; assert users.json().get('read_only') is True; assert all(x.get('role')=='customer' and x.get('account_category')=='customer' for x in users.json()['items'])
    assert c.get('/api/admin/sessions',headers=mh).status_code==403


def test_manager_can_respond_to_support_feedback_but_user_role_changes_are_admin_only():
    c=TestClient(app); ah=_admin(c)
    u=c.post('/api/auth/signup',json={'name':'Feedback User','username':'feedbackuser','email':'feedbackuser@example.com','phone':'9876543293','password':'Password123'}); assert u.status_code==200
    uh={'Authorization':'Bearer '+u.json()['token']}
    fb=c.post('/api/account/feedback',headers=uh,json={'subject':'Delivery question','message':'Please advise','rating':4}); assert fb.status_code==200
    cr=c.post('/api/admin/users',headers=ah,json={'name':'Support Manager','username':'supportmanager','email':'supportmanager@example.com','phone':'9876543294','password':'Password123','role':'manager'}); assert cr.status_code==200
    ml=c.post('/api/admin/login',json={'email':'supportmanager','password':'Password123'}); mh={'Authorization':'Bearer '+ml.json()['token']}
    fid=fb.json()['id']
    rr=c.put('/api/admin/feedback/'+fid,headers=mh,json={'status':'reviewed','response':'We are checking this for you.'}); assert rr.status_code==200,rr.text
    rows=c.get('/api/admin/feedback',headers=mh).json()['items']; row=next(x for x in rows if x['id']==fid); assert row['admin_response']=='We are checking this for you.'
    manager_id=cr.json()['id']
    assert c.put('/api/admin/users/'+manager_id+'/role',headers=mh,json={'role':'admin'}).status_code==403
