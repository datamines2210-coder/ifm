import inspect
from app.scorer import router

def test_ranking_router_supports_algorithm_parameter():
    assert "algorithm" in inspect.signature(router.rankings).parameters

def test_ranking_no_longer_requires_two_matches_or_metric_game():
    src=inspect.getsource(router._ranking_result)
    assert 'matches",0) or 0) < 2' not in src
    assert 'games < 1' not in src
    assert 'matches",0) or 0) < 1' in src
