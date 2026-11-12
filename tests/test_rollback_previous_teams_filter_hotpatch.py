from pathlib import Path
H=Path("static/scorer.html").read_text()
def test_previous_expense_automation_ui_restored():
    assert "Automated Expense Workflow" in H
    assert "Manual Generate Expense (Optional / On Demand)" in H
def test_previous_teams_loader_restored():
    assert "async function loadTeams()" in H
def test_scorer_shell_preserved():
    assert "Badminton Scorer" in H and 'id="teams"' in H
