import base64, uuid
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

def admin(c):
    r=c.post('/api/auth/login',json={'email':settings.admin_username,'password':settings.admin_password})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['token']}

def test_category_picture_upload_and_catalog_exposure():
    c=TestClient(app); h=admin(c)
    raw=b'\x89PNG\r\n\x1a\ncategory-test'
    data='data:image/png;base64,'+base64.b64encode(raw).decode()
    r=c.post('/api/admin/catalog/categories/Pickles/image',headers=h,json={'data_url':data,'filename':'pickles.png'})
    assert r.status_code==200,r.text
    url=r.json()['image']; assert url.startswith('/static/uploads/categories/')
    assert c.get(url).content==raw
    assert c.get('/api/catalog').json()['category_media']['Pickles']==url

def test_customer_address_saves_pinned_locality_coordinates():
    c=TestClient(app); u='map'+uuid.uuid4().hex[:8]
    r=c.post('/api/auth/signup',json={'name':'Map User','username':u,'email':u+'@example.com','phone':'9876543210','password':'Passw0rd123'})
    assert r.status_code==200,r.text
    c.headers.update({'Authorization':'Bearer '+r.json()['token']})
    r=c.put('/api/account/address',json={'address_line1':'1 Test','address_line2':'','locality':'Indiranagar','city':'Bengaluru','state':'Karnataka','pincode':'560038','latitude':12.9784,'longitude':77.6408})
    assert r.status_code==200,r.text
    p=c.get('/api/account/profile').json()['profile']
    assert p['locality']=='Indiranagar' and p['latitude']==12.9784 and p['longitude']==77.6408

def test_admin_ui_has_25_row_paging_and_session_termination():
    html=TestClient(app).get('/admin').text
    assert 'ADMIN_PAGE_SIZE=25' in html
    assert 'Terminate session' in html
    assert 'Catalog categories' in html
    store=TestClient(app).get('/').text
    assert 'accountAddressMap' in store and 'deliveryMap' in store and 'Use current location' in store
