from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def admin_login(c=client):
    r=c.post("/api/travel/auth/login",json={"email":"travel-admin@example.invalid","password":"ChangeMe-Travel-Admin-123!"})
    assert r.status_code == 200
    token=r.json()["token"]
    c.headers.update({"Authorization":"Bearer "+token})
    return token


def test_travel_health():
    r = client.get("/api/travel/health")
    assert r.status_code == 200
    assert r.json()["service"] == "travel"


def test_travel_packages_seeded():
    r = client.get("/api/travel/packages")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 3
    assert any("Holiday" in i["title"] for i in items)


def test_travel_package_requires_admin():
    r = client.post("/api/travel/packages", json={"title": "New Package"})
    assert r.status_code == 401


def test_travel_package_crud_as_admin():
    c = TestClient(app)
    admin_login(c)
    r = c.post("/api/travel/packages", json={"title": "Beach Retreat", "category": "Package", "duration": "4 days"})
    assert r.status_code == 200
    pid = r.json()["id"]
    r = c.put(f"/api/travel/packages/{pid}", json={"title": "Beach Retreat Deluxe"})
    assert r.status_code == 200
    assert r.json()["title"] == "Beach Retreat Deluxe"
    r = c.delete(f"/api/travel/packages/{pid}")
    assert r.status_code == 200
    r = c.put(f"/api/travel/packages/{pid}", json={"title": "Gone"})
    assert r.status_code == 404


def test_travel_inquiry_public_and_listed_by_admin():
    r = client.post("/api/travel/inquiries", json={"name": "Asha", "email": "asha@example.com", "message": "Interested in Kerala trip"})
    assert r.status_code == 200
    c = TestClient(app)
    admin_login(c)
    r = c.get("/api/travel/inquiries")
    assert r.status_code == 200
    assert any(i["name"] == "Asha" for i in r.json()["items"])
