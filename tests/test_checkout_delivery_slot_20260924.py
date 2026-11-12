from fastapi.testclient import TestClient
from app.main import app

def test_checkout_rejects_invalid_delivery_slot_before_catalog_processing():
    # Pydantic request validation rejects a slot outside 09:00-20:00 operating windows.
    c=TestClient(app)
    r=c.post('/api/checkout', json={
        'customer_name':'Test User','email':'test@example.com','phone':'9876543210','pincode':'560078',
        'address':'Test street, Bengaluru','delivery_date':'2099-01-01','delivery_slot':'20:00-21:00',
        'items':[{'product_id':'demo-up-001','quantity':1}]
    })
    assert r.status_code == 422
