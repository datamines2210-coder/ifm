import base64, io, uuid
from fastapi.testclient import TestClient
from openpyxl import Workbook
from app.main import app
from app.config import settings

def admin(c):
    r=c.post('/api/auth/login',json={'email':settings.admin_username,'password':settings.admin_password})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['token']}

def test_new_product_category_is_public_and_manageable():
    c=TestClient(app); h=admin(c); cat='Fresh '+uuid.uuid4().hex[:6]; pid='cat-'+uuid.uuid4().hex[:8]
    item={'id':pid,'name':'Category Test','category':cat,'state':'Karnataka','price':20,'mrp':25,'unit':'1 pack','description':'test','image':'','parent_url':'','active':True,'status':'live'}
    assert c.post('/api/admin/catalog',headers=h,json=item).status_code==200
    assert cat in c.get('/api/catalog').json()['categories']
    cats=c.get('/api/admin/catalog/categories',headers=h).json()['items']
    assert any(x['category']==cat for x in cats)

def test_catalog_import_validate_only_blocks_bad_data_without_write():
    c=TestClient(app); h=admin(c); pid='bad-'+uuid.uuid4().hex[:8]
    wb=Workbook(); ws=wb.active; ws.append(['id','name','category','state','price','mrp','unit','description','image','parent_url','status']); ws.append([pid,'Bad','Tea','Karnataka',100,50,'1','bad','','','live'])
    b=io.BytesIO(); wb.save(b); data='data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,'+base64.b64encode(b.getvalue()).decode()
    r=c.post('/api/admin/catalog/import',headers=h,json={'data_url':data,'filename':'bad.xlsx','validate_only':True})
    assert r.status_code==200 and r.json()['status']=='rejected'
    assert not any(x['id']==pid for x in c.get('/api/admin/catalog',headers=h).json()['items'])

def test_offer_recommendations_endpoint_is_explainable():
    c=TestClient(app); h=admin(c); r=c.get('/api/admin/offers/recommendations',headers=h)
    assert r.status_code==200
    d=r.json(); assert d['items'] and 'basis' in d
