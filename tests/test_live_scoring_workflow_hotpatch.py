import inspect
from app.scorer import database, router

def test_point_does_not_auto_complete_match():
    src=inspect.getsource(database.add_point)
    assert "status='completed'" not in src
    assert "_apply_game_completion" in src

def test_error_and_point_share_completion_engine():
    assert "_apply_game_completion" in inspect.getsource(database.add_point)
    assert "_apply_game_completion" in inspect.getsource(database.adjust_error)

def test_complete_validates_expected_score():
    src=inspect.getsource(router.complete_match_atomic)
    assert "expected_score" in src
    assert "Final score changed on the server" in src
