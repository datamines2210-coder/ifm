from datetime import datetime, timezone, timedelta
import app.scorer.router as router


def _stats():
    return {"player_stats":[
        {"name":"Error Control","games":10,"metric_games":10,"matches":5,"wins":3,"points":50,"service_faults":2,"service_returns":2,"unforced_errors":3,"forced_errors":3},
        {"name":"Winner","games":10,"metric_games":10,"matches":5,"wins":4,"points":80,"service_faults":5,"service_returns":5,"unforced_errors":8,"forced_errors":8},
    ]}


def _patch(monkeypatch):
    start=datetime(2026,10,1,tzinfo=timezone.utc)
    monkeypatch.setattr(router,"_period_bounds",lambda *a,**k:(start,start+timedelta(days=1)))
    monkeypatch.setattr(router,"period_stats",lambda *a,**k:_stats())


def test_algo_1_preserves_error_first(monkeypatch):
    _patch(monkeypatch)
    d=router._ranking_result(algorithm="algo_1")
    assert d["algorithm_label"]=="Algo_1 (Error)"
    assert d["items"][0]["name"]=="Error Control"


def test_algo_2_prioritizes_winning_points(monkeypatch):
    _patch(monkeypatch)
    d=router._ranking_result(algorithm="algo_2")
    assert d["items"][0]["name"]=="Winner"


def test_algo_3_exposes_benchmark_metrics(monkeypatch):
    _patch(monkeypatch)
    d=router._ranking_result(algorithm="algo_3")
    assert d["algorithm_label"]=="Algo_3 (DUPR)"
    assert all(0 <= x["benchmark_score"] <= 100 for x in d["items"])
    assert all("service_return_errors_avg_per_game" in x for x in d["items"])


def test_ranking_requires_two_matches_and_metric_game(monkeypatch):
    start=datetime(2026,10,1,tzinfo=timezone.utc)
    monkeypatch.setattr(router,"_period_bounds",lambda *a,**k:(start,start+timedelta(days=1)))
    sample={"player_stats":[
        {"name":"One Match","games":3,"metric_games":3,"matches":1,"wins":1,"points":20,"service_faults":0,"service_returns":0,"unforced_errors":0,"forced_errors":0},
        {"name":"Score Only","games":4,"metric_games":0,"matches":2,"wins":1,"points":0,"service_faults":0,"service_returns":0,"unforced_errors":0,"forced_errors":0},
        {"name":"Qualified","games":4,"metric_games":2,"matches":2,"wins":1,"points":12,"service_faults":1,"service_returns":1,"unforced_errors":1,"forced_errors":1},
    ]}
    monkeypatch.setattr(router,"period_stats",lambda *a,**k:sample)
    d=router._ranking_result(algorithm="algo_1")
    assert [x["name"] for x in d["items"]] == ["Qualified"]
    assert d["items"][0]["win_points_avg_per_game"] == 6.0
