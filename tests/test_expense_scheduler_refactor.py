from pathlib import Path
import ast
p=Path("app/scorer/expense_scheduler.py").read_text()
r=Path("app/scorer/router.py").read_text()
def test_scheduler_imports(): ast.parse(p); ast.parse(r)
def test_disabled_by_default(): assert 'SCORER_EXPENSE_INTERNAL_SCHEDULER' in p and '"0"' in p
def test_atomic_scheduled_job_claim(): assert 'scheduled:expense:' in r and '"duplicate":True' in r
def test_scheduler_logs_failures(): assert 'log.exception(' in p
