from pathlib import Path
HTML=Path("static/scorer.html").read_text(encoding="utf-8")
def test_renderer_does_not_use_missing_fmt():
    a=HTML.index("async function loadBenchmarkReference"); b=HTML.index("async function loadRankings",a)
    assert "fmt(" not in HTML[a:b] and "benchmarkNumber(" in HTML[a:b]
def test_admin_view_id_is_correct():
    assert "if(v==='admin'&&isAdmin())" in HTML
    assert "if(v==='administration'&&isAdmin())" not in HTML
def test_selector_and_reference_branch_exist():
    assert "['algo_1','algo_2','algo_3','benchmarks'].includes(value)" in HTML
    assert "rankingAlgorithm==='benchmarks'" in HTML
