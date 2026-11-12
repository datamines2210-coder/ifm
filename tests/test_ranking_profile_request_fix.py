from pathlib import Path
R=Path("app/scorer/router.py").read_text(encoding="utf-8")
def ranking_source():
    a=R.index("def _ranking_result(")
    b=R.index("\ndef _performance_group_bounds",a)
    return R[a:b]
def test_missing_helper_removed():
    assert "list_players(" not in ranking_source()
def test_profile_level_uses_existing_rows_helper():
    s=ranking_source()
    assert 'rows("SELECT id, skill_level FROM players")' in s
    assert 'item["skill_level"]' in s
def test_three_algorithms_remain_supported():
    assert '{"algo_1","algo_2","algo_3"}' in ranking_source()
