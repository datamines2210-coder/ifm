"""Phase 5: compatibility facade contract tests."""
import ast
from pathlib import Path

def test_facades_preserve_function_identity():
    from app.scorer import database as db
    from app.scorer.core import persistence, administration
    from app.scorer.engines.statistics import repository as stats
    for name in ("connect", "row", "rows", "init_db"):
        assert getattr(persistence, name) is getattr(db, name)
    for name in ("log_rows", "create_album_item", "delete_player_account"):
        assert getattr(administration, name) is getattr(db, name)
    for name in ("player_stats", "period_stats", "list_performance_benchmarks"):
        assert getattr(stats, name) is getattr(db, name)

def test_router_preserves_public_routes_and_uses_facades():
    source=Path(__file__).resolve().parents[1].joinpath("app/scorer/router.py").read_text()
    ast.parse(source)
    assert "from .core.persistence import" in source
    assert "from .core.administration import" in source
    assert "from .engines.statistics.repository import" in source
    for route in ("/matches/{match_id}/point", "/matches/{match_id}/undo", "/expenses/jobs/run"):
        assert route in source

def test_statistics_and_expenses_use_own_boundaries():
    base=Path(__file__).resolve().parents[1]/"app/scorer/engines"
    assert "from .repository import period_stats" in (base/"statistics/service.py").read_text()
    assert "from ...core.persistence import" in (base/"expenses/service.py").read_text()
