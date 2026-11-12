from pathlib import Path
import inspect
from app.scorer import router
H=Path("static/scorer.html").read_text(encoding="utf-8")
def src(): return inspect.getsource(router._ranking_result)
def test_header():
 assert "Performance vs Expected</th>" in H
 assert "Performance Score vs Expected</th>" not in H
def test_profile_is_preserved_from_period_stats():
 s=src(); assert 'item.get("player_id")' not in s and 'player_profiles=' not in s
def test_all_algorithms_use_same_population():
 s=src()
 assert s.index("qualified=[]") < s.index('if algorithm=="algo_3"')
 assert s.index("qualified.append(item)") < s.index('if algorithm=="algo_3"')
 assert 'ranking=sorted(qualified' in s
def test_only_completed_match_is_population_gate():
 assert 'if int(item.get("matches",0) or 0) < 1:' in src()
