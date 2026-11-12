from pathlib import Path
h=Path('static/scorer.html').read_text()
r=Path('app/scorer/router.py').read_text()
def test_period_variable_fixed():
    assert "const period=expensePeriod||'today'" in h
    assert 'currentExpensePeriod||' not in h
def test_job_pagination_and_report():
    assert 'limit: int=10' in r
    assert '/expenses/jobs/{job_id}/report' in r
    assert 'expenseJobsPage=1' in h
def test_daily_manual_visibility():
    assert 'expenseDailyManualSection' in h
    assert "expensePeriod==='today'?'':'none'" in h
def test_scheduler_is_opt_in():
    s=Path('app/scorer/expense_scheduler.py').read_text()
    assert 'SCORER_EXPENSE_SCHEDULER_ENABLED' in s
