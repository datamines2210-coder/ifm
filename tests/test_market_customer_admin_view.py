from fastapi.testclient import TestClient
from app.main import app
from app.config import settings


def test_admin_customer_list_contains_new_signup_and_whatsapp_default():
    c=TestClient(app)
    signup=c.post('/api/auth/signup',json={'name':'Listed Customer','username':'listedcustomer','email':'listed@example.com','phone':'9876543210','password':'Password123'})
    assert signup.status_code==200, signup.text
    admin=c.post('/api/auth/login',json={'email':settings.admin_username,'password':settings.admin_password})
    assert admin.status_code==200, admin.text
    h={'Authorization':'Bearer '+admin.json()['token']}
    users=c.get('/api/admin/users',headers=h)
    assert users.status_code==200, users.text
    row=next(x for x in users.json()['items'] if x['email']=='listed@example.com')
    assert row['username']=='listedcustomer'
    assert row['phone']=='9876543210'
    cfg=c.get('/api/public-config').json()
    assert cfg['whatsapp_url']=='https://wa.me/918604303030?text=Hi%21%20I%20have%20a%20question%20about%20your%20services.'


def test_admin_existing_token_bootstrap_loads_customers_after_enhanced_loader_is_defined():
    from pathlib import Path
    html = (Path(__file__).resolve().parents[1] / 'static' / 'admin.html').read_text(encoding='utf-8')
    enhanced = "const originalLoad=load;load=async function()"
    boot = "if(token) load();"
    assert enhanced in html
    assert boot in html
    assert html.index(boot) > html.index(enhanced)
    assert "resetIdleTimer();load()}else" not in html


def test_storefront_uses_whatsapp_svg_instead_of_phone_glyph():
    from pathlib import Path
    html = (Path(__file__).resolve().parents[1] / 'static' / 'index.html').read_text(encoding='utf-8')
    assert 'id="whatsappFloat"' in html
    assert '<svg viewBox="0 0 32 32"' in html
    assert '>☎</a>' not in html
