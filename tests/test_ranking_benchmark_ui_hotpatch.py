from pathlib import Path

def _html():
    return Path("static/scorer.html").read_text(encoding="utf-8")

def test_benchmarks_is_valid_selector_state():
    h=_html()
    assert "['algo_1','algo_2','algo_3','benchmarks'].includes(value)" in h
    assert "if(rankingAlgorithm==='benchmarks')return loadBenchmarkReference()" in h

def test_benchmark_and_security_are_separate_cards():
    h=_html()
    marker='Reset Defaults</button></div></div><div class="card"><h3>Security Operations</h3>'
    assert marker in h

def test_benchmark_reference_table_columns_present():
    h=_html()
    for label in ('Rank','Level','Expected Score','SF/Game','SRE/Game','UE+FE/Game','WP/Game'):
        assert f'<th>{label}</th>' in h
