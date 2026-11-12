from app.scorer.engines.expenses.calculations import _money_split, _expense_period_dates
from app.scorer.engines.matches.contracts import CompletedMatchFact
import pytest

def test_paise_allocation():
    split = _money_split(10, ['b','a','c'])
    assert round(sum(split.values()), 2) == 10
    assert split['a'] == 3.34

def test_expense_period_bounds():
    assert _expense_period_dates('custom','2026-10-01','2026-10-02')[0].isoformat() == '2026-10-01'

def test_only_completed_match_facts():
    with pytest.raises(ValueError):
        CompletedMatchFact('m',0,('p',),status='live')

def test_legacy_api_remains_registered():
    from app.main import app
    paths = {route.path for route in app.routes}
    assert '/api/scorer/expenses/jobs' in paths
    assert '/api/scorer/players' in paths
    assert '/scorer' in paths
