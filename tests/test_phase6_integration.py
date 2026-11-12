"""Phase 6 isolated SQLite and API contract smoke/regression tests.

Runs against temporary SQLite only; never opens the production database.
"""
import sqlite3
import pytest
from fastapi.testclient import TestClient
from app.scorer import database as db

@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'scorer-test.db')
    db.init_db()
    return db

@pytest.fixture
def players(isolated_db):
    return [isolated_db.create_player({'name': f'Phase6 Player {i}'}) for i in range(4)]

def test_database_schema_and_foreign_keys(isolated_db):
    with isolated_db.connect() as c:
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {'players','matches','games','point_events','match_player_stats','expense_sessions','expense_participants','expense_jobs','expense_ledger'} <= tables
        assert c.execute('PRAGMA foreign_keys').fetchone()[0] == 1
        assert c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'

def test_point_undo_and_completed_match_idempotency(isolated_db, players):
    a, b = players[:2]
    mid = isolated_db.create_match({'match_type':'singles','best_of':1,'player_a1_id':a,'player_b1_id':b})
    assert isolated_db.add_point(mid, 'A', player_id=a)['score_a'] == 1
    assert isolated_db.undo_point(mid)['score_a'] == 0
    with pytest.raises(ValueError, match='not complete'):
        isolated_db.complete_live_match(mid)
    for _ in range(21):
        result = isolated_db.add_point(mid, 'A', player_id=a)
    assert result['score_a'] == 21
    assert isolated_db.complete_live_match(mid)['winner_side'] == 'A'
    assert isolated_db.complete_live_match(mid)['already_completed'] is True
    with isolated_db.connect() as c:
        assert c.execute('SELECT COUNT(*) FROM point_events WHERE match_id=?',(mid,)).fetchone()[0] == 21
        assert c.execute('SELECT points FROM match_player_stats WHERE match_id=? AND player_id=?',(mid,a)).fetchone()[0] == 21
        assert c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'

def test_error_event_and_undo_consistency(isolated_db, players):
    a,b=players[:2]
    mid=isolated_db.create_match({'match_type':'singles','best_of':1,'player_a1_id':a,'player_b1_id':b})
    result=isolated_db.add_point(mid,'A',event_type='error',error_type='service_error',player_id=a,opponent_player_id=b)
    assert result['score_a'] == 0 and result['score_b'] == 0
    with isolated_db.connect() as c:
        assert c.execute('SELECT service_faults FROM match_player_stats WHERE match_id=? AND player_id=?',(mid,a)).fetchone()[0] == 1
    assert isolated_db.undo_point(mid)['undone_error_type']=='service_error'
    with isolated_db.connect() as c:
        assert c.execute('SELECT service_faults FROM match_player_stats WHERE match_id=? AND player_id=?',(mid,a)).fetchone()[0] == 0

def test_period_statistics_read_only(isolated_db, players):
    from app.scorer.engines.statistics.repository import period_stats
    with isolated_db.connect() as c:
        before=c.total_changes
    result=period_stats(0,4102444800)
    assert result is not None
    with isolated_db.connect() as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'

def test_api_routes_and_authentication_boundary(isolated_db):
    from app.main import app
    client=TestClient(app)
    assert client.get('/scorer').status_code == 200
    for path in ['/api/scorer/players','/api/scorer/matches','/api/scorer/statistics','/api/scorer/expenses/jobs']:
        assert client.get(path).status_code in (401,403), path
    paths={r.path for r in app.routes}
    assert {'/api/scorer/matches/{match_id}/point','/api/scorer/matches/{match_id}/undo','/api/scorer/matches/{match_id}/complete','/api/scorer/rankings','/api/scorer/expenses/jobs'} <= paths

def test_scorer_runtime_no_market_travel_sports_imports():
    from pathlib import Path
    import app
    root=Path(app.__file__).resolve().parent
    assert not (root/'market').exists()
    assert not (root/'travel').exists()
    assert not (root/'sports').exists()
