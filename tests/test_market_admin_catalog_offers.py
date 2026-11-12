from pathlib import Path
import uuid
import base64, io
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from app.main import app
from app.config import settings

def admin(c):
    r=c.post('/api/auth/login',json={'email':settings.admin_username,'password':settings.admin_password}); assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['token']}

def test_catalog_coming_soon_template_import_and_offers():
    c=TestClient(app); h=admin(c)
    item={'id':'soon-1','name':'Soon Tea','category':'Tea','state':'Assam','price':100,'mrp':120,'unit':'100 g','description':'soon','image':'','parent_url':'','active':True,'status':'coming_soon'}
    assert c.post('/api/admin/catalog',headers=h,json=item).status_code==200
    public=c.get('/api/catalog').json()['items']; assert any(x['id']=='soon-1' and x['status']=='coming_soon' for x in public)
    x=c.get('/api/admin/catalog/template.xlsx',headers=h); assert x.status_code==200
    wb=load_workbook(io.BytesIO(x.content)); ws=wb['Catalog']; assert 'status' in [z.value for z in ws[1]]
    offer={'id':'family20','title':'Family Festival','slogan':'Save together','offer_type':'percentage','value':20,'code':'FAMILY20','scope':'site','target':'','image':'','cta_text':'Shop','cta_link':'#products','placement':'offers','status':'active','priority':1}
    assert c.post('/api/admin/offers',headers=h,json=offer).status_code==200
    assert c.get('/api/offers').json()['items'][0]['id']=='family20'

def test_admin_customer_crud_without_orders():
    c=TestClient(app); h=admin(c)
    r=c.post('/api/admin/users',headers=h,json={'name':'Test Customer','username':'customerx','email':'customerx@example.com','phone':'9999999999','password':'Password123','role':'customer'}); assert r.status_code==200,r.text
    uid=r.json()['id']
    body={'name':'Updated Customer','username':'updatedcustomer','email':'customerx@example.com','phone':'8888888888','address_line1':'1 Main','address_line2':'','city':'Bengaluru','state':'Karnataka','pincode':'560001','bank_name':'Bank','bank_account_masked':'****1234','ifsc':'TEST0001'}
    assert c.put('/api/admin/users/'+uid,headers=h,json=body).status_code==200
    assert c.get('/api/admin/users/'+uid,headers=h).json()['name']=='Updated Customer'
    assert c.delete('/api/admin/users/'+uid,headers=h).status_code==200


def test_uploaded_catalog_image_is_served_from_static_url():
    c=TestClient(app); h=admin(c)
    item={'id':'image-serve-1','name':'Image Product','category':'Test','state':'Karnataka','price':10,'mrp':10,'unit':'1','description':'image','image':'','parent_url':'','active':True,'status':'live'}
    assert c.post('/api/admin/catalog',headers=h,json=item).status_code==200
    # Minimal valid-enough PNG payload: the upload endpoint validates type/size, not image decoding.
    raw=b'\x89PNG\r\n\x1a\nmarket-image-test'
    data_url='data:image/png;base64,'+base64.b64encode(raw).decode('ascii')
    r=c.post('/api/admin/catalog/image-serve-1/image',headers=h,json={'data_url':data_url,'filename':'product.png'})
    assert r.status_code==200,r.text
    url=r.json()['image']
    assert url.startswith('/static/uploads/catalog/')
    served=c.get(url)
    assert served.status_code==200
    assert served.content==raw

def test_admin_users_are_categorized_and_builtin_admin_is_manageable():
    c=TestClient(app); h=admin(c)
    d=c.get('/api/admin/users',headers=h); assert d.status_code==200,d.text
    items=d.json()['items']; builtin=next(x for x in items if x['id']=='admin')
    assert builtin['account_category']=='administrator' and builtin['builtin'] is True
    assert all(x.get('account_category') in {'customer','administrator','staff','test_system'} for x in items)


def test_storefront_hides_customer_account_edit_controls_for_admin():
    html=TestClient(app).get('/').text
    assert "isCustomer=logged&&user.role==='customer'" in html
    assert "$(id).style.display=isCustomer?'block':'none'" in html

def test_admin_bulk_delete_stale_users_protects_recent_and_order_history():
    import time
    from app.db import connect
    c=TestClient(app); h=admin(c)
    def add(username):
        r=c.post('/api/admin/users',headers=h,json={'name':'Stale Candidate','username':username,'email':username+'@example.com','phone':'9999999999','password':'Password123','role':'customer'}); assert r.status_code==200,r.text; return r.json()['id']
    stale=add('stale_bulk_1'); recent=add('recent_bulk_1')
    with connect() as db:
        db.execute('UPDATE users SET created_at=? WHERE id=?',(int(time.time())-200*86400,stale))
    r=c.post('/api/admin/users/bulk-delete',headers=h,json={'user_ids':[stale,recent],'stale_days':90,'include_never_used':True}); assert r.status_code==200,r.text
    d=r.json(); assert stale in d['deleted']; assert any(x['id']==recent and x['reason']=='not_stale' for x in d['skipped'])
    assert c.get('/api/admin/users/'+recent,headers=h).status_code==200

def test_admin_customers_ui_has_stale_bulk_controls():
    html=TestClient(app).get('/admin').text
    assert 'Inactive 90+ days' in html
    assert 'Delete selected users' in html
    assert '/api/admin/users/bulk-delete' in html

def test_admin_bulk_manual_selection_can_delete_recent_no_order_customer():
    c=TestClient(app); h=admin(c)
    suffix=uuid.uuid4().hex[:8]
    payload={'name':'Manual Delete','username':'manual'+suffix,'email':f'manual{suffix}@example.com','phone':'9876543210','password':'Password123','role':'customer'}
    made=c.post('/api/admin/users',headers=h,json=payload); assert made.status_code==200,made.text
    uid=made.json()['id']
    r=c.post('/api/admin/users/bulk-delete',headers=h,json={'user_ids':[uid],'stale_days':90,'include_never_used':True,'deletion_mode':'manual'})
    assert r.status_code==200,r.text
    assert uid in r.json()['deleted']


def test_admin_customers_ui_allows_manual_checkbox_selection():
    html=(Path(__file__).resolve().parents[1]/'static'/'admin.html').read_text(encoding='utf-8')
    assert 'function userCanBeBulkDeleted' in html
    assert 'Delete selected users' in html
    assert "deletion_mode:staleMode?'stale':'manual'" in html
