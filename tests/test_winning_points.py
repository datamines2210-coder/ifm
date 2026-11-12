from pathlib import Path
from app.scorer import router as scorer_router


def test_ranking_uses_win_points_average_before_win_rate(monkeypatch):
    fake = {"player_stats": [
        {"id":"a","name":"Alpha","matches":2,"wins":1,"games":2,"points":8,"service_faults":1,"service_returns":1,"unforced_errors":1,"forced_errors":1},
        {"id":"b","name":"Beta","matches":2,"wins":2,"games":2,"points":5,"service_faults":1,"service_returns":1,"unforced_errors":1,"forced_errors":1},
    ]}
    monkeypatch.setattr(scorer_router, "period_stats", lambda *a, **k: fake)
    data = scorer_router._ranking_result("yearly", year=2026)
    assert [x["name"] for x in data["items"]] == ["Alpha", "Beta"]
    assert data["items"][0]["win_points_avg_per_game"] == 4.0


def test_winning_points_frontend_contract():
    html=Path("static/scorer.html").read_text(encoding="utf-8")
    assert "<th>Win points avg/game</th><th>Error avg/game</th>" in html
    assert "id=\"winningPointsGraph\"" in html
    assert ">Winning Points</span>" in html
    assert "addWinningPoint" in html
    assert "Winning Points" in html
    assert ".score-player-name{font-size:14px;font-weight:800" in html


def test_error_counters_do_not_change_winning_points_or_score(monkeypatch):
    from app.scorer import database as db
    # Covered end-to-end by scorer tests; this contract guards the implementation path.
    source=Path("app/scorer/database.py").read_text(encoding="utf-8")
    block=source[source.index("def adjust_error"):source.index("def decrement_side_point")]
    assert "SET points=points+1" not in block
    assert "UPDATE games SET score_a=score_a+" not in block

def test_selected_player_average_includes_winning_points():
    source=Path("app/scorer/database.py").read_text(encoding="utf-8")
    assert '"winning_points": round(sum(x["points"] for x in player_totals.values())/games, 2)' in source

def test_completion_requires_mandatory_values_frontend_and_backend():
    html=Path("static/scorer.html").read_text(encoding="utf-8")
    assert "Game results do not determine a match winner." in html
    router=Path("app/scorer/router.py").read_text(encoding="utf-8")
    assert "Match winner is required before completing the match" in router
    assert "Winner is required for every game before completing the match" in router

def test_today_ranking_period_and_player_highlight(monkeypatch):
    from datetime import timedelta
    fake={"player_stats":[{"id":"m","name":"Mukund","matches":1,"wins":1,"games":1,"points":9,"service_faults":0,"service_returns":0,"unforced_errors":0,"forced_errors":0}]}
    monkeypatch.setattr(scorer_router,"period_stats",lambda *a,**k: fake)
    data=scorer_router._ranking_result("today")
    assert data["period"]=="today"
    assert data["start_date"]==data["end_date"]
    assert data["items"][0]["name"]=="Mukund"
    html=Path("static/scorer.html").read_text(encoding="utf-8")
    assert "showRankingPeriod('today')\">Today" in html
    assert "Today · 12:00 AM to 11:59 PM" in html
    assert "The player of the ${periodLabel} is" in html
    assert "period==='yearly'?'year'" in html
