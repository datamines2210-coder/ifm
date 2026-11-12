from pathlib import Path
import inspect
from app.scorer import router
H=Path("static/scorer.html").read_text()
def test_headers():
 assert "Performance Score vs Expected (%)</th>" in H
 a=H.index("Performance Score vs Expected (%)</th>"); assert "<th>Profile (Level)</th>" in H[a:a+700]
def test_profile_level_only():
 assert "${esc(x.skill_level||'—')}" in H
 s=inspect.getsource(router._ranking_result); assert 'item["skill_level"]' in s and "Closest:" not in s
def test_no_calculated_level():
 s=inspect.getsource(router._ranking_result); assert 'x["ranking_status"]=b["level"]' not in s
