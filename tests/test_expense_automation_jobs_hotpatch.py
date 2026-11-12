from pathlib import Path
R=Path("app/scorer/router.py").read_text();D=Path("app/scorer/database.py").read_text();H=Path("static/scorer.html").read_text();S=Path("app/scorer/expense_scheduler.py").read_text()
def test_config_items(): assert "expense_items" in D and '@router.post("/expenses/config/items")' in R and "Drinks" in D and "Fruits" in D
def test_court_rule(): assert '1 if n<=7 else (2 if n<=11 else 3)' in R
def test_two_sources(): assert "status='completed'" in R and "schedule_batch_id<>''" in R and "Match History + Create Games" in R
def test_hours(): assert 'max(ends)-min(starts)' in R and '/1800' in R
def test_idempotency(): assert 'idem=f"auto:{expense_date}:v1"' in R and "idempotency_key=?" in R
def test_job_scopes(): assert 'pattern=r"^(today|weekly|monthly|yearly|custom)$"' in R and '@router.post("/expenses/jobs/run")' in R
def test_scheduler(): assert "now.hour>=12" in S and "trigger_type=\"scheduled\"" in S
def test_manual_retained(): assert "Manual Generate Expense (Optional / On Demand)" in H and 'onclick="generateExpense()"' in H
def test_separate_workflows(): assert '@router.get("/expenses/records")' in R and '@router.get("/expenses/report")' in R and '@router.get("/expenses/profile/{player_id}")' in R
def test_docs_location(): assert Path("docs/SCORER_EXPENSE_AUTOMATION_JOBS_HOTPATCH.md").exists()
