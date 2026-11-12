from datetime import datetime, timezone

import app.scorer.router as router


def test_performance_grouping_is_calendar_aligned():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, tzinfo=timezone.utc)
    groups = router._performance_group_bounds(start, end, "monthly")
    assert [g["label"] for g in groups] == ["Week1", "Week2", "Week3", "Week4", "Week5"]
    assert all(groups[i]["end"] == groups[i + 1]["start"] for i in range(len(groups) - 1))
    assert groups[0]["start"] == start
    assert groups[-1]["end"] == end


def test_yearly_performance_has_one_bucket_per_month():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2027, 1, 1, tzinfo=timezone.utc)
    groups = router._performance_group_bounds(start, end, "yearly")
    assert len(groups) == 12
    assert [g["label"] for g in groups] == [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]


def test_selected_player_average_uses_error_count_and_player_games(monkeypatch):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, tzinfo=timezone.utc)
    match = {
        "id": "m1", "created_at": int(datetime(2026, 1, 10, tzinfo=timezone.utc).timestamp()),
        "team_a_id": "", "team_b_id": "", "player_a1_id": "P1", "player_a2_id": "",
        "player_b1_id": "P2", "player_b2_id": "", "winner_side": "A",
    }

    monkeypatch.setattr(router, "_period_bounds", lambda *args, **kwargs: (start, end))
    monkeypatch.setattr(router, "_side_player_ids_from_match", lambda m, side: ["P1"] if side == "A" else ["P2"])
    monkeypatch.setattr(router, "rows", lambda q, args=():
        [match] if "FROM matches" in q else ([{"score_a": 21, "score_b": 10}] if "FROM games" in q else []))
    monkeypatch.setattr(router, "match_detail", lambda mid: {
        "player_stats": [
            {"id": "P1", "side": "A", "service_faults": 2, "service_returns": 1, "unforced_errors": 4, "forced_errors": 0},
            {"id": "P2", "side": "B", "service_faults": 0, "service_returns": 0, "unforced_errors": 0, "forced_errors": 3},
        ],
        "events": [
            {"player_id": "P1", "error_type": "unforced_error", "error_count": 4},
            {"player_id": "P1", "error_type": "service_error", "error_count": 2},
            {"player_id": "P1", "error_type": "service_return", "error_count": 1},
        ],
    })

    result = router.statistics_performance(period="monthly", player="P1", _=None)
    active = next(g for g in result["groups"] if g["matches"])
    assert active["player_games"] == 1
    assert active["averages_per_game"]["service_faults"] == 2.0
    assert active["averages_per_game"]["service_returns"] == 1.0
    assert active["averages_per_game"]["unforced_errors"] == 4.0
    assert active["averages_per_game"]["total_errors"] == 7.0


def test_all_player_average_uses_player_game_denominator(monkeypatch):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, tzinfo=timezone.utc)
    match = {
        "id": "m1", "created_at": int(datetime(2026, 1, 10, tzinfo=timezone.utc).timestamp()),
        "team_a_id": "", "team_b_id": "", "player_a1_id": "P1", "player_a2_id": "",
        "player_b1_id": "P2", "player_b2_id": "", "winner_side": "A",
    }
    monkeypatch.setattr(router, "_period_bounds", lambda *args, **kwargs: (start, end))
    monkeypatch.setattr(router, "_side_player_ids_from_match", lambda m, side: ["P1"] if side == "A" else ["P2"])
    monkeypatch.setattr(router, "rows", lambda q, args=():
        [match] if "FROM matches" in q else ([{"score_a": 21, "score_b": 10}] if "FROM games" in q else []))
    monkeypatch.setattr(router, "match_detail", lambda mid: {
        "player_stats": [
            {"id": "P1", "side": "A", "service_faults": 2, "service_returns": 0, "unforced_errors": 4, "forced_errors": 0},
            {"id": "P2", "side": "B", "service_faults": 0, "service_returns": 0, "unforced_errors": 0, "forced_errors": 2},
        ],
        "events": [],
    })

    result = router.statistics_performance(period="monthly", _=None)
    active = next(g for g in result["groups"] if g["matches"])
    assert active["player_games"] == 2
    assert active["averages_per_game"]["service_faults"] == 1.0
    assert active["averages_per_game"]["unforced_errors"] == 2.0
    assert active["averages_per_game"]["forced_errors"] == 1.0
    assert active["averages_per_game"]["total_errors"] == 4.0

def test_selected_player_monthly_uses_canonical_stats_and_game_denominator(monkeypatch):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, tzinfo=timezone.utc)
    match = {"id":"m_fix","created_at":int(datetime(2026,1,18,tzinfo=timezone.utc).timestamp()),"team_a_id":"","team_b_id":"","player_a1_id":"P1","player_a2_id":"","player_b1_id":"P2","player_b2_id":"","winner_side":"A"}
    monkeypatch.setattr(router, "_period_bounds", lambda *a, **k: (start, end))
    monkeypatch.setattr(router, "_side_player_ids_from_match", lambda m, side: ["P1"] if side == "A" else ["P2"])
    games=[{"score_a":21,"score_b":10},{"score_a":18,"score_b":21},{"score_a":21,"score_b":17}]
    monkeypatch.setattr(router, "rows", lambda q, args=(): [match] if "FROM matches" in q else (games if "FROM games" in q else []))
    monkeypatch.setattr(router, "match_detail", lambda mid: {"player_stats":[{"id":"P1","side":"A","points":30,"service_faults":3,"service_returns":6,"unforced_errors":9,"forced_errors":0}],"events":[{"player_id":"P1","error_type":"service_error","error_count":1163277341},{"player_id":"P1","error_type":"unforced_error","error_count":2326554682}]})
    result=router.statistics_performance(period="monthly", player="P1", _=None)
    active=next(g for g in result["groups"] if g["matches"])
    assert active["player_games"] == 3
    assert active["averages_per_game"]["service_faults"] == 1.0
    assert active["averages_per_game"]["service_returns"] == 2.0
    assert active["averages_per_game"]["unforced_errors"] == 3.0
    assert active["averages_per_game"]["total_errors"] == 6.0
