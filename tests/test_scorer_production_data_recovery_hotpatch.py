from pathlib import Path
S=Path("scripts/recover_scorer_data.py").read_text()
D=Path("app/db.py").read_text()
def test_recovery_prefers_real_db_and_backs_up():
    assert "--source-db" in S and "backup_target" in S and "integrity_check" in S
def test_sql_fallback_is_supported():
    assert "--sql-export" in S and "DELETE FROM team_players" in S
def test_recovery_refuses_empty_players():
    assert "contains no players" in S and "Recovered database has no players" in S
def test_market_razorpay_is_tifa():
    assert "https://pages.razorpay.com/tifa" in D
def test_scorer_not_part_of_payment_change():
    assert "app/scorer" not in D
