from pathlib import Path
H=Path("static/scorer.html").read_text(encoding="utf-8")
def test_algo3_highlight_removes_benchmark_word():
 assert "who performs best at their skill level is" in H
 assert "who performs best against their skill-level benchmark is" not in H
def test_algo3_explanation_uses_skill_level_wording():
 assert "ranks players by performance at their skill level" in H
def test_admin_benchmark_configuration_name_is_retained():
 assert "Performance Benchmarks" in H
 assert ">Benchmarks<" in H
def test_other_algorithm_highlights_unchanged():
 assert "who controls error best is" in H
 assert "who produces the most winning points is" in H
