from pathlib import Path
R=Path("app/scorer/router.py").read_text()
def block(): return R[R.index('@router.get("/teams/rankings")'):R.index('@router.post("/teams")')]
def test_wins_are_primary_team_ranking_key():
    assert 'return (-x["wins"],-x["win_rate"],wp is None,-(wp or 0),err is None' in block()
def test_requested_contract_label():
    assert '"wins_then_win_rate_then_win_points_avg_per_game_then_lowest_error_avg_per_game"' in block()
def test_tiebreakers_preserved():
    assert '-x["matches"],x["error_total"],x["name"].lower()' in block()
def test_dynamic_team_identity_preserved():
    assert 'name":f"Team_{pair_numbers.get(key, 0)}"' in block()
def test_period_filter_preserved():
    assert 'start_date: str = "", end_date: str = ""' in block()
