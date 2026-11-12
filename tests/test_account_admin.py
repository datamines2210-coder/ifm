import uuid

from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_token

client = TestClient(app)


def admin_login(c=client):
    token = create_token("admin", "administrator", role="admin")
    c.headers.update({"Authorization": "Bearer " + token})
    return token


def unique_email(prefix):
    # The main storefront DB isn't test-isolated (unlike scorer/travel/sports),
    # so each test run needs a fresh email to avoid clashing with prior runs.
    return f"{prefix}.{uuid.uuid4().hex[:10]}@example.com"


def signup(prefix, name="Test User"):
    c = TestClient(app)
    email = unique_email(prefix)
    username = "test" + uuid.uuid4().hex[:12]
    r = c.post("/api/auth/signup", json={"name": name, "username": username, "email": email, "phone": "9876543210", "password": "Passw0rd123"})
    assert r.status_code == 200, r.text
    c.headers.update({"Authorization": "Bearer " + r.json()["token"]})
    return c, r.json()["user"], email


def checkout(c, pincode="560001"):
    items = client.get("/api/catalog").json()["items"]
    r = c.post("/api/checkout", json={
        "customer_name": "Test User", "email": "buyer@example.com", "phone": "9876543210",
        "pincode": pincode, "address": "1 MG Road, Bengaluru",
        "delivery_date":"2099-01-01","delivery_slot":"09:00-10:00","items": [{"product_id": items[0]["id"], "quantity": 2}],
    })
    assert r.status_code == 200, r.text
    return r.json()["order_id"]


def test_account_summary_and_orders_reflect_created_order():
    c, user, _ = signup("account.summary")
    order_id = checkout(c)
    summary = c.get("/api/account/summary").json()
    assert summary["order_count"] == 1
    orders = c.get("/api/account/orders").json()["items"]
    assert any(o["id"] == order_id for o in orders)
    detail = c.get(f"/api/account/orders/{order_id}").json()
    assert detail["id"] == order_id
    assert detail["delivery"] is None  # not paid/dispatched yet


def test_account_order_detail_is_owner_only():
    c1, _, _ = signup("owner1")
    order_id = checkout(c1)
    c2, _, _ = signup("owner2")
    r = c2.get(f"/api/account/orders/{order_id}")
    assert r.status_code == 404


def test_admin_mark_paid_triggers_dispatch_assignment():
    c, _, _ = signup("dispatch.test")
    order_id = checkout(c, pincode="560001")
    admin = TestClient(app)
    admin_login(admin)
    r = admin.put(f"/api/admin/orders/{order_id}/status", json={"status": "paid"})
    assert r.status_code == 200, r.text
    assert r.json()["delivery"]["dispatch_source"] in ("office_direct", "regional_hub")
    assert r.json()["delivery"]["status"] == "assigned"
    r = admin.put(f"/api/admin/orders/{order_id}/delivery", json={"status": "dispatched", "tracking_number": "TRACK123"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "dispatched"
    assert r.json()["tracking_number"] == "TRACK123"
    order_detail = c.get(f"/api/account/orders/{order_id}").json()
    assert order_detail["delivery"]["status"] == "dispatched"


def test_admin_orders_listing_and_filter():
    c, _, _ = signup("admin.orders.test")
    order_id = checkout(c)
    admin = TestClient(app)
    admin_login(admin)
    r = admin.get("/api/admin/orders")
    assert r.status_code == 200
    assert any(o["id"] == order_id for o in r.json()["items"])
    r = admin.get("/api/admin/orders?status=created")
    assert all(o["status"] == "created" for o in r.json()["items"])
    assert any(o["id"] == order_id for o in r.json()["items"])


def test_feedback_create_list_and_admin_update():
    c, _, _ = signup("feedback.test")
    order_id = checkout(c)
    r = c.post("/api/account/feedback", json={"order_id": order_id, "subject": "Late delivery", "message": "Please expedite", "rating": 3})
    assert r.status_code == 200, r.text
    fid = r.json()["id"]
    items = c.get("/api/account/feedback").json()["items"]
    assert any(f["id"] == fid for f in items)
    admin = TestClient(app)
    admin_login(admin)
    r = admin.get("/api/admin/feedback")
    assert any(f["id"] == fid for f in r.json()["items"])
    r = admin.put(f"/api/admin/feedback/{fid}", json={"status": "resolved"})
    assert r.status_code == 200


def test_feedback_rejects_order_not_owned():
    c1, _, _ = signup("fbowner1")
    order_id = checkout(c1)
    c2, _, _ = signup("fbowner2")
    r = c2.post("/api/account/feedback", json={"order_id": order_id, "subject": "Not mine"})
    assert r.status_code == 404


def test_admin_user_detail_includes_orders_and_feedback():
    c, user, _ = signup("admin.detail.test")
    checkout(c)
    admin = TestClient(app)
    admin_login(admin)
    r = admin.get(f"/api/admin/users/{user['id']}")
    assert r.status_code == 200, r.text
    assert r.json()["order_count"] == 1


def test_auth_history_recorded_for_signup_and_login():
    c, user, email = signup("history.test")
    r = TestClient(app).post("/api/auth/login", json={"email": email, "password": "Passw0rd123"})
    assert r.status_code == 200
    c.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    history = c.get("/api/account/auth-history").json()["items"]
    assert any(e["event_type"] == "signup" for e in history)
    assert any(e["event_type"] == "login_success" for e in history)
    admin = TestClient(app)
    admin_login(admin)
    r = admin.get("/api/admin/auth-logs")
    assert r.status_code == 200
    assert any(e["user_id"] == user["id"] for e in r.json()["items"])



def test_customer_session_expires_after_four_hours_idle():
    from app.db import connect
    c, user, _ = signup("idle.customer")
    token = c.headers["Authorization"].split(" ", 1)[1]
    with connect() as db:
        db.execute("UPDATE auth_sessions SET last_activity_at=? WHERE session_id=(SELECT json_extract(?, '$.sid'))", (int(__import__('time').time()) - 4 * 60 * 60 - 1, __import__('json').dumps(__import__('app.auth', fromlist=['decode_token']).decode_token(token))))
    r = c.get('/api/auth/me')
    assert r.status_code == 401
    assert '4 hours' in r.json()['detail']


def test_admin_session_expires_after_four_hours_idle():
    from app.db import connect
    c = TestClient(app)
    token = admin_login(c)
    with connect() as db:
        db.execute("UPDATE auth_sessions SET last_activity_at=? WHERE session_id=(SELECT json_extract(?, '$.sid'))", (int(__import__('time').time()) - 4 * 60 * 60 - 1, __import__('json').dumps(__import__('app.auth', fromlist=['decode_token']).decode_token(token))))
    r = c.get('/api/admin/catalog')
    assert r.status_code == 401


def test_razorpay_redirect_uses_requested_url():
    c = TestClient(app)
    assert __import__('app.db', fromlist=['get_payment_settings']).get_payment_settings()['razorpay_checkout_url'] == 'https://pages.razorpay.com/tifa'
