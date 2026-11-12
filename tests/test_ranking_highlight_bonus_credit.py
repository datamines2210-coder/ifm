from pathlib import Path
import inspect
from app.scorer import router
H=Path("static/scorer.html").read_text(encoding="utf-8")
def src(): return inspect.getsource(router._ranking_result)
def test_skill_level_header():
 assert "<th>Skill Level</th>" in H
 assert "<th>Profile (Level)</th>" not in H
def test_algorithm_highlight_templates():
 assert "who controls error best is" in H
 assert "who produces the most winning points is" in H
 assert "who performs best against their skill-level benchmark is" in H
def test_all_period_labels_supported():
 for x in ["'day'","'week'","'month'","'year'","'selected period'"]: assert x in H
def test_benchmark_bonus_can_exceed_100():
 s=src()
 assert "return min(1.5, 1.0 + 0.5*((low-value)/low))" in s
 assert "return min(1.5, 1.0 + 0.5*((value-high)/base))" in s
def test_component_bonus_is_safely_capped():
 assert src().count("min(1.5") >= 2
