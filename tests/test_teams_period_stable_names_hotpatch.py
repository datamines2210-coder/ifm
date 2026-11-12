from pathlib import Path
R=Path("app/scorer/router.py").read_text()
H=Path("static/scorer.html").read_text()
def team_block(): return R[R.index('@router.get("/teams/rankings")'):R.index('@router.post("/teams")')]
def test_history_style_period_options():
 for x in ["All Time","Today","This Week","This Month","This Year","Custom Date"]: assert x in H
 assert '<select id="teamsPeriod"' in H
def test_all_time_default():
 assert '<option value="all">All Time</option>' in H
 assert "let teamsPeriodMode='all'" in H
def test_period_ranges():
 for x in ["mode==='today'","mode==='week'","mode==='month'","mode==='year'","mode==='custom'"]: assert x in H
 assert "q.set('start_date',range.start)" in H and "q.set('end_date',range.end)" in H
def test_stable_names_come_from_all_time_history():
 b=team_block()
 assert "pair_numbers={}" in b and "next_pair_number=1" in b
 assert "SELECT id FROM matches WHERE status='completed' AND match_type='doubles' ORDER BY" in b
 assert 'name":f"Team_{pair_numbers.get(key, 0)}"' in b
def test_names_not_rank_numbers():
 b=team_block()
 assert 'item["rank"]=index' in b
 assert 'item["name"]=f"Team_{index}"' not in b
def test_players_remain_visible():
 assert "<th>Team</th><th>Players</th>" in H
 assert "t.players.map(p=>esc(p.name)).join(' / ')" in H
def test_ranking_logic_preserved():
 assert 'return (-x["win_rate"],wp is None,-(wp or 0),err is None' in R
