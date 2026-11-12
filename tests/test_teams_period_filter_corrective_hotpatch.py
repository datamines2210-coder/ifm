from pathlib import Path
H=Path("static/scorer.html").read_text()
def test_period_state_exists():
    assert "let teamsPeriodMode='all'" in H
def test_period_range_all_today_week_month_year_custom():
    for token in ["mode==='all'","mode==='today'","mode==='week'","mode==='month'","mode==='year'","mode==='custom'"]:
        assert token in H
def test_request_sends_dates():
    assert "q.set('start_date',range.start)" in H
    assert "q.set('end_date',range.end)" in H
    assert "'/teams/rankings'+(q.toString()?'?'+q.toString():'')" in H
def test_old_unfiltered_loader_removed():
    assert "async function loadTeams(){try{const d=await api('/teams/rankings');" not in H
def test_filter_change_reloads():
    assert "function setTeamsPeriod(mode)" in H and "loadTeams()" in H
def test_custom_date_control_present():
    assert 'id="teamsDate"' in H and 'onchange="loadTeams()"' in H
