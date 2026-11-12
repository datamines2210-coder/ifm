"""Compatibility and engine ownership regression checks."""
from app.scorer.engines.expenses import service
from app.scorer import router


def test_router_uses_expense_engine_implementations():
    for name in ("_expense_snapshot", "_expense_audit", "_match_players_for_date", "_expense_session_item", "_expense_activity_for_day", "_upsert_automatic_expense", "_run_expense_job"):
        assert getattr(router, name) is getattr(service, name)


def test_expense_engine_does_not_import_http_router():
    from pathlib import Path
    source = Path(service.__file__).read_text()
    assert "from ...router" not in source
    assert "@router." not in source


def test_existing_expense_api_routes_preserved():
    paths = {r.path for r in router.router.routes}
    assert "/api/scorer/expenses/jobs/run" in paths
    assert "/api/scorer/expenses/jobs" in paths
    assert "/api/scorer/expenses/jobs/{job_id}/report" in paths
    assert "/api/scorer/expenses/report" in paths
