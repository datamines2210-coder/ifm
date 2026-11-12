from pathlib import Path
r=Path(__file__).resolve().parents[1]
def test_job_api_contract():
 s=(r/'app/scorer/router.py').read_text()
 assert 'def expense_jobs(page: int=1, limit: int=10' in s
 assert '@router.get("/expenses/jobs/{job_id}/report")' in s
 assert 'progress=? WHERE id=?' in s
def test_daily_manual_and_report():
 s=(r/'static/scorer.html').read_text()
 assert "manual.style.display=expensePeriod==='today'" in s
 assert "matched.has(p.id)?'selected'" not in s
 assert 'downloadAllExpensePlayers' in s
