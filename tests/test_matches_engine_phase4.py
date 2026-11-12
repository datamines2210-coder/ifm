import ast
from pathlib import Path

def test_matches_repository_exports_legacy_transactions():
    from app.scorer.engines.matches import repository
    from app.scorer import database
    for name in repository.__all__:
        assert getattr(repository, name) is getattr(database, name), name

def test_router_imports_matches_repository_and_preserves_routes():
    source=Path(__file__).resolve().parents[1].joinpath('app/scorer/router.py').read_text()
    tree=ast.parse(source)
    assert 'from .engines.matches.repository import (' in source
    for route in ('/matches/{match_id}/point','/matches/{match_id}/undo','/matches/{match_id}/complete','/matches/{match_id}/error','/matches/{match_id}/score-adjust'):
        assert route in source
    assert tree
