import time
import uuid

from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_token
from app.db import (
    log_auth_event, list_auth_logs, list_archived_auth_logs,
    archive_old_auth_logs, purge_old_archived_auth_logs, delete_auth_logs_by_filter,
)

client = TestClient(app)


def admin_login(c=client):
    token = create_token("admin", "administrator", role="admin")
    c.headers.update({"Authorization": "Bearer " + token})
    return token


def test_archive_old_auth_logs_moves_rows_past_cutoff():
    user_id = f"usr_{uuid.uuid4().hex[:10]}"
    now = int(time.time())
    old_id = f"log_{uuid.uuid4().hex[:10]}"
    recent_id = f"log_{uuid.uuid4().hex[:10]}"
    log_auth_event(old_id, now - 400 * 86400, "login_success", True, user_id, "old@example.com")
    log_auth_event(recent_id, now, "login_success", True, user_id, "recent@example.com")
    archived = archive_old_auth_logs(now - 365 * 86400)
    assert archived >= 1
    live = [dict(r) for r in list_auth_logs(user_id=user_id)]
    archive = [dict(r) for r in list_archived_auth_logs(user_id=user_id)]
    assert any(r["id"] == recent_id for r in live)
    assert not any(r["id"] == old_id for r in live)
    assert any(r["id"] == old_id for r in archive)


def test_purge_old_archived_auth_logs_deletes_past_four_years():
    user_id = f"usr_{uuid.uuid4().hex[:10]}"
    now = int(time.time())
    ancient_id = f"log_{uuid.uuid4().hex[:10]}"
    log_auth_event(ancient_id, now - 5 * 365 * 86400, "login_success", True, user_id, "ancient@example.com")
    archive_old_auth_logs(now - 365 * 86400)
    assert any(r["id"] == ancient_id for r in list_archived_auth_logs(user_id=user_id))
    purged = purge_old_archived_auth_logs(now - 4 * 365 * 86400)
    assert purged >= 1
    assert not any(r["id"] == ancient_id for r in list_archived_auth_logs(user_id=user_id))


def test_admin_auth_log_archive_endpoint_lists_archived_events():
    user_id = f"usr_{uuid.uuid4().hex[:10]}"
    now = int(time.time())
    old_id = f"log_{uuid.uuid4().hex[:10]}"
    log_auth_event(old_id, now - 400 * 86400, "login_success", True, user_id, "old2@example.com")
    archive_old_auth_logs(now - 365 * 86400)
    admin = TestClient(app)
    admin_login(admin)
    r = admin.get(f"/api/admin/auth-logs/archive?user_id={user_id}")
    assert r.status_code == 200
    assert any(e["id"] == old_id for e in r.json()["items"])


def test_admin_cleanup_weekly_preset_deletes_archive_only():
    user_id = f"usr_{uuid.uuid4().hex[:10]}"
    now = int(time.time())
    old_id = f"log_{uuid.uuid4().hex[:10]}"
    log_auth_event(old_id, now - 400 * 86400, "login_success", True, user_id, "cleanup@example.com")
    archive_old_auth_logs(now - 365 * 86400)
    admin = TestClient(app)
    admin_login(admin)
    r = admin.post("/api/admin/auth-logs/cleanup", json={"mode": "yearly", "target": "archive"})
    assert r.status_code == 200, r.text
    assert r.json()["deleted"]["archive"] >= 1
    assert not any(e["id"] == old_id for e in list_archived_auth_logs(user_id=user_id))


def test_admin_cleanup_custom_range_requires_bounds():
    admin = TestClient(app)
    admin_login(admin)
    r = admin.post("/api/admin/auth-logs/cleanup", json={"mode": "custom", "target": "live"})
    assert r.status_code == 400


def test_admin_cleanup_custom_range_deletes_live_events_in_window():
    user_id = f"usr_{uuid.uuid4().hex[:10]}"
    now = int(time.time())
    target_id = f"log_{uuid.uuid4().hex[:10]}"
    log_auth_event(target_id, now - 5000, "login_success", True, user_id, "custom@example.com")
    admin = TestClient(app)
    admin_login(admin)
    r = admin.post("/api/admin/auth-logs/cleanup", json={
        "mode": "custom", "target": "live", "start_at": now - 6000, "end_at": now - 4000,
    })
    assert r.status_code == 200, r.text
    assert r.json()["deleted"]["live"] >= 1
    assert not any(e["id"] == target_id for e in list_auth_logs(user_id=user_id))


def test_delete_auth_logs_by_filter_both_targets():
    user_id = f"usr_{uuid.uuid4().hex[:10]}"
    now = int(time.time())
    live_id = f"log_{uuid.uuid4().hex[:10]}"
    log_auth_event(live_id, now, "login_success", True, user_id, "both@example.com")
    deleted = delete_auth_logs_by_filter("both", now - 10, now + 10)
    assert deleted["live"] >= 1


def test_four_year_event_is_retained_in_archive():
    user_id = f"usr_{uuid.uuid4().hex[:10]}"
    now = int(time.time())
    event_id = f"log_{uuid.uuid4().hex[:10]}"
    log_auth_event(event_id, now - (3 * 365 + 30) * 86400, "logout", True, user_id, "retained@example.com")
    archive_old_auth_logs(now - 365 * 86400)
    purge_old_archived_auth_logs(now - 4 * 365 * 86400)
    assert any(r["id"] == event_id for r in list_archived_auth_logs(user_id=user_id))
