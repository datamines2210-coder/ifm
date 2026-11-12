from pathlib import Path
import inspect
from app.scorer import router
H=Path("static/scorer.html").read_text()
def test_separate_bottom_benchmark_section():
 assert H.index('benchmark-admin-section')>H.index('<h3>Match Data Export</h3>')
def test_best_fit_status_and_strict_qualifier():
 s=inspect.getsource(router._ranking_result);assert "Closest:" in s and "benchmark_qualified" in s
def test_score_two_decimals():
 assert "Number(x.benchmark_score).toFixed(2)" in H
