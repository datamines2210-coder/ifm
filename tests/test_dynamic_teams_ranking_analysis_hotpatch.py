from pathlib import Path
R=Path("app/scorer/router.py").read_text();H=Path("static/scorer.html").read_text()
def block(): return R[R.index('@router.get("/teams/rankings")'):R.index('@router.post("/teams")')]
def test_dynamic_pairs(): assert "status='completed' AND match_type='doubles'" in block() and "SELECT id,name FROM teams" not in block() and "if len(ids)!=2: continue" in block()
def test_one_match(): assert 'item["matches"] >= 2' not in block() and 'items.append(item)' in block()
def test_rank_order(): assert 'return (-x["win_rate"],wp is None,-(wp or 0),err is None' in R and "win_rate_then_win_points_avg_per_game_then_lowest_error_avg_per_game" in R
def test_date_filter(): assert 'start_date: str = "", end_date: str = ""' in block() and "q.set('start_date',date);q.set('end_date',date)" in H
def test_missing_telemetry(): assert 'if games else None' in block() and "v===null||v===undefined?'—'" in H
def test_analysis(): assert '"error_breakdown":breakdown' in R and "Team Performance Analysis" in H and "Improvement area:" in H
def test_saved_team_admin_untouched(): assert '@router.post("/teams")' in R and '@router.put("/teams/{team_id}/players")' in R
