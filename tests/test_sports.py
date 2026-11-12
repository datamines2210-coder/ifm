from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def admin_login(c=client):
    r=c.post("/api/sports/auth/login",json={"email":"sports-admin@example.invalid","password":"ChangeMe-Sports-Admin-123!"})
    assert r.status_code == 200
    token=r.json()["token"]
    c.headers.update({"Authorization":"Bearer "+token})
    return token


def test_sports_health():
    r = client.get("/api/sports/health")
    assert r.status_code == 200
    assert r.json()["service"] == "sports"


def test_sports_communities_seeded():
    r = client.get("/api/sports/communities")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 5
    assert any(i["key"] == "badminton" for i in items)


def test_sports_posts_seeded_and_filterable():
    r = client.get("/api/sports/posts")
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 3
    r = client.get("/api/sports/posts?post_type=blog")
    assert r.status_code == 200
    assert all(i["post_type"] == "blog" for i in r.json()["items"])


def test_sports_community_requires_admin():
    r = client.post("/api/sports/communities", json={"key": "golf", "name": "Golf"})
    assert r.status_code == 401


def test_sports_community_crud_as_admin():
    c = TestClient(app)
    admin_login(c)
    r = c.post("/api/sports/communities", json={"key": "golf", "name": "Golf", "icon": "⛳"})
    assert r.status_code == 200
    cid = r.json()["id"]
    r = c.put(f"/api/sports/communities/{cid}", json={"key": "golf", "name": "Golf Club"})
    assert r.status_code == 200
    assert r.json()["name"] == "Golf Club"
    r = c.delete(f"/api/sports/communities/{cid}")
    assert r.status_code == 200
    r = c.put(f"/api/sports/communities/{cid}", json={"key": "golf", "name": "Gone"})
    assert r.status_code == 404


def test_sports_inquiry_public_and_listed_by_admin():
    r = client.post("/api/sports/inquiries", json={"name": "Ravi", "sport": "badminton", "message": "Looking for a doubles partner"})
    assert r.status_code == 200
    c = TestClient(app)
    admin_login(c)
    r = c.get("/api/sports/inquiries")
    assert r.status_code == 200
    assert any(i["name"] == "Ravi" for i in r.json()["items"])
